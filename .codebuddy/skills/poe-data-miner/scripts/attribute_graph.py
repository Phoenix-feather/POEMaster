#!/usr/bin/env python3
"""
POE属性关联图模块
存储机制节点和关系边，支持图遍历查询
"""

import json
import sqlite3
from pathlib import Path
from typing import Dict, List, Any, Optional, Set, Tuple
from dataclasses import dataclass
from enum import Enum

# 尝试导入yaml
try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


class NodeType(Enum):
    """节点类型"""
    ENTITY = "entity"        # 实体节点（技能、物品等）
    MECHANISM = "mechanism"  # 机制节点（skillTypes、效果等）
    ATTRIBUTE = "attribute"  # 属性节点（stats）
    CONSTRAINT = "constraint"  # 约束节点


class EdgeType(Enum):
    """边类型"""
    HAS_TYPE = "has_type"
    HAS_STAT = "has_stat"
    CAUSES = "causes"
    BLOCKS = "blocks"
    BYPASSES = "bypasses"
    MODIFIES = "modifies"
    ENHANCES = "enhances"
    REDUCES = "reduces"
    TRIGGERS = "triggers"
    REQUIRES = "requires"
    CONSUMES = "consumes"
    GRANTS = "grants"
    # 预置边类型
    USES_FORMULA = "uses_formula"
    APPLIES = "applies"
    RESERVES = "reserves"


@dataclass
class GraphNode:
    """图节点"""
    id: str
    type: NodeType
    name: str
    attributes: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.attributes is None:
            self.attributes = {}


@dataclass
class GraphEdge:
    """图边"""
    source: str
    target: str
    type: EdgeType
    weight: float = 1.0
    attributes: Dict[str, Any] = None
    confirmed: bool = False
    source_type: str = "auto"  # auto, predefined, user_confirmed
    
    def __post_init__(self):
        if self.attributes is None:
            self.attributes = {}


