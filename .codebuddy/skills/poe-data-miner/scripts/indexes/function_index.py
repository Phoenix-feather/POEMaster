"""
函数调用索引

三级索引：快速定位CalcModules中的函数和调用关系
"""

import re
import logging
from typing import Dict, List, Any, Optional, Set
from pathlib import Path
from collections import defaultdict

from .base_index import BaseIndex

logger = logging.getLogger(__name__)


class FunctionCallIndex(BaseIndex):
    """函数调用三级索引"""
    
    def __init__(self, db_path: str):
        """
        初始化函数调用索引
        
        Args:
            db_path: 索引数据库路径
        """
        super().__init__(db_path, 'function_index')
    
    def _create_tables(self):
        """创建索引表"""
        cursor = self.conn.cursor()
        
        # 函数定义表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS function_definitions (
                function_name TEXT PRIMARY KEY,
                file_path TEXT NOT NULL,
                start_line INTEGER,
                end_line INTEGER,
                parameters TEXT,
                return_type TEXT,
                description TEXT,
                is_local INTEGER DEFAULT 0,
                is_exported INTEGER DEFAULT 0,
                call_count INTEGER DEFAULT 0,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 函数调用表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS function_calls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                caller_function TEXT NOT NULL,
                caller_file TEXT NOT NULL,
                caller_line INTEGER,
                callee_function TEXT NOT NULL,
                call_context TEXT,
                call_type TEXT DEFAULT 'normal',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (callee_function) REFERENCES function_definitions(function_name)
            )
        ''')
        
        # 函数参数表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS function_parameters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                function_name TEXT NOT NULL,
                param_name TEXT NOT NULL,
                param_index INTEGER,
                param_type TEXT,
                default_value TEXT,
                is_variadic INTEGER DEFAULT 0,
                FOREIGN KEY (function_name) REFERENCES function_definitions(function_name)
            )
        ''')
        
        # 创建索引
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_function_name ON function_definitions(function_name)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_caller_function ON function_calls(caller_function)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_callee_function ON function_calls(callee_function)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_file_path ON function_definitions(file_path)')
        
        self.conn.commit()
    
    def build_index(self, pob_data_path: str):
        """
        构建函数调用索引
        
        Args:
            pob_data_path: POB数据路径
        """
        logger.info(f"开始构建函数调用索引: {pob_data_path}")
        
        pob_path = Path(pob_data_path)
        
        # 1. 索引Modules目录中的Calc*.lua文件
        modules_dir = pob_path / 'Modules'
        if modules_dir.exists():
            for lua_file in modules_dir.glob('Calc*.lua'):
                self._index_lua_functions(lua_file)
            
            # 也索引Common.lua等工具文件
            for lua_file in modules_dir.glob('*.lua'):
                if 'Calc' in lua_file.name or lua_file.name in ['Common.lua', 'Data.lua']:
                    continue  # 已经索引过了
                if lua_file.name in ['Common.lua', 'Data.lua', 'ModTools.lua', 'ItemTools.lua']:
                    self._index_lua_functions(lua_file)
        
        # 2. 构建调用图
        self._build_call_graph()
        
        # 3. 更新调用计数
        self._update_call_counts()
        
        logger.info(f"函数调用索引构建完成: {self._get_record_count()} 个函数")
    
    def _index_lua_functions(self, lua_file: Path):
        """索引Lua文件中的函数定义和调用"""
        logger.debug(f"索引函数: {lua_file.name}")
        
        try:
            with open(lua_file, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')
            
            # 第一遍：提取函数定义
            functions = self._extract_function_definitions(lua_file, lines, content)
            
            # 第二遍：提取函数调用
            calls = self._extract_function_calls(lua_file, lines, functions)
            
            # 插入数据库
            self._insert_functions(functions)
            self._insert_calls(calls)
            
        except Exception as e:
            logger.error(f"索引函数失败 {lua_file.name}: {e}")
    
    def _extract_function_definitions(self, lua_file: Path, lines: List[str], content: str) -> List[Dict]:
        """
        提取函数定义
        
        Lua函数定义格式：
        1. function funcName(...) ... end
        2. local function funcName(...) ... end
        3. funcName = function(...) ... end
        4. obj.method = function(...) ... end
        """
        functions = []
        
        # 模式1: function funcName(...) 或 local function funcName(...)
        func_pattern1 = re.compile(r'^(local\s+)?function\s+([a-zA-Z_][a-zA-Z0-9_.]*)\s*\(([^)]*)\)')
        
        # 模式2: funcName = function(...) 或 obj.method = function(...)
        func_pattern2 = re.compile(r'([a-zA-Z_][a-zA-Z0-9_.]*)\s*=\s*function\s*\(([^)]*)\)')
        
        i = 0
        while i < len(lines):
            line = lines[i]
            
            # 尝试模式1
            match1 = func_pattern1.search(line)
            if match1:
                is_local = match1.group(1) is not None
                func_name = match1.group(2)
                params_str = match1.group(3)
                
                # 查找函数结束位置
                end_line = self._find_function_end(lines, i)
                
                # 提取描述（从注释）
                description = self._extract_function_description(lines, i)
                
                # 解析参数
                params = self._parse_parameters(params_str)
                
                functions.append({
                    'function_name': func_name,
                    'file_path': str(lua_file),
                    'start_line': i + 1,
                    'end_line': end_line + 1,
                    'parameters': params,
                    'is_local': is_local,
                    'description': description
                })
            
            # 尝试模式2
            else:
                match2 = func_pattern2.search(line)
                if match2:
                    func_name = match2.group(1)
                    params_str = match2.group(2)
                    
                    # 查找函数结束位置
                    end_line = self._find_function_end(lines, i)
                    
                    # 提取描述
                    description = self._extract_function_description(lines, i)
                    
                    # 解析参数
                    params = self._parse_parameters(params_str)
                    
                    functions.append({
                        'function_name': func_name,
                        'file_path': str(lua_file),
                        'start_line': i + 1,
                        'end_line': end_line + 1,
                        'parameters': params,
                        'is_local': False,
                        'description': description
                    })
            
            i += 1
        
        return functions
    
    def _find_function_end(self, lines: List[str], start_line: int) -> int:
        """查找函数结束位置（匹配end）"""
        depth = 0
        in_function = False
        
        for i in range(start_line, len(lines)):
            line = lines[i]
            
            # 计算块的开始
            if 'function' in line and not line.strip().startswith('--'):
                if 'function' in line.split('=')[-1]:  # function literal
                    depth += 1
                    in_function = True
                elif re.search(r'\bfunction\s+[a-zA-Z_]', line):  # named function
                    depth += 1
                    in_function = True
            
            # 计算其他块开始
            depth += line.count('{') + line.count('if') + line.count('for') + line.count('while')
            
            # 计算块结束
            depth -= line.count('}')
            
            if 'end' in line and not line.strip().startswith('--'):
                depth -= line.count('end')
                
                if in_function and depth == 0:
                    return i
        
        return len(lines) - 1
    
    def _extract_function_description(self, lines: List[str], func_line: int) -> str:
        """提取函数描述（从注释）"""
        description_lines = []
        
        # 查找函数前的注释
        for i in range(func_line - 1, max(0, func_line - 10), -1):
            line = lines[i].strip()
            
            if line.startswith('--'):
                # 移除注释标记
                desc = line.lstrip('-').strip()
                if desc:
                    description_lines.insert(0, desc)
            elif line == '':
                continue
            else:
                break
        
        return ' '.join(description_lines) if description_lines else ''
    
    def _parse_parameters(self, params_str: str) -> List[Dict]:
        """解析函数参数"""
        if not params_str.strip():
            return []
        
        params = []
        param_list = [p.strip() for p in params_str.split(',')]
        
        for i, param in enumerate(param_list):
            param_info = {
                'param_name': param,
                'param_index': i,
                'param_type': 'any',
                'default_value': None,
                'is_variadic': param == '...'
            }
            
            # 检查是否有默认值（Lua不直接支持，但在注释中可能标注）
            # 格式: param = default
            if '=' in param:
                parts = param.split('=')
                param_info['param_name'] = parts[0].strip()
                param_info['default_value'] = parts[1].strip()
            
            params.append(param_info)
        
        return params
    
    def _extract_function_calls(self, lua_file: Path, lines: List[str], 
                                defined_functions: List[Dict]) -> List[Dict]:
        """
        提取函数调用
        
        格式：
        1. funcName(...)
        2. obj:method(...)
        3. obj.method(...)
        """
        calls = []
        
        # 已定义的函数名集合
        defined_names = {f['function_name'] for f in defined_functions}
        
        # 常见函数名（用于过滤）
        builtin_functions = {
            'print', 'pairs', 'ipairs', 'next', 'type', 'tostring', 'tonumber',
            'table.insert', 'table.remove', 'table.concat', 'table.sort',
            'string.format', 'string.len', 'string.sub', 'string.find',
            'math.floor', 'math.ceil', 'math.min', 'math.max', 'math.abs'
        }
        
        for i, line in enumerate(lines):
            # 跳过注释行
            if line.strip().startswith('--'):
                continue
            
            # 提取当前行所在的函数（调用者）
            caller = self._find_caller_function(defined_functions, i)
            
            # 查找函数调用
            # 模式: funcName( 或 obj:method( 或 obj.method(
            call_pattern = re.compile(r'([a-zA-Z_][a-zA-Z0-9_.:]*?)\s*\(')
            
            for match in call_pattern.finditer(line):
                callee = match.group(1)
                
                # 过滤
                if callee in builtin_functions:
                    continue
                
                # 移除对象前缀，只保留方法名
                if '.' in callee or ':' in callee:
                    parts = re.split(r'[.:]', callee)
                    if len(parts) > 1:
                        # 可能是 obj.method 或 obj:method
                        callee = parts[-1]
                
                # 只记录用户定义的函数或可能是重要的函数
                if callee in defined_names or callee.startswith('is') or callee.startswith('has') or callee.startswith('calc'):
                    calls.append({
                        'caller_function': caller,
                        'caller_file': str(lua_file),
                        'caller_line': i + 1,
                        'callee_function': callee,
                        'call_context': line.strip()
                    })
        
        return calls
    
    def _find_caller_function(self, defined_functions: List[Dict], line_number: int) -> str:
        """查找某个行所在的函数"""
        for func in defined_functions:
            if func['start_line'] <= line_number + 1 <= func['end_line']:
                return func['function_name']
        return '<global>'
    
    def _insert_functions(self, functions: List[Dict]):
        """插入函数定义"""
        cursor = self.conn.cursor()
        
        for func in functions:
            # 插入函数定义
            cursor.execute('''
                INSERT OR REPLACE INTO function_definitions 
                (function_name, file_path, start_line, end_line, parameters, 
                 is_local, description)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                func['function_name'],
                func['file_path'],
                func['start_line'],
                func['end_line'],
                str(func['parameters']),  # JSON字符串
                func['is_local'],
                func['description']
            ))
            
            # 插入参数
            for param in func['parameters']:
                cursor.execute('''
                    INSERT INTO function_parameters 
                    (function_name, param_name, param_index, param_type, 
                     default_value, is_variadic)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    func['function_name'],
                    param['param_name'],
                    param['param_index'],
                    param['param_type'],
                    param['default_value'],
                    param['is_variadic']
                ))
        
        self.conn.commit()
    
    def _insert_calls(self, calls: List[Dict]):
        """插入函数调用"""
        cursor = self.conn.cursor()
        
        for call in calls:
            cursor.execute('''
                INSERT INTO function_calls 
                (caller_function, caller_file, caller_line, callee_function, call_context)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                call['caller_function'],
                call['caller_file'],
                call['caller_line'],
                call['callee_function'],
                call['call_context']
            ))
        
        self.conn.commit()
    
    def _build_call_graph(self):
        """构建调用图（计算调用深度和循环检测）"""
        logger.info("构建函数调用图...")
        
        cursor = self.conn.cursor()
        
        # 获取所有函数
        functions = cursor.execute(
            'SELECT function_name FROM function_definitions'
        ).fetchall()
        
        # 构建邻接表
        call_graph = defaultdict(set)
        
        calls = cursor.execute(
            'SELECT caller_function, callee_function FROM function_calls'
        ).fetchall()
        
        for call in calls:
            call_graph[call['caller_function']].add(call['callee_function'])
        
        # 计算每个函数的调用深度
        for func in functions:
            func_name = func['function_name']
            depth = self._calculate_call_depth(func_name, call_graph, set())
            
            cursor.execute('''
                UPDATE function_definitions 
                SET call_depth = ? 
                WHERE function_name = ?
            ''', (depth, func_name))
        
        self.conn.commit()
    
    def _calculate_call_depth(self, func_name: str, call_graph: Dict, visited: Set[str]) -> int:
        """计算函数调用深度"""
        if func_name in visited:
            return 0  # 循环调用
        
        visited.add(func_name)
        
        callees = call_graph.get(func_name, set())
        if not callees:
            return 0
        
        max_depth = 0
        for callee in callees:
            depth = self._calculate_call_depth(callee, call_graph, visited.copy())
            max_depth = max(max_depth, depth + 1)
        
        return max_depth
    
    def _update_call_counts(self):
        """更新调用计数"""
        cursor = self.conn.cursor()
        
        cursor.execute('''
            UPDATE function_definitions 
            SET call_count = (
                SELECT COUNT(*) FROM function_calls 
                WHERE function_calls.callee_function = function_definitions.function_name
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
        
        # 删除旧数据
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM function_definitions WHERE file_path = ?', (changed_file,))
        cursor.execute('DELETE FROM function_calls WHERE caller_file = ?', (changed_file,))
        
        # 重新索引
        self._index_lua_functions(file_path)
        
        # 重建调用图
        self._build_call_graph()
    
    def search(self, query: Dict[str, Any]) -> Dict[str, Any]:
        """
        搜索函数索引
        
        Args:
            query: 查询参数，支持:
                - function_name: 函数名
                - file_path: 文件路径
                - caller: 调用者函数名
                - callee: 被调用函数名
                
        Returns:
            查询结果
        """
        cursor = self.conn.cursor()
        
        # 按函数名查询
        if 'function_name' in query:
            func_name = query['function_name']
            
            # 查询定义
            definition = cursor.execute(
                'SELECT * FROM function_definitions WHERE function_name = ?',
                (func_name,)
            ).fetchone()
            
            # 查询调用者
            callers = cursor.execute(
                'SELECT * FROM function_calls WHERE callee_function = ?',
                (func_name,)
            ).fetchall()
            
            # 查询被调用函数
            callees = cursor.execute(
                'SELECT * FROM function_calls WHERE caller_function = ?',
                (func_name,)
            ).fetchall()
            
            # 查询参数
            parameters = cursor.execute(
                'SELECT * FROM function_parameters WHERE function_name = ?',
                (func_name,)
            ).fetchall()
            
            return {
                'found': definition is not None,
                'definition': dict(definition) if definition else None,
                'parameters': [dict(p) for p in parameters],
                'called_by': [dict(c) for c in callers],
                'calls_to': [dict(c) for c in callees],
                'call_count': len(callers)
            }
        
        # 按文件查询
        elif 'file_path' in query:
            file_path = query['file_path']
            
            functions = cursor.execute(
                'SELECT * FROM function_definitions WHERE file_path = ?',
                (file_path,)
            ).fetchall()
            
            return {
                'found': len(functions) > 0,
                'functions': [dict(f) for f in functions],
                'function_count': len(functions)
            }
        
        return {'found': False}
    
    def _get_record_count(self) -> int:
        """获取记录数量"""
        cursor = self.conn.cursor()
        count = cursor.execute('SELECT COUNT(*) FROM function_definitions').fetchone()[0]
        return count
    
    def get_top_called_functions(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        获取调用次数最多的函数
        
        Args:
            limit: 返回数量
            
        Returns:
            函数列表
        """
        cursor = self.conn.cursor()
        
        results = cursor.execute('''
            SELECT function_name, file_path, call_count 
            FROM function_definitions 
            ORDER BY call_count DESC 
            LIMIT ?
        ''', (limit,)).fetchall()
        
        return [dict(r) for r in results]
    
    def find_call_chain(self, start_func: str, end_func: str, max_depth: int = 10) -> List[List[str]]:
        """
        查找两个函数之间的调用链
        
        Args:
            start_func: 起始函数
            end_func: 目标函数
            max_depth: 最大搜索深度
            
        Returns:
            调用链列表
        """
        cursor = self.conn.cursor()
        
        # 获取所有调用关系
        calls = cursor.execute(
            'SELECT caller_function, callee_function FROM function_calls'
        ).fetchall()
        
        # 构建邻接表
        call_graph = defaultdict(list)
        for call in calls:
            call_graph[call['caller_function']].append(call['callee_function'])
        
        # BFS查找路径
        from collections import deque
        
        paths = []
        queue = deque([(start_func, [start_func])])
        visited = set()
        
        while queue and len(paths) < 10:
            current, path = queue.popleft()
            
            if len(path) > max_depth:
                continue
            
            if current == end_func:
                paths.append(path)
                continue
            
            if current in visited:
                continue
            
            visited.add(current)
            
            for callee in call_graph[current]:
                if callee not in path:  # 避免循环
                    queue.append((callee, path + [callee]))
        
        return paths
