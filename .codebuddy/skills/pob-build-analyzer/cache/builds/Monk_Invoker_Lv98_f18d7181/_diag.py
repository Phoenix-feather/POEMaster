"""系统诊断光环分析数值链路"""
import sys, logging
logging.basicConfig(level=logging.WARNING)
sys.path.insert(0, '.codebuddy/skills/pob-build-analyzer')
from pob_calc import POBCalculator

calc = POBCalculator.from_current()
lua = calc._lua
from pob_calc.calculator import calculate as calc_fn

lua.execute('_spike_build.mainSocketGroup = 7')

# === Phase 1: 测量各阶段的 DPS ===
# 1a. auto_configure 后（含 sim mod + charge 配置）
bl_raw = calc_fn(lua, calc._calcs)
print(f'[1a] auto_configure后 baseline: {bl_raw["TotalDPS"]:.0f}')

# 1b. 查看 configTab.modList 中的 sim mod
sim_mods = lua.execute(r"""
local ml = _spike_build.configTab.modList
local lines = {}
for _, m in ipairs(ml) do
    if string.find(m.source or '', 'sim') then
        lines[#lines+1] = string.format('%s %s %s val=%s', m.name, m.type, m.source, tostring(m.value))
    end
end
if #lines == 0 then lines[#lines+1] = '(none)' end
return table.concat(lines, '\n')
""")
print(f'[1b] configTab.modList sim mods:')
for line in sim_mods.split('\n'):
    print(f'      {line}')

# 1c. 查看 configTab.input 中的条件配置
configs = lua.execute(r"""
local lines = {}
for k, v in pairs(_spike_build.configTab.input or {}) do
    if v ~= nil and v ~= false then
        lines[#lines+1] = k .. '=' .. tostring(v)
    end
end
if #lines == 0 then lines[#lines+1] = '(none)' end
return table.concat(lines, '\n')
""")
print(f'[1c] configTab.input conditions:')
for line in configs.split('\n'):
    print(f'      {line}')

# === Phase 2: 测试手动移除每个 sim mod 后的 DPS ===
print('\n=== Phase 2: 逐个移除 sim mod 测试 ===')
from pob_calc.what_if import _rebuild_config_tab_modlist

for src_name in ['EC_sim', 'CI_crit_sim', 'CI_speed_sim', 'Zenith_II_sim', 'UA_Unbound']:
    # 移除该 mod
    lua.execute(f"""
local ml = _spike_build.configTab.modList
for i = #ml, 1, -1 do
    if ml[i].source == '{src_name}' then
        table.remove(ml, i)
    end
end
""")
    _rebuild_config_tab_modlist(lua)
    bl_test = calc_fn(lua, calc._calcs)
    delta = (bl_raw["TotalDPS"] - bl_test["TotalDPS"]) / bl_test["TotalDPS"] * 100 if bl_test["TotalDPS"] > 0 else 0
    print(f'  移除 {src_name:20s}: DPS={bl_test["TotalDPS"]:8.0f} -> 失去 {delta:+.1f}%')
    
    # 恢复: 通过 _inject_unimplemented_mods 重新注入
    from pob_calc.build_loader import _inject_unimplemented_mods
    _inject_unimplemented_mods(lua, '{}')
    _rebuild_config_tab_modlist(lua)

# 验证恢复
bl_verify = calc_fn(lua, calc._calcs)
print(f'\n  恢复后 baseline: {bl_verify["TotalDPS"]:.0f} (应为 {bl_raw["TotalDPS"]:.0f})')

# === Phase 3: 模拟 aura_spirit_analysis 的流程 ===
print('\n=== Phase 3: 模拟 aura_spirit_analysis 流程 ===')
from pob_calc.what_if import (
    _query_active_skills_info, _discover_ifskill_configs,
    _inject_ifskill_defaults, _merge_unimplemented_effects,
    _test_remove_skill_group, _test_mod_effect, _resolve_inject_mods,
)

skills_info = _query_active_skills_info(lua, None)
aura_names = {si["main_skill_name"] for si in skills_info if si["is_aura"]}
print(f'[3a] Aura names: {aura_names}')

configs_found = _discover_ifskill_configs(lua, aura_names)
for c in configs_found:
    print(f'      {c["aura_name"]}/{c["config_var"]} max={c["actual_max"]:.0f}')

# 注入 ifSkill 默认值
_inject_ifskill_defaults(lua, None, aura_configs=configs_found)
bl_ifskill = calc_fn(lua, calc._calcs)
print(f'[3b] 注入 ifSkill 默认值后: {bl_ifskill["TotalDPS"]:.0f}')

# 合并未实现效果
inject_config = _merge_unimplemented_effects(lua)
print(f'[3c] inject_config keys: {list(inject_config.keys())}')

# 测试每个光环
for si in skills_info:
    if not si["is_aura"]:
        continue
    name = si["main_skill_name"]
    inject_mods = inject_config.get(name)
    
    if inject_mods:
        # sim mod path
        resolved = _resolve_inject_mods(lua, None, inject_mods, name)
        r = _test_mod_effect(lua, calc._calcs, bl_ifskill, resolved, name)
        print(f'  {name:25s} [sim_mod] dps_pct={r["dps_pct"]:+.1f}% simulated={r.get("simulated")}')
    else:
        # standard remove path
        r = _test_remove_skill_group(lua, calc._calcs, si["group_idx"], bl_ifskill,
            skill_name=name, aura_only=False)
        print(f'  {name:25s} [remove]  dps_pct={r["dps_pct"]:+.1f}% simulated={r.get("simulated")}')
