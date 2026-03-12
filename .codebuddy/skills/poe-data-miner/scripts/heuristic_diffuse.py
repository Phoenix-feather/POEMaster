#!/usr/bin/env python3
"""
启发式扩散能力模块（Phase 2: 验证约束扩散）

提供从已知边扩散发现相似边的能力，支持验证状态约束
"""

import sqlite3
import json
import logging
from typing import Dict, List, Any, Optional, Set, Tuple
from pathlib import Path
from datetime import datetime

# 导入关联图模块
try:
    from attribute_graph import AttributeGraph, NodeType, EdgeType, VerificationStatus, EvidenceType, DiscoveryMethod
    from heuristic_discovery import HeuristicDiscovery
    from heuristic_config_loader import get_config
except ImportError:
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from attribute_graph import AttributeGraph, NodeType, EdgeType, VerificationStatus, EvidenceType, DiscoveryMethod
    from heuristic_discovery import HeuristicDiscovery
    from heuristic_config_loader import get_config

logger = logging.getLogger(__name__)


class HeuristicDiffuse:
    """
    启发式扩散能力类（Phase 2: 验证约束）
    
    新增功能：
    1. 验证约束扩散 - 只从verified边扩散
    2. 验证状态感知 - 扩散时考虑验证状态
    3. 置信度传递 - 正确计算新边置信度
    4. 证据类型标注 - 设置evidence_type为DIFFUSION
    """
    
    def __init__(self, graph_db_path: str, verification_config: Optional[Dict[str, Any]] = None):
        """
        初始化扩散器
        
        Args:
            graph_db_path: 关联图数据库路径
            verification_config: 验证配置
        """
        self.graph_db_path = graph_db_path
        self.discovery = HeuristicDiscovery(graph_db_path, verification_config)
        self.conn: Optional[sqlite3.Connection] = None
        
        # 验证配置
        self.config = verification_config or {}
        self.min_source_confidence = self.config.get('min_source_confidence', 0.7)
        self.similarity_threshold = self.config.get('similarity_threshold', 0.7)
        
        # 加载配置
        self.similarity_weights = get_config('similarity_weights', {
            'types': 0.3,
            'properties': 0.4,
            'trigger_mechanisms': 0.2,
            'stats': 0.05,
            'constraints': 0.05
        })
        
        # 连接数据库
        self._connect()
        
        logger.info(f"HeuristicDiffuse初始化完成: {graph_db_path}")
    
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
                            similarity_threshold: Optional[float] = None,
                            require_verified: bool = True,
                            min_source_confidence: Optional[float] = None) -> List[Dict[str, Any]]:
        """
        从一条已知的绕过边，发现类似的绕过边（Phase 2: 验证约束）
        
        算法流程：
        1. 检查源边验证状态（如果require_verified=True）
        2. 提取已知绕过边的关键特征
        3. 寻找具有相似特征的实体
        4. 验证这些实体是否也能绕过
        5. 生成新的绕过边（带验证字段）
        
        Args:
            known_bypass_edge: 已知绕过边
            similarity_threshold: 相似度阈值（None使用配置值）
            require_verified: 是否要求源边已验证
            min_source_confidence: 源边最小置信度（None使用配置值）
            
        Returns:
            新发现的绕过边列表
        """
        source = known_bypass_edge.get('source', '')
        target = known_bypass_edge.get('target', '')
        edge_id = known_bypass_edge.get('edge_id')
        
        # 使用配置值
        if similarity_threshold is None:
            similarity_threshold = self.similarity_threshold
        if min_source_confidence is None:
            min_source_confidence = self.min_source_confidence
        
        # Phase 2: 验证约束检查
        if require_verified and edge_id:
            if not self._is_source_edge_verified(edge_id, min_source_confidence):
                logger.warning(f"源边 {edge_id} 未通过验证约束检查，跳过扩散")
                return []
        
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
                
                evidence_content = (
                    f"扩散源: {source}\n"
                    f"目标约束: {target}\n"
                    f"相似度: {similarity:.2f}\n"
                    f"源边ID: {edge_id}\n"
                    f"原始证据: {known_bypass_edge.get('evidence', 'N/A')}"
                )
                
                # Phase 2: 计算置信度（考虑源边置信度和相似度）
                source_confidence = known_bypass_edge.get('confidence', 1.0)
                new_confidence = similarity * source_confidence * 0.9  # 扩散衰减
                
                # 生成新边（Phase 2: 完整验证字段）
                new_edge = self.discovery.create_bypass_edge(
                    entity, target, evidence,
                    confidence=new_confidence,
                    evidence_type=EvidenceType.ANALOGY.value,
                    evidence_source=f"diffusion_from:{edge_id}" if edge_id else "diffusion",
                    evidence_content=evidence_content,
                    discovery_method=DiscoveryMethod.DIFFUSION.value,
                    initial_status=self._determine_diffused_status(new_confidence)
                )
                
                if new_edge:
                    new_edge['similarity'] = similarity
                    new_edge['source_entity'] = source
                    new_edge['source_confidence'] = source_confidence
                    new_bypasses.append(new_edge)
        
        logger.info(f"扩散完成: 源={source}, 目标={target}, 发现{len(new_bypasses)}条新边")
        return new_bypasses
    
    def _is_source_edge_verified(self, edge_id: int, min_confidence: float) -> bool:
        """
        检查源边是否通过验证约束
        
        Args:
            edge_id: 边ID
            min_confidence: 最小置信度
            
        Returns:
            是否通过验证
        """
        cursor = self.conn.cursor()
        
        cursor.execute('''
            SELECT status, confidence FROM graph_edges WHERE id = ?
        ''', (edge_id,))
        
        row = cursor.fetchone()
        if not row:
            return False
        
        status = row[0]
        confidence = row[1] or 0.0
        
        # 验证条件：状态为verified或pending，且置信度达标
        is_verified = status in [VerificationStatus.VERIFIED.value, VerificationStatus.PENDING.value]
        has_confidence = confidence >= min_confidence
        
        return is_verified and has_confidence
    
    def _determine_diffused_status(self, confidence: float) -> str:
        """
        根据置信度确定扩散边的初始状态
        
        Args:
            confidence: 置信度
            
        Returns:
            验证状态
        """
        if confidence >= 0.7:
            return VerificationStatus.PENDING.value
        else:
            return VerificationStatus.HYPOTHESIS.value
    
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
        
        # 从配置加载权重（而不是硬编码）
        weights = {
            'types': self.similarity_weights.get('types', 0.3),
            'properties': self.similarity_weights.get('properties', 0.4),
            'trigger_mechanisms': self.similarity_weights.get('trigger_mechanisms', 0.2),
            'stats': self.similarity_weights.get('stats', 0.05),
            'constraints': self.similarity_weights.get('constraints', 0.05)
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
                     max_depth: int = 2, similarity_threshold: Optional[float] = None,
                     require_verified: bool = True) -> List[Dict[str, Any]]:
        """
        深度扩散（递归扩散，Phase 2: 验证约束）
        
        Args:
            start_entity: 起始实体
            constraint: 约束节点
            max_depth: 最大扩散深度
            similarity_threshold: 相似度阈值
            require_verified: 是否要求源边已验证
            
        Returns:
            所有发现的绕过边
        """
        if similarity_threshold is None:
            similarity_threshold = self.similarity_threshold
        
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
                
                # 扩散（Phase 2: 验证约束）
                new_bypasses = self.diffuse_from_bypass(
                    virtual_bypass, 
                    similarity_threshold,
                    require_verified=False  # 深度扩散不检查虚拟边
                )
                
                for new_bypass in new_bypasses:
                    new_entity = new_bypass['source']
                    
                    if new_entity not in visited:
                        all_bypasses.append(new_bypass)
                        visited.add(new_entity)
                        next_layer.append(new_entity)
            
            current_layer = next_layer
        
        logger.info(f"深度扩散完成: 起始={start_entity}, 深度={max_depth}, 发现{len(all_bypasses)}条边")
        return all_bypasses
    
    # ========== Phase 2: 验证约束扩散方法 ==========
    
    def diffuse_from_verified_edges(self, edge_type: str = 'bypasses',
                                    max_edges: int = 10,
                                    similarity_threshold: Optional[float] = None,
                                    min_source_confidence: Optional[float] = None) -> List[Dict[str, Any]]:
        """
        从已验证边批量扩散（Phase 2新增）
        
        只从verified和pending状态的边扩散，确保扩散源头可信
        
        Args:
            edge_type: 边类型
            max_edges: 最大源边数量
            similarity_threshold: 相似度阈值
            min_source_confidence: 源边最小置信度
            
        Returns:
            新发现的边列表
        """
        if similarity_threshold is None:
            similarity_threshold = self.similarity_threshold
        if min_source_confidence is None:
            min_source_confidence = self.min_source_confidence
        
        cursor = self.conn.cursor()
        
        # 查询已验证边
        cursor.execute('''
            SELECT 
                e.id as edge_id,
                e.source_node, e.target_node, e.edge_type,
                e.confidence, e.evidence_type, e.evidence,
                n.name as source_name, n2.name as target_name
            FROM graph_edges e
            LEFT JOIN graph_nodes n ON e.source_node = n.id
            LEFT JOIN graph_nodes n2 ON e.target_node = n2.id
            WHERE e.edge_type = ?
                AND e.status IN (?, ?)
                AND e.confidence >= ?
            ORDER BY e.confidence DESC
            LIMIT ?
        ''', (
            edge_type,
            VerificationStatus.VERIFIED.value,
            VerificationStatus.PENDING.value,
            min_source_confidence,
            max_edges
        ))
        
        verified_edges = cursor.fetchall()
        
        logger.info(f"找到{len(verified_edges)}条已验证边作为扩散源")
        
        # 批量扩散
        all_new_edges = []
        seen_entities = set()
        
        for edge in verified_edges:
            bypass_edge = {
                'edge_id': edge['edge_id'],
                'source': edge['source_node'],
                'target': edge['target_node'],
                'confidence': edge['confidence'],
                'evidence_type': edge['evidence_type'],
                'evidence': edge['evidence']
            }
            
            new_edges = self.diffuse_from_bypass(
                bypass_edge,
                similarity_threshold,
                require_verified=True,
                min_source_confidence=min_source_confidence
            )
            
            for new_edge in new_edges:
                entity = new_edge['source']
                if entity not in seen_entities:
                    all_new_edges.append(new_edge)
                    seen_entities.add(entity)
        
        logger.info(f"从已验证边扩散完成，发现{len(all_new_edges)}条新边")
        return all_new_edges
    
    def diffuse_with_confidence_propagation(self, source_edge: Dict[str, Any],
                                           similarity_threshold: Optional[float] = None) -> List[Dict[str, Any]]:
        """
        带置信度传播的扩散（Phase 2新增）
        
        置信度传播公式：
        new_confidence = source_confidence * similarity * decay_factor
        
        Args:
            source_edge: 源边
            similarity_threshold: 相似度阈值
            
        Returns:
            新边列表
        """
        if similarity_threshold is None:
            similarity_threshold = self.similarity_threshold
        
        source_confidence = source_edge.get('confidence', 1.0)
        decay_factor = 0.9  # 扩散衰减因子
        
        # 标准扩散流程
        new_edges = self.diffuse_from_bypass(
            source_edge,
            similarity_threshold,
            require_verified=True
        )
        
        # 应用置信度传播
        for edge in new_edges:
            similarity = edge.get('similarity', 0.7)
            
            # 传播置信度
            propagated_confidence = source_confidence * similarity * decay_factor
            
            # 更新边
            cursor = self.conn.cursor()
            cursor.execute('''
                UPDATE graph_edges
                SET confidence = ?,
                    attributes = json_set(attributes, '$.propagated_confidence', ?)
                WHERE id = ?
            ''', (propagated_confidence, propagated_confidence, edge['edge_id']))
            
            edge['propagated_confidence'] = propagated_confidence
            edge['source_confidence'] = source_confidence
        
        self.conn.commit()
        
        logger.info(f"置信度传播完成: 源置信度={source_confidence:.2f}, 发现{len(new_edges)}条新边")
        return new_edges
    
    def get_diffusion_stats(self) -> Dict[str, Any]:
        """
        获取扩散统计信息（Phase 2新增）
        
        Returns:
            统计信息字典
        """
        cursor = self.conn.cursor()
        
        # 统计各状态的扩散边
        cursor.execute('''
            SELECT 
                discovery_method,
                status,
                COUNT(*) as count,
                AVG(confidence) as avg_confidence
            FROM graph_edges
            WHERE discovery_method = ?
            GROUP BY discovery_method, status
        ''', (DiscoveryMethod.DIFFUSION.value,))
        
        diffusion_stats = {}
        for row in cursor.fetchall():
            method = row[0]
            status = row[1]
            count = row[2]
            avg_conf = row[3] or 0.0
            
            if method not in diffusion_stats:
                diffusion_stats[method] = {}
            
            diffusion_stats[method][status] = {
                'count': count,
                'avg_confidence': avg_conf
            }
        
        # 统计可扩散源边
        cursor.execute('''
            SELECT COUNT(*)
            FROM graph_edges
            WHERE status IN (?, ?) AND confidence >= ?
        ''', (
            VerificationStatus.VERIFIED.value,
            VerificationStatus.PENDING.value,
            self.min_source_confidence
        ))
        
        available_sources = cursor.fetchone()[0]
        
        return {
            'diffusion_edges_by_status': diffusion_stats,
            'available_source_edges': available_sources,
            'config': {
                'similarity_threshold': self.similarity_threshold,
                'min_source_confidence': self.min_source_confidence
            }
        }


