"""
验证系统测试脚本

测试验证系统的各个组件
"""

import sys
import tempfile
import shutil
from pathlib import Path
import sqlite3
import json

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from verification import (
    VerificationEngine,
    VerificationAwareQueryEngine,
    EvidenceEvaluator,
    Evidence
)
from attribute_graph import AttributeGraph, VerificationStatus, EvidenceType


class TestVerificationSystem:
    """验证系统测试"""
    
    def __init__(self):
        self.test_dir = None
        self.graph_db_path = None
        self.pob_data_path = None
    
    def setup(self):
        """设置测试环境"""
        # 创建临时目录
        self.test_dir = Path(tempfile.mkdtemp())
        
        # 创建临时数据库
        self.graph_db_path = self.test_dir / 'test_graph.db'
        
        # 初始化关联图（v2: 使用 GraphBuilder）
        self.graph = AttributeGraph(str(self.graph_db_path))
        
        # v2: 手动创建符合 v2 schema 的测试数据库
        self._init_v2_test_db()
        
        # 创建测试数据
        self._create_test_data()
        
        # 创建临时POB数据路径（空目录即可）
        self.pob_data_path = self.test_dir / 'POBData'
        self.pob_data_path.mkdir(parents=True, exist_ok=True)
        
        print(f"✅ 测试环境已设置: {self.test_dir}")
    
    def _init_v2_test_db(self):
        """初始化 v2 schema 的测试数据库"""
        conn = sqlite3.connect(str(self.graph_db_path))
        cursor = conn.cursor()
        
        # v2 schema
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS graph_nodes (
                node_id TEXT PRIMARY KEY,
                node_type TEXT NOT NULL,
                name TEXT NOT NULL,
                properties TEXT,
                source TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS graph_edges (
                edge_id TEXT PRIMARY KEY,
                source_id TEXT NOT NULL,
                target_id TEXT NOT NULL,
                edge_type TEXT NOT NULL,
                properties TEXT,
                confidence REAL DEFAULT 1.0,
                source TEXT,
                status TEXT DEFAULT 'verified'
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS anomaly_paths (
                anomaly_id TEXT PRIMARY KEY,
                constraint_id TEXT NOT NULL,
                modifier_id TEXT NOT NULL,
                mechanism TEXT NOT NULL,
                path_description TEXT,
                value_score INTEGER,
                source TEXT,
                verified BOOLEAN DEFAULT 0
            )
        ''')
        conn.commit()
        conn.close()
    
    def teardown(self):
        """清理测试环境"""
        if self.test_dir and self.test_dir.exists():
            shutil.rmtree(self.test_dir)
        
        print(f"✅ 测试环境已清理")
    
    def _create_test_data(self):
        """创建测试数据（v2 schema）"""
        cursor = self.graph.conn.cursor()
        
        # 创建测试节点（v2: node_id, node_type, name）
        test_nodes = [
            ('Fireball', 'entity', 'Fireball'),
            ('FireSpell', 'category', 'FireSpell'),
            ('fire_damage', 'constraint', 'fire_damage'),
            ('CoC', 'entity', 'CastOnCrit'),
            ('Triggered', 'category', 'Triggered'),
            ('Energy', 'constraint', 'Energy')
        ]
        
        for node_id, node_type, name in test_nodes:
            cursor.execute('''
                INSERT OR IGNORE INTO graph_nodes (node_id, node_type, name)
                VALUES (?, ?, ?)
            ''', (node_id, node_type, name))
        
        # 创建测试边（v2: edge_id, source_id, target_id, edge_type, status）
        test_edges = [
            # verified边
            {
                'id': 'edge_1',
                'source': 'Fireball',
                'target': 'FireSpell',
                'type': 'belongs_to',
                'status': VerificationStatus.VERIFIED.value,
                'confidence': 1.0
            },
            # pending边
            {
                'id': 'edge_2',
                'source': 'FireSpell',
                'target': 'fire_damage',
                'type': 'blocks_when',
                'status': VerificationStatus.PENDING.value,
                'confidence': 0.5
            },
            # hypothesis边
            {
                'id': 'edge_3',
                'source': 'CoC',
                'target': 'Triggered',
                'type': 'triggers',
                'status': VerificationStatus.HYPOTHESIS.value,
                'confidence': 0.3
            }
        ]
        
        for edge in test_edges:
            cursor.execute('''
                INSERT INTO graph_edges 
                (edge_id, source_id, target_id, edge_type, status, confidence)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                edge['id'],
                edge['source'],
                edge['target'],
                edge['type'],
                edge['status'],
                edge['confidence']
            ))
        
        self.graph.conn.commit()
        print(f"✅ 测试数据已创建: {len(test_nodes)} 个节点, {len(test_edges)} 条边")
    
    def test_evidence_evaluator(self):
        """测试证据评估器"""
        print("\n" + "="*60)
        print("测试 EvidenceEvaluator")
        print("="*60)
        
        evaluator = EvidenceEvaluator()
        
        # 测试1: 单个强证据
        evidence_list = [
            Evidence(
                type=EvidenceType.STAT.value,
                strength=1.0,
                source='test.lua',
                content='FireDamage定义',
                layer=1,
                confidence=1.0
            )
        ]
        
        result = evaluator.evaluate(evidence_list)
        
        print(f"\n测试1 - 单个强证据:")
        print(f"  状态: {result['status']}")
        print(f"  置信度: {result['confidence']:.2f}")
        print(f"  强度: {result['overall_strength']:.2f}")
        
        assert result['status'] == VerificationStatus.VERIFIED.value
        assert result['overall_strength'] >= 0.8
        print("  ✅ 通过")
        
        # 测试2: 多个证据
        evidence_list = [
            Evidence(
                type=EvidenceType.STAT.value,
                strength=1.0,
                source='test1.lua',
                content='stat定义',
                layer=1
            ),
            Evidence(
                type=EvidenceType.CODE.value,
                strength=0.8,
                source='test2.lua',
                content='代码逻辑',
                layer=2
            ),
            Evidence(
                type=EvidenceType.ANALOGY.value,
                strength=0.5,
                source='语义',
                content='类比推理',
                layer=3
            )
        ]
        
        result = evaluator.evaluate(evidence_list)
        
        print(f"\n测试2 - 多个证据:")
        print(f"  状态: {result['status']}")
        print(f"  置信度: {result['confidence']:.2f}")
        print(f"  强度: {result['overall_strength']:.2f}")
        print(f"  证据数: {result['evidence_count']}")
        
        assert result['evidence_count'] == 3
        print("  ✅ 通过")
        
        # 测试3: 冲突检测
        counter_examples = [
            Evidence(
                type=EvidenceType.STAT.value,
                strength=1.0,
                source='test.lua',
                content='反例',
                layer=1
            )
        ]
        
        result = evaluator.evaluate(evidence_list, counter_examples)
        
        print(f"\n测试3 - 冲突检测:")
        print(f"  状态: {result['status']}")
        print(f"  冲突: {result['conflict_detected']}")
        
        assert result['conflict_detected'] == True
        assert result['status'] == VerificationStatus.REJECTED.value
        print("  ✅ 通过")
        
        print("\n✅ EvidenceEvaluator 测试通过")
    
    def test_verification_engine(self):
        """测试验证引擎"""
        print("\n" + "="*60)
        print("测试 VerificationEngine")
        print("="*60)
        
        engine = VerificationEngine(
            str(self.pob_data_path),
            str(self.graph_db_path)
        )
        
        try:
            # 测试1: 获取边信息
            edge = engine._get_edge(1)
            
            print(f"\n测试1 - 获取边信息:")
            print(f"  边ID: {edge['id']}")
            print(f"  源节点: {edge['source_node']}")
            print(f"  目标节点: {edge['target_node']}")
            print(f"  状态: {edge['status']}")
            
            assert edge is not None
            print("  ✅ 通过")
            
            # 测试2: 验证知识
            result = engine.verify_knowledge(2, auto_verify=False)
            
            print(f"\n测试2 - 验证知识:")
            print(f"  成功: {result['success']}")
            print(f"  边ID: {result.get('edge_id')}")
            
            assert result['success']
            print("  ✅ 通过")
            
            # 测试3: 用户验证
            result = engine.user_verify(
                edge_id=2,
                decision='accept',
                reason='测试确认'
            )
            
            print(f"\n测试3 - 用户验证:")
            print(f"  成功: {result['success']}")
            print(f"  新状态: {result.get('new_status')}")
            
            assert result['success']
            assert result['new_status'] == VerificationStatus.VERIFIED.value
            print("  ✅ 通过")
            
            # 测试4: 统计信息
            stats = engine.get_verification_stats()
            
            print(f"\n测试4 - 统计信息:")
            print(f"  总知识数: {stats['total_knowledge']}")
            print(f"  验证率: {stats['verified_rate']:.1%}")
            print(f"  平均置信度: {stats['average_confidence']:.2f}")
            
            assert stats['total_knowledge'] == 3
            print("  ✅ 通过")
            
            print("\n✅ VerificationEngine 测试通过")
        
        finally:
            engine.close()
    
    def test_verification_query_engine(self):
        """测试验证感知查询引擎"""
        print("\n" + "="*60)
        print("测试 VerificationAwareQueryEngine")
        print("="*60)
        
        query_engine = VerificationAwareQueryEngine(
            str(self.pob_data_path),
            str(self.graph_db_path)
        )
        
        try:
            # 测试1: 查询verified知识
            result = query_engine.query_by_type('entity', auto_verify=False)
            
            print(f"\n测试1 - 查询verified知识:")
            print(f"  已验证: {len(result['verified'])}")
            print(f"  待确认: {len(result['pending'])}")
            
            assert len(result['verified']) >= 1
            print("  ✅ 通过")
            
            # 测试2: 查询pending知识
            result = query_engine.query_by_type('type_node', auto_verify=False)
            
            print(f"\n测试2 - 查询pending知识:")
            print(f"  已验证: {len(result['verified'])}")
            print(f"  待确认: {len(result['pending'])}")
            
            print("  ✅ 通过")
            
            # 测试3: 队列统计
            stats = query_engine.get_pending_queue_stats()
            
            print(f"\n测试3 - 队列统计:")
            print(f"  总pending: {stats['total_pending']}")
            print(f"  从未验证: {stats['never_verified']}")
            
            print("  ✅ 通过")
            
            print("\n✅ VerificationAwareQueryEngine 测试通过")
        
        finally:
            query_engine.close()
    
    def run_all_tests(self):
        """运行所有测试"""
        print("\n" + "="*80)
        print("开始验证系统测试")
        print("="*80)
        
        try:
            # 设置环境
            self.setup()
            
            # 运行测试
            self.test_evidence_evaluator()
            self.test_verification_engine()
            self.test_verification_query_engine()
            
            print("\n" + "="*80)
            print("✅ 所有测试通过")
            print("="*80)
            
        except AssertionError as e:
            print(f"\n❌ 测试失败: {e}")
            raise
        
        except Exception as e:
            print(f"\n❌ 测试异常: {e}")
            import traceback
            traceback.print_exc()
            raise
        
        finally:
            # 清理环境
            self.teardown()


def main():
    """主函数"""
    tester = TestVerificationSystem()
    tester.run_all_tests()


if __name__ == '__main__':
    main()
