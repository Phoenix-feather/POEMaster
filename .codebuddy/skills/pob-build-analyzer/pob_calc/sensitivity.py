"""灵敏度分析模块。

职责：
- sensitivity_analysis: 等基准灵敏度分析
- SENSITIVITY_PROFILES 定义
- 辅助函数（inject, binary_search, query_merged_inc 等）
"""
import logging
import re
from .calculator import calculate

logger = logging.getLogger(__name__)

# 分析品质上限：所有宝石品质按此上限计算（游戏实际上限 20%）
GEM_QUALITY_CAP = 20

# =============================================================================
# 品质上限工具
# =============================================================================

def _cap_all_gem_qualities(lua):
    """临时将所有宝石品质限制到 GEM_QUALITY_CAP，返回被修改的 gem 列表。

    用于分析场景：确保所有数值基于标准品质上限计算，而非玩家超品质。
    调用 _restore_gem_qualities 恢复原始品质。
    """
    result = lua.execute(r'''
        local sgList = _spike_build.skillsTab.socketGroupList
        local modified = {}
        for _, sg in ipairs(sgList) do
            for _, gem in ipairs(sg.gemList or {}) do
                if gem.quality and gem.quality > ''' + str(GEM_QUALITY_CAP) + r''' then
                    modified[#modified+1] = { orig = gem.quality }
                    gem.quality = ''' + str(GEM_QUALITY_CAP) + r'''
                end
            end
        end
        return #modified
    ''')
    count = int(result) if result else 0
    if count > 0:
        logger.info("品质上限: %d 个宝石品质被限制到 %d%%", count, GEM_QUALITY_CAP)
    return count


