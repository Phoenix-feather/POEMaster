"""完整分析编排层。

职责：
- full_analysis: 单技能完整分析流程（向后兼容）
- full_build_analysis: 多技能×多套装完整分析（新入口）
- extract_global_data / strip_global_data: 全局数据分离
- _find_socket_group_by_skill_name / _find_best_dps_socket_group
"""
import logging
import re
from .calculator import calculate as calc_fn, get_main_skill
from .sensitivity import sensitivity_analysis, _detect_skill_flags
from .sensitivity import SENSITIVITY_PROFILES
from .sensitivity import _DEFENCE_PROFILES, _RECOVERY_PROFILES
from .sensitivity import _FIXED_SOURCE_PROFILES, _ATTACK_ONLY_PROFILES
from .sensitivity import _SPELL_ONLY_PROFILES, _PROJECTILE_ONLY_PROFILES
from .sensitivity import _DOT_ONLY_PROFILES
from .dps_breakdown import dps_breakdown
from .aura_analysis import aura_spirit_analysis
from .passive_analysis import passive_node_analysis, passive_node_exploration
from .passive_analysis import diagnose_jewels
from .defence import (defence_overview, resource_overview,
                      life_recovery_analysis, mana_recovery_analysis)

logger = logging.getLogger(__name__)

# 全局字段（从 full_analysis 结果中提取到 global.json）
_GLOBAL_FIELDS = {
    "defence_overview", "defence_sensitivity",
    "resource_overview", "life_recovery", "mana_recovery",
    "recovery_sensitivity",
}

# =============================================================================
# 完整分析流程
# =============================================================================


def _find_socket_group_by_skill_name(lua, calcs, skill_name: str) -> tuple:
    """按技能名称（模糊匹配）查找技能组号。

    支持自然语言输入：大小写不敏感，支持部分匹配。
    例如 "ball lightning", "Ball Lightning", "ball" 都能匹配到 Ball Lightning。

    Returns:
        (group_index, matched_name, dps) 或 (None, None, 0)
    """
    # 规范化搜索词
    needle = skill_name.strip().lower()

    result = lua.execute('''
        local build = _spike_build
        local groups = build.skillsTab.socketGroupList
        local original = build.mainSocketGroup
        local entries = {}

        for i = 1, #groups do
            build.mainSocketGroup = i
            local ok, err = pcall(function()
                local env = calcs.initEnv(build, "MAIN")
                calcs.perform(env)
                local ms = env.player.mainSkill
                local name = "?"
                if ms and ms.activeEffect and ms.activeEffect.grantedEffect then
                    name = ms.activeEffect.grantedEffect.name or "?"
                end
                local dps = env.player.output.TotalDPS or 0
                entries[#entries+1] = tostring(i) .. "\\1" .. name .. "\\1" .. tostring(dps)
            end)
        end

        build.mainSocketGroup = original
        return table.concat(entries, "\\2")
    ''')

    if not result:
        return (None, None, 0)

    entries = str(result).split('\2')
    best_match = None

    for entry in entries:
        parts = entry.split('\1')
        if len(parts) < 3:
            continue
        idx = int(parts[0])
        name = parts[1]
        dps = float(parts[2])
        name_lower = name.lower()

        # 精确匹配
        if name_lower == needle:
            return (idx, name, dps)

        # 部分匹配：搜索词包含在技能名中，或技能名包含搜索词
        if needle in name_lower or name_lower in needle:
            if best_match is None or dps > best_match[2]:
                best_match = (idx, name, dps)

    if best_match:
        return best_match
    return (None, None, 0)


