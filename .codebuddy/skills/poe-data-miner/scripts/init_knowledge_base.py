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
    初始化关联图 - 从实体和规则库构建完整图
    
    数据流:
    1. entities.db → graph_nodes (entity, mechanism, attribute) + graph_edges (has_type, has_stat)
    2. rules.db → graph_edges (requires, excludes, provides 等)
    3. predefined_edges.yaml → 预置边
    """
    print("\n" + "=" * 60)
    print("4. 初始化关联图")
    print("=" * 60)
    
    # Step 1: 创建图数据库（初始化表结构并加载预置边）
    print("初始化图数据库结构...")
    graph = AttributeGraph(db_path, predefined_edges_path=predefined_edges_path)
    
    # Step 2: 清理旧的规则边 (status = 'verified')，保留预置边
    print("\n清理旧数据...")
    graph_conn = sqlite3.connect(db_path)
    graph_cursor = graph_conn.cursor()
    
    graph_cursor.execute("DELETE FROM graph_edges WHERE status = 'verified'")
    deleted_edges = graph_cursor.rowcount
    graph_cursor.execute("DELETE FROM graph_nodes WHERE type IN ('entity', 'mechanism', 'attribute')")
    deleted_nodes = graph_cursor.rowcount
    graph_conn.commit()
    print(f"  清理 {deleted_nodes} 个旧节点, {deleted_edges} 条旧边")
    graph_conn.close()
    
    # Step 3: 从实体库构建节点和属性边
    print("\n从实体库构建节点和属性边...")
    entities_conn = sqlite3.connect(entities_db_path)
    entities_cursor = entities_conn.cursor()
    
    # 查询所有实体
    entities_cursor.execute('''
        SELECT id, name, type, skill_types, stats, constant_stats, quality_stats, data_json
        FROM entities
    ''')
    rows = entities_cursor.fetchall()
    print(f"  找到 {len(rows)} 个实体")
    
    # 转换为字典列表
    entities = []
    for row in rows:
        eid, name, etype, skill_types_json, stats_json, constant_stats_json, quality_stats_json, data_json = row
        entities.append({
            'id': eid,
            'name': name or eid,
            'type': etype,
            'skill_types': json.loads(skill_types_json) if skill_types_json else [],
            'stats': json.loads(stats_json) if stats_json else [],
            'constant_stats': json.loads(constant_stats_json) if constant_stats_json else [],
            'quality_stats': json.loads(quality_stats_json) if quality_stats_json else [],
            'data': json.loads(data_json) if data_json else {}
        })
    
    entities_conn.close()
    
    # 调用 build_from_entities 创建节点和 has_type/has_stat 边
    graph.build_from_entities(entities)
    print(f"  已创建实体节点和属性边")
    
    # Step 4: 从规则库生成规则边
    print("\n从规则库生成规则边...")
    
    rules_conn = sqlite3.connect(rules_db_path)
    rules_cursor = rules_conn.cursor()
    
    graph_conn = sqlite3.connect(db_path)
    graph_cursor = graph_conn.cursor()
    
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
    mechanism_nodes = set()  # 记录机制节点
    
    for rule in rules:
        (rule_id, category, source_entity, target_entity, relation_type,
         condition, effect, evidence, source_layer, source_formula,
         heuristic_record_id, verified_at) = rule
        
        # 跳过没有 source_entity 的规则
        if not source_entity:
            continue
        
        # 根据规则类型处理
        if category == 'constraint':
            # constraint 规则：从 condition 字段提取真正的目标节点
            import re
            
            # 提取 requireSkillTypes
            req_match = re.search(r'requireSkillTypes:\s*([^\n]+)', condition or '')
            if req_match:
                types_str = req_match.group(1).strip()
                # 分割多个类型（逗号分隔）
                skill_types = [t.strip() for t in types_str.split(',') if t.strip() and t.strip() not in ('AND', 'OR', 'NOT')]
                
                for skill_type in skill_types:
                    node_set.add(skill_type)
                    mechanism_nodes.add(skill_type)
                    
                    try:
                        graph_cursor.execute('''
                            INSERT INTO graph_edges (
                                source_node, target_node, edge_type, weight, attributes,
                                status, source_rule, heuristic_record_id, verified_at,
                                condition, effect, evidence, created_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            source_entity,
                            skill_type,
                            'requires',
                            1.0,
                            json.dumps({'category': category, 'source_layer': source_layer}, ensure_ascii=False),
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
                        pass  # 忽略重复边
            
            # 提取 excludeSkillTypes
            exc_match = re.search(r'excludeSkillTypes:\s*([^\n]+)', condition or '')
            if exc_match:
                types_str = exc_match.group(1).strip()
                skill_types = [t.strip() for t in types_str.split(',') if t.strip() and t.strip() not in ('AND', 'OR', 'NOT')]
                
                for skill_type in skill_types:
                    node_set.add(skill_type)
                    mechanism_nodes.add(skill_type)
                    
                    try:
                        graph_cursor.execute('''
                            INSERT INTO graph_edges (
                                source_node, target_node, edge_type, weight, attributes,
                                status, source_rule, heuristic_record_id, verified_at,
                                condition, effect, evidence, created_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            source_entity,
                            skill_type,
                            'excludes',
                            1.0,
                            json.dumps({'category': category, 'source_layer': source_layer}, ensure_ascii=False),
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
                        pass
            
            # 提取 effect 字段中的 addSkillTypes（因果链关键！）
            add_match = re.search(r'addSkillTypes:\s*([^\n]+)', effect or '')
            if add_match:
                types_str = add_match.group(1).strip()
                skill_types = [t.strip() for t in types_str.split(',') if t.strip()]
                
                for skill_type in skill_types:
                    node_set.add(skill_type)
                    mechanism_nodes.add(skill_type)
                    
                    try:
                        graph_cursor.execute('''
                            INSERT INTO graph_edges (
                                source_node, target_node, edge_type, weight, attributes,
                                status, source_rule, heuristic_record_id, verified_at,
                                condition, effect, evidence, created_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            source_entity,
                            skill_type,
                            'provides',
                            1.0,
                            json.dumps({'category': category, 'source_layer': source_layer}, ensure_ascii=False),
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
                        pass
        
        elif category == 'relation':
            # relation 规则：直接使用 target_entity，但标记为机制节点
            if not target_entity:
                continue
            
            node_set.add(source_entity)
            node_set.add(target_entity)
            mechanism_nodes.add(target_entity)
            
            edge_type = relation_type if relation_type else 'relates'
            
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
                    1.0,
                    json.dumps({'category': category, 'source_layer': source_layer}, ensure_ascii=False),
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
        
        elif category == 'formula_application':
            # formula_application 规则：使用 uses_formula 边类型
            if not source_formula:
                continue
            
            node_set.add(source_entity)
            node_set.add(source_formula)
            
            try:
                graph_cursor.execute('''
                    INSERT INTO graph_edges (
                        source_node, target_node, edge_type, weight, attributes,
                        status, source_rule, heuristic_record_id, verified_at,
                        condition, effect, evidence, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    source_entity,
                    source_formula,
                    'uses_formula',
                    1.0,
                    json.dumps({'category': category, 'source_layer': source_layer}, ensure_ascii=False),
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
                pass
    
    graph_conn.commit()
    print(f"  生成 {edge_count} 条规则边")
    
    # Step 5: 确保规则涉及的节点存在（部分可能已在build_from_entities中创建）
    print("确保规则节点存在...")
    new_nodes = 0
    new_mechanisms = 0
    for node_id in node_set:
        graph_cursor.execute('SELECT id FROM graph_nodes WHERE id = ?', (node_id,))
        if not graph_cursor.fetchone():
            # 判断节点类型
            node_type = 'mechanism' if node_id in mechanism_nodes else 'entity'
            graph_cursor.execute('''
                INSERT INTO graph_nodes (id, name, type, created_at)
                VALUES (?, ?, ?, ?)
            ''', (node_id, node_id, node_type, datetime.now().isoformat()))
            new_nodes += 1
            if node_type == 'mechanism':
                new_mechanisms += 1
    
    graph_conn.commit()
    print(f"  新增 {new_nodes} 个规则节点 ({new_mechanisms} 个机制节点)")
    
    # 预置边已在 AttributeGraph 构造函数中加载
    
    # 关闭连接
    rules_conn.close()
    graph_conn.close()
    
    # Step 6: 构建类型层（启发式推理扩展）
    print("\n构建类型层节点...")
    type_stats = build_type_layer(db_path, entities_db_path)
    print(f"  类型节点: {type_stats['type_nodes']}")
    print(f"  has_type 边: {type_stats['has_type_edges']}")
    
    # Step 7: 构建属性层
    print("\n构建属性层节点...")
    property_stats = build_property_layer(db_path)
    print(f"  属性节点: {property_stats['property_nodes']}")
    print(f"  implies 边: {property_stats['implies_edges']}")
    
    # Step 8: 构建触发机制层
    print("\n构建触发机制层节点...")
    trigger_stats = build_trigger_layer(db_path, entities_db_path)
    print(f"  触发机制节点: {trigger_stats['trigger_mechanisms']}")
    print(f"  produces 边: {trigger_stats['produces_edges']}")
    print(f"  triggers_via 边: {trigger_stats['triggers_via_edges']}")
    
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


def build_type_layer(graph_db_path: str, entities_db_path: str) -> dict:
    """
    构建类型层节点（启发式推理扩展 Phase 2）
    
    从 entities.db 提取所有唯一的 skill_types，创建 type_node 节点
    
    Returns:
        {'type_nodes': int, 'has_type_edges': int}
    """
    # 连接数据库
    graph_conn = sqlite3.connect(graph_db_path)
    graph_cursor = graph_conn.cursor()
    
    entities_conn = sqlite3.connect(entities_db_path)
    entities_cursor = entities_conn.cursor()
    
    # 提取所有唯一的 skill_types
    entities_cursor.execute('''
        SELECT DISTINCT json_each.value
        FROM entities, json_each(skill_types)
        WHERE skill_types IS NOT NULL AND skill_types != '[]'
    ''')
    
    skill_types = [row[0] for row in entities_cursor.fetchall()]
    print(f"  发现 {len(skill_types)} 个唯一类型")
    
    # 创建 type_node 节点
    type_nodes = 0
    has_type_edges = 0
    
    for skill_type in skill_types:
        # 创建类型节点（如果不存在）
        node_id = f"type_{skill_type.lower().replace(' ', '_')}"
        
        try:
            graph_cursor.execute('''
                INSERT OR IGNORE INTO graph_nodes (id, type, name, attributes, created_at)
                VALUES (?, 'type_node', ?, ?, ?)
            ''', (
                node_id,
                skill_type,
                json.dumps({'original_type': skill_type}, ensure_ascii=False),
                datetime.now().isoformat()
            ))
            
            if graph_cursor.rowcount > 0:
                type_nodes += 1
        except Exception as e:
            pass
    
    graph_conn.commit()
    entities_conn.close()
    
    # 统计 has_type 边（已由 build_from_entities 创建）
    graph_cursor.execute('''
        SELECT COUNT(*) FROM graph_edges WHERE edge_type = 'has_type'
    ''')
    has_type_edges = graph_cursor.fetchone()[0]
    
    graph_conn.close()
    
    return {
        'type_nodes': type_nodes,
        'has_type_edges': has_type_edges
    }


def build_property_layer(graph_db_path: str) -> dict:
    """
    构建属性层节点（启发式推理扩展 Phase 2）
    
    定义类型到属性的映射规则，创建 property_node 节点和 implies 边
    
    Returns:
        {'property_nodes': int, 'implies_edges': int}
    """
    # 定义类型到属性的映射规则
    type_property_mappings = {
        # Meta 技能相关
        'Meta': {
            'properties': ['UsesTriggerMechanism'],
            'description': 'Meta技能使用触发机制'
        },
        'Meta + GeneratesEnergy': {
            'properties': ['UsesEnergySystem'],
            'description': 'Meta技能生成能量时使用能量系统'
        },
        
        # Hazard 相关
        'Hazard': {
            'properties': ['DoesNotUseEnergy', 'DoesNotProduceTriggered'],
            'description': 'Hazard不使用能量系统，不产生Triggered标签'
        },
        
        # Triggered 标签相关
        'Triggered': {
            'properties': ['CannotGenerateEnergyForMeta'],
            'description': 'Triggered标签的技能无法为Meta技能生成能量'
        },
        
        # Duration 相关
        'Duration': {
            'properties': ['HasDuration'],
            'description': '持续时间技能'
        },
        
        # Triggers 相关
        'Triggers': {
            'properties': ['CanTriggerOtherSkills'],
            'description': '可触发其他技能'
        }
    }
    
    # 连接数据库
    graph_conn = sqlite3.connect(graph_db_path)
    graph_cursor = graph_conn.cursor()
    
    property_nodes = 0
    implies_edges = 0
    
    # 收集所有属性
    all_properties = set()
    for mapping in type_property_mappings.values():
        all_properties.update(mapping['properties'])
    
    # 创建 property_node 节点
    for prop in all_properties:
        node_id = f"prop_{prop.lower().replace(' ', '_')}"
        
        try:
            graph_cursor.execute('''
                INSERT OR IGNORE INTO graph_nodes (id, type, name, attributes, created_at)
                VALUES (?, 'property_node', ?, ?, ?)
            ''', (
                node_id,
                prop,
                json.dumps({'description': prop}, ensure_ascii=False),
                datetime.now().isoformat()
            ))
            
            if graph_cursor.rowcount > 0:
                property_nodes += 1
        except Exception as e:
            pass
    
    # 创建 implies 边（从 type_node 到 property_node）
    for type_combo, mapping in type_property_mappings.items():
        # 解析组合类型
        types = [t.strip() for t in type_combo.split('+')]
        
        # 为每个属性创建 implies 边
        for prop in mapping['properties']:
            # 对于组合类型，我们需要更复杂的逻辑
            # 这里简化处理：为第一个类型创建 implies 边
            if len(types) == 1:
                type_node_id = f"type_{types[0].lower().replace(' ', '_')}"
                prop_node_id = f"prop_{prop.lower().replace(' ', '_')}"
                
                try:
                    graph_cursor.execute('''
                        INSERT OR IGNORE INTO graph_edges (
                            source_node, target_node, edge_type, weight, attributes,
                            status, evidence, created_at
                        ) VALUES (?, ?, 'implies', 1.0, ?, 'verified', ?, ?)
                    ''', (
                        type_node_id,
                        prop_node_id,
                        json.dumps({'description': mapping['description']}, ensure_ascii=False),
                        mapping['description'],
                        datetime.now().isoformat()
                    ))
                    
                    if graph_cursor.rowcount > 0:
                        implies_edges += 1
                except Exception as e:
                    pass
    
    graph_conn.commit()
    graph_conn.close()
    
    return {
        'property_nodes': property_nodes,
        'implies_edges': implies_edges
    }


def build_trigger_layer(graph_db_path: str, entities_db_path: str) -> dict:
    """
    构建触发机制层节点（启发式推理扩展 Phase 2）
    
    定义触发机制类型，创建 trigger_mechanism 节点、produces 边和 triggers_via 边
    
    Returns:
        {'trigger_mechanisms': int, 'produces_edges': int, 'triggers_via_edges': int}
    """
    # 定义触发机制类型
    trigger_mechanisms = {
        'MetaTrigger': {
            'produces': ['Triggered'],
            'description': 'Meta触发机制，产生Triggered标签'
        },
        'HazardTrigger': {
            'produces': [],
            'description': 'Hazard触发机制，不产生Triggered标签'
        },
        'CreationTrigger': {
            'produces': [],
            'description': 'Creation触发机制（如Doedre），不产生Triggered标签'
        }
    }
    
    # 定义实体到触发机制的映射
    # 从 entities.db 中识别哪些实体使用哪种触发机制
    entity_trigger_mapping = {
        # Meta 技能使用 MetaTrigger
        'MetaCastOnCritPlayer': 'MetaTrigger',
        'MetaCastOnMeleeKillPlayer': 'MetaTrigger',
        'MetaCastOnDeathPlayer': 'MetaTrigger',
        
        # Hazard 技能使用 HazardTrigger
        'SpearfieldPlayer': 'HazardTrigger',
        'TrailOfCaltropsPlayer': 'HazardTrigger',
        
        # Creation 技能使用 CreationTrigger
        'SupportDoedresUndoingPlayer': 'CreationTrigger'
    }
    
    # 连接数据库
    graph_conn = sqlite3.connect(graph_db_path)
    graph_cursor = graph_conn.cursor()
    
    trigger_mech_count = 0
    produces_edges = 0
    triggers_via_edges = 0
    
    # 创建 trigger_mechanism 节点
    for mech_name, mech_info in trigger_mechanisms.items():
        node_id = f"trigger_{mech_name.lower()}"
        
        try:
            graph_cursor.execute('''
                INSERT OR IGNORE INTO graph_nodes (id, type, name, attributes, created_at)
                VALUES (?, 'trigger_mechanism', ?, ?, ?)
            ''', (
                node_id,
                mech_name,
                json.dumps({
                    'description': mech_info['description'],
                    'produces': mech_info['produces']
                }, ensure_ascii=False),
                datetime.now().isoformat()
            ))
            
            if graph_cursor.rowcount > 0:
                trigger_mech_count += 1
        except Exception as e:
            pass
        
        # 创建 produces 边
        for label in mech_info['produces']:
            label_node_id = f"type_{label.lower()}"
            
            # 确保标签节点存在
            try:
                graph_cursor.execute('''
                    INSERT OR IGNORE INTO graph_nodes (id, type, name, created_at)
                    VALUES (?, 'type_node', ?, ?)
                ''', (label_node_id, label, datetime.now().isoformat()))
            except:
                pass
            
            # 创建 produces 边
            try:
                graph_cursor.execute('''
                    INSERT OR IGNORE INTO graph_edges (
                        source_node, target_node, edge_type, weight, attributes,
                        status, evidence, created_at
                    ) VALUES (?, ?, 'produces', 1.0, ?, 'verified', ?, ?)
                ''', (
                    node_id,
                    label_node_id,
                    json.dumps({'description': f'{mech_name}产生{label}标签'}, ensure_ascii=False),
                    f'{mech_name} produces {label}',
                    datetime.now().isoformat()
                ))
                
                if graph_cursor.rowcount > 0:
                    produces_edges += 1
            except Exception as e:
                pass
    
    # 创建 triggers_via 边（从实体到触发机制）
    for entity_id, trigger_mech in entity_trigger_mapping.items():
        trigger_node_id = f"trigger_{trigger_mech.lower()}"
        
        # 检查实体节点是否存在
        graph_cursor.execute('SELECT id FROM graph_nodes WHERE id = ?', (entity_id,))
        if graph_cursor.fetchone():
            try:
                graph_cursor.execute('''
                    INSERT OR IGNORE INTO graph_edges (
                        source_node, target_node, edge_type, weight, attributes,
                        status, evidence, created_at
                    ) VALUES (?, ?, 'triggers_via', 1.0, ?, 'verified', ?, ?)
                ''', (
                    entity_id,
                    trigger_node_id,
                    json.dumps({'description': f'{entity_id}通过{trigger_mech}触发'}, ensure_ascii=False),
                    f'{entity_id} triggers via {trigger_mech}',
                    datetime.now().isoformat()
                ))
                
                if graph_cursor.rowcount > 0:
                    triggers_via_edges += 1
            except Exception as e:
                pass
    
    graph_conn.commit()
    graph_conn.close()
    
    return {
        'trigger_mechanisms': trigger_mech_count,
        'produces_edges': produces_edges,
        'triggers_via_edges': triggers_via_edges
    }


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
