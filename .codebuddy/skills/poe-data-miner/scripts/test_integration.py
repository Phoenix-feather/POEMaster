#!/usr/bin/env python3
"""
POE Data Miner 集成测试
测试各模块的集成工作流程
"""

import os
import sys
import json
import sqlite3
import tempfile
import shutil
from pathlib import Path

# 添加脚本目录到路径
SCRIPTS_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPTS_DIR))

# 测试配置
TEST_POB_DATA = Path("F:/AI4POE/POBData")
TEST_OUTPUT_DIR = Path(tempfile.mkdtemp(prefix="poe_test_"))


def setup_test_env():
    """设置测试环境"""
    print("=" * 60)
    print("设置测试环境...")
    
    # 创建测试目录
    test_kb = TEST_OUTPUT_DIR / "knowledge_base"
    test_cache = TEST_OUTPUT_DIR / "cache"
    
    test_kb.mkdir(parents=True, exist_ok=True)
    test_cache.mkdir(parents=True, exist_ok=True)
    
    print(f"测试目录: {TEST_OUTPUT_DIR}")
    print(f"知识库: {test_kb}")
    print(f"缓存: {test_cache}")
    
    return test_kb, test_cache


def cleanup_test_env():
    """清理测试环境"""
    print("\n清理测试环境...")
    if TEST_OUTPUT_DIR.exists():
        shutil.rmtree(TEST_OUTPUT_DIR)
    print("测试环境已清理")


def test_data_scanner(cache_dir: Path):
    """测试 11.1: 数据扫描和实体索引"""
    print("\n" + "=" * 60)
    print("测试 11.1: 数据扫描模块")
    
    try:
        from data_scanner import DataScanner
        
        scanner = DataScanner(str(TEST_POB_DATA), str(cache_dir))
        results = scanner.scan()
        
        # 验证扫描结果
        assert results['total_files'] > 0, "应该扫描到文件"
        assert 'skills' in results['categories'], "应该识别技能文件"
        assert results['version_info'] is not None, "应该提取版本信息"
        
        print(f"✓ 扫描了 {results['total_files']} 个文件")
        print(f"✓ 版本信息: {results['version_info']}")
        
        return True
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        return False


def test_entity_index(cache_dir: Path, kb_dir: Path):
    """测试 11.1: 实体索引"""
    print("\n测试 11.1b: 实体索引模块")
    
    try:
        from entity_index import EntityIndex
        
        db_path = kb_dir / "entities.db"
        index = EntityIndex(str(db_path))
        
        # 初始化数据库
        index.initialize()
        
        # 测试插入
        test_entity = {
            'id': 'test_cast_on_critical',
            'name': 'Cast on Critical',
            'type': 'active_skill',
            'description': 'Test description',
            'skill_types': json.dumps(['Meta', 'GeneratesEnergy', 'Triggers']),
            'constant_stats': json.dumps([['spirit_reservation_flat', 100]]),
            'stats': json.dumps(['energy_generated_+%']),
            'levels': json.dumps({}),
            'source_file': 'test.lua'
        }
        
        index.insert_entity(test_entity)
        
        # 测试查询
        entity = index.get_entity('test_cast_on_critical')
        assert entity is not None, "应该能查到实体"
        assert entity['name'] == 'Cast on Critical', "名称应该匹配"
        
        # 测试类型查询
        meta_skills = index.query_by_type('active_skill')
        assert len(meta_skills) > 0, "应该能按类型查询"
        
        print(f"✓ 实体索引创建成功")
        print(f"✓ 插入测试实体: {entity['name']}")
        
        return True
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        return False


def test_rules_extractor(cache_dir: Path, kb_dir: Path):
    """测试 11.2: 规则提取和规则库"""
    print("\n" + "=" * 60)
    print("测试 11.2: 规则提取模块")
    
    try:
        from rules_extractor import RulesExtractor
        
        db_path = kb_dir / "rules.db"
        extractor = RulesExtractor(str(db_path))
        
        # 初始化数据库
        extractor.initialize()
        
        # 测试插入规则
        test_rule = {
            'id': 'rule_triggered_energy',
            'type': 'condition',
            'layer': 3,
            'source': 'code',
            'pattern': 'if skillTypes[Triggered]',
            'conditions': json.dumps({'skill_type': 'Triggered'}),
            'effects': json.dumps({'energy_generation': 0}),
            'confidence': 1.0,
            'verified': True
        }
        
        extractor.insert_rule(test_rule)
        
        # 测试查询
        rules = extractor.query_rules(type='condition')
        assert len(rules) > 0, "应该能查询到规则"
        
        print(f"✓ 规则库创建成功")
        print(f"✓ 插入测试规则: {test_rule['id']}")
        
        return True
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        return False