def _find_best_dps_socket_group(lua, calcs) -> tuple:
    """扫描所有技能组，找到 TotalDPS 最大的组号。

    Returns:
        (group_index, dps) 或 (None, 0) 如果没有 DPS 技能
    """
    result = lua.execute('''
        local build = _spike_build
        local groups = build.skillsTab.socketGroupList
        local best_group = nil
        local best_dps = 0
        local original = build.mainSocketGroup

        for i = 1, #groups do
            build.mainSocketGroup = i
            local ok, err = pcall(function()
                local env = calcs.initEnv(build, "MAIN")
                calcs.perform(env)
                local dps = env.player.output.TotalDPS or 0
                if dps > best_dps then
                    best_dps = dps
                    best_group = i
                end
            end)
        end

        -- 恢复原始
        build.mainSocketGroup = original
        return tostring(best_group or 0) .. "|" .. tostring(best_dps)
    ''')

    if result:
        parts = str(result).split('|')
        try:
            group = int(parts[0])
            dps = float(parts[1]) if len(parts) > 1 else 0
            return (group, dps) if group > 0 else (None, 0)
        except (ValueError, IndexError):
            pass
    return (None, 0)


# =============================================================================
# 完整分析流程（单技能，向后兼容）
# =============================================================================


def full_analysis(lua, calcs, target_pct: float = 20.0,
                  exploration_min_pct: float = 0.5,
                  skill_name: str = None) -> dict:
    """完整构筑分析流程。

    一次调用完成所有分析，无需临时脚本。

    Args:
        target_pct: 灵敏度分析的 DPS 增幅目标（默认 20%）
        exploration_min_pct: 天赋探索最低阈值（默认 0.5%）
        skill_name: 指定主技能名称（自然语言，大小写不敏感，支持部分匹配）。
                    例如 "ball lightning"、"Comet"、"ball"。
                    若为 None，使用构筑默认主技能；若默认 DPS=0 则自动选最高 DPS 技能。

    Returns:
        {
            "baseline": {stat: value},
            "main_skill": {"name": str, "castTime": float},
            "skill_flags": {"is_spell": bool, "is_projectile": bool, ...},
            "sensitivity": [灵敏度分析结果列表],
            "talent_value": [已分配天赋价值列表],
            "talent_exploration": [未分配天赋探索列表],
            "jewel_diagnosis": [珠宝诊断列表],
            "dps_breakdown": {DPS 来源拆解},
            "aura_spirit": {光环与精魄分析, 详见 aura_spirit_analysis()},
        }
    """
    # 0. 如果指定了 skill_name，按名称查找技能组
    if skill_name:
        group, matched, dps = _find_socket_group_by_skill_name(
            lua, calcs, skill_name)
        if group is not None:
            lua.execute(f'_spike_build.mainSocketGroup = {group}')
            logger.info("按名称切换到技能组 %d: %s (DPS=%.0f)",
                        group, matched, dps)
        else:
            logger.warning("未找到匹配 '%s' 的技能，使用默认", skill_name)

    # 1. 基线计算
    baseline = calc_fn(lua, calcs)

    # 如果 TotalDPS=0（且未指定 skill_name），自动扫描所有技能组找到最大 DPS 的
    if baseline.get("TotalDPS", 0) == 0 and not skill_name:
        best_group, best_dps = _find_best_dps_socket_group(lua, calcs)
        if best_group is not None and best_dps > 0:
            lua.execute(f'_spike_build.mainSocketGroup = {best_group}')
            baseline = calc_fn(lua, calcs)
            logger.info("自动切换到技能组 %d (DPS=%.0f)", best_group, best_dps)

    logger.info("基线计算完成: TotalDPS=%.0f", baseline.get("TotalDPS", 0))

    # 2. 主技能信息
    main_skill = get_main_skill(lua, calcs)
    logger.info("主技能: %s", main_skill.get("name", "?"))

    # 3. 技能 flags
    skill_flags = _detect_skill_flags(lua, calcs)

    # 4. 灵敏度分析（仅进攻 profile，排除防御、恢复和来源固定）
    _excluded_from_offence = _DEFENCE_PROFILES | _RECOVERY_PROFILES | _FIXED_SOURCE_PROFILES

    # 基于技能 flags 排除不适用的 profile
    if skill_flags["is_spell"]:
        _excluded_from_offence |= _ATTACK_ONLY_PROFILES
    else:
        _excluded_from_offence |= _SPELL_ONLY_PROFILES
    if not skill_flags["is_projectile"]:
        _excluded_from_offence |= _PROJECTILE_ONLY_PROFILES
    if not skill_flags["is_dot"]:
        _excluded_from_offence |= _DOT_ONLY_PROFILES

    _offence_only_profiles = [k for k in SENSITIVITY_PROFILES if k not in _excluded_from_offence]
    sens = sensitivity_analysis(
        lua, calcs,
        profiles=_offence_only_profiles,
        target_pct=target_pct,
        baseline=baseline,
    )
    logger.info("灵敏度分析完成: %d 个 profile", len(sens))

    # 5. 天赋价值分析
    talent_value = passive_node_analysis(lua, calcs, baseline=baseline)
    logger.info("天赋价值分析完成: %d 个节点", len(talent_value))

    # 6. 天赋探索分析
    talent_exploration = passive_node_exploration(
        lua, calcs, baseline=baseline,
        min_dps_pct=exploration_min_pct,
    )
    logger.info("天赋探索完成: %d 个候选节点", len(talent_exploration))

    # 7. 珠宝诊断
    jewel_diag = diagnose_jewels(lua, calcs, baseline=baseline)
    logger.info("珠宝诊断完成: %d 个珠宝", len(jewel_diag))

    # 8. DPS 来源拆解
    dps_bd = dps_breakdown(lua, calcs, baseline=baseline)
    logger.info("DPS 拆解完成: %d 个公式项", len(dps_bd["formula_items"]))

    # 9. 光环与精魄分析（传入 dps_breakdown 以引用构筑已有 modifier）
    aura_spirit = aura_spirit_analysis(
        lua, calcs, baseline=baseline, skill_flags=skill_flags,
        dps_breakdown=dps_bd)
    logger.info("光环与精魄分析完成")

    # 10. 防御概览（纯 output 读取，零 Lua 交互）
    defence_ov = defence_overview(baseline)
    logger.info("防御概览完成")

    # 11. 防御灵敏度分析（复用 sensitivity_analysis 框架，target_stat=TotalEHP）
    def_sens = sensitivity_analysis(
        lua, calcs,
        profiles=list(_DEFENCE_PROFILES),
        target_stat="TotalEHP",
        target_pct=target_pct,
        baseline=baseline,
    )
    logger.info("防御灵敏度分析完成: %d 个 profile", len(def_sens))

    # 12. 资源面分析（纯 output 读取，零 Lua 交互）
    res_ov = resource_overview(baseline)
    life_recov = life_recovery_analysis(baseline)
    mana_recov = mana_recovery_analysis(baseline)
    logger.info("资源面分析完成")

    # 13. 恢复增强灵敏度（复用 sensitivity_analysis 框架，各 profile 独立 target_stat）
    recovery_sens = sensitivity_analysis(
        lua, calcs,
        profiles=list(_RECOVERY_PROFILES),
        target_pct=target_pct,
        baseline=baseline,
    )
    logger.info("恢复灵敏度分析完成: %d 个 profile", len(recovery_sens))

    return {
        "baseline": baseline,
        "main_skill": main_skill,
        "skill_flags": skill_flags,
        "sensitivity": sens,
        "talent_value": talent_value,
        "talent_exploration": talent_exploration,
        "jewel_diagnosis": jewel_diag,
        "dps_breakdown": dps_bd,
        "aura_spirit": aura_spirit,
        "defence_overview": defence_ov,
        "defence_sensitivity": def_sens,
        "resource_overview": res_ov,
        "life_recovery": life_recov,
        "mana_recovery": mana_recov,
        "recovery_sensitivity": recovery_sens,
    }


