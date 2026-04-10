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


def _test_spirit_support_contributions(lua, calcs, baseline: dict):
    """对构筑中每个精魄辅助做禁用测试，测量实际贡献。

    在干净的 Lua 环境中逐个执行（光环分析之前）。
    """
    base_dps = baseline.get("TotalDPS", 0)
    base_ehp = baseline.get("TotalEHP", 0)
    base_regen = baseline.get("LifeRegenRecovery", 0)

    # 先收集所有精魄辅助的 skillId
    sids_raw = lua.execute(r'''
        local b = _spike_build
        local sids = {}
        for _, g in ipairs(b.skillsTab.socketGroupList) do
            for _, gem in ipairs(g.gemList or {}) do
                local ge = gem.grantedEffect
                    or (gem.gemData and gem.gemData.grantedEffect)
                if ge and ge.support and gem.enabled and gem.skillId then
                    local lv = ge.levels and ge.levels[gem.level or 1]
                    if lv and (lv.spiritReservationFlat or 0) > 0 then
                        sids[#sids+1] = gem.skillId
                    end
                end
            end
        end
        return table.concat(sids, "|")
    ''')

    contribs = {}
    if sids_raw:
        for sid in str(sids_raw).split("|"):
            if not sid:
                continue
            # 每个辅助独立测试：禁用 → 计算 → 恢复
            r = lua.execute(
                'local b = _spike_build\n'
                'for _, g in ipairs(b.skillsTab.socketGroupList) do\n'
                '  for _, gem in ipairs(g.gemList or {}) do\n'
                '    if gem.skillId == "' + sid + '" then\n'
                '      gem.enabled = false\n'
                '      local env = calcs.initEnv(b, "MAIN")\n'
                '      calcs.perform(env)\n'
                '      local o = env.player.output\n'
                '      gem.enabled = true\n'
                '      return string.format("%.2f|%.2f|%.1f",\n'
                '        o.TotalDPS or 0, o.TotalEHP or 0,\n'
                '        o.LifeRegenRecovery or 0)\n'
                '    end\n'
                '  end\n'
                'end\n'
                'return nil')
            if r and str(r) != "nil":
                p = str(r).split("|")
                try:
                    contribs[sid] = {
                        "dps_delta": round(base_dps - float(p[0]), 1),
                        "ehp_delta": round(base_ehp - float(p[1]), 1),
                        "regen_delta": round(base_regen - float(p[2]), 1),
                    }
                except (ValueError, IndexError):
                    pass

    _test_spirit_support_contributions._cache = contribs


_test_spirit_support_contributions._cache = {}


def _test_spirit_support_recommendations(lua, calcs, baseline: dict,
                                          skill_flags: dict = None) -> list:
    """在干净环境中测试精魄辅助推荐。

    必须在 aura_spirit_analysis 之前调用——后者的 _rebuild_config_tab_modlist
    会污染 configTab.modList，导致 calcs.initEnv 读到错误的 modifier。

    本函数复用 aura_analysis 中的候选发现/过滤/测试逻辑，
    但在编排层的干净 baseline 环境下执行。

    Args:
        lua: LuaRuntime
        calcs: POB calcs 模块
        baseline: 干净环境下的基线 output
        skill_flags: 技能 flags

    Returns:
        精魄辅助测试结果列表（与 aura_spirit_analysis 7C 格式一致）
    """
    from .aura_analysis import (
        _query_active_skills_info,
        _query_total_spirit,
        discover_spirit_supports,
        merge_candidates,
        filter_spirit_supports,
        _test_add_spirit_support,
        _SPIRIT_SUPPORT_CANDIDATES,
    )

    is_attack = skill_flags.get("is_attack", False) if skill_flags else False
    is_spell = skill_flags.get("is_spell", True) if skill_flags else True

    # 查询光环技能组
    skills_info = _query_active_skills_info(lua, calcs)
    aura_groups = [si for si in skills_info if si["is_aura"]]
    if not aura_groups:
        logger.info("精魄辅助推荐: 无光环技能组，跳过")
        return []

    # 查询精魄
    total_spirit, reserved_spirit = _query_total_spirit(lua, calcs)
    available_spirit = total_spirit - reserved_spirit

    # 动态扫描 + 合并 + 过滤
    discovered_supports = discover_spirit_supports(lua)

    hardcoded_formatted = []
    for ss in _SPIRIT_SUPPORT_CANDIDATES:
        hardcoded_formatted.append({
            "key": ss.get("key", ""),
            "name": ss.get("name", ""),
            "name_cn": ss.get("name_cn", ""),
            "skill_id": ss.get("skill_id", ""),
            "spirit": ss.get("spirit", 0),
            "description": ss.get("description", ""),
            "condition": ss.get("condition", ""),
            "note": ss.get("note", ""),
            "estimated": ss.get("estimated", False),
        })

    merged_supports = merge_candidates(hardcoded_formatted, discovered_supports)
    filtered_supports = filter_spirit_supports(
        merged_supports, is_attack, is_spell, skill_flags)
    filtered_supports.sort(key=lambda x: x.get("spirit", 0))

    logger.info("精魄辅助推荐(干净环境): 候选 %d → 过滤后 %d, 光环组 %d",
                len(merged_supports), len(filtered_supports), len(aura_groups))

    # 测试所有候选（在干净 baseline 环境中）
    spirit_support_tests = []
    for ss in filtered_supports:
        for aura_si in aura_groups:
            result = _test_add_spirit_support(
                lua, calcs, ss, aura_si["group_idx"], baseline, skill_flags)
            # 标注精魄需求
            actual_spirit = result.get("spirit", 0)
            if actual_spirit > available_spirit:
                shortfall = actual_spirit - available_spirit
                result["spirit_shortfall"] = shortfall
                result["spirit_note"] = (
                    f"需精魄 {actual_spirit:.0f}（缺 {shortfall:.0f}）")
            result["source"] = ss.get("source", "unknown")
            spirit_support_tests.append(result)

    logger.info("精魄辅助推荐完成: %d 个测试结果", len(spirit_support_tests))
    return spirit_support_tests


