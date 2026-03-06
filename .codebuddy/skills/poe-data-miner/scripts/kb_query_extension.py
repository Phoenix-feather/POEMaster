#!/usr/bin/env python3
"""
扩展kb_query.py以支持公式查询

这个文件展示如何将公式查询功能集成到kb_query.py中
"""

# 在KnowledgeBaseQuery类中添加以下方法：

def __init__(self, kb_path: str = None):
    """初始化（扩展版）"""
    self.kb_path = Path(kb_path) if kb_path else DEFAULT_KB_PATH
    self.entities_db = self.kb_path / 'entities.db'
    self.rules_db = self.kb_path / 'rules.db'
    self.graph_db = self.kb_path / 'graph.db'
    self.mechanisms_db = self.kb_path / 'mechanisms.db'
    self.formulas_db = self.kb_path / 'formulas.db'  # 新增

# ========== 公式查询 ==========

def get_formulas_stats(self) -> Dict[str, Any]:
    """获取公式库统计信息"""
    if not self.formulas_db.exists():
        return {'error': 'formulas.db not found'}

    conn = sqlite3.connect(self.formulas_db)
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM formulas")
    formula_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM formula_stats")
    stat_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM formula_calls")
    call_count = cursor.fetchone()[0]

    cursor.execute("""
        SELECT call_depth, COUNT(*) as cnt
        FROM formulas
        GROUP BY call_depth
        ORDER BY call_depth
    """)
    depth_dist = {row[0]: row[1] for row in cursor.fetchall()}

    conn.close()

    return {
        'formulas': formula_count,
        'stat_relations': stat_count,
        'call_relations': call_count,
        'depth_distribution': depth_dist
    }

def get_formula(self, formula_id: str) -> Optional[Dict[str, Any]]:
    """获取单个公式"""
    if not self.formulas_db.exists():
        return None

    conn = sqlite3.connect(self.formulas_db)
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM formulas WHERE id = ?', (formula_id,))
    row = cursor.fetchone()

    if row:
        cols = [d[0] for d in cursor.description]
        result = dict(zip(cols, row))

        # 解析JSON字段
        json_fields = ['exact_stats', 'fuzzy_stats', 'inferred_tags',
                      'calls', 'called_by', 'total_stats', 'constraints']

        for field in json_fields:
            if result.get(field):
                try:
                    result[field] = json.loads(result[field])
                except:
                    pass

        conn.close()
        return result

    conn.close()
    return None

def search_formulas(self, keyword: str) -> List[Dict[str, Any]]:
    """搜索公式"""
    if not self.formulas_db.exists():
        return []

    conn = sqlite3.connect(self.formulas_db)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, name, source_file, call_depth
        FROM formulas
        WHERE name LIKE ? OR source_file LIKE ?
        ORDER BY call_depth DESC
        LIMIT 20
    """, (f'%{keyword}%', f'%{keyword}%'))

    results = []
    for row in cursor.fetchall():
        results.append({
            'id': row[0],
            'name': row[1],
            'source': row[2],
            'depth': row[3]
        })

    conn.close()
    return results

def find_formulas_for_entity(self, entity_id: str) -> List[Dict[str, Any]]:
    """查找与实体相关的公式"""
    if not self.formulas_db.exists():
        return []

    # 导入公式匹配器
    from formula_matcher import FormulaMatcher

    matcher = FormulaMatcher(
        str(self.formulas_db),
        str(self.entities_db)
    )

    matches = matcher.find_matching_formulas(entity_id)

    return [
        {
            'formula_id': m.formula_id,
            'formula_name': m.formula_name,
            'score': m.score,
            'details': m.details
        }
        for m in matches
    ]

def find_formulas_by_stat(self, stat_id: str) -> List[Dict[str, Any]]:
    """查找使用指定stat的公式"""
    if not self.formulas_db.exists():
        return []

    conn = sqlite3.connect(self.formulas_db)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT f.id, f.name, f.call_depth, fs.confidence
        FROM formulas f
        JOIN formula_stats fs ON f.id = fs.formula_id
        WHERE fs.stat_id = ?
        ORDER BY fs.confidence DESC, f.call_depth DESC
        LIMIT 20
    """, (stat_id,))

    results = []
    for row in cursor.fetchall():
        results.append({
            'id': row[0],
            'name': row[1],
            'depth': row[2],
            'confidence': row[3]
        })

    conn.close()
    return results

def get_formula_call_chain(self, formula_id: str) -> Optional[Dict[str, Any]]:
    """获取公式的调用链"""
    if not self.formulas_db.exists():
        return None

    from formula_matcher import FormulaMatcher

    matcher = FormulaMatcher(
        str(self.formulas_db),
        str(self.entities_db)
    )

    return matcher.get_formula_call_chain(formula_id)


# 在main函数中添加以下命令处理：

"""
# 公式查询
formula_parser = subparsers.add_parser('formula', help='公式查询')
formula_parser.add_argument('id', nargs='?', help='公式ID')
formula_parser.add_argument('--search', '-s', help='搜索公式')
formula_parser.add_argument('--entity', '-e', help='查找实体相关的公式')
formula_parser.add_argument('--stat', help='查找使用指定stat的公式')
formula_parser.add_argument('--chain', '-c', action='store_true', help='显示调用链')

# 在命令处理部分添加：
elif args.command == 'formula':
    if args.entity:
        matches = kb.find_formulas_for_entity(args.entity)
        print(f"找到 {len(matches)} 个匹配的公式：")
        for i, m in enumerate(matches[:10], 1):
            print(f"{i}. {m['formula_name']} (分数: {m['score']:.3f})")
    elif args.stat:
        formulas = kb.find_formulas_by_stat(args.stat)
        print(f"找到 {len(formulas)} 个使用此stat的公式：")
        for i, f in enumerate(formulas):
            print(f"{i}. {f['name']} (深度: {f['depth']}, 置信度: {f['confidence']:.2f})")
    elif args.search:
        formulas = kb.search_formulas(args.search)
        for f in formulas:
            print(f"{f['id']}: {f['name']} (深度: {f['depth']})")
    elif args.id:
        if args.chain:
            chain = kb.get_formula_call_chain(args.id)
            if chain:
                print(f"公式: {chain['formula']['name']}")
                print(f"深度: {chain['formula']['depth']}")
                print(f"源文件: {chain['formula']['source']}")
                if chain['calls']:
                    print(f"调用: {[c['name'] for c in chain['calls']]}")
                if chain['called_by']:
                    print(f"被调用: {[c['name'] for c in chain['called_by']]}")
        else:
            formula = kb.get_formula(args.id)
            if formula:
                print(json.dumps(formula, indent=2, ensure_ascii=False, default=str))
            else:
                print(f"Formula not found: {args.id}")
    else:
        stats = kb.get_formulas_stats()
        print("公式库统计：")
        print(f"  公式数量: {stats.get('formulas', 0)}")
        print(f"  Stat关联: {stats.get('stat_relations', 0)}")
        print(f"  调用关系: {stats.get('call_relations', 0)}")
        if 'depth_distribution' in stats:
            print("  深度分布:")
            for depth, count in sorted(stats['depth_distribution'].items()):
                print(f"    深度 {depth}: {count} 个")
"""