# =============================================================================
# 全局数据提取（构筑级，不随技能切换变化）
# =============================================================================


def _extract_build_attributes(baseline: dict) -> dict:
    """从 baseline 提取构筑属性（不随技能变化的属性）。

    排除模拟值（AccuracyHitChance/StunAvoidChance），返回整数。
    """
    attrs = {}
    for k in ("TotalAttr", "Str", "Dex", "Int", "Accuracy"):
        if k in baseline:
            v = baseline[k]
            attrs[k] = int(round(v)) if isinstance(v, float) else v
    return attrs


def _extract_jewel_overview(jewel_diagnosis: list) -> list:
    """从 jewel_diagnosis 提取珠宝概览（含词条及 DPS/EHP 影响）。"""
    overview = []
    for j in (jewel_diagnosis or []):
        overview.append({
            "name": j.get("name", ""),
            "base_type": j.get("base_type", ""),
            "rarity": j.get("rarity", ""),
            "slot_name": j.get("slot_name", ""),
            "granted_passives": j.get("granted_passives", []),
            "mods": j.get("mods", []),
            "status": j.get("status"),
        })
    return overview


# 伤害构成元素配置（模块级常量）
_ELEM_HIT_CONFIG = [
    ("Lightning", "LightningHitAverage", "LightningCritAverage", "LightningEnemyDamage"),
    ("Cold", "ColdHitAverage", "ColdCritAverage", "ColdEnemyDamage"),
    ("Fire", "FireHitAverage", "FireCritAverage", "FireEnemyDamage"),
    ("Physical", "PhysicalHitAverage", "PhysicalCritAverage", "PhysicalEnemyDamage"),
    ("Chaos", "ChaosHitAverage", "ChaosCritAverage", "ChaosEnemyDamage"),
]
_ELEM_LABELS = {
    "Lightning": "\u26a1 \u95ea\u7535", "Cold": "\u2744 \u51b0\u971c",
    "Fire": "\ud83d\udd25 \u706b\u7130", "Physical": "\u2694 \u7269\u7406",
    "Chaos": "\ud83d\udd2e \u6df7\u6c8c",
}
_ELEM_COLORS = {
    "Lightning": "#a78bfa", "Cold": "#60a5fa",
    "Fire": "#f97316", "Physical": "#d4d4d8",
    "Chaos": "#c084fc",
}


