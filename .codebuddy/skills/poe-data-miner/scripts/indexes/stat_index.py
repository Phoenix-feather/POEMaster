"""
Stat索引

一级索引：快速定位stat定义和使用位置
"""

import re
import logging
from typing import Dict, List, Any, Optional
from pathlib import Path
import sqlite3

from .base_index import BaseIndex

logger = logging.getLogger(__name__)


class StatIndex(BaseIndex):
    """Stat一级索引"""
    
    def __init__(self, db_path: str):
        """
        初始化Stat索引
        
        Args:
            db_path: 索引数据库路径
        """
        super().__init__(db_path, 'stat_index')
    
    def _create_tables(self):
        """创建索引表"""
        cursor = self.conn.cursor()
        
        # stat定义表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS stat_definitions (
                stat_id TEXT PRIMARY KEY,
                stat_name TEXT NOT NULL,
                definition_file TEXT,
                definition_line INTEGER,
                definition_context TEXT,
                description TEXT,
                usage_count INTEGER DEFAULT 0,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # stat使用表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS stat_usages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stat_id TEXT NOT NULL,
                skill_name TEXT NOT NULL,
                file_path TEXT NOT NULL,
                line_number INTEGER,
                context TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (stat_id) REFERENCES stat_definitions(stat_id)
            )
        ''')
        
        # 创建索引
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_stat_id ON stat_usages(stat_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_skill_name ON stat_usages(skill_name)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_stat_name ON stat_definitions(stat_name)')
        
        self.conn.commit()
    
    def build_index(self, pob_data_path: str):
        """
        构建Stat索引
        
        Args:
            pob_data_path: POB数据路径
        """
        logger.info(f"开始构建Stat索引: {pob_data_path}")
        
        pob_path = Path(pob_data_path)
        
        # 1. 索引StatDescriptions目录
        stat_desc_dir = pob_path / 'Data' / 'StatDescriptions'
        if stat_desc_dir.exists():
            for lua_file in stat_desc_dir.glob('*.lua'):
                self._index_stat_descriptions(lua_file)
        
        # 2. 索引技能文件中的stats字段
        skills_dir = pob_path / 'Data' / 'Skills'
        if skills_dir.exists():
            for lua_file in skills_dir.glob('*.lua'):
                self._index_skill_stats(lua_file)
        
        # 3. 更新使用计数
        self._update_usage_counts()
        
        logger.info(f"Stat索引构建完成: {self._get_record_count()} 条记录")
    
    def _index_stat_descriptions(self, lua_file: Path):
        """索引StatDescriptions文件"""
        logger.debug(f"索引StatDescriptions文件: {lua_file.name}")
        
        try:
            with open(lua_file, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')
            
            # 提取stat定义
            # 格式: ["stat_id"] = { ... }
            stat_pattern = re.compile(r'\["([^"]+)"\]\s*=\s*\{')
            
            for i, line in enumerate(lines, 1):
                match = stat_pattern.search(line)
                if match:
                    stat_id = match.group(1)
                    
                    # 提取上下文（前后5行）
                    context_start = max(0, i - 6)
                    context_end = min(len(lines), i + 4)
                    context = '\n'.join(lines[context_start:context_end])
                    
                    # 插入或更新定义
                    cursor = self.conn.cursor()
                    cursor.execute('''
                        INSERT OR REPLACE INTO stat_definitions 
                        (stat_id, stat_name, definition_file, definition_line, definition_context)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (stat_id, stat_id, str(lua_file), i, context))
            
            self.conn.commit()
            
        except Exception as e:
            logger.error(f"索引StatDescriptions文件失败 {lua_file.name}: {e}")
    
    def _index_skill_stats(self, lua_file: Path):
        """索引技能文件中的stats字段"""
        logger.debug(f"索引技能stats: {lua_file.name}")
        
        try:
            with open(lua_file, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')
            
            # 提取技能名称和stats
            # 格式: { name = "SkillName", stats = { "stat1", "stat2" } }
            
            current_skill = None
            in_stats_block = False
            
            for i, line in enumerate(lines, 1):
                # 匹配技能名称
                name_match = re.search(r'name\s*=\s*"([^"]+)"', line)
                if name_match:
                    current_skill = name_match.group(1)
                
                # 匹配stats块开始
                if 'stats' in line and '=' in line and '{' in line:
                    in_stats_block = True
                    continue
                
                # 匹配stats块结束
                if in_stats_block and '}' in line:
                    in_stats_block = False
                    current_skill = None
                    continue
                
                # 提取stat
                if in_stats_block and current_skill:
                    stat_match = re.search(r'"([^"]+)"', line)
                    if stat_match:
                        stat_id = stat_match.group(1)
                        
                        # 插入使用记录
                        cursor = self.conn.cursor()
                        cursor.execute('''
                            INSERT INTO stat_usages 
                            (stat_id, skill_name, file_path, line_number, context)
                            VALUES (?, ?, ?, ?, ?)
                        ''', (stat_id, current_skill, str(lua_file), i, line.strip()))
                        
                        # 确保stat定义存在
                        cursor.execute('''
                            INSERT OR IGNORE INTO stat_definitions (stat_id, stat_name)
                            VALUES (?, ?)
                        ''', (stat_id, stat_id))
            
            self.conn.commit()
            
        except Exception as e:
            logger.error(f"索引技能stats失败 {lua_file.name}: {e}")
    
    def _update_usage_counts(self):
        """更新stat使用计数"""
        cursor = self.conn.cursor()
        
        cursor.execute('''
            UPDATE stat_definitions 
            SET usage_count = (
                SELECT COUNT(*) FROM stat_usages 
                WHERE stat_usages.stat_id = stat_definitions.stat_id
            )
        ''')
        
        self.conn.commit()
    
    def update_index(self, changed_file: str):
        """
        增量更新索引
        
        Args:
            changed_file: 变更的文件路径
        """
        file_path = Path(changed_file)
        
        if 'StatDescriptions' in changed_file:
            self._index_stat_descriptions(file_path)
        elif 'Skills' in changed_file:
            self._index_skill_stats(file_path)
        
        self._update_usage_counts()
    
    def search(self, query: Dict[str, Any]) -> Dict[str, Any]:
        """
        搜索Stat索引
        
        Args:
            query: 查询参数，支持:
                - stat_id: stat ID
                - skill_name: 技能名称
                - fuzzy: 模糊搜索关键词
                
        Returns:
            查询结果
        """
        cursor = self.conn.cursor()
        
        # 精确查询stat_id
        if 'stat_id' in query:
            stat_id = query['stat_id']
            
            # 查询定义
            definition = cursor.execute(
                'SELECT * FROM stat_definitions WHERE stat_id = ?',
                (stat_id,)
            ).fetchone()
            
            # 查询使用
            usages = cursor.execute(
                'SELECT * FROM stat_usages WHERE stat_id = ?',
                (stat_id,)
            ).fetchall()
            
            return {
                'found': definition is not None,
                'definition': dict(definition) if definition else None,
                'usages': [dict(u) for u in usages],
                'usage_count': len(usages)
            }
        
        # 按技能名称查询
        elif 'skill_name' in query:
            skill_name = query['skill_name']
            
            usages = cursor.execute(
                'SELECT * FROM stat_usages WHERE skill_name = ?',
                (skill_name,)
            ).fetchall()
            
            return {
                'found': len(usages) > 0,
                'usages': [dict(u) for u in usages],
                'usage_count': len(usages)
            }
        
        # 模糊搜索
        elif 'fuzzy' in query:
            keyword = query['fuzzy']
            
            definitions = cursor.execute(
                'SELECT * FROM stat_definitions WHERE stat_id LIKE ? OR stat_name LIKE ?',
                (f'%{keyword}%', f'%{keyword}%')
            ).fetchall()
            
            return {
                'found': len(definitions) > 0,
                'definitions': [dict(d) for d in definitions],
                'count': len(definitions)
            }
        
        return {'found': False}
    
    def _get_record_count(self) -> int:
        """获取记录数量"""
        cursor = self.conn.cursor()
        count = cursor.execute('SELECT COUNT(*) FROM stat_definitions').fetchone()[0]
        return count
    
    def get_top_stats(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        获取使用频率最高的stats
        
        Args:
            limit: 返回数量
            
        Returns:
            stat列表
        """
        cursor = self.conn.cursor()
        
        results = cursor.execute('''
            SELECT stat_id, stat_name, usage_count 
            FROM stat_definitions 
            ORDER BY usage_count DESC 
            LIMIT ?
        ''', (limit,)).fetchall()
        
        return [dict(r) for r in results]