def _test_candidate_auras(lua, calcs, baseline: dict,
                          skill_flags: dict = None) -> list:
    """在干净环境中测试候选光环推荐。

    必须在 aura_spirit_analysis 之前调用——后者的 _rebuild_config_tab_modlist
    会污染 configTab.modList，导致 calcs.initEnv 读到错误的 modifier。

    Returns:
        候选光环测试结果列表（与 aura_spirit_analysis 7B 格式一致）
    """
    from .aura_analysis import (
        _query_active_skills_info,
        _query_total_spirit,
        _test_add_candidate_aura,
        _AURA_CANDIDATES,
    )

    # 查询光环技能组
    skills_info = _query_active_skills_info(lua, calcs)
    aura_names = {si["main_skill_name"] for si in skills_info if si["is_aura"]}

    # 查询精魄
    total_spirit, reserved_spirit = _query_total_spirit(lua, calcs)
    available_spirit = total_spirit - reserved_spirit

    candidate_auras = []
    for aura in _AURA_CANDIDATES:
        # 跳过构筑中已有的光环
        if aura["name"] in aura_names:
            continue
        result = _test_add_candidate_aura(lua, calcs, aura, baseline)
        # 标注精魄需求
        actual_spirit = result.get("spirit", 0)
        if actual_spirit > available_spirit:
            shortfall = actual_spirit - available_spirit
            result["spirit_shortfall"] = shortfall
            result["spirit_note"] = f"需精魄 {actual_spirit:.0f}（缺 {shortfall:.0f}）"
        candidate_auras.append(result)

    candidate_auras.sort(key=lambda x: x.get("dps_pct", 0), reverse=True)
    logger.info("候选光环推荐(干净环境): %d 个候选（跳过已有: %s）",
                len(candidate_auras),
                ", ".join(aura_names & {a["name"] for a in _AURA_CANDIDATES}))
    return candidate_auras


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

    # 8.5 精魄辅助贡献测试（在干净环境中，光环分析之前）
    _test_spirit_support_contributions(lua, calcs, baseline)

    # 8.6 精魄辅助推荐（在干净环境中执行，避免 aura_spirit_analysis 的状态污染）
    # INVARIANT: 必须在 aura_spirit_analysis 之前执行——后者的 _rebuild_config_tab_modlist
    #            会污染 configTab.modList，导致推荐测试的 calcs.initEnv 读到脏状态
    spirit_support_results = _test_spirit_support_recommendations(
        lua, calcs, baseline, skill_flags=skill_flags)
    assert spirit_support_results is not None, \
        "spirit_support_results must be computed before aura_spirit_analysis"
    logger.info("精魄辅助推荐完成(干净环境): %d 个结果", len(spirit_support_results))

    # 8.7 候选光环推荐（在干净环境中执行，避免状态污染导致 DPS 值异常）
    candidate_aura_results = _test_candidate_auras(
        lua, calcs, baseline, skill_flags=skill_flags)
    logger.info("候选光环推荐完成(干净环境): %d 个结果", len(candidate_aura_results))

    # 9. 光环与精魄分析（用 scope 保护，防止 configTab/gem 状态泄漏）
    from .lua_env import LuaEnvManager
    _env = LuaEnvManager(lua, calcs)
    with _env.config_scope():
        with _env.gem_scope():
            aura_spirit = aura_spirit_analysis(
                lua, calcs, baseline=baseline, skill_flags=skill_flags,
                dps_breakdown=dps_bd,
                spirit_support_results=spirit_support_results,
                candidate_aura_results=candidate_aura_results)
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


