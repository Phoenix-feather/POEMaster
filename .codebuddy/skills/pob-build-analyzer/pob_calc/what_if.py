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
        "unit": "%",
    },
    "spell_damage_inc": {
        "mod_name": "Damage", "mod_type": "INC",
        "label": "increased Spell Damage",
        "description": "法术伤害增加（仅法术生效，POB中为 Damage INC + ModFlag.Spell）",
        "search_max": 500,
        "flags": 0x02,  # ModFlag.Spell — 仅法术构筑有效
        "unit": "%",
    },
    "attack_damage_inc": {
        "mod_name": "Damage", "mod_type": "INC",
        "label": "increased Attack Damage",
        "description": "攻击伤害增加（仅攻击生效，POB中为 Damage INC + ModFlag.Attack）",
        "search_max": 500,
        "flags": 0x01,  # ModFlag.Attack — 仅攻击构筑有效
        "unit": "%",
    },
    "damage_more": {
        "mod_name": "Damage", "mod_type": "MORE",
        "label": "more Damage",
        "description": "独立乘区，如来自辅助宝石或特殊机制",
        "search_max": 100,
        "unit": "%",
    },
    "physical_damage_inc": {
        "mod_name": "PhysicalDamage", "mod_type": "INC",
        "label": "increased Physical Damage",
        "description": "物理伤害增加，仅对物理伤害生效",
        "search_max": 500, "unit": "%",
    },
    "fire_damage_inc": {
        "mod_name": "FireDamage", "mod_type": "INC",
        "label": "increased Fire Damage",
        "description": "火焰伤害增加",
        "search_max": 500, "unit": "%",
    },
    "cold_damage_inc": {
        "mod_name": "ColdDamage", "mod_type": "INC",
        "label": "increased Cold Damage",
        "description": "冰霜伤害增加",
        "search_max": 500, "unit": "%",
    },
    "lightning_damage_inc": {
        "mod_name": "LightningDamage", "mod_type": "INC",
        "label": "increased Lightning Damage",
        "description": "闪电伤害增加",
        "search_max": 500, "unit": "%",
    },
    "elemental_damage_inc": {
        "mod_name": "ElementalDamage", "mod_type": "INC",
        "label": "increased Elemental Damage",
        "description": "元素伤害增加，对火/冰/电都生效",
        "search_max": 500, "unit": "%",
    },
    "chaos_damage_inc": {
        "mod_name": "ChaosDamage", "mod_type": "INC",
        "label": "increased Chaos Damage",
        "description": "混沌伤害增加",
        "search_max": 500, "unit": "%",
    },

    # === Flag-based 伤害类（带 ModFlag 条件）===
    # 这些 profile 对应 ModParser.lua modNameList 中的 flag-based 伤害类型。
    # POB 中 "melee damage" = Damage INC + ModFlag.Melee，不是 MeleeDamage INC。
    # 注入时通过 NewMod 第5参数传递 flags，由 SumInternal 的 band(cfg.flags, mod.flags)==mod.flags 匹配。
    "melee_damage_inc": {
        "mod_name": "Damage", "mod_type": "INC",
        "label": "increased Melee Damage",
        "description": "近战伤害增加（仅近战攻击生效，POB中为 Damage INC + ModFlag.Melee）",
        "search_max": 500,
        "flags": 0x100,  # ModFlag.Melee
        "unit": "%",
    },
    "projectile_damage_inc": {
        "mod_name": "Damage", "mod_type": "INC",
        "label": "increased Projectile Damage",
        "description": "投射物伤害增加（仅投射物技能生效，POB中为 Damage INC + ModFlag.Projectile）",
        "search_max": 500,
        "flags": 0x400,  # ModFlag.Projectile
        "unit": "%",
    },
    "dot_damage_inc": {
        "mod_name": "Damage", "mod_type": "INC",
        "label": "increased Damage over Time",
        "description": "持续伤害增加（仅DOT生效，POB中为 Damage INC + ModFlag.Dot）",
        "search_max": 500,
        "flags": 0x08,  # ModFlag.Dot
        "unit": "%",
    },

    # === 暴击类 ===
    "crit_chance_inc": {
        "mod_name": "CritChance", "mod_type": "INC",
        "label": "increased Critical Hit Chance",
        "description": "暴击率增加（INC叠加到已有的INC总量）",
        "search_max": 1000, "unit": "%",
    },
    "crit_chance_base": {
        "mod_name": "CritChance", "mod_type": "BASE",
        "label": "to Critical Hit Chance",
        "description": "基础暴击率（加到技能基础暴击上，再被INC放大）",
        "search_max": 30, "unit": "%",
    },
    "crit_multi_inc": {
        "mod_name": "CritMultiplier", "mod_type": "INC",
        "label": "increased Critical Damage Bonus",
        "description": "暴击伤害增加（常见词缀，线性叠加到INC总量）",
        "search_max": 500, "unit": "%",
    },
    "crit_multi_base": {
        "mod_name": "CritMultiplier", "mod_type": "BASE",
        "label": "to Critical Damage Bonus",
        "description": "暴击伤害基础（稀有词缀如力量之盾，被INC放大）",
        "search_max": 200, "unit": "%",
    },

    # === 速度类 ===
    "speed_inc": {
        "mod_name": "Speed", "mod_type": "INC",
        "label": "increased Attack and Cast Speed",
        "description": "攻击/施法速度增加（通用，无flag限制）",
        "search_max": 300, "unit": "%",
    },
    "cast_speed_inc": {
        "mod_name": "Speed", "mod_type": "INC",
        "label": "increased Cast Speed",
        "description": "施法速度增加（仅非攻击技能，POB中为 Speed INC + ModFlag.Cast）",
        "search_max": 300,
        "flags": 0x10,  # ModFlag.Cast — 法术/非攻击技能有效
        "unit": "%",
    },
    "attack_speed_inc": {
        "mod_name": "Speed", "mod_type": "INC",
        "label": "increased Attack Speed",
        "description": "攻击速度增加（仅攻击技能，POB中为 Speed INC + ModFlag.Attack）",
        "search_max": 300,
        "flags": 0x01,  # ModFlag.Attack — 仅攻击技能有效
        "unit": "%",
    },
    "speed_more": {
        "mod_name": "Speed", "mod_type": "MORE",
        "label": "more Attack and Cast Speed",
        "description": "速度独立乘区，如辅助宝石效果",
        "search_max": 100, "unit": "%",
    },

    # === 穿透类（只有 BASE）===
    # 注：MAIN 模式已包含穿透计算（initEnv 默认 buffMode=EFFECTIVE）。
    # 穿透在敌人抗性为负时无效（CalcOffence.lua:3821 — resist <= minPen 时穿透不再降低抗性）。
    # 如果灵敏度显示穿透影响为 0，通常意味着构筑配置中敌人抗性已被诅咒/曝光压至负值。
    "lightning_pen": {
        "mod_name": "LightningPenetration", "mod_type": "BASE",
        "label": "Penetrate Lightning Resistance",
        "description": "闪电抗性穿透（敌人负抗时无效）",
        "search_max": 100, "unit": "%",
    },
    "fire_pen": {
        "mod_name": "FirePenetration", "mod_type": "BASE",
        "label": "Penetrate Fire Resistance",
        "description": "火焰抗性穿透（敌人负抗时无效）",
        "search_max": 100, "unit": "%",
    },
    "cold_pen": {
        "mod_name": "ColdPenetration", "mod_type": "BASE",
        "label": "Penetrate Cold Resistance",
        "description": "冰霜抗性穿透（敌人负抗时无效）",
        "search_max": 100, "unit": "%",
    },
    "elemental_pen": {
        "mod_name": "ElementalPenetration", "mod_type": "BASE",
        "label": "Penetrate Elemental Resistances",
        "description": "元素抗性穿透（对火/冰/电都生效，敌人负抗时无效）",
        "search_max": 100, "unit": "%",
    },
    "chaos_pen": {
        "mod_name": "ChaosPenetration", "mod_type": "BASE",
        "label": "Penetrate Chaos Resistance",
        "description": "混沌抗性穿透（敌人负抗时无效）",
        "search_max": 100, "unit": "%",
    },

    # === 投射物/AoE ===
    "projectile_count": {
        "mod_name": "ProjectileCount", "mod_type": "BASE",
        "label": "additional Projectiles",
        "description": "额外投射物数量（ProjectileCount没有INC类型）",
        "search_max": 20, "unit": "",
    },
    "aoe_inc": {
        "mod_name": "AreaOfEffect", "mod_type": "INC",
        "label": "increased Area of Effect",
        "description": "影响范围增加（对半径是平方根关系）",
        "search_max": 500, "unit": "%",
    },

    # === 持续时间 ===
    "duration_inc": {
        "mod_name": "Duration", "mod_type": "INC",
        "label": "increased Skill Effect Duration",
        "description": "技能持续时间增加",
        "search_max": 500, "unit": "%",
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
        "search_max": 500, "unit": "",
    },
    "flat_fire_attack": {
        "mod_name": "FireMin+Max", "mod_type": "BASE",
        "label": "Adds Fire Damage to Attacks",
        "description": "添加固定火焰伤害（仅攻击）",
        "search_max": 500, "unit": "",
    },
    "flat_cold_attack": {
        "mod_name": "ColdMin+Max", "mod_type": "BASE",
        "label": "Adds Cold Damage to Attacks",
        "description": "添加固定冰霜伤害（仅攻击）",
        "search_max": 500, "unit": "",
    },
    "flat_physical_attack": {
        "mod_name": "PhysicalMin+Max", "mod_type": "BASE",
        "label": "Adds Physical Damage to Attacks",
        "description": "添加固定物理伤害（仅攻击）",
        "search_max": 300, "unit": "",
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
    "attack_damage_inc", "attack_speed_inc",
    "melee_damage_inc",  # 近战也是攻击专属
}

