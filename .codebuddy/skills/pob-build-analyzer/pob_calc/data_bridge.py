"""
POE Data Bridge - 数据桥接模块

从 poe-data-miner 的 entities.db 读取结构化游戏数据，供 pob-build-analyzer 使用。

使用方式:
    from pob_calc.data_bridge import POEDataBridge
    bridge = POEDataBridge()
    more_val = bridge.get_skill_stat_at_level("TrinityPlayer", 24, 0)
"""

import sqlite3
import json
import logging
import re
from pathlib import Path
from typing import Optional, List, Dict, Tuple

logger = logging.getLogger(__name__)


# 条件映射表：从 stat 名称中的条件字符串到可读描述
_CONDITION_MAP = {
    "one_other_support": "1个其他辅助",
    "no_other_supports": "无其他辅助",
    # 可扩展更多条件...
}


class POEDataBridge:
    """POE 数据桥接器 - 从 entities.db 读取游戏数据。"""
    
    def __init__(self):
        """初始化数据桥接器，连接到 entities.db。"""
        # 路径解析: pob_calc/ → pob-build-analyzer/ → .codebuddy/skills/ → poe-data-miner/
        self.db_path = (
            Path(__file__).parent.parent.parent  # pob-build-analyzer
            / "poe-data-miner"
            / "knowledge_base"
            / "entities.db"
        )
        
        if not self.db_path.exists():
            raise FileNotFoundError(
                f"entities.db not found at {self.db_path}. "
                "Ensure poe-data-miner is installed and knowledge_base is initialized."
            )
        
        self._conn: Optional[sqlite3.Connection] = None
        logger.debug(f"POEDataBridge initialized with db_path: {self.db_path}")
    
    @property
    def conn(self) -> sqlite3.Connection:
        """延迟创建数据库连接。"""
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row
        return self._conn
    
    def close(self):
        """关闭数据库连接。"""
        if self._conn:
            self._conn.close()
            self._conn = None
    
    def get_entity(self, entity_id: str) -> Optional[dict]:
        """获取完整实体数据。
        
        Args:
            entity_id: 实体 ID（如 "TrinityPlayer"）
        
        Returns:
            实体数据字典，不存在则返回 None
        """
        row = self.conn.execute(
            "SELECT * FROM entities WHERE id = ?", (entity_id,)
        ).fetchone()
        
        if not row:
            return None
        
        result = dict(row)
        return result
    
    def get_skill_stat_at_level(
        self, skill_id: str, level: int, stat_index: int = 0
    ) -> float:
        """获取技能在指定等级的 stat 值。
        
        Args:
            skill_id: 技能 ID（如 "TrinityPlayer"）
            level: 宝石等级
            stat_index: stat 索引（0-based，对应 stat_sets.levels[level].values[stat_index]）
        
        Returns:
            stat 值，不存在则返回 0.0
        """
        row = self.conn.execute(
            "SELECT stat_sets FROM entities WHERE id = ?", (skill_id,)
        ).fetchone()
        
        if not row or not row["stat_sets"]:
            return 0.0
        
        try:
            stat_sets = json.loads(row["stat_sets"])
            levels = stat_sets.get("levels", {})
            level_key = str(level)
            
            if level_key in levels:
                values = levels[level_key].get("values", [])
                if stat_index < len(values):
                    return float(values[stat_index])
            
            # 向下查找最近的等级
            for lv in range(level, 0, -1):
                lk = str(lv)
                if lk in levels:
                    values = levels[lk].get("values", [])
                    if stat_index < len(values):
                        return float(values[stat_index])
            
            return 0.0
        except (json.JSONDecodeError, KeyError, IndexError, TypeError) as e:
            logger.warning(f"Failed to get stat for {skill_id} level {level}: {e}")
            return 0.0
    
    def get_support_level_bonus(self, support_id: str) -> int:
        """获取辅助宝石给被辅助技能的等级加成。
        
        Args:
            support_id: 辅助技能 ID（如 "SupportDiallasDesirePlayer"）
        
        Returns:
            等级加成数值，不存在则返回 0
        """
        row = self.conn.execute(
            "SELECT constant_stats FROM entities WHERE id = ?", (support_id,)
        ).fetchone()
        
        if not row or not row["constant_stats"]:
            return 0
        
        try:
            constant_stats = json.loads(row["constant_stats"])
            for stat in constant_stats:
                if isinstance(stat, list) and len(stat) >= 2:
                    stat_name = stat[0]
                    # 匹配所有形式的 level 加成 stat
                    if "supported_active_skill_gem_level" in stat_name:
                        return int(stat[1])
            return 0
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning(f"Failed to get level bonus for {support_id}: {e}")
            return 0
    
    def get_quality_speed_per_q(self, skill_id: str) -> float:
        """获取技能品质对应的 Speed INC 每品质点数。
        
        Args:
            skill_id: 技能 ID（如 "TrinityPlayer"）
        
        Returns:
            Speed INC 每品质点数，不存在则返回 0.0
        """
        row = self.conn.execute(
            "SELECT quality_stats FROM entities WHERE id = ?", (skill_id,)
        ).fetchone()
        
        if not row or not row["quality_stats"]:
            return 0.0
        
        try:
            quality_stats = json.loads(row["quality_stats"])
            for stat in quality_stats:
                if isinstance(stat, list) and len(stat) >= 2:
                    stat_name = stat[0]
                    # 匹配 speed 相关的 quality stat
                    if "speed" in stat_name.lower():
                        return float(stat[1])
            return 0.0
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning(f"Failed to get quality speed for {skill_id}: {e}")
            return 0.0
    
    def _parse_stat_name(self, stat_name: str, value: int) -> Tuple[str, Optional[str]]:
        """解析 stat 名称，提取效果和条件。

        Args:
            stat_name: stat 名称（如 "supported_active_skill_gem_level_+"）
            value: stat 值

        Returns:
            (效果描述, 条件描述) 元组，条件为 None 表示无条件
        """
        # 效果类型
        if "level_+" in stat_name:
            effect = f"+{value} level"
        elif "quality_%" in stat_name:
            effect = f"+{value}% quality"
        else:
            # 其他类型的 stat，直接显示
            effect = f"{stat_name}: {value}"

        # 条件提取
        condition = None
        if "_if_" in stat_name:
            match = re.search(r'_if_(.+)$', stat_name)
            if match:
                cond_str = match.group(1)
                # 使用映射表转换
                condition = _CONDITION_MAP.get(cond_str, cond_str.replace('_', ' '))

        return effect, condition
    
    def get_support_effects(self, support_id: str) -> List[Dict]:
        """获取辅助宝石的所有效果和条件。

        Args:
            support_id: 辅助技能 ID（如 "SupportDiallasDesirePlayer"）

        Returns:
            效果列表，每个元素为：
            {
                "effect": 效果描述,
                "condition": 条件描述或 None,
                "stat": stat 名称,
                "value": stat 值
            }
        """
        row = self.conn.execute(
            "SELECT constant_stats FROM entities WHERE id = ?", (support_id,)
        ).fetchone()

        if not row or not row["constant_stats"]:
            return []

        try:
            constant_stats = json.loads(row["constant_stats"])
            effects = []

            for stat in constant_stats:
                if isinstance(stat, list) and len(stat) >= 2:
                    stat_name = stat[0]
                    value = stat[1]

                    effect, condition = self._parse_stat_name(stat_name, value)

                    effects.append({
                        "effect": effect,
                        "condition": condition,
                        "stat": stat_name,
                        "value": value,
                    })

            return effects
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning(f"Failed to get effects for {support_id}: {e}")
            return []
    
    def get_support_by_name(self, name: str) -> Optional[str]:
        """根据辅助宝石名称查找 entity ID。

        支持精确匹配和模糊匹配（去除空格和特殊字符）。
        优先返回技能 ID（格式：Support...Player）。

        Args:
            name: 辅助宝石显示名称（如 "Dialla's Desire"）

        Returns:
            entity ID（如 "SupportDiallasDesirePlayer"），未找到返回 None
        """
        # 1. 尝试精确匹配，优先返回技能 ID
        rows = self.conn.execute(
            "SELECT id FROM entities WHERE name = ?",
            (name,)
        ).fetchall()
        
        if rows:
            # 优先返回 Support...Player 格式的 ID
            for row in rows:
                if row['id'].startswith('Support') and row['id'].endswith('Player'):
                    return row['id']
            # 否则返回第一个结果
            return rows[0]['id']

        # 2. 尝试模糊匹配（分词模式）
        # 清理名称：移除撇号，按空格分词
        words = name.replace("'", "").split()
        if words:
            # 构建模式：每个词作为独立片段
            pattern = "%".join(["%Support"] + words + ["Player%"])
            
            row = self.conn.execute(
                "SELECT id FROM entities WHERE id LIKE ?",
                (pattern,)
            ).fetchone()
            
            if row:
                return row['id']

        return None

