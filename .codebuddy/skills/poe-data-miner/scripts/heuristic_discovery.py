#!/usr/bin/env python3
"""
启发式发现能力模块（Phase 2: 验证引导发现）

提供从零开始发现新关系的能力，支持验证状态感知
"""

import sqlite3
import json
import logging
from typing import Dict, List, Any, Optional, Set, Tuple
from pathlib import Path
from datetime import datetime
from collections import Counter

# 导入关联图模块
try:
    from attribute_graph import AttributeGraph, NodeType, EdgeType, VerificationStatus, EvidenceType, DiscoveryMethod
    from heuristic_query import HeuristicQuery
except ImportError:
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from attribute_graph import AttributeGraph, NodeType, EdgeType, VerificationStatus, EvidenceType, DiscoveryMethod
    from heuristic_query import HeuristicQuery

logger = logging.getLogger(__name__)


class HeuristicDiscovery:
    """
    启发式发现能力类（Phase 2: 验证引导）
    
    新增功能：
    1. 验证状态感知 - 使用pending知识作为发现线索
    2. 证据类型标注 - 正确设置evidence_type等字段
    3. 置信度计算 - 基于证据强度计算置信度
    4. 发现方法标注 - 设置discovery_method字段
    """
    
    def __init__(self, graph_db_path: str, verification_config: Optional[Dict[str, Any]] = None):
        """
        初始化发现器
        
        Args:
            graph_db_path: 关联图数据库路径
            verification_config: 验证配置
        """
        self.graph_db_path = graph_db_path
        self.query = HeuristicQuery(graph_db_path, verification_config)
        self.conn: Optional[sqlite3.Connection] = None
        
        # 验证配置
        self.config = verification_config or {}
        self.default_hypothesis_confidence = self.config.get('default_hypothesis_confidence', 0.3)
        self.default_pending_confidence = self.config.get('default_pending_confidence', 0.5)
        
        # 推理链记录
        self.reasoning_chain: List[Dict[str, Any]] = []
        
        # 连接数据库
        self._connect()
        
        logger.info(f"HeuristicDiscovery初始化完成: {graph_db_path}")
    
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
                          confidence: Optional[float] = None,
                          evidence_type: str = None,
                          evidence_source: str = None,
                          evidence_content: str = None,
                          discovery_method: str = None,
                          initial_status: str = None) -> Optional[Dict[str, Any]]:
        """
        创建绕过边（Phase 2: 完整验证字段）
        
        Args:
            source: 源节点ID
            target: 目标节点ID
            evidence: 证据描述（简短）
            confidence: 置信度（None则自动计算）
            evidence_type: 证据类型 (stat/code/pattern/analogy)
            evidence_source: 证据来源文件
            evidence_content: 证据详细内容
            discovery_method: 发现方法 (pattern/analogy/diffusion/heuristic)
            initial_status: 初始状态 (None则根据置信度自动确定)
            
        Returns:
            新边信息
        """
        cursor = self.conn.cursor()
        
        # 设置默认值
        if evidence_type is None:
            evidence_type = EvidenceType.ANALOGY.value
        
        if discovery_method is None:
            discovery_method = DiscoveryMethod.HEURISTIC.value
        
        if evidence_content is None:
            evidence_content = evidence
        
        # 根据证据类型计算置信度
        if confidence is None:
            confidence = self._calculate_confidence(evidence_type, discovery_method)
        
        # 根据置信度确定初始状态
        if initial_status is None:
            initial_status = self._determine_initial_status(confidence)
        
        try:
            cursor.execute('''
                INSERT INTO graph_edges (
                    source_node, target_node, edge_type, weight, attributes,
                    status, evidence, confidence, evidence_type, evidence_source,
                    evidence_content, discovery_method, created_at
                ) VALUES (?, ?, 'bypasses', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                source,
                target,
                confidence,
                json.dumps({
                    'confidence': confidence,
                    'discovery_method': discovery_method,
                    'evidence_type': evidence_type
                }, ensure_ascii=False),
                initial_status,
                evidence,
                confidence,
                evidence_type,
                evidence_source,
                evidence_content,
                discovery_method,
                datetime.now().isoformat()
            ))
            
            self.conn.commit()
            
            # 获取新插入的边ID
            cursor.execute('SELECT last_insert_rowid()')
            edge_id = cursor.fetchone()[0]
            
            logger.info(f"创建绕过边: {source} -> {target}, 状态={initial_status}, 置信度={confidence:.2f}")
            
            return {
                'edge_id': edge_id,
                'source': source,
                'target': target,
                'edge_type': 'bypasses',
                'status': initial_status,
                'confidence': confidence,
                'evidence': evidence,
                'evidence_type': evidence_type,
                'evidence_source': evidence_source,
                'evidence_content': evidence_content,
                'discovery_method': discovery_method
            }
        
        except Exception as e:
            logger.error(f"创建边失败: {e}")
            return None
    
    def _calculate_confidence(self, evidence_type: str, discovery_method: str) -> float:
        """
        根据证据类型和发现方法计算置信度
        
        Args:
            evidence_type: 证据类型
            discovery_method: 发现方法
            
        Returns:
            置信度 (0.0-1.0)
        """
        # 证据类型权重
        evidence_weights = {
            EvidenceType.STAT.value: 1.0,
            EvidenceType.CODE.value: 0.8,
            EvidenceType.PATTERN.value: 0.7,
            EvidenceType.ANALOGY.value: 0.5,
            EvidenceType.USER_INPUT.value: 1.0,
            EvidenceType.DATA_EXTRACTION.value: 1.0
        }
        
        # 发现方法权重
        method_weights = {
            DiscoveryMethod.DATA_EXTRACTION.value: 1.0,
            DiscoveryMethod.PATTERN.value: 0.7,
            DiscoveryMethod.ANALOGY.value: 0.5,
            DiscoveryMethod.DIFFUSION.value: 0.6,
            DiscoveryMethod.USER_INPUT.value: 1.0,
            DiscoveryMethod.HEURISTIC.value: 0.5
        }
        
        ev_weight = evidence_weights.get(evidence_type, 0.5)
        method_weight = method_weights.get(discovery_method, 0.5)
        
        # 综合置信度
        return (ev_weight * 0.6 + method_weight * 0.4) * 0.8  # 新发现的置信度不超过0.8
    
    def _determine_initial_status(self, confidence: float) -> str:
        """
        根据置信度确定初始验证状态
        
        Args:
            confidence: 置信度
            
        Returns:
            验证状态
        """
        if confidence >= 0.8:
            return VerificationStatus.PENDING.value  # 高置信度也需要验证
        elif confidence >= 0.5:
            return VerificationStatus.PENDING.value
        else:
            return VerificationStatus.HYPOTHESIS.value
    
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
    
    # ========== Phase 2: 验证引导发现方法 ==========
    
    def discover_from_pending_knowledge(self, max_discoveries: int = 10) -> List[Dict[str, Any]]:
        """
        从pending知识中发现新关系（Phase 2新增）
        
        策略：
        1. 查询所有pending状态的边
        2. 分析pending边的特征
        3. 寻找类似模式的实体
        4. 生成新假设
        
        Args:
            max_discoveries: 最大发现数量
            
        Returns:
            发现的新边列表
        """
        logger.info(f"开始从pending知识中发现新关系，最多{max_discoveries}条")
        
        self.reasoning_chain = []
        discoveries = []
        
        # Step 1: 查询pending边
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT 
                e.id, e.source_node, e.target_node, e.edge_type,
                e.confidence, e.evidence_type, e.evidence_content,
                n.name as source_name, n2.name as target_name
            FROM graph_edges e
            LEFT JOIN graph_nodes n ON e.source_node = n.id
            LEFT JOIN graph_nodes n2 ON e.target_node = n2.id
            WHERE e.status = ?
            ORDER BY e.confidence DESC
            LIMIT ?
        ''', (VerificationStatus.PENDING.value, max_discoveries * 2))
        
        pending_edges = cursor.fetchall()
        
        self.reasoning_chain.append({
            'step': 'query_pending',
            'description': f'找到{len(pending_edges)}条pending边'
        })
        
        # Step 2: 分析每条pending边，寻找类似实体
        for pending_edge in pending_edges:
            if len(discoveries) >= max_discoveries:
                break
            
            source = pending_edge['source_node']
            target = pending_edge['target_node']
            edge_type = pending_edge['edge_type']
            
            # 提取源实体特征
            source_features = self._extract_entity_features(source)
            
            # 寻找相似实体
            similar_entities = self._find_similar_entities_for_discovery(
                source_features, 
                exclude=[source],
                limit=3
            )
            
            # 为每个相似实体创建假设边
            for similar_entity, similarity in similar_entities:
                # 检查边是否已存在
                cursor.execute('''
                    SELECT COUNT(*) FROM graph_edges
                    WHERE source_node = ? AND target_node = ? AND edge_type = ?
                ''', (similar_entity, target, edge_type))
                
                if cursor.fetchone()[0] > 0:
                    continue  # 边已存在
                
                # 创建假设边
                evidence = f"基于pending知识 [{pending_edge['source_name']} -> {pending_edge['target_name']}] 类比推理"
                evidence_content = (
                    f"源实体: {pending_edge['source_name']}\n"
                    f"目标: {pending_edge['target_name']}\n"
                    f"相似度: {similarity:.2f}\n"
                    f"参考pending边ID: {pending_edge['id']}"
                )
                
                new_edge = self.create_bypass_edge(
                    similar_entity,
                    target,
                    evidence,
                    confidence=similarity * pending_edge['confidence'],
                    evidence_type=EvidenceType.ANALOGY.value,
                    evidence_source=f"pending_edge:{pending_edge['id']}",
                    evidence_content=evidence_content,
                    discovery_method=DiscoveryMethod.ANALOGY.value,
                    initial_status=VerificationStatus.HYPOTHESIS.value
                )
                
                if new_edge:
                    discoveries.append(new_edge)
                    
                    self.reasoning_chain.append({
                        'step': 'create_hypothesis',
                        'description': f"创建假设: {similar_entity} -> {target} (相似度{similarity:.2f})"
                    })
        
        logger.info(f"从pending知识中发现{len(discoveries)}条新边")
        return discoveries
    
    def _extract_entity_features(self, entity: str) -> Dict[str, List[str]]:
        """
        提取实体特征（用于发现）
        
        Args:
            entity: 实体ID
            
        Returns:
            特征字典
        """
        cursor = self.conn.cursor()
        
        features = {
            'types': [],
            'stats': [],
            'constraints': [],
            'properties': []
        }
        
        # 获取类型
        cursor.execute('''
            SELECT target_node FROM graph_edges
            WHERE source_node = ? AND edge_type = 'has_type'
        ''', (entity,))
        features['types'] = [row[0] for row in cursor.fetchall()]
        
        # 获取stats
        cursor.execute('''
            SELECT target_node FROM graph_edges
            WHERE source_node = ? AND edge_type = 'has_stat'
        ''', (entity,))
        features['stats'] = [row[0] for row in cursor.fetchall()]
        
        # 获取约束
        cursor.execute('''
            SELECT target_node FROM graph_edges
            WHERE source_node = ? AND edge_type = 'constrained_by'
        ''', (entity,))
        features['constraints'] = [row[0] for row in cursor.fetchall()]
        
        # 获取属性（通过implies边）
        for type_node in features['types']:
            cursor.execute('''
                SELECT target_node FROM graph_edges
                WHERE source_node = ? AND edge_type = 'implies'
            ''', (type_node,))
            features['properties'].extend([row[0] for row in cursor.fetchall()])
        
        # 去重
        features['properties'] = list(set(features['properties']))
        
        return features
    
    def _find_similar_entities_for_discovery(self, features: Dict[str, List[str]],
                                              exclude: List[str] = None,
                                              limit: int = 5) -> List[Tuple[str, float]]:
        """
        寻找相似实体（用于发现）
        
        Args:
            features: 参考特征
            exclude: 排除的实体
            limit: 返回数量限制
            
        Returns:
            相似实体列表 [(entity_id, similarity), ...]
        """
        cursor = self.conn.cursor()
        
        # 获取所有实体
        cursor.execute('''
            SELECT id FROM graph_nodes WHERE type = 'entity'
        ''')
        
        all_entities = [row[0] for row in cursor.fetchall()]
        
        if exclude:
            all_entities = [e for e in all_entities if e not in exclude]
        
        similar = []
        
        for entity in all_entities:
            entity_features = self._extract_entity_features(entity)
            
            # 计算相似度（简化版Jaccard）
            similarity = self._calculate_feature_similarity(features, entity_features)
            
            if similarity >= 0.5:  # 相似度阈值
                similar.append((entity, similarity))
        
        # 排序并返回top N
        similar.sort(key=lambda x: x[1], reverse=True)
        return similar[:limit]
    
    def _calculate_feature_similarity(self, f1: Dict[str, List[str]], 
                                      f2: Dict[str, List[str]]) -> float:
        """
        计算特征相似度
        
        Args:
            f1: 特征1
            f2: 特征2
            
        Returns:
            相似度 (0.0-1.0)
        """
        def jaccard(set1: Set[str], set2: Set[str]) -> float:
            if not set1 and not set2:
                return 1.0
            if not set1 or not set2:
                return 0.0
            intersection = len(set1 & set2)
            union = len(set1 | set2)
            return intersection / union if union > 0 else 0.0
        
        # 计算各维度相似度
        type_sim = jaccard(set(f1.get('types', [])), set(f2.get('types', [])))
        stat_sim = jaccard(set(f1.get('stats', [])), set(f2.get('stats', [])))
        prop_sim = jaccard(set(f1.get('properties', [])), set(f2.get('properties', [])))
        
        # 加权平均
        weights = {'types': 0.5, 'stats': 0.3, 'properties': 0.2}
        total_sim = (
            type_sim * weights['types'] +
            stat_sim * weights['stats'] +
            prop_sim * weights['properties']
        )
        
        return total_sim
    
    def discover_high_confidence_hypotheses(self, min_confidence: float = 0.7) -> List[Dict[str, Any]]:
        """
        发现高置信度假设并升级为pending（Phase 2新增）
        
        Args:
            min_confidence: 最小置信度阈值
            
        Returns:
            升级的边列表
        """
        cursor = self.conn.cursor()
        
        # 查询高置信度假设
        cursor.execute('''
            SELECT id, source_node, target_node, confidence
            FROM graph_edges
            WHERE status = ? AND confidence >= ?
            ORDER BY confidence DESC
        ''', (VerificationStatus.HYPOTHESIS.value, min_confidence))
        
        hypotheses = cursor.fetchall()
        
        upgraded = []
        
        for hypothesis in hypotheses:
            edge_id = hypothesis[0]
            
            # 升级为pending
            cursor.execute('''
                UPDATE graph_edges
                SET status = ?, last_verified = ?
                WHERE id = ?
            ''', (VerificationStatus.PENDING.value, datetime.now().isoformat(), edge_id))
            
            upgraded.append({
                'edge_id': edge_id,
                'source': hypothesis[1],
                'target': hypothesis[2],
                'confidence': hypothesis[3],
                'old_status': VerificationStatus.HYPOTHESIS.value,
                'new_status': VerificationStatus.PENDING.value
            })
        
        self.conn.commit()
        
        logger.info(f"升级{len(upgraded)}条高置信度假设为pending")
        return upgraded


