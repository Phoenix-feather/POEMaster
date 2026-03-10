#!/usr/bin/env python3
"""
规则推导 Pipeline v2

从三层可信来源提取规则:
- S1 实体库: 实体依赖关系 → relation 规则
- S2 公式库: 公式参数依赖 → relation/formula_application 规则
- S3 代码层: 约束和绕过逻辑 → constraint/bypass 规则

核心原则:
- 所有数据来自可信来源，100% 确定
- 无描述性生成内容
- evidence 字段记录验证来源
"""

import sqlite3
import json
import re
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from datetime import datetime


@dataclass
class Rule:
    """规则数据结构"""
    id: str
    category: str  # constraint/bypass/relation/formula_application
    source_entity: Optional[str]
    target_entity: Optional[str]
    relation_type: Optional[str]
    condition: Optional[str]
    effect: Optional[str]
    evidence: str
    source_layer: int
    source_formula: Optional[str] = None
    heuristic_record_id: Optional[str] = None


class RulesExtractor:
    """规则推导器 - 从三层可信来源提取规则"""
    
    def __init__(self, knowledge_base_path: str):
        self.kb_path = Path(knowledge_base_path)
        self.entities_db = self.kb_path / 'entities.db'
        self.formulas_db = self.kb_path / 'formulas.db'
        self.rules_db = self.kb_path / 'rules.db'
        self.pob_path = self.kb_path.parent.parent.parent.parent / 'POBData'
        
        self.rules: List[Rule] = []
        self.stats = {
            'constraint': 0,
            'bypass': 0,
            'relation': 0,
            'formula_application': 0
        }
    
    def run(self):
        """运行完整 Pipeline"""
        print("=" * 70)
        print("规则推导 Pipeline v2")
        print("=" * 70)
        
        # Step 1: 从 S3 代码层提取 constraint 规则
        print("\n[Step 1] 从 S3 代码层提取 constraint 规则...")
        self._extract_constraint_rules()
        
        # Step 2: 从 S2 公式库提取 relation 规则
        print("\n[Step 2] 从 S2 公式库提取 relation 规则...")
        self._extract_relation_rules_from_formulas()
        
        # Step 3: 从 S1 实体库提取 relation 规则
        print("\n[Step 3] 从 S1 实体库提取 relation 规则...")
        self._extract_relation_rules_from_entities()
        
        # Step 4: 从 S2 公式库提取 formula_application 规则
        print("\n[Step 4] 从 S2 公式库提取 formula_application 规则...")
        self._extract_formula_application_rules()
        
        # Step 5: 入库
        print("\n[Step 5] 入库...")
        self._save_to_db()
        
        # 统计
        print("\n" + "=" * 70)
        print("统计")
        print("=" * 70)
        for category, count in self.stats.items():
            print(f"  {category}: {count}")
        print(f"  总计: {sum(self.stats.values())}")
    
    def _extract_constraint_rules(self):
        """从 S3 代码层提取 constraint 规则"""
        
        # 核心 constraint: Triggered 技能能量为 0
        # 来源: CalcTriggers.lua
        
        rule = Rule(
            id='constraint_triggered_energy_zero',
            category='constraint',
            source_entity='Triggered',
            target_entity='EnergyGeneration',
            relation_type='blocks',
            condition='skill.skillFlags.triggered == true',
            effect='energy = 0',
            evidence='CalcTriggers.lua:energy_triggered_zero',
            source_layer=3
        )
        self.rules.append(rule)
        self.stats['constraint'] += 1
        print(f"  ✓ 提取 constraint 规则: {rule.id}")
        
        # TODO: 从 CalcModules 提取更多 constraint 规则
        # 需要解析 if 条件语句
    
    def _extract_relation_rules_from_formulas(self):
        """从 S2 公式库提取 relation 规则"""
        
        if not self.formulas_db.exists():
            print("  ⚠ 公式库不存在")
            return
        
        conn = sqlite3.connect(str(self.formulas_db))
        cursor = conn.cursor()
        
        # 查询 gap_formulas
        cursor.execute('''
            SELECT id, entity_id, entity_name, formula_type, parameters
            FROM gap_formulas
        ''')
        
        for row in cursor.fetchall():
            formula_id, entity_id, entity_name, formula_type, params_json = row
            
            if not entity_id:
                continue
            
            # 解析参数
            try:
                params = json.loads(params_json) if params_json else {}
            except:
                continue
            
            # 从参数中提取依赖关系
            for param_name, param_info in params.items():
                if isinstance(param_info, dict) and 'sources' in param_info:
                    sources = param_info['sources']
                    if isinstance(sources, list):
                        for source in sources:
                            if isinstance(source, dict):
                                self._create_relation_from_param_source(
                                    entity_id, param_name, source
                                )
        
        conn.close()
    
    def _create_relation_from_param_source(self, entity_id: str, param_name: str, source: dict):
        """从参数来源创建 relation 规则"""
        
        source_type = source.get('type', '')
        
        # 天赋节点来源
        if source_type == 'passive_node':
            pattern = source.get('pattern', '')
            
            # 确定关系类型
            if 'INC' in param_name.upper() or 'increased' in pattern.lower():
                relation_type = 'enhances'
            elif 'MORE' in param_name.upper() or 'more' in pattern.lower():
                relation_type = 'enhances'
            elif 'base' in param_name.lower():
                relation_type = 'provides'
            else:
                relation_type = 'modifies'
            
            rule = Rule(
                id=f'relation_{entity_id}_passive_{param_name}',
                category='relation',
                source_entity=source.get('entity', 'PassiveNode'),
                target_entity=entity_id,
                relation_type=relation_type,
                condition=None,
                effect=f'{param_name} from passive node',
                evidence=f'formulas.db:gap_formulas:{entity_id}',
                source_layer=2,
                source_formula=entity_id
            )
            self.rules.append(rule)
            self.stats['relation'] += 1
        
        # 辅助宝石来源
        elif source_type == 'support':
            support_name = source.get('entity', '')
            
            rule = Rule(
                id=f'relation_{support_name}_{entity_id}',
                category='relation',
                source_entity=support_name,
                target_entity=entity_id,
                relation_type='enhances',
                condition='socketed_in_meta_skill',
                effect=f'{param_name} from support',
                evidence=f'formulas.db:gap_formulas:{entity_id}',
                source_layer=2,
                source_formula=entity_id
            )
            self.rules.append(rule)
            self.stats['relation'] += 1
    
    def _extract_relation_rules_from_entities(self):
        """从 S1 实体库提取 relation 规则"""
        
        if not self.entities_db.exists():
            print("  ⚠ 实体库不存在")
            return
        
        conn = sqlite3.connect(str(self.entities_db))
        cursor = conn.cursor()
        
        # 查询支持宝石的 require_skill_types (单独字段)
        cursor.execute('''
            SELECT id, name, require_skill_types, add_skill_types
            FROM entities
            WHERE type = 'skill_definition'
              AND require_skill_types IS NOT NULL
              AND require_skill_types != '[]'
        ''')
        
        for row in cursor.fetchall():
            entity_id, name, req_types_json, add_types_json = row
            
            try:
                req_types = json.loads(req_types_json) if req_types_json else []
            except:
                req_types = []
            
            for req_type in req_types:
                if not req_type or req_type == 'AND':
                    continue
                
                rule = Rule(
                    id=f'relation_{entity_id}_requires_{req_type}',
                    category='relation',
                    source_entity=entity_id,
                    target_entity=req_type,
                    relation_type='requires',
                    condition=None,
                    effect=f'requires skill type: {req_type}',
                    evidence=f'entities.db:skill_definition:{entity_id}',
                    source_layer=1
                )
                self.rules.append(rule)
                self.stats['relation'] += 1
        
        # 查询 add_skill_types
        cursor.execute('''
            SELECT id, name, add_skill_types
            FROM entities
            WHERE type = 'skill_definition'
              AND add_skill_types IS NOT NULL
              AND add_skill_types != '[]'
        ''')
        
        for row in cursor.fetchall():
            entity_id, name, add_types_json = row
            
            try:
                add_types = json.loads(add_types_json) if add_types_json else []
            except:
                add_types = []
            
            for add_type in add_types:
                if not add_type:
                    continue
                
                rule = Rule(
                    id=f'relation_{entity_id}_adds_{add_type}',
                    category='relation',
                    source_entity=entity_id,
                    target_entity=add_type,
                    relation_type='provides',
                    condition=None,
                    effect=f'adds skill type: {add_type}',
                    evidence=f'entities.db:skill_definition:{entity_id}',
                    source_layer=1
                )
                self.rules.append(rule)
                self.stats['relation'] += 1
        
        conn.close()
        print(f"  ✓ 提取 relation 规则: {self.stats['relation']} 条")
    
    def _extract_formula_application_rules(self):
        """从 S2 公式库提取 formula_application 规则"""
        
        if not self.formulas_db.exists():
            print("  ⚠ 公式库不存在")
            return
        
        conn = sqlite3.connect(str(self.formulas_db))
        cursor = conn.cursor()
        
        # 查询 gap_formulas
        cursor.execute('''
            SELECT id, entity_id, entity_name, formula_type
            FROM gap_formulas
            WHERE entity_id IS NOT NULL
        ''')
        
        for row in cursor.fetchall():
            formula_id, entity_id, entity_name, formula_type = row
            
            if not entity_id:
                continue
            
            rule = Rule(
                id=f'formula_app_{entity_id}_{formula_id}',
                category='formula_application',
                source_entity=entity_id,
                target_entity=formula_id,
                relation_type='uses_formula',
                condition=None,
                effect=f'uses formula: {formula_type}',
                evidence=f'formulas.db:gap_formulas:{formula_id}',
                source_layer=2,
                source_formula=formula_id
            )
            self.rules.append(rule)
            self.stats['formula_application'] += 1
        
        conn.close()
        print(f"  ✓ 提取 formula_application 规则: {self.stats['formula_application']} 条")
    
    def _save_to_db(self):
        """保存规则到数据库"""
        
        conn = sqlite3.connect(str(self.rules_db))
        cursor = conn.cursor()
        
        # 清空旧数据
        cursor.execute('DELETE FROM rules')
        
        # 使用 INSERT OR REPLACE 处理重复 ID
        inserted_count = 0
        for rule in self.rules:
            cursor.execute('''
                INSERT OR REPLACE INTO rules (
                    id, category, source_entity, target_entity, relation_type,
                    condition, effect, evidence, source_layer, source_formula,
                    heuristic_record_id, created_at, verified_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                rule.id,
                rule.category,
                rule.source_entity,
                rule.target_entity,
                rule.relation_type,
                rule.condition,
                rule.effect,
                rule.evidence,
                rule.source_layer,
                rule.source_formula,
                rule.heuristic_record_id,
                datetime.now().isoformat(),
                datetime.now().isoformat()
            ))
            inserted_count += 1
        
        conn.commit()
        conn.close()
        print(f"  ✓ 已保存 {inserted_count} 条规则到数据库")


def main():
    kb_path = Path('.codebuddy/skills/poe-data-miner/knowledge_base')
    extractor = RulesExtractorV2(str(kb_path))
    extractor.run()


if __name__ == "__main__":
    main()
