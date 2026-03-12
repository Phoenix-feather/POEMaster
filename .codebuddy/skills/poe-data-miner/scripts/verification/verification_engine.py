"""
验证引擎

协调搜索器和评估器，执行完整的验证流程
"""

import logging
import sqlite3
from typing import Dict, List, Any, Optional
from pathlib import Path
from datetime import datetime
import json

# 导入验证组件
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from verification.pob_searcher import POBCodeSearcher
from verification.evidence_evaluator import EvidenceEvaluator, Evidence
from attribute_graph import AttributeGraph, VerificationStatus, EvidenceType

logger = logging.getLogger(__name__)


class VerificationEngine:
    """
    验证引擎
    
    职责：
    1. 协调POBCodeSearcher和EvidenceEvaluator
    2. 执行完整的验证流程
    3. 更新知识库状态
    4. 记录验证历史
    """
    
    def __init__(self, pob_data_path: str, graph_db_path: str, config: Optional[Dict[str, Any]] = None):
        """
        初始化验证引擎
        
        Args:
            pob_data_path: POB数据路径
            graph_db_path: 关联图数据库路径
            config: 配置字典
        """
        self.pob_data_path = Path(pob_data_path)
        self.graph_db_path = Path(graph_db_path)
        
        # 初始化组件
        self.searcher = POBCodeSearcher(str(pob_data_path))
        self.evaluator = EvidenceEvaluator(config)
        
        # 连接知识库
        self.graph = AttributeGraph(str(graph_db_path))
        
        logger.info(f"VerificationEngine初始化完成")
    
    def verify_knowledge(self, edge_id: int, auto_verify: bool = True) -> Dict[str, Any]:
        """
        验证单条知识
        
        Args:
            edge_id: 边ID
            auto_verify: 是否自动验证（强度≥0.8时自动验证）
            
        Returns:
            验证结果
        """
        logger.info(f"验证知识: edge_id={edge_id}")
        
        # 1. 获取边信息
        edge = self._get_edge(edge_id)
        if not edge:
            return {
                'success': False,
                'error': f'边 {edge_id} 不存在'
            }
        
        # 2. 执行三层搜索
        evidence_list = self._search_evidence(edge)
        
        # 3. 评估证据
        evaluation = self.evaluator.evaluate(evidence_list)
        
        # 4. 决定是否自动验证
        if auto_verify and evaluation['overall_strength'] >= 0.8:
            # 自动验证
            self._update_edge_status(
                edge_id=edge_id,
                new_status=evaluation['status'],
                confidence=evaluation['confidence'],
                evidence_list=evidence_list,
                verified_by='auto'
            )
            
            logger.info(f"自动验证完成: edge_id={edge_id}, status={evaluation['status']}")
        
        return {
            'success': True,
            'edge_id': edge_id,
            'edge_info': edge,
            'evidence_list': [e.to_dict() for e in evidence_list],
            'evaluation': evaluation,
            'auto_verified': auto_verify and evaluation['overall_strength'] >= 0.8
        }
    
    def verify_implication(self, source: str, target: str, edge_type: str = 'implies',
                          auto_verify: bool = True) -> Dict[str, Any]:
        """
        验证隐含关系并创建边
        
        Args:
            source: 源节点
            target: 目标节点
            edge_type: 边类型
            auto_verify: 是否自动验证
            
        Returns:
            验证结果
        """
        logger.info(f"验证隐含关系: {source} --[{edge_type}]--> {target}")
        
        # 1. 执行三层搜索
        evidence_list = self._search_implication_evidence(source, target)
        
        # 2. 评估证据
        evaluation = self.evaluator.evaluate(evidence_list)
        
        # 3. 创建边
        edge_id = self._create_edge(
            source=source,
            target=target,
            edge_type=edge_type,
            status=evaluation['status'],
            confidence=evaluation['confidence'],
            evidence_list=evidence_list,
            verified_by='auto' if auto_verify and evaluation['overall_strength'] >= 0.8 else 'pending'
        )
        
        return {
            'success': True,
            'edge_id': edge_id,
            'source': source,
            'target': target,
            'edge_type': edge_type,
            'evidence_list': [e.to_dict() for e in evidence_list],
            'evaluation': evaluation,
            'auto_verified': auto_verify and evaluation['overall_strength'] >= 0.8
        }
    
    def batch_verify(self, edge_ids: List[int], auto_verify_threshold: float = 0.8) -> Dict[str, Any]:
        """
        批量验证知识
        
        Args:
            edge_ids: 边ID列表
            auto_verify_threshold: 自动验证阈值
            
        Returns:
            批量验证结果
        """
        logger.info(f"批量验证: {len(edge_ids)}条知识")
        
        results = {
            'total': len(edge_ids),
            'verified': 0,
            'pending': 0,
            'hypothesis': 0,
            'rejected': 0,
            'errors': 0,
            'details': []
        }
        
        for edge_id in edge_ids:
            try:
                result = self.verify_knowledge(edge_id, auto_verify=True)
                
                if result['success']:
                    status = result['evaluation']['status']
                    
                    if status == VerificationStatus.VERIFIED.value:
                        results['verified'] += 1
                    elif status == VerificationStatus.PENDING.value:
                        results['pending'] += 1
                    elif status == VerificationStatus.HYPOTHESIS.value:
                        results['hypothesis'] += 1
                    else:
                        results['rejected'] += 1
                    
                    results['details'].append({
                        'edge_id': edge_id,
                        'status': status,
                        'strength': result['evaluation']['overall_strength']
                    })
                else:
                    results['errors'] += 1
                    
            except Exception as e:
                logger.error(f"验证失败 edge_id={edge_id}: {e}")
                results['errors'] += 1
        
        logger.info(f"批量验证完成: verified={results['verified']}, pending={results['pending']}")
        
        return results
    
    def user_verify(self, edge_id: int, decision: str, reason: str = None) -> Dict[str, Any]:
        """
        用户验证
        
        Args:
            edge_id: 边ID
            decision: 决策（accept/reject）
            reason: 原因
            
        Returns:
            验证结果
        """
        logger.info(f"用户验证: edge_id={edge_id}, decision={decision}")
        
        # 获取边信息
        edge = self._get_edge(edge_id)
        if not edge:
            return {
                'success': False,
                'error': f'边 {edge_id} 不存在'
            }
        
        # 确定新状态
        if decision == 'accept':
            new_status = VerificationStatus.VERIFIED.value
            new_confidence = 1.0
        elif decision == 'reject':
            new_status = VerificationStatus.REJECTED.value
            new_confidence = 0.0
        else:
            return {
                'success': False,
                'error': f'无效的决策: {decision}'
            }
        
        # 更新状态
        self._update_edge_status(
            edge_id=edge_id,
            new_status=new_status,
            confidence=new_confidence,
            evidence_list=None,
            verified_by='user',
            reason=reason
        )
        
        return {
            'success': True,
            'edge_id': edge_id,
            'old_status': edge['status'],
            'new_status': new_status,
            'decision': decision,
            'reason': reason
        }
    
    def _get_edge(self, edge_id: int) -> Optional[Dict[str, Any]]:
        """获取边信息"""
        cursor = self.graph.conn.cursor()
        
        row = cursor.execute(
            'SELECT * FROM graph_edges WHERE id = ?',
            (edge_id,)
        ).fetchone()
        
        if row:
            return dict(row)
        
        return None
    
    def _search_evidence(self, edge: Dict[str, Any]) -> List[Evidence]:
        """
        搜索边的证据
        
        Args:
            edge: 边信息
            
        Returns:
            证据列表
        """
        evidence_list = []
        
        source = edge['source_node']
        target = edge['target_node']
        edge_type = edge['edge_type']
        
        # Layer 1: 搜索stat定义
        if edge_type in ['has_stat', 'implies']:
            stat_result = self.searcher.search_stat_definition(target)
            
            if stat_result['found']:
                evidence_list.append(Evidence(
                    type=EvidenceType.STAT.value,
                    strength=1.0,
                    source=stat_result['source'] or 'StatDescriptions',
                    content=f"Stat {target} 定义",
                    layer=1,
                    confidence=1.0
                ))
        
        # Layer 2: 搜索约束关系
        if edge_type in ['has_type', 'requires', 'excludes']:
            constraint_result = self.searcher.search_skilltype_constraint(target)
            
            if constraint_result['found']:
                evidence_list.append(Evidence(
                    type=EvidenceType.CODE.value,
                    strength=0.8,
                    source='SkillType constraint',
                    content=f"{target} 约束关系",
                    layer=2,
                    confidence=1.0
                ))
        
        # Layer 2: 搜索函数逻辑
        related_functions = self.searcher._find_related_functions(source, target)
        for func_name in related_functions[:3]:  # 限制数量
            func_result = self.searcher.search_function_logic(func_name)
            
            if func_result['found']:
                evidence_list.append(Evidence(
                    type=EvidenceType.CODE.value,
                    strength=0.8,
                    source=func_result['definition']['file_path'],
                    content=f"函数 {func_name}",
                    layer=2,
                    confidence=1.0
                ))
        
        # Layer 3: 语义推断
        semantic_result = self.searcher.search_semantic_similarity(source, top_k=10)
        
        if semantic_result['found']:
            # 如果有高相似度实体，作为证据
            high_sim_entities = [
                e for e in semantic_result['similar_entities']
                if e['similarity'] > 0.7
            ]
            
            if high_sim_entities:
                evidence_list.append(Evidence(
                    type=EvidenceType.ANALOGY.value,
                    strength=0.5,
                    source='Semantic similarity',
                    content=f"相似实体: {[e['entity'] for e in high_sim_entities[:3]]}",
                    layer=3,
                    confidence=0.8
                ))
        
        return evidence_list
    
    def _search_implication_evidence(self, source: str, target: str) -> List[Evidence]:
        """
        搜索隐含关系的证据
        
        Args:
            source: 源
            target: 目标
            
        Returns:
            证据列表
        """
        # 使用POBCodeSearcher的verify_implication方法
        result = self.searcher.verify_implication(source, target)
        
        evidence_list = []
        
        for ev in result.get('evidence', []):
            evidence_list.append(Evidence(
                type=ev['type'],
                strength=ev['strength'],
                source=ev['source'],
                content=ev['content'],
                layer=ev['layer'],
                confidence=1.0
            ))
        
        return evidence_list
    
    def _create_edge(self, source: str, target: str, edge_type: str,
                     status: str, confidence: float, evidence_list: List[Evidence],
                     verified_by: str) -> int:
        """
        创建边
        
        Returns:
            边ID
        """
        cursor = self.graph.conn.cursor()
        
        # 确保节点存在
        cursor.execute('''
            INSERT OR IGNORE INTO graph_nodes (id, type, name)
            VALUES (?, 'type_node', ?)
        ''', (source, source))
        
        cursor.execute('''
            INSERT OR IGNORE INTO graph_nodes (id, type, name)
            VALUES (?, 'property_node', ?)
        ''', (target, target))
        
        # 创建边
        evidence_content = json.dumps([e.to_dict() for e in evidence_list]) if evidence_list else None
        
        cursor.execute('''
            INSERT INTO graph_edges 
            (source_node, target_node, edge_type, status, confidence, 
             evidence_type, evidence_content, verified_by, last_verified)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            source, target, edge_type, status, confidence,
            evidence_list[0].type if evidence_list else None,
            evidence_content,
            verified_by,
            datetime.now().isoformat()
        ))
        
        edge_id = cursor.lastrowid
        
        # 记录验证历史
        self._record_verification_history(
            edge_id=edge_id,
            old_status=None,
            new_status=status,
            old_confidence=None,
            new_confidence=confidence,
            evidence_list=evidence_list,
            verified_by=verified_by
        )
        
        self.graph.conn.commit()
        
        return edge_id
    
    def _update_edge_status(self, edge_id: int, new_status: str, confidence: float,
                           evidence_list: Optional[List[Evidence]], verified_by: str,
                           reason: str = None):
        """
        更新边状态
        
        Args:
            edge_id: 边ID
            new_status: 新状态
            confidence: 置信度
            evidence_list: 证据列表
            verified_by: 验证者
            reason: 原因
        """
        cursor = self.graph.conn.cursor()
        
        # 获取旧状态
        old_edge = self._get_edge(edge_id)
        old_status = old_edge['status'] if old_edge else None
        old_confidence = old_edge['confidence'] if old_edge else None
        
        # 更新边
        evidence_content = json.dumps([e.to_dict() for e in evidence_list]) if evidence_list else None
        
        cursor.execute('''
            UPDATE graph_edges 
            SET status = ?, confidence = ?, 
                evidence_type = ?, evidence_content = ?,
                last_verified = ?, verified_by = ?
            WHERE id = ?
        ''', (
            new_status, confidence,
            evidence_list[0].type if evidence_list else None,
            evidence_content,
            datetime.now().isoformat(),
            verified_by,
            edge_id
        ))
        
        # 记录验证历史
        self._record_verification_history(
            edge_id=edge_id,
            old_status=old_status,
            new_status=new_status,
            old_confidence=old_confidence,
            new_confidence=confidence,
            evidence_list=evidence_list,
            verified_by=verified_by,
            reason=reason
        )
        
        self.graph.conn.commit()
    
    def _record_verification_history(self, edge_id: int, old_status: Optional[str],
                                     new_status: str, old_confidence: Optional[float],
                                     new_confidence: float, evidence_list: Optional[List[Evidence]],
                                     verified_by: str, reason: str = None):
        """
        记录验证历史
        
        Args:
            edge_id: 边ID
            old_status: 旧状态
            new_status: 新状态
            old_confidence: 旧置信度
            new_confidence: 新置信度
            evidence_list: 证据列表
            verified_by: 验证者
            reason: 原因
        """
        cursor = self.graph.conn.cursor()
        
        evidence_type = evidence_list[0].type if evidence_list else None
        evidence_source = evidence_list[0].source if evidence_list else None
        evidence_content = json.dumps([e.to_dict() for e in evidence_list]) if evidence_list else None
        
        cursor.execute('''
            INSERT INTO verification_history 
            (edge_id, old_status, new_status, old_confidence, new_confidence,
             evidence_type, evidence_source, evidence_content, reason, verified_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            edge_id, old_status, new_status, old_confidence, new_confidence,
            evidence_type, evidence_source, evidence_content, reason, verified_by
        ))
    
    def get_verification_stats(self) -> Dict[str, Any]:
        """
        获取验证统计
        
        Returns:
            统计信息
        """
        cursor = self.graph.conn.cursor()
        
        # 总数
        total = cursor.execute('SELECT COUNT(*) FROM graph_edges').fetchone()[0]
        
        # 按状态统计
        cursor.execute('''
            SELECT status, COUNT(*) as count 
            FROM graph_edges 
            GROUP BY status
        ''')
        
        by_status = {row['status']: row['count'] for row in cursor.fetchall()}
        
        # 平均置信度
        avg_confidence = cursor.execute('SELECT AVG(confidence) FROM graph_edges').fetchone()[0] or 0.0
        
        # 验证历史数量
        history_count = cursor.execute('SELECT COUNT(*) FROM verification_history').fetchone()[0]
        
        return {
            'total_knowledge': total,
            'by_status': by_status,
            'verified_rate': by_status.get('verified', 0) / total if total > 0 else 0,
            'average_confidence': avg_confidence,
            'verification_history_count': history_count
        }
    
    def close(self):
        """关闭连接"""
        if self.searcher:
            self.searcher.close()
        
        if self.graph:
            self.graph.conn.close()
        
        logger.info("VerificationEngine已关闭")
    
    def __enter__(self):
        """上下文管理器入口"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.close()
