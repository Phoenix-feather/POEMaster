#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""数据库详细分析工具 - 显示所有表的结构和数据分布"""

import sqlite3
import json
from pathlib import Path
from collections import Counter
from typing import Dict, List, Any

def analyze_database(db_path: Path, db_name: str):
    """分析单个数据库"""
    if not db_path.exists():
        print(f"\n{'='*80}")
        print(f"{db_name} - 不存在")
        print(f"{'='*80}\n")
        return
    
    print(f"\n{'='*80}")
    print(f"{db_name}")
    print(f"{'='*80}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 获取所有表
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in cursor.fetchall()]
    
    for table in tables:
        analyze_table(cursor, table)
    
    conn.close()

def analyze_table(cursor, table_name: str):
    """分析单个表"""
    print(f"\n{'─'*80}")
    print(f"表: {table_name}")
    print(f"{'─'*80}")
    
    # 获取总行数
    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
    total_rows = cursor.fetchone()[0]
    print(f"总行数: {total_rows:,}")
    
    if total_rows == 0:
        print("  (表为空)")
        return
    
    # 获取表结构
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = cursor.fetchall()
    
    print(f"\n字段详情:")
    print(f"{'序号':<4} {'字段名':<25} {'类型':<12} {'非空':<8} {'默认值':<10}")
    print(f"{'-'*4} {'-'*25} {'-'*12} {'-'*8} {'-'*10}")
    
    for col in columns:
        cid, name, dtype, notnull, default, pk = col
        notnull_str = "NOT NULL" if notnull else "NULL"
        default_str = str(default)[:10] if default else "-"
        print(f"{cid:<4} {name:<25} {dtype:<12} {notnull_str:<8} {default_str:<10}")
    
    # 分析字段数据分布
    print(f"\n字段数据分布:")
    print(f"{'─'*80}")
    
    for col in columns:
        col_name = col[1]
        col_type = col[2]
        
        # 统计NULL、空字符串、非空值
        cursor.execute(f"""
            SELECT 
                COUNT(CASE WHEN {col_name} IS NULL THEN 1 END) as null_count,
                COUNT(CASE WHEN {col_name} = '' THEN 1 END) as empty_count,
                COUNT(CASE WHEN {col_name} IS NOT NULL AND {col_name} != '' THEN 1 END) as filled_count
            FROM {table_name}
        """)
        
        null_count, empty_count, filled_count = cursor.fetchone()
        
        null_pct = (null_count / total_rows * 100) if total_rows > 0 else 0
        empty_pct = (empty_count / total_rows * 100) if total_rows > 0 else 0
        filled_pct = (filled_count / total_rows * 100) if total_rows > 0 else 0
        
        # 简化显示
        if null_count == total_rows:
            status = "全为NULL"
        elif filled_count == total_rows:
            status = "完全填充 ✓"
        elif filled_count > 0:
            status = f"{filled_pct:.1f}% 填充"
        else:
            status = "空"
        
        print(f"{col_name:<30} {status:<20} (NULL: {null_count:,}, 空: {empty_count:,}, 有值: {filled_count:,})")
        
        # 对于特定字段，显示值分布
        if col_name in ['type', 'category', 'node_type', 'edge_type'] and filled_count > 0:
            analyze_value_distribution(cursor, table_name, col_name, total_rows)
        
        # 对于JSON字段，显示简要信息
        if col_name in ['levels', 'stat_sets', 'mod_data', 'stats', 'skill_types', 'tags'] and filled_count > 0:
            analyze_json_field(cursor, table_name, col_name, filled_count)

def analyze_value_distribution(cursor, table_name: str, col_name: str, total_rows: int):
    """分析字段值分布"""
    cursor.execute(f"""
        SELECT {col_name}, COUNT(*) as count
        FROM {table_name}
        WHERE {col_name} IS NOT NULL
        GROUP BY {col_name}
        ORDER BY count DESC
        LIMIT 10
    """)
    
    values = cursor.fetchall()
    if values:
        print(f"  值分布 (Top 10):")
        for value, count in values:
            pct = (count / total_rows * 100)
            print(f"    {value:<30} {count:>6,} ({pct:>5.2f}%)")

def analyze_json_field(cursor, table_name: str, col_name: str, filled_count: int):
    """分析JSON字段"""
    cursor.execute(f"""
        SELECT {col_name}
        FROM {table_name}
        WHERE {col_name} IS NOT NULL AND {col_name} != ''
        LIMIT 5
    """)
    
    samples = cursor.fetchall()
    if samples:
        print(f"  JSON示例 (前5个):")
        for i, sample in enumerate(samples, 1):
            try:
                data = json.loads(sample[0])
                if isinstance(data, dict):
                    keys_count = len(data)
                    print(f"    [{i}] 字典, {keys_count}个键: {list(data.keys())[:3]}...")
                elif isinstance(data, list):
                    items_count = len(data)
                    if items_count > 0:
                        first_item_type = type(data[0]).__name__
                        print(f"    [{i}] 列表, {items_count}项, 类型: {first_item_type}")
                    else:
                        print(f"    [{i}] 空列表")
                else:
                    print(f"    [{i}] {type(data).__name__}: {str(data)[:50]}")
            except:
                print(f"    [{i}] 解析失败")

def main():
    """主函数"""
    kb_path = Path(__file__).parent.parent / 'knowledge_base'
    
    print("=" * 80)
    print("POE知识库数据库详细分析")
    print("=" * 80)
    print(f"知识库路径: {kb_path}")
    
    # 分析各个数据库
    databases = [
        (kb_path / 'entities.db', 'entities.db (实体数据库)'),
        (kb_path / 'rules.db', 'rules.db (规则数据库)'),
        (kb_path / 'graph.db', 'graph.db (关联图数据库)'),
        (kb_path / 'mechanisms.db', 'mechanisms.db (机制数据库)')
    ]
    
    for db_path, db_name in databases:
        analyze_database(db_path, db_name)
    
    # 生成摘要
    print(f"\n{'='*80}")
    print("摘要统计")
    print(f"{'='*80}\n")
    
    total_entities = 0
    total_rules = 0
    total_nodes = 0
    total_edges = 0
    total_mechanisms = 0
    
    if (kb_path / 'entities.db').exists():
        conn = sqlite3.connect(kb_path / 'entities.db')
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM entities")
        total_entities = cursor.fetchone()[0]
        conn.close()
    
    if (kb_path / 'rules.db').exists():
        conn = sqlite3.connect(kb_path / 'rules.db')
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM rules")
        total_rules = cursor.fetchone()[0]
        conn.close()
    
    if (kb_path / 'graph.db').exists():
        conn = sqlite3.connect(kb_path / 'graph.db')
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM graph_nodes")
        total_nodes = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM graph_edges")
        total_edges = cursor.fetchone()[0]
        conn.close()
    
    if (kb_path / 'mechanisms.db').exists():
        conn = sqlite3.connect(kb_path / 'mechanisms.db')
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM mechanisms")
        total_mechanisms = cursor.fetchone()[0]
        conn.close()
    
    print(f"entities.db:")
    print(f"  - 实体数: {total_entities:,}")
    
    print(f"\nrules.db:")
    print(f"  - 规则数: {total_rules:,}")
    
    print(f"\ngraph.db:")
    print(f"  - 节点数: {total_nodes:,}")
    print(f"  - 边数: {total_edges:,}")
    
    print(f"\nmechanisms.db:")
    print(f"  - 机制数: {total_mechanisms:,}")
    
    print(f"\n{'='*80}")
    print("分析完成")
    print(f"{'='*80}\n")

if __name__ == '__main__':
    main()
