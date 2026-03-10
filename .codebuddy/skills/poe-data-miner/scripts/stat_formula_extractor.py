#!/usr/bin/env python3
"""
Meta缺口公式提取器 (Gap Formula Extractor) v6

从Meta技能的实体完整数据中提取POB未实现的公式:
- 能量获取公式 (energy_gain)
- 最大能量公式 (max_energy)
- 伤害修正公式 (damage_modifier)
- 触发条件 (trigger_condition)

数据来源:
- entities.db 中的 Meta 技能实体 (constantStats, stats, qualityStats, skill_types)
- entities.db 中的 Support 辅助实体 (requireSkillTypes 含 GeneratesEnergy)
- entities.db 中的 hidden Support 实体 (SupportMeta*, 如果存在)
- entities.db 中的 passive_node / ascendancy_node 实体 (stat_descriptions 字段)
- entities.db 中的 mod_affix 实体 (stat_descriptions 字段)
- entities.db 中的非Meta技能实体 (active_skill_energy_generated_+%_final)
- StatDescriptions/skill_stat_descriptions.lua 中的精确描述文本 (决定公式修正因子)
- StatDescriptions/stat_descriptions.lua 中的能量stat分类谱 (INC/MORE/条件/特殊)

v6 核心变更 (相对于v5):
- 统一数据访问模式: 天赋/装备/技能都从实体库查询
- 修复实体库字段映射: 使用 stat_descriptions 统一字段
- 移除文件扫描: 不再直接扫描 Mod*.lua 文件

v5 核心变更 (相对于v4):
- 新增装备词缀能量修饰符扫描: ModJewel/ModCorrupted/ModItemExclusive/ModRunes/ModScalability
- 完整覆盖所有能量修饰符来源 (天赋+辅助+装备+被触发法术)

v4 核心变更 (相对于v3):
- 扩展搜索范围: 被动天赋/升华节点中的能量INC/MORE文本模式
- 扩展搜索范围: 被触发法术的 active_skill_energy_generated_+%_final (MORE惩罚)
- 完整能量stat分类谱: 6种能量相关stat的INC/MORE/条件/特殊分类
- 修正 "MORE=0 符合预期" 的错误结论

v3 核心变更 (相对于v2):
- 动态收集INC/MORE修饰符: 扫描实体的 stats/constantStats/qualityStats 全部字段
- 查询外部Support: 找到 requireSkillTypes 含 GeneratesEnergy 的辅助宝石
- 公式文本使用实际收集到的stat名称，不再硬编码 'energy_generated_+%' 或 'more_energy_i'
- 每个公式的 parameters 中记录完整的数据证据链

输出到 formulas.db 的 gap_formulas 表
"""

import re
import sqlite3
import json
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Set
from dataclasses import dataclass, asdict


@dataclass
class GapFormula:
    """缺口公式"""
    id: str                  # 唯一ID
    entity_id: str           # 关联的技能实体ID
    entity_name: str         # 实体名称
    formula_type: str        # energy_gain / max_energy / damage_modifier / trigger_condition
    formula_text: str        # 人可读公式
    parameters: str          # JSON: 参数名→值映射
    stat_sources: str        # JSON: 来源stat列表
    description: str         # 公式描述（来自StatDescriptions的精确文本）
    confidence: float        # 置信度 (0-1)
    pob_status: str          # "unimplemented" / "partial" / "commented_out"
    notes: str               # 补充说明


@dataclass
class EnergyModifier:
    """从实体数据动态收集到的能量修饰符"""
    stat_name: str           # stat全名
    mod_type: str            # 'INC' 或 'MORE'
    source_field: str        # 来源字段: stats / constantStats / qualityStats
    source_entity: str       # 来源实体ID
    value: Optional[float]   # 值（constantStats有值，stats无值）
    per_quality: bool        # 是否按品质缩放（qualityStats）
    evidence: str            # 数据证据描述


# ────────────────────────────────────────────────────────
# INC/MORE 判定规则 (来自POB stat命名惯例，非硬编码)
# ────────────────────────────────────────────────────────
#
# POB stat命名惯例:
#   stat_name_+%        → INC类型 (increased/reduced, 加法叠加)
#   stat_name_+%_final  → MORE类型 (more/less, 乘法独立)
#
# 完整能量stat分类谱 (来自StatDescriptions stat_descriptions.lua):
#   ┌───────────────────────────────────────────────────────────────────────┐
#   │ Stat ID                              │ 类型   │ 描述文本                                              │
#   ├───────────────────────────────────────┼────────┼───────────────────────────────────────────────────────┤
#   │ energy_generated_+%                   │ INC    │ "Meta Skills gain X% increased/reduced Energy"        │
#   │ ascendancy_energy_generated_+%_final  │ MORE   │ "Meta Skills gain X% more/less Energy"                │
#   │ energy_generated_+%_if_crit_recently  │ 条件INC│ "...increased Energy if dealt Crit Recently"          │
#   │ energy_generated_+%_on_full_mana      │ 条件INC│ "...increased Energy while on Full Mana"              │
#   │ energy_generation_is_doubled          │ 特殊×2 │ "Energy Generation is doubled"                        │
#   │ active_skill_energy_generated_+%_final│ MORE   │ 技能专属MORE惩罚 (Incinerate -98%, FlameWall -50%等)  │
#   └───────────────────────────────────────┴────────┴───────────────────────────────────────────────────────┘
#
# 数据来源层级 (v5扩展):
#   1. Meta实体自身 stats[] — 声明stat存在，值由levels表按等级插值
#   2. Meta实体自身 constantStats[] — 固定值stat
#   3. Meta实体自身 qualityStats[] — 按品质缩放的stat (如 0.75 per quality)
#   4. 外部Support辅助 constantStats[] — 来自辅助宝石的加成
#      (通过 requireSkillTypes 含 GeneratesEnergy 关联)
#   5. [v4新增] 被动天赋节点 (passive_node) — 描述文本含 "Meta Skills gain X% increased Energy"
#   6. [v4新增] 升华天赋节点 (ascendancy_node) — 描述文本含 "Meta Skills gain X% more Energy"
#      → 对应 ascendancy_energy_generated_+%_final (MORE)
#   7. [v4新增] 被触发法术实体 constantStats[] — active_skill_energy_generated_+%_final
#      → 如 Incinerate(-98%), FlameWall(-50%), SolarOrb(-50%)
#   8. [v4新增] 条件INC: energy_generated_+%_if_crit_recently, energy_generated_+%_on_full_mana
#   9. [v4新增] 特殊: energy_generation_is_doubled (×2)
#  10. [v5新增] 装备词缀 (ModJewel/ModCorrupted/ModItemExclusive/ModRunes/ModScalability)
#      → 如 "Meta Skills gain (4-8)% increased Energy" (珠宝词缀)
#      → 如 "Meta Skills gain (20-30)% increased Energy" (腐化词缀)
#
# ────────────────────────────────────────────────────────

# 能量相关INC/MORE stat的识别模式
# 匹配所有 energy 相关的 _+% 和 _+%_final 后缀 stat
ENERGY_INC_PATTERN = re.compile(r'.*energy\w*_\+%$')          # INC: 以 _+% 结尾
ENERGY_MORE_PATTERN = re.compile(r'.*energy\w*_\+%_final$')   # MORE: 以 _+%_final 结尾

# v4新增: 条件INC stat模式
ENERGY_CONDITIONAL_INC_STATS = {
    'energy_generated_+%_if_crit_recently': 'INC_CONDITIONAL',
    'energy_generated_+%_on_full_mana': 'INC_CONDITIONAL',
}
# v4新增: 特殊能量stat
ENERGY_SPECIAL_STATS = {
    'energy_generation_is_doubled': 'SPECIAL_DOUBLE',
}