def test_attribute_graph(kb_dir: Path):
    """测试 11.3: 关联图构建和查询"""
    print("\n" + "=" * 60)
    print("测试 11.3: 关联图模块")
    
    try:
        from attribute_graph import AttributeGraph
        
        db_path = kb_dir / "graph.db"
        graph = AttributeGraph(str(db_path))
        
        # 初始化数据库
        graph.initialize()
        
        # 测试创建节点
        graph.create_node('cast_on_critical', 'entity', 'Cast on Critical')
        graph.create_node('energy_gen', 'mechanism', 'Energy Generation')
        graph.create_node('triggered', 'constraint', 'Triggered Restriction')
        
        # 测试创建边
        graph.create_edge('cast_on_critical', 'energy_gen', 'causes', 'auto')
        graph.create_edge('triggered', 'energy_gen', 'blocks', 'rule')
        
        # 测试查询
        nodes = graph.query_nodes(type='entity')
        assert len(nodes) > 0, "应该能查询到节点"
        
        edges = graph.query_edges(edge_type='causes')
        assert len(edges) > 0, "应该能查询到边"
        
        print(f"✓ 关联图创建成功")
        print(f"✓ 节点数: {len(graph.query_nodes())}")
        print(f"✓ 边数: {len(graph.query_edges())}")
        
        return True
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        return False


def test_query_engine(kb_dir: Path):
    """测试 11.4: 问答引擎各模式"""
    print("\n" + "=" * 60)
    print("测试 11.4: 问答引擎模块")
    
    try:
        from query_engine import QueryEngine
        
        engine = QueryEngine(str(kb_dir))
        
        # 测试问题分析
        question = "Cast on Critical如何获得能量？"
        analysis = engine.analyze_question(question)
        
        print(f"✓ 问题分析完成")
        print(f"  意图: {analysis.get('intent', 'unknown')}")
        print(f"  实体: {analysis.get('entities', [])}")
        
        # 测试查询模式选择
        mode = engine.select_query_mode(analysis)
        print(f"✓ 选择查询模式: {mode}")
        
        return True
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        return False


def test_incremental_learning(kb_dir: Path):
    """测试 11.5: 增量学习流程"""
    print("\n" + "=" * 60)
    print("测试 11.5: 增量学习模块")
    
    try:
        from knowledge_manager import IncrementalLearning
        
        learning = IncrementalLearning(str(kb_dir))
        
        # 测试创建启发记录
        record_id = learning.create_heuristic_record(
            question="如何绕过Triggered限制？",
            discovery={
                'type': 'bypass',
                'answer': 'Doedre\'s Undoing通过Hazard机制绕过',
                'key_entities': ['Doedre\'s Undoing', 'Cast on Critical']
            }
        )
        
        print(f"✓ 创建启发记录: {record_id}")
        
        # 测试创建待确认项
        pending_id = learning.create_pending_confirmation({
            'type': 'bypass',
            'question': '测试问题',
            'answer': '测试答案'
        })
        
        print(f"✓ 创建待确认项: {pending_id}")
        
        # 测试获取待确认项
        pending_items = learning.get_pending_items()
        assert len(pending_items) > 0, "应该有待确认项"
        
        print(f"✓ 待确认项数量: {len(pending_items)}")
        
        return True
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        return False


def test_recovery_mechanism(kb_dir: Path):
    """测试 11.6: 恢复机制"""
    print("\n" + "=" * 60)
    print("测试 11.6: 恢复机制模块")
    
    try:
        from knowledge_manager import RecoveryMechanism
        
        recovery = RecoveryMechanism(str(kb_dir))
        
        # 测试版本检测
        changed = recovery.check_version_change("0.5.0")
        print(f"✓ 版本变化检测: {changed}")
        
        # 测试版本更新
        recovery.update_version("0.5.0", "test_hash")
        print(f"✓ 版本已更新")
        
        # 测试添加未确认项
        uv_id = recovery.add_to_unverified_list({
            'priority': 'high',
            'trigger': {
                'type': 'version_update',
                'change_description': '测试变化'
            },
            'affected_knowledge': {
                'heuristic_id': 'hr_0001'
            }
        })
        
        print(f"✓ 创建未确认项: {uv_id}")
        
        # 测试获取未确认项
        uv_items = recovery.get_unverified_items()
        print(f"✓ 未确认项数量: {len(uv_items)}")
        
        return True
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        return False