def _restore_gem_qualities(lua):
    """恢复被 _cap_all_gem_qualities 修改的宝石品质（重新从 XML 加载）。

    注意：此函数需要 build_loader 的 skillGroups 数据，简化实现为直接
    重新加载技能组（build_loader.load_skill_groups）。
    """
    pass  # 品质修改在单次分析流程中不需要恢复（每次 full_analysis 重新加载）
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
        "label": "暴击率",
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
        "label": "暴击伤害",
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

    # ========== 防御灵敏度 profile (target_stat="TotalEHP") ==========
    # 复用 sensitivity_analysis 框架，以 TotalEHP 为优化目标。
    # 注意: 这些 profile 不带 flags，对任何技能类型都适用。

    # === 生命类 ===
    "life_inc": {
        "mod_name": "Life", "mod_type": "INC",
        "label": "生命上限",
        "description": "生命上限增加（同时提升 TotalEHP 和偷取上限）",
        "search_max": 500, "unit": "%",
    },
    "life_flat": {
        "mod_name": "Life", "mod_type": "BASE",
        "label": "生命固定值",
        "description": "生命上限固定值（装备基础属性）",
        "search_max": 500, "unit": "",
    },

    # === 护甲类 ===
    "armour_inc": {
        "mod_name": "Armour", "mod_type": "INC",
        "label": "护甲增加",
        "description": "护甲增加（降低物理承伤，受递减效应影响）",
        "search_max": 300, "unit": "%",
    },
    "armour_flat": {
        "mod_name": "Armour", "mod_type": "BASE",
        "label": "护甲固定值",
        "description": "护甲固定值（装备基础属性）",
        "search_max": 5000, "unit": "",
    },

    # === 闪避类 ===
    "evasion_inc": {
        "mod_name": "Evasion", "mod_type": "INC",
        "label": "闪避增加",
        "description": "闪避值增加",
        "search_max": 300, "unit": "%",
    },
    "evasion_flat": {
        "mod_name": "Evasion", "mod_type": "BASE",
        "label": "闪避值",
        "description": "闪避值固定值（装备基础属性）",
        "search_max": 5000, "unit": "",
    },

    # === 抗性类 ===
    # 注: 注入 FireResist BASE 会直接叠加到抗性计算中。
    # 如果构筑抗性已满(75%)，注入可能导致溢出，灵敏度趋近于 0。
    "fire_resist": {
        "mod_name": "FireResist", "mod_type": "BASE",
        "label": "火焰抗性",
        "description": "火焰抗性（满抗后无额外收益）",
        "search_max": 75, "unit": "%",
    },
    "cold_resist": {
        "mod_name": "ColdResist", "mod_type": "BASE",
        "label": "冰霜抗性",
        "description": "冰霜抗性（满抗后无额外收益）",
        "search_max": 75, "unit": "%",
    },
    "lightning_resist": {
        "mod_name": "LightningResist", "mod_type": "BASE",
        "label": "闪电抗性",
        "description": "闪电抗性（满抗后无额外收益）",
        "search_max": 75, "unit": "%",
    },
    "chaos_resist": {
        "mod_name": "ChaosResist", "mod_type": "BASE",
        "label": "混沌抗性",
        "description": "混沌抗性（通常是最稀缺的抗性）",
        "search_max": 75, "unit": "%",
    },
    "all_elemental_resist": {
        "mod_name": "ElementalResist", "mod_type": "BASE",
        "label": "全元素抗性",
        "description": "全元素抗性（同时增加火/冰/电抗性）",
        "search_max": 75, "unit": "%",
    },

    # === 格挡类 ===
    "block_chance": {
        "mod_name": "BlockChance", "mod_type": "BASE",
        "label": "格挡概率",
        "description": "攻击格挡概率（受 BlockChanceMax 上限限制）",
        "search_max": 75, "unit": "%",
    },
    "spell_block": {
        "mod_name": "SpellBlockChance", "mod_type": "BASE",
        "label": "法术格挡概率",
        "description": "法术格挡概率（与攻击格挡独立）",
        "search_max": 75, "unit": "%",
    },

    # === 减伤类 ===
    "damage_reduction": {
        "mod_name": "DamageReduction", "mod_type": "BASE",
        "label": "物理减伤",
        "description": "额外物理伤害减免（与护甲减伤叠加，受 DamageReductionMax 限制）",
        "search_max": 90, "unit": "%",
    },

    # === 恢复类 ===
    # 以 LifeRegenRecovery / LifeLeech / MaxLifeLeechRate 等为 target_stat
    "life_regen": {
        "mod_name": "LifeRegen", "mod_type": "BASE",
        "label": "生命再生",
        "description": "每秒生命再生（天赋/装备固定值，不受战斗影响）",
        "search_max": 100, "unit": "/s",
        "target_stat": "LifeRegenRecovery",
    },
    "life_leech": {
        "mod_name": "PhysicalDamageLifeLeech", "mod_type": "BASE",
        "label": "物理生命偷取",
        "description": "物理伤害生命偷取比例（受 MaxLifeLeechRate 上限约束）",
        "search_max": 20, "unit": "%",
        "target_stat": "LifeLeech",
    },
    "life_recoup": {
        "mod_name": "LifeRecoup", "mod_type": "BASE",
        "label": "伤害回收",
        "description": "伤害回收为生命（消耗能量后延迟恢复，4秒内回完）",
        "search_max": 20, "unit": "%",
        "target_stat": "LifeRecoup",
    },
    "life_recovery_rate": {
        "mod_name": "LifeRecoveryRate", "mod_type": "INC",
        "label": "生命恢复速率",
        "description": "生命恢复速率增加（影响再生/偷取/回收/击中恢复）",
        "search_max": 100, "unit": "%",
        "target_stat": "LifeRegenRecovery",
    },
    "flask_effect": {
        "mod_name": "FlaskEffect", "mod_type": "INC",
        "label": "药剂效果",
        "description": "药剂效果增加（提升生命/魔力药剂恢复量）",
        "search_max": 100, "unit": "%",
        "target_stat": "LifeRegenRecovery",
    },
    "mana_regen": {
        "mod_name": "ManaRegen", "mod_type": "BASE",
        "label": "魔力再生",
        "description": "每秒魔力再生",
        "search_max": 100, "unit": "/s",
        "target_stat": "ManaRegenRecovery",
    },
    "mana_leech": {
        "mod_name": "PhysicalDamageManaLeech", "mod_type": "BASE",
        "label": "物理魔力偷取",
        "description": "物理伤害魔力偷取比例（受 MaxManaLeechRate 上限约束）",
        "search_max": 20, "unit": "%",
        "target_stat": "ManaLeech",
    },
    "mana_recovery_rate": {
        "mod_name": "ManaRecoveryRate", "mod_type": "INC",
        "label": "魔力恢复速率",
        "description": "魔力恢复速率增加（影响再生/偷取/回收）",
        "search_max": 100, "unit": "%",
        "target_stat": "ManaRegenRecovery",
    },
}

