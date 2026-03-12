#!/usr/bin/env python3
"""
种子知识验证器

Phase 4: 替换 init_knowledge_base.py 中的硬编码映射

功能：
1. 定义种子知识（类型-属性映射、触发机制映射）
2. 使用验证系统自动验证
3. 返回验证后的映射关系

种子知识来源：
- 原始硬编码映射
- POB代码验证结果
- 已验证的预置边
"""

import json
import sqlite3
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime

# 导入验证组件
import sys
sys.path.insert(0, str(Path(__file__).parent))

from verification.verification_engine import VerificationEngine
from verification.pob_searcher import POBCodeSearcher
from verification.evidence_evaluator import EvidenceEvaluator, Evidence, EvidenceType
from attribute_graph import VerificationStatus

logger = logging.getLogger(__name__)


# ========== 种子知识定义 ==========

# 类型-属性映射种子（原始硬编码）
SEED_TYPE_PROPERTY_MAPPINGS = {
    'Meta': {
        'properties': ['UsesTriggerMechanism'],
        'description': 'Meta技能使用触发机制',
        'evidence_hints': ['Meta', 'trigger', 'energy']
    },
    'Meta + GeneratesEnergy': {
        'properties': ['UsesEnergySystem'],
        'description': 'Meta技能生成能量时使用能量系统',
        'evidence_hints': ['Meta', 'GeneratesEnergy', 'energy']
    },
    'Hazard': {
        'properties': ['DoesNotUseEnergy', 'DoesNotProduceTriggered'],
        'description': 'Hazard不使用能量系统，不产生Triggered标签',
        'evidence_hints': ['Hazard', 'energy', 'Triggered']
    },
    'Triggered': {
        'properties': ['CannotGenerateEnergyForMeta'],
        'description': 'Triggered标签的技能无法为Meta技能生成能量',
        'evidence_hints': ['Triggered', 'Meta', 'energy']
    },
    'Duration': {
        'properties': ['HasDuration'],
        'description': '持续时间技能',
        'evidence_hints': ['Duration', 'duration']
    },
    'Triggers': {
        'properties': ['CanTriggerOtherSkills'],
        'description': '可触发其他技能',
        'evidence_hints': ['Triggers', 'trigger']
    }
}

# 触发机制映射种子
SEED_TRIGGER_MECHANISMS = {
    'MetaTrigger': {
        'produces': ['Triggered'],
        'description': 'Meta触发机制，产生Triggered标签',
        'evidence_hints': ['Meta', 'Triggered', 'trigger']
    },
    'HazardTrigger': {
        'produces': [],
        'description': 'Hazard触发机制，不产生Triggered标签',
        'evidence_hints': ['Hazard', 'Triggered']
    },
    'CreationTrigger': {
        'produces': [],
        'description': 'Creation触发机制（如Doedre），不产生Triggered标签',
        'evidence_hints': ['creation', 'trigger', 'energy']
    }
}


