#!/usr/bin/env python3
"""
机制提取器 v2
从 ModCache.lua 中提取 stat 映射，建立机制节点。
从 CalcOffence/CalcDefence/CalcTriggers 中提取行为描述。

核心原理：
- 机制通过 stat ID/internal stat name 识别，而不是描述
- 例如: "InstantLifeLeech" 是机制标识符
- 描述 "Leech from Critical Hits is instant" 只是显示文本

v2 新增：
- friendly_name: 中文友好名称
- behavior_description: 从 POB 代码逆向提炼的行为描述
- mechanism_category: 机制分类（8 种枚举）
- formula_abstract: 抽象公式（有计算逻辑的机制）
- affected_stats: 影响/被影响的 stat 列表
- mechanism_relations 表: 机制间关系
- 行为提取: Flag/Numeric/Trigger 三型策略
"""

import re
import json
import sqlite3
import yaml
from pathlib import Path
from typing import Dict, List, Set, Any, Optional, Tuple
from collections import defaultdict

# 尝试导入 Lua 解析器
try:
    from lua_parser import LuaParser
    HAS_LUA_PARSER = True  # 默认使用 Lua 解析器
except ImportError:
    HAS_LUA_PARSER = False


# ============================================================
# 机制分类枚举
# ============================================================
MECHANISM_CATEGORIES = {
    'leech',             # 偷取类（即时偷取、偷取转换）
    'conversion',        # 转换类（伤害类型转换、承受转换）
    'immunity',          # 免疫类（异常免疫、无法被X）
    'trigger',           # 触发类（暴击施放、受伤施放等）
    'resource',          # 资源类（回复转移、资源转换）
    'damage_modifier',   # 伤害修饰类（忽略抗性、穿透护甲）
    'block',             # 格挡类（无法格挡、格挡转换）
    'suppress',          # 压制类（法术压制）
    'aggregation',       # 聚合类（Sum/More/Flag/Override — Modifier引擎核心语义）
}


