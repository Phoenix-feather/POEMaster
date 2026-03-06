#!/usr/bin/env python3
"""
Schema 管理工具 - 完整版
- 集中存储管理
- 队列机制
- 循环检测
- 迭代次数动态计算
"""

import hashlib
import json
import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Set, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime
import copy


@dataclass
class QueueRecord:
    """队列记录"""
    id: str
    schema: str
    consumer: str
    reason: str
    created_at: str
    status: str = "pending"
    retry_count: int = 0


@dataclass
class SchemaInfo:
    """结构信息"""
    hash: Optional[str] = None
    last_modified: Optional[str] = None
    definition: Dict = field(default_factory=dict)
    consumers: List[Dict] = field(default_factory=list)


class SchemaManager:
    """Schema 管理器"""
    
    def __init__(self, schemas_path: str):
        """
        初始化 Schema 管理器
        
        Args:
            schemas_path: schemas.json 文件路径
        """
        self.schemas_path = Path(schemas_path)
        self.data: Dict = {}
        self.schemas: Dict[str, SchemaInfo] = {}
        self.queue: List[QueueRecord] = []
        self.change_tracking: Dict = {}
        self.config: Dict = {}
        
        self._load()
    
    def _load(self):
        """加载 schemas.json"""
        if not self.schemas_path.exists():
            self._init_empty()
            return
        
        with open(self.schemas_path, 'r', encoding='utf-8') as f:
            self.data = json.load(f)
        
        # 解析 schemas
        for schema_id, schema_data in self.data.get('schemas', {}).items():
            self.schemas[schema_id] = SchemaInfo(
                hash=schema_data.get('hash'),
                last_modified=schema_data.get('last_modified'),
                definition=schema_data.get('definition', {}),
                consumers=schema_data.get('consumers', [])
            )
        
        # 解析队列
        for record_data in self.data.get('notification_queue', {}).get('records', []):
            self.queue.append(QueueRecord(**record_data))
        
        # 解析追踪和配置
        self.change_tracking = self.data.get('change_tracking', {})
        self.config = self.data.get('config', {
            'max_depth': 3,
            'safety_factor': 1.5,
            'min_iterations': 5,
            'max_iterations_limit': 100
        })
    
    def _init_empty(self):
        """初始化空数据"""
        self.data = {
            'schemas': {},
            'notification_queue': {'records': [], 'stats': {}},
            'change_tracking': {'current_chain': [], 'detected_circular': False},
            'config': {
                'max_depth': 3,
                'safety_factor': 1.5,
                'min_iterations': 5,
                'max_iterations_limit': 100
            }
        }
        self.schemas = {}
        self.queue = []
        self.change_tracking = self.data['change_tracking']
        self.config = self.data['config']
    
    def save(self):
        """保存到文件"""
        # 构建数据结构
        self.data['schemas'] = {
            schema_id: {
                'hash': info.hash,
                'last_modified': info.last_modified,
                'definition': info.definition,
                'consumers': info.consumers
            }
            for schema_id, info in self.schemas.items()
        }
        
        self.data['notification_queue']['records'] = [
            asdict(record) for record in self.queue
        ]
        self.data['change_tracking'] = self.change_tracking
        
        # 写入文件
        with open(self.schemas_path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)
    
    # ========== 文件角色查询 ==========
    
    def get_file_role(self, file_name: str) -> Dict[str, List[str]]:
        """
        获取文件的角色
        
        Returns:
            {
                'definitions': ['schema1', 'schema2'],  # 作为定义者
                'consumptions': ['schema3', 'schema4']  # 作为引用者
            }
        """
        definitions = []
        consumptions = []
        
        for schema_id, info in self.schemas.items():
            # 检查是否是定义者
            if info.definition.get('file') == file_name:
                definitions.append(schema_id)
            
            # 检查是否是引用者
            for consumer in info.consumers:
                if consumer.get('file') == file_name:
                    consumptions.append(schema_id)
        
        return {'definitions': definitions, 'consumptions': consumptions}
    
    def is_definition_file(self, file_name: str) -> bool:
        """检查文件是否是定义者"""
        for info in self.schemas.values():
            if info.definition.get('file') == file_name:
                return True
        return False
    
    def is_consumer_file(self, file_name: str) -> bool:
        """检查文件是否是引用者"""
        for info in self.schemas.values():
            for consumer in info.consumers:
                if consumer.get('file') == file_name:
                    return True
        return False
    
    def get_schema(self, schema_id: str) -> Optional[SchemaInfo]:
        """获取结构信息"""
        return self.schemas.get(schema_id)
    
    # ========== 哈希计算 ==========
    
    def compute_hash(self, schema_id: str, structure: Dict = None) -> str:
        """
        计算结构哈希
        
        Args:
            schema_id: 结构 ID
            structure: 结构定义（可选，用于计算新哈希）
        """
        if structure is None:
            # 从定义文件提取结构
            structure = self._extract_structure_from_code(schema_id)
        
        if not structure:
            return None
        
        # 规范化结构定义
        canonical = {
            'fields': sorted(structure.keys()) if isinstance(structure, dict) else []
        }
        
        canonical_str = json.dumps(canonical, sort_keys=True)
        hash_value = hashlib.sha256(canonical_str.encode()).hexdigest()[:8]
        
        return hash_value
    
    def _extract_structure_from_code(self, schema_id: str) -> Dict:
        """从代码中提取结构定义"""
        info = self.schemas.get(schema_id)
        if not info or not info.definition:
            return {}
        
        # 简化实现：返回空字典，实际应该解析代码
        return {}
    
    # ========== 队列操作 ==========
    
    def add_to_queue(self, schema_id: str, consumer_file: str, reason: str = "structure_changed"):
        """添加记录到队列"""
        # 检查是否已存在
        for record in self.queue:
            if record.schema == schema_id and record.consumer == consumer_file:
                # 已存在，不重复添加
                return
        
        # 创建新记录
        record = QueueRecord(
            id=f"rec_{len(self.queue) + 1:04d}",
            schema=schema_id,
            consumer=consumer_file,
            reason=reason,
            created_at=datetime.now().isoformat()
        )
        self.queue.append(record)
        
        # 更新统计
        self.data.setdefault('notification_queue', {}).setdefault('stats', {})
        self.data['notification_queue']['stats']['total_added'] = \
            self.data['notification_queue']['stats'].get('total_added', 0) + 1
    
    def remove_from_queue(self, consumer_file: str):
        """从队列中移除消费者相关的记录"""
        self.queue = [
            record for record in self.queue
            if record.consumer != consumer_file
        ]
    
    def get_pending_consumers(self, schema_id: str = None) -> List[str]:
        """获取待处理的消费者列表"""
        if schema_id:
            return list(set(
                record.consumer for record in self.queue
                if record.schema == schema_id
            ))
        return list(set(record.consumer for record in self.queue))
    
    def is_queue_empty(self) -> bool:
        """队列是否为空"""
        return len(self.queue) == 0
    
    # ========== 更新操作 ==========
    
    def update_schema(self, schema_id: str, structure: Dict = None):
        """
        更新结构定义（定义者修改后调用）
        """
        info = self.schemas.get(schema_id)
        if not info:
            return
        
        # 计算新哈希
        new_hash = self.compute_hash(schema_id, structure)
        
        if new_hash and new_hash != info.hash:
            # 结构变化了
            info.hash = new_hash
            info.last_modified = datetime.now().isoformat()
            
            # 添加消费者到队列
            for consumer in info.consumers:
                self.add_to_queue(schema_id, consumer['file'])
    
    def update_consumer_adapted(self, schema_id: str, consumer_file: str):
        """
        更新引用者适配时间（引用者修改后调用）
        """
        info = self.schemas.get(schema_id)
        if not info:
            return
        
        for consumer in info.consumers:
            if consumer.get('file') == consumer_file:
                consumer['last_adapted'] = datetime.now().isoformat()
                break
    
    # ========== 循环检测 ==========
    
    def detect_circular(self) -> Tuple[bool, List[str]]:
        """
        检测是否存在循环引用
        
        Returns:
            (是否循环, 循环涉及的文件列表)
        """
        # 构建引用图
        graph = self._build_reference_graph()
        
        # 检测环
        visited = set()
        rec_stack = set()
        circular_files = set()
        
        def dfs(node, path):
            visited.add(node)
            rec_stack.add(node)
            
            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    if dfs(neighbor, path + [node]):
                        return True
                elif neighbor in rec_stack:
                    # 发现环
                    circular_files.update(path)
                    circular_files.add(node)
                    return True
            
            rec_stack.remove(node)
            return False
        
        for node in graph:
            if node not in visited:
                dfs(node, [])
        
        is_circular = len(circular_files) > 0
        self.change_tracking['detected_circular'] = is_circular
        self.change_tracking['circular_files'] = list(circular_files)
        
        return is_circular, list(circular_files)
    
    def _build_reference_graph(self) -> Dict[str, Set[str]]:
        """构建引用图"""
        graph = {}
        
        for schema_id, info in self.schemas.items():
            def_file = info.definition.get('file')
            if def_file:
                if def_file not in graph:
                    graph[def_file] = set()
                
                # 定义者文件 → 引用者文件
                for consumer in info.consumers:
                    consumer_file = consumer.get('file')
                    if consumer_file:
                        graph[def_file].add(consumer_file)
        
        return graph
    
    # ========== 迭代次数计算 ==========
    
    def calculate_max_iterations(self, planned_files: int) -> int:
        """
        动态计算最大迭代次数
        
        Args:
            planned_files: 计划修改的文件数量
        """
        max_depth = self.config.get('max_depth', 3)
        safety_factor = self.config.get('safety_factor', 1.5)
        min_iterations = self.config.get('min_iterations', 5)
        max_limit = self.config.get('max_iterations_limit', 100)
        
        # 计算
        max_iter = int(planned_files * max_depth * safety_factor)
        max_iter = max(min_iterations, min(max_iter, max_limit))
        
        # 更新配置
        self.data.setdefault('notification_queue', {}).setdefault('stats', {})
        self.data['notification_queue']['stats']['max_iterations'] = max_iter
        
        return max_iter
    
    # ========== 报告生成 ==========
    
    def generate_report(self) -> str:
        """生成状态报告"""
        lines = [
            "=" * 60,
            "Schema 管理报告",
            f"生成时间: {datetime.now().isoformat()}",
            "=" * 60,
            ""
        ]
        
        # 结构摘要
        lines.append("一、结构摘要")
        lines.append("-" * 40)
        for schema_id, info in self.schemas.items():
            lines.append(f"  [{schema_id}]")
            lines.append(f"    定义者: {info.definition.get('file', 'N/A')}")
            lines.append(f"    哈希: {info.hash or 'N/A'}")
            lines.append(f"    引用者: {len(info.consumers)} 个")
        
        # 队列状态
        lines.append("\n\n二、队列状态")
        lines.append("-" * 40)
        if self.queue:
            for record in self.queue:
                lines.append(f"  [{record.status}] {record.consumer} ← {record.schema}")
        else:
            lines.append("  队列为空")
        
        # 循环检测
        lines.append("\n\n三、循环检测")
        lines.append("-" * 40)
        is_circular, circular_files = self.detect_circular()
        if is_circular:
            lines.append(f"  [警告] 检测到循环引用")
            lines.append(f"  涉及文件: {', '.join(circular_files)}")
        else:
            lines.append("  无循环引用")
        
        return "\n".join(lines)


def main():
    """主函数"""
    import sys
    
    schemas_path = Path(__file__).parent.parent / "schemas" / "schemas.json"
    
    if not schemas_path.exists():
        print(f"[ERROR] schemas.json not found: {schemas_path}")
        sys.exit(1)
    
    manager = SchemaManager(str(schemas_path))
    
    # 测试文件角色查询
    print("文件角色测试:")
    for file_name in ['entity_index.py', 'rules_extractor.py', 'attribute_graph.py']:
        role = manager.get_file_role(file_name)
        print(f"  {file_name}:")
        print(f"    定义: {role['definitions']}")
        print(f"    引用: {role['consumptions']}")
    
    print("\n" + manager.generate_report())


if __name__ == "__main__":
    main()
