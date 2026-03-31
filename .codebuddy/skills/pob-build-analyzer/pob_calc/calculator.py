#!/usr/bin/env python3
"""
POB 计算引擎接口。

职责：
  - calculate:          运行 initEnv + perform，返回 output dict
  - get_active_skills:  获取主动技能列表
  - get_main_skill:     获取主技能信息
"""


def calculate(lua, calcs, mode: str = "MAIN") -> dict[str, float]:
    """运行 POB 计算引擎，返回完整 output。

    Args:
        lua: LuaRuntime 实例
        calcs: POB calcs 模块
        mode: 计算模式 — "MAIN" (默认，已含穿透/敌人抗性), "CALCS", "CALCULATOR"

    Returns:
        {stat_name: value} 字典，仅包含数值型字段

    注：initEnv 对非 "CALCS" 模式默认 buffMode=EFFECTIVE（CalcSetup.lua:579），
    已含 mode_effective=true、mode_buffs=true、mode_combat=true。
    """
    result = lua.execute(f'''
        local build = _spike_build
        local env = calcs.initEnv(build, "{mode}")
        calcs.perform(env)
        local output = env.player.output
        local lines = {{}}
        for k, v in pairs(output) do
            if type(v) == "number" then
                lines[#lines+1] = k .. "=" .. tostring(v)
            end
        end
        -- 额外读取 skillModList 中的 Speed INC（用于门槛效果分析）
        local ms = env.player.mainSkill
        if ms and ms.skillModList and ms.skillCfg then
            local sInc = ms.skillModList:Sum("INC", ms.skillCfg, "Speed")
            lines[#lines+1] = "Speed_INC=" .. tostring(sInc)
            local sMore = ms.skillModList:More(ms.skillCfg, "Speed")
            lines[#lines+1] = "Speed_MORE=" .. tostring(sMore)
        end
        return table.concat(lines, "|")
    ''')

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


def get_active_skills(lua, calcs) -> list[str]:
    """获取构筑中所有主动技能的名称列表。"""
    result = lua.execute('''
        local build = _spike_build
        local env = calcs.initEnv(build, "MAIN")
        calcs.perform(env)
        local names = {}
        for _, sk in ipairs(env.player.activeSkillList) do
            local name = sk.activeEffect and sk.activeEffect.grantedEffect
                and sk.activeEffect.grantedEffect.name or "?"
            names[#names+1] = name
        end
        return table.concat(names, "|")
    ''')

    if result:
        return str(result).split('|')
    return []


def get_main_skill(lua, calcs) -> dict:
    """获取主技能信息。"""
    result = lua.execute('''
        local build = _spike_build
        local env = calcs.initEnv(build, "MAIN")
        calcs.perform(env)
        if env.player.mainSkill then
            local ms = env.player.mainSkill
            local name = ms.activeEffect and ms.activeEffect.grantedEffect
                and ms.activeEffect.grantedEffect.name or "unknown"
            local castTime = ms.skillData and ms.skillData.castTime or 0
            return name .. "|" .. tostring(castTime)
        end
        return "none|0"
    ''')

    if result:
        parts = str(result).split('|')
        return {
            'name': parts[0],
            'castTime': float(parts[1]) if len(parts) > 1 else 0,
        }
    return {'name': 'none', 'castTime': 0}


def compare_with_pob(lua, calcs, build_info: dict, keys: list[str] = None) -> list[dict]:
    """将计算结果与 POB PlayerStats XML 对比。

    Args:
        lua: LuaRuntime
        calcs: POB calcs 模块
        build_info: 包含 playerStats 的 BuildInfo
        keys: 要对比的 stat 名称列表，默认为常见防御/攻击 stat

    Returns:
        [{stat, pob_value, calc_value, delta_pct, match}, ...]
    """
    if keys is None:
        keys = [
            'Life', 'LifeUnreserved', 'Mana', 'ManaUnreserved',
            'Spirit', 'SpiritUnreserved',
            'EnergyShield', 'Evasion', 'Armour',
            'Str', 'Dex', 'Int',
            'FireResist', 'ColdResist', 'LightningResist', 'ChaosResist',
            'ColdResistOverCap',
            'EffectiveMovementSpeedMod',
            'TotalEHP',
            'PhysicalMaximumHitTaken', 'ColdMaximumHitTaken', 'ChaosMaximumHitTaken',
            'LifeRegenRecovery', 'ManaRegenRecovery',
        ]

    outputs = calculate(lua, calcs)
    pob_stats = build_info.get('playerStats', {})

    results = []
    for key in keys:
        pob_val = float(pob_stats.get(key, '0'))
        calc_val = outputs.get(key, 0.0)

        if abs(pob_val) < 0.001 and abs(calc_val) < 0.001:
            delta_pct = 0.0
            match = True
        elif abs(pob_val) > 0.001:
            delta_pct = (calc_val - pob_val) / abs(pob_val) * 100
            match = abs(calc_val - pob_val) < max(0.5, abs(pob_val) * 0.001)
        else:
            delta_pct = 0.0
            match = abs(calc_val - pob_val) < 0.5

        results.append({
            'stat': key,
            'pob_value': pob_val,
            'calc_value': calc_val,
            'delta_pct': delta_pct,
            'match': match,
        })

    return results
