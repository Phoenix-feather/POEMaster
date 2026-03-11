#!/usr/bin/env python3
"""
公式索引初始化 (Formula Index)

统一初始化3类公式索引:
  类型A: 通用公式卡片 (universal_formulas.yaml → universal_formulas表)
  类型B: Stat映射索引 (SkillStatMap + 内联statMap → stat_mappings表)
  类型C: 缺口公式    (Meta能量系统 → gap_formulas表)

支持两种运行模式:
  1. 单独运行: python formula_index.py [--pob-path PATH] [--db PATH] [--entities-db PATH]
  2. 合入重构: init_knowledge_base.py 调用 init_formula_index(pob_path, db_path, entities_db_path)

公式库初始化会:
  - 清空旧的4张表 (formulas, formula_features, formula_stats, formula_calls)
  - 创建新的3张表 (universal_formulas, stat_mappings, gap_formulas)
  - 导入通用公式卡片、stat映射、缺口公式
"""

import os
import sys
import json
import sqlite3
import yaml
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime

# 添加脚本目录到路径
SCRIPTS_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPTS_DIR))


def _get_config_path() -> Path:
    """获取配置目录路径"""
    return SCRIPTS_DIR.parent / 'config'


def _load_universal_formulas(config_path: Path = None) -> list:
    """加载通用公式卡片"""
    if config_path is None:
        config_path = _get_config_path()
    
    yaml_path = config_path / 'universal_formulas.yaml'
    if not yaml_path.exists():
        print(f"    [WARN] 通用公式卡片文件不存在: {yaml_path}")
        return []
    
    with open(yaml_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    
    return data.get('formulas', [])


def _create_universal_formulas_table(cursor):
    """创建通用公式表"""
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS universal_formulas (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            name_en TEXT,
            domain TEXT NOT NULL,
            category TEXT,
            keywords TEXT,
            formula TEXT NOT NULL,
            parameters TEXT,
            notes TEXT,
            source_file TEXT,
            source_lines TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_uf_domain ON universal_formulas(domain)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_uf_category ON universal_formulas(category)')


def _import_universal_formulas(cursor, formulas: list) -> int:
    """导入通用公式卡片"""
    cursor.execute('DELETE FROM universal_formulas')
    
    count = 0
    for f in formulas:
        cursor.execute('''
            INSERT INTO universal_formulas
            (id, name, name_en, domain, category, keywords, formula,
             parameters, notes, source_file, source_lines)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            f['id'],
            f['name'],
            f.get('name_en'),
            f['domain'],
            f.get('category'),
            json.dumps(f.get('keywords', []), ensure_ascii=False),
            f['formula'],
            json.dumps(f.get('parameters', {}), ensure_ascii=False),
            f.get('notes'),
            f.get('source_file'),
            f.get('source_lines')
        ))
        count += 1
    
    return count


def _cleanup_old_tables(cursor):
    """清理旧的公式库表（v1 Jaccard时代的）"""
    old_tables = ['formulas', 'formula_features', 'formula_stats', 'formula_calls']
    cleaned = []
    
    for table in old_tables:
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table,)
        )
        if cursor.fetchone():
            cursor.execute(f'DROP TABLE {table}')
            cleaned.append(table)
    
    if cleaned:
        print(f"    已清理旧表: {', '.join(cleaned)}")
    
    return cleaned


def init_formula_index(
    pob_path: str,
    db_path: str,
    entities_db_path: str,
    config_path: str = None,
    clean_old: bool = True
) -> Dict:
    """
    初始化公式索引（核心函数）
    
    可被 init_knowledge_base.py 直接调用，也可通过命令行单独运行。
    
    Args:
        pob_path: POB数据目录路径
        db_path: 公式库数据库路径 (formulas.db)
        entities_db_path: 实体库数据库路径 (entities.db)
        config_path: 配置目录路径（含universal_formulas.yaml）
        clean_old: 是否清理旧的v1表
    
    Returns:
        统计信息字典
    """
    from stat_map_index import StatMapIndex
    from formula_extractor import FormulaExtractor
    
    config_dir = Path(config_path) if config_path else _get_config_path()
    stats = {}
    
    # ========== Phase 0: 清理旧表 ==========
    if clean_old:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cleaned = _cleanup_old_tables(cursor)
        conn.commit()
        conn.close()
        stats['cleaned_tables'] = cleaned
    
    # ========== Phase 1: 类型A — 通用公式卡片 ==========
    print("\n  Phase 1: 通用公式卡片 (类型A)")
    
    formulas_data = _load_universal_formulas(config_dir)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    _create_universal_formulas_table(cursor)
    uf_count = _import_universal_formulas(cursor, formulas_data)
    conn.commit()
    conn.close()
    
    print(f"    已导入 {uf_count} 张通用公式卡片")
    stats['universal_formulas'] = uf_count
    
    # ========== Phase 2: 类型B — Stat映射索引 ==========
    print("\n  Phase 2: Stat映射索引 (类型B)")
    
    indexer = StatMapIndex(pob_path, db_path)
    indexer.extract_all()
    indexer.save_to_db()
    
    sm_stats = indexer.get_stats()
    stats['stat_mappings'] = sm_stats
    print(f"    全局: {sm_stats['global']}, 内联: {sm_stats['inline']}, 总计: {sm_stats['total']}")
    
    # ========== Phase 3: 类型C — 缺口公式 ==========
    print("\n  Phase 3: 缺口公式 (类型C)")
    
    if entities_db_path and Path(entities_db_path).exists():
        extractor = FormulaExtractor(pob_path, db_path, entities_db_path)
        extractor.extract_gap_formulas()
        extractor.save_gap_formulas()
        
        gf_stats = extractor.get_gap_formulas_stats()
        stats['gap_formulas'] = gf_stats
        print(f"    缺口公式: {gf_stats['total']} 个, 覆盖 {gf_stats['entities_covered']} 个实体")
    else:
        print(f"    [SKIP] 实体库不存在，跳过缺口公式提取")
        stats['gap_formulas'] = {'total': 0, 'entities_covered': 0}
    
    # ========== 汇总 ==========
    stats['total'] = (
        stats['universal_formulas'] +
        stats['stat_mappings']['total'] +
        stats['gap_formulas']['total']
    )
    
    return stats


def diagnose_formula_index(db_path: str):
    """诊断公式索引数据库"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("\n" + "=" * 60)
    print("公式索引诊断")
    print("=" * 60)
    
    # 检查表是否存在
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in cursor.fetchall()]
    print(f"\n现有表: {tables}")
    
    # 旧表检测
    old_tables = {'formulas', 'formula_features', 'formula_stats', 'formula_calls'}
    found_old = old_tables & set(tables)
    if found_old:
        print(f"⚠️  检测到旧版表(v1): {found_old}")
    
    # 新表检测
    new_tables = {'universal_formulas', 'stat_mappings', 'gap_formulas'}
    found_new = new_tables & set(tables)
    missing_new = new_tables - set(tables)
    if missing_new:
        print(f"⚠️  缺失新版表: {missing_new}")
    
    # 各表统计
    for table in sorted(found_new):
        cursor.execute(f'SELECT COUNT(*) FROM {table}')
        count = cursor.fetchone()[0]
        print(f"\n--- {table} ({count} rows) ---")
        
        cursor.execute(f'PRAGMA table_info({table})')
        cols = [col[1] for col in cursor.fetchall()]
        print(f"  字段: {', '.join(cols)}")
        
        if table == 'universal_formulas':
            cursor.execute('SELECT domain, COUNT(*) FROM universal_formulas GROUP BY domain')
            for domain, cnt in cursor.fetchall():
                print(f"  {domain}: {cnt}")
        
        elif table == 'stat_mappings':
            cursor.execute('SELECT scope, COUNT(*) FROM stat_mappings GROUP BY scope')
            for scope, cnt in cursor.fetchall():
                print(f"  {scope}: {cnt}")
            cursor.execute('SELECT domain, COUNT(*) FROM stat_mappings GROUP BY domain ORDER BY COUNT(*) DESC LIMIT 8')
            print("  按领域(Top 8):")
            for domain, cnt in cursor.fetchall():
                print(f"    {domain}: {cnt}")
        
        elif table == 'gap_formulas':
            cursor.execute('SELECT formula_type, COUNT(*) FROM gap_formulas GROUP BY formula_type')
            for ftype, cnt in cursor.fetchall():
                print(f"  {ftype}: {cnt}")
    
    conn.close()


def main():
    """命令行入口（单独运行模式）"""
    import argparse
    from pob_paths import get_pob_path, get_knowledge_base_path
    
    parser = argparse.ArgumentParser(
        description='初始化公式索引（支持单独运行和合入重构流程）'
    )
    parser.add_argument('--pob-path', help='POB数据目录路径（默认自动检测）')
    parser.add_argument('--db', help='公式库数据库路径（默认: knowledge_base/formulas.db）')
    parser.add_argument('--entities-db', help='实体库路径（默认: knowledge_base/entities.db）')
    parser.add_argument('--config', help='配置目录路径（含universal_formulas.yaml）')
    parser.add_argument('--no-clean', action='store_true', help='不清理旧的v1表')
    parser.add_argument('--diagnose-only', action='store_true', help='仅诊断现有数据库')
    
    args = parser.parse_args()
    
    # 路径解析
    try:
        pob_path = Path(args.pob_path) if args.pob_path else get_pob_path()
    except FileNotFoundError as e:
        print(f"[ERROR] {e}")
        sys.exit(1)
    
    kb_path = get_knowledge_base_path()
    db_path = args.db or str(kb_path / 'formulas.db')
    entities_db = args.entities_db or str(kb_path / 'entities.db')
    
    if args.diagnose_only:
        diagnose_formula_index(db_path)
        return
    
    print("=" * 60)
    print("公式索引初始化")
    print("=" * 60)
    print(f"POB数据:  {pob_path}")
    print(f"公式库:   {db_path}")
    print(f"实体库:   {entities_db}")
    
    stats = init_formula_index(
        pob_path=str(pob_path),
        db_path=db_path,
        entities_db_path=entities_db,
        config_path=args.config,
        clean_old=not args.no_clean
    )
    
    print("\n" + "=" * 60)
    print("公式索引初始化完成")
    print("=" * 60)
    print(f"通用公式卡片: {stats['universal_formulas']} 张")
    print(f"Stat映射:     {stats['stat_mappings']['total']} 条 (全局{stats['stat_mappings']['global']} + 内联{stats['stat_mappings']['inline']})")
    print(f"缺口公式:     {stats['gap_formulas']['total']} 个")
    print(f"总计:          {stats['total']} 条")
    print(f"\n数据库位置: {db_path}")


if __name__ == '__main__':
    main()
