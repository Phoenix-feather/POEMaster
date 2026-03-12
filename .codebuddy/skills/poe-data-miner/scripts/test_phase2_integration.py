#!/usr/bin/env python3
"""
Phase 2集成测试：验证感知启发式推理

测试三个模块的集成：
1. HeuristicQuery - 验证感知查询
2. HeuristicDiscovery - 验证引导发现
3. HeuristicDiffuse - 验证约束扩散
"""

import unittest
import sqlite3
import tempfile
import shutil
from pathlib import Path
import sys

# 添加scripts目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from heuristic_query import HeuristicQuery
from heuristic_discovery import HeuristicDiscovery
from heuristic_diffuse import HeuristicDiffuse
from attribute_graph import AttributeGraph, NodeType, EdgeType, VerificationStatus, EvidenceType, DiscoveryMethod


class TestPhase2Integration(unittest.TestCase):
    """Phase 2集成测试类"""
    
    @classmethod
    def setUpClass(cls):
        """设置测试数据库"""
        cls.temp_dir = tempfile.mkdtemp()
        cls.graph_db_path = str(Path(cls.temp_dir) / 'test_graph.db')
        
        # 初始化关联图
        cls.graph = AttributeGraph(cls.graph_db_path)
        
        # 插入测试数据
        cls._insert_test_data()
        
        print(f"\n测试数据库: {cls.graph_db_path}")
    
    @classmethod
    def tearDownClass(cls):
        """清理测试数据库"""
        if hasattr(cls, 'graph'):
            cls.graph.conn.close()
        
        if Path(cls.temp_dir).exists():
            shutil.rmtree(cls.temp_dir)
    
    @classmethod
    def _insert_test_data(cls):
        """插入测试数据"""
        cursor = cls.graph.conn.cursor()
        
        # 插入节点
        test_nodes = [
            ('skill1', NodeType.ENTITY.value, 'Meta Skill 1'),
            ('skill2', NodeType.ENTITY.value, 'Meta Skill 2'),
            ('skill3', NodeType.ENTITY.value, 'Meta Skill 3'),
            ('skill4', NodeType.ENTITY.value, 'Regular Skill'),
            ('constraint1', NodeType.CONSTRAINT.value, 'Meta Tag Constraint'),
            ('type_meta', NodeType.TYPE_NODE.value, 'Meta'),
            ('type_triggered', NodeType.TYPE_NODE.value, 'Triggered'),
            ('trigger_mech', NodeType.TRIGGER_MECHANISM.value, 'MetaTrigger'),
        ]
        
        for node_id, node_type, name in test_nodes:
            cursor.execute('''
                INSERT OR REPLACE INTO graph_nodes (id, type, name)
                VALUES (?, ?, ?)
            ''', (node_id, node_type, name))
        
        # 插入边（包含验证字段）
        test_edges = [
            # skill1 -> constraint1 (verified bypass)
            ('skill1', 'constraint1', EdgeType.BYPASSES.value, 
             VerificationStatus.VERIFIED.value, 0.95, 
             EvidenceType.CODE.value, DiscoveryMethod.DATA_EXTRACTION.value),
            
            # skill2 -> constraint1 (pending bypass)
            ('skill2', 'constraint1', EdgeType.BYPASSES.value,
             VerificationStatus.PENDING.value, 0.75,
             EvidenceType.PATTERN.value, DiscoveryMethod.HEURISTIC.value),
            
            # skill3 -> constraint1 (hypothesis bypass)
            ('skill3', 'constraint1', EdgeType.BYPASSES.value,
             VerificationStatus.HYPOTHESIS.value, 0.45,
             EvidenceType.ANALOGY.value, DiscoveryMethod.ANALOGY.value),
            
            # 类型关系
            ('skill1', 'type_meta', EdgeType.HAS_TYPE.value,
             VerificationStatus.VERIFIED.value, 1.0,
             EvidenceType.DATA_EXTRACTION.value, DiscoveryMethod.DATA_EXTRACTION.value),
            
            ('skill2', 'type_meta', EdgeType.HAS_TYPE.value,
             VerificationStatus.VERIFIED.value, 1.0,
             EvidenceType.DATA_EXTRACTION.value, DiscoveryMethod.DATA_EXTRACTION.value),
            
            ('skill1', 'trigger_mech', EdgeType.TRIGGERS_VIA.value,
             VerificationStatus.VERIFIED.value, 1.0,
             EvidenceType.CODE.value, DiscoveryMethod.DATA_EXTRACTION.value),
        ]
        
        for source, target, edge_type, status, confidence, ev_type, disc_method in test_edges:
            cursor.execute('''
                INSERT INTO graph_edges (
                    source_node, target_node, edge_type, status, confidence,
                    evidence_type, discovery_method, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
            ''', (source, target, edge_type, status, confidence, ev_type, disc_method))
        
        cls.graph.conn.commit()
        print(f"已插入 {len(test_nodes)} 个节点和 {len(test_edges)} 条边")
    
    def test_01_heuristic_query_verification_aware(self):
        """测试HeuristicQuery验证感知查询"""
        print("\n=== 测试1: HeuristicQuery验证感知查询 ===")
        
        query = HeuristicQuery(self.graph_db_path)
        
        try:
            # 测试分层查询
            result = query.query_bypasses_by_verification_status('constraint1', min_confidence=0.0)
            
            # 验证结果结构
            self.assertIn('verified', result)
            self.assertIn('pending', result)
            self.assertIn('hypothesis', result)
            self.assertIn('summary', result)
            
            # 验证计数
            self.assertEqual(result['summary']['verified_count'], 1)
            self.assertEqual(result['summary']['pending_count'], 1)
            self.assertEqual(result['summary']['hypothesis_count'], 1)
            
            # 验证verified边包含完整字段
            if result['verified']:
                edge = result['verified'][0]
                self.assertIn('confidence', edge)
                self.assertIn('evidence_type', edge)
                self.assertIn('discovery_method', edge)
                
                print(f"  ✓ 分层查询成功: verified={result['summary']['verified_count']}, "
                      f"pending={result['summary']['pending_count']}, "
                      f"hypothesis={result['summary']['hypothesis_count']}")
            
            # 测试置信度过滤
            result_high_conf = query.query_bypasses('constraint1', min_confidence=0.8)
            self.assertEqual(len(result_high_conf), 1)  # 只有verified边
            
            print(f"  ✓ 置信度过滤成功: 置信度>=0.8的结果数={len(result_high_conf)}")
            
            # 测试验证统计
            stats = query.get_verification_stats()
            self.assertIn('total_edges', stats)
            self.assertIn('avg_confidence', stats)
            
            print(f"  ✓ 验证统计成功: 总边数={stats['total_edges']}, 平均置信度={stats['avg_confidence']:.2f}")
        
        finally:
            query.close()
    
    def test_02_heuristic_discovery_verification_guided(self):
        """测试HeuristicDiscovery验证引导发现"""
        print("\n=== 测试2: HeuristicDiscovery验证引导发现 ===")
        
        discovery = HeuristicDiscovery(self.graph_db_path)
        
        try:
            # 测试创建边（带验证字段）
            new_edge = discovery.create_bypass_edge(
                'skill4', 'constraint1',
                evidence='测试证据',
                evidence_type=EvidenceType.CODE.value,
                discovery_method=DiscoveryMethod.PATTERN.value
            )
            
            self.assertIsNotNone(new_edge)
            self.assertIn('edge_id', new_edge)
            self.assertIn('confidence', new_edge)
            self.assertIn('evidence_type', new_edge)
            self.assertIn('discovery_method', new_edge)
            
            # 验证置信度自动计算
            self.assertGreater(new_edge['confidence'], 0.0)
            self.assertLessEqual(new_edge['confidence'], 1.0)
            
            print(f"  ✓ 创建边成功: ID={new_edge['edge_id']}, "
                  f"置信度={new_edge['confidence']:.2f}, "
                  f"状态={new_edge['status']}")
            
            # 测试从pending知识发现
            discoveries = discovery.discover_from_pending_knowledge(max_discoveries=5)
            
            print(f"  ✓ 从pending知识发现: 发现{len(discoveries)}条新边")
            
            # 测试升级高置信度假设
            upgraded = discovery.discover_high_confidence_hypotheses(min_confidence=0.7)
            
            print(f"  ✓ 升级假设: 升级{len(upgraded)}条假设为pending")
        
        finally:
            discovery.close()
    
    def test_03_heuristic_diffuse_verification_constrained(self):
        """测试HeuristicDiffuse验证约束扩散"""
        print("\n=== 测试3: HeuristicDiffuse验证约束扩散 ===")
        
        config = {
            'similarity_threshold': 0.5,
            'min_source_confidence': 0.7
        }
        
        diffuse = HeuristicDiffuse(self.graph_db_path, config)
        
        try:
            # 测试从已验证边扩散
            new_edges = diffuse.diffuse_from_verified_edges(
                edge_type=EdgeType.BYPASSES.value,
                max_edges=5,
                similarity_threshold=0.5,
                min_source_confidence=0.7
            )
            
            print(f"  ✓ 从已验证边扩散: 发现{len(new_edges)}条新边")
            
            # 验证新边的验证字段
            if new_edges:
                edge = new_edges[0]
                self.assertIn('confidence', edge)
                self.assertIn('evidence_type', edge)
                self.assertIn('discovery_method', edge)
                
                # 验证发现方法为DIFFUSION
                self.assertEqual(edge['discovery_method'], DiscoveryMethod.DIFFUSION.value)
                
                print(f"    - 新边: {edge['source']} -> {edge['target']}, "
                      f"置信度={edge['confidence']:.2f}, "
                      f"方法={edge['discovery_method']}")
            
            # 测试扩散统计
            stats = diffuse.get_diffusion_stats()
            
            self.assertIn('available_source_edges', stats)
            self.assertIn('config', stats)
            
            print(f"  ✓ 扩散统计: 可扩散源边数={stats['available_source_edges']}, "
                  f"配置={stats['config']}")
        
        finally:
            diffuse.close()
    
    def test_04_full_workflow(self):
        """测试完整工作流"""
        print("\n=== 测试4: 完整工作流 ===")
        
        # Step 1: 查询pending知识
        query = HeuristicQuery(self.graph_db_path)
        result = query.query_bypasses_by_verification_status('constraint1', min_confidence=0.5)
        query.close()
        
        pending_count = result['summary']['pending_count']
        print(f"  Step 1: 查询到{pending_count}条pending知识")
        
        # Step 2: 从pending知识发现新关系
        discovery = HeuristicDiscovery(self.graph_db_path)
        discoveries = discovery.discover_from_pending_knowledge(max_discoveries=3)
        discovery.close()
        
        print(f"  Step 2: 从pending知识发现{len(discoveries)}条新边")
        
        # Step 3: 从已验证边扩散
        diffuse = HeuristicDiffuse(self.graph_db_path, {
            'min_source_confidence': 0.8,
            'similarity_threshold': 0.5
        })
        
        diffused = diffuse.diffuse_from_verified_edges(
            edge_type=EdgeType.BYPASSES.value,
            max_edges=3,
            min_source_confidence=0.8
        )
        diffuse.close()
        
        print(f"  Step 3: 从已验证边扩散发现{len(diffused)}条新边")
        
        # Step 4: 验证最终统计
        query = HeuristicQuery(self.graph_db_path)
        stats = query.get_verification_stats()
        query.close()
        
        print(f"  Step 4: 最终统计 - 总边数={stats['total_edges']}, "
              f"verified={stats['verified_count']}, "
              f"pending={stats['pending_count']}, "
              f"hypothesis={stats['hypothesis_count']}")
        
        print("  ✓ 完整工作流测试通过")


def run_tests():
    """运行测试"""
    print("\n" + "="*70)
    print("Phase 2 集成测试：验证感知启发式推理")
    print("="*70)
    
    # 创建测试套件
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestPhase2Integration)
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # 输出总结
    print("\n" + "="*70)
    print("测试总结")
    print("="*70)
    print(f"运行测试: {result.testsRun}")
    print(f"成功: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"失败: {len(result.failures)}")
    print(f"错误: {len(result.errors)}")
    
    if result.wasSuccessful():
        print("\n✅ 所有测试通过！Phase 2集成成功。")
    else:
        print("\n❌ 部分测试失败，请检查错误信息。")
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
