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
            SELECT id, name, calls, exact_stats, fuzzy_stats, source_file
            FROM formulas
        """)
        
        for row in cursor.fetchall():
            formula_id = row[0]
            name = row[1]
            calls = json.loads(row[2]) if row[2] else []
            exact_stats = json.loads(row[3]) if row[3] else []
            fuzzy_stats = json.loads(row[4]) if row[4] else []
            source_file = row[5] or ''
            
            self.formulas[formula_id] = {
                'id': formula_id,
                'name': name,
                'calls': calls,
                'exact_stats': exact_stats,
                'fuzzy_stats': fuzzy_stats,
                'source_file': source_file,
                'called_by': [],
                'call_depth': 0,
                'total_stats': set(exact_stats + fuzzy_stats)
            }
            
            # 同名函数保存为列表（处理重复）
            if name not in self.name_to_id:
                self.name_to_id[name] = []
            self.name_to_id[name].append(formula_id)
            
            # 也存储 module.name 和 module:name 的短名称映射
            if '.' in name or ':' in name:
                short_name = name.split('.')[-1].split(':')[-1]
                if short_name not in self.name_to_id:
                    self.name_to_id[short_name] = []
                self.name_to_id[short_name].append(formula_id)
        
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
            caller_source = formula.get('source_file', '')
            
            for called_name in formula['calls']:
                # 查找被调用函数的formula_id
                candidates = self.name_to_id.get(called_name, [])
                
                if not candidates:
                    continue
                
                # 优先匹配同文件的函数，其次选择第一个
                callee_id = None
                for cid in candidates:
                    if cid == formula_id:
                        continue  # 跳过自身递归
                    callee_src = self.formulas[cid].get('source_file', '')
                    if callee_src == caller_source:
                        callee_id = cid
                        break
                
                if callee_id is None:
                    # 选择第一个非自身的候选
                    for cid in candidates:
                        if cid != formula_id:
                            callee_id = cid
                            break
                
                if callee_id is None:
                    continue
                
                # 添加边
                self.call_graph.edges[formula_id].add(callee_id)
                if callee_id not in self.call_graph.reverse_edges:
                    self.call_graph.reverse_edges[callee_id] = set()
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
        """计算调用深度（反向BFS：从叶子节点向上传播最大深度）
        
        深度定义：
        - 叶子节点（不调用其他函数）= 深度0
        - 调用叶子节点的函数 = 深度1
        - 以此类推，取最大值
        
        修复：不使用visited集合阻止重复访问，而是使用深度更新逻辑
        确保每个节点取到最大深度值。
        """
        print("\n计算调用深度...")
        
        # 方法：拓扑排序 + 动态规划（正向：caller→callee）
        # depth(f) = 0 if f是叶子节点
        # depth(f) = 1 + max(depth(callee) for callee in f.callees) 
        
        # 初始化深度
        depths = {}
        for formula_id in self.formulas:
            depths[formula_id] = 0
        
        # 计算入度（被多少函数调用不重要，重要的是调用了多少函数）
        # 使用拓扑排序：先处理叶子节点，再逐层向上
        
        # 检测循环依赖，使用DFS + memo
        computing = set()
        computed = set()
        
        def compute_depth(fid):
            """递归计算深度，处理循环引用"""
            if fid in computed:
                return depths[fid]
            if fid in computing:
                # 循环依赖，返回0避免无限递归
                return 0
            
            computing.add(fid)
            
            callees = self.call_graph.edges.get(fid, set())
            if not callees:
                depths[fid] = 0
            else:
                max_callee_depth = 0
                for callee_id in callees:
                    if callee_id in self.formulas:
                        d = compute_depth(callee_id)
                        max_callee_depth = max(max_callee_depth, d)
                depths[fid] = 1 + max_callee_depth
            
            computing.discard(fid)
            computed.add(fid)
            return depths[fid]
        
        for formula_id in self.formulas:
            compute_depth(formula_id)
        
        # 统计
        max_depth = max(depths.values()) if depths else 0
        leaves = sum(1 for d in depths.values() if d == 0)
        non_zero = sum(1 for d in depths.values() if d > 0)
        
        print(f"  叶子节点(depth=0): {leaves}")
        print(f"  非叶子节点(depth>0): {non_zero}")
        
        # 更新formulas
        for formula_id, depth in depths.items():
            self.formulas[formula_id]['call_depth'] = depth
        
        # 保存到数据库
        self._save_call_depths()
        
        print(f"[OK] 计算完成，深度范围: 0 - {max_depth}")
    
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
        if self.formulas:
            max_stats = max(len(f['total_stats']) for f in self.formulas.values())
            avg_stats = sum(len(f['total_stats']) for f in self.formulas.values()) / len(self.formulas)
        else:
            max_stats = 0
            avg_stats = 0
        
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
