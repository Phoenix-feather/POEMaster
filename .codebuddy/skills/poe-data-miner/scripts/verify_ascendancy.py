#!/usr/bin/env python3
import sqlite3

conn = sqlite3.connect('knowledge_base/entities.db')
cursor = conn.cursor()

# 检查passive_node的ascendancy_name字段
cursor.execute('SELECT COUNT(*) FROM entities WHERE type="passive_node"')
total = cursor.fetchone()[0]

cursor.execute('SELECT COUNT(*) FROM entities WHERE type="passive_node" AND ascendancy_name IS NOT NULL AND ascendancy_name != ""')
filled = cursor.fetchone()[0]

print(f'passive_node总数: {total}')
print(f'ascendancy_name已填充: {filled}')
print(f'覆盖率: {filled/total*100:.1f}%')

if filled > 0:
    print(f'\n示例:')
    cursor.execute('SELECT name, ascendancy_name FROM entities WHERE type="passive_node" AND ascendancy_name IS NOT NULL LIMIT 5')
    for row in cursor.fetchall():
        print(f'  {row[0]} - {row[1]}')

conn.close()