# v4新增: 被动天赋节点描述文本中的能量模式 (tree.lua存储的是英文描述文本)
PASSIVE_ENERGY_INC_PATTERN = re.compile(
    r'Meta Skills gain (\d+)% (?:increased|reduced) Energy',
    re.IGNORECASE
)
PASSIVE_ENERGY_MORE_PATTERN = re.compile(
    r'Meta Skills gain (\d+)% (?:more|less) Energy',
    re.IGNORECASE
)
PASSIVE_ENERGY_CONDITIONAL_PATTERNS = [
    (re.compile(r'Meta Skills gain (\d+)% (?:increased|reduced) Energy if', re.IGNORECASE),
     'INC_CONDITIONAL', 'energy_generated_+%_if_crit_recently'),
    (re.compile(r'Meta Skills gain (\d+)% (?:increased|reduced) Energy while', re.IGNORECASE),
     'INC_CONDITIONAL', 'energy_generated_+%_on_full_mana'),
]
PASSIVE_ENERGY_DOUBLED_PATTERN = re.compile(
    r'Energy Generation is doubled',
    re.IGNORECASE
)
PASSIVE_INVOCATION_ENERGY_PATTERN = re.compile(
    r'Invocated skills have (\d+)% (?:increased|reduced) Maximum Energy',
    re.IGNORECASE
)

# stat名称匹配模式 (用于识别能量获取事件的stat类别)
STAT_PATTERN_MONSTER_POWER = re.compile(
    r'(\w+)_gain_(\w+)_centienergy_per_monster_power(?:_on_(\w+))?'
)
STAT_PATTERN_FIXED_EVENT = re.compile(
    r'(\w+)_gain_(\w+)_centienergy_(?:on|when)_(\w+)'
)
STAT_PATTERN_CONTINUOUS = re.compile(
    r'(\w+)_gain_(\w+)_centienergy_per_(\w+)'
)
STAT_PATTERN_MINION_DEATH = re.compile(
    r'(\w+)_gain_(\w+)_energy_per_(\w+)_minion_relative'
)

# 最大能量stat名称模式
MAX_ENERGY_PATTERNS = [
    # 动态型: maximum_energy_per_Xms_total_cast_time
    (re.compile(r'generic_ongoing_trigger_(\d+)_maximum_energy_per_(\w+)ms_total_cast_time'),
     'dynamic', 'max_energy = Σ(socketed_spell_cast_time_ms) × {per_Xms} / 1000'),

    # 固定型: maximum_energy
    (re.compile(r'generic_ongoing_trigger_maximum_energy'),
     'fixed', 'max_energy = {value} / 100'),
]

# 伤害修正模式
DAMAGE_MOD_PATTERNS = [
    (re.compile(r'trigger_meta_gem_damage_\+%_final'), 'damage_modifier',
     'final_damage = base × (1 + {value}/100)'),
]

# StatDescriptions中指示ailment_threshold修正的关键短语
AILMENT_THRESHOLD_PHRASE = "modified by the percentage of the enemy's Ailment Threshold"
# StatDescriptions中指示per Power的关键短语
PER_POWER_PHRASES = ["per Power of enemies", "per enemy Power"]


