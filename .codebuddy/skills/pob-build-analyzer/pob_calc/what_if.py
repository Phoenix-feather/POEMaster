#!/usr/bin/env python3
"""
What-If 分析模块。

职责：
  - what_if_mod:            向 modDB 注入 modifier 并对比
  - what_if_nodes:          临时增删天赋点并对比
  - what_if_item:           临时替换装备并对比
  - sensitivity_analysis:   等基准灵敏度分析（固定 DPS 目标，反算各维度所需值）
  - passive_node_analysis:  天赋价值分析（逐个移除 Notable/Keystone）
  - _diff_outputs:          对比两个 output dict，返回差异

Mod 类型语义层说明：
  POB 的 modifier 系统有严格的 BASE/INC/MORE 类型区分，不同 stat 的含义不同。
  例如 CritMultiplier 的公式是 (BASE/100) × (1+INC/100) × MORE，
  游戏中 "50% increased critical damage bonus" 对应 INC 50，不是 BASE 50。
  SENSITIVITY_PROFILES 确保每个测试项使用游戏词缀对应的正确 mod 类型。

INC 合并查询机制（v1.0.6 修复）：
  POB 的伤害 INC 在 calcDamage() 中合并计算（CalcOffence.lua:135-136）：
    local modNames = damageStatsForTypes[typeFlags]
    local inc = 1 + skillModList:Sum("INC", cfg, unpack(modNames)) / 100
  damageStatsForTypes 是一个 magic table，根据 typeFlags 位运算自动生成 mod 名称列表。
  例如 Lightning (typeFlags=0x02)：modNames = {"Damage", "LightningDamage", "ElementalDamage"}
  这意味着 Damage INC、LightningDamage INC、ElementalDamage INC 共享同一个 INC 乘区。
  _query_merged_inc_total() 复现此逻辑，确保公式中的 INC 分母正确。

等基准对比设计（v1.0.6）：
  传统做法注入固定值（+50 INC、+20 MORE、+2 BASE 等），但不同维度注入量不同，
  导致 DPS% 变化无法直接横向比较。
  新设计固定 DPS 目标（默认 +30%），通过二分搜索反算每个维度达到该目标所需的注入值。
  这样所有维度在相同 DPS 增幅下比较"所需投入"，值越小 = 性价比越高。

POE1/POE2 数据分离（v1.0.5 审计结论）：
  底层 POBData/ 已是 POE2 专用数据（GameVersions 0_x 体系），无 POE1 版本混入。
  已确认的 POE1 残留均为死代码：CalcSetup.lua 中 SpellDodgeChanceMax=75 和
  Siphoning/Challenger/Blitz/CrabBarriers=0（值为 0 无影响），ModParser.lua 中
  DMGSPELLS 匹配模式（POE2 物品不会生成此文本）。
  本模块中已规避的 POE1 遗留：flat damage 限制为攻击专属（POE2 无法术固定伤害词缀）。
"""
import logging
from .calculator import calculate

logger = logging.getLogger(__name__)

# =============================================================================
# DPS 灵敏度测试集
# =============================================================================
#
# 每个 profile: {
#   "mod_name":    str,     # POB mod 名称
#   "mod_type":    str,     # BASE/INC/MORE
#   "label":       str,     # 英文游戏词缀（保留）
#   "description": str,     # 中文说明（保留）
#   "search_max":  int,     # 等基准搜索上界（二分搜索最大值）
# }
#
# 设计原则：
#   1. mod_type 必须对应游戏中最常见/可获取的词缀类型
#   2. label 使用游戏内英文措辞，description 使用中文说明
#   3. search_max 是二分搜索的上界，根据游戏可获取范围估算
#   4. Penetration 只有 BASE（游戏设计如此）
#   5. ProjectileCount 只有 BASE（没有 INC）
#   6. "spell damage" 在 POB 中是 Damage + ModFlag.Spell，
#      但注入到 modDB 时无 flag 的 Damage INC 也会对法术生效
#      （skillModList 查询时用 cfg 中的技能 flag 做交集匹配）
#
# POB 公式参考（CalcOffence.lua）：
#   Damage:          base × (1 + Σ INC/100) × Π MORE
#   Speed:           (1/castTime) × (1 + Σ INC/100) × Π MORE
#   CritChance:      (baseCrit + Σ BASE) × (1 + Σ INC/100) × Π MORE
#   CritMultiplier:  1 + (Σ BASE/100) × (1 + Σ INC/100) × Π MORE
#                    POE2 默认 BASE=100（Misc.lua characterConstants）
#                    例：BASE=100, INC=200 → 1 + (100/100)×(1+200/100) = 4.0
#                    INC 是对 BASE 的乘法放大，不是简单加法！
#   CritEffect:      (1 - cc) + cc × CritMultiplier    (cc = CritChance%)
#                    CritMulti 变化通过 CritEffect 传导到 DPS，被 cc 稀释
#   Penetration:     effectiveResist = enemyResist - Σ BASE
#   ProjectileCount: Σ BASE × Π MORE
#   AreaOfEffect:    radius = base × √((1 + Σ INC/100) × Π MORE)
#
# INC 合并机制（CalcOffence.lua:53-63, 135-136）：
#   damageStatsForTypes 根据 typeFlags 合并 mod 名称：
#     Lightning(0x02) → {"Damage", "LightningDamage", "ElementalDamage"}
#     Fire(0x08)      → {"Damage", "FireDamage", "ElementalDamage"}
#     Physical(0x01)  → {"Damage", "PhysicalDamage"}
#   POB 对这些名称执行一次 Sum("INC", cfg, ...)，得到单一 INC 值。
#   因此 Damage INC、LightningDamage INC、ElementalDamage INC 共享同一乘区。
#
# DPS 总公式：
#   TotalDPS = AverageHit × Speed
#   AverageHit = baseDamage × (1+Σ dmgINC/100) × Π dmgMORE × CritEffect × effMult
#   effMult = Π (1 - effectiveResist/100)   每种伤害类型独立计算

