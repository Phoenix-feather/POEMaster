#!/usr/bin/env python3
"""
POB Build Analyzer — 统一 API

用法:
    # 方式 1: 直接传 share code（首次使用）
    from pob_calc import POBCalculator
    bid = POBCalculator.save_build(share_code)      # 缓存到磁盘
    calc = POBCalculator.from_current()              # 从缓存加载

    # 方式 2: 已有缓存，直接加载
    calc = POBCalculator.from_current()
    result = calc.full_analysis(skill_name="spark")

    # 方式 3: 传统方式（不使用缓存）
    calc = POBCalculator(share_code="eNrt...")
"""
from pathlib import Path

from .decoder import decode_share_code
from .build_parser import parse_build_xml
from .build_cache import BuildCache, format_build_list
from .runtime import create_runtime
from .build_loader import load_all
from . import calculator as _calc
from . import what_if as _whatif

# 模块级单例缓存管理器
_cache = BuildCache()


class POBCalculator:
    """POB 构筑计算器。

    从 share code 或 XML 加载构筑，驱动 POB 原生计算引擎。
    支持 What-If 分析（天赋点增删、装备替换、modifier 注入）。

    推荐使用缓存工厂方法:
        POBCalculator.save_build(share_code)  → 缓存 share code
        POBCalculator.from_current()          → 从当前缓存加载
        POBCalculator.list_builds()           → 查看缓存列表

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

        # 缓存 build_id（仅通过缓存工厂方法创建时设置）
        self._build_id = None

    # === 缓存工厂方法 ===

    @classmethod
    def save_build(cls, share_code: str) -> str:
        """保存 share code 到缓存并设为当前活跃构筑。

        Args:
            share_code: POB 分享码

        Returns:
            build_id 字符串
        """
        return _cache.save(share_code)

    @classmethod
    def from_current(cls, pob_path: str = None) -> "POBCalculator":
        """从当前活跃缓存构筑创建计算器。

        Raises:
            FileNotFoundError: 无活跃构筑
        """
        build_id = _cache.get_current_id()
        if not build_id:
            raise FileNotFoundError("没有活跃构筑，请先调用 save_build() 缓存一个构筑")
        xml_text = _cache.load(build_id)
        inst = cls(xml_text=xml_text, pob_path=pob_path)
        inst._build_id = build_id
        return inst

    @classmethod
    def from_build_id(cls, build_id: str,
                      pob_path: str = None) -> "POBCalculator":
        """从指定缓存构筑创建计算器。

        Args:
            build_id: 构筑 ID
        """
        xml_text = _cache.load(build_id)
        inst = cls(xml_text=xml_text, pob_path=pob_path)
        inst._build_id = build_id
        return inst

    @staticmethod
    def list_builds() -> str:
        """列出所有缓存构筑（格式化表格）。"""
        builds = _cache.list()
        return format_build_list(builds)

    @staticmethod
    def remove_builds(indices: str) -> list[str]:
        """按序号删除缓存构筑。

        序号基于 list_builds() 显示的顺序（1-based）。
        支持: "3", "2-5", "1,3,5", "2-4,7"
        """
        return _cache.remove(indices)

    @staticmethod
    def clear_builds():
        """清空全部构筑缓存。"""
        _cache.clear_all()

    @staticmethod
    def set_current_build(build_id: str):
        """切换当前活跃构筑。"""
        _cache.set_current(build_id)

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

    def sensitivity_analysis(self, profiles: list[str] = None,
                             target_stat: str = "TotalDPS",
                             target_pct: float = 30.0,
                             is_spell: bool = None) -> list[dict]:
        """等基准灵敏度分析。

        固定 DPS 增幅目标（默认 +30%），通过二分搜索反算每个维度达到该目标所需的注入值。
        所有维度在相同 DPS 增幅下比较"所需投入"，值越小 = 性价比越高 = 优化杠杆越大。

        注：MAIN 模式已含穿透/敌人抗性计算。穿透 profile 若显示无法达到，
        表示构筑配置中敌人抗性已被诅咒/曝光压至负值（穿透无法降低负抗）。

        POE2 机制：法术不受固定伤害(flat damage)加成。
        当 is_spell=True（或自动检测为法术）时，自动排除攻击专属 profile。

        INC 合并说明（v1.0.6 修复）：
        POB 的伤害 INC 在同一乘区内合并计算，例如 Lightning 伤害的 INC 乘区
        包含 Damage + LightningDamage + ElementalDamage 三个 stat 的总和。
        公式中的 current_total 显示的是合并后的 INC 总值，而非单个 stat。

        Args:
            profiles: 要测试的 profile key 列表，None = 全部
                      可选 key 见 what_if.SENSITIVITY_PROFILES
            target_stat: 排序依据的目标 stat（默认 "TotalDPS"）
            target_pct: DPS 增幅目标百分比（默认 30.0 = +30%）
            is_spell: 主技能是否法术。None=自动检测。

        Returns:
            按所需值升序排列（值越小 = 性价比越高）的列表，每项包含:
            - key, label (英文), description (中文)
            - mod_name, mod_type
            - needed_value: 达到目标所需的注入值（None=无法达到）
            - target_pct: 目标增幅百分比
            - actual_pct: 实际增幅百分比
            - current_total: 当前 modDB 合并汇总值
            - formula: 一行简洁的增量公式
            - sample_diff: 注入后的完整差异字典
        """
        return _whatif.sensitivity_analysis(
            self._lua, self._calcs,
            profiles=profiles,
            target_stat=target_stat,
            target_pct=target_pct,
            baseline=self.get_baseline(),
            is_spell=is_spell,
        )

    def passive_node_analysis(self, dps_stat: str = "TotalDPS",
                              ehp_stat: str = "TotalEHP") -> list[dict]:
        """天赋价值分析：逐个移除 Notable/Keystone 天赋，评估 DPS 和 EHP 影响。

        Returns:
            按 DPS 损失降序排列的列表，每项包含:
            - id, name, type (Notable/Keystone)
            - dps_before, dps_after, dps_delta, dps_pct
            - ehp_before, ehp_after, ehp_delta, ehp_pct
            - category: "进攻" / "防御" / "混合" / "无效"
        """
        return _whatif.passive_node_analysis(
            self._lua, self._calcs,
            baseline=self.get_baseline(),
            dps_stat=dps_stat,
            ehp_stat=ehp_stat,
        )

    def passive_node_exploration(self, dps_stat: str = "TotalDPS",
                                 ehp_stat: str = "TotalEHP",
                                 min_dps_pct: float = 0.5) -> list[dict]:
        """天赋探索：逐个添加未分配的 Notable/Keystone 天赋，评估 DPS 和 EHP 收益。

        使用 POB 原生 override.addNodes 机制，不修改 build 对象。
        注意：绕过了路径连通性检查，部分节点实际游戏中可能无法直接点出。

        Args:
            dps_stat: DPS 指标名（默认 TotalDPS）
            ehp_stat: EHP 指标名（默认 TotalEHP）
            min_dps_pct: 最小变化百分比阈值（低于此不返回，默认 0.5%）

        Returns:
            按 DPS 增益降序排列的列表，每项包含:
            - id, name, type (Notable/Keystone)
            - dps_before, dps_after, dps_delta, dps_pct
            - ehp_before, ehp_after, ehp_delta, ehp_pct
            - category: "进攻" / "防御" / "混合" / "无效"
        """
        return _whatif.passive_node_exploration(
            self._lua, self._calcs,
            baseline=self.get_baseline(),
            dps_stat=dps_stat,
            ehp_stat=ehp_stat,
            min_dps_pct=min_dps_pct,
        )

    def diagnose_jewels(self, dps_stat: str = "TotalDPS") -> list[dict]:
        """诊断构筑中所有珠宝的加载状态和 DPS 贡献。

        检查每个珠宝是否正确加载、mod 是否被解析、是否影响 DPS。
        特别关注 Megalomaniac 等通过 "Allocates" 分配天赋的珠宝。

        对于 GrantedPassive 珠宝，会同时测试：
        1. 移除物品后的 DPS 变化（item_mods 贡献）
        2. 移除 granted 节点后的 DPS 变化（granted_passives 贡献）
        取两者中影响更大的作为 dps_pct。

        Returns:
            [{slot_name, node_id, item_id, name, base_type, rarity,
              mod_count, mods, granted_passives,
              dps_pct (总 DPS 贡献),
              granted_dps_pct (仅 granted 节点的 DPS 贡献, 仅 GrantedPassive 珠宝有),
              dps_source ("item_mods" / "granted_passives"),
              status}, ...]
            status: "ok" / "empty" / "no_base" / "no_mods"
        """
        return _whatif.diagnose_jewels(
            self._lua, self._calcs,
            baseline=self.get_baseline(),
            dps_stat=dps_stat,
        )

    def dps_breakdown(self) -> dict:
        """DPS 来源拆解 — 将当前 DPS 的每个公式项拆解到具体来源。

        Output-driven：从 output.* 非零值判断活跃公式组件，
        对每个组件调用 skillModList:Tabulate() 获取 mod 来源。
        两层粒度：按公式项分组，每组内按 source 分类。
        Label 可读化：天赋→名称，装备→物品名，技能→宝石名。

        Returns:
            {
                "total_dps": float,
                "average_hit": float,
                "speed": float,
                "combined_dps": float,
                "active_damage_types": [str],      # 如 ["Lightning", "Cold"]
                "formula_items": [
                    {
                        "key": str,                 # 如 "Lightning_Damage_INC"
                        "formula_name": str,        # 如 "Lightning Damage INC"
                        "total_value": float,       # 汇总值
                        "display_value": str,       # 可读展示（如 "137%", "x 1.39"）
                        "category_summary": {       # 按来源类别汇总
                            "Tree": float,
                            "Item": float,
                            "Skill": float,
                            ...
                        },
                        "sources": [                # 逐条来源明细
                            {
                                "source": str,      # 原始 source 标识
                                "label": str,       # 可读名称（天赋名/物品名/宝石名）
                                "category": str,    # Tree/Item/Skill/Base/Config/Other
                                "value": float,     # 贡献值
                                "mod_name": str,    # mod 名称
                            }, ...
                        ]
                    }, ...
                ]
            }
        """
        return _whatif.dps_breakdown(
            self._lua, self._calcs,
            baseline=self.get_baseline(),
        )

    def full_analysis(self, target_pct: float = 20.0,
                      exploration_min_pct: float = 0.5,
                      skill_name: str = None) -> dict:
        """完整构筑分析流程 — 一次调用完成所有分析。

        包含：基线计算、灵敏度分析、天赋价值分析、天赋探索、珠宝诊断、
        DPS 来源拆解、光环与精魄分析。
        结果可直接用于构筑优化决策，无需临时脚本。

        如果当前实例是通过缓存工厂方法（from_current / from_build_id）创建的，
        分析结果会自动持久化到构筑缓存目录：
          - analysis_{skill}.json  （原始数据）
          - report_{skill}.md     （格式化报告）

        Args:
            target_pct: 灵敏度分析 DPS 增幅目标（默认 20%）
            exploration_min_pct: 天赋探索最低 DPS 变化阈值（默认 0.5%）
            skill_name: 指定主技能名称（自然语言，大小写不敏感，支持部分匹配）。
                        例如 "ball lightning"、"Comet"、"ball"。
                        若为 None，使用构筑默认主技能；若默认 DPS=0 则自动选最高 DPS 技能。

        Returns:
            {
                "baseline": {stat: value},
                "main_skill": {"name": str, "castTime": float},
                "skill_flags": {"is_spell": bool, ...},
                "sensitivity": [灵敏度排序列表, 含 dps_per_unit],
                "talent_value": [已分配天赋价值列表],
                "talent_exploration": [未分配天赋探索列表],
                "jewel_diagnosis": [珠宝诊断列表],
                "dps_breakdown": {DPS 来源拆解，详见 dps_breakdown()},
                "aura_spirit": {光环与精魄分析，详见 aura_spirit_analysis()},
            }
        """
        result = _whatif.full_analysis(
            self._lua, self._calcs,
            target_pct=target_pct,
            exploration_min_pct=exploration_min_pct,
            skill_name=skill_name,
        )
        # 更新缓存的基线
        self._baseline = result["baseline"]

        # 自动持久化到缓存目录
        if self._build_id:
            try:
                actual_skill = result.get("main_skill", {}).get("name", skill_name or "unknown")
                report_md = _whatif.format_report(result)
                _cache.save_report(self._build_id, actual_skill, result, report_md)
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning("报告持久化失败: %s", e)

        return result

    @staticmethod
    def format_report(data: dict) -> str:
        """将 full_analysis() 返回的数据格式化为 Markdown 表格报告。

        所有详细来源均以表格展示，提高可读性。

        Args:
            data: full_analysis() 的返回值

        Returns:
            完整的 Markdown 报告字符串
        """
        return _whatif.format_report(data)

    @staticmethod
    def get_report(skill_name: str, build_id: str = None,
                   fmt: str = "md") -> str | None:
        """读取已保存的分析报告。

        Args:
            skill_name: 技能名称（如 "spark", "comet"）
            build_id: 构筑 ID，None 则使用当前活跃构筑
            fmt: "md"（Markdown 报告）或 "json"（原始 JSON 数据）

        Returns:
            文件内容字符串，不存在则返回 None
        """
        bid = build_id or _cache.get_current_id()
        if not bid:
            return None
        return _cache.load_report(bid, skill_name, fmt)

    @staticmethod
    def get_report_path(skill_name: str, build_id: str = None,
                        fmt: str = "md") -> str | None:
        """获取已保存报告的文件路径。

        Args:
            skill_name: 技能名称
            build_id: 构筑 ID，None 则使用当前活跃构筑
            fmt: "md" 或 "json"

        Returns:
            绝对路径字符串，不存在则返回 None
        """
        bid = build_id or _cache.get_current_id()
        if not bid:
            return None
        path = _cache.get_report_path(bid, skill_name, fmt)
        return str(path) if path else None
