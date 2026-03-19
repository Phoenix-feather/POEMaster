#!/usr/bin/env python3
"""
POE实体索引模块
SQLite实体索引，存储技能、物品、天赋等实体的完整属性
"""

import sqlite3
import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

# 导入数据扫描模块
try:
    from data_scanner import POBDataScanner, ScanResult, DataType
except ImportError:
    # 如果导入失败，定义必要的类
    pass


class EntityIndex:
    """实体索引管理器"""
    
    def __init__(self, db_path: str):
        """
        初始化实体索引
        
        Args:
            db_path: SQLite数据库文件路径
        """
        self.db_path = Path(db_path)
        self.conn: Optional[sqlite3.Connection] = None
        self._init_database()
    
    def _init_database(self):
        """初始化数据库"""
        # 确保目录存在
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 连接数据库
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        
        # 创建表
        self._create_tables()
        self._migrate_schema()
        self._create_indexes()
    
    def _create_tables(self):
        """创建表结构"""
        cursor = self.conn.cursor()
        
        # 实体表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS entities (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                type TEXT NOT NULL,
                skill_types TEXT,
                constant_stats TEXT,
                stats TEXT,
                description TEXT,
                reservation TEXT,
                mod_tags TEXT,
                weight_keys TEXT,
                affix_type TEXT,
                mod_data TEXT,
                data_json TEXT,
                source_file TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                
                -- 技能定义字段
                base_type_name TEXT,
                cast_time REAL,
                quality_stats TEXT,
                levels TEXT,
                stat_sets TEXT,
                support INTEGER DEFAULT 0,
                require_skill_types TEXT,
                add_skill_types TEXT,
                exclude_skill_types TEXT,
                is_trigger INTEGER DEFAULT 0,
                hidden INTEGER DEFAULT 0,
                
                -- 宝石定义字段
                game_id TEXT,
                variant_id TEXT,
                granted_effect_id TEXT,
                tags TEXT,
                gem_type TEXT,
                tag_string TEXT,
                req_str INTEGER DEFAULT 0,
                req_dex INTEGER DEFAULT 0,
                req_int INTEGER DEFAULT 0,
                tier INTEGER,
                natural_max_level INTEGER,
                additional_stat_set1 TEXT,
                additional_stat_set2 TEXT,
                weapon_requirements TEXT,
                gem_family TEXT,
                
                -- 唯一物品字段
                requires_level INTEGER,
                granted_skill TEXT,
                implicits INTEGER,
                variant TEXT,
                source TEXT,
                
                -- 天赋节点字段
                ascendancy_name TEXT,
                is_notable INTEGER DEFAULT 0,
                is_keystone INTEGER DEFAULT 0,
                stats_node TEXT,
                reminder_text TEXT,
                
                -- [v2新增] 统一描述文本字段（天赋节点和装备词缀共用）
                stat_descriptions TEXT,  -- JSON数组，存储描述文本
                
                -- [v3新增] 宝石→隐藏技能关联
                additional_granted_effect_ids TEXT,  -- JSON数组，additionalGrantedEffectId1/2/3
                
                -- [v4新增] 解读层预计算字段
                summary TEXT,           -- 核心机制描述（从技能专属statMap覆盖+description提炼）
                key_mechanics TEXT,      -- JSON数组: [{name, stat, formula, effect}, ...] 结构化机制列表
                display_stats TEXT       -- JSON数组: ["描述行1", "描述行2", ...] StatDescriber生成的人类可读描述
            )
        ''')
        
        # 已知路径表（缓存）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS known_paths (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                path_json TEXT,
                confirmed BOOLEAN DEFAULT 0,
                confidence REAL DEFAULT 0.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        self.conn.commit()
    
    def _migrate_schema(self):
        """Schema 迁移：向已有表添加新列（如果缺失）"""
        cursor = self.conn.cursor()
        
        # 获取当前表的列名
        cursor.execute('PRAGMA table_info(entities)')
        existing_columns = {row[1] for row in cursor.fetchall()}
        
        # v3 迁移: additional_granted_effect_ids
        if 'additional_granted_effect_ids' not in existing_columns:
            cursor.execute('''
                ALTER TABLE entities ADD COLUMN additional_granted_effect_ids TEXT
            ''')
            self.conn.commit()
        
        # v4 迁移: 解读层预计算字段
        for col_name in ('summary', 'key_mechanics', 'display_stats'):
            if col_name not in existing_columns:
                cursor.execute(f'ALTER TABLE entities ADD COLUMN {col_name} TEXT')
        self.conn.commit()
    
    def _create_indexes(self):
        """创建索引"""
        cursor = self.conn.cursor()
        
        # 实体表索引
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(type)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_entities_name ON entities(name)')
        
        # skillTypes全文索引（使用LIKE模拟）
        # SQLite的FTS需要额外配置，这里用普通索引
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_entities_skill_types ON entities(skill_types)')
        
        self.conn.commit()
    
    def insert_entity(self, entity: Dict[str, Any], source_file: str = None):
        """
        插入实体
        
        Args:
            entity: 实体数据
            source_file: 来源文件
        """
        cursor = self.conn.cursor()
        
        # 提取ID和名称
        entity_id = entity.get('id') or entity.get('name', '')
        name = entity.get('name', entity_id) or 'Unknown'
        
        # 跳过无效实体
        if not entity_id:
            return
        
        # 确定类型
        entity_type = entity.get('type', 'unknown')
        
        # 序列化复杂数据 - 原有字段
        skill_types = json.dumps(entity.get('skill_types', []), ensure_ascii=False)
        constant_stats = json.dumps(entity.get('constant_stats', []), ensure_ascii=False)
        stats = json.dumps(entity.get('stats', []), ensure_ascii=False)
        reservation = json.dumps(entity.get('reservation', {}), ensure_ascii=False)
        mod_tags = json.dumps(entity.get('mod_tags', []), ensure_ascii=False)
        weight_keys = json.dumps(entity.get('weight_keys', []), ensure_ascii=False)
        affix_type = entity.get('affix_type', '') or ''
        mod_data = json.dumps(entity.get('mod_data', []), ensure_ascii=False)
        data_json = json.dumps(entity, ensure_ascii=False)
        
        # 序列化新字段 - 技能定义
        base_type_name = entity.get('base_type_name')
        cast_time = entity.get('cast_time')
        quality_stats = json.dumps(entity.get('quality_stats', []), ensure_ascii=False)
        levels = json.dumps(entity.get('levels', {}), ensure_ascii=False)
        stat_sets = json.dumps(entity.get('stat_sets', {}), ensure_ascii=False)
        support = 1 if entity.get('support') else 0
        require_skill_types = json.dumps(entity.get('require_skill_types', []), ensure_ascii=False)
        add_skill_types = json.dumps(entity.get('add_skill_types', []), ensure_ascii=False)
        exclude_skill_types = json.dumps(entity.get('exclude_skill_types', []), ensure_ascii=False)
        is_trigger = 1 if entity.get('is_trigger') else 0
        hidden = 1 if entity.get('hidden') else 0
        
        # 序列化新字段 - 宝石定义
        game_id = entity.get('game_id')
        variant_id = entity.get('variant_id')
        granted_effect_id = entity.get('granted_effect_id')
        tags = json.dumps(entity.get('tags', {}), ensure_ascii=False)
        gem_type = entity.get('gem_type')
        tag_string = entity.get('tag_string')
        req_str = entity.get('req_str', 0)
        req_dex = entity.get('req_dex', 0)
        req_int = entity.get('req_int', 0)
        tier = entity.get('tier')
        natural_max_level = entity.get('natural_max_level')
        additional_stat_set1 = entity.get('additional_stat_set1')
        additional_stat_set2 = entity.get('additional_stat_set2')
        weapon_requirements = entity.get('weapon_requirements')
        gem_family = entity.get('gem_family')
        
        # 序列化新字段 - 唯一物品
        requires_level = entity.get('requires_level')
        granted_skill = entity.get('granted_skill')
        implicits = entity.get('implicits')
        variant = json.dumps(entity.get('variant', []), ensure_ascii=False)
        source = entity.get('source')
        
        # 序列化新字段 - 天赋节点
        ascendancy_name = entity.get('ascendancy_name')
        is_notable = 1 if entity.get('is_notable') else 0
        is_keystone = 1 if entity.get('is_keystone') else 0
        stats_node = json.dumps(entity.get('stats_node', []), ensure_ascii=False)
        reminder_text = json.dumps(entity.get('reminder_text', []), ensure_ascii=False)
        
        # [v2新增] stat_descriptions: 统一存储天赋节点和装备词缀的描述文本
        # 天赋节点使用 stats_node，装备词缀使用 descriptions
        stat_descriptions = None
        if entity.get('stat_descriptions'):
            stat_descriptions = json.dumps(entity.get('stat_descriptions'), ensure_ascii=False)
        elif entity.get('descriptions'):
            stat_descriptions = json.dumps(entity.get('descriptions'), ensure_ascii=False)
        
        # [v3新增] additional_granted_effect_ids: 宝石→隐藏技能关联
        # 从 Gems.lua 的 additionalGrantedEffectId1/2/3 提取
        additional_granted_effect_ids = None
        if entity.get('additional_granted_effect_ids'):
            additional_granted_effect_ids = json.dumps(
                entity.get('additional_granted_effect_ids'), ensure_ascii=False
            )
        
        # [v4新增] 解读层预计算字段
        summary = entity.get('summary')  # 核心机制描述文本
        key_mechanics = None
        if entity.get('key_mechanics'):
            key_mechanics = json.dumps(entity.get('key_mechanics'), ensure_ascii=False)
        display_stats = None
        if entity.get('display_stats'):
            display_stats = json.dumps(entity.get('display_stats'), ensure_ascii=False)
        
        cursor.execute('''
            INSERT OR REPLACE INTO entities 
            (id, name, type, skill_types, constant_stats, stats, description, reservation, mod_tags, weight_keys, affix_type, mod_data, data_json, source_file, updated_at,
             base_type_name, cast_time, quality_stats, levels, stat_sets, support, require_skill_types, add_skill_types, exclude_skill_types, is_trigger, hidden,
             game_id, variant_id, granted_effect_id, tags, gem_type, tag_string, req_str, req_dex, req_int, tier, natural_max_level, additional_stat_set1, additional_stat_set2, weapon_requirements, gem_family,
             requires_level, granted_skill, implicits, variant, source,
             ascendancy_name, is_notable, is_keystone, stats_node, reminder_text, stat_descriptions,
             additional_granted_effect_ids,
             summary, key_mechanics, display_stats)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?,
                    ?,
                    ?, ?, ?)
        ''', (
            entity_id,
            name,
            entity_type,
            skill_types,
            constant_stats,
            stats,
            entity.get('description'),
            reservation,
            mod_tags,
            weight_keys,
            affix_type,
            mod_data,
            data_json,
            source_file,
            # 技能定义字段
            base_type_name,
            cast_time,
            quality_stats,
            levels,
            stat_sets,
            support,
            require_skill_types,
            add_skill_types,
            exclude_skill_types,
            is_trigger,
            hidden,
            # 宝石定义字段
            game_id,
            variant_id,
            granted_effect_id,
            tags,
            gem_type,
            tag_string,
            req_str,
            req_dex,
            req_int,
            tier,
            natural_max_level,
            additional_stat_set1,
            additional_stat_set2,
            weapon_requirements,
            gem_family,
            # 唯一物品字段
            requires_level,
            granted_skill,
            implicits,
            variant,
            source,
            # 天赋节点字段
            ascendancy_name,
            is_notable,
            is_keystone,
            stats_node,
            reminder_text,
            # v2新增字段
            stat_descriptions,
            # v3新增字段
            additional_granted_effect_ids,
            # v4新增字段 - 解读层
            summary,
            key_mechanics,
            display_stats,
        ))
        
        self.conn.commit()
    
    def insert_entities_from_scan(self, scan_results: List[Any]):
        """
        从扫描结果插入实体
        
        Args:
            scan_results: 扫描结果列表
        """
        for result in scan_results:
            source_file = result.file_path
            
            for entity in result.entities:
                # 设置类型
                if result.data_type:
                    entity['type'] = result.data_type.value
                
                self.insert_entity(entity, source_file)
    
    def get_entity_by_id(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """
        按ID查询实体
        
        Args:
            entity_id: 实体ID
            
        Returns:
            实体数据或None
        """
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM entities WHERE id = ?', (entity_id,))
        row = cursor.fetchone()
        
        if row:
            return self._row_to_dict(row)
        return None
    
    def get_entities_by_type(self, entity_type: str) -> List[Dict[str, Any]]:
        """
        按类型查询实体
        
        Args:
            entity_type: 实体类型
            
        Returns:
            实体列表
        """
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM entities WHERE type = ?', (entity_type,))
        rows = cursor.fetchall()
        
        return [self._row_to_dict(row) for row in rows]
    
    def get_entities_by_skill_type(self, skill_type: str) -> List[Dict[str, Any]]:
        """
        按skillType查询实体
        
        Args:
            skill_type: 技能类型
            
        Returns:
            实体列表
        """
        cursor = self.conn.cursor()
        # 使用LIKE进行模糊匹配
        pattern = f'%"{skill_type}"%'
        cursor.execute('SELECT * FROM entities WHERE skill_types LIKE ?', (pattern,))
        rows = cursor.fetchall()
        
        return [self._row_to_dict(row) for row in rows]
    
    def search_entities(self, query: str) -> List[Dict[str, Any]]:
        """
        搜索实体
        
        Args:
            query: 搜索查询
            
        Returns:
            匹配的实体列表
        """
        cursor = self.conn.cursor()
        pattern = f'%{query}%'
        cursor.execute('''
            SELECT * FROM entities 
            WHERE name LIKE ? OR id LIKE ? OR description LIKE ?
        ''', (pattern, pattern, pattern))
        rows = cursor.fetchall()
        
        return [self._row_to_dict(row) for row in rows]
    
    def get_entities_with_stats(self, stat_name: str) -> List[Dict[str, Any]]:
        """
        获取拥有特定stat的实体
        
        Args:
            stat_name: stat名称
            
        Returns:
            实体列表
        """
        cursor = self.conn.cursor()
        pattern = f'%"{stat_name}"%'
        cursor.execute('''
            SELECT * FROM entities 
            WHERE stats LIKE ? OR constant_stats LIKE ?
        ''', (pattern, pattern))
        rows = cursor.fetchall()
        
        return [self._row_to_dict(row) for row in rows]
    
    def get_all_entities(self) -> List[Dict[str, Any]]:
        """获取所有实体"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM entities')
        rows = cursor.fetchall()
        
        return [self._row_to_dict(row) for row in rows]
    
    def get_entity_count(self) -> int:
        """获取实体数量"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM entities')
        return cursor.fetchone()[0]
    
    def get_type_counts(self) -> Dict[str, int]:
        """获取各类型实体数量"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT type, COUNT(*) as count FROM entities GROUP BY type')
        rows = cursor.fetchall()
        
        return {row['type']: row['count'] for row in rows}
    
    def clear_all(self):
        """清空所有数据"""
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM entities')
        cursor.execute('DELETE FROM known_paths')
        self.conn.commit()
    
    def update_enrichment_fields(self, entity_id: str, 
                                  summary: str = None,
                                  key_mechanics: list = None,
                                  display_stats: list = None):
        """
        更新实体的解读层字段（预计算后回写）
        
        Args:
            entity_id: 实体ID
            summary: 核心机制描述文本
            key_mechanics: 结构化机制列表 [{name, stat, formula, effect}, ...]
            display_stats: StatDescriber 生成的描述行列表 ["text1", "text2", ...]
        """
        cursor = self.conn.cursor()
        
        km_json = json.dumps(key_mechanics, ensure_ascii=False) if key_mechanics else None
        ds_json = json.dumps(display_stats, ensure_ascii=False) if display_stats else None
        
        cursor.execute('''
            UPDATE entities 
            SET summary = ?, key_mechanics = ?, display_stats = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (summary, km_json, ds_json, entity_id))
        
        self.conn.commit()
    
    def batch_update_enrichment(self, updates: List[Dict[str, Any]]):
        """
        批量更新解读层字段（高效事务模式）
        
        Args:
            updates: [{id, summary, key_mechanics, display_stats}, ...]
        """
        cursor = self.conn.cursor()
        
        for u in updates:
            km_json = json.dumps(u.get('key_mechanics'), ensure_ascii=False) if u.get('key_mechanics') else None
            ds_json = json.dumps(u.get('display_stats'), ensure_ascii=False) if u.get('display_stats') else None
            
            cursor.execute('''
                UPDATE entities 
                SET summary = ?, key_mechanics = ?, display_stats = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (u.get('summary'), km_json, ds_json, u['id']))
        
        self.conn.commit()
    
    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()
            self.conn = None
    
    def _row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        """将行转换为字典"""
        result = dict(row)
        
        # 解析所有JSON字段（与kb_query.py保持一致）
        json_fields = [
            'skill_types', 'constant_stats', 'stats', 'reservation',
            'mod_tags', 'weight_keys', 'mod_data', 'data_json',
            'quality_stats', 'levels', 'stat_sets',
            'require_skill_types', 'add_skill_types', 'exclude_skill_types',
            'tags', 'stats_node', 'reminder_text', 'variant',
            'stat_descriptions', 'additional_granted_effect_ids',
            'key_mechanics', 'display_stats'
        ]
        for field in json_fields:
            if result.get(field):
                try:
                    result[field] = json.loads(result[field])
                except (json.JSONDecodeError, TypeError):
                    pass
        
        return result
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='POE实体索引管理')
    parser.add_argument('db_path', help='SQLite数据库路径')
    parser.add_argument('--pob-path', help='POB数据目录路径（用于导入）')
    parser.add_argument('--config', help='配置文件路径')
    parser.add_argument('--query', '-q', help='查询实体')
    parser.add_argument('--type', '-t', help='按类型查询')
    parser.add_argument('--skill-type', '-s', help='按skillType查询')
    parser.add_argument('--stats', help='查找拥有特定stat的实体')
    parser.add_argument('--summary', action='store_true', help='显示摘要')
    
    args = parser.parse_args()
    
    # 创建索引管理器
    with EntityIndex(args.db_path) as index:
        # 导入数据
        if args.pob_path:
            print(f"从 {args.pob_path} 导入数据...")
            scanner = POBDataScanner(args.pob_path, args.config)
            results = scanner.scan_all_files()
            index.insert_entities_from_scan(results)
            print(f"已导入 {index.get_entity_count()} 个实体")
        
        # 查询
        if args.query:
            entities = index.search_entities(args.query)
            for entity in entities:
                print(f"- {entity['id']}: {entity['name']}")
        
        if args.type:
            entities = index.get_entities_by_type(args.type)
            for entity in entities:
                print(f"- {entity['id']}: {entity['name']}")
        
        if args.skill_type:
            entities = index.get_entities_by_skill_type(args.skill_type)
            for entity in entities:
                print(f"- {entity['id']}: {entity['name']}")
        
        if args.stats:
            entities = index.get_entities_with_stats(args.stats)
            for entity in entities:
                print(f"- {entity['id']}: {entity['name']}")
        
        # 显示摘要
        if args.summary:
            print(f"总实体数: {index.get_entity_count()}")
            print("各类型数量:")
            for type_name, count in index.get_type_counts().items():
                print(f"  {type_name}: {count}")


# ─────────────────────────────────────────────────────────────────
# EntityEnricher: 解读层预计算（Phase 2a: Tasks 3.2 + 3.3 + 3.4）
# ─────────────────────────────────────────────────────────────────

import logging
import re

logger = logging.getLogger(__name__)


class EntityEnricher:
    """
    实体解读层预计算器
    
    在初始化阶段为每个实体预计算三个解读字段：
    - summary: 核心机制描述文本（从技能专属statMap覆盖+description提炼）
    - key_mechanics: 结构化机制列表 [{name, stat, formula, effect}, ...]
    - display_stats: StatDescriber 生成的人类可读描述行列表
    
    设计原则（D1）：如果查询不到说明设计有漏洞，不做动态兜底。
    """
    
    # 全局 stat 名 → 通用含义映射（用于 constant_stats 中非前缀匹配的常见机制 stat）
    KNOWN_MECHANIC_STATS = {
        'number_of_chains': {'name': 'Chain', 'effect': 'Chains to additional targets'},
        'number_of_additional_projectiles': {'name': 'Additional Projectiles', 'effect': 'Fires additional projectiles'},
        'base_number_of_projectiles_in_spiral_nova': {'name': 'Nova Projectiles', 'effect': 'Number of projectiles in nova pattern'},
        'active_skill_area_of_effect_+%_final': {'name': 'Area of Effect', 'effect': 'Modifies area of effect'},
        'shock_effect_+%': {'name': 'Shock Effect', 'effect': 'Increases Shock effectiveness'},
        'chill_effect_+%': {'name': 'Chill Effect', 'effect': 'Increases Chill effectiveness'},
        'freeze_effect_+%': {'name': 'Freeze Effect', 'effect': 'Increases Freeze effectiveness'},
        'active_skill_hit_damage_freeze_multiplier_+%_final': {'name': 'Freeze Multiplier', 'effect': 'Multiplies Freeze buildup from hits'},
        'active_skill_chill_effect_+%_final': {'name': 'Chill Multiplier', 'effect': 'Multiplies Chill effect'},
        'base_skill_effect_duration': {'name': 'Duration', 'effect': 'Base skill effect duration'},
        'active_skill_damage_+%_final': {'name': 'Damage (MORE)', 'effect': 'MORE multiplier to damage'},
        'base_critical_strike_multiplier_+': {'name': 'Critical Multiplier', 'effect': 'Additional Critical Strike Multiplier'},
        'maximum_number_of_summoned_totems': {'name': 'Totem Limit', 'effect': 'Maximum number of summoned totems'},
    }
    
    # 忽略的通用 stat（不构成独特机制特征）
    IGNORE_STATS = {
        'movement_speed_acceleration_+%_per_second_while_performing_action',
        'movement_speed_while_performing_action_locked_duration_%',
        'base_is_projectile',
        'projectile_uses_contact_position',
        'projectile_uses_contact_direction',
        'check_for_targets_between_initiator_and_projectile_source',
        'skill_can_fire_arrows',
        'can_perform_skill_while_moving',
        'base_deal_no_damage',
        'active_skill_ignore_setting_aim_stance',
        'is_area_damage',
        'base_skill_is_totemable',
        'base_skill_is_trappable',
        'base_skill_is_mineable',
        'active_skill_attack_damage_final_permyriad',
        'active_skill_spell_damage_final_permyriad',
        'active_skill_override_turn_duration_ms',
        'channel_start_lock_cancelling_of_attack_time_%',
        'channel_skill_end_animation_duration_multiplier_permyriad',
    }
    
    # 已知的技能名前缀模式（用于从 stat 名提取前缀）
    # 格式: stat名 = {前缀}_{后缀}
    # 如 arc_damage_+%_final_for_each_remaining_chain → 前缀 = "arc"
    
    def __init__(self, entity_index: 'EntityIndex', stat_describer=None):
        """
        初始化解读层预计算器
        
        Args:
            entity_index: EntityIndex 实例（用于读写数据库）
            stat_describer: StatDescriberBridge 实例（用于生成 display_stats）
                           None 则跳过 display_stats 预计算
        """
        self.entity_index = entity_index
        self.stat_describer = stat_describer
    
    def enrich_all(self) -> Dict[str, int]:
        """
        为所有实体预计算解读层字段
        
        Returns:
            {'total': N, 'summary': N, 'key_mechanics': N, 'display_stats': N}
            各字段的非空数量统计
        """
        cursor = self.entity_index.conn.cursor()
        cursor.execute('SELECT id, type, data_json, constant_stats, stats, stat_sets, '
                       'description, stats_node, stat_descriptions '
                       'FROM entities')
        rows = cursor.fetchall()
        
        stats = {'total': len(rows), 'summary': 0, 'key_mechanics': 0, 'display_stats': 0}
        updates = []
        batch_size = 500
        
        for row in rows:
            eid, etype, data_json_str, cs_str, stats_str, ss_str, desc, sn_str, sd_str = row
            
            # 解析 JSON 字段
            data_json = self._safe_json(data_json_str, {})
            constant_stats = self._safe_json(cs_str, [])
            entity_stats = self._safe_json(stats_str, [])
            stat_sets = self._safe_json(ss_str, {})
            stats_node = self._safe_json(sn_str, [])
            stat_descriptions = self._safe_json(sd_str, [])
            
            entity_data = {
                'id': eid, 'type': etype, 'description': desc,
                'constant_stats': constant_stats,
                'stats': entity_stats,
                'stat_sets': stat_sets,
                'stats_node': stats_node,
                'stat_descriptions': stat_descriptions,
            }
            # 从 data_json 补充 skill_types 等
            entity_data['skill_types'] = data_json.get('skill_types', [])
            entity_data['name'] = data_json.get('name', eid)
            entity_data['levels'] = data_json.get('levels', {})
            entity_data['gem_type'] = data_json.get('gem_type')
            
            # 计算三个解读字段
            summary = self._compute_summary(entity_data, etype)
            key_mechanics = self._compute_key_mechanics(entity_data, etype)
            display_stats_list = self._compute_display_stats(entity_data, etype)
            
            if summary:
                stats['summary'] += 1
            if key_mechanics:
                stats['key_mechanics'] += 1
            if display_stats_list:
                stats['display_stats'] += 1
            
            updates.append({
                'id': eid,
                'summary': summary,
                'key_mechanics': key_mechanics,
                'display_stats': display_stats_list,
            })
            
            # 批量写入
            if len(updates) >= batch_size:
                self.entity_index.batch_update_enrichment(updates)
                updates = []
        
        # 写入剩余
        if updates:
            self.entity_index.batch_update_enrichment(updates)
        
        return stats
    
    # ─── Task 3.2: Summary 提取 ───
    
    def _compute_summary(self, entity: Dict[str, Any], etype: str) -> Optional[str]:
        """
        提取核心机制描述 summary
        
        逻辑：
        1. skill_definition: 从技能专属 statMap 覆盖 + description 提炼独特性
        2. gem_definition: 使用 description（宝石无独立 statMap）
        3. unique_item: 从 stat_descriptions 或 description 提取
        4. passive_node: 仅对 notable/keystone 提取 stat_descriptions 摘要
        5. mod_affix: 使用 stat_descriptions 首行
        
        无独特性时返回 None（不做无意义的描述）
        """
        if etype == 'skill_definition':
            return self._summary_for_skill(entity)
        elif etype == 'gem_definition':
            return self._summary_for_gem(entity)
        elif etype == 'unique_item':
            return self._summary_for_unique(entity)
        elif etype == 'passive_node':
            return self._summary_for_passive(entity)
        elif etype == 'mod_affix':
            return self._summary_for_mod(entity)
        return None
    
    def _summary_for_skill(self, entity: Dict[str, Any]) -> Optional[str]:
        """
        技能的 summary 提取
        
        来源优先级：
        1. 技能专属 statMap 覆盖（前缀为技能名的 stat）→ 提炼核心机制
        2. 独特 constant_stats → 识别非通用的固定效果
        3. description → 游戏内描述的首句
        
        如果以上都是通用内容（无独特性），返回 None
        """
        stat_sets = entity.get('stat_sets', {})
        stat_map = stat_sets.get('statMap', {})
        constant_stats = entity.get('constant_stats', [])
        description = entity.get('description', '') or ''
        skill_name = entity.get('name', '')
        skill_types = entity.get('skill_types', [])
        
        parts = []
        
        # 1. 从 statMap 提取独特机制描述
        unique_stats = [k for k in stat_map.keys() 
                       if not k.startswith('quality_display_')]
        if unique_stats:
            mechanic_names = []
            for stat_name in unique_stats:
                readable = self._stat_name_to_readable(stat_name, skill_name)
                if readable:
                    mechanic_names.append(readable)
            if mechanic_names:
                parts.append('; '.join(mechanic_names))
        
        # 2. 从 constant_stats 提取独特固定效果
        unique_cs = self._filter_unique_constant_stats(constant_stats, skill_name)
        if unique_cs:
            cs_descs = []
            for stat_name, value in unique_cs:
                readable = self._constant_stat_to_readable(stat_name, value)
                if readable:
                    cs_descs.append(readable)
            if cs_descs:
                parts.append('; '.join(cs_descs[:3]))  # 最多3个
        
        # 3. 如果既没有 statMap 也没有独特 cs，用 description 首句
        if not parts and description:
            # 提取第一句话（到第一个句号或换行）
            first_sentence = re.split(r'[.\n]', description)[0].strip()
            if first_sentence and len(first_sentence) > 10:
                parts.append(first_sentence)
        
        if not parts:
            return None
        
        # 组装 summary
        # 前置：技能类型标签
        type_prefix = self._skill_type_prefix(skill_types)
        summary = '. '.join(parts)
        if type_prefix:
            summary = f"[{type_prefix}] {summary}"
        
        return summary
    
    def _summary_for_gem(self, entity: Dict[str, Any]) -> Optional[str]:
        """宝石的 summary：直接使用 description 首句"""
        description = entity.get('description', '') or ''
        if not description:
            return None
        first_sentence = re.split(r'[.\n]', description)[0].strip()
        if first_sentence and len(first_sentence) > 10:
            return first_sentence
        return None
    
    def _summary_for_unique(self, entity: Dict[str, Any]) -> Optional[str]:
        """唯一物品的 summary：从 stat_descriptions 或 stats 中提取关键效果"""
        # 1. stat_descriptions（如果有）
        stat_descs = entity.get('stat_descriptions', [])
        if isinstance(stat_descs, list) and stat_descs:
            return '; '.join(str(s) for s in stat_descs[:3])
        
        # 2. stats 字段（唯一物品的 stats 可能直接是描述文本字符串列表）
        entity_stats = entity.get('stats', [])
        if isinstance(entity_stats, list) and entity_stats:
            text_stats = [str(s) for s in entity_stats if isinstance(s, str) and len(s) > 5]
            if text_stats:
                return '; '.join(text_stats[:3])
        
        # 3. description
        description = entity.get('description', '') or ''
        if description:
            return re.split(r'[.\n]', description)[0].strip() or None
        return None
    
    def _summary_for_passive(self, entity: Dict[str, Any]) -> Optional[str]:
        """
        天赋节点的 summary
        
        仅对 notable 和 keystone 生成 summary（普通小节点不需要）。
        从 stat_descriptions 提取。
        """
        stat_descs = entity.get('stat_descriptions', [])
        if isinstance(stat_descs, list) and stat_descs:
            return '; '.join(str(s) for s in stat_descs[:3])
        
        # 天赋节点如果没有 stat_descriptions，检查 stats_node
        stats_node = entity.get('stats_node', [])
        if isinstance(stats_node, list) and stats_node:
            readable_stats = []
            for sn in stats_node[:3]:
                if isinstance(sn, str):
                    readable = self._stat_name_to_readable(sn, '')
                    if readable:
                        readable_stats.append(readable)
            if readable_stats:
                return '; '.join(readable_stats)
        
        return None
    
    def _summary_for_mod(self, entity: Dict[str, Any]) -> Optional[str]:
        """Mod 词缀的 summary：使用 stat_descriptions 首行"""
        stat_descs = entity.get('stat_descriptions', [])
        if isinstance(stat_descs, list) and stat_descs:
            return str(stat_descs[0])
        return None
    
    # ─── Task 3.3: Key Mechanics 提取 ───
    
    def _compute_key_mechanics(self, entity: Dict[str, Any], etype: str) -> Optional[List[Dict[str, Any]]]:
        """
        提取结构化机制列表 key_mechanics
        
        每个元素: {name, stat, formula, effect}
        
        仅对 skill_definition 提取（其他类型的机制信息由 mechanisms.db 覆盖）
        """
        if etype != 'skill_definition':
            return None
        
        stat_sets = entity.get('stat_sets', {})
        stat_map = stat_sets.get('statMap', {})
        constant_stats = entity.get('constant_stats', [])
        skill_name = entity.get('name', '')
        
        mechanics = []
        seen_stats = set()
        
        # 1. 从 statMap 提取（这些是技能专属的覆盖映射——最有价值的机制信息）
        for stat_name in stat_map:
            if stat_name.startswith('quality_display_'):
                continue  # 品质显示用的标记，不是真正的机制
            if stat_name in seen_stats:
                continue
            seen_stats.add(stat_name)
            
            mechanic = self._stat_to_mechanic(stat_name, skill_name, constant_stats)
            if mechanic:
                mechanics.append(mechanic)
        
        # 2. 从 constant_stats 中提取有独特意义的固定 stat
        for cs_item in constant_stats:
            if not isinstance(cs_item, (list, tuple)) or len(cs_item) < 2:
                continue
            stat_name, value = cs_item[0], cs_item[1]
            if stat_name in seen_stats:
                continue
            if stat_name in self.IGNORE_STATS:
                continue
            
            # 检查是否是已知的有意义的机制 stat
            if stat_name in self.KNOWN_MECHANIC_STATS:
                info = self.KNOWN_MECHANIC_STATS[stat_name]
                mechanics.append({
                    'name': info['name'],
                    'stat': stat_name,
                    'formula': f'{stat_name} = {value}',
                    'effect': info['effect'],
                })
                seen_stats.add(stat_name)
            elif self._is_skill_specific_stat(stat_name, skill_name):
                # 技能专属前缀的 constant_stat
                mechanic = self._stat_to_mechanic(stat_name, skill_name, constant_stats)
                if mechanic:
                    mechanics.append(mechanic)
                    seen_stats.add(stat_name)
        
        return mechanics if mechanics else None
    
    def _stat_to_mechanic(self, stat_name: str, skill_name: str, 
                          constant_stats: list) -> Optional[Dict[str, str]]:
        """
        将单个 stat 转换为结构化机制描述
        
        Returns:
            {name, stat, formula, effect} 或 None
        """
        # 查找该 stat 在 constant_stats 中的值
        value = None
        for cs_item in constant_stats:
            if isinstance(cs_item, (list, tuple)) and len(cs_item) >= 2:
                if cs_item[0] == stat_name:
                    value = cs_item[1]
                    break
        
        # 从 stat 名称提取可读的机制名
        readable_name = self._stat_name_to_readable(stat_name, skill_name)
        if not readable_name:
            readable_name = stat_name  # fallback
        
        # 构建公式表达
        formula = stat_name
        if value is not None:
            formula = f'{stat_name} = {value}'
        
        # 解读效果
        effect = self._interpret_stat_effect(stat_name, value)
        
        return {
            'name': readable_name,
            'stat': stat_name,
            'formula': formula,
            'effect': effect,
        }
    
    # ─── Task 3.4: Display Stats (via StatDescriber bridge) ───
    
    def _compute_display_stats(self, entity: Dict[str, Any], etype: str) -> Optional[List[str]]:
        """
        通过 StatDescriber 桥接生成人类可读描述
        
        优先级：
        1. 使用 stat_describer_bridge（lupa 运行原始 Lua 代码）
        2. 已有的 stat_descriptions 字段（data_scanner 提取的天赋/装备描述）
        3. 唯一物品的 stats 字段（直接是描述文本字符串列表）
        4. None（无可用描述）
        """
        # 1. 使用 StatDescriber 桥接
        if self.stat_describer and self.stat_describer.available:
            lines = self.stat_describer.describe_entity_stats(entity, etype)
            if lines:
                return lines
        
        # 2. 已有的 stat_descriptions（天赋节点和装备词缀已有描述文本）
        stat_descs = entity.get('stat_descriptions', [])
        if isinstance(stat_descs, list) and stat_descs:
            return [str(s) for s in stat_descs]
        
        # 3. 唯一物品的 stats 字段（直接是描述文本）
        if etype == 'unique_item':
            entity_stats = entity.get('stats', [])
            if isinstance(entity_stats, list) and entity_stats:
                text_stats = [str(s) for s in entity_stats if isinstance(s, str)]
                if text_stats:
                    return text_stats
        
        return None
    
    # ─── 辅助方法 ───
    
    def _safe_json(self, s: Optional[str], default):
        """安全解析 JSON 字符串"""
        if not s:
            return default
        try:
            return json.loads(s)
        except (json.JSONDecodeError, TypeError):
            return default
    
    def _is_skill_specific_stat(self, stat_name: str, skill_name: str) -> bool:
        """
        判断 stat 是否是技能专属的（前缀匹配技能名）
        
        例如: skill_name="Arc" → 前缀 "arc_"
              skill_name="Detonating Arrow" → 前缀 "detonating_arrow_"
        """
        if not skill_name:
            return False
        # 将技能名转换为 stat 前缀格式（小写 + 下划线替换空格）
        prefix = skill_name.lower().replace(' ', '_').replace("'", '') + '_'
        return stat_name.startswith(prefix)
    
    def _stat_name_to_readable(self, stat_name: str, skill_name: str) -> Optional[str]:
        """
        将 stat 名称转换为可读的机制名
        
        例如:
          arc_damage_+%_final_for_each_remaining_chain → MORE Damage per Remaining Chain
          detonating_arrow_all_damage_%_to_gain_as_fire_per_stage → Damage gained as Fire per Stage
          empower_barrage_base_number_of_barrage_repeats → Base Barrage Repeats
        """
        # 先检查已知映射
        if stat_name in self.KNOWN_MECHANIC_STATS:
            return self.KNOWN_MECHANIC_STATS[stat_name]['name']
        
        # 移除技能名前缀
        suffix = stat_name
        if skill_name:
            prefix = skill_name.lower().replace(' ', '_').replace("'", '') + '_'
            if stat_name.startswith(prefix):
                suffix = stat_name[len(prefix):]
            else:
                # 尝试其他常见前缀（如 empower_barrage_ 对应 Barrage）
                # 使用通用策略：找最长匹配的下划线分割点
                pass
        
        # 将下划线分割、去除符号、首字母大写
        parts = suffix.replace('+%', 'Pct').replace('-%', 'Reduction').replace('%', 'Pct')
        parts = parts.replace('_', ' ').strip()
        
        if not parts or parts == stat_name:
            return None
        
        # 识别 MORE/LESS/INC 等关键词
        readable = parts.title()
        if 'Final' in readable:
            readable = readable.replace('Final', '(MORE/LESS)')
        
        return readable if len(readable) > 3 else None
    
    def _constant_stat_to_readable(self, stat_name: str, value) -> Optional[str]:
        """将 constant_stat 转换为可读文本"""
        if stat_name in self.KNOWN_MECHANIC_STATS:
            info = self.KNOWN_MECHANIC_STATS[stat_name]
            if 'duration' in stat_name.lower() and isinstance(value, (int, float)):
                return f"{info['name']}: {value/1000:.1f}s"
            return f"{info['name']}: {value}"
        
        if stat_name in self.IGNORE_STATS:
            return None
        
        # 通用格式化
        readable = stat_name.replace('_', ' ').replace('+%', '%').replace('-%', '% less')
        if isinstance(value, (int, float)) and value != 0:
            return f"{readable}: {value}"
        return None
    
    def _interpret_stat_effect(self, stat_name: str, value) -> str:
        """解读 stat 的效果描述"""
        lower = stat_name.lower()
        
        # 基于 stat 名称中的关键词推断效果
        if 'final' in lower and 'damage' in lower:
            if value and value > 0:
                return f'{value}% MORE damage'
            elif value and value < 0:
                return f'{abs(value)}% LESS damage'
            return 'MORE/LESS damage modifier'
        
        if 'gained' in lower and 'infusion' in lower:
            return f'Gained on Infusion consumption (value: {value})'
        
        if 'per_stage' in lower or 'per_stack' in lower:
            return f'Scales per stage/stack (value: {value})'
        
        if 'chain' in lower:
            return f'Chain-related mechanic (value: {value})'
        
        if 'cooldown' in lower:
            return f'Affects cooldown (value: {value})'
        
        if 'number_of' in lower or 'max_number' in lower:
            return f'Count/limit mechanic (value: {value})'
        
        if 'duration' in lower:
            if isinstance(value, (int, float)) and value >= 100:
                return f'Duration: {value/1000:.1f}s'
            return f'Duration modifier (value: {value})'
        
        if 'reservation' in lower or 'mana_cost' in lower:
            return f'Cost/reservation modifier (value: {value})'
        
        if value is not None:
            return f'Value: {value}'
        return 'Effect from statMap override'
    
    def _skill_type_prefix(self, skill_types: list) -> str:
        """从技能类型列表生成简短的类型前缀标签"""
        priority_types = [
            'Spell', 'Attack', 'Channel', 'Minion', 'Aura', 
            'Warcry', 'Curse', 'Herald', 'Trap', 'Mine', 'Totem',
            'Projectile', 'Area', 'Duration', 'Buff',
        ]
        matched = []
        for pt in priority_types:
            if pt in skill_types:
                matched.append(pt)
            if len(matched) >= 3:
                break
        return '/'.join(matched)
    
    def _filter_unique_constant_stats(self, constant_stats: list, skill_name: str) -> List[tuple]:
        """
        从 constant_stats 中过滤出有独特意义的固定 stat
        排除通用的移动速度惩罚等无信息量的 stat
        """
        unique = []
        for cs_item in constant_stats:
            if not isinstance(cs_item, (list, tuple)) or len(cs_item) < 2:
                continue
            stat_name = cs_item[0]
            value = cs_item[1]
            
            # 排除通用无信息量的 stat
            if stat_name in self.IGNORE_STATS:
                continue
            
            # 排除值为 0 的 stat
            if isinstance(value, (int, float)) and value == 0:
                continue
            
            unique.append((stat_name, value))
        
        return unique


if __name__ == '__main__':
    main()
