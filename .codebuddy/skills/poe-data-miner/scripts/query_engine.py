#!/usr/bin/env python3
"""
POE问答引擎模块
链式索引 + 关联图发散检索，三源联动（实体+规则+关联图）
"""

import re
import json
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from entity_index import EntityIndex
from rules_extractor import RulesExtractor
from attribute_graph import AttributeGraph, NodeType, EdgeType


class QueryType(Enum):
    """查询类型"""
    ENTITY_ATTRIBUTE = "entity_attribute"      # 实体属性查询
    RULE_CALCULATION = "rule_calculation"      # 规则计算查询
    MECHANISM_RELATION = "mechanism_relation"  # 机制关联查询
    COMPREHENSIVE = "comprehensive"            # 综合查询
    EXPLORATION = "exploration"                # 探索查询


@dataclass
class QueryAnalysis:
    """问题分析结果"""
    original_question: str
    query_type: QueryType
    entities: List[str]
    intent: str
    constraints: List[str]
    keywords: List[str]


@dataclass
class QueryResult:
    """查询结果"""
    question: str
    answer: str
    sources: Dict[str, Any]
    confidence: float
    needs_confirmation: bool
    related_questions: List[str]


class QuestionAnalyzer:
    """问题分析器"""
    
    def __init__(self):
        """初始化分析器"""
        self.intent_patterns = {
            '绕过': ['绕过', '避开', '避免', 'bypass', '绕开'],
            '计算': ['计算', '多少', '怎么算', '公式', 'calculate'],
            '配合': ['配合', '联动', '组合', '搭配', '一起'],
            '限制': ['限制', '为什么不能', '为什么不', '无法', '限制'],
            '增加': ['增加', '提升', '提高', '加成', 'increase'],
            '减少': ['减少', '降低', '降低', 'decrease'],
            '查询': ['是什么', '有什么', '哪些', '什么'],
            '比较': ['比较', '区别', '差异', '哪个好']
        }
        
        self.entity_keywords = {
            '技能': ['技能', 'skill', 'gem'],
            '物品': ['物品', '装备', 'item', 'unique'],
            '天赋': ['天赋', 'passive', 'tree']
        }
    
    def analyze(self, question: str) -> QueryAnalysis:
        """
        分析问题
        
        Args:
            question: 用户问题
            
        Returns:
            分析结果
        """
        # 提取意图
        intent = self._extract_intent(question)
        
        # 提取实体
        entities = self._extract_entities(question)
        
        # 提取约束
        constraints = self._extract_constraints(question)
        
        # 提取关键词
        keywords = self._extract_keywords(question)
        
        # 确定查询类型
        query_type = self._determine_query_type(intent, entities, constraints)
        
        return QueryAnalysis(
            original_question=question,
            query_type=query_type,
            entities=entities,
            intent=intent,
            constraints=constraints,
            keywords=keywords
        )
    
    def _extract_intent(self, question: str) -> str:
        """提取意图"""
        question_lower = question.lower()
        
        for intent, patterns in self.intent_patterns.items():
            for pattern in patterns:
                if pattern.lower() in question_lower:
                    return intent
        
        return '查询'
    
    def _extract_entities(self, question: str) -> List[str]:
        """提取实体名称"""
        entities = []
        
        # 匹配引号内的内容
        quoted = re.findall(r'[""「」『』]([^""「」『』]+)[""「」『』]', question)
        entities.extend(quoted)
        
        # 匹配大写开头的词（可能是技能名）
        # 这里简化处理，实际需要更复杂的NLP
        
        # 匹配已知的技能名模式
        skill_patterns = [
            r'Cast on \w+',
            r'\w+ Aura',
            r'\w+ Strike',
            r'\w+ Slam'
        ]
        
        for pattern in skill_patterns:
            matches = re.findall(pattern, question)
            entities.extend(matches)
        
        return list(set(entities))
    
    def _extract_constraints(self, question: str) -> List[str]:
        """提取约束"""
        constraints = []
        
        constraint_keywords = ['限制', '无法', '不能', '不超过', '最多', '最少', '必须']
        
        for keyword in constraint_keywords:
            if keyword in question:
                # 提取约束相关的短语
                pattern = rf'{keyword}[^，。！？,\.!?]*'
                matches = re.findall(pattern, question)
                constraints.extend(matches)
        
        return constraints
    
    def _extract_keywords(self, question: str) -> List[str]:
        """提取关键词"""
        # 移除常见停用词
        stopwords = {'的', '是', '在', '有', '和', '与', '或', '吗', '呢', '啊'}
        
        # 分词（简单实现）
        words = re.findall(r'[\w]+', question)
        
        keywords = [w for w in words if w not in stopwords and len(w) > 1]
        
        return keywords
    
    def _determine_query_type(self, intent: str, entities: List[str], constraints: List[str]) -> QueryType:
        """确定查询类型"""
        if intent in ['绕过', '配合']:
            return QueryType.EXPLORATION
        
        if intent == '计算':
            return QueryType.RULE_CALCULATION
        
        if intent in ['限制', '比较']:
            return QueryType.MECHANISM_RELATION
        
        if entities and not constraints:
            return QueryType.ENTITY_ATTRIBUTE
        
        return QueryType.COMPREHENSIVE


