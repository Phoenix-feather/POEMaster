#!/usr/bin/env python3
"""
公式库初始化脚本

完整流程：
1. 自动定位POB数据路径（遵循项目规则 pob-data-extraction-scope）
2. 从POB提取所有函数（formula_extractor）
3. 分析调用链（call_chain_analyzer）
4. 诊断公式库质量
"""

import sys
import os
import json
import sqlite3
from pathlib import Path
import argparse

# 添加scripts目录到路径
SCRIPTS_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPTS_DIR))

from formula_extractor import FormulaExtractor
from call_chain_analyzer import CallChainAnalyzer
from pob_paths import get_pob_path, get_knowledge_base_path


def init_formula_library(pob_path: str, db_path: str, entities_db_path: str):
    """初始化公式库"""
    print("=" * 70)
    print("POE公式库初始化")
    print("=" * 70)
    print(f"POB数据: {pob_path}")
    print(f"公式库: {db_path}")
    print(f"实体库: {entities_db_path}")
    
    # 删除旧数据库（全新初始化）
    if Path(db_path).exists():
        os.remove(db_path)
        print(f"[OK] 已删除旧数据库")
    
    # Phase 1: 公式提取
    print("\n" + "=" * 70)
    print("Phase 1: 公式提取")
    print("=" * 70)
    
    extractor = FormulaExtractor(
        pob_path=pob_path,
        db_path=db_path,
        entities_db_path=entities_db_path
    )
    
    formulas = extractor.extract_all_functions()
    
    # Phase 2: 调用链分析
    print("\n" + "=" * 70)
    print("Phase 2: 调用链分析")
    print("=" * 70)
    
    analyzer = CallChainAnalyzer(db_path=db_path)
    analyzer.analyze()
    
    # Phase 3: 诊断
    print("\n" + "=" * 70)
    print("Phase 3: 公式库诊断")
    print("=" * 70)
    
    diagnose_formula_db(db_path)
    
    print("\n" + "=" * 70)
    print("初始化完成！")
    print("=" * 70)
    print(f"数据库位置: {db_path}")


