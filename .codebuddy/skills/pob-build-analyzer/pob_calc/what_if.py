"""What-If 分析模块 — re-export 入口 + API 函数。

保持向后兼容：from pob_calc.what_if import X 继续可用。

独立 API 函数（不属于任何分析模块）：
- what_if_mod: 向 modDB 注入 modifier 并对比
- what_if_item: 临时替换装备并对比
- _inject_and_calc: 注入 mod 并计算的底层辅助
- _make_formula: 生成装备词缀公式文本
"""
import logging
from .calculator import calculate

logger = logging.getLogger(__name__)

# ── Re-export: 所有公共函数保持旧 import 路径可用 ──

from .sensitivity import (  # noqa: F401
    sensitivity_analysis,
    SENSITIVITY_PROFILES,
    _detect_skill_flags,
    _cap_all_gem_qualities,
    _restore_gem_qualities,
    GEM_QUALITY_CAP,
    _DEFENCE_PROFILES,
    _RECOVERY_PROFILES,
    _FIXED_SOURCE_PROFILES,
    _ATTACK_ONLY_PROFILES,
    _SPELL_ONLY_PROFILES,
    _PROJECTILE_ONLY_PROFILES,
    _DOT_ONLY_PROFILES,
    _query_all_merged_inc,
    _query_mod_total_single,
    _inject_profile,
    _binary_search_needed_value,
    _diff_outputs,
)

from .dps_breakdown import dps_breakdown  # noqa: F401

from .aura_analysis import (  # noqa: F401
    aura_spirit_analysis,
    _merge_unimplemented_effects,
    _rebuild_config_tab_modlist,
    _set_config_and_rebuild,
    _discover_ifskill_configs,
    _inject_ifskill_defaults,
    _test_aura_config_range,
    _query_active_skills_info,
    _query_total_spirit,
    _test_remove_skill_group,
    _resolve_charge_map,
    _fill_charge_configs,
    _resolve_pre_configs,
    _resolve_inject_mods,
    _test_mod_effect,
    _test_mod_effect_inner,
    _test_add_candidate_aura,
    _test_add_spirit_support,
    _validate_aura_consistency,
)

from .passive_analysis import (  # noqa: F401
    passive_node_analysis,
    passive_node_exploration,
    diagnose_jewels,
    what_if_nodes,
)

from .defence import (  # noqa: F401
    defence_overview,
    resource_overview,
    life_recovery_analysis,
    mana_recovery_analysis,
)

from .report_formatter import (  # noqa: F401
    format_report,
    _format_section7,
    _format_section_defence,
)

from .full_analysis import (  # noqa: F401
    full_analysis,
    extract_global_data,
    strip_global_data,
    _find_socket_group_by_skill_name,
    _find_best_dps_socket_group,
    _extract_build_attributes,
    _extract_jewel_overview,
    _extract_damage_composition,
    _extract_build_modifiers,
)

from .lua_env import LuaEnvManager  # noqa: F401


# ── API 函数（独立于分析模块，保留在此文件中） ──


def _parse_lua_output(result) -> dict:
    """解析 Lua 端返回的 key=value|... 格式 output 为 dict。"""
    outputs = {}
    if result:
        for pair in str(result).split('|'):
            if '=' in pair:
                k, v = pair.split('=', 1)
                try:
                    outputs[k] = float(v)
                except ValueError:
                    pass
    return outputs


def _inject_and_calc(lua, calcs, mod_lines_lua: str, baseline: dict,
                     buff_mode: str = "MAIN") -> dict:
    """注入 modifier(s) 并对比。内部通用函数。

    Args:
        mod_lines_lua: Lua 代码片段，在 initEnv 后、perform 前执行。
                       可以包含多行 env.modDB:NewMod(...)。
        baseline: 基线 output dict
        buff_mode: "MAIN" 或 "EFFECTIVE"

    Returns:
        {stat: (before, after, delta)} 差异字典
    """
    result = lua.execute(f'''
        local build = _spike_build
        local env = calcs.initEnv(build, "{buff_mode}")
{mod_lines_lua}
        calcs.perform(env)
        local output = env.player.output
        local lines = {{}}
        for k, v in pairs(output) do
            if type(v) == "number" then
                lines[#lines+1] = k .. "=" .. tostring(v)
            end
        end
        return table.concat(lines, "|")
    ''')

    after = _parse_lua_output(result)
    return _diff_outputs(baseline, after)