# ============================================================
# 44 个机制完整定义
# ============================================================
KNOWN_MECHANISMS: Dict[str, Dict[str, Any]] = {
    # === 偷取类 (leech) ===
    'InstantLifeLeech': {
        'friendly_name': '即时生命偷取',
        'category': 'leech',
        'behavior_type': 'numeric',  # Sum("BASE") 类型
        'formula_abstract': '即时恢复 = 总偷取量 × min(max(InstantLifeLeech%, 0), 100) / 100',
        'affected_stats': ['LifeLeech', 'LifeLeechInstant', 'LifeLeechInstantProportion'],
        'code_refs': [
            {'file': 'CalcOffence.lua', 'line': 3994, 'pattern': 'Sum("BASE", cfg, "InstantLifeLeech")'}
        ],
    },
    'InstantManaLeech': {
        'friendly_name': '即时魔力偷取',
        'category': 'leech',
        'behavior_type': 'numeric',
        'formula_abstract': '即时恢复 = 总偷取量 × min(max(InstantManaLeech%, 0), 100) / 100',
        'affected_stats': ['ManaLeech', 'ManaLeechInstant', 'ManaLeechInstantProportion'],
        'code_refs': [
            {'file': 'CalcOffence.lua', 'line': 3999, 'pattern': 'Sum("BASE", cfg, "InstantManaLeech")'}
        ],
    },
    'InstantEnergyShieldLeech': {
        'friendly_name': '即时能量护盾偷取',
        'category': 'leech',
        'behavior_type': 'numeric',
        'formula_abstract': '即时恢复 = 总偷取量 × min(max(InstantEnergyShieldLeech%, 0), 100) / 100',
        'affected_stats': ['EnergyShieldLeech', 'EnergyShieldLeechInstant', 'EnergyShieldLeechInstantProportion'],
        'code_refs': [
            {'file': 'CalcOffence.lua', 'line': 4004, 'pattern': 'Sum("BASE", cfg, "InstantEnergyShieldLeech")'}
        ],
    },
    'CanLeechLifeOnFullLife': {
        'friendly_name': '满血时保留生命偷取',
        'category': 'leech',
        'behavior_type': 'flag',
        'formula_abstract': None,
        'affected_stats': ['LifeLeech', 'LifeLeechRate'],
        'code_refs': [
            {'file': 'CalcPerform.lua', 'line': 654, 'pattern': 'Flag(nil, "CanLeechLifeOnFullLife")'}
        ],
    },
    'GhostReaver': {
        'friendly_name': '幽魂掠夺',
        'category': 'leech',
        'behavior_type': 'flag',
        'formula_abstract': 'ES偷取 += 生命偷取（GhostReaver 激活时，所有生命偷取转为 ES 偷取）',
        'affected_stats': ['LifeLeech', 'EnergyShieldLeech', 'MaxEnergyShieldLeechRate'],
        'code_refs': [
            {'file': 'CalcOffence.lua', 'line': 3636, 'pattern': 'Flag(nil, "GhostReaver")'},
            {'file': 'CalcOffence.lua', 'line': 3901, 'pattern': 'energyShieldLeech = energyShieldLeech + lifeLeech'},
        ],
    },

    # === 免疫类 (immunity) ===
    'CannotBeIgnited': {
        'friendly_name': '免疫点燃',
        'category': 'immunity',
        'behavior_type': 'flag',
        'formula_abstract': None,
        'affected_stats': ['IgniteAvoidChance', 'IgniteDuration'],
        'code_refs': [
            {'file': 'CalcDefence.lua', 'line': 1938, 'pattern': '{Ailment}Immune (动态拼接)'}
        ],
    },
    'CannotBeFrozen': {
        'friendly_name': '免疫冰冻',
        'category': 'immunity',
        'behavior_type': 'flag',
        'formula_abstract': None,
        'affected_stats': ['FreezeAvoidChance', 'FreezeDuration'],
        'code_refs': [
            {'file': 'CalcDefence.lua', 'line': 1938, 'pattern': '{Ailment}Immune (动态拼接)'}
        ],
    },
    'CannotBeShocked': {
        'friendly_name': '免疫感电',
        'category': 'immunity',
        'behavior_type': 'flag',
        'formula_abstract': None,
        'affected_stats': ['ShockAvoidChance', 'ShockDuration'],
        'code_refs': [
            {'file': 'CalcDefence.lua', 'line': 1938, 'pattern': '{Ailment}Immune (动态拼接)'}
        ],
    },
    'CannotBePoisoned': {
        'friendly_name': '免疫中毒',
        'category': 'immunity',
        'behavior_type': 'flag',
        'formula_abstract': None,
        'affected_stats': ['PoisonAvoidChance', 'PoisonDuration'],
        'code_refs': [
            {'file': 'CalcDefence.lua', 'line': 1934, 'pattern': '{Ailment}Immune (动态拼接)'}
        ],
    },
    'CannotBeBled': {
        'friendly_name': '免疫流血',
        'category': 'immunity',
        'behavior_type': 'flag',
        'formula_abstract': None,
        'affected_stats': ['BleedAvoidChance', 'BleedDuration'],
        'code_refs': [
            {'file': 'CalcDefence.lua', 'line': 1934, 'pattern': '{Ailment}Immune (动态拼接)'}
        ],
    },
    'CannotBeStunned': {
        'friendly_name': '免疫晕眩',
        'category': 'immunity',
        'behavior_type': 'flag',
        'formula_abstract': None,
        'affected_stats': ['StunAvoidChance', 'StunThreshold'],
        'code_refs': [
            {'file': 'CalcDefence.lua', 'line': 1934, 'pattern': '{Ailment}Immune (动态拼接)'}
        ],
    },
    'CannotBeEvaded': {
        'friendly_name': '命中必中',
        'category': 'damage_modifier',
        'behavior_type': 'flag',
        'formula_abstract': '命中率 = 100%（跳过闪避检定）',
        'affected_stats': ['HitChance', 'Accuracy', 'Evasion'],
        'code_refs': [
            {'file': 'CalcOffence.lua', 'line': 2471, 'pattern': 'Flag(cfg, "CannotBeEvaded")'},
            {'file': 'CalcDefence.lua', 'line': 1391, 'pattern': 'enemyDB:Flag(nil, "CannotBeEvaded")'},
        ],
    },

    # === 伤害转换类 (conversion) ===
    'PhysicalDamageConvertToFire': {
        'friendly_name': '物理伤害转换为火焰',
        'category': 'conversion',
        'behavior_type': 'numeric',
        'formula_abstract': '火焰伤害 += 物理基础 × PhysicalDamageConvertToFire% / 100（总转换不超过100%）',
        'affected_stats': ['PhysicalDamage', 'FireDamage', 'DamageConversion'],
        'code_refs': [
            {'file': 'CalcOffence.lua', 'line': 1133, 'pattern': 'PhysicalDamageConvertToFire'}
        ],
    },
    'PhysicalDamageConvertToCold': {
        'friendly_name': '物理伤害转换为冰霜',
        'category': 'conversion',
        'behavior_type': 'numeric',
        'formula_abstract': '冰霜伤害 += 物理基础 × PhysicalDamageConvertToCold% / 100（总转换不超过100%）',
        'affected_stats': ['PhysicalDamage', 'ColdDamage', 'DamageConversion'],
        'code_refs': [
            {'file': 'CalcOffence.lua', 'line': 1133, 'pattern': 'PhysicalDamageConvertToCold'}
        ],
    },
    'PhysicalDamageConvertToLightning': {
        'friendly_name': '物理伤害转换为闪电',
        'category': 'conversion',
        'behavior_type': 'numeric',
        'formula_abstract': '闪电伤害 += 物理基础 × PhysicalDamageConvertToLightning% / 100（总转换不超过100%）',
        'affected_stats': ['PhysicalDamage', 'LightningDamage', 'DamageConversion'],
        'code_refs': [
            {'file': 'CalcOffence.lua', 'line': 1133, 'pattern': 'PhysicalDamageConvertToLightning'}
        ],
    },
    'PhysicalDamageConvertToChaos': {
        'friendly_name': '物理伤害转换为混沌',
        'category': 'conversion',
        'behavior_type': 'numeric',
        'formula_abstract': '混沌伤害 += 物理基础 × PhysicalDamageConvertToChaos% / 100（总转换不超过100%）',
        'affected_stats': ['PhysicalDamage', 'ChaosDamage', 'DamageConversion'],
        'code_refs': [
            {'file': 'CalcOffence.lua', 'line': 1133, 'pattern': 'PhysicalDamageConvertToChaos'}
        ],
    },
    'ColdDamageConvertToFire': {
        'friendly_name': '冰霜伤害转换为火焰',
        'category': 'conversion',
        'behavior_type': 'numeric',
        'formula_abstract': '火焰伤害 += 冰霜基础 × ColdDamageConvertToFire% / 100（总转换不超过100%）',
        'affected_stats': ['ColdDamage', 'FireDamage', 'DamageConversion'],
        'code_refs': [
            {'file': 'CalcOffence.lua', 'line': 1133, 'pattern': 'ColdDamageConvertToFire'}
        ],
    },
    'LightningDamageConvertToFire': {
        'friendly_name': '闪电伤害转换为火焰',
        'category': 'conversion',
        'behavior_type': 'numeric',
        'formula_abstract': '火焰伤害 += 闪电基础 × LightningDamageConvertToFire% / 100（总转换不超过100%）',
        'affected_stats': ['LightningDamage', 'FireDamage', 'DamageConversion'],
        'code_refs': [
            {'file': 'CalcOffence.lua', 'line': 1133, 'pattern': 'LightningDamageConvertToFire'}
        ],
    },
    'LightningDamageConvertToCold': {
        'friendly_name': '闪电伤害转换为冰霜',
        'category': 'conversion',
        'behavior_type': 'numeric',
        'formula_abstract': '冰霜伤害 += 闪电基础 × LightningDamageConvertToCold% / 100（总转换不超过100%）',
        'affected_stats': ['LightningDamage', 'ColdDamage', 'DamageConversion'],
        'code_refs': [
            {'file': 'CalcOffence.lua', 'line': 1133, 'pattern': 'LightningDamageConvertToCold'}
        ],
    },
    'FireDamageConvertToChaos': {
        'friendly_name': '火焰伤害转换为混沌',
        'category': 'conversion',
        'behavior_type': 'numeric',
        'formula_abstract': '混沌伤害 += 火焰基础 × FireDamageConvertToChaos% / 100（总转换不超过100%）',
        'affected_stats': ['FireDamage', 'ChaosDamage', 'DamageConversion'],
        'code_refs': [
            {'file': 'CalcOffence.lua', 'line': 1133, 'pattern': 'FireDamageConvertToChaos'}
        ],
    },
    'ColdDamageConvertToChaos': {
        'friendly_name': '冰霜伤害转换为混沌',
        'category': 'conversion',
        'behavior_type': 'numeric',
        'formula_abstract': '混沌伤害 += 冰霜基础 × ColdDamageConvertToChaos% / 100（总转换不超过100%）',
        'affected_stats': ['ColdDamage', 'ChaosDamage', 'DamageConversion'],
        'code_refs': [
            {'file': 'CalcOffence.lua', 'line': 1133, 'pattern': 'ColdDamageConvertToChaos'}
        ],
    },
    'LightningDamageConvertToChaos': {
        'friendly_name': '闪电伤害转换为混沌',
        'category': 'conversion',
        'behavior_type': 'numeric',
        'formula_abstract': '混沌伤害 += 闪电基础 × LightningDamageConvertToChaos% / 100（总转换不超过100%）',
        'affected_stats': ['LightningDamage', 'ChaosDamage', 'DamageConversion'],
        'code_refs': [
            {'file': 'CalcOffence.lua', 'line': 1133, 'pattern': 'LightningDamageConvertToChaos'}
        ],
    },

    # === 承受转换类 (conversion) ===
    'PhysicalDamageFromHitsTakenAsLightning': {
        'friendly_name': '物理承受转为闪电',
        'category': 'conversion',
        'behavior_type': 'numeric',
        'formula_abstract': '闪电承受 += 物理命中伤害 × 转换% / 100',
        'affected_stats': ['PhysicalDamageTaken', 'LightningDamageTaken', 'DamageShift'],
        'code_refs': [
            {'file': 'CalcDefence.lua', 'line': 357, 'pattern': 'sourceType.."DamageFromHitsTakenAs"..damageType'}
        ],
    },
    'PhysicalDamageFromHitsTakenAsFire': {
        'friendly_name': '物理承受转为火焰',
        'category': 'conversion',
        'behavior_type': 'numeric',
        'formula_abstract': '火焰承受 += 物理命中伤害 × 转换% / 100',
        'affected_stats': ['PhysicalDamageTaken', 'FireDamageTaken', 'DamageShift'],
        'code_refs': [
            {'file': 'CalcDefence.lua', 'line': 357, 'pattern': 'sourceType.."DamageFromHitsTakenAs"..damageType'}
        ],
    },
    'PhysicalDamageFromHitsTakenAsCold': {
        'friendly_name': '物理承受转为冰霜',
        'category': 'conversion',
        'behavior_type': 'numeric',
        'formula_abstract': '冰霜承受 += 物理命中伤害 × 转换% / 100',
        'affected_stats': ['PhysicalDamageTaken', 'ColdDamageTaken', 'DamageShift'],
        'code_refs': [
            {'file': 'CalcDefence.lua', 'line': 357, 'pattern': 'sourceType.."DamageFromHitsTakenAs"..damageType'}
        ],
    },
    'PhysicalDamageFromHitsTakenAsChaos': {
        'friendly_name': '物理承受转为混沌',
        'category': 'conversion',
        'behavior_type': 'numeric',
        'formula_abstract': '混沌承受 += 物理命中伤害 × 转换% / 100',
        'affected_stats': ['PhysicalDamageTaken', 'ChaosDamageTaken', 'DamageShift'],
        'code_refs': [
            {'file': 'CalcDefence.lua', 'line': 357, 'pattern': 'sourceType.."DamageFromHitsTakenAs"..damageType'}
        ],
    },
    'LightningDamageTakenAsFire': {
        'friendly_name': '闪电承受转为火焰',
        'category': 'conversion',
        'behavior_type': 'numeric',
        'formula_abstract': '火焰承受 += 闪电伤害 × 转换% / 100',
        'affected_stats': ['LightningDamageTaken', 'FireDamageTaken', 'DamageShift'],
        'code_refs': [
            {'file': 'CalcDefence.lua', 'line': 357, 'pattern': 'sourceType.."DamageTakenAs"..damageType'}
        ],
    },
    'LightningDamageTakenAsCold': {
        'friendly_name': '闪电承受转为冰霜',
        'category': 'conversion',
        'behavior_type': 'numeric',
        'formula_abstract': '冰霜承受 += 闪电伤害 × 转换% / 100',
        'affected_stats': ['LightningDamageTaken', 'ColdDamageTaken', 'DamageShift'],
        'code_refs': [
            {'file': 'CalcDefence.lua', 'line': 357, 'pattern': 'sourceType.."DamageTakenAs"..damageType'}
        ],
    },
    'FireDamageTakenAsChaos': {
        'friendly_name': '火焰承受转为混沌',
        'category': 'conversion',
        'behavior_type': 'numeric',
        'formula_abstract': '混沌承受 += 火焰伤害 × 转换% / 100',
        'affected_stats': ['FireDamageTaken', 'ChaosDamageTaken', 'DamageShift'],
        'code_refs': [
            {'file': 'CalcDefence.lua', 'line': 357, 'pattern': 'sourceType.."DamageTakenAs"..damageType'}
        ],
    },
    'ColdDamageTakenAsFire': {
        'friendly_name': '冰霜承受转为火焰',
        'category': 'conversion',
        'behavior_type': 'numeric',
        'formula_abstract': '火焰承受 += 冰霜伤害 × 转换% / 100',
        'affected_stats': ['ColdDamageTaken', 'FireDamageTaken', 'DamageShift'],
        'code_refs': [
            {'file': 'CalcDefence.lua', 'line': 357, 'pattern': 'sourceType.."DamageTakenAs"..damageType'}
        ],
    },
    'ChaosDamageTakenAsFire': {
        'friendly_name': '混沌承受转为火焰',
        'category': 'conversion',
        'behavior_type': 'numeric',
        'formula_abstract': '火焰承受 += 混沌伤害 × 转换% / 100',
        'affected_stats': ['ChaosDamageTaken', 'FireDamageTaken', 'DamageShift'],
        'code_refs': [
            {'file': 'CalcDefence.lua', 'line': 357, 'pattern': 'sourceType.."DamageTakenAs"..damageType'}
        ],
    },
    'ChaosDamageTakenAsCold': {
        'friendly_name': '混沌承受转为冰霜',
        'category': 'conversion',
        'behavior_type': 'numeric',
        'formula_abstract': '冰霜承受 += 混沌伤害 × 转换% / 100',
        'affected_stats': ['ChaosDamageTaken', 'ColdDamageTaken', 'DamageShift'],
        'code_refs': [
            {'file': 'CalcDefence.lua', 'line': 357, 'pattern': 'sourceType.."DamageTakenAs"..damageType'}
        ],
    },
    'ChaosDamageTakenAsLightning': {
        'friendly_name': '混沌承受转为闪电',
        'category': 'conversion',
        'behavior_type': 'numeric',
        'formula_abstract': '闪电承受 += 混沌伤害 × 转换% / 100',
        'affected_stats': ['ChaosDamageTaken', 'LightningDamageTaken', 'DamageShift'],
        'code_refs': [
            {'file': 'CalcDefence.lua', 'line': 357, 'pattern': 'sourceType.."DamageTakenAs"..damageType'}
        ],
    },

    # === 资源类 (resource) ===
    'ZealotsOath': {
        'friendly_name': '狂热誓言',
        'category': 'resource',
        'behavior_type': 'flag',
        'formula_abstract': 'ES回复 += 生命回复（当 ZealotsOath 激活且生命回复 > 0 时，生命回复转为 ES 回复）',
        'affected_stats': ['LifeRegen', 'EnergyShieldRegen', 'LifeRegenRecovery'],
        'code_refs': [
            {'file': 'CalcDefence.lua', 'line': 1648, 'pattern': 'Flag(nil, "ZealotsOath")'},
            {'file': 'CalcDefence.lua', 'line': 1680, 'pattern': 'ZealotsOath breakdown'},
        ],
    },
    'LifeConvertToEnergyShield': {
        'friendly_name': '生命转换为能量护盾',
        'category': 'resource',
        'behavior_type': 'numeric',
        'formula_abstract': 'ES基础 += 生命基础 × LifeConvertToEnergyShield% / 100',
        'affected_stats': ['Life', 'EnergyShield', 'LifeConversion'],
        'code_refs': [
            {'file': 'CalcPerform.lua', 'line': 954, 'pattern': 'NewMod("LifeConvertToEnergyShield", "BASE", ...)'}
        ],
    },
    'ChaosInoculation': {
        'friendly_name': '混沌无伤',
        'category': 'resource',
        'behavior_type': 'flag',
        'formula_abstract': '最大生命 = 1, 混沌抗性 = 100%',
        'affected_stats': ['Life', 'ChaosResist', 'MaxLife'],
        'code_refs': [
            {'file': 'CalcDefence.lua', 'line': 83, 'pattern': 'Flag(nil, "ChaosInoculation")'}
        ],
    },
    'EnergyShieldProtectsMana': {
        'friendly_name': '能量护盾保护魔力',
        'category': 'resource',
        'behavior_type': 'flag',
        'formula_abstract': 'ES 优先吸收本应从魔力扣除的伤害（灵能之血）',
        'affected_stats': ['EnergyShield', 'Mana', 'ManaUnreserved'],
        'code_refs': [
            {'file': 'CalcOffence.lua', 'line': 5614, 'pattern': 'Flag(nil, "EnergyShieldProtectsMana")'}
        ],
    },

    # === 伤害修饰类 (damage_modifier) ===
    'IgnoreEnemyArmour': {
        'friendly_name': '忽略敌人护甲',
        'category': 'damage_modifier',
        'behavior_type': 'flag',
        'formula_abstract': '物理伤害减免 = 0（跳过敌人护甲检定）',
        'affected_stats': ['Armour', 'PhysicalDamageReduction', 'PhysicalDamage'],
        'code_refs': [
            {'file': 'CalcOffence.lua', 'line': 3737, 'pattern': 'Flag(cfg, "IgnoreEnemyArmour")'}
        ],
    },
    'IronReflexes': {
        'friendly_name': '钢铁反射',
        'category': 'damage_modifier',
        'behavior_type': 'flag',
        'formula_abstract': '护甲 += 闪避值（所有闪避值转为护甲）',
        'affected_stats': ['Armour', 'Evasion'],
        'code_refs': [
            {'file': 'CalcDefence.lua', 'line': 800, 'pattern': 'Flag(nil, "IronReflexes")'}
        ],
    },

    # === 格挡类 (block) ===
    'CannotBlockAttacks': {
        'friendly_name': '无法格挡攻击',
        'category': 'block',
        'behavior_type': 'flag',
        'formula_abstract': '攻击格挡几率 = 0',
        'affected_stats': ['BlockChance', 'AttackBlockChance'],
        'code_refs': [
            {'file': 'CalcDefence.lua', 'line': 1017, 'pattern': 'Flag(nil, "CannotBlockAttacks")'}
        ],
    },
    'CannotBlockSpells': {
        'friendly_name': '无法格挡法术',
        'category': 'block',
        'behavior_type': 'flag',
        'formula_abstract': '法术格挡几率 = 0',
        'affected_stats': ['SpellBlockChance'],
        'code_refs': [
            {'file': 'CalcDefence.lua', 'line': 1021, 'pattern': 'Flag(nil, "CannotBlockSpells")'}
        ],
    },
    'SpellBlockChanceIsBlockChance': {
        'friendly_name': '法术格挡等同攻击格挡',
        'category': 'block',
        'behavior_type': 'flag',
        'formula_abstract': '法术格挡几率 = 攻击格挡几率',
        'affected_stats': ['SpellBlockChance', 'BlockChance'],
        'code_refs': [
            {'file': 'CalcDefence.lua', 'line': 996, 'pattern': 'Flag(nil, "SpellBlockChanceIsBlockChance")'}
        ],
    },

    # === 触发类 (trigger) ===
    'CastOnCriticalStrike': {
        'friendly_name': '暴击施放',
        'category': 'trigger',
        'behavior_type': 'trigger',
        'formula_abstract': '触发冷却 = 技能冷却 / (1 + 冷却恢复速度%); 触发条件 = 暴击命中',
        'affected_stats': ['TriggerRate', 'CritChance', 'CooldownRecovery'],
        'code_refs': [
            {'file': 'CalcTriggers.lua', 'line': 1089, 'pattern': 'configTable["cast on critical strike"]'}
        ],
    },
    'CastWhenDamageTaken': {
        'friendly_name': '受伤施放',
        'category': 'trigger',
        'behavior_type': 'trigger',
        'formula_abstract': '触发条件 = 累计受伤达到阈值; 阈值 = 宝石等级决定的伤害值',
        'affected_stats': ['TriggerRate', 'DamageTaken', 'CooldownRecovery'],
        'code_refs': [
            {'file': 'CalcTriggers.lua', 'line': 1113, 'pattern': 'configTable["cast when damage taken"]'}
        ],
    },
    'CastWhileChannelling': {
        'friendly_name': '引导施放',
        'category': 'trigger',
        'behavior_type': 'trigger',
        'formula_abstract': '触发间隔 = 引导技能施法间隔; 触发条件 = 引导中',
        'affected_stats': ['TriggerRate', 'CastSpeed', 'CooldownRecovery'],
        'code_refs': [
            {'file': 'CalcTriggers.lua', 'line': 1295, 'pattern': 'configTable["cast while channelling"]'}
        ],
    },
    'Spellslinger': {
        'friendly_name': '法术弹幕',
        'category': 'trigger',
        'behavior_type': 'trigger',
        'formula_abstract': '触发条件 = 使用法杖攻击; 触发率 = 攻击率（受冷却限制）',
        'affected_stats': ['TriggerRate', 'AttackSpeed', 'CooldownRecovery', 'ManaReservation'],
        'code_refs': [
            {'file': 'CalcTriggers.lua', 'line': 1153, 'pattern': 'configTable["spellslinger"]'}
        ],
    },

    # === Modifier聚合类 (aggregation) — 来自 Classes/ModStore.lua ===
    'ModStore_Sum': {
        'friendly_name': 'Modifier聚合: Sum (加法叠加)',
        'category': 'aggregation',
        'behavior_type': 'numeric',
        'formula_abstract': 'Sum(type, cfg, ...) = Σ(mod.value) for all mods matching (name, type, flags). type=BASE时为基础值叠加, type=INC时为increased/reduced百分比叠加',
        'affected_stats': ['*'],  # 适用于所有stat
        'code_refs': [
            {'file': 'Classes/ModStore.lua', 'line': 129, 'pattern': 'function ModStoreClass:Sum(modType, cfg, ...)'}
        ],
    },
    'ModStore_More': {
        'friendly_name': 'Modifier聚合: More (乘法独立)',
        'category': 'aggregation',
        'behavior_type': 'numeric',
        'formula_abstract': 'More(cfg, ...) = Π(1 + mod.value/100) for all MORE-type mods. 每个more/less独立乘算, 不同来源不叠加',
        'affected_stats': ['*'],
        'code_refs': [
            {'file': 'Classes/ModStore.lua', 'line': 158, 'pattern': 'function ModStoreClass:More(cfg, ...)'}
        ],
    },
    'ModStore_Flag': {
        'friendly_name': 'Modifier聚合: Flag (布尔标记)',
        'category': 'aggregation',
        'behavior_type': 'flag',
        'formula_abstract': 'Flag(cfg, ...) = true if any mod with matching name exists and EvalMod passes. 用于开关型机制(如CannotBeEvaded, GhostReaver)',
        'affected_stats': ['*'],
        'code_refs': [
            {'file': 'Classes/ModStore.lua', 'line': 169, 'pattern': 'function ModStoreClass:Flag(cfg, ...)'}
        ],
    },
    'ModStore_Override': {
        'friendly_name': 'Modifier聚合: Override (覆盖)',
        'category': 'aggregation',
        'behavior_type': 'numeric',
        'formula_abstract': 'Override(cfg, ...) = mod.value of first matching OVERRIDE-type mod. 直接覆盖计算结果, 优先级最高',
        'affected_stats': ['*'],
        'code_refs': [
            {'file': 'Classes/ModStore.lua', 'line': 180, 'pattern': 'function ModStoreClass:Override(cfg, ...)'}
        ],
    },
    'ModStore_EvalMod': {
        'friendly_name': 'Modifier求值: EvalMod (条件评估)',
        'category': 'aggregation',
        'behavior_type': 'numeric',
        'formula_abstract': 'EvalMod(mod, cfg) 评估modifier的条件标签(Condition/Multiplier/PerStat/PercentStat/MultiplierThreshold/ActorCondition/SocketedIn/InSlot). 返回(pass, value)对',
        'affected_stats': ['*'],
        'code_refs': [
            {'file': 'Classes/ModStore.lua', 'line': 304, 'pattern': 'function ModStoreClass:EvalMod(mod, cfg, ...)'}
        ],
    },
}

