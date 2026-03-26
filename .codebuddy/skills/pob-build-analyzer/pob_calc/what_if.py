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

# 来源固定 profile 集合（升华/光环/辅助宝石提供，无法通过装备/天赋灵活优化）
# 这些维度在灵敏度分析中默认排除，因为不具备可操作的优化空间
_FIXED_SOURCE_PROFILES = {
    "damage_more",     # more Damage — 主要来自升华、光环、辅助宝石
    "speed_more",      # more Speed — 同上
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
            "dps_pct": 移除此珠宝后 DPS 下降百分比（正值=正向贡献）,
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
            # dps_pct 表示珠宝的 DPS 贡献（正值=增加 DPS，负值=降低 DPS）
            # 计算方式：移除珠宝后 DPS 下降 → 贡献为正
            jewel["dps_pct"] = round(-dps_delta / base_dps * 100, 2) if base_dps != 0 else 0.0
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
                # dps_pct 表示贡献（正值=增加 DPS）
                gp_dps_pct = round(-gp_dps_delta / base_dps * 100, 2) if base_dps != 0 else 0.0

                jewel["granted_dps_pct"] = gp_dps_pct
                # 取物品移除和节点移除中影响更大的作为总 DPS 贡献
                if abs(gp_dps_pct) > abs(jewel["dps_pct"]):
                    jewel["dps_pct"] = gp_dps_pct
                    jewel["dps_source"] = "granted_passives"
                else:
                    jewel["dps_source"] = "item_mods"
            except Exception as e:
                logger.warning("GrantedPassive DPS 诊断失败 %s: %s", slot_name, e)

    # 逐 mod DPS 测试：对每颗有效珠宝的每个 mod 逐个禁用后计算 DPS
    for jewel in jewels:
        if jewel["status"] != "ok" or base_dps == 0:
            continue
        if not jewel.get("mods"):
            continue

        node_id = jewel["node_id"]
        slot_name = jewel["slot_name"]
        mods = jewel["mods"]

        # 分离 GrantedPassive 和普通 mod
        granted_names = []
        granted_indices = []
        normal_indices = []
        for i, m in enumerate(mods):
            if m.get("name") == "GrantedPassive" and m.get("type") == "LIST":
                granted_names.append(m.get("value", ""))
                granted_indices.append(i)
            else:
                normal_indices.append(i)

        # 普通 mod：在 Lua 端对 item.modList 逐个禁用测试
        if normal_indices:
            # 构建 Lua 端需要测试的索引列表（1-based）
            lua_indices = ",".join(str(i + 1) for i in normal_indices)
            try:
                per_mod_result = lua.execute(f'''
                    local build = _spike_build
                    local slot = build.itemsTab.slots['{slot_name}']
                    if not slot then return "" end
                    local item = build.itemsTab.items[slot.selItemId]
                    if not item or not item.modList then return "" end

                    local results = {{}}
                    local ml = item.modList
                    local testIndices = {{{lua_indices}}}

                    for _, idx in ipairs(testIndices) do
                        local m = ml[idx]
                        if not m then
                            results[#results+1] = "ERR"
                        else
                            local origVal = m.value
                            local origType = m.type
                            local canZero = (origType == "BASE" or origType == "INC"
                                             or origType == "MORE")
                                            and type(origVal) == "number"
                            if canZero then
                                m.value = 0
                                local ok, dps = pcall(function()
                                    local env = calcs.initEnv(build, "MAIN")
                                    calcs.perform(env)
                                    return env.player.output.TotalDPS or 0
                                end)
                                m.value = origVal
                                results[#results+1] = ok and tostring(dps) or "ERR"
                            else
                                table.remove(ml, idx)
                                local ok, dps = pcall(function()
                                    local env = calcs.initEnv(build, "MAIN")
                                    calcs.perform(env)
                                    return env.player.output.TotalDPS or 0
                                end)
                                table.insert(ml, idx, m)
                                results[#results+1] = ok and tostring(dps) or "ERR"
                            end
                        end
                    end
                    return table.concat(results, ",")
                ''')

                if per_mod_result:
                    dps_values = str(per_mod_result).split(",")
                    for j, dps_str in enumerate(dps_values):
                        if j < len(normal_indices) and dps_str != "ERR":
                            try:
                                after = float(dps_str)
                                # dps_pct 表示贡献（正值=增加 DPS）
                                delta_pct = round(-(after - base_dps) / base_dps * 100, 2)
                                mods[normal_indices[j]]["dps_pct"] = delta_pct
                            except (ValueError, ZeroDivisionError):
                                mods[normal_indices[j]]["dps_pct"] = None
                        elif j < len(normal_indices):
                            mods[normal_indices[j]]["dps_pct"] = None
            except Exception as e:
                logger.warning("珠宝普通 mod DPS 诊断失败 %s: %s", slot_name, e)

        # GrantedPassive mod：用 override.removeNodes 逐个天赋节点移除
        for gi, gname in zip(granted_indices, granted_names):
            if not gname:
                mods[gi]["dps_pct"] = None
                continue
            try:
                # 用单行 Lua 避免多行字符串嵌套问题
                lua_code = (
                    'local build = _spike_build; '
                    'local tree = build.spec.tree; '
                    f'local node = tree.notableMap["{gname}"]; '
                    'if not node then return "NOT_FOUND" end; '
                    'local removeNodes = {}; '
                    'removeNodes[node] = true; '
                    'removeNodes[node.id] = true; '
                    'local override = { removeNodes = removeNodes }; '
                    'local env = calcs.initEnv(build, "CALCULATOR", override); '
                    'calcs.perform(env); '
                    'return tostring(env.player.output.TotalDPS or 0)'
                )
                r = lua.execute(lua_code)
                if r and str(r) != "NOT_FOUND":
                    after = float(str(r))
                    # dps_pct 表示贡献（正值=增加 DPS）
                    delta_pct = round(-(after - base_dps) / base_dps * 100, 2)
                    mods[gi]["dps_pct"] = delta_pct
                else:
                    mods[gi]["dps_pct"] = None
            except Exception as e:
                logger.warning("GrantedPassive 逐条 DPS 诊断失败 %s[%s]: %s",
                               slot_name, gname, e)
                mods[gi]["dps_pct"] = None

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

        -- === 8. Conversion & Gain 表 ===
        -- 只输出对当前构筑有实际 DPS 贡献的条目
        -- 判断依据：fromType 有基础伤害（output[fromType.."MinBase"] > 0）
        -- 注意：Self-Gain（如 Cold→Cold 15%）是 POB 支持的机制
        --       calcGainedDamage() 遍历所有 otherType（包括 self），
        --       DamageGainAsCold 等通用 mod 会产生 gainTable[Cold][Cold] > 0
        local isElemental = {Lightning=true, Cold=true, Fire=true}
        if ms.conversionTable and ms.gainTable then
            -- 收集每种 fromType 是否有基础伤害
            local hasBase = {}
            for _, dt in ipairs(dmgTypes) do
                local minB = output[dt.."MinBase"] or 0
                local maxB = output[dt.."MaxBase"] or 0
                hasBase[dt] = (minB > 0 or maxB > 0)
            end
            for _, fromType in ipairs(dmgTypes) do
                if hasBase[fromType] then
                    for _, toType in ipairs(dmgTypes) do
                        -- Conversion: 跳过 self（同类型转换无意义）
                        -- Gain: 允许 self（Cold→Cold self-gain 是真实机制）
                        local convPct = 0
                        local gainPct = 0
                        if fromType ~= toType and ms.conversionTable[fromType] then
                            convPct = (ms.conversionTable[fromType][toType] or 0) * 100
                        end
                        if ms.gainTable[fromType] then
                            gainPct = (ms.gainTable[fromType][toType] or 0) * 100
                        end
                        if convPct > 0.01 or gainPct > 0.01 then
                            -- Gain mod 来源 Tabulate
                            local gainTab = ""
                            if gainPct > 0.01 then
                                -- 通用 Gain mods（对所有 fromType→toType 都生效，包括 self-gain）
                                local gainMods = {
                                    "DamageAs"..toType,
                                    "DamageGainAs"..toType,
                                }
                                -- 特定类型 Gain mods（仅 fromType != toType 时有意义）
                                if fromType ~= toType then
                                    gainMods[#gainMods+1] = fromType.."DamageAs"..toType
                                    gainMods[#gainMods+1] = fromType.."DamageGainAs"..toType
                                end
                                if isElemental[fromType] then
                                    gainMods[#gainMods+1] = "ElementalDamageAs"..toType
                                    gainMods[#gainMods+1] = "ElementalDamageGainAs"..toType
                                end
                                if fromType ~= "Chaos" then
                                    gainMods[#gainMods+1] = "NonChaosDamageAs"..toType
                                    gainMods[#gainMods+1] = "NonChaosDamageGainAs"..toType
                                end
                                gainTab = tabStr("BASE", table.unpack(gainMods))
                            end
                            local labelSuffix = (fromType == toType) and " (Self-Gain)" or ""
                            lines[#lines+1] = "CONV_GAIN|" .. fromType .. "|" .. toType .. "|"
                                .. string.format("%.2f", convPct) .. "|"
                                .. string.format("%.2f", gainPct) .. "|"
                                .. gainTab
                        end
                    end
                    -- convMult（未转换比例）
                    if ms.conversionTable[fromType] then
                        local convMult = ms.conversionTable[fromType].mult or 1
                        if convMult < 0.999 then
                            lines[#lines+1] = "CONV_MULT|" .. fromType .. "|" .. string.format("%.4f", convMult)
                        end
                    end
                end
            end
        end

        -- === 9. effMult（穿透 / 抗性 / 受伤增加） ===
        -- 从 MAIN 模式 env 直接读取数据（避免 CALCS 模式的 Lua 5.4 兼容问题）
        -- env.mode_effective = true（MAIN 模式默认），所以抗性/穿透计算已生效
        local enemyDB = env.enemyDB

        if enemyDB and env.mode_effective then
            for _, dt in ipairs(activeDT) do
                local takenInc = enemyDB:Sum("INC", cfg, "DamageTaken", dt.."DamageTaken")
                local takenMore = enemyDB:More(cfg, "DamageTaken", dt.."DamageTaken")
                local resist = 0
                local pen = 0
                -- 元素追加 ElementalDamageTaken
                if isElemental[dt] then
                    takenInc = takenInc + enemyDB:Sum("INC", cfg, "ElementalDamageTaken")
                    pen = skillModList:Sum("BASE", cfg, dt.."Penetration", "ElementalPenetration")
                elseif dt == "Chaos" then
                    pen = skillModList:Sum("BASE", cfg, "ChaosPenetration")
                end
                -- 获取敌人抗性
                if dt == "Physical" then
                    resist = enemyDB:Sum("BASE", nil, "PhysicalDamageReduction")
                else
                    resist = enemyDB:Sum("BASE", nil, dt.."Resist")
                end
                -- 计算 effMult（与 CalcOffence.lua:3816-3821 一致）
                local effectiveResist = resist > 0 and math.max(resist - pen, 0) or resist
                local effMult = (1 + takenInc / 100) * takenMore * (1 - effectiveResist / 100)
                if effMult ~= 0 and (math.abs(effMult - 1) > 0.001 or pen > 0) then
                    -- 格式: EFF_MULT|dt|effMult|resist|pen|takenInc|takenMore
                    lines[#lines+1] = "EFF_MULT|" .. dt .. "|"
                        .. string.format("%.6f", effMult) .. "|"
                        .. string.format("%.1f", resist) .. "|"
                        .. string.format("%.1f", pen) .. "|"
                        .. string.format("%.1f", takenInc) .. "|"
                        .. string.format("%.6f", takenMore)
                end
            end
        end

        -- === 10. Double/Triple Damage ===
        local doubleDmgChance = output.DoubleDamageChance or 0
        local tripleDmgChance = output.TripleDamageChance or 0
        local scaledDmgEffect = output.ScaledDamageEffect or 1
        if scaledDmgEffect ~= 1 or doubleDmgChance > 0 or tripleDmgChance > 0 then
            lines[#lines+1] = "DOUBLE_TRIPLE|"
                .. string.format("%.1f", doubleDmgChance) .. "|"
                .. string.format("%.1f", tripleDmgChance) .. "|"
                .. string.format("%.6f", scaledDmgEffect)
        end

        -- === 11. HitChance ===
        local hitChance = output.HitChance or 100
        if hitChance < 100 then
            local accHitChance = output.AccuracyHitChance or 100
            local enemyBlock = output.enemyBlockChance or 0
            lines[#lines+1] = "HITCHANCE|"
                .. string.format("%.2f", hitChance) .. "|"
                .. string.format("%.2f", accHitChance) .. "|"
                .. string.format("%.2f", enemyBlock)
        end

        -- === 12. DPS Multiplier ===
        local dpsMultiplier = ms.skillData and ms.skillData.dpsMultiplier or 1
        if dpsMultiplier ~= 1 then
            lines[#lines+1] = "DPS_MULT|" .. string.format("%.4f", dpsMultiplier)
        end

        -- === 13. CombinedDPS 构成 ===
        do
            local globalOutput = env.player.output
            local totalDPS = globalOutput.TotalDPS or 0
            local totalDotDPS = globalOutput.TotalDotDPS or 0
            local impaleDPS = globalOutput.ImpaleDPS or 0
            local mirageDPS = globalOutput.MirageDPS or 0
            local cullMult = globalOutput.CullMultiplier or 1
            local resDpsMult = globalOutput.ReservationDpsMultiplier or 1
            local combinedDPS = globalOutput.CombinedDPS or 0
            local bleedDPS = globalOutput.BleedDPS or globalOutput.TotalBleedDPS or 0
            local poisonDPS = globalOutput.PoisonDPS or globalOutput.TotalPoisonDPS or 0
            local igniteDPS = globalOutput.IgniteDPS or globalOutput.TotalIgniteDPS or 0
            if combinedDPS > totalDPS or totalDotDPS > 0 or impaleDPS > 0 or cullMult > 1 then
                lines[#lines+1] = "COMBINED_DPS|"
                    .. string.format("%.1f", totalDPS) .. "|"
                    .. string.format("%.1f", totalDotDPS) .. "|"
                    .. string.format("%.1f", impaleDPS) .. "|"
                    .. string.format("%.1f", mirageDPS) .. "|"
                    .. string.format("%.6f", cullMult) .. "|"
                    .. string.format("%.6f", resDpsMult) .. "|"
                    .. string.format("%.1f", combinedDPS) .. "|"
                    .. string.format("%.1f", bleedDPS) .. "|"
                    .. string.format("%.1f", poisonDPS) .. "|"
                    .. string.format("%.1f", igniteDPS)
            end
        end

        return table.concat(lines, "\n")
    '''

    result = lua.execute(lua_script)

    active_types = []
    jewel_node_ids = set()  # 珠宝槽位节点 ID 集合
    formula_items = []
    _conv_mult_data = {}  # fromType → convMult（未转换比例）

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

        elif section == "CONV_GAIN":
            # 格式: CONV_GAIN|fromType|toType|convPct|gainPct|gainTab
            parts = line.split('|', 5)
            _parse_conv_gain(parts, formula_items, jewel_node_ids)

        elif section == "CONV_MULT":
            # 格式: CONV_MULT|fromType|convMult
            # 存储为元信息，不作为 formula_item
            parts = line.split('|')
            if len(parts) >= 3:
                _conv_mult_data[parts[1]] = float(parts[2])

        elif section == "EFF_MULT":
            # 格式: EFF_MULT|dt|effMult|resist|pen|takenInc|takenMore
            parts = line.split('|')
            _parse_eff_mult(parts, formula_items)

        elif section == "DOUBLE_TRIPLE":
            # 格式: DOUBLE_TRIPLE|doublePct|triplePct|scaledEffect
            parts = line.split('|')
            _parse_double_triple(parts, formula_items)

        elif section == "HITCHANCE":
            # 格式: HITCHANCE|hitChance|accHitChance|enemyBlock
            parts = line.split('|')
            _parse_hitchance(parts, formula_items)

        elif section == "DPS_MULT":
            # 格式: DPS_MULT|multiplier
            parts = line.split('|')
            _parse_dps_mult(parts, formula_items)

        elif section == "COMBINED_DPS":
            # 格式: COMBINED_DPS|totalDPS|dotDPS|impaleDPS|mirageDPS|cullMult|resDpsMult|combinedDPS|bleedDPS|poisonDPS|igniteDPS
            parts = line.split('|')
            _parse_combined_dps(parts, formula_items)

    # 过滤掉没有来源的非 base-damage 空项
    formula_items = [fi for fi in formula_items
                     if fi.get("_is_base") or fi.get("_no_sources_ok") or fi["sources"]]
    # 清理内部标记
    for fi in formula_items:
        fi.pop("_is_base", None)
        fi.pop("_no_sources_ok", None)

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


def _parse_conv_gain(parts: list, formula_items: list,
                     jewel_node_ids: set = None):
    """解析 CONV_GAIN 行（伤害转换与增益）。

    格式: CONV_GAIN|fromType|toType|convPct|gainPct|gainTab
    """
    if len(parts) < 5:
        return
    try:
        from_type = parts[1]
        to_type = parts[2]
        conv_pct = float(parts[3])
        gain_pct = float(parts[4])
    except (ValueError, IndexError):
        return

    sources = []

    if conv_pct > 0.01:
        sources.append({
            "source": "conversion",
            "label": f"{from_type} → {to_type} 转换",
            "category": "Conversion",
            "value": conv_pct,
            "mod_name": f"{from_type}DamageConvertTo{to_type}",
        })

    if gain_pct > 0.01:
        # 解析 gain mod 来源
        gain_tab = parts[5] if len(parts) > 5 else ""
        if gain_tab:
            for entry in gain_tab.split('\2'):
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
                        "detail": f"Gain as {to_type}",
                    })
        else:
            # 没有详细来源，用总值
            sources.append({
                "source": "gain",
                "label": f"{from_type} → {to_type} 额外获得",
                "category": "Gain",
                "value": gain_pct,
                "mod_name": f"{from_type}DamageGainAs{to_type}",
            })

    if not sources:
        return

    sources.sort(key=lambda s: abs(s["value"]), reverse=True)
    cat_sum = {}
    for s in sources:
        cat = s["category"]
        cat_sum[cat] = cat_sum.get(cat, 0.0) + s["value"]

    total = conv_pct + gain_pct
    display_parts = []
    if conv_pct > 0.01:
        display_parts.append(f"转换 {conv_pct:.1f}%")
    if gain_pct > 0.01:
        display_parts.append(f"增益 {gain_pct:.1f}%")
    if from_type == to_type:
        display = f"{from_type} Self-Gain: {' + '.join(display_parts)}"
    else:
        display = f"{from_type} → {to_type}: {' + '.join(display_parts)}"

    key_suffix = "SelfGain" if from_type == to_type else "ConvGain"
    formula_items.append({
        "key": f"{from_type}_to_{to_type}_{key_suffix}",
        "formula_name": f"{from_type} → {to_type} {'Self-Gain' if from_type == to_type else 'Conversion/Gain'}",
        "total_value": total,
        "display_value": display,
        "category_summary": cat_sum,
        "sources": sources,
        "_no_sources_ok": True,
    })


def _parse_eff_mult(parts: list, formula_items: list):
    """解析 EFF_MULT 行（有效 DPS 乘数：穿透/抗性/受伤增加）。

    格式: EFF_MULT|dt|effMult|resist|pen|takenInc|takenMore
    """
    if len(parts) < 7:
        return
    try:
        dt = parts[1]
        eff_mult = float(parts[2])
        resist = float(parts[3])
        pen = float(parts[4])
        taken_inc = float(parts[5])
        taken_more = float(parts[6])
    except (ValueError, IndexError):
        return

    sources = []

    if resist != 0:
        sources.append({
            "source": "enemy",
            "label": f"敌人 {dt} 抗性",
            "category": "Enemy",
            "value": resist,
            "mod_name": f"{dt}Resist",
        })

    if pen != 0:
        sources.append({
            "source": "player",
            "label": f"{dt} 穿透",
            "category": "Penetration",
            "value": pen,
            "mod_name": f"{dt}Penetration",
        })

    if taken_inc != 0:
        sources.append({
            "source": "enemy",
            "label": f"敌人受到 {dt} 伤害增加",
            "category": "Enemy",
            "value": taken_inc,
            "mod_name": f"{dt}DamageTaken_INC",
        })

    if taken_more != 1:
        sources.append({
            "source": "enemy",
            "label": f"敌人受到 {dt} 伤害 MORE",
            "category": "Enemy",
            "value": (taken_more - 1) * 100,
            "mod_name": f"{dt}DamageTaken_MORE",
        })

    # 公式: effMult = (1 + takenInc/100) × takenMore × (1 - max(resist-pen, 0)/100)
    formula_detail = f"(1+{taken_inc:.0f}/100) × {taken_more:.4f}"
    if resist != 0 or pen != 0:
        effective_resist = max(resist - pen, 0)
        formula_detail += f" × (1-{effective_resist:.0f}/100)"

    formula_items.append({
        "key": f"{dt}_EffMult",
        "formula_name": f"{dt} Effective DPS Multiplier",
        "total_value": eff_mult,
        "display_value": f"x{eff_mult:.4f}",
        "category_summary": {s["category"]: s["value"] for s in sources},
        "sources": sources,
        "_no_sources_ok": True,
        "formula_detail": formula_detail,
    })


def _parse_double_triple(parts: list, formula_items: list):
    """解析 DOUBLE_TRIPLE 行。

    格式: DOUBLE_TRIPLE|doublePct|triplePct|scaledEffect
    """
    if len(parts) < 4:
        return
    try:
        double_pct = float(parts[1])
        triple_pct = float(parts[2])
        scaled_effect = float(parts[3])
    except (ValueError, IndexError):
        return

    if scaled_effect == 1 and double_pct == 0 and triple_pct == 0:
        return

    sources = []
    if double_pct > 0:
        sources.append({
            "source": "player",
            "label": f"双倍伤害 {double_pct:.1f}%",
            "category": "DoubleDamage",
            "value": double_pct,
            "mod_name": "DoubleDamageChance",
        })
    if triple_pct > 0:
        sources.append({
            "source": "player",
            "label": f"三倍伤害 {triple_pct:.1f}%",
            "category": "TripleDamage",
            "value": triple_pct,
            "mod_name": "TripleDamageChance",
        })

    formula_items.append({
        "key": "ScaledDamageEffect",
        "formula_name": "Scaled Damage Effect (Double/Triple)",
        "total_value": scaled_effect,
        "display_value": f"x{scaled_effect:.4f}",
        "category_summary": {s["category"]: s["value"] for s in sources},
        "sources": sources,
        "_no_sources_ok": True,
    })


def _parse_hitchance(parts: list, formula_items: list):
    """解析 HITCHANCE 行。

    格式: HITCHANCE|hitChance|accHitChance|enemyBlock
    """
    if len(parts) < 4:
        return
    try:
        hit_chance = float(parts[1])
        acc_hit_chance = float(parts[2])
        enemy_block = float(parts[3])
    except (ValueError, IndexError):
        return

    sources = []
    if acc_hit_chance < 100:
        sources.append({
            "source": "player",
            "label": "命中率（准确度）",
            "category": "Accuracy",
            "value": acc_hit_chance,
            "mod_name": "AccuracyHitChance",
        })
    if enemy_block > 0:
        sources.append({
            "source": "enemy",
            "label": "敌人格挡率",
            "category": "Enemy",
            "value": -enemy_block,
            "mod_name": "enemyBlockChance",
        })

    formula_items.append({
        "key": "HitChance",
        "formula_name": "Hit Chance",
        "total_value": hit_chance,
        "display_value": f"{hit_chance:.1f}%",
        "category_summary": {s["category"]: s["value"] for s in sources},
        "sources": sources,
        "_no_sources_ok": True,
    })


def _parse_dps_mult(parts: list, formula_items: list):
    """解析 DPS_MULT 行。

    格式: DPS_MULT|multiplier
    """
    if len(parts) < 2:
        return
    try:
        mult = float(parts[1])
    except (ValueError, IndexError):
        return

    if mult == 1:
        return

    sources = [{
        "source": "skill",
        "label": "技能 DPS 乘数",
        "category": "Skill",
        "value": mult,
        "mod_name": "dpsMultiplier",
    }]

    formula_items.append({
        "key": "DPS_Multiplier",
        "formula_name": "DPS Multiplier",
        "total_value": mult,
        "display_value": f"x{mult:.2f}",
        "category_summary": {"Skill": mult},
        "sources": sources,
        "_no_sources_ok": True,
    })


def _parse_combined_dps(parts: list, formula_items: list):
    """解析 COMBINED_DPS 行（组合 DPS 构成）。

    格式: COMBINED_DPS|totalDPS|dotDPS|impaleDPS|mirageDPS|cullMult|resDpsMult|combinedDPS|bleedDPS|poisonDPS|igniteDPS
    """
    if len(parts) < 8:
        return
    try:
        total_dps = float(parts[1])
        dot_dps = float(parts[2])
        impale_dps = float(parts[3])
        mirage_dps = float(parts[4])
        cull_mult = float(parts[5])
        res_dps_mult = float(parts[6])
        combined_dps = float(parts[7])
        bleed_dps = float(parts[8]) if len(parts) > 8 else 0
        poison_dps = float(parts[9]) if len(parts) > 9 else 0
        ignite_dps = float(parts[10]) if len(parts) > 10 else 0
    except (ValueError, IndexError):
        return

    sources = []
    if total_dps > 0:
        sources.append({
            "source": "hit",
            "label": "Hit DPS",
            "category": "Hit",
            "value": total_dps,
            "mod_name": "TotalDPS",
        })
    if bleed_dps > 0:
        sources.append({
            "source": "ailment",
            "label": "流血 DPS",
            "category": "DOT",
            "value": bleed_dps,
            "mod_name": "BleedDPS",
        })
    if poison_dps > 0:
        sources.append({
            "source": "ailment",
            "label": "中毒 DPS",
            "category": "DOT",
            "value": poison_dps,
            "mod_name": "PoisonDPS",
        })
    if ignite_dps > 0:
        sources.append({
            "source": "ailment",
            "label": "点燃 DPS",
            "category": "DOT",
            "value": ignite_dps,
            "mod_name": "IgniteDPS",
        })
    if dot_dps > 0 and (dot_dps - bleed_dps - poison_dps - ignite_dps) > 0.5:
        other_dot = dot_dps - bleed_dps - poison_dps - ignite_dps
        sources.append({
            "source": "dot",
            "label": "其他 DOT DPS",
            "category": "DOT",
            "value": other_dot,
            "mod_name": "OtherDotDPS",
        })
    if impale_dps > 0:
        sources.append({
            "source": "impale",
            "label": "穿刺 DPS",
            "category": "Impale",
            "value": impale_dps,
            "mod_name": "ImpaleDPS",
        })
    if mirage_dps > 0:
        sources.append({
            "source": "mirage",
            "label": "幻影 DPS",
            "category": "Mirage",
            "value": mirage_dps,
            "mod_name": "MirageDPS",
        })
    if cull_mult > 1:
        # Cull 额外 DPS
        base_before_cull = combined_dps / cull_mult / res_dps_mult if cull_mult > 1 else combined_dps
        cull_dps = base_before_cull * (cull_mult - 1)
        sources.append({
            "source": "cull",
            "label": f"处决 (x{cull_mult:.4f})",
            "category": "Cull",
            "value": cull_dps,
            "mod_name": "CullMultiplier",
        })
    if res_dps_mult > 1:
        base_before_res = combined_dps / res_dps_mult
        res_dps = base_before_res * (res_dps_mult - 1)
        sources.append({
            "source": "reservation",
            "label": f"保留 DPS 乘数 (x{res_dps_mult:.4f})",
            "category": "Reservation",
            "value": res_dps,
            "mod_name": "ReservationDpsMultiplier",
        })

    sources.sort(key=lambda s: abs(s["value"]), reverse=True)
    cat_sum = {}
    for s in sources:
        cat = s["category"]
        cat_sum[cat] = cat_sum.get(cat, 0.0) + s["value"]

    formula_items.append({
        "key": "CombinedDPS",
        "formula_name": "Combined DPS",
        "total_value": combined_dps,
        "display_value": f"{combined_dps:,.0f}",
        "category_summary": cat_sum,
        "sources": sources,
        "_no_sources_ok": True,
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
# Section 7: 光环与精魄分析 (Aura & Spirit Analysis)
# =============================================================================
#
# 设计文档（explore 模式确认）：
#   7A — 现有光环/精魄移除测试
#   7B — 潜在光环推荐（6 个非 Herald 候选）
#   7C — 精魄辅助推荐（DPS 相关 + 估算）
#   7D — Spirit Budget 汇总
#
# 机制确认：
#   - Blasphemy 已排除（太复杂）
#   - Herald 已排除（攻击构筑特有，用户自带）
#   - Direstrike Low Life 条件：按满足条件计算，标注
#   - Refraction III：纳入但标记为估算
#   - Precision：POB 完整支持 Accuracy → HitChance → DPS 链路
#   - Deadly Herald：仅限 Herald 技能，8A 已覆盖
#
# 候选光环（8B，6 个）：
#   Trinity(100), Archmage(100), Charge Infusion(60),
#   Attrition(60), Berserk(60), Elemental Conflux(60)
#
# 候选精魄辅助（8C，4+1 个）：
#   Direstrike I(20), Direstrike II(40), Precision I(10), Precision II(20),
#   Refraction III(30, 估算)

# 光环预设配置映射（7A 测试时需要启用条件配置）
# key = 光环名称, value = [{"var": "configVar", "value": bool|int}, ...]
# Charge 数量在运行时从构筑 output 动态读取（见 _resolve_charge_configs）
_AURA_PRE_CONFIGS = {
    "Charge Infusion": [
        {"var": "useFrenzyCharges", "value": True},
        {"var": "overrideFrenzyCharges", "value": None},  # 动态: FrenzyChargesMax
        {"var": "usePowerCharges", "value": True},
        {"var": "overridePowerCharges", "value": None},   # 动态: PowerChargesMax
        {"var": "useEnduranceCharges", "value": True},
        {"var": "overrideEnduranceCharges", "value": None},  # 动态: EnduranceChargesMax
    ],
}

# 需要通过注入 mod 模拟的光环（POB 不计算的动态效果）
# 格式：{"mod": {...}, "expect_factor": 期望系数}
# mod.value 在运行时从构筑实际宝石等级动态填充（见 _resolve_ec_more_value）
_AURA_INJECT_MODS = {
    "Elemental Conflux": {
        "mod": {
            # value 在运行时从构筑 EC 宝石等级动态读取（statSets[1].levels[level][1]）
            # Level 20=59%, Level 21=60% 等
            "name": "ElementalDamage", "type": "MORE", "value": None,
        },
        "stat_skill_id": "ElementalConfluxPlayer",
        "expect_factor": 1/3,  # 简化：假设构筑只用一种元素
        "description": "每8秒随机选择火/冰/电，给该元素 MORE 伤害。期望收益 = MORE * 元素占比",
    },
}

# 光环/精魄候选数据
_AURA_CANDIDATES = [
    {
        "key": "trinity",
        "name": "Trinity",
        "name_cn": "三位一体",
        "skill_id": "TrinityPlayer",
        "spirit": 100,
        "description": "三属性穿透（需要 ResonanceCount 配置）",
    },
    {
        "key": "archmage",
        "name": "Archmage",
        "name_cn": "大法师",
        "skill_id": "ArchmagePlayer",
        "spirit": 100,
        "description": "Mana 转附加闪电伤害",
    },
    {
        "key": "charge_infusion",
        "name": "Charge Infusion",
        "name_cn": "充能灌注",
        "skill_id": "ChargeRegulationPlayer",
        "spirit": 60,
        "description": "Frenzy/Power/Endurance Charge 增益",
        "charge_configs": [
            {"var": "useFrenzyCharges", "type": "check", "value": True},
            {"var": "overrideFrenzyCharges", "type": "count", "value": 3},
            {"var": "usePowerCharges", "type": "check", "value": True},
            {"var": "overridePowerCharges", "type": "count", "value": 3},
            {"var": "useEnduranceCharges", "type": "check", "value": True},
            {"var": "overrideEnduranceCharges", "type": "count", "value": 3},
        ],
    },
    {
        "key": "attrition",
        "name": "Attrition",
        "name_cn": "损耗",
        "skill_id": "AttritionPlayer",
        "spirit": 60,
        "description": "命中附带 Wither 叠层",
    },
    {
        "key": "berserk",
        "name": "Berserk",
        "name_cn": "狂暴",
        "skill_id": "BerserkPlayer",
        "spirit": 60,
        "description": "MORE Damage + 受伤增加",
    },
    {
        "key": "elemental_conflux",
        "name": "Elemental Conflux",
        "name_cn": "元素交融",
        "skill_id": "ElementalConfluxPlayer",
        "spirit": 60,
        "description": "元素异常状态同步",
    },
]

_SPIRIT_SUPPORT_CANDIDATES = [
    {
        "key": "direstrike_1",
        "name": "Direstrike I",
        "name_cn": "猛击 I",
        "skill_id": "SupportDirestrikePlayer",
        "spirit": 20,
        "description": "攻击伤害 INC 50%",
        "condition": "Low Life",
        "note": "需要 Low Life 状态",
    },
    {
        "key": "direstrike_2",
        "name": "Direstrike II",
        "name_cn": "猛击 II",
        "skill_id": "SupportDirestrikePlayerTwo",
        "spirit": 40,
        "description": "攻击伤害 INC 70%",
        "condition": "Low Life",
        "note": "需要 Low Life 状态",
    },
    {
        "key": "precision_1",
        "name": "Precision I",
        "name_cn": "精准 I",
        "skill_id": "SupportPrecisionPlayer",
        "spirit": 10,
        "description": "命中 INC 30%",
        "condition": "仅攻击构筑",
        "note": "",
    },
    {
        "key": "precision_2",
        "name": "Precision II",
        "name_cn": "精准 II",
        "skill_id": "SupportPrecisionPlayerTwo",
        "spirit": 20,
        "description": "命中 INC 50%",
        "condition": "仅攻击构筑",
        "note": "",
    },
    {
        "key": "refraction_3",
        "name": "Refraction III",
        "name_cn": "折射 III",
        "skill_id": "SupportRefractionPlayerThree",
        "spirit": 30,
        "description": "每 1000 护甲 +2 元素暴露",
        "condition": "需要 Banner",
        "note": "POB 可能无法计算，标记为估算",
        "estimated": True,
    },
]

# POB ConfigOptions 中 count 类型的可测试范围上限。
# apply 函数内部用 m_max(m_min(val, N), 0) 做 clamp，
# 测试时传入 99999 让 clamp 自动截断，再从 modDB 读回实际值即可得到真实上限。
_PROBE_MAX = 99999


def _rebuild_config_tab_modlist(lua):
    """重建 build.configTab.modList / enemyModList。

    重新遍历 ConfigOptions 的所有条目，根据当前 configTab.input 值重建 modList。
    """
    lua.execute('''
        local build = _spike_build
        local configSettings = LoadModule("Modules/ConfigOptions")
        if not configSettings then return end
        local modList = new("ModList")
        local enemyModList = new("ModList")
        local input = build.configTab.input
        for _, varData in ipairs(configSettings) do
            if varData.apply then
                local varName = varData.var
                if varData.type == "check" then
                    local val = input[varName]
                    if val == nil and varData.defaultState then val = true end
                    if val then pcall(varData.apply, true, modList, enemyModList, build) end
                elseif varData.type == "count" or varData.type == "integer" or varData.type == "countAllowZero" or varData.type == "float" then
                    local val = input[varName]
                    if val and (val ~= 0 or varData.type ~= "count") then
                        pcall(varData.apply, val, modList, enemyModList, build)
                    end
                elseif varData.type == "list" then
                    local val = input[varName]
                    if val == nil and varData.list and varData.defaultIndex then
                        local defaultEntry = varData.list[varData.defaultIndex]
                        if defaultEntry then val = defaultEntry.val end
                    end
                    if val then pcall(varData.apply, val, modList, enemyModList, build) end
                end
            end
        end
        build.configTab.modList = modList
        build.configTab.enemyModList = enemyModList
    ''')


def _set_config_and_rebuild(lua, config_var: str, config_type: str, value):
    """设置一个 ConfigTab 配置值并重建 modList。

    Args:
        config_var: 配置变量名（如 'configResonanceCount'）
        config_type: 'count' 或 'check' 或 'list'
        value: 要设置的值
    """
    lua.execute(f'_spike_build.configTab.input["{config_var}"] = {value}')
    _rebuild_config_tab_modlist(lua)


def _discover_ifskill_configs(lua, aura_names: set[str]) -> list[dict]:
    """动态扫描 ConfigOptions，发现所有与构筑光环匹配的 ifSkill count 配置。

    通过 Lua 端遍历 ConfigSettings，匹配 ifSkill 条件（支持字符串和表两种格式），
    返回所有 count/integer/countAllowZero 类型的配置条目。

    Args:
        aura_names: 构筑中光环/精魄预留技能的名称集合

    Returns:
        [{
            "config_var": str,      # 配置变量名
            "config_type": str,     # 'count'/'integer'/'countAllowZero'
            "aura_name": str,       # 匹配的光环名称
            "label": str,           # POB 配置标签
            "actual_max": float,    # apply 函数 clamp 后的真实上限
        }, ...]
    """
    if not aura_names:
        return []

    # 构建 Lua 端的光环名称查找表
    aura_list = ",".join(aura_names)
    lua.execute(f'_aura_names_list = "{aura_list}"')
    result = lua.execute('''
        local configSettings = LoadModule("Modules/ConfigOptions")
        if not configSettings then return "" end

        local auraNames = {}
        for n in _aura_names_list:gmatch("[^,]+") do
            auraNames[n:match("^%s*(.-)%s*$")] = true
        end

        local lines = {}
        for _, varData in ipairs(configSettings) do
            if not varData.var then goto next end

            -- 只处理 count 类型（有范围的数值参数）
            if varData.type ~= "count" and varData.type ~= "integer"
               and varData.type ~= "countAllowZero" then
                goto next
            end

            -- 检查 ifSkill 条件是否匹配
            local matchedAura = nil
            local ifSkill = varData.ifSkill
            if type(ifSkill) == "string" then
                if auraNames[ifSkill] then matchedAura = ifSkill end
            elseif type(ifSkill) == "table" then
                for _, s in ipairs(ifSkill) do
                    if auraNames[s] then matchedAura = s; break end
                end
            end

            if matchedAura then
                lines[#lines+1] = varData.var .. "|" .. varData.type .. "|"
                    .. matchedAura .. "|" .. tostring(varData.label or "")
            end
            ::next::
        end
        return table.concat(lines, "\\n")
    ''')

    configs = []
    if not result:
        return configs

    for line in str(result).split('\n'):
        if not line.strip() or '|' not in line:
            continue
        parts = line.split('|')
        if len(parts) < 4:
            continue
        config_var, config_type, aura_name, label = parts[0], parts[1], parts[2], parts[3]

        # 用 _PROBE_MAX 探测真实上限：用临时 ModList 避免污染 configTab.modList
        # ConfigOptions 的 apply 对 count 类型做 m_max(m_min(val, max), 0)，
        # Sum(BASE, Multiplier:*) 返回 clamp 后的实际最大值。
        actual_max = lua.execute(f'''
            local configSettings = LoadModule("Modules/ConfigOptions")
            local probeList = new("ModList")
            for _, varData in ipairs(configSettings) do
                if varData.apply and varData.var and varData.var == "{config_var}" then
                    pcall(varData.apply, {_PROBE_MAX}, probeList, nil, _spike_build)
                    break
                end
            end
            -- Sum 正确合并所有同名 mod（ModList 内部双视图不影响 Sum 值）
            local s = 0
            for k, v in pairs(probeList) do
                if type(v) == "table" then
                    for _, mod in ipairs(v) do
                        if type(mod) == "table" and mod.name and mod.name:match("^Multiplier:") then
                            s = math.max(s, tonumber(mod.value) or 0)
                        end
                    end
                end
            end
            return tostring(math.floor(s + 0.5))
        ''')
        try:
            actual_max = float(actual_max)
        except (ValueError, TypeError):
            actual_max = 0.0

        # 清除探测值，避免影响后续注入逻辑
        lua.execute(f'_spike_build.configTab.input["{config_var}"] = nil')

        configs.append({
            "config_var": config_var,
            "config_type": config_type,
            "aura_name": aura_name,
            "label": label,
            "actual_max": max(actual_max, 1),
        })

    return configs


def _inject_ifskill_defaults(lua, calcs,
                              aura_configs: list[dict] | None = None):
    """为所有条件光环注入参数中间值（基线配置）。

    动态发现或使用已传入的配置列表，对每个 count 配置注入 min~max 的中间值。
    """
    if aura_configs is None:
        # 动态发现构筑中所有光环名称
        skills_info = _query_active_skills_info(lua, calcs)
        aura_names = {si["main_skill_name"] for si in skills_info if si["is_aura"]}
        aura_configs = _discover_ifskill_configs(lua, aura_names)

    for cfg in aura_configs:
        config_var = cfg["config_var"]
        config_type = cfg["config_type"]
        actual_max = cfg["actual_max"]
        mid = int(actual_max / 2)

        current = lua.execute(f'''
            return tostring(_spike_build.configTab.input["{config_var}"] or "nil")
        ''')
        if str(current) == "nil":
            _set_config_and_rebuild(lua, config_var, config_type, mid)
            logger.info("已注入 %s %s=%d（范围 0~%d）",
                        cfg["aura_name"], config_var, mid, int(actual_max))


def _test_aura_config_range(lua, calcs, aura_name: str,
                            baseline: dict,
                            aura_configs: list[dict] | None = None,
                            no_aura_dps: float = None) -> list[dict]:
    """测试条件光环所有可配置参数在最小/最大值时的 DPS 范围。

    动态查找该光环的所有 count 类型 ifSkill 配置，逐一测试端点值。
    百分比计算基准为"无光环"DPS，展示参数变化带来的 DPS 贡献。

    Args:
        aura_name: 光环名称
        baseline: 当前 baseline（用于恢复状态）
        aura_configs: 已发现的配置列表（避免重复扫描）
        no_aura_dps: 无该光环时的 DPS（作为百分比计算基准）

    Returns:
        [{"config_var", "label", "aura_name", "actual_max",
          "dps_pct_min", "dps_pct_max", "dps_min", "dps_max", "mid"}, ...]
        空列表表示该光环无条件配置。
    """
    if aura_configs is None:
        aura_configs = _discover_ifskill_configs(lua, {aura_name})

    matched = [c for c in aura_configs if c["aura_name"] == aura_name]
    if not matched:
        return []

    from .calculator import calculate as calc_fn
    # 如果没有提供 no_aura_dps，用当前 baseline（兼容旧行为）
    base_dps = no_aura_dps if no_aura_dps else baseline.get("TotalDPS", 0)

    results = []
    for cfg in matched:
        config_var = cfg["config_var"]
        config_type = cfg["config_type"]
        actual_max = cfg["actual_max"]
        mid = int(actual_max / 2)

        for endpoint_name, endpoint_val in [("min", 0), ("max", actual_max)]:
            _set_config_and_rebuild(lua, config_var, config_type, endpoint_val)
            output = calc_fn(lua, calcs)
            eps_dps = output.get("TotalDPS", 0)
            dps_pct = ((eps_dps - base_dps) / base_dps * 100) if base_dps > 0 else 0
            cfg[f"dps_{endpoint_name}"] = eps_dps
            cfg[f"dps_pct_{endpoint_name}"] = dps_pct
            # 同时读取 Speed，用于检测门槛效果和计算边际收益
            eps_speed = output.get("Speed", 0)
            if eps_speed and eps_speed > 0:
                cfg[f"speed_{endpoint_name}"] = eps_speed

        # 恢复中间值
        _set_config_and_rebuild(lua, config_var, config_type, mid)
        cfg["mid"] = mid

        results.append(cfg)

    return results


def _query_active_skills_info(lua, calcs) -> list[dict]:
    """查询构筑中所有活跃技能组信息，识别光环和精魄辅助。

    检测逻辑：
    - is_aura: 基于 skillTypes 判断是否为 Aura/Persistent+Buff 精魄预留技能，
      或组内包含精魄辅助宝石（spirit support gems）
    - spirit_cost: 所有宝石的精魄消耗总和

    Returns:
        [{
            "group_idx": int,          # 技能组索引 (1-based)
            "label": str,               # 用户标签
            "main_skill_name": str,     # 主技能名称
            "is_aura": bool,            # 是否是光环/精魄预留 (8A 测试目标)
            "spirit_cost": float,       # 总精魄消耗
            "gems": [                  # 宝石列表
                {
                    "name": str,
                    "skill_id": str,
                    "is_support": bool,
                    "enabled": bool,
                    "spirit": float,
                }, ...
            ],
            "spirit_supports": [       # 精魄辅助宝石列表
                {"name": str, "skill_id": str, "spirit": float}, ...
            ],
        }, ...]
    """
    result = lua.execute('''
        local build = _spike_build
        local groups = build.skillsTab.socketGroupList
        local lines = {}

        for gi = 1, #groups do
            local group = groups[gi]
            if not group.enabled then
                lines[#lines+1] = tostring(gi) .. "||disabled"
                goto next_group
            end

            local label = group.label or ""
            local mainSkillName = ""
            local totalSpirit = 0
            local isAuraOrSpiritReserved = false

            -- 收集所有宝石信息
            local gemInfos = {}
            local spiritSupports = {}

            for j = 1, #group.gemList do
                local gem = group.gemList[j]
                if not gem.enabled then goto next_gem end

                local gName = gem.nameSpec or "?"
                local gSkillId = gem.skillId or "?"
                local gSupport = false
                local gSpirit = 0

                -- 获取技能效果数据
                local grantedEffect = gem.grantedEffect
                    or (gem.gemData and gem.gemData.grantedEffect)
                if not grantedEffect then
                    if gem.skillId and data.skills[gem.skillId] then
                        grantedEffect = data.skills[gem.skillId]
                    end
                end

                if grantedEffect then
                    gSupport = grantedEffect.support or false
                    gName = grantedEffect.name or gName

                    -- 检查精魄消耗（从 levels 中获取 spiritReservationFlat）
                    local lvl = grantedEffect.levels and grantedEffect.levels[gem.level]
                    if lvl then
                        if lvl.spiritReservationFlat then
                            gSpirit = lvl.spiritReservationFlat
                        end
                    end

                    -- 累加总精魄消耗
                    if gSpirit > 0 then
                        totalSpirit = totalSpirit + gSpirit
                    end

                    -- 收集精魄辅助信息（有精魄消耗的辅助宝石）
                    if gSupport and gSpirit > 0 then
                        spiritSupports[#spiritSupports+1] = gName .. "|" .. (gem.skillId or "?") .. "|" .. tostring(gSpirit)
                        -- 有精魄辅助 = 光环/精魄预留组
                        isAuraOrSpiritReserved = true
                    end

                    -- 确认是否是主技能
                    if j == (group.mainActiveSkill or 1) then
                        mainSkillName = gName

                        -- 判断主技能是否为光环或精魄预留技能
                        -- 光环定义：
                        --   1. SkillType.Aura = 传统光环 (如 Purity of Fire)
                        --   2. Persistent+Buff+HasReservation 但排除：
                        --      - GeneratesRemnants(183): Life Remnants, Siphon Elements 等残骸技能
                        --      - DodgeReplacement(229): Blink 等位移替换技能
                        --      - CreatesMinion: 召唤技能
                        --      - AppliesCurse(69): 诅咒
                        --      - Triggered(37): 触发技能
                        --      - Movement(34): 移动技能
                        local st = grantedEffect.skillTypes
                        if st then
                            local isAuraSkill = (st[SkillType.Aura] ~= nil)
                            local isPer = (st[SkillType.Persistent] ~= nil)
                            local isBuff = (st[SkillType.Buff] ~= nil)
                            local isRes = (st[SkillType.HasReservation] ~= nil)
                            local isMovement = (st[SkillType.Movement] ~= nil)
                            local isMinion = (st[SkillType.CreatesMinion] ~= nil)
                            local isCurse = (st[69] ~= nil)          -- AppliesCurse
                            local isTriggered = (st[37] ~= nil)      -- Triggered
                            local isRemnant = (st[183] ~= nil)       -- GeneratesRemnants
                            local isDodge = (st[229] ~= nil)         -- DodgeReplacement

                            -- 排除项
                            if isCurse or isTriggered or isMovement or isDodge then
                                isAuraOrSpiritReserved = false
                            -- Aura 类型 → 光环
                            elseif isAuraSkill then
                                isAuraOrSpiritReserved = true
                            -- Persistent+Buff+HasReservation（排除残骸/召唤）→ 精魄预留光环
                            elseif isPer and isBuff and isRes and not isMinion and not isRemnant then
                                isAuraOrSpiritReserved = true
                            end
                        end
                    end
                end

                gemInfos[#gemInfos+1] = gName .. "|" .. (gem.skillId or "?") .. "|" .. tostring(gSupport) .. "|true|" .. tostring(gSpirit)
                ::next_gem::
            end

            lines[#lines+1] = tostring(gi) .. "||"
                .. label .. "||"
                .. mainSkillName .. "||"
                .. tostring(isAuraOrSpiritReserved) .. "||"
                .. tostring(totalSpirit) .. "||"
                .. table.concat(gemInfos, ";;") .. "||"
                .. table.concat(spiritSupports, ";;")

            ::next_group::
        end

        return table.concat(lines, "\\n")
    ''')

    if not result:
        return []

    skills_info = []
    for line in str(result).split('\n'):
        if not line.strip():
            continue
        parts = line.split('||')
        if len(parts) < 7:
            # disabled 组
            if len(parts) >= 2 and parts[1] == "disabled":
                continue
            continue

        gi = int(parts[0])
        label = parts[1]
        main_name = parts[2]
        is_aura = parts[3] == "true"
        spirit_cost = float(parts[4])

        gems = []
        if parts[5]:
            for gem_str in parts[5].split(';;'):
                gp = gem_str.split('|')
                if len(gp) >= 4:
                    gems.append({
                        "name": gp[0],
                        "skill_id": gp[1],
                        "is_support": gp[2] == "true",
                        "enabled": gp[3] == "true",
                        "spirit": float(gp[4]) if len(gp) > 4 and gp[4] else 0,
                    })

        spirit_supports = []
        if parts[6]:
            for ss_str in parts[6].split(';;'):
                sp = ss_str.split('|')
                if len(sp) >= 3:
                    spirit_supports.append({
                        "name": sp[0],
                        "skill_id": sp[1],
                        "spirit": float(sp[2]),
                    })

        skills_info.append({
            "group_idx": gi,
            "label": label,
            "main_skill_name": main_name,
            "is_aura": is_aura,
            "spirit_cost": spirit_cost,
            "gems": gems,
            "spirit_supports": spirit_supports,
        })

    return skills_info


def _query_total_spirit(lua, calcs) -> float:
    """查询构筑的总精魄和已用精魄。

    Returns:
        (total_spirit, reserved_spirit) 元组
    """
    result = lua.execute('''
        local build = _spike_build
        local env = calcs.initEnv(build, "MAIN")
        calcs.perform(env)
        local total = env.player.output.Spirit or 0
        local reserved = env.player.output.SpiritReserved or 0
        return tostring(total) .. "|" .. tostring(reserved)
    ''')
    if result:
        parts = str(result).split('|')
        try:
            return float(parts[0]), float(parts[1])
        except (ValueError, IndexError):
            pass
    return 0, 0


def _test_remove_skill_group(lua, calcs, group_idx: int,
                             baseline: dict, skill_name: str = None,
                             pre_configs: list = None,
                             inject_mods: list = None) -> dict:
    """测试禁用指定技能组后的 DPS 变化。

    按主技能名称匹配，禁用所有同名副本组（包括 item-granted 副本）。
    pre_configs: 预设配置（如 Charge）
    inject_mods: 需要注入的 mod 列表（用于模拟 POB 不计算的动态效果）
                [{"name": str, "type": "MORE"|"INC"|"BASE", "value": float}, ...]
    因为 POB 构筑中同一技能可能存在 socketed 和 item-granted 两个版本。

    Args:
        group_idx: 技能组索引 (1-based)
        skill_name: 主技能名称（用于匹配所有副本）。若为 None，只禁用指定组。

    Returns:
        {"dps_before", "dps_after", "dps_pct", "ehp_pct", "simulated": bool}
    """
    base_dps = baseline.get("TotalDPS", 0)
    base_ehp = baseline.get("TotalEHP", 0)

    # 预设条件配置（如 Charge），并重算 baseline
    if pre_configs:
        for cfg in pre_configs:
            var, val = cfg["var"], cfg["value"]
            if isinstance(val, bool):
                lua_val = "true" if val else "false"
            else:
                lua_val = val
            lua.execute(f'_spike_build.configTab.input["{var}"] = {lua_val}')
        _rebuild_config_tab_modlist(lua)
        from .calculator import calculate as calc_fn
        charged_bl = calc_fn(lua, calcs)
        base_dps = charged_bl.get("TotalDPS", 0)
        base_ehp = charged_bl.get("TotalEHP", 0)

    # 构建 Lua 代码：按名称禁用所有同名组
    if skill_name:
        lua_name = skill_name.replace("\\", "\\\\").replace('"', '\\"')
        lua_code = f'''
            local build = _spike_build
            local targetName = "{lua_name}"
            local disabled = {{}}

            -- 禁用所有同名组（通过 nameSpec 或 skillId 匹配）
            -- build_loader 不设 grantedEffect，必须用 nameSpec/skillId
            for i = 1, #build.skillsTab.socketGroupList do
                local group = build.skillsTab.socketGroupList[i]
                if not group.enabled then goto next end
                local mainIdx = group.mainActiveSkill or 1
                local gem = group.gemList[mainIdx]
                if not gem then goto next end
                -- Try grantedEffect name first (fallback), then nameSpec, then skillId
                local ge = gem.grantedEffect or (gem.gemData and gem.gemData.grantedEffect)
                local matched = false
                if ge and ge.name == targetName then
                    matched = true
                elseif gem.nameSpec == targetName then
                    matched = true
                elseif gem.skillId == targetName then
                    matched = true
                else
                    -- Also check grantedEffect via data.skills lookup
                    local sid = gem.skillId
                    if sid and data.skills[sid] and data.skills[sid].name == targetName then
                        matched = true
                    end
                end
                if matched then
                    group.enabled = false
                    disabled[#disabled+1] = i
                end
                ::next::
            end

            local ok, env = pcall(function()
                return calcs.initEnv(build, "MAIN")
            end)
            local result = ""
            if ok then
                pcall(calcs.perform, env)
                result = tostring(env.player.output.TotalDPS or 0) .. "|" .. tostring(env.player.output.TotalEHP or 0)
            else
                result = "ERROR"
            end

            -- 恢复
            for _, idx in ipairs(disabled) do
                build.skillsTab.socketGroupList[idx].enabled = true
            end

            return result
        '''
    else:
        lua_code = f'''
            local build = _spike_build
            local gi = {group_idx}
            local group = build.skillsTab.socketGroupList[gi]
            if not group then return "ERROR" end
            local origEnabled = group.enabled
            group.enabled = false
            local ok, env = pcall(function()
                return calcs.initEnv(build, "MAIN")
            end)
            local result = ""
            if ok then
                pcall(calcs.perform, env)
                result = tostring(env.player.output.TotalDPS or 0) .. "|" .. tostring(env.player.output.TotalEHP or 0)
            else
                result = "ERROR"
            end
            group.enabled = origEnabled
            return result
        '''

    result = lua.execute(lua_code)

    def _restore_pre_configs():
        if pre_configs:
            for cfg in pre_configs:
                lua.execute(f'_spike_build.configTab.input["{cfg["var"]}"] = nil')
            _rebuild_config_tab_modlist(lua)

    if not result or result == "ERROR":
        _restore_pre_configs()
        return {"dps_before": base_dps, "dps_after": base_dps, "dps_pct": 0, "ehp_pct": 0, "simulated": bool(pre_configs)}

    parts = str(result).split('|')
    try:
        new_dps = float(parts[0])
        new_ehp = float(parts[1])
    except (ValueError, IndexError):
        _restore_pre_configs()
        return {"dps_before": base_dps, "dps_after": base_dps, "dps_pct": 0, "ehp_pct": 0, "simulated": bool(pre_configs)}

    # dps_pct 表示光环贡献（正值=增加 DPS）
    dps_pct = -((new_dps - base_dps) / base_dps * 100) if base_dps > 0 else 0
    ehp_pct = -((new_ehp - base_ehp) / base_ehp * 100) if base_ehp > 0 else 0

    _restore_pre_configs()
    return {
        "dps_before": base_dps,
        "dps_after": new_dps,
        "dps_pct": dps_pct,
        "ehp_pct": ehp_pct,
        "simulated": bool(pre_configs),
    }


def _resolve_charge_map(lua, calcs) -> dict:
    """从构筑 output 读取最大充能球数。

    Returns:
        {"FrenzyCharges": int, "PowerCharges": int, "EnduranceCharges": int}
    """
    charges = lua.execute('''
        local env = calcs.initEnv(_spike_build, "MAIN")
        calcs.perform(env)
        local out = env.player.output
        return string.format("%d|%d|%d",
            tonumber(out.FrenzyChargesMax or 0),
            tonumber(out.PowerChargesMax or 0),
            tonumber(out.EnduranceChargesMax or 0))
    ''')
    if charges and str(charges) != "nil" and "|" in str(charges):
        parts = str(charges).split("|")
        return {
            "FrenzyCharges": int(parts[0]) if parts[0].isdigit() else 3,
            "PowerCharges": int(parts[1]) if parts[1].isdigit() else 3,
            "EnduranceCharges": int(parts[2]) if parts[2].isdigit() else 3,
        }
    logger.warning("无法读取构筑充能球数，使用默认值 3")
    return {"FrenzyCharges": 3, "PowerCharges": 3, "EnduranceCharges": 3}


def _fill_charge_configs(configs: list, charge_map: dict,
                        context: str = "") -> list:
    """将 configs 中 value=None 的项用 charge_map 填充。"""
    resolved = []
    for cfg in configs:
        cfg = dict(cfg)
        if cfg.get("value") is None:
            var = cfg["var"]
            for charge_type, max_val in charge_map.items():
                if charge_type in var:
                    cfg["value"] = max_val
                    logger.info("动态设置 %s: %s = %d", context, var, max_val)
                    break
            if cfg.get("value") is None:
                cfg["value"] = 0
        resolved.append(cfg)
    return resolved


def _resolve_pre_configs(lua, calcs, aura_name: str):
    """动态解析光环的预设配置，填充 None 值为构筑实际数据。

    对于 Charge Infusion：从构筑 output 读取最大充能球数。

    Returns:
        tuple: (configs_list, charge_counts_dict) 或 None
    """
    base_configs = _AURA_PRE_CONFIGS.get(aura_name)
    if not base_configs:
        return None

    if not any(c["value"] is None for c in base_configs):
        return (base_configs, None)

    charge_map = _resolve_charge_map(lua, calcs)
    resolved = _fill_charge_configs(base_configs, charge_map, context=aura_name)
    return (resolved, charge_map)


def _resolve_inject_mods(lua, calcs, inject_config: dict, aura_name: str) -> dict:
    """动态解析注入 mod 的值（从构筑实际数据读取）。

    对于 EC：从 statSets[1].levels[actual_gem_level][1] 读取 MORE 百分比。
    """
    config = dict(inject_config)  # 浅拷贝避免修改原数据
    mod = dict(config["mod"])
    stat_skill_id = config.get("stat_skill_id")

    if mod["value"] is None and stat_skill_id:
        # 动态读取：从构筑中找到该光环的宝石等级
        actual_level = lua.execute(f'''
            local build = _spike_build
            for gi = 1, #build.skillsTab.socketGroupList do
                local group = build.skillsTab.socketGroupList[gi]
                for j = 1, #group.gemList do
                    local gem = group.gemList[j]
                    local ge = gem.grantedEffect
                        or (gem.gemData and gem.gemData.grantedEffect)
                    if ge and ge.name and ge.name:find("{aura_name}") then
                        return tostring(gem.level)
                    end
                end
            end
            return nil
        ''')
        if actual_level and str(actual_level) != "nil":
            lvl = int(actual_level)
            # 从 data.skills[skillId].statSets[1].levels[level][1] 读取
            more_val = lua.execute(f'''
                local data = _spike_build.data
                local sk = data.skills["{stat_skill_id}"]
                if sk and sk.statSets and sk.statSets[1] and sk.statSets[1].levels then
                    local lvldata = sk.statSets[1].levels[{lvl}]
                    if lvldata and lvldata[1] then
                        return tostring(lvldata[1])
                    end
                end
                return nil
            ''')
            if more_val and str(more_val) != "nil":
                mod["value"] = float(more_val)
                config["gem_level"] = lvl  # 保存实际宝石等级
                logger.info("动态读取 %s MORE: Lv%d = %.0f%%", aura_name, lvl, mod["value"])
            else:
                # 回退到 statSets 第一个有数据的等级
                logger.warning("无法从 statSets 读取 %s Lv%d MORE，使用默认值", aura_name, lvl)
                mod["value"] = 0
        else:
            logger.warning("构筑中未找到 %s，跳过动态 MORE 读取", aura_name)
            mod["value"] = 0

    config["mod"] = mod
    return config


def _test_mod_effect(lua, calcs, baseline: dict,
                     aura_config: dict, skill_name: str) -> dict:
    """测试注入 mod 后的 DPS 变化（用于模拟 POB 不计算的动态效果）。

    用于 Elemental Conflux 等需要手动注入 mod 的光环。
    对于 EC，会根据主技能的伤害类型分布计算加权期望。

    Args:
        aura_config: 光环配置
            {"mod": {"name": str, "type": "MORE"|"INC"|"BASE", "value": float},
             "expect_factor": float (默认期望系数，会被实际计算覆盖)}
        skill_name: 光环名称（用于报告）

    Returns:
        {"dps_before", "dps_after", "dps_pct", "ehp_pct", "simulated": True}
    """
    from .calculator import calculate as calc_fn

    mod = aura_config["mod"]
    default_expect_factor = aura_config.get("expect_factor", 1.0)

    # 对于 EC，动态计算期望系数
    if skill_name == "Elemental Conflux":
        # 获取主技能的伤害类型分布
        damage_breakdown = lua.execute('''
            local env = calcs.initEnv(_spike_build, "MAIN")
            calcs.perform(env)
            local output = env.player.output

            -- 获取各元素的伤害贡献（StoredCombinedAvg 是各元素的平均DPS贡献）
            local fire = output.FireStoredCombinedAvg or 0
            local cold = output.ColdStoredCombinedAvg or 0
            local lightning = output.LightningStoredCombinedAvg or 0
            local total = fire + cold + lightning

            -- 计算元素伤害占比
            local fire_pct = total > 0 and (fire / total) or 0
            local cold_pct = total > 0 and (cold / total) or 0
            local lightning_pct = total > 0 and (lightning / total) or 0

            -- EC 期望收益 = (火占比 + 冰占比 + 电占比) / 3
            -- 因为 EC 随机选择一个元素，选中的元素如果主技能用到了，才有收益
            local expect_factor = (fire_pct + cold_pct + lightning_pct) / 3

            return string.format("%.4f|%.4f|%.4f|%.4f",
                expect_factor, fire_pct, cold_pct, lightning_pct)
        ''')
        parts = str(damage_breakdown).split('|')
        expect_factor = float(parts[0]) if parts else default_expect_factor
        fire_pct = float(parts[1]) * 100 if len(parts) > 1 else 0
        cold_pct = float(parts[2]) * 100 if len(parts) > 2 else 0
        lightning_pct = float(parts[3]) * 100 if len(parts) > 3 else 0
    else:
        expect_factor = default_expect_factor
        fire_pct = cold_pct = lightning_pct = 0

    # 计算期望值
    expected_value = mod["value"] * expect_factor

    # 注入期望值 mod 到 modDB
    lua.execute(f'''
        local env = calcs.initEnv(_spike_build, "MAIN")
        -- 注入期望值 mod（已乘期望系数）
        env.player.modDB:NewMod("{mod["name"]}", "{mod["type"]}", {expected_value}, "{skill_name} (期望)")
        calcs.perform(env)
        _spike_base_dps = env.player.output.TotalDPS or 0
        _spike_base_ehp = env.player.output.TotalEHP or 0
    ''')
    base_dps = float(lua.eval('_spike_base_dps') or 0)
    base_ehp = float(lua.eval('_spike_base_ehp') or 0)

    # 计算无 mod 的 DPS（移除光环后的 DPS）
    lua.execute('''
        local env = calcs.initEnv(_spike_build, "MAIN")
        calcs.perform(env)
        _spike_no_mod_dps = env.player.output.TotalDPS or 0
        _spike_no_mod_ehp = env.player.output.TotalEHP or 0
    ''')
    no_mod_dps = float(lua.eval('_spike_no_mod_dps') or 0)
    no_mod_ehp = float(lua.eval('_spike_no_mod_ehp') or 0)

    # 清理临时变量
    lua.execute('_spike_base_dps, _spike_base_ehp, _spike_no_mod_dps, _spike_no_mod_ehp = nil, nil, nil, nil')

    # 百分比：有 mod vs 无 mod（移除光环 = DPS 下降 → 贡献为正）
    dps_pct = -((no_mod_dps - base_dps) / base_dps * 100) if base_dps > 0 else 0
    ehp_pct = -((no_mod_ehp - base_ehp) / base_ehp * 100) if base_ehp > 0 else 0

    result = {
        "dps_before": base_dps,
        "dps_after": no_mod_dps,
        "dps_pct": dps_pct,
        "ehp_pct": ehp_pct,
        "simulated": True,
        "expect_factor": expect_factor,
        "raw_value": mod["value"],
        "gem_level": aura_config.get("gem_level"),  # 构筑实际宝石等级
    }

    # 对于 EC，记录伤害构成用于报告
    if skill_name == "Elemental Conflux":
        result["damage_breakdown"] = {
            "fire": fire_pct,
            "cold": cold_pct,
            "lightning": lightning_pct,
        }

    return result



def _test_add_candidate_aura(lua, calcs, aura: dict,
                              baseline: dict) -> dict:
    """测试添加候选光环后的 DPS 变化。

    通过向 Lua 添加一个新的 socket group 来测试光环效果。
    如果 aura 有 charge_configs 字段，在测试前先启用对应的 Charge 配置。

    Returns:
        {"name", "dps_before", "dps_after", "dps_pct", "spirit", "error"}
    """
    base_dps = baseline.get("TotalDPS", 0)
    base_ehp = baseline.get("TotalEHP", 0)
    skill_id = aura["skill_id"]

    # 预设 Charge/条件配置（如有）
    charge_configs = aura.get("charge_configs", [])
    # 动态解析 Charge 数量（None → 从构筑 output 读取）
    if charge_configs and any(c.get("value") is None for c in charge_configs):
        charge_map = _resolve_charge_map(lua, calcs)
        resolved_configs = _fill_charge_configs(charge_configs, charge_map, context=aura["name"])
    else:
        resolved_configs = charge_configs
    for cfg in resolved_configs:
        var, val = cfg["var"], cfg["value"]
        if isinstance(val, bool):
            lua_val = "true" if val else "false"
            lua.execute(f'_spike_build.configTab.input["{var}"] = {lua_val}')
        else:
            lua.execute(f'_spike_build.configTab.input["{var}"] = {val}')

    # 重建 configTab modList（使预设生效）
    if resolved_configs:
        _rebuild_config_tab_modlist(lua)

    result = lua.execute(f'''
        local build = _spike_build

        -- 查找候选光环的 skillId 对应的 grantedEffect
        local ge = nil
        -- 先尝试通过 data.gems 查找
        for gid, gem in pairs(data.gems) do
            if gem.grantedEffectId == "{skill_id}" then
                ge = gem.grantedEffect
                break
            end
        end
        -- 再尝试通过 data.skills 直接查找
        if not ge and data.skills["{skill_id}"] then
            ge = data.skills["{skill_id}"]
        end

        if not ge then
            return "NOT_FOUND|" .. "{skill_id}"
        end

        -- 创建新的技能组
        local maxLevel = 0
        for lvl, _ in pairs(ge.levels or {{}}) do
            if lvl > maxLevel then maxLevel = lvl end
        end
        if maxLevel == 0 then maxLevel = 1 end

        -- 动态读取精魄消耗
        local spiritCost = 0
        local maxLvData = ge.levels[maxLevel]
        if maxLvData and maxLvData.spiritReservationFlat then
            spiritCost = maxLvData.spiritReservationFlat
        end

        local newGroup = {{
            enabled = true,
            includeInFullDPS = true,
            label = "[WhatIf] {aura["name"]}",
            slot = nil,
            source = nil,
            mainActiveSkill = 1,
            mainActiveSkillCalcs = 1,
            displaySkillList = {{}},
            displaySkillListCalcs = {{}},
            displayGemList = {{}},
            gemList = {{
                {{
                    skillId = "{skill_id}",
                    nameSpec = ge.name or "{aura["name"]}",
                    level = maxLevel,
                    quality = 0,
                    enabled = true,
                    enableGlobal1 = true,
                    enableGlobal2 = true,
                    count = 1,
                    statSet = {{}},
                    statSetCalcs = {{}},
                    skillMinionSkillStatSetIndexLookup = {{}},
                    skillMinionSkillStatSetIndexLookupCalcs = {{}},
                    grantedEffect = ge,
                }},
            }},
        }}

        -- 注册到构建
        local origCount = #build.skillsTab.socketGroupList
        table.insert(build.skillsTab.socketGroupList, newGroup)

        -- 重新计算
        local ok, env = pcall(function()
            return calcs.initEnv(build, "MAIN")
        end)
        if not ok then
            build.skillsTab.socketGroupList[origCount + 1] = nil
            return "ERROR|" .. tostring(env)
        end

        pcall(calcs.perform, env)
        local newDps = env.player.output.TotalDPS or 0
        local newEhp = env.player.output.TotalEHP or 0

        -- 清理
        build.skillsTab.socketGroupList[origCount + 1] = nil

        return "OK|" .. tostring(newDps) .. "|" .. tostring(newEhp) .. "|" .. tostring(spiritCost)
    ''')

    def _restore_charge_configs():
        """恢复 charge 配置并重建 configTab modList。"""
        if resolved_configs:
            for cfg in resolved_configs:
                lua.execute(f'_spike_build.configTab.input["{cfg["var"]}"] = nil')
            _rebuild_config_tab_modlist(lua)

    if not result:
        _restore_charge_configs()
        return {
            "name": aura["name"], "dps_before": base_dps, "dps_after": base_dps,
            "dps_pct": 0, "spirit": 0, "error": "Lua returned None",
        }

    parts = str(result).split('|')
    if parts[0] == "NOT_FOUND" or parts[0] == "ERROR":
        _restore_charge_configs()
        return {
            "name": aura["name"], "dps_before": base_dps, "dps_after": base_dps,
            "dps_pct": 0, "spirit": 0,
            "error": str(result),
        }

    try:
        new_dps = float(parts[1])
        new_ehp = float(parts[2]) if len(parts) > 2 else base_ehp
        spirit_cost = float(parts[3]) if len(parts) > 3 else 0
    except (ValueError, IndexError):
        _restore_charge_configs()
        return {
            "name": aura["name"], "dps_before": base_dps, "dps_after": base_dps,
            "dps_pct": 0, "spirit": 0, "error": "Parse error",
        }

    _restore_charge_configs()

    dps_pct = ((new_dps - base_dps) / base_dps * 100) if base_dps > 0 else 0
    ehp_pct = ((new_ehp - base_ehp) / base_ehp * 100) if base_ehp > 0 else 0

    return {
        "name": aura["name"],
        "name_cn": aura.get("name_cn", ""),
        "description": aura.get("description", ""),
        "dps_before": base_dps,
        "dps_after": new_dps,
        "dps_pct": dps_pct,
        "ehp_pct": ehp_pct,
        "spirit": spirit_cost,
        "error": None,
    }


def _test_add_spirit_support(lua, calcs, support: dict,
                             aura_group_idx: int,
                             baseline: dict) -> dict:
    """测试向指定光环技能组添加精魄辅助后的 DPS 变化。

    Args:
        support: 精魄辅助候选数据
        aura_group_idx: 目标光环技能组索引

    Returns:
        {"name", "dps_before", "dps_after", "dps_pct", "spirit",
         "target_aura", "condition", "note", "estimated", "error"}
    """
    base_dps = baseline.get("TotalDPS", 0)
    base_ehp = baseline.get("TotalEHP", 0)
    skill_id = support["skill_id"]

    result = lua.execute(f'''
        local build = _spike_build
        local gi = {aura_group_idx}
        local group = build.skillsTab.socketGroupList[gi]
        if not group then return "ERROR|group not found" end

        -- 查找精魄辅助的 grantedEffect
        local ge = nil
        for gid, gem in pairs(data.gems) do
            if gem.grantedEffectId == "{skill_id}" then
                ge = gem.grantedEffect
                break
            end
        end
        if not ge and data.skills["{skill_id}"] then
            ge = data.skills["{skill_id}"]
        end
        if not ge then
            return "NOT_FOUND|{skill_id}"
        end

        local maxLevel = 0
        for lvl, _ in pairs(ge.levels or {{}}) do
            if lvl > maxLevel then maxLevel = lvl end
        end
        if maxLevel == 0 then maxLevel = 1 end

        -- 动态读取精魄消耗
        local spiritCost = 0
        local maxLvData = ge.levels[maxLevel]
        if maxLvData and maxLvData.spiritReservationFlat then
            spiritCost = maxLvData.spiritReservationFlat
        end

        -- 创建精魄辅助宝石对象
        local supportGem = {{
            skillId = "{skill_id}",
            nameSpec = ge.name or "{support["name"]}",
            level = maxLevel,
            quality = 0,
            enabled = true,
            enableGlobal1 = true,
            enableGlobal2 = true,
            count = 1,
            statSet = {{}},
            statSetCalcs = {{}},
            skillMinionSkillStatSetIndexLookup = {{}},
            skillMinionSkillStatSetIndexLookupCalcs = {{}},
            grantedEffect = ge,
            color = "^8",
        }}

        -- 添加到技能组的 gemList
        local origGemCount = #group.gemList
        table.insert(group.gemList, supportGem)

        -- 重新计算
        local ok, env = pcall(function()
            return calcs.initEnv(build, "MAIN")
        end)
        if not ok then
            group.gemList[origGemCount + 1] = nil
            return "ERROR|" .. tostring(env)
        end

        pcall(calcs.perform, env)
        local newDps = env.player.output.TotalDPS or 0
        local newEhp = env.player.output.TotalEHP or 0

        -- 清理
        group.gemList[origGemCount + 1] = nil

        return "OK|" .. tostring(newDps) .. "|" .. tostring(newEhp) .. "|" .. tostring(spiritCost)
    ''')

    if not result:
        return {
            "name": support["name"], "dps_before": base_dps, "dps_after": base_dps,
            "dps_pct": 0, "spirit": 0, "target_aura": "",
            "condition": support.get("condition", ""), "note": support.get("note", ""),
            "estimated": support.get("estimated", False), "error": "Lua returned None",
        }

    parts = str(result).split('|')
    if parts[0] == "NOT_FOUND" or parts[0] == "ERROR":
        return {
            "name": support["name"], "dps_before": base_dps, "dps_after": base_dps,
            "dps_pct": 0, "spirit": 0, "target_aura": "",
            "condition": support.get("condition", ""), "note": support.get("note", ""),
            "estimated": support.get("estimated", False), "error": str(result),
        }

    try:
        new_dps = float(parts[1])
        new_ehp = float(parts[2]) if len(parts) > 2 else base_ehp
        spirit_cost = float(parts[3]) if len(parts) > 3 else 0
    except (ValueError, IndexError):
        return {
            "name": support["name"], "dps_before": base_dps, "dps_after": base_dps,
            "dps_pct": 0, "spirit": 0, "target_aura": "",
            "condition": support.get("condition", ""), "note": support.get("note", ""),
            "estimated": support.get("estimated", False), "error": "Parse error",
        }

    dps_pct = ((new_dps - base_dps) / base_dps * 100) if base_dps > 0 else 0
    ehp_pct = ((new_ehp - base_ehp) / base_ehp * 100) if base_ehp > 0 else 0

    # 获取目标光环名称
    target_aura = ""
    skills_info = _query_active_skills_info(lua, calcs)
    for si in skills_info:
        if si["group_idx"] == aura_group_idx:
            target_aura = si["main_skill_name"]
            break

    return {
        "name": support["name"],
        "name_cn": support.get("name_cn", ""),
        "description": support.get("description", ""),
        "dps_before": base_dps,
        "dps_after": new_dps,
        "dps_pct": dps_pct,
        "ehp_pct": ehp_pct,
        "spirit": spirit_cost,
        "target_aura": target_aura,
        "target_group_idx": aura_group_idx,
        "condition": support.get("condition", ""),
        "note": support.get("note", ""),
        "estimated": support.get("estimated", False),
        "error": None,
    }


def aura_spirit_analysis(lua, calcs, baseline: dict = None,
                         skill_flags: dict = None,
                         dps_breakdown: dict = None) -> dict:
    """Section 7: 光环与精魄分析。

    7A: 现有光环/精魄移除测试 — 逐一禁用构筑中的光环，测量 DPS 贡献
    7B: 潜在光环推荐 — 测试 6 个候选光环的 DPS 收益
    7C: 精魄辅助推荐 — 测试向现有光环添加精魄辅助的 DPS 收益
    7D: Spirit Budget 汇总 — 总精魄、已用精魄、推荐精魄

    Args:
        lua: LuaRuntime
        calcs: POB calcs 模块
        baseline: 基线 output
        skill_flags: 技能 flags（用于过滤攻击/法术专属）
        dps_breakdown: DPS 拆解数据（含构筑已有 modifier 总量，如 Speed_INC）
    """
    from .calculator import calculate as calc_fn

    if baseline is None:
        baseline = calc_fn(lua, calcs)

    base_dps = baseline.get("TotalDPS", 0)
    is_attack = skill_flags.get("is_attack", False) if skill_flags else False
    is_spell = skill_flags.get("is_spell", True) if skill_flags else True

    # 先查询技能信息以获取光环名称列表
    skills_info = _query_active_skills_info(lua, calcs)
    aura_names = {si["main_skill_name"] for si in skills_info if si["is_aura"]}

    # 动态发现所有与构筑光环匹配的 ifSkill count 配置
    aura_configs = _discover_ifskill_configs(lua, aura_names)
    logger.info("发现 %d 个条件配置: %s",
                len(aura_configs),
                ", ".join(f"{c['aura_name']}/{c['config_var']}({int(c['actual_max'])})"
                          for c in aura_configs))

    # 注入中间值作为基线
    _inject_ifskill_defaults(lua, calcs, aura_configs=aura_configs)
    baseline = calc_fn(lua, calcs)
    base_dps = baseline.get("TotalDPS", 0)
    logger.info("注入 ifSkill 默认值后基线: TotalDPS=%.0f", base_dps)

    logger.info("技能信息查询完成: %d 个技能组", len(skills_info))

    # 查询精魄
    total_spirit, reserved_spirit = _query_total_spirit(lua, calcs)
    logger.info("精魄: 总计 %.0f, 已用 %.0f", total_spirit, reserved_spirit)

    # === 7A: 现有光环/精魄移除测试 ===
    existing_auras = []
    seen_aura_names = set()
    for si in skills_info:
        if not si["is_aura"]:
            continue
        # 跳过精魄消耗为 0 且无精魄辅助的组（重复/无效组）
        if si["spirit_cost"] <= 0 and not si["spirit_supports"]:
            continue
        # 跳过重复组（同名光环只保留第一个）
        aura_key = si["main_skill_name"]
        if aura_key in seen_aura_names:
            continue
        seen_aura_names.add(aura_key)

        # 检查是否需要预设配置（如 Charge）
        pre_resolve = _resolve_pre_configs(lua, calcs, si["main_skill_name"])
        pre_configs = pre_resolve[0] if pre_resolve else None
        charge_counts = pre_resolve[1] if pre_resolve else None

        # 检查是否需要注入 mod 模拟（如 Elemental Conflux）
        inject_mods = _AURA_INJECT_MODS.get(si["main_skill_name"])

        if inject_mods:
            # 动态解析注入 mod 的值（如 EC MORE 从实际宝石等级读取）
            resolved_mods = _resolve_inject_mods(
                lua, calcs, inject_mods, si["main_skill_name"])
            # 使用 mod 注入方式测试
            result = _test_mod_effect(
                lua, calcs, baseline, resolved_mods,
                skill_name=si["main_skill_name"])
        else:
            # 标准测试：禁用技能组
            result = _test_remove_skill_group(
                lua, calcs, si["group_idx"], baseline,
                skill_name=si["main_skill_name"],
                pre_configs=pre_configs)

        aura_entry = {
            "name": si["main_skill_name"],
            "label": si["label"],
            "group_idx": si["group_idx"],
            "spirit_cost": si["spirit_cost"],
            "spirit_supports": si["spirit_supports"],
            "gems": [g["name"] for g in si["gems"] if g["enabled"]],
            **result,
        }

        # 保存 Charge 数量供报告使用
        if charge_counts:
            aura_entry["charge_counts"] = charge_counts

        # 对有条件配置的光环，测试参数范围（min/max 端点）
        # 使用"无光环"时的 DPS 作为百分比计算基准
        config_range = _test_aura_config_range(
            lua, calcs, si["main_skill_name"], baseline,
            aura_configs=aura_configs,
            no_aura_dps=result.get("dps_after"))
        if config_range:
            aura_entry["config_ranges"] = config_range

        existing_auras.append(aura_entry)

    # 排序：按 DPS 影响绝对值降序
    existing_auras.sort(key=lambda x: abs(x["dps_pct"]), reverse=True)
    logger.info("8A 完成: %d 个光环测试", len(existing_auras))

    # === 7B: 潜在光环推荐 ===
    available_spirit = total_spirit - reserved_spirit
    candidate_auras = []
    for aura in _AURA_CANDIDATES:
        # 跳过构筑中已有的光环
        if aura["name"] in aura_names:
            continue
        result = _test_add_candidate_aura(lua, calcs, aura, baseline)
        # 标注精魄需求（不再标记 error，统一展示）
        actual_spirit = result.get("spirit", 0)
        if actual_spirit > available_spirit:
            shortfall = actual_spirit - available_spirit
            result["spirit_shortfall"] = shortfall
            result["spirit_note"] = f"需精魄 {actual_spirit:.0f}（缺 {shortfall:.0f}）"
        candidate_auras.append(result)

    # 排序：按 DPS 增益降序
    candidate_auras.sort(key=lambda x: x.get("dps_pct", 0), reverse=True)
    logger.info("8B 完成: %d 个候选光环测试", len(candidate_auras))

    # === 7C: 精魄辅助推荐 ===
    spirit_support_tests = []

    # 找到所有可以作为精魄辅助目标的光环技能组
    aura_groups = [si for si in skills_info if si["is_aura"]]

    # 过滤出适合的精魄候选
    # Precision 仅对攻击构筑有效
    filtered_supports = []
    for ss in _SPIRIT_SUPPORT_CANDIDATES:
        if ss["key"] in ("precision_1", "precision_2") and not is_attack:
            continue
        filtered_supports.append(ss)

    for ss in filtered_supports:
        for aura_si in aura_groups:
            result = _test_add_spirit_support(
                lua, calcs, ss, aura_si["group_idx"], baseline)
            # 标注精魄需求（不再标记 error，统一展示）
            actual_spirit = result.get("spirit", 0)
            if actual_spirit > available_spirit:
                shortfall = actual_spirit - available_spirit
                result["spirit_shortfall"] = shortfall
                result["spirit_note"] = f"需精魄 {actual_spirit:.0f}（缺 {shortfall:.0f}）"
            spirit_support_tests.append(result)

    # 排序：按 DPS 增益降序
    spirit_support_tests.sort(
        key=lambda x: -abs(x.get("dps_pct", 0))
    )
    logger.info("8C 完成: %d 个精魄辅助测试", len(spirit_support_tests))

    # === 7D: Spirit Budget ===
    # 计算推荐精魄消耗总和（含精魄不足项）
    recommended_spirit = 0
    for ca in candidate_auras:
        if ca.get("dps_pct", 0) > 0.1:
            recommended_spirit += ca.get("spirit", 0)

    spirit_budget = {
        "total": total_spirit,
        "reserved": reserved_spirit,
        "available": available_spirit,
        "recommended_total": recommended_spirit,
        "recommended_remaining": available_spirit - recommended_spirit,
    }

    # === 提取构筑已有 modifier 总量（来自 dps_breakdown） ===
    build_modifiers = {}
    if dps_breakdown:
        for item in dps_breakdown.get("formula_items", []):
            key = item.get("key", "")
            total = item.get("total_value", 0)
            display = item.get("display_value", "")
            # 提取关键 modifier：Speed_INC, ElementalDamage_INC, ElementalDamage_MORE 等
            if key and total:
                build_modifiers[key] = {"total": total, "display": display}

    return {
        "existing_auras": existing_auras,
        "candidate_auras": candidate_auras,
        "spirit_support_tests": spirit_support_tests,
        "spirit_budget": spirit_budget,
        "build_modifiers": build_modifiers,
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
            "aura_spirit": {光环与精魄分析, 详见 aura_spirit_analysis()},
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

    # 7. 光环与精魄分析（传入 dps_breakdown 以引用构筑已有 modifier）
    aura_spirit = aura_spirit_analysis(
        lua, calcs, baseline=baseline, skill_flags=skill_flags,
        dps_breakdown=dps_bd)
    logger.info("光环与精魄分析完成")

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
    }


# =============================================================================
# 报告格式化（Markdown 表格）
# =============================================================================


def _format_section7(lines: list, aura_data: dict, skill_flags: dict,
                    baseline: dict, build_modifiers: dict = None):
    """格式化 Section 7: 光环与精魄分析。"""
    existing_auras = aura_data.get("existing_auras", [])
    candidate_auras = aura_data.get("candidate_auras", [])
    spirit_tests = aura_data.get("spirit_support_tests", [])
    budget = aura_data.get("spirit_budget", {})

    # 从 build_modifiers 提取构筑已有 modifier 总量
    bm = build_modifiers or {}
    speed_inc = bm.get("Speed_INC", {}).get("total", 0)
    # Damage_MORE 是所有 MORE 修饰符的汇总乘数（如 ×1.20 表示 20% MORE）
    total_more = bm.get("Damage_MORE", {}).get("total", 1)

    lines.append("## 7. 光环与精魄分析")
    lines.append("")

    # 7A: 现有光环
    lines.append("### 7A. 现有光环 DPS 贡献")
    lines.append("")

    if existing_auras:
        lines.append("| # | 光环 | DPS 贡献 | EHP 贡献 | 精魄消耗 | 条件参数范围 |")
        lines.append("|---|------|----------|----------|----------|-------------|")
        for i, a in enumerate(existing_auras, 1):
            name = a.get("name", "?")
            dp = a.get("dps_pct", 0)
            ep = a.get("ehp_pct", 0)
            sp = a.get("spirit_cost", 0)



            # DPS 贡献列：正值=该光环对 DPS 的正向贡献（移除后 DPS 下降的百分比）
            dp_str = f"{dp:+.1f}%"
            if a.get("simulated"):
                dp_str += " ⚠️模拟"

            # 条件参数范围列：展示参数对 DPS 的影响
            # 百分比 vs「无光环」状态（no_aura_dps），展示参数变化带来的 DPS 贡献
            ranges = a.get("config_ranges", [])
            if ranges:
                parts = []
                for cr in ranges:
                    label = cr.get("label", cr["config_var"])
                    label = label.rstrip(":")
                    actual_max = int(cr["actual_max"])
                    pct_min = cr.get("dps_pct_min", 0)
                    pct_max = cr.get("dps_pct_max", 0)
                    mid = cr.get("mid", 0)
                    dp_str += f" (条件: {label}={mid})"

                    # 动态检测 Speed 门槛效果：比较 min 和 max 端点的 Speed
                    marginal_note = ""
                    speed_min = cr.get("speed_min", 0)
                    speed_max = cr.get("speed_max", 0)
                    if speed_min > 0 and speed_max > speed_min:
                        # Speed 发生跳变（门槛效果触发）
                        actual_speed_inc = (speed_max - speed_min) / speed_min * 100
                        # 边际收益 = 新增 INC / (1 + 已有 INC)
                        marginal = actual_speed_inc / (1 + speed_inc / 100) if speed_inc > 0 else actual_speed_inc
                        marginal_note = f" (Speed门槛+{actual_speed_inc:.1f}%, 边际≈{marginal:.1f}%)"

                    parts.append(f"{label}=0: {pct_min:+.1f}%, {label}={actual_max}: {pct_max:+.1f}%{marginal_note}")
                range_str = "; ".join(parts)
            else:
                range_str = "-"

            lines.append(f"| {i} | {name} | {dp_str} | {ep:+.1f}% | {sp:.0f} | {range_str} |")
        lines.append("")

        # 模拟值说明
        simulated_auras = [a for a in existing_auras if a.get("simulated")]
        if simulated_auras:
            lines.append("**⚠️模拟值说明：**")
            lines.append("")
            for a in simulated_auras:
                name = a.get("name", "?")
                gem_level = a.get("gem_level", "20")  # 构筑实际宝石等级
                if name == "Elemental Conflux":
                    raw_val = a.get("raw_value", 59)
                    expect_factor = a.get("expect_factor", 1/3)
                    breakdown = a.get("damage_breakdown", {})
                    fire_pct = breakdown.get("fire", 0)
                    cold_pct = breakdown.get("cold", 0)
                    lightning_pct = breakdown.get("lightning", 0)
                    total_elemental = fire_pct + cold_pct + lightning_pct
                    expected_more = raw_val * expect_factor
                    lines.append(f"- **{name}** (Lv{gem_level}): 给选中元素 {raw_val:.0f}% MORE。主技能伤害构成：火 {fire_pct:.1f}% / 冰 {cold_pct:.1f}% / 电 {lightning_pct:.1f}%，元素总占比 {total_elemental:.1f}%。期望收益 = {raw_val:.0f}% × {total_elemental:.1f}% ÷ 3 ≈ {expected_more:.1f}% MORE")
                elif name == "Charge Infusion":
                    charges = a.get("charge_counts", {})
                    f_str = f"F={charges.get('FrenzyCharges', '?')}"
                    p_str = f"P={charges.get('PowerCharges', '?')}"
                    e_str = f"E={charges.get('EnduranceCharges', '?')}"
                    lines.append(f"- **{name}** (Lv{gem_level}): 需启用 Charge 配置才能生效，已模拟 {f_str}/{p_str}/{e_str}")
                else:
                    lines.append(f"- **{name}** (Lv{gem_level}): 已模拟条件配置")
            lines.append("")

            # 通用说明
            lines.append("**模拟方法说明：**")
            lines.append("")
            lines.append("- **等级前提**：光环模拟基于构筑实际宝石等级数据（非固定 Level 20）")
            lines.append("- **DPS 贡献计算**：移除光环后 DPS 下降百分比（正值=正向贡献）。条件光环需注入参数才能生效，默认注入参数最大值的 50%，标注在 DPS 贡献括号中")
            lines.append(f"- **构筑已有 modifier**：施法速度 INC {speed_inc:.0f}%，总 MORE ×{total_more:.2f}。INC 叠加为加法（新增边际递减），MORE 叠加为乘法")
            lines.append("- **条件范围计算**：设置参数绝对值（0 和 max），对比「无光环」DPS。自动检测 Speed 门槛效果（端点间 Speed 跳变）并标注实际边际收益")
            lines.append("- **期望收益计算**：对于 EC 等随机效果光环，期望 = 效果值 × 受影响技能元素占比之和 ÷ 3（因为随机选择火/冰/电之一）")
            lines.append("")

        # 纯防御光环（移除后 DPS 影响小但 EHP 有影响）
        def_auras = [a for a in existing_auras
                     if abs(a.get("dps_pct", 0)) < 0.1
                     and abs(a.get("ehp_pct", 0)) >= 0.1]
        if def_auras:
            lines.append("**纯防御光环**（移除后 EHP 下降）：")
            lines.append("")
            for a in def_auras:
                lines.append(f"- **{a['name']}**: EHP {a['ehp_pct']:+.1f}%, 精魄 {a['spirit_cost']:.0f}")
            lines.append("")

        dps_auras = [a for a in existing_auras if abs(a.get("dps_pct", 0)) >= 0.1]
        zero_auras = [a for a in existing_auras
                      if abs(a.get("dps_pct", 0)) < 0.1
                      and abs(a.get("ehp_pct", 0)) < 0.1]

        if zero_auras:
            lines.append(f"**DPS/EHP 影响未检测到** ({len(zero_auras)} 个)：")
            lines.append("")
            lines.append("这些光环可能提供非DPS收益（如生存/功能性），或其效果依赖动态条件（如Frenzy Charge）而POB未完全计算。")
            lines.append("")
            for a in zero_auras:
                lines.append(f"- **{a['name']}**: 精魄 {a['spirit_cost']:.0f}")
            lines.append("")
    else:
        lines.append("构筑中无活跃光环。")
        lines.append("")

    # 7B: 潜在光环推荐
    lines.append("### 7B. 潜在光环推荐")
    lines.append("")

    effective_candidates = [c for c in candidate_auras
                            if c.get("dps_pct", 0) > 0.1]
    failed_candidates = [c for c in candidate_auras
                          if c.get("dps_pct", 0) <= 0.1]

    if effective_candidates:
        lines.append("| # | 光环 | 精魄 | DPS% | EHP% | 说明 |")
        lines.append("|---|------|------|------|------|------|")
        for i, c in enumerate(effective_candidates, 1):
            name = c.get("name", "?")
            name_cn = c.get("name_cn", "")
            sp = c.get("spirit", 0)
            dp = c.get("dps_pct", 0)
            ep = c.get("ehp_pct", 0)
            desc = c.get("description", "")
            # 精魄不足时在说明中标注
            if c.get("spirit_note"):
                desc = f"{c['spirit_note']}; {desc}" if desc else c["spirit_note"]
            display = f"{name}" + (f"（{name_cn}）" if name_cn else "")
            lines.append(f"| {i} | {display} | {sp:.0f} | {dp:+.1f}% | {ep:+.1f}% | {desc} |")
        lines.append("")

    if failed_candidates:
        lines.append("**无 DPS 影响：**")
        lines.append("")
        for c in failed_candidates:
            name = c.get("name", "?")
            name_cn = c.get("name_cn", "")
            display = f"{name}" + (f"（{name_cn}）" if name_cn else "")
            lines.append(f"- {display}")
        lines.append("")

    # 7C: 精魄辅助推荐
    lines.append("### 7C. 精魄辅助推荐")
    lines.append("")

    effective_ss = [s for s in spirit_tests
                    if s.get("dps_pct", 0) > 0.1]
    failed_ss = [s for s in spirit_tests
                 if s.get("dps_pct", 0) <= 0.1]

    if effective_ss:
        lines.append("| # | 精魄辅助 | 目标光环 | 精魄 | DPS% | 条件 |")
        lines.append("|---|----------|----------|------|------|------|")
        for i, s in enumerate(effective_ss, 1):
            name = s.get("name", "?")
            name_cn = s.get("name_cn", "")
            target = s.get("target_aura", "?")
            sp = s.get("spirit", 0)
            dp = s.get("dps_pct", 0)
            cond = s.get("condition", "")
            # 精魄不足时在条件中标注
            if s.get("spirit_note"):
                cond = f"{s['spirit_note']}; {cond}" if cond else s["spirit_note"]
            estimated = " ⚠️估算" if s.get("estimated") else ""
            display = f"{name}" + (f"（{name_cn}）" if name_cn else "")
            lines.append(f"| {i} | {display} | {target} | {sp:.0f} | {dp:+.1f}% | {cond}{estimated} |")
        lines.append("")

    if failed_ss:
        lines.append(f"**无 DPS 影响：** {len(failed_ss)} 个组合")
        lines.append("")

    # 7D: Spirit Budget
    lines.append("### 7D. 精魄预算")
    lines.append("")

    total = budget.get("total", 0)
    reserved = budget.get("reserved", 0)
    available = budget.get("available", 0)
    rec_total = budget.get("recommended_total", 0)
    rec_remain = budget.get("recommended_remaining", 0)

    lines.append("| 项目 | 精魄 |")
    lines.append("|------|------|")
    lines.append(f"| 总精魄 | {total:.0f} |")
    lines.append(f"| 已用精魄 | {reserved:.0f} |")
    lines.append(f"| 可用精魄 | {available:.0f} |")

    if rec_total > 0:
        lines.append(f"| 推荐光环消耗 | {rec_total:.0f} |")
        lines.append(f"| 推荐后剩余 | {rec_remain:.0f} |")

    if rec_remain < 0:
        lines.append("")
        lines.append("**注意**: 推荐光环的精魄总消耗超过可用精魄，需要根据优先级取舍。")

    lines.append("")

    # 7E: 数据一致性校验
    warnings = _validate_aura_consistency(aura_data)
    if warnings:
        lines.append("### 7E. 数据一致性检查")
        lines.append("")
        lines.append("**⚠️ 以下项目需要人工确认：**")
        lines.append("")
        for w in warnings:
            lines.append(f"- {w}")
        lines.append("")


def _validate_aura_consistency(aura_data: dict) -> list:
    """数据一致性校验，返回警告列表。

    校验规则：
    1. EC MORE 值非零（确保动态读取成功）
    2. Charge 数量与默认值 3 不同时标注
    3. 候选光环无 DPS 影响时检查可能原因
    """
    warnings = []

    existing = aura_data.get("existing_auras", [])
    candidates = aura_data.get("candidate_auras", [])

    # B1. EC MORE 值检查
    for a in existing:
        if a.get("name") == "Elemental Conflux" and a.get("simulated"):
            raw_val = a.get("raw_value", 0)
            gem_level = a.get("gem_level")
            if raw_val <= 0:
                warnings.append(f"EC MORE 值为 {raw_val}（动态读取可能失败），结果不可靠")
            elif gem_level and gem_level != 20:
                # 非标准等级时提示
                warnings.append(f"EC 使用构筑实际等级 Lv{gem_level}（MORE={raw_val:.0f}%），非满级 Lv20")

    # B2. Charge 数量标注
    for a in existing:
        if a.get("name") == "Charge Infusion" and a.get("simulated"):
            cc = a.get("charge_counts", {})
            if cc:
                parts = []
                for ct, val in cc.items():
                    if val != 3:
                        parts.append(f"{ct}={val}")
                if parts:
                    warnings.append(f"Charge Infusion 使用非默认 Charge 数量: {', '.join(parts)}")

    # B3. 空结果归因检查
    for c in candidates:
        if c.get("dps_pct", 0) <= 0.1:
            name = c.get("name", "?")
            if name == "Berserk":
                warnings.append(f"{name} 无 DPS 影响：可能因为构筑已通过其他方式获得 Rage 效果")
            elif name == "Attrition":
                warnings.append(f"{name} 无 DPS 影响：需要命中敌人才能叠加 Wither，纯模拟可能无法体现")

    # B4. 精魄辅助无影响检查
    ss_tests = aura_data.get("spirit_support_tests", [])
    zero_ss = [s for s in ss_tests if s.get("dps_pct", 0) <= 0.1]
    if len(zero_ss) == len(ss_tests) and len(ss_tests) > 0:
        warnings.append("所有精魄辅助测试均无 DPS 影响：可能是法术构筑（Direstrike/Precision 对攻击构筑无效）")

    return warnings


def format_report(data: dict) -> str:
    """将 full_analysis() 返回的数据格式化为 Markdown 表格报告。

    所有详细来源均以表格形式展示，提高可读性。

    Args:
        data: full_analysis() 的返回值

    Returns:
        完整的 Markdown 格式报告字符串
    """
    lines = []

    baseline = data.get("baseline", {})
    main_skill = data.get("main_skill", {})
    skill_flags = data.get("skill_flags", {})
    sensitivity = data.get("sensitivity", [])
    talent_value = data.get("talent_value", [])
    talent_exploration = data.get("talent_exploration", [])
    jewel_diag = data.get("jewel_diagnosis", [])
    dps_bd = data.get("dps_breakdown", {})

    skill_name = main_skill.get("name", "未知")
    total_dps = baseline.get("TotalDPS", 0)
    avg_hit = baseline.get("AverageHit", 0)
    speed = baseline.get("Speed", 0)
    crit_chance = baseline.get("CritChance", 0)
    crit_multi = baseline.get("CritMultiplier", 0)
    total_ehp = baseline.get("TotalEHP", 0)

    # --- 标题 ---
    lines.append(f"# {skill_name} 构筑 DPS 优化报告")
    lines.append("")

    # --- Section 1: 基线概览 ---
    lines.append("## 1. 基线概览")
    lines.append("")
    lines.append("| 指标 | 数值 |")
    lines.append("|------|------|")
    lines.append(f"| 主技能 | {skill_name} |")

    flag_tags = []
    if skill_flags.get("is_spell"):
        flag_tags.append("法术")
    if skill_flags.get("is_attack"):
        flag_tags.append("攻击")
    if skill_flags.get("is_projectile"):
        flag_tags.append("投射物")
    if skill_flags.get("is_dot"):
        flag_tags.append("DOT")
    if flag_tags:
        lines.append(f"| 技能类型 | {', '.join(flag_tags)} |")

    lines.append(f"| TotalDPS | **{total_dps:,.0f}** |")
    lines.append(f"| AverageHit | {avg_hit:,.0f} |")
    lines.append(f"| Speed | {speed:.2f}/s |")
    if crit_chance:
        lines.append(f"| CritChance | {crit_chance:.1f}% |")
    if crit_multi:
        lines.append(f"| CritMultiplier | {crit_multi:.2f}x |")
    lines.append(f"| TotalEHP | {total_ehp:,.0f} |")
    lines.append("")

    # --- Section 2: DPS 来源拆解 ---
    lines.append("## 2. DPS 来源拆解")
    lines.append("")

    formula_items = dps_bd.get("formula_items", [])
    active_types = dps_bd.get("active_damage_types", [])
    if active_types:
        lines.append(f"活跃伤害类型: {', '.join(active_types)}")
        lines.append("")

    for fi in formula_items:
        fname = fi["formula_name"]
        dval = fi["display_value"]
        lines.append(f"### {fname} = {dval}")
        lines.append("")

        # 公式详情（如 effMult 的计算过程）
        formula_detail = fi.get("formula_detail", "")
        if formula_detail:
            lines.append(f"**公式**: `{formula_detail}`")
            lines.append("")

        # 类别汇总
        cat_sum = fi.get("category_summary", {})
        if cat_sum:
            lines.append("**类别汇总**: " + " | ".join(
                f"{cat}: {val:+.1f}" for cat, val in
                sorted(cat_sum.items(), key=lambda x: abs(x[1]), reverse=True)
            ))
            lines.append("")

        # 详细来源表格
        sources = fi.get("sources", [])
        if sources:
            lines.append("| 来源 | 类别 | 值 |")
            lines.append("|------|------|-----|")
            for s in sources:
                label = s.get("label", s.get("source", "?"))
                cat = s.get("category", "?")
                val = s.get("value", 0)
                detail = s.get("detail", "")
                # 大数值用逗号分隔
                if abs(val) >= 1000:
                    val_disp = f"{val:+,.0f}"
                else:
                    val_disp = f"{val:+.1f}"
                if detail:
                    val_str = f"{val_disp} ({detail})"
                else:
                    val_str = val_disp
                lines.append(f"| {label} | {cat} | {val_str} |")
            lines.append("")

    # --- Section 3: 灵敏度分析 ---
    lines.append("## 3. 灵敏度分析")
    lines.append("")

    effective = [s for s in sensitivity if s.get("needed_value") is not None]
    unreachable = [s for s in sensitivity if s.get("needed_value") is None]

    if effective:
        lines.append("### 有效维度（按性价比排序）")
        lines.append("")
        lines.append("| # | 维度 | 类型 | 所需值 | 单位 | DPS/单位 | 当前值 | 公式 |")
        lines.append("|---|------|------|--------|------|----------|--------|------|")
        for i, s in enumerate(effective, 1):
            key = s.get("key", "?")
            mod_type = s.get("mod_type", "?")
            needed = s.get("needed_value", 0)
            unit = s.get("unit", "")
            dpu = s.get("dps_per_unit", 0)
            cur = s.get("current_total", 0)
            formula = s.get("formula", "")
            lines.append(
                f"| {i} | {key} | {mod_type} | "
                f"{needed:+.1f}{unit} | {unit} | "
                f"{dpu:.2f}%/{unit if unit else '1'} | "
                f"{cur:.0f} | {formula} |"
            )
        lines.append("")

    if unreachable:
        lines.append("### 无影响维度")
        lines.append("")
        lines.append("| 维度 | 类型 | 说明 |")
        lines.append("|------|------|------|")
        for s in unreachable:
            key = s.get("key", "?")
            mod_type = s.get("mod_type", "?")
            desc = s.get("description", "无法达到目标")
            lines.append(f"| {key} | {mod_type} | {desc} |")
        lines.append("")

    # --- Section 4: 天赋价值 ---
    lines.append("## 4. 已分配天赋价值")
    lines.append("")

    dps_talents = [t for t in talent_value if abs(t.get("dps_pct", 0)) > 0.1]
    def_talents = [t for t in talent_value
                   if abs(t.get("dps_pct", 0)) <= 0.1 and abs(t.get("ehp_pct", 0)) > 0.1]
    zero_talents = [t for t in talent_value
                    if abs(t.get("dps_pct", 0)) <= 0.1 and abs(t.get("ehp_pct", 0)) <= 0.1]

    if dps_talents:
        lines.append("### DPS 影响天赋")
        lines.append("")
        lines.append("| # | 天赋 | 类型 | 移除后 DPS% | 移除后 EHP% | 分类 |")
        lines.append("|---|------|------|-------------|-------------|------|")
        for i, t in enumerate(dps_talents, 1):
            lines.append(
                f"| {i} | {t['name']} | {t['type']} | "
                f"{t['dps_pct']:+.1f}% | {t.get('ehp_pct', 0):+.1f}% | "
                f"{t['category']} |"
            )
        lines.append("")

    if def_talents:
        lines.append("### 纯防御天赋")
        lines.append("")
        lines.append("| 天赋 | 移除后 EHP% |")
        lines.append("|------|-------------|")
        for t in def_talents:
            lines.append(f"| {t['name']} | {t.get('ehp_pct', 0):+.1f}% |")
        lines.append("")

    if zero_talents:
        lines.append(f"### 无效天赋 ({len(zero_talents)} 个)")
        lines.append("")
        names = ", ".join(t["name"] for t in zero_talents)
        lines.append(f"{names}")
        lines.append("")

    # --- Section 5: 天赋探索 ---
    lines.append("## 5. 未分配天赋探索")
    lines.append("")

    if talent_exploration:
        top_n = 10
        shown = talent_exploration[:top_n]
        rest = len(talent_exploration) - len(shown)

        lines.append("| # | 天赋 | 类型 | DPS% | EHP% | 分类 |")
        lines.append("|---|------|------|------|------|------|")
        for i, t in enumerate(shown, 1):
            lines.append(
                f"| {i} | {t['name']} | {t['type']} | "
                f"{t['dps_pct']:+.1f}% | {t.get('ehp_pct', 0):+.1f}% | "
                f"{t['category']} |"
            )
        if rest > 0:
            lines.append("")
            lines.append(f"*（另有 {rest} 个候选天赋未显示）*")
        lines.append("")
    else:
        lines.append("无有意义的候选天赋。")
        lines.append("")

    # --- Section 6: 珠宝诊断 ---
    lines.append("## 6. 珠宝诊断")
    lines.append("")

    if jewel_diag:
        for j in jewel_diag:
            name = j.get("name", "?")
            base = j.get("base_type", "?")
            rarity = j.get("rarity", "?")
            dp = j.get("dps_pct", 0)
            status = j.get("status", "?")
            slot = j.get("slot_name", "")

            lines.append(f"### {name} ({base}, {rarity})")
            lines.append("")
            lines.append(f"- **DPS 贡献**: {dp:+.1f}% | **状态**: {status} | **槽位**: {slot}")

            # granted passives
            gp = j.get("granted_passives", [])
            if gp:
                gdp = j.get("granted_dps_pct", 0)
                lines.append(f"- **分配天赋**: {', '.join(gp)} (DPS {gdp:+.1f}%)")

            lines.append("")

            # mods 明细表
            mods = j.get("mods", [])
            if mods:
                lines.append("| Mod | 类型 | 值 | DPS% |")
                lines.append("|-----|------|-----|------|")
                for m in mods:
                    mname = m.get("name", "?")
                    mtype = m.get("type", "?")
                    mval = m.get("value", "?")
                    mdps = m.get("dps_pct")
                    # 跳过无意义的 Lua table 指针
                    if isinstance(mval, str) and mval.startswith("table:"):
                        mval = "(complex data)"
                    dps_str = f"{mdps:+.1f}%" if mdps is not None else "—"
                    lines.append(f"| {mname} | {mtype} | {mval} | {dps_str} |")
                lines.append("")

    else:
        lines.append("无珠宝。")
        lines.append("")

    # --- Section 7: 光环与精魄分析 ---
    aura_data = data.get("aura_spirit", {})
    bm = aura_data.get("build_modifiers", {})
    _format_section7(lines, aura_data, skill_flags, baseline,
                    build_modifiers=bm)

    # --- Section 8: 总结与建议 ---
    lines.append("## 8. 总结与建议")
    lines.append("")

    # 8a. 核心数据一句话
    lines.append(f"当前 **{skill_name}** TotalDPS = **{total_dps:,.0f}**，"
                 f"AverageHit = {avg_hit:,.0f}，Speed = {speed:.2f}/s，"
                 f"CritChance = {crit_chance:.1f}%，CritMultiplier = {crit_multi:.2f}x。")
    lines.append("")

    # 8b. 最高性价比优化方向（灵敏度 Top 3）
    effective_sens = [s for s in sensitivity if s.get("needed_value") is not None]
    if effective_sens:
        lines.append("### 🎯 最高性价比优化方向")
        lines.append("")
        for i, s in enumerate(effective_sens[:3], 1):
            key = s.get("key", "?")
            mod_type = s.get("mod_type", "?")
            needed = s.get("needed_value", 0)
            unit = s.get("unit", "")
            dpu = s.get("dps_per_unit", 0)
            cur = s.get("current_total", 0)
            lines.append(
                f"{i}. **{key}** ({mod_type}): "
                f"每 1{unit} 提升 {dpu:.2f}% DPS，"
                f"当前 {cur:.0f}，需要 +{needed:.0f}{unit} 达到 +20% DPS"
            )
        lines.append("")

    # 8c. 推荐点出的天赋（探索 Top 5）
    if talent_exploration:
        lines.append("### 🌳 推荐点出的天赋")
        lines.append("")
        for i, t in enumerate(talent_exploration[:5], 1):
            ehp_note = f"，EHP {t.get('ehp_pct', 0):+.1f}%" if abs(t.get('ehp_pct', 0)) > 0.1 else ""
            lines.append(f"{i}. **{t['name']}**: DPS {t['dps_pct']:+.1f}%{ehp_note}")
        lines.append("")

    # 8d. 低效天赋提醒
    if zero_talents:
        lines.append("### ⚠️ 低效天赋")
        lines.append("")
        lines.append(f"有 **{len(zero_talents)}** 个已分配天赋对 DPS 和 EHP 均无可测量影响，"
                     "可考虑重新规划路径或替换为高收益节点：")
        lines.append("")
        # 列出前 10 个，避免过长
        shown_zero = zero_talents[:10]
        lines.append(", ".join(f"**{t['name']}**" for t in shown_zero))
        if len(zero_talents) > 10:
            lines.append(f"  …及其他 {len(zero_talents) - 10} 个")
        lines.append("")

    # 8e. 珠宝优化建议
    if jewel_diag:
        low_dps_jewels = [j for j in jewel_diag
                          if abs(j.get("dps_pct", 0)) < 0.1 and j.get("status") == "ok"]
        high_dps_jewels = sorted(
            [j for j in jewel_diag if abs(j.get("dps_pct", 0)) >= 0.1],
            key=lambda j: j.get("dps_pct", 0),
            reverse=True,
        )
        if high_dps_jewels or low_dps_jewels:
            lines.append("### 💎 珠宝建议")
            lines.append("")
            if high_dps_jewels:
                best = high_dps_jewels[0]
                lines.append(f"- 当前 DPS 贡献最高的珠宝: **{best.get('name', '?')}** "
                             f"({best.get('dps_pct', 0):+.1f}%)")
            if low_dps_jewels:
                names = ", ".join(f"**{j.get('name', '?')}**" for j in low_dps_jewels)
                lines.append(f"- 无 DPS 贡献的珠宝: {names}，可考虑替换为伤害珠宝")
            lines.append("")

    # 8f. 敌人抗性/穿透提醒
    unreachable_sens = [s for s in sensitivity if s.get("needed_value") is None]
    pen_unreachable = [s for s in unreachable_sens if "pen" in s.get("key", "")]
    if pen_unreachable:
        lines.append("### 🛡️ 敌人抗性说明")
        lines.append("")
        lines.append("所有穿透维度均无影响 — 当前构筑配置下敌人抗性已为负值或零值，"
                     "穿透无法进一步降低负抗。如果面对高抗性 Boss（抗性 > 0），"
                     "穿透会成为有效优化维度。")
        lines.append("")

    return "\n".join(lines)
