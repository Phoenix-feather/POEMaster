#!/usr/bin/env python3
"""
完整初始化知识库，记录日志到文件
"""
import sys
import io
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
from datetime import datetime

# 添加脚本目录
SCRIPTS_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPTS_DIR))

# 导入初始化函数
from init_knowledge_base import (
    init_entity_index,
    init_formula_library,
    init_rules_db,
    init_attribute_graph,
    extract_mechanisms,
    update_version_yaml,
    import_heuristic_records
)
from pob_paths import get_pob_path, get_knowledge_base_path, validate_pob_path

def main():
    # 路径
    pob_path = get_pob_path()
    kb_path = get_knowledge_base_path()
    kb_path.mkdir(parents=True, exist_ok=True)
    
    # 数据库路径
    entities_db = kb_path / 'entities.db'
    formulas_db = kb_path / 'formulas.db'
    rules_db = kb_path / 'rules.db'
    graph_db = kb_path / 'graph.db'
    
    # 预置边
    script_dir = Path(__file__).parent
    predefined_edges_path = script_dir.parent / 'config' / 'predefined_edges.yaml'
    
    # 日志文件
    log_file = kb_path / 'init_log.txt'
    
    print(f"开始初始化，日志将保存到: {log_file}")
    
    with open(log_file, 'w', encoding='utf-8') as f:
        f.write(f"POE知识库初始化日志\n")
        f.write(f"时间: {datetime.now().isoformat()}\n")
        f.write(f"POB数据: {pob_path}\n")
        f.write(f"知识库: {kb_path}\n")
        f.write("=" * 60 + "\n\n")
    
    results = {}
    
    # Step 1: 实体索引
    print("\n[1/6] 初始化实体索引...")
    try:
        entity_stats = init_entity_index(str(pob_path), str(entities_db))
        results['entity'] = entity_stats
        print(f"  ✅ 完成: {entity_stats['total']} 个实体")
    except Exception as e:
        print(f"  ❌ 失败: {e}")
        results['entity'] = {'error': str(e)}
    
    # Step 2: 公式库
    print("\n[2/6] 初始化公式库...")
    try:
        formula_stats = init_formula_library(str(pob_path), str(formulas_db), str(entities_db))
        results['formula'] = formula_stats
        print(f"  ✅ 完成: {formula_stats.get('total', 0)} 条公式")
    except Exception as e:
        print(f"  ❌ 失败: {e}")
        import traceback
        traceback.print_exc()
        results['formula'] = {'error': str(e)}
    
    # Step 3: 规则库
    print("\n[3/6] 初始化规则库...")
    try:
        rules_stats = init_rules_db(str(rules_db), str(entities_db))
        results['rules'] = rules_stats
        print(f"  ✅ 完成: {rules_stats['total']} 条规则")
    except Exception as e:
        print(f"  ❌ 失败: {e}")
        results['rules'] = {'error': str(e)}
    
    # Step 4: 关联图
    print("\n[4/6] 初始化关联图...")
    try:
        graph_stats = init_attribute_graph(
            str(graph_db),
            str(entities_db),
            str(rules_db),
            predefined_edges_path=str(predefined_edges_path) if predefined_edges_path.exists() else None,
            pob_path=str(pob_path),
            use_verified_mappings=True
        )
        results['graph'] = graph_stats
        print(f"  ✅ 完成: {graph_stats['nodes']} 节点, {graph_stats['edges']} 边")
    except Exception as e:
        print(f"  ❌ 失败: {e}")
        import traceback
        traceback.print_exc()
        results['graph'] = {'error': str(e)}
    
    # Step 5: 机制提取
    print("\n[5/6] 提取机制...")
    modcache_path = pob_path / 'Data' / 'ModCache.lua'
    if modcache_path.exists():
        try:
            mechanism_stats = extract_mechanisms(
                str(modcache_path),
                str(kb_path / 'mechanisms.db'),
                str(entities_db)
            )
            results['mechanism'] = mechanism_stats
            print(f"  ✅ 完成: {mechanism_stats.get('mechanisms', 0)} 个机制")
        except Exception as e:
            print(f"  ❌ 失败: {e}")
            results['mechanism'] = {'error': str(e)}
    else:
        print("  ⚠ 跳过: ModCache.lua 不存在")
        results['mechanism'] = {'skipped': True}
    
    # Step 6: 版本和启发记录
    print("\n[6/6] 更新版本和启发记录...")
    try:
        update_version_yaml(str(kb_path))
        heuristic_stats = import_heuristic_records(str(kb_path), str(rules_db), str(graph_db))
        print(f"  ✅ 完成")
    except Exception as e:
        print(f"  ❌ 失败: {e}")
    
    # 汇总
    print("\n" + "=" * 60)
    print("初始化完成汇总")
    print("=" * 60)
    
    for key, value in results.items():
        if 'error' in value:
            print(f"{key}: ❌ {value['error']}")
        elif 'total' in value:
            print(f"{key}: ✅ {value['total']}")
        else:
            print(f"{key}: {value}")
    
    return results

if __name__ == '__main__':
    main()
