#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""完整数据库结构分析工具"""

import sqlite3
import json
from pathlib import Path
from typing import List, Dict, Any

def print_header(title: str, width: int = 100):
    """打印标题头"""
    print("\n" + "=" * width)
    print(title.center(width))
    print("=" * width)

def print_section(title: str, width: int = 100):
    """打印章节头"""
    print("\n" + "─" * width)
    print(f" {title}")
    print("─" * width)

def analyze_database_complete(db_path: Path, db_name: str):
    """完整分析数据库"""
    if not db_path.exists():
        print_header(f"{db_name} - 不存在")
        return
    
    print_header(f"{db_name}")
    
    # 文件大小
    file_size = db_path.stat().st_size
    print(f"\n文件大小: {file_size / 1024 / 1024:.2f} MB")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 获取所有表
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in cursor.fetchall()]
    
    print(f"表数量: {len(tables)}")
    
    for i, table in enumerate(tables, 1):
        print_section(f"{i}. 表: {table}")
        analyze_table_complete(cursor, table)
    
    conn.close()

def analyze_table_complete(cursor, table_name: str):
    """完整分析表"""
    # 总行数
    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
    total_rows = cursor.fetchone()[0]
    print(f"\n总行数: {total_rows:,}")
    
    if total_rows == 0:
        print("  (表为空)")
        return
    
    # 获取表结构
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = cursor.fetchall()
    
    print(f"\n表结构:")
    print(f"{'序号':<6} {'字段名':<30} {'类型':<12} {'非空':<8} {'主键':<6} {'默认值'}")
    print(f"{'-'*6} {'-'*30} {'-'*12} {'-'*8} {'-'*6} {'-'*20}")
    
    for col in columns:
        cid, name, dtype, notnull, default, pk = col
        notnull_str = "NOT NULL" if notnull else "NULL"
        pk_str = "PK" if pk else ""
        default_str = str(default)[:20] if default else "-"
        print(f"{cid:<6} {name:<30} {dtype:<12} {notnull_str:<8} {pk_str:<6} {default_str}")
    
    # 字段数据分布
    print(f"\n数据分布详情:")
    
    for col in columns:
        col_name = col[1]
        col_type = col[2]
        
        # 基本统计
        cursor.execute(f"""
            SELECT 
                COUNT(CASE WHEN {col_name} IS NULL THEN 1 END) as null_count,
                COUNT(CASE WHEN {col_name} = '' THEN 1 END) as empty_count,
                COUNT(CASE WHEN {col_name} IS NOT NULL AND {col_name} != '' THEN 1 END) as filled_count,
                COUNT(DISTINCT {col_name}) as distinct_count
            FROM {table_name}
        """)
        
        null_count, empty_count, filled_count, distinct_count = cursor.fetchone()
        
        null_pct = (null_count / total_rows * 100) if total_rows > 0 else 0
        empty_pct = (empty_count / total_rows * 100) if total_rows > 0 else 0
        filled_pct = (filled_count / total_rows * 100) if total_rows > 0 else 0
        
        print(f"\n  【{col_name}】")
        print(f"    类型: {col_type}")
        print(f"    NULL: {null_count:,} ({null_pct:.2f}%)")
        print(f"    空字符串: {empty_count:,} ({empty_pct:.2f}%)")
        print(f"    有值: {filled_count:,} ({filled_pct:.2f}%)")
        print(f"    不同值数量: {distinct_count:,}")
        
        # 对于分类字段，显示值分布
        if col_name in ['type', 'category', 'node_type', 'edge_type', 'affix_type']:
            show_value_distribution(cursor, table_name, col_name, total_rows)
        
        # 对于重要字段，显示示例
        elif filled_count > 0 and distinct_count > 0:
            show_sample_values(cursor, table_name, col_name, distinct_count)

def show_value_distribution(cursor, table_name: str, col_name: str, total_rows: int):
    """显示值分布"""
    cursor.execute(f"""
        SELECT {col_name}, COUNT(*) as count
        FROM {table_name}
        WHERE {col_name} IS NOT NULL
        GROUP BY {col_name}
        ORDER BY count DESC
        LIMIT 20
    """)
    
    values = cursor.fetchall()
    if values:
        print(f"    值分布 (Top 20):")
        for value, count in values:
            pct = (count / total_rows * 100)
            bar = "█" * int(pct / 2)
            print(f"      {str(value):<30} {count:>6,} ({pct:>5.2f}%) {bar}")

