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
                reminder_text TEXT
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
        
        cursor.execute('''
            INSERT OR REPLACE INTO entities 
            (id, name, type, skill_types, constant_stats, stats, description, reservation, mod_tags, weight_keys, affix_type, mod_data, data_json, source_file, updated_at,
             base_type_name, cast_time, quality_stats, levels, stat_sets, support, require_skill_types, add_skill_types, exclude_skill_types, is_trigger, hidden,
             game_id, variant_id, granted_effect_id, tags, gem_type, tag_string, req_str, req_dex, req_int, tier, natural_max_level, additional_stat_set1, additional_stat_set2, weapon_requirements, gem_family,
             requires_level, granted_skill, implicits, variant, source,
             ascendancy_name, is_notable, is_keystone, stats_node, reminder_text)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?)
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
            reminder_text
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
    
    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()
            self.conn = None
    
    def _row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        """将行转换为字典"""
        result = dict(row)
        
        # 解析JSON字段
        for field in ['skill_types', 'constant_stats', 'stats', 'reservation', 'data_json']:
            if result.get(field):
                try:
                    result[field] = json.loads(result[field])
                except json.JSONDecodeError:
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


if __name__ == '__main__':
    main()
