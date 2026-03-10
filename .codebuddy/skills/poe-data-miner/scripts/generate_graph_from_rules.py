#!/usr/bin/env python3
"""
从规则库生成关联图边

规则 → 边映射:
- 每条规则 → 一条边
- 规则属性 → 边属性
- status = 'verified' (已验证)
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime


def generate_graph_from_rules():
    """从规则库生成关联图边"""
    
    kb_path = Path('.codebuddy/skills/poe-data-miner/knowledge_base')
    rules_db = kb_path / 'rules.db'
    graph_db = kb_path / 'graph.db'
    
    print("=" * 70)
    print("从规则库生成关联图边")
    print("=" * 70)
    
    # 连接数据库
    rules_conn = sqlite3.connect(str(rules_db))
    rules_cursor = rules_conn.cursor()
    
    graph_conn = sqlite3.connect(str(graph_db))
    graph_cursor = graph_conn.cursor()
    
    # Step 1: 清理旧的规则边 (status = 'verified')
    print("\n[Step 1] 清理旧的规则边...")
    graph_cursor.execute("DELETE FROM graph_edges WHERE status = 'verified'")
    print(f"  ✓ 删除 {graph_cursor.rowcount} 条旧边")
    graph_conn.commit()
    
    # Step 2: 查询所有规则
    print("\n[Step 2] 查询规则...")
    rules_cursor.execute('''
        SELECT id, category, source_entity, target_entity, relation_type,
               condition, effect, evidence, source_layer, source_formula,
               heuristic_record_id, verified_at
        FROM rules
    ''')
    rules = rules_cursor.fetchall()
    print(f"  ✓ 找到 {len(rules)} 条规则")
    
    # Step 3: 生成边
    print("\n[Step 3] 生成边...")
    
    edge_count = 0
    node_set = set()
    
    for rule in rules:
        (rule_id, category, source_entity, target_entity, relation_type,
         condition, effect, evidence, source_layer, source_formula,
         heuristic_record_id, verified_at) = rule
        
        # 跳过没有 source_entity 或 target_entity 的规则
        if not source_entity or not target_entity:
            continue
        
        # 记录节点
        node_set.add(source_entity)
        node_set.add(target_entity)
        
        # 确定边类型
        edge_type = relation_type if relation_type else 'relates'
        
        # 生成边属性
        attributes = {
            'category': category,
            'source_layer': source_layer
        }
        
        # 插入边
        try:
            graph_cursor.execute('''
                INSERT INTO graph_edges (
                    source_node, target_node, edge_type, weight, attributes,
                    status, source_rule, heuristic_record_id, verified_at,
                    condition, effect, evidence, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                source_entity,
                target_entity,
                edge_type,
                1.0,  # 权重
                json.dumps(attributes, ensure_ascii=False),
                'verified',
                rule_id,
                heuristic_record_id,
                verified_at or datetime.now().isoformat(),
                condition,
                effect,
                evidence,
                datetime.now().isoformat()
            ))
            edge_count += 1
        except Exception as e:
            print(f"  ⚠ 插入边失败: {rule_id} - {e}")
    
    graph_conn.commit()
    print(f"  ✓ 生成 {edge_count} 条边")
    print(f"  ✓ 涉及 {len(node_set)} 个节点")
    
    # Step 4: 更新节点表
    print("\n[Step 4] 更新节点表...")
    
    for node_id in node_set:
        # 检查节点是否存在
        graph_cursor.execute('SELECT id FROM graph_nodes WHERE id = ?', (node_id,))
        if not graph_cursor.fetchone():
            # 创建新节点
            graph_cursor.execute('''
                INSERT INTO graph_nodes (id, name, type, created_at)
                VALUES (?, ?, ?, ?)
            ''', (node_id, node_id, 'entity', datetime.now().isoformat()))
    
    graph_conn.commit()
    print(f"  ✓ 确保节点存在")
    
    # Step 5: 统计
    print("\n[Step 5] 统计...")
    
    graph_cursor.execute('SELECT COUNT(*) FROM graph_edges WHERE status = "verified"')
    verified_count = graph_cursor.fetchone()[0]
    print(f"  verified 边: {verified_count}")
    
    graph_cursor.execute('''
        SELECT edge_type, COUNT(*) 
        FROM graph_edges 
        WHERE status = 'verified'
        GROUP BY edge_type
    ''')
    print("\n  按边类型:")
    for row in graph_cursor.fetchall():
        print(f"    {row[0]}: {row[1]}")
    
    graph_cursor.execute('SELECT COUNT(*) FROM graph_nodes')
    node_count = graph_cursor.fetchone()[0]
    print(f"\n  总节点数: {node_count}")
    
    # 关闭连接
    rules_conn.close()
    graph_conn.close()
    
    print("\n" + "=" * 70)
    print("关联图生成完成")
    print("=" * 70)


if __name__ == "__main__":
    generate_graph_from_rules()
