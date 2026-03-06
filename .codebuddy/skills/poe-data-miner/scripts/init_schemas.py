#!/usr/bin/env python3
"""
Schema 初始化脚本
- 扫描代码文件
- 识别定义者和引用者
- 生成 schemas.json
"""

import re
import json
import hashlib
from pathlib import Path
from typing import Dict, List, Any, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class SchemaDefinition:
    """结构定义"""
    schema_id: str
    definition_file: str
    definition_type: str  # sqlite_table, dataclass, enum
    class_name: str = None
    table_name: str = None


@dataclass 
class ConsumerReference:
    """引用关系"""
    schema_id: str
    consumer_file: str


class SchemaInitializer:
    """Schema 初始化器"""
    
    # 定义模式
    DEFINITION_PATTERNS = {
        'sqlite_table': re.compile(
            r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)\s*\(',
            re.IGNORECASE
        ),
        'dataclass': re.compile(
            r'@dataclass\s*\nclass\s+(\w+):',
            re.MULTILINE
        ),
        'enum': re.compile(
            r'class\s+(\w+)\(Enum\):',
            re.MULTILINE
        )
    }
    
    # 引用模式
    REFERENCE_PATTERNS = {
        'import': re.compile(
            r'from\s+(\w+)\s+import\s+(\w+)'
        ),
        'sql_table': re.compile(
            r'(?:FROM|INTO|UPDATE|TABLE)\s+(\w+)',
            re.IGNORECASE
        )
    }
    
    def __init__(self, scripts_dir: str):
        """
        初始化
        
        Args:
            scripts_dir: 脚本目录路径
        """
        self.scripts_dir = Path(scripts_dir)
        self.definitions: List[SchemaDefinition] = []
        self.references: List[ConsumerReference] = []
        self.file_contents: Dict[str, str] = {}
    
    def scan_all_files(self):
        """扫描所有 Python 文件"""
        print("扫描代码文件...")
        
        for py_file in self.scripts_dir.glob("*.py"):
            content = py_file.read_text(encoding='utf-8')
            self.file_contents[py_file.name] = content
            
            # 识别定义
            self._extract_definitions(py_file.name, content)
            
            # 识别引用
            self._extract_references(py_file.name, content)
        
        print(f"  扫描了 {len(self.file_contents)} 个文件")
        print(f"  发现 {len(self.definitions)} 个结构定义")
        print(f"  发现 {len(self.references)} 个引用关系")
    
    def _extract_definitions(self, file_name: str, content: str):
        """提取结构定义"""
        # SQLite 表定义
        for match in self.DEFINITION_PATTERNS['sqlite_table'].finditer(content):
            table_name = match.group(1)
            self.definitions.append(SchemaDefinition(
                schema_id=table_name,
                definition_file=file_name,
                definition_type='sqlite_table',
                table_name=table_name
            ))
        
        # Dataclass 定义
        for match in self.DEFINITION_PATTERNS['dataclass'].finditer(content):
            class_name = match.group(1)
            self.definitions.append(SchemaDefinition(
                schema_id=class_name,
                definition_file=file_name,
                definition_type='dataclass',
                class_name=class_name
            ))
        
        # Enum 定义
        for match in self.DEFINITION_PATTERNS['enum'].finditer(content):
            class_name = match.group(1)
            self.definitions.append(SchemaDefinition(
                schema_id=class_name,
                definition_file=file_name,
                definition_type='enum',
                class_name=class_name
            ))
    
    def _extract_references(self, file_name: str, content: str):
        """提取引用关系"""
        # 已知的结构 ID
        known_schemas = {
            'entities', 'rules', 'graph_nodes', 'graph_edges',
            'DataType', 'Rule', 'GraphNode', 'GraphEdge',
            'ScanResult', 'ScanCache'
        }
        
        # 从 SQL 查询中提取表引用
        for match in self.REFERENCE_PATTERNS['sql_table'].finditer(content):
            table_name = match.group(1).lower()
            if table_name in known_schemas:
                self.references.append(ConsumerReference(
                    schema_id=table_name,
                    consumer_file=file_name
                ))
        
        # 从导入语句中提取引用
        for match in self.REFERENCE_PATTERNS['import'].finditer(content):
            module = match.group(1)
            class_name = match.group(2)
            if class_name in known_schemas:
                self.references.append(ConsumerReference(
                    schema_id=class_name,
                    consumer_file=file_name
                ))
    
    def build_schemas_json(self) -> Dict:
        """构建 schemas.json 数据结构"""
        schemas = {}
        
        # 按结构 ID 分组定义
        for defn in self.definitions:
            if defn.schema_id not in schemas:
                schemas[defn.schema_id] = {
                    'hash': None,
                    'last_modified': None,
                    'definition': {
                        'file': defn.definition_file,
                        'type': defn.definition_type
                    },
                    'consumers': []
                }
                
                if defn.definition_type == 'sqlite_table':
                    schemas[defn.schema_id]['definition']['table_name'] = defn.table_name
                elif defn.definition_type in ('dataclass', 'enum'):
                    schemas[defn.schema_id]['definition']['class_name'] = defn.class_name
        
        # 添加引用者
        for ref in self.references:
            if ref.schema_id in schemas:
                # 检查定义者不是自己
                if schemas[ref.schema_id]['definition']['file'] != ref.consumer_file:
                    # 检查是否已存在
                    exists = any(
                        c['file'] == ref.consumer_file 
                        for c in schemas[ref.schema_id]['consumers']
                    )
                    if not exists:
                        schemas[ref.schema_id]['consumers'].append({
                            'file': ref.consumer_file,
                            'last_adapted': None
                        })
        
        return {
            '$schema': 'schema-management-system-v1',
            'version': '1.0.0',
            'description': '数据结构定义中心 - 自动生成',
            'schemas': schemas,
            'notification_queue': {
                'records': [],
                'stats': {
                    'total_added': 0,
                    'total_processed': 0,
                    'total_failed': 0,
                    'max_iterations': 10,
                    'current_iteration': 0
                },
                'failed_records': []
            },
            'change_tracking': {
                'current_chain': [],
                'detected_circular': False,
                'circular_files': [],
                'processing_history': []
            },
            'config': {
                'max_depth': 3,
                'safety_factor': 1.5,
                'min_iterations': 5,
                'max_iterations_limit': 100,
                'stale_threshold_hours': 24
            }
        }
    
    def save_schemas_json(self, output_path: str):
        """保存 schemas.json"""
        data = self.build_schemas_json()
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"\n保存到: {output_path}")
    
    def print_summary(self):
        """打印摘要"""
        print("\n" + "=" * 60)
        print("初始化摘要")
        print("=" * 60)
        
        # 按文件分组定义
        by_file: Dict[str, List[str]] = {}
        for defn in self.definitions:
            if defn.definition_file not in by_file:
                by_file[defn.definition_file] = []
            by_file[defn.definition_file].append(defn.schema_id)
        
        print("\n定义者文件:")
        for file_name, schemas in by_file.items():
            print(f"  {file_name}:")
            for schema_id in schemas:
                print(f"    - {schema_id}")
        
        # 按结构分组引用者
        by_schema: Dict[str, Set[str]] = {}
        for ref in self.references:
            if ref.schema_id not in by_schema:
                by_schema[ref.schema_id] = set()
            # 排除定义者自己
            if ref.schema_id in schemas:
                continue
            by_schema[ref.schema_id].add(ref.consumer_file)
        
        print("\n引用关系:")
        for schema_id, consumers in by_schema.items():
            if consumers:
                print(f"  {schema_id}:")
                for consumer in consumers:
                    print(f"    ← {consumer}")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='初始化 schemas.json')
    parser.add_argument(
        '--scripts-dir',
        default=None,
        help='脚本目录路径'
    )
    parser.add_argument(
        '--output',
        default=None,
        help='输出文件路径'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='仅显示结果，不保存'
    )
    
    args = parser.parse_args()
    
    # 确定路径
    if args.scripts_dir:
        scripts_dir = Path(args.scripts_dir)
    else:
        scripts_dir = Path(__file__).parent
    
    if args.output:
        output_path = args.output
    else:
        output_path = scripts_dir.parent / "schemas" / "schemas.json"
    
    # 执行初始化
    initializer = SchemaInitializer(str(scripts_dir))
    initializer.scan_all_files()
    initializer.print_summary()
    
    if not args.dry_run:
        initializer.save_schemas_json(str(output_path))
        print("\n初始化完成！")
    else:
        print("\n[DRY RUN] 未保存文件")


if __name__ == "__main__":
    main()
