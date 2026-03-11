#!/usr/bin/env python3
"""
启发式推理系统测试脚本
验证三层推理能力：查询、发现、扩散
"""

import sys
from pathlib import Path

# 添加脚本目录到路径
SCRIPTS_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPTS_DIR))

from heuristic_reason import HeuristicReason
from pob_paths import get_knowledge_base_path


def test_heuristic_system():
    """测试启发式推理系统"""
    
    print("=" * 60)
    print("启发式推理系统测试")
    print("=" * 60)
    
    # 获取知识库路径
    kb_path = get_knowledge_base_path()
    graph_db = kb_path / 'graph.db'
    
    if not graph_db.exists():
        print(f"\n[ERROR] 关联图数据库不存在: {graph_db}")
        print("[提示] 请先运行 init_knowledge_base.py 构建知识库")
        return False
    
    print(f"\n关联图数据库: {graph_db}")
    
    # 初始化推理器
    reason = HeuristicReason(str(graph_db))
    
    try:
        # 测试1: 查询已知绕过边
        print("\n" + "=" * 60)
        print("测试1: 查询已知绕过边")
        print("=" * 60)
        
        # 尝试查询一个可能的约束节点
        constraint = "EnergyCycleLimit"
        print(f"\n查询约束: {constraint}")
        
        result = reason.query_bypass(constraint, mode='query', include_hypothesis=True)
        
        print(f"已知绕过边数量: {result['summary']['known_count']}")
        
        if result['known_bypasses']:
            print("\n已发现的绕过边:")
            for bp in result['known_bypasses'][:5]:
                print(f"  - {bp['source']} --[bypasses]--> {bp['target']}")
                if 'evidence' in bp:
                    print(f"    证据: {bp['evidence'][:80]}...")
        
        # 测试2: 从零发现绕过边
        print("\n" + "=" * 60)
        print("测试2: 从零发现绕过边（如果无已知边）")
        print("=" * 60)
        
        if not result['known_bypasses']:
            print(f"\n开始从零发现绕过 {constraint} 的路径...")
            
            result_discover = reason.query_bypass(constraint, mode='discover')
            
            print(f"发现的绕过边数量: {result_discover['summary']['discovered_count']}")
            
            if result_discover['discovered_bypasses']:
                print("\n发现的绕过边:")
                for bp in result_discover['discovered_bypasses'][:5]:
                    print(f"  - {bp['source']} --[bypasses]--> {bp['target']}")
                    print(f"    置信度: {bp.get('confidence', 'N/A')}")
                    print(f"    状态: {bp.get('status', 'N/A')}")
            
            if result_discover['reasoning_chain']:
                print("\n推理链:")
                for step in result_discover['reasoning_chain']:
                    print(f"  [{step['step']}] {step['description']}")
        else:
            print("\n已有已知绕过边，跳过发现测试")
        
        # 测试3: 自动模式（组合三种能力）
        print("\n" + "=" * 60)
        print("测试3: 自动模式")
        print("=" * 60)
        
        print(f"\n使用自动模式查询绕过 {constraint}...")
        
        result_auto = reason.query_bypass(constraint, mode='auto')
        
        print(f"\n总计绕过边: {result_auto['summary']['total_count']}")
        print(f"  - 已知: {result_auto['summary']['known_count']}")
        print(f"  - 发现: {result_auto['summary']['discovered_count']}")
        print(f"  - 扩散: {result_auto['summary']['diffused_count']}")
        
        if result_auto['reasoning_chain']:
            print("\n推理链:")
            for step in result_auto['reasoning_chain']:
                print(f"  [{step['step']}] {step['description']}")
        
        # 测试4: 推荐绕过方案
        print("\n" + "=" * 60)
        print("测试4: 推荐绕过方案")
        print("=" * 60)
        
        print(f"\n推荐绕过 {constraint} 的前5个方案...")
        
        suggestions = reason.suggest_bypasses(constraint, top_k=5)
        
        if suggestions:
            for i, sug in enumerate(suggestions, 1):
                print(f"\n{i}. {sug['source']} --[bypasses]--> {sug['target']}")
                if 'confidence' in sug:
                    print(f"   置信度: {sug['confidence']:.2f}")
                if 'similarity' in sug:
                    print(f"   相似度: {sug['similarity']:.2f}")
        else:
            print("\n暂无推荐方案")
        
        print("\n" + "=" * 60)
        print("测试完成")
        print("=" * 60)
        
        return True
    
    except Exception as e:
        print(f"\n[ERROR] 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        reason.close()


def test_graph_structure():
    """测试图结构（新增节点和边类型）"""
    
    import sqlite3
    
    print("\n" + "=" * 60)
    print("图结构测试")
    print("=" * 60)
    
    kb_path = get_knowledge_base_path()
    graph_db = kb_path / 'graph.db'
    
    if not graph_db.exists():
        print(f"\n[ERROR] 关联图数据库不存在: {graph_db}")
        return False
    
    conn = sqlite3.connect(str(graph_db))
    cursor = conn.cursor()
    
    # 测试节点类型
    print("\n节点类型统计:")
    cursor.execute('SELECT type, COUNT(*) FROM graph_nodes GROUP BY type')
    for row in cursor.fetchall():
        print(f"  - {row[0]}: {row[1]}")
    
    # 测试边类型
    print("\n边类型统计:")
    cursor.execute('SELECT edge_type, COUNT(*) FROM graph_edges GROUP BY edge_type')
    for row in cursor.fetchall():
        print(f"  - {row[0]}: {row[1]}")
    
    # 测试新增节点类型
    print("\n检查新增节点类型:")
    new_node_types = ['type_node', 'property_node', 'trigger_mechanism']
    for node_type in new_node_types:
        cursor.execute('SELECT COUNT(*) FROM graph_nodes WHERE type = ?', (node_type,))
        count = cursor.fetchone()[0]
        status = "✓" if count > 0 else "✗"
        print(f"  {status} {node_type}: {count}")
    
    # 测试新增边类型
    print("\n检查新增边类型:")
    new_edge_types = ['implies', 'produces', 'triggers_via', 'creates', 'bypasses']
    for edge_type in new_edge_types:
        cursor.execute('SELECT COUNT(*) FROM graph_edges WHERE edge_type = ?', (edge_type,))
        count = cursor.fetchone()[0]
        status = "✓" if count > 0 else "✗"
        print(f"  {status} {edge_type}: {count}")
    
    conn.close()
    
    return True


if __name__ == '__main__':
    # 测试图结构
    test_graph_structure()
    
    # 测试启发式推理系统
    test_heuristic_system()