def show_sample_values(cursor, table_name: str, col_name: str, distinct_count: int):
    """显示示例值"""
    cursor.execute(f"""
        SELECT {col_name}
        FROM {table_name}
        WHERE {col_name} IS NOT NULL AND {col_name} != ''
        LIMIT 5
    """)
    
    samples = cursor.fetchall()
    if samples:
        print(f"    示例值:")
        for i, sample in enumerate(samples, 1):
            value = str(sample[0])
            if len(value) > 80:
                value = value[:77] + "..."
            print(f"      [{i}] {value}")

def main():
    """主函数"""
    kb_path = Path(__file__).parent.parent / 'knowledge_base'
    
    print("\n" + "█" * 100)
    print("POE知识库完整数据库结构分析报告".center(100))
    print("█" * 100)
    print(f"\n知识库路径: {kb_path}")
    print(f"分析时间: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 数据库列表
    databases = [
        (kb_path / 'entities.db', 'entities.db (实体数据库)'),
        (kb_path / 'rules.db', 'rules.db (规则数据库)'),
        (kb_path / 'graph.db', 'graph.db (关联图数据库)'),
        (kb_path / 'mechanisms.db', 'mechanisms.db (机制数据库)')
    ]
    
    # 分析每个数据库
    for db_path, db_name in databases:
        analyze_database_complete(db_path, db_name)
    
    # 最终统计
    print_header("最终统计")
    
    stats = {}
    
    # entities.db统计
    if (kb_path / 'entities.db').exists():
        conn = sqlite3.connect(kb_path / 'entities.db')
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM entities")
        stats['entities_total'] = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT type, COUNT(*) 
            FROM entities 
            GROUP BY type 
            ORDER BY COUNT(*) DESC
        """)
        stats['entities_by_type'] = cursor.fetchall()
        
        conn.close()
    
    # rules.db统计
    if (kb_path / 'rules.db').exists():
        conn = sqlite3.connect(kb_path / 'rules.db')
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM rules")
        stats['rules_total'] = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT category, COUNT(*) 
            FROM rules 
            GROUP BY category 
            ORDER BY COUNT(*) DESC
        """)
        stats['rules_by_category'] = cursor.fetchall()
        
        conn.close()
    
    # graph.db统计
    if (kb_path / 'graph.db').exists():
        conn = sqlite3.connect(kb_path / 'graph.db')
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM graph_nodes")
        stats['nodes_total'] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM graph_edges")
        stats['edges_total'] = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT type, COUNT(*) 
            FROM graph_nodes 
            GROUP BY type 
            ORDER BY COUNT(*) DESC
        """)
        stats['nodes_by_type'] = cursor.fetchall()
        
        cursor.execute("""
            SELECT edge_type, COUNT(*) 
            FROM graph_edges 
            GROUP BY edge_type 
            ORDER BY COUNT(*) DESC
        """)
        stats['edges_by_type'] = cursor.fetchall()
        
        conn.close()
    
    # mechanisms.db统计
    if (kb_path / 'mechanisms.db').exists():
        conn = sqlite3.connect(kb_path / 'mechanisms.db')
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM mechanisms")
        stats['mechanisms_total'] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM mechanism_sources")
        stats['mechanism_sources_total'] = cursor.fetchone()[0]
        
        conn.close()
    
    # 打印统计
    print(f"\n实体总数: {stats.get('entities_total', 0):,}")
    if 'entities_by_type' in stats:
        print("  按类型:")
        for type_name, count in stats['entities_by_type']:
            print(f"    {type_name:<25} {count:>6,}")
    
    print(f"\n规则总数: {stats.get('rules_total', 0):,}")
    if 'rules_by_category' in stats:
        print("  按类别:")
        for cat_name, count in stats['rules_by_category']:
            print(f"    {cat_name:<25} {count:>6,}")
    
    print(f"\n图节点总数: {stats.get('nodes_total', 0):,}")
    if 'nodes_by_type' in stats:
        print("  按类型:")
        for type_name, count in stats['nodes_by_type']:
            print(f"    {type_name:<25} {count:>6,}")
    
    print(f"\n图边总数: {stats.get('edges_total', 0):,}")
    if 'edges_by_type' in stats:
        print("  按类型:")
        for type_name, count in stats['edges_by_type']:
            print(f"    {type_name:<25} {count:>6,}")
    
    print(f"\n机制总数: {stats.get('mechanisms_total', 0):,}")
    print(f"机制来源总数: {stats.get('mechanism_sources_total', 0):,}")
    
    print("\n" + "█" * 100)
    print("分析完成".center(100))
    print("█" * 100 + "\n")

if __name__ == '__main__':
    main()
