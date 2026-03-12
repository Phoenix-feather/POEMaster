"""
验证感知查询引擎

集成验证引擎到查询流程，实时验证pending知识
"""

import logging
import asyncio
from typing import Dict, List, Any, Optional, Callable
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import time

# 导入验证组件
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from verification.verification_engine import VerificationEngine
from attribute_graph import AttributeGraph, VerificationStatus

logger = logging.getLogger(__name__)


class VerificationAwareQueryEngine:
    """
    验证感知查询引擎
    
    职责：
    1. 在查询时自动验证pending知识
    2. 实时调整置信度和权重
    3. 异步验证队列管理
    4. 动态更新知识状态
    """
    
    def __init__(self, pob_data_path: str, graph_db_path: str, config: Optional[Dict[str, Any]] = None):
        """
        初始化验证感知查询引擎
        
        Args:
            pob_data_path: POB数据路径
            graph_db_path: 关联图数据库路径
            config: 配置字典
        """
        self.pob_data_path = Path(pob_data_path)
        self.graph_db_path = Path(graph_db_path)
        
        # 加载配置
        self.config = config or {}
        self.auto_verify_threshold = self.config.get('auto_verify_threshold', 0.8)
        self.max_async_verifications = self.config.get('max_async_verifications', 10)
        self.verification_timeout = self.config.get('verification_timeout', 2.0)
        
        # 初始化验证引擎
        self.verification_engine = VerificationEngine(str(pob_data_path), str(graph_db_path), config)
        
        # 初始化关联图
        self.graph = AttributeGraph(str(graph_db_path))
        
        # 异步验证队列
        self.verification_queue = []
        self.executor = ThreadPoolExecutor(max_workers=2)
        
        logger.info(f"VerificationAwareQueryEngine初始化完成")
    
    def query_with_verification(self, query_params: Dict[str, Any], 
                                auto_verify: bool = True) -> Dict[str, Any]:
        """
        验证感知查询
        
        Args:
            query_params: 查询参数
            auto_verify: 是否自动验证pending知识
            
        Returns:
            查询结果，包含verified和pending两个列表
        """
        logger.info(f"执行验证感知查询: {query_params}")
        
        start_time = time.time()
        
        # 1. 查询verified知识
        verified_results = self._query_verified(query_params)
        
        # 2. 查询pending知识
        pending_results = self._query_pending(query_params)
        
        # 3. 如果启用自动验证，验证pending知识
        upgraded_results = []
        still_pending = []
        
        if auto_verify and pending_results:
            # 筛选需要验证的pending知识
            to_verify = self._select_for_verification(pending_results)
            
            # 异步验证
            verification_results = self._async_verify_batch(to_verify)
            
            # 分类结果
            for i, result in enumerate(verification_results):
                if result['success'] and result.get('auto_verified'):
                    upgraded_results.append(pending_results[i])
                    # 更新为verified状态
                    pending_results[i]['status'] = VerificationStatus.VERIFIED.value
                    pending_results[i]['confidence'] = 1.0
                else:
                    still_pending.append(pending_results[i])
        else:
            still_pending = pending_results
        
        # 4. 组合结果
        all_verified = verified_results + upgraded_results
        
        duration = time.time() - start_time
        
        return {
            'verified': all_verified,
            'pending': still_pending,
            'hypothesis': [],  # 查询阶段不返回假设
            'summary': {
                'verified_count': len(all_verified),
                'pending_count': len(still_pending),
                'upgraded_count': len(upgraded_results),
                'verification_performed': len(to_verify) if auto_verify and pending_results else 0,
                'query_duration': duration
            }
        }
    
    def query_by_type(self, entity_type: str, auto_verify: bool = True) -> Dict[str, Any]:
        """
        按类型查询（验证感知）
        
        Args:
            entity_type: 实体类型
            auto_verify: 是否自动验证
            
        Returns:
            查询结果
        """
        query_params = {
            'query_type': 'by_type',
            'entity_type': entity_type
        }
        
        return self.query_with_verification(query_params, auto_verify)
    
    def query_by_tag(self, tag: str, auto_verify: bool = True) -> Dict[str, Any]:
        """
        按标签查询（验证感知）
        
        Args:
            tag: 标签
            auto_verify: 是否自动验证
            
        Returns:
            查询结果
        """
        query_params = {
            'query_type': 'by_tag',
            'tag': tag
        }
        
        return self.query_with_verification(query_params, auto_verify)
    
    def query_bypass_paths(self, constraint: str, auto_verify: bool = True) -> Dict[str, Any]:
        """
        查询绕过路径（验证感知）
        
        Args:
            constraint: 约束条件
            auto_verify: 是否自动验证
            
        Returns:
            查询结果
        """
        query_params = {
            'query_type': 'bypass_paths',
            'constraint': constraint
        }
        
        return self.query_with_verification(query_params, auto_verify)
    
    def _query_verified(self, query_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """查询verified知识"""
        cursor = self.graph.conn.cursor()
        
        results = []
        
        # 根据查询类型构建SQL
        query_type = query_params.get('query_type')
        
        if query_type == 'by_type':
            entity_type = query_params['entity_type']
            
            rows = cursor.execute('''
                SELECT e.*, n.name as source_name, n2.name as target_name
                FROM graph_edges e
                JOIN graph_nodes n ON e.source_node = n.id
                JOIN graph_nodes n2 ON e.target_node = n2.id
                WHERE n.type = ? AND e.status = ?
            ''', (entity_type, VerificationStatus.VERIFIED.value)).fetchall()
            
            results = [dict(row) for row in rows]
        
        elif query_type == 'by_tag':
            # 通过属性或节点名查找
            tag = query_params['tag']
            
            rows = cursor.execute('''
                SELECT e.*, n.name as source_name, n2.name as target_name
                FROM graph_edges e
                JOIN graph_nodes n ON e.source_node = n.id
                JOIN graph_nodes n2 ON e.target_node = n2.id
                WHERE (n.name LIKE ? OR e.attributes LIKE ?) AND e.status = ?
            ''', (f'%{tag}%', f'%{tag}%', VerificationStatus.VERIFIED.value)).fetchall()
            
            results = [dict(row) for row in rows]
        
        elif query_type == 'bypass_paths':
            # 查询绕过边
            constraint = query_params['constraint']
            
            rows = cursor.execute('''
                SELECT e.*, n.name as source_name, n2.name as target_name
                FROM graph_edges e
                JOIN graph_nodes n ON e.source_node = n.id
                JOIN graph_nodes n2 ON e.target_node = n2.id
                WHERE e.edge_type = 'bypasses' 
                AND n2.name LIKE ? 
                AND e.status = ?
            ''', (f'%{constraint}%', VerificationStatus.VERIFIED.value)).fetchall()
            
            results = [dict(row) for row in rows]
        
        else:
            # 通用查询
            rows = cursor.execute('''
                SELECT e.*, n.name as source_name, n2.name as target_name
                FROM graph_edges e
                JOIN graph_nodes n ON e.source_node = n.id
                JOIN graph_nodes n2 ON e.target_node = n2.id
                WHERE e.status = ?
            ''', (VerificationStatus.VERIFIED.value,)).fetchall()
            
            results = [dict(row) for row in rows]
        
        return results
    
    def _query_pending(self, query_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """查询pending知识"""
        cursor = self.graph.conn.cursor()
        
        results = []
        
        query_type = query_params.get('query_type')
        
        if query_type == 'by_type':
            entity_type = query_params['entity_type']
            
            rows = cursor.execute('''
                SELECT e.*, n.name as source_name, n2.name as target_name
                FROM graph_edges e
                JOIN graph_nodes n ON e.source_node = n.id
                JOIN graph_nodes n2 ON e.target_node = n2.id
                WHERE n.type = ? AND e.status = ?
            ''', (entity_type, VerificationStatus.PENDING.value)).fetchall()
            
            results = [dict(row) for row in rows]
        
        elif query_type == 'by_tag':
            tag = query_params['tag']
            
            rows = cursor.execute('''
                SELECT e.*, n.name as source_name, n2.name as target_name
                FROM graph_edges e
                JOIN graph_nodes n ON e.source_node = n.id
                JOIN graph_nodes n2 ON e.target_node = n2.id
                WHERE (n.name LIKE ? OR e.attributes LIKE ?) AND e.status = ?
            ''', (f'%{tag}%', f'%{tag}%', VerificationStatus.PENDING.value)).fetchall()
            
            results = [dict(row) for row in rows]
        
        elif query_type == 'bypass_paths':
            constraint = query_params['constraint']
            
            rows = cursor.execute('''
                SELECT e.*, n.name as source_name, n2.name as target_name
                FROM graph_edges e
                JOIN graph_nodes n ON e.source_node = n.id
                JOIN graph_nodes n2 ON e.target_node = n2.id
                WHERE e.edge_type = 'bypasses' 
                AND n2.name LIKE ? 
                AND e.status = ?
            ''', (f'%{constraint}%', VerificationStatus.PENDING.value)).fetchall()
            
            results = [dict(row) for row in rows]
        
        else:
            rows = cursor.execute('''
                SELECT e.*, n.name as source_name, n2.name as target_name
                FROM graph_edges e
                JOIN graph_nodes n ON e.source_node = n.id
                JOIN graph_nodes n2 ON e.target_node = n2.id
                WHERE e.status = ?
            ''', (VerificationStatus.PENDING.value,)).fetchall()
            
            results = [dict(row) for row in rows]
        
        return results
    
    def _select_for_verification(self, pending_results: List[Dict[str, Any]]) -> List[int]:
        """
        选择需要验证的pending知识
        
        策略：
        1. 从未验证过的优先
        2. 高影响度的优先
        3. 查询频率高的优先
        
        Args:
            pending_results: pending知识列表
            
        Returns:
            需要验证的边ID列表
        """
        to_verify = []
        
        for result in pending_results[:self.max_async_verifications]:
            edge_id = result['id']
            
            # 检查是否需要验证
            should_verify = False
            
            # 1. 从未验证过
            if result.get('last_verified') is None:
                should_verify = True
            
            # 2. 高影响度（通过边的连接数判断）
            elif self._get_impact_score(edge_id) > 5:
                should_verify = True
            
            # 3. 查询频率（通过验证历史判断）
            elif self._get_query_count(edge_id) > 3:
                should_verify = True
            
            if should_verify:
                to_verify.append(edge_id)
        
        return to_verify
    
    def _async_verify_batch(self, edge_ids: List[int]) -> List[Dict[str, Any]]:
        """
        异步批量验证
        
        Args:
            edge_ids: 边ID列表
            
        Returns:
            验证结果列表
        """
        logger.info(f"异步验证 {len(edge_ids)} 条知识")
        
        results = []
        
        # 使用线程池执行验证
        futures = []
        for edge_id in edge_ids:
            future = self.executor.submit(
                self.verification_engine.verify_knowledge,
                edge_id,
                True  # auto_verify
            )
            futures.append(future)
        
        # 等待结果（带超时）
        for future in futures:
            try:
                result = future.result(timeout=self.verification_timeout)
                results.append(result)
            except Exception as e:
                logger.error(f"验证超时或失败: {e}")
                results.append({
                    'success': False,
                    'error': str(e)
                })
        
        return results
    
    def _get_impact_score(self, edge_id: int) -> int:
        """获取边的影响分数"""
        cursor = self.graph.conn.cursor()
        
        # 计算连接数作为影响分数
        row = cursor.execute('''
            SELECT source_node, target_node FROM graph_edges WHERE id = ?
        ''', (edge_id,)).fetchone()
        
        if not row:
            return 0
        
        source = row['source_node']
        target = row['target_node']
        
        # 统计相关边的数量
        count = cursor.execute('''
            SELECT COUNT(*) FROM graph_edges 
            WHERE source_node = ? OR target_node = ? 
            OR source_node = ? OR target_node = ?
        ''', (source, source, target, target)).fetchone()[0]
        
        return count
    
    def _get_query_count(self, edge_id: int) -> int:
        """获取边的查询次数（通过验证历史）"""
        cursor = self.graph.conn.cursor()
        
        count = cursor.execute('''
            SELECT COUNT(*) FROM verification_history WHERE edge_id = ?
        ''', (edge_id,)).fetchone()[0]
        
        return count
    
    def get_pending_queue_stats(self) -> Dict[str, Any]:
        """
        获取待验证队列统计
        
        Returns:
            统计信息
        """
        cursor = self.graph.conn.cursor()
        
        # 总数
        total = cursor.execute(
            'SELECT COUNT(*) FROM graph_edges WHERE status = ?',
            (VerificationStatus.PENDING.value,)
        ).fetchone()[0]
        
        # 从未验证的
        never_verified = cursor.execute('''
            SELECT COUNT(*) FROM graph_edges 
            WHERE status = ? AND last_verified IS NULL
        ''', (VerificationStatus.PENDING.value,)).fetchone()[0]
        
        # 高影响的
        high_impact = 0
        pending_rows = cursor.execute(
            'SELECT id FROM graph_edges WHERE status = ?',
            (VerificationStatus.PENDING.value,)
        ).fetchall()
        
        for row in pending_rows:
            if self._get_impact_score(row['id']) > 5:
                high_impact += 1
        
        return {
            'total_pending': total,
            'never_verified': never_verified,
            'high_impact': high_impact,
            'queue_capacity': self.max_async_verifications
        }
    
    def close(self):
        """关闭连接"""
        if self.verification_engine:
            self.verification_engine.close()
        
        if self.graph:
            self.graph.conn.close()
        
        if self.executor:
            self.executor.shutdown(wait=False)
        
        logger.info("VerificationAwareQueryEngine已关闭")
    
    def __enter__(self):
        """上下文管理器入口"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.close()