def _extract_damage_composition(baseline: dict) -> list:
    """从 baseline 提取伤害构成（每个元素的非暴击/暴击命中，POB 直出）。

    权重基于 HitAverage（进攻侧，已含 INC/MORE/Crit），
    不用 EnemyDamage（那是防御侧字段，衡量构筑承受能力上限）。

    Returns:
        [{ "element": "Lightning", "hit_avg": float, "crit_avg": float,
           "weight_pct": float }, ...]
        按 hit_avg 降序排列。
    """
    elems = []
    for elem, hit_key, crit_key, _enemy_key in _ELEM_HIT_CONFIG:
        hit_avg = baseline.get(hit_key, 0)
        if hit_avg <= 0:
            continue
        crit_avg = baseline.get(crit_key, 0)
        elems.append({
            "element": elem,
            "label": _ELEM_LABELS.get(elem, elem),
            "color": _ELEM_COLORS.get(elem, "#888"),
            "hit_avg": hit_avg,
            "crit_avg": crit_avg,
        })
    # 按 hit_avg 降序排列
    elems.sort(key=lambda e: e["hit_avg"], reverse=True)
    # 计算权重（基于 HitAverage）
    total_hit = sum(e["hit_avg"] for e in elems) or 1
    for e in elems:
        e["weight_pct"] = e["hit_avg"] / total_hit * 100
    return elems


