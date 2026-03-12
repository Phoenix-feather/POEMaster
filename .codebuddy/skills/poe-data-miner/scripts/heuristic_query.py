#!/usr/bin/env python3
"""
启发式查询能力模块（Phase 2: 验证感知查询）

提供快速检索已知边的能力，支持验证状态分层查询
"""

import sqlite3
import logging
from typing import Dict, List, Any, Optional, Set, Tuple
from pathlib import Path
from collections import deque
from datetime import datetime

# 导入关联图模块
try:
    from attribute_graph import AttributeGraph, NodeType, EdgeType, VerificationStatus, EvidenceType, DiscoveryMethod
except ImportError:
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from attribute_graph import AttributeGraph, NodeType, EdgeType, VerificationStatus, EvidenceType, DiscoveryMethod

logger = logging.getLogger(__name__)


class HeuristicQuery:
    """
    启发式查询能力类（Phase 2: 验证感知）
    
    新增功能：
    1. 验证状态分层查询 - 按verified/pending/hypothesis分层返回
    2. 置信度过滤 - 只返回置信度>=阈值的边
    3. 完整验证字段 - 返回confidence, evidence_type等字段
    4. 证据类型过滤 - 按证据类型查询
    """
    
    def __init__(self, graph_db_path: str, verification_config: Optional[Dict[str, Any]] = None):
        """
        初始化查询器
        
        Args:
            graph_db_path: 关联图数据库路径
            verification_config: 验证配置
        """
        self.graph_db_path = graph_db_path
        self.conn: Optional[sqlite3.Connection] = None
        
        # 验证配置
        self.config = verification_config or {}
        self.default_confidence_threshold = self.config.get('default_confidence_threshold', 0.5)
        
        # 连接数据库
        self._connect()
        
        logger.info(f"HeuristicQuery初始化完成: {graph_db_path}")
    
    def _connect(self):
        """连接数据库"""
        self.conn = sqlite3.connect(self.graph_db_path)
        self.conn.row_factory = sqlite3.Row
    
    def close(self):
        """关闭连接"""
        if self.conn:
            self.conn.close()
            self.conn = None
    
    # ========== 核心查询方法 ==========
    
    def query_bypasses(self, constraint: str, include_hypothesis: bool = False,
                       min_confidence: Optional[float] = None) -> List[Dict[str, Any]]:
        """
        查询已知绕过某个约束的边（Phase 2: 验证感知）
        
        Args:
            constraint: 约束节点ID
            include_hypothesis: 是否包含假设边
            min_confidence: 最小置信度阈值（None表示使用默认值）
            
        Returns:
            绕过边列表（包含完整验证字段）
        """
        cursor = self.conn.cursor()
        
        # 使用配置的默认置信度
        if min_confidence is None:
            min_confidence = self.default_confidence_threshold
        
        query = '''
            SELECT 
                e.id as edge_id,
                e.source_node as source,
                e.target_node as target,
                e.edge_type as edge_type,
                e.weight as weight,
                e.status as status,
                e.source_rule as source_rule,
                e.heuristic_record_id as heuristic_record_id,
                e.evidence as evidence,
                e.confidence as confidence,
                e.evidence_type as evidence_type,
                e.evidence_source as evidence_source,
                e.evidence_content as evidence_content,
                e.discovery_method as discovery_method,
                e.last_verified as last_verified,
                e.verified_by as verified_by,
                n.name as source_name,
                n2.name as target_name
            FROM graph_edges e
            LEFT JOIN graph_nodes n ON e.source_node = n.id
            LEFT JOIN graph_nodes n2 ON e.target_node = n2.id
            WHERE e.target_node = ? AND e.edge_type = 'bypasses'
        '''
        
        params = [constraint]
        
        # 验证状态过滤
        if not include_hypothesis:
            query += " AND e.status IN (?, ?)"
            params.extend([VerificationStatus.VERIFIED.value, VerificationStatus.PENDING.value])
        
        # 置信度过滤
        query += " AND e.confidence >= ?"
        params.append(min_confidence)
        
        query += " ORDER BY e.confidence DESC, e.status ASC"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        bypasses = []
        for row in rows:
            bypasses.append({
                'edge_id': row['edge_id'],
                'source': row['source'],
                'source_name': row['source_name'],
                'target': row['target'],
                'target_name': row['target_name'],
                'edge_type': row['edge_type'],
                'weight': row['weight'],
                'status': row['status'],
                'source_rule': row['source_rule'],
                'heuristic_record_id': row['heuristic_record_id'],
                'evidence': row['evidence'],
                # Phase 2: 完整验证字段
                'confidence': row['confidence'],
                'evidence_type': row['evidence_type'],
                'evidence_source': row['evidence_source'],
                'evidence_content': row['evidence_content'],
                'discovery_method': row['discovery_method'],
                'last_verified': row['last_verified'],
                'verified_by': row['verified_by']
            })
        
        logger.debug(f"查询绕过边: constraint={constraint}, 结果数={len(bypasses)}")
        return bypasses
    
    def query_constraint_causes(self, constraint: str, max_depth: int = 3) -> List[Dict[str, Any]]:
        """
        查询约束的成因（反向追溯）
        
        Args:
            constraint: 约束节点ID
            max_depth: 最大追溯深度
            
        Returns:
            成因链列表
        """
        cursor = self.conn.cursor()
        
        # 找到所有直接指向约束的边
        cursor.execute('''
            SELECT 
                e.source_node,
                e.edge_type,
                e.condition,
                e.effect,
                n.name as source_name,
                n.type as source_type
            FROM graph_edges e
            LEFT JOIN graph_nodes n ON e.source_node = n.id
            WHERE e.target_node = ?
        ''', (constraint,))
        
        direct_causes = cursor.fetchall()
        
        causes = []
        for cause in direct_causes:
            # 追溯因果链
            causal_chain = self.trace_causal_chain(cause['source_node'], max_depth)
            
            causes.append({
                'source': cause['source_node'],
                'source_name': cause['source_name'],
                'source_type': cause['source_type'],
                'edge_type': cause['edge_type'],
                'condition': cause['condition'],
                'effect': cause['effect'],
                'causal_chain': causal_chain
            })
        
        return causes
    
    # ========== 图遍历辅助方法 ==========
    
    def trace_back_to_entity(self, node_id: str, max_depth: int = 5) -> List[Dict[str, Any]]:
        """
        从任意节点反向追溯到实体节点
        
        Args:
            node_id: 起始节点ID
            max_depth: 最大追溯深度
            
        Returns:
            路径列表（每条路径从起始节点到实体节点）
        """
        cursor = self.conn.cursor()
        
        # BFS反向搜索
        visited = set()
        queue = deque([(node_id, [])])
        paths = []
        
        while queue:
            current, path = queue.popleft()
            
            if len(path) >= max_depth:
                continue
            
            if current in visited:
                continue
            visited.add(current)
            
            # 获取节点类型
            cursor.execute('SELECT type FROM graph_nodes WHERE id = ?', (current,))
            row = cursor.fetchone()
            if not row:
                continue
            
            node_type = row['type']
            
            # 如果是实体节点，记录路径
            if node_type == 'entity':
                paths.append({
                    'start_node': node_id,
                    'end_node': current,
                    'path': path,
                    'depth': len(path)
                })
                continue
            
            # 获取反向边（谁指向当前节点）
            cursor.execute('''
                SELECT source_node, edge_type, n.type as source_type
                FROM graph_edges e
                LEFT JOIN graph_nodes n ON e.source_node = n.id
                WHERE e.target_node = ?
            ''', (current,))
            
            reverse_edges = cursor.fetchall()
            
            for edge in reverse_edges:
                new_path = path + [{
                    'source': edge['source_node'],
                    'target': current,
                    'edge_type': edge['edge_type']
                }]
                queue.append((edge['source_node'], new_path))
        
        return paths
    
    def get_all_paths(self, source: str, target: str, max_depth: int = 5) -> List[List[Dict[str, Any]]]:
        """
        查找两个节点之间的所有路径（BFS）
        
        Args:
            source: 起始节点ID
            target: 目标节点ID
            max_depth: 最大搜索深度
            
        Returns:
            所有路径列表
        """
        cursor = self.conn.cursor()
        
        paths = []
        visited = set()
        queue = deque([(source, [])])
        
        while queue:
            current, path = queue.popleft()
            
            if len(path) > max_depth:
                continue
            
            if current == target and path:
                paths.append(path)
                continue
            
            if current in visited:
                continue
            visited.add(current)
            
            # 获取邻居
            cursor.execute('''
                SELECT target_node, edge_type, n.name as target_name
                FROM graph_edges e
                LEFT JOIN graph_nodes n ON e.target_node = n.id
                WHERE e.source_node = ?
            ''', (current,))
            
            neighbors = cursor.fetchall()
            
            for neighbor in neighbors:
                if neighbor['target_node'] not in visited:
                    new_path = path + [{
                        'source': current,
                        'target': neighbor['target_node'],
                        'target_name': neighbor['target_name'],
                        'edge_type': neighbor['edge_type']
                    }]
                    queue.append((neighbor['target_node'], new_path))
        
        return paths
    
    def get_neighbors_by_edge_type(self, node_id: str, edge_type: str, 
                                     direction: str = 'outgoing') -> List[Dict[str, Any]]:
        """
        获取特定边类型的邻居节点
        
        Args:
            node_id: 节点ID
            edge_type: 边类型
            direction: 方向 ('outgoing' 或 'incoming')
            
        Returns:
            邻居节点列表
        """
        cursor = self.conn.cursor()
        
        if direction == 'outgoing':
            cursor.execute('''
                SELECT 
                    e.target_node as neighbor,
                    e.edge_type,
                    e.weight,
                    e.status,
                    n.name as neighbor_name,
                    n.type as neighbor_type
                FROM graph_edges e
                LEFT JOIN graph_nodes n ON e.target_node = n.id
                WHERE e.source_node = ? AND e.edge_type = ?
            ''', (node_id, edge_type))
        else:
            cursor.execute('''
                SELECT 
                    e.source_node as neighbor,
                    e.edge_type,
                    e.weight,
                    e.status,
                    n.name as neighbor_name,
                    n.type as neighbor_type
                FROM graph_edges e
                LEFT JOIN graph_nodes n ON e.source_node = n.id
                WHERE e.target_node = ? AND e.edge_type = ?
            ''', (node_id, edge_type))
        
        rows = cursor.fetchall()
        
        neighbors = []
        for row in rows:
            neighbors.append({
                'neighbor': row['neighbor'],
                'neighbor_name': row['neighbor_name'],
                'neighbor_type': row['neighbor_type'],
                'edge_type': row['edge_type'],
                'weight': row['weight'],
                'status': row['status']
            })
        
        return neighbors
    
    def trace_causal_chain(self, node_id: str, max_depth: int = 3) -> List[Dict[str, Any]]:
        """
        追溯因果链（从节点向上追溯）
        
        Args:
            node_id: 起始节点ID
            max_depth: 最大追溯深度
            
        Returns:
            因果链（从当前节点向上追溯）
        """
        cursor = self.conn.cursor()
        
        chain = []
        current = node_id
        visited = set()
        
        while len(chain) < max_depth and current not in visited:
            visited.add(current)
            
            # 获取当前节点信息
            cursor.execute('SELECT id, name, type FROM graph_nodes WHERE id = ?', (current,))
            row = cursor.fetchone()
            if not row:
                break
            
            chain.append({
                'node': row['id'],
                'name': row['name'],
                'type': row['type']
            })
            
            # 获取因果边（使用 causes, produces, implies 等边类型）
            cursor.execute('''
                SELECT source_node, edge_type, n.name as source_name, n.type as source_type
                FROM graph_edges e
                LEFT JOIN graph_nodes n ON e.source_node = n.id
                WHERE e.target_node = ? AND e.edge_type IN ('causes', 'produces', 'implies')
            ''', (current,))
            
            cause = cursor.fetchone()
            if not cause:
                break
            
            chain[-1]['cause_source'] = cause['source_node']
            chain[-1]['cause_edge_type'] = cause['edge_type']
            
            current = cause['source_node']
        
        return chain
    
    # ========== 统计方法 ==========
    
    def get_node_stats(self, node_id: str) -> Dict[str, Any]:
        """
        获取节点统计信息
        
        Args:
            node_id: 节点ID
            
        Returns:
            统计信息
        """
        cursor = self.conn.cursor()
        
        # 获取节点信息
        cursor.execute('SELECT * FROM graph_nodes WHERE id = ?', (node_id,))
        node = cursor.fetchone()
        if not node:
            return {}
        
        # 获取出边统计
        cursor.execute('''
            SELECT edge_type, COUNT(*) as count
            FROM graph_edges
            WHERE source_node = ?
            GROUP BY edge_type
        ''', (node_id,))
        outgoing_stats = {row['edge_type']: row['count'] for row in cursor.fetchall()}
        
        # 获取入边统计
        cursor.execute('''
            SELECT edge_type, COUNT(*) as count
            FROM graph_edges
            WHERE target_node = ?
            GROUP BY edge_type
        ''', (node_id,))
        incoming_stats = {row['edge_type']: row['count'] for row in cursor.fetchall()}
        
        return {
            'node': dict(node),
            'outgoing_edges': outgoing_stats,
            'incoming_edges': incoming_stats,
            'total_outgoing': sum(outgoing_stats.values()),
            'total_incoming': sum(incoming_stats.values())
        }
    
    # ========== Phase 2: 验证感知查询方法 ==========
    
    def query_bypasses_by_verification_status(self, constraint: str,
                                               min_confidence: Optional[float] = None) -> Dict[str, List[Dict[str, Any]]]:
        """
        按验证状态分层查询绕过边（Phase 2新增）
        
        返回三层结果：
        - verified: 已验证的知识（置信度100%）
        - pending: 待确认的知识（置信度50-99%）
        - hypothesis: 假设性知识（置信度<50%）
        
        Args:
            constraint: 约束节点ID
            min_confidence: 最小置信度阈值
            
        Returns:
            分层结果字典
        """
        if min_confidence is None:
            min_confidence = self.default_confidence_threshold
        
        cursor = self.conn.cursor()
        
        # 查询所有绕过边（包含假设）
        query = '''
            SELECT 
                e.id as edge_id,
                e.source_node as source,
                e.target_node as target,
                e.edge_type as edge_type,
                e.weight as weight,
                e.status as status,
                e.confidence as confidence,
                e.evidence_type as evidence_type,
                e.evidence_source as evidence_source,
                e.evidence_content as evidence_content,
                e.discovery_method as discovery_method,
                e.last_verified as last_verified,
                e.verified_by as verified_by,
                n.name as source_name,
                n2.name as target_name
            FROM graph_edges e
            LEFT JOIN graph_nodes n ON e.source_node = n.id
            LEFT JOIN graph_nodes n2 ON e.target_node = n2.id
            WHERE e.target_node = ? AND e.edge_type = 'bypasses'
                AND e.confidence >= ?
            ORDER BY e.confidence DESC
        '''
        
        cursor.execute(query, (constraint, min_confidence))
        rows = cursor.fetchall()
        
        # 分层结果
        result = {
            'verified': [],
            'pending': [],
            'hypothesis': [],
            'summary': {
                'constraint': constraint,
                'min_confidence': min_confidence,
                'total_count': len(rows),
                'verified_count': 0,
                'pending_count': 0,
                'hypothesis_count': 0
            }
        }
        
        for row in rows:
            edge_data = {
                'edge_id': row['edge_id'],
                'source': row['source'],
                'source_name': row['source_name'],
                'target': row['target'],
                'target_name': row['target_name'],
                'edge_type': row['edge_type'],
                'weight': row['weight'],
                'status': row['status'],
                'confidence': row['confidence'],
                'evidence_type': row['evidence_type'],
                'evidence_source': row['evidence_source'],
                'evidence_content': row['evidence_content'],
                'discovery_method': row['discovery_method'],
                'last_verified': row['last_verified'],
                'verified_by': row['verified_by']
            }
            
            # 按状态分层
            status = row['status']
            if status == VerificationStatus.VERIFIED.value:
                result['verified'].append(edge_data)
                result['summary']['verified_count'] += 1
            elif status == VerificationStatus.PENDING.value:
                result['pending'].append(edge_data)
                result['summary']['pending_count'] += 1
            elif status == VerificationStatus.HYPOTHESIS.value:
                result['hypothesis'].append(edge_data)
                result['summary']['hypothesis_count'] += 1
        
        logger.info(f"分层查询绕过边: constraint={constraint}, verified={result['summary']['verified_count']}, "
                   f"pending={result['summary']['pending_count']}, hypothesis={result['summary']['hypothesis_count']}")
        
        return result
    
    def query_with_verification_layers(self, query_type: str, 
                                       params: Dict[str, Any],
                                       min_confidence: Optional[float] = None) -> Dict[str, List[Dict[str, Any]]]:
        """
        通用验证感知查询（Phase 2新增）
        
        支持多种查询类型的分层返回
        
        Args:
            query_type: 查询类型 ('bypasses', 'causes', 'all_edges', 'by_type')
            params: 查询参数
            min_confidence: 最小置信度阈值
            
        Returns:
            分层结果字典
        """
        if min_confidence is None:
            min_confidence = self.default_confidence_threshold
        
        cursor = self.conn.cursor()
        
        # 构建查询
        base_query = '''
            SELECT 
                e.id as edge_id,
                e.source_node as source,
                e.target_node as target,
                e.edge_type as edge_type,
                e.weight as weight,
                e.status as status,
                e.confidence as confidence,
                e.evidence_type as evidence_type,
                e.evidence_source as evidence_source,
                e.evidence_content as evidence_content,
                e.discovery_method as discovery_method,
                e.last_verified as last_verified,
                e.verified_by as verified_by,
                n.name as source_name,
                n2.name as target_name
            FROM graph_edges e
            LEFT JOIN graph_nodes n ON e.source_node = n.id
            LEFT JOIN graph_nodes n2 ON e.target_node = n2.id
            WHERE e.confidence >= ?
        '''
        
        query_params = [min_confidence]
        
        # 添加查询条件
        if query_type == 'bypasses':
            base_query += " AND e.edge_type = 'bypasses'"
            if 'constraint' in params:
                base_query += " AND e.target_node = ?"
                query_params.append(params['constraint'])
        
        elif query_type == 'causes':
            base_query += " AND e.edge_type IN ('causes', 'produces', 'implies')"
            if 'target' in params:
                base_query += " AND e.target_node = ?"
                query_params.append(params['target'])
        
        elif query_type == 'by_type':
            if 'node_type' in params:
                base_query += " AND n.type = ?"
                query_params.append(params['node_type'])
        
        # 添加排序
        base_query += " ORDER BY e.confidence DESC, e.status ASC"
        
        cursor.execute(base_query, query_params)
        rows = cursor.fetchall()
        
        # 分层结果
        result = {
            'verified': [],
            'pending': [],
            'hypothesis': [],
            'summary': {
                'query_type': query_type,
                'params': params,
                'min_confidence': min_confidence,
                'total_count': len(rows),
                'verified_count': 0,
                'pending_count': 0,
                'hypothesis_count': 0
            }
        }
        
        for row in rows:
            edge_data = {
                'edge_id': row['edge_id'],
                'source': row['source'],
                'source_name': row['source_name'],
                'target': row['target'],
                'target_name': row['target_name'],
                'edge_type': row['edge_type'],
                'weight': row['weight'],
                'status': row['status'],
                'confidence': row['confidence'],
                'evidence_type': row['evidence_type'],
                'evidence_source': row['evidence_source'],
                'evidence_content': row['evidence_content'],
                'discovery_method': row['discovery_method'],
                'last_verified': row['last_verified'],
                'verified_by': row['verified_by']
            }
            
            status = row['status']
            if status == VerificationStatus.VERIFIED.value:
                result['verified'].append(edge_data)
                result['summary']['verified_count'] += 1
            elif status == VerificationStatus.PENDING.value:
                result['pending'].append(edge_data)
                result['summary']['pending_count'] += 1
            elif status == VerificationStatus.HYPOTHESIS.value:
                result['hypothesis'].append(edge_data)
                result['summary']['hypothesis_count'] += 1
        
        return result
    
    def get_verification_stats(self, node_id: Optional[str] = None) -> Dict[str, Any]:
        """
        获取验证统计信息（Phase 2新增）
        
        Args:
            node_id: 节点ID（None表示全局统计）
            
        Returns:
            验证统计字典
        """
        cursor = self.conn.cursor()
        
        stats = {
            'total_edges': 0,
            'verified_count': 0,
            'pending_count': 0,
            'hypothesis_count': 0,
            'rejected_count': 0,
            'avg_confidence': 0.0,
            'by_evidence_type': {},
            'by_discovery_method': {}
        }
        
        # 基础查询
        if node_id:
            query = '''
                SELECT 
                    e.status,
                    e.confidence,
                    e.evidence_type,
                    e.discovery_method
                FROM graph_edges e
                WHERE e.source_node = ? OR e.target_node = ?
            '''
            cursor.execute(query, (node_id, node_id))
        else:
            query = '''
                SELECT 
                    e.status,
                    e.confidence,
                    e.evidence_type,
                    e.discovery_method
                FROM graph_edges e
            '''
            cursor.execute(query)
        
        rows = cursor.fetchall()
        
        stats['total_edges'] = len(rows)
        
        total_confidence = 0.0
        confidence_count = 0
        
        for row in rows:
            status = row['status']
            confidence = row['confidence'] or 0.0
            evidence_type = row['evidence_type']
            discovery_method = row['discovery_method']
            
            # 按状态计数
            if status == VerificationStatus.VERIFIED.value:
                stats['verified_count'] += 1
            elif status == VerificationStatus.PENDING.value:
                stats['pending_count'] += 1
            elif status == VerificationStatus.HYPOTHESIS.value:
                stats['hypothesis_count'] += 1
            elif status == VerificationStatus.REJECTED.value:
                stats['rejected_count'] += 1
            
            # 平均置信度
            total_confidence += confidence
            confidence_count += 1
            
            # 按证据类型统计
            if evidence_type:
                stats['by_evidence_type'][evidence_type] = \
                    stats['by_evidence_type'].get(evidence_type, 0) + 1
            
            # 按发现方法统计
            if discovery_method:
                stats['by_discovery_method'][discovery_method] = \
                    stats['by_discovery_method'].get(discovery_method, 0) + 1
        
        # 计算平均置信度
        if confidence_count > 0:
            stats['avg_confidence'] = total_confidence / confidence_count
        
        # 添加百分比
        if stats['total_edges'] > 0:
            stats['verified_percentage'] = stats['verified_count'] / stats['total_edges'] * 100
            stats['pending_percentage'] = stats['pending_count'] / stats['total_edges'] * 100
            stats['hypothesis_percentage'] = stats['hypothesis_count'] / stats['total_edges'] * 100
        
        return stats