SENSITIVITY_PROFILES = {
    # === 伤害类 ===
    "damage_inc": {
        "mod_name": "Damage", "mod_type": "INC",
        "label": "increased Damage",
        "description": "通用伤害增加，对所有伤害类型生效",
        "search_max": 500,
    },
    "damage_more": {
        "mod_name": "Damage", "mod_type": "MORE",
        "label": "more Damage",
        "description": "独立乘区，如来自辅助宝石或特殊机制",
        "search_max": 100,
    },
    "physical_damage_inc": {
        "mod_name": "PhysicalDamage", "mod_type": "INC",
        "label": "increased Physical Damage",
        "description": "物理伤害增加，仅对物理伤害生效",
        "search_max": 500,
    },
    "fire_damage_inc": {
        "mod_name": "FireDamage", "mod_type": "INC",
        "label": "increased Fire Damage",
        "description": "火焰伤害增加",
        "search_max": 500,
    },
    "cold_damage_inc": {
        "mod_name": "ColdDamage", "mod_type": "INC",
        "label": "increased Cold Damage",
        "description": "冰霜伤害增加",
        "search_max": 500,
    },
    "lightning_damage_inc": {
        "mod_name": "LightningDamage", "mod_type": "INC",
        "label": "increased Lightning Damage",
        "description": "闪电伤害增加",
        "search_max": 500,
    },
    "elemental_damage_inc": {
        "mod_name": "ElementalDamage", "mod_type": "INC",
        "label": "increased Elemental Damage",
        "description": "元素伤害增加，对火/冰/电都生效",
        "search_max": 500,
    },
    "chaos_damage_inc": {
        "mod_name": "ChaosDamage", "mod_type": "INC",
        "label": "increased Chaos Damage",
        "description": "混沌伤害增加",
        "search_max": 500,
    },

    # === 暴击类 ===
    "crit_chance_inc": {
        "mod_name": "CritChance", "mod_type": "INC",
        "label": "increased Critical Hit Chance",
        "description": "暴击率增加（INC叠加到已有的INC总量）",
        "search_max": 1000,
    },
    "crit_chance_base": {
        "mod_name": "CritChance", "mod_type": "BASE",
        "label": "to Critical Hit Chance",
        "description": "基础暴击率（加到技能基础暴击上，再被INC放大）",
        "search_max": 30,
    },
    "crit_multi_inc": {
        "mod_name": "CritMultiplier", "mod_type": "INC",
        "label": "increased Critical Damage Bonus",
        "description": "暴击伤害增加（常见词缀，线性叠加到INC总量）",
        "search_max": 500,
    },
    "crit_multi_base": {
        "mod_name": "CritMultiplier", "mod_type": "BASE",
        "label": "to Critical Damage Bonus",
        "description": "暴击伤害基础（稀有词缀如力量之盾，被INC放大）",
        "search_max": 200,
    },

    # === 速度类 ===
    "speed_inc": {
        "mod_name": "Speed", "mod_type": "INC",
        "label": "increased Attack and Cast Speed",
        "description": "攻击/施法速度增加",
        "search_max": 300,
    },
    "speed_more": {
        "mod_name": "Speed", "mod_type": "MORE",
        "label": "more Attack and Cast Speed",
        "description": "速度独立乘区，如辅助宝石效果",
        "search_max": 100,
    },

    # === 穿透类（只有 BASE）===
    # 注：MAIN 模式已包含穿透计算（initEnv 默认 buffMode=EFFECTIVE）。
    # 穿透在敌人抗性为负时无效（CalcOffence.lua:3821 — resist <= minPen 时穿透不再降低抗性）。
    # 如果灵敏度显示穿透影响为 0，通常意味着构筑配置中敌人抗性已被诅咒/曝光压至负值。
    "lightning_pen": {
        "mod_name": "LightningPenetration", "mod_type": "BASE",
        "label": "Penetrate Lightning Resistance",
        "description": "闪电抗性穿透（敌人负抗时无效）",
        "search_max": 100,
    },
    "fire_pen": {
        "mod_name": "FirePenetration", "mod_type": "BASE",
        "label": "Penetrate Fire Resistance",
        "description": "火焰抗性穿透（敌人负抗时无效）",
        "search_max": 100,
    },
    "cold_pen": {
        "mod_name": "ColdPenetration", "mod_type": "BASE",
        "label": "Penetrate Cold Resistance",
        "description": "冰霜抗性穿透（敌人负抗时无效）",
        "search_max": 100,
    },
    "elemental_pen": {
        "mod_name": "ElementalPenetration", "mod_type": "BASE",
        "label": "Penetrate Elemental Resistances",
        "description": "元素抗性穿透（对火/冰/电都生效，敌人负抗时无效）",
        "search_max": 100,
    },
    "chaos_pen": {
        "mod_name": "ChaosPenetration", "mod_type": "BASE",
        "label": "Penetrate Chaos Resistance",
        "description": "混沌抗性穿透（敌人负抗时无效）",
        "search_max": 100,
    },

    # === 投射物/AoE ===
    "projectile_count": {
        "mod_name": "ProjectileCount", "mod_type": "BASE",
        "label": "additional Projectiles",
        "description": "额外投射物数量（ProjectileCount没有INC类型）",
        "search_max": 20,
    },
    "aoe_inc": {
        "mod_name": "AreaOfEffect", "mod_type": "INC",
        "label": "increased Area of Effect",
        "description": "影响范围增加（对半径是平方根关系）",
        "search_max": 500,
    },

    # === 持续时间 ===
    "duration_inc": {
        "mod_name": "Duration", "mod_type": "INC",
        "label": "increased Skill Effect Duration",
        "description": "技能持续时间增加",
        "search_max": 500,
    },

    # === 添加伤害（flat damage，注入到 min+max）===
    # POE2 机制说明：
    #   POE2 中法术技能不存在 "Adds X to Y damage to Spells" 词缀。
    #   固定伤害(flat damage)仅对攻击技能有效（"Adds X to Y damage to Attacks"）。
    #   POB 代码中虽有 DMGSPELLS 匹配模式（ModParser.lua），这是 POE1 遗留，
    #   POE2 游戏内不会生成此类词缀。
    #
    # 注入机制说明：
    #   modDB:NewMod("LightningMin", "BASE", 50, "WhatIf") 创建 flags=0 的 mod。
    #   ModDB:SumInternal 使用 band(cfg.flags, mod.flags) == mod.flags 匹配，
    #   flags=0 的 mod 会通过任何 flag 检查（包括法术的 ModFlag.Spell），
    #   这意味着注入的固定伤害会无差别地影响法术，与 POE2 实际机制不符。
    #
    # 以下 profile 仅用于攻击构筑的分析，标注为攻击专属。
    # 法术构筑的灵敏度分析应忽略这些 profile。
    "flat_lightning_attack": {
        "mod_name": "LightningMin+Max", "mod_type": "BASE",
        "label": "Adds Lightning Damage to Attacks",
        "description": "添加固定闪电伤害（仅攻击）",
        "search_max": 500,
    },
    "flat_fire_attack": {
        "mod_name": "FireMin+Max", "mod_type": "BASE",
        "label": "Adds Fire Damage to Attacks",
        "description": "添加固定火焰伤害（仅攻击）",
        "search_max": 500,
    },
    "flat_cold_attack": {
        "mod_name": "ColdMin+Max", "mod_type": "BASE",
        "label": "Adds Cold Damage to Attacks",
        "description": "添加固定冰霜伤害（仅攻击）",
        "search_max": 500,
    },
    "flat_physical_attack": {
        "mod_name": "PhysicalMin+Max", "mod_type": "BASE",
        "label": "Adds Physical Damage to Attacks",
        "description": "添加固定物理伤害（仅攻击）",
        "search_max": 300,
    },
}