# 关系定义
MECHANISM_RELATIONS: List[Dict[str, str]] = [
    # 偷取系统内部关系
    {
        'mechanism_a': 'GhostReaver',
        'mechanism_b': 'InstantLifeLeech',
        'relation_type': 'converts',
        'direction': 'a_to_b',
        'description': 'GhostReaver 将所有生命偷取转为 ES 偷取，包括即时偷取部分',
    },
    {
        'mechanism_a': 'GhostReaver',
        'mechanism_b': 'InstantEnergyShieldLeech',
        'relation_type': 'modifies',
        'direction': 'a_to_b',
        'description': 'GhostReaver 激活后，原生命偷取的即时比例转移到 ES 即时偷取',
    },
    {
        'mechanism_a': 'GhostReaver',
        'mechanism_b': 'CanLeechLifeOnFullLife',
        'relation_type': 'modifies',
        'direction': 'a_to_b',
        'description': '当 GhostReaver 未激活时，CanLeechLifeOnFullLife 允许满血继续偷取',
    },

    # 资源转换关系
    {
        'mechanism_a': 'ZealotsOath',
        'mechanism_b': 'ChaosInoculation',
        'relation_type': 'stacks_with',
        'direction': 'both',
        'description': 'ZealotsOath + CI = 生命回复转为 ES 回复（常见组合）',
    },
    {
        'mechanism_a': 'ChaosInoculation',
        'mechanism_b': 'LifeConvertToEnergyShield',
        'relation_type': 'overrides',
        'direction': 'a_to_b',
        'description': 'CI 将最大生命设为1，LifeConvertToES 的效果被覆盖',
    },
    {
        'mechanism_a': 'EnergyShieldProtectsMana',
        'mechanism_b': 'ChaosInoculation',
        'relation_type': 'stacks_with',
        'direction': 'both',
        'description': 'EB + CI 允许 ES 保护魔力而非生命，是经典组合',
    },

    # 格挡互斥
    {
        'mechanism_a': 'CannotBlockAttacks',
        'mechanism_b': 'SpellBlockChanceIsBlockChance',
        'relation_type': 'mutually_exclusive',
        'direction': 'both',
        'description': '无法格挡攻击时，法术格挡=攻击格挡变得无意义',
    },

    # 转换链关系
    {
        'mechanism_a': 'PhysicalDamageConvertToFire',
        'mechanism_b': 'PhysicalDamageConvertToCold',
        'relation_type': 'stacks_with',
        'direction': 'both',
        'description': '多种物理转换可叠加，但总转换比例不超过100%',
    },
    {
        'mechanism_a': 'PhysicalDamageConvertToFire',
        'mechanism_b': 'PhysicalDamageConvertToLightning',
        'relation_type': 'stacks_with',
        'direction': 'both',
        'description': '多种物理转换可叠加，但总转换比例不超过100%',
    },
    {
        'mechanism_a': 'PhysicalDamageConvertToCold',
        'mechanism_b': 'ColdDamageConvertToFire',
        'relation_type': 'converts',
        'direction': 'a_to_b',
        'description': '物理→冰→火 转换链，冰霜转火焰在物理转冰之后生效',
    },

    # 承受转换关系
    {
        'mechanism_a': 'PhysicalDamageFromHitsTakenAsLightning',
        'mechanism_b': 'PhysicalDamageFromHitsTakenAsFire',
        'relation_type': 'stacks_with',
        'direction': 'both',
        'description': '多种承受转换可叠加分流物理伤害',
    },
    {
        'mechanism_a': 'PhysicalDamageFromHitsTakenAsLightning',
        'mechanism_b': 'PhysicalDamageFromHitsTakenAsCold',
        'relation_type': 'stacks_with',
        'direction': 'both',
        'description': '多种承受转换可叠加分流物理伤害',
    },

    # 免疫类不互斥，可叠加
    {
        'mechanism_a': 'CannotBeIgnited',
        'mechanism_b': 'CannotBeFrozen',
        'relation_type': 'stacks_with',
        'direction': 'both',
        'description': '元素异常免疫独立生效，可同时拥有多种',
    },
    {
        'mechanism_a': 'CannotBeFrozen',
        'mechanism_b': 'CannotBeShocked',
        'relation_type': 'stacks_with',
        'direction': 'both',
        'description': '元素异常免疫独立生效，可同时拥有多种',
    },

    # 钢铁反射与闪避
    {
        'mechanism_a': 'IronReflexes',
        'mechanism_b': 'CannotBeEvaded',
        'relation_type': 'stacks_with',
        'direction': 'both',
        'description': '钢铁反射将闪避转护甲；命中必中跳过敌人闪避检定，互不影响',
    },

    # 触发类内部关系
    {
        'mechanism_a': 'CastOnCriticalStrike',
        'mechanism_b': 'CastWhenDamageTaken',
        'relation_type': 'mutually_exclusive',
        'direction': 'both',
        'description': '同一技能不能同时受两个触发辅助支持',
    },
    {
        'mechanism_a': 'CastOnCriticalStrike',
        'mechanism_b': 'CastWhileChannelling',
        'relation_type': 'mutually_exclusive',
        'direction': 'both',
        'description': '同一技能不能同时受两个触发辅助支持',
    },
    {
        'mechanism_a': 'CastWhenDamageTaken',
        'mechanism_b': 'CastWhileChannelling',
        'relation_type': 'mutually_exclusive',
        'direction': 'both',
        'description': '同一技能不能同时受两个触发辅助支持',
    },
    {
        'mechanism_a': 'CastOnCriticalStrike',
        'mechanism_b': 'Spellslinger',
        'relation_type': 'mutually_exclusive',
        'direction': 'both',
        'description': '同一技能不能同时受两个触发辅助支持',
    },

    # === Modifier聚合引擎内部关系 (来自 Classes/ModStore.lua) ===
    {
        'mechanism_a': 'ModStore_Sum',
        'mechanism_b': 'ModStore_More',
        'relation_type': 'stacks_with',
        'direction': 'both',
        'description': 'Sum(BASE)先加法叠加基础值, Sum(INC)加法叠加百分比, 然后More乘法独立叠加. 计算顺序: base × (1 + ΣInc/100) × ΠMore',
    },
    {
        'mechanism_a': 'ModStore_Override',
        'mechanism_b': 'ModStore_Sum',
        'relation_type': 'overrides',
        'direction': 'a_to_b',
        'description': 'Override优先级最高, 存在Override时跳过Sum/More计算直接使用覆盖值',
    },
    {
        'mechanism_a': 'ModStore_Override',
        'mechanism_b': 'ModStore_More',
        'relation_type': 'overrides',
        'direction': 'a_to_b',
        'description': 'Override优先级最高, 存在Override时跳过Sum/More计算直接使用覆盖值',
    },
    {
        'mechanism_a': 'ModStore_EvalMod',
        'mechanism_b': 'ModStore_Sum',
        'relation_type': 'modifies',
        'direction': 'a_to_b',
        'description': 'EvalMod评估条件标签后决定modifier是否参与Sum/More/Flag聚合',
    },
    {
        'mechanism_a': 'ModStore_EvalMod',
        'mechanism_b': 'ModStore_More',
        'relation_type': 'modifies',
        'direction': 'a_to_b',
        'description': 'EvalMod评估条件标签后决定modifier是否参与Sum/More/Flag聚合',
    },
    {
        'mechanism_a': 'ModStore_EvalMod',
        'mechanism_b': 'ModStore_Flag',
        'relation_type': 'modifies',
        'direction': 'a_to_b',
        'description': 'EvalMod评估条件标签后决定modifier是否参与Sum/More/Flag聚合',
    },
]


