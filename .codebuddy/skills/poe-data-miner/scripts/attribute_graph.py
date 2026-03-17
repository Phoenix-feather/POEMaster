#!/usr/bin/env python3
"""
POE关联图模块 — v2 方案

GraphBuilder 替代旧的 AttributeGraph。
10 步构建 + 后处理异常发现存档。

核心设计：
  图 = 完整的正常运行逻辑（可查询任何机制问题）+ 异常突破点
  
  节点类型（4种）：category / entity / constraint / tag
  边类型（15种）：结构边 + 机制边 + 约束边 + 改变者边
"""

import json
import re
import sqlite3
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

# 尝试导入yaml
try:
    import yaml
    HAS_YAML = True
    
    # 自定义 Dumper：多行字符串使用块标量样式（|）
    class MultilineDumper(yaml.SafeDumper):
        pass
    
    def _str_representer(dumper, data):
        """如果字符串包含换行符，使用块标量样式"""
        if '\n' in data:
            return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
        return dumper.represent_scalar('tag:yaml.org,2002:str', data)
    
    MultilineDumper.add_representer(str, _str_representer)
    
except ImportError:
    HAS_YAML = False
    MultilineDumper = None

logger = logging.getLogger(__name__)


# ============================================================
# 枚举定义
# ============================================================

class NodeType(Enum):
    """节点类型（v2: 4种）"""
    CATEGORY = "category"        # 一级集合节点（~15-20个）
    ENTITY = "entity"            # 具体技能/辅助/物品/天赋
    CONSTRAINT = "constraint"    # 约束条件（路径通行条件）
    TAG = "tag"                  # 运行时标签（动态获得/失去）


class EdgeType(Enum):
    """边类型（v2: 15种）"""
    # === 结构边 ===
    BELONGS_TO = "belongs_to"          # 实体归属集合
    IS_SUBSET_OF = "is_subset_of"      # 子集合关系

    # === 机制边（集合之间的正常逻辑）===
    TRIGGERS = "triggers"              # 触发关系
    PRODUCES_ENERGY = "produces_energy" # 产生能量
    CONVERTS_TO = "converts_to"        # 伤害转换
    SUMMONS = "summons"                # 召唤关系
    RESERVES = "reserves"              # 预留资源
    DEPLOYS_AS = "deploys_as"          # 部署方式
    GRANTS_BUFF = "grants_buff"        # 给予增益
    APPLIES_EFFECT = "applies_effect"  # 施加效果

    # === 约束边 ===
    REQUIRES_TAG = "requires_tag"      # 需要目标有某标签
    ADDS_TAG = "adds_tag"              # 给目标添加标签
    BLOCKS_WHEN = "blocks_when"        # 条件阻断
    EXCLUDES_TAG = "excludes_tag"      # 排除某标签

    # === 改变者边 ===
    MODIFIES = "modifies"              # 改变标签/机制

    # === 异常发现边 ===
    BYPASSES = "bypasses"              # 绕过约束


# === 保留的枚举（验证系统依赖）===

class VerificationStatus(Enum):
    """验证状态 — 被 verification/ 系统使用，必须保留"""
    VERIFIED = "verified"
    PENDING = "pending"
    HYPOTHESIS = "hypothesis"
    REJECTED = "rejected"


class EvidenceType(Enum):
    """证据类型 — 被 verification/ 系统使用，必须保留"""
    STAT = "stat"
    CODE = "code"
    PATTERN = "pattern"
    ANALOGY = "analogy"
    USER_INPUT = "user_input"
    DATA_EXTRACTION = "data_extraction"


# ============================================================
# 集合定义常量
# ============================================================

# 15个一级集合 + 2个虚拟父级
CATEGORY_DEFINITIONS = {
    # --- 攻击类 ---
    "MeleeAttack": {
        "display_name": "近战攻击",
        "match_condition": {"all": ["Attack", "Melee"]},
        "description": "Attack ∧ Melee",
    },
    "RangedAttack": {
        "display_name": "远程攻击",
        "match_condition": {"all": ["Attack"], "any": ["Ranged", "Projectile", "Bow"]},
        "description": "Attack ∧ (Ranged ∨ Projectile ∨ Bow)",
    },
    # --- 法术类 ---
    "Spell": {
        "display_name": "法术",
        "match_condition": {"all": ["Spell"]},
        "description": "Spell（含Curse子集）",
    },
    "Curse": {
        "display_name": "诅咒",
        "match_condition": {"all": ["AppliesCurse"]},
        "description": "AppliesCurse（Spell的子集）",
    },
    # --- Meta类 ---
    "MetaTriggerEnergy": {
        "display_name": "触发型Meta（能量系统）",
        "match_condition": {"all": ["Meta", "Triggers", "GeneratesEnergy"]},
        "description": "Meta ∧ Triggers ∧ GeneratesEnergy",
    },
    "Invocation": {
        "display_name": "调用型Meta",
        "match_condition": {"all": ["Meta", "Invocation"]},
        "description": "Meta ∧ Invocation",
    },
    "Totem": {
        "display_name": "图腾Meta",
        "match_condition": {"all": ["SummonsTotem"]},
        "description": "SummonsTotem 相关",
    },
    "Blasphemy": {
        "display_name": "亵渎",
        "match_condition": {"all": ["Meta", "IsBlasphemy"]},
        "description": "Meta ∧ IsBlasphemy — 诅咒→光环转换",
    },
    # --- 其他类 ---
    "Aura": {
        "display_name": "光环",
        "match_condition": {"all": ["HasReservation", "Buff", "Persistent"]},
        "description": "HasReservation ∧ Buff ∧ Persistent",
    },
    "Minion": {
        "display_name": "召唤物",
        "match_condition": {"all": ["Minion"]},
        "description": "Minion",
    },
    "Trap": {
        "display_name": "陷阱",
        "match_condition": {"all": ["Trappable"]},
        "description": "Trappable 系统（间接集合）",
        "indirect": True,
    },
    "Mine": {
        "display_name": "地雷",
        "match_condition": {"all": ["Mineable"]},
        "description": "Mineable 系统（间接集合）",
        "indirect": True,
    },
    "Warcry": {
        "display_name": "战吼",
        "match_condition": {"all": ["Warcry"]},
        "description": "Warcry",
    },
    "Herald": {
        "display_name": "先驱",
        "match_condition": {"all": ["Herald"]},
        "description": "Herald",
    },
    "Guard": {
        "display_name": "防御技能",
        "match_condition": {"all": ["Guard"]},
        "description": "Guard",
    },
}

# 虚拟父级集合（用于 is_subset_of 层级，不直接做实体归属匹配）
VIRTUAL_PARENTS = {
    "Attack": {
        "display_name": "攻击（虚拟父级）",
        "description": "MeleeAttack 和 RangedAttack 的父集合",
    },
    "Meta": {
        "display_name": "Meta（虚拟父级）",
        "description": "MetaTriggerEnergy / Invocation / Totem / Blasphemy 的父集合",
    },
}

# 集合层级关系（is_subset_of）
SUBSET_RELATIONS = [
    ("Curse", "Spell"),
    ("MetaTriggerEnergy", "Meta"),
    ("Invocation", "Meta"),
    ("Totem", "Meta"),
    ("Blasphemy", "Meta"),
    ("MeleeAttack", "Attack"),
    ("RangedAttack", "Attack"),
]

# 标签→集合映射表（用于约束归纳）
TAG_TO_CATEGORY = {
    # 核心集合映射
    "Attack": ["MeleeAttack", "RangedAttack"],
    "Melee": ["MeleeAttack"],
    "RangedAttack": ["RangedAttack"],
    "Spell": ["Spell"],
    "AppliesCurse": ["Curse"],
    "SummonsTotem": ["Totem"],
    "Warcry": ["Warcry"],
    "CreatesMinion": ["Minion"],
    "Minion": ["Minion"],
    "Herald": ["Herald"],
    "Guard": ["Guard"],
    "Meta": ["MetaTriggerEnergy", "Invocation", "Totem", "Blasphemy"],
    "Trappable": ["Trap"],
    "Mineable": ["Mine"],

    # 非集合标签（维度/兼容性/武器限定） — 映射为 None
    "Damage": None,
    "Projectile": None,
    "CrossbowAmmoSkill": None,
    "CrossbowSkill": None,
    "Persistent": None,
    "Buff": None,
    "Triggerable": None,
    "Channel": None,
    "Duration": None,
    "Area": None,
    "Cooldown": None,
    "Bow": None,
    "Ranged": None,
    "HasReservation": None,
    "GeneratesEnergy": None,
    "Triggers": None,
    "Invocation": None,
    "IsBlasphemy": None,
    "Totemable": None,
}

# step3: 标签推导的机制边规则
MECHANISM_EDGE_RULES = [
    # (源标签条件, 目标集合, 边类型, 边属性)
    {
        "name": "Trap deploys_as",
        "source_tag": "Trappable",
        "target_category": "Trap",
        "edge_type": EdgeType.DEPLOYS_AS,
        "description": "Trappable技能可被陷阱部署",
    },
    {
        "name": "Mine deploys_as",
        "source_tag": "Mineable",
        "target_category": "Mine",
        "edge_type": EdgeType.DEPLOYS_AS,
        "description": "Mineable技能可被地雷部署",
    },
    {
        "name": "Totem summons",
        "source_tag": "Totemable",
        "target_category": "Totem",
        "edge_type": EdgeType.SUMMONS,
        "description": "Totemable技能可被图腾召唤",
    },
    {
        "name": "Aura reserves",
        "source_tag": "HasReservation",
        "target_category": "Aura",
        "edge_type": EdgeType.RESERVES,
        "description": "HasReservation技能预留资源",
        "additional_condition": {"all": ["Buff", "Persistent"]},
    },
    {
        "name": "Herald reserves",
        "source_tag": "Herald",
        "target_category": "Herald",
        "edge_type": EdgeType.RESERVES,
        "description": "Herald技能预留资源",
    },
    {
        "name": "Curse applies_effect",
        "source_tag": "AppliesCurse",
        "target_category": "Curse",
        "edge_type": EdgeType.APPLIES_EFFECT,
        "description": "AppliesCurse技能施加诅咒效果",
    },
    {
        "name": "Blasphemy converts Curse to Aura",
        "source_tag": "IsBlasphemy",
        "target_category": "Blasphemy",
        "edge_type": EdgeType.CONVERTS_TO,
        "description": "Blasphemy将诅咒转换为光环",
        "properties": {"from_category": "Curse", "to_category": "Aura"},
    },
]


# ============================================================
# 集合匹配优先级（用于解决优先匹配问题）
# 更具体的集合优先于更宽泛的集合
# ============================================================

# 匹配顺序：先匹配最具体的（条件多的），再匹配宽泛的
# MetaTriggerEnergy（3个条件）> Invocation/Blasphemy（2个）> Spell（1个）
# Curse（AppliesCurse）在Spell之前匹配，因为Curse是子集
CATEGORY_MATCH_ORDER = [
    # 最具体的Meta子类型（3个条件）
    "MetaTriggerEnergy",
    # 2个条件的类型
    "Invocation", "Blasphemy", "MeleeAttack", "RangedAttack", "Aura",
    # 1个条件的特殊类型
    "Curse", "Totem", "Minion", "Warcry", "Herald", "Guard",
    # 最宽泛的
    "Spell",
    # 间接集合（不直接做 belongs_to，只做机制边参考）
    "Trap", "Mine",
]


# ============================================================
# GraphBuilder 核心类
# ============================================================