# 需要同时注入两个 mod 的特殊 profile（flat damage — 仅攻击构筑有效）
# value 是 Min 的值，Max 按 2:1 比例计算
_FLAT_DAMAGE_PROFILES = {
    "flat_lightning_attack": ("LightningMin", "LightningMax"),
    "flat_fire_attack": ("FireMin", "FireMax"),
    "flat_cold_attack": ("ColdMin", "ColdMax"),
    "flat_physical_attack": ("PhysicalMin", "PhysicalMax"),
}

# 攻击专属 profile 集合（法术构筑灵敏度分析时自动排除）
_ATTACK_ONLY_PROFILES = {
    "flat_lightning_attack", "flat_fire_attack",
    "flat_cold_attack", "flat_physical_attack",
}


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

    after = {}
    if result:
        for pair in str(result).split('|'):
            if '=' in pair:
                k, v = pair.split('=', 1)
                try:
                    after[k] = float(v)
                except ValueError:
                    pass
    return _diff_outputs(baseline, after)


def _detect_is_spell(lua, calcs) -> bool:
    """自动检测主技能是否为法术。

    通过 mainSkill.skillCfg.flags 位运算判断（ModFlag.Spell = 0x02）。
    注：skillFlags 表在部分构筑中可能为 nil，但 skillCfg.flags 始终可用。
    """
    result = lua.execute('''
        local build = _spike_build
        local env = calcs.initEnv(build, "MAIN")
        calcs.perform(env)
        local ms = env.player.mainSkill
        if ms and ms.skillCfg then
            local flags = ms.skillCfg.flags or 0
            -- ModFlag.Spell = 0x02 (Global.lua:220)
            if flags & 2 ~= 0 then return "1" end
        end
        return "0"
    ''')
    is_spell = str(result).strip() == "1"
    logger.info("主技能法术检测: %s", "是法术" if is_spell else "非法术")
    return is_spell


