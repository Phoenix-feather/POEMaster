#!/usr/bin/env python3
"""
显示每个实体类型的具体字段内容
"""

import sqlite3
import json
from pathlib import Path
from collections import defaultdict

def show_entity_fields(db_path: str):
    """显示每个实体类型的具体字段"""
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 获取所有实体类型
    cursor.execute('SELECT DISTINCT type FROM entities ORDER BY type')
    entity_types = [row[0] for row in cursor.fetchall()]
    
    print("=" * 120)
    print("实体类型字段详情")
    print("=" * 120)
    
    for entity_type in entity_types:
        print(f"\n{'='*120}")
        print(f"实体类型: {entity_type}")
        print(f"{'='*120}")
        
        # 获取该类型的数量
        cursor.execute('SELECT COUNT(*) FROM entities WHERE type = ?', (entity_type,))
        count = cursor.fetchone()[0]
        print(f"总数: {count:,}")
        
        # 获取表结构
        cursor.execute('PRAGMA table_info(entities)')
        all_fields = [col[1] for col in cursor.fetchall()]
        
        # 获取一个示例实体
        cursor.execute('SELECT * FROM entities WHERE type = ? LIMIT 1', (entity_type,))
        sample = cursor.fetchone()
        
        if not sample:
            print("  无数据")
            continue
        
        print(f"\n字段详情:")
        print("-" * 120)
        
        # 统计每个字段的填充率
        field_stats = []
        for i, field in enumerate(all_fields):
            # 统计填充率
            cursor.execute(f'''
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN "{field}" IS NOT NULL AND "{field}" != '' AND "{field}" != '[]' AND "{field}" != '{{}}' THEN 1 ELSE 0 END) as filled
                FROM entities 
                WHERE type = ?
            ''', (entity_type,))
            
            total, filled = cursor.fetchone()
            fill_rate = (filled / total * 100) if total > 0 else 0
            
            # 获取示例值
            example_value = sample[i]
            
            # 格式化示例值
            if example_value is None:
                example_display = "NULL"
            elif isinstance(example_value, str):
                if len(example_value) > 100:
                    example_display = example_value[:100] + "..."
                else:
                    example_display = example_value
            else:
                example_display = str(example_value)
            
            field_stats.append({
                'field': field,
                'filled': filled,
                'total': total,
                'fill_rate': fill_rate,
                'example': example_display
            })
        
        # 显示字段统计
        for stat in field_stats:
            status = "[Y]" if stat['fill_rate'] == 100 else ("[P]" if stat['fill_rate'] > 0 else "[N]")
            print(f"  {status} {stat['field']:<30} {stat['filled']:>5}/{stat['total']:<5} ({stat['fill_rate']:>5.1f}%)  示例: {stat['example']}")
        
        # 显示完整示例实体
        print(f"\n完整示例实体:")
        print("-" * 120)
        cursor.execute('''
            SELECT id, name, data_json 
            FROM entities 
            WHERE type = ? 
            LIMIT 1
        ''', (entity_type,))
        
        row = cursor.fetchone()
        if row:
            entity_id, name, data_json = row
            print(f"ID: {entity_id}")
            print(f"Name: {name}")
            
            if data_json:
                try:
                    data = json.loads(data_json)
                    print(f"\n完整数据（格式化）:")
                    print(json.dumps(data, indent=2, ensure_ascii=False)[:500])
                    if len(json.dumps(data, indent=2, ensure_ascii=False)) > 500:
                        print("... (数据过长，已截断)")
                except:
                    print(f"\n原始数据: {data_json[:200]}...")
        
        # 显示该类型的特殊字段（高填充率的字段）
        high_fill_fields = [f for f in field_stats if f['fill_rate'] > 50]
        if high_fill_fields:
            print(f"\n关键字段（填充率>50%）:")
            for f in high_fill_fields:
                print(f"  - {f['field']}: {f['fill_rate']:.1f}%")
    
    conn.close()

def show_field_values_distribution(db_path: str):
    """显示关键字段的值分布"""
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("\n\n")
    print("=" * 120)
    print("关键字段值分布")
    print("=" * 120)
    
    # skill_definition的关键字段
    print("\n【skill_definition 关键字段】")
    print("-" * 120)
    
    # cast_time分布
    cursor.execute('''
        SELECT cast_time, COUNT(*) as count
        FROM entities
        WHERE type = 'skill_definition' AND cast_time IS NOT NULL
        GROUP BY cast_time
        ORDER BY count DESC
        LIMIT 10
    ''')
    print("\ncast_time分布 (Top 10):")
    for row in cursor.fetchall():
        print(f"  {row[0]:>6}秒: {row[1]:>4}个")
    
    # gem_definition的关键字段
    print("\n【gem_definition 关键字段】")
    print("-" * 120)
    
    # gem_type分布
    cursor.execute('''
        SELECT gem_type, COUNT(*) as count
        FROM entities
        WHERE type = 'gem_definition' AND gem_type IS NOT NULL
        GROUP BY gem_type
        ORDER BY count DESC
    ''')
    print("\ngem_type分布:")
    for row in cursor.fetchall():
        print(f"  {row[0]:<20}: {row[1]:>4}个")
    
    # tier分布
    cursor.execute('''
        SELECT tier, COUNT(*) as count
        FROM entities
        WHERE type = 'gem_definition' AND tier IS NOT NULL
        GROUP BY tier
        ORDER BY tier
    ''')
    print("\ntier分布:")
    for row in cursor.fetchall():
        print(f"  Tier {row[0]:>2}: {row[1]:>4}个")
    
    # passive_node的关键字段
    print("\n【passive_node 关键字段】")
    print("-" * 120)
    
    # is_notable分布
    cursor.execute('''
        SELECT is_notable, COUNT(*) as count
        FROM entities
        WHERE type = 'passive_node'
        GROUP BY is_notable
    ''')
    print("\nis_notable分布:")
    for row in cursor.fetchall():
        label = "Notable" if row[0] == 1 else "Normal"
        print(f"  {label:<10}: {row[1]:>4}个")
    
    # ascendancy_name分布
    cursor.execute('''
        SELECT ascendancy_name, COUNT(*) as count
        FROM entities
        WHERE type = 'passive_node' AND ascendancy_name IS NOT NULL
        GROUP BY ascendancy_name
        ORDER BY count DESC
    ''')
    print("\nascendancy_name分布:")
    for row in cursor.fetchall():
        print(f"  {row[0]:<20}: {row[1]:>4}个")
    
    # stat_mapping的关键字段
    print("\n【stat_mapping 关键字段】")
    print("-" * 120)
    
    # 查看一个示例
    cursor.execute('''
        SELECT id, name, mod_data, description
        FROM entities
        WHERE type = 'stat_mapping'
        LIMIT 3
    ''')
    print("\n示例:")
    for row in cursor.fetchall():
        print(f"\n  ID: {row[0]}")
        print(f"  Name: {row[1]}")
        print(f"  Description: {row[3]}")
        if row[2]:
            try:
                mod_data = json.loads(row[2])
                print(f"  Mod数据: {json.dumps(mod_data, ensure_ascii=False)[:200]}...")
            except:
                print(f"  Mod数据: {row[2][:200]}...")
    
    conn.close()

if __name__ == '__main__':
    db_path = Path(__file__).parent.parent / 'knowledge_base' / 'entities.db'
    show_entity_fields(str(db_path))
    show_field_values_distribution(str(db_path))
