#!/usr/bin/env python3
"""
辅助匹配系统 v1
预计算主动技能与辅助宝石的兼容矩阵、效果分类、潜力推荐。

核心数据来源：
- entities.db 中 type='skill_definition' AND support=1 的辅助宝石
- entities.db 中 type='skill_definition' AND support=0 的主动技能
- 辅助的 require_skill_types / exclude_skill_types（RPN 逻辑表达式）
- 主动技能的 skill_types（标签数组）
- 辅助的 constant_stats / stats / stat_sets（效果数据）

三张输出表：
1. support_compatibility: 兼容矩阵（skill_id × support_id → compatible + match_reason）
2. support_effects: 效果分类（support_id → effect_category + quantifiable + key_stats + formula_impact + level_scaling）
3. support_potential: 潜力推荐（skill_id × support_id → synergy_type + potential_reason）
"""

import json
import sqlite3
import re
from pathlib import Path
from typing import Dict, List, Set, Any, Optional, Tuple
from collections import defaultdict


# ============================================================
# 效果分类定义
# ============================================================
EFFECT_CATEGORIES = {
    'damage_more',       # MORE 伤害乘数
    'damage_added',      # 附加伤害
    'speed',             # 攻击/施法速度
    'aoe',               # 范围
    'chain',             # 连锁
    'projectile',        # 投射物
    'duration',          # 持续时间
    'crit',              # 暴击
    'dot',               # 持续伤害
    'utility',           # 工具型（诅咒、光环等）
    'defense',           # 防御型
    'trigger',           # 触发型（元技能）
    'minion',            # 召唤物增强
    'cost_reduction',    # 消耗减少
    'conversion',        # 伤害转换
}

# 协同类型定义
SYNERGY_TYPES = {
    'mechanic_match',    # 机制协同（如 Spell Echo + Arc 连锁清图）
    'tag_synergy',       # 标签协同（辅助 add_skill_types 与技能现有标签互补）
    'stat_amplify',      # stat 增强（辅助的 stat 与技能核心 stat 有交叉）
}


# ============================================================
# stat 名称到效果分类的映射规则
# ============================================================
STAT_CATEGORY_RULES: List[Tuple[str, str, str]] = [
    # (正则模式, 效果分类, 玩家友好描述)
    
    # MORE 伤害
    (r'damage_\+%_final', 'damage_more', '伤害独立乘区'),
    (r'support_.*_damage_\+%_final', 'damage_more', '辅助伤害独立乘区'),
    (r'active_skill_damage_\+%_final', 'damage_more', '主动技能伤害独立乘区'),
    
    # 附加伤害
    (r'base_.*_damage', 'damage_added', '基础附加伤害'),
    (r'added_.*_damage', 'damage_added', '附加伤害'),
    (r'damage_effectiveness', 'damage_added', '附加伤害效率'),
    
    # 速度
    (r'cast_speed', 'speed', '施法/攻击速度'),
    (r'attack_speed', 'speed', '攻击速度'),
    (r'speed_\+%', 'speed', '施法或攻击速度'),
    
    # 范围
    (r'area_of_effect', 'aoe', '技能范围'),
    (r'area_radius', 'aoe', '技能半径'),
    
    # 连锁
    (r'chain', 'chain', '连锁次数（每次连锁伤害衰减）'),
    (r'number_of_chains', 'chain', '连锁次数'),
    
    # 投射物
    (r'projectile', 'projectile', '投射物数量/速度'),
    (r'number_of_additional_projectiles', 'projectile', '额外投射物数量'),
    (r'fork', 'projectile', '分裂次数'),
    
    # 持续时间
    (r'duration', 'duration', '技能持续时间'),
    (r'skill_effect_duration', 'duration', '技能效果持续时间'),
    
    # 暴击
    (r'crit', 'crit', '暴击率/暴击伤害'),
    (r'critical_strike', 'crit', '暴击率/暴击伤害'),
    (r'cannot_crit', 'crit', '禁止暴击'),
    
    # 持续伤害
    (r'damage_over_time', 'dot', '持续伤害'),
    (r'bleed|poison|ignite', 'dot', '异常状态持续伤害'),
    
    # 触发
    (r'triggered_by', 'trigger', '触发机制'),
    (r'trigger', 'trigger', '触发机制'),
    (r'cast_on_', 'trigger', '触发施放'),
    (r'invocation', 'trigger', '元技能触发'),
    
    # 召唤物
    (r'minion', 'minion', '召唤物属性'),
    (r'totem', 'minion', '图腾属性'),
    
    # 消耗减少
    (r'mana_cost', 'cost_reduction', '法力消耗'),
    (r'spirit_cost', 'cost_reduction', '灵魂消耗'),
    (r'cost_\+%', 'cost_reduction', '消耗倍率'),
    
    # 转换
    (r'convert', 'conversion', '伤害类型转换'),
    (r'gain_.*_as', 'conversion', '额外伤害转换'),
    
    # 防御
    (r'life_gain', 'defense', '生命回复'),
    (r'energy_shield', 'defense', '能量护盾'),
    (r'block', 'defense', '格挡'),
    (r'armour', 'defense', '护甲'),
    (r'evasion', 'defense', '闪避'),
]

# ============================================================
# _per_ stat 无 cap 时的合理最大层数估值
# 用于 Type C（无伴随 cap stat、无 "up to" 描述）的 _per_ stat
# key: _per_ 后面的条件关键词片段, value: 合理最大层数
# ============================================================
# ============================================================
# 通用 stat qualifier 词典（用于语义有效性检查）
# 三个正交维度：从 _final stat 名中分词后匹配
# ============================================================
DAMAGE_TYPE_WORDS: Set[str] = {
    'physical', 'fire', 'cold', 'lightning', 'chaos', 'elemental',
}
ATTACK_MODE_WORDS: Set[str] = {
    'melee', 'spell', 'projectile', 'area', 'attack', 'ranged',
}
DAMAGE_SCOPE_WORDS: Set[str] = {
    'hit', 'dot', 'ailment', 'bleed', 'poison', 'ignite',
    'burning', 'damage_over_time',
}

# Flag stat → 阻断的伤害类型/模式映射
# key: flag stat 名, value: 被阻断的维度标签集合
BLOCK_FLAG_MAP: Dict[str, Set[str]] = {
    'deal_no_elemental_damage':        {'fire', 'cold', 'lightning', 'elemental'},
    'base_deal_no_chaos_damage':       {'chaos'},
    'deal_no_physical_damage':         {'physical'},
    'cannot_inflict_elemental_ailments': {'ignite', 'burning', 'freeze', 'chill', 'shock'},
    'never_freeze':                    {'freeze', 'chill'},
    'never_ignite':                    {'ignite', 'burning'},
    'never_shock':                     {'shock'},
    'cannot_cause_bleeding':           {'bleed'},
    'cannot_crit':                     {'crit'},
    'global_cannot_crit':              {'crit'},
}

PER_STAT_MAX_HEURISTIC: Dict[str, int] = {
    'different_elemental': 3,          # 3种元素类型（火/冰/电）
    'elemental_skill_used_recently': 3, # 3种不同元素技能
    'charge_type_or_infusion': 5,      # 3 charge + ~2 infusion
    'charge_type': 3,                  # 3种能量球（暴击/狂怒/耐力）
    'infusion_type': 3,                # 估约3种灌注
    'combo_stack': 10,                 # combo 默认 max 10（通常有伴随 cap）
    'recently': 5,                     # "used recently" 一般 ~4-6 次
    'used_recently': 5,                # 同上
    'time': 6,                         # 时间叠加默认 ~6 stacks
}