def _extract_build_modifiers(dps_bd: dict) -> dict:
    """从 dps_breakdown 提取通用修饰符汇总（排除 category=Skill）。

    Returns:
        {modifier_key: {"total": float, "sources": [source_dict, ...],
                        "affects": str, "formula_name": str}}
    """
    modifiers = {}
    for item in dps_bd.get("formula_items", []):
        key = item.get("key", "")
        if not key or key == "CombinedDPS":
            continue
        # 过滤掉 EffMult（敌人抗性系数，不适合展示）
        if key.endswith("_EffMult"):
            continue
        # 只保留构筑级别来源：天赋/装备/珠宝
        # 排除 Skill（技能专属如 Cascade）和 Other（模拟注入如 Zenith）
        universal_sources = [
            s for s in item.get("sources", [])
            if s.get("category") in ("Tree", "Item", "Jewel")
        ]
        if not universal_sources:
            continue

        # 重新计算通用来源的总值
        is_more = key.endswith("_MORE")
        if is_more:
            # MORE: 累乘
            total = 1.0
            for s in universal_sources:
                total *= (1 + (s.get("value", 0) / 100))
        else:
            # INC/BASE: 累加
            total = sum(s.get("value", 0) for s in universal_sources)

        # 从 formula_name 提取 affects（例如 "通用伤害 INC (Lightning,Cold,Fire)"）
        fn = item.get("formula_name", "")
        affects = ""
        m = re.search(r'\(([^)]+)\)\s*$', fn)
        if m:
            affects = m.group(1)
        modifiers[key] = {
            "total": total,
            "sources": universal_sources,
            "affects": affects,
            "formula_name": fn,
        }
    return modifiers


def extract_global_data(full_result: dict) -> dict:
    """从 full_analysis 结果中提取全局数据。

    Args:
        full_result: full_analysis() 的完整返回值

    Returns:
        global_data dict，包含 defence/resource/modifiers/attributes/jewels/composition
    """
    baseline = full_result.get("baseline", {})
    dps_bd = full_result.get("dps_breakdown", {})

    return {
        "build_modifiers": _extract_build_modifiers(dps_bd),
        "build_attributes": _extract_build_attributes(baseline),
        "damage_composition": _extract_damage_composition(baseline),
        "defence_overview": full_result.get("defence_overview"),
        "defence_sensitivity": full_result.get("defence_sensitivity"),
        "resource_overview": full_result.get("resource_overview"),
        "life_recovery": full_result.get("life_recovery"),
        "mana_recovery": full_result.get("mana_recovery"),
        "recovery_sensitivity": full_result.get("recovery_sensitivity"),
        "jewel_overview": _extract_jewel_overview(
            full_result.get("jewel_diagnosis")
        ),
    }


def strip_global_data(full_result: dict) -> dict:
    """从 full_analysis 结果中移除全局字段，返回纯技能数据。"""
    skill_data = {}
    for k, v in full_result.items():
        if k not in _GLOBAL_FIELDS:
            skill_data[k] = v
    return skill_data


# =============================================================================
# 多技能 × 多套装完整分析
# =============================================================================


