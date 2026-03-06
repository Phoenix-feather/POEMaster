#!/usr/bin/env python3
"""
公式提取器 - 从POB的Lua文件中提取所有计算函数

核心功能：
1. 解析Lua函数定义
2. 提取stat特征
3. 推断标签
4. 建立调用关系
5. 存储到formulas.db
"""

import os
import re
import json
import sqlite3
from pathlib import Path
from typing import Dict, List, Any, Optional, Set, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime


@dataclass
class LuaFunction:
    """Lua函数定义"""
    name: str
    params: List[str]
    body: str
    start_line: int
    end_line: int
    is_local: bool = False
    source_file: str = ""


@dataclass
class FormulaFeatures:
    """公式特征"""
    exact_stats: List[str] = field(default_factory=list)      # 精确stat ID
    fuzzy_stats: List[str] = field(default_factory=list)      # 模糊stat名称
    inferred_tags: List[str] = field(default_factory=list)    # 推断标签
    calls: List[str] = field(default_factory=list)            # 调用的函数


class FormulaExtractor:
    """公式提取器"""
    
    def __init__(self, pob_path: str, db_path: str, entities_db_path: str = None):
        """
        初始化公式提取器
        
        Args:
            pob_path: POB数据目录路径
            db_path: 公式库数据库路径
            entities_db_path: 实体库路径（用于加载官方stat ID）
        """
        self.pob_path = Path(pob_path)
        self.db_path = Path(db_path)
        self.entities_db_path = Path(entities_db_path) if entities_db_path else None
        
        # 加载官方stat ID
        self.official_stats = self._load_official_stats()
        
        # 初始化数据库
        self._init_database()
        
        print(f"[初始化] 公式提取器")
        print(f"  POB路径: {self.pob_path}")
        print(f"  数据库: {self.db_path}")
        print(f"  官方Stat ID数量: {len(self.official_stats)}")
    
    def _load_official_stats(self) -> Set[str]:
        """从实体库加载官方stat ID"""
        official_stats = set()
        
        if not self.entities_db_path or not self.entities_db_path.exists():
            print("[警告] 未找到实体库，无法加载官方stat ID")
            return official_stats
        
        try:
            conn = sqlite3.connect(str(self.entities_db_path))
            cursor = conn.cursor()
            
            # 从stat_mapping实体提取stat ID
            cursor.execute("""
                SELECT data_json 
                FROM entities 
                WHERE type = 'stat_mapping'
            """)
            
            for row in cursor.fetchall():
                data = json.loads(row[0]) if row[0] else {}
                mod_data = data.get('mod_data', [])
                
                if isinstance(mod_data, list):
                    for mod in mod_data:
                        if isinstance(mod, dict) and 'name' in mod:
                            official_stats.add(mod['name'])
            
            conn.close()
            print(f"[OK] 从实体库加载 {len(official_stats)} 个官方stat ID")
            
        except Exception as e:
            print(f"[错误] 加载官方stat ID失败: {e}")
        
        return official_stats
    
    def _init_database(self):
        """初始化数据库表"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        # 创建formulas表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS formulas (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                code TEXT NOT NULL,
                source_file TEXT NOT NULL,
                line_start INTEGER,
                line_end INTEGER,
                exact_stats TEXT,
                fuzzy_stats TEXT,
                inferred_tags TEXT,
                calls TEXT,
                called_by TEXT,
                call_depth INTEGER DEFAULT 0,
                total_stats TEXT,
                constraints TEXT,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 创建formula_features表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS formula_features (
                formula_id TEXT,
                feature_type TEXT,
                feature_value TEXT,
                confidence REAL DEFAULT 1.0,
                PRIMARY KEY (formula_id, feature_type, feature_value)
            )
        """)
        
        # 创建formula_stats表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS formula_stats (
                formula_id TEXT,
                stat_id TEXT,
                relation TEXT,
                confidence REAL DEFAULT 1.0,
                PRIMARY KEY (formula_id, stat_id, relation)
            )
        """)
        
        # 创建formula_calls表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS formula_calls (
                caller_id TEXT,
                callee_id TEXT,
                call_count INTEGER DEFAULT 1,
                call_context TEXT,
                PRIMARY KEY (caller_id, callee_id)
            )
        """)
        
        # 创建索引
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_formula_source ON formulas(source_file)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_formula_name ON formulas(name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_feature_value ON formula_features(feature_value)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_fs_stat ON formula_stats(stat_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_fc_callee ON formula_calls(callee_id)")
        
        conn.commit()
        conn.close()
        
        print(f"[OK] 数据库初始化完成: {self.db_path}")
    
    def extract_all_functions(self):
        """提取所有Lua函数"""
        print("\n" + "=" * 70)
        print("开始提取所有Lua函数")
        print("=" * 70)
        
        all_functions = []
        lua_files = list(self.pob_path.rglob('*.lua'))
        
        print(f"\n找到 {len(lua_files)} 个Lua文件")
        
        for i, lua_file in enumerate(lua_files, 1):
            if i % 100 == 0:
                print(f"  处理进度: {i}/{len(lua_files)}")
            
            # 跳过黑名单文件
            if self._should_skip_file(lua_file):
                continue
            
            try:
                functions = self._parse_lua_file(lua_file)
                
                for func in functions:
                    formula = self._extract_formula(func, lua_file)
                    if formula:
                        all_functions.append(formula)
                        
            except Exception as e:
                print(f"[错误] 解析文件失败 {lua_file}: {e}")
        
        print(f"\n[OK] 提取完成，共 {len(all_functions)} 个函数")
        
        # 保存到数据库
        self._save_formulas(all_functions)
        
        return all_functions
    
    def _should_skip_file(self, file_path: Path) -> bool:
        """判断是否应该跳过文件"""
        skip_patterns = [
            'LaunchServer.lua',  # HTTP服务器
            'test',              # 测试文件
            'spec',              # 测试规格
        ]
        
        file_str = str(file_path)
        for pattern in skip_patterns:
            if pattern in file_str:
                return True
        
        return False
    
    def _parse_lua_file(self, file_path: Path) -> List[LuaFunction]:
        """解析Lua文件，提取所有函数定义"""
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        functions = []
        
        # 解析标准函数定义: function name(params) ... end
        pattern1 = r'function\s+(\w+)\s*\(([^)]*)\)'
        matches1 = list(re.finditer(pattern1, content))
        
        for match in matches1:
            func_name = match.group(1)
            params_str = match.group(2)
            params = [p.strip() for p in params_str.split(',') if p.strip()]
            
            # 提取函数体
            start_pos = match.start()
            body = self._extract_function_body(content, start_pos)
            
            if body:
                start_line = content[:start_pos].count('\n') + 1
                end_line = start_line + body.count('\n')
                
                func = LuaFunction(
                    name=func_name,
                    params=params,
                    body=body,
                    start_line=start_line,
                    end_line=end_line,
                    source_file=str(file_path.relative_to(self.pob_path))
                )
                functions.append(func)
        
        # 解析local函数定义: local function name(params) ... end
        pattern2 = r'local\s+function\s+(\w+)\s*\(([^)]*)\)'
        matches2 = list(re.finditer(pattern2, content))
        
        for match in matches2:
            func_name = match.group(1)
            params_str = match.group(2)
            params = [p.strip() for p in params_str.split(',') if p.strip()]
            
            # 提取函数体
            start_pos = match.start()
            body = self._extract_function_body(content, start_pos)
            
            if body:
                start_line = content[:start_pos].count('\n') + 1
                end_line = start_line + body.count('\n')
                
                func = LuaFunction(
                    name=func_name,
                    params=params,
                    body=body,
                    start_line=start_line,
                    end_line=end_line,
                    is_local=True,
                    source_file=str(file_path.relative_to(self.pob_path))
                )
                functions.append(func)
        
        return functions
    
    def _extract_function_body(self, content: str, start_pos: int) -> Optional[str]:
        """提取函数体（使用括号平衡）"""
        # 找到函数开始的 {
        brace_start = content.find('{', start_pos)
        if brace_start == -1:
            return None
        
        # 使用括号平衡找到匹配的 }
        depth = 0
        i = brace_start
        
        while i < len(content):
            if content[i] == '{':
                depth += 1
            elif content[i] == '}':
                depth -= 1
                if depth == 0:
                    # 找到匹配的结束括号
                    return content[brace_start:i+1]
            i += 1
        
        return None
    
    def _extract_formula(self, func: LuaFunction, source_file: Path) -> Optional[Dict]:
        """提取公式并分析特征"""
        # 提取特征
        features = self._extract_features(func.body)
        
        # 生成公式ID
        formula_id = f"{source_file.stem}_{func.name}"
        
        formula = {
            'id': formula_id,
            'name': func.name,
            'code': func.body,
            'source_file': func.source_file,
            'line_start': func.start_line,
            'line_end': func.end_line,
            'exact_stats': json.dumps(features.exact_stats, ensure_ascii=False),
            'fuzzy_stats': json.dumps(features.fuzzy_stats, ensure_ascii=False),
            'inferred_tags': json.dumps(features.inferred_tags, ensure_ascii=False),
            'calls': json.dumps(features.calls, ensure_ascii=False),
            'called_by': json.dumps([], ensure_ascii=False),
            'call_depth': 0,
            'total_stats': json.dumps([], ensure_ascii=False),
            'constraints': json.dumps([], ensure_ascii=False),
            'description': ''
        }
        
        return formula
    
    def _extract_features(self, code: str) -> FormulaFeatures:
        """从代码中提取特征"""
        features = FormulaFeatures()
        
        # 1. 提取stat名称
        stat_names = self._extract_stat_names(code)
        
        # 2. 分类为精确/模糊
        for stat_name in stat_names:
            if stat_name in self.official_stats:
                features.exact_stats.append(stat_name)
            else:
                features.fuzzy_stats.append(stat_name)
        
        # 3. 推断标签
        features.inferred_tags = self._infer_tags(code)
        
        # 4. 提取函数调用
        features.calls = self._extract_function_calls(code)
        
        return features
    
    def _extract_stat_names(self, code: str) -> List[str]:
        """从代码中提取stat名称"""
        stats = []
        
        # 模式1：activeSkill.skillData.xxx
        pattern1 = r'activeSkill\.skillData\.(\w+)'
        stats.extend(re.findall(pattern1, code))
        
        # 模式2：skillModList:Sum("INC", cfg, "Speed")
        pattern2 = r'skillModList:(Sum|More|Flag)\([^,]+,\s*[^,]+,\s*"(\w+)"\)'
        for match in re.finditer(pattern2, code):
            stats.append(match.group(2))
        
        # 模式3：output.xxx
        pattern3 = r'output\.(\w+)'
        stats.extend(re.findall(pattern3, code))
        
        # 模式4：skill.skillData.xxx
        pattern4 = r'skill\.skillData\.(\w+)'
        stats.extend(re.findall(pattern4, code))
        
        return list(set(stats))  # 去重
    
    def _infer_tags(self, code: str) -> List[str]:
        """从代码推断标签"""
        tags = []
        
        # 规则库
        tag_rules = [
            (r'triggerSource', 'triggered'),
            (r'trigger', 'triggered'),
            (r'cooldown', 'cooldown'),
            (r'castTime', 'cast'),
            (r'attackSpeed', 'attack'),
            (r'spell', 'spell'),
            (r'projectile', 'projectile'),
            (r'area', 'area'),
            (r'minion', 'minion'),
            (r'totem', 'totem'),
        ]
        
        for pattern, tag in tag_rules:
            if re.search(pattern, code, re.IGNORECASE):
                tags.append(tag)
        
        return list(set(tags))  # 去重
    
    def _extract_function_calls(self, code: str) -> List[str]:
        """提取函数调用"""
        calls = []
        
        # 匹配 functionName( 格式
        pattern = r'\b(\w+)\s*\('
        matches = re.findall(pattern, code)
        
        # 过滤掉Lua关键字和内置函数
        keywords = {'if', 'for', 'while', 'function', 'return', 'local', 'end', 'then', 'else', 'elseif', 'do', 'repeat', 'until'}
        builtin = {'print', 'pairs', 'ipairs', 'next', 'type', 'tostring', 'tonumber', 'math', 'table', 'string'}
        
        for match in matches:
            if match not in keywords and match not in builtin:
                calls.append(match)
        
        return list(set(calls))  # 去重
    
    def _save_formulas(self, formulas: List[Dict]):
        """保存公式到数据库"""
        print("\n保存公式到数据库...")
        
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        # 批量插入
        for formula in formulas:
            try:
                cursor.execute("""
                    INSERT OR REPLACE INTO formulas 
                    (id, name, code, source_file, line_start, line_end, 
                     exact_stats, fuzzy_stats, inferred_tags, calls, called_by,
                     call_depth, total_stats, constraints, description)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    formula['id'],
                    formula['name'],
                    formula['code'],
                    formula['source_file'],
                    formula['line_start'],
                    formula['line_end'],
                    formula['exact_stats'],
                    formula['fuzzy_stats'],
                    formula['inferred_tags'],
                    formula['calls'],
                    formula['called_by'],
                    formula['call_depth'],
                    formula['total_stats'],
                    formula['constraints'],
                    formula['description']
                ))
                
                # 插入特征索引
                formula_id = formula['id']
                
                # 精确stat
                for stat in json.loads(formula['exact_stats']):
                    cursor.execute("""
                        INSERT OR IGNORE INTO formula_features
                        (formula_id, feature_type, feature_value, confidence)
                        VALUES (?, 'exact', ?, 1.0)
                    """, (formula_id, stat))
                
                # 模糊stat
                for stat in json.loads(formula['fuzzy_stats']):
                    cursor.execute("""
                        INSERT OR IGNORE INTO formula_features
                        (formula_id, feature_type, feature_value, confidence)
                        VALUES (?, 'fuzzy', ?, 0.7)
                    """, (formula_id, stat))
                
                # 标签
                for tag in json.loads(formula['inferred_tags']):
                    cursor.execute("""
                        INSERT OR IGNORE INTO formula_features
                        (formula_id, feature_type, feature_value, confidence)
                        VALUES (?, 'tag', ?, 0.8)
                    """, (formula_id, tag))
                
            except Exception as e:
                print(f"[错误] 保存公式失败 {formula['id']}: {e}")
        
        conn.commit()
        conn.close()
        
        print(f"[OK] 已保存 {len(formulas)} 个公式到数据库")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='公式提取器')
    parser.add_argument('pob_path', help='POB数据目录路径')
    parser.add_argument('--db', default='formulas.db', help='公式库数据库路径')
    parser.add_argument('--entities-db', help='实体库路径（用于加载官方stat ID）')
    
    args = parser.parse_args()
    
    # 创建提取器
    extractor = FormulaExtractor(
        pob_path=args.pob_path,
        db_path=args.db,
        entities_db_path=args.entities_db
    )
    
    # 提取所有函数
    formulas = extractor.extract_all_functions()
    
    print(f"\n完成！共提取 {len(formulas)} 个公式")


if __name__ == "__main__":
    main()
