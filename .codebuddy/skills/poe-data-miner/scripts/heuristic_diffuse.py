#!/usr/bin/env python3
"""
启发式扩散能力模块
提供从已知边扩散发现相似边的能力
"""

import sqlite3
import json
from typing import Dict, List, Any, Optional, Set, Tuple
from pathlib import Path
from datetime import datetime

# 导入关联图模块
try:
    from attribute_graph import AttributeGraph, NodeType, EdgeType
    from heuristic_discovery import HeuristicDiscovery
except ImportError:
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from attribute_graph import AttributeGraph, NodeType, EdgeType
    from heuristic_discovery import HeuristicDiscovery


class HeuristicDiffuse:
    """启发式扩散能力类"""
    
    def __init__(self, graph_db_path: str):
        """
        初始化扩散器
        
        Args:
            graph_db_path: 关联图数据库路径
        """
        self.graph_db_path = graph_db_path
        self.discovery = HeuristicDiscovery(graph_db_path)
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
        self.discovery.close()
    
    # ========== 核心扩散算法 ==========
    
    def diffuse_from_bypass(self, known_bypass_edge: Dict[str, Any], 
                            similarity_threshold: float = 0.7) -> List[Dict[str, Any]]:
        """
        从一条已知的绕过边，发现类似的绕过边
        
        算法流程：
        1. 提取已知绕过边的关键特征
        2. 寻找具有相似特征的实体
        3. 验证这些实体是否也能绕过
        4. 生成新的绕过边
        
        Args:
            known_bypass_edge: 已知绕过边
            similarity_threshold: 相似度阈值
            
        Returns:
            新发现的绕过边列表
        """
        source = known_bypass_edge.get('source', '')
        target = known_bypass_edge.get('target', '')
        
        # Step 1: 提取关键特征
        features = self.extract_key_features(source)
        
        # Step 2: 寻找相似实体
        similar_entities = self.find_similar_entities(features, exclude=[source], 
                                                      threshold=similarity_threshold)
        
        # Step 3 & 4: 验证并生成新边
        new_bypasses = []
        
        for entity, similarity in similar_entities:
            # 验证是否能绕过
            key_factors = self.discovery.get_constraint_key_factors(target)
            
            if self.discovery.verify_bypass(entity, target, key_factors):
                # 收集证据
                evidence = self.discovery.gather_evidence(entity, target, key_factors)
                evidence += f"\n  - 与已知绕过实体 {source} 相似度: {similarity:.2f}"
                
                # 生成新边
                confidence = similarity * 0.8  # 基于相似度计算置信度
                new_edge = self.discovery.create_bypass_edge(
                    entity, target, evidence, confidence=confidence
                )
                
                if new_edge:
                    new_edge['similarity'] = similarity
                    new_edge['source_entity'] = source
                    new_bypasses.append(new_edge)
        
        return new_bypasses
    
    # ========== 特征提取算法 ==========
    
    def extract_key_features(self, entity: str) -> Dict[str, List[str]]:
        """
        提取实体的关键特征
        
        Args:
            entity: 实体ID
            
        Returns:
            特征字典
        """
        cursor = self.conn.cursor()
        
        features = {
            'types': [],
            'properties': [],
            'trigger_mechanisms': [],
            'stats': [],
            'constraints': []
        }
        
        # 获取所有出边
        cursor.execute('''
            SELECT target_node, edge_type
            FROM graph_edges
            WHERE source_node = ?
        ''', (entity,))
        
        edges = cursor.fetchall()
        
        for edge in edges:
            target = edge['target_node']
            edge_type = edge['edge_type']
            
            if edge_type == 'has_type':
                features['types'].append(target)
            elif edge_type == 'has_stat':
                features['stats'].append(target)
            elif edge_type == 'triggers_via':
                features['trigger_mechanisms'].append(target)
            elif edge_type == 'constrained_by':
                features['constraints'].append(target)
        
        # 获取隐含属性
        implied_props = self.get_implied_properties(entity)
        features['properties'] = implied_props
        
        return features
    
    def get_implied_properties(self, entity: str) -> List[str]:
        """
        获取实体的隐含属性
        
        Args:
            entity: 实体ID
            
        Returns:
            隐含属性列表
        """
        cursor = self.conn.cursor()
        
        properties = []
        
        # 获取实体的所有类型
        cursor.execute('''
            SELECT target_node
            FROM graph_edges
            WHERE source_node = ? AND edge_type = 'has_type'
        ''', (entity,))
        
        types = [row['target_node'] for row in cursor.fetchall()]
        
        # 对每个类型，检查是否有 implies 边指向属性
        for type_node in types:
            cursor.execute('''
                SELECT target_node
                FROM graph_edges
                WHERE source_node = ? AND edge_type = 'implies'
            ''', (type_node,))
            
            implied = [row['target_node'] for row in cursor.fetchall()]
            properties.extend(implied)
        
        # 去重
        properties = list(set(properties))
        
        return properties
    
    # ========== 相似度计算算法 ==========
    
    def find_similar_entities(self, features: Dict[str, List[str]], 
                              exclude: List[str] = None,
                              threshold: float = 0.7) -> List[Tuple[str, float]]:
        """
        寻找相似实体
        
        Args:
            features: 参考特征
            exclude: 排除的实体列表
            threshold: 相似度阈值
            
        Returns:
            相似实体列表 [(entity_id, similarity), ...]
        """
        cursor = self.conn.cursor()
        
        similar = []
        
        # 获取所有实体
        cursor.execute('''
            SELECT id
            FROM graph_nodes
            WHERE type = 'entity'
        ''')
        
        all_entities = [row['id'] for row in cursor.fetchall()]
        
        # 排除特定实体
        if exclude:
            all_entities = [e for e in all_entities if e not in exclude]
        
        # 计算每个实体的相似度
        for entity in all_entities:
            entity_features = self.extract_key_features(entity)
            
            # 计算相似度
            similarity = self.calculate_similarity(features, entity_features)
            
            if similarity >= threshold:
                similar.append((entity, similarity))
        
        # 按相似度排序
        similar.sort(key=lambda x: x[1], reverse=True)
        
        return similar
    
    def calculate_similarity(self, features1: Dict[str, List[str]], 
                            features2: Dict[str, List[str]]) -> float:
        """
        计算特征相似度（Jaccard 相似度加权平均）
        
        Args:
            features1: 特征1
            features2: 特征2
            
        Returns:
            相似度 [0, 1]
        """
        # Jaccard 相似度函数
        def jaccard(set1: Set[str], set2: Set[str]) -> float:
            if not set1 and not set2:
                return 1.0
            if not set1 or not set2:
                return 0.0
            
            intersection = len(set1 & set2)
            union = len(set1 | set2)
            
            return intersection / union if union > 0 else 0.0
        
        # 特征类型权重
        weights = {
            'types': 0.3,
            'properties': 0.4,  # 属性权重最高（最能体现绕过能力）
            'trigger_mechanisms': 0.2,
            'stats': 0.05,
            'constraints': 0.05
        }
        
        # 计算加权平均
        total_similarity = 0.0
        total_weight = 0.0
        
        for key, weight in weights.items():
            set1 = set(features1.get(key, []))
            set2 = set(features2.get(key, []))
            
            sim = jaccard(set1, set2)
            total_similarity += weight * sim
            total_weight += weight
        
        return total_similarity / total_weight if total_weight > 0 else 0.0
    
    # ========== 批量扩散 ==========
    
    def diffuse_from_multiple_bypasses(self, bypass_edges: List[Dict[str, Any]],
                                       similarity_threshold: float = 0.7,
                                       max_new_edges: int = 10) -> List[Dict[str, Any]]:
        """
        从多条已知绕过边批量扩散
        
        Args:
            bypass_edges: 已知绕过边列表
            similarity_threshold: 相似度阈值
            max_new_edges: 最大新边数量
            
        Returns:
            新发现的绕过边列表
        """
        all_new_bypasses = []
        seen_entities = set()
        
        for bypass_edge in bypass_edges:
            # 从单条边扩散
            new_bypasses = self.diffuse_from_bypass(bypass_edge, similarity_threshold)
            
            # 去重
            for new_bypass in new_bypasses:
                entity = new_bypass['source']
                if entity not in seen_entities:
                    all_new_bypasses.append(new_bypass)
                    seen_entities.add(entity)
                    
                    if len(all_new_bypasses) >= max_new_edges:
                        return all_new_bypasses
        
        return all_new_bypasses
    
    # ========== 深度扩散 ==========
    
    def deep_diffuse(self, start_entity: str, constraint: str,
                     max_depth: int = 2, similarity_threshold: float = 0.7) -> List[Dict[str, Any]]:
        """
        深度扩散（递归扩散）
        
        Args:
            start_entity: 起始实体
            constraint: 约束节点
            max_depth: 最大扩散深度
            similarity_threshold: 相似度阈值
            
        Returns:
            所有发现的绕过边
        """
        all_bypasses = []
        visited = {start_entity}
        
        # 当前层实体
        current_layer = [start_entity]
        
        for depth in range(max_depth):
            next_layer = []
            
            for entity in current_layer:
                # 创建虚拟绕过边（用于扩散）
                virtual_bypass = {
                    'source': entity,
                    'target': constraint
                }
                
                # 扩散
                new_bypasses = self.diffuse_from_bypass(virtual_bypass, similarity_threshold)
                
                for new_bypass in new_bypasses:
                    new_entity = new_bypass['source']
                    
                    if new_entity not in visited:
                        all_bypasses.append(new_bypass)
                        visited.add(new_entity)
                        next_layer.append(new_entity)
            
            current_layer = next_layer
        
        return all_bypasses


