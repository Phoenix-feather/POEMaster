#!/usr/bin/env python3
"""检查unique_item的来源"""

import sqlite3
from pathlib import Path

db_path = Path(__file__).parent.parent / 'knowledge_base' / 'entities.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 查看来源文件
cursor.execute('''
    SELECT DISTINCT source_file
    FROM entities
    WHERE type="unique_item"
    ORDER BY source_file
''')

print('unique_item来源文件:')
print('-' * 80)
for row in cursor.fetchall():
    print(f'  {row[0]}')

print()

# 统计每个来源的数量
cursor.execute('''
    SELECT source_file, COUNT(*) as count
    FROM entities
    WHERE type="unique_item"
    GROUP BY source_file
    ORDER BY count DESC
''')

print('来源统计:')
print('-' * 80)
for row in cursor.fetchall():
    print(f'  {row[0]:<50} {row[1]:>5}个')

conn.close()
