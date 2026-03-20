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
import re
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
                       limit: int = 50, summary: bool = False,
                       detail_id: str = None) -> Dict[str, Any]:
        """
        查询技能的辅助宝石匹配
        
        Args:
            skill_id: 主动技能 ID
            mode: 查询模式
                - 'all': 所有兼容辅助列表
                - 'dps': 按可量化增益分类（quantifiable=1 的辅助）
                - 'utility': 工具型辅助（quantifiable=0 的辅助）
                - 'potential': 潜力推荐
            summary: (仅 dps 模式) True 时返回紧凑摘要，每辅助一行
            detail_id: (仅 dps 模式) 指定辅助ID时返回该辅助的完整详情
        
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
            'max_support_gems': 5,  # POE2 硬编码上限：每技能最多5个辅助宝石
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
                       e.key_stats, e.formula_impact, e.level_scaling,
                       e.multipliers
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
                
                # 解析 multipliers JSON（预计算倍率数据）
                if r[6]:
                    try:
                        entry['multipliers'] = json.loads(r[6])
                    except (json.JSONDecodeError, TypeError):
                        entry['multipliers'] = None
                else:
                    entry['multipliers'] = None
                # 解析 key_stats 并拆分正/负效果（支持 Flag 型）
                if r[3]:
                    try:
                        raw_stats = json.loads(r[3])
                    except (json.JSONDecodeError, TypeError):
                        raw_stats = []
                    
                    entry['key_stats'] = raw_stats
                    positive = []
                    negative = []
                    has_flag_restriction = False
                    has_conditional_category = False
                    
                    for ks in raw_stats:
                        val = ks.get('value')
                        stat = ks.get('stat', '')
                        source = ks.get('source', '')
                        
                        # Flag 型 stat（无数值，从 FLAG_SEMANTIC_MAP 来）
                        if source == 'flag':
                            polarity = ks.get('polarity', 'mechanic')
                            flag_desc = ks.get('flag_desc', stat.replace('_', ' '))
                            item = {
                                'stat': stat,
                                'value': None,
                                'desc': flag_desc,
                                'is_flag': True,
                            }
                            if polarity == 'restriction':
                                negative.append(item)
                                has_flag_restriction = True
                            elif polarity == 'benefit':
                                positive.append(item)
                            # mechanic 类型不计入正/负
                            continue
                        
                        # 数值型 stat
                        if val is None:
                            continue
                        
                        desc = self._format_stat_effect(stat, val)
                        item = {'stat': stat, 'value': val, 'desc': desc}
                        
                        if isinstance(val, (int, float)) and val < 0:
                            negative.append(item)
                        elif isinstance(val, (int, float)) and val != 0:
                            positive.append(item)
                            # 检查是否属于条件型分类
                            lower_stat = stat.lower()
                            if any(kw in lower_stat for kw in ('chain', 'projectile', 'fork', 'number_of')):
                                has_conditional_category = True
                    
                    entry['positive_effects'] = positive
                    entry['negative_effects'] = negative
                    
                    # 问题3: 判断 DPS 计算类型
                    has_numeric_pos = any(not p.get('is_flag') for p in positive)
                    has_numeric_neg = any(not n.get('is_flag') for n in negative)
                    
                    if has_flag_restriction:
                        # 有 Flag 限制 → 条件型（取决于 build 是否受限）
                        entry['dps_type'] = 'conditional'
                        entry['dps_note'] = '收益取决于build是否受Flag限制影响'
                    elif has_conditional_category:
                        # 有多目标类 stat（chain/projectile/fork）→ 条件型
                        entry['dps_type'] = 'conditional'
                        entry['dps_note'] = '多目标收益取决于实际命中数'
                    elif has_numeric_pos and has_numeric_neg:
                        # 有数值正面和数值负面 → 直接可量化
                        entry['dps_type'] = 'direct'
                    elif has_numeric_pos and not has_numeric_neg:
                        # 只有正面无负面 → 直接可量化（纯增益）
                        entry['dps_type'] = 'direct'
                        entry['dps_note'] = '纯增益，无代价'
                    else:
                        entry['dps_type'] = 'utility'
                else:
                    entry['key_stats'] = []
                    entry['positive_effects'] = []
                    entry['negative_effects'] = []
                    entry['dps_type'] = 'utility'
                
                # 解析 level_scaling
                if r[5]:
                    try:
                        entry['level_scaling'] = json.loads(r[5])
                    except (json.JSONDecodeError, TypeError):
                        entry['level_scaling'] = r[5]
                
                by_category.setdefault(cat, []).append(entry)
            
            result['by_category'] = by_category
            result['total'] = sum(len(v) for v in by_category.values())
            
            # Direction A: --detail <id> 展开单辅助完整详情
            if detail_id:
                found_entry = None
                found_cat = None
                for cat, entries in by_category.items():
                    for entry in entries:
                        if entry['support_id'] == detail_id:
                            found_entry = entry
                            found_cat = cat
                            break
                    if found_entry:
                        break
                if found_entry:
                    result['by_category'] = {found_cat: [found_entry]}
                    result['total'] = 1
                    result['detail_for'] = detail_id
                else:
                    result['by_category'] = {}
                    result['total'] = 0
                    result['detail_for'] = detail_id
                    result['error'] = f'辅助 {detail_id} 不在 dps 兼容列表中'
            
            # Direction A: --summary 紧凑摘要模式
            # 每辅助压缩为一行描述，去掉 key_stats 原始数据
            elif summary:
                # 获取技能的基础覆盖数据（用于动态计算 coverage 倍率）
                base_cov = self._get_skill_base_coverage(skill_id)
                # 获取技能的三维度 profile（用于语义有效性检查）
                skill_profile = self._get_skill_profile(skill_id)
                
                # 读取所有辅助的 restrictions（批量查询）
                support_ids_in_result = []
                for cat_entries in by_category.values():
                    for e in cat_entries:
                        support_ids_in_result.append(e['support_id'])
                
                restrictions_map: Dict[str, Any] = {}
                if support_ids_in_result:
                    placeholders = ','.join(['?'] * len(support_ids_in_result))
                    cursor.execute(
                        f'SELECT support_id, restrictions FROM support_effects WHERE support_id IN ({placeholders})',
                        support_ids_in_result
                    )
                    for r in cursor.fetchall():
                        if r[1]:
                            try:
                                restrictions_map[r[0]] = json.loads(r[1])
                            except (json.JSONDecodeError, TypeError):
                                pass
                
                compact_cats: Dict[str, List] = {}
                for cat, entries in by_category.items():
                    compact_list = []
                    for entry in entries:
                        sid = entry['support_id']
                        
                        # 语义有效性检查
                        restrictions = restrictions_map.get(sid)
                        effectiveness = self._check_effectiveness(restrictions, skill_profile)
                        eff_rating = effectiveness['rating']
                        
                        # 跳过 fatal（致命不匹配）
                        if eff_rating == 'fatal':
                            continue
                        
                        compact = {
                            'id': sid,
                            'name': entry['name'],
                            'dps_type': entry.get('dps_type', 'utility'),
                        }
                        
                        # 标注语义有效性（非 effective 时才显示）
                        if eff_rating != 'effective':
                            compact['effectiveness'] = eff_rating
                            compact['effectiveness_reason'] = effectiveness.get('reason', '')
                        
                        # 正面效果 → 一行描述
                        pos = entry.get('positive_effects', [])
                        if pos:
                            compact['pos'] = [
                                p.get('desc', p.get('flag_desc', p.get('stat', '')))
                                for p in pos
                            ]
                        # 负面效果 → 一行描述
                        neg = entry.get('negative_effects', [])
                        if neg:
                            compact['neg'] = [
                                n.get('desc', n.get('flag_desc', n.get('stat', '')))
                                for n in neg
                            ]
                        # dps_note 保留
                        if entry.get('dps_note'):
                            compact['note'] = entry['dps_note']
                        # formula_impact 保留但截断
                        if entry.get('formula_impact'):
                            fi = entry['formula_impact']
                            compact['impact'] = fi[:120] + '…' if len(fi) > 120 else fi
                        
                        # 📊 期望效率倍率（ineffective 时标注为 N/A）
                        if eff_rating == 'ineffective':
                            compact['efficiency'] = 'N/A (增益不适用)'
                        elif entry.get('multipliers'):
                            eff = self._compute_efficiency(entry['multipliers'], base_cov)
                            compact['efficiency'] = self._format_efficiency_line(eff)
                        
                        compact_list.append(compact)
                    compact_cats[cat] = compact_list
                result['by_category'] = compact_cats
                result['summary_mode'] = True
                result['base_coverage'] = base_cov
                result['skill_profile'] = {
                    k: sorted(v) for k, v in skill_profile.items() if v
                }
        
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

    def _get_skill_base_coverage(self, skill_id: str) -> Dict[str, int]:
        """
        获取技能的基础覆盖数据（连锁次数、投射物数量）。
        从 entities.db 的 constant_stats 和 display_stats 中提取。
        
        Returns:
            {'base_chains': int, 'base_projectiles': int}
        """
        result = {'base_chains': 0, 'base_projectiles': 1}  # 默认 0 连锁、1 投射物
        
        conn = sqlite3.connect(self.entities_db)
        cursor = conn.cursor()
        cursor.execute(
            'SELECT constant_stats, display_stats FROM entities WHERE id = ?',
            (skill_id,)
        )
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return result
        
        # 从 constant_stats 提取
        if row[0]:
            try:
                cs = json.loads(row[0])
                for item in cs:
                    if isinstance(item, list) and len(item) >= 2:
                        sn = str(item[0]).lower()
                        sv = item[1]
                        if isinstance(sv, (int, float)):
                            if 'number_of_chains' in sn:
                                result['base_chains'] = int(sv)
                            elif 'number_of_additional_projectiles' in sn or 'projectile_count' in sn:
                                result['base_projectiles'] += int(sv)
            except (json.JSONDecodeError, TypeError):
                pass
        
        # 从 display_stats 中补充（如 "Chains 5 times"）
        if row[1]:
            try:
                ds = json.loads(row[1])
                for d in ds:
                    if isinstance(d, str):
                        d_lower = d.lower().replace('\n', ' ')
                        m = re.search(r'chains?\s+(\d+)\s+times?', d_lower)
                        if m:
                            result['base_chains'] = max(result['base_chains'], int(m.group(1)))
                        m = re.search(r'fires?\s+(\d+)\s+(?:additional\s+)?projectiles?', d_lower)
                        if m:
                            result['base_projectiles'] = max(result['base_projectiles'], int(m.group(1)))
            except (json.JSONDecodeError, TypeError):
                pass
        
        return result
    
    def _compute_efficiency(self, multipliers: Dict[str, Any],
                            base_coverage: Dict[str, int]) -> Dict[str, Any]:
        """
        计算单个辅助的总效率倍率。
        
        总效率 = 单体DPS × 目标数量
        单体DPS = damage × speed
        目标数量 = chain_ratio × projectile_ratio
        
        Args:
            multipliers: 预计算的 multipliers JSON
            base_coverage: {'base_chains': int, 'base_projectiles': int}
        
        Returns:
            {
                'single_min': float,  # 单体 DPS 最小倍率
                'single_max': float,  # 单体 DPS 最大倍率
                'target_ratio': float,  # 目标数量倍率
                'total_min': float,   # 总效率最小
                'total_max': float,   # 总效率最大
                'breakdown': str,     # 人类可读分解
            }
        """
        dmg = multipliers.get('damage', {})
        spd = multipliers.get('speed', {})
        cov = multipliers.get('coverage_add', {})
        
        dmg_min = dmg.get('min', 1.0)
        dmg_max = dmg.get('max', 1.0)
        spd_min = spd.get('min', 1.0)
        spd_max = spd.get('max', 1.0)
        
        single_min = round(dmg_min * spd_min, 4)
        single_max = round(dmg_max * spd_max, 4)
        
        # 目标数量倍率
        target_ratio = 1.0
        added_chains = cov.get('chains', 0)
        chains_more = cov.get('chains_more', 0)  # 乘法系数 (1 = 100% more → ×2.0)
        added_proj = cov.get('projectiles', 0)
        
        bc = base_coverage['base_chains']
        bp = base_coverage['base_projectiles']
        
        # 连锁计算：总连锁 = (1 + base + added) × (1 + chains_more)
        total_chains_before = 1 + bc + added_chains
        more_multiplier = 1.0 + chains_more  # chains_more=1 → ×2.0
        total_chains_after = total_chains_before * more_multiplier
        base_chains_total = 1 + bc
        
        if total_chains_after != base_chains_total:
            target_ratio *= total_chains_after / base_chains_total
        
        if added_proj != 0 and bp > 0:
            # proj_ratio = (base + added) / base
            target_ratio *= (bp + added_proj) / bp
        
        target_ratio = round(target_ratio, 4)
        
        total_min = round(single_min * target_ratio, 4)
        total_max = round(single_max * target_ratio, 4)
        
        # 构建 breakdown 文本
        parts = []
        if dmg_min != 1.0 or dmg_max != 1.0:
            if dmg_min == dmg_max:
                parts.append(f"伤害 x{dmg_min:.2f}")
            else:
                parts.append(f"伤害 x{dmg_min:.2f} ~ x{dmg_max:.2f}")
        if spd_min != 1.0 or spd_max != 1.0:
            if spd_min == spd_max:
                parts.append(f"速度 x{spd_min:.2f}")
            else:
                parts.append(f"速度 x{spd_min:.2f} ~ x{spd_max:.2f}")
        if target_ratio != 1.0:
            target_detail = []
            if added_chains != 0 or chains_more != 0:
                final_chains = int(total_chains_after)
                if chains_more != 0 and added_chains == 0:
                    target_detail.append(
                        f"连锁 {base_chains_total}→{final_chains} (MORE +{int(chains_more*100)}%)"
                    )
                elif chains_more != 0 and added_chains != 0:
                    target_detail.append(
                        f"连锁 {base_chains_total}→{final_chains} (+{added_chains}, MORE +{int(chains_more*100)}%)"
                    )
                else:
                    target_detail.append(f"连锁 {base_chains_total}→{1+bc+added_chains}")
            if added_proj != 0:
                target_detail.append(f"投射物 {bp}→{bp+added_proj}")
            parts.append(f"目标 x{target_ratio:.2f} ({', '.join(target_detail)})")
        
        breakdown = ' | '.join(parts) if parts else '无倍率变化'
        
        return {
            'single_min': single_min,
            'single_max': single_max,
            'target_ratio': target_ratio,
            'total_min': total_min,
            'total_max': total_max,
            'breakdown': breakdown,
        }
    
    def _format_efficiency_line(self, eff: Dict[str, Any]) -> str:
        """格式化效率倍率为一行文本
        
        方案 A：单维度简化 + 范围加空格
        - 单维度: x1.04 ~ x1.20 (伤害)
        - 多维度: x1.15 (伤害 x1.35 | 速度 x0.85)
        - 固定值单维度: x1.25 (伤害)
        - 固定值多维度: x1.25 (伤害 x1.25 | 速度 x1.00)  -- 实际不会出现
        - 无变化: x1.00 (无倍率变化)
        """
        total_min = eff['total_min']
        total_max = eff['total_max']
        breakdown = eff['breakdown']
        
        # 判断是否为单维度：breakdown 中只有一个维度标签，没有 |
        is_single_dim = '|' not in breakdown and breakdown != '无倍率变化'
        
        if is_single_dim:
            # 提取维度标签（如 "伤害"、"速度"、"目标"）
            dim_label = breakdown.split(' ')[0] if breakdown else ''
            if total_min == total_max:
                return f"x{total_min:.2f} ({dim_label})"
            else:
                return f"x{total_min:.2f} ~ x{total_max:.2f} ({dim_label})"
        else:
            # 多维度或无变化：保留完整 breakdown
            if total_min == total_max:
                return f"x{total_min:.2f} ({breakdown})"
            else:
                return f"x{total_min:.2f} ~ x{total_max:.2f} ({breakdown})"

    def _format_stat_effect(self, stat_name: str, value) -> str:
        """
        将 stat 名称 + 数值转换为人类可读的效果描述。
        
        示例：
            ("support_chain_hit_damage_+%_final", -30) → "30% LESS hit damage"
            ("number_of_chains", 1)                    → "+1 chains"
            ("support_multiple_damage_+%_final", -35)  → "35% LESS damage"
            ("cast_speed_+%_final", 15)                → "15% MORE cast speed"
        """
        lower = stat_name.lower()
        
        # MORE/LESS 乘数（_final 后缀）
        if 'final' in lower:
            abs_val = abs(value) if isinstance(value, (int, float)) else value
            label = 'MORE' if isinstance(value, (int, float)) and value > 0 else 'LESS'
            # 从 stat 名称中提取被影响的属性
            subject = lower
            for prefix in ('support_', 'active_skill_'):
                subject = subject.replace(prefix, '')
            subject = subject.replace('_+%_final', '').replace('_final', '')
            subject = subject.replace('_', ' ').strip()
            return f"{abs_val}% {label} {subject}"
        
        # 百分比增减（_+% 后缀）
        if '+%' in lower and 'final' not in lower:
            sign = '+' if isinstance(value, (int, float)) and value > 0 else ''
            subject = lower.replace('_+%', '').replace('_', ' ').strip()
            return f"{sign}{value}% {subject}"
        
        # 数量型（number_of_xxx / additional_xxx）
        if 'number_of' in lower or 'additional' in lower:
            subject = lower
            for prefix in ('number_of_', 'additional_'):
                subject = subject.replace(prefix, '')
            subject = subject.replace('_', ' ').strip()
            sign = '+' if isinstance(value, (int, float)) and value > 0 else ''
            return f"{sign}{value} {subject}"
        
        # 通用格式
        readable = stat_name.replace('_', ' ')
        return f"{readable}: {value}"
    
    # ========== 语义有效性检查 (6.3.1) ==========
    
    # 技能标签 → 三维度映射表
    _TAG_TO_DAMAGE_TYPE = {
        'Fire': 'fire', 'Cold': 'cold', 'Lightning': 'lightning',
        'Chaos': 'chaos', 'Physical': 'physical',
    }
    _TAG_TO_ATTACK_MODE = {
        'Spell': 'spell', 'Attack': 'attack', 'Melee': 'melee',
        'Projectile': 'projectile', 'Area': 'area', 'RangedAttack': 'ranged',
    }
    _TAG_TO_DAMAGE_SCOPE = {
        'Hit': 'hit', 'DamageOverTime': 'dot', 'Ailment': 'ailment',
    }
    
    def _get_skill_profile(self, skill_id: str) -> Dict[str, set]:
        """
        从技能的 skill_types 标签中提取三维度 profile。
        
        Returns:
            {
                'damage_types': {'lightning', 'elemental'},
                'attack_modes': {'spell'},
                'damage_scopes': {'hit'},
            }
        """
        profile: Dict[str, set] = {
            'damage_types': set(),
            'attack_modes': set(),
            'damage_scopes': set(),
        }
        
        conn = sqlite3.connect(self.entities_db)
        cursor = conn.cursor()
        cursor.execute('SELECT skill_types FROM entities WHERE id = ?', (skill_id,))
        row = cursor.fetchone()
        conn.close()
        
        if not row or not row[0]:
            return profile
        
        try:
            skill_types = json.loads(row[0])
        except (json.JSONDecodeError, TypeError):
            return profile
        
        if not isinstance(skill_types, list):
            return profile
        
        for tag in skill_types:
            if tag in self._TAG_TO_DAMAGE_TYPE:
                profile['damage_types'].add(self._TAG_TO_DAMAGE_TYPE[tag])
            if tag in self._TAG_TO_ATTACK_MODE:
                profile['attack_modes'].add(self._TAG_TO_ATTACK_MODE[tag])
            if tag in self._TAG_TO_DAMAGE_SCOPE:
                profile['damage_scopes'].add(self._TAG_TO_DAMAGE_SCOPE[tag])
        
        # 派生：如果有具体元素类型但没有 'elemental'，自动添加
        elem_types = {'fire', 'cold', 'lightning'}
        if profile['damage_types'] & elem_types:
            profile['damage_types'].add('elemental')
        
        # 派生：有 Damage 标签但无 DamageOverTime → 推断为 hit
        tag_set = set(skill_types)
        if 'Damage' in tag_set and 'DamageOverTime' not in tag_set:
            profile['damage_scopes'].add('hit')
        
        # 派生：有 DamageOverTime → 添加 dot
        if 'DamageOverTime' in tag_set:
            profile['damage_scopes'].add('dot')
        
        return profile
    
    def _check_effectiveness(self, restrictions: Dict[str, Any],
                             skill_profile: Dict[str, set]) -> Dict[str, Any]:
        """
        检查辅助的语义限制与技能 profile 的匹配度。
        
        四级评分：
        - 'effective': 所有限定维度匹配，或无限制
        - 'partial': 部分维度匹配
        - 'ineffective': 核心增益维度不匹配（辅助的增益不适用于技能）
        - 'fatal': 阻断维度命中技能的核心伤害类型
        
        Returns:
            {
                'rating': 'effective'|'partial'|'ineffective'|'fatal',
                'reason': str,
                'blocked_types': [...],  # fatal 时
                'unmatched_requires': {...},  # ineffective 时
            }
        """
        if not restrictions:
            return {'rating': 'effective', 'reason': '无语义限制'}
        
        blocks = restrictions.get('blocks', {})
        requires = restrictions.get('requires', {})
        
        result: Dict[str, Any] = {'rating': 'effective', 'reason': ''}
        
        # 1. 检查 blocks（致命检查优先）
        if blocks:
            blocked_dt = set(blocks.get('damage_types', []))
            blocked_ail = set(blocks.get('ailments', []))
            
            skill_dt = skill_profile.get('damage_types', set())
            
            # 致命：辅助阻断的伤害类型覆盖了技能的全部伤害类型
            if blocked_dt and skill_dt:
                # 检查 skill 是否完全依赖被阻断的类型
                # 例如：deal_no_elemental → blocks {fire,cold,lightning,elemental}
                #       技能 profile = {lightning, elemental}
                #       → skill_dt 是 blocked_dt 的子集 → fatal
                remaining_dt = skill_dt - blocked_dt
                # 'elemental' 是派生的，如果具体类型全被 block，elemental 也无效
                if remaining_dt == {'elemental'} and not (skill_dt & {'physical', 'chaos'} - blocked_dt):
                    remaining_dt = set()
                
                if not remaining_dt:
                    blocked_list = sorted(blocked_dt & skill_dt)
                    return {
                        'rating': 'fatal',
                        'reason': f'辅助阻断了技能的全部伤害类型: {blocked_list}',
                        'blocked_types': blocked_list,
                    }
        
        # 2. 检查 requires（有效性检查）
        if requires:
            unmatched: Dict[str, Any] = {}
            match_count = 0
            total_dims = 0
            
            for dim_key in ('damage_types', 'attack_modes', 'damage_scopes'):
                req_set = set(requires.get(dim_key, []))
                if not req_set:
                    continue
                total_dims += 1
                
                skill_set = skill_profile.get(dim_key, set())
                
                if req_set & skill_set:
                    match_count += 1
                else:
                    unmatched[dim_key] = {
                        'required': sorted(req_set),
                        'skill_has': sorted(skill_set),
                    }
            
            if total_dims > 0 and match_count == 0:
                return {
                    'rating': 'ineffective',
                    'reason': f'辅助增益不适用于技能 (0/{total_dims} 维度匹配)',
                    'unmatched_requires': unmatched,
                }
            elif unmatched:
                return {
                    'rating': 'partial',
                    'reason': f'部分增益适用 ({match_count}/{total_dims} 维度匹配)',
                    'unmatched_requires': unmatched,
                }
        
        result['reason'] = '所有维度匹配'
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
    support_parser.add_argument('--summary', action='store_true',
                                help='(dps模式) 紧凑摘要输出，每辅助一行')
    support_parser.add_argument('--detail', dest='detail_id', default=None,
                                help='(dps模式) 展开指定辅助ID的完整详情')
    
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
        result = kb.query_supports(
            args.skill_id, mode=args.mode, limit=args.limit,
            summary=getattr(args, 'summary', False),
            detail_id=getattr(args, 'detail_id', None),
        )
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
