#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检查未完成的任务"""

import sqlite3
import json

conn = sqlite3.connect('knowledge_base/entities.db')
cursor = conn.cursor()

print("=" * 60)
print("任务完成状态检查")
print("=" * 60)

# 1. 检查 mod_definition
cursor.execute('SELECT COUNT(*) FROM entities WHERE type="mod_definition"')
mod_count = cursor.fetchone()[0]
print(f"\n1. ModCache提取:")
print(f"   mod_definition实体数: {mod_count}")
if mod_count > 0:
    print("   ✅ 已完成")
else:
    print("   ❌ 未完成")

# 2. 检查 minion_definition
cursor.execute('SELECT COUNT(*) FROM entities WHERE type="minion_definition"')
minion_count = cursor.fetchone()[0]
print(f"\n2. Minion提取:")
print(f"   minion_definition实体数: {minion_count}")

cursor.execute('SELECT id, stats, skill_types FROM entities WHERE type="minion_definition" LIMIT 3')
minions = cursor.fetchall()
for m in minions:
    stats = json.loads(m[1]) if m[1] else []
    skills = json.loads(m[2]) if m[2] else []
    print(f"   {m[0]}:")
    print(f"     - stats字段数: {len(stats)}")
    print(f"     - skills字段数: {len(skills)}")
    if len(stats) > 0 or len(skills) > 0:
        print("     ✅ stats/skills已提取")
    else:
        print("     ❌ stats/skills未提取")

# 3. 检查 gem_definition
cursor.execute('SELECT COUNT(*) FROM entities WHERE type="gem_definition"')
gem_count = cursor.fetchone()[0]
print(f"\n3. Gem提取:")
print(f"   gem_definition实体数: {gem_count}")

cursor.execute('SELECT id, granted_effect_id, req_int FROM entities WHERE type="gem_definition" LIMIT 3')
gems = gems = cursor.fetchall()
for g in gems:
    print(f"   {g[0]}:")
    print(f"     - granted_effect_id: {g[1]}")
    print(f"     - req_int: {g[2]}")
    if g[1] and g[2]:
        print("     ✅ 新字段已提取")
    else:
        print("     ❌ 新字段缺失")

# 4. 检查 skill_definition
cursor.execute('SELECT COUNT(*) FROM entities WHERE type="skill_definition"')
skill_count = cursor.fetchone()[0]
print(f"\n4. Skill提取:")
print(f"   skill_definition实体数: {skill_count}")

cursor.execute('SELECT id, levels, stat_sets FROM entities WHERE type="skill_definition" LIMIT 3')
skills = cursor.fetchall()
for s in skills:
    levels = json.loads(s[1]) if s[1] else {}
    stat_sets = json.loads(s[2]) if s[2] else {}
    print(f"   {s[0]}:")
    print(f"     - levels字段数: {len(levels)}")
    print(f"     - stat_sets字段数: {len(stat_sets)}")
    if len(levels) > 0:
        print("     ✅ levels已提取")
    else:
        print("     ❌ levels缺失")

# 5. 检查 mechanisms
cursor.execute('SELECT COUNT(*) FROM mechanisms')
mech_count = cursor.fetchone()[0]
print(f"\n5. Mechanisms提取:")
print(f"   机制数: {mech_count}")
if mech_count > 0:
    print("   ✅ 已完成")
else:
    print("   ❌ 未完成")

conn.close()

print("\n" + "=" * 60)
print("总结")
print("=" * 60)
