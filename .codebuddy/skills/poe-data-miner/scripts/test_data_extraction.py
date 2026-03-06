#!/usr/bin/env python3
"""
测试数据提取完整性
验证新字段是否正确提取
"""

import sys
import sqlite3
import json
from pathlib import Path

# 添加scripts目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

def test_levels_extraction(db_path):
    """测试levels字段提取"""
    print("\n" + "="*60)
    print("测试1: 技能levels字段提取")
    print("="*60)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 测试MetaCastOnCritPlayer
    cursor.execute('''
        SELECT id, name, levels 
        FROM entities 
        WHERE id = 'MetaCastOnCritPlayer'
    ''')
    
    row = cursor.fetchone()
    if row:
        id, name, levels_json = row
        print(f"✓ 找到技能: {name} ({id})")
        
        if levels_json:
            levels = json.loads(levels_json)
            print(f"✓ Levels字段已提取，包含 {len(levels)} 个等级")
            
            # 检查关键数据
            if '1' in levels:
                level1 = levels['1']
                print(f"\n  等级1数据:")
                for key, value in level1.items():
                    print(f"    - {key}: {value}")
                
                # 检查spiritReservationFlat
                if 'spiritReservationFlat' in level1:
                    print(f"\n✓ spiritReservationFlat已提取: {level1['spiritReservationFlat']}")
                else:
                    print(f"\n✗ 缺少spiritReservationFlat字段")
        else:
            print("✗ Levels字段为空")
    else:
        print("✗ 未找到MetaCastOnCritPlayer")
    
    conn.close()

def test_support_gem_fields(db_path):
    """测试辅助宝石字段提取"""
    print("\n" + "="*60)
    print("测试2: 辅助宝石限制字段提取")
    print("="*60)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 查找辅助宝石（但不是hidden的）
    cursor.execute('''
        SELECT id, name, support, require_skill_types, add_skill_types, is_trigger
        FROM entities 
        WHERE type = 'skill_definition' AND support = 1
        LIMIT 5
    ''')
    
    rows = cursor.fetchall()
    if rows:
        print(f"✓ 找到 {len(rows)} 个辅助宝石（非hidden）")
        for row in rows:
            id, name, support, require_types, add_types, is_trigger = row
            print(f"\n  {name}:")
            print(f"    - support: {support}")
            if require_types:
                print(f"    - require_skill_types: {require_types}")
            if add_types:
                print(f"    - add_skill_types: {add_types}")
            print(f"    - is_trigger: {is_trigger}")
    else:
        print("✗ 未找到辅助宝石（可能都被hidden过滤了）")
    
    conn.close()

def test_hidden_filter(db_path):
    """测试hidden过滤"""
    print("\n" + "="*60)
    print("测试3: Hidden过滤")
    print("="*60)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 查找应该被过滤的hidden技能
    cursor.execute('''
        SELECT COUNT(*) 
        FROM entities 
        WHERE id LIKE '%SupportMetaCastOnCrit%'
    ''')
    
    count = cursor.fetchone()[0]
    if count == 0:
        print("✓ Hidden技能已被正确过滤（SupportMetaCastOnCritPlayer未出现在数据库中）")
    else:
        print(f"✗ Hidden技能未被过滤，找到 {count} 个记录")
    
    conn.close()

def test_gem_definition_fields(db_path):
    """测试宝石定义字段提取"""
    print("\n" + "="*60)
    print("测试4: 宝石定义字段提取")
    print("="*60)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 查找Arc宝石
    cursor.execute('''
        SELECT id, name, granted_effect_id, req_str, req_dex, req_int, 
               natural_max_level, gem_type, tag_string
        FROM entities 
        WHERE id LIKE '%SkillGemArc' AND type = 'gem_definition'
        LIMIT 1
    ''')
    
    row = cursor.fetchone()
    if row:
        id, name, granted_id, req_str, req_dex, req_int, max_level, gem_type, tag_str = row
        print(f"✓ 找到宝石: {name}")
        print(f"  - granted_effect_id: {granted_id}")
        print(f"  - 需求: 力量={req_str}, 敏捷={req_dex}, 智力={req_int}")
        print(f"  - 最大等级: {max_level}")
        print(f"  - 宝石类型: {gem_type}")
        print(f"  - 标签: {tag_str}")
        
        # 验证关键字段
        if granted_id == 'ArcPlayer':
            print("\n✓ granted_effect_id正确关联到技能")
        else:
            print(f"\n✗ granted_effect_id错误: {granted_id}")
        
        if req_int == 100:
            print("✓ 智力需求正确")
        else:
            print(f"✗ 智力需求错误: {req_int}")
    else:
        print("✗ 未找到Arc宝石定义")
    
    conn.close()

def test_stat_sets_extraction(db_path):
    """测试statSets详细数据提取"""
    print("\n" + "="*60)
    print("测试5: StatSets详细数据提取")
    print("="*60)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 查找Arc技能
    cursor.execute('''
        SELECT id, name, stat_sets 
        FROM entities 
        WHERE id = 'ArcPlayer'
    ''')
    
    row = cursor.fetchone()
    if row:
        id, name, stat_sets_json = row
        print(f"✓ 找到技能: {name}")
        
        if stat_sets_json:
            stat_sets = json.loads(stat_sets_json)
            print(f"✓ StatSets字段已提取")
            
            # 检查关键字段
            if 'baseEffectiveness' in stat_sets:
                print(f"  - baseEffectiveness: {stat_sets['baseEffectiveness']}")
            if 'incrementalEffectiveness' in stat_sets:
                print(f"  - incrementalEffectiveness: {stat_sets['incrementalEffectiveness']}")
            if 'baseFlags' in stat_sets:
                print(f"  - baseFlags: {stat_sets['baseFlags']}")
            if 'levels' in stat_sets:
                print(f"  - statSets.levels: {len(stat_sets['levels'])} 个等级")
        else:
            print("✗ StatSets字段为空")
    else:
        print("✗ 未找到ArcPlayer")
    
    conn.close()

def main():
    """主测试函数"""
    print("\n" + "="*60)
    print("POEMaster 数据提取完整性测试")
    print("="*60)
    
    db_path = Path(__file__).parent.parent / 'knowledge_base' / 'entities.db'
    
    if not db_path.exists():
        print(f"\n✗ 数据库不存在: {db_path}")
        print("\n请先运行以下命令初始化知识库:")
        print("  python scripts/init_knowledge_base.py")
        return
    
    print(f"\n数据库路径: {db_path}")
    
    # 运行所有测试
    test_levels_extraction(str(db_path))
    test_support_gem_fields(str(db_path))
    test_hidden_filter(str(db_path))
    test_gem_definition_fields(str(db_path))
    test_stat_sets_extraction(str(db_path))
    
    print("\n" + "="*60)
    print("测试完成")
    print("="*60)

if __name__ == '__main__':
    main()
