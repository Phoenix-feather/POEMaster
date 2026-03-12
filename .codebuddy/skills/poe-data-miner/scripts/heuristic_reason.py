#!/usr/bin/env python3
"""
启发式推理统一接口
整合查询、发现、扩散三层能力
"""

import sqlite3
from typing import Dict, List, Any, Optional
from pathlib import Path

# 导入三层能力模块
try:
    from heuristic_query import HeuristicQuery
    from heuristic_discovery import HeuristicDiscovery
    from heuristic_diffuse import HeuristicDiffuse
    from heuristic_config_loader import get_config
except ImportError:
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from heuristic_query import HeuristicQuery
    from heuristic_discovery import HeuristicDiscovery
    from heuristic_diffuse import HeuristicDiffuse
    from heuristic_config_loader import get_config


class HeuristicReason:
    """启发式推理统一接口"""
    
    def __init__(self, graph_db_path: str):
        """
        初始化推理器
        
        Args:
            graph_db_path: 关联图数据库路径
        """
        self.graph_db_path = graph_db_path
        self.query = HeuristicQuery(graph_db_path)
        self.discovery = HeuristicDiscovery(graph_db_path)
        self.diffuse = HeuristicDiffuse(graph_db_path)
        
        # 加载配置
        self.default_threshold = get_config('defaults.similarity_threshold', 0.7)
        self.max_diffuse_results = get_config('defaults.max_diffuse_results', 10)
        
        # 结果缓存
        self._cache: Dict[str, Any] = {}
    
    def close(self):
        """关闭连接"""
        self.query.close()
        self.discovery.close()
        self.diffuse.close()
    
    # ========== 核心统一接口 ==========
    
    def query_bypass(self, constraint: str, mode: str = 'auto', 
                     include_hypothesis: bool = True,
                     similarity_threshold: float = None,
                     max_diffuse_results: int = None) -> Dict[str, Any]:
        """
        查询绕过路径（三层能力统一接口）
        
        Args:
            constraint: 约束节点 ID
            mode: 模式选择
                - 'query': 只查询已知边
                - 'discover': 从零推理发现新边
                - 'diffuse': 从已知边扩散
                - 'auto': 自动选择（有已知边→扩散，无已知边→发现）
            include_hypothesis: 是否包含假设边
            similarity_threshold: 扩散时的相似度阈值（None则使用配置）
            max_diffuse_results: 扩散时的最大结果数（None则使用配置）
            
        Returns:
            {
                'constraint': constraint,
                'mode': mode,
                'known_bypasses': [...],      # 已知绕过边
                'discovered_bypasses': [...], # 新发现的绕过边
                'diffused_bypasses': [...],   # 扩散发现的绕过边
                'reasoning_chain': [...]      # 推理链
            }
        """
        # 使用配置中的默认值（如果未提供参数）
        if similarity_threshold is None:
            similarity_threshold = self.default_threshold
        if max_diffuse_results is None:
            max_diffuse_results = self.max_diffuse_results
        
        result = {
            'constraint': constraint,
            'mode': mode,
            'known_bypasses': [],
            'discovered_bypasses': [],
            'diffused_bypasses': [],
            'reasoning_chain': []
        }
        
        if mode == 'query':
            # 第一层：只查询已知边
            result['known_bypasses'] = self.query.query_bypasses(
                constraint, include_hypothesis=include_hypothesis
            )
        
        elif mode == 'discover':
            # 第二层：从零推理
            result['discovered_bypasses'] = self.discovery.discover_bypass_paths(constraint)
            result['reasoning_chain'] = self.discovery.get_reasoning_chain()
        
        elif mode == 'diffuse':
            # 第三层：从已知扩散
            known = self.query.query_bypasses(constraint, include_hypothesis=False)
            result['known_bypasses'] = known
            
            if known:
                # 从已知边扩散
                for bypass in known:
                    diffused = self.diffuse.diffuse_from_bypass(
                        bypass, similarity_threshold=similarity_threshold
                    )
                    result['diffused_bypasses'].extend(diffused)
                
                # 去重
                result['diffused_bypasses'] = self._deduplicate_bypasses(
                    result['diffused_bypasses']
                )
                
                # 限制数量
                if len(result['diffused_bypasses']) > max_diffuse_results:
                    result['diffused_bypasses'] = result['diffused_bypasses'][:max_diffuse_results]
        
        else:  # auto
            # 自动组合三种能力
            # 1. 查询已知
            known = self.query.query_bypasses(constraint, include_hypothesis=include_hypothesis)
            result['known_bypasses'] = known
            
            if known:
                # 2. 从已知扩散
                for bypass in known:
                    diffused = self.diffuse.diffuse_from_bypass(
                        bypass, similarity_threshold=similarity_threshold
                    )
                    result['diffused_bypasses'].extend(diffused)
                
                # 去重并限制数量
                result['diffused_bypasses'] = self._deduplicate_bypasses(
                    result['diffused_bypasses']
                )
                
                if len(result['diffused_bypasses']) > max_diffuse_results:
                    result['diffused_bypasses'] = result['diffused_bypasses'][:max_diffuse_results]
                
                # 记录推理链
                result['reasoning_chain'] = [
                    {'step': 'query', 'description': f'查询已知绕过 {constraint} 的边'},
                    {'step': 'diffuse', 'description': f'从 {len(known)} 条已知边扩散发现 {len(result["diffused_bypasses"])} 条新边'}
                ]
            else:
                # 3. 从零发现
                discovered = self.discovery.discover_bypass_paths(constraint)
                result['discovered_bypasses'] = discovered
                result['reasoning_chain'] = self.discovery.get_reasoning_chain()
        
        # 汇总统计
        result['summary'] = {
            'known_count': len(result['known_bypasses']),
            'discovered_count': len(result['discovered_bypasses']),
            'diffused_count': len(result['diffused_bypasses']),
            'total_count': (
                len(result['known_bypasses']) + 
                len(result['discovered_bypasses']) + 
                len(result['diffused_bypasses'])
            )
        }
        
        return result
    
    # ========== 其他查询接口 ==========
    
    def query_constraint_causes(self, constraint: str, max_depth: int = 3) -> List[Dict[str, Any]]:
        """
        查询约束的成因
        
        Args:
            constraint: 约束节点ID
            max_depth: 最大追溯深度
            
        Returns:
            成因列表
        """
        return self.query.query_constraint_causes(constraint, max_depth=max_depth)
    
    def query_similar_entities(self, entity: str, threshold: float = 0.7,
                               exclude: List[str] = None) -> List[tuple]:
        """
        查询相似实体
        
        Args:
            entity: 实体ID
            threshold: 相似度阈值
            exclude: 排除的实体列表
            
        Returns:
            相似实体列表 [(entity_id, similarity), ...]
        """
        features = self.diffuse.extract_key_features(entity)
        return self.diffuse.find_similar_entities(features, exclude=exclude, threshold=threshold)
    
    def query_node_stats(self, node_id: str) -> Dict[str, Any]:
        """
        查询节点统计信息
        
        Args:
            node_id: 节点ID
            
        Returns:
            统计信息
        """
        return self.query.get_node_stats(node_id)
    
    # ========== 辅助方法 ==========
    
    def _deduplicate_bypasses(self, bypasses: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        去重绕过边
        
        Args:
            bypasses: 绕过边列表
            
        Returns:
            去重后的列表
        """
        seen = set()
        deduplicated = []
        
        for bypass in bypasses:
            source = bypass.get('source', '')
            target = bypass.get('target', '')
            key = f"{source}-->{target}"
            
            if key not in seen:
                seen.add(key)
                deduplicated.append(bypass)
        
        return deduplicated
    
    # ========== 高级接口 ==========
    
    def explain_bypass(self, entity: str, constraint: str) -> Dict[str, Any]:
        """
        解释为什么某个实体能绕过某个约束
        
        Args:
            entity: 实体ID
            constraint: 约束节点ID
            
        Returns:
            解释信息
        """
        # 提取实体特征
        features = self.diffuse.extract_key_features(entity)
        
        # 获取约束的关键因素
        key_factors = self.discovery.get_constraint_key_factors(constraint)
        
        # 收集证据
        evidence = self.discovery.gather_evidence(entity, constraint, key_factors)
        
        # 查找相似实体
        similar_entities = self.query_similar_entities(entity, threshold=0.5, exclude=[entity])
        
        return {
            'entity': entity,
            'constraint': constraint,
            'features': features,
            'key_factors': key_factors,
            'evidence': evidence,
            'similar_entities': similar_entities[:5]  # 只返回前5个
        }
    
    def suggest_bypasses(self, constraint: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        推荐绕过某个约束的最佳方案
        
        Args:
            constraint: 约束节点ID
            top_k: 返回前K个推荐
            
        Returns:
            推荐列表（按置信度排序）
        """
        # 使用 auto 模式查询
        result = self.query_bypass(constraint, mode='auto')
        
        # 合并所有绕过边
        all_bypasses = (
            result['known_bypasses'] + 
            result['discovered_bypasses'] + 
            result['diffused_bypasses']
        )
        
        # 按置信度排序
        def get_confidence(bypass):
            return bypass.get('confidence', bypass.get('weight', 1.0))
        
        all_bypasses.sort(key=get_confidence, reverse=True)
        
        # 返回前K个
        return all_bypasses[:top_k]


def main():
    """测试函数"""
    import argparse
    import json
    
    parser = argparse.ArgumentParser(description='启发式推理统一接口测试')
    parser.add_argument('graph_db', help='关联图数据库路径')
    parser.add_argument('--bypass', help='查询绕过某个约束')
    parser.add_argument('--mode', choices=['query', 'discover', 'diffuse', 'auto'],
                       default='auto', help='查询模式')
    parser.add_argument('--explain', nargs=2, metavar=('ENTITY', 'CONSTRAINT'),
                       help='解释为什么实体能绕过约束')
    parser.add_argument('--suggest', help='推荐绕过约束的方案')
    parser.add_argument('--top-k', type=int, default=5, help='返回前K个推荐')
    
    args = parser.parse_args()
    
    reason = HeuristicReason(args.graph_db)
    
    if args.bypass:
        print(f"查询绕过 {args.bypass} 的路径 (模式: {args.mode})...\n")
        
        result = reason.query_bypass(args.bypass, mode=args.mode)
        
        print("=" * 60)
        print("查询结果")
        print("=" * 60)
        
        if result['known_bypasses']:
            print(f"\n已知绕过边 ({result['summary']['known_count']} 条):")
            for bp in result['known_bypasses']:
                print(f"  - {bp['source']} --[bypasses]--> {bp['target']}")
                if 'evidence' in bp:
                    print(f"    证据: {bp['evidence']}")
        
        if result['discovered_bypasses']:
            print(f"\n发现的绕过边 ({result['summary']['discovered_count']} 条):")
            for bp in result['discovered_bypasses']:
                print(f"  - {bp['source']} --[bypasses]--> {bp['target']}")
                print(f"    置信度: {bp.get('confidence', 'N/A')}")
                print(f"    状态: {bp.get('status', 'N/A')}")
        
        if result['diffused_bypasses']:
            print(f"\n扩散发现的绕过边 ({result['summary']['diffused_count']} 条):")
            for bp in result['diffused_bypasses']:
                print(f"  - {bp['source']} --[bypasses]--> {bp['target']}")
                print(f"    相似度: {bp.get('similarity', 'N/A'):.2f}")
                print(f"    置信度: {bp.get('confidence', 'N/A'):.2f}")
        
        if result['reasoning_chain']:
            print("\n推理链:")
            for step in result['reasoning_chain']:
                print(f"  [{step['step']}] {step['description']}")
        
        print(f"\n总计: {result['summary']['total_count']} 条绕过边")
    
    if args.explain:
        entity, constraint = args.explain
        
        print(f"解释 {entity} 如何绕过 {constraint}...\n")
        
        explanation = reason.explain_bypass(entity, constraint)
        
        print("实体特征:")
        print(json.dumps(explanation['features'], indent=2, ensure_ascii=False))
        
        print(f"\n约束关键因素: {explanation['key_factors']}")
        
        print(f"\n证据:\n{explanation['evidence']}")
        
        if explanation['similar_entities']:
            print(f"\n相似实体:")
            for ent, sim in explanation['similar_entities']:
                print(f"  - {ent} (相似度: {sim:.2f})")
    
    if args.suggest:
        print(f"推荐绕过 {args.suggest} 的方案 (前{args.top_k}个)...\n")
        
        suggestions = reason.suggest_bypasses(args.suggest, top_k=args.top_k)
        
        for i, sug in enumerate(suggestions, 1):
            print(f"{i}. {sug['source']} --[bypasses]--> {sug['target']}")
            if 'confidence' in sug:
                print(f"   置信度: {sug['confidence']:.2f}")
            if 'similarity' in sug:
                print(f"   相似度: {sug['similarity']:.2f}")
            if 'evidence' in sug:
                print(f"   证据: {sug['evidence'][:100]}...")
    
    reason.close()


if __name__ == '__main__':
    main()
