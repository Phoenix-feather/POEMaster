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
        
        # Step 1: 从 S1 实体库提取 constraint 规则
        print("\n[Step 1] 从 S1 实体库提取 constraint 规则...")
        self._extract_constraint_rules_from_entities()
        
        # Step 2: 从 Support 实体提取 constraint 规则
        print("\n[Step 2] 从 Support 实体提取 constraint 规则...")
        self._extract_constraints_from_support_entities()
        
        # Step 3: 从代码逻辑提取 constraint 规则
        print("\n[Step 3] 从代码逻辑提取 constraint 规则...")
        self._extract_constraints_from_code()
        
        # Step 4: 从 S2 公式库提取 relation 规则
        print("\n[Step 4] 从 S2 公式库提取 relation 规则...")
        self._extract_relation_rules_from_formulas()
        
        # Step 5: 从 S1 实体库提取 relation 规则
        print("\n[Step 5] 从 S1 实体库提取 relation 规则...")
        self._extract_relation_rules_from_entities()
        
        # Step 6: 从 S2 公式库提取 formula_application 规则
        print("\n[Step 6] 从 S2 公式库提取 formula_application 规则...")
        self._extract_formula_application_rules()
        
        # Step 7: 入库
        print("\n[Step 7] 入库...")
        self._save_to_db()
        
        # 统计
        print("\n" + "=" * 70)
        print("统计")
        print("=" * 70)
        for category, count in self.stats.items():
            print(f"  {category}: {count}")
        print(f"  总计: {sum(self.stats.values())}")
    
    def _extract_constraint_rules(self):
        """
        从数据结构+代码提取 constraint 规则
        
        方法论:
        1. 数据结构: Support*.requireSkillTypes/excludeSkillTypes (L1)
        2. 代码逻辑: CalcTriggers条件判断 (L3)
        """
        
        # ===== 数据结构提取: Support实体约束 =====
        print("  [数据结构] 从 Support 实体提取约束...")
        self._extract_constraints_from_support_entities()
        
        # ===== 代码逻辑提取: 通用触发约束 =====
        print("  [代码逻辑] 从 CalcTriggers 提取通用约束...")
        self._extract_constraints_from_code()
    
    def _extract_constraints_from_support_entities(self):
        """
        从 Support 实体提取约束 (L1结构化约束)
        
        数据来源: POB Lua 文件（直接读取，因hidden实体被扫描器跳过）
        约束字段: requireSkillTypes, excludeSkillTypes, addSkillTypes
        """
        
        # 读取技能定义文件
        skills_dir = self.pob_path / 'Data' / 'Skills'
        support_constraints = {}
        
        for lua_file in skills_dir.glob('*.lua'):
            with open(lua_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 提取 Support* 实体（包括hidden）
            support_entities = self._parse_support_entities(content)
            support_constraints.update(support_entities)
        
        # 建立 Meta ↔ Support 映射
        meta_to_support = {}
        for support_id in support_constraints:
            if support_id.startswith('SupportMeta'):
                meta_id = support_id.replace('Support', '', 1)
                meta_to_support[meta_id] = support_id
        
        print(f"    找到 {len(meta_to_support)} 个 Meta-Support 映射")
        
        # 生成约束规则
        for meta_id, support_id in meta_to_support.items():
            support_data = support_constraints[support_id]
            
            # requireSkillTypes 约束
            req_types = support_data.get('requireSkillTypes', [])
            if req_types:
                condition_str = f"requireSkillTypes: {','.join(req_types)}"
                add_types = support_data.get('addSkillTypes', [])
                effect_str = f"addSkillTypes: {','.join(add_types)}" if add_types else "skill becomes triggered"
                
                rule = Rule(
                    id=f'constraint_{meta_id}_triggered_skill_requires',
                    category='constraint',
                    source_entity=meta_id,
                    target_entity='TriggeredSkill',
                    relation_type='requires',
                    condition=condition_str,
                    effect=effect_str,
                    evidence=f'{support_id}.requireSkillTypes',
                    source_layer=1
                )
                self.rules.append(rule)
                self.stats['constraint'] += 1
                print(f"    ✓ {meta_id}: requires {req_types}")
            
            # excludeSkillTypes 约束
            exc_types = support_data.get('excludeSkillTypes', [])
            if exc_types:
                condition_str = f"excludeSkillTypes: {','.join(exc_types)}"
                
                rule = Rule(
                    id=f'constraint_{meta_id}_triggered_skill_excludes',
                    category='constraint',
                    source_entity=meta_id,
                    target_entity='TriggeredSkill',
                    relation_type='excludes',
                    condition=condition_str,
                    effect='cannot be triggered',
                    evidence=f'{support_id}.excludeSkillTypes',
                    source_layer=1
                )
                self.rules.append(rule)
                self.stats['constraint'] += 1
                print(f"    ✓ {meta_id}: excludes {exc_types}")
    
    def _parse_support_entities(self, content: str) -> Dict[str, Dict]:
        """解析 Lua 文件中的 Support 实体"""
        supports = {}
        
        pattern = r'skills\s*\[\s*"(Support[^"]+)"\s*\]\s*=\s*\{'
        
        for match in re.finditer(pattern, content):
            support_id = match.group(1)
            start = match.end()
            table_content = self._extract_table_content(content, start - 1)
            
            supports[support_id] = {
                'requireSkillTypes': self._extract_skill_types(table_content, 'requireSkillTypes'),
                'excludeSkillTypes': self._extract_skill_types(table_content, 'excludeSkillTypes'),
                'addSkillTypes': self._extract_skill_types(table_content, 'addSkillTypes')
            }
        
        return supports
    
    def _extract_skill_types(self, table_content: str, field_name: str) -> List[str]:
        """提取 SkillType 列表"""
        pattern = rf'{field_name}\s*=\s*\{{([^}}]+)\}}'
        match = re.search(pattern, table_content)
        
        if not match:
            return []
        
        types_str = match.group(1)
        types = re.findall(r'SkillType\.(\w+)|"(\w+)"', types_str)
        result = []
        for t in types:
            if t[0]:
                result.append(t[0])
            elif t[1]:
                result.append(t[1])
        
        return list(set(result))
    
    def _extract_table_content(self, content: str, start: int) -> str:
        """提取 Lua 表内容（括号平衡）"""
        depth = 0
        end = start
        
        for i, char in enumerate(content[start:], start):
            if char == '{':
                depth += 1
            elif char == '}':
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        
        return content[start:end]
    
    def _extract_constraints_from_code(self):
        """
        从代码逻辑提取约束 (L3代码约束)
        
        来源:
        1. 通用条件约束 (如 not isTriggered)
        2. CalcTriggers.lua configTable 中的触发器条件
        """
        
        calc_triggers_path = self.pob_path / 'Modules' / 'CalcTriggers.lua'
        if not calc_triggers_path.exists():
            print(f"    ⚠ CalcTriggers.lua 不存在")
            return
        
        with open(calc_triggers_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 1. 通用条件约束
        code_constraints = self._parse_code_constraints(content)
        
        for constraint in code_constraints:
            rule = Rule(
                id=f'constraint_{constraint["id"]}',
                category='constraint',
                source_entity=constraint['source'],
                target_entity=constraint['target'],
                relation_type=constraint['relation'],
                condition=constraint['condition'],
                effect=constraint['effect'],
                evidence=f'CalcTriggers.lua:{constraint["evidence"]}',
                source_layer=3
            )
            self.rules.append(rule)
            self.stats['constraint'] += 1
            print(f"    ✓ [通用] {constraint['id']}")
        
        # 2. 从 configTable 提取触发器条件约束
        trigger_constraints = self._parse_trigger_config_table(content)
        
        for constraint in trigger_constraints:
            rule = Rule(
                id=f'constraint_{constraint["id"]}',
                category='constraint',
                source_entity=constraint['source'],
                target_entity=constraint['target'],
                relation_type=constraint['relation'],
                condition=constraint['condition'],
                effect=constraint['effect'],
                evidence=f'CalcTriggers.lua:configTable:{constraint["trigger_name"]}',
                source_layer=3
            )
            self.rules.append(rule)
            self.stats['constraint'] += 1
            print(f"    ✓ [触发器] {constraint['trigger_name']}: {constraint['condition'][:50]}...")
    
    def _parse_trigger_config_table(self, content: str) -> List[Dict]:
        """
        解析 CalcTriggers.lua 中的 configTable
        
        提取每个触发器的:
        - triggerSkillCond: 触发源条件
        - triggeredSkillCond: 被触发技能条件
        """
        
        constraints = []
        
        # 查找 configTable 定义
        config_match = re.search(r'local configTable\s*=\s*\{', content)
        if not config_match:
            return constraints
        
        # 提取 configTable 内容（到下一个 top-level 定义）
        start = config_match.end()
        
        # 查找每个触发器配置
        trigger_pattern = r'\["([^"]+)"\]\s*=\s*function\(\)[^}]*return\s*\{([^}]+)\}'
        
        for match in re.finditer(trigger_pattern, content[start:], re.DOTALL):
            trigger_name = match.group(1)
            config_body = match.group(2)
            
            # 提取 triggerSkillCond
            trigger_cond = self._extract_function_condition(config_body, 'triggerSkillCond')
            if trigger_cond:
                constraints.append({
                    'id': f'trigger_{trigger_name}_source_cond',
                    'source': trigger_name,
                    'target': 'TriggerSource',
                    'relation': 'requires',
                    'condition': trigger_cond,
                    'effect': 'trigger source must match condition',
                    'trigger_name': trigger_name
                })
            
            # 提取 triggeredSkillCond
            triggered_cond = self._extract_function_condition(config_body, 'triggeredSkillCond')
            if triggered_cond:
                constraints.append({
                    'id': f'trigger_{trigger_name}_target_cond',
                    'source': trigger_name,
                    'target': 'TriggeredSkill',
                    'relation': 'requires',
                    'condition': triggered_cond,
                    'effect': 'triggered skill must match condition',
                    'trigger_name': trigger_name
                })
        
        return constraints
    
    def _extract_function_condition(self, config_body: str, func_name: str) -> Optional[str]:
        """提取函数体中的条件逻辑"""
        
        # 查找函数定义
        pattern = func_name + r'\s*=\s*function\([^)]*\)\s*return\s+([^}]+)\s*end'
        match = re.search(pattern, config_body, re.DOTALL)
        
        if not match:
            return None
        
        condition_body = match.group(1).strip()
        
        # 提取关键条件
        conditions = []
        
        # skillTypes 检查
        skill_types = re.findall(r'skillTypes\[SkillType\.(\w+)\]', condition_body)
        if skill_types:
            conditions.append(f"skillTypes: {','.join(skill_types)}")
        
        # skillFlags 检查
        flags = re.findall(r'skillFlags\.(\w+)', condition_body)
        if flags:
            conditions.append(f"skillFlags: {','.join(flags)}")
        
        # slotMatch 检查
        if 'slotMatch' in condition_body:
            conditions.append('slotMatch: true')
        
        # weaponTypes 检查
        weapons = re.findall(r'weaponTypes\["(\w+)"\]', condition_body)
        if weapons:
            conditions.append(f"weaponTypes: {','.join(weapons)}")
        
        # weapon 检查
        weapon_flags = re.findall(r'ModFlag\.(\w+)', condition_body)
        if weapon_flags:
            conditions.append(f"weaponFlags: {','.join(weapon_flags)}")
        
        return ', '.join(conditions) if conditions else condition_body[:100]
    
    def _parse_code_constraints(self, content: str) -> List[Dict]:
        """
        从 CalcTriggers.lua 提取通用代码约束
        
        提取源:
        1. 条件判断语句中的 isTriggered/notTriggered 等
        2. 隐式约束（如触发源不能是被触发技能）
        """
        
        constraints = []
        
        # 1. 触发源不能是被触发技能
        if re.search(r'not\s+skillData\.triggered', content) or \
           re.search(r'not\s+activeSkill\.skillData\.triggered', content):
            constraints.append({
                'id': 'trigger_source_not_triggered',
                'source': 'TriggerSkill',
                'target': 'TriggeredSkill',
                'relation': 'excludes',
                'condition': 'source skill must not be triggered',
                'effect': 'prevents recursive triggers',
                'evidence': 'not skillData.triggered'
            })
        
        # 2. 禁用的技能无法触发
        if re.search(r'skillFlags\.disabled', content):
            constraints.append({
                'id': 'disabled_skill_blocks_trigger',
                'source': 'DisabledSkill',
                'target': 'TriggerSystem',
                'relation': 'excludes',
                'condition': 'skillFlags.disabled == true',
                'effect': 'disabled skills cannot trigger',
                'evidence': 'skillFlags.disabled check'
            })
        
        # 3. 技能必须启用才能被触发
        if re.search(r'skillFlags\.enable', content):
            constraints.append({
                'id': 'skill_must_be_enabled',
                'source': 'TriggeredSkill',
                'target': 'SkillFlag',
                'relation': 'requires',
                'condition': 'skillFlags.enable == true',
                'effect': 'disabled skills cannot be triggered',
                'evidence': 'skillFlags.enable check'
            })
        
        # 4. 触发器能量检查
        if re.search(r'triggerEnergy', content):
            constraints.append({
                'id': 'trigger_energy_required',
                'source': 'MetaSkill',
                'target': 'TriggerEnergy',
                'relation': 'requires',
                'condition': 'triggerEnergy >= threshold',
                'effect': 'requires sufficient trigger energy to fire',
                'evidence': 'triggerEnergy threshold check'
            })
        
        # 5. 冷却时间约束
        if re.search(r'cooldownSpeed', content):
            constraints.append({
                'id': 'cooldown_applies_to_triggered',
                'source': 'TriggeredSkill',
                'target': 'Cooldown',
                'relation': 'has',
                'condition': 'triggered skill has cooldown',
                'effect': 'triggered skill goes on cooldown after triggering',
                'evidence': 'cooldownSpeed check'
            })
        
        # 6. 武器类型约束
        if re.search(r'weaponTypes', content):
            constraints.append({
                'id': 'weapon_type_restriction',
                'source': 'TriggerSkill',
                'target': 'WeaponType',
                'relation': 'requires',
                'condition': 'correct weapon type equipped',
                'effect': 'trigger requires specific weapon type',
                'evidence': 'weaponTypes check'
            })
        
        # 7. 全局触发计数器
        if re.search(r'globalTrigger', content):
            constraints.append({
                'id': 'global_trigger_enables',
                'source': 'GlobalTrigger',
                'target': 'TriggerSystem',
                'relation': 'controls',
                'condition': 'globalTrigger enabled',
                'effect': 'global trigger enables/disables all triggers',
                'evidence': 'globalTrigger check'
            })
        
        # 8. 插槽匹配约束
        if re.search(r'slotMatch', content):
            constraints.append({
                'id': 'slot_matching_required',
                'source': 'TriggeredSkill',
                'target': 'TriggerSkill',
                'relation': 'requires',
                'condition': 'triggered skill must be socketed in meta skill',
                'effect': 'skills must be in correct socket',
                'evidence': 'slotMatch check'
            })
        
        # 9. 技能类型标签约束（从代码逻辑中提取）
        skill_type_checks = re.findall(r'skillTypes\[SkillType\.(\w+)\]', content)
        unique_skill_types = list(set(skill_type_checks))
        
        for skill_type in unique_skill_types:
            constraints.append({
                'id': f'skill_type_{skill_type.lower()}_checked',
                'source': 'TriggerSystem',
                'target': f'SkillType.{skill_type}',
                'relation': 'checks',
                'condition': f'skillTypes[{skill_type}] evaluated',
                'effect': f'skill type {skill_type} affects trigger behavior',
                'evidence': f'skillTypes[SkillType.{skill_type}]'
            })
        
        print(f"    找到 {len(constraints)} 个通用代码约束")
        return constraints
    
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
    
    def _extract_constraint_rules_from_entities(self):
        """
        从 S1 实体库提取 constraint 规则
        
        约束字段: requireSkillTypes, excludeSkillTypes
        关系字段: addSkillTypes（保留为relation规则）
        """
        
        if not self.entities_db.exists():
            print("  ⚠ 实体库不存在")
            return
        
        conn = sqlite3.connect(str(self.entities_db))
        cursor = conn.cursor()
        
        constraint_count = 0
        
        # 查询 require_skill_types → constraint
        cursor.execute('''
            SELECT id, name, require_skill_types
            FROM entities
            WHERE type = 'skill_definition'
              AND require_skill_types IS NOT NULL
              AND require_skill_types != '[]'
        ''')
        
        for row in cursor.fetchall():
            entity_id, name, req_types_json = row
            
            try:
                req_types = json.loads(req_types_json) if req_types_json else []
            except:
                req_types = []
            
            # 过滤 AND/OR
            req_types = [t for t in req_types if t and t not in ('AND', 'OR')]
            
            if req_types:
                condition_str = f"requireSkillTypes: {','.join(req_types)}"
                
                rule = Rule(
                    id=f'constraint_{entity_id}_skill_type_requires',
                    category='constraint',
                    source_entity=entity_id,
                    target_entity='SupportedSkill',
                    relation_type='requires',
                    condition=condition_str,
                    effect='skill must match required types',
                    evidence=f'entities.db:{entity_id}.requireSkillTypes',
                    source_layer=1
                )
                self.rules.append(rule)
                self.stats['constraint'] += 1
                constraint_count += 1
        
        # 查询 exclude_skill_types → constraint
        cursor.execute('''
            SELECT id, name, exclude_skill_types
            FROM entities
            WHERE type = 'skill_definition'
              AND exclude_skill_types IS NOT NULL
              AND exclude_skill_types != '[]'
        ''')
        
        for row in cursor.fetchall():
            entity_id, name, exc_types_json = row
            
            try:
                exc_types = json.loads(exc_types_json) if exc_types_json else []
            except:
                exc_types = []
            
            exc_types = [t for t in exc_types if t and t not in ('AND', 'OR')]
            
            if exc_types:
                condition_str = f"excludeSkillTypes: {','.join(exc_types)}"
                
                rule = Rule(
                    id=f'constraint_{entity_id}_skill_type_excludes',
                    category='constraint',
                    source_entity=entity_id,
                    target_entity='SupportedSkill',
                    relation_type='excludes',
                    condition=condition_str,
                    effect='skill cannot have excluded types',
                    evidence=f'entities.db:{entity_id}.excludeSkillTypes',
                    source_layer=1
                )
                self.rules.append(rule)
                self.stats['constraint'] += 1
                constraint_count += 1
        
        conn.close()
        print(f"  ✓ 提取 constraint 规则: {constraint_count} 条")
    
    def _extract_relation_rules_from_entities(self):
        """从 S1 实体库提取 relation 规则（仅 addSkillTypes）"""
        
        if not self.entities_db.exists():
            return
        
        conn = sqlite3.connect(str(self.entities_db))
        cursor = conn.cursor()
        
        # 查询 add_skill_types → relation（功能性关系）
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
                if not add_type or add_type in ('AND', 'OR'):
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
    extractor = RulesExtractor(str(kb_path))
    extractor.run()


if __name__ == "__main__":
    main()
