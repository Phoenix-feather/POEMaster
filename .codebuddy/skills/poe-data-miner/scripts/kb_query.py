#!/usr/bin/env python3
"""
POE知识库查询工具
封装常用查询，避免命令行引号问题
"""

import sqlite3
import json
import argparse
from pathlib import Path
from typing import List, Dict, Any, Optional

# 默认数据库路径
DEFAULT_KB_PATH = Path(__file__).parent.parent / 'knowledge_base'


class KnowledgeBaseQuery:
    """知识库查询工具"""
    
    def __init__(self, kb_path: str = None):
        self.kb_path = Path(kb_path) if kb_path else DEFAULT_KB_PATH
        self.entities_db = self.kb_path / 'entities.db'
        self.rules_db = self.kb_path / 'rules.db'
        self.graph_db = self.kb_path / 'graph.db'
        self.mechanisms_db = self.kb_path / 'mechanisms.db'
    
    # ========== 实体查询 ==========
    
    def get_entity(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """获取单个实体"""
        conn = sqlite3.connect(self.entities_db)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM entities WHERE id = ?', (entity_id,))
        row = cursor.fetchone()
        
        if row:
            cols = [d[0] for d in cursor.description]
            result = dict(zip(cols, row))
            # 解析JSON字段
            for key in ['skill_types', 'constant_stats', 'stats', 'reservation']:
                if result.get(key):
                    try:
                        result[key] = json.loads(result[key])
                    except:
                        pass
            conn.close()
            return result
        
        conn.close()
        return None
    
    def search_entities(self, keyword: str, limit: int = 20) -> List[Dict[str, Any]]:
        """搜索实体"""
        conn = sqlite3.connect(self.entities_db)
        cursor = conn.cursor()
        
        pattern = f'%{keyword}%'
        cursor.execute('''
            SELECT id, name, type FROM entities 
            WHERE id LIKE ? OR name LIKE ? 
            LIMIT ?
        ''', (pattern, pattern, limit))
        
        results = []
        for row in cursor.fetchall():
            results.append({'id': row[0], 'name': row[1], 'type': row[2]})
        
        conn.close()
        return results
    
    def get_entities_by_type(self, entity_type: str, limit: int = 50) -> List[Dict[str, Any]]:
        """按类型获取实体"""
        conn = sqlite3.connect(self.entities_db)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, name, type FROM entities 
            WHERE type = ? 
            LIMIT ?
        ''', (entity_type, limit))
        
        results = []
        for row in cursor.fetchall():
            results.append({'id': row[0], 'name': row[1], 'type': row[2]})
        
        conn.close()
        return results
    
    def get_entities_by_skill_type(self, skill_type: str, limit: int = 50) -> List[Dict[str, Any]]:
        """按技能类型获取实体"""
        conn = sqlite3.connect(self.entities_db)
        cursor = conn.cursor()
        
        pattern = f'%{skill_type}%'
        cursor.execute('''
            SELECT id, name, skill_types FROM entities 
            WHERE skill_types LIKE ? 
            LIMIT ?
        ''', (pattern, limit))
        
        results = []
        for row in cursor.fetchall():
            results.append({'id': row[0], 'name': row[1], 'skill_types': row[2]})
        
        conn.close()
        return results
    
    def get_meta_skills(self) -> List[Dict[str, Any]]:
        """获取所有元技能"""
        return self.get_entities_by_skill_type('Meta')
    
    # ========== 规则查询 ==========
    
    def get_rule(self, rule_id: str) -> Optional[Dict[str, Any]]:
        """获取单个规则"""
        conn = sqlite3.connect(self.rules_db)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM rules WHERE id = ?', (rule_id,))
        row = cursor.fetchone()
        
        if row:
            cols = [d[0] for d in cursor.description]
            result = dict(zip(cols, row))
            conn.close()
            return result
        
        conn.close()
        return None
    
    def get_rules_by_category(self, category: str) -> List[Dict[str, Any]]:
        """按类别获取规则"""
        conn = sqlite3.connect(self.rules_db)
        cursor = conn.cursor()
        
        cursor.execute('SELECT id, name, category, condition, effect, formula FROM rules WHERE category = ?', (category,))
        
        results = []
        cols = [d[0] for d in cursor.description]
        for row in cursor.fetchall():
            results.append(dict(zip(cols, row)))
        
        conn.close()
        return results
    
    def search_rules(self, keyword: str, limit: int = 20) -> List[Dict[str, Any]]:
        """搜索规则"""
        conn = sqlite3.connect(self.rules_db)
        cursor = conn.cursor()
        
        pattern = f'%{keyword}%'
        cursor.execute('''
            SELECT id, name, category, condition, effect FROM rules 
            WHERE name LIKE ? OR condition LIKE ? OR effect LIKE ?
            LIMIT ?
        ''', (pattern, pattern, pattern, limit))
        
        results = []
        cols = [d[0] for d in cursor.description]
        for row in cursor.fetchall():
            results.append(dict(zip(cols, row)))
        
        conn.close()
        return results
    
    def get_formula_rules(self) -> List[Dict[str, Any]]:
        """获取公式规则"""
        return self.get_rules_by_category('formula')
    
    def get_constraint_rules(self) -> List[Dict[str, Any]]:
        """获取约束规则"""
        return self.get_rules_by_category('constraint')
    
    def get_bypass_rules(self) -> List[Dict[str, Any]]:
        """获取绕过规则"""
        return self.get_rules_by_category('bypass')
    
    # ========== 图查询 ==========
    
    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        """获取节点"""
        conn = sqlite3.connect(self.graph_db)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM graph_nodes WHERE id = ?', (node_id,))
        row = cursor.fetchone()
        
        if row:
            cols = [d[0] for d in cursor.description]
            result = dict(zip(cols, row))
            conn.close()
            return result
        
        conn.close()
        return None
    
    def get_neighbors(self, node_id: str) -> List[Dict[str, Any]]:
        """获取邻居节点"""
        conn = sqlite3.connect(self.graph_db)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT e.edge_type, n.id, n.name, n.type 
            FROM graph_edges e 
            JOIN graph_nodes n ON e.target = n.id 
            WHERE e.source = ?
        ''', (node_id,))
        
        results = []
        for row in cursor.fetchall():
            results.append({
                'edge_type': row[0],
                'id': row[1],
                'name': row[2],
                'type': row[3]
            })
        
        conn.close()
        return results
    
    def find_path(self, source: str, target: str, max_depth: int = 5) -> List[List[Dict]]:
        """查找路径（BFS）"""
        conn = sqlite3.connect(self.graph_db)
        cursor = conn.cursor()
        
        # BFS实现
        queue = [(source, [])]
        visited = set()
        
        while queue and len(visited) < 1000:
            current, path = queue.pop(0)
            
            if current in visited:
                continue
            visited.add(current)
            
            # 获取邻居
            cursor.execute('''
                SELECT target, edge_type FROM graph_edges WHERE source = ?
            ''', (current,))
            neighbors = cursor.fetchall()
            
            for neighbor_id, edge_type in neighbors:
                new_path = path + [{'from': current, 'edge': edge_type, 'to': neighbor_id}]
                
                if neighbor_id == target:
                    conn.close()
                    return new_path
                
                if neighbor_id not in visited and len(new_path) < max_depth:
                    queue.append((neighbor_id, new_path))
        
        conn.close()
        return []

    # ========== 机制查询 ==========

    def get_mechanism(self, mechanism_id: str) -> Optional[Dict[str, Any]]:
        """获取单个机制"""
        if not self.mechanisms_db.exists():
            return None
        
        conn = sqlite3.connect(self.mechanisms_db)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM mechanisms WHERE id = ?', (mechanism_id,))
        row = cursor.fetchone()
        
        if row:
            cols = [d[0] for d in cursor.description]
            result = dict(zip(cols, row))
            
            # 获取来源
            cursor.execute('SELECT * FROM mechanism_sources WHERE mechanism_id = ?', (mechanism_id,))
            result['sources'] = [dict(zip([d[0] for d in cursor.description], r)) for r in cursor.fetchall()]
            
            conn.close()
            return result
        
        conn.close()
        return None
    
    def search_mechanisms(self, keyword: str) -> List[Dict[str, Any]]:
        """搜索机制"""
        if not self.mechanisms_db.exists():
            return []
        
        conn = sqlite3.connect(self.mechanisms_db)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, name, source_count FROM mechanisms 
            WHERE id LIKE ? OR name LIKE ?
            ORDER BY source_count DESC
        ''', (f'%{keyword}%', f'%{keyword}%'))
        
        results = [{'id': r[0], 'name': r[1], 'source_count': r[2]} for r in cursor.fetchall()]
        conn.close()
        return results
    
    def get_all_mechanisms(self) -> List[Dict[str, Any]]:
        """获取所有机制"""
        if not self.mechanisms_db.exists():
            return []
        
        conn = sqlite3.connect(self.mechanisms_db)
        cursor = conn.cursor()
        
        cursor.execute('SELECT id, name, source_count FROM mechanisms ORDER BY source_count DESC')
        results = [{'id': r[0], 'name': r[1], 'source_count': r[2]} for r in cursor.fetchall()]
        conn.close()
        return results

    # ========== 统计信息 ==========
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        stats = {
            'entities': {},
            'rules': {},
            'graph': {},
            'mechanisms': {}
        }
        
        # 实体统计
        conn = sqlite3.connect(self.entities_db)
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM entities')
        stats['entities']['total'] = cursor.fetchone()[0]
        cursor.execute('SELECT type, COUNT(*) FROM entities GROUP BY type')
        stats['entities']['by_type'] = dict(cursor.fetchall())
        conn.close()
        
        # 规则统计
        conn = sqlite3.connect(self.rules_db)
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM rules')
        stats['rules']['total'] = cursor.fetchone()[0]
        cursor.execute('SELECT category, COUNT(*) FROM rules GROUP BY category')
        stats['rules']['by_category'] = dict(cursor.fetchall())
        conn.close()
        
        # 图统计
        conn = sqlite3.connect(self.graph_db)
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM graph_nodes')
        stats['graph']['nodes'] = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM graph_edges')
        stats['graph']['edges'] = cursor.fetchone()[0]
        cursor.execute('SELECT type, COUNT(*) FROM graph_nodes GROUP BY type')
        stats['graph']['node_types'] = dict(cursor.fetchall())
        cursor.execute('SELECT edge_type, COUNT(*) FROM graph_edges GROUP BY edge_type')
        stats['graph']['edge_types'] = dict(cursor.fetchall())
        conn.close()
        
        # 机制统计
        if self.mechanisms_db.exists():
            conn = sqlite3.connect(self.mechanisms_db)
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM mechanisms')
            stats['mechanisms']['total'] = cursor.fetchone()[0]
            cursor.execute('SELECT COUNT(*) FROM mechanism_sources')
            stats['mechanisms']['sources'] = cursor.fetchone()[0]
            conn.close()
        
        return stats


def main():
    parser = argparse.ArgumentParser(description='POE知识库查询工具')
    parser.add_argument('--kb-path', default=None, help='知识库路径')
    
    subparsers = parser.add_subparsers(dest='command', help='命令')
    
    # 实体查询
    entity_parser = subparsers.add_parser('entity', help='实体查询')
    entity_parser.add_argument('id', nargs='?', help='实体ID')
    entity_parser.add_argument('--search', '-s', help='搜索关键词')
    entity_parser.add_argument('--type', '-t', help='按类型查询')
    entity_parser.add_argument('--skill-type', help='按技能类型查询')
    entity_parser.add_argument('--meta', action='store_true', help='列出所有元技能')
    
    # 规则查询
    rule_parser = subparsers.add_parser('rule', help='规则查询')
    rule_parser.add_argument('id', nargs='?', help='规则ID')
    rule_parser.add_argument('--category', '-c', help='按类别查询')
    rule_parser.add_argument('--search', '-s', help='搜索关键词')
    rule_parser.add_argument('--formula', action='store_true', help='公式规则')
    rule_parser.add_argument('--constraint', action='store_true', help='约束规则')
    rule_parser.add_argument('--bypass', action='store_true', help='绕过规则')
    
    # 图查询
    graph_parser = subparsers.add_parser('graph', help='图查询')
    graph_parser.add_argument('id', nargs='?', help='节点ID')
    graph_parser.add_argument('--neighbors', '-n', action='store_true', help='获取邻居')
    graph_parser.add_argument('--path', '-p', nargs=2, help='查找路径 (source target)')
    
    # 统计
    stats_parser = subparsers.add_parser('stats', help='统计信息')
    
    # 机制查询
    mech_parser = subparsers.add_parser('mechanism', help='机制查询')
    mech_parser.add_argument('id', nargs='?', help='机制ID')
    mech_parser.add_argument('--search', '-s', help='搜索关键词')
    mech_parser.add_argument('--all', '-a', action='store_true', help='列出所有机制')
    
    args = parser.parse_args()
    
    kb = KnowledgeBaseQuery(args.kb_path)
    
    if args.command == 'entity':
        if args.meta:
            results = kb.get_meta_skills()
            for r in results:
                print(f"{r['id']}: {r['name']}")
        elif args.search:
            results = kb.search_entities(args.search)
            for r in results:
                print(f"{r['id']}: {r['name']} ({r['type']})")
        elif args.type:
            results = kb.get_entities_by_type(args.type)
            for r in results:
                print(f"{r['id']}: {r['name']}")
        elif args.skill_type:
            results = kb.get_entities_by_skill_type(args.skill_type)
            for r in results:
                print(f"{r['id']}: {r['name']}")
        elif args.id:
            entity = kb.get_entity(args.id)
            if entity:
                print(json.dumps(entity, indent=2, ensure_ascii=False, default=str))
            else:
                print(f"Entity not found: {args.id}")
        else:
            print("Please specify --search, --type, --skill-type, --meta, or an entity ID")
    
    elif args.command == 'rule':
        if args.formula:
            results = kb.get_formula_rules()
            for r in results:
                print(f"{r['name']}: {r.get('formula', 'N/A')}")
        elif args.constraint:
            results = kb.get_constraint_rules()
            for r in results:
                print(f"{r['name']}: {r.get('condition', '')} -> {r.get('effect', '')}")
        elif args.bypass:
            results = kb.get_bypass_rules()
            for r in results:
                print(f"{r['name']}: {r.get('condition', '')} -> {r.get('effect', '')}")
        elif args.category:
            results = kb.get_rules_by_category(args.category)
            for r in results:
                print(f"{r['id']}: {r['name']}")
        elif args.search:
            results = kb.search_rules(args.search)
            for r in results:
                print(f"[{r['category']}] {r['name']}")
        elif args.id:
            rule = kb.get_rule(args.id)
            if rule:
                print(json.dumps(rule, indent=2, ensure_ascii=False, default=str))
            else:
                print(f"Rule not found: {args.id}")
        else:
            print("Please specify --formula, --constraint, --bypass, --category, --search, or a rule ID")
    
    elif args.command == 'graph':
        if args.path:
            path = kb.find_path(args.path[0], args.path[1])
            if path:
                for step in path:
                    print(f"{step['from']} --{step['edge']}--> {step['to']}")
            else:
                print("No path found")
        elif args.neighbors and args.id:
            neighbors = kb.get_neighbors(args.id)
            for n in neighbors:
                print(f"--{n['edge_type']}--> {n['name']} ({n['type']})")
        elif args.id:
            node = kb.get_node(args.id)
            if node:
                print(json.dumps(node, indent=2, ensure_ascii=False, default=str))
            else:
                print(f"Node not found: {args.id}")
        else:
            print("Please specify --neighbors, --path, or a node ID")
    
    elif args.command == 'stats':
        stats = kb.get_stats()
        print(json.dumps(stats, indent=2, ensure_ascii=False))
    
    elif args.command == 'mechanism':
        if args.all:
            results = kb.get_all_mechanisms()
            for r in results:
                print(f"{r['id']}: {r['source_count']} sources")
        elif args.search:
            results = kb.search_mechanisms(args.search)
            for r in results:
                print(f"{r['id']}: {r['source_count']} sources")
        elif args.id:
            mech = kb.get_mechanism(args.id)
            if mech:
                print(json.dumps(mech, indent=2, ensure_ascii=False, default=str))
            else:
                print(f"Mechanism not found: {args.id}")
        else:
            print("Please specify --all, --search, or a mechanism ID")
    
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
