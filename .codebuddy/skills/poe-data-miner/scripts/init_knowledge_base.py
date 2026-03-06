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
from rules_extractor import RulesExtractor
from attribute_graph import AttributeGraph, NodeType, EdgeType, GraphNode, GraphEdge

# 导入 schema 验证
try:
    from schema_validator import validate_before_init
    HAS_SCHEMA_VALIDATOR = True
except ImportError:
    HAS_SCHEMA_VALIDATOR = False


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


def init_rules_db(db_path: str, entities_db_path: str) -> dict:
    """初始化规则库 - 使用 RulesExtractor 封装类"""
    print("\n" + "=" * 60)
    print("2. 初始化规则库")
    print("=" * 60)
    
    # 使用 RulesExtractor 封装类
    extractor = RulesExtractor(db_path)
    
    # ========== Layer 1: 从实体提取属性规则 ==========
    print("提取 Layer 1 规则 (实体-stats关系)...")
    
    entities_conn = sqlite3.connect(entities_db_path)
    entities_cursor = entities_conn.cursor()
    
    # 读取实体数据
    entities_cursor.execute("SELECT id, name, type, skill_types, constant_stats, stats, data_json FROM entities")
    entities = []
    for row in entities_cursor.fetchall():
        entity_id, name, entity_type, skill_types, constant_stats, stats, data_json = row
        
        entity = {
            'id': entity_id,
            'name': name or entity_id,
            'type': entity_type,
            'skill_types': json.loads(skill_types) if skill_types else [],
            'constant_stats': json.loads(constant_stats) if constant_stats else [],
            'stats': json.loads(stats) if stats else []
        }
        entities.append(entity)
    
    entities_conn.close()
    
    # 使用 RulesExtractor 提取 Layer 1 规则
    layer1_rules = extractor.extract_layer1_stats(entities)
    print(f"  Layer 1: {len(layer1_rules)} 条规则")
    
    # ========== Layer 2: 从 stat_mapping 提取属性映射规则 ==========
    print("提取 Layer 2 规则 (属性映射)...")
    
    entities_conn = sqlite3.connect(entities_db_path)
    entities_cursor = entities_conn.cursor()
    
    # 读取 stat_mapping 实体 (注意：实际数据类型是 stat_mapping，不是 mod_definition)
    entities_cursor.execute("SELECT data_json FROM entities WHERE type='stat_mapping'")
    stat_mappings = []
    for row in entities_cursor.fetchall():
        data = json.loads(row[0])
        stat_mappings.append(data)
    
    entities_conn.close()
    
    # 使用 RulesExtractor 提取 Layer 2 规则
    layer2_rules = extractor.extract_layer2_statmap(stat_mappings)
    print(f"  Layer 2: {len(layer2_rules)} 条规则")
    
    # ========== Layer 3: 从计算模块提取公式和约束规则 ==========
    print("提取 Layer 3 规则 (计算模块)...")
    
    entities_conn = sqlite3.connect(entities_db_path)
    entities_cursor = entities_conn.cursor()
    
    # 读取 calculation_module 实体
    entities_cursor.execute("SELECT data_json FROM entities WHERE type='calculation_module'")
    functions = []
    for row in entities_cursor.fetchall():
        data = json.loads(row[0])
        functions.append(data)
    
    entities_conn.close()
    
    # 使用 RulesExtractor 提取 Layer 3 规则
    layer3_rules = extractor.extract_layer3_calccode(functions)
    print(f"  Layer 3: {len(layer3_rules)} 条规则")
    
    # ========== 添加预置规则 ==========
    print("添加预置规则...")
    predefined_rules = [
        {
            'id': 'rule_triggered_energy_block',
            'name': '触发技能能量限制',
            'category': 'constraint',
            'condition': 'skill has SkillType.Triggered',
            'effect': 'energy generation = 0',
            'description': '被触发的技能无法为元技能提供能量',
            'source_layer': 3
        },
        {
            'id': 'rule_hazard_bypass',
            'name': 'Hazard区域绕过',
            'category': 'bypass',
            'condition': 'damage source = Hazard zone explosion',
            'effect': 'bypasses Triggered energy limit',
            'description': "Doedre's Undoing通过Hazard区域爆炸绕过触发限制",
            'source_layer': 3
        },
        {
            'id': 'rule_energy_formula',
            'name': '能量获取公式',
            'category': 'formula',
            'formula': 'energy = base × (1 + Σinc) × Πmore',
            'description': '能量获取公式: 基础值 × (1 + 加法叠加) × 乘法叠加',
            'source_layer': 3
        },
        {
            'id': 'rule_inc_stacking',
            'name': 'INC加成叠加',
            'category': 'formula',
            'formula': 'total_inc = Σ(all_inc_modifiers)',
            'description': '所有increased修饰符线性叠加',
            'source_layer': 3
        },
        {
            'id': 'rule_more_stacking',
            'name': 'MORE加成叠加',
            'category': 'formula',
            'formula': 'total_more = Π(all_more_modifiers)',
            'description': '所有more修饰符乘法叠加',
            'source_layer': 3
        }
    ]
    
    # 直接插入预置规则
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    for rule in predefined_rules:
        cursor.execute('''
            INSERT OR REPLACE INTO rules
            (id, name, category, condition, effect, formula, description, source_layer)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            rule['id'], rule['name'], rule['category'],
            rule.get('condition'), rule.get('effect'), rule.get('formula'),
            rule.get('description'), rule['source_layer']
        ))
    
    conn.commit()
    
    # 保存所有提取的规则
    extractor.save_rules_to_db()
    
    # 统计
    cursor.execute("SELECT category, COUNT(*) FROM rules GROUP BY category")
    cat_counts = dict(cursor.fetchall())
    cursor.execute("SELECT COUNT(*) FROM rules")
    total = cursor.fetchone()[0]
    
    conn.close()
    extractor.close()
    
    print(f"[OK] 已创建 {total} 条规则")
    for c, count in cat_counts.items():
        print(f"  - {c}: {count}")
    
    return {'total': total, 'by_category': cat_counts}


def init_attribute_graph(db_path: str, entities_db_path: str, rules_db_path: str, predefined_edges_path: str = None) -> dict:
    """初始化关联图 - 使用 AttributeGraph 封装类"""
    print("\n" + "=" * 60)
    print("3. 初始化关联图")
    print("=" * 60)
    
    # 使用 AttributeGraph 封装类（传递预置边配置文件路径）
    graph = AttributeGraph(db_path, predefined_edges_path=predefined_edges_path)
    
    # ========== 从实体索引创建节点和边 ==========
    print("从实体索引构建关联图...")
    
    entities_conn = sqlite3.connect(entities_db_path)
    entities_cursor = entities_conn.cursor()
    
    # 读取所有实体
    entities_cursor.execute("SELECT id, name, type, skill_types, constant_stats, stats FROM entities")
    entities = []
    for row in entities_cursor.fetchall():
        entity_id, name, entity_type, skill_types, constant_stats, stats = row
        entities.append({
            'id': entity_id,
            'name': name or entity_id,
            'type': entity_type,
            'skill_types': json.loads(skill_types) if skill_types else [],
            'constant_stats': json.loads(constant_stats) if constant_stats else [],
            'stats': json.loads(stats) if stats else []
        })
    
    entities_conn.close()
    
    # 使用 AttributeGraph.build_from_entities()
    graph.build_from_entities(entities)
    
    # ========== 从规则创建约束节点 ==========
    print("从规则构建约束节点...")
    
    rules_conn = sqlite3.connect(rules_db_path)
    rules_cursor = rules_conn.cursor()
    
    # 读取约束和绕过规则
    rules_cursor.execute("SELECT id, name, category, condition, effect, description FROM rules WHERE category IN ('constraint', 'bypass', 'formula')")
    rules = []
    for row in rules_cursor.fetchall():
        rules.append({
            'id': row[0],
            'name': row[1],
            'category': row[2],
            'condition': row[3],
            'effect': row[4],
            'description': row[5]
        })
    
    rules_conn.close()
    
    # 使用 AttributeGraph.build_from_rules()
    graph.build_from_rules(rules)
    
    # 预置边已在 AttributeGraph 构造函数中通过 predefined_edges_path 加载
    
    # ========== 统计 ==========
    stats = graph.get_stats()
    
    graph.close()
    
    print(f"[OK] 已创建 {stats['node_count']} 个节点")
    for t, c in stats['node_types'].items():
        print(f"  - {t}: {c}")
    
    print(f"[OK] 已创建 {stats['edge_count']} 条边")
    for t, c in stats['edge_types'].items():
        print(f"  - {t}: {c}")
    
    return {
        'nodes': stats['node_count'],
        'edges': stats['edge_count'],
        'node_types': stats['node_types'],
        'edge_types': stats['edge_types']
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
    print("4. 导入启发记录")
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
    print("5. 提取机制 (基于 stat ID)")
    print("=" * 60)
    
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


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='初始化POE知识库')
    parser.add_argument('pob_path', help='POB数据目录路径')
    parser.add_argument('--kb-path', default=None, help='知识库目录路径')
    
    args = parser.parse_args()
    
    # 转换为绝对路径
    pob_path = Path(args.pob_path).resolve()
    kb_path = Path(args.kb_path).resolve() if args.kb_path else pob_path.parent / 'knowledge_base'
    
    # 创建目录
    kb_path.mkdir(parents=True, exist_ok=True)
    
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
    print(f"规则库:   {rules_stats['total']} 条规则")
    print(f"关联图:   {graph_stats['nodes']} 个节点, {graph_stats['edges']} 条边")
    print(f"机制库:   {mechanism_stats['mechanisms']} 个机制, {mechanism_stats.get('sources', 0)} 个来源")
    print(f"启发记录: {heuristic_stats['imported']} 条已导入")


if __name__ == '__main__':
    main()