# 法术专属 profile 集合（攻击构筑灵敏度分析时自动排除）
_SPELL_ONLY_PROFILES = {
    "spell_damage_inc", "cast_speed_inc",
}

# DOT 专属 profile 集合（hit-based 构筑灵敏度分析时自动排除）
_DOT_ONLY_PROFILES = {
    "dot_damage_inc",
}

# 投射物专属 profile 集合（非投射物构筑灵敏度分析时自动排除）
_PROJECTILE_ONLY_PROFILES = {
    "projectile_damage_inc",
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


def _detect_skill_flags(lua, calcs) -> dict:
    """自动检测主技能的完整 flag 信息。

    Returns:
        {"is_spell": bool, "is_projectile": bool, "is_dot": bool, "is_melee": bool,
         "is_area": bool, "raw_flags": int}
    """
    result = lua.execute('''
        local build = _spike_build
        local env = calcs.initEnv(build, "MAIN")
        calcs.perform(env)
        local ms = env.player.mainSkill
        if ms and ms.skillCfg then
            return tostring(ms.skillCfg.flags or 0)
        end
        return "0"
    ''')
    try:
        raw_flags = int(str(result).strip())
    except (ValueError, TypeError):
        raw_flags = 0

    flags = {
        "is_spell":      bool(raw_flags & 0x02),   # ModFlag.Spell
        "is_attack":     bool(raw_flags & 0x01),   # ModFlag.Attack
        "is_dot":        bool(raw_flags & 0x08),   # ModFlag.Dot
        "is_cast":       bool(raw_flags & 0x10),   # ModFlag.Cast
        "is_melee":      bool(raw_flags & 0x100),  # ModFlag.Melee
        "is_projectile": bool(raw_flags & 0x400),  # ModFlag.Projectile
        "is_area":       bool(raw_flags & 0x200),  # ModFlag.Area
        "raw_flags":     raw_flags,
    }
    logger.info("主技能 flags: 0x%x — %s", raw_flags,
                ", ".join(k for k, v in flags.items() if v and k != "raw_flags"))
    return flags


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
            "unit": 单位（"%" 或 ""）,
            "dps_per_unit": 每单位数值对 DPS 的贡献百分比（actual_pct / needed_value）,
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

    # 获取完整 flag 信息，用于精确排除不适用的 profile
    skill_flags = _detect_skill_flags(lua, calcs)

    if profiles is None:
        profiles = list(SENSITIVITY_PROFILES.keys())

        # 基于技能 flags 精确排除不适用的 profile
        excluded = set()

        if is_spell or skill_flags["is_spell"]:
            # 法术构筑排除攻击专属 profile（含 flat damage、attack damage、attack speed、melee）
            excluded |= _ATTACK_ONLY_PROFILES
            logger.info("法术构筑：排除 %d 个攻击专属 profile", len(_ATTACK_ONLY_PROFILES))
        else:
            # 攻击构筑排除法术专属 profile（spell damage、cast speed）
            excluded |= _SPELL_ONLY_PROFILES
            logger.info("攻击构筑：排除 %d 个法术专属 profile", len(_SPELL_ONLY_PROFILES))

        if not skill_flags["is_projectile"]:
            # 非投射物技能排除投射物专属 profile
            excluded |= _PROJECTILE_ONLY_PROFILES
            logger.info("非投射物技能：排除 projectile_damage_inc")

        if not skill_flags["is_dot"]:
            # 非 DOT 技能排除 DOT 专属 profile
            excluded |= _DOT_ONLY_PROFILES
            logger.info("非DOT技能：排除 dot_damage_inc")

        profiles = [p for p in profiles if p not in excluded]

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
        unit = profile.get("unit", "%")

        # 查询当前 modDB 汇总值
        if mod_type == "INC" and mod_name in _DAMAGE_INC_STATS:
            # 伤害 INC 使用该 stat 对应的伤害类型的合并值
            # 根据 mod_name 确定对应的伤害类型
            per_type = merged_inc_cache.get("per_type_inc", {})
            main_type = merged_inc_cache.get("main_damage_type", "Physical")
            main_merged = merged_inc_cache.get("merged_damage_inc", 0.0)

            if mod_name in ("Damage", "ElementalDamage"):
                # 通用/元素伤害：显示主伤害类型的合并值
                current_total = main_merged
            elif mod_name == "ColdDamage":
                current_total = per_type.get("Cold", main_merged)
            elif mod_name == "FireDamage":
                current_total = per_type.get("Fire", main_merged)
            elif mod_name == "LightningDamage":
                current_total = per_type.get("Lightning", main_merged)
            elif mod_name == "PhysicalDamage":
                current_total = per_type.get("Physical", main_merged)
            elif mod_name == "ChaosDamage":
                current_total = per_type.get("Chaos", main_merged)
            else:
                current_total = main_merged
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

        # 计算每单位数值对 DPS 的贡献百分比
        # dps_per_unit = target_pct / needed_value（即每 1 单位注入带来多少 % DPS）
        if needed_value is not None and needed_value > 0:
            dps_per_unit = round(actual_pct / needed_value, 4)
        else:
            dps_per_unit = None

        results.append({
            "key": key,
            "label": label,
            "description": description,
            "mod_name": mod_name,
            "mod_type": mod_type,
            "needed_value": needed_value,
            "unit": unit,
            "dps_per_unit": dps_per_unit,
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
        local output = env.player.output

        -- damageStatsForTypes 合并逻辑（CalcOffence.lua:53-63）
        local dmgTypeFlags = {
            Physical = 0x01, Lightning = 0x02, Cold = 0x04,
            Fire = 0x08, Elemental = 0x0E, Chaos = 0x10,
        }
        local dmgFlagOrder = { "Physical", "Lightning", "Cold", "Fire", "Elemental", "Chaos" }

        -- 查找主伤害类型：从 output 找 XxxHitAverage 最高的
        -- output 中存储的是 XxxHitAverage / XxxCritAverage（非 XxxTotalDPS）
        local dmgTypes = {"Physical", "Lightning", "Cold", "Fire", "Chaos"}
        local bestType = nil
        local bestAvg = 0
        for _, dt in ipairs(dmgTypes) do
            local avg = output[dt.."HitAverage"] or output[dt.."CritAverage"] or 0
            if avg > bestAvg then
                bestAvg = avg
                bestType = dt
            end
        end

        -- 如果没有 hit 伤害（纯 DOT 构筑），尝试从 DotDPS 找
        if not bestType or bestAvg == 0 then
            for _, dt in ipairs(dmgTypes) do
                local dotDps = output[dt.."DotDPS"] or 0
                if dotDps > bestAvg then
                    bestAvg = dotDps
                    bestType = dt
                end
            end
        end

        bestType = bestType or "Physical"

        -- 对每个有伤害的类型，分别计算合并 INC 和 typeFlags
        -- 返回所有有伤害类型的合并 INC（取最高的作为主要值）
        local results = {}

        for _, dt in ipairs(dmgTypes) do
            local avg = output[dt.."HitAverage"] or 0
            if avg > 0 then
                local typeFlags = dmgTypeFlags[dt] or 0
                local modNames = { "Damage" }
                for _, tp in ipairs(dmgFlagOrder) do
                    local flag = dmgTypeFlags[tp]
                    if flag and (typeFlags & flag) ~= 0 then
                        modNames[#modNames+1] = tp .. "Damage"
                    end
                end
                local inc = skillModList:Sum("INC", cfg, unpack(modNames))
                results[#results+1] = dt .. ":" .. tostring(inc)
            end
        end

        -- 主伤害类型的合并 INC
        local mainTypeFlags = dmgTypeFlags[bestType] or 0
        local mainModNames = { "Damage" }
        for _, tp in ipairs(dmgFlagOrder) do
            local flag = dmgTypeFlags[tp]
            if flag and (mainTypeFlags & flag) ~= 0 then
                mainModNames[#mainModNames+1] = tp .. "Damage"
            end
        end
        local mainInc = skillModList:Sum("INC", cfg, unpack(mainModNames))

        return tostring(mainInc) .. "|" .. bestType .. "|" .. table.concat(results, ",")
    ''')

    merged_inc = 0.0
    main_type = "Physical"
    per_type_inc = {}
    if result:
        parts = str(result).split('|')
        try:
            merged_inc = float(parts[0])
        except (ValueError, IndexError):
            pass
        if len(parts) > 1:
            main_type = parts[1]
        if len(parts) > 2 and parts[2]:
            # 解析每个类型的合并 INC: "Cold:219,Fire:209,Lightning:108"
            for item in parts[2].split(','):
                if ':' in item:
                    dt, val = item.split(':', 1)
                    try:
                        per_type_inc[dt] = float(val)
                    except ValueError:
                        pass

    logger.info("伤害 INC 合并值: %.1f%% (主伤害类型: %s, 各类型: %s)",
                merged_inc, main_type,
                ", ".join(f"{k}={v:.0f}" for k, v in per_type_inc.items()))
    return {
        "merged_damage_inc": merged_inc,
        "main_damage_type": main_type,
        "per_type_inc": per_type_inc,
    }


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
    flags = profile.get("flags", 0)

    if key in _FLAT_DAMAGE_PROFILES:
        min_name, max_name = _FLAT_DAMAGE_PROFILES[key]
        int_val = int(round(value))
        max_val = int_val * 2  # Min:Max = 1:2
        mod_lines = (
            f'        env.modDB:NewMod("{min_name}", "BASE", {int_val}, "WhatIf")\n'
            f'        env.modDB:NewMod("{max_name}", "BASE", {max_val}, "WhatIf")'
        )
    elif flags:
        # 带 flags 的 mod 注入（如 Spell Damage = Damage INC + ModFlag.Spell）
        int_val = int(round(value)) if mod_type == "BASE" else value
        mod_lines = (
            f'        env.modDB:NewMod("{mod_name}", "{mod_type}", {int_val}, "WhatIf", {flags})'
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
    # CalcSetup.lua 中 addNodes/removeNodes 使用两种不同的 key 格式：
    #   第 707 行：for node in pairs(override.addNodes) — node 对象作为 key
    #   第 734 行：override.removeNodes[node] — node 对象作为 key（普通天赋）
    #   第 1291 行：override.removeNodes[node.id] — 整数 node.id 作为 key（GrantedPassive）
    # 必须同时设置两种 key 才能正确处理 GrantedPassive 珠宝分配的天赋节点。
    add_ids = ','.join(str(nid) for nid in add)
    remove_ids = ','.join(str(nid) for nid in remove)

    result = lua.execute(f'''
        local build = _spike_build
        local addNodes = {{}}
        local removeNodes = {{}}

        -- addNodes: CalcSetup:707 uses `for node in pairs(override.addNodes)`
        -- key = node object
        for _, nid in ipairs({{ {add_ids} }}) do
            local node = build.spec.nodes[nid]
            if node then addNodes[node] = true end
        end

        -- removeNodes: CalcSetup has TWO key formats:
        --   line 734:  removeNodes[node]    (node object) — regular allocNodes
        --   line 1291: removeNodes[node.id] (integer)     — GrantedPassive nodes
        -- We set both keys so both code paths work correctly.
        for _, nid in ipairs({{ {remove_ids} }}) do
            local node = build.spec.nodes[nid]
            if node then
                removeNodes[node] = true     -- for CalcSetup:734 (regular passives)
                removeNodes[node.id] = true  -- for CalcSetup:1291 (GrantedPassive)
            end
        end

        local override = {{
            addNodes = addNodes,
            removeNodes = removeNodes,
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


def _get_unallocated_notable_nodes(lua) -> list[dict]:
    """获取天赋树上未分配的 Notable / Keystone 节点列表。

    从 spec.nodes（全部节点）中排除 spec.allocNodes（已分配节点），
    仅返回 Notable 和 Keystone 类型的节点。
    """
    result = lua.execute('''
        local build = _spike_build
        local nodes = {}
        for id, node in pairs(build.spec.nodes) do
            if not build.spec.allocNodes[id] then
                if node.type == "Notable" or node.type == "Keystone" then
                    -- 排除升华节点（不同升华的节点不应混入）
                    if not node.ascendancyName or node.ascendancyName == build.spec.curAscendClassName then
                        nodes[#nodes+1] = tostring(id) .. "|" .. (node.dn or "?") .. "|" .. (node.type or "?")
                    end
                end
            end
        end
        return table.concat(nodes, "\\n")
    ''')
    nodes = []
    if result:
        for line in str(result).strip().split('\n'):
            if not line:
                continue
            parts = line.split('|', 2)
            if len(parts) == 3:
                try:
                    nodes.append({
                        'id': int(parts[0]),
                        'name': parts[1],
                        'type': parts[2],
                    })
                except ValueError:
                    pass
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


def passive_node_exploration(lua, calcs, baseline: dict = None,
                             dps_stat: str = "TotalDPS",
                             ehp_stat: str = "TotalEHP",
                             min_dps_pct: float = 0.5) -> list[dict]:
    """天赋探索分析：逐个添加未分配的 Notable/Keystone，评估 DPS 和 EHP 收益。

    使用 POB 原生 override.addNodes 机制临时添加节点，不修改 build 对象。
    注意：由于绕过了路径连通性检查，部分节点在实际游戏中可能无法直接点出。

    Args:
        baseline: 基线 output
        dps_stat: DPS 指标名（默认 TotalDPS）
        ehp_stat: EHP 指标名（默认 TotalEHP）
        min_dps_pct: 最小 DPS 变化百分比阈值（低于此值不显示，默认 0.5%）

    Returns:
        按 DPS 增益降序排列：
        [{id, name, type, dps_pct, ehp_pct, category}, ...]
        category: "进攻" / "防御" / "混合" / "无效"
    """
    if baseline is None:
        baseline = calculate(lua, calcs)

    nodes = _get_unallocated_notable_nodes(lua)
    logger.info("天赋探索: %d 个未分配 Notable/Keystone", len(nodes))

    base_dps = baseline.get(dps_stat, 0)
    base_ehp = baseline.get(ehp_stat, 0)

    results = []
    for node in nodes:
        nid = node['id']
        diff = what_if_nodes(lua, calcs, add=[nid], baseline=baseline)

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

        # 只保留有意义的结果
        if abs(dps_pct) >= min_dps_pct or abs(ehp_pct) >= min_dps_pct:
            results.append({
                "id": nid, "name": node['name'], "type": node['type'],
                "dps_before": base_dps, "dps_after": dps_after,
                "dps_delta": dps_delta, "dps_pct": round(dps_pct, 2),
                "ehp_before": base_ehp, "ehp_after": ehp_after,
                "ehp_delta": ehp_delta, "ehp_pct": round(ehp_pct, 2),
                "category": category,
            })

    results.sort(key=lambda x: x["dps_pct"], reverse=True)
    return results


# =============================================================================
# 珠宝诊断
# =============================================================================


def diagnose_jewels(lua, calcs, baseline: dict = None,
                    dps_stat: str = "TotalDPS") -> list[dict]:
    """诊断构筑中所有珠宝的加载状态和 DPS 贡献。

    检查每个珠宝是否正确加载、mod 是否被解析、是否影响 DPS。
    特别关注 Megalomaniac 等通过 "Allocates" 分配天赋的珠宝。

    Returns:
        [{
            "slot_name": 槽位名,
            "node_id": 天赋树节点 ID,
            "item_id": 物品 ID,
            "name": 物品名称（如 "Megalomaniac"）,
            "base_type": 基础类型（如 "Large Jewel"）,
            "rarity": 稀有度,
            "mod_count": mod 数量,
            "mods": mod 列表 [{"name", "type", "value", "source"}],
            "granted_passives": 分配的天赋节点名称列表,
            "dps_pct": 移除此珠宝后 DPS 变化百分比,
            "status": "ok" / "empty" / "no_base" / "no_mods",
        }, ...]
    """
    if baseline is None:
        baseline = calculate(lua, calcs)

    base_dps = baseline.get(dps_stat, 0)

    # 从 Lua 端获取所有珠宝槽位信息
    result = lua.execute('''
        local build = _spike_build
        local lines = {}

        for _, slot in ipairs(build.itemsTab.orderedSlots) do
            local sn = slot.slotName or ""
            if sn:find("^Jewel ") then
                local itemId = slot.selItemId or 0
                local nodeId = slot.nodeId or 0
                local item = build.itemsTab.items[itemId]
                if item and item.base then
                    local name = item.title or item.name or "?"
                    local baseType = item.base.name or item.baseName or "?"
                    local rarity = item.rarity or "?"

                    -- 收集 mod 信息（mod 结构: {name=str, type=str, value=...}）
                    -- 注意：m.name 或 m[1] 可能是 table（如 tag 列表），需用 tostring 安全转换
                    local modTexts = {}
                    local grantedPassives = {}
                    if item.modList then
                        for i = 1, #item.modList do
                            local m = item.modList[i]
                            local mName = type(m.name) == "string" and m.name
                                or type(m[1]) == "string" and m[1]
                                or tostring(m.name or m[1] or "?")
                            local mType = tostring(m.type or "?")
                            local mVal = tostring(m.value or 0)
                            modTexts[#modTexts+1] = mName .. "|" .. mType .. "|" .. mVal

                            -- 检查 GrantedPassive（Megalomaniac / Forbidden Flame 等）
                            if mName == "GrantedPassive" and mType == "LIST" then
                                grantedPassives[#grantedPassives+1] = tostring(m.value or "?")
                            end
                        end
                    end

                    -- 检查 variant 信息（Megalomaniac 用 3-variant 系统）
                    local variantInfo = ""
                    if item.variant then
                        variantInfo = tostring(item.variant)
                    end
                    if item.variantAlt then
                        variantInfo = variantInfo .. "," .. tostring(item.variantAlt)
                    end
                    if item.variantAlt2 then
                        variantInfo = variantInfo .. "," .. tostring(item.variantAlt2)
                    end

                    lines[#lines+1] = tostring(nodeId) .. "@@"
                        .. tostring(itemId) .. "@@"
                        .. name .. "@@"
                        .. baseType .. "@@"
                        .. rarity .. "@@"
                        .. tostring(#modTexts) .. "@@"
                        .. table.concat(modTexts, ";;") .. "@@"
                        .. table.concat(grantedPassives, ";;") .. "@@"
                        .. variantInfo
                elseif itemId > 0 then
                    -- 物品存在但没有 base（解析失败）
                    lines[#lines+1] = tostring(nodeId) .. "@@"
                        .. tostring(itemId) .. "@@?@@?@@?@@0@@@@@@no_base"
                else
                    -- 空槽位
                    lines[#lines+1] = tostring(nodeId) .. "@@0@@@@@@@@0@@@@@@empty"
                end
            end
        end
        return table.concat(lines, "\\n")
    ''')

    jewels = []
    if result:
        for line in str(result).strip().split('\n'):
            if not line:
                continue
            parts = line.split('@@')
            if len(parts) < 9:
                continue

            node_id = int(parts[0]) if parts[0].isdigit() else 0
            item_id = int(parts[1]) if parts[1].isdigit() else 0
            name = parts[2] or "?"
            base_type = parts[3] or "?"
            rarity = parts[4] or "?"
            mod_count = int(parts[5]) if parts[5].isdigit() else 0
            variant_info = parts[8] if len(parts) > 8 else ""

            # 解析 mod 列表
            mods = []
            if parts[6]:
                for mod_text in parts[6].split(';;'):
                    if '|' in mod_text:
                        mp = mod_text.split('|', 2)
                        mods.append({
                            "name": mp[0],
                            "type": mp[1] if len(mp) > 1 else "?",
                            "value": mp[2] if len(mp) > 2 else "0",
                        })

            # 解析 GrantedPassive
            granted_passives = []
            if parts[7]:
                granted_passives = [p for p in parts[7].split(';;') if p]

            # 判断状态
            if variant_info == "no_base":
                status = "no_base"
            elif variant_info == "empty" or item_id == 0:
                status = "empty"
            elif mod_count == 0:
                status = "no_mods"
            else:
                status = "ok"

            jewels.append({
                "slot_name": f"Jewel {node_id}",
                "node_id": node_id,
                "item_id": item_id,
                "name": name,
                "base_type": base_type,
                "rarity": rarity,
                "mod_count": mod_count,
                "mods": mods,
                "granted_passives": granted_passives,
                "variant_info": variant_info,
                "dps_pct": 0.0,
                "status": status,
            })

    # 对每个有效珠宝测试 DPS 贡献
    #
    # 两种测试方式：
    #   1) 普通珠宝（rare/magic/unique 无 GrantedPassive）：
    #      临时将 slot.selItemId=0 + spec.jewels[nodeId]=nil，移除珠宝物品
    #      CalcSetup:838 在 allocNodes[nodeId] 存在时处理珠宝 mod，
    #      同时清除 spec.jewels 确保 CalcSetup 不会从中读取物品。
    #
    #   2) GrantedPassive 珠宝（Megalomaniac, Forbidden Flame 等）：
    #      这类珠宝的核心收益来自 "Allocates X" 分配的天赋节点，
    #      仅移除物品不会影响 DPS（因为天赋已经被分配到 allocNodes 中）。
    #      需要额外通过 override.removeNodes 移除 granted 节点来评估。
    #      使用双 key 格式：removeNodes[node]=true + removeNodes[node.id]=true
    #      以兼容 CalcSetup:734（普通天赋）和 CalcSetup:1291（GrantedPassive）。
    for jewel in jewels:
        if jewel["status"] != "ok" or base_dps == 0:
            continue

        node_id = jewel["node_id"]
        slot_name = jewel["slot_name"]

        # 测试1：移除珠宝物品（对 rare jewel mods 有效）
        try:
            diff_result = lua.execute(f'''
                local build = _spike_build
                local slot = build.itemsTab.slots['{slot_name}']
                if not slot then return tostring({base_dps}) end
                local originalId = slot.selItemId
                local originalJewel = build.spec.jewels[{node_id}]
                slot.selItemId = 0
                build.spec.jewels[{node_id}] = nil
                local env = calcs.initEnv(build, "MAIN")
                calcs.perform(env)
                local dps = env.player.output.TotalDPS or 0
                slot.selItemId = originalId
                build.spec.jewels[{node_id}] = originalJewel
                return tostring(dps)
            ''')
            after_dps = float(str(diff_result)) if diff_result else base_dps
            dps_delta = after_dps - base_dps
            jewel["dps_pct"] = round(dps_delta / base_dps * 100, 2) if base_dps != 0 else 0.0
        except Exception as e:
            logger.warning("珠宝 DPS 诊断失败 %s: %s", slot_name, e)

        # 测试2：对有 GrantedPassive 的珠宝，额外测试移除 granted 节点的 DPS
        if jewel.get("granted_passives"):
            granted_names = jewel["granted_passives"]
            try:
                # 在 Lua 端查找 notableMap 中对应的节点 ID
                names_lua = ', '.join(f'"{name}"' for name in granted_names)
                granted_diff = lua.execute(f'''
                    local build = _spike_build
                    local tree = build.spec.tree
                    local removeNodes = {{}}
                    local names = {{ {names_lua} }}
                    for _, name in ipairs(names) do
                        local node = tree.notableMap[name]
                        if node then
                            removeNodes[node] = true
                            removeNodes[node.id] = true
                        end
                    end
                    local override = {{ removeNodes = removeNodes }}
                    local env = calcs.initEnv(build, "CALCULATOR", override)
                    calcs.perform(env)
                    return tostring(env.player.output.TotalDPS or 0)
                ''')
                gp_after_dps = float(str(granted_diff)) if granted_diff else base_dps
                gp_dps_delta = gp_after_dps - base_dps
                gp_dps_pct = round(gp_dps_delta / base_dps * 100, 2) if base_dps != 0 else 0.0

                jewel["granted_dps_pct"] = gp_dps_pct
                # 取物品移除和节点移除中影响更大的作为总 DPS 贡献
                if abs(gp_dps_pct) > abs(jewel["dps_pct"]):
                    jewel["dps_pct"] = gp_dps_pct
                    jewel["dps_source"] = "granted_passives"
                else:
                    jewel["dps_source"] = "item_mods"
            except Exception as e:
                logger.warning("GrantedPassive DPS 诊断失败 %s: %s", slot_name, e)

    # 按 DPS 贡献降序排列（绝对值最大的在前）
    jewels.sort(key=lambda x: abs(x["dps_pct"]), reverse=True)
    return jewels


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
# DPS 来源拆解（v1.0.11）
# =============================================================================
#
# 设计原则：
#   1. Output-driven：从 output 非零值判断哪些公式项活跃
#   2. Tabulate 拆解：对每个活跃公式项调用 skillModList:Tabulate() 获取 mod 级来源
#   3. 两层粒度：第一层按公式项分组，第二层每组内按 source 展开全部 mod
#   4. Source 分类：mod.source 前缀 — Base/Tree/Item/Skill/Config
#   5. Label 可读化：Tree→天赋名，Item→物品名，Skill→技能名
#   6. category_summary：每个公式项内按 category 聚合的汇总值
#
# Spike 确认（本轮探索）：
#   - Tabulate("MORE") 的 entry.value 是百分比原值（如 39，不是 1.39）
#     MoreInternal 内部做 result *= (1 + value/100)
#   - node.dn 可靠（PassiveTree.lua 构建时设置，_get_notable_nodes 已验证）
#   - Base Damage 由三部分组成：
#     宝石/武器基础: source[{Type}Min/Max]
#     added damage 词缀: skillModList:Sum("BASE", cfg, "{Type}Min/Max") → 可 Tabulate
#     baseMultiplier: grantedEffectLevel.baseMultiplier
#
# POB mod.source 格式：
#   "Base"                    → 游戏常量
#   "Tree:{nodeId}"           → 被动天赋
#   "Item:{itemId}:{name}"    → 装备/珠宝
#   "Skill:{skillId}"         → 技能宝石
#   "Config"                  → 面板设置


def _classify_source(source: str, jewel_node_ids: set = None) -> str:
    """将 mod.source 字符串分类为来源类型。

    珠宝半径效果的 source 格式为 "Tree:{nodeId}"，其中 nodeId 是珠宝槽位。
    通过 jewel_node_ids 集合识别这些节点，将其分类为 "Jewel" 而非 "Tree"。
    """
    if not source:
        return "Other"
    prefix = source.split(":")[0] if ":" in source else source
    if prefix == "Tree" and jewel_node_ids:
        node_id = source.split(":")[1] if ":" in source else ""
        if node_id in jewel_node_ids:
            return "Jewel"
    if prefix in ("Base", "Tree", "Item", "Skill", "Config"):
        return prefix
    return "Other"


def _source_label_fallback(source: str) -> str:
    """当 Lua 端未返回 label 时的 fallback 转换。"""
    if not source:
        return "未知"
    if source == "Base":
        return "基础值"
    if source == "Config":
        return "配置"
    prefix = source.split(":")[0] if ":" in source else source
    rest = source[len(prefix)+1:] if ":" in source else ""
    if prefix == "Tree":
        return f"天赋#{rest}"
    if prefix == "Item":
        name = rest.split(":", 1)[-1] if ":" in rest else rest
        return name if name else f"物品#{rest}"
    if prefix == "Skill":
        return f"技能#{rest}"
    if prefix == "Jewel":
        return f"珠宝#{rest}"
    return source


def dps_breakdown(lua, calcs, baseline: dict = None) -> dict:
    """DPS 来源拆解 — 将当前 DPS 的每个公式项拆解到具体来源。

    Output-driven：从 output.* 非零值判断活跃公式组件，
    对每个组件调用 skillModList:Tabulate() 获取 mod 来源。
    两层粒度：按公式项分组，每组内按 source 分类。
    Label 可读化：天赋→名称，装备→物品名，技能→宝石名。

    Args:
        lua: LuaRuntime
        calcs: POB calcs 模块
        baseline: 基线 output（None 则重新计算）

    Returns:
        {
            "total_dps": float,
            "average_hit": float,
            "speed": float,
            "combined_dps": float,
            "active_damage_types": [str],
            "formula_items": [
                {
                    "key": str,
                    "formula_name": str,
                    "total_value": float,
                    "display_value": str,
                    "category_summary": {category: float},
                    "sources": [{source, label, category, value, mod_name}, ...]
                }, ...
            ]
        }
    """
    if baseline is None:
        baseline = calculate(lua, calcs)

    # 如果 TotalDPS=0，自动切换到最大 DPS 的技能组
    if baseline.get("TotalDPS", 0) == 0:
        best_group, best_dps = _find_best_dps_socket_group(lua, calcs)
        if best_group is not None and best_dps > 0:
            lua.execute(f'_spike_build.mainSocketGroup = {best_group}')
            baseline = calculate(lua, calcs)
            logger.info("dps_breakdown: 自动切换到技能组 %d (DPS=%.0f)", best_group, best_dps)

    # 一次 Lua 调用完成全部查询
    # 输出格式：每行 SECTION|... 用 \n 分隔
    # Tabulate entries: modName\1source\1value\1label 用 \2 分隔
    lua_script = r'''
        local build = _spike_build
        local env = calcs.initEnv(build, "MAIN")
        calcs.perform(env)
        local ms = env.player.mainSkill
        if not ms then return "" end

        local cfg = ms.skillCfg
        local skillModList = ms.skillModList
        local output = env.player.output
        local lines = {}

        -- === 建立 source → 可读名 映射 ===
        local nodeNames = {}
        for id, node in pairs(build.spec.allocNodes) do
            nodeNames[tostring(id)] = node.dn or ("Node "..tostring(id))
        end
        -- 未分配节点也查（可能有 granted passive 等）
        if build.spec.tree and build.spec.tree.nodes then
            for id, node in pairs(build.spec.tree.nodes) do
                if not nodeNames[tostring(id)] then
                    nodeNames[tostring(id)] = node.dn or ("Node "..tostring(id))
                end
            end
        end

        local skillNames = {}
        if env.player.activeSkillList then
            for _, sk in ipairs(env.player.activeSkillList) do
                local ge = sk.activeEffect and sk.activeEffect.grantedEffect
                if ge then
                    local modSrc = ge.modSource or ""
                    local sid = modSrc:match("Skill:(.+)")
                    if sid and ge.name then
                        skillNames[sid] = ge.name
                    end
                end
                -- 辅助宝石也纳入映射
                if sk.supportList then
                    for _, sup in ipairs(sk.supportList) do
                        local sge = sup.grantedEffect
                        if sge then
                            local sms = sge.modSource or ""
                            local ssid = sms:match("Skill:(.+)")
                            if ssid and sge.name then
                                skillNames[ssid] = sge.name
                            end
                        end
                    end
                end
            end
        end

        -- 物品名映射 + slot 部位映射
        local itemNames = {}
        local itemNameToSlot = {} -- "物品名, 基底" → slotName（用于标注部位）
        if build.itemsTab and build.itemsTab.items then
            for id, item in pairs(build.itemsTab.items) do
                if item.name then
                    itemNames[tostring(id)] = item.name
                end
            end
        end
        -- 通过 orderedSlots 建立 物品名 → slotName 映射
        -- 因为 mod source 中 itemId 始终是 -1 (Item.lua:1760)，只能用名称匹配
        if build.itemsTab and build.itemsTab.orderedSlots then
            for _, slot in ipairs(build.itemsTab.orderedSlots) do
                if slot.selItemId and slot.selItemId ~= 0 and slot.slotName then
                    local sItem = build.itemsTab.items[slot.selItemId]
                    if sItem and sItem.name then
                        -- key = "物品名" (不含基底)
                        itemNameToSlot[sItem.name] = slot.slotName
                        -- 也存 "物品名, 基底" 格式（mod source 中的 name 含基底）
                        if sItem.baseName then
                            itemNameToSlot[sItem.name .. ", " .. sItem.baseName] = slot.slotName
                        end
                    end
                end
            end
        end

        -- 珠宝节点映射：nodeId → 物品名
        -- 珠宝半径效果的 mod 使用 source="Tree:{nodeId}"，需要识别为 Jewel 而非 Tree
        -- 同时需要识别 GrantedPassive（如 Megalomaniac "Allocates"）分配的天赋节点
        local jewelNodeMap = {}
        if build.itemsTab and build.itemsTab.orderedSlots then
            for _, slot in ipairs(build.itemsTab.orderedSlots) do
                local sn = slot.slotName or ""
                if sn:find("^Jewel ") and slot.nodeId and slot.selItemId then
                    local jItem = build.itemsTab.items[slot.selItemId]
                    if jItem and jItem.name then
                        -- 珠宝槽位本身
                        jewelNodeMap[tostring(slot.nodeId)] = jItem.name

                        -- GrantedPassive 分配的天赋节点
                        -- (source="Tree:{grantedNodeId}"，需要用 notableMap 查找)
                        if jItem.modList then
                            for mi = 1, #jItem.modList do
                                local m = jItem.modList[mi]
                                local mName = type(m.name) == "string" and m.name or (type(m[1]) == "string" and m[1] or "")
                                if mName == "GrantedPassive" and m.value then
                                    local gpName = tostring(m.value)
                                    -- 通过 notableMap 找到节点 ID
                                    if build.spec.tree and build.spec.tree.notableMap then
                                        local gpNode = build.spec.tree.notableMap[gpName]
                                        if gpNode and gpNode.id then
                                            jewelNodeMap[tostring(gpNode.id)] = jItem.name .. " → " .. (gpNode.dn or gpName)
                                        end
                                    end
                                end
                            end
                        end
                    end
                end
            end
        end

        local function resolveLabel(src)
            if not src or src == "" then return "Unknown" end
            if src == "Base" then return "Base" end
            if src == "Config" then return "Config" end
            local prefix, rest = src:match("^([^:]+):(.+)$")
            if not prefix then return src end
            if prefix == "Tree" then
                -- 检查是否是珠宝相关节点（珠宝槽位半径效果 或 GrantedPassive 天赋）
                if jewelNodeMap[rest] then
                    return jewelNodeMap[rest]
                end
                return nodeNames[rest] or ("Node "..rest)
            end
            if prefix == "Item" then
                local itemId = rest:match("^(%-?%d+)")
                if itemId then
                    -- source format: "Item:-1:Heart of the Well, Diamond" or "Item:3:xxx" or "Item:3"
                    local nameFromSrc = rest:match("^%-?%d+:(.+)$")
                    local displayName = nameFromSrc
                    if not displayName or displayName == "" then
                        displayName = itemNames[itemId] or ("Item "..itemId)
                    end
                    -- 附加 slot 部位标签（通过物品名匹配）
                    local slotLabel = itemNameToSlot[displayName]
                    if not slotLabel then
                        -- 尝试只用逗号前的名称部分匹配
                        local shortName = displayName:match("^([^,]+)")
                        if shortName then
                            slotLabel = itemNameToSlot[shortName]
                        end
                    end
                    if slotLabel then
                        -- 简化 "Jewel 61834" → "Jewel"
                        local displaySlot = slotLabel:match("^Jewel ") and "Jewel" or slotLabel
                        displayName = displayName .. " (" .. displaySlot .. ")"
                    end
                    return displayName
                end
                return rest
            end
            if prefix == "Skill" then
                return skillNames[rest] or ("Skill "..rest)
            end
            return src
        end

        -- === 序列化 Tabulate ===
        -- 每条: modName\1source\1value\1label
        local function tabStr(modType, ...)
            local tab = skillModList:Tabulate(modType, cfg, ...)
            local parts = {}
            for _, entry in ipairs(tab) do
                if entry.value ~= 0 then
                    local m = entry.mod
                    local src = m.source or "Unknown"
                    local name = type(m.name) == "string" and m.name or "?"
                    local lbl = resolveLabel(src)
                    parts[#parts+1] = name .. "\1" .. src .. "\1" .. tostring(entry.value) .. "\1" .. lbl
                end
            end
            return table.concat(parts, "\2")
        end

        -- === 1. 识别活跃伤害类型 ===
        local dmgTypes = {"Physical", "Lightning", "Cold", "Fire", "Chaos"}
        local activeDT = {}
        for _, dt in ipairs(dmgTypes) do
            if (output[dt.."HitAverage"] or 0) > 0 then
                activeDT[#activeDT+1] = dt
            end
        end
        lines[#lines+1] = "META|active_types|" .. table.concat(activeDT, ",")

        -- 输出珠宝节点 ID 列表（Python 端用于区分 Tree vs Jewel）
        local jnIds = {}
        for nid, _ in pairs(jewelNodeMap) do
            jnIds[#jnIds+1] = nid
        end
        if #jnIds > 0 then
            lines[#lines+1] = "META|jewel_nodes|" .. table.concat(jnIds, ",")
        end

        -- damageStatsForTypes 逻辑 (CalcOffence.lua:52-63)
        local dtFlags = {
            Physical=0x01, Lightning=0x02, Cold=0x04,
            Fire=0x08, Elemental=0x0E, Chaos=0x10,
        }
        local dtOrder = {"Physical","Lightning","Cold","Fire","Elemental","Chaos"}

        local function getModNames(tf)
            local mn = {"Damage"}
            for _, tp in ipairs(dtOrder) do
                local f = dtFlags[tp]
                if f and (tf & f) ~= 0 then
                    mn[#mn+1] = tp .. "Damage"
                end
            end
            return mn
        end

        -- === 2. Base Damage 拆解 ===
        local damageSource = ms.skillData.sourceInstance or (env.player.weaponData1 or {})
        local baseMultiplier = 1
        if ms.activeEffect and ms.activeEffect.grantedEffectLevel then
            baseMultiplier = ms.activeEffect.grantedEffectLevel.baseMultiplier or ms.skillData.baseMultiplier or 1
        end
        for _, dt in ipairs(activeDT) do
            local dtMin = dt.."Min"
            local dtMax = dt.."Max"
            -- 宝石/武器基础
            local gemMin = damageSource[dtMin] or 0
            local gemMax = damageSource[dtMax] or 0
            -- added damage (可 Tabulate)
            local addedMinSum = skillModList:Sum("BASE", cfg, dtMin)
            local addedMaxSum = skillModList:Sum("BASE", cfg, dtMax)
            local addedMinTab = tabStr("BASE", dtMin)
            local addedMaxTab = tabStr("BASE", dtMax)
            -- addedMult
            local addedMult = 1
            local addedMultINC = skillModList:Sum("INC", cfg, "Added"..dt.."Damage", "AddedDamage")
            local addedMultMORE = skillModList:More(cfg, "Added"..dt.."Damage", "AddedDamage")
            if addedMultINC ~= 0 or addedMultMORE ~= 1 then
                addedMult = (1 + addedMultINC / 100) * addedMultMORE
            end
            -- 总 base = (gem + added*addedMult) * baseMultiplier
            local totalMin = (gemMin + addedMinSum * addedMult) * baseMultiplier
            local totalMax = (gemMax + addedMaxSum * addedMult) * baseMultiplier
            if totalMin > 0 or totalMax > 0 then
                -- 格式: BASE_DMG|type|totalMin|totalMax|gemMin|gemMax|addedMult|baseMultiplier|addedMinTab|addedMaxTab
                lines[#lines+1] = "BASE_DMG|" .. dt .. "|"
                    .. tostring(totalMin) .. "|" .. tostring(totalMax) .. "|"
                    .. tostring(gemMin) .. "|" .. tostring(gemMax) .. "|"
                    .. tostring(addedMult) .. "|" .. tostring(baseMultiplier) .. "|"
                    .. addedMinTab .. "|" .. addedMaxTab
            end
        end

        -- === 3. Damage INC/MORE (按 mod 类别分组，不按伤害类型重复) ===
        -- 收集所有活跃伤害类型涉及的 mod 名称（去重）
        -- 例如 Lightning+Cold+Fire → {"Damage", "LightningDamage", "ColdDamage", "FireDamage", "ElementalDamage"}
        local allModNames = {}
        local seenModName = {}
        -- 同时记录每个 modName 影响的伤害类型
        local modNameAffects = {} -- modName → {dt1, dt2, ...}
        for _, dt in ipairs(activeDT) do
            local tf = dtFlags[dt]
            local mn = getModNames(tf)
            for _, m in ipairs(mn) do
                if not seenModName[m] then
                    seenModName[m] = true
                    allModNames[#allModNames+1] = m
                    modNameAffects[m] = {}
                end
                modNameAffects[m][#modNameAffects[m]+1] = dt
            end
        end
        -- 按优先级排序: Damage(通用) > ElementalDamage > 特定元素Damage
        local modNameOrder = {Damage=1, ElementalDamage=2, PhysicalDamage=3,
            LightningDamage=4, ColdDamage=5, FireDamage=6, ChaosDamage=7}
        table.sort(allModNames, function(a, b)
            return (modNameOrder[a] or 99) < (modNameOrder[b] or 99)
        end)
        -- 每个 modName 单独 Tabulate
        for _, modName in ipairs(allModNames) do
            local incSum = skillModList:Sum("INC", cfg, modName)
            local incTab = tabStr("INC", modName)
            local affects = table.concat(modNameAffects[modName], ",")
            if incSum ~= 0 or (incTab and incTab ~= "") then
                -- 格式: DMG_INC_BY_MOD|modName|incSum|affects|tabEntries
                lines[#lines+1] = "DMG_INC_BY_MOD|" .. modName .. "|" .. tostring(incSum) .. "|" .. affects .. "|" .. incTab
            end
        end
        -- MORE 类似处理（但通常只有 Damage MORE，特定元素 MORE 很少见）
        for _, modName in ipairs(allModNames) do
            local moreVal = skillModList:More(cfg, modName)
            local moreTab = tabStr("MORE", modName)
            if moreVal ~= 1 or (moreTab and moreTab ~= "") then
                local affects = table.concat(modNameAffects[modName], ",")
                lines[#lines+1] = "DMG_MORE_BY_MOD|" .. modName .. "|" .. tostring(moreVal) .. "|" .. affects .. "|" .. moreTab
            end
        end

        -- === 4. Speed ===
        if (output.Speed or 0) > 0 then
            -- 基础速度（非 modDB 中的值）
            local baseSpeed = 0
            local baseSpeedLabel = "Base"
            -- 判断是否攻击技能：ModFlag.Attack = 0x01
            local isAttack = cfg.flags and (cfg.flags & 0x01) ~= 0
            if isAttack and damageSource and damageSource.AttackRate then
                baseSpeed = damageSource.AttackRate
                baseSpeedLabel = "Weapon Attack Rate"
            elseif ms.skillData.castTimeOverride then
                baseSpeed = 1 / ms.skillData.castTimeOverride
                baseSpeedLabel = "Cast Time Override"
            elseif ms.skillData.castTime then
                baseSpeed = 1 / ms.skillData.castTime
                baseSpeedLabel = "Base Cast Rate"
            else
                -- 触发技能等：castTime 不可用，使用 output.Speed（已含 INC/MORE）
                baseSpeed = output.Speed
                baseSpeedLabel = "Trigger Rate (computed)"
            end
            lines[#lines+1] = "SPEED_BASE|Speed|" .. tostring(baseSpeed) .. "|" .. baseSpeedLabel
            local sInc = skillModList:Sum("INC", cfg, "Speed")
            lines[#lines+1] = "SPEED_INC|Speed|" .. tostring(sInc) .. "|" .. tabStr("INC", "Speed")
            local sMore = skillModList:More(cfg, "Speed")
            lines[#lines+1] = "SPEED_MORE|Speed|" .. tostring(sMore) .. "|" .. tabStr("MORE", "Speed")
        end

        -- === 5. CritChance ===
        if (output.CritChance or 0) > 0 then
            -- 宝石/武器固有基础暴击率（不在 modDB 中）
            local baseCrit = ms.skillData.CritChance or damageSource.CritChance or 0
            local ccB = skillModList:Sum("BASE", cfg, "CritChance")
            lines[#lines+1] = "CRIT_BASE|CritChance|" .. tostring(ccB) .. "|" .. tostring(baseCrit) .. "|" .. tabStr("BASE", "CritChance")
            local ccI = skillModList:Sum("INC", cfg, "CritChance")
            lines[#lines+1] = "CRIT_INC|CritChance|" .. tostring(ccI) .. "|" .. tabStr("INC", "CritChance")
            local ccM = skillModList:More(cfg, "CritChance")
            lines[#lines+1] = "CRIT_MORE|CritChance|" .. tostring(ccM) .. "|" .. tabStr("MORE", "CritChance")
        end

        -- === 6. CritMultiplier ===
        if (output.CritMultiplier or 0) > 0 and not skillModList:Flag(cfg, "NoCritMultiplier") then
            local cmB = skillModList:Sum("BASE", cfg, "CritMultiplier")
            lines[#lines+1] = "CRITMULTI_BASE|CritMultiplier|" .. tostring(cmB) .. "|" .. tabStr("BASE", "CritMultiplier")
            local cmI = skillModList:Sum("INC", cfg, "CritMultiplier")
            lines[#lines+1] = "CRITMULTI_INC|CritMultiplier|" .. tostring(cmI) .. "|" .. tabStr("INC", "CritMultiplier")
            local cmM = skillModList:More(cfg, "CritMultiplier")
            lines[#lines+1] = "CRITMULTI_MORE|CritMultiplier|" .. tostring(cmM) .. "|" .. tabStr("MORE", "CritMultiplier")
        end

        -- === 7. Lucky ===
        for _, dt in ipairs(activeDT) do
            local lc = 0
            if skillModList:Flag(cfg, "LuckyHits")
            or skillModList:Flag(cfg, "ElementalLuckHits")
            or skillModList:Flag(cfg, "CritLucky") then
                lc = 100
            else
                lc = skillModList:Sum("BASE", cfg, dt.."LuckyHitsChance", "LuckyHitsChance")
            end
            if lc > 0 then
                lines[#lines+1] = "LUCKY|" .. dt .. "|" .. tostring(lc) .. "|" .. tabStr("BASE", dt.."LuckyHitsChance", "LuckyHitsChance")
            end
        end

        return table.concat(lines, "\n")
    '''

    result = lua.execute(lua_script)

    active_types = []
    jewel_node_ids = set()  # 珠宝槽位节点 ID 集合
    formula_items = []

    if not result:
        return _empty_breakdown(baseline)

    raw = str(result).replace('\r', '')
    for line in raw.split('\n'):
        if not line.strip():
            continue

        # 先用 maxsplit=1 取 section，再按 section 类型决定分割策略
        section = line.split('|', 1)[0]

        if section == "META":
            parts = line.split('|')
            if len(parts) > 2:
                if parts[1] == "active_types":
                    active_types = [t.strip() for t in parts[2].split(',') if t.strip()]
                elif parts[1] == "jewel_nodes":
                    jewel_node_ids = {nid.strip() for nid in parts[2].split(',') if nid.strip()}

        elif section == "BASE_DMG":
            # 格式: BASE_DMG|type|totalMin|totalMax|gemMin|gemMax|addedMult|baseMult|addedMinTab|addedMaxTab
            # addedMaxTab（最后一个字段）可能含 |，用 maxsplit=9 保护
            parts = line.split('|', 9)
            _parse_base_damage(parts, formula_items, jewel_node_ids)

        elif section == "SPEED_BASE":
            # 格式: SPEED_BASE|Speed|baseSpeed|label
            parts = line.split('|', 3)
            _parse_speed_base(parts, formula_items)

        elif section in ("DMG_INC_BY_MOD", "DMG_MORE_BY_MOD",
                         "SPEED_INC", "SPEED_MORE",
                         "CRIT_INC", "CRIT_MORE",
                         "CRITMULTI_BASE", "CRITMULTI_INC", "CRITMULTI_MORE",
                         "LUCKY"):
            if section in ("DMG_INC_BY_MOD", "DMG_MORE_BY_MOD"):
                # 新格式: SECTION|modName|total|affects|entries
                parts = line.split('|', 4)
                mod_name = parts[1] if len(parts) > 1 else "?"
                affects = parts[3] if len(parts) > 3 else ""
                # 将 affects 列入 formula_name 显示
                affects_label = f" ({affects})" if affects else ""
                # 人类可读名称映射
                mod_display = {
                    "Damage": "通用伤害",
                    "ElementalDamage": "元素伤害",
                    "PhysicalDamage": "物理伤害",
                    "LightningDamage": "闪电伤害",
                    "ColdDamage": "冰霜伤害",
                    "FireDamage": "火焰伤害",
                    "ChaosDamage": "混沌伤害",
                }.get(mod_name, mod_name)
                if section == "DMG_INC_BY_MOD":
                    # 将 affects 和 tabEntries 打包为标准格式
                    # 构造与 _parse_tabulate_item 兼容的 parts
                    std_parts = [section, mod_name,
                                 parts[2] if len(parts) > 2 else "0",
                                 parts[4] if len(parts) > 4 else ""]
                    _parse_tabulate_item(std_parts, "INC", formula_items,
                                         f"{mod_display} INC{affects_label}",
                                         f"{mod_name}_INC",
                                         jewel_node_ids)
                else:
                    std_parts = [section, mod_name,
                                 parts[2] if len(parts) > 2 else "1",
                                 parts[4] if len(parts) > 4 else ""]
                    _parse_tabulate_item(std_parts, "MORE", formula_items,
                                         f"{mod_display} MORE{affects_label}",
                                         f"{mod_name}_MORE",
                                         jewel_node_ids)
            else:
                # 标准格式: SECTION|subkey|total_value|entries
                # entries（最后一个字段）可能含 |，用 maxsplit=3 保护
                parts = line.split('|', 3)
                dt = parts[1] if len(parts) > 1 else "?"

                if section == "SPEED_INC":
                    _parse_tabulate_item(parts, "INC", formula_items,
                                         "Speed INC", "Speed_INC",
                                         jewel_node_ids)
                elif section == "SPEED_MORE":
                    _parse_tabulate_item(parts, "MORE", formula_items,
                                         "Speed MORE", "Speed_MORE",
                                         jewel_node_ids)
                elif section == "CRIT_INC":
                    _parse_tabulate_item(parts, "INC", formula_items,
                                         "CritChance INC", "CritChance_INC",
                                         jewel_node_ids)
                elif section == "CRIT_MORE":
                    _parse_tabulate_item(parts, "MORE", formula_items,
                                         "CritChance MORE", "CritChance_MORE",
                                         jewel_node_ids)
                elif section == "CRITMULTI_BASE":
                    _parse_tabulate_item(parts, "BASE", formula_items,
                                         "CritMultiplier BASE", "CritMultiplier_BASE",
                                         jewel_node_ids)
                elif section == "CRITMULTI_INC":
                    _parse_tabulate_item(parts, "INC", formula_items,
                                         "CritMultiplier INC", "CritMultiplier_INC",
                                         jewel_node_ids)
                elif section == "CRITMULTI_MORE":
                    _parse_tabulate_item(parts, "MORE", formula_items,
                                         "CritMultiplier MORE", "CritMultiplier_MORE",
                                         jewel_node_ids)
                elif section == "LUCKY":
                    _parse_tabulate_item(parts, "BASE", formula_items,
                                         f"{dt} Lucky Hits", f"{dt}_Lucky",
                                         jewel_node_ids)

        elif section == "CRIT_BASE":
            # 特殊格式: CRIT_BASE|CritChance|ccB|baseCrit|tabEntries
            parts = line.split('|', 4)
            _parse_crit_base(parts, formula_items, jewel_node_ids)

    # 过滤掉没有来源的非 base-damage 空项
    formula_items = [fi for fi in formula_items
                     if fi.get("_is_base") or fi["sources"]]
    # 清理内部标记
    for fi in formula_items:
        fi.pop("_is_base", None)

    return {
        "total_dps": baseline.get("TotalDPS", 0),
        "average_hit": baseline.get("AverageHit", 0),
        "speed": baseline.get("Speed", 0),
        "combined_dps": baseline.get("CombinedDPS", 0),
        "active_damage_types": active_types,
        "formula_items": formula_items,
    }


def _parse_base_damage(parts: list, formula_items: list,
                       jewel_node_ids: set = None):
    """解析 BASE_DMG 行。

    格式: BASE_DMG|type|totalMin|totalMax|gemMin|gemMax|addedMult|baseMult|addedMinTab|addedMaxTab
    """
    if len(parts) < 9:
        return
    try:
        dt = parts[1]
        total_min = float(parts[2])
        total_max = float(parts[3])
        gem_min = float(parts[4])
        gem_max = float(parts[5])
        added_mult = float(parts[6])
        base_mult = float(parts[7])
    except (ValueError, IndexError):
        return

    sources = []

    # 宝石/武器基础
    if gem_min > 0 or gem_max > 0:
        avg = (gem_min + gem_max) / 2
        sources.append({
            "source": "gem",
            "label": "技能基础",
            "category": "Skill",
            "value": avg,
            "mod_name": "gem_base",
            "detail": f"{gem_min:.0f}-{gem_max:.0f}",
        })

    # added damage (Tabulate 结果)
    # parts[8] = addedMinTab, parts[9] = addedMaxTab
    added_min_tab = parts[8] if len(parts) > 8 else ""
    added_max_tab = parts[9] if len(parts) > 9 else ""
    _merge_added_damage_sources(sources, added_min_tab, added_max_tab, jewel_node_ids)

    # 排序
    sources.sort(key=lambda s: abs(s["value"]), reverse=True)

    # category_summary
    cat_sum = {}
    for s in sources:
        cat = s["category"]
        cat_sum[cat] = cat_sum.get(cat, 0.0) + s["value"]

    total_avg = (total_min + total_max) / 2
    if total_avg < 0.01:
        return  # 浮点精度噪声，跳过
    display = f"{total_min:.0f}-{total_max:.0f}"
    if base_mult != 1:
        display += f" (x{base_mult:.2f} base mult)"

    formula_items.append({
        "key": f"{dt}_Base_Damage",
        "formula_name": f"{dt} Base Damage",
        "total_value": total_avg,
        "display_value": display,
        "category_summary": cat_sum,
        "sources": sources,
        "_is_base": True,
    })


def _merge_added_damage_sources(sources: list, min_tab: str, max_tab: str,
                                jewel_node_ids: set = None):
    """合并 Min/Max Tabulate 结果为单条 source（取均值）。

    同一 source 的多条 mod 会累加（如装备同时给 +10 和 +20 flat damage）。
    """
    # 解析 min tab — 同 source 累加
    min_by_source = {}
    if min_tab:
        for entry in min_tab.split('\2'):
            p = entry.split('\1')
            if len(p) >= 4:
                try:
                    val = float(p[2])
                except ValueError:
                    continue
                if p[1] in min_by_source:
                    min_by_source[p[1]]["value"] += val
                else:
                    min_by_source[p[1]] = {
                        "mod_name": p[0], "value": val, "label": p[3]
                    }

    # 解析 max tab — 同 source 累加
    max_by_source = {}
    if max_tab:
        for entry in max_tab.split('\2'):
            p = entry.split('\1')
            if len(p) >= 4:
                try:
                    val = float(p[2])
                except ValueError:
                    continue
                if p[1] in max_by_source:
                    max_by_source[p[1]]["value"] += val
                else:
                    max_by_source[p[1]] = {
                        "mod_name": p[0], "value": val, "label": p[3]
                    }

    # 合并同 source 的 min/max
    all_sources = set(min_by_source.keys()) | set(max_by_source.keys())
    for src in all_sources:
        mi = min_by_source.get(src, {}).get("value", 0)
        mx = max_by_source.get(src, {}).get("value", 0)
        lbl = min_by_source.get(src, max_by_source.get(src, {})).get("label", "")
        mn = min_by_source.get(src, max_by_source.get(src, {})).get("mod_name", "?")
        avg = (mi + mx) / 2
        if avg == 0:
            continue
        sources.append({
            "source": src,
            "label": lbl or _source_label_fallback(src),
            "category": _classify_source(src, jewel_node_ids),
            "value": avg,
            "mod_name": mn,
            "detail": f"+{mi:.0f}-{mx:.0f}",
        })


def _parse_tabulate_item(parts: list, mod_type: str, formula_items: list,
                         formula_name: str, key: str,
                         jewel_node_ids: set = None):
    """解析标准 Tabulate 行。

    格式: SECTION|subkey|total_value|entries
    entries: modName\1source\1value\1label\2modName\1source\1value\1label
    """
    if len(parts) < 3:
        return
    try:
        total_value = float(parts[2])
    except (ValueError, IndexError):
        return

    sources = []
    if len(parts) >= 4 and parts[3]:
        for entry in parts[3].split('\2'):
            p = entry.split('\1')
            if len(p) >= 3:
                try:
                    val = float(p[2])
                except ValueError:
                    continue
                label = p[3] if len(p) > 3 else _source_label_fallback(p[1])
                sources.append({
                    "source": p[1],
                    "label": label,
                    "category": _classify_source(p[1], jewel_node_ids),
                    "value": val,
                    "mod_name": p[0],
                })

    sources.sort(key=lambda s: abs(s["value"]), reverse=True)

    # category_summary
    cat_sum = {}
    for s in sources:
        cat = s["category"]
        cat_sum[cat] = cat_sum.get(cat, 0.0) + s["value"]

    # display_value
    if mod_type == "INC":
        display = f"{total_value:.0f}%"
    elif mod_type == "MORE":
        display = f"x {total_value:.2f}"
    elif mod_type == "BASE":
        display = f"{total_value:.0f}"
    else:
        display = f"{total_value:.1f}"

    formula_items.append({
        "key": key,
        "formula_name": formula_name,
        "total_value": total_value,
        "display_value": display,
        "category_summary": cat_sum,
        "sources": sources,
    })


def _parse_crit_base(parts: list, formula_items: list,
                     jewel_node_ids: set = None):
    """解析 CritChance BASE 行（含宝石固有 baseCrit）。

    格式: CRIT_BASE|CritChance|ccB|baseCrit|tabEntries
    - ccB: skillModList:Sum("BASE", "CritChance") — 额外加的 flat crit
    - baseCrit: 宝石/武器固有暴击率（不在 modDB 中）
    """
    if len(parts) < 4:
        return
    try:
        added_base = float(parts[2])
        gem_base = float(parts[3])
    except (ValueError, IndexError):
        return

    sources = []

    # 宝石/武器固有基础暴击率
    if gem_base > 0:
        sources.append({
            "source": "gem",
            "label": "技能基础暴击率",
            "category": "Skill",
            "value": gem_base,
            "mod_name": "gem_base_crit",
        })

    # 额外 BASE mod (Tabulate 结果)
    tab_data = parts[4] if len(parts) > 4 else ""
    if tab_data:
        for entry in tab_data.split('\2'):
            p = entry.split('\1')
            if len(p) >= 3:
                try:
                    val = float(p[2])
                except ValueError:
                    continue
                label = p[3] if len(p) > 3 else _source_label_fallback(p[1])
                sources.append({
                    "source": p[1],
                    "label": label,
                    "category": _classify_source(p[1], jewel_node_ids),
                    "value": val,
                    "mod_name": p[0],
                })

    sources.sort(key=lambda s: abs(s["value"]), reverse=True)

    cat_sum = {}
    for s in sources:
        cat = s["category"]
        cat_sum[cat] = cat_sum.get(cat, 0.0) + s["value"]

    total = gem_base + added_base
    formula_items.append({
        "key": "CritChance_BASE",
        "formula_name": "CritChance BASE",
        "total_value": total,
        "display_value": f"{total:.1f}% (base {gem_base:.1f}% + added {added_base:.0f}%)",
        "category_summary": cat_sum,
        "sources": sources,
    })


def _parse_speed_base(parts: list, formula_items: list):
    """解析 Speed BASE 行（基础攻击/施法速度）。

    格式: SPEED_BASE|Speed|baseSpeed|label
    """
    if len(parts) < 4:
        return
    try:
        base_speed = float(parts[2])
    except (ValueError, IndexError):
        return
    if base_speed <= 0:
        return

    label = parts[3] if len(parts) > 3 else "Base"
    sources = [{
        "source": "gem",
        "label": label,
        "category": "Skill",
        "value": base_speed,
        "mod_name": "base_speed",
    }]

    formula_items.append({
        "key": "Speed_BASE",
        "formula_name": "Speed Base",
        "total_value": base_speed,
        "display_value": f"{base_speed:.2f}/s",
        "category_summary": {"Skill": base_speed},
        "sources": sources,
    })


def _empty_breakdown(baseline: dict) -> dict:
    """空结构。"""
    return {
        "total_dps": baseline.get("TotalDPS", 0),
        "average_hit": baseline.get("AverageHit", 0),
        "speed": baseline.get("Speed", 0),
        "combined_dps": baseline.get("CombinedDPS", 0),
        "active_damage_types": [],
        "formula_items": [],
    }


# =============================================================================
# 完整分析流程
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
        }
    """
    from .calculator import calculate as calc_fn, get_main_skill

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

    # 4. 灵敏度分析
    sens = sensitivity_analysis(
        lua, calcs,
        target_pct=target_pct,
        baseline=baseline,
        is_spell=skill_flags["is_spell"],
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

    return {
        "baseline": baseline,
        "main_skill": main_skill,
        "skill_flags": skill_flags,
        "sensitivity": sens,
        "talent_value": talent_value,
        "talent_exploration": talent_exploration,
        "jewel_diagnosis": jewel_diag,
        "dps_breakdown": dps_bd,
    }