# ============================================================
# Flag 型 stat 语义映射表
# 这些 stat 存在于 stats 字段中（纯字符串，无数值），
# 需要映射为人类可读描述和正面/负面极性。
# polarity: 'restriction' = 负面限制, 'benefit' = 正面效果, 'mechanic' = 中性机制
# ============================================================
FLAG_SEMANTIC_MAP: Dict[str, Dict[str, str]] = {
    # === 元素/伤害类型限制（restriction，严重） ===
    'cannot_inflict_elemental_ailments':   {'desc': '不能造成元素异常（电震/点燃/冻结）', 'polarity': 'restriction', 'category': 'damage_more'},
    'deal_no_elemental_damage':           {'desc': '不能造成元素伤害', 'polarity': 'restriction', 'category': 'conversion'},
    'base_deal_no_chaos_damage':          {'desc': '不能造成混沌伤害', 'polarity': 'restriction', 'category': 'conversion'},
    
    # === 暴击限制 ===
    'cannot_crit':                        {'desc': '不能暴击', 'polarity': 'restriction', 'category': 'crit'},
    'global_cannot_crit':                 {'desc': '不能暴击', 'polarity': 'restriction', 'category': 'crit'},
    
    # === 异常状态限制 ===
    'never_freeze':                       {'desc': '不能冻结敌人', 'polarity': 'restriction', 'category': 'dot'},
    'never_ignite':                       {'desc': '不能点燃敌人', 'polarity': 'restriction', 'category': 'dot'},
    'never_shock':                        {'desc': '不能电击敌人', 'polarity': 'restriction', 'category': 'dot'},
    'cannot_cause_bleeding':              {'desc': '不能造成流血', 'polarity': 'restriction', 'category': 'dot'},
    'cannot_inflict_maim':                {'desc': '不能造成残废', 'polarity': 'restriction', 'category': 'dot'},
    'cannot_consume_impale':              {'desc': '不能消耗穿刺', 'polarity': 'restriction', 'category': 'damage_more'},
    
    # === 召唤物限制 ===
    'minions_cannot_be_damaged':          {'desc': '召唤物不会受到伤害', 'polarity': 'benefit', 'category': 'minion'},
    'minions_deal_no_damage':             {'desc': '召唤物不造成伤害', 'polarity': 'restriction', 'category': 'minion'},
    
    # === 能量球/资源限制 ===
    'skill_cannot_generate_power_charges':  {'desc': '不能产生暴击球', 'polarity': 'restriction', 'category': 'crit'},
    'skill_cannot_generate_endurance_charges': {'desc': '不能产生耐力球', 'polarity': 'restriction', 'category': 'defense'},
    
    # === 目标/攻击限制 ===
    'can_only_damage_low_life_enemies':   {'desc': '只能伤害低血量敌人', 'polarity': 'restriction', 'category': 'damage_more'},
    'number_of_totems_allowed_is_1':      {'desc': '最多放置1个图腾', 'polarity': 'restriction', 'category': 'minion'},
    
    # === 正面效果（benefit） ===
    'projectiles_nova':                   {'desc': '投射物以nova方式发射', 'polarity': 'benefit', 'category': 'projectile'},
    'global_knockback':                   {'desc': '击退敌人', 'polarity': 'benefit', 'category': 'utility'},
    'global_always_hit':                  {'desc': '命中无法被闪避', 'polarity': 'benefit', 'category': 'damage_more'},
    'global_maim_on_hit':                 {'desc': '命中时造成残废', 'polarity': 'benefit', 'category': 'utility'},
    'global_poison_on_hit':               {'desc': '命中时造成中毒', 'polarity': 'benefit', 'category': 'dot'},
    'global_bleed_on_hit':                {'desc': '命中时造成流血', 'polarity': 'benefit', 'category': 'dot'},
    'supported_by_inevitable_criticals':  {'desc': '暴击无法被闪避', 'polarity': 'benefit', 'category': 'crit'},
    'hits_ignore_enemy_fire_resistance':  {'desc': '命中无视敌人火焰抗性', 'polarity': 'benefit', 'category': 'damage_more'},
    'double_ancestral_boost_effect':      {'desc': '祖灵增益效果翻倍', 'polarity': 'benefit', 'category': 'damage_more'},
    'life_leech_from_source_not_removed_at_full_life': {'desc': '满血时偷取不被移除', 'polarity': 'benefit', 'category': 'defense'},
    'always_shock_wet_enemies':           {'desc': '总是电击潮湿的敌人', 'polarity': 'benefit', 'category': 'dot'},
    'base_chaos_damage_can_ignite':       {'desc': '混沌伤害可以点燃', 'polarity': 'benefit', 'category': 'conversion'},
    'mana_leech_from_elemental_instead':  {'desc': '从元素伤害中偷取法力', 'polarity': 'benefit', 'category': 'cost_reduction'},
    
    # === 中性机制（mechanic） ===
    'curse_apply_as_curse_zone':          {'desc': '诅咒以区域方式施放', 'polarity': 'mechanic', 'category': 'utility'},
    'wall_is_created_in_a_circle_instead': {'desc': '墙壁改为环形', 'polarity': 'mechanic', 'category': 'aoe'},
    'repeat_last_step_of_combo_attack':   {'desc': '重复连击最后一段', 'polarity': 'mechanic', 'category': 'damage_more'},
    'storm_skills_spawn_at_initiator_location': {'desc': '风暴技能在自身位置生成', 'polarity': 'mechanic', 'category': 'aoe'},
    'strikes_are_ancestrally_boosted':    {'desc': '近战打击获得祖灵增幅', 'polarity': 'benefit', 'category': 'damage_more'},
}

# 编译正则
_COMPILED_STAT_RULES = [(re.compile(pattern, re.IGNORECASE), cat, desc) for pattern, cat, desc in STAT_CATEGORY_RULES]


# ============================================================
# 潜力推荐的机制协同规则
# ============================================================
MECHANIC_SYNERGY_RULES: List[Dict[str, Any]] = [
    # 连锁 + 范围技能
    {
        'support_has_stat': re.compile(r'chain|number_of_chains', re.IGNORECASE),
        'skill_has_type': {'Spell', 'Projectile'},
        'synergy_type': 'mechanic_match',
        'reason': '连锁与投射物/法术的清图协同',
    },
    # 投射物 + 投射物技能
    {
        'support_has_stat': re.compile(r'projectile|fork', re.IGNORECASE),
        'skill_has_type': {'Projectile'},
        'synergy_type': 'mechanic_match',
        'reason': '额外投射物与投射物技能的覆盖协同',
    },
    # 范围 + 范围技能
    {
        'support_has_stat': re.compile(r'area_of_effect|area_radius', re.IGNORECASE),
        'skill_has_type': {'Area'},
        'synergy_type': 'mechanic_match',
        'reason': '范围增加与范围技能的覆盖协同',
    },
    # DoT + 持续伤害技能
    {
        'support_has_stat': re.compile(r'damage_over_time|bleed|poison|ignite', re.IGNORECASE),
        'skill_has_type': {'DamageOverTime'},
        'synergy_type': 'mechanic_match',
        'reason': '持续伤害增强与 DoT 技能的协同',
    },
    # 暴击 + 可暴击技能
    {
        'support_has_stat': re.compile(r'crit|critical_strike', re.IGNORECASE),
        'skill_has_type': {'Spell', 'Attack'},
        'synergy_type': 'stat_amplify',
        'reason': '暴击增强与可暴击技能的核心数值协同',
    },
    # 持续时间 + 持续型技能
    {
        'support_has_stat': re.compile(r'duration|skill_effect_duration', re.IGNORECASE),
        'skill_has_type': {'Duration'},
        'synergy_type': 'tag_synergy',
        'reason': '持续时间增加与持续型技能的标签协同',
    },
    # 触发型 + 可触发技能
    {
        'support_has_stat': re.compile(r'triggered_by|trigger|invocation', re.IGNORECASE),
        'skill_has_type': {'Triggerable'},
        'synergy_type': 'mechanic_match',
        'reason': '触发机制与可触发技能的自动施放协同',
    },
    # 召唤物增强 + 召唤技能
    {
        'support_has_stat': re.compile(r'minion', re.IGNORECASE),
        'skill_has_type': {'CreatesMinion'},
        'synergy_type': 'mechanic_match',
        'reason': '召唤物增强与创建召唤物技能的协同',
    },
]


# ============================================================
# RPN 逻辑表达式求值器
# ============================================================
def evaluate_rpn_expression(expression: List[str], available_types: Set[str]) -> bool:
    """
    求值 POB 的 RPN（逆波兰表达式）风格的 SkillType 条件表达式。
    
    POB 中 require_skill_types 和 exclude_skill_types 使用 RPN 逻辑：
    - 普通标签名：检查是否在 available_types 中
    - "AND"：弹出栈顶两个值，求逻辑与
    - "OR"：弹出栈顶两个值，求逻辑或
    - "NOT"：弹出栈顶一个值，求逻辑非
    
    示例：
    - ["Spell"] → 检查是否有 Spell
    - ["Spell", "Triggerable", "AND"] → Spell AND Triggerable
    - ["RangedAttack", "CrossbowAmmoSkill", "OR"] → RangedAttack OR CrossbowAmmoSkill
    - ["Spell", "Triggerable", "Fire", "AND", "AND"] → Spell AND Triggerable AND Fire
    - ["Trapped", "RemoteMined", "OR", "SummonsTotem", "AND", "InbuiltTrigger"] 
      → (Trapped OR RemoteMined) AND SummonsTotem, InbuiltTrigger
    
    对于没有逻辑运算符的简单列表（如 ["Damage", "Attack", "CrossbowAmmoSkill"]）：
    - 默认行为：任一匹配即可（隐式 OR）
    
    Args:
        expression: RPN 表达式列表
        available_types: 技能拥有的 SkillType 标签集合
    
    Returns:
        True 如果条件满足
    """
    if not expression:
        return True
    
    operators = {'AND', 'OR', 'NOT'}
    
    # 检查是否包含运算符
    has_operators = any(token in operators for token in expression)
    
    if not has_operators:
        # 没有运算符：简单列表，隐式 OR（任一匹配即可）
        return any(tag in available_types for tag in expression)
    
    # RPN 求值
    stack: List[bool] = []
    
    for token in expression:
        if token == 'AND':
            if len(stack) < 2:
                return False
            b = stack.pop()
            a = stack.pop()
            stack.append(a and b)
        elif token == 'OR':
            if len(stack) < 2:
                return False
            b = stack.pop()
            a = stack.pop()
            stack.append(a or b)
        elif token == 'NOT':
            if len(stack) < 1:
                return False
            a = stack.pop()
            stack.append(not a)
        else:
            # 标签名：检查是否在技能的 skill_types 中
            stack.append(token in available_types)
    
    # 如果栈中有多个值，用 AND 合并（多个独立条件，全部都要满足）
    if not stack:
        return True
    return all(stack)


