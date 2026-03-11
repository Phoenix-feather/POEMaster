#!/usr/bin/env python3
"""
启发式查询能力模块
提供快速检索已知边的能力
"""

import sqlite3
from typing import Dict, List, Any, Optional, Set, Tuple
from pathlib import Path
from collections import deque

# 导入关联图模块
try:
    from attribute_graph import AttributeGraph, NodeType, EdgeType
except ImportError:
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from attribute_graph import AttributeGraph, NodeType, EdgeType


class HeuristicQuery:
    """启发式查询能力类"""
    
    def __init__(self, graph_db_path: str):
        """
        初始化查询器
        
        Args:
            graph_db_path: 关联图数据库路径
        """
        self.graph_db_path = graph_db_path
        self.conn: Optional[sqlite3.Connection] = None
        
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
    
    # ========== 核心查询方法 ==========
    
    def query_bypasses(self, constraint: str, include_hypothesis: bool = False) -> List[Dict[str, Any]]:
        """
        查询已知绕过某个约束的边
        
        Args:
            constraint: 约束节点ID
            include_hypothesis: 是否包含假设边
            
        Returns:
            绕过边列表
        """
        cursor = self.conn.cursor()
        
        query = '''
            SELECT 
                e.source_node as source,
                e.target_node as target,
                e.edge_type as edge_type,
                e.weight as weight,
                e.status as status,
                e.source_rule as source_rule,
                e.heuristic_record_id as heuristic_record_id,
                e.evidence as evidence,
                n.name as source_name,
                n2.name as target_name
            FROM graph_edges e
            LEFT JOIN graph_nodes n ON e.source_node = n.id
            LEFT JOIN graph_nodes n2 ON e.target_node = n2.id
            WHERE e.target_node = ? AND e.edge_type = 'bypasses'
        '''
        
        params = [constraint]
        
        if not include_hypothesis:
            query += " AND e.status = 'verified'"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        bypasses = []
        for row in rows:
            bypasses.append({
                'source': row['source'],
                'source_name': row['source_name'],
                'target': row['target'],
                'target_name': row['target_name'],
                'edge_type': row['edge_type'],
                'weight': row['weight'],
                'status': row['status'],
                'source_rule': row['source_rule'],
                'heuristic_record_id': row['heuristic_record_id'],
                'evidence': row['evidence']
            })
        
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


def main():
    """测试函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='启发式查询测试')
    parser.add_argument('graph_db', help='关联图数据库路径')
    parser.add_argument('--bypass', help='查询绕过某个约束')
    parser.add_argument('--causes', help='查询约束的成因')
    parser.add_argument('--stats', help='获取节点统计')
    
    args = parser.parse_args()
    
    query = HeuristicQuery(args.graph_db)
    
    if args.bypass:
        bypasses = query.query_bypasses(args.bypass)
        print(f"绕过 {args.bypass} 的边:")
        for bp in bypasses:
            print(f"  - {bp['source']} --[{bp['edge_type']}]--> {bp['target']}")
            print(f"    证据: {bp['evidence']}")
    
    if args.causes:
        causes = query.query_constraint_causes(args.causes)
        print(f"{args.causes} 的成因:")
        for cause in causes:
            print(f"  - {cause['source']} --[{cause['edge_type']}]--> {args.causes}")
            print(f"    因果链: {' -> '.join([c['name'] for c in cause['causal_chain']])}")
    
    if args.stats:
        stats = query.get_node_stats(args.stats)
        print(f"{args.stats} 的统计:")
        print(f"  节点类型: {stats['node']['type']}")
        print(f"  出边统计: {stats['outgoing_edges']}")
        print(f"  入边统计: {stats['incoming_edges']}")
    
    query.close()


if __name__ == '__main__':
    main()