def full_build_analysis(lua, calcs, skills: list[str] = None,
                        weapon_sets: list[int] = None,
                        target_pct: float = 20.0,
                        exploration_min_pct: float = 0.5) -> dict:
    """多技能 × 多套装完整分析。

    Phase 0: 全局分析（防御/资源/恢复/光环/珠宝，每套装一次）
    Phase 1: 技能分析（灵敏度/天赋/DPS拆解，每技能×每套装）
    Phase 2: 套装对比（如果有多套装）

    Args:
        lua: LuaRuntime
        calcs: POB calcs 模块
        skills: 技能名称列表。None = 自动发现所有 DPS>0 的技能
        weapon_sets: 套装列表 [1] 或 [1,2]。None = 自动检测
        target_pct: 灵敏度分析目标 DPS 增幅
        exploration_min_pct: 天赋探索最低阈值

    Returns:
        {
            "weapon_sets": [1] 或 [1,2],
            "ws1": {"global": {...}, "skills": {"spark": {...}, ...}},
            "ws2": {"global": {...}, "skills": {...}},  # 如果有
            "comparison": {...},  # 如果有多套装
        }
    """
    from .lua_env import LuaEnvManager

    env = LuaEnvManager(lua, calcs)

    # 自动检测套装
    if weapon_sets is None:
        weapon_sets = [1, 2] if env.has_weapon_set_2() else [1]

    results = {"weapon_sets": weapon_sets}

    for ws in weapon_sets:
        use_second = (ws == 2)
        with env.weapon_set_scope(use_second):
            # Phase 0: 全局分析（不随技能变化的部分）
            # 用最高 DPS 技能组计算防御/资源基线
            best_group, best_dps = _find_best_dps_socket_group(lua, calcs)
            if best_group is not None and best_dps > 0:
                lua.execute(f'_spike_build.mainSocketGroup = {best_group}')

            global_baseline = env.calc()

            # 用最高 DPS 技能的 dps_breakdown 提取 build_modifiers
            best_dps_bd = dps_breakdown(lua, calcs, baseline=global_baseline)
            best_jewels = diagnose_jewels(lua, calcs, baseline=global_baseline)

            global_data = {
                "baseline": global_baseline,
                "build_modifiers": _extract_build_modifiers(best_dps_bd),
                "build_attributes": _extract_build_attributes(global_baseline),
                "damage_composition": _extract_damage_composition(global_baseline),
                "defence_overview": defence_overview(global_baseline),
                "resource_overview": resource_overview(global_baseline),
                "life_recovery": life_recovery_analysis(global_baseline),
                "mana_recovery": mana_recovery_analysis(global_baseline),
                "jewel_overview": _extract_jewel_overview(best_jewels),
                "defence_sensitivity": sensitivity_analysis(
                    lua, calcs,
                    profiles=list(_DEFENCE_PROFILES),
                    target_stat="TotalEHP",
                    target_pct=target_pct,
                    baseline=global_baseline),
                "recovery_sensitivity": sensitivity_analysis(
                    lua, calcs,
                    profiles=list(_RECOVERY_PROFILES),
                    target_pct=target_pct,
                    baseline=global_baseline),
            }

            # 自动发现该套装下的技能
            ws_skills = skills if skills else env.get_weapon_set_skills(ws)
            if not ws_skills:
                ws_skills = _auto_discover_skills(lua, calcs)

            # Phase 1: 逐技能分析（含光环/珠宝——它们的 DPS 贡献取决于主技能）
            skill_results = {}
            for skill_name in ws_skills:
                with env.skill_scope(skill_name):
                    with env.config_scope():
                        with env.gem_scope():
                            baseline = env.calc()
                            if baseline.get("TotalDPS", 0) == 0:
                                continue

                            skill_flags = _detect_skill_flags(lua, calcs)

                            excluded = (_DEFENCE_PROFILES | _RECOVERY_PROFILES
                                        | _FIXED_SOURCE_PROFILES)
                            if skill_flags["is_spell"]:
                                excluded |= _ATTACK_ONLY_PROFILES
                            else:
                                excluded |= _SPELL_ONLY_PROFILES
                            if not skill_flags["is_projectile"]:
                                excluded |= _PROJECTILE_ONLY_PROFILES
                            if not skill_flags["is_dot"]:
                                excluded |= _DOT_ONLY_PROFILES
                            offence_profiles = [k for k in SENSITIVITY_PROFILES
                                                if k not in excluded]

                            main_skill = get_main_skill(lua, calcs)
                            dps_bd = dps_breakdown(lua, calcs, baseline=baseline)

                            skill_results[main_skill.get("name", skill_name)] = {
                                "baseline": baseline,
                                "main_skill": main_skill,
                                "skill_flags": skill_flags,
                                "sensitivity": sensitivity_analysis(
                                    lua, calcs,
                                    profiles=offence_profiles,
                                    target_pct=target_pct,
                                    baseline=baseline),
                                "talent_value": passive_node_analysis(
                                    lua, calcs, baseline=baseline),
                                "talent_exploration": passive_node_exploration(
                                    lua, calcs, baseline=baseline,
                                    min_dps_pct=exploration_min_pct),
                                "dps_breakdown": dps_bd,
                                "aura_spirit": aura_spirit_analysis(
                                    lua, calcs, baseline=baseline,
                                    skill_flags=skill_flags,
                                    dps_breakdown=dps_bd),
                                "jewel_diagnosis": diagnose_jewels(
                                    lua, calcs, baseline=baseline),
                            }

            results[f"ws{ws}"] = {
                "global": global_data,
                "skills": skill_results,
            }

    # Phase 2: 套装对比
    if len(weapon_sets) > 1 and "ws1" in results and "ws2" in results:
        results["comparison"] = _compare_weapon_sets(
            results["ws1"], results["ws2"])

    return results