class QueryEngine:
    """问答引擎"""
    
    def __init__(self, db_path: str, predefined_edges_path: str = None):
        """
        初始化问答引擎
        
        Args:
            db_path: SQLite数据库路径（知识库目录，如 knowledge_base/）
            predefined_edges_path: 预置边配置路径（v2中已废弃，保留参数兼容性）
        """
        self.db_path = db_path
        self.entity_index = EntityIndex(db_path)
        self.rules_extractor = RulesExtractor(db_path)
        # v2: AttributeGraph 现在是 GraphBuilder 的别名，查询模式只需要 graph.db 路径
        # predefined_edges_path 在 v2 中不再需要（异常存档由 GraphBuilder.build() 处理）
        graph_db_path = f"{db_path}/graph.db" if not db_path.endswith('.db') else db_path
        self.attribute_graph = AttributeGraph(graph_db_path)
        self.analyzer = QuestionAnalyzer()
    
    def query(self, question: str) -> QueryResult:
        """
        处理查询
        
        Args:
            question: 用户问题
            
        Returns:
            查询结果
        """
        # 分析问题
        analysis = self.analyzer.analyze(question)
        
        # 根据查询类型选择处理方式
        if analysis.query_type == QueryType.ENTITY_ATTRIBUTE:
            return self._query_entity_attribute(analysis)
        elif analysis.query_type == QueryType.RULE_CALCULATION:
            return self._query_rule_calculation(analysis)
        elif analysis.query_type == QueryType.MECHANISM_RELATION:
            return self._query_mechanism_relation(analysis)
        elif analysis.query_type == QueryType.EXPLORATION:
            return self._query_exploration(analysis)
        else:
            return self._query_comprehensive(analysis)
    
    def _query_entity_attribute(self, analysis: QueryAnalysis) -> QueryResult:
        """实体属性查询"""
        entities_data = []
        
        for entity_name in analysis.entities:
            entity = self.entity_index.get_entity_by_id(entity_name)
            if not entity:
                # 尝试搜索
                results = self.entity_index.search_entities(entity_name)
                if results:
                    entity = results[0]
            
            if entity:
                entities_data.append(entity)
        
        # 生成回答
        answer = self._format_entity_answer(entities_data, analysis)
        
        return QueryResult(
            question=analysis.original_question,
            answer=answer,
            sources={'entities': entities_data},
            confidence=0.9 if entities_data else 0.3,
            needs_confirmation=False,
            related_questions=self._generate_related_questions(analysis, entities_data)
        )
    
    def _query_rule_calculation(self, analysis: QueryAnalysis) -> QueryResult:
        """规则计算查询"""
        # 先获取实体
        entities_data = []
        for entity_name in analysis.entities:
            entity = self.entity_index.get_entity_by_id(entity_name)
            if entity:
                entities_data.append(entity)
        
        # 获取相关规则
        rules = []
        for entity in entities_data:
            entity_rules = self.rules_extractor.get_rules_for_entity(entity.get('id', ''))
            rules.extend(entity_rules)
        
        # 搜索公式类规则
        formula_rules = self.rules_extractor.get_rules_by_category('formula')
        
        # 生成回答
        answer = self._format_calculation_answer(entities_data, rules, formula_rules, analysis)
        
        return QueryResult(
            question=analysis.original_question,
            answer=answer,
            sources={'entities': entities_data, 'rules': rules},
            confidence=0.85,
            needs_confirmation=False,
            related_questions=[]
        )
    
    def _query_mechanism_relation(self, analysis: QueryAnalysis) -> QueryResult:
        """机制关联查询"""
        # 在关联图中搜索
        graph_data = []
        
        for keyword in analysis.keywords:
            nodes = self.attribute_graph.search_nodes(keyword)
            for node in nodes:
                # v2: 使用 node_id 而非 id
                node_id = node.get('node_id') or node.get('id')
                neighbors = self.attribute_graph.get_neighbors(node_id)
                graph_data.append({
                    'node': node,
                    'neighbors': neighbors
                })
        
        # 生成回答
        answer = self._format_mechanism_answer(graph_data, analysis)
        
        return QueryResult(
            question=analysis.original_question,
            answer=answer,
            sources={'graph': graph_data},
            confidence=0.8,
            needs_confirmation=False,
            related_questions=[]
        )
    
    def _query_exploration(self, analysis: QueryAnalysis) -> QueryResult:
        """探索查询（发散式）"""
        discoveries = []
        needs_confirmation = False
        
        # 获取实体
        entities_data = []
        for entity_name in analysis.entities:
            entity = self.entity_index.get_entity_by_id(entity_name)
            if entity:
                entities_data.append(entity)
        
        # 分析意图
        if analysis.intent == '绕过':
            # 查找限制相关的节点
            constraint_nodes = self.attribute_graph.get_nodes_by_type(NodeType.CONSTRAINT)
            
            for constraint in constraint_nodes:
                # v2: 使用 node_id 而非 id
                constraint_id = constraint.get('node_id') or constraint.get('id')
                # 查找绕过路径
                bypass_paths = self.attribute_graph.find_bypass_paths(constraint_id)
                
                if bypass_paths:
                    for bp in bypass_paths:
                        discoveries.append({
                            'type': 'bypass',
                            'constraint': constraint.get('name', ''),
                            'method': bp['bypass_source'],
                            'confirmed': bp.get('confirmed', False)
                        })
                        if not bp.get('confirmed', False):
                            needs_confirmation = True
        
        # 生成回答
        answer = self._format_exploration_answer(entities_data, discoveries, analysis)
        
        return QueryResult(
            question=analysis.original_question,
            answer=answer,
            sources={'entities': entities_data, 'discoveries': discoveries},
            confidence=0.7 if needs_confirmation else 0.9,
            needs_confirmation=needs_confirmation,
            related_questions=[]
        )
    
    def _query_comprehensive(self, analysis: QueryAnalysis) -> QueryResult:
        """综合查询"""
        # 结合所有数据源
        entities_data = []
        rules = []
        graph_data = []
        
        # 获取实体
        for entity_name in analysis.entities:
            entity = self.entity_index.get_entity_by_id(entity_name)
            if entity:
                entities_data.append(entity)
                # 获取相关规则
                entity_rules = self.rules_extractor.get_rules_for_entity(entity.get('id', ''))
                rules.extend(entity_rules)
        
        # 搜索关联图
        for keyword in analysis.keywords:
            nodes = self.attribute_graph.search_nodes(keyword)
            for node in nodes[:5]:  # 限制数量
                # v2: 使用 node_id 而非 id
                node_id = node.get('node_id') or node.get('id')
                neighbors = self.attribute_graph.get_neighbors(node_id)
                graph_data.append({
                    'node': node,
                    'neighbors': neighbors
                })
        
        # 生成回答
        answer = self._format_comprehensive_answer(entities_data, rules, graph_data, analysis)
        
        return QueryResult(
            question=analysis.original_question,
            answer=answer,
            sources={'entities': entities_data, 'rules': rules, 'graph': graph_data},
            confidence=0.75,
            needs_confirmation=False,
            related_questions=[]
        )
    
    def _format_entity_answer(self, entities: List[Dict], analysis: QueryAnalysis) -> str:
        """格式化实体回答"""
        if not entities:
            return "未找到相关实体信息。"
        
        lines = []
        for entity in entities:
            lines.append(f"## {entity.get('name', entity.get('id', '未知'))}")
            
            # 技能类型
            skill_types = entity.get('skill_types', [])
            if skill_types:
                lines.append(f"**技能类型**: {', '.join(skill_types)}")
            
            # 属性
            stats = entity.get('stats', [])
            if stats:
                lines.append(f"**属性**: {', '.join(stats[:5])}")  # 限制显示数量
            
            # 常量属性
            constant_stats = entity.get('constant_stats', [])
            if constant_stats:
                lines.append("**基础属性**:")
                for stat in constant_stats[:3]:
                    if isinstance(stat, (list, tuple)) and len(stat) >= 2:
                        lines.append(f"  - {stat[0]}: {stat[1]}")
            
            lines.append("")
        
        return '\n'.join(lines)
    
    def _format_calculation_answer(self, entities: List[Dict], rules: List[Dict], 
                                   formulas: List[Dict], analysis: QueryAnalysis) -> str:
        """格式化计算回答"""
        lines = []
        
        # 实体信息
        if entities:
            lines.append("## 相关实体")
            for entity in entities:
                lines.append(f"- {entity.get('name', entity.get('id', ''))}")
            lines.append("")
        
        # 公式
        if formulas:
            lines.append("## 计算公式")
            for formula in formulas:
                lines.append(f"- {formula.get('name', '公式')}: {formula.get('formula', '')}")
            lines.append("")
        
        # 相关规则
        if rules:
            lines.append("## 相关规则")
            for rule in rules[:5]:
                lines.append(f"- {rule.get('name', '')}")
                if rule.get('description'):
                    lines.append(f"  {rule.get('description')}")
        
        return '\n'.join(lines)
    
    def _format_mechanism_answer(self, graph_data: List[Dict], analysis: QueryAnalysis) -> str:
        """格式化机制回答"""
        if not graph_data:
            return "未找到相关机制信息。"
        
        lines = ["## 机制关联"]
        
        for data in graph_data:
            node = data['node']
            neighbors = data['neighbors']
            
            lines.append(f"\n### {node['name']}")
            
            for neighbor in neighbors:
                edge_type = neighbor.get('edge_type', 'related')
                lines.append(f"- [{edge_type}] → {neighbor.get('name', neighbor.get('id', ''))}")
        
        return '\n'.join(lines)
    
    def _format_exploration_answer(self, entities: List[Dict], discoveries: List[Dict], 
                                   analysis: QueryAnalysis) -> str:
        """格式化探索回答"""
        lines = []
        
        if analysis.intent == '绕过':
            lines.append("## 绕过路径探索")
            
            if discoveries:
                for d in discoveries:
                    status = "✓ 已验证" if d['confirmed'] else "? 待确认"
                    lines.append(f"\n### {d['method']} {status}")
                    lines.append(f"- **限制**: {d['constraint']}")
                    lines.append(f"- **方法**: {d['method']}")
            else:
                lines.append("未找到已知的绕过方法。")
                lines.append("建议：探索其他可能的机制组合。")
        else:
            lines.append("## 探索结果")
            
            if entities:
                lines.append("\n### 相关实体")
                for entity in entities:
                    lines.append(f"- {entity.get('name', entity.get('id', ''))}")
            
            if discoveries:
                lines.append("\n### 发现")
                for d in discoveries:
                    lines.append(f"- {d}")
        
        return '\n'.join(lines)
    
    def _format_comprehensive_answer(self, entities: List[Dict], rules: List[Dict], 
                                     graph_data: List[Dict], analysis: QueryAnalysis) -> str:
        """格式化综合回答"""
        lines = [f"## 查询结果: {analysis.original_question}"]
        
        if entities:
            lines.append("\n### 相关实体")
            for entity in entities:
                lines.append(f"- {entity.get('name', entity.get('id', ''))}")
        
        if rules:
            lines.append("\n### 相关规则")
            for rule in rules[:5]:
                lines.append(f"- {rule.get('name', '')}")
        
        if graph_data:
            lines.append("\n### 关联关系")
            for data in graph_data[:3]:
                node = data['node']
                lines.append(f"- {node['name']}")
        
        return '\n'.join(lines)
    
    def _generate_related_questions(self, analysis: QueryAnalysis, entities: List[Dict]) -> List[str]:
        """生成相关问题"""
        questions = []
        
        for entity in entities:
            name = entity.get('name', '')
            skill_types = entity.get('skill_types', [])
            
            if 'Meta' in skill_types:
                questions.append(f"{name}的能量如何计算？")
            
            if 'GeneratesEnergy' in skill_types:
                questions.append(f"如何增加{name}的能量获取？")
        
        return questions[:3]
    
    def close(self):
        """关闭资源"""
        self.entity_index.close()
        self.rules_extractor.close()
        self.attribute_graph.close()


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='POE问答引擎')
    parser.add_argument('db_path', help='SQLite数据库路径')
    parser.add_argument('--question', '-q', help='问题')
    parser.add_argument('--predefined', help='预置边配置文件路径')
    
    args = parser.parse_args()
    
    engine = QueryEngine(args.db_path, args.predefined)
    
    try:
        if args.question:
            result = engine.query(args.question)
            print(result.answer)
            
            if result.needs_confirmation:
                print("\n--- 此回答需要您的确认 ---")
        else:
            # 交互模式
            print("POE问答引擎 (输入 'quit' 退出)")
            while True:
                question = input("\n问题: ").strip()
                if question.lower() in ['quit', 'exit', 'q']:
                    break
                
                if question:
                    result = engine.query(question)
                    print("\n" + result.answer)
    finally:
        engine.close()


if __name__ == '__main__':
    main()
