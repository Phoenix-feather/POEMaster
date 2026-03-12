#!/usr/bin/env python3
"""检查知识库统计"""
import sqlite3
from pathlib import Path

kb_path = Path(__file__).parent.parent / 'knowledge_base'

print('=' * 60)
print('知识库统计')
print('=' * 60)

# entities
conn = sqlite3.connect(str(kb_path / 'entities.db'))
c = conn.cursor()
c.execute('SELECT COUNT(*) FROM entities')
print(f'entities.db: {c.fetchone()[0]} 条实体')
c.execute('SELECT type, COUNT(*) FROM entities GROUP BY type')
for row in c.fetchall():
    print(f'  - {row[0]}: {row[1]}')
conn.close()

# rules
conn = sqlite3.connect(str(kb_path / 'rules.db'))
c = conn.cursor()
c.execute('SELECT COUNT(*) FROM rules')
print(f'\nrules.db: {c.fetchone()[0]} 条规则')
c.execute('SELECT category, COUNT(*) FROM rules GROUP BY category')
for row in c.fetchall():
    print(f'  - {row[0]}: {row[1]}')
conn.close()

# graph
conn = sqlite3.connect(str(kb_path / 'graph.db'))
c = conn.cursor()
c.execute('SELECT COUNT(*) FROM graph_nodes')
nodes = c.fetchone()[0]
c.execute('SELECT COUNT(*) FROM graph_edges')
edges = c.fetchone()[0]
print(f'\ngraph.db: {nodes} 节点, {edges} 边')

c.execute('SELECT type, COUNT(*) FROM graph_nodes GROUP BY type')
print('  节点类型:')
for row in c.fetchall():
    print(f'    - {row[0]}: {row[1]}')

c.execute('SELECT status, COUNT(*) FROM graph_edges GROUP BY status')
print('  边状态:')
for row in c.fetchall():
    print(f'    - {row[0]}: {row[1]}')
conn.close()

# formulas (新表结构)
conn = sqlite3.connect(str(kb_path / 'formulas.db'))
c = conn.cursor()

# 检查表是否存在
c.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in c.fetchall()]

print(f'\nformulas.db: 表 {tables}')

# 通用公式
if 'universal_formulas' in tables:
    c.execute('SELECT COUNT(*) FROM universal_formulas')
    uf = c.fetchone()[0]
    print(f'  universal_formulas: {uf} 条')

# stat映射
if 'stat_mappings' in tables:
    c.execute('SELECT COUNT(*) FROM stat_mappings')
    sm = c.fetchone()[0]
    print(f'  stat_mappings: {sm} 条')

# 缺口公式
if 'gap_formulas' in tables:
    c.execute('SELECT COUNT(*) FROM gap_formulas')
    gf = c.fetchone()[0]
    print(f'  gap_formulas: {gf} 条')

# 旧表（如果存在）
if 'formulas' in tables:
    c.execute('SELECT COUNT(*) FROM formulas')
    old = c.fetchone()[0]
    print(f'  formulas (旧): {old} 条')

conn.close()
