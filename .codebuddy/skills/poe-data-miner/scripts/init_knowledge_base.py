#!/usr/bin/env python3
"""
POE知识库初始化脚本
统一初始化实体索引、规则库、关联图
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
from rules_extractor import RulesExtractor  # 使用新版本
from attribute_graph import AttributeGraph  # 用于初始化表结构和加载预置边
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


def init_rules_db(db_path: str, entities_db_path: str) -> dict:
    """初始化规则库 - 使用新的 RulesExtractor"""
    print("\n" + "=" * 60)
    print("3. 初始化规则库")
    print("=" * 60)
    
    # 获取知识库路径
    kb_path = Path(entities_db_path).parent
    
    # 使用新的 RulesExtractor
    extractor = RulesExtractor(str(kb_path))
    extractor.run()
    
    # 统计
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT category, COUNT(*) FROM rules GROUP BY category")
    cat_counts = dict(cursor.fetchall())
    cursor.execute("SELECT COUNT(*) FROM rules")
    total = cursor.fetchone()[0]
    conn.close()
    
    print(f"[OK] 已创建 {total} 条规则")
    for c, count in cat_counts.items():
        print(f"  - {c}: {count}")
    
    return {'total': total, 'by_category': cat_counts}


def init_attribute_graph(db_path: str, entities_db_path: str, rules_db_path: str, predefined_edges_path: str = None) -> dict:
    """
    初始化关联图 - 从规则库生成边
    
    数据流: rules.db → graph.db
    边状态: verified (已验证)
    """
    print("\n" + "=" * 60)
    print("4. 初始化关联图")
    print("=" * 60)
    
    # Step 1: 创建图数据库（初始化表结构）
    print("初始化图数据库结构...")
    graph = AttributeGraph(db_path, predefined_edges_path=predefined_edges_path)
    
    # Step 2: 从规则库生成边
    print("从规则库生成边...")
    
    rules_conn = sqlite3.connect(rules_db_path)
    rules_cursor = rules_conn.cursor()
    
    graph_conn = sqlite3.connect(db_path)
    graph_cursor = graph_conn.cursor()
    
    # 清理旧的规则边 (status = 'verified')
    graph_cursor.execute("DELETE FROM graph_edges WHERE status = 'verified'")
    deleted_count = graph_cursor.rowcount
    if deleted_count > 0:
        print(f"  清理 {deleted_count} 条旧边")
    
    # 查询所有规则
    rules_cursor.execute('''
        SELECT id, category, source_entity, target_entity, relation_type,
               condition, effect, evidence, source_layer, source_formula,
               heuristic_record_id, verified_at
        FROM rules
    ''')
    rules = rules_cursor.fetchall()
    print(f"  找到 {len(rules)} 条规则")
    
    # 生成边
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
    print(f"  生成 {edge_count} 条边")
    
    # Step 3: 确保节点存在
    print("确保节点存在...")
    for node_id in node_set:
        graph_cursor.execute('SELECT id FROM graph_nodes WHERE id = ?', (node_id,))
        if not graph_cursor.fetchone():
            graph_cursor.execute('''
                INSERT INTO graph_nodes (id, name, type, created_at)
                VALUES (?, ?, ?, ?)
            ''', (node_id, node_id, 'entity', datetime.now().isoformat()))
    
    graph_conn.commit()
    print(f"  确保 {len(node_set)} 个节点存在")
    
    # 预置边已在 AttributeGraph 构造函数中加载
    
    # 关闭连接
    rules_conn.close()
    graph_conn.close()
    
    # 统计
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM graph_nodes')
    node_count = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM graph_edges')
    edge_count = cursor.fetchone()[0]
    
    cursor.execute('SELECT type, COUNT(*) FROM graph_nodes GROUP BY type')
    node_types = {row[0]: row[1] for row in cursor.fetchall()}
    
    cursor.execute('SELECT edge_type, COUNT(*) FROM graph_edges GROUP BY edge_type')
    edge_types = {row[0]: row[1] for row in cursor.fetchall()}
    
    cursor.execute('SELECT status, COUNT(*) FROM graph_edges GROUP BY status')
    edge_status = {row[0]: row[1] for row in cursor.fetchall()}
    
    conn.close()
    
    print(f"[OK] 已创建 {node_count} 个节点")
    for t, c in node_types.items():
        print(f"  - {t}: {c}")
    
    print(f"[OK] 已创建 {edge_count} 条边")
    for t, c in edge_types.items():
        print(f"  - {t}: {c}")
    
    print("边状态分布:")
    for s, c in edge_status.items():
        print(f"  - {s}: {c}")
    
    return {
        'nodes': node_count,
        'edges': edge_count,
        'node_types': node_types,
        'edge_types': edge_types,
        'edge_status': edge_status
    }


def update_version_yaml(kb_path: str, version: str = None):
    """更新版本信息"""
    print("\n更新版本信息...")
    
    version_file = Path(kb_path) / 'version.yaml'
    
    content = f"""# 版本信息
# 记录当前知识库对应的POB版本