def main():
    """测试函数（Phase 2: 验证引导发现）"""
    import argparse
    
    parser = argparse.ArgumentParser(description='启发式发现测试（验证感知）')
    parser.add_argument('graph_db', help='关联图数据库路径')
    parser.add_argument('--discover', help='发现绕过某个约束的路径')
    parser.add_argument('--discover-pending', action='store_true',
                       help='从pending知识发现新关系')
    parser.add_argument('--upgrade-hypotheses', action='store_true',
                       help='升级高置信度假设')
    parser.add_argument('--min-confidence', type=float, default=0.7,
                       help='最小置信度阈值')
    parser.add_argument('--max-discoveries', type=int, default=10,
                       help='最大发现数量')
    
    args = parser.parse_args()
    
    discovery = HeuristicDiscovery(args.graph_db)
    
    try:
        if args.discover:
            print(f"=== 开始发现绕过 {args.discover} 的路径 ===\n")
            
            bypasses = discovery.discover_bypass_paths(args.discover)
            
            print(f"\n发现 {len(bypasses)} 条绕过路径:")
            for bp in bypasses:
                print(f"\n  边 ID: {bp['edge_id']}")
                print(f"  {bp['source']} --[{bp['edge_type']}]--> {bp['target']}")
                print(f"  置信度: {bp['confidence']:.2f}")
                print(f"  状态: {bp['status']}")
                print(f"  证据类型: {bp['evidence_type']}")
                print(f"  发现方法: {bp['discovery_method']}")
                print(f"  证据: {bp['evidence']}")
            
            print("\n推理链:")
            for step in discovery.get_reasoning_chain():
                print(f"  [{step['step']}] {step['description']}")
        
        if args.discover_pending:
            print("=== 从pending知识发现新关系 ===\n")
            
            discoveries = discovery.discover_from_pending_knowledge(args.max_discoveries)
            
            print(f"\n发现 {len(discoveries)} 条新边:")
            for d in discoveries:
                print(f"\n  边 ID: {d['edge_id']}")
                print(f"  {d['source']} -> {d['target']}")
                print(f"  置信度: {d['confidence']:.2f}")
                print(f"  状态: {d['status']}")
                print(f"  证据类型: {d['evidence_type']}")
            
            print("\n推理链:")
            for step in discovery.get_reasoning_chain():
                print(f"  [{step['step']}] {step['description']}")
        
        if args.upgrade_hypotheses:
            print(f"=== 升级高置信度假设 (阈值={args.min_confidence}) ===\n")
            
            upgraded = discovery.discover_high_confidence_hypotheses(args.min_confidence)
            
            print(f"\n升级 {len(upgraded)} 条假设:")
            for u in upgraded:
                print(f"  边 ID {u['edge_id']}: {u['old_status']} -> {u['new_status']}")
    
    finally:
        discovery.close()


if __name__ == '__main__':
    main()
