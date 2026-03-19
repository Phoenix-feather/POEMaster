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
from entity_index import EntityIndex, EntityEnricher
from mechanism_extractor import MechanismExtractor
from support_matcher import SupportMatcher
from formula_index import init_formula_index
from pob_paths import get_pob_path, get_knowledge_base_path, validate_pob_path

# 导入 StatDescriber 桥接
try:
    from stat_describer_bridge import StatDescriberBridge
    HAS_STAT_DESCRIBER = True
except ImportError:
    HAS_STAT_DESCRIBER = False

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


def enrich_entities(pob_path: str, db_path: str) -> dict:
    """
    Step 2: 解读层预计算（Phase 2a）
    
    为所有实体预计算 summary / key_mechanics / display_stats 字段。
    使用 StatDescriber 桥接（lupa）生成精确的 stat 描述文本。
    
    设计原则：如果查询不到说明设计有漏洞，不做动态兜底。
    """
    print("\n" + "=" * 60)
    print("2. 解读层预计算 (summary / key_mechanics / display_stats)")
    print("=" * 60)
    
    # 初始化 StatDescriber 桥接
    stat_describer = None
    if HAS_LUPA and HAS_STAT_DESCRIBER:
        try:
            stat_describer = StatDescriberBridge(pob_path)
            if stat_describer.available:
                print(f"[OK] StatDescriber 桥接已就绪 (lupa)")
            else:
                print(f"[WARN] StatDescriber 加载失败: {stat_describer.error}")
                print(f"       display_stats 将回退到已有的 stat_descriptions")
                stat_describer = None
        except Exception as e:
            print(f"[WARN] StatDescriber 初始化异常: {e}")
            stat_describer = None
    else:
        missing = []
        if not HAS_LUPA:
            missing.append("lupa")
        if not HAS_STAT_DESCRIBER:
            missing.append("stat_describer_bridge")
        print(f"[WARN] 缺少依赖: {', '.join(missing)}")
        print(f"       display_stats 将回退到已有的 stat_descriptions")
    
    # 运行 enrichment
    index = EntityIndex(db_path)
    enricher = EntityEnricher(index, stat_describer=stat_describer)
    
    import time
    start = time.time()
    stats = enricher.enrich_all()
    elapsed = time.time() - start
    
    index.close()
    if stat_describer:
        stat_describer.close()
    
    total = stats['total']
    print(f"\n[OK] 解读层预计算完成 ({elapsed:.1f}s)")
    print(f"     - summary 非空: {stats['summary']}/{total} ({stats['summary']*100//total}%)")
    print(f"     - key_mechanics 非空: {stats['key_mechanics']}/{total} ({stats['key_mechanics']*100//total}%)")
    print(f"     - display_stats 非空: {stats['display_stats']}/{total} ({stats['display_stats']*100//total}%)")
    
    return stats


def init_formula_library(pob_path: str, db_path: str, entities_db_path: str) -> dict:
    """初始化公式库（v2: 3类公式索引）"""
    print("\n" + "=" * 60)
    print("3. 初始化公式索引")
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


def extract_mechanisms(modcache_path: str, db_path: str, entities_db_path: str = None,
                       pob_path: str = None) -> dict:
    """
    提取机制到数据库 (v2: 含行为描述提取 + mechanism_relations)
    
    Args:
        modcache_path: ModCache.lua 路径
        db_path: 输出数据库路径
        entities_db_path: 实体数据库路径
        pob_path: POB 根目录路径（用于行为提取）
    """
    print("\n" + "=" * 60)
    print("4. 提取机制 (v2: stat ID + 行为描述 + 关系)")
    print("=" * 60)
    
    # 检查 lupa 依赖
    if not HAS_LUPA:
        print("[警告] 缺少 lupa 库，无法提取机制")
        print("[提示] 请运行: pip install lupa")
        print("[提示] 机制提取将被跳过，知识库仍可正常使用\n")
        return {'mechanisms': 0, 'sources': 0, 'relations': 0}
    
    try:
        extractor = MechanismExtractor(
            modcache_path,
            entities_db_path=entities_db_path,
            pob_path=pob_path
        )
        extractor.parse_modcache()
        if entities_db_path:
            extractor.build_entity_mapping()
        extractor.identify_mechanisms()
        
        # v2: 加载 YAML 补充描述 + 行为提取
        extractor.load_yaml_descriptions()
        extractor.extract_behaviors()
        
        extractor.export_to_db(db_path)
        
        # 统计
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM mechanisms')
        mech_count = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM mechanism_sources')
        source_count = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM mechanism_relations')
        relation_count = cursor.fetchone()[0]
        # v2: 统计覆盖率
        cursor.execute('SELECT COUNT(*) FROM mechanisms WHERE friendly_name IS NOT NULL AND friendly_name != id')
        friendly_count = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM mechanisms WHERE behavior_description IS NOT NULL')
        behavior_count = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM mechanisms WHERE mechanism_category IS NOT NULL')
        category_count = cursor.fetchone()[0]
        conn.close()
        
        print(f"[OK] 提取了 {mech_count} 个机制, {source_count} 个来源, {relation_count} 条关系")
        print(f"     friendly_name: {friendly_count}/{mech_count}")
        print(f"     behavior_description: {behavior_count}/{mech_count}")
        print(f"     mechanism_category: {category_count}/{mech_count}")
        
        return {
            'mechanisms': mech_count,
            'sources': source_count,
            'relations': relation_count,
            'friendly_name_coverage': friendly_count,
            'behavior_coverage': behavior_count,
        }
    
    except Exception as e:
        print(f"[错误] 机制提取失败: {e}")
        import traceback
        traceback.print_exc()
        print("[提示] 知识库仍可正常使用，但缺少机制数据\n")
        return {'mechanisms': 0, 'sources': 0, 'relations': 0}