def main():
    """测试函数（Phase 2: 验证感知查询）"""
    import argparse
    
    parser = argparse.ArgumentParser(description='启发式查询测试（验证感知）')
    parser.add_argument('graph_db', help='关联图数据库路径')
    parser.add_argument('--bypass', help='查询绕过某个约束')
    parser.add_argument('--bypass-layers', help='按验证状态分层查询绕过边')
    parser.add_argument('--causes', help='查询约束的成因')
    parser.add_argument('--stats', help='获取节点统计')
    parser.add_argument('--verification-stats', action='store_true', 
                       help='获取验证统计信息')
    parser.add_argument('--node', help='指定节点ID（用于验证统计）')
    parser.add_argument('--min-confidence', type=float, default=0.5,
                       help='最小置信度阈值（默认0.5）')
    
    args = parser.parse_args()
    
    # 配置
    config = {
        'default_confidence_threshold': args.min_confidence
    }
    
    query = HeuristicQuery(args.graph_db, config)
    
    try:
        if args.bypass:
            print(f"=== 查询绕过 {args.bypass} 的边 ===")
            bypasses = query.query_bypasses(args.bypass, min_confidence=args.min_confidence)
            print(f"找到 {len(bypasses)} 条边:\n")
            for bp in bypasses:
                print(f"  {bp['source_name']} --[{bp['edge_type']}]--> {bp['target_name']}")
                print(f"    状态: {bp['status']}, 置信度: {bp['confidence']:.2f}")
                print(f"    证据类型: {bp['evidence_type']}")
                if bp['evidence_content']:
                    print(f"    证据: {bp['evidence_content'][:100]}...")
                print()
        
        if args.bypass_layers:
            print(f"=== 分层查询绕过 {args.bypass_layers} 的边 ===")
            result = query.query_bypasses_by_verification_status(
                args.bypass_layers, 
                min_confidence=args.min_confidence
            )
            
            summary = result['summary']
            print(f"\n总数: {summary['total_count']}")
            print(f"  已验证: {summary['verified_count']}")
            print(f"  待确认: {summary['pending_count']}")
            print(f"  假设: {summary['hypothesis_count']}\n")
            
            if result['verified']:
                print("【已验证边】")
                for edge in result['verified'][:5]:  # 只显示前5条
                    print(f"  {edge['source_name']} -> {edge['target_name']}")
                    print(f"    置信度: {edge['confidence']:.2f}, 证据: {edge['evidence_type']}")
                print()
            
            if result['pending']:
                print("【待确认边】")
                for edge in result['pending'][:5]:
                    print(f"  {edge['source_name']} -> {edge['target_name']}")
                    print(f"    置信度: {edge['confidence']:.2f}")
                print()
            
            if result['hypothesis']:
                print("【假设边】")
                for edge in result['hypothesis'][:5]:
                    print(f"  {edge['source_name']} -> {edge['target_name']}")
                    print(f"    置信度: {edge['confidence']:.2f}, 发现方法: {edge['discovery_method']}")
                print()
        
        if args.causes:
            print(f"=== {args.causes} 的成因 ===")
            causes = query.query_constraint_causes(args.causes)
            for cause in causes:
                print(f"  {cause['source_name']} --[{cause['edge_type']}]--> {args.causes}")
                print(f"    因果链: {' -> '.join([c['name'] for c in cause['causal_chain']])}")
        
        if args.stats:
            print(f"=== {args.stats} 的统计 ===")
            stats = query.get_node_stats(args.stats)
            print(f"  节点类型: {stats['node']['type']}")
            print(f"  出边统计: {stats['outgoing_edges']}")
            print(f"  入边统计: {stats['incoming_edges']}")
        
        if args.verification_stats:
            print("=== 验证统计信息 ===")
            stats = query.get_verification_stats(args.node)
            print(f"  总边数: {stats['total_edges']}")
            print(f"  已验证: {stats['verified_count']} ({stats.get('verified_percentage', 0):.1f}%)")
            print(f"  待确认: {stats['pending_count']} ({stats.get('pending_percentage', 0):.1f}%)")
            print(f"  假设: {stats['hypothesis_count']} ({stats.get('hypothesis_percentage', 0):.1f}%)")
            print(f"  平均置信度: {stats['avg_confidence']:.2f}")
            print(f"\n  按证据类型:")
            for etype, count in stats['by_evidence_type'].items():
                print(f"    {etype}: {count}")
            print(f"\n  按发现方法:")
            for method, count in stats['by_discovery_method'].items():
                print(f"    {method}: {count}")
    
    finally:
        query.close()


if __name__ == '__main__':
    main()