# ============================================================
# SupportMatcher 主类
# ============================================================
class SupportMatcher:
    """
    辅助匹配预计算引擎
    
    负责：
    1. 从 entities.db 加载辅助和主动技能数据
    2. 计算兼容矩阵 → support_compatibility 表
    3. 分析效果分类 → support_effects 表
    4. 生成潜力推荐 → support_potential 表
    """
    
    def __init__(self, entities_db_path: str):
        """
        Args:
            entities_db_path: entities.db 的路径
        """
        self.entities_db_path = entities_db_path
        
        # 数据缓存
        self._supports: List[Dict[str, Any]] = []       # 辅助宝石列表
        self._active_skills: List[Dict[str, Any]] = []   # 主动技能列表
        
        # 结果缓存
        self._compatibility: List[Dict[str, Any]] = []   # 兼容矩阵
        self._effects: Dict[str, Dict[str, Any]] = {}    # 效果分类（support_id → info）
        self._potentials: List[Dict[str, Any]] = []       # 潜力推荐
    
    def load_data(self):
        """从 entities.db 加载辅助和主动技能数据"""
        print("\n[Step 5] 辅助匹配系统")
        print("=" * 50)
        print("加载实体数据...")
        
        conn = sqlite3.connect(self.entities_db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 加载辅助宝石（support=1 且非隐藏）
        cursor.execute('''
            SELECT id, name, skill_types, require_skill_types, add_skill_types,
                   exclude_skill_types, constant_stats, stats, stat_sets, levels,
                   hidden, is_trigger, summary, key_mechanics, display_stats
            FROM entities 
            WHERE type = 'skill_definition' AND support = 1 AND hidden = 0
        ''')
        for row in cursor.fetchall():
            support = self._parse_entity_row(row)
            self._supports.append(support)
        
        # 加载主动技能（support=0 且非隐藏）
        cursor.execute('''
            SELECT id, name, skill_types, constant_stats, stats, stat_sets, levels,
                   hidden, is_trigger, summary, key_mechanics
            FROM entities
            WHERE type = 'skill_definition' AND support = 0 AND hidden = 0
        ''')
        for row in cursor.fetchall():
            skill = self._parse_entity_row(row)
            # 跳过没有 skill_types 的技能（内部触发技能等）
            if skill.get('_skill_types_set'):
                self._active_skills.append(skill)
        
        conn.close()
        
        print(f"  加载了 {len(self._supports)} 个辅助宝石, {len(self._active_skills)} 个主动技能")
    
    def _parse_entity_row(self, row: sqlite3.Row) -> Dict[str, Any]:
        """解析实体行为字典，自动反序列化 JSON 字段"""
        result = dict(row)
        
        json_fields = [
            'skill_types', 'require_skill_types', 'add_skill_types',
            'exclude_skill_types', 'constant_stats', 'stats', 'stat_sets',
            'levels', 'key_mechanics', 'display_stats'
        ]
        for field in json_fields:
            val = result.get(field)
            if val and isinstance(val, str):
                try:
                    result[field] = json.loads(val)
                except (json.JSONDecodeError, TypeError):
                    pass
        
        # 预计算 skill_types 集合（方便后续匹配）
        skill_types = result.get('skill_types')
        if isinstance(skill_types, list):
            result['_skill_types_set'] = set(skill_types)
        else:
            result['_skill_types_set'] = set()
        
        return result
    
    # ============================================================
    # 5.2: 兼容矩阵计算
    # ============================================================
    def compute_compatibility(self):
        """
        计算所有主动技能 × 辅助宝石的兼容矩阵。
        
        兼容性判断逻辑：
        1. 辅助的 require_skill_types 必须被技能满足（RPN 表达式）
        2. 辅助的 exclude_skill_types 不能被技能匹配（RPN 表达式，匹配则排除）
        3. 两个条件同时满足则 compatible=True
        """
        print("计算兼容矩阵...")
        
        self._compatibility = []
        compatible_count = 0
        
        for support in self._supports:
            support_id = support['id']
            require_types = support.get('require_skill_types', [])
            exclude_types = support.get('exclude_skill_types', [])
            
            if not isinstance(require_types, list):
                require_types = []
            if not isinstance(exclude_types, list):
                exclude_types = []
            
            for skill in self._active_skills:
                skill_id = skill['id']
                skill_types_set = skill['_skill_types_set']
                
                # 判断 require：技能必须满足辅助的 require_skill_types
                require_match = evaluate_rpn_expression(require_types, skill_types_set)
                
                # 判断 exclude：技能不能匹配辅助的 exclude_skill_types
                exclude_match = evaluate_rpn_expression(exclude_types, skill_types_set) if exclude_types else False
                
                compatible = require_match and not exclude_match
                
                if compatible:
                    compatible_count += 1
                    # 生成匹配原因
                    match_reason = self._build_match_reason(
                        require_types, exclude_types, skill_types_set
                    )
                    
                    self._compatibility.append({
                        'skill_id': skill_id,
                        'support_id': support_id,
                        'compatible': True,
                        'match_reason': match_reason,
                    })
        
        total_pairs = len(self._supports) * len(self._active_skills)
        print(f"  兼容对数: {compatible_count}/{total_pairs} "
              f"({compatible_count * 100 // max(total_pairs, 1)}%)")
    
    def _build_match_reason(self, require_types: List[str], exclude_types: List[str],
                            skill_types_set: Set[str]) -> str:
        """构建匹配原因说明"""
        operators = {'AND', 'OR', 'NOT'}
        
        # 提取 require 中的标签（去掉运算符）
        require_tags = [t for t in require_types if t not in operators]
        matched_tags = [t for t in require_tags if t in skill_types_set]
        
        parts = []
        if matched_tags:
            parts.append(f"匹配标签: {', '.join(matched_tags)}")
        elif not require_types:
            parts.append("无标签要求")
        
        if exclude_types:
            exclude_tags = [t for t in exclude_types if t not in operators]
            excluded_but_absent = [t for t in exclude_tags if t not in skill_types_set]
            if excluded_but_absent:
                parts.append(f"未被排除: {', '.join(excluded_but_absent[:3])}")
        
        return '; '.join(parts) if parts else '默认兼容'
    
    # ============================================================
    # 5.3 + 5.5: 效果分类 + 等级成长
    # ============================================================
    def compute_effects(self):
        """
        分析每个辅助宝石的效果分类。
        
        提取信息：
        - effect_category: 主要效果分类
        - quantifiable: 是否可量化（有 MORE/INC 数值）
        - key_stats: 关键 stat 列表（JSON）
        - formula_impact: 对 DPS 公式的影响描述
        - level_scaling: 1/10/20 级关键 stat 数值（JSON）
        """
        print("分析效果分类...")
        
        self._effects = {}
        
        for support in self._supports:
            support_id = support['id']
            
            # 收集所有相关 stat
            all_stat_names = self._collect_support_stats(support)
            
            # 分类
            categories = self._classify_stats(all_stat_names)
            
            # 确定主要分类（出现次数最多的）
            primary_category = 'utility'  # 默认
            if categories:
                primary_category = max(categories, key=lambda c: categories[c]['count'])
            
            # 是否可量化
            quantifiable = self._check_quantifiable(support)
            
            # 关键 stat
            key_stats = self._extract_key_stats(support, categories)
            
            # 公式影响（传入 key_stats + display_stats 以注入具体数值和叠加上下文）
            display_stats = support.get('display_stats', [])
            formula_impact = self._build_formula_impact(categories, key_stats, display_stats)
            
            # 等级成长（5.5）
            level_scaling = self._extract_level_scaling(support)
            
            # 倍率预计算（5.8: 分维度期望倍率）
            multipliers = self._compute_multipliers(key_stats, support)
            
            # 语义限制提取（5.6: 通用 qualifier 系统）
            restrictions = self._extract_restrictions(support)
            
            self._effects[support_id] = {
                'support_id': support_id,
                'support_name': support.get('name', support_id),
                'effect_category': primary_category,
                'quantifiable': quantifiable,
                'key_stats': key_stats,
                'formula_impact': formula_impact,
                'level_scaling': level_scaling,
                'multipliers': multipliers,
                'restrictions': restrictions,
            }
        
        # 统计
        cat_dist = defaultdict(int)
        quant_count = 0
        has_scaling = 0
        has_multipliers = 0
        has_restrictions = 0
        for eff in self._effects.values():
            cat_dist[eff['effect_category']] += 1
            if eff['quantifiable']:
                quant_count += 1
            if eff['level_scaling']:
                has_scaling += 1
            if eff.get('multipliers'):
                has_multipliers += 1
            if eff.get('restrictions'):
                has_restrictions += 1
        
        print(f"  效果分类完成: {len(self._effects)} 个辅助")
        print(f"  可量化: {quant_count}/{len(self._effects)}")
        print(f"  有等级成长: {has_scaling}/{len(self._effects)}")
        print(f"  有倍率数据: {has_multipliers}/{len(self._effects)}")
        print(f"  有语义限制: {has_restrictions}/{len(self._effects)}")
        print(f"  分类分布: {dict(sorted(cat_dist.items(), key=lambda x: -x[1]))}")
    
    def _collect_support_stats(self, support: Dict[str, Any]) -> List[str]:
        """收集辅助宝石的所有相关 stat 名称"""
        stat_names = []
        
        # 1. constant_stats：固定 stat
        constant_stats = support.get('constant_stats', [])
        if isinstance(constant_stats, list):
            for item in constant_stats:
                if isinstance(item, list) and len(item) >= 1:
                    stat_names.append(str(item[0]))
        
        # 2. stats：随等级变化的 stat
        stats = support.get('stats', [])
        if isinstance(stats, list):
            for s in stats:
                if isinstance(s, str):
                    stat_names.append(s)
        
        # 3. stat_sets.statMap 中的 stat
        stat_sets = support.get('stat_sets', {})
        if isinstance(stat_sets, dict):
            stat_map = stat_sets.get('statMap', {})
            if isinstance(stat_map, dict):
                stat_names.extend(stat_map.keys())
        
        return stat_names
    
    def _classify_stats(self, stat_names: List[str]) -> Dict[str, Dict[str, Any]]:
        """将 stat 名称列表分类为效果类型"""
        categories: Dict[str, Dict[str, Any]] = {}
        
        for stat_name in stat_names:
            for pattern, cat, desc in _COMPILED_STAT_RULES:
                if pattern.search(stat_name):
                    if cat not in categories:
                        categories[cat] = {
                            'count': 0,
                            'stats': [],
                            'formula_impacts': set(),
                        }
                    categories[cat]['count'] += 1
                    categories[cat]['stats'].append(stat_name)
                    categories[cat]['formula_impacts'].add(desc)
                    break  # 每个 stat 只归入一个分类
        
        return categories
    
    def _check_quantifiable(self, support: Dict[str, Any]) -> bool:
        """
        检查辅助是否可量化（对 DPS / 防御有直接数值影响）。
        
        可量化条件（严格判定）：
        1. constant_stats 中有 _final（MORE 乘数）或 _+%（INC 加成）的 stat 且有数值
        2. stat_sets.statMap 中的 stat 能匹配到量化类效果分类
           （damage_more/damage_added/speed/crit/aoe/chain/projectile/dot/conversion）
        
        不可量化的典型辅助：纯触发型（如 CastWhileChannelling）、纯工具型（如 Blasphemy）
        """
        # 量化效果分类集合（这些分类直接影响 DPS 或可数值化）
        quantifiable_categories = {
            'damage_more', 'damage_added', 'speed', 'crit', 'aoe',
            'chain', 'projectile', 'dot', 'conversion', 'cost_reduction',
        }
        
        # 检查 constant_stats 中是否有可量化的 stat
        constant_stats = support.get('constant_stats', [])
        if isinstance(constant_stats, list):
            for item in constant_stats:
                if isinstance(item, list) and len(item) >= 2:
                    stat_name = str(item[0])
                    value = item[1]
                    if value and value != 0:
                        # 用分类规则判断是否属于可量化分类
                        for pattern, cat, _ in _COMPILED_STAT_RULES:
                            if pattern.search(stat_name) and cat in quantifiable_categories:
                                return True
        
        # 检查 stat_sets.statMap 中的 stat 是否有可量化分类
        stat_sets = support.get('stat_sets', {})
        if isinstance(stat_sets, dict):
            stat_map = stat_sets.get('statMap', {})
            if isinstance(stat_map, dict):
                for stat_name in stat_map.keys():
                    for pattern, cat, _ in _COMPILED_STAT_RULES:
                        if pattern.search(stat_name) and cat in quantifiable_categories:
                            return True
        
        # 检查 stats（随等级变化的 stat）
        stats = support.get('stats', [])
        if isinstance(stats, list):
            for stat_name in stats:
                if isinstance(stat_name, str):
                    for pattern, cat, _ in _COMPILED_STAT_RULES:
                        if pattern.search(stat_name) and cat in quantifiable_categories:
                            return True
        
        return False
    
    def _extract_key_stats(self, support: Dict[str, Any],
                           categories: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        提取关键 stat 列表（含名称和数值）。
        
        三个数据源：
        1. constant_stats: 固定数值型 stat（如 [["stat", -30]]）
        2. stat_sets.levels: 随等级变化的数值型 stat
        3. stats: Flag 型 stat（纯字符串，通过 FLAG_SEMANTIC_MAP 查表）
        """
        key_stats = []
        
        # 收集已有的 stat 名称（用于去重）
        existing_stats: Set[str] = set()
        
        # === 数据源 1: constant_stats（固定数值型） ===
        constant_stats = support.get('constant_stats', [])
        if isinstance(constant_stats, list):
            for item in constant_stats:
                if isinstance(item, list) and len(item) >= 2:
                    stat_name = str(item[0])
                    value = item[1]
                    if value and value != 0:
                        # 确定该 stat 的效果分类
                        stat_cat = 'utility'
                        for pattern, cat, _ in _COMPILED_STAT_RULES:
                            if pattern.search(stat_name):
                                stat_cat = cat
                                break
                        
                        key_stats.append({
                            'stat': stat_name,
                            'value': value,
                            'category': stat_cat,
                            'source': 'constant',
                        })
                        existing_stats.add(stat_name)
        
        # 收集 constant_stats 中的 stat 名称（用于 Flag 去重）
        constant_stat_names = set()
        if isinstance(constant_stats, list):
            for item in constant_stats:
                if isinstance(item, list) and len(item) >= 1:
                    constant_stat_names.add(str(item[0]))
        
        # === 数据源 2: stat_sets.levels（等级成长型） ===
        stat_sets = support.get('stat_sets', {})
        if isinstance(stat_sets, dict):
            stat_map = stat_sets.get('statMap', {})
            levels_data = stat_sets.get('levels', {})
            
            if isinstance(stat_map, dict) and isinstance(levels_data, dict):
                stat_map_keys = list(stat_map.keys())
                
                level1 = levels_data.get('1', {})
                if isinstance(level1, dict):
                    values = level1.get('values', [])
                    if isinstance(values, list):
                        for i, val in enumerate(values):
                            if i < len(stat_map_keys) and val and val != 0:
                                stat_name = stat_map_keys[i]
                                if stat_name not in existing_stats:
                                    stat_cat = 'utility'
                                    for pattern, cat, _ in _COMPILED_STAT_RULES:
                                        if pattern.search(stat_name):
                                            stat_cat = cat
                                            break
                                    
                                    key_stats.append({
                                        'stat': stat_name,
                                        'value': val,
                                        'category': stat_cat,
                                        'source': 'stat_sets_level_1',
                                    })
                                    existing_stats.add(stat_name)
        
        # === 数据源 3: stats 字段中的 Flag 型 stat ===
        stats = support.get('stats', [])
        if isinstance(stats, list):
            for s in stats:
                if not isinstance(s, str):
                    continue
                # 跳过已在 constant_stats 或 stat_sets 中有数值的 stat
                if s in existing_stats or s in constant_stat_names:
                    continue
                
                # 查 FLAG_SEMANTIC_MAP（精确匹配 + global_ 前缀 fallback）
                flag_info = FLAG_SEMANTIC_MAP.get(s)
                if not flag_info and s.startswith('global_'):
                    # fallback: 去掉 global_ 前缀再查
                    flag_info = FLAG_SEMANTIC_MAP.get(s[len('global_'):])
                if flag_info:
                    key_stats.append({
                        'stat': s,
                        'value': None,  # Flag 型无数值
                        'category': flag_info['category'],
                        'source': 'flag',
                        'flag_desc': flag_info['desc'],
                        'polarity': flag_info['polarity'],
                    })
                    existing_stats.add(s)
        
        return key_stats
    
    def _build_formula_impact(self, categories: Dict[str, Dict[str, Any]],
                              key_stats: Optional[List[Dict[str, Any]]] = None,
                              display_stats: Optional[List[str]] = None) -> str:
        """
        构建公式影响描述（含正面/负面数值区分 + Flag 型限制 + _per_ 叠加上下文）。
        
        输出格式示例:
          [damage_more] 伤害独立乘区 (MORE +40%) | [chain] 连锁次数 (+1, LESS -30%)
          [damage_more] 伤害独立乘区 (MORE +40%) | ⚠️ 不能造成元素异常
          [damage_more] 伤害独立乘区 (MORE +12% per elemental type, desc: "12% more Elemental Damage for each Skill used Recently of a different Elemental type")
        """
        if not categories and not key_stats:
            return '无直接公式影响'
        
        # 构建 stat→value 映射（用于在描述中注入具体数值）
        stat_values: Dict[str, Any] = {}
        flag_items: List[Dict[str, Any]] = []  # Flag 型条目
        if key_stats:
            for ks in key_stats:
                if ks.get('source') == 'flag':
                    flag_items.append(ks)
                else:
                    stat_values[ks.get('stat', '')] = ks.get('value')
        
        # 预处理 display_stats：为 _per_ stat 查找对应的描述文本
        per_stat_context = self._find_per_stat_context(stat_values, display_stats)
        
        impacts = []
        for cat, info in sorted(categories.items(), key=lambda x: -x[1]['count']):
            formula_impacts = info.get('formula_impacts', set())
            if not formula_impacts:
                continue
            
            # 收集该分类下各 stat 的数值注释（去重）
            value_notes = []
            seen_stats = set()
            for stat_name in info.get('stats', []):
                if stat_name in seen_stats:
                    continue
                seen_stats.add(stat_name)
                val = stat_values.get(stat_name)
                if val is not None and val != 0:
                    if isinstance(val, (int, float)):
                        stat_lower_fi = stat_name.lower()
                        if '_more_times' in stat_lower_fi or '_more_time' in stat_lower_fi:
                            # 乘法语义：val=1 → 100% more (翻倍)
                            pct = int(val * 100)
                            note = f"MORE +{pct}% times"
                            value_notes.append(note)
                        elif 'final' in stat_name.lower():
                            label = 'MORE' if val > 0 else 'LESS'
                            note = f"{label} {val:+g}%"
                            # 附加叠加上下文（如 "per elemental type, up to 36%"）
                            ctx = per_stat_context.get(stat_name)
                            if ctx:
                                note += f" {ctx}"
                            value_notes.append(note)
                        else:
                            note = f"{val:+g}"
                            ctx = per_stat_context.get(stat_name)
                            if ctx:
                                note += f" {ctx}"
                            value_notes.append(note)
            
            desc = '; '.join(formula_impacts)
            if value_notes:
                desc += f" ({', '.join(value_notes)})"
            impacts.append(f"[{cat}] {desc}")
        
        # 附加 Flag 型限制/效果
        for flag in flag_items:
            polarity = flag.get('polarity', 'mechanic')
            flag_desc = flag.get('flag_desc', flag.get('stat', ''))
            if polarity == 'restriction':
                impacts.append(f"⚠️ {flag_desc}")
            elif polarity == 'benefit':
                impacts.append(f"✅ {flag_desc}")
            else:
                impacts.append(f"🔧 {flag_desc}")
        
        return ' | '.join(impacts) if impacts else '无直接公式影响'
    
    def _find_per_stat_context(self, stat_values: Dict[str, Any],
                                display_stats: Optional[List[str]]) -> Dict[str, str]:
        """
        为含 _per_ 的 stat 从 display_stats 中提取叠加上下文注释。
        
        策略：
        1. 筛选 stat_values 中含 '_per_' 的 stat 名
        2. 从 stat 名中提取关键词（去掉 support_/active_skill_ 前缀，按 _ 切分）
        3. 在 display_stats 中找到最匹配的描述行
        4. 从描述中提取 "for each ..." / "per ..." / "up to ..." 等叠加上下文短语
        
        Returns:
            {stat_name: context_str} 例如 {"support_elemental_damage_+%_final_per_different_...": "per elemental type — \"12% more Elemental Damage for each...\""}
        """
        if not display_stats or not isinstance(display_stats, list):
            return {}
        
        result: Dict[str, str] = {}
        
        for stat_name, val in stat_values.items():
            if '_per_' not in stat_name:
                continue
            
            # 从 stat 名中提取数值的绝对值（用于在 display_stats 中匹配）
            abs_val_str = str(abs(int(val))) if isinstance(val, (int, float)) and val == int(val) else str(abs(val)) if isinstance(val, (int, float)) else None
            
            # 尝试在 display_stats 中找到对应描述
            best_desc = None
            best_score = 0
            
            # 从 stat 名提取关键词（去掉前缀和 _per_ 后面的部分取其之前的核心词）
            stat_lower = stat_name.lower()
            for prefix in ('support_', 'active_skill_'):
                stat_lower = stat_lower.replace(prefix, '', 1) if stat_lower.startswith(prefix) else stat_lower
            
            # 提取 _per_ 之后的短语作为条件关键词
            per_idx = stat_lower.find('_per_')
            per_condition = stat_lower[per_idx + 5:] if per_idx >= 0 else ''  # e.g. "different_elemental_skill_used_recently"
            per_words = set(per_condition.replace('_', ' ').split())  # e.g. {"different", "elemental", "skill", "used", "recently"}
            
            for ds in display_stats:
                if not isinstance(ds, str):
                    continue
                ds_clean = ds.replace('\n', ' ').lower()
                score = 0
                
                # 数值匹配
                if abs_val_str and abs_val_str + '%' in ds_clean:
                    score += 3
                elif abs_val_str and abs_val_str in ds_clean:
                    score += 1
                
                # "per" 或 "for each" 在描述中出现
                if ' per ' in ds_clean or 'for each' in ds_clean or 'every ' in ds_clean:
                    score += 2
                
                # per 条件关键词匹配
                matched_words = sum(1 for w in per_words if w in ds_clean and len(w) > 2)
                score += matched_words
                
                if score > best_score:
                    best_score = score
                    best_desc = ds.replace('\n', ' ').strip()
            
            # 只在足够匹配时附加（避免错误关联）
            if best_desc and best_score >= 3:
                # 提取叠加上下文片段
                context = self._extract_stacking_phrase(best_desc)
                if context:
                    result[stat_name] = context
        
        return result
    
    def _extract_stacking_phrase(self, desc: str) -> str:
        """
        从 display_stats 描述中提取叠加上下文短语。
        
        提取模式：
        - "for each X" → "for each X"
        - "per X" → "per X"  
        - "up to X%" → "up to X%"
        - "every X seconds" → "every X seconds"
        
        返回压缩的上下文字符串。
        """
        desc_lower = desc.lower()
        
        fragments = []
        
        # 提取 "for each ..." 片段
        for pattern_str in (r'for each\b[^,;]*', r'\bper\b[^,;]*'):
            m = re.search(pattern_str, desc_lower)
            if m:
                frag = m.group(0).strip()
                # 限制长度避免过长
                if len(frag) > 80:
                    frag = frag[:77] + '...'
                fragments.append(frag)
                break  # 取第一个匹配
        
        # 提取 "up to X%" 片段
        m = re.search(r'up to [\d,.]+%?', desc_lower)
        if m:
            fragments.append(m.group(0).strip())
        
        if fragments:
            return '(' + ', '.join(fragments) + ')'
        
        return ''
    
    def _resolve_per_cap(self, stat_name: str, per_value: float,
                         support: Dict[str, Any]) -> Dict[str, Any]:
        """
        为含 _per_ 的 stat 解析 cap（最大叠加层数/上限百分比）。
        
        三类 Cap 规则：
        - Type A (伴随 cap stat): constant_stats 中存在 max_XXX/maximum_XXX stat
          → max = per_value × cap_stat_value
        - Type B (display "up to N%"): display_stats 包含 "up to N%"
          → max = N%
        - Type C (无 cap): 使用 PER_STAT_MAX_HEURISTIC 查找表
          → max = per_value × heuristic_max_stacks
        
        Returns:
            {
                'cap_type': 'A'|'B'|'C',
                'per_value': float,         # 每层值
                'max_stacks': int|None,     # 最大层数（Type A/C）
                'max_value': float,         # 最大百分比值
                'cap_source': str,          # cap 数据来源说明
            }
        """
        abs_per = abs(per_value)
        
        # === Type B (优先): display_stats 中的 "up to N%" ===
        # display_stats 是 GGG 官方描述，语义权威性最高，优先于 stat 名推断
        display_stats = support.get('display_stats', [])
        if isinstance(display_stats, list):
            for ds in display_stats:
                if not isinstance(ds, str):
                    continue
                ds_lower = ds.replace('\n', ' ').lower()
                
                # 确保这条 display_stat 与当前 _per_ stat 相关
                # 用数值匹配 + per/each 关键词
                abs_val_str = str(int(abs_per)) if abs_per == int(abs_per) else str(abs_per)
                if abs_val_str not in ds_lower:
                    continue
                if not (' per ' in ds_lower or 'for each' in ds_lower or 'every ' in ds_lower):
                    continue
                
                # 提取 "up to N%" 
                m = re.search(r'up to (\d+(?:\.\d+)?)(%)?', ds_lower)
                if m:
                    cap_num = float(m.group(1))
                    has_percent = m.group(2) is not None
                    
                    if has_percent:
                        # "up to 45%" → max = 45%
                        max_value = cap_num
                        max_stacks = int(max_value / abs_per) if abs_per > 0 else None
                    else:
                        # "up to 40" (无%) → 同样是百分比上限
                        # 因为 display 上下文是 "X% more ... up to N"，
                        # N 是 X% 累计的百分比上限（POB 中对应 limitTotal=true）
                        # 例: Arakaali's "8% more ... up to 40" → max 40% MORE
                        max_value = cap_num
                        max_stacks = int(max_value / abs_per) if abs_per > 0 else None
                    
                    return {
                        'cap_type': 'B',
                        'per_value': per_value,
                        'max_stacks': max_stacks,
                        'max_value': max_value,
                        'cap_source': f'display: "up to {m.group(0)}"',
                    }
        
        # === Type A: 伴随 cap stat (仅在 display 无 "up to" 时生效) ===
        constant_stats = support.get('constant_stats', [])
        if isinstance(constant_stats, list):
            # 提取 _per_ 前面的 stat 前缀来匹配伴随 cap
            # 例如 support_cadence_attack_speed_+%_per_use_recently → 找 maximum_stacks
            stat_lower = stat_name.lower()
            per_idx = stat_lower.find('_per_')
            if per_idx >= 0:
                per_condition = stat_lower[per_idx + 5:]  # e.g. "poison_stack"
                
                for item in constant_stats:
                    if not isinstance(item, list) or len(item) < 2:
                        continue
                    cs_name = str(item[0]).lower()
                    cs_val = item[1]
                    
                    if not isinstance(cs_val, (int, float)) or cs_val <= 0:
                        continue
                    
                    # 匹配模式：max_XXX / maximum_XXX / XXX_cap 
                    # 条件关键词必须在 cap stat 名中出现
                    is_cap_stat = False
                    
                    # max_poison_stacks, maximum_number_of_combo_stacks, etc.
                    if ('max' in cs_name or 'maximum' in cs_name) and cs_name != stat_lower:
                        # 检查条件关键词重叠
                        per_words = set(per_condition.replace('_', ' ').split())
                        cap_words = set(cs_name.replace('_', ' ').split())
                        overlap = per_words & cap_words - {'per', 'final', 'support', 'stack', 'stacks'}
                        if overlap or per_condition in cs_name or any(w in cs_name for w in per_words if len(w) > 3):
                            is_cap_stat = True
                    
                    # XXX_cap pattern (e.g. support_channelling_damage_cap)
                    if cs_name.endswith('_cap') and cs_name != stat_lower:
                        is_cap_stat = True
                    
                    if is_cap_stat:
                        # Type A 走到这里，说明 display_stats 中没有 "up to" 信息
                        # 此时 cap stat 值一律视为层数上限（stack count）
                        # 例: Cadence maximum_stacks=6 → 6 stacks × 8% = 48%
                        #     Culmination maximum_number_of_combo_stacks=10 → 10 × 3% = 30%
                        max_stacks = int(cs_val)
                        max_value = abs_per * max_stacks
                        
                        return {
                            'cap_type': 'A',
                            'per_value': per_value,
                            'max_stacks': max_stacks,
                            'max_value': max_value,
                            'cap_source': f'伴随stat {item[0]}={cs_val} (层数)',
                        }
        
        # === Type C: 无 cap，使用启发式估值 ===
        stat_lower = stat_name.lower()
        per_idx = stat_lower.find('_per_')
        per_condition = stat_lower[per_idx + 5:] if per_idx >= 0 else ''
        
        best_max = None
        for key, max_stacks in PER_STAT_MAX_HEURISTIC.items():
            if key in per_condition:
                best_max = max_stacks
                break
        
        if best_max is None:
            # 通用 fallback: per_condition 中取最后一部分词
            best_max = 5  # 保守默认
        
        max_value = abs_per * best_max
        return {
            'cap_type': 'C',
            'per_value': per_value,
            'max_stacks': best_max,
            'max_value': max_value,
            'cap_source': f'启发式估值 (max {best_max} stacks)',
        }
    
    def _compute_multipliers(self, key_stats: List[Dict[str, Any]],
                             support: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        为辅助宝石计算分维度期望倍率（预计算阶段）。
        
        5 个维度：
        1. damage: _final damage stats → MORE/LESS 乘积
        2. speed: _final speed stats → MORE/LESS 乘积
        3. coverage_add: chain/projectile 的增减量（动态 coverage 在 kb_query 中算）
        4. crit_notes: 暴击相关标注（不计入倍率）
        5. notes: 其他注释（damage_added, conversion, AoE 等）
        
        _per_ stat 的处理：
        - min = 1层时的 MORE/LESS
        - max = 满 cap 时的 MORE/LESS
        
        Returns:
            {
                'damage': {'min': float, 'max': float, 'details': [...]},
                'speed': {'min': float, 'max': float, 'details': [...]},
                'coverage_add': {'chains': int, 'projectiles': int},
                'crit_notes': [...],
                'notes': [...],
            }
            或 None（如果没有可量化的倍率 stat）
        """
        if not key_stats:
            return None
        
        damage_mores_min: List[float] = []  # 1层 MORE 值列表
        damage_mores_max: List[float] = []  # 满cap MORE 值列表
        damage_details: List[Dict[str, Any]] = []
        
        speed_mores_min: List[float] = []
        speed_mores_max: List[float] = []
        speed_details: List[Dict[str, Any]] = []
        
        coverage_chains = 0
        coverage_chains_more = 0.0  # 乘法连锁 (如 chains_hit_X_more_times = 1 → 100% more)
        coverage_projectiles = 0
        
        crit_notes: List[str] = []
        notes: List[str] = []
        
        for ks in key_stats:
            stat = ks.get('stat', '')
            val = ks.get('value')
            cat = ks.get('category', 'utility')
            source = ks.get('source', '')
            
            # Flag 型 stat 不参与倍率计算
            if source == 'flag':
                polarity = ks.get('polarity', 'mechanic')
                flag_desc = ks.get('flag_desc', stat)
                if cat == 'crit':
                    crit_notes.append(flag_desc)
                elif polarity == 'restriction':
                    notes.append(f"⚠️ {flag_desc}")
                elif polarity == 'benefit':
                    notes.append(f"✅ {flag_desc}")
                continue
            
            if val is None or val == 0:
                continue
            
            if not isinstance(val, (int, float)):
                continue
            
            stat_lower = stat.lower()
            is_final = 'final' in stat_lower
            is_per = '_per_' in stat_lower
            
            # === damage _final (MORE/LESS) ===
            if is_final and cat in ('damage_more', 'dot'):
                if is_per:
                    cap_info = self._resolve_per_cap(stat, val, support)
                    # min = 1 层, max = 满 cap
                    min_val = val
                    max_val = cap_info['max_value'] if val > 0 else -cap_info['max_value']
                    
                    damage_mores_min.append(min_val)
                    damage_mores_max.append(max_val)
                    damage_details.append({
                        'stat': stat,
                        'per_value': val,
                        'cap': cap_info,
                        'type': 'per_stack',
                    })
                else:
                    damage_mores_min.append(val)
                    damage_mores_max.append(val)
                    damage_details.append({
                        'stat': stat,
                        'value': val,
                        'type': 'fixed',
                    })
            
            # === speed _final (MORE/LESS) ===
            elif is_final and cat == 'speed':
                if is_per:
                    cap_info = self._resolve_per_cap(stat, val, support)
                    min_val = val
                    max_val = cap_info['max_value'] if val > 0 else -cap_info['max_value']
                    
                    speed_mores_min.append(min_val)
                    speed_mores_max.append(max_val)
                    speed_details.append({
                        'stat': stat,
                        'per_value': val,
                        'cap': cap_info,
                        'type': 'per_stack',
                    })
                else:
                    speed_mores_min.append(val)
                    speed_mores_max.append(val)
                    speed_details.append({
                        'stat': stat,
                        'value': val,
                        'type': 'fixed',
                    })
            
            # === chain (coverage) ===
            elif cat == 'chain' and 'number_of_chains' in stat_lower:
                coverage_chains += int(val)
            elif cat == 'chain' and ('_more_times' in stat_lower or '_more_time' in stat_lower):
                # 乘法连锁: chains_hit_X_more_times = N → N × 100% more chains
                # 例: chains_hit_X_more_times = 1 → 100% more chain times (翻倍)
                coverage_chains_more += float(val)
            elif cat == 'chain' and is_final:
                # chain damage penalty (e.g. -30% per chain)
                # 这个是 damage penalty，算在 damage
                damage_mores_min.append(val)
                damage_mores_max.append(val)
                damage_details.append({
                    'stat': stat,
                    'value': val,
                    'type': 'fixed',
                })
            
            # === projectile (coverage) ===
            elif cat == 'projectile' and ('number_of' in stat_lower or 'additional' in stat_lower):
                coverage_projectiles += int(val)
            
            # === crit (标注不估) ===
            elif cat == 'crit':
                if is_final:
                    label = 'MORE' if val > 0 else 'LESS'
                    crit_notes.append(f"{label} {val:+g}% crit")
                else:
                    crit_notes.append(f"{val:+g} crit")
            
            # === damage_added, conversion, aoe 等 → notes ===
            elif cat == 'damage_added':
                notes.append(f"附加伤害 {val:+g}")
            elif cat == 'conversion':
                notes.append(f"伤害转换 {val:+g}%")
            elif cat == 'aoe':
                if is_final:
                    notes.append(f"AoE {'MORE' if val > 0 else 'LESS'} {val:+g}%")
                else:
                    notes.append(f"AoE {val:+g}%")
            elif cat == 'speed' and not is_final:
                # INC speed → 标注不乘
                notes.append(f"INC 速度 {val:+g}%")
        
        # 计算乘积倍率
        def multiply_mores(mores: List[float]) -> float:
            """计算 MORE 乘积: Π(1 + value/100)"""
            result = 1.0
            for m in mores:
                result *= (1.0 + m / 100.0)
            return round(result, 4)
        
        damage_min = multiply_mores(damage_mores_min)
        damage_max = multiply_mores(damage_mores_max)
        speed_min = multiply_mores(speed_mores_min)
        speed_max = multiply_mores(speed_mores_max)
        
        # 如果所有维度都是 1.0（无变化），且无 coverage/crit/notes → 返回 None
        has_effect = (
            damage_min != 1.0 or damage_max != 1.0 or
            speed_min != 1.0 or speed_max != 1.0 or
            coverage_chains != 0 or coverage_chains_more != 0 or
            coverage_projectiles != 0 or
            crit_notes or notes
        )
        
        if not has_effect:
            return None
        
        result: Dict[str, Any] = {}
        
        if damage_min != 1.0 or damage_max != 1.0 or damage_details:
            result['damage'] = {
                'min': damage_min,
                'max': damage_max,
                'details': damage_details,
            }
        
        if speed_min != 1.0 or speed_max != 1.0 or speed_details:
            result['speed'] = {
                'min': speed_min,
                'max': speed_max,
                'details': speed_details,
            }
        
        if coverage_chains != 0 or coverage_chains_more != 0 or coverage_projectiles != 0:
            cov: Dict[str, Any] = {
                'chains': coverage_chains,
                'projectiles': coverage_projectiles,
            }
            if coverage_chains_more != 0:
                # chains_more: 乘法系数 (1 = 100% more → ×2.0)
                cov['chains_more'] = coverage_chains_more
            result['coverage_add'] = cov
        
        if crit_notes:
            result['crit_notes'] = crit_notes
        
        if notes:
            result['notes'] = notes
        
        return result
    
    def _extract_level_scaling(self, support: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        提取辅助宝石的等级成长关键点。
        
        从 stat_sets.levels 中提取 1/10/20 级的数值。
        stat_sets.levels 的格式：
        {
            "1": {"values": [50, 10], ...},
            "10": {"values": [46, 10], ...},
            "20": {"values": [41, 10], ...},
        }
        
        关联 stat_sets.statMap 的 key 顺序来确定每个 value 对应的 stat。
        """
        stat_sets = support.get('stat_sets', {})
        if not isinstance(stat_sets, dict):
            return None
        
        stat_map = stat_sets.get('statMap', {})
        levels_data = stat_sets.get('levels', {})
        
        if not isinstance(stat_map, dict) or not isinstance(levels_data, dict):
            return None
        
        stat_map_keys = list(stat_map.keys())
        if not stat_map_keys:
            return None
        
        target_levels = ['1', '10', '20']
        scaling = {}
        
        for level_str in target_levels:
            level_info = levels_data.get(level_str)
            if not isinstance(level_info, dict):
                continue
            
            values = level_info.get('values', [])
            if not isinstance(values, list):
                continue
            
            level_data = {}
            for i, val in enumerate(values):
                if i < len(stat_map_keys):
                    stat_name = stat_map_keys[i]
                    level_data[stat_name] = val
            
            if level_data:
                scaling[f"level_{level_str}"] = level_data
        
        return scaling if scaling else None
    
    # ============================================================
    # 5.6: 通用 stat qualifier 提取 + 语义限制
    # ============================================================
    @staticmethod
    def _extract_stat_qualifiers(stat_name: str) -> Dict[str, Set[str]]:
        """
        从 _final stat 名称中提取三维度 qualifier。
        
        通过分词后匹配已知词典，自动识别 stat 的伤害类型/攻击模式/伤害范畴限定。
        
        Args:
            stat_name: stat 名称（如 'physical_damage_+%_final'、'spell_hit_damage_+%_final'）
        
        Returns:
            {
                'damage_types': {'physical'},
                'attack_modes': {'spell'},
                'damage_scopes': {'hit'},
            }
        """
        lower = stat_name.lower()
        # 去除常见前缀和后缀，提取有意义的单词
        for prefix in ('support_', 'active_skill_', 'base_'):
            if lower.startswith(prefix):
                lower = lower[len(prefix):]
        
        # 分词（按 _ 拆分）
        tokens = set(lower.replace('+%', '').replace('%', '').split('_'))
        # 也检查组合词（如 damage_over_time 作为整体）
        combined = lower.replace('+%', '').replace('%', '')
        
        result: Dict[str, Set[str]] = {
            'damage_types': set(),
            'attack_modes': set(),
            'damage_scopes': set(),
        }
        
        for word in DAMAGE_TYPE_WORDS:
            if word in tokens or word in combined:
                result['damage_types'].add(word)
        
        for word in ATTACK_MODE_WORDS:
            if word in tokens or word in combined:
                result['attack_modes'].add(word)
        
        for word in DAMAGE_SCOPE_WORDS:
            if word in tokens:
                result['damage_scopes'].add(word)
            elif word.replace('_', '') in combined.replace('_', ''):
                # 处理 'damage_over_time' 的组合匹配
                result['damage_scopes'].add(word)
        
        return result
    
    def _extract_restrictions(self, support: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        从辅助宝石的所有 stat 中提取语义限制信息。
        
        扫描两类 stat：
        1. _final stat → requires（辅助增益的适用维度）
        2. Flag stat (deal_no_*, cannot_*) → blocks（辅助带来的伤害阻断）
        
        Returns:
            {
                'requires': {
                    'damage_types': ['physical'],
                    'attack_modes': ['melee'],
                    'damage_scopes': ['hit'],
                },
                'blocks': {
                    'damage_types': ['elemental', 'fire', 'cold', 'lightning'],
                    'ailments': ['ignite', 'burning'],
                },
            }
            或 None（如果没有任何限制信息）
        """
        requires_damage_types: Set[str] = set()
        requires_attack_modes: Set[str] = set()
        requires_damage_scopes: Set[str] = set()
        blocks_damage_types: Set[str] = set()
        blocks_ailments: Set[str] = set()
        
        # === 扫描所有 stat 名称 ===
        all_stat_names = self._collect_support_stats(support)
        
        for stat_name in all_stat_names:
            lower = stat_name.lower()
            
            # 1. _final stat → 提取 requires 维度
            if 'final' in lower:
                qualifiers = self._extract_stat_qualifiers(stat_name)
                requires_damage_types |= qualifiers['damage_types']
                requires_attack_modes |= qualifiers['attack_modes']
                requires_damage_scopes |= qualifiers['damage_scopes']
        
        # === 扫描 Flag stat → blocks ===
        stats = support.get('stats', [])
        if isinstance(stats, list):
            for s in stats:
                if not isinstance(s, str):
                    continue
                s_lower = s.lower()
                # 去掉 global_ 前缀统一匹配
                s_normalized = s_lower
                if s_normalized.startswith('global_'):
                    s_normalized = s_normalized[7:]
                
                for flag_key, blocked_set in BLOCK_FLAG_MAP.items():
                    flag_normalized = flag_key.lower()
                    if flag_normalized.startswith('global_'):
                        flag_normalized = flag_normalized[7:]
                    
                    if s_normalized == flag_normalized or s_lower == flag_key:
                        # 区分被阻断的是伤害类型还是异常状态
                        for b in blocked_set:
                            if b in DAMAGE_TYPE_WORDS:
                                blocks_damage_types.add(b)
                            else:
                                blocks_ailments.add(b)
        
        # 构建结果
        has_requires = requires_damage_types or requires_attack_modes or requires_damage_scopes
        has_blocks = blocks_damage_types or blocks_ailments
        
        if not has_requires and not has_blocks:
            return None
        
        result: Dict[str, Any] = {}
        
        if has_requires:
            req: Dict[str, List[str]] = {}
            if requires_damage_types:
                req['damage_types'] = sorted(requires_damage_types)
            if requires_attack_modes:
                req['attack_modes'] = sorted(requires_attack_modes)
            if requires_damage_scopes:
                req['damage_scopes'] = sorted(requires_damage_scopes)
            result['requires'] = req
        
        if has_blocks:
            blk: Dict[str, List[str]] = {}
            if blocks_damage_types:
                blk['damage_types'] = sorted(blocks_damage_types)
            if blocks_ailments:
                blk['ailments'] = sorted(blocks_ailments)
            result['blocks'] = blk
        
        return result
    
    # ============================================================
    # 5.4: 潜力推荐
    # ============================================================
    def compute_potentials(self):
        """
        为不可量化但机制适配的辅助-技能组合生成潜力推荐。
        
        推荐逻辑：
        1. 必须已经是兼容的（在 support_compatibility 中）
        2. 辅助不可量化（quantifiable=False）或者有独特机制协同
        3. 满足某条 MECHANIC_SYNERGY_RULES 规则
        """
        print("生成潜力推荐...")
        
        # 构建兼容矩阵的快速查找集合
        compatible_pairs: Set[Tuple[str, str]] = set()
        for comp in self._compatibility:
            if comp['compatible']:
                compatible_pairs.add((comp['skill_id'], comp['support_id']))
        
        self._potentials = []
        
        for support in self._supports:
            support_id = support['id']
            support_stats = self._collect_support_stats(support)
            support_stats_str = ' '.join(support_stats).lower()
            effect_info = self._effects.get(support_id, {})
            
            for skill in self._active_skills:
                skill_id = skill['id']
                
                # 必须兼容
                if (skill_id, support_id) not in compatible_pairs:
                    continue
                
                skill_types_set = skill['_skill_types_set']
                
                # 检查每条协同规则
                for rule in MECHANIC_SYNERGY_RULES:
                    stat_pattern = rule['support_has_stat']
                    required_types = rule['skill_has_type']
                    
                    # 辅助的 stat 必须匹配规则的模式
                    has_stat_match = stat_pattern.search(support_stats_str)
                    # 技能必须有规则要求的标签
                    has_type_match = required_types.intersection(skill_types_set)
                    
                    if has_stat_match and has_type_match:
                        self._potentials.append({
                            'skill_id': skill_id,
                            'support_id': support_id,
                            'synergy_type': rule['synergy_type'],
                            'potential_reason': rule['reason'],
                        })
                        break  # 每对只取第一条匹配的规则
        
        # 统计
        synergy_dist = defaultdict(int)
        for p in self._potentials:
            synergy_dist[p['synergy_type']] += 1
        
        print(f"  潜力推荐: {len(self._potentials)} 条")
        print(f"  协同类型分布: {dict(sorted(synergy_dist.items(), key=lambda x: -x[1]))}")
    
    # ============================================================
    # 导出到数据库
    # ============================================================
    def export_to_db(self, db_path: str):
        """导出三张表到 supports.db"""
        print(f"导出到 {db_path}...")
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 创建 support_compatibility 表
        cursor.execute('DROP TABLE IF EXISTS support_compatibility')
        cursor.execute('''
            CREATE TABLE support_compatibility (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                skill_id TEXT NOT NULL,
                support_id TEXT NOT NULL,
                compatible INTEGER NOT NULL DEFAULT 1,
                match_reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(skill_id, support_id)
            )
        ''')
        
        # 创建 support_effects 表
        cursor.execute('DROP TABLE IF EXISTS support_effects')
        cursor.execute('''
            CREATE TABLE support_effects (
                support_id TEXT PRIMARY KEY,
                support_name TEXT NOT NULL,
                effect_category TEXT NOT NULL DEFAULT 'utility',
                quantifiable INTEGER NOT NULL DEFAULT 0,
                key_stats TEXT,
                formula_impact TEXT,
                level_scaling TEXT,
                multipliers TEXT,
                restrictions TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 创建 support_potential 表
        cursor.execute('DROP TABLE IF EXISTS support_potential')
        cursor.execute('''
            CREATE TABLE support_potential (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                skill_id TEXT NOT NULL,
                support_id TEXT NOT NULL,
                synergy_type TEXT NOT NULL DEFAULT 'mechanic_match',
                potential_reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(skill_id, support_id)
            )
        ''')
        
        # 创建索引
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_compat_skill ON support_compatibility(skill_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_compat_support ON support_compatibility(support_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_effects_category ON support_effects(effect_category)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_potential_skill ON support_potential(skill_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_potential_support ON support_potential(support_id)')
        
        # 插入 support_compatibility（仅兼容的对）
        compat_count = 0
        for comp in self._compatibility:
            if comp['compatible']:
                cursor.execute('''
                    INSERT OR IGNORE INTO support_compatibility 
                    (skill_id, support_id, compatible, match_reason)
                    VALUES (?, ?, ?, ?)
                ''', (
                    comp['skill_id'],
                    comp['support_id'],
                    1,
                    comp.get('match_reason', ''),
                ))
                compat_count += 1
        
        # 插入 support_effects
        effects_count = 0
        for support_id, eff in self._effects.items():
            cursor.execute('''
                INSERT OR REPLACE INTO support_effects
                (support_id, support_name, effect_category, quantifiable, 
                 key_stats, formula_impact, level_scaling, multipliers, restrictions)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                support_id,
                eff.get('support_name', support_id),
                eff['effect_category'],
                1 if eff['quantifiable'] else 0,
                json.dumps(eff['key_stats'], ensure_ascii=False) if eff['key_stats'] else None,
                eff.get('formula_impact'),
                json.dumps(eff['level_scaling'], ensure_ascii=False) if eff['level_scaling'] else None,
                json.dumps(eff['multipliers'], ensure_ascii=False) if eff.get('multipliers') else None,
                json.dumps(eff['restrictions'], ensure_ascii=False) if eff.get('restrictions') else None,
            ))
            effects_count += 1
        
        # 插入 support_potential
        potential_count = 0
        for pot in self._potentials:
            cursor.execute('''
                INSERT OR IGNORE INTO support_potential
                (skill_id, support_id, synergy_type, potential_reason)
                VALUES (?, ?, ?, ?)
            ''', (
                pot['skill_id'],
                pot['support_id'],
                pot['synergy_type'],
                pot.get('potential_reason', ''),
            ))
            potential_count += 1
        
        conn.commit()
        conn.close()
        
        print(f"  support_compatibility: {compat_count} 条")
        print(f"  support_effects: {effects_count} 条")
        print(f"  support_potential: {potential_count} 条")
        
        return {
            'compatibility': compat_count,
            'effects': effects_count,
            'potentials': potential_count,
        }


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='辅助匹配预计算 v1')
    parser.add_argument('entities_db', help='entities.db 路径')
    parser.add_argument('--output', '-o', help='输出 supports.db 路径')
    
    args = parser.parse_args()
    
    matcher = SupportMatcher(args.entities_db)
    matcher.load_data()
    matcher.compute_compatibility()
    matcher.compute_effects()
    matcher.compute_potentials()
    
    if args.output:
        matcher.export_to_db(args.output)
    
    print("\n完成!")


if __name__ == '__main__':
    main()