class GraphBuilder:
    """
    关联图构建器 — v2 方案
    
    在 attribute_graph.py 中替代旧的 AttributeGraph。
    10 步构建 + 后处理。
    
    Usage:
        builder = GraphBuilder(
            graph_db_path="knowledge_base/graph.db",
            entities_db_path="knowledge_base/entities.db",
            pob_path="POBData",
            archive_path="config/predefined_edges.yaml"
        )
        stats = builder.build()
    """
    
    def __init__(self, graph_db_path: str, entities_db_path: str = None,
                 pob_path: str = None, archive_path: str = None):
        """
        初始化 GraphBuilder
        
        Args:
            graph_db_path: graph.db 路径（构建模式会删除重建，查询模式只读）
            entities_db_path: entities.db 路径（只读，构建模式必须，查询模式可选）
            pob_path: POBData 根目录路径（用于 step4/5/6 解析 Lua 文件）
            archive_path: predefined_edges.yaml 异常发现存档路径
            
        Note:
            查询模式（调用 get_*, search_* 方法）只需要 graph_db_path
            构建模式（调用 build()）需要所有参数
        """
        self.graph_db_path = Path(graph_db_path)
        self.entities_db_path = Path(entities_db_path) if entities_db_path else None
        self.pob_path = Path(pob_path) if pob_path else None
        self.archive_path = Path(archive_path) if archive_path else None
        
        self.graph_conn: Optional[sqlite3.Connection] = None
        self.entities_conn: Optional[sqlite3.Connection] = None
        
        # 构建过程中的统计
        self.stats = {
            "step1_categories": 0,
            "step1_subset_edges": 0,
            "step2_belongs_to": 0,
            "step2_entities": 0,
            "step3_mechanism_edges": 0,
            "step4_triggers": 0,
            "step5_produces_energy": 0,
            "step6_blocks_when": 0,
            "step7_modifiers": 0,
            "step8_tag_propagation": 0,
            "step9_restored": 0,
            "step10_discovered": 0,
            "total_nodes": 0,
            "total_edges": 0,
        }
    
    @property
    def conn(self) -> Optional[sqlite3.Connection]:
        """兼容别名：旧代码使用 self.graph.conn 访问数据库连接"""
        if not self.graph_conn:
            self._open_graph_db()
        return self.graph_conn
    
    # ============================================================
    # 数据库初始化
    # ============================================================
    
    def _init_graph_db(self):
        """初始化 graph.db — 删除重建，创建 v2 Schema"""
        # 如果已存在，删除旧文件
        if self.graph_db_path.exists():
            self.graph_db_path.unlink()
            logger.info("已删除旧的 graph.db")
        
        self.graph_db_path.parent.mkdir(parents=True, exist_ok=True)
        self.graph_conn = sqlite3.connect(str(self.graph_db_path))
        self.graph_conn.row_factory = sqlite3.Row
        
        # 启用WAL模式提高并发写性能
        self.graph_conn.execute("PRAGMA journal_mode=WAL")
        self.graph_conn.execute("PRAGMA synchronous=NORMAL")
        
        cursor = self.graph_conn.cursor()
        
        # 节点表
        cursor.execute('''
            CREATE TABLE graph_nodes (
                node_id TEXT PRIMARY KEY,
                node_type TEXT NOT NULL,
                name TEXT NOT NULL,
                properties TEXT,
                source TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            )
        ''')
        
        # 边表
        cursor.execute('''
            CREATE TABLE graph_edges (
                edge_id TEXT PRIMARY KEY,
                source_id TEXT NOT NULL,
                source_name TEXT,
                source_type TEXT,
                target_id TEXT NOT NULL,
                target_name TEXT,
                target_type TEXT,
                edge_type TEXT NOT NULL,
                properties TEXT,
                confidence REAL DEFAULT 1.0,
                source TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (source_id) REFERENCES graph_nodes(node_id),
                FOREIGN KEY (target_id) REFERENCES graph_nodes(node_id)
            )
        ''')
        
        # 异常路径表
        cursor.execute('''
            CREATE TABLE anomaly_paths (
                anomaly_id TEXT PRIMARY KEY,
                constraint_id TEXT NOT NULL,
                modifier_id TEXT NOT NULL,
                mechanism TEXT NOT NULL,
                path_description TEXT,
                value_score INTEGER,
                source TEXT,
                discovered_at TEXT DEFAULT (datetime('now')),
                verified BOOLEAN DEFAULT 0
            )
        ''')
        
        # 索引
        cursor.execute('CREATE INDEX idx_nodes_type ON graph_nodes(node_type)')
        cursor.execute('CREATE INDEX idx_edges_source ON graph_edges(source_id)')
        cursor.execute('CREATE INDEX idx_edges_target ON graph_edges(target_id)')
        cursor.execute('CREATE INDEX idx_edges_type ON graph_edges(edge_type)')
        cursor.execute('CREATE INDEX idx_anomaly_value ON anomaly_paths(value_score DESC)')
        
        self.graph_conn.commit()
        logger.info("graph.db v2 Schema 初始化完成")
    
    def _open_entities_db(self):
        """打开 entities.db（只读）"""
        if not self.entities_db_path:
            raise ValueError(
                "entities_db_path 未指定。构建模式需要 entities.db，"
                "请在创建 GraphBuilder 时提供 entities_db_path 参数。"
            )
        if not self.entities_db_path.exists():
            raise FileNotFoundError(f"entities.db 不存在: {self.entities_db_path}")
        
        self.entities_conn = sqlite3.connect(str(self.entities_db_path))
        self.entities_conn.row_factory = sqlite3.Row
    
    # ============================================================
    # 实体名称解析工具
    # ============================================================
    
    # 实体类型 emoji 映射
    ENTITY_TYPE_EMOJI = {
        'passive_node': '🔮 天赋',
        'gem_definition': '💎 宝石',
        'skill_definition': '⚔️ 技能',
        'unique_item': '⭐ 传奇',
        'mod_affix': '📜 词缀',
        'item_base': '📦 基底',
        'minion_definition': '👻 召唤物',
        'stat_mapping': '📊 属性映射',
        'calculation_module': '⚙️ 计算模块',
    }
    
    def _resolve_entity_name(self, entity_id: str) -> dict:
        """解析实体的可读名称
        
        优先级：
        1. 图内节点 → 直接返回 name
        2. 实体库 → 查询 entities.db
        3. ID推断 → 从ID格式推断类型和名称
        
        Returns:
            dict: {'id': str, 'name': str, 'type': str, 'effect': str}
        """
        result = {'id': entity_id, 'name': entity_id, 'type': '未知'}
        
        # 1. 先查图内节点
        if self.graph_conn:
            cursor = self.graph_conn.cursor()
            cursor.execute(
                'SELECT name, node_type FROM graph_nodes WHERE node_id = ?',
                (entity_id,)
            )
            row = cursor.fetchone()
            if row:
                return {
                    'id': entity_id,
                    'name': row['name'],
                    'type': self._format_node_type(row['node_type']),
                }
        
        # 2. 查实体库
        if self.entities_conn:
            cursor = self.entities_conn.cursor()
            cursor.execute(
                'SELECT name, type, stat_descriptions FROM entities WHERE id = ?',
                (entity_id,)
            )
            row = cursor.fetchone()
            if row:
                return {
                    'id': entity_id,
                    'name': row['name'] or entity_id,
                    'type': self._format_entity_type(row['type']),
                    'effect': self._truncate_description(row['stat_descriptions']),
                }
        
        # 3. 从ID推断
        return self._infer_from_id(entity_id)
    
    def _format_entity_type(self, entity_type: str) -> str:
        """格式化实体类型为 emoji 前缀"""
        return self.ENTITY_TYPE_EMOJI.get(entity_type, f'📋 {entity_type}')
    
    def _format_node_type(self, node_type: str) -> str:
        """格式化节点类型"""
        type_map = {
            'category': '📁 集合',
            'constraint': '🚫 约束',
            'entity': '📋 实体',
        }
        return type_map.get(node_type, f'📋 {node_type}')
    
    def _truncate_description(self, desc: str, max_len: int = 150) -> str:
        """截断描述文本"""
        if not desc:
            return ''
        # 处理可能是 JSON 数组格式的描述
        if desc.startswith('['):
            try:
                items = json.loads(desc)
                desc = ' | '.join(str(i) for i in items[:2])
            except:
                pass
        if len(desc) > max_len:
            return desc[:max_len] + '...'
        return desc
    
    def _infer_from_id(self, entity_id: str) -> dict:
        """从ID推断实体信息"""
        result = {'id': entity_id, 'name': entity_id, 'type': '未知'}
        
        if entity_id.startswith('passive_'):
            result['type'] = '🔮 天赋'
            result['name'] = f"天赋节点 #{entity_id.replace('passive_', '')}"
        elif entity_id.startswith('Support'):
            # SupportCursedGroundPlayer -> Cursed Ground
            clean = entity_id.replace('Support', '').replace('Player', '')
            # 驼峰转空格
            import re
            clean = re.sub(r'([A-Z])', r' \1', clean).strip()
            result['name'] = clean
            result['type'] = '💎 辅助宝石'
        elif entity_id.startswith('con_'):
            result['type'] = '🚫 约束'
        elif entity_id.startswith('cat_'):
            result['type'] = '📁 集合'
        
        return result
    
    def _insert_node(self, node_id: str, node_type: NodeType, name: str,
                     properties: dict = None, source: str = None):
        """插入节点（忽略重复）"""
        cursor = self.graph_conn.cursor()
        try:
            cursor.execute('''
                INSERT OR IGNORE INTO graph_nodes (node_id, node_type, name, properties, source)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                node_id,
                node_type.value,
                name,
                json.dumps(properties, ensure_ascii=False) if properties else None,
                source,
            ))
            return cursor.rowcount > 0
        except sqlite3.IntegrityError:
            return False
    
    def _insert_edge(self, edge_id: str, source_id: str, target_id: str,
                     edge_type: EdgeType, properties: dict = None,
                     confidence: float = 1.0, source: str = None,
                     source_name: str = None, source_type: str = None,
                     target_name: str = None, target_type: str = None):
        """插入边（忽略重复）
        
        Args:
            edge_id: 边唯一ID
            source_id: 源节点ID
            target_id: 目标节点ID
            edge_type: 边类型
            properties: 边属性
            confidence: 置信度
            source: 数据来源
            source_name: 源节点可读名称（新增）
            source_type: 源节点类型（新增）
            target_name: 目标节点可读名称（新增）
            target_type: 目标节点类型（新增）
        """
        cursor = self.graph_conn.cursor()
        
        # 如果未提供名称，尝试解析
        if source_name is None or target_name is None:
            resolved_source = self._resolve_entity_name(source_id)
            resolved_target = self._resolve_entity_name(target_id)
            if source_name is None:
                source_name = resolved_source.get('name')
                source_type = resolved_source.get('type')
            if target_name is None:
                target_name = resolved_target.get('name')
                target_type = resolved_target.get('type')
        
        try:
            cursor.execute('''
                INSERT OR IGNORE INTO graph_edges 
                (edge_id, source_id, source_name, source_type, 
                 target_id, target_name, target_type,
                 edge_type, properties, confidence, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                edge_id,
                source_id,
                source_name,
                source_type,
                target_id,
                target_name,
                target_type,
                edge_type.value,
                json.dumps(properties, ensure_ascii=False) if properties else None,
                confidence,
                source,
            ))
            return cursor.rowcount > 0
        except sqlite3.IntegrityError:
            return False
    
    def _insert_anomaly(self, anomaly_id: str, constraint_id: str, modifier_id: str,
                        mechanism: str, path_description: str = None,
                        value_score: int = 1, source: str = None):
        """插入异常路径"""
        cursor = self.graph_conn.cursor()
        try:
            cursor.execute('''
                INSERT OR IGNORE INTO anomaly_paths
                (anomaly_id, constraint_id, modifier_id, mechanism, path_description, 
                 value_score, source)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                anomaly_id, constraint_id, modifier_id, mechanism,
                path_description, value_score, source,
            ))
            return cursor.rowcount > 0
        except sqlite3.IntegrityError:
            return False

    # ============================================================
    # 主构建流程
    # ============================================================
    
    def build(self) -> dict:
        """
        完整构建流程 — 10步 + 后处理
        
        Returns:
            构建统计字典
        """
        logger.info("=" * 60)
        logger.info("GraphBuilder v2: 开始构建关联图")
        logger.info("=" * 60)
        
        try:
            # 初始化数据库
            self._init_graph_db()
            self._open_entities_db()
            
            # === 基础图结构（Phase A）===
            self.step1_create_categories()
            self.step2_assign_membership()
            self.step3_build_mechanism_edges()
            
            # === 触发 + 能量（Phase B）===
            self.step4_parse_triggers()
            self.step5_parse_energy()
            
            # === 约束 + 改变者 + 标签传播（Phase C）===
            self.step6_extract_blocks_when()
            self.step7_build_modifiers()
            self.step8_extract_tag_propagation()
            
            # === 异常发现（Phase D）===
            self.step9_restore_archive()
            self.step10_discover_anomalies()
            
            # === 后处理 ===
            self._postprocess_archive()
            
            # 提交所有更改
            self.graph_conn.commit()
            
            # 收集最终统计
            self._collect_final_stats()
            
            logger.info("=" * 60)
            logger.info("GraphBuilder v2: 构建完成")
            logger.info(f"  节点: {self.stats['total_nodes']}")
            logger.info(f"  边: {self.stats['total_edges']}")
            logger.info("=" * 60)
            
            return self.stats
        
        finally:
            if self.entities_conn:
                self.entities_conn.close()
                self.entities_conn = None
    
    def _collect_final_stats(self):
        """收集最终统计数据"""
        cursor = self.graph_conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM graph_nodes')
        self.stats['total_nodes'] = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM graph_edges')
        self.stats['total_edges'] = cursor.fetchone()[0]
        
        cursor.execute('SELECT node_type, COUNT(*) FROM graph_nodes GROUP BY node_type')
        self.stats['node_type_counts'] = {row[0]: row[1] for row in cursor.fetchall()}
        
        cursor.execute('SELECT edge_type, COUNT(*) FROM graph_edges GROUP BY edge_type')
        self.stats['edge_type_counts'] = {row[0]: row[1] for row in cursor.fetchall()}
        
        cursor.execute('SELECT COUNT(*) FROM anomaly_paths')
        self.stats['anomaly_count'] = cursor.fetchone()[0]
    
    # ============================================================
    # Step 1: 创建集合节点 + is_subset_of 层级
    # ============================================================
    
    def step1_create_categories(self):
        """
        Step 1: 创建集合节点和层级关系
        
        输入: 硬编码的 15 个集合定义 + 2 个虚拟父级
        输出: ~17 个 category 节点 + ~7 条 is_subset_of 边
        """
        logger.info("[Step 1] 创建集合节点...")
        
        cat_count = 0
        
        # 创建 15 个一级集合
        for cat_id, cat_def in CATEGORY_DEFINITIONS.items():
            node_id = f"cat_{cat_id}"
            inserted = self._insert_node(
                node_id=node_id,
                node_type=NodeType.CATEGORY,
                name=cat_def["display_name"],
                properties={
                    "category_id": cat_id,
                    "match_condition": cat_def["match_condition"],
                    "description": cat_def["description"],
                    "indirect": cat_def.get("indirect", False),
                },
                source="step1_hardcoded",
            )
            if inserted:
                cat_count += 1
        
        # 创建 2 个虚拟父级
        for parent_id, parent_def in VIRTUAL_PARENTS.items():
            node_id = f"cat_{parent_id}"
            inserted = self._insert_node(
                node_id=node_id,
                node_type=NodeType.CATEGORY,
                name=parent_def["display_name"],
                properties={
                    "category_id": parent_id,
                    "virtual": True,
                    "description": parent_def["description"],
                },
                source="step1_hardcoded",
            )
            if inserted:
                cat_count += 1
        
        # 创建 is_subset_of 层级边
        subset_count = 0
        for child_id, parent_id in SUBSET_RELATIONS:
            edge_id = f"subset_{child_id}_of_{parent_id}"
            inserted = self._insert_edge(
                edge_id=edge_id,
                source_id=f"cat_{child_id}",
                target_id=f"cat_{parent_id}",
                edge_type=EdgeType.IS_SUBSET_OF,
                properties={"description": f"{child_id} ⊂ {parent_id}"},
                source="step1_hardcoded",
            )
            if inserted:
                subset_count += 1
        
        self.graph_conn.commit()
        self.stats["step1_categories"] = cat_count
        self.stats["step1_subset_edges"] = subset_count
        logger.info(f"  创建 {cat_count} 个集合节点, {subset_count} 条 is_subset_of 边")
    
    # ============================================================
    # Step 2: 实体归属集合
    # ============================================================
    
    def step2_assign_membership(self):
        """
        Step 2: 将实体分配到集合（belongs_to）
        
        输入: entities.db skillTypes 字段
        输出: ~1,400 条 belongs_to 边
        
        规则：
        - 只有 Active skill_definition（非Support）参与 belongs_to
        - Support skill_definition 不属于集合（但改变者Support后续会建 modifies 边）
        - minion_definition 归属 Minion
        - 一个实体可属于多个集合（如 Curse 同时属于 Curse 和 Spell）
        """
        logger.info("[Step 2] 分配实体归属...")
        
        cursor = self.entities_conn.cursor()
        
        belongs_count = 0
        entity_count = 0
        multi_category_count = 0
        
        # 查询所有 skill_definition（非 Support）
        cursor.execute('''
            SELECT id, name, skill_types, type, support
            FROM entities
            WHERE type IN ('skill_definition', 'minion_definition')
              AND skill_types IS NOT NULL 
              AND skill_types != '[]'
        ''')
        rows = cursor.fetchall()
        
        for row in rows:
            entity_id = row[0]
            entity_name = row[1] or entity_id
            skill_types_json = row[2]
            entity_type = row[3]
            is_support = row[4]
            
            # Support不参与 belongs_to
            if is_support:
                continue
            
            # 解析 skillTypes
            try:
                skill_types = json.loads(skill_types_json) if skill_types_json else []
            except (json.JSONDecodeError, TypeError):
                continue
            
            if not skill_types:
                continue
            
            skill_types_set = set(skill_types)
            
            # 匹配集合
            matched_categories = self._match_categories(skill_types_set)
            
            if not matched_categories:
                continue
            
            # 创建实体节点
            self._insert_node(
                node_id=entity_id,
                node_type=NodeType.ENTITY,
                name=entity_name,
                properties={
                    "entity_type": entity_type,
                    "skill_types": skill_types,
                    "categories": matched_categories,
                },
                source="step2_entities_db",
            )
            entity_count += 1
            
            if len(matched_categories) > 1:
                multi_category_count += 1
            
            # 创建 belongs_to 边
            for cat_id in matched_categories:
                edge_id = f"bt_{entity_id}_to_{cat_id}"
                inserted = self._insert_edge(
                    edge_id=edge_id,
                    source_id=entity_id,
                    target_id=f"cat_{cat_id}",
                    edge_type=EdgeType.BELONGS_TO,
                    source="step2_entities_db",
                )
                if inserted:
                    belongs_count += 1
        
        self.graph_conn.commit()
        self.stats["step2_belongs_to"] = belongs_count
        self.stats["step2_entities"] = entity_count
        logger.info(f"  {entity_count} 个实体, {belongs_count} 条 belongs_to 边")
        logger.info(f"  其中 {multi_category_count} 个实体属于多个集合")
    
    def _match_categories(self, skill_types_set: set) -> List[str]:
        """
        将实体的 skillTypes 匹配到集合
        
        规则：
        - 按 CATEGORY_MATCH_ORDER 顺序匹配
        - 一个实体可匹配多个集合
        - 间接集合（Trap/Mine）不做 belongs_to
        
        Args:
            skill_types_set: 实体的 skillTypes 集合
            
        Returns:
            匹配到的集合ID列表
        """
        matched = []
        
        for cat_id in CATEGORY_MATCH_ORDER:
            cat_def = CATEGORY_DEFINITIONS.get(cat_id)
            if not cat_def:
                continue
            
            # 间接集合不做 belongs_to（仅用于机制边）
            if cat_def.get("indirect"):
                continue
            
            condition = cat_def["match_condition"]
            
            # 检查 all 条件：所有标签必须存在
            all_tags = condition.get("all", [])
            if all_tags and not all(tag in skill_types_set for tag in all_tags):
                continue
            
            # 检查 any 条件：至少一个标签存在
            any_tags = condition.get("any", [])
            if any_tags and not any(tag in skill_types_set for tag in any_tags):
                continue
            
            matched.append(cat_id)
        
        return matched
    
    # ============================================================
    # Step 3: 标签推导的机制边
    # ============================================================
    
    def step3_build_mechanism_edges(self):
        """
        Step 3: 从 skillTypes 标签推导机制边
        
        输入: entities.db skillTypes（Trappable/Mineable/Totemable/HasReservation/AppliesCurse）
        输出: deploys_as/summons/reserves/applies_effect/converts_to 边
        
        机制边连接的是集合→集合，不是实体→实体。
        同时统计每个机制边涉及的实体数量作为属性。
        """
        logger.info("[Step 3] 构建标签推导的机制边...")
        
        cursor = self.entities_conn.cursor()
        mechanism_count = 0
        
        for rule in MECHANISM_EDGE_RULES:
            source_tag = rule["source_tag"]
            target_category = rule["target_category"]
            edge_type = rule["edge_type"]
            
            # 统计有该标签的实体数量
            query = '''
                SELECT COUNT(*) FROM entities
                WHERE type = 'skill_definition'
                  AND support = 0
                  AND skill_types LIKE ?
            '''
            cursor.execute(query, (f'%"{source_tag}"%',))
            entity_count = cursor.fetchone()[0]
            
            # 如果有附加条件，进一步过滤
            additional = rule.get("additional_condition")
            if additional:
                # 需要更精确的统计
                all_tags = additional.get("all", [])
                if all_tags:
                    # 查出所有有source_tag的实体，然后Python过滤
                    cursor.execute('''
                        SELECT skill_types FROM entities
                        WHERE type = 'skill_definition'
                          AND support = 0
                          AND skill_types LIKE ?
                    ''', (f'%"{source_tag}"%',))
                    filtered_count = 0
                    for row in cursor.fetchall():
                        try:
                            st = json.loads(row[0]) if row[0] else []
                            st_set = set(st)
                            if all(tag in st_set for tag in all_tags):
                                filtered_count += 1
                        except (json.JSONDecodeError, TypeError):
                            pass
                    entity_count = filtered_count
            
            if entity_count == 0:
                logger.debug(f"  跳过 {rule['name']}: 无匹配实体")
                continue
            
            # 确定源集合：根据标签找到哪些集合的成员有这个标签
            # 机制边的语义是 "某些集合可以通过某种方式与目标集合交互"
            # 例如：deploys_as 连接的是"有 Trappable 标签的集合"→ Trap
            source_categories = self._find_categories_with_tag(source_tag, cursor)
            
            for src_cat in source_categories:
                edge_id = f"mech_{src_cat}_{edge_type.value}_{target_category}"
                properties = {
                    "description": rule["description"],
                    "source_tag": source_tag,
                    "entity_count": entity_count,
                }
                if rule.get("properties"):
                    properties.update(rule["properties"])
                
                inserted = self._insert_edge(
                    edge_id=edge_id,
                    source_id=f"cat_{src_cat}",
                    target_id=f"cat_{target_category}",
                    edge_type=edge_type,
                    properties=properties,
                    source="step3_tag_deduction",
                )
                if inserted:
                    mechanism_count += 1
        
        self.graph_conn.commit()
        self.stats["step3_mechanism_edges"] = mechanism_count
        logger.info(f"  创建 {mechanism_count} 条机制边")
    
    def _find_categories_with_tag(self, tag: str, cursor: sqlite3.Cursor) -> List[str]:
        """
        查找哪些集合有成员拥有指定标签
        
        遍历所有集合定义，检查是否有成员同时满足集合条件和目标标签。
        
        Args:
            tag: 要搜索的标签
            cursor: entities.db cursor
            
        Returns:
            有该标签成员的集合ID列表
        """
        categories_with_tag = []
        
        # 查询所有有该标签的非Support skill_definition实体
        cursor.execute('''
            SELECT skill_types FROM entities
            WHERE type = 'skill_definition'
              AND support = 0
              AND skill_types LIKE ?
        ''', (f'%"{tag}"%',))
        
        # 收集所有有该标签的实体的 skillTypes
        entities_with_tag = []
        for row in cursor.fetchall():
            try:
                st = json.loads(row[0]) if row[0] else []
                entities_with_tag.append(set(st))
            except (json.JSONDecodeError, TypeError):
                pass
        
        if not entities_with_tag:
            return []
        
        # 对每个集合检查：是否有实体同时匹配集合条件和目标标签
        for cat_id in CATEGORY_MATCH_ORDER:
            cat_def = CATEGORY_DEFINITIONS.get(cat_id)
            if not cat_def:
                continue
            # 间接集合也参与（因为它们是机制边的端点）
            # 但排除自身引用（避免 Trap→Trap）
            if cat_id == TAG_TO_CATEGORY.get(tag, [None])[0] if isinstance(TAG_TO_CATEGORY.get(tag), list) else None:
                continue
            
            condition = cat_def["match_condition"]
            all_tags = set(condition.get("all", []))
            any_tags = set(condition.get("any", []))
            
            for st_set in entities_with_tag:
                # 检查集合条件
                if all_tags and not all_tags.issubset(st_set):
                    continue
                if any_tags and not any_tags.intersection(st_set):
                    continue
                # 这个集合有成员拥有目标标签
                categories_with_tag.append(cat_id)
                break
        
        return categories_with_tag

    # ============================================================
    # Step 4-10: Phase B/C/D 的占位（将在后续Phase实现）
    # 注意：这些不是空实现，而是标记后续Phase补充的完整方法
    # ============================================================
    
    def step4_parse_triggers(self):
        """
        Step 4: 解析 CalcTriggers configTable → triggers 边
        
        输入: CalcTriggers.lua configTable（第881-1416行，61个条目）
        输出: triggers 边（每条连接源集合→目标集合，或实体→集合）
        
        解析逻辑：
        1. 读取 CalcTriggers.lua 全文
        2. 提取 configTable 的每个 key-value 块
        3. 从 triggerSkillCond 提取 SkillType.XXX 引用 → 确定源条件（什么触发）
        4. 从 triggeredSkillCond 提取 SkillType.XXX 引用 → 确定目标条件（触发什么）
        5. 从 ModFlag 提取武器限定 → 作为约束属性
        6. 将 SkillType 映射到集合 → 创建 triggers 边
        
        分三类条目：
        A. 有 triggerSkillCond + triggeredSkillCond → 完整触发关系
        B. 只有 triggerSkillCond → 触发源条件明确，目标由插槽决定
        C. customHandler / globalTrigger → 特殊处理或跳过
        """
        logger.info("[Step 4] 解析 CalcTriggers configTable → triggers 边...")
        
        if not self.pob_path:
            logger.warning("  pob_path 未设置，跳过 step4")
            self.stats["step4_triggers"] = 0
            return
        
        calc_triggers_path = self.pob_path / "Modules" / "CalcTriggers.lua"
        if not calc_triggers_path.exists():
            logger.warning(f"  CalcTriggers.lua 不存在: {calc_triggers_path}")
            self.stats["step4_triggers"] = 0
            return
        
        # 读取文件
        with open(calc_triggers_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 提取 configTable 块（从 "local configTable = {" 到匹配的 "}"）
        config_entries = self._extract_config_entries(content)
        logger.info(f"  解析到 {len(config_entries)} 个 configTable 条目")
        
        triggers_count = 0
        
        for entry_name, entry_code in config_entries.items():
            # 分析条目类型
            trigger_info = self._analyze_trigger_entry(entry_name, entry_code)
            
            if not trigger_info:
                continue
            
            # 跳过 globalTrigger 类型（没有明确的源→目标关系）
            if trigger_info.get("type") == "global_trigger":
                logger.debug(f"  跳过 globalTrigger: {entry_name}")
                continue
            
            # 跳过 customHandler 类型
            if trigger_info.get("type") == "custom_handler":
                logger.debug(f"  跳过 customHandler: {entry_name}")
                continue
            
            # 创建 triggers 边
            source_categories = trigger_info.get("source_categories", [])
            target_categories = trigger_info.get("target_categories", [])
            source_skill_types = trigger_info.get("source_skill_types", [])
            target_skill_types = trigger_info.get("target_skill_types", [])
            weapon_flags = trigger_info.get("weapon_flags", [])
            negated_types = trigger_info.get("negated_types", [])
            
            # 构建边属性
            properties = {
                "trigger_name": entry_name,
                "trigger_type": trigger_info.get("type", "standard"),
            }
            if source_skill_types:
                properties["source_skill_types"] = source_skill_types
            if target_skill_types:
                properties["target_skill_types"] = target_skill_types
            if weapon_flags:
                properties["weapon_requirement"] = weapon_flags
            if negated_types:
                properties["negated_types"] = negated_types
            if trigger_info.get("triggered_by_flag"):
                properties["triggered_by_flag"] = trigger_info["triggered_by_flag"]
            
            # 创建边：源集合→目标集合
            # 如果有明确的源集合和目标集合
            if source_categories and target_categories:
                for src_cat in source_categories:
                    for tgt_cat in target_categories:
                        edge_id = f"trig_{entry_name.replace(' ', '_')}_{src_cat}_to_{tgt_cat}"
                        inserted = self._insert_edge(
                            edge_id=edge_id,
                            source_id=f"cat_{src_cat}",
                            target_id=f"cat_{tgt_cat}",
                            edge_type=EdgeType.TRIGGERS,
                            properties=properties,
                            confidence=1.0,
                            source="step4_calc_triggers",
                        )
                        if inserted:
                            triggers_count += 1
            elif source_categories:
                # 只有源集合，目标是"被触发的技能"（类型由插槽决定）
                for src_cat in source_categories:
                    edge_id = f"trig_{entry_name.replace(' ', '_')}_{src_cat}"
                    # 目标为 Spell（大多数触发目标是法术），但标记为通用
                    tgt_cat = "Spell"  # 默认触发目标
                    inserted = self._insert_edge(
                        edge_id=edge_id,
                        source_id=f"cat_{src_cat}",
                        target_id=f"cat_{tgt_cat}",
                        edge_type=EdgeType.TRIGGERS,
                        properties=properties,
                        confidence=0.8,  # 稍低置信度，因为目标由插槽决定
                        source="step4_calc_triggers",
                    )
                    if inserted:
                        triggers_count += 1
            elif target_categories:
                # 只有目标集合，源是特定条件（如 globalTrigger 或特殊条件）
                for tgt_cat in target_categories:
                    edge_id = f"trig_{entry_name.replace(' ', '_')}_to_{tgt_cat}"
                    inserted = self._insert_edge(
                        edge_id=edge_id,
                        source_id=f"cat_MetaTriggerEnergy",  # 默认源为 Meta
                        target_id=f"cat_{tgt_cat}",
                        edge_type=EdgeType.TRIGGERS,
                        properties=properties,
                        confidence=0.7,
                        source="step4_calc_triggers",
                    )
                    if inserted:
                        triggers_count += 1
        
        self.graph_conn.commit()
        self.stats["step4_triggers"] = triggers_count
        logger.info(f"  创建 {triggers_count} 条 triggers 边")
    
    def _extract_config_entries(self, lua_content: str) -> Dict[str, str]:
        """
        从 CalcTriggers.lua 提取 configTable 的所有条目
        
        返回: {条目名: 条目代码块}
        """
        entries = {}
        
        # 找到 configTable 块的起始
        config_start = lua_content.find("local configTable = {")
        if config_start < 0:
            logger.warning("  未找到 configTable 定义")
            return entries
        
        # 从 configTable 开始，逐个提取 ["xxx"] = function 块
        # 使用正则匹配每个条目的开始
        entry_pattern = re.compile(
            r'\["([^"]+)"\]\s*=\s*function',
            re.MULTILINE
        )
        
        # 找到所有条目的位置
        matches = list(entry_pattern.finditer(lua_content, config_start))
        
        for i, match in enumerate(matches):
            entry_name = match.group(1)
            start_pos = match.start()
            
            # 条目的结束位置：下一个条目的开始 或 configTable 的结束
            if i + 1 < len(matches):
                end_pos = matches[i + 1].start()
            else:
                # 最后一个条目：找到 configTable 的闭合 }
                # 从最后一个条目开始向后搜索，找到独立的 }
                end_pos = lua_content.find("\n}", match.end())
                if end_pos < 0:
                    end_pos = len(lua_content)
                else:
                    end_pos += 2  # 包含 \n}
            
            entry_code = lua_content[start_pos:end_pos].strip()
            entries[entry_name] = entry_code
        
        return entries
    
    def _analyze_trigger_entry(self, name: str, code: str) -> Optional[Dict[str, Any]]:
        """
        分析单个 configTable 条目，提取触发关系信息
        
        返回:
            {
                "type": "standard" | "global_trigger" | "custom_handler" | "conditional",
                "source_skill_types": [...],   # triggerSkillCond 中的 SkillType
                "target_skill_types": [...],   # triggeredSkillCond 中的 SkillType
                "source_categories": [...],    # 映射后的源集合
                "target_categories": [...],    # 映射后的目标集合
                "weapon_flags": [...],         # ModFlag 武器限定
                "negated_types": [...],        # 否定的 SkillType（not xxx）
                "triggered_by_flag": str,      # triggeredByXxx 标记
            }
        """
        result = {
            "source_skill_types": [],
            "target_skill_types": [],
            "source_categories": [],
            "target_categories": [],
            "weapon_flags": [],
            "negated_types": [],
        }
        
        # 检测 customHandler
        if "customHandler" in code:
            result["type"] = "custom_handler"
            return result
        
        # 检测 globalTrigger（只设置 globalTrigger 且没有 triggerSkillCond）
        if "globalTrigger = true" in code and "triggerSkillCond" not in code:
            result["type"] = "global_trigger"
            return result
        
        # 检测特殊双路径条目（automation/call to arms/autoexertion）
        # 这些条目用 grantedEffect.name == "XXX" 匹配自身
        name_match_pattern = re.compile(
            r'grantedEffect\.name\s*==\s*"([^"]+)"'
        )
        name_matches = name_match_pattern.findall(code)
        
        # 提取 triggerSkillCond 块中的 SkillType
        trigger_cond_match = re.search(
            r'triggerSkillCond\s*=\s*function\s*\(.*?\)(.*?)(?:end[,\s}])',
            code,
            re.DOTALL
        )
        
        if trigger_cond_match:
            cond_code = trigger_cond_match.group(1)
            
            # 提取 SkillType.XXX 引用
            skill_types = re.findall(r'SkillType\.(\w+)', cond_code)
            
            # 检测否定（not skill.skillTypes[SkillType.XXX]）
            negated = re.findall(r'not\s+skill\.skillTypes\[SkillType\.(\w+)\]', cond_code)
            
            # 检测 skillFlags 引用（如 skill.skillFlags.totem）
            skill_flags = re.findall(r'skill\.skillFlags\.(\w+)', cond_code)
            
            # 排除否定的类型
            positive_types = [st for st in skill_types if st not in negated]
            
            result["source_skill_types"] = positive_types
            result["negated_types"] = negated
            
            # 提取 ModFlag（武器限定）
            mod_flags = re.findall(r'ModFlag\.(\w+)', cond_code)
            result["weapon_flags"] = mod_flags
            
            # 处理 skillFlags（如 totem）
            if skill_flags:
                for flag in skill_flags:
                    if flag == "totem":
                        result["source_skill_types"].append("SummonsTotem")
            
            # 如果 triggerSkillCond 返回 true（无过滤），标记为通用
            if "return true" in cond_code and not positive_types:
                result["source_skill_types"] = ["ANY"]
        
        # 提取 triggeredSkillCond 块中的 SkillType
        triggered_cond_match = re.search(
            r'triggeredSkillCond\s*=\s*function\s*\(.*?\)(.*?)(?:end[,\s}])',
            code,
            re.DOTALL
        )
        
        if triggered_cond_match:
            tcond_code = triggered_cond_match.group(1)
            target_types = re.findall(r'SkillType\.(\w+)', tcond_code)
            result["target_skill_types"] = target_types
            
            # 提取 triggeredByXxx 标记
            triggered_by = re.findall(r'triggeredBy(\w+)', tcond_code)
            if triggered_by:
                result["triggered_by_flag"] = triggered_by[0]
        
        # SkillType → 集合映射
        result["source_categories"] = self._skill_types_to_categories(
            result["source_skill_types"], result["negated_types"]
        )
        result["target_categories"] = self._skill_types_to_categories(
            result["target_skill_types"], []
        )
        
        # 确定条目类型
        if not trigger_cond_match and not triggered_cond_match:
            # 没有任何条件函数
            if "globalTrigger" in code:
                result["type"] = "global_trigger"
            elif name_matches:
                result["type"] = "self_reference"
            else:
                result["type"] = "unconditional"
        else:
            result["type"] = "standard"
        
        return result
    
    def _skill_types_to_categories(self, skill_types: List[str],
                                    negated_types: List[str]) -> List[str]:
        """
        将 SkillType 列表映射到集合列表
        
        映射规则：
        - Attack → [MeleeAttack, RangedAttack]（如果没有 Melee/Ranged 进一步限定）
        - Attack + Melee → [MeleeAttack]
        - Melee（单独）→ [MeleeAttack]
        - Spell → [Spell]
        - Hex → [Curse]（Hex 在 SkillType 空间 = AppliesCurse）
        - Damage → []（太宽泛，不映射到具体集合）
        - RangedAttack → [RangedAttack]
        - SummonsTotem → [Totem]
        - ANY → 不映射（保持空，表示全部技能）
        
        组合逻辑：
        - triggerSkillCond 中 SkillType.A or SkillType.B → 合并映射
        - triggerSkillCond 中 SkillType.A and SkillType.B → 交集映射
        
        简化处理：这里将所有出现的 SkillType 都当作 OR 组合
        （因为 configTable 中大部分用 or 连接，且 and 的情况通常是 Attack and Melee → MeleeAttack）
        """
        if not skill_types or "ANY" in skill_types:
            return []
        
        categories = set()
        has_attack = "Attack" in skill_types
        has_melee = "Melee" in skill_types
        has_ranged = "RangedAttack" in skill_types or "Ranged" in skill_types
        has_damage = "Damage" in skill_types
        has_spell = "Spell" in skill_types
        has_hex = "Hex" in skill_types
        has_totem = "SummonsTotem" in skill_types
        
        # Attack 和 Melee 同时出现 → 特指 MeleeAttack
        # Attack 单独 → MeleeAttack + RangedAttack
        # Melee 单独 → MeleeAttack
        if has_attack and has_melee:
            categories.add("MeleeAttack")
        elif has_attack and has_ranged:
            categories.add("RangedAttack")
        elif has_attack:
            # Attack 单独 → 同时映射近战和远程
            categories.add("MeleeAttack")
            categories.add("RangedAttack")
        elif has_melee:
            categories.add("MeleeAttack")
        
        if has_ranged and not has_attack:
            categories.add("RangedAttack")
        
        # Spell → Spell 集合
        if has_spell:
            categories.add("Spell")
        
        # Hex → Curse（Hex 是 POB 对 AppliesCurse 的别名）
        if has_hex:
            categories.add("Curse")
        
        # Damage（单独）→ 太宽泛，但与 Attack 组合 (Damage or Attack) 是常见模式
        # 这种情况下 Attack 已处理，Damage 主要扩展覆盖面
        if has_damage and not has_attack and not has_melee:
            # Damage 单独出现时，可覆盖 MeleeAttack + RangedAttack + Spell
            # 但大多数 configTable 中 Damage or Attack → 本质是 Attack 类
            categories.add("MeleeAttack")
            categories.add("RangedAttack")
        
        # SummonsTotem → Totem
        if has_totem:
            categories.add("Totem")
        
        # 移除被否定的集合
        for neg_type in negated_types:
            neg_cats = TAG_TO_CATEGORY.get(neg_type)
            if isinstance(neg_cats, list):
                for nc in neg_cats:
                    categories.discard(nc)
        
        return sorted(categories)
    
    def step5_parse_energy(self):
        """
        Step 5: 解析 centienergy stat → produces_energy 边
        
        输入: Data/Skills/act_*.lua 和 other.lua 中 Meta 技能的 constantStats
        输出: produces_energy 边（源集合→Meta技能实体/MetaTriggerEnergy集合）
        
        处理流程：
        1. 搜索所有 act_*.lua 和 other.lua 中的 centienergy stat
        2. 解析 stat 名称，提取产能条件（on_crit / on_melee_kill / on_block 等）
        3. 确定产能条件对应的源集合
        4. 查找对应的 Meta 技能实体（在 entities.db 中）
        5. 创建 produces_energy 边：源集合 → MetaTriggerEnergy 集合
        
        centienergy stat 名称模式：
          {prefix}_gain_X_centienergy_{suffix}
          prefix 编码了技能名，suffix 编码了产能条件
        
        产能条件→源集合映射（根据游戏机制和描述确认）：
        - on_crit → 暴击（Attack + Spell 都能暴击）
        - on_melee_kill → 近战击杀 → MeleeAttack
        - on_block → 格挡 → 被动行为（无特定源集合）
        - on_stun / on_heavy_stun → 近战眩晕 → MeleeAttack
        - on_hit (melee context) → 近战命中 → MeleeAttack
        - per_unit_travelled → 翻滚距离 → 被动行为
        - per_monster_power_on_ignite/shock/freeze → 异常状态 → Spell + Attack
        - per_mana_spent / per_10ms_base_cast_time → 施法 → Spell
        - per_charm_charge_used → 使用Charm → 被动行为
        """
        logger.info("[Step 5] 解析 centienergy stat → produces_energy 边...")
        
        if not self.pob_path:
            logger.warning("  pob_path 未设置，跳过 step5")
            self.stats["step5_produces_energy"] = 0
            return
        
        # 收集所有 centienergy 信息
        energy_entries = self._collect_centienergy_stats()
        logger.info(f"  发现 {len(energy_entries)} 个 Meta 技能的能量定义")
        
        energy_count = 0
        
        for entry in energy_entries:
            skill_key = entry["skill_key"]
            skill_name = entry["skill_name"]
            energy_conditions = entry["energy_conditions"]
            skill_types = entry.get("skill_types", [])
            is_invocation = "Invocation" in skill_types
            
            # 确定该 Meta 技能所属的集合
            meta_category = "Invocation" if is_invocation else "MetaTriggerEnergy"
            
            # 查找实体节点（可能在 step2 已创建）
            entity_id = self._find_entity_id_by_key(skill_key)
            
            # 对每个产能条件创建 produces_energy 边
            for condition in energy_conditions:
                source_categories = condition["source_categories"]
                condition_name = condition["condition"]
                stat_name = condition["stat_name"]
                value = condition["value"]
                
                properties = {
                    "meta_skill": skill_name,
                    "meta_skill_key": skill_key,
                    "stat_name": stat_name,
                    "centienergy_value": value,
                    "condition": condition_name,
                    "is_invocation": is_invocation,
                }
                
                if source_categories:
                    # 有明确源集合 → 源集合 produces_energy Meta集合
                    for src_cat in source_categories:
                        edge_id = f"energy_{src_cat}_{condition_name}_{skill_key}"
                        inserted = self._insert_edge(
                            edge_id=edge_id,
                            source_id=f"cat_{src_cat}",
                            target_id=f"cat_{meta_category}",
                            edge_type=EdgeType.PRODUCES_ENERGY,
                            properties=properties,
                            confidence=1.0,
                            source="step5_centienergy",
                        )
                        if inserted:
                            energy_count += 1
                else:
                    # 无明确源集合（被动行为如格挡/翻滚/使用Charm）
                    # 创建一个通用边，源为虚拟"被动行为"
                    # 由于没有"被动行为"集合，直接将边挂在 Meta 集合上作为属性
                    edge_id = f"energy_passive_{condition_name}_{skill_key}"
                    properties["source_type"] = "passive_behavior"
                    inserted = self._insert_edge(
                        edge_id=edge_id,
                        source_id=f"cat_{meta_category}",
                        target_id=f"cat_{meta_category}",
                        edge_type=EdgeType.PRODUCES_ENERGY,
                        properties=properties,
                        confidence=0.9,
                        source="step5_centienergy",
                    )
                    if inserted:
                        energy_count += 1
        
        self.graph_conn.commit()
        self.stats["step5_produces_energy"] = energy_count
        logger.info(f"  创建 {energy_count} 条 produces_energy 边")
    
    def _collect_centienergy_stats(self) -> List[Dict[str, Any]]:
        """
        从 POB 技能文件中收集所有 centienergy stat 定义
        
        扫描文件：act_str.lua, act_int.lua, act_dex.lua, other.lua
        
        返回: [{
            "skill_key": "MetaCastOnCritPlayer",
            "skill_name": "Cast on Critical",
            "skill_types": [...],
            "energy_conditions": [{
                "stat_name": "cast_on_crit_gain_X_centienergy_per_monster_power_on_crit",
                "value": 100,
                "condition": "on_crit",
                "source_categories": ["MeleeAttack", "RangedAttack", "Spell"],
            }]
        }]
        """
        skills_dir = self.pob_path / "Data" / "Skills"
        target_files = ["act_str.lua", "act_int.lua", "act_dex.lua", "other.lua"]
        
        energy_entries = []
        
        # centienergy stat 的条件→集合映射
        # 根据游戏描述和 CalcTriggers.lua 的 triggerSkillCond 交叉验证
        condition_to_categories = {
            # 近战行为
            "on_melee_kill": ["MeleeAttack"],
            "on_stun": ["MeleeAttack"],
            "on_heavy_stun": ["MeleeAttack"],
            # 命中行为（特定武器上下文）
            # on_hit 在 Lightning/Fire spell on hit 上下文中特指近战命中
            "on_hit": ["MeleeAttack"],
            # 暴击（攻击和法术都能暴击）
            "on_crit": ["MeleeAttack", "RangedAttack", "Spell"],
            # 元素异常（攻击和法术都能施加）
            "on_ignite": ["MeleeAttack", "RangedAttack", "Spell"],
            "on_shock": ["MeleeAttack", "RangedAttack", "Spell"],
            "on_freeze": ["MeleeAttack", "RangedAttack", "Spell"],
            # 格挡、翻滚、使用Charm → 被动行为，无特定源集合
            "on_block": [],
            "per_unit_travelled": [],
            "per_charm_charge_used": [],
            # 施法相关（Spellslinger）
            "per_10ms_base_cast_time": ["Spell"],
        }
        
        for filename in target_files:
            filepath = skills_dir / filename
            if not filepath.exists():
                continue
            
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 查找所有包含 centienergy 的技能块
            # 首先找到所有技能定义的位置
            skill_blocks = self._extract_skill_blocks_with_centienergy(content)
            
            for block in skill_blocks:
                skill_key = block["skill_key"]
                skill_name = block.get("skill_name", skill_key)
                skill_types = block.get("skill_types", [])
                
                # 提取所有 centienergy stat
                stats = block["centienergy_stats"]
                
                conditions = []
                for stat_name, value in stats:
                    condition = self._parse_centienergy_condition(stat_name)
                    source_cats = condition_to_categories.get(condition, [])
                    conditions.append({
                        "stat_name": stat_name,
                        "value": value,
                        "condition": condition,
                        "source_categories": source_cats,
                    })
                
                if conditions:
                    energy_entries.append({
                        "skill_key": skill_key,
                        "skill_name": skill_name,
                        "skill_types": skill_types,
                        "energy_conditions": conditions,
                        "source_file": filename,
                    })
        
        return energy_entries
    
    def _extract_skill_blocks_with_centienergy(self, lua_content: str) -> List[Dict[str, Any]]:
        """
        从 Lua 技能文件中提取包含 centienergy 的技能块
        
        解析策略：
        1. 找到所有 skills["XXX"] = { 块
        2. 检查每个块是否包含 centienergy
        3. 提取 skillTypes、constantStats 中的 centienergy stat
        """
        blocks = []
        
        # 正则：匹配 skills["XXX"] = { 开头
        skill_start_pattern = re.compile(
            r'skills\["(\w+)"\]\s*=\s*\{',
            re.MULTILINE
        )
        
        matches = list(skill_start_pattern.finditer(lua_content))
        
        for i, match in enumerate(matches):
            skill_key = match.group(1)
            start = match.start()
            
            # 确定块的范围（到下一个 skills[""] 或文件末尾）
            if i + 1 < len(matches):
                end = matches[i + 1].start()
            else:
                end = len(lua_content)
            
            block_text = lua_content[start:end]
            
            # 检查是否包含 centienergy
            if "centienergy" not in block_text:
                continue
            
            # 提取技能名称（name 字段）
            name_match = re.search(r'name\s*=\s*"([^"]+)"', block_text)
            skill_name = name_match.group(1) if name_match else skill_key
            
            # 提取 skillTypes
            skill_types = []
            st_pattern = re.compile(r'SkillType\.(\w+)')
            # 找到 skillTypes = { ... } 块
            st_block_match = re.search(r'skillTypes\s*=\s*\{([^}]+)\}', block_text)
            if st_block_match:
                skill_types = st_pattern.findall(st_block_match.group(1))
            
            # 提取 centienergy stat 和值
            # Lua 格式: { "stat_name_centienergy_xxx", value }
            # 匹配数组风格表: { "...", number }
            centienergy_pattern = re.compile(
                r'\{\s*"([^"]*centienergy[^"]*)"\s*,\s*([\d.]+)\s*\}'
            )
            centienergy_stats = centienergy_pattern.findall(block_text)
            
            if centienergy_stats:
                blocks.append({
                    "skill_key": skill_key,
                    "skill_name": skill_name,
                    "skill_types": skill_types,
                    "centienergy_stats": [(name, float(val)) for name, val in centienergy_stats],
                })
        
        return blocks
    
    def _parse_centienergy_condition(self, stat_name: str) -> str:
        """
        从 centienergy stat 名称中解析产能条件
        
        stat 名称模式：
          {prefix}_gain_X_centienergy_{suffix}
          
        suffix 编码了条件：
          per_monster_power_on_crit → on_crit
          per_monster_power_on_melee_kill → on_melee_kill
          on_block → on_block
          per_monster_power_on_stun → on_stun
          per_monster_power_on_heavy_stun → on_heavy_stun
          per_monster_power_on_hit → on_hit
          per_unit_travelled_while_dodge_rolling → per_unit_travelled
          per_monster_power_on_ignite → on_ignite
          per_monster_power_on_shock → on_shock
          per_monster_power_on_freeze → on_freeze
          per_10ms_base_cast_time → per_10ms_base_cast_time
          per_charm_charge_used_on_using_charm → per_charm_charge_used
        """
        # 提取 centienergy 后面的 suffix
        ce_idx = stat_name.find("centienergy")
        if ce_idx < 0:
            return "unknown"
        
        suffix = stat_name[ce_idx + len("centienergy"):]
        # 去掉前导下划线
        suffix = suffix.lstrip("_")
        
        # 优先匹配更具体的模式
        condition_patterns = [
            ("per_monster_power_on_heavy_stun", "on_heavy_stun"),
            ("per_monster_power_on_melee_kill", "on_melee_kill"),
            ("per_monster_power_on_ignite", "on_ignite"),
            ("per_monster_power_on_shock", "on_shock"),
            ("per_monster_power_on_freeze", "on_freeze"),
            ("per_monster_power_on_crit", "on_crit"),
            ("per_monster_power_on_stun", "on_stun"),
            ("per_monster_power_on_hit", "on_hit"),
            ("per_unit_travelled", "per_unit_travelled"),
            ("per_10ms_base_cast_time", "per_10ms_base_cast_time"),
            ("per_charm_charge_used", "per_charm_charge_used"),
            ("on_block", "on_block"),
            ("on_melee_kill", "on_melee_kill"),
            ("on_hit", "on_hit"),
        ]
        
        for pattern, condition in condition_patterns:
            if pattern in suffix:
                return condition
        
        return "unknown"
    
    def _find_entity_id_by_key(self, skill_key: str) -> Optional[str]:
        """
        在 entities.db 中查找 Meta 技能的实体 ID
        
        尝试匹配策略：
        1. 直接匹配 id = skill_key
        2. 模糊匹配 name LIKE skill_key
        """
        if not self.entities_conn:
            return None
        
        cursor = self.entities_conn.cursor()
        
        # 精确匹配
        cursor.execute('SELECT id FROM entities WHERE id = ?', (skill_key,))
        row = cursor.fetchone()
        if row:
            return row[0]
        
        # 模糊匹配（去掉 Player 后缀等）
        clean_key = skill_key.replace("Player", "").replace("Meta", "")
        cursor.execute(
            'SELECT id FROM entities WHERE id LIKE ? LIMIT 1',
            (f'%{clean_key}%',)
        )
        row = cursor.fetchone()
        if row:
            return row[0]
        
        return None
    
    def step6_extract_blocks_when(self):
        """
        Step 6: 四层 blocks_when 约束提取
        
        Layer 1: entities.db exclude_skill_types → 归纳为集合级约束
        Layer 2: SkillStatMap.lua cannot/never/dealNo stat → flag 型约束
        Layer 3: 预定义的 Calc 代码阻断模式（一次性固化）
        Layer 4: entities.db stat_descriptions 中 cannot/instead/immune 文本
        
        每个约束创建一个 constraint 节点 + blocks_when 边
        """
        logger.info("[Step 6] 提取 blocks_when 约束...")
        
        total_count = 0
        
        # Layer 1: exclude_skill_types
        count1 = self._step6_layer1_exclude_skill_types()
        total_count += count1
        logger.info(f"  Layer 1 (exclude_skill_types): {count1} 条")
        
        # Layer 2: SkillStatMap cannot stat
        count2 = self._step6_layer2_skillstatmap_cannot()
        total_count += count2
        logger.info(f"  Layer 2 (SkillStatMap cannot): {count2} 条")
        
        # Layer 3: Calc 代码预定义阻断
        count3 = self._step6_layer3_calc_code_blocks()
        total_count += count3
        logger.info(f"  Layer 3 (Calc code): {count3} 条")
        
        # Layer 4: stat_descriptions cannot/instead/immune
        count4 = self._step6_layer4_stat_descriptions()
        total_count += count4
        logger.info(f"  Layer 4 (stat_descriptions): {count4} 条")
        
        self.graph_conn.commit()
        self.stats["step6_blocks_when"] = total_count
        logger.info(f"  总计 {total_count} 条 blocks_when 约束")
    
    def _step6_layer1_exclude_skill_types(self) -> int:
        """
        Layer 1: 从 entities.db exclude_skill_types 提取集合级阻断约束
        
        逻辑：将相同排除模式的 Support 合并为集合级约束
        例：100个 Support 排除 Triggered → "Triggered blocks 大多数Support辅助"
        """
        cursor = self.entities_conn.cursor()
        
        # 查询所有有 exclude_skill_types 的 Support
        cursor.execute('''
            SELECT id, name, exclude_skill_types
            FROM entities
            WHERE type = 'skill_definition'
              AND support = 1
              AND exclude_skill_types IS NOT NULL
              AND exclude_skill_types != '[]'
        ''')
        rows = cursor.fetchall()
        
        # 归纳：按排除标签聚合
        tag_exclusion_counts = {}  # {tag: count}
        for row in rows:
            try:
                excluded_tags = json.loads(row[2]) if row[2] else []
            except (json.JSONDecodeError, TypeError):
                continue
            
            for tag in excluded_tags:
                if tag in ('AND', 'OR', 'NOT'):
                    continue
                tag_exclusion_counts[tag] = tag_exclusion_counts.get(tag, 0) + 1
        
        # 创建约束节点和边
        count = 0
        for tag, support_count in tag_exclusion_counts.items():
            if support_count < 3:
                # 少于3个Support有这个排除 → 不归纳（可能是特例）
                continue
            
            constraint_id = f"con_exclude_{tag.lower()}"
            
            # 创建 constraint 节点
            self._insert_node(
                node_id=constraint_id,
                node_type=NodeType.CONSTRAINT,
                name=f"排除 {tag}",
                properties={
                    "constraint_type": "exclude_skill_type",
                    "excluded_tag": tag,
                    "support_count": support_count,
                    "layer": 1,
                    "description": f"{support_count}个Support排除{tag}标签的技能",
                },
                source="step6_layer1",
            )
            
            # 确定被阻断的集合（哪些集合的成员会获得该标签）
            blocked_categories = TAG_TO_CATEGORY.get(tag)
            if blocked_categories is None:
                # 非集合标签（维度标签如 Triggered, Persistent）
                # 创建通用 blocks_when 边
                edge_id = f"bw_{constraint_id}_general"
                self._insert_edge(
                    edge_id=edge_id,
                    source_id=constraint_id,
                    target_id=constraint_id,  # 自引用表示通用约束
                    edge_type=EdgeType.BLOCKS_WHEN,
                    properties={
                        "condition_tag": tag,
                        "scope": "general",
                        "support_count": support_count,
                        "description": f"有{tag}标签时，{support_count}个Support不可用",
                    },
                    source="step6_layer1",
                )
                count += 1
            elif isinstance(blocked_categories, list):
                # 映射到具体集合
                for cat_id in blocked_categories:
                    edge_id = f"bw_{constraint_id}_{cat_id}"
                    self._insert_edge(
                        edge_id=edge_id,
                        source_id=constraint_id,
                        target_id=f"cat_{cat_id}",
                        edge_type=EdgeType.BLOCKS_WHEN,
                        properties={
                            "condition_tag": tag,
                            "scope": "category",
                            "support_count": support_count,
                            "description": f"有{tag}标签时，{support_count}个Support对{cat_id}不可用",
                        },
                        source="step6_layer1",
                    )
                    count += 1
        
        return count
    
    def _step6_layer2_skillstatmap_cannot(self) -> int:
        """
        Layer 2: 从 SkillStatMap.lua 提取 cannot/never/dealNo flag 型约束
        
        解析 SkillStatMap.lua 中所有包含 flag("Cannot"/"Never"/"DealNo"/"NoXxx"/"XxxImmune")
        的 stat 映射，创建引擎级约束。
        """
        if not self.pob_path:
            return 0
        
        ssm_path = self.pob_path / "Data" / "SkillStatMap.lua"
        if not ssm_path.exists():
            return 0
        
        with open(ssm_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 提取所有带阻止语义的 stat 条目
        # 模式1：flag("CannotXxx") / flag("NeverXxx") / flag("DealNoXxx") / flag("NoXxxRecharge") / flag("XxxImmune")
        # 模式2：value = -100（完全消除）
        
        count = 0
        
        # 解析每个 stat 条目块
        stat_pattern = re.compile(
            r'\["([^"]+)"\]\s*=\s*\{(.*?)\}',
            re.DOTALL
        )
        
        blocking_flag_pattern = re.compile(
            r'flag\("(Cannot\w+|Never\w+|DealNo\w+|No\w+Recharge|No\w+Regen|\w+Immune|NoCrit\w+|NoAdditional\w+|NoRepeat\w+)"\)'
        )
        
        value_minus_100_pattern = re.compile(r'value\s*=\s*-100')
        
        for match in stat_pattern.finditer(content):
            stat_name = match.group(1)
            stat_body = match.group(2)
            
            # 检查是否有阻止 flag
            blocking_flags = blocking_flag_pattern.findall(stat_body)
            has_value_minus_100 = value_minus_100_pattern.search(stat_body)
            
            if not blocking_flags and not has_value_minus_100:
                continue
            
            constraint_id = f"con_ssm_{stat_name}"
            
            # 确定约束效果
            effects = []
            if blocking_flags:
                effects.extend(blocking_flags)
            if has_value_minus_100:
                # 提取被消除的属性
                mod_name_match = re.search(r'mod\("(\w+)"', stat_body)
                if mod_name_match:
                    effects.append(f"Eliminates_{mod_name_match.group(1)}")
            
            # 创建 constraint 节点
            self._insert_node(
                node_id=constraint_id,
                node_type=NodeType.CONSTRAINT,
                name=f"SSM: {stat_name}",
                properties={
                    "constraint_type": "engine_stat",
                    "stat_name": stat_name,
                    "flags": effects,
                    "layer": 2,
                    "description": f"引擎stat {stat_name} 阻止 {', '.join(effects)}",
                },
                source="step6_layer2",
            )
            
            # 创建 blocks_when 边（自引用，表示引擎级约束）
            edge_id = f"bw_{constraint_id}"
            self._insert_edge(
                edge_id=edge_id,
                source_id=constraint_id,
                target_id=constraint_id,
                edge_type=EdgeType.BLOCKS_WHEN,
                properties={
                    "stat_name": stat_name,
                    "flags": effects,
                    "scope": "engine",
                    "description": f"引擎级: {stat_name} → {', '.join(effects)}",
                },
                source="step6_layer2",
            )
            count += 1
        
        return count
    
    def _step6_layer3_calc_code_blocks(self) -> int:
        """
        Layer 3: 预定义的 Calc 代码阻断模式
        
        这些是从 CalcOffence/CalcPerform/CalcTriggers/CalcDefence 中
        一次性提取并固化的阻断规则。代码中的 if-not 模式表达了
        "某些条件下某些功能被阻断"。
        """
        # 固化的 Calc 代码阻断规则
        calc_blocks = [
            {
                "id": "con_calc_trap_mine_totem_no_leech",
                "name": "陷阱/地雷/图腾无法吸取",
                "tags": ["Trapped", "RemoteMined", "UsedByTotem"],
                "blocked": "leech",
                "source_file": "CalcOffence.lua",
                "description": "trap/mine/totem投放的技能不能吸取生命/魔力",
            },
            {
                "id": "con_calc_trap_mine_totem_no_on_hit_recovery",
                "name": "陷阱/地雷/图腾无命中回复",
                "tags": ["Trapped", "RemoteMined", "UsedByTotem"],
                "blocked": "on_hit_recovery",
                "source_file": "CalcOffence.lua",
                "description": "trap/mine/totem投放的技能不触发命中回复",
            },
            {
                "id": "con_calc_trap_mine_totem_no_on_kill_recovery",
                "name": "陷阱/地雷/图腾无击杀回复",
                "tags": ["Trapped", "RemoteMined", "UsedByTotem"],
                "blocked": "on_kill_recovery",
                "source_file": "CalcOffence.lua",
                "description": "trap/mine/totem投放的技能不触发击杀回复",
            },
            {
                "id": "con_calc_trap_mine_totem_triggered_no_recently",
                "name": "陷阱/地雷/图腾/触发无'最近'条件",
                "tags": ["Trapped", "RemoteMined", "UsedByTotem", "Triggered"],
                "blocked": "recently_conditions",
                "source_file": "CalcPerform.lua",
                "description": "trap/mine/totem/triggered技能不满足'最近'条件",
            },
            {
                "id": "con_calc_triggered_no_trigger_source",
                "name": "已触发技能不能作为触发源",
                "tags": ["Triggered"],
                "blocked": "trigger_source_eligibility",
                "source_file": "CalcTriggers.lua",
                "description": "已被触发的技能不能再作为其他触发的源",
            },
            {
                "id": "con_calc_totem_no_buff_to_player",
                "name": "图腾技能buff不传递给玩家",
                "tags": ["UsedByTotem"],
                "blocked": "buff_transfer_to_player",
                "source_file": "CalcPerform.lua",
                "description": "图腾使用的技能的buff效果不传递给玩家",
            },
            {
                "id": "con_calc_triggered_no_energy",
                "name": "已触发技能不产生能量",
                "tags": ["Triggered"],
                "blocked": "energy_generation",
                "source_file": "CalcTriggers.lua",
                "description": "已被触发的技能不能为Meta技能产生能量",
            },
            {
                "id": "con_calc_persistent_no_trigger",
                "name": "持续效果不被触发机制影响",
                "tags": ["Persistent"],
                "blocked": "trigger_interaction",
                "source_file": "CalcTriggers.lua",
                "description": "持续效果(光环/先驱等)不参与触发计算",
            },
            {
                "id": "con_calc_meta_no_support_as_active",
                "name": "Meta技能不被普通Support增强",
                "tags": ["Meta"],
                "blocked": "generic_support",
                "source_file": "CalcActiveSkill.lua",
                "description": "Meta技能本身不能被大多数普通Support宝石增强",
            },
            {
                "id": "con_calc_minion_no_direct_player_stat",
                "name": "召唤物不继承玩家直接属性",
                "tags": ["Minion"],
                "blocked": "direct_player_stats",
                "source_file": "CalcActiveSkill.lua",
                "description": "召唤物有独立的stat系统，不直接继承玩家属性",
            },
            {
                "id": "con_calc_channel_no_repeat",
                "name": "引导技能不能重复",
                "tags": ["Channel"],
                "blocked": "repeat",
                "source_file": "CalcActiveSkill.lua",
                "description": "引导类技能不能获得重复次数加成",
            },
            {
                "id": "con_calc_trap_mine_no_direct_damage_to_player",
                "name": "陷阱/地雷伤害不算玩家伤害",
                "tags": ["Trapped", "RemoteMined"],
                "blocked": "player_damage_attribution",
                "source_file": "CalcOffence.lua",
                "description": "陷阱/地雷造成的伤害不算作玩家直接造成的伤害",
            },
        ]
        
        count = 0
        for block in calc_blocks:
            constraint_id = block["id"]
            
            self._insert_node(
                node_id=constraint_id,
                node_type=NodeType.CONSTRAINT,
                name=block["name"],
                properties={
                    "constraint_type": "calc_code",
                    "condition_tags": block["tags"],
                    "blocked_function": block["blocked"],
                    "source_file": block["source_file"],
                    "layer": 3,
                    "description": block["description"],
                },
                source="step6_layer3",
            )
            
            # 创建 blocks_when 边
            edge_id = f"bw_{constraint_id}"
            self._insert_edge(
                edge_id=edge_id,
                source_id=constraint_id,
                target_id=constraint_id,
                edge_type=EdgeType.BLOCKS_WHEN,
                properties={
                    "condition_tags": block["tags"],
                    "blocked": block["blocked"],
                    "scope": "calc_code",
                    "description": block["description"],
                },
                source="step6_layer3",
            )
            count += 1
        
        return count
    
    def _step6_layer4_stat_descriptions(self) -> int:
        """
        Layer 4: 从 entities.db stat_descriptions 提取 cannot/instead/immune 文本约束
        
        扫描天赋节点和装备词缀的描述文本，找到表达阻断/替换/免疫的条目。
        """
        cursor = self.entities_conn.cursor()
        
        # 查询所有有 stat_descriptions 的实体
        cursor.execute('''
            SELECT id, name, type, stat_descriptions
            FROM entities
            WHERE stat_descriptions IS NOT NULL
              AND stat_descriptions != '[]'
              AND stat_descriptions != 'null'
              AND type IN ('passive_node', 'ascendancy_node', 'mod_affix', 'unique_item')
        ''')
        rows = cursor.fetchall()
        
        # 关键词模式
        blocking_patterns = [
            (re.compile(r'[Cc]annot\s+(.+?)(?:\.|$)', re.IGNORECASE), "cannot"),
            (re.compile(r'[Ii]mmune\s+to\s+(.+?)(?:\.|$)', re.IGNORECASE), "immune"),
            (re.compile(r'[Nn]ever\s+(.+?)(?:\.|$)', re.IGNORECASE), "never"),
            (re.compile(r'(.+?)\s+instead\s+of\s+(.+?)(?:\.|$)', re.IGNORECASE), "instead"),
            (re.compile(r'[Yy]ou\s+can(?:no|\')?t\s+(.+?)(?:\.|$)', re.IGNORECASE), "cannot"),
            (re.compile(r'[Dd]isable[sd]?\s+(.+?)(?:\.|$)', re.IGNORECASE), "disable"),
        ]
        
        count = 0
        seen_descriptions = set()  # 去重
        
        for row in rows:
            entity_id = row[0]
            entity_name = row[1] or entity_id
            entity_type = row[2]
            
            try:
                descriptions = json.loads(row[3]) if row[3] else []
            except (json.JSONDecodeError, TypeError):
                continue
            
            if not isinstance(descriptions, list):
                continue
            
            for desc in descriptions:
                if not isinstance(desc, str):
                    continue
                
                desc_lower = desc.lower()
                
                # 跳过纯数值描述（如 "+10% increased damage"）
                if not any(kw in desc_lower for kw in ['cannot', 'immune', 'never', 'instead', "can't", 'disable']):
                    continue
                
                # 去重（同一描述可能出现在多个实体上）
                desc_key = desc_lower.strip()
                if desc_key in seen_descriptions:
                    continue
                seen_descriptions.add(desc_key)
                
                # 匹配阻断模式
                for pattern, block_type in blocking_patterns:
                    match = pattern.search(desc)
                    if match:
                        # 创建约束
                        constraint_id = f"con_desc_{hash(desc_key) & 0xFFFFFF:06x}"
                        
                        self._insert_node(
                            node_id=constraint_id,
                            node_type=NodeType.CONSTRAINT,
                            name=f"描述约束: {desc[:60]}",
                            properties={
                                "constraint_type": "stat_description",
                                "block_type": block_type,
                                "description_text": desc,
                                "source_entity": entity_id,
                                "source_entity_name": entity_name,
                                "source_entity_type": entity_type,
                                "layer": 4,
                            },
                            source="step6_layer4",
                        )
                        
                        edge_id = f"bw_{constraint_id}"
                        self._insert_edge(
                            edge_id=edge_id,
                            source_id=constraint_id,
                            target_id=constraint_id,
                            edge_type=EdgeType.BLOCKS_WHEN,
                            properties={
                                "block_type": block_type,
                                "description_text": desc,
                                "scope": "description",
                            },
                            source="step6_layer4",
                        )
                        count += 1
                        break  # 每个描述只匹配一次
        
        return count
    
    def step7_build_modifiers(self):
        """
        Step 7: 构建改变者（modifies 边）
        
        Layer 1: Support add_skill_types（全自动，100%置信度）
                 直接从 entities.db 获取 Support 添加的标签
        Layer 2: 天赋 stat_descriptions（半自动）
                 识别含关键词（instead/trigger/count_as/convert）的描述
        Layer 3: 装备/唯一物品特殊词缀（半自动）
                 同样从 stat_descriptions 识别机制改变者
        """
        logger.info("[Step 7] 构建改变者 modifies 边...")
        
        total_count = 0
        
        # Layer 1: Support add_skill_types
        count1 = self._step7_layer1_support_add_types()
        total_count += count1
        logger.info(f"  Layer 1 (Support add_types): {count1} 条")
        
        # Layer 2: 天赋 stat_descriptions 关键词
        count2 = self._step7_layer2_passive_descriptions()
        total_count += count2
        logger.info(f"  Layer 2 (passive descriptions): {count2} 条")
        
        # Layer 3: 装备/物品 stat_descriptions
        count3 = self._step7_layer3_item_descriptions()
        total_count += count3
        logger.info(f"  Layer 3 (item descriptions): {count3} 条")
        
        self.graph_conn.commit()
        self.stats["step7_modifiers"] = total_count
        logger.info(f"  总计 {total_count} 条 modifies 边")
    
    def _step7_layer1_support_add_types(self) -> int:
        """
        Layer 1: Support 的 add_skill_types 字段
        
        只有添加真实机制标签（非 SupportedByX）的 Support 才是改变者。
        """
        cursor = self.entities_conn.cursor()
        
        cursor.execute('''
            SELECT id, name, add_skill_types, require_skill_types
            FROM entities
            WHERE type = 'skill_definition'
              AND support = 1
              AND add_skill_types IS NOT NULL
              AND add_skill_types != '[]'
        ''')
        rows = cursor.fetchall()
        
        # 过滤出 "SupportedBy" 前缀的标签（这些不是机制改变）
        count = 0
        for row in rows:
            entity_id = row[0]
            entity_name = row[1] or entity_id
            
            try:
                added_tags = json.loads(row[2]) if row[2] else []
                require_tags = json.loads(row[3]) if row[3] else []
            except (json.JSONDecodeError, TypeError):
                continue
            
            # 过滤出真实机制标签
            real_tags = [t for t in added_tags if not t.startswith("SupportedBy")]
            
            if not real_tags:
                continue
            
            # 确定影响的集合
            affected_categories = set()
            for req_tag in require_tags:
                if req_tag in ('AND', 'OR', 'NOT'):
                    continue
                cats = TAG_TO_CATEGORY.get(req_tag)
                if isinstance(cats, list):
                    affected_categories.update(cats)
            
            # 创建实体节点（如果不存在）
            self._insert_node(
                node_id=entity_id,
                node_type=NodeType.ENTITY,
                name=entity_name,
                properties={
                    "entity_type": "support",
                    "adds_tags": real_tags,
                    "require_tags": require_tags,
                    "modifier_source": "support",
                },
                source="step7_layer1",
            )
            
            # 对每个真实标签创建 modifies 边
            for tag in real_tags:
                target_cats = TAG_TO_CATEGORY.get(tag)
                
                if affected_categories:
                    # 有明确的影响集合
                    for cat_id in affected_categories:
                        edge_id = f"mod_{entity_id}_{tag}_{cat_id}"
                        self._insert_edge(
                            edge_id=edge_id,
                            source_id=entity_id,
                            target_id=f"cat_{cat_id}",
                            edge_type=EdgeType.MODIFIES,
                            properties={
                                "modifier_source": "support",
                                "scope": "linked_skill",
                                "effect": f"adds_tag:{tag}",
                                "added_tag": tag,
                            },
                            confidence=1.0,
                            source="step7_layer1",
                        )
                        count += 1
                else:
                    # 无明确影响集合 → 通用改变者
                    edge_id = f"mod_{entity_id}_{tag}_general"
                    # 目标指向自身（通用改变者标记）
                    self._insert_edge(
                        edge_id=edge_id,
                        source_id=entity_id,
                        target_id=entity_id,
                        edge_type=EdgeType.MODIFIES,
                        properties={
                            "modifier_source": "support",
                            "scope": "linked_skill",
                            "effect": f"adds_tag:{tag}",
                            "added_tag": tag,
                        },
                        confidence=1.0,
                        source="step7_layer1",
                    )
                    count += 1
        
        return count
    
    def _step7_layer2_passive_descriptions(self) -> int:
        """
        Layer 2: 天赋节点 stat_descriptions 中的机制改变者
        
        识别含关键词的描述：
        - instead → 行为替换
        - trigger/triggered → 触发行为改变
        - count as / counts as → 类型替换
        - convert → 伤害/行为转换
        - also / additional → 附加行为
        """
        cursor = self.entities_conn.cursor()
        
        cursor.execute('''
            SELECT id, name, stat_descriptions
            FROM entities
            WHERE type IN ('passive_node', 'ascendancy_node')
              AND stat_descriptions IS NOT NULL
              AND stat_descriptions != '[]'
        ''')
        rows = cursor.fetchall()
        
        # 机制改变关键词
        modifier_patterns = [
            (re.compile(r'instead\s+(?:of\s+)?(.+)', re.IGNORECASE), "behavior_replace"),
            (re.compile(r'(?:trigger|triggered)\s+(.+)', re.IGNORECASE), "trigger_modify"),
            (re.compile(r'count(?:s)?\s+as\s+(.+)', re.IGNORECASE), "type_replace"),
            (re.compile(r'convert(?:s|ed)?\s+(.+)', re.IGNORECASE), "conversion"),
            (re.compile(r'also\s+(?:deal|apply|gain|have|are)\s+(.+)', re.IGNORECASE), "addition"),
        ]
        
        count = 0
        
        for row in rows:
            entity_id = row[0]
            entity_name = row[1] or entity_id
            
            try:
                descriptions = json.loads(row[2]) if row[2] else []
            except (json.JSONDecodeError, TypeError):
                continue
            
            if not isinstance(descriptions, list):
                continue
            
            for desc in descriptions:
                if not isinstance(desc, str):
                    continue
                
                desc_lower = desc.lower()
                
                # 跳过纯数值描述（注意：count 必须匹配 "count as"/"counts as" 避免误匹配 "Counter" 等）
                if not any(kw in desc_lower for kw in ['instead', 'trigger', 'count as', 'counts as', 'convert', 'also deal', 'also apply']):
                    continue
                
                # 匹配改变模式
                for pattern, effect_type in modifier_patterns:
                    if pattern.search(desc):
                        # 创建实体节点（如果不存在）
                        self._insert_node(
                            node_id=entity_id,
                            node_type=NodeType.ENTITY,
                            name=entity_name,
                            properties={
                                "entity_type": "passive_node",
                                "modifier_source": "passive",
                            },
                            source="step7_layer2",
                        )
                        
                        edge_id = f"mod_{entity_id}_{effect_type}_{hash(desc) & 0xFFFFFF:06x}"
                        self._insert_edge(
                            edge_id=edge_id,
                            source_id=entity_id,
                            target_id=entity_id,
                            edge_type=EdgeType.MODIFIES,
                            properties={
                                "modifier_source": "passive",
                                "scope": "all_skills",
                                "effect": effect_type,
                                "description_text": desc,
                            },
                            confidence=0.8,
                            source="step7_layer2",
                        )
                        count += 1
                        break
        
        return count
    
    def _step7_layer3_item_descriptions(self) -> int:
        """
        Layer 3: 装备/唯一物品 stat_descriptions 中的机制改变者
        
        与 Layer 2 类似，但针对 unique_item 和 mod_affix。
        """
        cursor = self.entities_conn.cursor()
        
        cursor.execute('''
            SELECT id, name, type, stat_descriptions
            FROM entities
            WHERE type IN ('unique_item', 'mod_affix')
              AND stat_descriptions IS NOT NULL
              AND stat_descriptions != '[]'
        ''')
        rows = cursor.fetchall()
        
        # 同样的机制改变关键词
        modifier_patterns = [
            (re.compile(r'instead\s+(?:of\s+)?(.+)', re.IGNORECASE), "behavior_replace"),
            (re.compile(r'(?:trigger|triggered)\s+(.+)', re.IGNORECASE), "trigger_modify"),
            (re.compile(r'count(?:s)?\s+as\s+(.+)', re.IGNORECASE), "type_replace"),
            (re.compile(r'convert(?:s|ed)?\s+(.+)', re.IGNORECASE), "conversion"),
        ]
        
        count = 0
        
        for row in rows:
            entity_id = row[0]
            entity_name = row[1] or entity_id
            entity_type = row[2]
            
            try:
                descriptions = json.loads(row[3]) if row[3] else []
            except (json.JSONDecodeError, TypeError):
                continue
            
            if not isinstance(descriptions, list):
                continue
            
            for desc in descriptions:
                if not isinstance(desc, str):
                    continue
                
                desc_lower = desc.lower()
                if not any(kw in desc_lower for kw in ['instead', 'trigger', 'count as', 'counts as', 'convert']):
                    continue
                
                for pattern, effect_type in modifier_patterns:
                    if pattern.search(desc):
                        self._insert_node(
                            node_id=entity_id,
                            node_type=NodeType.ENTITY,
                            name=entity_name,
                            properties={
                                "entity_type": entity_type,
                                "modifier_source": "item",
                            },
                            source="step7_layer3",
                        )
                        
                        edge_id = f"mod_{entity_id}_{effect_type}_{hash(desc) & 0xFFFFFF:06x}"
                        self._insert_edge(
                            edge_id=edge_id,
                            source_id=entity_id,
                            target_id=entity_id,
                            edge_type=EdgeType.MODIFIES,
                            properties={
                                "modifier_source": "item",
                                "scope": "all_skills",
                                "effect": effect_type,
                                "description_text": desc,
                            },
                            confidence=0.7,
                            source="step7_layer3",
                        )
                        count += 1
                        break
        
        return count
    
    def step8_extract_tag_propagation(self):
        """
        Step 8: 标签传播附加到机制边
        
        核心逻辑：
        1. 所有 triggers 边隐含添加 Triggered 标签
           （CalcTriggers 代码逻辑：被触发技能获得 Triggered 状态）
        2. 特定 Meta 技能有额外的标签传播
           （从 configTable 的 triggeredSkillCond 推断）
        3. deploys_as 边（Trap/Mine/Totem）添加对应的运行时标签
           （Trapped/RemoteMined/UsedByTotem）
        
        注意：Meta 技能的 entities.db add_skill_types 字段为空，
        标签传播是 CalcTriggers 代码隐含行为，不是声明式数据。
        """
        logger.info("[Step 8] 提取 tag_propagation 附加到机制边...")
        
        count = 0
        graph_cursor = self.graph_conn.cursor()
        
        # === Part 1: 所有 triggers 边添加 Triggered 标签 ===
        graph_cursor.execute('''
            SELECT edge_id, properties FROM graph_edges
            WHERE edge_type = 'triggers'
        ''')
        
        for row in graph_cursor.fetchall():
            edge_id = row[0]
            try:
                props = json.loads(row[1]) if row[1] else {}
            except (json.JSONDecodeError, TypeError):
                props = {}
            
            # 所有触发机制都给目标技能添加 Triggered 标签
            if "adds_tag" not in props:
                props["adds_tag"] = []
            
            if "Triggered" not in props["adds_tag"]:
                props["adds_tag"].append("Triggered")
            
            # 特殊触发有额外标签
            trigger_name = props.get("trigger_name", "")
            extra_tags = self._get_trigger_extra_tags(trigger_name)
            for tag in extra_tags:
                if tag not in props["adds_tag"]:
                    props["adds_tag"].append(tag)
            
            self.graph_conn.execute(
                'UPDATE graph_edges SET properties = ? WHERE edge_id = ?',
                (json.dumps(props, ensure_ascii=False), edge_id)
            )
            count += 1
        
        # === Part 2: deploys_as 边添加部署标签 ===
        # Trap → Trapped, Mine → RemoteMined, Totem → UsedByTotem
        deploy_tags = {
            "Trap": ["Trapped"],
            "Mine": ["RemoteMined"],
            "Totem": ["UsedByTotem"],
        }
        
        graph_cursor.execute('''
            SELECT edge_id, target_id, properties FROM graph_edges
            WHERE edge_type = 'deploys_as'
        ''')
        
        for row in graph_cursor.fetchall():
            edge_id = row[0]
            target_id = row[1]  # e.g., "cat_Trap"
            try:
                props = json.loads(row[2]) if row[2] else {}
            except (json.JSONDecodeError, TypeError):
                props = {}
            
            # 从 target_id 确定部署类型
            cat_name = target_id.replace("cat_", "")
            tags = deploy_tags.get(cat_name, [])
            
            if tags:
                if "adds_tag" not in props:
                    props["adds_tag"] = []
                for tag in tags:
                    if tag not in props["adds_tag"]:
                        props["adds_tag"].append(tag)
                
                self.graph_conn.execute(
                    'UPDATE graph_edges SET properties = ? WHERE edge_id = ?',
                    (json.dumps(props, ensure_ascii=False), edge_id)
                )
                count += 1
        
        # === Part 3: summons 边添加图腾标签 ===
        graph_cursor.execute('''
            SELECT edge_id, properties FROM graph_edges
            WHERE edge_type = 'summons'
        ''')
        
        for row in graph_cursor.fetchall():
            edge_id = row[0]
            try:
                props = json.loads(row[1]) if row[1] else {}
            except (json.JSONDecodeError, TypeError):
                props = {}
            
            if "adds_tag" not in props:
                props["adds_tag"] = []
            
            if "UsedByTotem" not in props["adds_tag"]:
                props["adds_tag"].append("UsedByTotem")
            
            self.graph_conn.execute(
                'UPDATE graph_edges SET properties = ? WHERE edge_id = ?',
                (json.dumps(props, ensure_ascii=False), edge_id)
            )
            count += 1
        
        self.graph_conn.commit()
        self.stats["step8_tag_propagation"] = count
        logger.info(f"  更新 {count} 条机制边的 adds_tag 属性")
    
    def _get_trigger_extra_tags(self, trigger_name: str) -> List[str]:
        """
        获取特定触发机制的额外标签
        
        大部分触发只添加 Triggered，但有些有额外的：
        - 格挡触发(Cast on Block) → Triggered (已在 Part 1 处理)
        - 图腾 → Triggered, UsedByTotem (图腾触发的情况)
        - Invocation 类 → Triggered (同标准)
        """
        # 目前所有触发的额外标签与 Triggered 一致
        # 保留此方法以支持未来特殊情况
        # 例如，如果某些触发有特殊的 flag（如 triggeredByCoC 等）
        
        # 当前 configTable 中不同触发名称对应不同的 triggeredByXxx 标志：
        # cast on critical strike → triggeredByCoc
        # cast on melee kill → triggeredByCom
        # spellslinger → triggeredBySpellslinger
        # 这些标志在运行时用于区分触发源，但对图中都归纳为 Triggered 标签
        
        return []
    
    def step9_restore_archive(self):
        """
        Step 9: 从 predefined_edges.yaml v2 存档恢复历史异常到图
        
        读取存档中的 anomalies 条目，将 confirmed 和 pending_review 的异常
        恢复为 bypasses 边 + anomaly_paths 表记录。
        """
        logger.info("[Step 9] 从存档恢复历史异常...")
        
        if not self.archive_path or not self.archive_path.exists():
            logger.info("  无存档文件，跳过 step9")
            self.stats["step9_restored"] = 0
            return
        
        if not HAS_YAML:
            logger.warning("  未安装 PyYAML，无法加载存档")
            self.stats["step9_restored"] = 0
            return
        
        try:
            with open(self.archive_path, 'r', encoding='utf-8') as f:
                archive = yaml.safe_load(f)
        except Exception as e:
            logger.warning(f"  加载存档失败: {e}")
            self.stats["step9_restored"] = 0
            return
        
        if not archive or not isinstance(archive, dict):
            logger.info("  存档内容为空或格式错误")
            self.stats["step9_restored"] = 0
            return
        
        # 检查存档版本
        metadata = archive.get("metadata", {})
        archive_version = metadata.get("version", "1.0.0")
        
        # === v3 格式兼容 ===
        # v3 使用 "bypasses" 键（按机制聚合），v2 使用 "anomalies"
        bypasses_v3 = archive.get("bypasses", [])
        anomalies_v2 = archive.get("anomalies", [])
        
        count = 0
        
        # 处理 v3 格式
        if bypasses_v3:
            for bypass in bypasses_v3:
                if not isinstance(bypass, dict):
                    continue
                
                status = bypass.get("status", "confirmed")
                if status not in ("confirmed", "pending_review", "new_discovery"):
                    continue
                
                bypass_id = bypass.get("id", f"v3_archive_{count}")
                
                # v3 隐藏技能信息
                hidden_skill = bypass.get("hidden_skill", {})
                modifier_id = hidden_skill.get("id", bypass.get("modifier_id", "unknown"))
                modifier_name = hidden_skill.get("name", modifier_id)
                
                mechanism = bypass.get("mechanism", "")
                value_score = bypass.get("value_score", 1)
                
                # 确保 modifier 节点存在
                self._insert_node(
                    node_id=modifier_id,
                    node_type=NodeType.ENTITY,
                    name=modifier_name,
                    properties={
                        "entity_type": "archive_hidden_skill",
                        "description": mechanism,
                    },
                    source="step9_archive_v3",
                )
                
                # v3 聚合约束列表
                bypassed_constraints = bypass.get("bypassed_constraints", [])
                for bc in bypassed_constraints:
                    if not isinstance(bc, dict):
                        continue
                    
                    constraint_id = bc.get("id", "unknown")
                    constraint_name = bc.get("name", constraint_id)
                    constraint_desc = bc.get("description", "")
                    
                    # 确保约束节点存在
                    self._insert_node(
                        node_id=constraint_id,
                        node_type=NodeType.CONSTRAINT,
                        name=constraint_name or f"存档约束: {constraint_id}",
                        properties={
                            "constraint_type": "archive",
                            "description": constraint_desc or mechanism,
                        },
                        source="step9_archive_v3",
                    )
                    
                    # 创建 bypasses 边
                    edge_id = f"bypass_{modifier_id}_{constraint_id}"
                    self._insert_edge(
                        edge_id=edge_id,
                        source_id=modifier_id,
                        target_id=constraint_id,
                        edge_type=EdgeType.BYPASSES,
                        properties={
                            "mechanism": mechanism,
                            "value_score": value_score,
                            "bypass_path": bypass.get("bypass_path", "archive"),
                            "archive_status": status,
                            "support_id": bypass.get("support", {}).get("id", ""),
                            "excluded_by": bypass.get("excluded_by_tags", []),
                            "evidence": bypass.get("evidence", {}),
                            "source": "archive_v3",
                        },
                        confidence=0.9 if status == "confirmed" else 0.6,
                        source="step9_archive_v3",
                    )
                
                # 写入 anomaly_paths 表（聚合记录）
                constraint_ids = [bc.get("id", "") for bc in bypassed_constraints]
                self._insert_anomaly(
                    anomaly_id=bypass_id,
                    constraint_id=json.dumps(constraint_ids, ensure_ascii=False) if len(constraint_ids) > 1 else (constraint_ids[0] if constraint_ids else "unknown"),
                    modifier_id=modifier_id,
                    mechanism=mechanism,
                    path_description=bypass.get("path_description", mechanism),
                    value_score=value_score,
                    source="archive_v3",
                )
                count += 1
        
        # 处理 v2 格式（兼容旧存档）
        elif anomalies_v2:
            for anomaly in anomalies_v2:
                if not isinstance(anomaly, dict):
                    continue
                
                status = anomaly.get("status", "confirmed")
                if status not in ("confirmed", "pending_review", "new_discovery"):
                    continue
                
                anomaly_id = anomaly.get("id", f"archive_{count}")
                
                # 兼容新旧格式：constraint/modifier 可能是字典或字符串
                constraint_data = anomaly.get("constraint", "unknown")
                if isinstance(constraint_data, dict):
                    constraint_id = constraint_data.get("id", "unknown")
                    constraint_name = constraint_data.get("name", constraint_id)
                    constraint_desc = constraint_data.get("description", "")
                else:
                    constraint_id = constraint_data
                    constraint_name = constraint_id
                    constraint_desc = ""
                
                modifier_data = anomaly.get("modifier", "unknown")
                if isinstance(modifier_data, dict):
                    modifier_id = modifier_data.get("id", "unknown")
                    modifier_name = modifier_data.get("name", modifier_id)
                else:
                    modifier_id = modifier_data
                    modifier_name = modifier_id
                
                mechanism_data = anomaly.get("mechanism", "")
                if isinstance(mechanism_data, dict):
                    mechanism = mechanism_data.get("summary", "") or mechanism_data.get("detail", "")
                else:
                    mechanism = mechanism_data
                
                value_score = anomaly.get("value_score", 1)
                
                self._insert_node(
                    node_id=constraint_id,
                    node_type=NodeType.CONSTRAINT,
                    name=constraint_name or f"存档约束: {constraint_id}",
                    properties={
                        "constraint_type": "archive",
                        "description": constraint_desc or mechanism,
                    },
                    source="step9_archive_v2",
                )
                
                self._insert_node(
                    node_id=modifier_id,
                    node_type=NodeType.ENTITY,
                    name=modifier_name or modifier_id,
                    properties={
                        "entity_type": "archive_modifier",
                        "description": mechanism,
                    },
                    source="step9_archive_v2",
                )
                
                edge_id = f"bypass_{anomaly_id}"
                self._insert_edge(
                    edge_id=edge_id,
                    source_id=modifier_id,
                    target_id=constraint_id,
                    edge_type=EdgeType.BYPASSES,
                    properties={
                        "mechanism": mechanism,
                        "value_score": value_score,
                        "archive_status": status,
                        "source": "archive_v2",
                    },
                    confidence=0.9 if status == "confirmed" else 0.6,
                    source="step9_archive_v2",
                )
                
                self._insert_anomaly(
                    anomaly_id=anomaly_id,
                    constraint_id=constraint_id,
                    modifier_id=modifier_id,
                    mechanism=mechanism,
                    path_description=anomaly.get("path_description", mechanism),
                    value_score=value_score,
                    source="archive_v2",
                )
                count += 1
        
        self.graph_conn.commit()
        self.stats["step9_restored"] = count
        logger.info(f"  从存档恢复 {count} 条异常")
    
    def step10_discover_anomalies(self):
        """
        Step 10: 通用绕过检测（三子步骤）
        
        完全重写旧的暴力遍历 + 4规则检测。
        新方案基于代码结构分析，不依赖任何硬编码标签名。
        
        三子步骤：
        - step10a: 构建约束传播链（哪些 Support 给哪些技能添加什么约束）
        - step10b: 三路径通用绕过检测
        - step10c: 证据链生成 + 按机制聚合
        """
        logger.info("[Step 10] 通用绕过检测（v2: 三子步骤）...")
        
        # 收集已恢复的异常 ID（避免重复）
        graph_cursor = self.graph_conn.cursor()
        graph_cursor.execute('SELECT anomaly_id FROM anomaly_paths')
        existing_anomaly_ids = {row[0] for row in graph_cursor.fetchall()}
        
        # === Step 10a: 构建约束传播链 ===
        propagation_chains = self._step10a_build_constraint_chains()
        
        # === Step 10b: 三路径通用绕过检测 ===
        discovered = self._step10b_detect_bypasses(propagation_chains, existing_anomaly_ids)
        
        # === Step 10c: 证据链生成 + 写入图 ===
        count = self._step10c_write_results(discovered)
        
        self.graph_conn.commit()
        self.stats["step10_discovered"] = count
        logger.info(f"  发现 {count} 条新绕过（按机制聚合）")
    
    def _step10a_build_constraint_chains(self) -> List[Dict[str, Any]]:
        """
        Step 10a: 构建约束传播链
        
        核心逻辑：
        1. 从 entities.db 查询所有 support=1 且有 addSkillTypes 的 Support
        2. 提取每个 Support 的 excludeSkillTypes（排除列表）
        3. 从 gems 的 additionalGrantedEffectId 找隐藏技能关联
        4. 对每个隐藏技能，提取其 skillTypes
        5. 构建传播链：Support → addSkillTypes → 被排除的技能 → 绕过效果
        
        Returns:
            传播链列表，每项包含:
            - support_id: Support 技能 ID
            - support_name: Support 名称
            - add_types: Support 添加的标签列表
            - exclude_types: Support 排除的标签列表
            - gem_ids: 关联的宝石 ID 列表（通过 grantedEffectId 反查）
            - hidden_skills: 通过 additionalGrantedEffectId 关联的隐藏技能列表
        """
        logger.info("  [10a] 构建约束传播链...")
        
        if not self.entities_conn:
            logger.warning("  entities.db 不可用，跳过 step10a")
            return []
        
        ent_cursor = self.entities_conn.cursor()
        
        # === Part 1: 查询所有有 addSkillTypes 的 Support 技能 ===
        ent_cursor.execute('''
            SELECT id, name, add_skill_types, exclude_skill_types, skill_types
            FROM entities
            WHERE type = 'skill_definition'
              AND support = 1
              AND add_skill_types IS NOT NULL
              AND add_skill_types != '[]'
        ''')
        
        supports = []
        for row in ent_cursor.fetchall():
            try:
                add_types = json.loads(row[2]) if row[2] else []
                exclude_types = json.loads(row[3]) if row[3] else []
                skill_types = json.loads(row[4]) if row[4] else []
            except (json.JSONDecodeError, TypeError):
                continue
            
            if not add_types:
                continue
            
            supports.append({
                "support_id": row[0],
                "support_name": row[1] or row[0],
                "add_types": add_types,
                "exclude_types": exclude_types,
                "skill_types": skill_types,
            })
        
        logger.info(f"    有 addSkillTypes 的 Support: {len(supports)}")
        
        # === Part 2: 构建 grantedEffectId → gem 映射 ===
        # 用于反查：哪些宝石关联了这些 Support
        ent_cursor.execute('''
            SELECT id, name, granted_effect_id, additional_granted_effect_ids
            FROM entities
            WHERE type = 'gem_definition'
              AND granted_effect_id IS NOT NULL
        ''')
        
        effect_to_gems = {}  # grantedEffectId → [gem_info, ...]
        gem_additional_effects = {}  # gem_id → [additionalGrantedEffectId, ...]
        additional_effect_to_gems = {}  # additionalEffectId → [gem_info, ...]（反向映射）
        gem_granted_effect = {}  # gem_id → grantedEffectId
        
        for row in ent_cursor.fetchall():
            gem_id = row[0]
            gem_name = row[1] or gem_id
            granted_effect = row[2]
            additional_raw = row[3]
            
            if granted_effect:
                if granted_effect not in effect_to_gems:
                    effect_to_gems[granted_effect] = []
                effect_to_gems[granted_effect].append({
                    "gem_id": gem_id,
                    "gem_name": gem_name,
                })
                gem_granted_effect[gem_id] = granted_effect
            
            if additional_raw:
                try:
                    additional = json.loads(additional_raw)
                    if additional:
                        gem_additional_effects[gem_id] = additional
                        # 构建反向映射：additionalEffectId → 父宝石
                        for eff_id in additional:
                            if eff_id not in additional_effect_to_gems:
                                additional_effect_to_gems[eff_id] = []
                            additional_effect_to_gems[eff_id].append({
                                "gem_id": gem_id,
                                "gem_name": gem_name,
                            })
                except (json.JSONDecodeError, TypeError):
                    pass
        
        logger.info(f"    grantedEffectId 映射: {len(effect_to_gems)} 个")
        logger.info(f"    有 additionalGrantedEffectId 的宝石: {len(gem_additional_effects)} 个")
        logger.info(f"    additionalEffectId 反向映射: {len(additional_effect_to_gems)} 个")
        
        # === Part 3: 查询所有隐藏技能的 skillTypes ===
        ent_cursor.execute('''
            SELECT id, name, skill_types
            FROM entities
            WHERE type = 'skill_definition'
              AND hidden = 1
        ''')
        
        hidden_skills_map = {}  # skill_id → {name, skill_types}
        for row in ent_cursor.fetchall():
            try:
                skill_types = json.loads(row[2]) if row[2] else []
            except (json.JSONDecodeError, TypeError):
                skill_types = []
            
            hidden_skills_map[row[0]] = {
                "skill_id": row[0],
                "name": row[1] or row[0],
                "skill_types": skill_types,
            }
        
        logger.info(f"    隐藏技能（hidden=1）: {len(hidden_skills_map)} 个")
        
        # === Part 4: 组装传播链 ===
        # 设计 v3: 传播链 = Support 的约束规则 + 所有可能被排除的隐藏技能
        #
        # 核心逻辑：SupportMeta* 辅助的是同插槽的所有技能（运行时动态绑定），
        # 不限于同一宝石下的 additionalGrantedEffectId。
        # 因此对每个 Support，遍历所有隐藏技能，检查是否被排除。
        #
        # 两种关联方式：
        #   1. 直接关联：Support/隐藏技能同属一个宝石的 additionalGrantedEffectIds
        #   2. 标签排除：隐藏技能自带 Support.excludeSkillTypes 中的标签
        
        chains = []
        
        # 预先构建：哪些隐藏技能自带哪些标签（用于快速排除匹配）
        # tag → [hidden_skill_ids]
        tag_to_hidden_skills = {}
        for skill_id, skill_info in hidden_skills_map.items():
            for tag in skill_info["skill_types"]:
                if tag not in tag_to_hidden_skills:
                    tag_to_hidden_skills[tag] = []
                tag_to_hidden_skills[tag].append(skill_id)
        
        for support in supports:
            support_id = support["support_id"]
            exclude_types = set(support["exclude_types"])
            hidden_skills = []
            parent_gems = []
            related_gems_combined = []
            seen_hidden_ids = set()
            
            # --- 方式1: 通过宝石映射关联的隐藏技能 ---
            # support_id 作为 grantedEffectId
            for gem_info in effect_to_gems.get(support_id, []):
                gem_id = gem_info["gem_id"]
                related_gems_combined.append(gem_info)
                for eff_id in gem_additional_effects.get(gem_id, []):
                    if eff_id in seen_hidden_ids:
                        continue
                    hidden = hidden_skills_map.get(eff_id)
                    if hidden:
                        hidden_skills.append({
                            "skill_id": eff_id,
                            "name": hidden["name"],
                            "skill_types": hidden["skill_types"],
                            "via_gem": gem_id,
                            "via_gem_name": gem_info["gem_name"],
                            "association": "direct",  # 直接宝石关联
                        })
                        seen_hidden_ids.add(eff_id)
            
            # support_id 作为 additionalGrantedEffectId（SupportMeta* 走这条路）
            for gem_info in additional_effect_to_gems.get(support_id, []):
                gem_id = gem_info["gem_id"]
                parent_gems.append(gem_id)
                if gem_info not in related_gems_combined:
                    related_gems_combined.append(gem_info)
                
                for eff_id in gem_additional_effects.get(gem_id, []):
                    if eff_id == support_id or eff_id in seen_hidden_ids:
                        continue
                    hidden = hidden_skills_map.get(eff_id)
                    if hidden:
                        hidden_skills.append({
                            "skill_id": eff_id,
                            "name": hidden["name"],
                            "skill_types": hidden["skill_types"],
                            "via_gem": gem_id,
                            "via_gem_name": gem_info["gem_name"],
                            "association": "sibling",  # 同一宝石下的兄弟
                        })
                        seen_hidden_ids.add(eff_id)
            
            # --- 方式2: 通过标签排除匹配的隐藏技能 ---
            # 对每个排除标签，找到所有自带该标签的隐藏技能
            if exclude_types:
                for excl_tag in exclude_types:
                    matched_skills = tag_to_hidden_skills.get(excl_tag, [])
                    for skill_id in matched_skills:
                        if skill_id == support_id or skill_id in seen_hidden_ids:
                            continue
                        hidden = hidden_skills_map[skill_id]
                        hidden_skills.append({
                            "skill_id": skill_id,
                            "name": hidden["name"],
                            "skill_types": hidden["skill_types"],
                            "via_gem": "",
                            "via_gem_name": "",
                            "association": "tag_exclusion",  # 标签排除匹配
                        })
                        seen_hidden_ids.add(skill_id)
            
            chain = {
                "support_id": support_id,
                "support_name": support["support_name"],
                "add_types": support["add_types"],
                "exclude_types": support["exclude_types"],
                "skill_types": support["skill_types"],
                "related_gems": related_gems_combined,
                "hidden_skills": hidden_skills,
                "parent_gems": parent_gems,
            }
            chains.append(chain)
        
        logger.info(f"    传播链总数: {len(chains)}")
        chains_with_hidden = sum(1 for c in chains if c["hidden_skills"])
        total_hidden = sum(len(c["hidden_skills"]) for c in chains)
        logger.info(f"    有隐藏技能关联的传播链: {chains_with_hidden}")
        logger.info(f"    总隐藏技能关联: {total_hidden}")
        
        return chains
    
    def _step10b_detect_bypasses(self, chains: List[Dict[str, Any]],
                                  existing_ids: Set[str]) -> List[Dict[str, Any]]:
        """
        Step 10b: 三路径通用绕过检测
        
        不依赖任何硬编码标签名。纯粹基于数据结构逻辑：
        
        路径 A（排除免疫型）：
          Support 的 excludeSkillTypes 包含标签 X
          → 某隐藏技能自带标签 X
          → Support 无法辅助该隐藏技能
          → 隐藏技能不被添加 Support.addSkillTypes 中的约束标签
          → 绕过所有基于这些约束标签的限制
        
        路径 B（需求不匹配型）：
          Support 的 requireSkillTypes 需要标签 Y
          → 某独立技能不具备标签 Y
          → Support 无法辅助该技能
          → 同上
        
        路径 C（代码分支免疫型）：
          CalcTriggers/CalcOffence 等代码中，某些分支依赖条件标签
          → 技能没有该条件标签
          → 不进入该阻断分支
          → 已在 step6 layer3 中建立约束，这里交叉验证
        
        Args:
            chains: step10a 输出的传播链
            existing_ids: 已存在的异常 ID 集合
            
        Returns:
            发现的绕过列表（按机制聚合）
        """
        logger.info("  [10b] 三路径通用绕过检测...")
        
        # 收集所有 blocks_when 约束（用于路径 C 交叉验证）
        graph_cursor = self.graph_conn.cursor()
        graph_cursor.execute('''
            SELECT e.edge_id, e.source_id, e.target_id, e.properties,
                   n.properties as node_properties, n.name as constraint_name
            FROM graph_edges e
            JOIN graph_nodes n ON e.source_id = n.node_id
            WHERE e.edge_type = 'blocks_when'
        ''')
        
        all_constraints = []
        for row in graph_cursor.fetchall():
            try:
                edge_props = json.loads(row[3]) if row[3] else {}
                node_props = json.loads(row[4]) if row[4] else {}
            except (json.JSONDecodeError, TypeError):
                edge_props = {}
                node_props = {}
            
            all_constraints.append({
                "edge_id": row[0],
                "constraint_id": row[1],
                "constraint_name": row[5] or row[1],
                "target_id": row[2],
                "edge_props": edge_props,
                "node_props": node_props,
            })
        
        discovered = []
        
        # === 路径 A: 排除免疫型 ===
        path_a_count = 0
        for chain in chains:
            exclude_types = set(chain["exclude_types"])
            add_types = chain["add_types"]
            
            if not exclude_types or not add_types:
                continue
            
            for hidden in chain.get("hidden_skills", []):
                hidden_types = set(hidden["skill_types"])
                
                # 检查：隐藏技能是否具有被排除的标签？
                excluded_by = exclude_types & hidden_types
                
                if excluded_by:
                    # 命中路径 A！
                    # 这个隐藏技能因自带排除标签，不被 Support 辅助
                    # → 不会被添加 add_types 中的约束标签
                    
                    # 找出被绕过的约束（与 add_types 相关的 blocks_when 约束）
                    bypassed_constraints = self._find_constraints_for_tags(
                        add_types, all_constraints
                    )
                    
                    if bypassed_constraints:
                        anomaly_id = f"bypass_excl_{chain['support_id']}_{hidden['skill_id']}"
                        
                        if anomaly_id not in existing_ids:
                            discovered.append({
                                "anomaly_id": anomaly_id,
                                "bypass_path": "A_exclusion_immunity",
                                "support_id": chain["support_id"],
                                "support_name": chain["support_name"],
                                "hidden_skill_id": hidden["skill_id"],
                                "hidden_skill_name": hidden["name"],
                                "via_gem": hidden.get("via_gem", ""),
                                "via_gem_name": hidden.get("via_gem_name", ""),
                                "excluded_by_tags": sorted(excluded_by),
                                "not_added_tags": add_types,
                                "bypassed_constraints": bypassed_constraints,
                                "evidence": {
                                    "support_exclude": f"{chain['support_id']}.excludeSkillTypes = {sorted(exclude_types)}",
                                    "hidden_has": f"{hidden['skill_id']}.skillTypes 包含 {sorted(excluded_by)}",
                                    "support_add": f"{chain['support_id']}.addSkillTypes = {add_types}",
                                    "code_ref": "CalcTools.lua:canGrantedEffectSupportActiveSkill() 行85-110",
                                },
                            })
                            path_a_count += 1
        
        logger.info(f"    路径 A（排除免疫）: {path_a_count} 条")
        
        # === 路径 B: 需求不匹配型 ===
        # 从所有 Support 的 requireSkillTypes 检查
        path_b_count = 0
        if self.entities_conn:
            ent_cursor = self.entities_conn.cursor()
            ent_cursor.execute('''
                SELECT id, name, require_skill_types, add_skill_types
                FROM entities
                WHERE type = 'skill_definition'
                  AND support = 1
                  AND require_skill_types IS NOT NULL
                  AND require_skill_types != '[]'
                  AND add_skill_types IS NOT NULL
                  AND add_skill_types != '[]'
            ''')
            
            for row in ent_cursor.fetchall():
                try:
                    require_types = json.loads(row[2]) if row[2] else []
                    add_types = json.loads(row[3]) if row[3] else []
                except (json.JSONDecodeError, TypeError):
                    continue
                
                if not require_types or not add_types:
                    continue
                
                # 查找不满足 require 条件的独立技能
                # （这里我们只关注被 additionalGrantedEffectId 关联的隐藏技能）
                for chain in chains:
                    if chain["support_id"] != row[0]:
                        continue
                    for hidden in chain.get("hidden_skills", []):
                        hidden_types = set(hidden["skill_types"])
                        missing = set(require_types) - hidden_types
                        
                        if missing:
                            bypassed_constraints = self._find_constraints_for_tags(
                                add_types, all_constraints
                            )
                            
                            if bypassed_constraints:
                                anomaly_id = f"bypass_req_{row[0]}_{hidden['skill_id']}"
                                
                                if anomaly_id not in existing_ids:
                                    discovered.append({
                                        "anomaly_id": anomaly_id,
                                        "bypass_path": "B_requirement_mismatch",
                                        "support_id": row[0],
                                        "support_name": row[1] or row[0],
                                        "hidden_skill_id": hidden["skill_id"],
                                        "hidden_skill_name": hidden["name"],
                                        "via_gem": hidden.get("via_gem", ""),
                                        "via_gem_name": hidden.get("via_gem_name", ""),
                                        "missing_tags": sorted(missing),
                                        "not_added_tags": add_types,
                                        "bypassed_constraints": bypassed_constraints,
                                        "evidence": {
                                            "support_require": f"{row[0]}.requireSkillTypes = {require_types}",
                                            "hidden_lacks": f"{hidden['skill_id']}.skillTypes 缺少 {sorted(missing)}",
                                            "code_ref": "CalcTools.lua:canGrantedEffectSupportActiveSkill() 行85-110",
                                        },
                                    })
                                    path_b_count += 1
        
        logger.info(f"    路径 B（需求不匹配）: {path_b_count} 条")
        
        # === 路径 C: 代码分支免疫型 ===
        # 检查 step6 layer3 建立的 Calc 代码约束中，哪些可被绕过
        path_c_count = 0
        code_constraints = [c for c in all_constraints 
                           if c["edge_props"].get("layer") == "calc_code" 
                           or c["edge_props"].get("block_type") in ("selfCast", "recently")]
        
        if code_constraints and self.entities_conn:
            ent_cursor = self.entities_conn.cursor()
            
            for constraint in code_constraints:
                condition_tags = self._extract_constraint_condition_tags_v2(constraint)
                
                if not condition_tags:
                    continue
                
                # 找出具有排除标签的隐藏技能
                for chain in chains:
                    for hidden in chain.get("hidden_skills", []):
                        hidden_types = set(hidden["skill_types"])
                        
                        # 如果隐藏技能不具备约束条件中的任何标签 → 代码分支不会执行
                        condition_overlap = set(condition_tags) & hidden_types
                        
                        # 约束需要的标签都不在隐藏技能的 skillTypes 中
                        # → 隐藏技能不进入约束的代码分支 → 免疫该约束
                        if not condition_overlap and condition_tags:
                            anomaly_id = f"bypass_code_{constraint['constraint_id']}_{hidden['skill_id']}"
                            
                            if anomaly_id not in existing_ids:
                                discovered.append({
                                    "anomaly_id": anomaly_id,
                                    "bypass_path": "C_code_branch_immunity",
                                    "support_id": chain["support_id"],
                                    "support_name": chain["support_name"],
                                    "hidden_skill_id": hidden["skill_id"],
                                    "hidden_skill_name": hidden["name"],
                                    "via_gem": hidden.get("via_gem", ""),
                                    "via_gem_name": hidden.get("via_gem_name", ""),
                                    "constraint_id": constraint["constraint_id"],
                                    "constraint_name": constraint["constraint_name"],
                                    "condition_tags": sorted(condition_tags),
                                    "bypassed_constraints": [{
                                        "constraint_id": constraint["constraint_id"],
                                        "constraint_name": constraint["constraint_name"],
                                        "reason": f"隐藏技能不具备条件标签 {sorted(condition_tags)}"
                                    }],
                                    "evidence": {
                                        "constraint_needs": f"约束 {constraint['constraint_id']} 需要标签 {sorted(condition_tags)}",
                                        "hidden_lacks": f"{hidden['skill_id']}.skillTypes 不含任何条件标签",
                                        "code_ref": constraint["edge_props"].get("code_location", "CalcPerform/CalcOffence"),
                                    },
                                })
                                path_c_count += 1
        
        logger.info(f"    路径 C（代码分支免疫）: {path_c_count} 条")
        logger.info(f"    总发现: {len(discovered)} 条")
        
        return discovered
    
    def _find_constraints_for_tags(self, tags: List[str], 
                                    all_constraints: List[Dict]) -> List[Dict]:
        """
        查找与给定标签相关的约束
        
        逻辑：如果一个约束的 condition_tag 包含在 tags 列表中，
        那么这个约束可以被绕过（因为 tags 不会被添加到隐藏技能上）。
        
        Args:
            tags: Support 的 addSkillTypes 列表
            all_constraints: 所有 blocks_when 约束
            
        Returns:
            被绕过的约束列表
        """
        bypassed = []
        tag_set = set(tags)
        
        for constraint in all_constraints:
            edge_props = constraint["edge_props"]
            node_props = constraint["node_props"]
            
            # 约束的条件标签
            condition_tag = edge_props.get("condition_tag", "")
            condition_tags = edge_props.get("condition_tags", [])
            
            # 合并所有条件标签
            all_cond_tags = set()
            if condition_tag:
                all_cond_tags.add(condition_tag)
            if isinstance(condition_tags, list):
                all_cond_tags.update(condition_tags)
            
            # 检查：约束的条件标签是否在 Support 添加的标签集中？
            overlap = all_cond_tags & tag_set
            
            if overlap:
                bypassed.append({
                    "constraint_id": constraint["constraint_id"],
                    "constraint_name": constraint["constraint_name"],
                    "condition_tags_matched": sorted(overlap),
                    "reason": f"约束检查 {sorted(overlap)}，但隐藏技能不被添加这些标签",
                })
        
        return bypassed
    
    def _extract_constraint_condition_tags_v2(self, constraint: dict) -> List[str]:
        """
        从约束中提取条件标签（v2: 仅提取结构化标签，不提取描述文本）
        
        与旧版 _extract_constraint_condition_tags 的区别：
        - 不再使用 desc:xxx 格式的伪标签
        - 只返回真实的 SkillType 标签
        """
        edge_props = constraint["edge_props"]
        node_props = constraint["node_props"]
        
        tags = []
        
        # Layer 1: 直接的 condition_tag
        if "condition_tag" in edge_props:
            tags.append(edge_props["condition_tag"])
        
        # Layer 3: condition_tags 列表
        if "condition_tags" in edge_props:
            tags.extend(edge_props["condition_tags"])
        elif "condition_tags" in node_props:
            tags.extend(node_props["condition_tags"])
        
        # Layer 2: flags
        if "flags" in edge_props:
            flags = edge_props["flags"]
            if isinstance(flags, list):
                tags.extend(flags)
        
        return tags
    
    def _step10c_write_results(self, discovered: List[Dict[str, Any]]) -> int:
        """
        Step 10c: 写入发现结果到图数据库
        
        按机制聚合：同一个隐藏技能绕过多个约束 → 聚合为1条记录。
        
        Args:
            discovered: step10b 发现的绕过列表
            
        Returns:
            写入的记录数
        """
        logger.info("  [10c] 证据链生成 + 写入...")
        
        # 按 (support_id, hidden_skill_id) 聚合
        aggregated = {}
        for item in discovered:
            key = (item.get("support_id", ""), item.get("hidden_skill_id", ""))
            if key not in aggregated:
                aggregated[key] = {
                    "anomaly_id": item["anomaly_id"],
                    "bypass_path": item["bypass_path"],
                    "support_id": item.get("support_id", ""),
                    "support_name": item.get("support_name", ""),
                    "hidden_skill_id": item.get("hidden_skill_id", ""),
                    "hidden_skill_name": item.get("hidden_skill_name", ""),
                    "via_gem": item.get("via_gem", ""),
                    "via_gem_name": item.get("via_gem_name", ""),
                    "bypassed_constraints": [],
                    "evidence": item.get("evidence", {}),
                    "excluded_by_tags": item.get("excluded_by_tags", []),
                    "not_added_tags": item.get("not_added_tags", []),
                }
            
            # 追加被绕过的约束
            for bc in item.get("bypassed_constraints", []):
                # 去重
                if not any(
                    e["constraint_id"] == bc["constraint_id"]
                    for e in aggregated[key]["bypassed_constraints"]
                ):
                    aggregated[key]["bypassed_constraints"].append(bc)
        
        count = 0
        for key, agg in aggregated.items():
            anomaly_id = agg["anomaly_id"]
            
            # 构建机制描述
            mechanism = self._build_mechanism_description(agg)
            
            # 确定价值分数
            value_score = self._score_anomaly_v2(agg)
            
            # 确保节点存在
            # 隐藏技能节点
            self._insert_node(
                node_id=agg["hidden_skill_id"],
                node_type=NodeType.ENTITY,
                name=agg["hidden_skill_name"],
                properties={
                    "entity_type": "hidden_skill",
                    "via_gem": agg["via_gem"],
                },
                source="step10c_bypass",
            )
            
            # 为每个被绕过的约束创建 bypasses 边
            for bc in agg["bypassed_constraints"]:
                edge_id = f"bypass_{agg['hidden_skill_id']}_{bc['constraint_id']}"
                self._insert_edge(
                    edge_id=edge_id,
                    source_id=agg["hidden_skill_id"],
                    target_id=bc["constraint_id"],
                    edge_type=EdgeType.BYPASSES,
                    properties={
                        "mechanism": mechanism,
                        "bypass_path": agg["bypass_path"],
                        "value_score": value_score,
                        "support_id": agg["support_id"],
                        "excluded_by": agg.get("excluded_by_tags", []),
                        "evidence": agg.get("evidence", {}),
                        "source": "step10_v2",
                    },
                    confidence=0.95,
                    source="step10c_v2",
                )
            
            # 写入 anomaly_paths 表（聚合记录）
            constraint_ids = [bc["constraint_id"] for bc in agg["bypassed_constraints"]]
            self._insert_anomaly(
                anomaly_id=anomaly_id,
                constraint_id=json.dumps(constraint_ids, ensure_ascii=False),
                modifier_id=agg["hidden_skill_id"],
                mechanism=mechanism,
                path_description=self._build_path_description(agg),
                value_score=value_score,
                source="step10_v2",
            )
            count += 1
        
        return count
    
    def _build_mechanism_description(self, agg: dict) -> str:
        """构建机制描述文本"""
        path = agg["bypass_path"]
        
        if path == "A_exclusion_immunity":
            excluded_tags = ", ".join(agg.get("excluded_by_tags", []))
            add_tags = ", ".join(agg.get("not_added_tags", []))
            return (
                f"排除免疫: {agg['hidden_skill_name']} 自带 [{excluded_tags}] 标签, "
                f"被 {agg['support_name']} 的 excludeSkillTypes 排除, "
                f"因此不被添加 [{add_tags}] 约束标签"
            )
        elif path == "B_requirement_mismatch":
            missing = ", ".join(agg.get("missing_tags", []))
            return (
                f"需求不匹配: {agg['hidden_skill_name']} 缺少 [{missing}] 标签, "
                f"不满足 {agg['support_name']} 的 requireSkillTypes, "
                f"因此不被辅助、不受约束"
            )
        elif path == "C_code_branch_immunity":
            cond_tags = ", ".join(agg.get("condition_tags", []))
            return (
                f"代码分支免疫: {agg['hidden_skill_name']} 不具备 [{cond_tags}] 条件标签, "
                f"不进入阻断代码分支"
            )
        else:
            return f"绕过机制: {path}"
    
    def _build_path_description(self, agg: dict) -> str:
        """构建路径描述文本"""
        constraints_str = ", ".join(
            bc["constraint_name"] for bc in agg.get("bypassed_constraints", [])[:5]
        )
        total = len(agg.get("bypassed_constraints", []))
        suffix = f"(+{total - 5})" if total > 5 else ""
        
        return (
            f"{agg['hidden_skill_name']} (通过 {agg.get('via_gem_name', '?')}) "
            f"绕过 {total} 个约束: {constraints_str}{suffix}"
        )
    
    def _score_anomaly_v2(self, agg: dict) -> int:
        """
        评估绕过的价值分数（v2）
        
        3 = 高（涉及能量/触发系统，影响多个约束）
        2 = 中（影响2-3个约束）
        1 = 低（只影响1个约束）
        """
        num_constraints = len(agg.get("bypassed_constraints", []))
        
        if num_constraints >= 4:
            return 3
        elif num_constraints >= 2:
            return 2
        else:
            return 1
    
    def _postprocess_archive(self):
        """
        后处理: 回写 predefined_edges.yaml v3 格式
        
        v3 格式特点：
        - 按机制聚合（1个隐藏技能 × N个约束 = 1条记录）
        - 包含完整证据链
        - 不再使用旧的 anomaly 扁平格式
        
        三种状态合并：
        - 存档有 ∩ 算法有 → confirmed（双重验证）
        - 存档有 ∩ 算法没有 → pending_review
        - 算法有 ∩ 存档没有 → new_discovery
        """
        logger.info("[后处理] 存档回写 v3 格式...")
        
        if not self.archive_path:
            logger.info("  未指定存档路径，跳过后处理")
            return
        
        if not HAS_YAML:
            logger.warning("  未安装 PyYAML，无法回写存档")
            return
        
        # 加载现有存档的 ID（兼容 v2/v3）
        existing_ids = set()
        if self.archive_path.exists():
            try:
                with open(self.archive_path, 'r', encoding='utf-8') as f:
                    archive = yaml.safe_load(f) or {}
                # v3 格式
                for bypass in archive.get("bypasses", []):
                    if isinstance(bypass, dict):
                        existing_ids.add(bypass.get("id", ""))
                # v2 兼容
                for anomaly in archive.get("anomalies", []):
                    if isinstance(anomaly, dict):
                        existing_ids.add(anomaly.get("id", ""))
            except Exception:
                pass
        
        # 从 anomaly_paths 表收集所有记录
        graph_cursor = self.graph_conn.cursor()
        graph_cursor.execute('''
            SELECT anomaly_id, constraint_id, modifier_id, mechanism,
                   path_description, value_score, source
            FROM anomaly_paths
        ''')
        
        # 按 modifier_id 聚合
        by_modifier = {}
        for row in graph_cursor.fetchall():
            modifier_id = row[2]
            if modifier_id not in by_modifier:
                by_modifier[modifier_id] = {
                    "anomaly_id": row[0],
                    "modifier_id": modifier_id,
                    "mechanism": row[3],
                    "path_description": row[4],
                    "value_score": row[5],
                    "source": row[6],
                    "constraint_ids": [],
                }
            
            # constraint_id 可能是 JSON 数组（聚合记录）或单个 ID
            cid_raw = row[1]
            try:
                cids = json.loads(cid_raw) if cid_raw.startswith("[") else [cid_raw]
            except (json.JSONDecodeError, ValueError):
                cids = [cid_raw]
            
            for cid in cids:
                if cid not in by_modifier[modifier_id]["constraint_ids"]:
                    by_modifier[modifier_id]["constraint_ids"].append(cid)
        
        # 构建 v3 输出
        bypasses = []
        for modifier_id, data in by_modifier.items():
            # 解析修改者信息
            modifier_info = self._resolve_entity_name(modifier_id)
            
            # 获取 bypasses 边的属性
            graph_cursor.execute('''
                SELECT properties FROM graph_edges 
                WHERE edge_type = 'bypasses' AND source_id = ?
                LIMIT 1
            ''', (modifier_id,))
            edge_row = graph_cursor.fetchone()
            edge_props = {}
            if edge_row and edge_row[0]:
                try:
                    edge_props = json.loads(edge_row[0])
                except (json.JSONDecodeError, TypeError):
                    pass
            
            # 解析约束列表
            constraint_list = []
            for cid in data["constraint_ids"]:
                con_info = self._resolve_entity_name(cid)
                # 获取约束描述
                desc = ""
                graph_cursor.execute(
                    'SELECT properties FROM graph_nodes WHERE node_id = ?', (cid,)
                )
                con_row = graph_cursor.fetchone()
                if con_row and con_row[0]:
                    try:
                        con_props = json.loads(con_row[0])
                        desc = con_props.get("description_text") or con_props.get("description", "")
                    except:
                        pass
                
                constraint_list.append({
                    "id": cid,
                    "name": con_info.get("name", cid),
                    "description": desc,
                })
            
            # 确定状态
            status = "new_discovery"
            if data["anomaly_id"] in existing_ids:
                status = "confirmed"
            
            bypass_record = {
                "id": data["anomaly_id"],
                "hidden_skill": {
                    "id": modifier_id,
                    "name": modifier_info.get("name", modifier_id),
                },
                "support": {
                    "id": edge_props.get("support_id", ""),
                    "name": edge_props.get("support_name", ""),
                },
                "via_gem": edge_props.get("via_gem", ""),
                "bypass_path": edge_props.get("bypass_path", data.get("source", "")),
                "mechanism": data["mechanism"],
                "excluded_by_tags": edge_props.get("excluded_by", []),
                "evidence": edge_props.get("evidence", {}),
                "bypassed_constraints": constraint_list,
                "value_score": data["value_score"],
                "status": status,
                "discovered_version": self._get_game_version(),
                "last_verified_version": self._get_game_version(),
            }
            bypasses.append(bypass_record)
        
        # 处理存档中有但本次没发现的
        if self.archive_path.exists():
            try:
                with open(self.archive_path, 'r', encoding='utf-8') as f:
                    old_archive = yaml.safe_load(f) or {}
                
                current_ids = {b["id"] for b in bypasses}
                
                for old_bypass in old_archive.get("bypasses", []):
                    if isinstance(old_bypass, dict) and old_bypass.get("id") not in current_ids:
                        old_bypass["status"] = "pending_review"
                        bypasses.append(old_bypass)
                
                # v2 兼容
                for old_anomaly in old_archive.get("anomalies", []):
                    if isinstance(old_anomaly, dict) and old_anomaly.get("id") not in current_ids:
                        # 转换 v2 → v3 格式
                        old_anomaly["status"] = "pending_review"
                        bypasses.append(self._convert_v2_to_v3(old_anomaly))
            except Exception:
                pass
        
        # 按 value_score 降序排序
        bypasses.sort(key=lambda x: x.get("value_score", 0), reverse=True)
        
        # 统计
        stats_count = {
            "total": len(bypasses),
            "confirmed": sum(1 for b in bypasses if b.get("status") == "confirmed"),
            "new_discovery": sum(1 for b in bypasses if b.get("status") == "new_discovery"),
            "pending_review": sum(1 for b in bypasses if b.get("status") == "pending_review"),
        }
        
        output = {
            "metadata": {
                "version": "3.0.0",
                "last_updated": datetime.now().strftime("%Y-%m-%d"),
                "game_version": self._get_game_version(),
                "description": "绕过机制存档 v3 — 按机制聚合，含完整证据链",
                "stats": stats_count,
            },
            "bypasses": bypasses,
        }
        
        try:
            self.archive_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.archive_path, 'w', encoding='utf-8') as f:
                yaml.dump(output, f, Dumper=MultilineDumper,
                         default_flow_style=False,
                         allow_unicode=True, sort_keys=False)
            logger.info(f"  存档回写完成 (v3): {stats_count['total']} 条绕过")
            logger.info(f"    confirmed: {stats_count['confirmed']}")
            logger.info(f"    new_discovery: {stats_count['new_discovery']}")
            logger.info(f"    pending_review: {stats_count['pending_review']}")
        except Exception as e:
            logger.error(f"  存档回写失败: {e}")
    
    def _convert_v2_to_v3(self, v2_anomaly: dict) -> dict:
        """将 v2 anomaly 格式转换为 v3 bypass 格式"""
        constraint_data = v2_anomaly.get("constraint", {})
        modifier_data = v2_anomaly.get("modifier", {})
        mechanism_data = v2_anomaly.get("mechanism", {})
        
        if isinstance(constraint_data, str):
            constraint_data = {"id": constraint_data, "name": constraint_data}
        if isinstance(modifier_data, str):
            modifier_data = {"id": modifier_data, "name": modifier_data}
        if isinstance(mechanism_data, str):
            mechanism_data = {"summary": mechanism_data}
        
        return {
            "id": v2_anomaly.get("id", "unknown"),
            "hidden_skill": {
                "id": modifier_data.get("id", ""),
                "name": modifier_data.get("name", ""),
            },
            "support": {"id": "", "name": ""},
            "via_gem": "",
            "bypass_path": "legacy_v2",
            "mechanism": mechanism_data.get("summary", mechanism_data.get("detail", "")),
            "excluded_by_tags": [],
            "evidence": {},
            "bypassed_constraints": [constraint_data] if constraint_data else [],
            "value_score": v2_anomaly.get("value_score", 1),
            "status": v2_anomaly.get("status", "pending_review"),
            "discovered_version": v2_anomaly.get("discovered_version", "unknown"),
            "last_verified_version": v2_anomaly.get("last_verified_version", "unknown"),
        }
    
    def _get_game_version(self) -> str:
        """获取当前游戏版本"""
        if not self.pob_path:
            return "unknown"
        
        gv_path = self.pob_path / "GameVersions.lua"
        if not gv_path.exists():
            return "unknown"
        
        try:
            with open(gv_path, 'r', encoding='utf-8') as f:
                content = f.read()
            match = re.search(r'latestTreeVersion\s*=\s*"([^"]+)"', content)
            if match:
                return match.group(1).replace('_', '.')
            match = re.search(r'gameVersions\s*=\s*\{.*?"([^"]+)"', content, re.DOTALL)
            if match:
                return match.group(1)
        except Exception:
            pass
        
        return "unknown"
    
    # ============================================================
    # 查询接口
    # ============================================================
    
    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        """获取节点"""
        if not self.graph_conn:
            self._open_graph_db()
        
        cursor = self.graph_conn.cursor()
        cursor.execute('SELECT * FROM graph_nodes WHERE node_id = ?', (node_id,))
        row = cursor.fetchone()
        if row:
            return self._row_to_dict(row)
        return None
    
    def get_nodes_by_type(self, node_type: NodeType) -> List[Dict[str, Any]]:
        """按类型获取节点"""
        if not self.graph_conn:
            self._open_graph_db()
        
        cursor = self.graph_conn.cursor()
        cursor.execute('SELECT * FROM graph_nodes WHERE node_type = ?', (node_type.value,))
        return [self._row_to_dict(row) for row in cursor.fetchall()]
    
    def get_edges_by_type(self, edge_type: EdgeType) -> List[Dict[str, Any]]:
        """按类型获取边"""
        if not self.graph_conn:
            self._open_graph_db()
        
        cursor = self.graph_conn.cursor()
        cursor.execute('SELECT * FROM graph_edges WHERE edge_type = ?', (edge_type.value,))
        return [self._row_to_dict(row) for row in cursor.fetchall()]
    
    def get_neighbors(self, node_id: str, edge_type: str = None) -> List[Dict[str, Any]]:
        """获取节点的邻居"""
        if not self.graph_conn:
            self._open_graph_db()
        
        cursor = self.graph_conn.cursor()
        
        query = '''
            SELECT n.*, e.edge_type, e.properties as edge_properties, e.confidence
            FROM graph_nodes n
            JOIN graph_edges e ON n.node_id = e.target_id
            WHERE e.source_id = ?
        '''
        params = [node_id]
        
        if edge_type:
            query += ' AND e.edge_type = ?'
            params.append(edge_type)
        
        cursor.execute(query, params)
        results = []
        for row in cursor.fetchall():
            d = self._row_to_dict(row)
            d['edge_type'] = row['edge_type']
            d['edge_properties'] = json.loads(row['edge_properties']) if row['edge_properties'] else {}
            d['confidence'] = row['confidence']
            results.append(d)
        return results
    
    def get_reverse_neighbors(self, node_id: str, edge_type: str = None) -> List[Dict[str, Any]]:
        """获取反向邻居（谁指向这个节点）"""
        if not self.graph_conn:
            self._open_graph_db()
        
        cursor = self.graph_conn.cursor()
        
        query = '''
            SELECT n.*, e.edge_type, e.properties as edge_properties, e.confidence
            FROM graph_nodes n
            JOIN graph_edges e ON n.node_id = e.source_id
            WHERE e.target_id = ?
        '''
        params = [node_id]
        
        if edge_type:
            query += ' AND e.edge_type = ?'
            params.append(edge_type)
        
        cursor.execute(query, params)
        results = []
        for row in cursor.fetchall():
            d = self._row_to_dict(row)
            d['edge_type'] = row['edge_type']
            d['edge_properties'] = json.loads(row['edge_properties']) if row['edge_properties'] else {}
            d['confidence'] = row['confidence']
            results.append(d)
        return results
    
    def get_category_members(self, category_id: str) -> List[Dict[str, Any]]:
        """获取集合的所有成员"""
        cat_node_id = f"cat_{category_id}" if not category_id.startswith("cat_") else category_id
        return self.get_reverse_neighbors(cat_node_id, EdgeType.BELONGS_TO.value)
    
    def get_entity_categories(self, entity_id: str) -> List[Dict[str, Any]]:
        """获取实体所属的集合"""
        return self.get_neighbors(entity_id, EdgeType.BELONGS_TO.value)
    
    def find_path(self, source: str, target: str, max_depth: int = 5) -> List[List[Dict[str, Any]]]:
        """BFS查找路径"""
        if not self.graph_conn:
            self._open_graph_db()
        
        paths = []
        visited = set()
        queue = [(source, [{"node_id": source}])]
        
        while queue:
            current, path = queue.pop(0)
            
            if len(path) > max_depth:
                continue
            
            if current == target and len(path) > 1:
                paths.append(path)
                continue
            
            if current in visited:
                continue
            visited.add(current)
            
            neighbors = self.get_neighbors(current)
            for neighbor in neighbors:
                if neighbor['node_id'] not in visited:
                    new_path = path + [neighbor]
                    queue.append((neighbor['node_id'], new_path))
        
        return paths
    
    def get_stats(self) -> Dict[str, Any]:
        """获取图统计信息"""
        if not self.graph_conn:
            self._open_graph_db()
        
        cursor = self.graph_conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM graph_nodes')
        node_count = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM graph_edges')
        edge_count = cursor.fetchone()[0]
        
        cursor.execute('SELECT node_type, COUNT(*) FROM graph_nodes GROUP BY node_type')
        node_types = {row[0]: row[1] for row in cursor.fetchall()}
        
        cursor.execute('SELECT edge_type, COUNT(*) FROM graph_edges GROUP BY edge_type')
        edge_types = {row[0]: row[1] for row in cursor.fetchall()}
        
        cursor.execute('SELECT COUNT(*) FROM anomaly_paths')
        anomaly_count = cursor.fetchone()[0]
        
        return {
            'node_count': node_count,
            'edge_count': edge_count,
            'node_types': node_types,
            'edge_types': edge_types,
            'anomaly_count': anomaly_count,
        }
    
    def search_nodes(self, query: str) -> List[Dict[str, Any]]:
        """搜索节点"""
        if not self.graph_conn:
            self._open_graph_db()
        
        cursor = self.graph_conn.cursor()
        pattern = f'%{query}%'
        cursor.execute(
            'SELECT * FROM graph_nodes WHERE name LIKE ? OR node_id LIKE ?',
            (pattern, pattern)
        )
        return [self._row_to_dict(row) for row in cursor.fetchall()]
    
    def find_bypass_paths(self, constraint_id: str) -> List[Dict[str, Any]]:
        """
        查找约束的绕过路径（兼容旧 API）
        
        Args:
            constraint_id: 约束节点 ID
            
        Returns:
            绕过路径列表，每项包含 bypass_source、mechanism、confirmed 等字段
        """
        if not self.graph_conn:
            self._open_graph_db()
        
        cursor = self.graph_conn.cursor()
        
        # 从 anomaly_paths 表查询
        cursor.execute('''
            SELECT anomaly_id, modifier_id, mechanism, path_description, 
                   value_score, source, verified
            FROM anomaly_paths
            WHERE constraint_id = ?
        ''', (constraint_id,))
        
        results = []
        for row in cursor.fetchall():
            results.append({
                'id': row[0],
                'bypass_source': row[1],  # modifier_id
                'mechanism': row[2],
                'path_description': row[3],
                'value_score': row[4],
                'source': row[5],
                'confirmed': bool(row[6]),  # verified 字段
            })
        
        return results
    
    # ============================================================
    # 工具方法
    # ============================================================
    
    def _open_graph_db(self):
        """打开已有的 graph.db（用于查询模式）"""
        if not self.graph_db_path.exists():
            raise FileNotFoundError(f"graph.db 不存在: {self.graph_db_path}")
        self.graph_conn = sqlite3.connect(str(self.graph_db_path))
        self.graph_conn.row_factory = sqlite3.Row
    
    def _row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        """转换Row为字典，自动解析JSON字段"""
        result = dict(row)
        for key in ('properties', 'edge_properties'):
            if key in result and result[key]:
                try:
                    result[key] = json.loads(result[key])
                except (json.JSONDecodeError, TypeError):
                    pass
        return result
    
    def close(self):
        """关闭所有连接"""
        if self.graph_conn:
            self.graph_conn.close()
            self.graph_conn = None
        if self.entities_conn:
            self.entities_conn.close()
            self.entities_conn = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# ============================================================
# CLI 入口
# ============================================================

def main():
    """命令行入口"""
    import argparse
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%H:%M:%S'
    )
    
    parser = argparse.ArgumentParser(description='POE关联图构建器 v2')
    parser.add_argument('--graph-db', default='knowledge_base/graph.db', help='graph.db路径')
    parser.add_argument('--entities-db', default='knowledge_base/entities.db', help='entities.db路径')
    parser.add_argument('--pob-path', default=None, help='POBData目录路径')
    parser.add_argument('--archive', default='config/predefined_edges.yaml', help='异常存档路径')
    parser.add_argument('--build', action='store_true', help='执行完整构建')
    parser.add_argument('--stats', action='store_true', help='显示统计信息')
    parser.add_argument('--members', help='显示集合成员')
    parser.add_argument('--search', help='搜索节点')
    parser.add_argument('--neighbors', help='显示邻居节点')
    
    args = parser.parse_args()
    
    builder = GraphBuilder(
        graph_db_path=args.graph_db,
        entities_db_path=args.entities_db,
        pob_path=args.pob_path,
        archive_path=args.archive,
    )
    
    try:
        if args.build:
            stats = builder.build()
            print(f"\n构建完成:")
            for key, value in stats.items():
                if isinstance(value, dict):
                    print(f"  {key}:")
                    for k, v in value.items():
                        print(f"    {k}: {v}")
                else:
                    print(f"  {key}: {value}")
        
        elif args.stats:
            stats = builder.get_stats()
            print(f"节点数: {stats['node_count']}")
            print(f"边数: {stats['edge_count']}")
            print(f"异常数: {stats['anomaly_count']}")
            print("\n节点类型:")
            for t, c in stats['node_types'].items():
                print(f"  {t}: {c}")
            print("\n边类型:")
            for t, c in stats['edge_types'].items():
                print(f"  {t}: {c}")
        
        elif args.members:
            members = builder.get_category_members(args.members)
            print(f"{args.members} 集合成员 ({len(members)}):")
            for m in members:
                print(f"  - {m.get('node_id', '?')}: {m.get('name', '?')}")
        
        elif args.search:
            results = builder.search_nodes(args.search)
            print(f"搜索 '{args.search}' 结果 ({len(results)}):")
            for r in results:
                print(f"  [{r.get('node_type', '?')}] {r.get('node_id', '?')}: {r.get('name', '?')}")
        
        elif args.neighbors:
            neighbors = builder.get_neighbors(args.neighbors)
            print(f"{args.neighbors} 的邻居 ({len(neighbors)}):")
            for n in neighbors:
                print(f"  --[{n.get('edge_type', '?')}]--> {n.get('node_id', '?')}: {n.get('name', '?')}")
        
        else:
            parser.print_help()
    
    finally:
        builder.close()


# ============================================================
# 兼容别名 — 保持旧代码的 import 能正常工作
# ============================================================

# 旧代码使用: from attribute_graph import AttributeGraph
# 新代码应使用: from attribute_graph import GraphBuilder
AttributeGraph = GraphBuilder


if __name__ == '__main__':
    main()
