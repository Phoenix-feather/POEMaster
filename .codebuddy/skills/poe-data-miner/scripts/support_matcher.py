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
    # (正则模式, 效果分类, 公式影响描述)
    
    # MORE 伤害
    (r'damage_\+%_final', 'damage_more', 'AverageDamage 中的 more 乘数项'),
    (r'support_.*_damage_\+%_final', 'damage_more', 'AverageDamage 中的 support more 乘数项'),
    (r'active_skill_damage_\+%_final', 'damage_more', 'AverageDamage 中的 active skill more 乘数'),
    
    # 附加伤害
    (r'base_.*_damage', 'damage_added', 'AverageDamage 中的 base damage 加成'),
    (r'added_.*_damage', 'damage_added', 'AverageDamage 中的 added damage 加成'),
    (r'damage_effectiveness', 'damage_added', '附加伤害的效率系数'),
    
    # 速度
    (r'cast_speed', 'speed', 'CastRate / AttackRate 乘数'),
    (r'attack_speed', 'speed', 'AttackRate 乘数'),
    (r'speed_\+%', 'speed', 'CastRate 或 AttackRate 乘数'),
    
    # 范围
    (r'area_of_effect', 'aoe', 'AreaOfEffect 计算'),
    (r'area_radius', 'aoe', 'AreaRadius 加成'),
    
    # 连锁
    (r'chain', 'chain', 'ChainMax 增减 + 每次连锁衰减'),
    (r'number_of_chains', 'chain', 'ChainMax 增减'),
    
    # 投射物
    (r'projectile', 'projectile', 'ProjectileCount / ProjectileSpeed 修改'),
    (r'number_of_additional_projectiles', 'projectile', 'ProjectileCount 加成'),
    (r'fork', 'projectile', 'ForkMax 增加'),
    
    # 持续时间
    (r'duration', 'duration', 'Duration 乘数'),
    (r'skill_effect_duration', 'duration', 'Duration 乘数'),
    
    # 暴击
    (r'crit', 'crit', 'CritChance / CritMultiplier 修改'),
    (r'critical_strike', 'crit', 'CritChance / CritMultiplier 修改'),
    (r'cannot_crit', 'crit', '禁止暴击（CritChance 设为 0）'),
    
    # 持续伤害
    (r'damage_over_time', 'dot', 'DoT 伤害乘数'),
    (r'bleed|poison|ignite', 'dot', '异常状态 DoT 伤害'),
    
    # 触发
    (r'triggered_by', 'trigger', '触发机制（元技能）'),
    (r'trigger', 'trigger', '触发机制'),
    (r'cast_on_', 'trigger', '触发施放机制'),
    (r'invocation', 'trigger', '元技能触发机制'),
    
    # 召唤物
    (r'minion', 'minion', '召唤物属性修改'),
    (r'totem', 'minion', '图腾属性修改'),
    
    # 消耗减少
    (r'mana_cost', 'cost_reduction', 'Mana 消耗修改'),
    (r'spirit_cost', 'cost_reduction', 'Spirit 消耗修改'),
    (r'cost_\+%', 'cost_reduction', '消耗乘数修改'),
    
    # 转换
    (r'convert', 'conversion', '伤害类型转换'),
    (r'gain_.*_as', 'conversion', '额外获得伤害转换'),
    
    # 防御
    (r'life_gain', 'defense', '生命回复'),
    (r'energy_shield', 'defense', '能量护盾相关'),
    (r'block', 'defense', '格挡相关'),
    (r'armour', 'defense', '护甲相关'),
    (r'evasion', 'defense', '闪避相关'),
]

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
                   hidden, is_trigger, summary, key_mechanics
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
            'levels', 'key_mechanics'
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
            
            # 公式影响
            formula_impact = self._build_formula_impact(categories)
            
            # 等级成长（5.5）
            level_scaling = self._extract_level_scaling(support)
            
            self._effects[support_id] = {
                'support_id': support_id,
                'support_name': support.get('name', support_id),
                'effect_category': primary_category,
                'quantifiable': quantifiable,
                'key_stats': key_stats,
                'formula_impact': formula_impact,
                'level_scaling': level_scaling,
            }
        
        # 统计
        cat_dist = defaultdict(int)
        quant_count = 0
        has_scaling = 0
        for eff in self._effects.values():
            cat_dist[eff['effect_category']] += 1
            if eff['quantifiable']:
                quant_count += 1
            if eff['level_scaling']:
                has_scaling += 1
        
        print(f"  效果分类完成: {len(self._effects)} 个辅助")
        print(f"  可量化: {quant_count}/{len(self._effects)}")
        print(f"  有等级成长: {has_scaling}/{len(self._effects)}")
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
        """提取关键 stat 列表（含名称和数值）"""
        key_stats = []
        
        # 从 constant_stats 提取有数值的 stat
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
        
        # 从 stat_sets.levels 级别 1 中提取有数值的 stat
        stat_sets = support.get('stat_sets', {})
        if isinstance(stat_sets, dict):
            stat_map = stat_sets.get('statMap', {})
            levels_data = stat_sets.get('levels', {})
            
            if isinstance(stat_map, dict) and isinstance(levels_data, dict):
                # 获取 statMap 中的 stat 名称顺序
                stat_map_keys = list(stat_map.keys())
                
                # 取 level 1 的 values
                level1 = levels_data.get('1', {})
                if isinstance(level1, dict):
                    values = level1.get('values', [])
                    if isinstance(values, list):
                        for i, val in enumerate(values):
                            if i < len(stat_map_keys) and val and val != 0:
                                stat_name = stat_map_keys[i]
                                # 避免与 constant_stats 重复
                                existing = {ks['stat'] for ks in key_stats}
                                if stat_name not in existing:
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
        
        return key_stats
    
    def _build_formula_impact(self, categories: Dict[str, Dict[str, Any]]) -> str:
        """构建公式影响描述"""
        if not categories:
            return '无直接公式影响'
        
        impacts = []
        for cat, info in sorted(categories.items(), key=lambda x: -x[1]['count']):
            formula_impacts = info.get('formula_impacts', set())
            if formula_impacts:
                impacts.append(f"[{cat}] {'; '.join(formula_impacts)}")
        
        return ' | '.join(impacts) if impacts else '无直接公式影响'
    
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
                 key_stats, formula_impact, level_scaling)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                support_id,
                eff.get('support_name', support_id),
                eff['effect_category'],
                1 if eff['quantifiable'] else 0,
                json.dumps(eff['key_stats'], ensure_ascii=False) if eff['key_stats'] else None,
                eff.get('formula_impact'),
                json.dumps(eff['level_scaling'], ensure_ascii=False) if eff['level_scaling'] else None,
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
