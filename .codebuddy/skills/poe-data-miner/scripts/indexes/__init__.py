"""
索引系统模块

提供四级索引支持，用于快速查询POB代码：
- StatIndex: stat定义和使用索引
- SkillTypeIndex: skillType约束索引
- FunctionCallIndex: 函数调用索引
- SemanticFeatureIndex: 语义特征索引
"""

from .base_index import BaseIndex
from .stat_index import StatIndex
from .skilltype_index import SkillTypeIndex
from .function_index import FunctionCallIndex
from .semantic_index import SemanticFeatureIndex
from .index_manager import IndexManager

__all__ = [
    'BaseIndex',
    'StatIndex',
    'SkillTypeIndex',
    'FunctionCallIndex',
    'SemanticFeatureIndex',
    'IndexManager'
]
