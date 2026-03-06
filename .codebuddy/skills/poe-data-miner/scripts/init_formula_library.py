#!/usr/bin/env python3
"""
公式库初始化脚本

完整流程：
1. 从POB提取所有函数（formula_extractor）
2. 分析调用链（call_chain_analyzer）
3. 生成报告
"""

import sys
from pathlib import Path
import argparse

# 添加scripts目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from formula_extractor import FormulaExtractor
from call_chain_analyzer import CallChainAnalyzer


def init_formula_library(pob_path: str, db_path: str, entities_db_path: str):
    """
    初始化公式库
    
    Args:
        pob_path: POB数据目录路径
        db_path: 公式库数据库路径
        entities_db_path: 实体库路径
    """
    print("=" * 70)
    print("POE公式库初始化")
    print("=" * 70)
    print(f"POB数据: {pob_path}")
    print(f"公式库: {db_path}")
    print(f"实体库: {entities_db_path}")
    
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
    
    # 总结
    print("\n" + "=" * 70)
    print("初始化完成！")
    print("=" * 70)
    print(f"提取公式: {len(formulas)} 个")
    print(f"数据库位置: {db_path}")
    
    # 验证数据库
    import sqlite3
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM formulas")
    formula_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM formula_stats")
    stat_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM formula_calls")
    call_count = cursor.fetchone()[0]
    
    print(f"\n数据库统计：")
    print(f"  公式数量: {formula_count}")
    print(f"  Stat关联: {stat_count}")
    print(f"  调用关系: {call_count}")
    
    # 显示示例公式
    print(f"\n示例公式（前5个）：")
    cursor.execute("""
        SELECT id, name, call_depth, 
               json_array_length(exact_stats) as exact_count,
               json_array_length(fuzzy_stats) as fuzzy_count
        FROM formulas
        ORDER BY call_depth DESC
        LIMIT 5
    """)
    
    for i, row in enumerate(cursor.fetchall(), 1):
        print(f"  {i}. {row[1]} (深度:{row[2]}, 精确stat:{row[3]}, 模糊stat:{row[4]})")
    
    conn.close()


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='初始化POE公式库')
    parser.add_argument('pob_path', help='POB数据目录路径')
    parser.add_argument('--db', default='formulas.db', help='公式库数据库路径')
    parser.add_argument('--entities-db', help='实体库路径')
    
    args = parser.parse_args()
    
    # 检查POB路径
    pob_path = Path(args.pob_path)
    if not pob_path.exists():
        print(f"[错误] POB路径不存在: {pob_path}")
        return
    
    # 确定实体库路径
    if args.entities_db:
        entities_db_path = args.entities_db
    else:
        # 默认使用知识库中的实体库
        kb_path = Path(__file__).parent.parent / "knowledge_base" / "entities.db"
        entities_db_path = str(kb_path) if kb_path.exists() else None
    
    # 执行初始化
    init_formula_library(
        pob_path=str(pob_path),
        db_path=args.db,
        entities_db_path=entities_db_path
    )


if __name__ == "__main__":
    main()
