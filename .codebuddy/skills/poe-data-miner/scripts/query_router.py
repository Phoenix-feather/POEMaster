#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
查询路由器 - 自动分析问题类型并推荐查询方法

用途：在处理用户问题前，先用此工具分析问题类型，确定查询策略
"""
import re
from typing import Dict, List, Tuple
from dataclasses import dataclass
from enum import Enum


class QueryType(Enum):
    """查询类型"""
    ATTRIBUTE = "attribute"      # 属性查询 - 数据查询
    RULE = "rule"                # 规则查询 - 数据查询
    RELATION = "relation"        # 关系查询 - 关联图
    BYPASS = "bypass"            # 绕过查询 - 关联图优先
    COMPREHENSIVE = "comprehensive"  # 综合分析 - 混合查询


@dataclass
class QueryRecommendation:
    """查询推荐"""
    query_type: QueryType
    use_data_query: bool
    use_graph_query: bool
    priority: str  # "data", "graph", "mixed"
    reasoning: str
    checklist: List[str]


def analyze_question(question: str) -> QueryRecommendation:
    """
    分析问题类型并推荐查询方法
    
    Args:
        question: 用户问题
        
    Returns:
        QueryRecommendation: 查询推荐
    """
    # 问题关键词分析
    question_lower = question.lower()
    
    # 三问法判断
    is_what_question = _is_what_question(question_lower)
    is_how_question = _is_how_question(question_lower)
    is_bypass_question = _is_bypass_question(question_lower)
    is_relation_question = _is_relation_question(question_lower)
    
    # 综合判断
    if is_bypass_question:
        return _create_bypass_recommendation(question)
    elif is_relation_question or is_how_question:
        return _create_relation_recommendation(question)
    elif is_what_question:
        return _create_attribute_recommendation(question)
    else:
        return _create_comprehensive_recommendation(question)


def _is_what_question(question: str) -> bool:
    """判断是否为"是什么"问题"""
    patterns = [
        r'是什么',
        r'有多少',
        r'有哪些',
        r'是什么$',
        r'的属性',
        r'的数值',
        r'的公式',
        r'的定义',
        r'查询',
        r'获取',
        r'how much',
        r'what is',
        r'what are'
    ]
    return any(re.search(p, question) for p in patterns)


def _is_how_question(question: str) -> bool:
    """判断是否为"如何"问题"""
    patterns = [
        r'如何',
        r'怎么',
        r'怎样',
        r'如何实现',
        r'how to',
        r'how does',
        r'how can'
    ]
    return any(re.search(p, question) for p in patterns)


def _is_bypass_question(question: str) -> bool:
    """判断是否为绕过问题"""
    patterns = [
        r'绕过',
        r'规避',
        r'跳过',
        r'例外',
        r'异常',
        r'特例',
        r'是否有办法',
        r'能否',
        r'可以.*吗',
        r'bypass',
        r'workaround',
        r'exception'
    ]
    return any(re.search(p, question) for p in patterns)


def _is_relation_question(question: str) -> bool:
    """判断是否为关系问题"""
    patterns = [
        r'影响',
        r'关系',
        r'连接',
        r'关联',
        r'相互作用',
        r'依赖',
        r'导致',
        r'引起',
        r'affect',
        r'relationship',
        r'connect',
        r'interact'
    ]
    return any(re.search(p, question) for p in patterns)


def _create_attribute_recommendation(question: str) -> QueryRecommendation:
    """创建属性查询推荐"""
    return QueryRecommendation(
        query_type=QueryType.ATTRIBUTE,
        use_data_query=True,
        use_graph_query=False,
        priority="data",
        reasoning="这是属性查询问题，需要精确的数据值",
        checklist=[
            "✅ 查询entities.db获取实体属性",
            "✅ 查询rules.db获取规则定义",
            "✅ 查询formulas.db获取公式",
            "❌ 关联图查询（通常不需要）"
        ]
    )


def _create_relation_recommendation(question: str) -> QueryRecommendation:
    """创建关系查询推荐"""
    return QueryRecommendation(
        query_type=QueryType.RELATION,
        use_data_query=True,
        use_graph_query=True,
        priority="mixed",
        reasoning="这涉及实体之间的关系，需要关联图发现隐含关系",
        checklist=[
            "✅ 查询entities.db获取基础信息",
            "✅ 查询rules.db获取规则约束",
            "✅ 查询graph.db发现关系",
            "⚠️ 必须综合数据查询和图查询"
        ]
    )


def _create_bypass_recommendation(question: str) -> QueryRecommendation:
    """创建绕过查询推荐"""
    return QueryRecommendation(
        query_type=QueryType.BYPASS,
        use_data_query=True,
        use_graph_query=True,
        priority="graph",
        reasoning="⚠️ 绕过机制查询，必须优先使用关联图探索路径！",
        checklist=[
            "⚠️ 先查询graph.db探索绕过路径",
            "⚠️ 查找bypass/overrides/excludes类型的边",
            "✅ 查询rules.db确认约束规则",
            "✅ 查询entities.db确认实体属性",
            "⚠️ 必须验证绕过路径的有效性"
        ]
    )


def _create_comprehensive_recommendation(question: str) -> QueryRecommendation:
    """创建综合查询推荐"""
    return QueryRecommendation(
        query_type=QueryType.COMPREHENSIVE,
        use_data_query=True,
        use_graph_query=True,
        priority="mixed",
        reasoning="综合分析问题，需要同时使用数据查询和关联图",
        checklist=[
            "✅ 查询entities.db获取实体属性",
            "✅ 查询rules.db获取规则约束",
            "✅ 查询formulas.db获取公式",
            "✅ 查询graph.db发现隐含关系",
            "⚠️ 必须综合所有信息得出结论"
        ]
    )


def print_recommendation(rec: QueryRecommendation):
    """打印查询推荐"""
    print("=" * 60)
    print("查询策略分析")
    print("=" * 60)
    print(f"\n查询类型: {rec.query_type.value}")
    print(f"优先级: {rec.priority}")
    print(f"\n推理: {rec.reasoning}")
    print(f"\n检查清单:")
    for item in rec.checklist:
        print(f"  {item}")
    print("\n" + "=" * 60)


def main():
    """主函数"""
    import sys
    
    if len(sys.argv) < 2:
        print("用法: python query_router.py <用户问题>")
        print("\n示例:")
        print("  python query_router.py 'CoC的能量公式是什么？'")
        print("  python query_router.py '哪些技能会影响CoC的能量生成？'")
        print("  python query_router.py '如何绕过Triggerable限制？'")
        return
    
    question = " ".join(sys.argv[1:])
    print(f"\n用户问题: {question}\n")
    
    recommendation = analyze_question(question)
    print_recommendation(recommendation)
    
    # 提示下一步行动
    print("\n下一步行动:")
    if recommendation.priority == "data":
        print("  → 直接查询entities.db/rules.db/formulas.db")
    elif recommendation.priority == "graph":
        print("  → ⚠️ 必须先查询graph.db探索关系/绕过路径")
    else:  # mixed
        print("  → 先查询entities/rules/formulas获取基础信息")
        print("  → 再查询graph.db发现隐含关系")


if __name__ == "__main__":
    main()
