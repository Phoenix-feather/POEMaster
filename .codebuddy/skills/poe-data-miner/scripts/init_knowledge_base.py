#!/usr/bin/env python3
"""
POE知识库初始化脚本 v2
统一初始化实体索引、公式库、机制库
"""

import os
import sys
import json
import sqlite3
from pathlib import Path
from datetime import datetime

# 添加脚本目录到路径
SCRIPTS_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPTS_DIR))

from data_scanner import POBDataScanner
from entity_index import EntityIndex
from mechanism_extractor import MechanismExtractor
from formula_index import init_formula_index
from pob_paths import get_pob_path, get_knowledge_base_path, validate_pob_path

# 导入 schema 验证
try:
    from schema_validator import validate_before_init
    HAS_SCHEMA_VALIDATOR = True
except ImportError:
    HAS_SCHEMA_VALIDATOR = False

# 检查 lupa 依赖
try:
    import lupa
    HAS_LUPA = True
except ImportError:
    HAS_LUPA = False


def init_entity_index(pob_path: str, db_path: str) -> dict:
    """初始化实体索引"""
    print("\n" + "=" * 60)
    print("1. 初始化实体索引")
    print("=" * 60)
    
    index = EntityIndex(db_path)
    
    # 扫描数据
    print(f"扫描 {pob_path}...")
    scanner = POBDataScanner(pob_path)
    results = scanner.scan_all_files()
    
    # 导入实体
    print("导入实体...")
    count = 0
    for result in results:
        source_file = result.file_path
        for entity in result.entities:
            # 设置类型
            if result.data_type:
                entity['type'] = result.data_type.value
            index.insert_entity(entity, source_file)
            count += 1
    
    index.close()
    
    # 统计
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT type, COUNT(*) FROM entities GROUP BY type")
    type_counts = dict(cursor.fetchall())
    cursor.execute("SELECT COUNT(*) FROM entities")
    total = cursor.fetchone()[0]
    conn.close()
    
    print(f"[OK] 已导入 {total} 个实体")
    for t, c in type_counts.items():
        print(f"  - {t}: {c}")
    
    return {'total': total, 'by_type': type_counts}


def init_formula_library(pob_path: str, db_path: str, entities_db_path: str) -> dict:
    """初始化公式库（v2: 3类公式索引）"""
    print("\n" + "=" * 60)
    print("2. 初始化公式索引")
    print("=" * 60)
    
    # 调用新的统一初始化函数
    stats = init_formula_index(
        pob_path=pob_path,
        db_path=db_path,
        entities_db_path=entities_db_path,
        clean_old=True
    )
    
    uf = stats.get('universal_formulas', 0)
    sm = stats.get('stat_mappings', {}).get('total', 0)
    gf = stats.get('gap_formulas', {}).get('total', 0)
    
    print(f"[OK] 公式索引初始化完成")
    print(f"     - 通用公式卡片: {uf}")
    print(f"     - Stat映射: {sm}")
    print(f"     - 缺口公式: {gf}")
    
    return stats


def extract_mechanisms(modcache_path: str, db_path: str, entities_db_path: str = None) -> dict:
    """提取机制到数据库"""
    print("\n" + "=" * 60)
    print("3. 提取机制 (基于 stat ID)")
    print("=" * 60)
    
    # 检查 lupa 依赖
    if not HAS_LUPA:
        print("[警告] 缺少 lupa 库，无法提取机制")
        print("[提示] 请运行: pip install lupa")
        print("[提示] 机制提取将被跳过，知识库仍可正常使用\n")
        return {'mechanisms': 0, 'sources': 0}
    
    try:
        extractor = MechanismExtractor(modcache_path, entities_db_path)
        extractor.parse_modcache()
        if entities_db_path:
            extractor.build_entity_mapping()
        extractor.identify_mechanisms()
        extractor.export_to_db(db_path)
        
        # 统计
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM mechanisms')
        mech_count = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM mechanism_sources')
        source_count = cursor.fetchone()[0]
        conn.close()
        
        print(f"[OK] 提取了 {mech_count} 个机制, {source_count} 个来源")
        return {'mechanisms': mech_count, 'sources': source_count}
    
    except Exception as e:
        print(f"[错误] 机制提取失败: {e}")
        print("[提示] 知识库仍可正常使用，但缺少机制数据\n")
        return {'mechanisms': 0, 'sources': 0}