class BehaviorExtractor:
    """
    从 POB 源码提取机制行为描述。
    
    三种提取策略：
    - Flag: 扫描 modDB:Flag(nil, "FlagName") 检查点
    - Numeric: 扫描 modDB:Sum("BASE"|"INC") + modDB:More() 使用点
    - Trigger: 解析 CalcTriggers.configTable 中的触发器配置
    - Aggregation: 扫描 Classes/ModStore.lua 中的聚合方法定义
    """
    
    def __init__(self, pob_modules_path: Path, pob_classes_path: Path = None):
        self.modules_path = pob_modules_path
        self.classes_path = pob_classes_path or pob_modules_path.parent / 'Classes'
        self._file_cache: Dict[str, str] = {}
    
    def _read_file(self, filename: str) -> str:
        """读取并缓存 Lua 文件（支持 Modules/ 和 Classes/ 路径）"""
        if filename not in self._file_cache:
            # 先尝试 Modules/ 目录
            filepath = self.modules_path / filename
            if not filepath.exists() and self.classes_path:
                # 再尝试 Classes/ 目录
                filepath = self.classes_path / filename
            if filepath.exists():
                with open(filepath, 'r', encoding='utf-8') as f:
                    self._file_cache[filename] = f.read()
            else:
                self._file_cache[filename] = ''
        return self._file_cache[filename]
    
    def extract_flag_behavior(self, mech_id: str) -> Optional[str]:
        """
        提取 Flag 型机制的行为描述。
        扫描 CalcOffence.lua 和 CalcDefence.lua 中的 Flag 检查点，
        提取检查点周围的上下文来描述行为。
        """
        search_files = ['CalcOffence.lua', 'CalcDefence.lua', 'CalcPerform.lua']
        contexts = []
        
        for filename in search_files:
            content = self._read_file(filename)
            if not content:
                continue
            
            lines = content.split('\n')
            # 搜索 Flag 使用点
            for i, line in enumerate(lines):
                # 匹配 Flag(nil, "MechId") 或 Flag(cfg, "MechId")
                if f'"{mech_id}"' in line and ('Flag(' in line or ':Flag(' in line):
                    # 提取上下文 (前后各3行)
                    start = max(0, i - 3)
                    end = min(len(lines), i + 4)
                    ctx_lines = lines[start:end]
                    ctx = '\n'.join(f'  L{start+j+1}: {l.strip()}' for j, l in enumerate(ctx_lines))
                    contexts.append(f'[{filename}:{i+1}]\n{ctx}')
        
        if not contexts:
            return None
        
        return '\n'.join(contexts)
    
    def extract_numeric_behavior(self, mech_id: str) -> Optional[str]:
        """
        提取 Numeric 型机制的行为描述。
        扫描 Sum("BASE"|"INC") 和 More() 使用点。
        """
        search_files = ['CalcOffence.lua', 'CalcDefence.lua', 'CalcPerform.lua']
        contexts = []
        
        for filename in search_files:
            content = self._read_file(filename)
            if not content:
                continue
            
            lines = content.split('\n')
            for i, line in enumerate(lines):
                if f'"{mech_id}"' in line and ('Sum(' in line or 'More(' in line):
                    start = max(0, i - 2)
                    end = min(len(lines), i + 5)
                    ctx_lines = lines[start:end]
                    ctx = '\n'.join(f'  L{start+j+1}: {l.strip()}' for j, l in enumerate(ctx_lines))
                    contexts.append(f'[{filename}:{i+1}]\n{ctx}')
        
        if not contexts:
            return None
        
        return '\n'.join(contexts)
    
    def extract_trigger_behavior(self, trigger_key: str) -> Optional[str]:
        """
        提取 Trigger 型机制的行为描述。
        解析 CalcTriggers.lua 的 configTable 中对应的触发器配置。
        """
        content = self._read_file('CalcTriggers.lua')
        if not content:
            return None
        
        lines = content.split('\n')
        # 搜索 configTable 中的键
        trigger_key_lower = trigger_key.lower()
        in_config = False
        brace_depth = 0
        config_lines = []
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            # 查找 configTable["key"] = function(env)
            if not in_config:
                # 检查多种格式
                if (f'["{trigger_key_lower}"]' in stripped.lower() or
                    f"['{trigger_key_lower}']" in stripped.lower()):
                    in_config = True
                    brace_depth = 0
                    config_lines = [f'  L{i+1}: {stripped}']
                    # 计算当前行的花括号
                    brace_depth += stripped.count('{') - stripped.count('}')
                    if stripped.endswith('end,') or stripped.endswith('end'):
                        if brace_depth <= 0:
                            in_config = False
                            break
                    continue
            
            if in_config:
                config_lines.append(f'  L{i+1}: {stripped}')
                brace_depth += stripped.count('{') - stripped.count('}')
                
                # 结束检测: return ... end 或 brace 归零
                if ('end,' in stripped or stripped == 'end') and brace_depth <= 0:
                    in_config = False
                    break
                
                # 安全限制：最多50行
                if len(config_lines) > 50:
                    config_lines.append('  ... (截断)')
                    break
        
        if not config_lines:
            return None
        
        return f'[CalcTriggers.lua configTable["{trigger_key_lower}"]]\n' + '\n'.join(config_lines)
    
    def extract_aggregation_behavior(self, mech_id: str) -> Optional[str]:
        """
        提取 Aggregation 型机制的行为描述。
        从 Classes/ModStore.lua 提取方法定义及关键实现。
        """
        content = self._read_file('ModStore.lua')
        if not content:
            return None
        
        # 从 mech_id 提取方法名：ModStore_Sum → Sum, ModStore_EvalMod → EvalMod
        method_name = mech_id.replace('ModStore_', '')
        
        lines = content.split('\n')
        in_method = False
        method_lines = []
        depth = 0
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            if not in_method:
                # 匹配 function ModStoreClass:MethodName(
                if f'function ModStoreClass:{method_name}(' in stripped:
                    in_method = True
                    depth = 1
                    method_lines = [f'  L{i+1}: {stripped}']
                    continue
            
            if in_method:
                method_lines.append(f'  L{i+1}: {stripped}')
                
                # 追踪 function/if/for/while...end 嵌套
                for word in re.findall(r'\b(function|if|for|while|do|repeat|end|until)\b', stripped):
                    if word in ('function', 'if', 'for', 'while', 'repeat'):
                        depth += 1
                    elif word in ('end', 'until'):
                        depth -= 1
                
                if depth <= 0:
                    break
                
                # 安全限制
                if len(method_lines) > 80:
                    method_lines.append('  ... (截断)')
                    break
        
        if not method_lines:
            return None
        
        return f'[Classes/ModStore.lua: {method_name}()]\n' + '\n'.join(method_lines)
    
    def extract_behavior(self, mech_id: str, mech_info: Dict) -> Optional[str]:
        """根据行为类型提取对应的行为描述"""
        behavior_type = mech_info.get('behavior_type', 'flag')
        category = mech_info.get('category', '')
        
        # aggregation 类型：从 ModStore.lua 提取
        if category == 'aggregation' or mech_id.startswith('ModStore_'):
            return self.extract_aggregation_behavior(mech_id)
        
        if behavior_type == 'flag':
            return self.extract_flag_behavior(mech_id)
        elif behavior_type == 'numeric':
            # 先尝试数值型，再回退到 flag 型（很多数值型也有 Flag 检查）
            result = self.extract_numeric_behavior(mech_id)
            if not result:
                result = self.extract_flag_behavior(mech_id)
            return result
        elif behavior_type == 'trigger':
            # 使用机制 ID 对应的 configTable 键名
            trigger_keys = {
                'CastOnCriticalStrike': 'cast on critical strike',
                'CastWhenDamageTaken': 'cast when damage taken',
                'CastWhileChannelling': 'cast while channelling',
                'Spellslinger': 'spellslinger',
            }
            key = trigger_keys.get(mech_id, mech_id.lower())
            return self.extract_trigger_behavior(key)
        
        return None