def sensitivity_analysis(lua, calcs, profiles: list[str] = None,
                         target_stat: str = "TotalDPS",
                         target_pct: float = 30.0,
                         baseline: dict = None,
                         is_spell: bool = None) -> list[dict]:
    """等基准灵敏度分析。

    固定 DPS 增幅目标（默认 +30%），通过二分搜索反算每个维度达到该目标所需的注入值。
    所有维度在相同 DPS 增幅下比较"所需投入"，值越小 = 性价比越高 = 优化杠杆越大。

    注：MAIN 模式的 buffMode 默认为 EFFECTIVE（CalcSetup.lua:579），
    已包含敌人抗性/穿透/命中率等计算。穿透 profile 如果显示 0 影响，
    通常表示构筑配置中敌人抗性已被诅咒/曝光压至负值（穿透无法进一步降低负抗）。

    POE2 机制：法术不受固定伤害(flat damage)加成，仅攻击可以。
    当 is_spell=True 时自动排除攻击专属的 flat damage profile。

    Args:
        profiles: 要测试的 profile key 列表。None = 全部测试。
        target_stat: 排序依据的目标 stat（默认 TotalDPS）
        target_pct: DPS 增幅目标百分比（默认 30.0 = +30%）
        baseline: 基线 output
        is_spell: 主技能是否为法术。True=排除攻击专属profile，
                  False=保留全部，None=自动检测（从 env 判断技能 flag）。

    Returns:
        按所需值升序排列（值越小 = 性价比越高）的列表：
        [{
            "key": profile key,
            "label": 英文游戏词缀描述,
            "description": 中文说明,
            "mod_name": POB mod 名称,
            "mod_type": BASE/INC/MORE,
            "needed_value": 达到目标所需的注入值（None=无法达到）,
            "target_pct": 实际目标百分比（= target_pct 参数）,
            "current_total": 当前 modDB 中该 stat 的合并汇总值,
            "formula": 增量公式字符串,
            "sample_diff": 注入 needed_value 后的完整差异字典,
        }, ...]
    """
    if baseline is None:
        baseline = calculate(lua, calcs)

    # 自动检测主技能是否为法术
    if is_spell is None:
        is_spell = _detect_is_spell(lua, calcs)

    if profiles is None:
        profiles = list(SENSITIVITY_PROFILES.keys())
        # 法术构筑排除攻击专属 profile（POE2 法术不受 flat damage 加成）
        if is_spell:
            profiles = [p for p in profiles if p not in _ATTACK_ONLY_PROFILES]
            logger.info("法术构筑：已排除 %d 个攻击专属 flat damage profile",
                        len(_ATTACK_ONLY_PROFILES))

    base_dps = baseline.get(target_stat, 0)
    if base_dps == 0:
        logger.warning("基线 %s = 0，无法进行灵敏度分析", target_stat)
        return []

    target_dps = base_dps * (1 + target_pct / 100)

    # 预查询所有 INC 类型的合并汇总值
    merged_inc_cache = _query_all_merged_inc(lua, calcs)

    results = []
    for key in profiles:
        if key not in SENSITIVITY_PROFILES:
            logger.warning(f"Unknown sensitivity profile: {key}")
            continue

        profile = SENSITIVITY_PROFILES[key]
        mod_name = profile["mod_name"]
        mod_type = profile["mod_type"]
        label = profile["label"]
        description = profile["description"]
        search_max = profile["search_max"]

        # 查询当前 modDB 汇总值
        if mod_type == "INC" and mod_name in _DAMAGE_INC_STATS:
            # 伤害 INC 使用合并值
            current_total = merged_inc_cache.get("merged_damage_inc", 0.0)
        else:
            current_total = _query_mod_total_single(lua, calcs, mod_name, mod_type)

        # 二分搜索：找到达到 target_dps 所需的最小注入值
        needed_value = _binary_search_needed_value(
            lua, calcs, key, profile, baseline,
            target_stat, target_dps, search_max
        )

        # 计算实际注入 needed_value 后的 diff（用于 formula 和验证）
        sample_diff = {}
        actual_pct = 0.0
        if needed_value is not None:
            sample_diff = _inject_profile(lua, calcs, key, profile,
                                          needed_value, baseline)
            after_entry = sample_diff.get(target_stat)
            if after_entry:
                actual_pct = (after_entry[2] / base_dps * 100) if base_dps != 0 else 0

        # 生成公式
        formula = _make_formula(mod_name, mod_type, needed_value,
                                current_total, target_pct, actual_pct)

        results.append({
            "key": key,
            "label": label,
            "description": description,
            "mod_name": mod_name,
            "mod_type": mod_type,
            "needed_value": needed_value,
            "target_pct": target_pct,
            "actual_pct": round(actual_pct, 2),
            "current_total": current_total,
            "formula": formula,
            "sample_diff": sample_diff,
        })

    # 按所需值升序排列（值越小 = 性价比越高），None 排最后
    results.sort(key=lambda x: (x["needed_value"] is None, x["needed_value"] or 999999))
    return results


