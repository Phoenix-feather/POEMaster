#!/usr/bin/env python3
"""
机制提取器
从 ModCache.lua 中提取 stat 映射，建立机制节点

核心原理：
- 机制通过 stat ID/internal stat name 识别，而不是描述
- 例如: "InstantLifeLeech" 是机制标识符
- 描述 "Leech from Critical Hits is instant" 只是显示文本
"""

import re
import json
import sqlite3
from pathlib import Path
from typing import Dict, List, Set, Any
from collections import defaultdict

# 尝试导入 Lua 解析器
try:
    from lua_parser import LuaParser
    HAS_LUA_PARSER = True  # 默认使用 Lua 解析器
except ImportError:
    HAS_LUA_PARSER = False


class MechanismExtractor:
    """机制提取器"""
    
    # 已知的机制 stat 名称模式
    KNOWN_MECHANISM_PATTERNS = [
        # 立即偷取系列
        r'Instant\w+Leech',
        # 绕过/免疫系列
        r'CannotBe\w+',
        r'ImmuneTo\w+',
        r'Ignore\w+',
        # 转换系列
        r'\w+ConvertTo\w+',
        r'\w+TakenAs\w+',
        # 特殊机制
        r'GhostReaver',
        r'CanLeech\w+OnFull\w+',
        r'ZealotsOath',
    ]
    
    def __init__(self, modcache_path: str, entities_db_path: str = None):
        self.modcache_path = Path(modcache_path)
        self.entities_db_path = Path(entities_db_path) if entities_db_path else None
        self.stat_mappings: Dict[str, Dict] = {}
        self.mechanisms: Dict[str, Set[str]] = defaultdict(set)  # mechanism -> set of stat names
        self.stat_sources: Dict[str, List[Dict]] = defaultdict(list)  # stat name -> list of sources
        self.description_to_entities: Dict[str, List[Dict]] = defaultdict(list)  # description -> list of entities
        
    def parse_modcache(self) -> Dict[str, Dict]:
        """解析 ModCache.lua，优先使用 Lua 解析器"""
        print(f"解析 {self.modcache_path}...")
        
        with open(self.modcache_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 优先使用 Lua 解析器
        if HAS_LUA_PARSER:
            print("  使用 Lua 解析器...")
            return self._parse_modcache_with_lua(content)
        else:
            print("  使用正则解析器...")
            return self._parse_modcache_with_regex(content)
    
    def _parse_modcache_with_lua(self, content: str) -> Dict[str, Dict]:
        """使用 Lua 解析器解析 ModCache"""
        parser = LuaParser()
        mappings = parser.parse_modcache(content)
        
        # 转换为内部格式
        for desc, data in mappings.items():
            stats = data.get('stats', [])
            if stats:
                self.stat_mappings[desc] = {
                    'stats': stats,
                    'description': desc
                }
                
                # 记录每个 stat 对应的描述
                for stat in stats:
                    stat_name = stat.get('name', '')
                    if stat_name:
                        self.stat_sources[stat_name].append({
                            'description': desc,
                            'type': stat.get('type', ''),
                            'value': stat.get('value', ''),
                            'condition': stat.get('condition', '')
                        })
        
        print(f"  解析了 {len(self.stat_mappings)} 个描述映射")
        return self.stat_mappings
    
    def _parse_modcache_with_regex(self, content: str) -> Dict[str, Dict]:
        """使用正则解析 ModCache（回退方案）"""
        lines = content.split('\n')
        
        for line in lines:
            # 匹配有 stat 映射的行
            # 格式: c["description"]={{...stats...}, nil/str}
            # 修复：支持结尾是 nil 或字符串
            match = re.match(r'c\["([^"]+)"\]=\{\{(.+)\},\s*(?:nil|"[^"]*")\}', line)
            if not match:
                continue
            
            desc = match.group(1)
            stats_block = match.group(2)
            
            # 跳过空表 {{}, ...} - 这些没有 stat 数据
            if stats_block.strip() == '' or stats_block.strip() == '{}':
                continue
            
            # 解析 stat 块
            stats = self._parse_stats_block(stats_block)
            if stats:
                self.stat_mappings[desc] = {
                    'stats': stats,
                    'description': desc
                }
                
                # 记录每个 stat 对应的描述
                for stat in stats:
                    stat_name = stat.get('name', '')
                    if stat_name:
                        self.stat_sources[stat_name].append({
                            'description': desc,
                            'type': stat.get('type', ''),
                            'value': stat.get('value', ''),
                            'condition': stat.get('condition', '')
                        })
        
        print(f"  解析了 {len(self.stat_mappings)} 个描述映射")
        return self.stat_mappings
    
    def build_entity_mapping(self) -> Dict[str, List[Dict]]:
        """从实体数据库建立 描述→实体 映射"""
        if not self.entities_db_path or not self.entities_db_path.exists():
            print("  [WARN] 实体数据库不存在，跳过实体关联")
            return {}
        
        print(f"从实体数据库建立关联: {self.entities_db_path}")
        
        conn = sqlite3.connect(self.entities_db_path)
        cursor = conn.cursor()
        
        # 查询所有有 stats 的实体
        cursor.execute('''
            SELECT id, name, type, stats 
            FROM entities 
            WHERE stats IS NOT NULL AND stats != '[]' AND stats != ''
        ''')
        
        count = 0
        for row in cursor.fetchall():
            entity_id, entity_name, entity_type, stats_json = row
            if not stats_json:
                continue
            
            try:
                stats = json.loads(stats_json)
                for stat in stats:
                    if isinstance(stat, str) and stat.strip():
                        self.description_to_entities[stat.strip()].append({
                            'id': entity_id,
                            'name': entity_name,
                            'type': entity_type
                        })
                        count += 1
            except:
                pass
        
        conn.close()
        print(f"  建立了 {len(self.description_to_entities)} 个描述映射，涉及 {count} 个关联")
        return self.description_to_entities
    
    def _parse_stats_block(self, block: str) -> List[Dict]:
        """解析 stat 块"""
        stats = []
        
        # 匹配 name="StatName", type="TYPE", value=NUMBER 格式
        name_pattern = r'name="([^"]+)"'
        type_pattern = r'type="([^"]+)"'
        value_pattern = r'value=(\d+\.?\d*)'
        condition_pattern = r'\{type="Condition",var="([^"]+)"\}'
        
        # 分割多个 stat - 处理 [n]= 格式
        stat_blocks = re.split(r'\},\s*\[?\d*\]?=\{', block)
        
        for stat_block in stat_blocks:
            name_match = re.search(name_pattern, stat_block)
            type_match = re.search(type_pattern, stat_block)
            value_match = re.search(value_pattern, stat_block)
            condition_match = re.search(condition_pattern, stat_block)
            
            if name_match:
                stat = {
                    'name': name_match.group(1),
                    'type': type_match.group(1) if type_match else '',
                    'value': value_match.group(1) if value_match else '',
                    'condition': condition_match.group(1) if condition_match else ''
                }
                stats.append(stat)
        
        return stats
    
    def identify_mechanisms(self) -> Dict[str, Set[str]]:
        """识别机制"""
        print("识别机制...")
        
        # 合并所有已知的 stat 名称
        all_stat_names = set(self.stat_sources.keys())
        
        # 根据模式匹配识别机制
        for stat_name in all_stat_names:
            for pattern in self.KNOWN_MECHANISM_PATTERNS:
                if re.match(pattern, stat_name):
                    # 使用 stat 名称作为机制标识符
                    self.mechanisms[stat_name].add(stat_name)
                    break
        
        # 手动添加一些已知的机制
        known_mechanisms = {
            'InstantLifeLeech': '立即生命偷取',
            'InstantManaLeech': '立即魔力偷取',
            'InstantEnergyShieldLeech': '立即能量护盾偷取',
            'CanLeechLifeOnFullLife': '满血时生命偷取保留',
            'GhostReaver': '鬼影掠夺者(生命偷取转ES偷取)',
            'CannotBeIgnited': '免疫点燃',
            'CannotBeFrozen': '免疫冰冻',
            'CannotBeShocked': '免疫感电',
            'ImmuneToChaos': '免疫混沌',
        }
        
        for stat_name, mech_name in known_mechanisms.items():
            if stat_name in all_stat_names:
                self.mechanisms[stat_name].add(stat_name)
        
        print(f"  识别了 {len(self.mechanisms)} 个机制")
        return dict(self.mechanisms)
    
    def get_stat_sources(self, stat_name: str) -> List[Dict]:
        """获取某个 stat 的所有来源"""
        return self.stat_sources.get(stat_name, [])
    
    def export_to_db(self, db_path: str, entities_db_path: str = None):
        """导出到数据库"""
        print(f"导出到 {db_path}...")
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 创建机制表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS mechanisms (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                stat_names TEXT,
                description TEXT,
                source_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 创建机制-实体关联表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS mechanism_sources (
                id TEXT PRIMARY KEY,
                mechanism_id TEXT NOT NULL,
                entity_id TEXT,
                entity_name TEXT,
                description TEXT,
                stat_value TEXT,
                condition TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (mechanism_id) REFERENCES mechanisms(id)
            )
        ''')
        
        # 清空旧数据，避免重复
        cursor.execute('DELETE FROM mechanism_sources')
        cursor.execute('DELETE FROM mechanisms')
        
        # 插入机制
        for mech_id, stat_names in self.mechanisms.items():
            sources = self.get_stat_sources(mech_id)
            
            cursor.execute('''
                INSERT OR REPLACE INTO mechanisms (id, name, stat_names, description, source_count)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                mech_id,
                mech_id,  # 使用 stat 名称作为显示名称
                json.dumps(list(stat_names)),
                f"机制: {mech_id}",
                len(sources)
            ))
            
            # 插入来源
            for i, source in enumerate(sources):
                description = source.get('description', '')
                
                # 查找关联的实体
                entities = self.description_to_entities.get(description, [])
                if entities:
                    # 为每个关联实体创建一条记录
                    for j, entity in enumerate(entities):
                        cursor.execute('''
                            INSERT OR IGNORE INTO mechanism_sources 
                            (id, mechanism_id, entity_id, entity_name, description, stat_value, condition)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            f"{mech_id}_source_{i}_{j}",
                            mech_id,
                            entity.get('id', ''),
                            entity.get('name', ''),
                            description,
                            source.get('value', ''),
                            source.get('condition', '')
                        ))
                else:
                    # 没有关联实体，只保存描述
                    cursor.execute('''
                        INSERT OR IGNORE INTO mechanism_sources 
                        (id, mechanism_id, description, stat_value, condition)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (
                        f"{mech_id}_source_{i}",
                        mech_id,
                        description,
                        source.get('value', ''),
                        source.get('condition', '')
                    ))
        
        conn.commit()
        conn.close()
        
        print(f"  导出了 {len(self.mechanisms)} 个机制")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='提取机制')
    parser.add_argument('modcache_path', help='ModCache.lua 路径')
    parser.add_argument('--output', '-o', help='输出数据库路径')
    
    args = parser.parse_args()
    
    extractor = MechanismExtractor(args.modcache_path)
    extractor.parse_modcache()
    extractor.identify_mechanisms()
    
    # 打印一些示例
    print("\n" + "=" * 60)
    print("示例机制:")
    print("=" * 60)
    
    for mech_id in ['InstantLifeLeech', 'CanLeechLifeOnFullLife', 'GhostReaver']:
        if mech_id in extractor.mechanisms:
            sources = extractor.get_stat_sources(mech_id)
            print(f"\n{mech_id}:")
            print(f"  来源数量: {len(sources)}")
            for s in sources[:3]:
                print(f"  - {s['description'][:60]}...")
    
    if args.output:
        extractor.export_to_db(args.output)
    
    print("\n完成!")


if __name__ == '__main__':
    main()
