#!/usr/bin/env python3
"""
POB Build Analyzer — 统一 API

用法:
    from pob_calc import POBCalculator

    calc = POBCalculator(share_code="eNrtfWlz4ziyJv...")
    result = calc.calculate()
    diff = calc.what_if_nodes(add=[48524])
"""
from pathlib import Path

from .decoder import decode_share_code
from .build_parser import parse_build_xml
from .runtime import create_runtime
from .build_loader import load_all
from . import calculator as _calc
from . import what_if as _whatif


class POBCalculator:
    """POB 构筑计算器。

    从 share code 或 XML 加载构筑，驱动 POB 原生计算引擎。
    支持 What-If 分析（天赋点增删、装备替换、modifier 注入）。

    Args:
        share_code: POB 分享码（Base64 编码字符串）
        xml_text: POB XML 文本（与 share_code 二选一）
        xml_path: POB XML 文件路径（与 share_code/xml_text 二选一）
        pob_path: POBData 目录路径
    """

    def __init__(self, share_code: str = None, xml_text: str = None,
                 xml_path: str = None, pob_path: str = None):
        # 确定 XML 来源
        if share_code:
            self._xml_text = decode_share_code(share_code)
        elif xml_text:
            self._xml_text = xml_text
        elif xml_path:
            self._xml_text = Path(xml_path).read_text(encoding='utf-8')
        else:
            raise ValueError("必须提供 share_code、xml_text 或 xml_path 之一")

        # 解析 XML
        self._build_info = parse_build_xml(self._xml_text)

        # 创建 Lua 运行时
        pob = Path(pob_path) if pob_path else None
        self._lua, self._calcs, self._load_errors = create_runtime(pob)

        # 设置 calcs 全局引用
        self._lua.globals()['calcs'] = self._calcs

        # 加载构筑数据
        self._load_result = load_all(self._lua, self._build_info)

        # 缓存基线结果
        self._baseline = None

    @property
    def build_info(self) -> dict:
        """获取解析后的构筑信息。"""
        return self._build_info

    @property
    def load_result(self) -> dict:
        """获取数据加载统计。"""
        return self._load_result

    @property
    def load_errors(self) -> list:
        """获取模块加载错误列表。"""
        return self._load_errors

    def calculate(self, mode: str = "MAIN") -> dict[str, float]:
        """运行 POB 计算引擎，返回完整 output。

        Args:
            mode: "MAIN" (默认，对应 POB 主面板) 或 "CALCS"

        Returns:
            {stat_name: float_value} 字典
        """
        result = _calc.calculate(self._lua, self._calcs, mode)
        self._baseline = result
        return result

    def get_baseline(self) -> dict[str, float]:
        """获取基线计算结果（如未计算则自动执行）。"""
        if self._baseline is None:
            self._baseline = self.calculate()
        return self._baseline

    def get_active_skills(self) -> list[str]:
        """获取主动技能名称列表。"""
        return _calc.get_active_skills(self._lua, self._calcs)

    def get_main_skill(self) -> dict:
        """获取主技能信息 {name, castTime}。"""
        return _calc.get_main_skill(self._lua, self._calcs)

    def get_pob_player_stats(self) -> dict[str, float]:
        """获取 POB XML 中的 PlayerStats。"""
        stats = self._build_info.get('playerStats', {})
        return {k: float(v) for k, v in stats.items()}

    def compare_with_pob(self, keys: list[str] = None) -> list[dict]:
        """将计算结果与 POB PlayerStats 对比。

        Returns:
            [{stat, pob_value, calc_value, delta_pct, match}, ...]
        """
        return _calc.compare_with_pob(self._lua, self._calcs, self._build_info, keys)

    # === What-If API ===

    def what_if_mod(self, mod_name: str, mod_type: str, value: float) -> dict:
        """注入 modifier 并对比。

        Args:
            mod_name: 如 "Life", "Evasion", "PhysicalDamage"
            mod_type: "BASE", "INC", "MORE"
            value: 数值

        Returns:
            {stat: (before, after, delta)} 有变化的字段
        """
        return _whatif.what_if_mod(
            self._lua, self._calcs, mod_name, mod_type, value,
            baseline=self.get_baseline()
        )

    def what_if_nodes(self, add: list[int] = None, remove: list[int] = None) -> dict:
        """临时增删天赋点并对比。

        Args:
            add: 要添加的节点 ID 列表
            remove: 要移除的节点 ID 列表

        Returns:
            {stat: (before, after, delta)} 有变化的字段
        """
        return _whatif.what_if_nodes(
            self._lua, self._calcs, add=add, remove=remove,
            baseline=self.get_baseline()
        )

    def what_if_item(self, slot_name: str, item_raw_text: str) -> dict:
        """临时替换装备并对比。

        Args:
            slot_name: 如 "Helmet", "Body Armour", "Weapon 1"
            item_raw_text: 新装备原始文本

        Returns:
            {stat: (before, after, delta)} 有变化的字段
        """
        return _whatif.what_if_item(
            self._lua, self._calcs, slot_name, item_raw_text,
            baseline=self.get_baseline()
        )
