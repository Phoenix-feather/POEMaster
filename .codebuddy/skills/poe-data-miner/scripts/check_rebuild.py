#!/usr/bin/env python3
"""检查知识库重建结果"""
import sqlite3
import json
from pathlib import Path

kb = Path(__file__).parent.parent / 'knowledge_base'

# 检查 entities.db
print("=" * 50)
print("entities.db")
print("=" * 50)
conn = sqlite3.connect(str(kb / 'entities.db'))
c = conn.cursor()

c.execute('SELECT COUNT(*) FROM entities')
print(f"Total entities: {c.fetchone()[0]}")

c.execute('SELECT type, COUNT(*) FROM entities GROUP BY type ORDER BY COUNT(*) DESC')
for row in c.fetchall():
    print(f"  {row[0]}: {row[1]}")

c.execute("SELECT COUNT(*) FROM entities WHERE additional_granted_effect_ids IS NOT NULL AND additional_granted_effect_ids != '[]'")
print(f"\nWith additionalGrantedEffectId: {c.fetchone()[0]}")

c.execute("SELECT id, name, additional_granted_effect_ids FROM entities WHERE additional_granted_effect_ids IS NOT NULL AND additional_granted_effect_ids != '[]' LIMIT 5")
for row in c.fetchall():
    print(f"  {row[0]}: {row[1]} -> {row[2]}")

c.execute("SELECT COUNT(*) FROM entities WHERE hidden=1 AND type='skill_definition'")
print(f"\nHidden skills (type=skill_definition): {c.fetchone()[0]}")

c.execute("SELECT id, name FROM entities WHERE hidden=1 LIMIT 10")
hidden = c.fetchall()
if hidden:
    for row in hidden:
        print(f"  {row[0]}: {row[1]}")
else:
    print("  (none)")

conn.close()

# 检查 graph.db
print("\n" + "=" * 50)
print("graph.db")
print("=" * 50)
try:
    conn = sqlite3.connect(str(kb / 'graph.db'))
    c = conn.cursor()
    
    c.execute('SELECT COUNT(*) FROM graph_nodes')
    print(f"Nodes: {c.fetchone()[0]}")
    
    c.execute('SELECT COUNT(*) FROM graph_edges')
    print(f"Edges: {c.fetchone()[0]}")
    
    c.execute('SELECT edge_type, COUNT(*) FROM graph_edges GROUP BY edge_type ORDER BY COUNT(*) DESC')
    for row in c.fetchall():
        print(f"  {row[0]}: {row[1]}")
    
    c.execute('SELECT COUNT(*) FROM anomaly_paths')
    print(f"\nAnomaly paths: {c.fetchone()[0]}")
    
    c.execute('SELECT anomaly_id, modifier_id, mechanism FROM anomaly_paths LIMIT 5')
    for row in c.fetchall():
        print(f"  {row[0]}: {row[1]} - {row[2][:80]}")
    
    conn.close()
except Exception as e:
    print(f"Error: {e}")

# 检查 predefined_edges.yaml
print("\n" + "=" * 50)
print("predefined_edges.yaml")
print("=" * 50)
yaml_path = Path(__file__).parent.parent / 'config' / 'predefined_edges.yaml'
try:
    import yaml
    with open(yaml_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    
    meta = data.get('metadata', {})
    print(f"Version: {meta.get('version')}")
    print(f"Stats: {meta.get('stats')}")
    
    bypasses = data.get('bypasses', [])
    print(f"\nBypasses count: {len(bypasses)}")
    for b in bypasses[:3]:
        print(f"  - {b.get('id', '?')}")
        hs = b.get('hidden_skill', {})
        print(f"    hidden_skill: {hs.get('name', '?')}")
        print(f"    bypass_path: {b.get('bypass_path', '?')}")
        bc = b.get('bypassed_constraints', [])
        print(f"    bypassed_constraints: {len(bc)}")
except Exception as e:
    print(f"Error: {e}")