# =============================================================================
# INC 合并查询
# =============================================================================
#
# POB 的伤害 INC 合并机制（CalcOffence.lua:53-63）：
#   damageStatsForTypes 根据 typeFlags 生成 mod 名称列表。
#   例如 Lightning(0x02) → {"Damage", "LightningDamage", "ElementalDamage"}
#   然后 Sum("INC", cfg, unpack(modNames)) 将所有名称的 INC 合并为一个值。
#
# 这意味着 "Damage INC +50" 和 "LightningDamage INC +50" 和
# "ElementalDamage INC +50" 对 Lightning 伤害的影响完全相同 —
# 它们都是往同一个 INC 乘区里加 50。
#
# _query_all_merged_inc() 在 Lua 端复现此合并逻辑，返回当前已有的合并 INC 值。

# 伤害类 INC stat 名称（共享同一个 INC 乘区）
_DAMAGE_INC_STATS = {
    "Damage", "PhysicalDamage", "FireDamage", "ColdDamage",
    "LightningDamage", "ElementalDamage", "ChaosDamage",
}


def _query_all_merged_inc(lua, calcs) -> dict:
    """从 Lua 端查询构筑当前伤害 INC 合并值。

    复现 CalcOffence.lua:135-136 的 damageStatsForTypes 合并逻辑。

    Returns:
        {"merged_damage_inc": float} — 主伤害类型的合并 INC 总值
    """
    result = lua.execute('''
        local build = _spike_build
        local env = calcs.initEnv(build, "MAIN")
        calcs.perform(env)
        local ms = env.player.mainSkill
        if not ms then return "0" end

        local cfg = ms.skillCfg
        local skillModList = ms.skillModList

        -- 复现 damageStatsForTypes 逻辑
        -- 查找主伤害类型（从 output 中找 DPS 最高的类型）
        local output = env.player.output
        local dmgTypes = {"Physical", "Lightning", "Cold", "Fire", "Chaos"}
        local isElemental = { Fire = true, Cold = true, Lightning = true }
        local dmgTypeFlags = {
            Physical = 0x01, Lightning = 0x02, Cold = 0x04,
            Fire = 0x08, Elemental = 0x0E, Chaos = 0x10,
        }
        local dmgFlagOrder = { "Physical", "Lightning", "Cold", "Fire", "Elemental", "Chaos" }

        -- 找主伤害类型
        local bestType = "Physical"
        local bestDPS = 0
        for _, dt in ipairs(dmgTypes) do
            local dps = output[dt.."TotalDPS"] or 0
            if dps > bestDPS then
                bestDPS = dps
                bestType = dt
            end
        end

        -- 构建 typeFlags（与 calcDamage 一致）
        local typeFlags = dmgTypeFlags[bestType] or 0

        -- 构建 modNames（与 damageStatsForTypes 一致）
        local modNames = { "Damage" }
        for _, tp in ipairs(dmgFlagOrder) do
            local flag = dmgTypeFlags[tp]
            if flag and (typeFlags & flag) ~= 0 then
                modNames[#modNames+1] = tp .. "Damage"
            end
        end

        -- Sum("INC", cfg, unpack(modNames))
        local inc = skillModList:Sum("INC", cfg, unpack(modNames))
        return tostring(inc) .. "|" .. bestType
    ''')

    merged_inc = 0.0
    main_type = "Physical"
    if result:
        parts = str(result).split('|')
        try:
            merged_inc = float(parts[0])
        except (ValueError, IndexError):
            pass
        if len(parts) > 1:
            main_type = parts[1]

    logger.info("伤害 INC 合并值: %.1f%% (主伤害类型: %s)", merged_inc, main_type)
    return {"merged_damage_inc": merged_inc, "main_damage_type": main_type}


