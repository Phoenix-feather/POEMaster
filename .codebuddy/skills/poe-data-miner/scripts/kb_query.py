#!/usr/bin/env python3
"""
POE知识库查询工具 v3
封装常用查询，避免命令行引号问题

v3 新增：
- entity --detail (summary/levels/stats/full)
- mechanism --detail (behavior/relations/full)
- supports 子命令 (--mode all/dps/utility/potential)
- compare 子命令 (并排对比两个同类型实体)
- reverse-stat 子命令 (反查影响指定 stat 的来源)
- formula --chain 选项 (展示公式引用链路)
- 所有查询结果附加 response_type 字段
"""

import sqlite3
import json
import argparse
from pathlib import Path
from typing import List, Dict, Any, Optional

# 默认数据库路径
DEFAULT_KB_PATH = Path(__file__).parent.parent / 'knowledge_base'


class KnowledgeBaseQuery:
    """知识库查询工具 v3"""
    
    # 实体类型→返回字段集映射（按类型裁剪，去掉无关null字段噪声）
    # 公共字段：所有类型都返回的基础字段
    _COMMON_FIELDS = {
        'id', 'name', 'type', 'description', 'source_file',
        'data_json', 'created_at', 'updated_at',
        # 解读层字段（Phase 2a新增）
        'summary', 'key_mechanics', 'display_stats',
    }
    
    # 各类型的专属字段集
    _TYPE_FIELDS = {
        'skill_definition': {
            'skill_types', 'constant_stats', 'stats', 'reservation',
            'base_type_name', 'cast_time', 'quality_stats', 'levels', 'stat_sets',
            'support', 'require_skill_types', 'add_skill_types', 'exclude_skill_types',
            'is_trigger', 'hidden',
            'additional_granted_effect_ids',
        },
        'gem_definition': {
            'skill_types', 'tags', 'gem_type', 'tag_string',
            'game_id', 'variant_id', 'granted_effect_id',
            'req_str', 'req_dex', 'req_int',
            'tier', 'natural_max_level',
            'additional_stat_set1', 'additional_stat_set2',
            'weapon_requirements', 'gem_family',
            'additional_granted_effect_ids',
        },
        'unique_item': {
            'stats', 'mod_tags', 'mod_data',
            'requires_level', 'granted_skill', 'implicits',
            'variant', 'source',
            'stat_descriptions',
        },
        'passive_node': {
            'stats_node', 'reminder_text',
            'ascendancy_name', 'is_notable', 'is_keystone',
            'stat_descriptions',
        },
        'mod_affix': {
            'stats', 'mod_tags', 'weight_keys', 'affix_type', 'mod_data',
            'stat_descriptions',
        },
    }
    
    # 需要解析的JSON字段列表（完整22个字段）
    _JSON_FIELDS = [
        'skill_types', 'constant_stats', 'stats', 'reservation',
        'mod_tags', 'weight_keys', 'mod_data', 'data_json',
        'quality_stats', 'levels', 'stat_sets',
        'require_skill_types', 'add_skill_types', 'exclude_skill_types',
        'tags', 'stats_node', 'reminder_text', 'variant',
        'stat_descriptions', 'additional_granted_effect_ids',
        'key_mechanics', 'display_stats'
    ]
    
    def __init__(self, kb_path: str = None):
        self.kb_path = Path(kb_path) if kb_path else DEFAULT_KB_PATH
        self.entities_db = self.kb_path / 'entities.db'
        self.mechanisms_db = self.kb_path / 'mechanisms.db'
        self.supports_db = self.kb_path / 'supports.db'
        self.formulas_db = self.kb_path / 'formulas.db'
    
    def _parse_json_fields(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """解析字典中的JSON字段"""
        for key in self._JSON_FIELDS:
            if raw.get(key):
                try:
                    raw[key] = json.loads(raw[key])
                except (json.JSONDecodeError, TypeError):
                    pass
        return raw
    
    # ========== 实体查询 (6.1) ==========
    
    def get_entity(self, entity_id: str, detail: str = 'full') -> Optional[Dict[str, Any]]:
        """
        获取单个实体
        
        Args:
            entity_id: 实体ID
            detail: 详情级别
                - 'summary': 仅返回核心字段+解读字段
                - 'levels': 核心字段+等级数值成长
                - 'stats': 核心字段+完整stats数据
                - 'full': 返回该类型的所有相关字段（按类型裁剪，去除无关null字段）
        
        Returns:
            实体数据字典或None
        """
        conn = sqlite3.connect(self.entities_db)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM entities WHERE id = ?', (entity_id,))
        row = cursor.fetchone()
        
        if not row:
            conn.close()
            return None
        
        cols = [d[0] for d in cursor.description]
        raw = dict(zip(cols, row))
        self._parse_json_fields(raw)
        
        # 按实体类型裁剪字段
        entity_type = raw.get('type', 'unknown')
        result = self._filter_fields_by_type(raw, entity_type, detail)
        
        conn.close()
        return result
    
    def _filter_fields_by_type(self, raw: Dict[str, Any], entity_type: str, detail: str) -> Dict[str, Any]:
        """按实体类型和detail级别裁剪返回字段"""
        # 确定该类型应该返回的字段集
        type_specific = self._TYPE_FIELDS.get(entity_type, set())
        allowed_fields = self._COMMON_FIELDS | type_specific
        
        # 按detail级别进一步裁剪
        if detail == 'summary':
            summary_fields = {
                'id', 'name', 'type', 'description',
                'summary', 'key_mechanics', 'display_stats',
                'skill_types', 'cast_time', 'base_type_name',
                'gem_type', 'ascendancy_name', 'is_notable', 'is_keystone',
                'affix_type',
            }
            allowed_fields = allowed_fields & summary_fields
        elif detail == 'levels':
            levels_fields = {
                'id', 'name', 'type', 'description',
                'summary', 'key_mechanics', 'display_stats',
                'skill_types', 'cast_time', 'base_type_name',
                'levels', 'constant_stats', 'quality_stats',
            }
            allowed_fields = allowed_fields & levels_fields
        elif detail == 'stats':
            stats_fields = {
                'id', 'name', 'type', 'description',
                'summary', 'key_mechanics', 'display_stats',
                'skill_types', 'cast_time', 'base_type_name',
                'stats', 'constant_stats', 'stat_sets',
                'stats_node', 'stat_descriptions',
                'mod_data', 'mod_tags',
            }
            allowed_fields = allowed_fields & stats_fields
        # 'full' 不做额外裁剪
        
        # 构建结果：只包含在allowed_fields中且值非空/非默认的字段
        result = {}
        for key in allowed_fields:
            value = raw.get(key)
            if value is None:
                continue
            if isinstance(value, str) and value in ('', '[]', '{}', '0'):
                continue
            if isinstance(value, (list, dict)) and not value:
                continue
            if isinstance(value, int) and value == 0 and key in (
                'support', 'is_trigger', 'hidden', 'is_notable', 'is_keystone',
                'req_str', 'req_dex', 'req_int'
            ):
                continue
            result[key] = value
        
        result['response_type'] = self._infer_response_type(entity_type, detail)
        return result
    
    def _infer_response_type(self, entity_type: str, detail: str) -> str:
        """推断response_type"""
        if detail == 'summary':
            return 'entity_overview'
        elif detail == 'levels':
            return 'numeric_table'
        elif detail == 'stats':
            return 'stat_detail'
        else:
            type_response_map = {
                'skill_definition': 'skill_full',
                'gem_definition': 'gem_full',
                'unique_item': 'item_full',
                'passive_node': 'passive_full',
                'mod_affix': 'mod_full',
            }
            return type_response_map.get(entity_type, 'entity_full')
    
    def search_entities(self, keyword: str, limit: int = 20) -> List[Dict[str, Any]]:
        """搜索实体"""
        conn = sqlite3.connect(self.entities_db)
        cursor = conn.cursor()
        
        pattern = f'%{keyword}%'
        cursor.execute('''
            SELECT id, name, type FROM entities 
            WHERE id LIKE ? OR name LIKE ? 
            LIMIT ?
        ''', (pattern, pattern, limit))
        
        results = [
            {'id': r[0], 'name': r[1], 'type': r[2], 'response_type': 'entity_list'}
            for r in cursor.fetchall()
        ]
        conn.close()
        return results
    
    def get_entities_by_type(self, entity_type: str, limit: int = 50) -> List[Dict[str, Any]]:
        """按类型获取实体"""
        conn = sqlite3.connect(self.entities_db)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, name, type FROM entities 
            WHERE type = ? 
            LIMIT ?
        ''', (entity_type, limit))
        
        results = [
            {'id': r[0], 'name': r[1], 'type': r[2], 'response_type': 'entity_list'}
            for r in cursor.fetchall()
        ]
        conn.close()
        return results
    
    def get_entities_by_skill_type(self, skill_type: str, limit: int = 50) -> List[Dict[str, Any]]:
        """按技能类型获取实体"""
        conn = sqlite3.connect(self.entities_db)
        cursor = conn.cursor()
        
        pattern = f'%{skill_type}%'
        cursor.execute('''
            SELECT id, name, skill_types FROM entities 
            WHERE skill_types LIKE ? 
            LIMIT ?
        ''', (pattern, limit))
        
        results = [
            {'id': r[0], 'name': r[1], 'skill_types': r[2], 'response_type': 'entity_list'}
            for r in cursor.fetchall()
        ]
        conn.close()
        return results
    
    def get_meta_skills(self) -> List[Dict[str, Any]]:
        """获取所有元技能"""
        return self.get_entities_by_skill_type('Meta')
    
    # ========== 机制查询 (6.2) ==========

    def get_mechanism(self, mechanism_id: str, detail: str = 'full') -> Optional[Dict[str, Any]]:
        """
        获取单个机制
        
        Args:
            mechanism_id: 机制ID
            detail: 详情级别
                - 'behavior': 基本信息 + 行为描述 + 公式
                - 'relations': 基本信息 + 关联机制
                - 'full': 所有信息（行为 + 来源 + 关系）
        """
        if not self.mechanisms_db.exists():
            return None
        
        conn = sqlite3.connect(self.mechanisms_db)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM mechanisms WHERE id = ?', (mechanism_id,))
        row = cursor.fetchone()
        
        if not row:
            conn.close()
            return None
        
        cols = [d[0] for d in cursor.description]
        result = dict(zip(cols, row))
        
        # 解析 JSON 字段
        for field in ('stat_names', 'affected_stats'):
            if result.get(field):
                try:
                    result[field] = json.loads(result[field])
                except (json.JSONDecodeError, TypeError):
                    pass
        
        if detail in ('full', 'behavior'):
            # 无需额外查询，行为字段已在 mechanisms 表中
            pass
        
        if detail in ('full', 'relations'):
            # 查询关联关系
            cursor.execute('''
                SELECT mechanism_a, mechanism_b, relation_type, direction, description
                FROM mechanism_relations
                WHERE mechanism_a = ? OR mechanism_b = ?
            ''', (mechanism_id, mechanism_id))
            
            relations = []
            for r in cursor.fetchall():
                related_id = r[1] if r[0] == mechanism_id else r[0]
                relations.append({
                    'related_mechanism': related_id,
                    'relation_type': r[2],
                    'direction': r[3],
                    'description': r[4],
                })
            result['relations'] = relations
        
        if detail == 'full':
            # 获取来源
            cursor.execute(
                'SELECT * FROM mechanism_sources WHERE mechanism_id = ?',
                (mechanism_id,)
            )
            source_cols = [d[0] for d in cursor.description]
            result['sources'] = [dict(zip(source_cols, r)) for r in cursor.fetchall()]
        
        # 按 detail 裁剪
        if detail == 'behavior':
            # 只保留行为相关字段
            keep = {
                'id', 'name', 'friendly_name', 'mechanism_category',
                'behavior_description', 'formula_abstract', 'affected_stats',
            }
            result = {k: v for k, v in result.items() if k in keep and v is not None}
            result['response_type'] = 'mechanism_behavior'
        elif detail == 'relations':
            keep = {
                'id', 'name', 'friendly_name', 'mechanism_category', 'relations',
            }
            result = {k: v for k, v in result.items() if k in keep and v is not None}
            result['response_type'] = 'mechanism_relations'
        else:
            result['response_type'] = 'mechanism_full'
        
        conn.close()
        return result
    
    def search_mechanisms(self, keyword: str) -> List[Dict[str, Any]]:
        """搜索机制"""
        if not self.mechanisms_db.exists():
            return []
        
        conn = sqlite3.connect(self.mechanisms_db)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, name, friendly_name, mechanism_category, source_count 
            FROM mechanisms 
            WHERE id LIKE ? OR name LIKE ? OR friendly_name LIKE ?
            ORDER BY source_count DESC
        ''', (f'%{keyword}%', f'%{keyword}%', f'%{keyword}%'))
        
        results = [
            {
                'id': r[0], 'name': r[1], 'friendly_name': r[2],
                'category': r[3], 'source_count': r[4],
                'response_type': 'mechanism_list',
            }
            for r in cursor.fetchall()
        ]
        conn.close()
        return results
    
    def get_all_mechanisms(self) -> List[Dict[str, Any]]:
        """获取所有机制"""
        if not self.mechanisms_db.exists():
            return []
        
        conn = sqlite3.connect(self.mechanisms_db)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, name, friendly_name, mechanism_category, source_count 
            FROM mechanisms ORDER BY source_count DESC
        ''')
        results = [
            {
                'id': r[0], 'name': r[1], 'friendly_name': r[2],
                'category': r[3], 'source_count': r[4],
                'response_type': 'mechanism_list',
            }
            for r in cursor.fetchall()
        ]
        conn.close()
        return results

    # ========== 辅助查询 (6.3) ==========

    def query_supports(self, skill_id: str, mode: str = 'all',
                       limit: int = 50) -> Dict[str, Any]:
        """
        查询技能的辅助宝石匹配
        
        Args:
            skill_id: 主动技能 ID
            mode: 查询模式
                - 'all': 所有兼容辅助列表
                - 'dps': 按可量化增益分类（quantifiable=1 的辅助）
                - 'utility': 工具型辅助（quantifiable=0 的辅助）
                - 'potential': 潜力推荐
        
        Returns:
            查询结果字典
        """
        if not self.supports_db.exists():
            return {
                'skill_id': skill_id,
                'mode': mode,
                'supports': [],
                'error': 'supports.db不存在，请先运行辅助匹配初始化',
                'response_type': 'support_query',
            }
        
        conn = sqlite3.connect(self.supports_db)
        cursor = conn.cursor()
        
        result = {
            'skill_id': skill_id,
            'mode': mode,
            'response_type': f'support_{mode}',
        }
        
        if mode == 'all':
            # 所有兼容辅助
            cursor.execute('''
                SELECT c.support_id, e.support_name, e.effect_category,
                       e.quantifiable, c.match_reason
                FROM support_compatibility c
                JOIN support_effects e ON c.support_id = e.support_id
                WHERE c.skill_id = ? AND c.compatible = 1
                ORDER BY e.effect_category, e.support_name
                LIMIT ?
            ''', (skill_id, limit))
            
            supports = []
            for r in cursor.fetchall():
                supports.append({
                    'support_id': r[0],
                    'name': r[1],
                    'category': r[2],
                    'quantifiable': bool(r[3]),
                    'match_reason': r[4],
                })
            result['supports'] = supports
            result['total'] = len(supports)
        
        elif mode == 'dps':
            # 可量化增益辅助，按 effect_category 分组
            cursor.execute('''
                SELECT c.support_id, e.support_name, e.effect_category,
                       e.key_stats, e.formula_impact, e.level_scaling
                FROM support_compatibility c
                JOIN support_effects e ON c.support_id = e.support_id
                WHERE c.skill_id = ? AND c.compatible = 1 AND e.quantifiable = 1
                ORDER BY e.effect_category, e.support_name
            ''', (skill_id,))
            
            by_category: Dict[str, List] = {}
            for r in cursor.fetchall():
                cat = r[2]
                entry = {
                    'support_id': r[0],
                    'name': r[1],
                    'formula_impact': r[4],
                }
                # 解析 key_stats
                if r[3]:
                    try:
                        entry['key_stats'] = json.loads(r[3])
                    except (json.JSONDecodeError, TypeError):
                        entry['key_stats'] = r[3]
                # 解析 level_scaling
                if r[5]:
                    try:
                        entry['level_scaling'] = json.loads(r[5])
                    except (json.JSONDecodeError, TypeError):
                        entry['level_scaling'] = r[5]
                
                by_category.setdefault(cat, []).append(entry)
            
            result['by_category'] = by_category
            result['total'] = sum(len(v) for v in by_category.values())
        
        elif mode == 'utility':
            # 工具型辅助（不可量化）
            cursor.execute('''
                SELECT c.support_id, e.support_name, e.effect_category,
                       e.formula_impact, c.match_reason
                FROM support_compatibility c
                JOIN support_effects e ON c.support_id = e.support_id
                WHERE c.skill_id = ? AND c.compatible = 1 AND e.quantifiable = 0
                ORDER BY e.effect_category, e.support_name
                LIMIT ?
            ''', (skill_id, limit))
            
            supports = []
            for r in cursor.fetchall():
                supports.append({
                    'support_id': r[0],
                    'name': r[1],
                    'category': r[2],
                    'formula_impact': r[3],
                    'match_reason': r[4],
                })
            result['supports'] = supports
            result['total'] = len(supports)
        
        elif mode == 'potential':
            # 潜力推荐
            cursor.execute('''
                SELECT p.support_id, e.support_name, p.synergy_type,
                       p.potential_reason, e.effect_category
                FROM support_potential p
                JOIN support_effects e ON p.support_id = e.support_id
                WHERE p.skill_id = ?
                ORDER BY p.synergy_type, e.support_name
            ''', (skill_id,))
            
            potentials = []
            for r in cursor.fetchall():
                potentials.append({
                    'support_id': r[0],
                    'name': r[1],
                    'synergy_type': r[2],
                    'potential_reason': r[3],
                    'effect_category': r[4],
                })
            result['potentials'] = potentials
            result['total'] = len(potentials)
        
        conn.close()
        return result

    # ========== 对比查询 (6.4) ==========

    def compare_entities(self, id1: str, id2: str,
                         detail: str = 'summary') -> Dict[str, Any]:
        """
        并排对比两个同类型实体
        
        Args:
            id1: 第一个实体ID
            id2: 第二个实体ID
            detail: 对比级别 (summary/stats/full)
        
        Returns:
            对比结果字典
        """
        entity1 = self.get_entity(id1, detail=detail)
        entity2 = self.get_entity(id2, detail=detail)
        
        result = {
            'response_type': 'comparison',
            'detail': detail,
        }
        
        if not entity1:
            result['error'] = f'实体 {id1} 不存在'
            return result
        if not entity2:
            result['error'] = f'实体 {id2} 不存在'
            return result
        
        type1 = entity1.get('type', 'unknown')
        type2 = entity2.get('type', 'unknown')
        
        result['entity_1'] = entity1
        result['entity_2'] = entity2
        result['same_type'] = type1 == type2
        
        # 提取差异
        if type1 == type2:
            all_keys = set(entity1.keys()) | set(entity2.keys())
            # 排除元字段
            meta_keys = {'response_type', 'created_at', 'updated_at', 'source_file', 'data_json'}
            compare_keys = all_keys - meta_keys
            
            differences = {}
            same = {}
            only_in_1 = {}
            only_in_2 = {}
            
            for key in sorted(compare_keys):
                v1 = entity1.get(key)
                v2 = entity2.get(key)
                
                if v1 is not None and v2 is None:
                    only_in_1[key] = v1
                elif v1 is None and v2 is not None:
                    only_in_2[key] = v2
                elif v1 != v2:
                    differences[key] = {'entity_1': v1, 'entity_2': v2}
                else:
                    same[key] = v1
            
            result['differences'] = differences
            result['same'] = same
            result['only_in_entity_1'] = only_in_1
            result['only_in_entity_2'] = only_in_2
        
        return result

    # ========== Stat 反查 (6.5) ==========

    def reverse_stat(self, stat_name: str, limit: int = 30) -> Dict[str, Any]:
        """
        反查影响指定 stat 的所有来源
        
        搜索范围：
        1. stat_mappings 表：stat 到 modifier 的映射
        2. entities 表：constant_stats / stats / stat_sets 中包含该 stat 的实体
        
        Args:
            stat_name: stat 名称（支持模糊匹配）
        
        Returns:
            反查结果字典
        """
        result = {
            'stat_name': stat_name,
            'response_type': 'reverse_stat',
            'stat_mappings': [],
            'entities': [],
        }
        
        # 1. 搜索 stat_mappings
        if self.formulas_db.exists():
            conn = sqlite3.connect(self.formulas_db)
            cursor = conn.cursor()
            
            try:
                cursor.execute('''
                    SELECT stat_name, modifier_code, source_file
                    FROM stat_mappings
                    WHERE stat_name LIKE ?
                    LIMIT ?
                ''', (f'%{stat_name}%', limit))
                
                for r in cursor.fetchall():
                    result['stat_mappings'].append({
                        'stat_name': r[0],
                        'modifier_code': r[1],
                        'source_file': r[2],
                    })
            except sqlite3.OperationalError:
                pass
            
            conn.close()
        
        # 2. 搜索 entities（constant_stats 和 stats 中包含该 stat）
        conn = sqlite3.connect(self.entities_db)
        cursor = conn.cursor()
        
        pattern = f'%{stat_name}%'
        cursor.execute('''
            SELECT id, name, type, constant_stats, stats
            FROM entities
            WHERE constant_stats LIKE ? OR stats LIKE ? OR stat_sets LIKE ?
            LIMIT ?
        ''', (pattern, pattern, pattern, limit))
        
        for r in cursor.fetchall():
            entry = {
                'id': r[0],
                'name': r[1],
                'type': r[2],
            }
            
            # 提取匹配的 stat 值
            if r[3]:  # constant_stats
                try:
                    cs = json.loads(r[3])
                    for item in cs:
                        if isinstance(item, list) and len(item) >= 2:
                            if stat_name.lower() in str(item[0]).lower():
                                entry['stat_value'] = item[1]
                                entry['stat_source'] = 'constant_stats'
                                break
                except (json.JSONDecodeError, TypeError):
                    pass
            
            if 'stat_source' not in entry and r[4]:  # stats
                try:
                    sts = json.loads(r[4])
                    for s in sts:
                        if stat_name.lower() in str(s).lower():
                            entry['stat_source'] = 'stats'
                            break
                except (json.JSONDecodeError, TypeError):
                    pass
            
            if 'stat_source' not in entry:
                entry['stat_source'] = 'stat_sets'
            
            result['entities'].append(entry)
        
        conn.close()
        
        result['total_mappings'] = len(result['stat_mappings'])
        result['total_entities'] = len(result['entities'])
        
        return result

    # ========== 公式查询 (6.6) ==========

    def query_formula(self, question: str, entity_id: str = None,
                      chain: bool = False) -> Dict[str, Any]:
        """
        公式查询接口 — 统一入口
        
        Args:
            question: 用户问题
            entity_id: 可选的实体ID
            chain: 是否展示公式引用链路
        """
        if not self.formulas_db.exists():
            return {
                'query': question, 'entity_id': entity_id,
                'universal': [], 'stat_mappings': [], 'gap_formulas': [],
                'error': 'formulas.db不存在，请先运行公式索引初始化',
                'response_type': 'formula_query',
            }
        
        from formula_matcher import FormulaMatcher
        
        matcher = FormulaMatcher(
            formulas_db_path=str(self.formulas_db),
            entities_db_path=str(self.entities_db)
        )
        
        query_result = matcher.query(question, entity_id)
        
        result = {
            'query': query_result.query,
            'entity_id': query_result.entity_id,
            'response_type': 'formula_query',
            'universal': [
                {
                    'id': r.id, 'name': r.name, 'formula': r.formula_text,
                    'domain': r.domain, 'score': r.score, **r.details
                }
                for r in query_result.universal
            ],
            'stat_mappings': [
                {
                    'stat_name': r.name, 'modifier': r.formula_text,
                    'domain': r.domain, **r.details
                }
                for r in query_result.stat_mappings
            ],
            'gap_formulas': [
                {
                    'id': r.id, 'name': r.name, 'formula': r.formula_text,
                    'score': r.score, **r.details
                }
                for r in query_result.gap_formulas
            ],
        }
        
        # 6.6: 公式引用链路
        if chain and result['universal']:
            result['formula_chains'] = self._build_formula_chains(result['universal'])
            result['response_type'] = 'formula_chain'
        
        return result
    
    def _build_formula_chains(self, formulas: List[Dict]) -> List[Dict[str, Any]]:
        """
        构建公式引用链路
        
        遍历每个公式的 formula_text，找到其中引用的其他公式名称，
        递归展开形成链路。
        """
        if not self.formulas_db.exists():
            return []
        
        conn = sqlite3.connect(self.formulas_db)
        cursor = conn.cursor()
        
        # 加载所有通用公式的名称→公式映射
        formula_map: Dict[str, str] = {}
        try:
            cursor.execute('SELECT id, name, formula_text FROM universal_formulas')
            for r in cursor.fetchall():
                formula_map[r[1]] = r[2]
                formula_map[r[0]] = r[2]
        except sqlite3.OperationalError:
            conn.close()
            return []
        
        conn.close()
        
        chains = []
        for formula in formulas:
            chain = self._trace_formula_chain(
                formula.get('name', ''),
                formula.get('formula', ''),
                formula_map,
                visited=set(),
                depth=0,
                max_depth=5,
            )
            if chain:
                chains.append({
                    'root': formula.get('name', ''),
                    'chain': chain,
                })
        
        return chains
    
    def _trace_formula_chain(self, name: str, formula_text: str,
                              formula_map: Dict[str, str],
                              visited: set, depth: int,
                              max_depth: int) -> List[Dict[str, Any]]:
        """递归追踪公式引用链"""
        if depth >= max_depth or name in visited:
            return []
        
        visited.add(name)
        
        chain_items = [{
            'depth': depth,
            'name': name,
            'formula': formula_text[:300] if formula_text else '',
        }]
        
        # 在 formula_text 中搜索引用的其他公式名称
        for ref_name, ref_formula in formula_map.items():
            if ref_name != name and ref_name in (formula_text or ''):
                sub_chain = self._trace_formula_chain(
                    ref_name, ref_formula, formula_map,
                    visited, depth + 1, max_depth
                )
                chain_items.extend(sub_chain)
        
        return chain_items

    def search_formulas_by_stat(self, stat_name: str) -> List[Dict[str, Any]]:
        """按stat名称搜索映射"""
        if not self.formulas_db.exists():
            return []
        
        from formula_matcher import FormulaMatcher
        matcher = FormulaMatcher(str(self.formulas_db), str(self.entities_db))
        results = matcher.query_by_stat(stat_name)
        
        return [
            {
                'stat_name': r.name, 'modifier': r.formula_text,
                'domain': r.domain, 'score': r.score,
                'response_type': 'stat_mapping',
                **r.details
            }
            for r in results
        ]

    def get_formula_stats(self) -> Dict[str, Any]:
        """获取公式索引统计"""
        if not self.formulas_db.exists():
            return {'error': 'formulas.db不存在', 'response_type': 'formula_stats'}
        
        conn = sqlite3.connect(self.formulas_db)
        cursor = conn.cursor()
        
        result = {'response_type': 'formula_stats'}
        for table in ['universal_formulas', 'stat_mappings', 'gap_formulas']:
            try:
                cursor.execute(f'SELECT COUNT(*) FROM {table}')
                result[table] = cursor.fetchone()[0]
            except sqlite3.OperationalError:
                result[table] = 'table_not_found'
        
        conn.close()
        return result

    # ========== 统计信息 ==========
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        stats = {
            'entities': {},
            'mechanisms': {},
            'formulas': {},
            'supports': {},
            'response_type': 'kb_stats',
        }
        
        # 实体统计
        conn = sqlite3.connect(self.entities_db)
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM entities')
        stats['entities']['total'] = cursor.fetchone()[0]
        cursor.execute('SELECT type, COUNT(*) FROM entities GROUP BY type')
        stats['entities']['by_type'] = dict(cursor.fetchall())
        conn.close()
        
        # 机制统计
        if self.mechanisms_db.exists():
            conn = sqlite3.connect(self.mechanisms_db)
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM mechanisms')
            stats['mechanisms']['total'] = cursor.fetchone()[0]
            cursor.execute('SELECT COUNT(*) FROM mechanism_sources')
            stats['mechanisms']['sources'] = cursor.fetchone()[0]
            try:
                cursor.execute('SELECT COUNT(*) FROM mechanism_relations')
                stats['mechanisms']['relations'] = cursor.fetchone()[0]
            except sqlite3.OperationalError:
                stats['mechanisms']['relations'] = 0
            conn.close()
        
        # 公式索引统计
        if self.formulas_db.exists():
            stats['formulas'] = self.get_formula_stats()
        
        # 辅助匹配统计
        if self.supports_db.exists():
            conn = sqlite3.connect(self.supports_db)
            cursor = conn.cursor()
            try:
                cursor.execute('SELECT COUNT(*) FROM support_compatibility')
                stats['supports']['compatibility'] = cursor.fetchone()[0]
                cursor.execute('SELECT COUNT(*) FROM support_effects')
                stats['supports']['effects'] = cursor.fetchone()[0]
                cursor.execute('SELECT COUNT(*) FROM support_potential')
                stats['supports']['potentials'] = cursor.fetchone()[0]
                cursor.execute('SELECT COUNT(*) FROM support_effects WHERE quantifiable = 1')
                stats['supports']['quantifiable'] = cursor.fetchone()[0]
            except sqlite3.OperationalError:
                pass
            conn.close()
        
        return stats


def main():
    parser = argparse.ArgumentParser(description='POE知识库查询工具 v3')
    parser.add_argument('--kb-path', default=None, help='知识库路径')
    
    subparsers = parser.add_subparsers(dest='command', help='命令')
    
    # 实体查询 (6.1)
    entity_parser = subparsers.add_parser('entity', help='实体查询')
    entity_parser.add_argument('id', nargs='?', help='实体ID')
    entity_parser.add_argument('--search', '-s', help='搜索关键词')
    entity_parser.add_argument('--type', '-t', help='按类型查询')
    entity_parser.add_argument('--skill-type', help='按技能类型查询')
    entity_parser.add_argument('--meta', action='store_true', help='列出所有元技能')
    entity_parser.add_argument('--detail', '-d',
                               choices=['summary', 'levels', 'stats', 'full'],
                               default='full', help='详情级别')
    
    # 统计
    subparsers.add_parser('stats', help='统计信息')
    
    # 机制查询 (6.2)
    mech_parser = subparsers.add_parser('mechanism', help='机制查询')
    mech_parser.add_argument('id', nargs='?', help='机制ID')
    mech_parser.add_argument('--search', '-s', help='搜索关键词')
    mech_parser.add_argument('--all', '-a', action='store_true', help='列出所有机制')
    mech_parser.add_argument('--detail', '-d',
                             choices=['behavior', 'relations', 'full'],
                             default='full', help='详情级别')
    
    # 辅助查询 (6.3)
    support_parser = subparsers.add_parser('supports', help='辅助匹配查询')
    support_parser.add_argument('skill_id', help='主动技能ID')
    support_parser.add_argument('--mode', '-m',
                                choices=['all', 'dps', 'utility', 'potential'],
                                default='all', help='查询模式')
    support_parser.add_argument('--limit', '-l', type=int, default=50, help='结果数量限制')
    
    # 对比查询 (6.4)
    compare_parser = subparsers.add_parser('compare', help='对比两个实体')
    compare_parser.add_argument('id1', help='第一个实体ID')
    compare_parser.add_argument('id2', help='第二个实体ID')
    compare_parser.add_argument('--detail', '-d',
                                choices=['summary', 'stats', 'full'],
                                default='summary', help='对比级别')
    
    # Stat 反查 (6.5)
    reverse_parser = subparsers.add_parser('reverse-stat', help='Stat反查')
    reverse_parser.add_argument('stat_name', help='stat名称')
    reverse_parser.add_argument('--limit', '-l', type=int, default=30, help='结果数量限制')
    
    # 公式查询 (6.6)
    formula_parser = subparsers.add_parser('formula', help='公式查询')
    formula_parser.add_argument('--query', '-q', help='问题查询')
    formula_parser.add_argument('--entity', '-e', help='实体ID查询')
    formula_parser.add_argument('--stat', '-s', help='stat名称查询')
    formula_parser.add_argument('--stats', action='store_true', help='公式索引统计')
    formula_parser.add_argument('--chain', action='store_true', help='展示公式引用链路')
    
    args = parser.parse_args()
    
    kb = KnowledgeBaseQuery(args.kb_path)
    
    if args.command == 'entity':
        if args.meta:
            results = kb.get_meta_skills()
            for r in results:
                print(f"{r['id']}: {r['name']}")
        elif args.search:
            results = kb.search_entities(args.search)
            for r in results:
                print(f"{r['id']}: {r['name']} ({r['type']})")
        elif args.type:
            results = kb.get_entities_by_type(args.type)
            for r in results:
                print(f"{r['id']}: {r['name']}")
        elif args.skill_type:
            results = kb.get_entities_by_skill_type(args.skill_type)
            for r in results:
                print(f"{r['id']}: {r['name']}")
        elif args.id:
            entity = kb.get_entity(args.id, detail=args.detail)
            if entity:
                print(json.dumps(entity, indent=2, ensure_ascii=False, default=str))
            else:
                print(f"Entity not found: {args.id}")
        else:
            print("Please specify --search, --type, --skill-type, --meta, or an entity ID")
    
    elif args.command == 'stats':
        stats = kb.get_stats()
        print(json.dumps(stats, indent=2, ensure_ascii=False))
    
    elif args.command == 'mechanism':
        if args.all:
            results = kb.get_all_mechanisms()
            for r in results:
                fname = r.get('friendly_name', '')
                cat = r.get('category', '')
                print(f"{r['id']}: {fname} [{cat}] ({r['source_count']} sources)")
        elif args.search:
            results = kb.search_mechanisms(args.search)
            for r in results:
                fname = r.get('friendly_name', '')
                cat = r.get('category', '')
                print(f"{r['id']}: {fname} [{cat}] ({r['source_count']} sources)")
        elif args.id:
            mech = kb.get_mechanism(args.id, detail=args.detail)
            if mech:
                print(json.dumps(mech, indent=2, ensure_ascii=False, default=str))
            else:
                print(f"Mechanism not found: {args.id}")
        else:
            print("Please specify --all, --search, or a mechanism ID")
    
    elif args.command == 'supports':
        result = kb.query_supports(args.skill_id, mode=args.mode, limit=args.limit)
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    
    elif args.command == 'compare':
        result = kb.compare_entities(args.id1, args.id2, detail=args.detail)
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    
    elif args.command == 'reverse-stat':
        result = kb.reverse_stat(args.stat_name, limit=args.limit)
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    
    elif args.command == 'formula':
        if args.stats:
            fstats = kb.get_formula_stats()
            print(json.dumps(fstats, indent=2, ensure_ascii=False))
        elif args.query:
            result = kb.query_formula(args.query, args.entity, chain=args.chain)
            print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
        elif args.stat:
            results = kb.search_formulas_by_stat(args.stat)
            for r in results:
                print(f"[{r.get('domain', '?')}] {r['stat_name']}")
                print(f"  → {r.get('modifier', '')[:100]}")
        elif args.entity:
            result = kb.query_formula("", args.entity, chain=args.chain)
            print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
        else:
            print("Please specify --query, --entity, --stat, or --stats")
    
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