class StatFormulaExtractor:
    """缺口公式提取器 v6 - 统一数据访问模式（天赋+装备+技能从实体库查询）"""

    def __init__(self, entities_db_path: str, db_path: str, pob_path: str = None):
        self.entities_db_path = Path(entities_db_path)
        self.db_path = Path(db_path)
        self.pob_path = Path(pob_path) if pob_path else None
        self.formulas: List[GapFormula] = []
        # stat名→StatDescriptions精确文本的映射
        self._stat_descriptions: Dict[str, str] = {}
        # 缓存: GeneratesEnergy 辅助宝石列表
        self._energy_support_gems: Optional[List[Dict]] = None
        # v4缓存: 被动天赋/升华节点中的能量修饰符
        self._passive_energy_modifiers: Optional[List[EnergyModifier]] = None
        # v4缓存: 被触发法术的能量MORE惩罚
        self._triggered_spell_more_modifiers: Optional[List[EnergyModifier]] = None
        # v4缓存: 条件INC和特殊stat
        self._conditional_energy_modifiers: Optional[List[EnergyModifier]] = None
        # v5缓存: 装备词缀中的能量修饰符 (v6改用实体库查询)
        self._equipment_energy_modifiers: Optional[List[EnergyModifier]] = None

    def extract_all(self) -> List[GapFormula]:
        """提取所有缺口公式"""
        self.formulas = []

        # Step 0: 加载StatDescriptions映射
        self._load_stat_descriptions()
        print(f"    加载 {len(self._stat_descriptions)} 条能量stat描述")

        # Step 1: 预加载 GeneratesEnergy 辅助宝石
        self._energy_support_gems = self._query_energy_support_gems()
        print(f"    找到 {len(self._energy_support_gems)} 个GeneratesEnergy辅助宝石")

        # Step 1.5 [v4]: 预加载被动/升华天赋节点中的能量修饰符
        self._passive_energy_modifiers = self._query_passive_energy_modifiers()
        passive_inc = sum(1 for m in self._passive_energy_modifiers if m.mod_type == 'INC')
        passive_more = sum(1 for m in self._passive_energy_modifiers if m.mod_type == 'MORE')
        passive_cond = sum(1 for m in self._passive_energy_modifiers if m.mod_type == 'INC_CONDITIONAL')
        passive_special = sum(1 for m in self._passive_energy_modifiers if m.mod_type == 'SPECIAL')
        print(f"    找到 {len(self._passive_energy_modifiers)} 个被动/升华能量修饰符 "
              f"(INC={passive_inc}, MORE={passive_more}, COND={passive_cond}, SPECIAL={passive_special})")

        # Step 1.6 [v4]: 预加载被触发法术的能量MORE惩罚
        self._triggered_spell_more_modifiers = self._query_triggered_spell_energy_more()
        print(f"    找到 {len(self._triggered_spell_more_modifiers)} 个被触发法术能量MORE惩罚")

        # Step 1.7 [v5]: 预加载装备词缀中的能量修饰符
        self._equipment_energy_modifiers = self._scan_equipment_energy_mods()
        eq_inc = sum(1 for m in self._equipment_energy_modifiers if m.mod_type == 'INC')
        eq_more = sum(1 for m in self._equipment_energy_modifiers if m.mod_type == 'MORE')
        eq_cond = sum(1 for m in self._equipment_energy_modifiers if 'condition' in m.evidence.lower())
        print(f"    找到 {len(self._equipment_energy_modifiers)} 个装备词缀能量修饰符 "
              f"(INC={eq_inc}, MORE={eq_more}, 条件={eq_cond})")

        # Step 2: 获取所有Meta技能实体（含完整字段）
        meta_entities = self._get_meta_entities()
        print(f"    找到 {len(meta_entities)} 个Meta技能实体")

        # Step 3: 获取所有隐藏Support实体（如果有的话）
        support_entities = self._get_support_meta_entities()
        print(f"    找到 {len(support_entities)} 个SupportMeta实体")

        # Step 4: 建立Meta→Support关联
        meta_support_map = self._build_meta_support_map(meta_entities, support_entities)

        # Step 5: 从每个Meta技能提取公式
        for entity in meta_entities:
            entity_id = entity['id']
            entity_name = entity.get('name', entity_id)
            data = entity.get('data', {})

            # 关联的SupportMeta数据
            support_data = meta_support_map.get(entity_id, {})

            # ── v4核心: 动态收集实体的INC/MORE修饰符（含被动/升华/被触发法术） ──
            modifiers = self._collect_energy_modifiers(entity)

            # 提取能量获取公式（使用动态收集的修饰符）
            self._extract_energy_gain(entity_id, entity_name, data, modifiers)

            # 提取最大能量公式（通常来自Support）
            self._extract_max_energy(entity_id, entity_name, data, support_data)

            # 提取伤害修正（通常来自Support）
            self._extract_damage_modifier(entity_id, entity_name, data, support_data)

            # 提取触发条件
            self._extract_trigger_condition(entity_id, entity_name, data)

        print(f"    总计提取 {len(self.formulas)} 个缺口公式")
        return self.formulas

    # ================================================================
    # 动态修饰符收集 (v3 核心)
    # ================================================================

    def _collect_energy_modifiers(self, entity: Dict) -> List[EnergyModifier]:
        """
        从实体完整数据中动态收集所有能量相关的INC/MORE修饰符。

        v4扩展搜索范围:
        1. entity['stats'] — 变量stat名列表 (值由levels表按等级插值)
        2. entity['constant_stats'] — 固定值stat [[name, value], ...]
        3. entity['quality_stats'] — 品质缩放stat [[name, value_per_quality], ...]
        4. 外部Support辅助宝石 — requireSkillTypes含GeneratesEnergy的辅助
        5. [v4] 被动天赋节点 — 描述文本中的能量INC (如 "Meta Skills gain 15% increased Energy")
        6. [v4] 升华天赋节点 — 描述文本中的能量MORE (如 "Meta Skills gain X% more Energy")
        7. [v4] 被触发法术 — active_skill_energy_generated_+%_final (MORE惩罚)
        8. [v4] 条件INC — energy_generated_+%_if_crit_recently 等
        9. [v4] 特殊 — energy_generation_is_doubled

        判定规则:
        - stat名以 _+% 结尾且不含 _final → INC
        - stat名以 _+%_final 结尾 → MORE
        - 被动描述文本 "increased" → INC, "more" → MORE
        """
        modifiers: List[EnergyModifier] = []
        entity_id = entity['id']
        data = entity.get('data', {})

        # ── 1. 扫描 stats 列表 (变量stat) ──
        stats_list = self._normalize_stats_list(
            data.get('stats', data.get('stats', entity.get('stats', [])))
        )
        for stat_name in stats_list:
            if not isinstance(stat_name, str):
                continue
            mod = self._classify_modifier(stat_name, None, 'stats', entity_id)
            if mod:
                modifiers.append(mod)

        # ── 2. 扫描 constantStats (固定值stat) ──
        constant_stats = self._normalize_stat_pairs(
            data.get('constant_stats', data.get('constantStats', entity.get('constant_stats', [])))
        )
        for stat_name, stat_value in constant_stats:
            mod = self._classify_modifier(stat_name, stat_value, 'constantStats', entity_id)
            if mod:
                modifiers.append(mod)

        # ── 3. 扫描 qualityStats (品质缩放stat) ──
        quality_stats = self._normalize_stat_pairs(
            data.get('quality_stats', data.get('qualityStats', entity.get('quality_stats', [])))
        )
        for stat_name, stat_value in quality_stats:
            mod = self._classify_modifier(stat_name, stat_value, 'qualityStats', entity_id)
            if mod:
                mod.per_quality = True
                mod.evidence = f"qualityStats of {entity_id}: {stat_name}={stat_value}/quality"
                modifiers.append(mod)

        # ── 4. 扫描外部Support辅助宝石 ──
        if self._energy_support_gems:
            for sup in self._energy_support_gems:
                sup_id = sup['id']
                sup_constants = self._normalize_stat_pairs(
                    sup.get('constant_stats', [])
                )
                for stat_name, stat_value in sup_constants:
                    mod = self._classify_modifier(stat_name, stat_value, 'constantStats', sup_id)
                    if mod:
                        mod.evidence = (
                            f"Support gem {sup_id} "
                            f"(requireSkillTypes: {sup.get('require_skill_types', [])}): "
                            f"{stat_name}={stat_value}"
                        )
                        modifiers.append(mod)

        # ── 5. [v4] 被动天赋/升华节点中的能量修饰符 ──
        if self._passive_energy_modifiers:
            modifiers.extend(self._passive_energy_modifiers)

        # ── 6. [v4] 被触发法术的能量MORE惩罚 ──
        # 注意: 这些是技能专属的MORE惩罚(如Incinerate -98%)
        # 它们不是全局修饰符，但记录在公式中以展示MORE项的存在
        if self._triggered_spell_more_modifiers:
            modifiers.extend(self._triggered_spell_more_modifiers)

        # ── 7. [v5] 装备词缀中的能量修饰符 ──
        # 注意: 这些是装备词缀，玩家可通过装备获得能量修饰符
        # 如珠宝词缀 "Meta Skills gain (4-8)% increased Energy"
        if self._equipment_energy_modifiers:
            modifiers.extend(self._equipment_energy_modifiers)

        return modifiers

    def _classify_modifier(self, stat_name: str, stat_value: Optional[float],
                           source_field: str, source_entity: str) -> Optional[EnergyModifier]:
        """
        判定单个stat是否为能量相关的INC或MORE修饰符。

        规则:
        - 必须包含 'energy' (不区分大小写)
        - 以 _+%_final 结尾 → MORE
        - 以 _+% 结尾 (且不含 _final) → INC
        - 其他 → 不是修饰符 (返回None)
        """
        if not isinstance(stat_name, str):
            return None

        stat_lower = stat_name.lower()
        if 'energy' not in stat_lower:
            return None

        # MORE: _+%_final 结尾
        if ENERGY_MORE_PATTERN.match(stat_name):
            return EnergyModifier(
                stat_name=stat_name,
                mod_type='MORE',
                source_field=source_field,
                source_entity=source_entity,
                value=stat_value,
                per_quality=False,
                evidence=f"{source_field} of {source_entity}: {stat_name}={stat_value}"
            )

        # INC: _+% 结尾 (MORE已在上面匹配，这里不会再匹配到_final)
        if ENERGY_INC_PATTERN.match(stat_name):
            return EnergyModifier(
                stat_name=stat_name,
                mod_type='INC',
                source_field=source_field,
                source_entity=source_entity,
                value=stat_value,
                per_quality=False,
                evidence=f"{source_field} of {source_entity}: {stat_name}={stat_value}"
            )

        return None

    def _normalize_stats_list(self, stats) -> List[str]:
        """归一化stats列表为字符串列表"""
        if isinstance(stats, dict):
            return list(stats.keys())
        if isinstance(stats, list):
            result = []
            for item in stats:
                if isinstance(item, str):
                    result.append(item)
                elif isinstance(item, (list, tuple)) and len(item) >= 1:
                    result.append(str(item[0]))
            return result
        return []

    def _normalize_stat_pairs(self, stats) -> List[Tuple[str, float]]:
        """归一化stat为 (name, value) 对列表"""
        if isinstance(stats, dict):
            return [(k, v) for k, v in stats.items()]
        if isinstance(stats, list):
            result = []
            for item in stats:
                if isinstance(item, (list, tuple)) and len(item) >= 2:
                    result.append((str(item[0]), item[1]))
                elif isinstance(item, dict):
                    name = item.get('stat', item.get('name', ''))
                    value = item.get('value', 0)
                    result.append((str(name), value))
            return result
        return []

    # ================================================================
    # Support辅助宝石查询
    # ================================================================

    def _query_energy_support_gems(self) -> List[Dict]:
        """
        查询 entities.db 中 requireSkillTypes 包含 'GeneratesEnergy' 的辅助宝石。

        这些是能对Meta技能的能量生成产生影响的辅助宝石，如:
        - SupportBoundlessEnergyPlayer (energy_generated_+% = 35)
        - SupportBoundlessEnergyPlayerTwo (energy_generated_+% = 45)
        - SupportEnergyRetentionPlayer 等
        """
        conn = sqlite3.connect(str(self.entities_db_path))
        cursor = conn.cursor()

        cursor.execute('''
            SELECT id, name, constant_stats, stats, require_skill_types, quality_stats
            FROM entities
            WHERE require_skill_types LIKE '%GeneratesEnergy%'
              AND support = 1
        ''')

        gems = []
        for row in cursor.fetchall():
            eid, name, constant_stats, stats, req_types, quality_stats = row
            gems.append({
                'id': eid,
                'name': name or eid,
                'constant_stats': json.loads(constant_stats) if constant_stats else [],
                'stats': json.loads(stats) if stats else [],
                'require_skill_types': json.loads(req_types) if req_types else [],
                'quality_stats': json.loads(quality_stats) if quality_stats else [],
            })

        conn.close()
        return gems

    # ================================================================
    # v4新增: 被动天赋/升华节点能量修饰符查询
    # ================================================================

    def _query_passive_energy_modifiers(self) -> List[EnergyModifier]:
        """
        [v4] 查询 entities.db 中的被动天赋和升华节点，
        从其描述文本中提取能量相关的INC/MORE/条件/特殊修饰符。

        被动节点在tree.lua中存储的是英文描述文本（如 "Meta Skills gain 15% increased Energy"），
        而非stat ID。需要通过文本模式匹配来识别。

        数据格式:
        - entities.type = 'passive_node' 或 'ascendancy_node'
        - entities.stats_node = JSON数组，包含描述文本字符串
        - 如: ["Meta Skills gain 15% increased Energy", "其他效果..."]

        对应StatDescriptions中的stat:
        - "Meta Skills gain X% increased Energy" → energy_generated_+% (INC)
        - "Meta Skills gain X% more Energy" → ascendancy_energy_generated_+%_final (MORE)
        - "Meta Skills gain X% increased Energy if..." → energy_generated_+%_if_crit_recently (条件INC)
        - "Energy Generation is doubled" → energy_generation_is_doubled (特殊×2)
        """
        modifiers: List[EnergyModifier] = []

        conn = sqlite3.connect(str(self.entities_db_path))
        cursor = conn.cursor()

        # 查询所有被动/升华节点的描述文本
        cursor.execute('''
            SELECT id, name, type, stat_descriptions, ascendancy_name
            FROM entities
            WHERE (type = 'passive_node' OR type = 'ascendancy_node')
              AND stat_descriptions IS NOT NULL
              AND stat_descriptions != '[]'
        ''')

        for row in cursor.fetchall():
            eid, name, etype, stat_desc_json, ascendancy = row
            try:
                stats_texts = json.loads(stat_desc_json) if stat_desc_json else []
            except (json.JSONDecodeError, TypeError):
                continue

            if not isinstance(stats_texts, list):
                continue

            for text in stats_texts:
                if not isinstance(text, str):
                    continue

                # ── 检查 MORE 模式（优先于INC，因为"more"比"increased"更稀有） ──
                m = PASSIVE_ENERGY_MORE_PATTERN.search(text)
                if m:
                    value = int(m.group(1))
                    # "less" = 负值
                    if 'less' in text.lower():
                        value = -value
                    modifiers.append(EnergyModifier(
                        stat_name='ascendancy_energy_generated_+%_final',
                        mod_type='MORE',
                        source_field='stats_node (description text)',
                        source_entity=eid,
                        value=value,
                        per_quality=False,
                        evidence=(
                            f"{'Ascendancy' if ascendancy else 'Passive'} node {eid} "
                            f"({name or 'unnamed'}"
                            f"{', ascendancy=' + ascendancy if ascendancy else ''}): "
                            f'"{text}"'
                        )
                    ))
                    continue  # MORE已匹配，不再检查INC

                # ── 检查条件INC模式 ──
                matched_conditional = False
                for pattern, mod_type, stat_id in PASSIVE_ENERGY_CONDITIONAL_PATTERNS:
                    mc = pattern.search(text)
                    if mc:
                        value = int(mc.group(1))
                        if 'reduced' in text.lower():
                            value = -value
                        modifiers.append(EnergyModifier(
                            stat_name=stat_id,
                            mod_type=mod_type,
                            source_field='stats_node (description text)',
                            source_entity=eid,
                            value=value,
                            per_quality=False,
                            evidence=(
                                f"{'Ascendancy' if ascendancy else 'Passive'} node {eid} "
                                f"({name or 'unnamed'}): \"{text}\""
                            )
                        ))
                        matched_conditional = True
                        break
                if matched_conditional:
                    continue

                # ── 检查普通INC模式 ──
                m = PASSIVE_ENERGY_INC_PATTERN.search(text)
                if m:
                    value = int(m.group(1))
                    if 'reduced' in text.lower():
                        value = -value
                    modifiers.append(EnergyModifier(
                        stat_name='energy_generated_+%',
                        mod_type='INC',
                        source_field='stats_node (description text)',
                        source_entity=eid,
                        value=value,
                        per_quality=False,
                        evidence=(
                            f"{'Ascendancy' if ascendancy else 'Passive'} node {eid} "
                            f"({name or 'unnamed'}"
                            f"{', ascendancy=' + ascendancy if ascendancy else ''}): "
                            f'"{text}"'
                        )
                    ))
                    continue

                # ── 检查 Energy Generation is doubled ──
                if PASSIVE_ENERGY_DOUBLED_PATTERN.search(text):
                    modifiers.append(EnergyModifier(
                        stat_name='energy_generation_is_doubled',
                        mod_type='SPECIAL',
                        source_field='stats_node (description text)',
                        source_entity=eid,
                        value=2,
                        per_quality=False,
                        evidence=(
                            f"{'Ascendancy' if ascendancy else 'Passive'} node {eid} "
                            f"({name or 'unnamed'}): \"{text}\""
                        )
                    ))
                    continue

                # ── 检查 Invocated skills Maximum Energy ──
                m = PASSIVE_INVOCATION_ENERGY_PATTERN.search(text)
                if m:
                    value = int(m.group(1))
                    if 'reduced' in text.lower():
                        value = -value
                    modifiers.append(EnergyModifier(
                        stat_name='invocation_maximum_energy_+%',
                        mod_type='INC',
                        source_field='stats_node (description text)',
                        source_entity=eid,
                        value=value,
                        per_quality=False,
                        evidence=(
                            f"{'Ascendancy' if ascendancy else 'Passive'} node {eid} "
                            f"({name or 'unnamed'}): \"{text}\" (Invocation专属)"
                        )
                    ))

        conn.close()
        return modifiers

    def _query_triggered_spell_energy_more(self) -> List[EnergyModifier]:
        """
        [v4] 查询 entities.db 中非Meta技能的 active_skill_energy_generated_+%_final。

        这些是被触发法术自身带有的能量MORE惩罚（通常为负值），例如:
        - Incinerate (IncineratePlayer): active_skill_energy_generated_+%_final = -98
        - Flame Wall (FlameWallPlayer): active_skill_energy_generated_+%_final = -50
        - Solar Orb (SolarOrbPlayer): active_skill_energy_generated_+%_final = -50

        这些MORE惩罚不在Meta技能实体上，而在被触发的法术实体上。
        当这些法术作为Meta技能的插槽法术使用时，此MORE惩罚生效。
        """
        modifiers: List[EnergyModifier] = []

        conn = sqlite3.connect(str(self.entities_db_path))
        cursor = conn.cursor()

        # 查找所有包含 active_skill_energy_generated_+%_final 的非Meta实体
        # constant_stats 中以JSON格式存储: [["stat_name", value], ...]
        cursor.execute('''
            SELECT id, name, type, constant_stats, stat_sets
            FROM entities
            WHERE constant_stats LIKE '%active_skill_energy_generated%final%'
              AND (skill_types NOT LIKE '%Meta%' OR skill_types IS NULL)
        ''')

        for row in cursor.fetchall():
            eid, name, etype, constant_stats_json, stat_sets_json = row
            try:
                constant_stats = json.loads(constant_stats_json) if constant_stats_json else []
            except (json.JSONDecodeError, TypeError):
                continue

            # 也检查stat_sets中的constantStats（多statSet技能可能只在非第一个statSet中有此stat）
            stat_sets_constants = []
            if stat_sets_json:
                try:
                    stat_sets = json.loads(stat_sets_json) if isinstance(stat_sets_json, str) else stat_sets_json
                    if isinstance(stat_sets, dict):
                        for set_key, set_data in stat_sets.items():
                            if isinstance(set_data, dict):
                                cs = set_data.get('constantStats', set_data.get('constant_stats', []))
                                if isinstance(cs, list):
                                    stat_sets_constants.extend(cs)
                except (json.JSONDecodeError, TypeError):
                    pass

            # 合并所有constantStats来源
            all_constants = self._normalize_stat_pairs(constant_stats) + self._normalize_stat_pairs(stat_sets_constants)

            for stat_name, stat_value in all_constants:
                if stat_name == 'active_skill_energy_generated_+%_final':
                    modifiers.append(EnergyModifier(
                        stat_name='active_skill_energy_generated_+%_final',
                        mod_type='MORE',
                        source_field='constantStats',
                        source_entity=eid,
                        value=stat_value,
                        per_quality=False,
                        evidence=(
                            f"Triggered spell {eid} ({name or 'unnamed'}): "
                            f"active_skill_energy_generated_+%_final={stat_value} "
                            f"(当此法术被Meta技能触发时，能量生成受{stat_value}% MORE惩罚)"
                        )
                    ))

        conn.close()
        return modifiers

    # ================================================================
    # 公式文本生成 (v3: 使用实际收集的stat名称)
    # ================================================================

    def _build_inc_term(self, modifiers: List[EnergyModifier]) -> Tuple[str, List[Dict]]:
        """
        从收集到的INC修饰符构建公式中的INC项。
        v4: 同时包含条件INC (INC_CONDITIONAL)，标注为可选项

        返回:
        - formula_part: 公式文本片段, 如 "(1 + Σ(energy_generated_+%) / 100)"
        - evidence_list: 数据证据列表
        """
        inc_mods = [m for m in modifiers if m.mod_type == 'INC']
        cond_inc_mods = [m for m in modifiers if m.mod_type == 'INC_CONDITIONAL']

        if not inc_mods and not cond_inc_mods:
            return '', []

        # 去重stat名（同名stat可能出现在多个字段中）
        unique_stats = []
        seen_names: Set[str] = set()
        for m in inc_mods:
            if m.stat_name not in seen_names:
                seen_names.add(m.stat_name)
                unique_stats.append(m)

        # 构建公式文本
        if len(unique_stats) == 1:
            stat = unique_stats[0]
            formula_part = f"(1 + Σ({stat.stat_name}) / 100)"
        elif len(unique_stats) > 1:
            stat_names = ' + '.join(m.stat_name for m in unique_stats)
            formula_part = f"(1 + Σ({stat_names}) / 100)"
        else:
            formula_part = ''

        # v4: 条件INC作为可选项附注
        if cond_inc_mods:
            cond_names = set(m.stat_name for m in cond_inc_mods)
            cond_part = ' + '.join(cond_names)
            if formula_part:
                formula_part += f" [条件INC可选: {cond_part}]"
            else:
                formula_part = f"[条件INC: (1 + Σ({cond_part}) / 100)]"

        # 构建证据 (合并INC + 条件INC)
        evidence = []
        for m in inc_mods + cond_inc_mods:
            entry = {
                'stat': m.stat_name,
                'type': m.mod_type,
                'source_field': m.source_field,
                'source_entity': m.source_entity,
            }
            if m.value is not None:
                entry['value'] = m.value
            if m.per_quality:
                entry['per_quality'] = True
            entry['evidence'] = m.evidence
            evidence.append(entry)

        return formula_part, evidence

    def _build_more_term(self, modifiers: List[EnergyModifier]) -> Tuple[str, List[Dict]]:
        """
        从收集到的MORE修饰符构建公式中的MORE项。
        v4: 同时包含SPECIAL修饰符（如 energy_generation_is_doubled）

        返回:
        - formula_part: 公式文本片段, 如 "Π(1 + active_skill_energy_generated_+%_final / 100)"
        - evidence_list: 数据证据列表
        """
        more_mods = [m for m in modifiers if m.mod_type == 'MORE']
        special_mods = [m for m in modifiers if m.mod_type == 'SPECIAL']

        if not more_mods and not special_mods:
            return '', []

        parts_list = []

        # 去重stat名
        unique_more = []
        seen_names: Set[str] = set()
        for m in more_mods:
            if m.stat_name not in seen_names:
                seen_names.add(m.stat_name)
                unique_more.append(m)

        # 构建MORE部分
        if len(unique_more) == 1:
            stat = unique_more[0]
            parts_list.append(f"Π(1 + {stat.stat_name} / 100)")
        elif len(unique_more) > 1:
            more_parts = [f"(1 + {m.stat_name}/100)" for m in unique_more]
            parts_list.append(" × ".join(more_parts))

        # v4: SPECIAL部分 (如 ×2 for energy_generation_is_doubled)
        for m in special_mods:
            if m.stat_name == 'energy_generation_is_doubled':
                parts_list.append("[×2 if energy_generation_is_doubled]")

        formula_part = " × ".join(parts_list) if parts_list else ''

        # 构建证据 (合并MORE + SPECIAL)
        evidence = []
        for m in more_mods + special_mods:
            entry = {
                'stat': m.stat_name,
                'type': m.mod_type,
                'source_field': m.source_field,
                'source_entity': m.source_entity,
            }
            if m.value is not None:
                entry['value'] = m.value
            entry['evidence'] = m.evidence
            evidence.append(entry)

        return formula_part, evidence

    # ================================================================
    # StatDescriptions 加载
    # ================================================================

    def _load_stat_descriptions(self):
        """从StatDescriptions加载能量相关stat的精确描述文本"""
        self._stat_descriptions = {}

        stat_desc_file = self._find_stat_descriptions_file()
        if not stat_desc_file:
            print("    [警告] 未找到StatDescriptions文件，将使用stat名称推断公式")
            return

        try:
            content = stat_desc_file.read_text(encoding='utf-8', errors='replace')

            # 匹配包含 Energy/energy 的描述 + 其关联的stat名
            pattern = re.compile(
                r'text="((?:[^"\\]|\\.|"(?=[^}]*stats=))*?(?:Energy|energy)[^"]*)"'
                r'.*?stats=\{\s*\[1\]="([^"]+)"',
                re.DOTALL
            )
            for match in pattern.finditer(content):
                desc_text = match.group(1).replace('\n', ' ').strip()
                stat_name = match.group(2).strip()
                if 'centienergy' in stat_name or 'energy' in stat_name.lower():
                    self._stat_descriptions[stat_name] = desc_text

            # 补充: 宽松模式匹配 centienergy stat
            pattern2 = re.compile(
                r'text="([^"]+)"'
                r'[\s\S]*?'
                r'\[1\]="((?:\w+_)?(?:gain|lose)_\w*(?:centienergy|energy)\w*)"',
                re.DOTALL
            )
            for match in pattern2.finditer(content):
                stat_name = match.group(2).strip()
                if stat_name not in self._stat_descriptions:
                    desc_text = match.group(1).replace('\n', ' ').strip()
                    self._stat_descriptions[stat_name] = desc_text

        except Exception as e:
            print(f"    [警告] 读取StatDescriptions失败: {e}")

    def _find_stat_descriptions_file(self) -> Optional[Path]:
        """定位StatDescriptions文件"""
        if self.pob_path:
            f = self.pob_path / 'Data' / 'StatDescriptions' / 'skill_stat_descriptions.lua'
            if f.exists():
                return f

        kb_path = self.entities_db_path.parent
        project_root = kb_path.parent.parent.parent

        for candidate in [
            project_root / 'POBData' / 'Data' / 'StatDescriptions' / 'skill_stat_descriptions.lua',
            kb_path.parent.parent.parent.parent / 'POBData' / 'Data' / 'StatDescriptions' / 'skill_stat_descriptions.lua',
        ]:
            if candidate.exists():
                return candidate

        for parent in [project_root, kb_path.parent, kb_path.parent.parent]:
            for f in parent.rglob('skill_stat_descriptions.lua'):
                return f

        return None

    # ================================================================
    # 能量获取公式分类 (v3: 接收完整修饰符列表)
    # ================================================================

    def _classify_energy_stat(self, stat_name: str, stat_value: int,
                              modifiers: List[EnergyModifier]) -> Optional[Dict]:
        """
        根据stat名称 + StatDescriptions精确文本 + 动态收集的修饰符，
        分类能量获取公式并生成带数据证据的公式文本。

        v3变更: 接收modifiers列表，公式中的INC/MORE项使用实际stat名称。

        返回 dict:
          subtype: SubA/SubB/SubC/SubD/SubE/SubF
          formula_text: 人可读公式（含实际stat名称）
          params: 参数字典（含完整数据证据）
          description: 精确描述文本
          confidence: 置信度
          notes: 补充说明
        """
        desc_text = self._stat_descriptions.get(stat_name, '')

        # 构建INC和MORE项的公式文本（使用实际stat名称）
        inc_term, inc_evidence = self._build_inc_term(modifiers)
        more_term, more_evidence = self._build_more_term(modifiers)

        # 组合修饰符后缀
        mod_suffix = ''
        if inc_term:
            mod_suffix += f" × {inc_term}"
        if more_term:
            mod_suffix += f" × {more_term}"

        # 基础参数
        base_params = {
            'centienergy': stat_value,
            'source_stat': stat_name,
        }
        if inc_evidence:
            base_params['inc_evidence'] = inc_evidence
        if more_evidence:
            base_params['more_evidence'] = more_evidence
        if not inc_evidence and not more_evidence:
            base_params['modifier_note'] = '该实体及关联Support中未发现energy相关INC/MORE修饰符'

        # ── 尝试匹配 monster_power 型 ──
        m = STAT_PATTERN_MONSTER_POWER.match(stat_name)
        if m:
            trigger_event = m.group(3) if m.lastindex >= 3 else 'unknown'

            has_ailment_threshold = AILMENT_THRESHOLD_PHRASE in desc_text if desc_text else False
            has_per_power = any(p in desc_text for p in PER_POWER_PHRASES) if desc_text else True

            base_params['trigger_event'] = trigger_event
            base_params['has_enemy_power'] = has_per_power
            base_params['has_ailment_threshold'] = has_ailment_threshold

            if has_ailment_threshold:
                # SubA: per Power + ailment_threshold修正
                return {
                    'subtype': 'SubA',
                    'formula_text': (
                        f"energy = enemy_power × ({stat_value}/100) "
                        f"× (hit_damage / ailment_threshold)"
                        f"{mod_suffix}"
                    ),
                    'params': base_params,
                    'description': desc_text or f"per Power, modified by Ailment Threshold ({trigger_event})",
                    'confidence': 0.95 if desc_text else 0.70,
                    'notes': self._build_notes('SubA',
                        'enemy_power缩放 + ailment_threshold修正(StatDescriptions文本)',
                        inc_evidence, more_evidence),
                }

            elif has_per_power:
                # SubB: per Power + 无ailment_threshold
                return {
                    'subtype': 'SubB',
                    'formula_text': (
                        f"energy = enemy_power × ({stat_value}/100)"
                        f"{mod_suffix}"
                    ),
                    'params': base_params,
                    'description': desc_text or f"per Power of enemies ({trigger_event})",
                    'confidence': 0.90 if desc_text else 0.70,
                    'notes': self._build_notes('SubB',
                        '仅enemy_power缩放, 无ailment_threshold',
                        inc_evidence, more_evidence),
                }

            else:
                # SubC: stat名含monster_power但描述无"per Power"
                base_params['has_enemy_power'] = False
                return {
                    'subtype': 'SubC',
                    'formula_text': (
                        f"energy = ({stat_value}/100)"
                        f"{mod_suffix}"
                    ),
                    'params': base_params,
                    'description': desc_text or f"fixed energy per event ({trigger_event})",
                    'confidence': 0.85 if desc_text else 0.60,
                    'notes': self._build_notes('SubC',
                        'stat名含monster_power但StatDescriptions无"per Power"(如Melee Kill)',
                        inc_evidence, more_evidence),
                }

        # ── 尝试匹配 minion_death 特殊型 ──
        m = STAT_PATTERN_MINION_DEATH.match(stat_name)
        if m:
            base_params['base_energy'] = 50
            base_params['has_minion_power'] = True
            return {
                'subtype': 'SubF',
                'formula_text': (
                    f"energy = base_energy × (minion_power_ratio)"
                    f"{mod_suffix}"
                ),
                'params': base_params,
                'description': desc_text or "base Energy when Minion killed, modified by Minion's Power",
                'confidence': 0.90 if desc_text else 0.65,
                'notes': self._build_notes('SubF',
                    'minion_death型, base_energy=50(StatDescriptions)',
                    inc_evidence, more_evidence),
            }

        # ── 尝试匹配固定值型 ──
        m = STAT_PATTERN_FIXED_EVENT.match(stat_name)
        if m:
            event = m.group(3)
            base_params['trigger_event'] = event
            base_params['has_enemy_power'] = False
            base_params['has_ailment_threshold'] = False
            return {
                'subtype': 'SubD',
                'formula_text': (
                    f"energy = ({stat_value}/100)"
                    f"{mod_suffix}"
                ),
                'params': base_params,
                'description': desc_text or f"fixed energy on {event}",
                'confidence': 0.90 if desc_text else 0.70,
                'notes': self._build_notes('SubD',
                    f'固定值型, 事件={event}',
                    inc_evidence, more_evidence),
            }

        # ── 尝试匹配连续/特殊计量型 ──
        m = STAT_PATTERN_CONTINUOUS.match(stat_name)
        if m:
            unit = m.group(3)
            base_params['unit'] = unit
            base_params['has_enemy_power'] = False
            base_params['has_ailment_threshold'] = False
            return {
                'subtype': 'SubE',
                'formula_text': (
                    f"energy = ({stat_value}/100) × {unit}_measure"
                    f"{mod_suffix}"
                ),
                'params': base_params,
                'description': desc_text or f"energy per {unit}",
                'confidence': 0.85 if desc_text else 0.60,
                'notes': self._build_notes('SubE',
                    f'连续/计量型, 按{unit}计量',
                    inc_evidence, more_evidence),
            }

        return None

    def _build_notes(self, subtype: str, base_note: str,
                     inc_evidence: List[Dict], more_evidence: List[Dict]) -> str:
        """构建notes字符串，附带INC/MORE数据证据（v4: 含被动/升华/被触发法术来源）"""
        parts = [f'{subtype}: {base_note}']

        if inc_evidence:
            inc_stats = [e['stat'] for e in inc_evidence]
            inc_sources = [f"{e['source_entity']}.{e['source_field']}" for e in inc_evidence]
            parts.append(
                f"INC项={','.join(set(inc_stats))} "
                f"(来源: {', '.join(set(inc_sources))})"
            )
        else:
            parts.append('INC项: 未在实体/Support/被动天赋数据中发现')

        if more_evidence:
            more_stats = [e['stat'] for e in more_evidence]
            more_sources = [f"{e['source_entity']}.{e['source_field']}" for e in more_evidence]
            parts.append(
                f"MORE项={','.join(set(more_stats))} "
                f"(来源: {', '.join(set(more_sources))})"
            )
        else:
            parts.append('MORE项: 未在实体/Support/升华/被触发法术数据中发现')

        return '; '.join(parts)

    # ================================================================
    # 实体获取
    # ================================================================

    def _get_meta_entities(self) -> List[Dict]:
        """获取所有Meta技能实体（含完整字段: stats, constantStats, qualityStats）"""
        conn = sqlite3.connect(str(self.entities_db_path))
        cursor = conn.cursor()

        cursor.execute('''
            SELECT id, name, type, skill_types, constant_stats, stats,
                   quality_stats, data_json
            FROM entities
            WHERE skill_types LIKE '%Meta%'
               OR skill_types LIKE '%GeneratesEnergy%'
        ''')

        entities = []
        for row in cursor.fetchall():
            entity_id, name, etype, skill_types, constant_stats, stats, quality_stats, data_json = row
            data = json.loads(data_json) if data_json else {}
            entities.append({
                'id': entity_id,
                'name': name or entity_id,
                'type': etype,
                'skill_types': json.loads(skill_types) if skill_types else [],
                'constant_stats': json.loads(constant_stats) if constant_stats else [],
                'stats': json.loads(stats) if stats else [],
                'quality_stats': json.loads(quality_stats) if quality_stats else [],
                'data': data
            })

        conn.close()
        return entities

    def _get_support_meta_entities(self) -> List[Dict]:
        """获取所有隐藏的SupportMeta实体"""
        conn = sqlite3.connect(str(self.entities_db_path))
        cursor = conn.cursor()

        cursor.execute('''
            SELECT id, name, type, constant_stats, stats, data_json
            FROM entities
            WHERE id LIKE 'SupportMeta%'
               OR name LIKE 'SupportMeta%'
        ''')

        entities = []
        for row in cursor.fetchall():
            entity_id, name, etype, constant_stats, stats, data_json = row
            data = json.loads(data_json) if data_json else {}
            entities.append({
                'id': entity_id,
                'name': name or entity_id,
                'constant_stats': json.loads(constant_stats) if constant_stats else [],
                'stats': json.loads(stats) if stats else [],
                'data': data
            })

        conn.close()
        return entities

    def _build_meta_support_map(self, meta_entities: List[Dict], support_entities: List[Dict]) -> Dict:
        """建立Meta→Support映射"""
        mapping = {}

        for meta in meta_entities:
            meta_id = meta['id']
            expected_support = f"Support{meta_id}"

            for sup in support_entities:
                if sup['id'] == expected_support or sup['name'] == expected_support:
                    mapping[meta_id] = sup
                    break

        return mapping

    # ================================================================
    # 公式提取
    # ================================================================

    def _extract_energy_gain(self, entity_id: str, entity_name: str, data: Dict,
                             modifiers: List[EnergyModifier]):
        """从实体数据提取能量获取公式 (v3: 动态INC/MORE)"""
        constant_stats = self._normalize_stat_pairs(
            data.get('constant_stats', data.get('constantStats', []))
        )

        for stat_name, stat_value in constant_stats:
            # 只处理能量相关stat
            if 'centienergy' not in stat_name and 'energy_per' not in stat_name:
                continue

            # 使用 StatDescriptions + 动态修饰符 驱动的分类
            classification = self._classify_energy_stat(stat_name, int(stat_value), modifiers)
            if classification:
                params = classification['params']

                # 收集所有相关的stat来源
                all_stat_sources = [stat_name]
                for m in modifiers:
                    if m.stat_name not in all_stat_sources:
                        all_stat_sources.append(m.stat_name)

                self.formulas.append(GapFormula(
                    id=f"gap_{entity_id}_energy_gain",
                    entity_id=entity_id,
                    entity_name=entity_name,
                    formula_type='energy_gain',
                    formula_text=classification['formula_text'],
                    parameters=json.dumps(params, ensure_ascii=False),
                    stat_sources=json.dumps(all_stat_sources),
                    description=f"{entity_name}: {classification['description']}",
                    confidence=classification['confidence'],
                    pob_status='unimplemented',
                    notes=(
                        f"[{classification['subtype']}] {classification['notes']}; "
                        f"SkillStatMap中无映射, CalcTriggers被注释"
                    )
                ))
                break  # 每个实体只取一个energy_gain公式

    def _extract_max_energy(self, entity_id: str, entity_name: str, data: Dict, support_data: Dict):
        """提取最大能量公式"""
        # 先从Support数据中查找
        all_constant_stats = []

        sup_constants = support_data.get('constant_stats', support_data.get('constantStats',
                         support_data.get('data', {}).get('constant_stats',
                         support_data.get('data', {}).get('constantStats', []))))
        if isinstance(sup_constants, dict):
            sup_constants = [[k, v] for k, v in sup_constants.items()]
        all_constant_stats.extend(sup_constants)

        # 也检查实体自身的constantStats
        own_constants = data.get('constant_stats', data.get('constantStats', []))
        if isinstance(own_constants, dict):
            own_constants = [[k, v] for k, v in own_constants.items()]
        all_constant_stats.extend(own_constants)

        for stat_entry in all_constant_stats:
            if isinstance(stat_entry, (list, tuple)) and len(stat_entry) >= 2:
                stat_name, stat_value = stat_entry[0], stat_entry[1]
            elif isinstance(stat_entry, dict):
                stat_name = stat_entry.get('stat', stat_entry.get('name', ''))
                stat_value = stat_entry.get('value', 0)
            else:
                continue

            for pattern, mode, formula_template in MAX_ENERGY_PATTERNS:
                match = pattern.match(stat_name)
                if match:
                    formula_text = formula_template.format(
                        per_Xms=stat_value,
                        value=stat_value
                    )

                    params = {
                        'value': stat_value,
                        'mode': mode,
                        'source_stat': stat_name
                    }

                    source = 'Support实体' if stat_entry in sup_constants else '自身实体'

                    self.formulas.append(GapFormula(
                        id=f"gap_{entity_id}_max_energy",
                        entity_id=entity_id,
                        entity_name=entity_name,
                        formula_type='max_energy',
                        formula_text=formula_text,
                        parameters=json.dumps(params),
                        stat_sources=json.dumps([stat_name]),
                        description=f"{entity_name}的最大能量公式（{mode}型，来自{source}）",
                        confidence=0.80,
                        pob_status='unimplemented',
                        notes=f'参数来自{source}的constantStats'
                    ))
                    break

    def _extract_damage_modifier(self, entity_id: str, entity_name: str, data: Dict, support_data: Dict):
        """提取伤害修正公式"""
        # 主要来自Support的constantStats
        all_constant_stats = []

        sup_constants = support_data.get('constant_stats', support_data.get('constantStats',
                         support_data.get('data', {}).get('constant_stats',
                         support_data.get('data', {}).get('constantStats', []))))
        if isinstance(sup_constants, dict):
            sup_constants = [[k, v] for k, v in sup_constants.items()]
        all_constant_stats.extend(sup_constants)

        for stat_entry in all_constant_stats:
            if isinstance(stat_entry, (list, tuple)) and len(stat_entry) >= 2:
                stat_name, stat_value = stat_entry[0], stat_entry[1]
            elif isinstance(stat_entry, dict):
                stat_name = stat_entry.get('stat', stat_entry.get('name', ''))
                stat_value = stat_entry.get('value', 0)
            else:
                continue

            for pattern, ftype, formula_template in DAMAGE_MOD_PATTERNS:
                if pattern.match(stat_name):
                    formula_text = formula_template.format(value=stat_value)

                    self.formulas.append(GapFormula(
                        id=f"gap_{entity_id}_damage_mod",
                        entity_id=entity_id,
                        entity_name=entity_name,
                        formula_type='damage_modifier',
                        formula_text=formula_text,
                        parameters=json.dumps({'value': stat_value, 'source_stat': stat_name}),
                        stat_sources=json.dumps([stat_name]),
                        description=f"{entity_name}的被触发法术伤害修正({stat_value}%)",
                        confidence=0.90,
                        pob_status='unimplemented',
                        notes='来自隐藏Support实体的constantStats'
                    ))
                    break

    def _extract_trigger_condition(self, entity_id: str, entity_name: str, data: Dict):
        """提取触发条件"""
        stats = data.get('stats', [])
        if isinstance(stats, dict):
            stats = list(stats.keys())

        has_trigger_stat = any(
            'triggers_at_maximum_energy' in s
            for s in stats if isinstance(s, str)
        )

        if has_trigger_stat:
            self.formulas.append(GapFormula(
                id=f"gap_{entity_id}_trigger",
                entity_id=entity_id,
                entity_name=entity_name,
                formula_type='trigger_condition',
                formula_text='trigger = (current_energy >= max_energy)',
                parameters=json.dumps({'condition': 'energy >= max_energy'}),
                stat_sources=json.dumps([s for s in stats if 'trigger' in str(s).lower()]),
                description=f"{entity_name}: 当前能量达到最大能量时触发所有插槽法术",
                confidence=0.95,
                pob_status='unimplemented',
                notes='generic_ongoing_trigger_triggers_at_maximum_energy stat确认'
            ))

    def save_to_db(self):
        """保存到数据库"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        # 创建表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS gap_formulas (
                id TEXT PRIMARY KEY,
                entity_id TEXT NOT NULL,
                entity_name TEXT,
                formula_type TEXT NOT NULL,
                formula_text TEXT NOT NULL,
                parameters TEXT,
                stat_sources TEXT,
                description TEXT,
                confidence REAL,
                pob_status TEXT DEFAULT 'unimplemented',
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 创建索引
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_gap_formulas_entity ON gap_formulas(entity_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_gap_formulas_type ON gap_formulas(formula_type)')

        # 清空旧数据
        cursor.execute('DELETE FROM gap_formulas')

        # 插入
        for f in self.formulas:
            cursor.execute('''
                INSERT OR REPLACE INTO gap_formulas
                (id, entity_id, entity_name, formula_type, formula_text,
                 parameters, stat_sources, description, confidence, pob_status, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                f.id, f.entity_id, f.entity_name, f.formula_type, f.formula_text,
                f.parameters, f.stat_sources, f.description, f.confidence,
                f.pob_status, f.notes
            ))

        conn.commit()
        conn.close()

    def get_stats(self) -> Dict:
        """获取统计信息"""
        total = len(self.formulas)
        by_type = {}
        by_entity = {}
        for f in self.formulas:
            by_type[f.formula_type] = by_type.get(f.formula_type, 0) + 1
            by_entity[f.entity_id] = by_entity.get(f.entity_id, 0) + 1

        return {
            'total': total,
            'by_type': by_type,
            'entities_covered': len(by_entity),
            'avg_confidence': sum(f.confidence for f in self.formulas) / max(total, 1)
        }

    def diagnose(self):
        """诊断输出"""
        stats = self.get_stats()

        print(f"\n--- 缺口公式统计 ---")
        print(f"  总公式数: {stats['total']}")
        print(f"  覆盖实体: {stats['entities_covered']}")
        print(f"  平均置信度: {stats['avg_confidence']:.2f}")

        print(f"\n  按类型:")
        for ftype, count in sorted(stats['by_type'].items()):
            print(f"    {ftype}: {count}")

        if self.formulas:
            print(f"\n  样本:")
            for f in self.formulas[:5]:
                print(f"    [{f.entity_name}] {f.formula_type}: {f.formula_text[:80]}...")

    # ================================================================
    # v5新增: 装备词缀能量修饰符扫描
    # ================================================================

    def _scan_equipment_energy_mods(self) -> List[EnergyModifier]:
        """
        [v6优化] 从 entities.db 查询 mod_affix 实体，提取装备词缀中的能量修饰符。

        优化说明:
        - v5 扫描 Mod*.lua 文件，与 data_scanner.py 重复工作
        - v6 改用实体库查询，复用 data_scanner 已提取的数据

        实体库中的 mod_affix 实体:
        - type = 'mod_affix'
        - stat_descriptions = JSON数组，存储描述文本
        - 如 ['Meta Skills gain (4-8)% increased Energy']

        返回: EnergyModifier 列表
        """
        modifiers: List[EnergyModifier] = []

        # 连接实体库
        if not self.entities_db_path.exists():
            return modifiers

        conn = sqlite3.connect(str(self.entities_db_path))
        cursor = conn.cursor()

        # 查询所有 mod_affix 实体
        cursor.execute('''
            SELECT id, name, stat_descriptions
            FROM entities
            WHERE type = 'mod_affix'
              AND stat_descriptions IS NOT NULL
              AND stat_descriptions != '[]'
        ''')

        # 能量词缀文本模式
        energy_pattern = re.compile(
            r'Meta Skills gain (\(.*?\))?\s*(\d+(?:-\d+)?)?\s*%?\s*(increased|reduced|more|less)\s*Energy'
            r'(.*?)$',
            re.IGNORECASE
        )

        for row in cursor.fetchall():
            mod_id, mod_name, stat_desc_json = row

            try:
                descriptions = json.loads(stat_desc_json) if stat_desc_json else []
            except (json.JSONDecodeError, TypeError):
                continue

            if not isinstance(descriptions, list):
                continue

            for text in descriptions:
                if not isinstance(text, str):
                    continue

                # 解析描述文本
                m = energy_pattern.search(text)
                if not m:
                    continue

                range_str = m.group(1) or m.group(2)  # (X-Y) 或 X
                mod_type_str = m.group(3).lower()     # increased/reduced/more/less
                condition_str = m.group(4).strip() if m.group(4) else ""

                # 确定值范围
                if range_str and '(' in range_str:
                    # 范围值 (X-Y)
                    range_match = re.search(r'(\d+)-(\d+)', range_str)
                    if range_match:
                        min_val = int(range_match.group(1))
                        max_val = int(range_match.group(2))
                        value = (min_val + max_val) / 2  # 取中间值
                    else:
                        continue
                elif range_str:
                    # 固定值 X
                    value = int(range_str)
                else:
                    continue

                # 确定修饰符类型
                if mod_type_str in ('increased', 'reduced'):
                    mod_type = 'INC'
                    if mod_type_str == 'reduced':
                        value = -value
                elif mod_type_str in ('more', 'less'):
                    mod_type = 'MORE'
                    if mod_type_str == 'less':
                        value = -value
                else:
                    continue

                # 构建证据字符串
                evidence = f"Equipment mod {mod_id} ({mod_name or 'unnamed'}): \"{text}\""
                if condition_str:
                    evidence += f" [条件: {condition_str}]"

                # 创建 EnergyModifier
                modifiers.append(EnergyModifier(
                    stat_name='energy_generated_+%' if mod_type == 'INC' else 'ascendancy_energy_generated_+%_final',
                    mod_type=mod_type,
                    source_field='stat_descriptions',
                    source_entity=mod_id,
                    value=value,
                    per_quality=False,
                    evidence=evidence
                ))

        conn.close()
        return modifiers


def main():
    """独立运行入口"""
    import argparse
    import sys

    SCRIPTS_DIR = Path(__file__).parent
    sys.path.insert(0, str(SCRIPTS_DIR))
    from pob_paths import get_knowledge_base_path, get_pob_path

    parser = argparse.ArgumentParser(description='Meta缺口公式提取 v4')
    parser.add_argument('--entities-db', help='实体库路径')
    parser.add_argument('--db', help='输出数据库路径')
    parser.add_argument('--pob-path', help='POBData路径（用于读取StatDescriptions）')

    args = parser.parse_args()

    kb_path = get_knowledge_base_path()
    entities_db = args.entities_db or str(kb_path / 'entities.db')
    db_path = args.db or str(kb_path / 'formulas.db')
    pob_path = args.pob_path or str(get_pob_path())

    print("=" * 60)
    print("Meta缺口公式提取 v4 (扩展搜索: 被动天赋/升华/被触发法术)")
    print("=" * 60)

    extractor = StatFormulaExtractor(entities_db, db_path, pob_path)
    extractor.extract_all()
    extractor.save_to_db()
    extractor.diagnose()

    print(f"\n[OK] 已保存到 {db_path}")


if __name__ == '__main__':
    main()
