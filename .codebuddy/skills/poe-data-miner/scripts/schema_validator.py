#!/usr/bin/env python3
"""
Schema 验证器 - 完整版
- 队列处理流程
- 循环处理
- 迭代控制
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Callable
from dataclasses import dataclass
from datetime import datetime

try:
    from schema_manager import SchemaManager, QueueRecord
except ImportError:
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from schema_manager import SchemaManager, QueueRecord


@dataclass
class ProcessResult:
    """处理结果"""
    success: bool
    message: str
    processed_files: List[str]
    remaining_queue: int
    iterations: int


class SchemaValidator:
    """Schema 验证器"""
    
    def __init__(self, schemas_path: str, scripts_dir: str = None):
        """
        初始化验证器
        
        Args:
            schemas_path: schemas.json 路径
            scripts_dir: 脚本目录路径
        """
        self.manager = SchemaManager(schemas_path)
        self.scripts_dir = Path(scripts_dir) if scripts_dir else Path(__file__).parent
        self.current_iteration = 0
        self.processed_files = set()
    
    # ========== 修改流程入口 ==========
    
    def before_file_modify(self, file_name: str) -> Dict[str, Any]:
        """
        文件修改前的检查和准备
        
        Args:
            file_name: 即将修改的文件名
        
        Returns:
            {
                'role': {'definitions': [...], 'consumptions': [...]},
                'warnings': [...],
                'pending_schemas': [...]  # 需要适配的结构
            }
        """
        role = self.manager.get_file_role(file_name)
        warnings = []
        pending_schemas = []
        
        # 如果是引用者，检查是否有待处理的结构变化
        for schema_id in role['consumptions']:
            schema = self.manager.get_schema(schema_id)
            if schema:
                # 检查是否在队列中
                for record in self.manager.queue:
                    if record.schema == schema_id and record.consumer == file_name:
                        pending_schemas.append(schema_id)
                        warnings.append(
                            f"结构 {schema_id} 已变化，请适配最新结构"
                        )
        
        return {
            'role': role,
            'warnings': warnings,
            'pending_schemas': pending_schemas
        }
    
    def after_file_modify(self, file_name: str, is_definition_changed: bool = False):
        """
        文件修改后的更新
        
        Args:
            file_name: 已修改的文件名
            is_definition_changed: 是否修改了结构定义
        """
        role = self.manager.get_file_role(file_name)
        
        # 移除队列中针对该文件的记录（因为是引用者）
        self.manager.remove_from_queue(file_name)
        
        # 如果是定义者且修改了结构，更新 schema 并通知消费者
        if is_definition_changed:
            for schema_id in role['definitions']:
                self.manager.update_schema(schema_id)
        
        # 更新引用者的适配时间
        for schema_id in role['consumptions']:
            self.manager.update_consumer_adapted(schema_id, file_name)
        
        # 保存
        self.manager.save()
    
    # ========== 队列处理流程 ==========
    
    def process_queue(
        self,
        modify_callback: Callable[[str, List[str]], bool] = None,
        planned_files: int = 1
    ) -> ProcessResult:
        """
        处理队列
        
        Args:
            modify_callback: 修改文件的回调函数 (file_name, pending_schemas) -> success
            planned_files: 计划修改的文件数量（用于计算迭代上限）
        
        Returns:
            处理结果
        """
        max_iterations = self.manager.calculate_max_iterations(planned_files)
        self.current_iteration = 0
        self.processed_files = set()
        
        while not self.manager.is_queue_empty() and self.current_iteration < max_iterations:
            self.current_iteration += 1
            
            # 检测循环
            is_circular, circular_files = self.manager.detect_circular()
            
            if is_circular:
                # 循环处理
                result = self._handle_circular(circular_files, modify_callback)
                if not result:
                    break
            else:
                # 正常处理
                result = self._process_queue_round(modify_callback)
                if not result:
                    break
        
        # 保存最终状态
        self.manager.save()
        
        return ProcessResult(
            success=self.manager.is_queue_empty(),
            message="队列为空，迭代完成" if self.manager.is_queue_empty() 
                    else f"达到最大迭代次数 {max_iterations}",
            processed_files=list(self.processed_files),
            remaining_queue=len(self.manager.queue),
            iterations=self.current_iteration
        )
    
    def _process_queue_round(self, modify_callback: Callable) -> bool:
        """处理一轮队列"""
        # 获取当前队列的所有记录
        records = list(self.manager.queue)
        
        if not records:
            return True
        
        for record in records:
            if record.status != "pending":
                continue
            
            # 调用回调处理
            if modify_callback:
                try:
                    success = modify_callback(
                        record.consumer,
                        [record.schema]
                    )
                    
                    if success:
                        # 移除记录
                        self.manager.remove_from_queue(record.consumer)
                        self.processed_files.add(record.consumer)
                        
                        # 更新适配时间
                        self.manager.update_consumer_adapted(
                            record.schema,
                            record.consumer
                        )
                    else:
                        # 标记失败
                        record.status = "failed"
                        record.retry_count += 1
                except Exception as e:
                    record.status = "failed"
                    record.retry_count += 1
            else:
                # 没有回调，直接标记处理
                self.manager.remove_from_queue(record.consumer)
                self.processed_files.add(record.consumer)
        
        return True
    
    def _handle_circular(self, circular_files: List[str], modify_callback: Callable) -> bool:
        """处理循环引用"""
        # 预更新阶段：收集所有需要的结构变更
        # （这里简化处理，实际应该分析具体变更）
        
        # 执行阶段：依次修改循环文件
        for file_name in circular_files:
            # 获取该文件需要适配的结构
            role = self.manager.get_file_role(file_name)
            pending_schemas = role['consumptions']
            
            if modify_callback:
                try:
                    modify_callback(file_name, pending_schemas)
                except Exception:
                    pass
            
            # 移除队列记录
            self.manager.remove_from_queue(file_name)
            self.processed_files.add(file_name)
            
            # 更新适配时间
            for schema_id in pending_schemas:
                self.manager.update_consumer_adapted(schema_id, file_name)
        
        return True
    
    # ========== 验证和报告 ==========
    
    def validate_structure_consistency(self, schema_id: str) -> Dict[str, Any]:
        """
        验证结构一致性
        
        检查定义者代码中的结构与 schemas.json 中记录的是否一致
        """
        schema = self.manager.get_schema(schema_id)
        if not schema:
            return {'valid': False, 'error': f"Schema {schema_id} not found"}
        
        # 从定义文件提取结构（简化实现）
        actual_hash = self.manager.compute_hash(schema_id)
        recorded_hash = schema.hash
        
        return {
            'valid': actual_hash == recorded_hash,
            'actual_hash': actual_hash,
            'recorded_hash': recorded_hash,
            'schema_id': schema_id
        }
    
    def check_stale_records(self, hours: int = 24) -> List[QueueRecord]:
        """检查过期的队列记录"""
        from datetime import timedelta
        
        stale_records = []
        threshold = datetime.now() - timedelta(hours=hours)
        
        for record in self.manager.queue:
            created_at = datetime.fromisoformat(record.created_at)
            if created_at < threshold:
                stale_records.append(record)
        
        return stale_records
    
    def generate_report(self) -> str:
        """生成完整报告"""
        lines = [
            "=" * 60,
            "Schema 验证报告",
            f"生成时间: {datetime.now().isoformat()}",
            "=" * 60,
            ""
        ]
        
        # 队列状态
        lines.append("一、队列状态")
        lines.append("-" * 40)
        lines.append(f"  待处理记录: {len(self.manager.queue)}")
        lines.append(f"  当前迭代: {self.current_iteration}")
        
        if self.manager.queue:
            lines.append("\n  待处理消费者:")
            for record in self.manager.queue:
                lines.append(f"    - {record.consumer} (schema: {record.schema})")
        
        # 循环检测
        lines.append("\n\n二、循环检测")
        lines.append("-" * 40)
        is_circular, circular_files = self.manager.detect_circular()
        if is_circular:
            lines.append("  [警告] 检测到循环引用")
            for f in circular_files:
                lines.append(f"    - {f}")
        else:
            lines.append("  无循环引用")
        
        # 过期记录
        stale_records = self.check_stale_records()
        if stale_records:
            lines.append("\n\n三、过期记录")
            lines.append("-" * 40)
            for record in stale_records:
                lines.append(f"  - {record.consumer} (创建于 {record.created_at})")
        
        # 已处理文件
        if self.processed_files:
            lines.append("\n\n四、本轮处理文件")
            lines.append("-" * 40)
            for f in sorted(self.processed_files):
                lines.append(f"  - {f}")
        
        return "\n".join(lines)


# ========== 便捷函数 ==========

def validate_before_init(schemas_path: str = None, scripts_dir: str = None) -> bool:
    """
    初始化前验证（供 init_knowledge_base.py 调用）
    """
    if schemas_path is None:
        schemas_path = Path(__file__).parent.parent / "schemas" / "schemas.json"
    
    if not Path(schemas_path).exists():
        print("[WARN] schemas.json not found, skipping validation")
        return True
    
    validator = SchemaValidator(str(schemas_path), scripts_dir)
    
    # 检查过期记录
    stale_records = validator.check_stale_records()
    if stale_records:
        print(f"[WARN] Found {len(stale_records)} stale queue records")
        for record in stale_records:
            print(f"  - {record.consumer}")
    
    # 检查循环
    is_circular, circular_files = validator.manager.detect_circular()
    if is_circular:
        print(f"[WARN] Detected circular references: {circular_files}")
    
    print(validator.generate_report())
    
    return not is_circular


def main():
    """主函数"""
    import sys
    
    schemas_path = Path(__file__).parent.parent / "schemas" / "schemas.json"
    
    if not schemas_path.exists():
        print(f"[ERROR] schemas.json not found: {schemas_path}")
        sys.exit(1)
    
    validator = SchemaValidator(str(schemas_path))
    
    print(validator.generate_report())
    
    # 测试队列处理
    print("\n\n测试队列处理:")
    
    # 模拟添加一些记录
    validator.manager.add_to_queue("entities", "rules_extractor.py")
    validator.manager.add_to_queue("rules", "attribute_graph.py")
    validator.manager.save()
    
    print(f"队列记录数: {len(validator.manager.queue)}")
    
    # 测试修改前检查
    print("\n修改前检查 (rules_extractor.py):")
    result = validator.before_file_modify("rules_extractor.py")
    print(f"  角色: {result['role']}")
    print(f"  警告: {result['warnings']}")
    print(f"  待处理结构: {result['pending_schemas']}")
    
    # 测试修改后更新
    print("\n修改后更新 (rules_extractor.py):")
    validator.after_file_modify("rules_extractor.py", is_definition_changed=True)
    print(f"  队列记录数: {len(validator.manager.queue)}")


if __name__ == "__main__":
    main()