def _query_mod_total_single(lua, calcs, mod_name: str, mod_type: str) -> float:
    """从 Lua 端查询构筑当前 modDB 中指定单个 stat 的汇总值。

    用于非伤害 INC 的 stat（Speed、CritChance、CritMultiplier 等）。

    Args:
        mod_name: stat 名称
        mod_type: "BASE" / "INC" / "MORE"

    Returns:
        汇总值（INC 返回百分比总和如 238，BASE 返回绝对值总和如 100）
    """
    if mod_type == "MORE":
        # MORE 是乘积，用 More() 查询返回最终乘数
        result = lua.execute(f'''
            local build = _spike_build
            local env = calcs.initEnv(build, "MAIN")
            calcs.perform(env)
            local ms = env.player.mainSkill
            if ms then
                local cfg = ms.skillCfg
                return tostring(ms.skillModList:More(cfg, "{mod_name}"))
            end
            return "1"
        ''')
    else:
        result = lua.execute(f'''
            local build = _spike_build
            local env = calcs.initEnv(build, "MAIN")
            calcs.perform(env)
            local ms = env.player.mainSkill
            if ms then
                local cfg = ms.skillCfg
                return tostring(ms.skillModList:Sum("{mod_type}", cfg, "{mod_name}"))
            end
            return "0"
        ''')
    try:
        return float(str(result))
    except (ValueError, TypeError):
        return 0.0


# =============================================================================
# 等基准二分搜索
# =============================================================================


def _inject_profile(lua, calcs, key: str, profile: dict,
                    value: float, baseline: dict) -> dict:
    """注入指定 profile 的 mod 并返回 diff。

    Args:
        value: 注入值（对 flat damage 是 Min 值，Max = value * 2）
    """
    mod_name = profile["mod_name"]
    mod_type = profile["mod_type"]

    if key in _FLAT_DAMAGE_PROFILES:
        min_name, max_name = _FLAT_DAMAGE_PROFILES[key]
        int_val = int(round(value))
        max_val = int_val * 2  # Min:Max = 1:2
        mod_lines = (
            f'        env.modDB:NewMod("{min_name}", "BASE", {int_val}, "WhatIf")\n'
            f'        env.modDB:NewMod("{max_name}", "BASE", {max_val}, "WhatIf")'
        )
    else:
        int_val = int(round(value)) if mod_type == "BASE" else value
        mod_lines = (
            f'        env.modDB:NewMod("{mod_name}", "{mod_type}", {int_val}, "WhatIf")'
        )

    return _inject_and_calc(lua, calcs, mod_lines, baseline)


