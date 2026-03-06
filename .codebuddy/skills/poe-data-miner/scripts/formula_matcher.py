#!/usr/bin/env python3
"""
公式匹配器 - 实现公式和实体的特征匹配

核心功能：
1. 从实体提取特征
2. 从公式提取特征
3. 计算匹配分数
4. 返回匹配结果
"""

import sqlite3
import json
from pathlib import Path
from typing import Dict, List, Set, Tuple
from dataclasses import dataclass


@dataclass
class Match:
    """匹配结果"""
    formula_id: str
    formula_name: str
    score: float
    details: Dict


class FormulaMatcher:
    """公式匹配器"""
    
    def __init__(self, formulas_db_path: str, entities_db_path: str):
        """
        初始化公式匹配器
        
        Args:
            formulas_db_path: 公式库数据库路径
            entities_db_path: 实体库数据库路径
        """
        self.formulas_db_path = Path(formulas_db_path)
        self.entities_db_path = Path(entities_db_path)
        
        # 加载公式特征
        self.formulas: Dict[str, Dict] = {}
        self._load_formulas()
        
        print(f"[初始化] 公式匹配器")
        print(f"  公式库: {self.formulas_db_path}")
        print(f"  实体库: {self.entities_db_path}")
        print(f"  加载公式: {len(self.formulas)} 个")
    
    def _load_formulas(self):
        """加载所有公式的特征"""
        conn = sqlite3.connect(str(self.formulas_db_path))
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, name, exact_stats, fuzzy_stats, inferred_tags
            FROM formulas
        """)
        
        for row in cursor.fetchall():
            formula_id = row[0]
            self.formulas[formula_id] = {
                'id': formula_id,
                'name': row[1],
                'exact_stats': set(json.loads(row[2])) if row[2] else set(),
                'fuzzy_stats': set(json.loads(row[3])) if row[3] else set(),
                'inferred_tags': set(json.loads(row[4])) if row[4] else set()
            }
        
        conn.close()
    
    def extract_entity_features(self, entity_id: str) -> Dict[str, Set[str]]:
        """
        从实体提取特征
        
        Args:
            entity_id: 实体ID
            
        Returns:
            {
                'exact_stats': Set[str],
                'fuzzy_stats': Set[str],
                'tags': Set[str]
            }
        """
        conn = sqlite3.connect(str(self.entities_db_path))
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT name, type, skill_types, data_json
            FROM entities
            WHERE id = ? OR name = ?
        """, (entity_id, entity_id))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return {
                'exact_stats': set(),
                'fuzzy_stats': set(),
                'tags': set()
            }
        
        name, entity_type, skill_types, data_json = row
        
        # 解析data_json
        data = json.loads(data_json) if data_json else {}
        
        # 提取特征
        features = {
            'exact_stats': set(),
            'fuzzy_stats': set(),
            'tags': set()
        }
        
        # 1. 从stats字段提取精确stat
        if 'stats' in data and data['stats']:
            features['exact_stats'].update(data['stats'])
        
        # 2. 从skill_types字段提取标签
        if skill_types:
            tags = json.loads(skill_types) if isinstance(skill_types, str) else skill_types
            features['tags'].update(tags)
        
        # 3. 从skillData提取模糊特征
        if 'skillData' in data:
            skill_data = data['skillData']
            for key in skill_data.keys():
                # 驼峰转下划线
                import re
                stat_name = re.sub(r'(?<!^)(?=[A-Z])', '_', key).lower()
                features['fuzzy_stats'].add(stat_name)
        
        return features
    
    def find_matching_formulas(self, entity_id: str, threshold: float = 0.3) -> List[Match]:
        """
        查找匹配的公式
        
        Args:
            entity_id: 实体ID
            threshold: 匹配阈值
            
        Returns:
            排序后的匹配结果列表
        """
        # 1. 提取实体特征
        entity_features = self.extract_entity_features(entity_id)
        
        # 2. 遍历所有公式计算匹配分数
        matches = []
        
        for formula_id, formula in self.formulas.items():
            score, details = self._calculate_match_score(formula, entity_features)
            
            if score >= threshold:
                match = Match(
                    formula_id=formula_id,
                    formula_name=formula['name'],
                    score=score,
                    details=details
                )
                matches.append(match)
        
        # 3. 排序
        matches.sort(key=lambda x: x.score, reverse=True)
        
        return matches
    
    def _calculate_match_score(
        self,
        formula_features: Dict[str, Set[str]],
        entity_features: Dict[str, Set[str]]
    ) -> Tuple[float, Dict]:
        """
        计算匹配分数
        
        Returns:
            (总分, 详细信息)
        """
        # 1. 精确匹配（官方stat ID）
        exact_overlap = len(
            formula_features['exact_stats'] & entity_features['exact_stats']
        )
        exact_union = len(
            formula_features['exact_stats'] | entity_features['exact_stats']
        )
        exact_score = exact_overlap / max(exact_union, 1)
        
        # 2. 模糊匹配（简化名称）
        fuzzy_overlap = len(
            formula_features['fuzzy_stats'] & entity_features['fuzzy_stats']
        )
        fuzzy_union = len(
            formula_features['fuzzy_stats'] | entity_features['fuzzy_stats']
        )
        fuzzy_score = fuzzy_overlap / max(fuzzy_union, 1)
        
        # 3. 标签匹配
        tag_overlap = len(
            formula_features['inferred_tags'] & entity_features['tags']
        )
        tag_union = len(
            formula_features['inferred_tags'] | entity_features['tags']
        )
        tag_score = tag_overlap / max(tag_union, 1)
        
        # 4. 综合评分
        total_score = (
            exact_score * 0.5 +
            fuzzy_score * 0.3 +
            tag_score * 0.2
        )
        
        details = {
            'exact_score': exact_score,
            'exact_overlap': exact_overlap,
            'exact_total': len(formula_features['exact_stats']),
            'fuzzy_score': fuzzy_score,
            'fuzzy_overlap': fuzzy_overlap,
            'fuzzy_total': len(formula_features['fuzzy_stats']),
            'tag_score': tag_score,
            'tag_overlap': tag_overlap,
            'tag_total': len(formula_features['inferred_tags']),
            'entity_stats': len(entity_features['exact_stats']),
            'entity_tags': len(entity_features['tags'])
        }
        
        return total_score, details
    
    def find_formulas_by_stat(self, stat_id: str) -> List[Match]:
        """
        查找使用指定stat的所有公式
        
        Args:
            stat_id: stat ID
            
        Returns:
            匹配的公式列表
        """
        conn = sqlite3.connect(str(self.formulas_db_path))
        cursor = conn.cursor()
        
        # 查询formula_stats表
        cursor.execute("""
            SELECT formula_id, confidence
            FROM formula_stats
            WHERE stat_id = ?
        """, (stat_id,))
        
        matches = []
        for row in cursor.fetchall():
            formula_id = row[0]
            confidence = row[1]
            
            if formula_id in self.formulas:
                match = Match(
                    formula_id=formula_id,
                    formula_name=self.formulas[formula_id]['name'],
                    score=confidence,
                    details={'stat_id': stat_id}
                )
                matches.append(match)
        
        conn.close()
        
        matches.sort(key=lambda x: x.score, reverse=True)
        return matches
    
    def get_formula_call_chain(self, formula_id: str) -> Dict:
        """
        获取公式的调用链
        
        Args:
            formula_id: 公式ID
            
        Returns:
            {
                'formula': formula_info,
                'calls': [callee_info, ...],
                'called_by': [caller_info, ...]
            }
        """
        conn = sqlite3.connect(str(self.formulas_db_path))
        cursor = conn.cursor()
        
        # 获取公式信息
        cursor.execute("""
            SELECT id, name, call_depth, source_file
            FROM formulas
            WHERE id = ?
        """, (formula_id,))
        
        row = cursor.fetchone()
        if not row:
            return {}
        
        result = {
            'formula': {
                'id': row[0],
                'name': row[1],
                'depth': row[2],
                'source': row[3]
            },
            'calls': [],
            'called_by': []
        }
        
        # 获取调用的函数
        cursor.execute("""
            SELECT callee_id
            FROM formula_calls
            WHERE caller_id = ?
        """, (formula_id,))
        
        for call_row in cursor.fetchall():
            callee_id = call_row[0]
            if callee_id in self.formulas:
                result['calls'].append({
                    'id': callee_id,
                    'name': self.formulas[callee_id]['name']
                })
        
        # 获取被调用信息
        cursor.execute("""
            SELECT caller_id
            FROM formula_calls
            WHERE callee_id = ?
        """, (formula_id,))
        
        for call_row in cursor.fetchall():
            caller_id = call_row[0]
            if caller_id in self.formulas:
                result['called_by'].append({
                    'id': caller_id,
                    'name': self.formulas[caller_id]['name']
                })
        
        conn.close()
        
        return result


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='公式匹配器')
    parser.add_argument('--formulas-db', default='formulas.db', help='公式库数据库路径')
    parser.add_argument('--entities-db', default='entities.db', help='实体库数据库路径')
    parser.add_argument('--entity', help='查询实体相关的公式')
    parser.add_argument('--stat', help='查询使用指定stat的公式')
    parser.add_argument('--formula', help='查询公式的调用链')
    
    args = parser.parse_args()
    
    # 创建匹配器
    matcher = FormulaMatcher(
        formulas_db_path=args.formulas_db,
        entities_db_path=args.entities_db
    )
    
    if args.entity:
        # 查询实体相关的公式
        print(f"\n查询实体: {args.entity}")
        matches = matcher.find_matching_formulas(args.entity)
        
        print(f"\n找到 {len(matches)} 个匹配的公式：")
        for i, match in enumerate(matches[:10], 1):
            print(f"\n{i}. {match.formula_name} (分数: {match.score:.3f})")
            print(f"   精确匹配: {match.details['exact_overlap']}/{match.details['exact_total']}")
            print(f"   模糊匹配: {match.details['fuzzy_overlap']}/{match.details['fuzzy_total']}")
            print(f"   标签匹配: {match.details['tag_overlap']}/{match.details['tag_total']}")
    
    elif args.stat:
        # 查询使用指定stat的公式
        print(f"\n查询stat: {args.stat}")
        matches = matcher.find_formulas_by_stat(args.stat)
        
        print(f"\n找到 {len(matches)} 个使用此stat的公式：")
        for i, match in enumerate(matches[:10], 1):
            print(f"{i}. {match.formula_name} (置信度: {match.score:.2f})")
    
    elif args.formula:
        # 查询公式的调用链
        print(f"\n查询公式: {args.formula}")
        chain = matcher.get_formula_call_chain(args.formula)
        
        if chain:
            print(f"\n公式: {chain['formula']['name']}")
            print(f"深度: {chain['formula']['depth']}")
            print(f"源文件: {chain['formula']['source']}")
            
            if chain['calls']:
                print(f"\n调用的函数 ({len(chain['calls'])}个):")
                for call in chain['calls'][:10]:
                    print(f"  - {call['name']}")
            
            if chain['called_by']:
                print(f"\n被调用 ({len(chain['called_by'])}次):")
                for caller in chain['called_by'][:10]:
                    print(f"  - {caller['name']}")
    
    else:
        print("请指定查询参数：--entity, --stat, 或 --formula")


if __name__ == "__main__":
    main()
