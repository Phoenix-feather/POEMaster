"""
SkillType索引

二级索引：快速定位skillTypes约束关系
"""

import re
import logging
from typing import Dict, List, Any
from pathlib import Path

from .base_index import BaseIndex

logger = logging.getLogger(__name__)


class SkillTypeIndex(BaseIndex):
    """SkillType二级索引"""
    
    def __init__(self, db_path: str):
        """
        初始化SkillType索引
        
        Args:
            db_path: 索引数据库路径
        """
        super().__init__(db_path, 'skilltype_index')
    
    def _create_tables(self):
        """创建索引表"""
        cursor = self.conn.cursor()
        
        # skillType定义表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS skilltype_definitions (
                skill_type TEXT PRIMARY KEY,
                type_name TEXT NOT NULL,
                description TEXT,
                related_stats TEXT,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # skillType约束表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS skilltype_constraints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                skill_type TEXT NOT NULL,
                constraint_type TEXT NOT NULL,
                skill_name TEXT NOT NULL,
                file_path TEXT NOT NULL,
                line_number INTEGER,
                context TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (skill_type) REFERENCES skilltype_definitions(skill_type)
            )
        ''')
        
        # 创建索引
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_skill_type ON skilltype_constraints(skill_type)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_constraint_type ON skilltype_constraints(constraint_type)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_skill_name ON skilltype_constraints(skill_name)')
        
        self.conn.commit()
    
    def build_index(self, pob_data_path: str):
        """
        构建SkillType索引
        
        Args:
            pob_data_path: POB数据路径
        """
        logger.info(f"开始构建SkillType索引: {pob_data_path}")
        
        pob_path = Path(pob_data_path)
        
        # 索引技能文件中的skillTypes约束
        skills_dir = pob_path / 'Data' / 'Skills'
        if skills_dir.exists():
            for lua_file in skills_dir.glob('*.lua'):
                self._index_skilltype_constraints(lua_file)
        
        logger.info(f"SkillType索引构建完成: {self._get_record_count()} 条记录")
    
    def _index_skilltype_constraints(self, lua_file: Path):
        """索引技能文件中的skillTypes约束"""
        logger.debug(f"索引skillType约束: {lua_file.name}")
        
        try:
            with open(lua_file, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')
            
            # 提取技能定义块
            # 格式: { name = "SkillName", requireSkillTypes = { ... }, ... }
            
            current_skill = None
            block_depth = 0
            skill_block_start = 0
            
            for i, line in enumerate(lines, 1):
                # 检测技能块开始
                if 'name' in line and '=' in line and '"' in line:
                    name_match = re.search(r'name\s*=\s*"([^"]+)"', line)
                    if name_match:
                        current_skill = name_match.group(1)
                        skill_block_start = i
                        block_depth = 1
                        continue
                
                # 计算块深度
                if current_skill:
                    block_depth += line.count('{') - line.count('}')
                    
                    # 块结束
                    if block_depth <= 0:
                        # 处理整个技能块
                        block_lines = lines[skill_block_start-1:i]
                        self._process_skill_block(current_skill, block_lines, lua_file)
                        
                        current_skill = None
                        block_depth = 0
            
            self.conn.commit()
            
        except Exception as e:
            logger.error(f"索引skillType约束失败 {lua_file.name}: {e}")
    
    def _process_skill_block(self, skill_name: str, block_lines: List[str], lua_file: Path):
        """处理技能块，提取约束"""
        
        block_text = '\n'.join(block_lines)
        
        # 提取requireSkillTypes
        require_match = re.search(r'requireSkillTypes\s*=\s*\{([^}]+)\}', block_text)
        if require_match:
            types_str = require_match.group(1)
            types = re.findall(r'SkillType\.(\w+)', types_str)
            
            for skill_type in types:
                self._insert_constraint(
                    skill_type=skill_type,
                    constraint_type='require',
                    skill_name=skill_name,
                    lua_file=lua_file,
                    line_num=self._find_line_number(block_lines, 'requireSkillTypes'),
                    context=require_match.group(0)
                )
        
        # 提取excludeSkillTypes
        exclude_match = re.search(r'excludeSkillTypes\s*=\s*\{([^}]+)\}', block_text)
        if exclude_match:
            types_str = exclude_match.group(1)
            types = re.findall(r'SkillType\.(\w+)', types_str)
            
            for skill_type in types:
                self._insert_constraint(
                    skill_type=skill_type,
                    constraint_type='exclude',
                    skill_name=skill_name,
                    lua_file=lua_file,
                    line_num=self._find_line_number(block_lines, 'excludeSkillTypes'),
                    context=exclude_match.group(0)
                )
        
        # 提取addSkillTypes
        add_match = re.search(r'addSkillTypes\s*=\s*\{([^}]+)\}', block_text)
        if add_match:
            types_str = add_match.group(1)
            types = re.findall(r'SkillType\.(\w+)', types_str)
            
            for skill_type in types:
                self._insert_constraint(
                    skill_type=skill_type,
                    constraint_type='add',
                    skill_name=skill_name,
                    lua_file=lua_file,
                    line_num=self._find_line_number(block_lines, 'addSkillTypes'),
                    context=add_match.group(0)
                )
    
    def _insert_constraint(self, skill_type: str, constraint_type: str, skill_name: str,
                          lua_file: Path, line_num: int, context: str):
        """插入约束记录"""
        cursor = self.conn.cursor()
        
        # 插入skillType定义
        cursor.execute('''
            INSERT OR IGNORE INTO skilltype_definitions (skill_type, type_name)
            VALUES (?, ?)
        ''', (skill_type, skill_type))
        
        # 插入约束
        cursor.execute('''
            INSERT INTO skilltype_constraints 
            (skill_type, constraint_type, skill_name, file_path, line_number, context)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (skill_type, constraint_type, skill_name, str(lua_file), line_num, context))
    
    def _find_line_number(self, lines: List[str], keyword: str) -> int:
        """查找关键词所在行号"""
        for i, line in enumerate(lines, 1):
            if keyword in line:
                return i
        return 0
    
    def update_index(self, changed_file: str):
        """
        增量更新索引
        
        Args:
            changed_file: 变更的文件路径
        """
        file_path = Path(changed_file)
        
        if 'Skills' in changed_file:
            # 删除旧约束
            cursor = self.conn.cursor()
            cursor.execute('DELETE FROM skilltype_constraints WHERE file_path = ?', (changed_file,))
            
            # 重新索引
            self._index_skilltype_constraints(file_path)
    
    def search(self, query: Dict[str, Any]) -> Dict[str, Any]:
        """
        搜索SkillType索引
        
        Args:
            query: 查询参数，支持:
                - skill_type: skillType名称
                - skill_name: 技能名称
                - constraint_type: 约束类型（require/exclude/add）
                
        Returns:
            查询结果
        """
        cursor = self.conn.cursor()
        
        # 按skillType查询
        if 'skill_type' in query:
            skill_type = query['skill_type']
            
            # 查询所有约束
            constraints = cursor.execute(
                'SELECT * FROM skilltype_constraints WHERE skill_type = ?',
                (skill_type,)
            ).fetchall()
            
            # 分类
            required = [dict(c) for c in constraints if c['constraint_type'] == 'require']
            excluded = [dict(c) for c in constraints if c['constraint_type'] == 'exclude']
            added = [dict(c) for c in constraints if c['constraint_type'] == 'add']
            
            return {
                'found': len(constraints) > 0,
                'skill_type': skill_type,
                'required_by': required,
                'excluded_by': excluded,
                'added_by': added,
                'total_constraints': len(constraints)
            }
        
        # 按技能名称查询
        elif 'skill_name' in query:
            skill_name = query['skill_name']
            
            constraints = cursor.execute(
                'SELECT * FROM skilltype_constraints WHERE skill_name = ?',
                (skill_name,)
            ).fetchall()
            
            return {
                'found': len(constraints) > 0,
                'skill_name': skill_name,
                'constraints': [dict(c) for c in constraints],
                'constraint_count': len(constraints)
            }
        
        return {'found': False}
    
    def _get_record_count(self) -> int:
        """获取记录数量"""
        cursor = self.conn.cursor()
        count = cursor.execute('SELECT COUNT(*) FROM skilltype_definitions').fetchone()[0]
        return count
    
    def get_all_skilltypes(self) -> List[str]:
        """获取所有skillType列表"""
        cursor = self.conn.cursor()
        
        results = cursor.execute(
            'SELECT skill_type FROM skilltype_definitions ORDER BY skill_type'
        ).fetchall()
        
        return [r['skill_type'] for r in results]
