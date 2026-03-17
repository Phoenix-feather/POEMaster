#!/usr/bin/env python3
"""
POE知识库版本管理模块

功能:
- 版本检测和更新
- 机制变化检测
- YAML文件管理工具

注意: 原有的 heuristic 系统已在 GraphBuilder v2 中被异常发现机制替代。
异常发现现由 attribute_graph.py 的 step9/step10 处理。
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import dataclass, asdict

# 尝试导入yaml
try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


class YAMLManager:
    """YAML文件管理器"""
    
    def __init__(self, file_path: str):
        self.file_path = Path(file_path)
        self.data: Dict[str, Any] = {}
        self._load()
    
    def _load(self):
        """加载文件"""
        if self.file_path.exists():
            with open(self.file_path, 'r', encoding='utf-8') as f:
                if HAS_YAML:
                    self.data = yaml.safe_load(f) or {}
                else:
                    # 简单解析
                    self.data = self._parse_simple_yaml(f.read())
        else:
            self.data = {}
    
    def _parse_simple_yaml(self, content: str) -> Dict:
        """简单YAML解析"""
        result = {}
        # 基本的键值对解析
        lines = content.split('\n')
        for line in lines:
            if ':' in line and not line.strip().startswith('#'):
                key, _, value = line.partition(':')
                key = key.strip()
                value = value.strip()
                if value and not value.startswith('[') and not value.startswith('{'):
                    result[key] = value.strip('"\'')
        return result
    
    def save(self):
        """保存文件"""
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(self.file_path, 'w', encoding='utf-8') as f:
            if HAS_YAML:
                yaml.dump(self.data, f, allow_unicode=True, default_flow_style=False)
            else:
                f.write(self._dict_to_yaml(self.data))
    
    def _dict_to_yaml(self, data: Dict, indent: int = 0) -> str:
        """字典转YAML字符串"""
        lines = []
        prefix = '  ' * indent
        
        for key, value in data.items():
            if isinstance(value, dict):
                lines.append(f"{prefix}{key}:")
                lines.append(self._dict_to_yaml(value, indent + 1))
            elif isinstance(value, list):
                lines.append(f"{prefix}{key}:")
                for item in value:
                    if isinstance(item, dict):
                        lines.append(f"{prefix}- ")
                        lines.append(self._dict_to_yaml(item, indent + 1))
                    else:
                        lines.append(f"{prefix}- {item}")
            else:
                lines.append(f"{prefix}{key}: {value}")
        
        return '\n'.join(lines)
    
    def get(self, key: str, default=None):
        return self.data.get(key, default)
    
    def set(self, key: str, value: Any):
        self.data[key] = value


class VersionManager:
    """版本管理器
    
    管理知识库的版本信息，检测POB数据变化。
    """
    
    def __init__(self, knowledge_base_path: str):
        """
        初始化版本管理器
        
        Args:
            knowledge_base_path: 知识库目录路径
        """
        self.kb_path = Path(knowledge_base_path)
        self.version_manager = YAMLManager(
            str(self.kb_path / 'version.yaml')
        )
    
    def check_version_change(self, current_version: str) -> bool:
        """
        检查版本是否变化
        
        Args:
            current_version: 当前版本号
            
        Returns:
            是否发生变化
        """
        stored_version = self.version_manager.get('pob_version', {}).get('game_version')
        return stored_version != current_version
    
    def get_current_version(self) -> str:
        """获取当前存储的版本"""
        return self.version_manager.get('pob_version', {}).get('game_version', 'unknown')
    
    def update_version(self, new_version: str, data_hash: str = None):
        """
        更新版本信息
        
        Args:
            new_version: 新版本号
            data_hash: 数据哈希
        """
        # 保存历史版本
        history = self.version_manager.get('version_history', [])
        old_version = self.version_manager.get('pob_version', {}).get('game_version')
        
        if old_version:
            history.append({
                'version': old_version,
                'initialized_at': self.version_manager.get('metadata', {}).get('last_initialized')
            })
            self.version_manager.set('version_history', history)
        
        # 更新当前版本
        self.version_manager.set('pob_version', {
            'game_version': new_version,
            'pob_version': new_version,
            'data_hash': data_hash,
            'detection': {
                'method': 'manual',
                'detected_at': datetime.now().isoformat()
            }
        })
        
        metadata = self.version_manager.get('metadata', {})
        metadata['last_initialized'] = datetime.now().isoformat()
        self.version_manager.set('metadata', metadata)
        
        self.version_manager.save()
    
    def get_version_history(self) -> List[Dict[str, Any]]:
        """获取版本历史"""
        return self.version_manager.get('version_history', [])


class MechanismChangeDetector:
    """机制变化检测器
    
    检测POB数据更新导致的机制变化。
    """
    
    def __init__(self, knowledge_base_path: str):
        self.kb_path = Path(knowledge_base_path)
    
    def detect_changes(self, old_entities: List[Dict], new_entities: List[Dict]) -> List[Dict[str, Any]]:
        """
        检测机制变化
        
        Args:
            old_entities: 旧实体数据
            new_entities: 新实体数据
            
        Returns:
            变化列表
        """
        changes = []
        
        old_index = {e['id']: e for e in old_entities}
        new_index = {e['id']: e for e in new_entities}
        
        # 检测数值变化
        for entity_id, new_entity in new_index.items():
            old_entity = old_index.get(entity_id)
            
            if old_entity:
                # 检查skillTypes变化
                old_types = set(old_entity.get('skill_types', []))
                new_types = set(new_entity.get('skill_types', []))
                
                if old_types != new_types:
                    changes.append({
                        'type': 'skill_types_change',
                        'entity_id': entity_id,
                        'old_value': list(old_types),
                        'new_value': list(new_types)
                    })
                
                # 检查constant_stats变化
                old_stats = {s[0]: s[1] for s in old_entity.get('constant_stats', []) if isinstance(s, (list, tuple))}
                new_stats = {s[0]: s[1] for s in new_entity.get('constant_stats', []) if isinstance(s, (list, tuple))}
                
                for stat_name, new_value in new_stats.items():
                    old_value = old_stats.get(stat_name)
                    if old_value != new_value:
                        changes.append({
                            'type': 'stat_value_change',
                            'entity_id': entity_id,
                            'stat_name': stat_name,
                            'old_value': old_value,
                            'new_value': new_value,
                            'is_mechanism_change': False  # 数值变化
                        })
        
        # 检测新增实体
        for entity_id in new_index:
            if entity_id not in old_index:
                changes.append({
                    'type': 'entity_added',
                    'entity_id': entity_id,
                    'entity_name': new_index[entity_id].get('name', entity_id)
                })
        
        # 检测删除实体
        for entity_id in old_index:
            if entity_id not in new_index:
                changes.append({
                    'type': 'entity_removed',
                    'entity_id': entity_id,
                    'entity_name': old_index[entity_id].get('name', entity_id)
                })
        
        return changes
    
    def categorize_changes(self, changes: List[Dict[str, Any]]) -> Dict[str, List[Dict]]:
        """
        分类变化
        
        Returns:
            按类型分类的变化字典
        """
        categorized = {
            'skill_types_change': [],
            'stat_value_change': [],
            'entity_added': [],
            'entity_removed': []
        }
        
        for change in changes:
            change_type = change.get('type', 'unknown')
            if change_type in categorized:
                categorized[change_type].append(change)
        
        return categorized


# ============================================================
# 兼容别名 - 保持旧代码可用（但标记为废弃）
# ============================================================

class IncrementalLearning:
    """[已废弃] 增量学习管理器
    
    此类已废弃。原有的 heuristic 功能已被 GraphBuilder v2 的
    异常发现机制（step9/step10）替代。
    
    保留此类仅为向后兼容，新代码请勿使用。
    """
    
    def __init__(self, knowledge_base_path: str):
        import warnings
        warnings.warn(
            "IncrementalLearning 已废弃。异常发现功能已迁移到 "
            "attribute_graph.GraphBuilder.step10_discover_anomalies()",
            DeprecationWarning,
            stacklevel=2
        )
        self.kb_path = Path(knowledge_base_path)
    
    def create_heuristic_record(self, question: str, discovery: Dict[str, Any]) -> str:
        """[已废弃] 创建启发记录"""
        raise NotImplementedError(
            "此方法已废弃。请使用 GraphBuilder.step10_discover_anomalies() "
            "自动发现异常，或通过 predefined_edges.yaml 手动添加已知异常。"
        )
    
    def create_pending_confirmation(self, discovery: Dict[str, Any]) -> str:
        """[已废弃] 创建待确认项"""
        raise NotImplementedError("此方法已废弃。")
    
    def get_pending_items(self) -> List[Dict[str, Any]]:
        """[已废弃] 获取待确认项"""
        return []


class RecoveryMechanism:
    """[已废弃] 恢复机制管理器
    
    版本管理功能已迁移到 VersionManager。
    启发重建功能已被 GraphBuilder v2 替代。
    """
    
    def __init__(self, knowledge_base_path: str):
        import warnings
        warnings.warn(
            "RecoveryMechanism 已废弃。请使用 VersionManager 进行版本管理，"
            "使用 MechanismChangeDetector 进行变化检测。",
            DeprecationWarning,
            stacklevel=2
        )
        self._version_manager = VersionManager(knowledge_base_path)
        self._change_detector = MechanismChangeDetector(knowledge_base_path)
    
    def check_version_change(self, current_version: str) -> bool:
        """检查版本变化（委托给 VersionManager）"""
        return self._version_manager.check_version_change(current_version)
    
    def update_version(self, new_version: str, data_hash: str = None):
        """更新版本（委托给 VersionManager）"""
        self._version_manager.update_version(new_version, data_hash)
    
    def add_to_unverified_list(self, item: Dict[str, Any]) -> str:
        """[已废弃] 添加到未确认列表"""
        raise NotImplementedError("此方法已废弃。")
    
    def get_unverified_items(self, status: str = 'pending') -> List[Dict[str, Any]]:
        """[已废弃] 获取未确认项"""
        return []
    
    def rebuild_from_heuristics(self) -> Dict[str, Any]:
        """[已废弃] 从启发记录重建"""
        raise NotImplementedError(
            "此方法已废弃。图重建请使用 GraphBuilder.build()，"
            "异常会从 predefined_edges.yaml 自动恢复。"
        )
    
    def detect_mechanism_changes(self, old_entities: List[Dict], new_entities: List[Dict]) -> List[Dict[str, Any]]:
        """检测机制变化（委托给 MechanismChangeDetector）"""
        return self._change_detector.detect_changes(old_entities, new_entities)


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='POE知识库版本管理')
    parser.add_argument('kb_path', help='知识库目录路径')
    parser.add_argument('--check-version', help='检查版本变化')
    parser.add_argument('--update-version', help='更新版本')
    parser.add_argument('--show-history', action='store_true', help='显示版本历史')
    
    args = parser.parse_args()
    
    version_mgr = VersionManager(args.kb_path)
    
    if args.check_version:
        changed = version_mgr.check_version_change(args.check_version)
        current = version_mgr.get_current_version()
        print(f"当前版本: {current}")
        print(f"检查版本: {args.check_version}")
        print(f"版本变化: {'是' if changed else '否'}")
    
    if args.update_version:
        version_mgr.update_version(args.update_version)
        print(f"版本已更新为: {args.update_version}")
    
    if args.show_history:
        history = version_mgr.get_version_history()
        if history:
            print("版本历史:")
            for h in history:
                print(f"  - {h.get('version', 'unknown')} @ {h.get('initialized_at', 'unknown')}")
        else:
            print("无版本历史记录")


if __name__ == '__main__':
    main()
