#!/usr/bin/env python3
"""验证unique_item修复结果"""

import sqlite3
from pathlib import Path

db_path = Path(__file__).parent.parent / 'knowledge_base' / 'entities.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 统计unique_item数量
cursor.execute('SELECT COUNT(*) FROM entities WHERE type="unique_item"')
total = cursor.fetchone()[0]
print(f'unique_item总数: {total}')
print()

# 显示示例
cursor.execute('''
    SELECT id, name, source_file, stats
    FROM entities
    WHERE type="unique_item"
    LIMIT 10
''')

print('示例:')
print('-' * 100)
for row in cursor.fetchall():
    id, name, source, stats = row
    stats_preview = stats[:100] + '...' if len(stats) > 100 else stats
    print(f'{id[:40]:<40} | {name[:30]:<30} | {source}')
    print(f'  Stats: {stats_preview}')
    print()

# 检查是否还有HTML数据
cursor.execute('''
    SELECT COUNT(*)
    FROM entities
    WHERE type="unique_item" AND stats LIKE '%<!DOCTYPE html>%'
''')
html_count = cursor.fetchone()[0]

if html_count > 0:
    print(f'⚠️  发现 {html_count} 个HTML数据（错误数据）')
else:
    print('✅ 无HTML数据（修复成功）')

conn.close()