# 目标 stat 中文显示名（公式中使用）
_STAT_DISPLAY = {
    "TotalDPS": "DPS",
    "TotalEHP": "EHP",
    "LifeRegenRecovery": "生命恢复",
    "LifeLeech": "生命偷取",
    "LifeRecoup": "伤害回收",
    "ManaRegenRecovery": "魔力恢复",
    "ManaLeech": "魔力偷取",
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

# 来源固定 profile 集合（升华/光环/辅助宝石提供，无法通过装备/天赋灵活优化）
# 这些维度在灵敏度分析中默认排除，因为不具备可操作的优化空间
_FIXED_SOURCE_PROFILES = {
    "damage_more",     # more Damage — 主要来自升华、光环、辅助宝石
    "speed_more",      # more Speed — 同上
}

# 防御灵敏度 profile 集合（以 TotalEHP 为优化目标）
_DEFENCE_PROFILES = {
    "life_inc", "life_flat",
    "armour_inc", "armour_flat",
    "evasion_inc", "evasion_flat",
    "fire_resist", "cold_resist", "lightning_resist", "chaos_resist",
    "all_elemental_resist",
    "block_chance", "spell_block",
    "damage_reduction",
}

# 恢复灵敏度 profile 集合（各恢复来源独立 target_stat）
# 不使用统一的 target_stat（如 LifeRegenRecovery），而是每个 profile 独立评估
_RECOVERY_PROFILES = {
    "life_regen", "life_leech", "life_recoup", "life_recovery_rate",
    "flask_effect", "mana_regen", "mana_leech", "mana_recovery_rate",
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

        # 排除来源固定的维度（升华/光环/辅助宝石，无法通过装备/天赋灵活优化）
        excluded |= _FIXED_SOURCE_PROFILES
        logger.info("排除 %d 个来源固定 profile (升华/光环): %s",
                     len(_FIXED_SOURCE_PROFILES), ", ".join(_FIXED_SOURCE_PROFILES))

        profiles = [p for p in profiles if p not in excluded]

    base_dps = baseline.get(target_stat, 0)
    if base_dps == 0:
        logger.warning("基线 %s = 0，无法进行灵敏度分析", target_stat)
        return []

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

        # per-profile target_stat 覆盖（恢复类 profile 各有独立目标）
        profile_target = profile.get("target_stat", target_stat)
        profile_base = baseline.get(profile_target, 0)
        profile_target_dps = profile_base * (1 + target_pct / 100)

        # 如果该 profile 的基线为 0，跳过
        if profile_base == 0:
            logger.debug("profile '%s' 基线 %s = 0，跳过", key, profile_target)
            results.append({
                "key": key, "label": label, "description": description,
                "mod_name": mod_name, "mod_type": mod_type,
                "needed_value": None, "unit": unit,
                "dps_per_unit": None, "target_pct": target_pct,
                "actual_pct": 0, "current_total": 0,
                "formula": f"基线 {profile_target}=0，无法分析",
                "sample_diff": {},
            })
            continue

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

        # 二分搜索：找到达到 profile_target_dps 所需的最小注入值
        needed_value = _binary_search_needed_value(
            lua, calcs, key, profile, baseline,
            profile_target, profile_target_dps, search_max
        )

        # 计算实际注入 needed_value 后的 diff（用于 formula 和验证）
        sample_diff = {}
        actual_pct = 0.0
        if needed_value is not None:
            sample_diff = _inject_profile(lua, calcs, key, profile,
                                          needed_value, baseline)
            after_entry = sample_diff.get(profile_target)
            if after_entry:
                actual_pct = (after_entry[2] / profile_base * 100) if profile_base != 0 else 0

        # 生成公式（target_label 从 _STAT_DISPLAY 获取中文显示名）
        tl = _STAT_DISPLAY.get(profile_target, profile_target)
        formula = _make_formula(mod_name, mod_type, needed_value,
                                current_total, target_pct, actual_pct,
                                target_label=tl)

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
            "target_label": tl,
            "flags": profile.get("flags"),
        })

    # 按所需值升序排列（值越小 = 性价比越高），None 排最后
    results.sort(key=lambda x: (x["needed_value"] is None, x["needed_value"] or 999999))



    # 同 mod_name + mod_type + needed_value 的 profile 去重
    # 规则：同一 pool 中，无 flags 的被有 flags 的替代（通用被精确替代）
    #       有 flags 的互相之间都保留（不同词缀来源，如 spell vs projectile）
    #       不同 mod_name 不去重（Damage vs ElementalDamage vs LightningDamage）
    _grouped = {}  # dk -> [profiles]
    for s in results:
        dk = (s.get("mod_name"), s.get("mod_type"), s.get("needed_value"))
        _grouped.setdefault(dk, []).append(s)
    _deduped = []
    for dk, group in _grouped.items():
        flagged = [s for s in group if s.get("flags")]
        if flagged:
            _deduped.extend(flagged)  # 保留所有有 flags 的
        else:
            _deduped.append(group[0])  # 无 flags 的只保留一个
    results = _deduped
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