class SeedKnowledgeVerifier:
    """
    种子知识验证器
    
    使用验证系统验证种子知识，返回验证后的映射
    """
    
    def __init__(self, pob_data_path: str, graph_db_path: str, 
                 config: Optional[Dict[str, Any]] = None):
        """
        初始化验证器
        
        Args:
            pob_data_path: POB数据路径
            graph_db_path: 关联图数据库路径
            config: 配置
        """
        self.pob_data_path = Path(pob_data_path)
        self.graph_db_path = Path(graph_db_path)
        
        # 配置
        self.config = config or {}
        self.auto_verify_threshold = self.config.get('auto_verify_threshold', 0.7)
        
        # 初始化验证组件
        self.searcher = POBCodeSearcher(str(pob_data_path))
        self.evaluator = EvidenceEvaluator()
        
        logger.info(f"SeedKnowledgeVerifier初始化完成")
    
    def verify_type_property_mappings(self) -> Dict[str, Dict[str, Any]]:
        """
        验证类型-属性映射种子知识
        
        Returns:
            验证后的映射字典
        """
        logger.info("开始验证类型-属性映射种子知识...")
        
        verified_mappings = {}
        
        for type_combo, mapping_info in SEED_TYPE_PROPERTY_MAPPINGS.items():
            properties = mapping_info['properties']
            description = mapping_info['description']
            evidence_hints = mapping_info['evidence_hints']
            
            logger.info(f"验证: {type_combo} -> {properties}")
            
            # 收集证据
            evidences = []
            
            for hint in evidence_hints:
                # Layer 1: 搜索stat定义
                stat_results = self.searcher.search_stat_definition(hint)
                
                if stat_results.get('found'):
                    evidence = Evidence(
                        type=EvidenceType.STAT,
                        source=stat_results.get('locations', [{}])[0].get('file', 'unknown'),
                        content=f"Found stat definition for '{hint}'",
                        strength=1.0
                    )
                    evidences.append(evidence)
                    logger.debug(f"  Layer 1 证据: {hint}")
                    continue
                
                # Layer 2: 搜索代码逻辑
                code_results = self.searcher.search_calc_logic(hint)
                
                if code_results.get('found'):
                    evidence = Evidence(
                        type=EvidenceType.CODE,
                        source=code_results.get('locations', [{}])[0].get('file', 'unknown'),
                        content=f"Found code logic for '{hint}'",
                        strength=0.8
                    )
                    evidences.append(evidence)
                    logger.debug(f"  Layer 2 证据: {hint}")
                    continue
            
            # 评估证据
            if evidences:
                result = self.evaluator.evaluate_evidence_set(evidences)
                confidence = result['confidence']
                status = result['status']
            else:
                # 无证据时，使用种子知识的默认置信度
                confidence = 0.5
                status = VerificationStatus.PENDING.value
                logger.warning(f"  无证据: {type_combo}，使用默认置信度 0.5")
            
            # 记录结果
            verified_mappings[type_combo] = {
                'properties': properties,
                'description': description,
                'confidence': confidence,
                'status': status,
                'evidence_count': len(evidences),
                'evidence_types': [e.type.value for e in evidences]
            }
            
            logger.info(f"  结果: status={status}, confidence={confidence:.2f}")
        
        logger.info(f"类型-属性映射验证完成: {len(verified_mappings)} 条")
        return verified_mappings
    
    def verify_trigger_mechanisms(self) -> Dict[str, Dict[str, Any]]:
        """
        验证触发机制映射种子知识
        
        Returns:
            验证后的映射字典
        """
        logger.info("开始验证触发机制映射种子知识...")
        
        verified_mechanisms = {}
        
        for mech_name, mech_info in SEED_TRIGGER_MECHANISMS.items():
            produces = mech_info['produces']
            description = mech_info['description']
            evidence_hints = mech_info['evidence_hints']
            
            logger.info(f"验证: {mech_name}")
            
            # 收集证据
            evidences = []
            
            for hint in evidence_hints:
                # Layer 1: 搜索stat定义
                stat_results = self.searcher.search_stat_definition(hint)
                
                if stat_results.get('found'):
                    evidence = Evidence(
                        type=EvidenceType.STAT,
                        source=stat_results.get('locations', [{}])[0].get('file', 'unknown'),
                        content=f"Found stat definition for '{hint}'",
                        strength=1.0
                    )
                    evidences.append(evidence)
                    continue
                
                # Layer 2: 搜索skillType约束
                type_results = self.searcher.search_skilltype_constraint(hint)
                
                if type_results.get('found'):
                    evidence = Evidence(
                        type=EvidenceType.CODE,
                        source=type_results.get('locations', [{}])[0].get('file', 'unknown'),
                        content=f"Found skillType constraint for '{hint}'",
                        strength=0.8
                    )
                    evidences.append(evidence)
            
            # 评估证据
            if evidences:
                result = self.evaluator.evaluate_evidence_set(evidences)
                confidence = result['confidence']
                status = result['status']
            else:
                confidence = 0.5
                status = VerificationStatus.PENDING.value
                logger.warning(f"  无证据: {mech_name}，使用默认置信度 0.5")
            
            # 记录结果
            verified_mechanisms[mech_name] = {
                'produces': produces,
                'description': description,
                'confidence': confidence,
                'status': status,
                'evidence_count': len(evidences),
                'evidence_types': [e.type.value for e in evidences]
            }
            
            logger.info(f"  结果: status={status}, confidence={confidence:.2f}")
        
        logger.info(f"触发机制映射验证完成: {len(verified_mechanisms)} 条")
        return verified_mechanisms
    
    def get_verified_property_mappings(self, min_confidence: float = 0.5) -> Dict[str, Dict[str, Any]]:
        """
        获取验证后的属性映射（过滤低置信度）
        
        Args:
            min_confidence: 最小置信度阈值
            
        Returns:
            过滤后的映射
        """
        all_mappings = self.verify_type_property_mappings()
        
        # 过滤低置信度
        filtered = {
            k: v for k, v in all_mappings.items()
            if v['confidence'] >= min_confidence
        }
        
        logger.info(f"属性映射过滤: {len(all_mappings)} -> {len(filtered)} (置信度>={min_confidence})")
        
        return filtered
    
    def get_verified_trigger_mechanisms(self, min_confidence: float = 0.5) -> Dict[str, Dict[str, Any]]:
        """
        获取验证后的触发机制映射（过滤低置信度）
        
        Args:
            min_confidence: 最小置信度阈值
            
        Returns:
            过滤后的映射
        """
        all_mechanisms = self.verify_trigger_mechanisms()
        
        # 过滤低置信度
        filtered = {
            k: v for k, v in all_mechanisms.items()
            if v['confidence'] >= min_confidence
        }
        
        logger.info(f"触发机制映射过滤: {len(all_mechanisms)} -> {len(filtered)} (置信度>={min_confidence})")
        
        return filtered
    
    def close(self):
        """关闭资源"""
        if self.searcher:
            self.searcher = None
        
        logger.info("SeedKnowledgeVerifier已关闭")


