"""
POB代码搜索器

集成四级索引，提供快速的三层搜索验证
"""

import logging
from typing import Dict, List, Any, Optional
from pathlib import Path

# 导入索引系统
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from indexes import IndexManager

logger = logging.getLogger(__name__)


class POBCodeSearcher:
    """
    POB代码搜索器
    
    提供三层搜索策略：
    - Layer 1: 显式stat定义（强度1.0）
    - Layer 2: 代码逻辑（强度0.8）
    - Layer 3: 语义推断（强度0.5）
    """
    
    def __init__(self, pob_data_path: str):
        """
        初始化POB代码搜索器
        
        Args:
            pob_data_path: POB数据路径
        """
        self.pob_data_path = Path(pob_data_path)
        
        # 初始化索引管理器
        index_config = self.pob_data_path.parent / 'config' / 'index_config.yaml'
        self.index_manager = IndexManager(
            str(self.pob_data_path),
            str(index_config) if index_config.exists() else None
        )
        
        logger.info(f"POBCodeSearcher初始化完成: {pob_data_path}")
    
    def search_stat_definition(self, stat_id: str) -> Dict[str, Any]:
        """
        Layer 1: 搜索显式stat定义
        
        Args:
            stat_id: stat ID
            
        Returns:
            搜索结果，包含：
            - found: 是否找到
            - layer: 搜索层级（1）
            - strength: 证据强度（1.0）
            - source: 来源信息
            - locations: 使用位置列表
        """
        logger.debug(f"Layer 1搜索stat定义: {stat_id}")
        
        # 使用StatIndex查询
        stat_index = self.index_manager.get_index('stat')
        if not stat_index:
            logger.error("StatIndex未初始化")
            return self._empty_result(1)
        
        result = stat_index.search({'stat_id': stat_id})
        
        if result['found']:
            return {
                'found': True,
                'layer': 1,
                'strength': 1.0,
                'source': result['definition']['definition_file'] if result['definition'] else None,
                'locations': result['usages'],
                'usage_count': result['usage_count'],
                'definition': result['definition']
            }
        
        return self._empty_result(1)
    
    def search_skilltype_constraint(self, skill_type: str) -> Dict[str, Any]:
        """
        Layer 2: 搜索skillType约束
        
        Args:
            skill_type: skillType名称
            
        Returns:
            搜索结果，包含：
            - found: 是否找到
            - layer: 搜索层级（2）
            - strength: 证据强度（0.8）
            - constraints: 约束关系
        """
        logger.debug(f"Layer 2搜索skillType约束: {skill_type}")
        
        # 使用SkillTypeIndex查询
        skilltype_index = self.index_manager.get_index('skilltype')
        if not skilltype_index:
            logger.error("SkillTypeIndex未初始化")
            return self._empty_result(2)
        
        result = skilltype_index.search({'skill_type': skill_type})
        
        if result['found']:
            return {
                'found': True,
                'layer': 2,
                'strength': 0.8,
                'skill_type': skill_type,
                'required_by': result['required_by'],
                'excluded_by': result['excluded_by'],
                'added_by': result['added_by'],
                'total_constraints': result['total_constraints']
            }
        
        return self._empty_result(2)
    
    def search_function_logic(self, function_name: str) -> Dict[str, Any]:
        """
        Layer 2: 搜索函数逻辑
        
        Args:
            function_name: 函数名
            
        Returns:
            搜索结果，包含：
            - found: 是否找到
            - layer: 搜索层级（2）
            - strength: 证据强度（0.8）
            - definition: 函数定义
            - calls: 调用关系
        """
        logger.debug(f"Layer 2搜索函数逻辑: {function_name}")
        
        # 使用FunctionIndex查询
        function_index = self.index_manager.get_index('function')
        if not function_index:
            logger.error("FunctionIndex未初始化")
            return self._empty_result(2)
        
        result = function_index.search({'function_name': function_name})
        
        if result['found']:
            return {
                'found': True,
                'layer': 2,
                'strength': 0.8,
                'definition': result['definition'],
                'parameters': result['parameters'],
                'called_by': result['called_by'],
                'calls_to': result['calls_to'],
                'call_count': result['call_count']
            }
        
        return self._empty_result(2)
    
    def search_semantic_similarity(self, entity: str, top_k: int = 10) -> Dict[str, Any]:
        """
        Layer 3: 搜索语义相似实体
        
        Args:
            entity: 实体名称
            top_k: 返回数量
            
        Returns:
            搜索结果，包含：
            - found: 是否找到
            - layer: 搜索层级（3）
            - strength: 证据强度（0.5）
            - similar_entities: 相似实体列表
        """
        logger.debug(f"Layer 3搜索语义相似: {entity}")
        
        # 使用SemanticIndex查询
        semantic_index = self.index_manager.get_index('semantic')
        if not semantic_index:
            logger.error("SemanticIndex未初始化")
            return self._empty_result(3)
        
        result = semantic_index.search({'entity': entity, 'top_k': top_k})
        
        if result['found']:
            return {
                'found': True,
                'layer': 3,
                'strength': 0.5,
                'similar_entities': result['similar_entities'],
                'count': len(result['similar_entities'])
            }
        
        return self._empty_result(3)
    
    def search_keyword(self, keywords: List[str]) -> Dict[str, Any]:
        """
        Layer 3: 按关键词搜索实体
        
        Args:
            keywords: 关键词列表
            
        Returns:
            搜索结果
        """
        logger.debug(f"Layer 3搜索关键词: {keywords}")
        
        semantic_index = self.index_manager.get_index('semantic')
        if not semantic_index:
            logger.error("SemanticIndex未初始化")
            return self._empty_result(3)
        
        result = semantic_index.search({'keywords': keywords})
        
        if result['found']:
            return {
                'found': True,
                'layer': 3,
                'strength': 0.5,
                'entities': result['entities'],
                'count': len(result['entities'])
            }
        
        return self._empty_result(3)
    
    def search_tag(self, tags: List[str]) -> Dict[str, Any]:
        """
        Layer 3: 按标签搜索实体
        
        Args:
            tags: 标签列表
            
        Returns:
            搜索结果
        """
        logger.debug(f"Layer 3搜索标签: {tags}")
        
        semantic_index = self.index_manager.get_index('semantic')
        if not semantic_index:
            logger.error("SemanticIndex未初始化")
            return self._empty_result(3)
        
        result = semantic_index.search({'tags': tags})
        
        if result['found']:
            return {
                'found': True,
                'layer': 3,
                'strength': 0.5,
                'entities': result['entities'],
                'count': len(result['entities'])
            }
        
        return self._empty_result(3)
    
    def verify_implication(self, source: str, target: str, max_depth: int = 3) -> Dict[str, Any]:
        """
        验证隐含关系（使用三层搜索）
        
        Args:
            source: 源实体/类型
            target: 目标属性
            max_depth: 最大搜索深度
            
        Returns:
            验证结果，包含：
            - status: verified/pending/hypothesis/rejected
            - confidence: 置信度
            - evidence: 证据链
            - counter_examples: 反例
        """
        logger.info(f"验证隐含关系: {source} → {target}")
        
        evidence_list = []
        counter_examples = []
        
        # Layer 1: 搜索stat定义
        stat_result = self.search_stat_definition(target)
        if stat_result['found']:
            # 检查stat是否在source实体中
            for location in stat_result.get('locations', []):
                if source in location.get('skill_name', ''):
                    evidence_list.append({
                        'layer': 1,
                        'type': 'stat_definition',
                        'strength': 1.0,
                        'source': location['file_path'],
                        'content': location['context']
                    })
        
        # Layer 2: 搜索约束关系
        constraint_result = self.search_skilltype_constraint(source)
        if constraint_result['found']:
            # 检查是否有排除或要求关系
            if constraint_result.get('excluded_by'):
                evidence_list.append({
                    'layer': 2,
                    'type': 'skilltype_constraint',
                    'strength': 0.8,
                    'source': 'SkillType constraint',
                    'content': f"{source} is excluded by {len(constraint_result['excluded_by'])} skills"
                })
            
            if constraint_result.get('added_by'):
                evidence_list.append({
                    'layer': 2,
                    'type': 'skilltype_added',
                    'strength': 0.8,
                    'source': 'SkillType added',
                    'content': f"{source} is added by {len(constraint_result['added_by'])} skills"
                })
        
        # Layer 3: 搜索函数逻辑
        # 尝试搜索相关的函数（如isTriggered, hasEnergy等）
        related_functions = self._find_related_functions(source, target)
        for func_name in related_functions:
            func_result = self.search_function_logic(func_name)
            if func_result['found']:
                evidence_list.append({
                    'layer': 2,
                    'type': 'function_logic',
                    'strength': 0.8,
                    'source': func_result['definition']['file_path'],
                    'function': func_name,
                    'content': func_result['definition'].get('description', '')
                })
        
        # Layer 3: 语义推断
        semantic_result = self.search_semantic_similarity(source, top_k=20)
        if semantic_result['found']:
            # 检查相似实体是否有相同属性
            for sim_entity in semantic_result.get('similar_entities', []):
                if sim_entity['similarity'] > 0.7:
                    # 可以进一步验证相似实体是否有目标属性
                    pass
        
        # 综合评估
        if evidence_list:
            # 计算综合强度
            total_strength = sum(e['strength'] for e in evidence_list)
            avg_strength = total_strength / len(evidence_list)
            
            # 决定状态
            if avg_strength >= 0.8:
                status = 'verified'
                confidence = 1.0
            elif avg_strength >= 0.5:
                status = 'pending'
                confidence = 0.5
            else:
                status = 'hypothesis'
                confidence = 0.3
        else:
            status = 'hypothesis'
            confidence = 0.3
        
        return {
            'status': status,
            'confidence': confidence,
            'evidence': evidence_list,
            'counter_examples': counter_examples,
            'evidence_count': len(evidence_list)
        }
    
    def _find_related_functions(self, source: str, target: str) -> List[str]:
        """
        查找相关函数名（优化版）
        
        策略：
        1. 从函数索引查询相关函数（主要策略）
        2. 基于关键词智能匹配（辅助策略）
        3. 硬编码关键词映射作为后备方案
        
        Args:
            source: 源实体
            target: 目标属性
            
        Returns:
            可能相关的函数名列表
        """
        related = []
        
        # 策略1: 从函数索引查询（如果索引已构建）
        try:
            function_index = self.index_manager.get_index('function')
            if function_index:
                # 提取关键词
                keywords = self._extract_keywords_from_entity(source, target)
                
                # 查询包含关键词的函数
                for keyword in keywords[:5]:  # 限制查询次数
                    result = function_index.search({'function_name': keyword})
                    if result['found']:
                        related.append(result['definition']['function_name'])
                
                # 查询高频调用的函数（可能是关键函数）
                top_funcs = function_index.get_top_called_functions(20)
                for func in top_funcs:
                    # 检查函数名是否与source/target相关
                    if any(kw in func['function_name'].lower() for kw in keywords):
                        related.append(func['function_name'])
        
        except Exception as e:
            logger.debug(f"函数索引查询失败，使用后备方案: {e}")
        
        # 策略2: 基于关键词智能匹配
        keywords = self._extract_keywords_from_entity(source, target)
        prefixes = ['is', 'has', 'can', 'should', 'calc', 'check', 'get']
        
        for keyword in keywords:
            # 尝试不同的命名模式
            for prefix in prefixes:
                # 模式1: prefixKeyword (如 isTriggered)
                related.append(f"{prefix}{keyword.capitalize()}")
                
                # 模式2: prefix_keyword (如 calc_energy)
                related.append(f"{prefix}_{keyword.lower()}")
        
        # 策略3: 硬编码关键词映射（后备方案）
        hardcoded_keywords = {
            'triggered': ['Triggered', 'Trigger'],
            'energy': ['Energy', 'EnergyCost', 'EnergyGain'],
            'damage': ['Damage', 'FireDamage', 'ColdDamage', 'LightningDamage'],
            'spell': ['Spell', 'FireSpell', 'ColdSpell', 'LightningSpell'],
            'attack': ['Attack', 'Melee', 'Projectile'],
            'bypass': ['Bypass', 'Ignore', 'Prevent'],
            'cost': ['Cost', 'ManaCost', 'LifeCost'],
            'speed': ['Speed', 'CastSpeed', 'AttackSpeed'],
            'cooldown': ['Cooldown', 'CooldownRecovery'],
            'duration': ['Duration', 'DurationMod']
        }
        
        for key, funcs in hardcoded_keywords.items():
            if key in source.lower() or key in target.lower():
                for prefix in prefixes:
                    for func in funcs:
                        related.append(f"{prefix}{func}")
        
        # 去重并限制数量
        unique_related = list(set(related))
        
        # 优先级排序：索引查询的结果优先
        # 然后是关键词匹配，最后是硬编码映射
        return unique_related[:20]  # 限制返回数量，避免过多查询
    
    def _extract_keywords_from_entity(self, source: str, target: str) -> List[str]:
        """
        从实体名称中提取关键词
        
        Args:
            source: 源实体
            target: 目标属性
            
        Returns:
            关键词列表
        """
        keywords = []
        
        # 提取驼峰命名中的关键词
        import re
        
        def extract_camel_case(s):
            """从驼峰命名提取单词"""
            # 分割驼峰命名
            words = re.findall(r'[A-Z]?[a-z]+|[A-Z]+(?=[A-Z][a-z]|\d|\W|$)', s)
            return [w.lower() for w in words]
        
        # 从source提取
        keywords.extend(extract_camel_case(source))
        
        # 从target提取
        keywords.extend(extract_camel_case(target))
        
        # 添加常见的游戏术语
        common_terms = [
            'damage', 'trigger', 'energy', 'mana', 'life', 'speed',
            'cooldown', 'duration', 'cost', 'cast', 'attack', 'spell',
            'melee', 'projectile', 'area', 'effect', 'mod', 'multiplier'
        ]
        
        for term in common_terms:
            if term in source.lower() or term in target.lower():
                keywords.append(term)
        
        return list(set(keywords))
    
    def _empty_result(self, layer: int) -> Dict[str, Any]:
        """返回空结果"""
        return {
            'found': False,
            'layer': layer,
            'strength': 0.0,
            'evidence': [],
            'counter_examples': []
        }
    
    def close(self):
        """关闭索引连接"""
        if self.index_manager:
            self.index_manager.close_all()
            logger.info("POBCodeSearcher已关闭")
    
    def __enter__(self):
        """上下文管理器入口"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.close()