def compute_support_matching(entities_db_path: str, db_path: str) -> dict:
    """
    预计算辅助匹配系统 (Step 5)
    
    Args:
        entities_db_path: entities.db 的路径
        db_path: 输出 supports.db 的路径
    
    Returns:
        统计信息字典
    """
    print("\n" + "=" * 50)
    print("5. 辅助匹配系统")
    print("=" * 50)
    
    try:
        matcher = SupportMatcher(entities_db_path)
        matcher.load_data()
        matcher.compute_compatibility()
        matcher.compute_effects()
        matcher.compute_potentials()
        stats = matcher.export_to_db(db_path)
        
        # 附加统计
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM support_effects WHERE quantifiable = 1')
        quantifiable_count = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM support_effects')
        effects_total = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(DISTINCT effect_category) FROM support_effects')
        category_count = cursor.fetchone()[0]
        conn.close()
        
        print(f"[OK] 辅助匹配: {stats['compatibility']} 兼容对, "
              f"{stats['effects']} 效果, {stats['potentials']} 潜力推荐")
        print(f"     可量化: {quantifiable_count}/{effects_total}, "
              f"效果分类: {category_count} 种")
        
        stats['quantifiable'] = quantifiable_count
        stats['effect_categories'] = category_count
        return stats
    
    except Exception as e:
        print(f"[错误] 辅助匹配计算失败: {e}")
        import traceback
        traceback.print_exc()
        print("[提示] 知识库仍可正常使用，但缺少辅助匹配数据\n")
        return {'compatibility': 0, 'effects': 0, 'potentials': 0}


