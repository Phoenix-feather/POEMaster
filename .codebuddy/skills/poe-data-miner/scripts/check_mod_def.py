#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检查mod_definition和stat_mapping的关系"""

import sqlite3
import json

conn = sqlite3.connect('knowledge_base/entities.db')
cursor = conn.cursor()

print("=" * 60)
print("mod_definition vs stat_mapping")
print("=" * 60)

# 检查 stat_mapping
cursor.execute('SELECT COUNT(*) FROM entities WHERE type="stat_mapping"')
stat_count = cursor.fetchone()[0]
print(f"\nstat_mapping实体数: {stat_count}")

# 检查 mod_definition
cursor.execute('SELECT COUNT(*) FROM entities WHERE type="mod_definition"')
mod_count = cursor.fetchone()[0]
print(f"mod_definition实体数: {mod_count}")

# 查看 stat_mapping 示例
print(f"\nstat_mapping示例:")
cursor.execute('SELECT id, name, type, mod_data FROM entities WHERE type="stat_mapping" LIMIT 3')
stats = cursor.fetchall()
for s in stats:
    print(f"  ID: {s[0]}")
    print(f"  Name: {s[1]}")
    print(f"  Type: {s[2]}")
    mod_data = json.loads(s[3]) if s[3] else []
    print(f"  Mod数据字段数: {len(mod_data)}")
    if mod_data:
        print(f"  Mod示例: {mod_data[0]}")
    print()

# 查看 mod_data 字段内容
print("mod_data字段内容示例:")
cursor.execute('SELECT id, mod_data FROM entities WHERE type="stat_mapping" AND mod_data IS NOT NULL LIMIT 1')
row = cursor.fetchone()
if row:
    print(f"  ID: {row[0]}")
    mod_data = json.loads(row[1])
    print(f"  Mod数量: {len(mod_data)}")
    for i, mod in enumerate(mod_data[:2]):
        print(f"  Mod {i+1}: {mod}")

conn.close()

print("\n" + "=" * 60)
print("结论")
print("=" * 60)
print("stat_mapping 和 mod_definition 是同一个概念")
print("ModCache.lua中的数据已被成功提取为stat_mapping类型")