def verify_and_get_property_mappings(pob_data_path: str, graph_db_path: str,
                                      min_confidence: float = 0.5) -> Dict[str, Dict[str, Any]]:
    """
    便捷函数：验证并获取属性映射
    
    Args:
        pob_data_path: POB数据路径
        graph_db_path: 图数据库路径
        min_confidence: 最小置信度
        
    Returns:
        验证后的属性映射
    """
    verifier = SeedKnowledgeVerifier(pob_data_path, graph_db_path)
    try:
        return verifier.get_verified_property_mappings(min_confidence)
    finally:
        verifier.close()


def verify_and_get_trigger_mechanisms(pob_data_path: str, graph_db_path: str,
                                       min_confidence: float = 0.5) -> Dict[str, Dict[str, Any]]:
    """
    便捷函数：验证并获取触发机制映射
    
    Args:
        pob_data_path: POB数据路径
        graph_db_path: 图数据库路径
        min_confidence: 最小置信度
        
    Returns:
        验证后的触发机制映射
    """
    verifier = SeedKnowledgeVerifier(pob_data_path, graph_db_path)
    try:
        return verifier.get_verified_trigger_mechanisms(min_confidence)
    finally:
        verifier.close()


def main():
    """测试函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='种子知识验证器测试')
    parser.add_argument('pob_path', help='POB数据路径')
    parser.add_argument('--graph-db', required=True, help='图数据库路径')
    parser.add_argument('--min-confidence', type=float, default=0.5,
                       help='最小置信度阈值')
    
    args = parser.parse_args()
    
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    verifier = SeedKnowledgeVerifier(args.pob_path, args.graph_db)
    
    try:
        # 验证属性映射
        print("\n=== 验证类型-属性映射 ===")
        property_mappings = verifier.get_verified_property_mappings(args.min_confidence)
        
        for type_combo, mapping in property_mappings.items():
            print(f"\n{type_combo}:")
            print(f"  属性: {mapping['properties']}")
            print(f"  置信度: {mapping['confidence']:.2f}")
            print(f"  状态: {mapping['status']}")
            print(f"  证据数: {mapping['evidence_count']}")
        
        # 验证触发机制映射
        print("\n=== 验证触发机制映射 ===")
        trigger_mechs = verifier.get_verified_trigger_mechanisms(args.min_confidence)
        
        for mech_name, mech in trigger_mechs.items():
            print(f"\n{mech_name}:")
            print(f"  产生: {mech['produces']}")
            print(f"  置信度: {mech['confidence']:.2f}")
            print(f"  状态: {mech['status']}")
            print(f"  证据数: {mech['evidence_count']}")
    
    finally:
        verifier.close()


if __name__ == '__main__':
    main()