class AttributeGraph:
    """属性关联图"""
    
    def __init__(self, db_path: str, predefined_edges_path: str = None):
        """
        初始化关联图
        
        Args:
            db_path: SQLite数据库路径
            predefined_edges_path: 预置边配置文件路径
        """
        self.db_path = Path(db_path)
        self.predefined_edges_path = predefined_edges_path
        self.conn: Optional[sqlite3.Connection] = None
        self.node_cache: Dict[str, GraphNode] = {}
        self.edge_cache: List[GraphEdge] = []
        
        self._init_database()
        
        if predefined_edges_path:
            self._load_predefined_edges()
    
    def _init_database(self):
        """初始化数据库"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self._create_tables()
        self._create_indexes()
    
    def _create_tables(self):
        """创建表结构"""
        cursor = self.conn.cursor()
        
        # 节点表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS graph_nodes (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                name TEXT NOT NULL,
                attributes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 边表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS graph_edges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_node TEXT NOT NULL,
                target_node TEXT NOT NULL,
                edge_type TEXT NOT NULL,
                weight REAL DEFAULT 1.0,
                attributes TEXT,
                confirmed BOOLEAN DEFAULT 0,
                source_type TEXT DEFAULT 'auto',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (source_node) REFERENCES graph_nodes(id),
                FOREIGN KEY (target_node) REFERENCES graph_nodes(id)
            )
        ''')
        
        self.conn.commit()
    
    def _create_indexes(self):
        """创建索引"""
        cursor = self.conn.cursor()
        
        # 节点索引
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_nodes_type ON graph_nodes(type)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_nodes_name ON graph_nodes(name)')
        
        # 边索引（用于图遍历）
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_edges_source ON graph_edges(source_node)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_edges_target ON graph_edges(target_node)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_edges_type ON graph_edges(edge_type)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_edges_confirmed ON graph_edges(confirmed)')
        
        self.conn.commit()
    
    # ========== 节点操作 ==========
    
    def create_node(self, node: GraphNode) -> bool:
        """创建节点"""
        cursor = self.conn.cursor()
        
        try:
            cursor.execute('''
                INSERT OR IGNORE INTO graph_nodes (id, type, name, attributes)
                VALUES (?, ?, ?, ?)
            ''', (
                node.id,
                node.type.value,
                node.name,
                json.dumps(node.attributes, ensure_ascii=False)
            ))
            self.conn.commit()
            self.node_cache[node.id] = node
            return True
        except sqlite3.IntegrityError:
            return False
    
    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        """获取节点"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM graph_nodes WHERE id = ?', (node_id,))
        row = cursor.fetchone()
        
        if row:
            return self._row_to_node_dict(row)
        return None
    
    def get_nodes_by_type(self, node_type: NodeType) -> List[Dict[str, Any]]:
        """按类型获取节点"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM graph_nodes WHERE type = ?', (node_type.value,))
        rows = cursor.fetchall()
        
        return [self._row_to_node_dict(row) for row in rows]
    
    def search_nodes(self, query: str) -> List[Dict[str, Any]]:
        """搜索节点"""
        cursor = self.conn.cursor()
        pattern = f'%{query}%'
        cursor.execute('SELECT * FROM graph_nodes WHERE name LIKE ? OR id LIKE ?', (pattern, pattern))
        rows = cursor.fetchall()
        
        return [self._row_to_node_dict(row) for row in rows]
    
    # ========== 边操作 ==========
    
    def create_edge(self, edge: GraphEdge) -> bool:
        """创建边"""
        cursor = self.conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO graph_edges 
                (source_node, target_node, edge_type, weight, attributes, confirmed, source_type)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                edge.source,
                edge.target,
                edge.type.value,
                edge.weight,
                json.dumps(edge.attributes, ensure_ascii=False),
                edge.confirmed,
                edge.source_type
            ))
            self.conn.commit()
            self.edge_cache.append(edge)
            return True
        except sqlite3.IntegrityError:
            return False
    
    def get_neighbors(self, node_id: str, edge_type: str = None) -> List[Dict[str, Any]]:
        """
        获取节点的邻居
        
        Args:
            node_id: 节点ID
            edge_type: 边类型过滤（可选）
            
        Returns:
            邻居节点列表
        """
        cursor = self.conn.cursor()
        
        if edge_type:
            cursor.execute('''
                SELECT n.*, e.edge_type, e.weight, e.confirmed, e.source_type
                FROM graph_nodes n
                JOIN graph_edges e ON n.id = e.target_node
                WHERE e.source_node = ? AND e.edge_type = ?
            ''', (node_id, edge_type))
        else:
            cursor.execute('''
                SELECT n.*, e.edge_type, e.weight, e.confirmed, e.source_type
                FROM graph_nodes n
                JOIN graph_edges e ON n.id = e.target_node
                WHERE e.source_node = ?
            ''', (node_id,))
        
        rows = cursor.fetchall()
        return [self._row_to_edge_dict(row) for row in rows]
    
    def get_reverse_neighbors(self, node_id: str, edge_type: str = None) -> List[Dict[str, Any]]:
        """获取反向邻居（谁指向这个节点）"""
        cursor = self.conn.cursor()
        
        if edge_type:
            cursor.execute('''
                SELECT n.*, e.edge_type, e.weight, e.confirmed, e.source_type
                FROM graph_nodes n
                JOIN graph_edges e ON n.id = e.source_node
                WHERE e.target_node = ? AND e.edge_type = ?
            ''', (node_id, edge_type))
        else:
            cursor.execute('''
                SELECT n.*, e.edge_type, e.weight, e.confirmed, e.source_type
                FROM graph_nodes n
                JOIN graph_edges e ON n.id = e.source_node
                WHERE e.target_node = ?
            ''', (node_id,))
        
        rows = cursor.fetchall()
        return [self._row_to_edge_dict(row) for row in rows]
    
    # ========== 图遍历 ==========
    
    def find_path(self, source: str, target: str, max_depth: int = 5) -> List[List[Dict[str, Any]]]:
        """
        查找两个节点之间的路径（BFS）
        
        Args:
            source: 起始节点
            target: 目标节点
            max_depth: 最大搜索深度
            
        Returns:
            所有找到的路径
        """
        paths = []
        visited = set()
        queue = [(source, [])]
        
        while queue:
            current, path = queue.pop(0)
            
            if len(path) > max_depth:
                continue
            
            if current == target and path:
                paths.append(path)
                continue
            
            if current in visited:
                continue
            visited.add(current)
            
            neighbors = self.get_neighbors(current)
            for neighbor in neighbors:
                if neighbor['id'] not in visited:
                    new_path = path + [neighbor]
                    queue.append((neighbor['id'], new_path))
        
        return paths
    
    def find_all_paths_by_edge_type(self, edge_type: str, max_depth: int = 3) -> List[List[Dict[str, Any]]]:
        """
        查找特定类型边的所有路径
        
        Args:
            edge_type: 边类型
            max_depth: 最大深度
            
        Returns:
            路径列表
        """
        cursor = self.conn.cursor()
        cursor.execute('SELECT DISTINCT source_node FROM graph_edges WHERE edge_type = ?', (edge_type,))
        sources = [row['source_node'] for row in cursor.fetchall()]
        
        all_paths = []
        for source in sources:
            paths = self._bfs_by_edge_type(source, edge_type, max_depth)
            all_paths.extend(paths)
        
        return all_paths
    
    def _bfs_by_edge_type(self, start: str, edge_type: str, max_depth: int) -> List[List[Dict[str, Any]]]:
        """按边类型BFS"""
        paths = []
        queue = [(start, [], 0)]
        
        while queue:
            current, path, depth = queue.pop(0)
            
            if depth >= max_depth:
                continue
            
            neighbors = self.get_neighbors(current, edge_type)
            for neighbor in neighbors:
                new_path = path + [neighbor]
                paths.append(new_path)
                queue.append((neighbor['id'], new_path, depth + 1))
        
        return paths
    
    def find_bypass_paths(self, constraint_node: str) -> List[Dict[str, Any]]:
        """
        查找绕过某个约束的路径
        
        Args:
            constraint_node: 约束节点ID
            
        Returns:
            绕过路径列表
        """
        # 查找所有 bypasses 类型的边指向这个约束
        bypasses = self.get_reverse_neighbors(constraint_node, EdgeType.BYPASSES.value)
        
        paths = []
        for bypass in bypasses:
            path = {
                'bypass_source': bypass['id'],
                'constraint': constraint_node,
                'edge_type': 'bypasses',
                'confirmed': bypass.get('confirmed', False),
                'source_type': bypass.get('source_type', 'auto')
            }
            paths.append(path)
        
        return paths
    
    # ========== 批量构建 ==========
    
    def build_from_entities(self, entities: List[Dict[str, Any]]):
        """
        从实体数据构建关联图
        
        Args:
            entities: 实体列表
        """
        for entity in entities:
            entity_id = entity.get('id', '')
            entity_name = entity.get('name', entity_id)
            
            # 创建实体节点
            self.create_node(GraphNode(
                id=entity_id,
                type=NodeType.ENTITY,
                name=entity_name,
                attributes={'type': entity.get('type', 'unknown')}
            ))
            
            # 创建skillTypes关联边
            skill_types = entity.get('skill_types', [])
            for skill_type in skill_types:
                # 创建机制节点
                mech_id = f"mech_{skill_type.lower()}"
                self.create_node(GraphNode(
                    id=mech_id,
                    type=NodeType.MECHANISM,
                    name=skill_type
                ))
                
                # 创建边
                self.create_edge(GraphEdge(
                    source=entity_id,
                    target=mech_id,
                    type=EdgeType.HAS_TYPE,
                    source_type="auto"
                ))
            
            # 创建stats关联边
            stats = entity.get('stats', [])
            constant_stats = entity.get('constant_stats', [])
            
            # 处理不同类型的 stats 格式
            all_stats = []
            
            # stats 可能是列表或字典
            if isinstance(stats, list):
                all_stats.extend(stats)
            elif isinstance(stats, dict):
                all_stats.extend(stats.keys())
            
            # constant_stats 可能是列表
            if isinstance(constant_stats, list):
                for s in constant_stats:
                    if isinstance(s, (list, tuple)) and len(s) > 0:
                        all_stats.append(s[0])
                    elif isinstance(s, str):
                        all_stats.append(s)
            elif isinstance(constant_stats, dict):
                all_stats.extend(constant_stats.keys())
            
            for stat in all_stats:
                if isinstance(stat, str):
                    # 创建属性节点
                    attr_id = f"attr_{stat.lower().replace('/', '_')}"
                    self.create_node(GraphNode(
                        id=attr_id,
                        type=NodeType.ATTRIBUTE,
                        name=stat
                    ))
                    
                    # 创建边
                    self.create_edge(GraphEdge(
                        source=entity_id,
                        target=attr_id,
                        type=EdgeType.HAS_STAT,
                        source_type="auto"
                    ))
    
    def build_from_rules(self, rules: List[Dict[str, Any]]):
        """
        从规则构建关联图
        
        Args:
            rules: 规则列表
        """
        for rule in rules:
            category = rule.get('category', '')
            condition = rule.get('condition', '')
            effect = rule.get('effect', '')
            
            if category == 'constraint' and condition and effect:
                # 创建约束节点
                constraint_id = f"constraint_{rule['id']}"
                self.create_node(GraphNode(
                    id=constraint_id,
                    type=NodeType.CONSTRAINT,
                    name=rule.get('name', ''),
                    attributes={'description': rule.get('description', '')}
                ))
                
                # 创建blocks边
                # 这里简化处理，实际需要解析condition和effect
                if 'Triggered' in condition:
                    mech_id = "mech_triggered"
                    self.create_node(GraphNode(
                        id=mech_id,
                        type=NodeType.MECHANISM,
                        name="Triggered"
                    ))
                    
                    self.create_edge(GraphEdge(
                        source=mech_id,
                        target=constraint_id,
                        type=EdgeType.CAUSES,
                        source_type="auto"
                    ))
    
    # ========== 预置边加载 ==========
    
    def _load_predefined_edges(self):
        """
        加载预置边
        
        预置边配置文件: config/predefined_edges.yaml
        包含无法从POB数据自动提取的关键隐含知识，如:
        - 能量生成绕过机制
        - 触发标签限制
        - Spirit预留规则
        """
        if not self.predefined_edges_path or not Path(self.predefined_edges_path).exists():
            print(f"[INFO] 无预置边配置，跳过加载")
            return
        
        print(f"[INFO] 加载预置边: {self.predefined_edges_path}")
        
        with open(self.predefined_edges_path, 'r', encoding='utf-8') as f:
            if HAS_YAML:
                config = yaml.safe_load(f)
            else:
                print("[WARN] PyYAML 未安装，无法加载预置边")
                return
        
        edges = config.get('edges', [])
        loaded_count = 0
        skipped_types = []
        
        for edge_config in edges:
            source = edge_config.get('source', '')
            target = edge_config.get('target', '')
            edge_type = edge_config.get('edge_type', '')
            
            # 确保节点存在
            self._ensure_node_exists(source, edge_config.get('description', ''))
            self._ensure_node_exists(target)
            
            # 创建边
            try:
                edge_type_enum = EdgeType(edge_type)
            except ValueError:
                if edge_type not in skipped_types:
                    skipped_types.append(edge_type)
                continue
            
            self.create_edge(GraphEdge(
                source=source,
                target=target,
                type=edge_type_enum,
                attributes={
                    'description': edge_config.get('description', ''),
                    'applicable_skills': edge_config.get('applicable_skills', [])
                },
                confirmed=True,
                source_type="predefined"
            ))
            loaded_count += 1
        
        # 输出加载结果
        if loaded_count > 0:
            print(f"[OK] 已加载 {loaded_count} 条预置边")
        if skipped_types:
            print(f"[WARN] 跳过未识别的边类型: {skipped_types}")
    
    def _ensure_node_exists(self, node_id: str, description: str = ''):
        """确保节点存在"""
        if not self.get_node(node_id):
            self.create_node(GraphNode(
                id=node_id,
                type=NodeType.MECHANISM,
                name=node_id,
                attributes={'description': description}
            ))
    
    # ========== 统计 ==========
    
    def get_stats(self) -> Dict[str, Any]:
        """获取图统计信息"""
        cursor = self.conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM graph_nodes')
        node_count = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM graph_edges')
        edge_count = cursor.fetchone()[0]
        
        cursor.execute('SELECT type, COUNT(*) FROM graph_nodes GROUP BY type')
        node_types = {row['type']: row[1] for row in cursor.fetchall()}
        
        cursor.execute('SELECT edge_type, COUNT(*) FROM graph_edges GROUP BY edge_type')
        edge_types = {row['edge_type']: row[1] for row in cursor.fetchall()}
        
        return {
            'node_count': node_count,
            'edge_count': edge_count,
            'node_types': node_types,
            'edge_types': edge_types
        }
    
    # ========== 工具方法 ==========
    
    def _row_to_node_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        """转换节点行"""
        result = dict(row)
        if result.get('attributes'):
            try:
                result['attributes'] = json.loads(result['attributes'])
            except json.JSONDecodeError:
                pass
        return result
    
    def _row_to_edge_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        """转换边行（包含目标节点信息）"""
        result = {
            'id': row['id'],
            'type': row['type'],
            'name': row['name'],
            'edge_type': row['edge_type'],
            'weight': row['weight'],
            'confirmed': row['confirmed'],
            'source_type': row['source_type']
        }
        return result
    
    def close(self):
        """关闭连接"""
        if self.conn:
            self.conn.close()
            self.conn = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='POE属性关联图')
    parser.add_argument('db_path', help='SQLite数据库路径')
    parser.add_argument('--predefined', help='预置边配置文件路径')
    parser.add_argument('--entities', help='实体JSON文件路径')
    parser.add_argument('--rules', help='规则JSON文件路径')
    parser.add_argument('--path', nargs=2, metavar=('SOURCE', 'TARGET'), help='查找路径')
    parser.add_argument('--neighbors', help='获取邻居节点')
    parser.add_argument('--bypass', help='查找绕过路径')
    parser.add_argument('--stats', action='store_true', help='显示统计信息')
    
    args = parser.parse_args()
    
    with AttributeGraph(args.db_path, args.predefined) as graph:
        # 构建
        if args.entities:
            with open(args.entities, 'r', encoding='utf-8') as f:
                entities = json.load(f)
            graph.build_from_entities(entities)
            print(f"从实体构建关联图完成")
        
        if args.rules:
            with open(args.rules, 'r', encoding='utf-8') as f:
                rules = json.load(f)
            graph.build_from_rules(rules)
            print(f"从规则构建关联图完成")
        
        # 查询
        if args.path:
            paths = graph.find_path(args.path[0], args.path[1])
            for i, path in enumerate(paths):
                print(f"路径 {i+1}: {' -> '.join(n['name'] for n in path)}")
        
        if args.neighbors:
            neighbors = graph.get_neighbors(args.neighbors)
            for n in neighbors:
                print(f"- [{n['edge_type']}] {n['name']}")
        
        if args.bypass:
            bypasses = graph.find_bypass_paths(args.bypass)
            for bp in bypasses:
                print(f"- {bp['bypass_source']} bypasses {bp['constraint']}")
        
        # 统计
        if args.stats:
            stats = graph.get_stats()
            print(f"节点数: {stats['node_count']}")
            print(f"边数: {stats['edge_count']}")
            print("节点类型:", stats['node_types'])
            print("边类型:", stats['edge_types'])


if __name__ == '__main__':
    main()