def main():
    """测试函数（Phase 2: 验证约束扩散）"""
    import argparse
    
    parser = argparse.ArgumentParser(description='启发式扩散测试（验证约束）')
    parser.add_argument('graph_db', help='关联图数据库路径')
    parser.add_argument('--diffuse', nargs=2, metavar=('SOURCE', 'TARGET'), 
                       help='从已知绕过边扩散')
    parser.add_argument('--diffuse-verified', action='store_true',
                       help='从已验证边批量扩散')
    parser.add_argument('--threshold', type=float, default=0.7, 
                       help='相似度阈值')
    parser.add_argument('--min-confidence', type=float, default=0.7,
                       help='源边最小置信度')
    parser.add_argument('--max-edges', type=int, default=10,
                       help='最大源边数量')
    parser.add_argument('--stats', action='store_true',
                       help='显示扩散统计')
    
    args = parser.parse_args()
    
    # 配置
    config = {
        'similarity_threshold': args.threshold,
        'min_source_confidence': args.min_confidence
    }
    
    diffuse = HeuristicDiffuse(args.graph_db, config)
    
    try:
        if args.diffuse:
            source, target = args.diffuse
            
            print(f"=== 从 {source} --[bypasses]--> {target} 扩散 ===\n")
            
            known_bypass = {
                'source': source,
                'target': target,
                'confidence': 1.0  # 假设源边置信度
            }
            
            new_bypasses = diffuse.diffuse_from_bypass(
                known_bypass, 
                args.threshold,
                require_verified=False
            )
            
            print(f"发现 {len(new_bypasses)} 条新的绕过边:\n")
            for bp in new_bypasses:
                print(f"  边 ID: {bp['edge_id']}")
                print(f"  {bp['source']} -> {bp['target']}")
                print(f"  相似度: {bp['similarity']:.2f}")
                print(f"  置信度: {bp['confidence']:.2f}")
                print(f"  状态: {bp['status']}")
                print(f"  证据类型: {bp['evidence_type']}")
                print(f"  发现方法: {bp['discovery_method']}\n")
        
        if args.diffuse_verified:
            print(f"=== 从已验证边批量扩散 (最小置信度={args.min_confidence}) ===\n")
            
            new_edges = diffuse.diffuse_from_verified_edges(
                edge_type='bypasses',
                max_edges=args.max_edges,
                similarity_threshold=args.threshold,
                min_source_confidence=args.min_confidence
            )
            
            print(f"发现 {len(new_edges)} 条新边:\n")
            for edge in new_edges[:10]:  # 只显示前10条
                print(f"  边 ID: {edge['edge_id']}")
                print(f"  {edge['source']} -> {edge['target']}")
                print(f"  相似度: {edge.get('similarity', 0):.2f}")
                print(f"  置信度: {edge['confidence']:.2f}")
                print(f"  状态: {edge['status']}\n")
            
            if len(new_edges) > 10:
                print(f"  ... 还有 {len(new_edges) - 10} 条边\n")
        
        if args.stats:
            print("=== 扩散统计信息 ===\n")
            
            stats = diffuse.get_diffusion_stats()
            
            print(f"可扩散源边数: {stats['available_source_edges']}")
            print(f"\n配置:")
            print(f"  相似度阈值: {stats['config']['similarity_threshold']}")
            print(f"  最小置信度: {stats['config']['min_source_confidence']}")
            
            print(f"\n扩散边统计:")
            for method, status_data in stats['diffusion_edges_by_status'].items():
                print(f"  方法: {method}")
                for status, data in status_data.items():
                    print(f"    {status}: {data['count']}条, 平均置信度={data['avg_confidence']:.2f}")
    
    finally:
        diffuse.close()


if __name__ == '__main__':
    main()
