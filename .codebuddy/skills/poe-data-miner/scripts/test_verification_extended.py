"""
验证系统扩展测试

增加边界条件、异常情况和性能测试
"""

import sys
import tempfile
import shutil
from pathlib import Path
import sqlite3
import time

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from verification import (
    VerificationEngine,
    VerificationAwareQueryEngine,
    EvidenceEvaluator,
    Evidence
)
from attribute_graph import AttributeGraph, VerificationStatus, EvidenceType


class ExtendedVerificationTests:
    """扩展验证系统测试"""
    
    def __init__(self):
        self.test_dir = None
        self.graph_db_path = None
        self.pob_data_path = None
    
    def setup(self):
        """设置测试环境"""
        self.test_dir = Path(tempfile.mkdtemp())
        self.graph_db_path = self.test_dir / 'test_graph.db'
        self.graph = AttributeGraph(str(self.graph_db_path))
        self._create_test_data()
        self.pob_data_path = self.test_dir / 'POBData'
        self.pob_data_path.mkdir(parents=True, exist_ok=True)
        print(f"✅ 测试环境已设置")
    
    def teardown(self):
        """清理测试环境"""
        if self.test_dir and self.test_dir.exists():
            shutil.rmtree(self.test_dir)
        print(f"✅ 测试环境已清理")
    
    def _create_test_data(self):
        """创建测试数据"""
        cursor = self.graph.conn.cursor()
        
        # 创建多样化的测试节点
        test_nodes = [
            ('Entity1', 'entity', 'Entity1'),
            ('Entity2', 'entity', 'Entity2'),
            ('Type1', 'type_node', 'Type1'),
            ('Type2', 'type_node', 'Type2'),
            ('Prop1', 'property_node', 'Prop1'),
            ('Prop2', 'property_node', 'Prop2'),
        ]
        
        for node_id, node_type, name in test_nodes:
            cursor.execute('''
                INSERT OR IGNORE INTO graph_nodes (id, type, name)
                VALUES (?, ?, ?)
            ''', (node_id, node_type, name))
        
        # 创建不同状态的边
        test_edges = [
            # verified
            {'source': 'Entity1', 'target': 'Type1', 'type': 'has_type',
             'status': VerificationStatus.VERIFIED.value, 'confidence': 1.0},
            # pending
            {'source': 'Type1', 'target': 'Prop1', 'type': 'implies',
             'status': VerificationStatus.PENDING.value, 'confidence': 0.5},
            # hypothesis
            {'source': 'Entity2', 'target': 'Type2', 'type': 'has_type',
             'status': VerificationStatus.HYPOTHESIS.value, 'confidence': 0.3},
            # rejected
            {'source': 'Type2', 'target': 'Prop2', 'type': 'implies',
             'status': VerificationStatus.REJECTED.value, 'confidence': 0.0},
        ]
        
        for edge in test_edges:
            cursor.execute('''
                INSERT INTO graph_edges 
                (source_node, target_node, edge_type, status, confidence)
                VALUES (?, ?, ?, ?, ?)
            ''', (edge['source'], edge['target'], edge['type'],
                  edge['status'], edge['confidence']))
        
        self.graph.conn.commit()
    
    def test_edge_cases(self):
        """测试边界条件"""
        print("\n" + "="*60)
        print("测试边界条件")
        print("="*60)
        
        engine = VerificationEngine(str(self.pob_data_path), str(self.graph_db_path))
        
        try:
            # 测试1: 验证不存在的边
            print("\n测试1 - 验证不存在的边:")
            result = engine.verify_knowledge(999)
            print(f"  成功: {result['success']}")
            print(f"  错误: {result.get('error', 'N/A')}")
            assert result['success'] == False
            print("  ✅ 通过")
            
            # 测试2: 验证已验证的边
            print("\n测试2 - 验证已验证的边:")
            result = engine.verify_knowledge(1)
            print(f"  成功: {result['success']}")
            assert result['success'] == True
            print("  ✅ 通过")
            
            # 测试3: 验证已拒绝的边
            print("\n测试3 - 验证已拒绝的边:")
            result = engine.verify_knowledge(4)
            print(f"  成功: {result['success']}")
            assert result['success'] == True
            print("  ✅ 通过")
            
            # 测试4: 用户拒绝已验证的边
            print("\n测试4 - 用户拒绝已验证的边:")
            result = engine.user_verify(edge_id=1, decision='reject', reason='测试拒绝')
            print(f"  成功: {result['success']}")
            print(f"  新状态: {result.get('new_status')}")
            assert result['success'] == True
            assert result['new_status'] == VerificationStatus.REJECTED.value
            print("  ✅ 通过")
            
            print("\n✅ 边界条件测试通过")
        
        finally:
            engine.close()
    
    def test_evidence_evaluation_edge_cases(self):
        """测试证据评估的边界条件"""
        print("\n" + "="*60)
        print("测试证据评估边界条件")
        print("="*60)
        
        evaluator = EvidenceEvaluator()
        
        # 测试1: 空证据列表
        print("\n测试1 - 空证据列表:")
        result = evaluator.evaluate([])
        print(f"  状态: {result['status']}")
        print(f"  证据数: {result['evidence_count']}")
        assert result['status'] == VerificationStatus.HYPOTHESIS.value
        print("  ✅ 通过")
        
        # 测试2: 极端强度的证据
        print("\n测试2 - 极端强度证据:")
        evidence = [Evidence(type='stat', strength=1.0, source='test', content='test', layer=1)]
        result = evaluator.evaluate(evidence)
        print(f"  状态: {result['status']}")
        print(f"  强度: {result['overall_strength']:.2f}")
        assert result['overall_strength'] >= 0.8
        print("  ✅ 通过")
        
        # 测试3: 强度分歧
        print("\n测试3 - 强度分歧:")
        evidence = [
            Evidence(type='stat', strength=1.0, source='test1', content='layer1', layer=1),
            Evidence(type='analogy', strength=0.3, source='test2', content='layer3', layer=3)
        ]
        result = evaluator.evaluate(evidence)
        print(f"  状态: {result['status']}")
        print(f"  强度: {result['overall_strength']:.2f}")
        print("  ✅ 通过")
        
        # 测试4: 大量证据
        print("\n测试4 - 大量证据:")
        evidence = [
            Evidence(type='stat', strength=0.9, source=f'test{i}', content=f'content{i}', layer=1)
            for i in range(50)
        ]
        result = evaluator.evaluate(evidence)
        print(f"  状态: {result['status']}")
        print(f"  证据数: {result['evidence_count']}")
        assert result['evidence_count'] == 50
        print("  ✅ 通过")
        
        print("\n✅ 证据评估边界测试通过")
    
    def test_performance(self):
        """测试性能"""
        print("\n" + "="*60)
        print("性能测试")
        print("="*60)
        
        engine = VerificationEngine(str(self.pob_data_path), str(self.graph_db_path))
        
        try:
            # 测试1: 单次验证性能
            print("\n测试1 - 单次验证性能:")
            start = time.time()
            result = engine.verify_knowledge(2, auto_verify=False)
            duration = time.time() - start
            print(f"  耗时: {duration*1000:.2f}ms")
            print(f"  成功: {result['success']}")
            assert duration < 1.0  # 应该在1秒内完成
            print("  ✅ 通过")
            
            # 测试2: 批量验证性能
            print("\n测试2 - 批量验证性能:")
            start = time.time()
            result = engine.batch_verify([2, 3], auto_verify_threshold=0.8)
            duration = time.time() - start
            print(f"  耗时: {duration*1000:.2f}ms")
            print(f"  总数: {result['total']}")
            assert duration < 2.0  # 应该在2秒内完成
            print("  ✅ 通过")
            
            # 测试3: 统计查询性能
            print("\n测试3 - 统计查询性能:")
            start = time.time()
            stats = engine.get_verification_stats()
            duration = time.time() - start
            print(f"  耗时: {duration*1000:.2f}ms")
            print(f"  总知识数: {stats['total_knowledge']}")
            assert duration < 0.1  # 应该在100ms内完成
            print("  ✅ 通过")
            
            print("\n✅ 性能测试通过")
        
        finally:
            engine.close()
    
    def test_error_handling(self):
        """测试错误处理"""
        print("\n" + "="*60)
        print("错误处理测试")
        print("="*60)
        
        # 测试1: 无效的数据库路径
        print("\n测试1 - 无效的数据库路径:")
        try:
            engine = VerificationEngine(str(self.pob_data_path), '/invalid/path/graph.db')
            print("  ❌ 应该抛出异常")
        except Exception as e:
            print(f"  ✅ 正确抛出异常: {type(e).__name__}")
        
        # 测试2: 无效的用户决策
        print("\n测试2 - 无效的用户决策:")
        engine = VerificationEngine(str(self.pob_data_path), str(self.graph_db_path))
        try:
            result = engine.user_verify(edge_id=1, decision='invalid')
            print(f"  成功: {result['success']}")
            print(f"  错误: {result.get('error', 'N/A')}")
            assert result['success'] == False
            print("  ✅ 正确处理无效决策")
        finally:
            engine.close()
        
        print("\n✅ 错误处理测试通过")
    
    def test_concurrent_operations(self):
        """测试并发操作"""
        print("\n" + "="*60)
        print("并发操作测试")
        print("="*60)
        
        from concurrent.futures import ThreadPoolExecutor
        
        engine = VerificationEngine(str(self.pob_data_path), str(self.graph_db_path))
        
        try:
            # 并发验证
            print("\n测试 - 并发验证:")
            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = [
                    executor.submit(engine.verify_knowledge, i, False)
                    for i in range(1, 4)
                ]
                
                results = [f.result() for f in futures]
            
            print(f"  完成数: {len(results)}")
            assert len(results) == 3
            print("  ✅ 通过")
            
            print("\n✅ 并发操作测试通过")
        
        finally:
            engine.close()
    
    def run_all_tests(self):
        """运行所有测试"""
        print("\n" + "="*80)
        print("开始扩展验证系统测试")
        print("="*80)
        
        try:
            self.setup()
            
            self.test_edge_cases()
            self.test_evidence_evaluation_edge_cases()
            self.test_performance()
            self.test_error_handling()
            self.test_concurrent_operations()
            
            print("\n" + "="*80)
            print("✅ 所有扩展测试通过")
            print("="*80)
        
        except Exception as e:
            print(f"\n❌ 测试失败: {e}")
            import traceback
            traceback.print_exc()
            raise
        
        finally:
            self.teardown()


def main():
    """主函数"""
    tester = ExtendedVerificationTests()
    tester.run_all_tests()


if __name__ == '__main__':
    main()