def _binary_search_needed_value(lua, calcs, key: str, profile: dict,
                                 baseline: dict, target_stat: str,
                                 target_dps: float, search_max: float,
                                 max_iters: int = 20) -> float | None:
    """二分搜索达到目标 DPS 所需的最小注入值。

    Returns:
        所需值（float），或 None 如果 search_max 内无法达到目标
    """
    base_dps = baseline.get(target_stat, 0)
    if base_dps == 0:
        return None

    # 先检查 search_max 能否达到目标
    diff_max = _inject_profile(lua, calcs, key, profile, search_max, baseline)
    max_entry = diff_max.get(target_stat)
    if not max_entry:
        return None  # 此维度对 target_stat 无影响
    max_after = max_entry[1]
    if max_after < target_dps:
        return None  # search_max 内无法达到目标

    # 检查最小值（1）是否已超过目标
    diff_min = _inject_profile(lua, calcs, key, profile, 1, baseline)
    min_entry = diff_min.get(target_stat)
    if min_entry and min_entry[1] >= target_dps:
        return 1.0

    # 二分搜索
    lo, hi = 1.0, float(search_max)
    for _ in range(max_iters):
        mid = (lo + hi) / 2
        if hi - lo < 0.5:
            break
        diff = _inject_profile(lua, calcs, key, profile, mid, baseline)
        entry = diff.get(target_stat)
        if entry and entry[1] >= target_dps:
            hi = mid
        else:
            lo = mid

    # 返回 hi（确保 >= target），取整到 0.5 精度
    result = round(hi * 2) / 2
    return result


def _diff_outputs(before: dict, after: dict, threshold: float = 0.001) -> dict:
    """对比两个 output dict，返回有变化的字段。

    Returns:
        {stat: (before_val, after_val, delta)} 仅包含有变化的字段
    """
    diff = {}
    all_keys = set(before.keys()) | set(after.keys())
    for k in all_keys:
        v1 = before.get(k, 0.0)
        v2 = after.get(k, 0.0)
        delta = v2 - v1
        if abs(delta) > threshold:
            diff[k] = (v1, v2, delta)
    return diff


# =============================================================================
# DPS 变化公式生成器（v1.0.6 等基准版本）
# =============================================================================
#
# 为每个 sensitivity profile 生成一行简洁的增量公式，
# 说明达到目标 DPS 增幅所需的投入。
#
# 示例：
#   Damage INC:          "INC 238%→297%, 需要 +59 → DPS +30.0%"
#   Damage MORE:         "需要 ×1.30 独立乘区 (+30) → DPS +30.0%"
#   CritMulti INC:       "INC 200%→376%, 需要 +176 → DPS +30.0%"
#   Speed INC:           "INC 50%→95%, 需要 +45 → DPS +30.0%"
#   Penetration:         "无法在搜索范围内达到目标"


def _make_formula(mod_name: str, mod_type: str, needed_value: float | None,
                  current_total: float, target_pct: float,
                  actual_pct: float) -> str:
    """生成一行简洁的增量公式字符串（等基准版本）。

    Args:
        needed_value: 达到目标所需的注入值，None=无法达到
        current_total: 当前 modDB 合并汇总值
        target_pct: 目标 DPS 增幅百分比
        actual_pct: 实际 DPS 增幅百分比（二分搜索精度范围内）

    Returns:
        如 "INC 238%→297%, 需要 +59 → DPS +30.0%"
    """
    if needed_value is None:
        return f"无法在搜索范围内达到 DPS +{target_pct:.0f}%"

    dps_part = f"DPS +{actual_pct:.1f}%"

    if mod_type == "INC":
        old_inc = current_total
        new_inc = old_inc + needed_value
        return f"INC {old_inc:.0f}%→{new_inc:.0f}%, 需要 +{needed_value:.0f} → {dps_part}"

    elif mod_type == "MORE":
        more_factor = needed_value
        return f"需要 MORE +{more_factor:.0f}% (×{1+more_factor/100:.2f}) → {dps_part}"

    elif mod_type == "BASE":
        if "Penetration" in mod_name:
            return f"需要 +{needed_value:.0f}% 穿透 → {dps_part}"
        elif mod_name == "ProjectileCount":
            old_base = current_total
            return f"投射物 {old_base:.0f}→{old_base+needed_value:.0f}, 需要 +{needed_value:.0f} → {dps_part}"
        elif mod_name in ("CritChance",):
            old_base = current_total
            return f"baseCrit {old_base:.1f}%→{old_base+needed_value:.1f}%, 需要 +{needed_value:.1f}% → {dps_part}"
        elif mod_name == "CritMultiplier":
            old_base = current_total
            return f"CritBase {old_base:.0f}→{old_base+needed_value:.0f}, 需要 +{needed_value:.0f} → {dps_part}"
        elif "Min+Max" in mod_name:
            max_val = needed_value * 2
            return f"需要添加 {needed_value:.0f}-{max_val:.0f} 基础伤害 → {dps_part}"
        else:
            old_base = current_total
            return f"BASE {old_base:.0f}→{old_base+needed_value:.0f}, 需要 +{needed_value:.0f} → {dps_part}"

    return f"需要 +{needed_value:.1f} → {dps_part}"


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


