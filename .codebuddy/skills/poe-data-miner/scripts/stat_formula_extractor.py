#!/usr/bin/env python3
"""
Meta缺口公式提取器 (Gap Formula Extractor)

从Meta技能的实体数据中提取POB未实现的公式:
- 能量获取公式 (energy_gain)
- 最大能量公式 (max_energy)
- 伤害修正公式 (damage_modifier)
- 触发条件 (trigger_condition)

数据来源:
- entities.db 中的 Meta 技能实体 (constantStats, stats, skill_types)
- entities.db 中的 hidden Support 实体 (如果存在)
- StatDescriptions/ 中的精确描述文本 (补充信息)

输出到 formulas.db 的 gap_formulas 表
"""

import re
import sqlite3
import json
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, asdict


@dataclass
class GapFormula:
    """缺口公式"""
    id: str                  # 唯一ID
    entity_id: str           # 关联的技能实体ID
    entity_name: str         # 实体名称
    formula_type: str        # energy_gain / max_energy / damage_modifier / trigger_condition
    formula_text: str        # 人可读公式
    parameters: str          # JSON: 参数名→值映射
    stat_sources: str        # JSON: 来源stat列表
    description: str         # 公式描述（可来自StatDescriptions）
    confidence: float        # 置信度 (0-1)
    pob_status: str          # "unimplemented" / "partial" / "commented_out"
    notes: str               # 补充说明


# 能量获取stat名称模式
ENERGY_GAIN_PATTERNS = [
    # monster_power型: gain_X_centienergy_per_monster_power
    (r'(\w+)_gain_(\w+)_centienergy_per_monster_power(?:_on_(\w+))?',
     'monster_power', 'energy = monster_power × ({centienergy}/100) × (1 + energy_generated_+%/100)'),

    # 固定值型: gain_X_centienergy_on_event
    (r'(\w+)_gain_(\w+)_centienergy_on_(\w+)',
     'fixed', 'energy = {centienergy}/100 × (1 + energy_generated_+%/100)'),

    # 连续型: gain_X_centienergy_per_Y
    (r'(\w+)_gain_(\w+)_centienergy_per_(\w+)',
     'continuous', 'energy = {centienergy}/100 × {unit} × (1 + energy_generated_+%/100)'),
]

# 最大能量stat名称模式
MAX_ENERGY_PATTERNS = [
    # 动态型: maximum_energy_per_Xms_total_cast_time
    (r'generic_ongoing_trigger_(\d+)_maximum_energy_per_(\w+)ms_total_cast_time',
     'dynamic', 'max_energy = Σ(socketed_spell_cast_time_ms) × {per_Xms} / 1000'),

    # 固定型: maximum_energy
    (r'generic_ongoing_trigger_maximum_energy',
     'fixed', 'max_energy = {value} / 100'),
]

# 伤害修正模式
DAMAGE_MOD_PATTERNS = [
    (r'trigger_meta_gem_damage_\+%_final', 'damage_modifier',
     'final_damage = base × (1 + {value}/100)'),
]


