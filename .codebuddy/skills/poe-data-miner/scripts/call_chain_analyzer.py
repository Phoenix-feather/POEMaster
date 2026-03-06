#!/usr/bin/env python3
"""
调用链分析器 - 分析函数调用关系，计算调用深度和综合特征

核心功能：
1. 构建调用图
2. 计算调用深度
3. 计算综合特征（包括间接调用）
4. 更新formulas数据库
"""

import sqlite3
import json
from pathlib import Path
from typing import Dict, List, Set, Tuple
from collections import defaultdict, deque
from dataclasses import dataclass, field


@dataclass
class CallGraph:
    """调用图"""
    nodes: Set[str] = field(default_factory=set)          # 所有节点
    edges: Dict[str, Set[str]] = field(default_factory=dict)  # 邻接表：caller -> [callees]
    reverse_edges: Dict[str, Set[str]] = field(default_factory=dict)  # 反向邻接表：callee -> [callers]


class CallChainAnalyzer:
    """调用链分析器"""
    
    def __init__(self, db_path: str):
        """
        初始化调用链分析器
        
        Args:
            db_path: 公式库数据库路径
        """
        self.db_path = Path(db_path)
        self.call_graph = CallGraph()
        self.formulas: Dict[str, Dict] = {}  # formula_id -> formula_data
        self.name_to_id: Dict[str, str] = {}  # function_name -> formula_id
        
        print(f"[初始化] 调用链分析器")
        print(f"  数据库: {self.db_path}")
    
    def load_formulas(self):
        """从数据库加载所有公式"""
        print("\n加载公式数据...")
        
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, name, calls, exact_stats, fuzzy_stats
            FROM formulas
        """)
        
        for row in cursor.fetchall():
            formula_id = row[0]
            name = row[1]
            calls = json.loads(row[2]) if row[2] else []
            exact_stats = json.loads(row[3]) if row[3] else []
            fuzzy_stats = json.loads(row[4]) if row[4] else []
            
            self.formulas[formula_id] = {
                'id': formula_id,
                'name': name,
                'calls': calls,
                'exact_stats': exact_stats,
                'fuzzy_stats': fuzzy_stats,
                'called_by': [],
                'call_depth': 0,
                'total_stats': set(exact_stats + fuzzy_stats)
            }
            
            self.name_to_id[name] = formula_id
        
        conn.close()
        
        print(f"[OK] 加载了 {len(self.formulas)} 个公式")
    
    def build_call_graph(self):
        """构建调用图"""
        print("\n构建调用图...")
        
        # 初始化图结构
        for formula_id in self.formulas.keys():
            self.call_graph.nodes.add(formula_id)
            self.call_graph.edges[formula_id] = set()
            self.call_graph.reverse_edges[formula_id] = set()
        
        # 建立边
        edge_count = 0
        for formula_id, formula in self.formulas.items():
            for called_name in formula['calls']:
                # 查找被调用函数的formula_id
                if called_name in self.name_to_id:
                    callee_id = self.name_to_id[called_name]
                    
                    # 添加边
                    self.call_graph.edges[formula_id].add(callee_id)
                    self.call_graph.reverse_edges[callee_id].add(formula_id)
                    
                    # 更新called_by
                    self.formulas[callee_id]['called_by'].append(formula_id)
                    
                    edge_count += 1
        
        print(f"[OK] 构建完成，{len(self.call_graph.nodes)} 个节点，{edge_count} 条边")
        
        # 保存调用关系到数据库
        self._save_call_relations()
    
    def _save_call_relations(self):
        """保存调用关系到数据库"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        # 清空旧数据
        cursor.execute("DELETE FROM formula_calls")
        
        # 插入新数据
        for caller_id, callees in self.call_graph.edges.items():
            for callee_id in callees:
                cursor.execute("""
                    INSERT INTO formula_calls (caller_id, callee_id, call_count)
                    VALUES (?, ?, 1)
                """, (caller_id, callee_id))
        
        # 更新formulas表的called_by字段
        for formula_id, formula in self.formulas.items():
            cursor.execute("""
                UPDATE formulas
                SET called_by = ?
                WHERE id = ?
            """, (json.dumps(formula['called_by'], ensure_ascii=False), formula_id))
        
        conn.commit()
        conn.close()
        
        print(f"[OK] 调用关系已保存到数据库")
    
    def calculate_call_depth(self):
        """计算调用深度（BFS从叶子节点开始）"""
        print("\n计算调用深度...")
        
        # 找到叶子节点（不调用其他函数的函数）
        leaves = []
        for formula_id, callees in self.call_graph.edges.items():
            if not callees:  # 没有调用任何函数
                leaves.append(formula_id)
        
        print(f"  找到 {len(leaves)} 个叶子节点")
        
        # BFS计算深度
        depths = {}
        queue = deque([(leaf_id, 0) for leaf_id in leaves])
        visited = set()
        
        while queue:
            formula_id, depth = queue.popleft()
            
            if formula_id in visited:
                continue
            
            visited.add(formula_id)
            
            # 更新深度（如果已经有深度，取最大值）
            if formula_id in depths:
                depths[formula_id] = max(depths[formula_id], depth)
            else:
                depths[formula_id] = depth
            
            # 处理调用者
            for caller_id in self.call_graph.reverse_edges[formula_id]:
                if caller_id not in visited:
                    queue.append((caller_id, depth + 1))
        
        # 更新formulas
        for formula_id, depth in depths.items():
            self.formulas[formula_id]['call_depth'] = depth
        
        # 保存到数据库
        self._save_call_depths()
        
        print(f"[OK] 计算完成，深度范围: 0 - {max(depths.values()) if depths else 0}")
    
    def _save_call_depths(self):
        """保存调用深度到数据库"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        for formula_id, formula in self.formulas.items():
            cursor.execute("""
                UPDATE formulas
                SET call_depth = ?
                WHERE id = ?
            """, (formula['call_depth'], formula_id))
        
        conn.commit()
        conn.close()
    
    def compute_total_stats(self):
        """计算综合stats（包括间接调用）"""
        print("\n计算综合stats...")
        
        # 按深度排序，从叶子节点开始计算
        sorted_formulas = sorted(
            self.formulas.items(),
            key=lambda x: x[1]['call_depth']
        )
        
        for formula_id, formula in sorted_formulas:
            total_stats = set(formula['exact_stats'] + formula['fuzzy_stats'])
            
            # 递归收集被调用函数的stats
            for callee_id in self.call_graph.edges[formula_id]:
                if callee_id in self.formulas:
                    total_stats.update(self.formulas[callee_id]['total_stats'])
            
            self.formulas[formula_id]['total_stats'] = total_stats
        
        # 保存到数据库
        self._save_total_stats()
        
        # 计算统计信息
        max_stats = max(len(f['total_stats']) for f in self.formulas.values())
        avg_stats = sum(len(f['total_stats']) for f in self.formulas.values()) / len(self.formulas)
        
        print(f"[OK] 计算完成，平均stats数: {avg_stats:.1f}，最大: {max_stats}")
    
    def _save_total_stats(self):
        """保存综合stats到数据库"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        for formula_id, formula in self.formulas.items():
            total_stats_list = list(formula['total_stats'])
            
            cursor.execute("""
                UPDATE formulas
                SET total_stats = ?
                WHERE id = ?
            """, (json.dumps(total_stats_list, ensure_ascii=False), formula_id))
            
            # 更新formula_stats表
            for stat in total_stats_list:
                cursor.execute("""
                    INSERT OR IGNORE INTO formula_stats
                    (formula_id, stat_id, relation, confidence)
                    VALUES (?, ?, 'uses', 1.0)
                """, (formula_id, stat))
        
        conn.commit()
        conn.close()
    
    def analyze(self):
        """执行完整的调用链分析"""
        print("\n" + "=" * 70)
        print("开始调用链分析")
        print("=" * 70)
        
        # 1. 加载公式
        self.load_formulas()
        
        # 2. 构建调用图
        self.build_call_graph()
        
        # 3. 计算调用深度
        self.calculate_call_depth()
        
        # 4. 计算综合stats
        self.compute_total_stats()
        
        # 5. 生成报告
        self.generate_report()
        
        print("\n" + "=" * 70)
        print("调用链分析完成")
        print("=" * 70)
    
    def generate_report(self):
        """生成分析报告"""
        print("\n" + "=" * 70)
        print("调用链分析报告")
        print("=" * 70)
        
        # 统计调用深度分布
        depth_dist = defaultdict(int)
        for formula in self.formulas.values():
            depth_dist[formula['call_depth']] += 1
        
        print("\n调用深度分布：")
        for depth in sorted(depth_dist.keys()):
            count = depth_dist[depth]
            print(f"  深度 {depth}: {count} 个函数")
        
        # 统计调用关系
        edge_count = sum(len(callees) for callees in self.call_graph.edges.values())
        avg_calls = edge_count / len(self.formulas) if self.formulas else 0
        
        print(f"\n调用关系统计：")
        print(f"  总边数: {edge_count}")
        print(f"  平均调用: {avg_calls:.2f} 个函数")
        
        # 显示最复杂的函数（调用最多其他函数）
        most_calls = sorted(
            self.formulas.items(),
            key=lambda x: len(x[1]['calls']),
            reverse=True
        )[:5]
        
        print(f"\n调用最多的函数（Top 5）：")
        for i, (formula_id, formula) in enumerate(most_calls, 1):
            print(f"  {i}. {formula['name']}: 调用 {len(formula['calls'])} 个函数")
        
        # 显示被调用最多的函数
        most_called = sorted(
            self.formulas.items(),
            key=lambda x: len(x[1]['called_by']),
            reverse=True
        )[:5]
        
        print(f"\n被调用最多的函数（Top 5）：")
        for i, (formula_id, formula) in enumerate(most_called, 1):
            print(f"  {i}. {formula['name']}: 被调用 {len(formula['called_by'])} 次")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='调用链分析器')
    parser.add_argument('db_path', help='公式库数据库路径')
    
    args = parser.parse_args()
    
    # 创建分析器
    analyzer = CallChainAnalyzer(db_path=args.db_path)
    
    # 执行分析
    analyzer.analyze()


if __name__ == "__main__":
    main()