def _extract_build_modifiers(dps_bd: dict,
                             spirit_support_ids: set = None) -> dict:
    """从 dps_breakdown 提取构筑通用修饰符汇总。

    包含：天赋/装备/珠宝 + 精魄辅助宝石的实际效果。
    精魄辅助"开启即生效"，属于构筑常驻修饰符。
    排除：光环本体效果（Trinity等）、普通技能辅助、模拟注入(Sim)、Base、Enemy等。

    Args:
        dps_bd: dps_breakdown 数据
        spirit_support_ids: 精魄辅助的 skill_id 集合（如 {"SupportMysticismPlayerTwo"}）
                           用于从 Skill 来源中筛选精魄辅助

    Returns:
        {modifier_key: {"total": float, "sources": [source_dict, ...],
                        "affects": str, "formula_name": str}}
    """
    _BASE_CATEGORIES = {"Tree", "Item", "Jewel"}
    _spirit_ids = spirit_support_ids or set()

    def _is_included(source: dict) -> bool:
        cat = source.get("category", "")
        if cat in _BASE_CATEGORIES:
            return True
        # 精魄辅助：category=Skill, source="Skill:{skill_id}"
        if cat == "Skill" and _spirit_ids:
            src = source.get("source", "")
            # source 格式: "Skill:SupportMysticismPlayerTwo"
            for sid in _spirit_ids:
                if sid in src:
                    return True
        return False

    modifiers = {}
    for item in dps_bd.get("formula_items", []):
        key = item.get("key", "")
        if not key or key == "CombinedDPS":
            continue
        if key.endswith("_EffMult"):
            continue
        universal_sources = [
            s for s in item.get("sources", []) if _is_included(s)
        ]
        if not universal_sources:
            continue

        # 重新计算来源总值
        is_more = key.endswith("_MORE")
        if is_more:
            total = 1.0
            for s in universal_sources:
                total *= (1 + (s.get("value", 0) / 100))
        else:
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


def _collect_spirit_support_ids(full_result: dict) -> set:
    """从 aura_spirit 数据中提取构筑已装备精魄辅助的 skill_id 集合。"""
    ids = set()
    aura = full_result.get("aura_spirit", {})
    for a in aura.get("existing_auras", []):
        for ss in a.get("spirit_supports", []):
            sid = ss.get("skill_id", "")
            if sid:
                ids.add(sid)
    return ids


def extract_global_data(full_result: dict) -> dict:
    """从 full_analysis 结果中提取全局数据。

    Args:
        full_result: full_analysis() 的完整返回值

    Returns:
        global_data dict，包含 defence/resource/modifiers/attributes/jewels/composition
    """
    baseline = full_result.get("baseline", {})
    dps_bd = full_result.get("dps_breakdown", {})

    # 提取构筑中已装备精魄辅助的 skill_id
    spirit_ids = _collect_spirit_support_ids(full_result)

    return {
        "build_modifiers": _extract_build_modifiers(dps_bd, spirit_ids),
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
                            jewel_diag = diagnose_jewels(lua, calcs, baseline=baseline)
                            _test_spirit_support_contributions(lua, calcs, baseline)
                            # INVARIANT: 精魄辅助推荐必须在 aura_spirit_analysis 之前
                            ss_results = _test_spirit_support_recommendations(
                                lua, calcs, baseline, skill_flags=skill_flags)
                            assert ss_results is not None
                            # 候选光环推荐（干净环境，光环分析之前）
                            ca_results = _test_candidate_auras(
                                lua, calcs, baseline, skill_flags=skill_flags)
                            sens = sensitivity_analysis(
                                lua, calcs,
                                profiles=offence_profiles,
                                target_pct=target_pct,
                                baseline=baseline)
                            talent_val = passive_node_analysis(
                                lua, calcs, baseline=baseline)
                            talent_exp = passive_node_exploration(
                                lua, calcs, baseline=baseline,
                                min_dps_pct=exploration_min_pct)

                            # 光环分析必须最后执行（会修改 configTab/gem 状态）
                            aura_data = aura_spirit_analysis(
                                lua, calcs, baseline=baseline,
                                skill_flags=skill_flags,
                                dps_breakdown=dps_bd,
                                spirit_support_results=ss_results,
                                candidate_aura_results=ca_results)

                            skill_results[main_skill.get("name", skill_name)] = {
                                "baseline": baseline,
                                "main_skill": main_skill,
                                "skill_flags": skill_flags,
                                "sensitivity": sens,
                                "talent_value": talent_val,
                                "talent_exploration": talent_exp,
                                "dps_breakdown": dps_bd,
                                "aura_spirit": aura_data,
                                "jewel_diagnosis": jewel_diag,
                            }

            results[f"ws{ws}"] = {
                "global": global_data,
                "skills": skill_results,
            }

            # 从技能分析结果中提取精魄辅助 ID，更新 build_modifiers
            if skill_results:
                first_skill = next(iter(skill_results.values()))
                spirit_ids = _collect_spirit_support_ids(first_skill)
                if spirit_ids:
                    global_data["build_modifiers"] = _extract_build_modifiers(
                        best_dps_bd, spirit_ids)

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


