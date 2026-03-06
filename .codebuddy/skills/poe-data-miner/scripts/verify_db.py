#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""验证数据库结构"""

import sqlite3
import os

db_path = 'knowledge_base/entities.db'

if not os.path.exists(db_path):
    print(f"错误: 数据库文件不存在: {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 获取表结构
cursor.execute('PRAGMA table_info(entities)')
cols = cursor.fetchall()

print(f"\n{'='*60}")
print(f"Entities表字段数: {len(cols)}")
print(f"{'='*60}\n")

print("字段列表:")
for col in cols:
    print(f"  {col[1]:25s} {col[2]}")

print(f"\n{'='*60}")
print("新字段验证:")
print(f"{'='*60}\n")

new_fields = [
    'base_type_name', 'cast_time', 'levels', 'stat_sets',
    'granted_effect_id', 'req_str', 'req_int', 'require_skill_types',
    'add_skill_types', 'exclude_skill_types', 'is_trigger', 'hidden'
]

for f in new_fields:
    exists = any(col[1] == f for col in cols)
    status = "✓" if exists else "✗"
    print(f"  {status} {f}")

# 统计数据
cursor.execute('SELECT COUNT(*) FROM entities')
count = cursor.fetchone()[0]
print(f"\n{'='*60}")
print(f"实体总数: {count}")
print(f"{'='*60}\n")

conn.close()