def _make_formula(mod_name: str, mod_type: str, needed_value: float | None,
                  current_total: float, target_pct: float,
                  actual_pct: float, target_label: str = "DPS") -> str:
    """生成一行简洁的增量公式字符串（等基准版本）。

    Args:
        needed_value: 达到目标所需的注入值，None=无法达到
        current_total: 当前 modDB 合并汇总值
        target_pct: 目标增幅百分比
        actual_pct: 实际增幅百分比（二分搜索精度范围内）
        target_label: 目标指标名称（默认 "DPS"，恢复 profile 用恢复指标名）

    Returns:
        如 "INC 238%→297%, 需要 +59 → DPS +30.0%"
    """
    if needed_value is None:
        return f"无法在搜索范围内达到 {target_label} +{target_pct:.0f}%"

    effect_part = f"{target_label} +{actual_pct:.1f}%"

    if mod_type == "INC":
        old_inc = current_total
        new_inc = old_inc + needed_value
        return f"INC {old_inc:.0f}%→{new_inc:.0f}%, 需要 +{needed_value:.0f} → {effect_part}"

    elif mod_type == "MORE":
        more_factor = needed_value
        return f"需要 MORE +{more_factor:.0f}% (×{1+more_factor/100:.2f}) → {effect_part}"

    elif mod_type == "BASE":
        if "Penetration" in mod_name:
            return f"需要 +{needed_value:.0f}% 穿透 → {effect_part}"
        elif mod_name == "ProjectileCount":
            old_base = current_total
            return f"投射物 {old_base:.0f}→{old_base+needed_value:.0f}, 需要 +{needed_value:.0f} → {effect_part}"
        elif mod_name in ("CritChance",):
            old_base = current_total
            return f"baseCrit {old_base:.1f}%→{old_base+needed_value:.1f}%, 需要 +{needed_value:.1f}% → {effect_part}"
        elif mod_name == "CritMultiplier":
            old_base = current_total
            return f"CritBase {old_base:.0f}→{old_base+needed_value:.0f}, 需要 +{needed_value:.0f} → {effect_part}"
        elif "Min+Max" in mod_name:
            max_val = needed_value * 2
            return f"需要添加 {needed_value:.0f}-{max_val:.0f} 基础伤害 → {effect_part}"
        else:
            old_base = current_total
            return f"BASE {old_base:.0f}→{old_base+needed_value:.0f}, 需要 +{needed_value:.0f} → {effect_part}"

    return f"需要 +{needed_value:.1f} → {effect_part}"


def what_if_mod(lua, calcs, mod_name: str, mod_type: str, value: float,
                baseline: dict = None, buff_mode: str = "MAIN") -> dict:
    """向 modDB 注入 modifier 并对比前后变化。

    Args:
        mod_name: modifier 名称 (如 "Life", "Evasion")
        mod_type: modifier 类型 (如 "BASE", "INC", "MORE")
        value: 数值
        baseline: 基线 output，若为 None 则自动计算
        buff_mode: 计算模式 — "MAIN" (默认，不含敌人效果) 或 "EFFECTIVE" (含敌人抗性/穿透)

    Returns:
        {stat: (before, after, delta)} 差异字典
    """
    if baseline is None:
        baseline = calculate(lua, calcs)

    mod_lines = f'        env.modDB:NewMod("{mod_name}", "{mod_type}", {value}, "WhatIf")'
    return _inject_and_calc(lua, calcs, mod_lines, baseline, buff_mode)




def what_if_item(lua, calcs, slot_name: str, item_raw_text: str,
                 baseline: dict = None) -> dict:
    """临时替换装备并对比。

    使用 POB 原生 override.repSlotName / override.repItem 机制。

    Args:
        slot_name: 装备槽位名称 (如 "Helmet", "Body Armour")
        item_raw_text: 新装备的原始文本
        baseline: 基线 output

    Returns:
        {stat: (before, after, delta)} 差异字典
    """
    if baseline is None:
        baseline = calculate(lua, calcs)

    raw_escaped = item_raw_text.replace('\\', '\\\\').replace("'", "\\'").replace('\n', '\\n').replace('\r', '')
    slot_escaped = slot_name.replace("'", "\\'")

    result = lua.execute(f'''
        local build = _spike_build
        local rawText = '{raw_escaped}'
        local ok, newItem = pcall(new, "Item", rawText)
        if not ok or not newItem or not newItem.base then
            return nil
        end
        local override = {{
            repSlotName = '{slot_escaped}',
            repItem = newItem,
        }}
        local env = calcs.initEnv(build, "CALCULATOR", override)
        calcs.perform(env)
        local output = env.player.output
        local lines = {{}}
        for k, v in pairs(output) do
            if type(v) == "number" then
                lines[#lines+1] = k .. "=" .. tostring(v)
            end
        end
        return table.concat(lines, "|")
    ''')

    after = _parse_lua_output(result)
    return _diff_outputs(baseline, after)