def what_if_nodes(lua, calcs, add: list[int] = None, remove: list[int] = None,
                  baseline: dict = None) -> dict:
    """临时增删天赋点并对比。

    使用 POB 原生 override.addNodes / override.removeNodes 机制，
    不修改 build 对象。

    Args:
        add: 要临时添加的节点 ID 列表
        remove: 要临时移除的节点 ID 列表
        baseline: 基线 output

    Returns:
        {stat: (before, after, delta)} 差异字典
    """
    if baseline is None:
        baseline = calculate(lua, calcs)

    add = add or []
    remove = remove or []

    # 构建 override Lua 表达式
    add_lua = '{' + ','.join(
        f'[_spike_build.spec.nodes[{nid}]] = true' for nid in add
    ) + '}' if add else '{}'

    remove_lua = '{' + ','.join(
        f'[_spike_build.spec.nodes[{nid}]] = true' for nid in remove
    ) + '}' if remove else '{}'

    result = lua.execute(f'''
        local build = _spike_build
        local override = {{
            addNodes = {add_lua},
            removeNodes = {remove_lua},
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

    after = {}
    if result:
        for pair in str(result).split('|'):
            if '=' in pair:
                k, v = pair.split('=', 1)
                try:
                    after[k] = float(v)
                except ValueError:
                    pass

    return _diff_outputs(baseline, after)


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

    after = {}
    if result:
        for pair in str(result).split('|'):
            if '=' in pair:
                k, v = pair.split('=', 1)
                try:
                    after[k] = float(v)
                except ValueError:
                    pass

    return _diff_outputs(baseline, after)


# =============================================================================
# 天赋价值分析
# =============================================================================


def _get_notable_nodes(lua) -> list[dict]:
    """获取构筑中已分配的 Notable / Keystone 天赋节点列表。"""
    result = lua.execute('''
        local build = _spike_build
        local nodes = {}
        for id, node in pairs(build.spec.allocNodes) do
            if node.type == "Notable" or node.type == "Keystone" then
                nodes[#nodes+1] = tostring(id) .. "|" .. (node.dn or "?") .. "|" .. (node.type or "?")
            end
        end
        return table.concat(nodes, "\\n")
    ''')
    nodes = []
    if result:
        for line in str(result).strip().split('\n'):
            parts = line.split('|', 2)
            if len(parts) == 3:
                nodes.append({
                    'id': int(parts[0]),
                    'name': parts[1],
                    'type': parts[2],
                })
    return nodes


def passive_node_analysis(lua, calcs, baseline: dict = None,
                          dps_stat: str = "TotalDPS",
                          ehp_stat: str = "TotalEHP") -> list[dict]:
    """天赋价值分析：逐个移除已分配的 Notable/Keystone，评估 DPS 和 EHP 影响。

    Returns:
        按 DPS 损失降序排列：
        [{id, name, type, dps_pct, ehp_pct, category}, ...]
        category: "进攻" / "防御" / "混合" / "无效"
    """
    if baseline is None:
        baseline = calculate(lua, calcs)

    nodes = _get_notable_nodes(lua)
    logger.info("天赋价值分析: %d 个 Notable/Keystone", len(nodes))

    base_dps = baseline.get(dps_stat, 0)
    base_ehp = baseline.get(ehp_stat, 0)

    results = []
    for node in nodes:
        nid = node['id']
        diff = what_if_nodes(lua, calcs, remove=[nid], baseline=baseline)

        dps_entry = diff.get(dps_stat)
        ehp_entry = diff.get(ehp_stat)

        dps_after = dps_entry[1] if dps_entry else base_dps
        dps_delta = dps_entry[2] if dps_entry else 0
        dps_pct = (dps_delta / base_dps * 100) if base_dps != 0 else 0

        ehp_after = ehp_entry[1] if ehp_entry else base_ehp
        ehp_delta = ehp_entry[2] if ehp_entry else 0
        ehp_pct = (ehp_delta / base_ehp * 100) if base_ehp != 0 else 0

        has_dps = abs(dps_pct) > 0.1
        has_ehp = abs(ehp_pct) > 0.1
        if has_dps and has_ehp:
            category = "混合"
        elif has_dps:
            category = "进攻"
        elif has_ehp:
            category = "防御"
        else:
            category = "无效"

        results.append({
            "id": nid, "name": node['name'], "type": node['type'],
            "dps_before": base_dps, "dps_after": dps_after,
            "dps_delta": dps_delta, "dps_pct": dps_pct,
            "ehp_before": base_ehp, "ehp_after": ehp_after,
            "ehp_delta": ehp_delta, "ehp_pct": ehp_pct,
            "category": category,
        })

    results.sort(key=lambda x: abs(x["dps_pct"]), reverse=True)
    return results