def _auto_discover_skills(lua, calcs) -> list[str]:
    """自动发现构筑中所有 DPS>0 的技能名称。"""
    result = lua.execute('''
        local build = _spike_build
        local names = {}
        local seen = {}
        local orig = build.mainSocketGroup
        for i = 1, #build.skillsTab.socketGroupList do
            local g = build.skillsTab.socketGroupList[i]
            if not g.enabled then goto next end
            build.mainSocketGroup = i
            local ok, env = pcall(calcs.initEnv, build, "MAIN")
            if ok then
                pcall(calcs.perform, env)
                local dps = env.player.output.TotalDPS or 0
                if dps > 0 then
                    local ms = env.player.mainSkill
                    local name = ms and ms.activeEffect
                        and ms.activeEffect.grantedEffect
                        and ms.activeEffect.grantedEffect.name
                    if name and not seen[name] then
                        seen[name] = true
                        names[#names+1] = name
                    end
                end
            end
            ::next::
        end
        build.mainSocketGroup = orig
        return table.concat(names, "|")
    ''')
    if result and str(result) != "":
        return str(result).split("|")
    return []


def _compare_weapon_sets(ws1_data: dict, ws2_data: dict) -> dict:
    """生成两个套装间的对比数据。

    Args:
        ws1_data: {"global": {...}, "skills": {...}}
        ws2_data: 同上

    Returns:
        {
            "defence": {"ehp_ws1", "ehp_ws2", "delta_pct"},
            "resource": {"spirit_ws1", "spirit_ws2"},
            "skills": {
                "skill_name": {"dps_ws1", "dps_ws2", "delta_pct"},
            },
            "ws1_only_skills": [...],
            "ws2_only_skills": [...],
            "shared_skills": [...],
        }
    """
    g1 = ws1_data.get("global", {})
    g2 = ws2_data.get("global", {})
    bl1 = g1.get("baseline", {})
    bl2 = g2.get("baseline", {})

    ehp1 = bl1.get("TotalEHP", 0)
    ehp2 = bl2.get("TotalEHP", 0)
    defence_delta = ((ehp2 - ehp1) / ehp1 * 100) if ehp1 > 0 else 0

    spirit1 = bl1.get("SpiritUnreserved", 0)
    spirit2 = bl2.get("SpiritUnreserved", 0)

    # 技能对比
    s1_names = set(ws1_data.get("skills", {}).keys())
    s2_names = set(ws2_data.get("skills", {}).keys())
    shared = s1_names & s2_names
    ws1_only = s1_names - s2_names
    ws2_only = s2_names - s1_names

    skill_comparison = {}
    for name in shared:
        dps1 = (ws1_data["skills"][name].get("baseline", {})
                .get("TotalDPS", 0))
        dps2 = (ws2_data["skills"][name].get("baseline", {})
                .get("TotalDPS", 0))
        delta = ((dps2 - dps1) / dps1 * 100) if dps1 > 0 else 0
        skill_comparison[name] = {
            "dps_ws1": dps1,
            "dps_ws2": dps2,
            "delta_pct": round(delta, 1),
        }

    return {
        "defence": {
            "ehp_ws1": ehp1,
            "ehp_ws2": ehp2,
            "delta_pct": round(defence_delta, 1),
        },
        "resource": {
            "spirit_ws1": spirit1,
            "spirit_ws2": spirit2,
        },
        "skills": skill_comparison,
        "ws1_only_skills": sorted(ws1_only),
        "ws2_only_skills": sorted(ws2_only),
        "shared_skills": sorted(shared),
    }