metadata:
  knowledge_base_version: "0.1.0"
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


def import_heuristic_records(kb_path: str, rules_db_path: str, graph_db_path: str) -> dict:
    """导入启发记录到知识库"""
    print("\n" + "=" * 60)
    print("5. 导入启发记录")
    print("=" * 60)
    
    import yaml
    
    heuristic_file = Path(kb_path) / 'heuristic_records.yaml'
    if not heuristic_file.exists():
        print("[INFO] 没有启发记录文件")
        return {'imported': 0}
    
    with open(heuristic_file, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    
    records = data.get('records', [])
    if not records:
        print("[INFO] 没有启发记录")
        return {'imported': 0}
    
    # 导入到规则库
    rules_conn = sqlite3.connect(rules_db_path)
    rules_cursor = rules_conn.cursor()
    
    # 导入到图
    graph_conn = sqlite3.connect(graph_db_path)
    graph_cursor = graph_conn.cursor()
    
    imported = 0
    for record in records:
        if not record.get('confirmation', {}).get('confirmed', False):
            continue
        
        # 创建规则
        rule_id = record.get('id', f"hr_{imported}")
        discovery = record.get('discovery', {})
        
        rules_cursor.execute('''
            INSERT OR IGNORE INTO rules (id, name, category, condition, effect, description, source_layer)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            rule_id,
            discovery.get('question', 'Unknown')[:50],
            discovery.get('type', 'heuristic'),
            'user_confirmed',
            discovery.get('answer', '')[:200],
            discovery.get('reason', ''),
            4  # Layer 4 = heuristic
        ))
        
        # 创建图节点
        graph_cursor.execute('''
            INSERT OR IGNORE INTO graph_nodes (id, type, name, attributes)
            VALUES (?, ?, ?, ?)
        ''', (
            rule_id,
            'heuristic',
            discovery.get('question', 'Unknown')[:50],
            str(discovery)
        ))
        
        imported += 1
    
    rules_conn.commit()
    graph_conn.commit()
    rules_conn.close()
    graph_conn.close()
    
    print(f"[OK] 已导入 {imported} 条启发记录")
    return {'imported': imported}


def extract_mechanisms(modcache_path: str, db_path: str, entities_db_path: str = None) -> dict:
    """提取机制到数据库"""
    print("\n" + "=" * 60)
    print("6. 提取机制 (基于 stat ID)")
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


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='初始化POE知识库')
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
    print("POE知识库初始化")
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
    rules_db = kb_path / 'rules.db'
    graph_db = kb_path / 'graph.db'
    
    # 预置边配置文件路径（相对于脚本目录）
    # 位置: config/predefined_edges.yaml
    # 说明: 包含无法从POB数据自动提取的关键隐含知识
    script_dir = Path(__file__).parent
    predefined_edges_path = script_dir.parent / 'config' / 'predefined_edges.yaml'
    
    if predefined_edges_path.exists():
        print(f"[INFO] 预置边配置: {predefined_edges_path}")
    else:
        print(f"[WARN] 预置边配置文件不存在: {predefined_edges_path}")
    
    entity_stats = init_entity_index(str(pob_path), str(entities_db))
    formula_stats = init_formula_library(str(pob_path), str(formulas_db), str(entities_db))
    rules_stats = init_rules_db(str(rules_db), str(entities_db))
    graph_stats = init_attribute_graph(
        str(graph_db), 
        str(entities_db), 
        str(rules_db),
        predefined_edges_path=str(predefined_edges_path) if predefined_edges_path.exists() else None
    )
    
    # 提取机制
    modcache_path = pob_path / 'Data' / 'ModCache.lua'
    if modcache_path.exists():
        mechanism_stats = extract_mechanisms(str(modcache_path), str(kb_path / 'mechanisms.db'), str(entities_db))
    else:
        mechanism_stats = {'mechanisms': 0}
    
    update_version_yaml(str(kb_path))
    
    # 导入启发记录
    heuristic_stats = import_heuristic_records(str(kb_path), str(rules_db), str(graph_db))
    
    # 最终统计
    print("\n" + "=" * 60)
    print("初始化完成")
    print("=" * 60)
    print(f"实体索引: {entity_stats['total']} 个实体")
    uf = formula_stats.get('universal_formulas', 0)
    sm_total = formula_stats.get('stat_mappings', {}).get('total', 0)
    gf_total = formula_stats.get('gap_formulas', {}).get('total', 0)
    print(f"公式索引: 通用{uf} + 映射{sm_total} + 缺口{gf_total} = {formula_stats.get('total', 0)} 条")
    print(f"规则库:   {rules_stats['total']} 条规则")
    print(f"关联图:   {graph_stats['nodes']} 个节点, {graph_stats['edges']} 条边")
    print(f"机制库:   {mechanism_stats['mechanisms']} 个机制, {mechanism_stats.get('sources', 0)} 个来源")
    print(f"启发记录: {heuristic_stats['imported']} 条已导入")


if __name__ == '__main__':
    main()