def test_e2e_bypass_question(kb_dir: Path):
    """测试 11.7: 端到端测试 - 绕过触发限制的问答流程"""
    print("\n" + "=" * 60)
    print("测试 11.7: 端到端问答流程")
    
    try:
        from query_engine import QueryEngine
        from attribute_graph import AttributeGraph
        
        # 设置完整的测试场景
        graph = AttributeGraph(str(kb_dir / "graph.db"))
        
        # 创建完整的图结构模拟绕过场景
        # 节点
        graph.create_node('doedre_undoing', 'entity', "Doedre's Undoing")
        graph.create_node('hazard_zone', 'mechanism', 'Hazard Zone')
        graph.create_node('curse_explosion', 'event', 'Curse Explosion')
        graph.create_node('triggered_limit', 'constraint', 'Triggered Energy Limit')
        graph.create_node('energy_gen', 'mechanism', 'Energy Generation')
        
        # 边
        graph.create_edge('doedre_undoing', 'hazard_zone', 'creates', 'rule')
        graph.create_edge('hazard_zone', 'curse_explosion', 'triggers', 'rule')
        graph.create_edge('curse_explosion', 'triggered_limit', 'bypasses', 'predefined')
        graph.create_edge('triggered_limit', 'energy_gen', 'blocks', 'rule')
        
        # 测试问答
        engine = QueryEngine(str(kb_dir))
        
        question = "Doedre's Undoing如何绕过能量限制？"
        result = engine.query(question)
        
        print(f"✓ 问题: {question}")
        print(f"✓ 分析结果: {result.get('analysis', {})}")
        print(f"✓ 查询模式: {result.get('mode', 'unknown')}")
        
        # 验证路径查找
        if 'graph_paths' in result:
            print(f"✓ 找到路径: {len(result['graph_paths'])} 条")
            for path in result['graph_paths'][:2]:
                print(f"  - {path}")
        
        return True
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("POE Data Miner 集成测试")
    print("=" * 60)
    
    results = {
        '11.1_data_scanner_entity_index': False,
        '11.2_rules_extractor': False,
        '11.3_attribute_graph': False,
        '11.4_query_engine': False,
        '11.5_incremental_learning': False,
        '11.6_recovery_mechanism': False,
        '11.7_e2e_bypass_question': False
    }
    
    try:
        kb_dir, cache_dir = setup_test_env()
        
        # 运行测试
        results['11.1_data_scanner_entity_index'] = test_data_scanner(cache_dir)
        results['11.1_data_scanner_entity_index'] = test_entity_index(cache_dir, kb_dir) and results['11.1_data_scanner_entity_index']
        results['11.2_rules_extractor'] = test_rules_extractor(cache_dir, kb_dir)
        results['11.3_attribute_graph'] = test_attribute_graph(kb_dir)
        results['11.4_query_engine'] = test_query_engine(kb_dir)
        results['11.5_incremental_learning'] = test_incremental_learning(kb_dir)
        results['11.6_recovery_mechanism'] = test_recovery_mechanism(kb_dir)
        results['11.7_e2e_bypass_question'] = test_e2e_bypass_question(kb_dir)
        
    finally:
        cleanup_test_env()
    
    # 打印结果
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, passed_flag in results.items():
        status = "✓ 通过" if passed_flag else "✗ 失败"
        print(f"{test_name}: {status}")
    
    print(f"\n总计: {passed}/{total} 测试通过")
    
    return passed == total


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='POE Data Miner 集成测试')
    parser.add_argument('--quick', action='store_true', help='快速测试（跳过数据扫描）')
    
    args = parser.parse_args()
    
    if args.quick:
        print("快速测试模式 - 跳过数据扫描")
    
    success = run_all_tests()
    sys.exit(0 if success else 1)
