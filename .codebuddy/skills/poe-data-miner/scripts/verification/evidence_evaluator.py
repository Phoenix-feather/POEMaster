"""
证据评估器

评估多个证据的综合强度，决定验证状态
"""

import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum

# 导入验证相关枚举
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from attribute_graph import VerificationStatus, EvidenceType

logger = logging.getLogger(__name__)


@dataclass
class Evidence:
    """证据数据结构"""
    type: str                  # 证据类型
    strength: float            # 证据强度 (0.0-1.0)
    source: str                # 证据来源
    content: str               # 证据内容
    layer: int = 0             # 搜索层级
    confidence: float = 1.0    # 可信度
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'type': self.type,
            'strength': self.strength,
            'source': self.source,
            'content': self.content,
            'layer': self.layer,
            'confidence': self.confidence
        }


class EvidenceEvaluator:
    """
    证据评估器
    
    职责：
    1. 评估多个证据的综合强度
    2. 检测证据冲突
    3. 决定验证状态（verified/pending/hypothesis/rejected）
    4. 提供验证建议
    """
    
    # 证据类型权重
    EVIDENCE_WEIGHTS = {
        EvidenceType.STAT.value: 0.4,                # Stat定义权重最高
        EvidenceType.DATA_EXTRACTION.value: 0.4,     # 数据提取权重最高
        EvidenceType.CODE.value: 0.3,                # 代码逻辑权重中等
        EvidenceType.PATTERN.value: 0.2,             # 模式匹配权重较低
        EvidenceType.ANALOGY.value: 0.1,             # 类比推理权重最低
        EvidenceType.USER_INPUT.value: 0.4           # 用户输入权重最高
    }
    
    # 验证阈值
    VERIFIED_THRESHOLD = 0.8       # 自动验证阈值
    PENDING_THRESHOLD = 0.5        # 待确认阈值
    HYPOTHESIS_THRESHOLD = 0.3     # 假设阈值
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化证据评估器
        
        Args:
            config: 配置字典，可覆盖默认权重和阈值
        """
        # 加载配置
        if config:
            self.weights = config.get('evidence_weights', self.EVIDENCE_WEIGHTS)
            self.verified_threshold = config.get('verified_threshold', self.VERIFIED_THRESHOLD)
            self.pending_threshold = config.get('pending_threshold', self.PENDING_THRESHOLD)
            self.hypothesis_threshold = config.get('hypothesis_threshold', self.HYPOTHESIS_THRESHOLD)
        else:
            self.weights = self.EVIDENCE_WEIGHTS
            self.verified_threshold = self.VERIFIED_THRESHOLD
            self.pending_threshold = self.PENDING_THRESHOLD
            self.hypothesis_threshold = self.HYPOTHESIS_THRESHOLD
        
        logger.info(f"EvidenceEvaluator初始化完成，验证阈值: {self.verified_threshold}")
    
    def evaluate(self, evidence_list: List[Evidence], counter_examples: Optional[List[Evidence]] = None) -> Dict[str, Any]:
        """
        评估证据列表
        
        Args:
            evidence_list: 证据列表
            counter_examples: 反例列表
            
        Returns:
            评估结果，包含：
            - status: 验证状态
            - confidence: 综合置信度
            - overall_strength: 综合证据强度
            - recommendation: 建议（accept/review/reject）
            - conflict_detected: 是否检测到冲突
            - conflict_details: 冲突详情
        """
        logger.debug(f"评估证据: {len(evidence_list)}个证据")
        
        if not evidence_list:
            return {
                'status': VerificationStatus.HYPOTHESIS.value,
                'confidence': 0.3,
                'overall_strength': 0.0,
                'recommendation': 'review',
                'conflict_detected': False,
                'conflict_details': None,
                'evidence_count': 0
            }
        
        # 1. 检测冲突
        conflict_result = self._detect_conflicts(evidence_list, counter_examples)
        
        # 2. 如果有反例，降低置信度
        if counter_examples and len(counter_examples) > 0:
            logger.warning(f"检测到 {len(counter_examples)} 个反例")
            return {
                'status': VerificationStatus.REJECTED.value,
                'confidence': 0.0,
                'overall_strength': 0.0,
                'recommendation': 'reject',
                'conflict_detected': True,
                'conflict_details': {
                    'type': 'counter_example',
                    'counter_examples': [e.to_dict() for e in counter_examples]
                },
                'evidence_count': len(evidence_list),
                'counter_example_count': len(counter_examples)
            }
        
        # 3. 计算综合证据强度
        overall_strength = self._calculate_overall_strength(evidence_list)
        
        # 4. 决定验证状态
        status, confidence = self._determine_status(overall_strength, conflict_result)
        
        # 5. 生成建议
        recommendation = self._generate_recommendation(status, overall_strength, conflict_result)
        
        result = {
            'status': status,
            'confidence': confidence,
            'overall_strength': overall_strength,
            'recommendation': recommendation,
            'conflict_detected': conflict_result['has_conflict'],
            'conflict_details': conflict_result.get('details'),
            'evidence_count': len(evidence_list),
            'evidence_breakdown': self._get_evidence_breakdown(evidence_list)
        }
        
        logger.info(f"评估结果: {status}, 强度: {overall_strength:.2f}, 置信度: {confidence:.2f}")
        
        return result
    
    def _calculate_overall_strength(self, evidence_list: List[Evidence]) -> float:
        """
        计算综合证据强度
        
        使用加权平均方法
        
        Args:
            evidence_list: 证据列表
            
        Returns:
            综合证据强度 (0.0-1.0)
        """
        if not evidence_list:
            return 0.0
        
        total_weighted_strength = 0.0
        total_weight = 0.0
        
        for evidence in evidence_list:
            # 获取证据类型的权重
            weight = self.weights.get(evidence.type, 0.1)
            
            # 考虑证据可信度
            effective_weight = weight * evidence.confidence
            
            # 加权强度
            total_weighted_strength += evidence.strength * effective_weight
            total_weight += effective_weight
        
        if total_weight == 0:
            return 0.0
        
        # 归一化
        overall_strength = total_weighted_strength / total_weight
        
        return overall_strength
    
    def _detect_conflicts(self, evidence_list: List[Evidence], counter_examples: Optional[List[Evidence]]) -> Dict[str, Any]:
        """
        检测证据冲突
        
        Args:
            evidence_list: 证据列表
            counter_examples: 反例列表
            
        Returns:
            冲突检测结果
        """
        # 如果有反例，直接返回冲突
        if counter_examples and len(counter_examples) > 0:
            return {
                'has_conflict': True,
                'type': 'counter_example',
                'details': {
                    'description': '存在反例证据',
                    'counter_examples': [e.to_dict() for e in counter_examples]
                }
            }
        
        # 检测证据强度冲突（强度差异过大）
        if len(evidence_list) >= 2:
            strengths = [e.strength for e in evidence_list]
            max_strength = max(strengths)
            min_strength = min(strengths)
            
            # 如果强度差异过大（>0.5），可能存在冲突
            if max_strength - min_strength > 0.5:
                # 检查是否是Layer 1证据与Layer 3证据的冲突
                layer1_evidence = [e for e in evidence_list if e.layer == 1]
                layer3_evidence = [e for e in evidence_list if e.layer == 3]
                
                if layer1_evidence and layer3_evidence:
                    # Layer 1证据优先级更高
                    return {
                        'has_conflict': False,  # 不算真正的冲突，Layer 1优先
                        'type': 'layer_priority',
                        'details': {
                            'description': 'Layer 1证据优先级高于Layer 3',
                            'layer1_count': len(layer1_evidence),
                            'layer3_count': len(layer3_evidence)
                        }
                    }
                
                # 其他情况标记为潜在冲突
                return {
                    'has_conflict': True,
                    'type': 'strength_divergence',
                    'details': {
                        'description': '证据强度差异过大',
                        'max_strength': max_strength,
                        'min_strength': min_strength,
                        'divergence': max_strength - min_strength
                    }
                }
        
        return {
            'has_conflict': False,
            'type': None,
            'details': None
        }
    
    def _determine_status(self, overall_strength: float, conflict_result: Dict[str, Any]) -> tuple:
        """
        决定验证状态
        
        Args:
            overall_strength: 综合证据强度
            conflict_result: 冲突检测结果
            
        Returns:
            (status, confidence) 元组
        """
        # 如果有冲突，降低置信度
        if conflict_result['has_conflict']:
            # 根据冲突类型调整
            conflict_type = conflict_result.get('type')
            
            if conflict_type == 'counter_example':
                return VerificationStatus.REJECTED.value, 0.0
            
            elif conflict_type == 'strength_divergence':
                # 强度分歧，降低一个级别
                if overall_strength >= self.verified_threshold:
                    return VerificationStatus.PENDING.value, 0.5
                elif overall_strength >= self.pending_threshold:
                    return VerificationStatus.HYPOTHESIS.value, 0.3
                else:
                    return VerificationStatus.HYPOTHESIS.value, 0.3
        
        # 无冲突，按阈值判断
        if overall_strength >= self.verified_threshold:
            return VerificationStatus.VERIFIED.value, 1.0
        
        elif overall_strength >= self.pending_threshold:
            return VerificationStatus.PENDING.value, 0.5
        
        elif overall_strength >= self.hypothesis_threshold:
            return VerificationStatus.HYPOTHESIS.value, 0.3
        
        else:
            return VerificationStatus.REJECTED.value, 0.0
    
    def _generate_recommendation(self, status: str, overall_strength: float, conflict_result: Dict[str, Any]) -> str:
        """
        生成建议
        
        Args:
            status: 验证状态
            overall_strength: 综合证据强度
            conflict_result: 冲突检测结果
            
        Returns:
            建议字符串（accept/review/reject）
        """
        if status == VerificationStatus.VERIFIED.value:
            return 'accept'
        
        elif status == VerificationStatus.REJECTED.value:
            return 'reject'
        
        elif status == VerificationStatus.PENDING.value:
            if conflict_result['has_conflict']:
                return 'review'  # 需要人工审查冲突
            else:
                # 根据强度判断是否可以自动接受
                if overall_strength >= 0.7:
                    return 'accept_with_caution'
                else:
                    return 'review'
        
        else:  # hypothesis
            return 'review'
    
    def _get_evidence_breakdown(self, evidence_list: List[Evidence]) -> Dict[str, Any]:
        """
        获取证据分解统计
        
        Args:
            evidence_list: 证据列表
            
        Returns:
            证据分解统计
        """
        breakdown = {
            'total_count': len(evidence_list),
            'by_type': {},
            'by_layer': {},
            'average_strength': 0.0,
            'max_strength': 0.0,
            'min_strength': 1.0
        }
        
        if not evidence_list:
            return breakdown
        
        strengths = []
        
        for evidence in evidence_list:
            # 按类型统计
            if evidence.type not in breakdown['by_type']:
                breakdown['by_type'][evidence.type] = 0
            breakdown['by_type'][evidence.type] += 1
            
            # 按层级统计
            layer_key = f"layer_{evidence.layer}"
            if layer_key not in breakdown['by_layer']:
                breakdown['by_layer'][layer_key] = 0
            breakdown['by_layer'][layer_key] += 1
            
            # 强度统计
            strengths.append(evidence.strength)
        
        breakdown['average_strength'] = sum(strengths) / len(strengths)
        breakdown['max_strength'] = max(strengths)
        breakdown['min_strength'] = min(strengths)
        
        return breakdown
    
    def evaluate_single_evidence(self, evidence: Evidence) -> Dict[str, Any]:
        """
        评估单个证据
        
        Args:
            evidence: 单个证据
            
        Returns:
            评估结果
        """
        # 获取证据类型权重
        weight = self.weights.get(evidence.type, 0.1)
        
        # 有效强度 = 强度 × 权重 × 可信度
        effective_strength = evidence.strength * weight * evidence.confidence
        
        # 决定状态
        if effective_strength >= self.verified_threshold:
            status = VerificationStatus.VERIFIED.value
            confidence = 1.0
            recommendation = 'accept'
        elif effective_strength >= self.pending_threshold:
            status = VerificationStatus.PENDING.value
            confidence = 0.5
            recommendation = 'review'
        elif effective_strength >= self.hypothesis_threshold:
            status = VerificationStatus.HYPOTHESIS.value
            confidence = 0.3
            recommendation = 'review'
        else:
            status = VerificationStatus.REJECTED.value
            confidence = 0.0
            recommendation = 'reject'
        
        return {
            'status': status,
            'confidence': confidence,
            'effective_strength': effective_strength,
            'raw_strength': evidence.strength,
            'weight': weight,
            'recommendation': recommendation,
            'evidence': evidence.to_dict()
        }
    
    def get_strength_requirement(self, target_status: str) -> float:
        """
        获取达到目标状态所需的证据强度
        
        Args:
            target_status: 目标验证状态
            
        Returns:
            所需的最小证据强度
        """
        if target_status == VerificationStatus.VERIFIED.value:
            return self.verified_threshold
        elif target_status == VerificationStatus.PENDING.value:
            return self.pending_threshold
        elif target_status == VerificationStatus.HYPOTHESIS.value:
            return self.hypothesis_threshold
        else:
            return 0.0
    
    def suggest_additional_evidence(self, current_strength: float, target_status: str) -> Dict[str, Any]:
        """
        建议需要的额外证据
        
        Args:
            current_strength: 当前证据强度
            target_status: 目标验证状态
            
        Returns:
            建议信息
        """
        target_strength = self.get_strength_requirement(target_status)
        
        if current_strength >= target_strength:
            return {
                'needed': False,
                'message': '当前证据强度已满足目标状态要求'
            }
        
        gap = target_strength - current_strength
        
        # 根据缺口大小建议证据类型
        suggestions = []
        
        if gap > 0.3:
            # 缺口较大，建议Layer 1证据
            suggestions.append({
                'type': EvidenceType.STAT.value,
                'layer': 1,
                'expected_contribution': 0.4,
                'description': '查找显式stat定义（Layer 1）'
            })
            suggestions.append({
                'type': EvidenceType.CODE.value,
                'layer': 2,
                'expected_contribution': 0.3,
                'description': '查找代码逻辑证据（Layer 2）'
            })
        
        elif gap > 0.1:
            # 缺口中等，建议Layer 2证据
            suggestions.append({
                'type': EvidenceType.CODE.value,
                'layer': 2,
                'expected_contribution': 0.3,
                'description': '查找代码逻辑证据（Layer 2）'
            })
            suggestions.append({
                'type': EvidenceType.PATTERN.value,
                'layer': 2,
                'expected_contribution': 0.2,
                'description': '查找模式匹配证据（Layer 2）'
            })
        
        else:
            # 缺口较小，Layer 3证据即可
            suggestions.append({
                'type': EvidenceType.PATTERN.value,
                'layer': 3,
                'expected_contribution': 0.2,
                'description': '查找语义推断证据（Layer 3）'
            })
        
        return {
            'needed': True,
            'current_strength': current_strength,
            'target_strength': target_strength,
            'gap': gap,
            'suggestions': suggestions
        }