class MechanismExtractor:
    """
    机制提取器 v2
    
    三阶段提取流程:
    A. 解析 ModCache.lua 获取 stat 映射
    B. 模式匹配识别机制
    C. 从 POB 代码提取行为描述
    D. 实体关联
    E. 导出（含 5 个新字段 + mechanism_relations 表）
    """
    
    # 已知的机制 stat 名称模式
    KNOWN_MECHANISM_PATTERNS = [
        # 立即偷取系列
        r'Instant\w+Leech',
        # 绕过/免疫系列
        r'CannotBe\w+',
        r'ImmuneTo\w+',
        r'Ignore\w+',
        # 转换系列
        r'\w+ConvertTo\w+',
        r'\w+TakenAs\w+',
        r'\w+FromHitsTakenAs\w+',
        # 特殊机制
        r'GhostReaver',
        r'CanLeech\w+OnFull\w+',
        r'ZealotsOath',
        r'ChaosInoculation',
        r'IronReflexes',
        r'EnergyShieldProtectsMana',
        r'SpellBlockChanceIsBlockChance',
    ]
    
    def __init__(self, modcache_path: str, entities_db_path: str = None,
                 pob_path: str = None):
        """
        初始化机制提取器
        
        Args:
            modcache_path: ModCache.lua 文件路径
            entities_db_path: 实体数据库路径（可选）
            pob_path: POB 根目录路径（用于行为提取，可选）
        """
        self.modcache_path = Path(modcache_path)
        self.entities_db_path = Path(entities_db_path) if entities_db_path else None
        self.pob_path = Path(pob_path) if pob_path else self.modcache_path.parent.parent
        self.stat_mappings: Dict[str, Dict] = {}
        self.mechanisms: Dict[str, Set[str]] = defaultdict(set)  # mechanism -> set of stat names
        self.stat_sources: Dict[str, List[Dict]] = defaultdict(list)  # stat name -> list of sources
        self.description_to_entities: Dict[str, List[Dict]] = defaultdict(list)  # description -> list of entities
        
        # v2: 行为提取器
        self._behavior_extractor: Optional[BehaviorExtractor] = None
        # v2: 行为描述缓存
        self._behavior_cache: Dict[str, Optional[str]] = {}
        # v2: YAML 补充描述
        self._yaml_descriptions: Dict[str, Dict] = {}
        
    def parse_modcache(self) -> Dict[str, Dict]:
        """解析 ModCache.lua，优先使用 Lua 解析器"""
        print(f"解析 {self.modcache_path}...")
        
        with open(self.modcache_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 优先使用 Lua 解析器
        if HAS_LUA_PARSER:
            print("  使用 Lua 解析器...")
            return self._parse_modcache_with_lua(content)
        else:
            print("  使用正则解析器...")
            return self._parse_modcache_with_regex(content)
    
    def _parse_modcache_with_lua(self, content: str) -> Dict[str, Dict]:
        """使用 Lua 解析器解析 ModCache"""
        parser = LuaParser()
        mappings = parser.parse_modcache(content)
        
        # 转换为内部格式
        for desc, data in mappings.items():
            stats = data.get('stats', [])
            if stats:
                self.stat_mappings[desc] = {
                    'stats': stats,
                    'description': desc
                }
                
                # 记录每个 stat 对应的描述
                for stat in stats:
                    stat_name = stat.get('name', '')
                    if stat_name:
                        self.stat_sources[stat_name].append({
                            'description': desc,
                            'type': stat.get('type', ''),
                            'value': stat.get('value', ''),
                            'condition': stat.get('condition', '')
                        })
        
        print(f"  解析了 {len(self.stat_mappings)} 个描述映射")
        return self.stat_mappings
    
    def _parse_modcache_with_regex(self, content: str) -> Dict[str, Dict]:
        """使用正则解析 ModCache（回退方案）"""
        lines = content.split('\n')
        
        for line in lines:
            # 匹配有 stat 映射的行
            # 格式: c["description"]={{...stats...}, nil/str}
            # 修复：支持结尾是 nil 或字符串
            match = re.match(r'c\["([^"]+)"\]=\{\{(.+)\},\s*(?:nil|"[^"]*")\}', line)
            if not match:
                continue
            
            desc = match.group(1)
            stats_block = match.group(2)
            
            # 跳过空表 {{}, ...} - 这些没有 stat 数据
            if stats_block.strip() == '' or stats_block.strip() == '{}':
                continue
            
            # 解析 stat 块
            stats = self._parse_stats_block(stats_block)
            if stats:
                self.stat_mappings[desc] = {
                    'stats': stats,
                    'description': desc
                }
                
                # 记录每个 stat 对应的描述
                for stat in stats:
                    stat_name = stat.get('name', '')
                    if stat_name:
                        self.stat_sources[stat_name].append({
                            'description': desc,
                            'type': stat.get('type', ''),
                            'value': stat.get('value', ''),
                            'condition': stat.get('condition', '')
                        })
        
        print(f"  解析了 {len(self.stat_mappings)} 个描述映射")
        return self.stat_mappings
    
    def build_entity_mapping(self) -> Dict[str, List[Dict]]:
        """从实体数据库建立 描述→实体 映射"""
        if not self.entities_db_path or not self.entities_db_path.exists():
            print("  [WARN] 实体数据库不存在，跳过实体关联")
            return {}
        
        print(f"从实体数据库建立关联: {self.entities_db_path}")
        
        conn = sqlite3.connect(self.entities_db_path)
        cursor = conn.cursor()
        
        # 查询所有有 stats 的实体
        cursor.execute('''
            SELECT id, name, type, stats 
            FROM entities 
            WHERE stats IS NOT NULL AND stats != '[]' AND stats != ''
        ''')
        
        count = 0
        for row in cursor.fetchall():
            entity_id, entity_name, entity_type, stats_json = row
            if not stats_json:
                continue
            
            try:
                stats = json.loads(stats_json)
                for stat in stats:
                    if isinstance(stat, str) and stat.strip():
                        self.description_to_entities[stat.strip()].append({
                            'id': entity_id,
                            'name': entity_name,
                            'type': entity_type
                        })
                        count += 1
            except:
                pass
        
        conn.close()
        print(f"  建立了 {len(self.description_to_entities)} 个描述映射，涉及 {count} 个关联")
        return self.description_to_entities
    
    def _parse_stats_block(self, block: str) -> List[Dict]:
        """解析 stat 块"""
        stats = []
        
        # 匹配 name="StatName", type="TYPE", value=NUMBER 格式
        name_pattern = r'name="([^"]+)"'
        type_pattern = r'type="([^"]+)"'
        value_pattern = r'value=(\d+\.?\d*)'
        condition_pattern = r'\{type="Condition",var="([^"]+)"\}'
        
        # 分割多个 stat - 处理 [n]= 格式
        stat_blocks = re.split(r'\},\s*\[?\d*\]?=\{', block)
        
        for stat_block in stat_blocks:
            name_match = re.search(name_pattern, stat_block)
            type_match = re.search(type_pattern, stat_block)
            value_match = re.search(value_pattern, stat_block)
            condition_match = re.search(condition_pattern, stat_block)
            
            if name_match:
                stat = {
                    'name': name_match.group(1),
                    'type': type_match.group(1) if type_match else '',
                    'value': value_match.group(1) if value_match else '',
                    'condition': condition_match.group(1) if condition_match else ''
                }
                stats.append(stat)
        
        return stats
    
    def identify_mechanisms(self) -> Dict[str, Set[str]]:
        """识别机制"""
        print("识别机制...")
        
        # 合并所有已知的 stat 名称
        all_stat_names = set(self.stat_sources.keys())
        
        # 根据模式匹配识别机制
        for stat_name in all_stat_names:
            for pattern in self.KNOWN_MECHANISM_PATTERNS:
                if re.match(pattern, stat_name):
                    # 使用 stat 名称作为机制标识符
                    self.mechanisms[stat_name].add(stat_name)
                    break
        
        # 确保所有 KNOWN_MECHANISMS 中定义的机制都被识别
        for mech_id in KNOWN_MECHANISMS:
            if mech_id in all_stat_names:
                self.mechanisms[mech_id].add(mech_id)
            elif mech_id not in self.mechanisms:
                # 即使 ModCache 中没有直接出现，也添加已知机制
                # （某些机制仅在 Calc 模块中以 Flag 方式存在）
                self.mechanisms[mech_id].add(mech_id)
        
        print(f"  识别了 {len(self.mechanisms)} 个机制")
        return dict(self.mechanisms)
    
    def load_yaml_descriptions(self, yaml_path: str = None):
        """
        加载 YAML 补充描述文件
        
        YAML 文件提供无法从代码自动提取的描述信息，作为最终回退。
        """
        if yaml_path is None:
            # 默认路径
            yaml_path = Path(__file__).parent.parent / 'config' / 'mechanism_descriptions.yaml'
        else:
            yaml_path = Path(yaml_path)
        
        if not yaml_path.exists():
            print(f"  [INFO] 未找到 mechanism_descriptions.yaml，跳过 YAML 补充")
            return
        
        print(f"加载 YAML 补充描述: {yaml_path}")
        with open(yaml_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        if data and 'mechanisms' in data:
            for mech in data['mechanisms']:
                mech_id = mech.get('id')
                if mech_id:
                    self._yaml_descriptions[mech_id] = mech
            print(f"  加载了 {len(self._yaml_descriptions)} 条 YAML 补充描述")
    
    def extract_behaviors(self):
        """
        Phase C: 从 POB 代码提取所有机制的行为描述
        """
        print("提取机制行为描述...")
        
        modules_path = self.pob_path / 'Modules'
        classes_path = self.pob_path / 'Classes'
        if not modules_path.exists():
            print(f"  [WARN] POB Modules 目录不存在: {modules_path}")
            print(f"         跳过行为提取")
            return
        
        self._behavior_extractor = BehaviorExtractor(modules_path, classes_path)
        
        extracted = 0
        for mech_id in self.mechanisms:
            mech_info = KNOWN_MECHANISMS.get(mech_id, {})
            if not mech_info:
                # 未在 KNOWN_MECHANISMS 中定义的机制，尝试 flag 提取
                mech_info = {'behavior_type': 'flag'}
            
            behavior = self._behavior_extractor.extract_behavior(mech_id, mech_info)
            self._behavior_cache[mech_id] = behavior
            if behavior:
                extracted += 1
        
        print(f"  提取了 {extracted}/{len(self.mechanisms)} 个机制的行为描述")
    
    def get_stat_sources(self, stat_name: str) -> List[Dict]:
        """获取某个 stat 的所有来源"""
        return self.stat_sources.get(stat_name, [])
    
    def _get_mechanism_info(self, mech_id: str) -> Dict[str, Any]:
        """
        获取机制的完整信息（合并多个来源）
        
        优先级：
        1. KNOWN_MECHANISMS 内置定义
        2. YAML 补充描述
        3. 代码提取的行为描述
        4. 默认值
        """
        # 基础信息从 KNOWN_MECHANISMS 获取
        known = KNOWN_MECHANISMS.get(mech_id, {})
        yaml_info = self._yaml_descriptions.get(mech_id, {})
        code_behavior = self._behavior_cache.get(mech_id)
        
        # friendly_name: KNOWN > YAML > 默认
        friendly_name = (
            known.get('friendly_name') or
            yaml_info.get('friendly_name') or
            mech_id
        )
        
        # category: KNOWN > YAML > 自动推断
        category = (
            known.get('category') or
            yaml_info.get('category') or
            self._infer_category(mech_id)
        )
        
        # behavior_description: 合并 YAML 描述 + 代码上下文
        behavior_desc_parts = []
        if yaml_info.get('behavior_description'):
            behavior_desc_parts.append(yaml_info['behavior_description'])
        if code_behavior:
            behavior_desc_parts.append(f'[POB代码上下文]\n{code_behavior}')
        behavior_description = '\n\n'.join(behavior_desc_parts) if behavior_desc_parts else None
        
        # formula_abstract: KNOWN > YAML
        formula_abstract = (
            known.get('formula_abstract') or
            yaml_info.get('formula_abstract')
        )
        
        # affected_stats: KNOWN > YAML
        affected_stats = (
            known.get('affected_stats') or
            yaml_info.get('affected_stats') or
            []
        )
        
        return {
            'friendly_name': friendly_name,
            'mechanism_category': category,
            'behavior_description': behavior_description,
            'formula_abstract': formula_abstract,
            'affected_stats': affected_stats,
        }
    
    def _infer_category(self, mech_id: str) -> str:
        """根据 stat 名称自动推断机制分类"""
        mech_lower = mech_id.lower()
        
        if 'leech' in mech_lower:
            return 'leech'
        elif 'convertto' in mech_lower or 'takenas' in mech_lower:
            return 'conversion'
        elif 'cannotbe' in mech_lower or 'immune' in mech_lower:
            return 'immunity'
        elif 'ignore' in mech_lower:
            return 'damage_modifier'
        elif 'block' in mech_lower:
            return 'block'
        elif 'suppress' in mech_lower:
            return 'suppress'
        elif any(kw in mech_lower for kw in ['cast', 'trigger', 'slinger']):
            return 'trigger'
        else:
            return 'damage_modifier'  # 默认归入伤害修饰
    
    def export_to_db(self, db_path: str, entities_db_path: str = None):
        """
        导出到数据库 (v2: 含 5 个新字段 + mechanism_relations 表)
        """
        print(f"导出到 {db_path}...")
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 创建机制表 (v2: 新增 5 个字段)
        cursor.execute('DROP TABLE IF EXISTS mechanisms')
        cursor.execute('''
            CREATE TABLE mechanisms (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                friendly_name TEXT,
                stat_names TEXT,
                description TEXT,
                behavior_description TEXT,
                mechanism_category TEXT,
                formula_abstract TEXT,
                affected_stats TEXT,
                source_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 创建机制-实体关联表
        cursor.execute('DROP TABLE IF EXISTS mechanism_sources')
        cursor.execute('''
            CREATE TABLE mechanism_sources (
                id TEXT PRIMARY KEY,
                mechanism_id TEXT NOT NULL,
                entity_id TEXT,
                entity_name TEXT,
                description TEXT,
                stat_value TEXT,
                condition TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (mechanism_id) REFERENCES mechanisms(id)
            )
        ''')
        
        # v2: 创建机制关系表
        cursor.execute('DROP TABLE IF EXISTS mechanism_relations')
        cursor.execute('''
            CREATE TABLE mechanism_relations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mechanism_a TEXT NOT NULL,
                mechanism_b TEXT NOT NULL,
                relation_type TEXT NOT NULL,
                direction TEXT NOT NULL DEFAULT 'both',
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (mechanism_a) REFERENCES mechanisms(id),
                FOREIGN KEY (mechanism_b) REFERENCES mechanisms(id)
            )
        ''')
        
        # 插入机制
        for mech_id, stat_names in self.mechanisms.items():
            sources = self.get_stat_sources(mech_id)
            info = self._get_mechanism_info(mech_id)
            
            cursor.execute('''
                INSERT OR REPLACE INTO mechanisms 
                (id, name, friendly_name, stat_names, description, 
                 behavior_description, mechanism_category, formula_abstract, affected_stats,
                 source_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                mech_id,
                info['friendly_name'],  # v2: 使用 friendly_name 作为 name
                info['friendly_name'],
                json.dumps(list(stat_names)),
                f"机制: {info['friendly_name']} ({mech_id})",
                info['behavior_description'],
                info['mechanism_category'],
                info['formula_abstract'],
                json.dumps(info['affected_stats'], ensure_ascii=False) if info['affected_stats'] else None,
                len(sources)
            ))
            
            # 插入来源
            for i, source in enumerate(sources):
                description = source.get('description', '')
                
                # 查找关联的实体
                entities = self.description_to_entities.get(description, [])
                if entities:
                    # 为每个关联实体创建一条记录
                    for j, entity in enumerate(entities):
                        cursor.execute('''
                            INSERT OR IGNORE INTO mechanism_sources 
                            (id, mechanism_id, entity_id, entity_name, description, stat_value, condition)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            f"{mech_id}_source_{i}_{j}",
                            mech_id,
                            entity.get('id', ''),
                            entity.get('name', ''),
                            description,
                            source.get('value', ''),
                            source.get('condition', '')
                        ))
                else:
                    # 没有关联实体，只保存描述
                    cursor.execute('''
                        INSERT OR IGNORE INTO mechanism_sources 
                        (id, mechanism_id, description, stat_value, condition)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (
                        f"{mech_id}_source_{i}",
                        mech_id,
                        description,
                        source.get('value', ''),
                        source.get('condition', '')
                    ))
        
        # v2: 插入机制关系
        existing_mechs = set(self.mechanisms.keys())
        relation_count = 0
        for rel in MECHANISM_RELATIONS:
            mech_a = rel['mechanism_a']
            mech_b = rel['mechanism_b']
            # 只插入两端都存在的关系
            if mech_a in existing_mechs and mech_b in existing_mechs:
                cursor.execute('''
                    INSERT INTO mechanism_relations 
                    (mechanism_a, mechanism_b, relation_type, direction, description)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    mech_a,
                    mech_b,
                    rel['relation_type'],
                    rel.get('direction', 'both'),
                    rel.get('description', ''),
                ))
                relation_count += 1
        
        conn.commit()
        conn.close()
        
        print(f"  导出了 {len(self.mechanisms)} 个机制, {relation_count} 条关系")
        
        # 打印统计
        self._print_stats()
    
    def _print_stats(self):
        """打印增强后的统计信息"""
        total = len(self.mechanisms)
        
        # 统计各字段覆盖率（与数据库口径一致）
        has_friendly = sum(1 for m in self.mechanisms if self._get_mechanism_info(m)['friendly_name'] != m)
        has_category = sum(1 for m in self.mechanisms if self._get_mechanism_info(m)['mechanism_category'])
        has_behavior = sum(1 for m in self.mechanisms if self._get_mechanism_info(m)['behavior_description'])
        has_formula = sum(1 for m in self.mechanisms if self._get_mechanism_info(m)['formula_abstract'])
        has_stats = sum(1 for m in self.mechanisms if self._get_mechanism_info(m)['affected_stats'])
        
        print(f"\n  === 机制增强统计 ===")
        print(f"  friendly_name:        {has_friendly}/{total} ({has_friendly*100//max(total,1)}%)")
        print(f"  mechanism_category:    {has_category}/{total} ({has_category*100//max(total,1)}%)")
        print(f"  behavior_description:  {has_behavior}/{total} ({has_behavior*100//max(total,1)}%)")
        print(f"  formula_abstract:      {has_formula}/{total} ({has_formula*100//max(total,1)}%)")
        print(f"  affected_stats:        {has_stats}/{total} ({has_stats*100//max(total,1)}%)")
        
        # 按分类统计
        categories = defaultdict(int)
        for mech_id in self.mechanisms:
            cat = self._get_mechanism_info(mech_id)['mechanism_category']
            categories[cat] += 1
        
        print(f"\n  === 分类分布 ===")
        for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
            print(f"  {cat}: {count}")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='提取机制 v2')
    parser.add_argument('modcache_path', help='ModCache.lua 路径')
    parser.add_argument('--output', '-o', help='输出数据库路径')
    parser.add_argument('--pob-path', help='POB根目录路径')
    parser.add_argument('--entities-db', help='实体数据库路径')
    parser.add_argument('--yaml-desc', help='YAML描述文件路径')
    
    args = parser.parse_args()
    
    pob_path = args.pob_path
    if not pob_path:
        # 从 modcache_path 推断 POB 路径
        pob_path = str(Path(args.modcache_path).parent.parent)
    
    extractor = MechanismExtractor(
        args.modcache_path,
        entities_db_path=args.entities_db,
        pob_path=pob_path
    )
    extractor.parse_modcache()
    if args.entities_db:
        extractor.build_entity_mapping()
    extractor.identify_mechanisms()
    
    # v2: 加载 YAML 补充 + 行为提取
    extractor.load_yaml_descriptions(args.yaml_desc)
    extractor.extract_behaviors()
    
    # 打印一些示例
    print("\n" + "=" * 60)
    print("示例机制:")
    print("=" * 60)
    
    for mech_id in ['InstantLifeLeech', 'GhostReaver', 'ZealotsOath', 'CastOnCriticalStrike']:
        if mech_id in extractor.mechanisms:
            info = extractor._get_mechanism_info(mech_id)
            print(f"\n{mech_id}:")
            print(f"  友好名: {info['friendly_name']}")
            print(f"  分类: {info['mechanism_category']}")
            print(f"  公式: {info['formula_abstract']}")
            behavior = extractor._behavior_cache.get(mech_id)
            if behavior:
                # 只显示前 200 字符
                preview = behavior[:200] + '...' if len(behavior) > 200 else behavior
                print(f"  行为: {preview}")
    
    if args.output:
        extractor.export_to_db(args.output)
    
    print("\n完成!")


if __name__ == '__main__':
    main()