def update_version_yaml(kb_path: str, version: str = None):
    """更新版本信息"""
    print("\n更新版本信息...")
    
    version_file = Path(kb_path) / 'version.yaml'
    
    content = f"""# 版本信息
# 记录当前知识库对应的POB版本

metadata:
  knowledge_base_version: "2.0.0"
  last_initialized: "{datetime.now().isoformat()}"

pob_version:
  game_version: "{version or 'unknown'}"
  pob_version: "{version or 'unknown'}"
  data_hash: null
  
  detection:
    method: "init_script"
    detected_at: "{datetime.now().isoformat()}"

version_history: []
"""
    
    with open(version_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"[OK] 版本信息已更新")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='初始化POE知识库 v2')
    parser.add_argument('pob_path', nargs='?', default=None, help='POB数据目录路径（默认自动检测）')
    parser.add_argument('--kb-path', default=None, help='知识库目录路径')
    
    args = parser.parse_args()
    
    # 使用 pob_paths 模块获取路径（统一入口）
    try:
        if args.pob_path:
            pob_path = Path(args.pob_path).resolve()
        else:
            pob_path = get_pob_path()
    except FileNotFoundError as e:
        print(f"[ERROR] {e}")
        sys.exit(1)
    
    kb_path = Path(args.kb_path).resolve() if args.kb_path else get_knowledge_base_path()
    
    # 创建目录
    kb_path.mkdir(parents=True, exist_ok=True)
    
    # POB路径验证
    is_valid, warnings = validate_pob_path(pob_path)
    if warnings:
        print(f"\n[WARN] POB路径验证有 {len(warnings)} 个警告:")
        for w in warnings:
            print(f"  - {w}")
    
    print("=" * 60)
    print("POE知识库初始化 v2")
    print("=" * 60)
    print(f"POB数据: {pob_path}")
    print(f"知识库: {kb_path}")
    
    # Schema 验证
    print("\n" + "=" * 60)
    print("0. Schema 验证")
    print("=" * 60)
    
    if HAS_SCHEMA_VALIDATOR:
        if not validate_before_init():
            print("\n[ERROR] Schema 验证失败，请先修复上述问题")
            sys.exit(1)
    else:
        print("[WARN] schema_validator 未安装，跳过验证")
    
    # 初始化各模块
    entities_db = kb_path / 'entities.db'
    formulas_db = kb_path / 'formulas.db'
    
    entity_stats = init_entity_index(str(pob_path), str(entities_db))
    
    # 公式库初始化（添加异常处理）
    try:
        formula_stats = init_formula_library(str(pob_path), str(formulas_db), str(entities_db))
    except Exception as e:
        print(f"\n[ERROR] 公式库初始化失败: {e}")
        import traceback
        traceback.print_exc()
        formula_stats = {'universal_formulas': 0, 'stat_mappings': {'total': 0}, 'gap_formulas': {'total': 0}, 'total': 0}
    
    # 提取机制
    modcache_path = pob_path / 'Data' / 'ModCache.lua'
    if modcache_path.exists():
        mechanism_stats = extract_mechanisms(str(modcache_path), str(kb_path / 'mechanisms.db'), str(entities_db))
    else:
        mechanism_stats = {'mechanisms': 0}
    
    update_version_yaml(str(kb_path))
    
    # 最终统计
    print("\n" + "=" * 60)
    print("初始化完成")
    print("=" * 60)
    print(f"实体索引: {entity_stats['total']} 个实体")
    uf = formula_stats.get('universal_formulas', 0)
    sm_total = formula_stats.get('stat_mappings', {}).get('total', 0)
    gf_total = formula_stats.get('gap_formulas', {}).get('total', 0)
    formula_total = formula_stats.get('total', 0)
    print(f"公式索引: 通用{uf} + 映射{sm_total} + 缺口{gf_total} = {formula_total} 条")
    print(f"机制库:   {mechanism_stats['mechanisms']} 个机制, {mechanism_stats.get('sources', 0)} 个来源")
    
    # 验证检查
    print("\n" + "=" * 60)
    print("数据完整性验证")
    print("=" * 60)
    
    issues = []
    
    # 检查实体数量
    if entity_stats['total'] < 1000:
        issues.append(f"实体数量过少: {entity_stats['total']}")
    
    # 检查公式库
    if formula_total == 0:
        issues.append("公式库为空，请检查 init_formula_library 是否执行成功")
    
    if issues:
        print("⚠ 发现以下问题:")
        for issue in issues:
            print(f"  - {issue}")
        print("\n建议: 重新运行初始化或单独初始化失败的模块")
    else:
        print("✅ 所有数据已正确初始化")


if __name__ == '__main__':
    main()