class StatFormulaExtractor:
    """缺口公式提取器"""

    def __init__(self, entities_db_path: str, db_path: str):
        self.entities_db_path = Path(entities_db_path)
        self.db_path = Path(db_path)
        self.formulas: List[GapFormula] = []

    def extract_all(self) -> List[GapFormula]:
        """提取所有缺口公式"""
        self.formulas = []

        # Step 1: 获取所有Meta技能实体
        meta_entities = self._get_meta_entities()
        print(f"    找到 {len(meta_entities)} 个Meta技能实体")

        # Step 2: 获取所有隐藏Support实体（如果有的话）
        support_entities = self._get_support_meta_entities()
        print(f"    找到 {len(support_entities)} 个Support实体")

        # Step 3: 建立Meta→Support关联
        meta_support_map = self._build_meta_support_map(meta_entities, support_entities)

        # Step 4: 从每个Meta技能提取公式
        for entity in meta_entities:
            entity_id = entity['id']
            entity_name = entity.get('name', entity_id)
            data = entity.get('data', {})

            # 关联的Support数据
            support_data = meta_support_map.get(entity_id, {})

            # 提取能量获取公式
            self._extract_energy_gain(entity_id, entity_name, data)

            # 提取最大能量公式（通常来自Support）
            self._extract_max_energy(entity_id, entity_name, data, support_data)

            # 提取伤害修正（通常来自Support）
            self._extract_damage_modifier(entity_id, entity_name, data, support_data)

            # 提取触发条件
            self._extract_trigger_condition(entity_id, entity_name, data)

        print(f"    总计提取 {len(self.formulas)} 个缺口公式")
        return self.formulas

    def _get_meta_entities(self) -> List[Dict]:
        """获取所有Meta技能实体"""
        conn = sqlite3.connect(str(self.entities_db_path))
        cursor = conn.cursor()

        cursor.execute('''
            SELECT id, name, type, skill_types, constant_stats, stats, data_json
            FROM entities
            WHERE skill_types LIKE '%Meta%'
               OR skill_types LIKE '%GeneratesEnergy%'
        ''')

        entities = []
        for row in cursor.fetchall():
            entity_id, name, etype, skill_types, constant_stats, stats, data_json = row
            data = json.loads(data_json) if data_json else {}
            entities.append({
                'id': entity_id,
                'name': name or entity_id,
                'type': etype,
                'skill_types': json.loads(skill_types) if skill_types else [],
                'constant_stats': json.loads(constant_stats) if constant_stats else [],
                'stats': json.loads(stats) if stats else [],
                'data': data
            })

        conn.close()
        return entities

    def _get_support_meta_entities(self) -> List[Dict]:
        """获取所有隐藏的SupportMeta实体"""
        conn = sqlite3.connect(str(self.entities_db_path))
        cursor = conn.cursor()

        # 搜索Support实体（可能因hidden=true被跳过）
        cursor.execute('''
            SELECT id, name, type, constant_stats, stats, data_json
            FROM entities
            WHERE id LIKE 'SupportMeta%'
               OR name LIKE 'SupportMeta%'
        ''')

        entities = []
        for row in cursor.fetchall():
            entity_id, name, etype, constant_stats, stats, data_json = row
            data = json.loads(data_json) if data_json else {}
            entities.append({
                'id': entity_id,
                'name': name or entity_id,
                'constant_stats': json.loads(constant_stats) if constant_stats else [],
                'stats': json.loads(stats) if stats else [],
                'data': data
            })

        conn.close()
        return entities

    def _build_meta_support_map(self, meta_entities: List[Dict], support_entities: List[Dict]) -> Dict:
        """建立Meta→Support映射"""
        mapping = {}

        for meta in meta_entities:
            meta_id = meta['id']
            # 尝试匹配：MetaCastOnCritPlayer → SupportMetaCastOnCritPlayer
            expected_support = f"Support{meta_id}"

            for sup in support_entities:
                if sup['id'] == expected_support or sup['name'] == expected_support:
                    mapping[meta_id] = sup
                    break

        return mapping

    def _extract_energy_gain(self, entity_id: str, entity_name: str, data: Dict):
        """从实体数据提取能量获取公式"""
        # data_json中字段名是下划线式 constant_stats，也兼容驼峰式 constantStats
        constant_stats = data.get('constant_stats', data.get('constantStats', []))
        if isinstance(constant_stats, dict):
            constant_stats = [[k, v] for k, v in constant_stats.items()]

        for stat_entry in constant_stats:
            if isinstance(stat_entry, (list, tuple)) and len(stat_entry) >= 2:
                stat_name, stat_value = stat_entry[0], stat_entry[1]
            elif isinstance(stat_entry, dict):
                stat_name = stat_entry.get('stat', stat_entry.get('name', ''))
                stat_value = stat_entry.get('value', 0)
            else:
                continue

            # 匹配能量获取模式
            for pattern, mode, formula_template in ENERGY_GAIN_PATTERNS:
                match = re.match(pattern, stat_name)
                if match:
                    formula_text = formula_template.format(
                        centienergy=stat_value,
                        unit='unit_measure'
                    )

                    params = {
                        'centienergy': stat_value,
                        'mode': mode,
                        'source_stat': stat_name
                    }

                    # 尝试获取触发事件类型
                    if match.lastindex and match.lastindex >= 3:
                        params['trigger_event'] = match.group(3)

                    self.formulas.append(GapFormula(
                        id=f"gap_{entity_id}_energy_gain",
                        entity_id=entity_id,
                        entity_name=entity_name,
                        formula_type='energy_gain',
                        formula_text=formula_text,
                        parameters=json.dumps(params),
                        stat_sources=json.dumps([stat_name]),
                        description=f"{entity_name}的能量获取公式（{mode}模式）",
                        confidence=0.85,
                        pob_status='unimplemented',
                        notes=f'SkillStatMap中无映射，CalcTriggers被注释'
                    ))
                    break

    def _extract_max_energy(self, entity_id: str, entity_name: str, data: Dict, support_data: Dict):
        """提取最大能量公式"""
        # 先从Support数据中查找
        all_constant_stats = []

        sup_constants = support_data.get('constant_stats', support_data.get('constantStats',
                         support_data.get('data', {}).get('constant_stats',
                         support_data.get('data', {}).get('constantStats', []))))
        if isinstance(sup_constants, dict):
            sup_constants = [[k, v] for k, v in sup_constants.items()]
        all_constant_stats.extend(sup_constants)

        # 也检查实体自身的constantStats
        own_constants = data.get('constant_stats', data.get('constantStats', []))
        if isinstance(own_constants, dict):
            own_constants = [[k, v] for k, v in own_constants.items()]
        all_constant_stats.extend(own_constants)

        for stat_entry in all_constant_stats:
            if isinstance(stat_entry, (list, tuple)) and len(stat_entry) >= 2:
                stat_name, stat_value = stat_entry[0], stat_entry[1]
            elif isinstance(stat_entry, dict):
                stat_name = stat_entry.get('stat', stat_entry.get('name', ''))
                stat_value = stat_entry.get('value', 0)
            else:
                continue

            for pattern, mode, formula_template in MAX_ENERGY_PATTERNS:
                match = re.match(pattern, stat_name)
                if match:
                    formula_text = formula_template.format(
                        per_Xms=stat_value,
                        value=stat_value
                    )

                    params = {
                        'value': stat_value,
                        'mode': mode,
                        'source_stat': stat_name
                    }

                    source = 'Support实体' if stat_entry in sup_constants else '自身实体'

                    self.formulas.append(GapFormula(
                        id=f"gap_{entity_id}_max_energy",
                        entity_id=entity_id,
                        entity_name=entity_name,
                        formula_type='max_energy',
                        formula_text=formula_text,
                        parameters=json.dumps(params),
                        stat_sources=json.dumps([stat_name]),
                        description=f"{entity_name}的最大能量公式（{mode}型，来自{source}）",
                        confidence=0.80,
                        pob_status='unimplemented',
                        notes=f'参数来自{source}的constantStats'
                    ))
                    break

    def _extract_damage_modifier(self, entity_id: str, entity_name: str, data: Dict, support_data: Dict):
        """提取伤害修正公式"""
        # 主要来自Support的constantStats
        all_constant_stats = []

        sup_constants = support_data.get('constant_stats', support_data.get('constantStats',
                         support_data.get('data', {}).get('constant_stats',
                         support_data.get('data', {}).get('constantStats', []))))
        if isinstance(sup_constants, dict):
            sup_constants = [[k, v] for k, v in sup_constants.items()]
        all_constant_stats.extend(sup_constants)

        for stat_entry in all_constant_stats:
            if isinstance(stat_entry, (list, tuple)) and len(stat_entry) >= 2:
                stat_name, stat_value = stat_entry[0], stat_entry[1]
            elif isinstance(stat_entry, dict):
                stat_name = stat_entry.get('stat', stat_entry.get('name', ''))
                stat_value = stat_entry.get('value', 0)
            else:
                continue

            for pattern, ftype, formula_template in DAMAGE_MOD_PATTERNS:
                if re.match(pattern, stat_name):
                    formula_text = formula_template.format(value=stat_value)

                    self.formulas.append(GapFormula(
                        id=f"gap_{entity_id}_damage_mod",
                        entity_id=entity_id,
                        entity_name=entity_name,
                        formula_type='damage_modifier',
                        formula_text=formula_text,
                        parameters=json.dumps({'value': stat_value, 'source_stat': stat_name}),
                        stat_sources=json.dumps([stat_name]),
                        description=f"{entity_name}的被触发法术伤害修正({stat_value}%)",
                        confidence=0.90,
                        pob_status='unimplemented',
                        notes='来自隐藏Support实体的constantStats'
                    ))
                    break

    def _extract_trigger_condition(self, entity_id: str, entity_name: str, data: Dict):
        """提取触发条件"""
        stats = data.get('stats', [])
        if isinstance(stats, dict):
            stats = list(stats.keys())

        has_trigger_stat = any(
            'triggers_at_maximum_energy' in s
            for s in stats if isinstance(s, str)
        )

        if has_trigger_stat:
            self.formulas.append(GapFormula(
                id=f"gap_{entity_id}_trigger",
                entity_id=entity_id,
                entity_name=entity_name,
                formula_type='trigger_condition',
                formula_text='trigger = (current_energy >= max_energy)',
                parameters=json.dumps({'condition': 'energy >= max_energy'}),
                stat_sources=json.dumps([s for s in stats if 'trigger' in str(s).lower()]),
                description=f"{entity_name}: 当前能量达到最大能量时触发所有插槽法术",
                confidence=0.95,
                pob_status='unimplemented',
                notes='generic_ongoing_trigger_triggers_at_maximum_energy stat确认'
            ))

    def save_to_db(self):
        """保存到数据库"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        # 创建表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS gap_formulas (
                id TEXT PRIMARY KEY,
                entity_id TEXT NOT NULL,
                entity_name TEXT,
                formula_type TEXT NOT NULL,
                formula_text TEXT NOT NULL,
                parameters TEXT,
                stat_sources TEXT,
                description TEXT,
                confidence REAL,
                pob_status TEXT DEFAULT 'unimplemented',
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 创建索引
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_gap_formulas_entity ON gap_formulas(entity_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_gap_formulas_type ON gap_formulas(formula_type)')

        # 清空旧数据
        cursor.execute('DELETE FROM gap_formulas')

        # 插入
        for f in self.formulas:
            cursor.execute('''
                INSERT OR REPLACE INTO gap_formulas
                (id, entity_id, entity_name, formula_type, formula_text,
                 parameters, stat_sources, description, confidence, pob_status, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                f.id, f.entity_id, f.entity_name, f.formula_type, f.formula_text,
                f.parameters, f.stat_sources, f.description, f.confidence,
                f.pob_status, f.notes
            ))

        conn.commit()
        conn.close()

    def get_stats(self) -> Dict:
        """获取统计信息"""
        total = len(self.formulas)
        by_type = {}
        by_entity = {}
        for f in self.formulas:
            by_type[f.formula_type] = by_type.get(f.formula_type, 0) + 1
            by_entity[f.entity_id] = by_entity.get(f.entity_id, 0) + 1

        return {
            'total': total,
            'by_type': by_type,
            'entities_covered': len(by_entity),
            'avg_confidence': sum(f.confidence for f in self.formulas) / max(total, 1)
        }

    def diagnose(self):
        """诊断输出"""
        stats = self.get_stats()

        print(f"\n--- 缺口公式统计 ---")
        print(f"  总公式数: {stats['total']}")
        print(f"  覆盖实体: {stats['entities_covered']}")
        print(f"  平均置信度: {stats['avg_confidence']:.2f}")

        print(f"\n  按类型:")
        for ftype, count in sorted(stats['by_type'].items()):
            print(f"    {ftype}: {count}")

        if self.formulas:
            print(f"\n  样本:")
            for f in self.formulas[:5]:
                print(f"    [{f.entity_name}] {f.formula_type}: {f.formula_text[:80]}...")


def main():
    """独立运行入口"""
    import argparse
    import sys

    SCRIPTS_DIR = Path(__file__).parent
    sys.path.insert(0, str(SCRIPTS_DIR))
    from pob_paths import get_knowledge_base_path

    parser = argparse.ArgumentParser(description='Meta缺口公式提取')
    parser.add_argument('--entities-db', help='实体库路径')
    parser.add_argument('--db', help='输出数据库路径')

    args = parser.parse_args()

    kb_path = get_knowledge_base_path()
    entities_db = args.entities_db or str(kb_path / 'entities.db')
    db_path = args.db or str(kb_path / 'formulas.db')

    print("=" * 60)
    print("Meta缺口公式提取")
    print("=" * 60)

    extractor = StatFormulaExtractor(entities_db, db_path)
    extractor.extract_all()
    extractor.save_to_db()
    extractor.diagnose()

    print(f"\n[OK] 已保存到 {db_path}")


if __name__ == '__main__':
    main()