def diagnose_formula_db(db_path: str):
    """诊断公式库质量"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 基础统计
    cursor.execute("SELECT COUNT(*) FROM formulas")
    total = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM formula_calls")
    call_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM formula_stats")
    stat_rel_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM formula_features")
    feature_count = cursor.fetchone()[0]
    
    print(f"\n--- 基础统计 ---")
    print(f"  公式总数: {total}")
    print(f"  调用关系: {call_count}")
    print(f"  Stat关联: {stat_rel_count}")
    print(f"  特征索引: {feature_count}")
    
    # 代码完整性
    cursor.execute("SELECT COUNT(*) FROM formulas WHERE length(code) > 50")
    has_code = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM formulas WHERE code IS NULL OR length(code) <= 10")
    no_code = cursor.fetchone()[0]
    
    cursor.execute("SELECT AVG(length(code)), MAX(length(code)), MIN(length(code)) FROM formulas WHERE code IS NOT NULL")
    avg_len, max_len, min_len = cursor.fetchone()
    
    print(f"\n--- 代码完整性 ---")
    print(f"  有效代码(>50字符): {has_code}/{total} ({has_code*100/total:.1f}%)")
    print(f"  无/短代码(<=10字符): {no_code}")
    print(f"  代码长度 - 平均:{avg_len:.0f} 最大:{max_len} 最小:{min_len}")
    
    # 特征提取质量
    cursor.execute("""
        SELECT COUNT(*) FROM formulas 
        WHERE exact_stats != '[]' AND exact_stats IS NOT NULL
    """)
    has_exact = cursor.fetchone()[0]
    
    cursor.execute("""
        SELECT COUNT(*) FROM formulas 
        WHERE fuzzy_stats != '[]' AND fuzzy_stats IS NOT NULL
    """)
    has_fuzzy = cursor.fetchone()[0]
    
    cursor.execute("""
        SELECT COUNT(*) FROM formulas 
        WHERE inferred_tags != '[]' AND inferred_tags IS NOT NULL
    """)
    has_tags = cursor.fetchone()[0]
    
    cursor.execute("""
        SELECT COUNT(*) FROM formulas 
        WHERE calls != '[]' AND calls IS NOT NULL
    """)
    has_calls = cursor.fetchone()[0]
    
    print(f"\n--- 特征提取质量 ---")
    print(f"  有精确stat: {has_exact}/{total} ({has_exact*100/total:.1f}%)")
    print(f"  有模糊stat: {has_fuzzy}/{total} ({has_fuzzy*100/total:.1f}%)")
    print(f"  有推断标签: {has_tags}/{total} ({has_tags*100/total:.1f}%)")
    print(f"  有函数调用: {has_calls}/{total} ({has_calls*100/total:.1f}%)")
    
    # 按来源文件统计
    cursor.execute("""
        SELECT source_file, COUNT(*), 
               AVG(length(code)),
               SUM(CASE WHEN exact_stats != '[]' THEN 1 ELSE 0 END),
               SUM(CASE WHEN fuzzy_stats != '[]' THEN 1 ELSE 0 END),
               SUM(CASE WHEN inferred_tags != '[]' THEN 1 ELSE 0 END)
        FROM formulas 
        GROUP BY source_file 
        ORDER BY COUNT(*) DESC
        LIMIT 15
    """)
    
    print(f"\n--- 按来源文件统计(Top 15) ---")
    print(f"  {'文件':<45} {'数量':>4} {'平均代码':>8} {'精确':>4} {'模糊':>4} {'标签':>4}")
    for row in cursor.fetchall():
        file_name = row[0]
        if len(file_name) > 44:
            file_name = "..." + file_name[-41:]
        print(f"  {file_name:<45} {row[1]:>4} {row[2]:>8.0f} {row[3]:>4} {row[4]:>4} {row[5]:>4}")
    
    # 调用深度分布
    cursor.execute("""
        SELECT call_depth, COUNT(*) 
        FROM formulas 
        GROUP BY call_depth 
        ORDER BY call_depth
    """)
    
    print(f"\n--- 调用深度分布 ---")
    for row in cursor.fetchall():
        print(f"  深度 {row[0]}: {row[1]} 个函数")
    
    # 样本检查：显示几个关键函数的代码片段
    print(f"\n--- 关键函数样本 ---")
    key_functions = [
        'isTriggered', 'processAddedCastTime', 'calcMultiSpellRotationImpact',
        'calcs.triggers', 'helmetFocusHandler', 'CWCHandler'
    ]
    
    for func_name in key_functions:
        cursor.execute("""
            SELECT name, length(code), exact_stats, fuzzy_stats, inferred_tags, calls
            FROM formulas 
            WHERE name LIKE ?
            LIMIT 1
        """, (f'%{func_name}%',))
        
        row = cursor.fetchone()
        if row:
            exact = json.loads(row[2]) if row[2] else []
            fuzzy = json.loads(row[3]) if row[3] else []
            tags = json.loads(row[4]) if row[4] else []
            calls = json.loads(row[5]) if row[5] else []
            print(f"\n  {row[0]}:")
            print(f"    代码长度: {row[1]} 字符")
            print(f"    精确stat({len(exact)}): {exact[:5]}{'...' if len(exact) > 5 else ''}")
            print(f"    模糊stat({len(fuzzy)}): {fuzzy[:5]}{'...' if len(fuzzy) > 5 else ''}")
            print(f"    标签({len(tags)}): {tags}")
            print(f"    调用({len(calls)}): {calls[:5]}{'...' if len(calls) > 5 else ''}")
        else:
            print(f"\n  {func_name}: [未找到]")
    
    conn.close()


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='初始化POE公式库')
    parser.add_argument('--pob-path', help='POB数据目录路径（默认自动检测）')
    parser.add_argument('--db', help='公式库数据库路径（默认知识库目录）')
    parser.add_argument('--entities-db', help='实体库路径（默认知识库目录）')
    parser.add_argument('--diagnose-only', action='store_true', help='仅运行诊断')
    
    args = parser.parse_args()
    
    # 自动检测路径
    try:
        pob_path = Path(args.pob_path) if args.pob_path else get_pob_path()
    except FileNotFoundError as e:
        print(f"[ERROR] {e}")
        return
    
    kb_path = get_knowledge_base_path()
    
    db_path = args.db or str(kb_path / "formulas.db")
    
    if args.entities_db:
        entities_db_path = args.entities_db
    else:
        entities_db = kb_path / "entities.db"
        entities_db_path = str(entities_db) if entities_db.exists() else None
    
    if args.diagnose_only:
        if Path(db_path).exists():
            diagnose_formula_db(db_path)
        else:
            print(f"[ERROR] 数据库不存在: {db_path}")
        return
    
    # 执行初始化
    init_formula_library(
        pob_path=str(pob_path),
        db_path=db_path,
        entities_db_path=entities_db_path
    )


if __name__ == "__main__":
    main()
