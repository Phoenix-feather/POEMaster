#!/usr/bin/env python3
"""
POE增量学习和恢复机制模块
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


@dataclass
class HeuristicRecord:
    """启发记录"""
    id: str
    original_question: str
    core_intent: Dict[str, str]
    discovery: Dict[str, Any]
    confirmation: Dict[str, Any]
    created_version: str
    last_verified_version: str


@dataclass
class PendingConfirmation:
    """待确认项"""
    id: str
    status: str
    created_at: str
    discovery: Dict[str, Any]
    recommendation: Dict[str, Any]
    data_updates: List[Dict[str, Any]]


@dataclass
class UnverifiedItem:
    """未确认项"""
    id: str
    status: str
    priority: str
    created_at: str
    trigger: Dict[str, Any]
    affected_knowledge: Dict[str, Any]
    resolution: Dict[str, Any]


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


class IncrementalLearning:
    """增量学习管理器"""
    
    def __init__(self, knowledge_base_path: str):
        """
        初始化增量学习管理器
        
        Args:
            knowledge_base_path: 知识库目录路径
        """
        self.kb_path = Path(knowledge_base_path)
        
        # 初始化YAML管理器
        self.heuristic_records = YAMLManager(
            str(self.kb_path / 'heuristic_records.yaml')
        )
        self.pending_confirmations = YAMLManager(
            str(self.kb_path / 'pending_confirmations.yaml')
        )
        self.learning_log = YAMLManager(
            str(self.kb_path / 'learning_log.yaml')
        )
    
    def create_heuristic_record(self, question: str, discovery: Dict[str, Any]) -> str:
        """
        创建启发记录
        
        Args:
            question: 原始问题
            discovery: 发现内容
            
        Returns:
            记录ID
        """
        # 生成ID
        records = self.heuristic_records.get('records', [])
        record_id = f"hr_{len(records) + 1:04d}"
        
        # 创建记录
        record = {
            'id': record_id,
            'original_question': question,
            'core_intent': self._extract_core_intent(question),
            'discovery': discovery,
            'confirmation': {
                'confirmed': False,
                'confirmed_at': None
            },
            'created_version': self._get_current_version(),
            'last_verified_version': self._get_current_version()
        }
        
        # 添加记录
        records.append(record)
        self.heuristic_records.set('records', records)
        
        # 更新元数据
        metadata = self.heuristic_records.get('metadata', {})
        metadata['total_records'] = len(records)
        metadata['last_updated'] = datetime.now().isoformat()
        self.heuristic_records.set('metadata', metadata)
        
        self.heuristic_records.save()
        
        return record_id
    
    def create_pending_confirmation(self, discovery: Dict[str, Any]) -> str:
        """
        创建待确认项
        
        Args:
            discovery: 发现内容
            
        Returns:
            项目ID
        """
        items = self.pending_confirmations.get('items', [])
        item_id = f"pc_{len(items) + 1:04d}"
        
        item = {
            'id': item_id,
            'status': 'pending',
            'created_at': datetime.now().isoformat(),
            'discovery': discovery,
            'recommendation': {
                'asked_count': 0,
                'last_asked_at': None
            },
            'data_updates': []
        }
        
        items.append(item)
        self.pending_confirmations.set('items', items)
        
        # 更新元数据
        metadata = self.pending_confirmations.get('metadata', {})
        metadata['total_items'] = len(items)
        self.pending_confirmations.set('metadata', metadata)
        
        self.pending_confirmations.save()
        
        return item_id
    
    def confirm_discovery(self, item_id: str, confirmed: bool) -> bool:
        """
        确认发现
        
        Args:
            item_id: 项目ID
            confirmed: 是否确认有效
            
        Returns:
            是否成功
        """
        items = self.pending_confirmations.get('items', [])
        
        for item in items:
            if item['id'] == item_id:
                item['status'] = 'confirmed' if confirmed else 'rejected'
                
                if confirmed:
                    # 执行数据更新
                    self._apply_data_updates(item.get('data_updates', []))
                
                self.pending_confirmations.save()
                
                # 记录学习事件
                self._log_learning_event(item, confirmed)
                
                return True
        
        return False
    
    def get_pending_items(self) -> List[Dict[str, Any]]:
        """获取所有待确认项"""
        items = self.pending_confirmations.get('items', [])
        return [item for item in items if item['status'] == 'pending']
    
    def increment_asked_count(self, item_id: str):
        """增加询问计数"""
        items = self.pending_confirmations.get('items', [])
        
        for item in items:
            if item['id'] == item_id:
                item['recommendation']['asked_count'] += 1
                item['recommendation']['last_asked_at'] = datetime.now().isoformat()
                self.pending_confirmations.save()
                break
    
    def _extract_core_intent(self, question: str) -> Dict[str, str]:
        """提取核心意图"""
        # 简单实现
        intent = {
            'target': '',
            'action': '',
            'constraint': ''
        }
        
        # 提取关键词
        if '绕过' in question:
            intent['action'] = '绕过'
        elif '计算' in question:
            intent['action'] = '计算'
        
        return intent
    
    def _get_current_version(self) -> str:
        """获取当前版本"""
        version_file = self.kb_path / 'version.yaml'
        if version_file.exists():
            version_manager = YAMLManager(str(version_file))
            return version_manager.get('pob_version', {}).get('game_version', 'unknown')
        return 'unknown'
    
    def _apply_data_updates(self, updates: List[Dict[str, Any]]):
        """
        应用数据更新
        
        Args:
            updates: 更新项列表，每项包含:
                - type: 更新类型 (add_edge, update_rule, add_node)
                - data: 更新数据
        """
        if not updates:
            return
        
        import sqlite3
        
        # 连接图数据库
        graph_db_path = self.kb_path / 'graph.db'
        rules_db_path = self.kb_path / 'rules.db'
        
        for update in updates:
            update_type = update.get('type')
            data = update.get('data', {})
            
            if update_type == 'add_edge':
                # 添加边到图
                try:
                    conn = sqlite3.connect(str(graph_db_path))
                    cursor = conn.cursor()
                    cursor.execute('''
                        INSERT OR IGNORE INTO graph_edges (
                            source_node, target_node, edge_type, weight, attributes,
                            status, source_rule, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        data.get('source'),
                        data.get('target'),
                        data.get('edge_type', 'relates'),
                        data.get('weight', 1.0),
                        json.dumps(data.get('attributes', {}), ensure_ascii=False),
                        'verified',
                        data.get('source_rule'),
                        datetime.now().isoformat()
                    ))
                    conn.commit()
                    conn.close()
                except Exception as e:
                    print(f"[WARN] 添加边失败: {e}")
            
            elif update_type == 'update_rule':
                # 更新规则
                try:
                    conn = sqlite3.connect(str(rules_db_path))
                    cursor = conn.cursor()
                    cursor.execute('''
                        UPDATE rules SET verified_at = ? WHERE id = ?
                    ''', (datetime.now().isoformat(), data.get('rule_id')))
                    conn.commit()
                    conn.close()
                except Exception as e:
                    print(f"[WARN] 更新规则失败: {e}")
            
            elif update_type == 'add_node':
                # 添加节点到图
                try:
                    conn = sqlite3.connect(str(graph_db_path))
                    cursor = conn.cursor()
                    cursor.execute('''
                        INSERT OR IGNORE INTO graph_nodes (id, name, type, attributes, created_at)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (
                        data.get('id'),
                        data.get('name', data.get('id')),
                        data.get('node_type', 'entity'),
                        json.dumps(data.get('attributes', {}), ensure_ascii=False),
                        datetime.now().isoformat()
                    ))
                    conn.commit()
                    conn.close()
                except Exception as e:
                    print(f"[WARN] 添加节点失败: {e}")
    
    def _log_learning_event(self, item: Dict[str, Any], confirmed: bool):
        """记录学习事件"""
        events = self.learning_log.get('events', [])
        
        event = {
            'id': f"le_{len(events) + 1:04d}",
            'timestamp': datetime.now().isoformat(),
            'type': 'confirmation',
            'details': {
                'discovery': item['discovery']
            },
            'user_feedback': {
                'action': 'confirmed' if confirmed else 'rejected',
                'timestamp': datetime.now().isoformat()
            }
        }
        
        events.append(event)
        self.learning_log.set('events', events)
        
        metadata = self.learning_log.get('metadata', {})
        metadata['total_events'] = len(events)
        self.learning_log.set('metadata', metadata)
        
        self.learning_log.save()


class RecoveryMechanism:
    """恢复机制管理器"""
    
    def __init__(self, knowledge_base_path: str):
        """
        初始化恢复机制管理器
        
        Args:
            knowledge_base_path: 知识库目录路径
        """
        self.kb_path = Path(knowledge_base_path)
        
        self.version_manager = YAMLManager(
            str(self.kb_path / 'version.yaml')
        )
        self.unverified_manager = YAMLManager(
            str(self.kb_path / 'unverified_list.yaml')
        )
        self.heuristic_manager = YAMLManager(
            str(self.kb_path / 'heuristic_records.yaml')
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
    
    def add_to_unverified_list(self, item: Dict[str, Any]) -> str:
        """
        添加到未确认列表
        
        Args:
            item: 项目数据
            
        Returns:
            项目ID
        """
        items = self.unverified_manager.get('items', [])
        item_id = f"uv_{len(items) + 1:04d}"
        
        new_item = {
            'id': item_id,
            'status': 'pending',
            'priority': item.get('priority', 'medium'),
            'created_at': datetime.now().isoformat(),
            'trigger': item.get('trigger', {}),
            'affected_knowledge': item.get('affected_knowledge', {}),
            'resolution': {
                'attempts': 0,
                'last_attempt': None,
                'notes': None,
                'result': None
            }
        }
        
        items.append(new_item)
        self.unverified_manager.set('items', items)
        
        metadata = self.unverified_manager.get('metadata', {})
        metadata['total_items'] = len(items)
        self.unverified_manager.set('metadata', metadata)
        
        self.unverified_manager.save()
        
        return item_id
    
    def get_unverified_items(self, status: str = 'pending') -> List[Dict[str, Any]]:
        """获取未确认项"""
        items = self.unverified_manager.get('items', [])
        return [item for item in items if item['status'] == status]
    
    def resolve_unverified_item(self, item_id: str, result: str, notes: str = None):
        """
        解决未确认项
        
        Args:
            item_id: 项目ID
            result: 结果 (confirmed_valid | confirmed_invalid | needs_update)
            notes: 备注
        """
        items = self.unverified_manager.get('items', [])
        
        for item in items:
            if item['id'] == item_id:
                item['status'] = 'resolved'
                item['resolution']['result'] = result
                item['resolution']['notes'] = notes
                item['resolution']['last_attempt'] = datetime.now().isoformat()
                
                # 移动到历史记录
                resolved_history = self.unverified_manager.get('resolved_history', [])
                resolved_history.append(item)
                self.unverified_manager.set('resolved_history', resolved_history)
                
                # 从列表中移除
                items.remove(item)
                
                self.unverified_manager.save()
                break
    
    def rebuild_from_heuristics(self) -> Dict[str, Any]:
        """
        从启发记录重建知识
        
        流程:
        1. 加载所有已确认的启发记录
        2. 验证每条记录是否仍然有效（检查数据源是否存在）
        3. 更新关联图中的边状态
        
        Returns:
            重建结果
        """
        records = self.heuristic_manager.get('records', [])
        
        results = {
            'total_records': len(records),
            'valid': 0,
            'invalid': 0,
            'needs_verification': 0,
            'details': []
        }
        
        import sqlite3
        graph_db_path = self.kb_path / 'graph.db'
        
        for record in records:
            record_id = record.get('id', 'unknown')
            confirmed = record.get('confirmation', {}).get('confirmed', False)
            discovery = record.get('discovery', {})
            
            if not confirmed:
                results['needs_verification'] += 1
                results['details'].append({
                    'id': record_id,
                    'status': 'needs_verification',
                    'reason': '未确认'
                })
                continue
            
            # 验证数据源
            source_entities = discovery.get('source_entities', [])
            target_entities = discovery.get('target_entities', [])
            
            # 检查实体是否存在
            entities_db_path = self.kb_path / 'entities.db'
            try:
                conn = sqlite3.connect(str(entities_db_path))
                cursor = conn.cursor()
                
                all_entities_exist = True
                for entity_id in source_entities + target_entities:
                    cursor.execute('SELECT id FROM entities WHERE id = ?', (entity_id,))
                    if not cursor.fetchone():
                        all_entities_exist = False
                        break
                
                conn.close()
                
                if not all_entities_exist:
                    results['invalid'] += 1
                    results['details'].append({
                        'id': record_id,
                        'status': 'invalid',
                        'reason': '数据源实体不存在'
                    })
                    continue
                
            except Exception as e:
                results['needs_verification'] += 1
                results['details'].append({
                    'id': record_id,
                    'status': 'needs_verification',
                    'reason': f'验证失败: {e}'
                })
                continue
            
            # 更新图中的边状态为 verified
            try:
                conn = sqlite3.connect(str(graph_db_path))
                cursor = conn.cursor()
                
                # 更新边状态
                for source in source_entities:
                    for target in target_entities:
                        cursor.execute('''
                            UPDATE graph_edges 
                            SET status = 'verified', verified_at = ?
                            WHERE source_node = ? AND target_node = ? AND source_rule = ?
                        ''', (datetime.now().isoformat(), source, target, record_id))
                
                conn.commit()
                conn.close()
                
                results['valid'] += 1
                results['details'].append({
                    'id': record_id,
                    'status': 'valid',
                    'reason': '验证成功'
                })
                
            except Exception as e:
                results['needs_verification'] += 1
                results['details'].append({
                    'id': record_id,
                    'status': 'needs_verification',
                    'reason': f'更新图失败: {e}'
                })
        
        return results
    
    def detect_mechanism_changes(self, old_entities: List[Dict], new_entities: List[Dict]) -> List[Dict[str, Any]]:
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
        
        return changes


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='POE增量学习和恢复机制')
    parser.add_argument('kb_path', help='知识库目录路径')
    parser.add_argument('--check-version', help='检查版本变化')
    parser.add_argument('--update-version', help='更新版本')
    parser.add_argument('--pending', action='store_true', help='显示待确认项')
    parser.add_argument('--unverified', action='store_true', help='显示未确认列表')
    parser.add_argument('--rebuild', action='store_true', help='从启发记录重建')
    
    args = parser.parse_args()
    
    learning = IncrementalLearning(args.kb_path)
    recovery = RecoveryMechanism(args.kb_path)
    
    if args.check_version:
        changed = recovery.check_version_change(args.check_version)
        print(f"版本变化: {'是' if changed else '否'}")
    
    if args.update_version:
        recovery.update_version(args.update_version)
        print(f"版本已更新为: {args.update_version}")
    
    if args.pending:
        items = learning.get_pending_items()
        for item in items:
            print(f"- [{item['id']}] {item['discovery'].get('question', '')}")
    
    if args.unverified:
        items = recovery.get_unverified_items()
        for item in items:
            print(f"- [{item['id']}] {item['trigger'].get('change_description', '')}")
    
    if args.rebuild:
        results = recovery.rebuild_from_heuristics()
        print(f"重建结果: {results}")


if __name__ == '__main__':
    main()