def main():
    """测试函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='启发式扩散测试')
    parser.add_argument('graph_db', help='关联图数据库路径')
    parser.add_argument('--diffuse', nargs=2, metavar=('SOURCE', 'TARGET'), 
                       help='从已知绕过边扩散')
    parser.add_argument('--threshold', type=float, default=0.7, 
                       help='相似度阈值')
    
    args = parser.parse_args()
    
    diffuse = HeuristicDiffuse(args.graph_db)
    
    if args.diffuse:
        source, target = args.diffuse
        
        print(f"从 {source} --[bypasses]--> {target} 扩散...\n")
        
        known_bypass = {
            'source': source,
            'target': target
        }
        
        new_bypasses = diffuse.diffuse_from_bypass(known_bypass, args.threshold)
        
        print(f"发现 {len(new_bypasses)} 条新的绕过边:")
        for bp in new_bypasses:
            print(f"\n  边 ID: {bp['edge_id']}")
            print(f"  {bp['source']} --[{bp['edge_type']}]--> {bp['target']}")
            print(f"  相似度: {bp['similarity']:.2f}")
            print(f"  置信度: {bp['confidence']:.2f}")
            print(f"  状态: {bp['status']}")
            print(f"  证据:\n{bp['evidence']}")
    
    diffuse.close()


if __name__ == '__main__':
    main()
