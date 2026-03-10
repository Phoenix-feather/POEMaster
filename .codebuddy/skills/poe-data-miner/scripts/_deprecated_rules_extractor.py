#!/usr/bin/env python3
"""
POE规则提取模块
从SkillStatMap、stats组合、计算代码三层提取规则
"""

import re
import json
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
import sqlite3

# 尝试导入yaml
try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


@dataclass
class Rule:
    """规则数据结构"""
    id: str
    name: str
    category: str  # constraint, formula, condition, modifier
    condition: Optional[str] = None
    effect: Optional[str] = None
    formula: Optional[str] = None
    description: Optional[str] = None
    related_entities: List[str] = None
    source_file: Optional[str] = None
    source_layer: int = 0  # 1, 2, 3 表示来自哪一层
    
    def __post_init__(self):
        if self.related_entities is None:
            self.related_entities = []


class RulesExtractor:
    """规则提取器"""
    
    def __init__(self, db_path: str = None, config_path: str = None):
        """
        初始化规则提取器
        
        Args:
            db_path: SQLite数据库路径
            config_path: 配置文件路径
        """
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None
        self.config = self._load_config(config_path) if config_path else self._default_config()
        self.rules: List[Rule] = []
        self.rule_counter = 0
        
        if db_path:
            self._init_database()
    
    def _default_config(self) -> Dict:
        """默认配置"""
        return {
            'templates': [],
            'calculation_patterns': {
                'energy': {
                    'function_names': ['calcEnergyGeneration', 'calcEnergy', 'getEnergyGen'],
                    'key_patterns': ['Triggered', 'energy', 'baseEnergy']
                },
                'damage': {
                    'function_names': ['calcDamage', 'calcHitDamage', 'getDamageMod'],
                    'key_patterns': ['increased', 'more', 'multiplier']
                }
            }
        }
    
    def _load_config(self, config_path: str) -> Dict:
        """加载配置文件"""
        with open(config_path, 'r', encoding='utf-8') as f:
            if HAS_YAML:
                return yaml.safe_load(f)
            else:
                return self._parse_simple_yaml(f.read())
    
    def _parse_simple_yaml(self, content: str) -> Dict:
        """简单YAML解析"""
        return {}
    
    def _init_database(self):
        """初始化数据库"""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()
    
    def _create_tables(self):
        """创建表结构"""
        cursor = self.conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS rules (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                condition TEXT,
                effect TEXT,
                formula TEXT,
                description TEXT,
                related_entities TEXT,
                source_file TEXT,
                source_layer INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        self.conn.commit()
    
    def extract_layer1_stats(self, entities: List[Dict[str, Any]]) -> List[Rule]:
        """
        Layer 1: 从stats组合提取实体属性
        
        Args:
            entities: 实体列表
            
        Returns:
            提取的规则列表
        """
        rules = []
        
        for entity in entities:
            entity_id = entity.get('id', '')
            entity_name = entity.get('name', entity_id)
            
            # 提取constantStats中的属性
            constant_stats = entity.get('constant_stats', [])
            for stat in constant_stats:
                if isinstance(stat, (list, tuple)) and len(stat) >= 2:
                    stat_name = stat[0]
                    stat_value = stat[1]
                    
                    rule = self._create_rule(
                        name=f"{entity_name} 基础属性: {stat_name}",
                        category="modifier",
                        condition=f"entity = '{entity_id}'",
                        effect=f"{stat_name} = {stat_value}",
                        description=f"{entity_name} 拥有基础属性 {stat_name} = {stat_value}",
                        related_entities=[entity_id],
                        source_layer=1
                    )
                    rules.append(rule)
            
            # 提取stats中的属性
            stats = entity.get('stats', [])
            for stat in stats:
                if isinstance(stat, str):
                    rule = self._create_rule(
                        name=f"{entity_name} 可变属性: {stat}",
                        category="modifier",
                        condition=f"entity = '{entity_id}'",
                        effect=f"has_stat: {stat}",
                        description=f"{entity_name} 拥有可变属性 {stat}",
                        related_entities=[entity_id],
                        source_layer=1
                    )
                    rules.append(rule)
            
            # 提取skillTypes
            skill_types = entity.get('skill_types', [])
            for skill_type in skill_types:
                rule = self._create_rule(
                    name=f"{entity_name} 技能类型: {skill_type}",
                    category="modifier",
                    condition=f"entity = '{entity_id}'",
                    effect=f"has_type: {skill_type}",
                    description=f"{entity_name} 拥有技能类型 {skill_type}",
                    related_entities=[entity_id],
                    source_layer=1
                )
                rules.append(rule)
        
        self.rules.extend(rules)
        return rules
    
    def extract_layer2_statmap(self, stat_mappings: List[Dict[str, Any]]) -> List[Rule]:
        """
        Layer 2: 从属性映射提取规则
        
        采用宽松匹配策略，适配多种数据格式:
        - stat_name / name / id 都可作为属性名
        - mods / mod_data 都可作为修饰列表
        """
        rules = []
        
        for mapping in stat_mappings:
            # 宽松匹配：尝试多种可能的字段名
            stat_name = (
                mapping.get('stat_name') or 
                mapping.get('name') or 
                mapping.get('id', '')
            )
            
            target = mapping.get('target')
            mapping_type = mapping.get('type')
            
            # 宽松匹配：mods 或 mod_data
            mods = mapping.get('mods') or mapping.get('mod_data') or []
            
            # 如果有 mod_data，提取其中的信息
            if isinstance(mods, list):
                for mod in mods:
                    if isinstance(mod, dict):
                        mod_type = mod.get('type', '')
                        mod_name = mod.get('name', '')
                        mod_value = mod.get('value', '')
                        
                        # 创建规则
                        if mod_name:
                            rule = self._create_rule(
                                name=f"属性修饰: {stat_name} -> {mod_name}",
                                category="modifier",
                                condition=f"stat = '{stat_name}'",
                                effect=f"{mod_type} {mod_name}" + (f" = {mod_value}" if mod_value else ""),
                                description=f"属性 {stat_name} 应用修饰 {mod_type}.{mod_name}",
                                source_layer=2
                            )
                            rules.append(rule)
            
            # 如果有 target，创建映射规则
            if target:
                rule = self._create_rule(
                    name=f"属性映射: {stat_name}",
                    category="modifier",
                    condition=f"stat = '{stat_name}'",
                    effect=f"modifies: {target}",
                    description=f"属性 {stat_name} 修饰 {target}",
                    source_layer=2
                )
                rules.append(rule)
        
        self.rules.extend(rules)
        return rules
    
    def extract_layer3_calccode(self, functions: List[Dict[str, Any]]) -> List[Rule]:
        """
        Layer 3: 从计算代码提取条件规则和公式
        
        Args:
            functions: 函数列表
            
        Returns:
            提取的规则列表
        """
        rules = []
        
        for func in functions:
            func_name = func.get('name', '')
            conditions = func.get('conditions', [])
            formulas = func.get('formulas', [])
            
            # 提取条件规则
            for cond in conditions:
                condition = cond.get('condition', '')
                action = cond.get('action', '')
                
                # 分析条件内容，识别规则类型
                rule_category = self._classify_condition(condition, action)
                
                rule = self._create_rule(
                    name=f"条件规则: {func_name}",
                    category=rule_category,
                    condition=condition,
                    effect=action,
                    description=f"在 {func_name} 中: 如果 {condition} 则 {action}",
                    source_layer=3
                )
                rules.append(rule)
            
            # 提取公式
            for formula in formulas:
                expression = formula.get('expression', '')
                
                if self._is_formula(expression):
                    rule = self._create_rule(
                        name=f"计算公式: {func_name}",
                        category="formula",
                        formula=expression,
                        description=f"在 {func_name} 中的计算: {expression}",
                        source_layer=3
                    )
                    rules.append(rule)
        
        self.rules.extend(rules)
        return rules
    
    def _create_rule(self, name: str, category: str, **kwargs) -> Rule:
        """创建规则"""
        self.rule_counter += 1
        rule_id = f"rule_{self.rule_counter:04d}"
        
        return Rule(
            id=rule_id,
            name=name,
            category=category,
            **kwargs
        )
    
    def _classify_condition(self, condition: str, action: str) -> str:
        """分类条件规则"""
        condition_lower = condition.lower()
        action_lower = action.lower()
        
        # 检查是否是阻止型规则
        if 'return 0' in action_lower or 'blocked' in action_lower:
            return 'constraint'
        
        # 检查是否包含限制关键字
        if any(kw in condition_lower for kw in ['triggered', 'cannot', 'blocked', 'limit']):
            return 'constraint'
        
        # 检查是否是触发型规则
        if any(kw in condition_lower for kw in ['when', 'on ', 'if ']):
            return 'condition'
        
        return 'modifier'
    
    def _is_formula(self, expression: str) -> bool:
        """
        判断是否是公式
        
        放宽过滤条件，避免遗漏重要的短公式和状态判断
        """
        if not expression or len(expression) <= 5:
            return False
        
        # 计算关键字
        calc_keywords = ['return', 'local', 'calc', 'sum', 'product', '*', '+', '-', '/']
        
        # 状态/条件关键字 (也很重要)
        state_keywords = ['if', 'then', 'else', 'true', 'false', 'nil', 'not', 'and', 'or']
        
        # 赋值关键字
        assign_keywords = ['=', '+=', '-=', '*=', '/=']
        
        # 函数调用
        func_keywords = ['function', 'call', 'invoke']
        
        # 判断是否包含任何关键字
        has_calc = any(kw in expression for kw in calc_keywords)
        has_state = any(kw in expression for kw in state_keywords)
        has_assign = any(kw in expression for kw in assign_keywords)
        has_func = any(kw in expression for kw in func_keywords)
        
        return has_calc or has_state or has_assign or has_func
    
    def save_rules_to_db(self):
        """保存规则到数据库"""
        if not self.conn:
            return
        
        cursor = self.conn.cursor()
        
        for rule in self.rules:
            cursor.execute('''
                INSERT OR REPLACE INTO rules 
                (id, name, category, condition, effect, formula, description, related_entities, source_file, source_layer)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                rule.id,
                rule.name,
                rule.category,
                rule.condition,
                rule.effect,
                rule.formula,
                rule.description,
                json.dumps(rule.related_entities, ensure_ascii=False),
                rule.source_file,
                rule.source_layer
            ))
        
        self.conn.commit()
    
    def get_rules_by_category(self, category: str) -> List[Dict[str, Any]]:
        """按类别获取规则"""
        if not self.conn:
            return []
        
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM rules WHERE category = ?', (category,))
        rows = cursor.fetchall()
        
        return [self._row_to_dict(row) for row in rows]
    
    def get_rules_for_entity(self, entity_id: str) -> List[Dict[str, Any]]:
        """获取与实体相关的规则"""
        if not self.conn:
            return []
        
        cursor = self.conn.cursor()
        pattern = f'%"{entity_id}"%'
        cursor.execute('SELECT * FROM rules WHERE related_entities LIKE ?', (pattern,))
        rows = cursor.fetchall()
        
        return [self._row_to_dict(row) for row in rows]
    
    def search_rules(self, query: str) -> List[Dict[str, Any]]:
        """搜索规则"""
        if not self.conn:
            return []
        
        cursor = self.conn.cursor()
        pattern = f'%{query}%'
        cursor.execute('''
            SELECT * FROM rules 
            WHERE name LIKE ? OR description LIKE ? OR condition LIKE ? OR effect LIKE ?
        ''', (pattern, pattern, pattern, pattern))
        rows = cursor.fetchall()
        
        return [self._row_to_dict(row) for row in rows]
    
    def get_rule_count(self) -> int:
        """获取规则数量"""
        if not self.conn:
            return len(self.rules)
        
        cursor = self.conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM rules')
        return cursor.fetchone()[0]
    
    def _row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        """将行转换为字典"""
        result = dict(row)
        
        if result.get('related_entities'):
            try:
                result['related_entities'] = json.loads(result['related_entities'])
            except json.JSONDecodeError:
                result['related_entities'] = []
        
        return result
    
    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()
            self.conn = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class EnergyRulesExtractor(RulesExtractor):
    """能量规则专用提取器"""
    
    def extract_energy_rules(self, functions: List[Dict[str, Any]]) -> List[Rule]:
        """提取能量相关规则"""
        rules = []
        
        for func in functions:
            func_name = func.get('name', '').lower()
            
            # 检查是否是能量相关函数
            if 'energy' in func_name or 'gen' in func_name:
                conditions = func.get('conditions', [])
                formulas = func.get('formulas', [])
                
                # 提取Triggered标签阻止能量生成的规则
                for cond in conditions:
                    condition = cond.get('condition', '')
                    action = cond.get('action', '')
                    
                    if 'Triggered' in condition:
                        rule = self._create_rule(
                            name="触发技能能量限制",
                            category="constraint",
                            condition="skill has SkillType.Triggered",
                            effect="energy generation blocked",
                            description="被触发的技能无法为元技能提供能量",
                            source_layer=3
                        )
                        rules.append(rule)
                
                # 提取能量公式
                for formula in formulas:
                    expression = formula.get('expression', '')
                    
                    # 检查是否是最终能量计算
                    if 'return' in expression and any(kw in expression for kw in ['base', 'inc', 'more']):
                        rule = self._create_rule(
                            name="能量获取公式",
                            category="formula",
                            formula="energy = base × (1 + Σinc) × Πmore",
                            description="能量获取公式: 基础值 × (1 + 加法叠加) × 乘法叠加",
                            source_layer=3
                        )
                        rules.append(rule)
        
        return rules


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='POE规则提取器')
    parser.add_argument('db_path', help='SQLite数据库路径')
    parser.add_argument('--entities', help='实体JSON文件路径')
    parser.add_argument('--stat-mappings', help='属性映射JSON文件路径')
    parser.add_argument('--functions', help='函数JSON文件路径')
    parser.add_argument('--query', '-q', help='搜索规则')
    parser.add_argument('--category', '-c', help='按类别查询')
    parser.add_argument('--entity', '-e', help='查询与实体相关的规则')
    parser.add_argument('--summary', action='store_true', help='显示摘要')
    
    args = parser.parse_args()
    
    with RulesExtractor(args.db_path) as extractor:
        # 提取规则
        if args.entities:
            with open(args.entities, 'r', encoding='utf-8') as f:
                entities = json.load(f)
            extractor.extract_layer1_stats(entities)
            print(f"Layer 1: 提取了 {len(extractor.rules)} 条规则")
        
        if args.stat_mappings:
            with open(args.stat_mappings, 'r', encoding='utf-8') as f:
                mappings = json.load(f)
            count_before = len(extractor.rules)
            extractor.extract_layer2_statmap(mappings)
            print(f"Layer 2: 提取了 {len(extractor.rules) - count_before} 条规则")
        
        if args.functions:
            with open(args.functions, 'r', encoding='utf-8') as f:
                functions = json.load(f)
            count_before = len(extractor.rules)
            extractor.extract_layer3_calccode(functions)
            print(f"Layer 3: 提取了 {len(extractor.rules) - count_before} 条规则")
        
        # 保存到数据库
        if extractor.rules:
            extractor.save_rules_to_db()
            print(f"总共保存了 {extractor.get_rule_count()} 条规则")
        
        # 查询
        if args.query:
            rules = extractor.search_rules(args.query)
            for rule in rules:
                print(f"- [{rule['category']}] {rule['name']}")
        
        if args.category:
            rules = extractor.get_rules_by_category(args.category)
            for rule in rules:
                print(f"- {rule['id']}: {rule['name']}")
        
        if args.entity:
            rules = extractor.get_rules_for_entity(args.entity)
            for rule in rules:
                print(f"- [{rule['category']}] {rule['name']}")
        
        # 显示摘要
        if args.summary:
            print(f"总规则数: {extractor.get_rule_count()}")


if __name__ == '__main__':
    main()