def run_completeness_check(kb_path: str) -> dict:
    """
    Step 7: 完整性校验（Phase 4, Task 8.1）
    
    检查所有数据库的覆盖率和数据质量：
    1. entities.db: summary / key_mechanics / display_stats 分类型覆盖率
    2. mechanisms.db: behavior_description / friendly_name / formula_abstract 覆盖率
    3. supports.db: compatibility / effects / potentials 完整性
    4. formulas.db: 各表数量合理性
    
    Returns:
        校验结果字典，含 issues 列表和 stats
    """
    print("\n" + "=" * 60)
    print("7. 完整性校验")
    print("=" * 60)
    
    kb = Path(kb_path)
    issues = []
    stats = {}
    
    # ===== 1. 实体库覆盖率 =====
    entities_db = kb / 'entities.db'
    if entities_db.exists():
        conn = sqlite3.connect(str(entities_db))
        cursor = conn.cursor()
        
        # 总量
        cursor.execute('SELECT COUNT(*) FROM entities')
        total = cursor.fetchone()[0]
        stats['entities_total'] = total
        
        # 分类型的 summary 覆盖率
        cursor.execute('''
            SELECT type, COUNT(*) as total,
                   SUM(CASE WHEN summary IS NOT NULL AND summary != '' THEN 1 ELSE 0 END) as has_summary,
                   SUM(CASE WHEN key_mechanics IS NOT NULL AND key_mechanics != '' AND key_mechanics != '[]' THEN 1 ELSE 0 END) as has_km,
                   SUM(CASE WHEN display_stats IS NOT NULL AND display_stats != '' AND display_stats != '[]' THEN 1 ELSE 0 END) as has_ds
            FROM entities GROUP BY type
        ''')
        
        type_coverage = {}
        total_summary = 0
        total_km = 0
        total_ds = 0
        
        print("\n  [实体库覆盖率 - 按类型]")
        print(f"  {'类型':<25} {'总数':>6} {'summary':>10} {'key_mech':>10} {'disp_stat':>10}")
        print(f"  {'-'*25} {'-'*6} {'-'*10} {'-'*10} {'-'*10}")
        
        for row in cursor.fetchall():
            etype, etotal, s_count, km_count, ds_count = row
            s_pct = s_count * 100 // etotal if etotal > 0 else 0
            km_pct = km_count * 100 // etotal if etotal > 0 else 0
            ds_pct = ds_count * 100 // etotal if etotal > 0 else 0
            
            print(f"  {etype:<25} {etotal:>6} {s_count:>5}({s_pct:>2}%) {km_count:>5}({km_pct:>2}%) {ds_count:>5}({ds_pct:>2}%)")
            
            type_coverage[etype] = {
                'total': etotal, 'summary': s_count,
                'key_mechanics': km_count, 'display_stats': ds_count
            }
            total_summary += s_count
            total_km += km_count
            total_ds += ds_count
        
        # 全局覆盖率
        s_global = total_summary * 100 // total if total > 0 else 0
        ds_global = total_ds * 100 // total if total > 0 else 0
        print(f"\n  全局: summary={total_summary}/{total}({s_global}%), "
              f"key_mechanics={total_km}/{total}, "
              f"display_stats={total_ds}/{total}({ds_global}%)")
        
        stats['entity_coverage'] = type_coverage
        stats['entity_summary_rate'] = s_global
        stats['entity_display_stats_rate'] = ds_global
        
        # 阈值检查
        # skill_definition 的 summary 应该 > 90%
        skill_cov = type_coverage.get('skill_definition', {})
        if skill_cov:
            skill_s_pct = skill_cov['summary'] * 100 // skill_cov['total'] if skill_cov['total'] > 0 else 0
            if skill_s_pct < 80:
                issues.append(f"skill_definition 的 summary 覆盖率低于 80%: {skill_s_pct}%")
        
        # passive_node 的 display_stats 应该 > 90%
        passive_cov = type_coverage.get('passive_node', {})
        if passive_cov:
            passive_ds_pct = passive_cov['display_stats'] * 100 // passive_cov['total'] if passive_cov['total'] > 0 else 0
            if passive_ds_pct < 80:
                issues.append(f"passive_node 的 display_stats 覆盖率低于 80%: {passive_ds_pct}%")
        
        conn.close()
    else:
        issues.append("entities.db 不存在")
    
    # ===== 2. 机制库覆盖率 =====
    mechanisms_db = kb / 'mechanisms.db'
    if mechanisms_db.exists():
        conn = sqlite3.connect(str(mechanisms_db))
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM mechanisms')
        mech_total = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM mechanisms WHERE friendly_name IS NOT NULL AND friendly_name != id")
        friendly_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM mechanisms WHERE behavior_description IS NOT NULL AND behavior_description != ''")
        behavior_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM mechanisms WHERE mechanism_category IS NOT NULL AND mechanism_category != ''")
        category_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM mechanisms WHERE formula_abstract IS NOT NULL AND formula_abstract != ''")
        formula_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM mechanisms WHERE affected_stats IS NOT NULL AND affected_stats != '' AND affected_stats != '[]'")
        affected_count = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM mechanism_relations')
        relation_count = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM mechanism_sources')
        source_count = cursor.fetchone()[0]
        
        print(f"\n  [机制库覆盖率]")
        print(f"  机制总数: {mech_total}")
        print(f"  friendly_name (中文名):    {friendly_count}/{mech_total} ({friendly_count*100//mech_total if mech_total else 0}%)")
        print(f"  behavior_description:      {behavior_count}/{mech_total} ({behavior_count*100//mech_total if mech_total else 0}%)")
        print(f"  mechanism_category:        {category_count}/{mech_total} ({category_count*100//mech_total if mech_total else 0}%)")
        print(f"  formula_abstract:          {formula_count}/{mech_total} ({formula_count*100//mech_total if mech_total else 0}%)")
        print(f"  affected_stats:            {affected_count}/{mech_total} ({affected_count*100//mech_total if mech_total else 0}%)")
        print(f"  mechanism_relations:       {relation_count} 条")
        print(f"  mechanism_sources:         {source_count} 条")
        
        stats['mechanism_total'] = mech_total
        stats['mechanism_behavior_rate'] = behavior_count * 100 // mech_total if mech_total else 0
        stats['mechanism_friendly_rate'] = friendly_count * 100 // mech_total if mech_total else 0
        stats['mechanism_relations'] = relation_count
        
        # 阈值检查
        if mech_total < 30:
            issues.append(f"机制数量过少: {mech_total} (预期 >= 30)")
        if (behavior_count * 100 // mech_total < 30) if mech_total else True:
            issues.append(f"behavior_description 覆盖率低于 30%: {behavior_count}/{mech_total}")
        
        # 检查孤立外键
        cursor.execute('''
            SELECT COUNT(*) FROM mechanism_sources ms 
            WHERE NOT EXISTS (SELECT 1 FROM mechanisms m WHERE m.id = ms.mechanism_id)
        ''')
        orphan_sources = cursor.fetchone()[0]
        cursor.execute('''
            SELECT COUNT(*) FROM mechanism_relations mr
            WHERE NOT EXISTS (SELECT 1 FROM mechanisms m WHERE m.id = mr.mechanism_a)
               OR NOT EXISTS (SELECT 1 FROM mechanisms m WHERE m.id = mr.mechanism_b)
        ''')
        orphan_relations = cursor.fetchone()[0]
        
        if orphan_sources > 0:
            issues.append(f"mechanism_sources 中有 {orphan_sources} 条孤立外键")
        if orphan_relations > 0:
            issues.append(f"mechanism_relations 中有 {orphan_relations} 条孤立外键")
        
        conn.close()
    else:
        issues.append("mechanisms.db 不存在")
    
    # ===== 3. 辅助匹配完整性 =====
    supports_db = kb / 'supports.db'
    if supports_db.exists():
        conn = sqlite3.connect(str(supports_db))
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM support_compatibility')
        compat_count = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM support_compatibility WHERE compatible = 1')
        compat_positive = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM support_effects')
        effects_count = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM support_effects WHERE quantifiable = 1')
        quantifiable_count = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(DISTINCT effect_category) FROM support_effects')
        category_count = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM support_potential')
        potential_count = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(DISTINCT synergy_type) FROM support_potential')
        synergy_types = cursor.fetchone()[0]
        
        # 效果分类分布
        cursor.execute('''
            SELECT effect_category, COUNT(*) 
            FROM support_effects 
            GROUP BY effect_category 
            ORDER BY COUNT(*) DESC
        ''')
        category_dist = cursor.fetchall()
        
        print(f"\n  [辅助匹配完整性]")
        print(f"  兼容矩阵:    {compat_count} 对 (其中兼容 {compat_positive})")
        print(f"  效果分类:     {effects_count} 个 (可量化 {quantifiable_count}, 分 {category_count} 类)")
        print(f"  潜力推荐:     {potential_count} 条 (协同类型 {synergy_types} 种)")
        print(f"  效果分类分布:")
        for cat, cnt in category_dist:
            print(f"    {cat:<20} {cnt:>4}")
        
        stats['support_compatibility'] = compat_count
        stats['support_compatible_positive'] = compat_positive
        stats['support_effects'] = effects_count
        stats['support_quantifiable'] = quantifiable_count
        stats['support_potentials'] = potential_count
        
        # 阈值检查
        if compat_count == 0:
            issues.append("support_compatibility 为空")
        if effects_count == 0:
            issues.append("support_effects 为空")
        if category_count < 5:
            issues.append(f"效果分类过少: {category_count} (预期 >= 5)")
        
        # 检查是否有没有 effect 的 support
        cursor.execute('''
            SELECT COUNT(DISTINCT c.support_id) 
            FROM support_compatibility c
            WHERE c.compatible = 1 
              AND NOT EXISTS (SELECT 1 FROM support_effects e WHERE e.support_id = c.support_id)
        ''')
        no_effect_supports = cursor.fetchone()[0]
        if no_effect_supports > 0:
            issues.append(f"有 {no_effect_supports} 个兼容辅助缺少效果分类")
        
        conn.close()
    else:
        issues.append("supports.db 不存在")
    
    # ===== 4. 公式库 =====
    formulas_db = kb / 'formulas.db'
    if formulas_db.exists():
        conn = sqlite3.connect(str(formulas_db))
        cursor = conn.cursor()
        
        formula_counts = {}
        for table in ['universal_formulas', 'stat_mappings', 'gap_formulas']:
            try:
                cursor.execute(f'SELECT COUNT(*) FROM {table}')
                formula_counts[table] = cursor.fetchone()[0]
            except sqlite3.OperationalError:
                formula_counts[table] = 0
        
        uf_c = formula_counts['universal_formulas']
        sm_c = formula_counts['stat_mappings']
        gf_c = formula_counts['gap_formulas']
        
        print(f"\n  [公式库]")
        print(f"  通用公式:     {uf_c}")
        print(f"  stat 映射:    {sm_c}")
        print(f"  缺口公式:     {gf_c}")
        
        stats['formula_universal'] = uf_c
        stats['formula_stat_mappings'] = sm_c
        stats['formula_gap'] = gf_c
        
        if uf_c == 0 and sm_c == 0:
            issues.append("公式库完全为空")
        
        conn.close()
    else:
        issues.append("formulas.db 不存在")
    
    # ===== 汇总 =====
    print(f"\n  {'='*50}")
    if issues:
        print(f"  ⚠ 发现 {len(issues)} 个问题:")
        for i, issue in enumerate(issues, 1):
            print(f"    {i}. {issue}")
    else:
        print(f"  ✅ 所有数据完整性检查通过")
    
    stats['issues'] = issues
    stats['issue_count'] = len(issues)
    
    return stats


def update_version_yaml(kb_path: str, version: str = None, kb_version: str = "3.0.0"):
    """更新版本信息"""
    print("\n更新版本信息...")
    
    version_file = Path(kb_path) / 'version.yaml'
    
    content = f"""# 版本信息
# 记录当前知识库对应的POB版本

metadata:
  knowledge_base_version: "{kb_version}"
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
    
    print(f"[OK] 版本信息已更新 (v{kb_version})")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='初始化POE知识库 v3')
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
    print("POE知识库初始化 v3")
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
    
    # Step 2: 解读层预计算
    enrichment_stats = enrich_entities(str(pob_path), str(entities_db))
    
    # 公式库初始化（添加异常处理）
    try:
        formula_stats = init_formula_library(str(pob_path), str(formulas_db), str(entities_db))
    except Exception as e:
        print(f"\n[ERROR] 公式库初始化失败: {e}")
        import traceback
        traceback.print_exc()
        formula_stats = {'universal_formulas': 0, 'stat_mappings': {'total': 0}, 'gap_formulas': {'total': 0}, 'total': 0}
    
    # 提取机制 (v2: 含行为描述提取)
    modcache_path = pob_path / 'Data' / 'ModCache.lua'
    if modcache_path.exists():
        mechanism_stats = extract_mechanisms(
            str(modcache_path),
            str(kb_path / 'mechanisms.db'),
            entities_db_path=str(entities_db),
            pob_path=str(pob_path)
        )
    else:
        mechanism_stats = {'mechanisms': 0, 'sources': 0, 'relations': 0}
    
    # 辅助匹配预计算 (Step 5)
    support_stats = compute_support_matching(
        str(entities_db),
        str(kb_path / 'supports.db')
    )
    
    # Step 6: 版本信息更新
    update_version_yaml(str(kb_path), kb_version="3.0.0")
    
    # Step 7: 完整性校验 (Phase 4, Task 8.1)
    check_stats = run_completeness_check(str(kb_path))
    
    # 最终统计
    print("\n" + "=" * 60)
    print("初始化完成 (v3.0.0)")
    print("=" * 60)
    print(f"实体索引: {entity_stats['total']} 个实体")
    en_s = enrichment_stats.get('summary', 0)
    en_km = enrichment_stats.get('key_mechanics', 0)
    en_ds = enrichment_stats.get('display_stats', 0)
    print(f"解读层:   summary={en_s} key_mechanics={en_km} display_stats={en_ds}")
    uf = formula_stats.get('universal_formulas', 0)
    sm_total = formula_stats.get('stat_mappings', {}).get('total', 0)
    gf_total = formula_stats.get('gap_formulas', {}).get('total', 0)
    formula_total = formula_stats.get('total', 0)
    print(f"公式索引: 通用{uf} + 映射{sm_total} + 缺口{gf_total} = {formula_total} 条")
    print(f"机制库:   {mechanism_stats['mechanisms']} 个机制, {mechanism_stats.get('sources', 0)} 个来源, {mechanism_stats.get('relations', 0)} 条关系")
    print(f"辅助匹配: {support_stats.get('compatibility', 0)} 兼容对, {support_stats.get('effects', 0)} 效果, {support_stats.get('potentials', 0)} 潜力推荐")
    
    issue_count = check_stats.get('issue_count', 0)
    if issue_count > 0:
        print(f"\n⚠ 完整性校验发现 {issue_count} 个问题，详见上方 Step 7 输出")
    else:
        print(f"\n✅ 所有数据完整性检查通过")


if __name__ == '__main__':
    main()
