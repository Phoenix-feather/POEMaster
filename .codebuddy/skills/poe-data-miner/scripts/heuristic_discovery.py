#!/usr/bin/env python3
"""
启发式发现能力模块
提供从零开始发现新关系的能力
"""

import sqlite3
import json
from typing import Dict, List, Any, Optional, Set, Tuple
from pathlib import Path
from datetime import datetime
from collections import Counter

# 导入关联图模块
try:
    from attribute_graph import AttributeGraph, NodeType, EdgeType
    from heuristic_query import HeuristicQuery
except ImportError:
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from attribute_graph import AttributeGraph, NodeType, EdgeType
    from heuristic_query import HeuristicQuery


class HeuristicDiscovery:
    """启发式发现能力类"""
    
    def __init__(self, graph_db_path: str):
        """
        初始化发现器
        
        Args:
            graph_db_path: 关联图数据库路径
        """
        self.graph_db_path = graph_db_path
        self.query = HeuristicQuery(graph_db_path)
        self.conn: Optional[sqlite3.Connection] = None
        
        # 推理链记录
        self.reasoning_chain: List[Dict[str, Any]] = []
        
        # 连接数据库
        self._connect()
    
    def _connect(self):
        """连接数据库"""
        self.conn = sqlite3.connect(self.graph_db_path)
        self.conn.row_factory = sqlite3.Row
    
    def close(self):
        """关闭连接"""
        if self.conn:
            self.conn.close()
            self.conn = None
        self.query.close()
    
    # ========== 核心发现算法 ==========
    
    def discover_bypass_paths(self, constraint: str) -> List[Dict[str, Any]]:
        """
        从零开始发现绕过某个约束的路径
        
        算法流程：
        1. 反向推理：分析约束的成因
        2. 反常检测：寻找不满足约束关键因素的实体
        3. 类比推理：分析反常实体的特征
        4. 假设验证：验证反常实体能否绕过
        5. 生成新边：如果验证通过，创建 bypasses 边
        
        Args:
            constraint: 约束节点ID
            
        Returns:
            发现的绕过路径列表
        """
        self.reasoning_chain = []
        
        # Step 1: 反向推理
        self.reasoning_chain.append({
            'step': 'backward_reasoning',
            'description': f'分析 {constraint} 的成因'
        })
        causes = self.analyze_constraint_causes(constraint)
        
        # Step 2: 识别关键因素
        self.reasoning_chain.append({
            'step': 'identify_key_factors',
            'description': '识别约束的关键因素'
        })
        key_factors = self.identify_key_factors(causes)
        
        # Step 3: 反常检测
        self.reasoning_chain.append({
            'step': 'anomaly_detection',
            'description': '寻找不满足关键因素的反常实体'
        })
        anomalies = self.find_anomalies(key_factors)
        
        # Step 4 & 5: 假设验证并生成新边
        discovered_bypasses = []
        
        for anomaly in anomalies:
            self.reasoning_chain.append({
                'step': 'verify_hypothesis',
                'description': f'验证 {anomaly} 能否绕过 {constraint}'
            })
            
            if self.verify_bypass(anomaly, constraint, key_factors):
                # 收集证据
                evidence = self.gather_evidence(anomaly, constraint, key_factors)
                
                # 生成新边
                new_edge = self.create_bypass_edge(anomaly, constraint, evidence)
                
                if new_edge:
                    discovered_bypasses.append(new_edge)
                    
                    self.reasoning_chain.append({
                        'step': 'create_edge',
                        'description': f'创建新边: {anomaly} --[bypasses]--> {constraint}',
                        'edge': new_edge
                    })
        
        return discovered_bypasses
    
    # ========== 反向推理算法 ==========
    
    def analyze_constraint_causes(self, constraint: str) -> List[Dict[str, Any]]:
        """
        分析约束的成因（反向图遍历）
        
        Args:
            constraint: 约束节点ID
            
        Returns:
            成因列表
        """
        # 使用查询能力获取成因
        causes = self.query.query_constraint_causes(constraint, max_depth=5)
        
        return causes
    
    def identify_key_factors(self, causes: List[Dict[str, Any]]) -> List[str]:
        """
        从成因中识别关键因素
        
        Args:
            causes: 成因列表
            
        Returns:
            关键因素列表
        """
        key_factors = []
        
        for cause in causes:
            # 提取因果链末端的关键因素
            if 'causal_chain' in cause and cause['causal_chain']:
                # 取因果链的最后一个节点作为关键因素
                last_node = cause['causal_chain'][-1]
                key_factors.append(last_node['node'])
            
            # 从条件字段提取关键因素
            if 'condition' in cause and cause['condition']:
                condition = cause['condition']
                
                # 提取 requires、excludes 等条件中的关键因素
                import re
                
                # 提取 requireSkillTypes
                req_match = re.search(r'requireSkillTypes:\s*([^\n]+)', condition)
                if req_match:
                    types = [t.strip() for t in req_match.group(1).split(',')]
                    key_factors.extend(types)
                
                # 提取 excludeSkillTypes
                exc_match = re.search(r'excludeSkillTypes:\s*([^\n]+)', condition)
                if exc_match:
                    types = [t.strip() for t in exc_match.group(1).split(',')]
                    key_factors.extend(types)
        
        # 去重
        key_factors = list(set(key_factors))
        
        return key_factors
    
    # ========== 反常检测算法 ==========
    
    def find_anomalies(self, key_factors: List[str]) -> List[str]:
        """
        寻找反常点（不满足关键因素的实体）
        
        Args:
            key_factors: 关键因素列表
            
        Returns:
            反常实体列表
        """
        cursor = self.conn.cursor()
        
        anomalies = []
        
        # 获取所有实体
        cursor.execute('''
            SELECT id, name
            FROM graph_nodes
            WHERE type = 'entity'
        ''')
        all_entities = cursor.fetchall()
        
        # 对每个关键因素，统计正常模式
        for factor in key_factors:
            normal_pattern = self.get_normal_pattern(factor)
            
            # 检查每个实体是否匹配正常模式
            for entity in all_entities:
                entity_id = entity['id']
                
                if not self.matches_pattern(entity_id, normal_pattern, factor):
                    anomalies.append(entity_id)
        
        # 去重并排序（出现次数多的在前）
        anomaly_counts = Counter(anomalies)
        anomalies = [entity for entity, count in anomaly_counts.most_common()]
        
        return anomalies
    
    def get_normal_pattern(self, factor: str) -> Dict[str, Any]:
        """
        获取大多数实体的正常模式
        
        Args:
            factor: 关键因素
            
        Returns:
            正常模式描述
        """
        cursor = self.conn.cursor()
        
        # 统计拥有该因素的实体数量
        cursor.execute('''
            SELECT COUNT(DISTINCT e.source_node)
            FROM graph_edges e
            WHERE e.target_node = ? AND e.edge_type = 'has_type'
        ''', (factor,))
        
        count = cursor.fetchone()[0]
        
        # 统计总实体数
        cursor.execute('SELECT COUNT(*) FROM graph_nodes WHERE type = \'entity\'')
        total = cursor.fetchone()[0]
        
        # 正常模式：大多数实体都不拥有该因素
        normal_pattern = {
            'factor': factor,
            'entities_with_factor': count,
            'total_entities': total,
            'percentage': count / total if total > 0 else 0,
            'is_common': (count / total) > 0.5 if total > 0 else False
        }
        
        return normal_pattern
    
    def matches_pattern(self, entity: str, pattern: Dict[str, Any], factor: str) -> bool:
        """
        检查实体是否匹配正常模式
        
        Args:
            entity: 实体ID
            pattern: 正常模式
            factor: 关键因素
            
        Returns:
            是否匹配
        """
        cursor = self.conn.cursor()
        
        # 检查实体是否拥有该因素
        cursor.execute('''
            SELECT COUNT(*)
            FROM graph_edges
            WHERE source_node = ? AND target_node = ? AND edge_type = 'has_type'
        ''', (entity, factor))
        
        has_factor = cursor.fetchone()[0] > 0
        
        # 如果该因素是常见的（大多数实体都有），则拥有该因素才是正常
        # 如果该因素是罕见的，则不拥有该因素才是正常
        if pattern['is_common']:
            return has_factor
        else:
            return not has_factor
    
    # ========== 假设验证算法 ==========
    
    def verify_bypass(self, entity: str, constraint: str, key_factors: List[str]) -> bool:
        """
        验证假设：entity 能否绕过 constraint
        
        Args:
            entity: 实体ID
            constraint: 约束节点ID
            key_factors: 关键因素列表
            
        Returns:
            是否能绕过
        """
        cursor = self.conn.cursor()
        
        # 检查实体是否满足关键因素
        satisfied_factors = []
        unsatisfied_factors = []
        
        for factor in key_factors:
            # 检查实体是否拥有该因素
            cursor.execute('''
                SELECT COUNT(*)
                FROM graph_edges
                WHERE source_node = ? AND target_node = ? AND edge_type = 'has_type'
            ''', (entity, factor))
            
            has_factor = cursor.fetchone()[0] > 0
            
            if has_factor:
                satisfied_factors.append(factor)
            else:
                unsatisfied_factors.append(factor)
        
        # 如果实体不满足关键因素，则可能绕过约束
        # 需要进一步验证
        
        # 检查实体是否已经有 bypasses 边指向该约束
        cursor.execute('''
            SELECT COUNT(*)
            FROM graph_edges
            WHERE source_node = ? AND target_node = ? AND edge_type = 'bypasses'
        ''', (entity, constraint))
        
        already_bypasses = cursor.fetchone()[0] > 0
        
        if already_bypasses:
            return False  # 已经绕过，不是新发现
        
        # 检查实体是否被约束阻止
        cursor.execute('''
            SELECT COUNT(*)
            FROM graph_edges
            WHERE source_node = ? AND target_node = ? AND edge_type IN ('blocked_by', 'constrained_by')
        ''', (entity, constraint))
        
        is_blocked = cursor.fetchone()[0] > 0
        
        if is_blocked:
            return False  # 被约束阻止，不能绕过
        
        # 如果不满足关键因素，且没有被阻止，则可能绕过
        return len(unsatisfied_factors) > 0
    
    def gather_evidence(self, entity: str, constraint: str, key_factors: List[str]) -> str:
        """
        收集证据
        
        Args:
            entity: 实体ID
            constraint: 约束节点ID
            key_factors: 关键因素列表
            
        Returns:
            证据描述
        """
        cursor = self.conn.cursor()
        
        evidence_parts = []
        
        # 获取实体名称
        cursor.execute('SELECT name FROM graph_nodes WHERE id = ?', (entity,))
        row = cursor.fetchone()
        entity_name = row['name'] if row else entity
        
        # 获取约束名称
        cursor.execute('SELECT name FROM graph_nodes WHERE id = ?', (constraint,))
        row = cursor.fetchone()
        constraint_name = row['name'] if row else constraint
        
        evidence_parts.append(f"实体 {entity_name} 不满足约束 {constraint_name} 的关键因素：")
        
        for factor in key_factors:
            # 检查实体是否拥有该因素
            cursor.execute('''
                SELECT COUNT(*)
                FROM graph_edges
                WHERE source_node = ? AND target_node = ? AND edge_type = 'has_type'
            ''', (entity, factor))
            
            has_factor = cursor.fetchone()[0] > 0
            
            if not has_factor:
                evidence_parts.append(f"  - 缺少关键因素: {factor}")
        
        # 检查触发机制
        cursor.execute('''
            SELECT target_node
            FROM graph_edges
            WHERE source_node = ? AND edge_type = 'triggers_via'
        ''', (entity,))
        
        trigger_mechs = cursor.fetchall()
        if trigger_mechs:
            trigger_names = [tm['target_node'] for tm in trigger_mechs]
            evidence_parts.append(f"  - 使用触发机制: {', '.join(trigger_names)}")
        
        return '\n'.join(evidence_parts)
    
    # ========== 新边生成 ==========
    
    def create_bypass_edge(self, source: str, target: str, evidence: str, 
                          confidence: float = 0.8) -> Optional[Dict[str, Any]]:
        """
        创建绕过边
        
        Args:
            source: 源节点ID
            target: 目标节点ID
            evidence: 证据描述
            confidence: 置信度
            
        Returns:
            新边信息
        """
        cursor = self.conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO graph_edges (
                    source_node, target_node, edge_type, weight, attributes,
                    status, evidence, created_at
                ) VALUES (?, ?, 'bypasses', ?, ?, 'hypothesis', ?, ?)
            ''', (
                source,
                target,
                confidence,
                json.dumps({'confidence': confidence, 'discovery_method': 'heuristic_discovery'}, ensure_ascii=False),
                evidence,
                datetime.now().isoformat()
            ))
            
            self.conn.commit()
            
            # 获取新插入的边ID
            cursor.execute('SELECT last_insert_rowid()')
            edge_id = cursor.fetchone()[0]
            
            return {
                'edge_id': edge_id,
                'source': source,
                'target': target,
                'edge_type': 'bypasses',
                'status': 'hypothesis',
                'confidence': confidence,
                'evidence': evidence
            }
        
        except Exception as e:
            print(f"创建边失败: {e}")
            return None
    
    # ========== 辅助方法 ==========
    
    def get_reasoning_chain(self) -> List[Dict[str, Any]]:
        """
        获取推理链
        
        Returns:
            推理链记录
        """
        return self.reasoning_chain
    
    def get_constraint_key_factors(self, constraint: str) -> List[str]:
        """
        获取约束的关键因素
        
        Args:
            constraint: 约束节点ID
            
        Returns:
            关键因素列表
        """
        causes = self.analyze_constraint_causes(constraint)
        return self.identify_key_factors(causes)


def main():
    """测试函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='启发式发现测试')
    parser.add_argument('graph_db', help='关联图数据库路径')
    parser.add_argument('--discover', help='发现绕过某个约束的路径')
    
    args = parser.parse_args()
    
    discovery = HeuristicDiscovery(args.graph_db)
    
    if args.discover:
        print(f"开始发现绕过 {args.discover} 的路径...\n")
        
        bypasses = discovery.discover_bypass_paths(args.discover)
        
        print(f"\n发现 {len(bypasses)} 条绕过路径:")
        for bp in bypasses:
            print(f"\n  边 ID: {bp['edge_id']}")
            print(f"  {bp['source']} --[{bp['edge_type']}]--> {bp['target']}")
            print(f"  置信度: {bp['confidence']}")
            print(f"  状态: {bp['status']}")
            print(f"  证据:\n{bp['evidence']}")
        
        print("\n推理链:")
        for step in discovery.get_reasoning_chain():
            print(f"  [{step['step']}] {step['description']}")
    
    discovery.close()


if __name__ == '__main__':
    main()
