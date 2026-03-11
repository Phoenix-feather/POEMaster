#!/usr/bin/env python3
"""
公式提取器 - 从POB提取公式

功能模块：
1. Lua函数提取（v1-v6）：解析Lua函数定义，提取stat特征
2. 缺口公式提取（v7）：提取Meta技能能量公式（合并自 stat_formula_extractor.py）

输出到 formulas.db：
- formulas 表：Lua函数代码（可选）
- gap_formulas 表：缺口公式（Meta能量系统）
- formula_features 表：公式特征索引
- formula_stats 表：公式stat关联
- formula_calls 表：函数调用关系

历史版本：
- v1-v6: Lua函数提取
- v7: 合并 stat_formula_extractor 功能，添加缺口公式提取

方法论 (v7 改进):
- 数据结构优先: stat ID 和类型来自数据结构层面
- 命名约定: INC/MORE 类型由 stat 名称后缀决定 (_+% / _+%_final)
- 描述文本: 仅用于数值提取和显示（无可避免）
- 证据链: 记录完整来源和方法论
"""

import os
import re
import json
import sqlite3
from pathlib import Path
from typing import Dict, List, Any, Optional, Set, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime


# ================================================================
# 数据类定义
# ================================================================

@dataclass
class LuaFunction:
    """Lua函数定义"""
    name: str
    params: List[str]
    body: str
    start_line: int
    end_line: int
    is_local: bool = False
    source_file: str = ""


@dataclass
class FormulaFeatures:
    """公式特征"""
    exact_stats: List[str] = field(default_factory=list)      # 精确stat ID
    fuzzy_stats: List[str] = field(default_factory=list)      # 模糊stat名称
    inferred_tags: List[str] = field(default_factory=list)    # 推断标签
    calls: List[str] = field(default_factory=list)            # 调用的函数


@dataclass
class GapFormula:
    """缺口公式 (v7: 合并自 stat_formula_extractor)"""
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
    """从实体数据动态收集到的能量修饰符 (v7)"""
    stat_name: str           # stat全名
    mod_type: str            # 'INC' 或 'MORE' 或 'INC_CONDITIONAL' 或 'SPECIAL'
    source_field: str        # 来源字段: stats / constantStats / qualityStats / stat_descriptions
    source_entity: str       # 来源实体ID
    value: Optional[float]   # 值（constantStats有值，stats无值）
    per_quality: bool        # 是否按品质缩放（qualityStats）
    evidence: str            # 数据证据描述


# ================================================================
# 能量相关模式定义 (v7: 合并自 stat_formula_extractor)
# ================================================================

# INC/MORE 判定规则 (来自POB stat命名惯例)
# stat_name_+%        → INC类型 (increased/reduced, 加法叠加)
# stat_name_+%_final  → MORE类型 (more/less, 乘法独立)
ENERGY_INC_PATTERN = re.compile(r'.*energy\w*_\+%$')
ENERGY_MORE_PATTERN = re.compile(r'.*energy\w*_\+%_final$')

# 条件INC stat模式
ENERGY_CONDITIONAL_INC_STATS = {
    'energy_generated_+%_if_crit_recently': 'INC_CONDITIONAL',
    'energy_generated_+%_on_full_mana': 'INC_CONDITIONAL',
}

# 特殊能量stat
ENERGY_SPECIAL_STATS = {
    'energy_generation_is_doubled': 'SPECIAL_DOUBLE',
}

# 被动天赋节点描述文本中的能量模式
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

# stat名称匹配模式
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

# 最大能量模式
MAX_ENERGY_PATTERNS = [
    (re.compile(r'generic_ongoing_trigger_(\d+)_maximum_energy_per_(\w+)ms_total_cast_time'),
     'dynamic', 'max_energy = Σ(socketed_spell_cast_time_ms) × {per_Xms} / 1000'),
    (re.compile(r'generic_ongoing_trigger_maximum_energy'),
     'fixed', 'max_energy = {value} / 100'),
]

# 伤害修正模式
DAMAGE_MOD_PATTERNS = [
    (re.compile(r'trigger_meta_gem_damage_\+%_final'), 'damage_modifier',
     'final_damage = base × (1 + {value}/100)'),
]

# StatDescriptions关键短语
AILMENT_THRESHOLD_PHRASE = "modified by the percentage of the enemy's Ailment Threshold"
PER_POWER_PHRASES = ["per Power of enemies", "per enemy Power"]


class FormulaExtractor:
    """公式提取器 (v7: 合并Lua函数提取 + 缺口公式提取)"""

    def __init__(self, pob_path: str, db_path: str, entities_db_path: str = None):
        """
        初始化公式提取器

        Args:
            pob_path: POB数据目录路径
            db_path: 公式库数据库路径
            entities_db_path: 实体库路径（用于加载官方stat ID和缺口公式提取）
        """
        self.pob_path = Path(pob_path)
        self.db_path = Path(db_path)
        self.entities_db_path = Path(entities_db_path) if entities_db_path else None

        # 加载官方stat ID
        self.official_stats = self._load_official_stats()

        # 缺口公式提取相关缓存
        self._stat_descriptions: Dict[str, str] = {}
        self._energy_support_gems: Optional[List[Dict]] = None
        self._passive_energy_modifiers: Optional[List[EnergyModifier]] = None
        self._triggered_spell_more_modifiers: Optional[List[EnergyModifier]] = None
        self._equipment_energy_modifiers: Optional[List[EnergyModifier]] = None
        self.gap_formulas: List[GapFormula] = []

        # 初始化数据库
        self._init_database()

        print(f"[初始化] 公式提取器 v7")
        print(f"  POB路径: {self.pob_path}")
        print(f"  数据库: {self.db_path}")
        print(f"  官方Stat ID数量: {len(self.official_stats)}")

    # ================================================================
    # 数据库初始化
    # ================================================================

    def _init_database(self):
        """初始化数据库表（v7: 添加gap_formulas表）"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        # 创建formulas表（Lua函数）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS formulas (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                code TEXT NOT NULL,
                source_file TEXT NOT NULL,
                line_start INTEGER,
                line_end INTEGER,
                exact_stats TEXT,
                fuzzy_stats TEXT,
                inferred_tags TEXT,
                calls TEXT,
                called_by TEXT,
                call_depth INTEGER DEFAULT 0,
                total_stats TEXT,
                constraints TEXT,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 创建gap_formulas表（缺口公式，v7新增）
        cursor.execute("""
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
        """)

        # 创建formula_features表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS formula_features (
                formula_id TEXT,
                feature_type TEXT,
                feature_value TEXT,
                confidence REAL DEFAULT 1.0,
                PRIMARY KEY (formula_id, feature_type, feature_value)
            )
        """)

        # 创建formula_stats表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS formula_stats (
                formula_id TEXT,
                stat_id TEXT,
                relation TEXT,
                confidence REAL DEFAULT 1.0,
                PRIMARY KEY (formula_id, stat_id, relation)
            )
        """)

        # 创建formula_calls表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS formula_calls (
                caller_id TEXT,
                callee_id TEXT,
                call_count INTEGER DEFAULT 1,
                call_context TEXT,
                PRIMARY KEY (caller_id, callee_id)
            )
        """)

        # 创建索引
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_formula_source ON formulas(source_file)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_formula_name ON formulas(name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_feature_value ON formula_features(feature_value)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_fs_stat ON formula_stats(stat_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_fc_callee ON formula_calls(callee_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_gap_formulas_entity ON gap_formulas(entity_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_gap_formulas_type ON gap_formulas(formula_type)")

        conn.commit()
        conn.close()

        print(f"[OK] 数据库初始化完成: {self.db_path}")

    # ================================================================
    # Lua函数提取（v1-v6原有功能）
    # ================================================================

    def _load_official_stats(self) -> Set[str]:
        """从实体库和SkillStatMap加载官方stat ID"""
        official_stats = set()

        # 来源1：从实体库加载
        if self.entities_db_path and self.entities_db_path.exists():
            try:
                conn = sqlite3.connect(str(self.entities_db_path))
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT data_json
                    FROM entities
                    WHERE type = 'stat_mapping'
                """)

                for row in cursor.fetchall():
                    data = json.loads(row[0]) if row[0] else {}
                    mod_data = data.get('mod_data', [])

                    if isinstance(mod_data, list):
                        for mod in mod_data:
                            if isinstance(mod, dict) and 'name' in mod:
                                official_stats.add(mod['name'])

                conn.close()
                print(f"[OK] 从实体库加载 {len(official_stats)} 个官方stat ID")

            except Exception as e:
                print(f"[WARN] 加载实体库官方stat失败: {e}")

        # 来源2：从SkillStatMap.lua提取POB内部modifier名称
        skill_stat_map = self.pob_path / 'Data' / 'SkillStatMap.lua'
        if skill_stat_map.exists():
            try:
                content = skill_stat_map.read_text(encoding='utf-8', errors='ignore')

                for m in re.finditer(r'skill\(\s*"(\w+)"', content):
                    official_stats.add(m.group(1))
                for m in re.finditer(r'mod\(\s*"(\w+)"', content):
                    official_stats.add(m.group(1))
                for m in re.finditer(r'flag\(\s*"(\w+)"', content):
                    official_stats.add(m.group(1))
                for m in re.finditer(r'\["(\w+)"\]', content):
                    official_stats.add(m.group(1))

                print(f"[OK] 从SkillStatMap.lua补充后共 {len(official_stats)} 个官方stat ID")

            except Exception as e:
                print(f"[WARN] 解析SkillStatMap.lua失败: {e}")
        else:
            print("[WARN] SkillStatMap.lua不存在，跳过Layer 2映射")

        if not official_stats:
            print("[WARN] 未加载任何官方stat ID")

        return official_stats

    def extract_all_functions(self):
        """提取所有Lua函数（通过pob_paths模块遵循POB数据提取范围规则）"""
        from pob_paths import collect_lua_files

        print("\n" + "=" * 70)
        print("开始提取Lua函数（遵循POB数据提取范围规则）")
        print("=" * 70)

        lua_files = collect_lua_files(self.pob_path, verbose=True)

        print(f"\n符合规则的Lua文件: {len(lua_files)} 个")

        all_functions = []
        for i, lua_file in enumerate(lua_files, 1):
            if i % 100 == 0:
                print(f"  处理进度: {i}/{len(lua_files)}")

            try:
                functions = self._parse_lua_file(lua_file)

                for func in functions:
                    formula = self._extract_formula(func, lua_file)
                    if formula:
                        all_functions.append(formula)

            except Exception as e:
                print(f"[WARN] 解析文件失败 {lua_file}: {e}")

        print(f"\n[OK] 提取完成，共 {len(all_functions)} 个函数")

        # 保存到数据库
        self._save_formulas(all_functions)

        return all_functions

    def _parse_lua_file(self, file_path: Path) -> List[LuaFunction]:
        """解析Lua文件，提取所有函数定义"""
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        functions = []
        seen_positions = set()

        patterns = [
            (r'local\s+function\s+(\w+)\s*\(([^)]*)\)', True),
            (r'(?<!local\s)function\s+([\w.:]+)\s*\(([^)]*)\)', False),
        ]

        for pattern, is_local in patterns:
            for match in re.finditer(pattern, content):
                start_pos = match.start()

                if start_pos in seen_positions:
                    continue

                if not is_local:
                    prefix_start = max(0, start_pos - 10)
                    prefix = content[prefix_start:start_pos].strip()
                    if prefix.endswith('local'):
                        continue

                seen_positions.add(start_pos)

                func_name = match.group(1)
                params_str = match.group(2)
                params = [p.strip() for p in params_str.split(',') if p.strip()]

                body = self._extract_function_body(content, start_pos)

                if body and len(body) > 10:
                    start_line = content[:start_pos].count('\n') + 1
                    end_line = start_line + body.count('\n')

                    func = LuaFunction(
                        name=func_name,
                        params=params,
                        body=body,
                        start_line=start_line,
                        end_line=end_line,
                        is_local=is_local,
                        source_file=str(file_path.relative_to(self.pob_path))
                    )
                    functions.append(func)

        return functions

    def _extract_function_body(self, content: str, start_pos: int) -> Optional[str]:
        """提取Lua函数体（使用function...end关键字平衡）"""
        length = len(content)
        i = start_pos
        depth = 0
        in_string = False
        string_char = None
        in_comment = False
        in_block_comment = False

        block_start_keywords = {'function', 'if', 'for', 'while', 'do', 'repeat'}

        while i < length:
            if in_block_comment:
                if content[i:i+2] == ']]':
                    in_block_comment = False
                    i += 2
                    continue
                i += 1
                continue

            if in_comment:
                if content[i] == '\n':
                    in_comment = False
                i += 1
                continue

            if in_string:
                if content[i] == '\\':
                    i += 2
                    continue
                if content[i] == string_char:
                    in_string = False
                i += 1
                continue

            if content[i:i+2] == '--':
                if content[i+2:i+4] == '[[':
                    in_block_comment = True
                    i += 4
                    continue
                else:
                    in_comment = True
                    i += 2
                    continue

            if content[i] in ('"', "'"):
                in_string = True
                string_char = content[i]
                i += 1
                continue

            if content[i:i+2] == '[[':
                end_pos = content.find(']]', i + 2)
                if end_pos != -1:
                    i = end_pos + 2
                    continue
                i += 2
                continue

            if content[i].isalpha() or content[i] == '_':
                word_start = i
                while i < length and (content[i].isalnum() or content[i] == '_'):
                    i += 1
                word = content[word_start:i]

                if word == 'end':
                    depth -= 1
                    if depth == 0:
                        return content[start_pos:i]
                elif word == 'until':
                    depth -= 1
                    if depth == 0:
                        while i < length and content[i] != '\n':
                            i += 1
                        return content[start_pos:i]
                elif word in block_start_keywords:
                    depth += 1
                    if word in ('for', 'while'):
                        j = i
                        temp_depth = 0
                        while j < length:
                            if content[j].isalpha() or content[j] == '_':
                                ws = j
                                while j < length and (content[j].isalnum() or content[j] == '_'):
                                    j += 1
                                w = content[ws:j]
                                if w == 'do' and temp_depth == 0:
                                    i = j
                                    break
                                elif w == 'function':
                                    temp_depth += 1
                                elif w == 'end':
                                    temp_depth -= 1
                                continue
                            elif content[j] in ('"', "'"):
                                sc = content[j]
                                j += 1
                                while j < length and content[j] != sc:
                                    if content[j] == '\\':
                                        j += 1
                                    j += 1
                                j += 1
                                continue
                            j += 1
                continue

            i += 1

        return None

    def _extract_formula(self, func: LuaFunction, source_file: Path) -> Optional[Dict]:
        """提取公式并分析特征"""
        features = self._extract_features(func.body)

        formula_id = f"{source_file.stem}_{func.name}"

        formula = {
            'id': formula_id,
            'name': func.name,
            'code': func.body,
            'source_file': func.source_file,
            'line_start': func.start_line,
            'line_end': func.end_line,
            'exact_stats': json.dumps(features.exact_stats, ensure_ascii=False),
            'fuzzy_stats': json.dumps(features.fuzzy_stats, ensure_ascii=False),
            'inferred_tags': json.dumps(features.inferred_tags, ensure_ascii=False),
            'calls': json.dumps(features.calls, ensure_ascii=False),
            'called_by': json.dumps([], ensure_ascii=False),
            'call_depth': 0,
            'total_stats': json.dumps([], ensure_ascii=False),
            'constraints': json.dumps([], ensure_ascii=False),
            'description': ''
        }

        return formula

    def _extract_features(self, code: str) -> FormulaFeatures:
        """从代码中提取特征"""
        features = FormulaFeatures()

        stat_names = self._extract_stat_names(code)

        for stat_name in stat_names:
            if stat_name in self.official_stats:
                features.exact_stats.append(stat_name)
            else:
                features.fuzzy_stats.append(stat_name)

        features.inferred_tags = self._infer_tags(code)
        features.calls = self._extract_function_calls(code)

        return features

    def _extract_stat_names(self, code: str) -> List[str]:
        """从代码中提取stat名称（覆盖全部11种POB stat引用模式）"""
        stats = set()

        # 模式1: output.xxx
        for m in re.finditer(r'output\.(\w+)', code):
            stats.add(m.group(1))

        # 模式2: skillData.xxx
        for m in re.finditer(r'(?:\w+\.)?skillData\.(\w+)', code):
            stats.add(m.group(1))

        # 模式3-6: skillModList:Sum/Flag/More/Override
        for m in re.finditer(r'skillModList:Sum\(\s*"(\w+)"\s*,\s*[^,]+,\s*"(\w+)"', code):
            stats.add(m.group(2))
        for m in re.finditer(r'skillModList:Flag\(\s*[^,]+,\s*"(\w+)"', code):
            stats.add(m.group(1))
        for m in re.finditer(r'skillModList:More\(\s*[^,]+,\s*"(\w+)"', code):
            stats.add(m.group(1))
        for m in re.finditer(r'skillModList:Override\(\s*[^,]+,\s*"(\w+)"', code):
            stats.add(m.group(1))

        # 模式7-10: modDB:Sum/Flag/More/Override
        for m in re.finditer(r'modDB:Sum\(\s*"(\w+)"\s*,\s*[^,]+,\s*"(\w+)"', code):
            stats.add(m.group(2))
        for m in re.finditer(r'modDB:Flag\(\s*[^,]+,\s*"(\w+)"', code):
            stats.add(m.group(1))
        for m in re.finditer(r'modDB:More\(\s*[^,]+,\s*"(\w+)"', code):
            stats.add(m.group(1))
        for m in re.finditer(r'modDB:Override\(\s*[^,]+,\s*"(\w+)"', code):
            stats.add(m.group(1))

        # 模式11: calcLib.mod
        for m in re.finditer(r'calcLib\.mod\([^)]*', code):
            for s in re.finditer(r'"(\w+)"', m.group(0)):
                stat_name = s.group(1)
                if stat_name not in ('BASE', 'INC', 'MORE', 'FLAG', 'OVERRIDE', 'LIST'):
                    stats.add(stat_name)

        # 模式12-13: Tabulate
        for m in re.finditer(r'(?:skillModList|modDB):Tabulate\(\s*"(\w+)"\s*,\s*[^,]+,\s*"(\w+)"', code):
            stats.add(m.group(2))

        # 模式14: NewMod
        for m in re.finditer(r'(?:skillModList|modDB):NewMod\(\s*"(\w+)"', code):
            stats.add(m.group(1))

        filter_words = {
            'nil', 'true', 'false', 'self', 'env', 'actor', 'player', 'enemy',
            'mainSkill', 'activeSkill', 'skill', 'source', 'breakdown',
            'cfg', 'skillCfg', 'value', 'mod', 'index', 'count', 'name',
            'type', 'level', 'num', 'str', 'table', 'math', 'string',
        }

        return list(stats - filter_words)

    def _infer_tags(self, code: str) -> List[str]:
        """从代码推断标签"""
        tags = set()

        trigger_rules = [
            (r'triggerSource|triggeredBy|\.triggered\b', 'triggered'),
            (r'triggerRate|triggerCD|TriggerRateCap', 'trigger_rate'),
            (r'CastWhileChannelling|CWC', 'cwc'),
            (r'CastOnCrit|CoC', 'coc'),
            (r'CastOnDeath', 'cod'),
            (r'CastOnMeleeKill|COMK', 'comk'),
        ]

        skill_rules = [
            (r'cooldown|CooldownRecovery', 'cooldown'),
            (r'castTime|CastSpeed|SpellCastTime', 'cast'),
            (r'attackSpeed|AttackRate|attackTime', 'attack'),
            (r'spell\b|SpellDamage', 'spell'),
            (r'projectile|Projectile', 'projectile'),
            (r'area\b|AreaOfEffect|AreaDamage', 'area'),
            (r'minion|Minion|SummonedMinion', 'minion'),
            (r'totem|Totem', 'totem'),
            (r'trap\b|Trap', 'trap'),
            (r'mine\b|Mine', 'mine'),
            (r'channel|Channelling', 'channel'),
            (r'melee|Melee', 'melee'),
            (r'ranged|Ranged', 'ranged'),
            (r'warcry|Warcry', 'warcry'),
            (r'aura\b|Aura', 'aura'),
            (r'curse|Curse', 'curse'),
            (r'brand|Brand', 'brand'),
        ]

        damage_rules = [
            (r'PhysicalDamage|physical', 'physical'),
            (r'FireDamage|fire\b', 'fire'),
            (r'ColdDamage|cold\b', 'cold'),
            (r'LightningDamage|lightning', 'lightning'),
            (r'ChaosDamage|chaos\b', 'chaos'),
            (r'ElementalDamage|elemental', 'elemental'),
            (r'DamageOverTime|DoT\b|dot\b', 'dot'),
            (r'bleed\b|Bleed|Bleeding', 'bleed'),
            (r'poison\b|Poison', 'poison'),
            (r'ignite\b|Ignite', 'ignite'),
        ]

        calc_rules = [
            (r'crit|CritChance|CritMultiplier', 'crit'),
            (r'accuracy|Accuracy', 'accuracy'),
            (r'armour|Armour', 'armour'),
            (r'evasion|Evasion', 'evasion'),
            (r'energyShield|EnergyShield', 'energy_shield'),
            (r'life\b|Life', 'life'),
            (r'mana\b|Mana', 'mana'),
            (r'leech|Leech', 'leech'),
            (r'block|Block', 'block'),
            (r'resist|Resist', 'resist'),
            (r'penetrat|Penetration', 'penetration'),
        ]

        for rules in [trigger_rules, skill_rules, damage_rules, calc_rules]:
            for pattern, tag in rules:
                if re.search(pattern, code):
                    tags.add(tag)

        return list(tags)

    def _extract_function_calls(self, code: str) -> List[str]:
        """提取函数调用"""
        calls = []
        pattern = r'\b(\w+)\s*\('
        matches = re.findall(pattern, code)

        keywords = {'if', 'for', 'while', 'function', 'return', 'local', 'end', 'then', 'else', 'elseif', 'do', 'repeat', 'until'}
        builtin = {'print', 'pairs', 'ipairs', 'next', 'type', 'tostring', 'tonumber', 'math', 'table', 'string'}

        for match in matches:
            if match not in keywords and match not in builtin:
                calls.append(match)

        return list(set(calls))

    def _save_formulas(self, formulas: List[Dict]):
        """保存公式到数据库"""
        print("\n保存公式到数据库...")

        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        for formula in formulas:
            try:
                cursor.execute("""
                    INSERT OR REPLACE INTO formulas
                    (id, name, code, source_file, line_start, line_end,
                     exact_stats, fuzzy_stats, inferred_tags, calls, called_by,
                     call_depth, total_stats, constraints, description)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    formula['id'],
                    formula['name'],
                    formula['code'],
                    formula['source_file'],
                    formula['line_start'],
                    formula['line_end'],
                    formula['exact_stats'],
                    formula['fuzzy_stats'],
                    formula['inferred_tags'],
                    formula['calls'],
                    formula['called_by'],
                    formula['call_depth'],
                    formula['total_stats'],
                    formula['constraints'],
                    formula['description']
                ))

                formula_id = formula['id']

                for stat in json.loads(formula['exact_stats']):
                    cursor.execute("""
                        INSERT OR IGNORE INTO formula_features
                        (formula_id, feature_type, feature_value, confidence)
                        VALUES (?, 'exact', ?, 1.0)
                    """, (formula_id, stat))

                for stat in json.loads(formula['fuzzy_stats']):
                    cursor.execute("""
                        INSERT OR IGNORE INTO formula_features
                        (formula_id, feature_type, feature_value, confidence)
                        VALUES (?, 'fuzzy', ?, 0.7)
                    """, (formula_id, stat))

                for tag in json.loads(formula['inferred_tags']):
                    cursor.execute("""
                        INSERT OR IGNORE INTO formula_features
                        (formula_id, feature_type, feature_value, confidence)
                        VALUES (?, 'tag', ?, 0.8)
                    """, (formula_id, tag))

            except Exception as e:
                print(f"[错误] 保存公式失败 {formula['id']}: {e}")

        conn.commit()
        conn.close()

        print(f"[OK] 已保存 {len(formulas)} 个公式到数据库")

    # ================================================================
    # 缺口公式提取（v7: 合并自 stat_formula_extractor）
    # ================================================================

    def extract_gap_formulas(self) -> List[GapFormula]:
        """提取Meta技能缺口公式（v7合并版）"""
        if not self.entities_db_path or not self.entities_db_path.exists():
            print("[WARN] 缺少实体库路径，跳过缺口公式提取")
            return []

        self.gap_formulas = []

        # Step 0: 加载StatDescriptions映射
        self._load_stat_descriptions()
        print(f"    加载 {len(self._stat_descriptions)} 条能量stat描述")

        # Step 1: 预加载 GeneratesEnergy 辅助宝石
        self._energy_support_gems = self._query_energy_support_gems()
        print(f"    找到 {len(self._energy_support_gems)} 个GeneratesEnergy辅助宝石")

        # Step 1.5: 预加载被动/升华天赋节点中的能量修饰符
        self._passive_energy_modifiers = self._query_passive_energy_modifiers()
        passive_inc = sum(1 for m in self._passive_energy_modifiers if m.mod_type == 'INC')
        passive_more = sum(1 for m in self._passive_energy_modifiers if m.mod_type == 'MORE')
        print(f"    找到 {len(self._passive_energy_modifiers)} 个被动/升华能量修饰符 (INC={passive_inc}, MORE={passive_more})")

        # Step 1.6: 预加载被触发法术的能量MORE惩罚
        self._triggered_spell_more_modifiers = self._query_triggered_spell_energy_more()
        print(f"    找到 {len(self._triggered_spell_more_modifiers)} 个被触发法术能量MORE惩罚")

        # Step 1.7: 预加载装备词缀中的能量修饰符
        self._equipment_energy_modifiers = self._scan_equipment_energy_mods()
        print(f"    找到 {len(self._equipment_energy_modifiers)} 个装备词缀能量修饰符")

        # Step 2: 获取所有Meta技能实体
        meta_entities = self._get_meta_entities()
        print(f"    找到 {len(meta_entities)} 个Meta技能实体")

        # Step 3: 获取所有隐藏Support实体
        support_entities = self._get_support_meta_entities()
        print(f"    找到 {len(support_entities)} 个SupportMeta实体")

        # Step 4: 建立Meta→Support关联
        meta_support_map = self._build_meta_support_map(meta_entities, support_entities)

        # Step 5: 从每个Meta技能提取公式
        for entity in meta_entities:
            entity_id = entity['id']
            entity_name = entity.get('name', entity_id)
            data = entity.get('data', {})
            support_data = meta_support_map.get(entity_id, {})

            modifiers = self._collect_energy_modifiers(entity)

            self._extract_energy_gain(entity_id, entity_name, data, modifiers)
            self._extract_max_energy(entity_id, entity_name, data, support_data)
            self._extract_damage_modifier(entity_id, entity_name, data, support_data)
            self._extract_trigger_condition(entity_id, entity_name, data)

        print(f"    总计提取 {len(self.gap_formulas)} 个缺口公式")
        return self.gap_formulas

    def _classify_stat_by_name(self, stat_name: str) -> str:
        """根据命名约定判断 stat 类型（数据结构层面，v7核心改进）"""
        if stat_name.endswith('_+%_final'):
            return 'MORE'
        elif stat_name.endswith('_+%'):
            return 'INC'
        else:
            return 'SPECIAL'

    def _load_stat_descriptions(self):
        """从StatDescriptions加载能量相关stat的精确描述文本"""
        self._stat_descriptions = {}

        stat_desc_file = self._find_stat_descriptions_file()
        if not stat_desc_file:
            print("    [警告] 未找到StatDescriptions文件，将使用stat名称推断公式")
            return

        try:
            content = stat_desc_file.read_text(encoding='utf-8', errors='replace')

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

        kb_path = self.entities_db_path.parent if self.entities_db_path else Path('.')
        project_root = kb_path.parent.parent.parent

        for candidate in [
            project_root / 'POBData' / 'Data' / 'StatDescriptions' / 'skill_stat_descriptions.lua',
            project_root.parent / 'POBData' / 'Data' / 'StatDescriptions' / 'skill_stat_descriptions.lua',
        ]:
            if candidate.exists():
                return candidate

        for parent in [project_root, kb_path.parent, kb_path.parent.parent]:
            for f in parent.rglob('skill_stat_descriptions.lua'):
                return f

        return None

    def _query_energy_support_gems(self) -> List[Dict]:
        """查询 entities.db 中 requireSkillTypes 包含 'GeneratesEnergy' 的辅助宝石"""
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

    def _query_passive_energy_modifiers(self) -> List[EnergyModifier]:
        """从被动天赋/升华节点提取能量修饰符（v7改进版）"""
        modifiers: List[EnergyModifier] = []

        conn = sqlite3.connect(str(self.entities_db_path))
        cursor = conn.cursor()

        energy_patterns = [
            (PASSIVE_ENERGY_INC_PATTERN, 'energy_generated_+%', 'INC'),
            (PASSIVE_ENERGY_MORE_PATTERN, 'ascendancy_energy_generated_+%_final', 'MORE'),
            (PASSIVE_ENERGY_DOUBLED_PATTERN, 'energy_generation_is_doubled', 'SPECIAL'),
        ]
        for pattern, mod_type, stat_id in PASSIVE_ENERGY_CONDITIONAL_PATTERNS:
            energy_patterns.append((pattern, stat_id, mod_type))

        cursor.execute('''
            SELECT id, name, type, stat_descriptions, ascendancy_name
            FROM entities
            WHERE (type = 'passive_node' OR type = 'ascendancy_node')
              AND stat_descriptions IS NOT NULL
              AND stat_descriptions != '[]'
              AND (stat_descriptions LIKE '%Meta Skills%Energy%'
                   OR stat_descriptions LIKE '%Energy Generation%')
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

                for pattern, stat_id, default_type in energy_patterns:
                    m = pattern.search(text)
                    if m:
                        if default_type == 'SPECIAL':
                            value = 2
                        else:
                            value = int(m.group(1))

                        if 'reduced' in text.lower() or 'less' in text.lower():
                            value = -value

                        actual_type = self._classify_stat_by_name(stat_id)

                        modifiers.append(EnergyModifier(
                            stat_name=stat_id,
                            mod_type=actual_type,
                            source_field='stat_descriptions (mode: pattern_match)',
                            source_entity=eid,
                            value=value,
                            per_quality=False,
                            evidence=(
                                f"{'Ascendancy' if ascendancy else 'Passive'} node {eid} "
                                f"({name or 'unnamed'}): \"{text}\" → "
                                f"stat={stat_id}, type={actual_type} (命名约定)"
                            )
                        ))
                        break

        conn.close()
        return modifiers

    def _query_triggered_spell_energy_more(self) -> List[EnergyModifier]:
        """查询被触发法术的 active_skill_energy_generated_+%_final"""
        modifiers: List[EnergyModifier] = []

        conn = sqlite3.connect(str(self.entities_db_path))
        cursor = conn.cursor()

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
                            f"active_skill_energy_generated_+%_final={stat_value}"
                        )
                    ))

        conn.close()
        return modifiers

    def _scan_equipment_energy_mods(self) -> List[EnergyModifier]:
        """从 entities.db 查询 mod_affix 实体，提取装备词缀中的能量修饰符（v7改进版）"""
        modifiers: List[EnergyModifier] = []

        if not self.entities_db_path.exists():
            return modifiers

        conn = sqlite3.connect(str(self.entities_db_path))
        cursor = conn.cursor()

        cursor.execute('''
            SELECT id, name, stat_descriptions
            FROM entities
            WHERE type = 'mod_affix'
              AND stat_descriptions IS NOT NULL
              AND stat_descriptions != '[]'
              AND stat_descriptions LIKE '%Meta Skills%Energy%'
        ''')

        range_pattern = re.compile(
            r'Meta Skills gain \((\d+)-(\d+)\)% (increased|reduced|more|less) Energy',
            re.IGNORECASE
        )
        fixed_pattern = re.compile(
            r'Meta Skills gain (\d+)% (increased|reduced|more|less) Energy',
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

                m = range_pattern.search(text)
                if m:
                    min_val = int(m.group(1))
                    max_val = int(m.group(2))
                    mod_type_str = m.group(3).lower()
                    mid_value = (min_val + max_val) // 2

                    if mod_type_str in ('more', 'less'):
                        stat_id = 'ascendancy_energy_generated_+%_final'
                    else:
                        stat_id = 'energy_generated_+%'

                    actual_type = self._classify_stat_by_name(stat_id)

                    if mod_type_str in ('reduced', 'less'):
                        mid_value = -mid_value

                    modifiers.append(EnergyModifier(
                        stat_name=stat_id,
                        mod_type=actual_type,
                        source_field='stat_descriptions (mode: pattern_match)',
                        source_entity=mod_id,
                        value=mid_value,
                        per_quality=False,
                        evidence=f"Equipment mod {mod_id}: \"{text}\" → stat={stat_id}, type={actual_type}"
                    ))
                    continue

                m = fixed_pattern.search(text)
                if m:
                    value = int(m.group(1))
                    mod_type_str = m.group(2).lower()

                    if mod_type_str in ('more', 'less'):
                        stat_id = 'ascendancy_energy_generated_+%_final'
                    else:
                        stat_id = 'energy_generated_+%'

                    actual_type = self._classify_stat_by_name(stat_id)

                    if mod_type_str in ('reduced', 'less'):
                        value = -value

                    modifiers.append(EnergyModifier(
                        stat_name=stat_id,
                        mod_type=actual_type,
                        source_field='stat_descriptions (mode: pattern_match)',
                        source_entity=mod_id,
                        value=value,
                        per_quality=False,
                        evidence=f"Equipment mod {mod_id}: \"{text}\" → stat={stat_id}, type={actual_type}"
                    ))

        conn.close()
        return modifiers

    def _collect_energy_modifiers(self, entity: Dict) -> List[EnergyModifier]:
        """从实体完整数据中动态收集所有能量相关的INC/MORE修饰符"""
        modifiers: List[EnergyModifier] = []
        entity_id = entity['id']
        data = entity.get('data', {})

        # 扫描 stats 列表
        stats_list = self._normalize_stats_list(
            data.get('stats', data.get('stats', entity.get('stats', [])))
        )
        for stat_name in stats_list:
            if not isinstance(stat_name, str):
                continue
            mod = self._classify_modifier(stat_name, None, 'stats', entity_id)
            if mod:
                modifiers.append(mod)

        # 扫描 constantStats
        constant_stats = self._normalize_stat_pairs(
            data.get('constant_stats', data.get('constantStats', entity.get('constant_stats', [])))
        )
        for stat_name, stat_value in constant_stats:
            mod = self._classify_modifier(stat_name, stat_value, 'constantStats', entity_id)
            if mod:
                modifiers.append(mod)

        # 扫描 qualityStats
        quality_stats = self._normalize_stat_pairs(
            data.get('quality_stats', data.get('qualityStats', entity.get('quality_stats', [])))
        )
        for stat_name, stat_value in quality_stats:
            mod = self._classify_modifier(stat_name, stat_value, 'qualityStats', entity_id)
            if mod:
                mod.per_quality = True
                modifiers.append(mod)

        # 扫描外部Support辅助宝石
        if self._energy_support_gems:
            for sup in self._energy_support_gems:
                sup_id = sup['id']
                sup_constants = self._normalize_stat_pairs(sup.get('constant_stats', []))
                for stat_name, stat_value in sup_constants:
                    mod = self._classify_modifier(stat_name, stat_value, 'constantStats', sup_id)
                    if mod:
                        mod.evidence = f"Support gem {sup_id}: {stat_name}={stat_value}"
                        modifiers.append(mod)

        # 添加被动/升华修饰符
        if self._passive_energy_modifiers:
            modifiers.extend(self._passive_energy_modifiers)

        # 添加被触发法术MORE惩罚
        if self._triggered_spell_more_modifiers:
            modifiers.extend(self._triggered_spell_more_modifiers)

        # 添加装备词缀修饰符
        if self._equipment_energy_modifiers:
            modifiers.extend(self._equipment_energy_modifiers)

        return modifiers

    def _classify_modifier(self, stat_name: str, stat_value: Optional[float],
                           source_field: str, source_entity: str) -> Optional[EnergyModifier]:
        """判定单个stat是否为能量相关的INC或MORE修饰符"""
        if not isinstance(stat_name, str):
            return None

        stat_lower = stat_name.lower()
        if 'energy' not in stat_lower:
            return None

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

    def _get_meta_entities(self) -> List[Dict]:
        """获取所有Meta技能实体"""
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

    def _build_inc_term(self, modifiers: List[EnergyModifier]) -> Tuple[str, List[Dict]]:
        """从收集到的INC修饰符构建公式中的INC项"""
        inc_mods = [m for m in modifiers if m.mod_type == 'INC']
        cond_inc_mods = [m for m in modifiers if m.mod_type == 'INC_CONDITIONAL']

        if not inc_mods and not cond_inc_mods:
            return '', []

        unique_stats = []
        seen_names: Set[str] = set()
        for m in inc_mods:
            if m.stat_name not in seen_names:
                seen_names.add(m.stat_name)
                unique_stats.append(m)

        if len(unique_stats) == 1:
            stat = unique_stats[0]
            formula_part = f"(1 + Σ({stat.stat_name}) / 100)"
        elif len(unique_stats) > 1:
            stat_names = ' + '.join(m.stat_name for m in unique_stats)
            formula_part = f"(1 + Σ({stat_names}) / 100)"
        else:
            formula_part = ''

        if cond_inc_mods:
            cond_names = set(m.stat_name for m in cond_inc_mods)
            cond_part = ' + '.join(cond_names)
            if formula_part:
                formula_part += f" [条件INC可选: {cond_part}]"
            else:
                formula_part = f"[条件INC: (1 + Σ({cond_part}) / 100)]"

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
        """从收集到的MORE修饰符构建公式中的MORE项"""
        more_mods = [m for m in modifiers if m.mod_type == 'MORE']
        special_mods = [m for m in modifiers if m.mod_type == 'SPECIAL']

        if not more_mods and not special_mods:
            return '', []

        parts_list = []

        unique_more = []
        seen_names: Set[str] = set()
        for m in more_mods:
            if m.stat_name not in seen_names:
                seen_names.add(m.stat_name)
                unique_more.append(m)

        if len(unique_more) == 1:
            stat = unique_more[0]
            parts_list.append(f"Π(1 + {stat.stat_name} / 100)")
        elif len(unique_more) > 1:
            more_parts = [f"(1 + {m.stat_name}/100)" for m in unique_more]
            parts_list.append(" × ".join(more_parts))

        for m in special_mods:
            if m.stat_name == 'energy_generation_is_doubled':
                parts_list.append("[×2 if energy_generation_is_doubled]")

        formula_part = " × ".join(parts_list) if parts_list else ''

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

    def _classify_energy_stat(self, stat_name: str, stat_value: int,
                              modifiers: List[EnergyModifier]) -> Optional[Dict]:
        """分类能量获取公式并生成带数据证据的公式文本"""
        desc_text = self._stat_descriptions.get(stat_name, '')

        inc_term, inc_evidence = self._build_inc_term(modifiers)
        more_term, more_evidence = self._build_more_term(modifiers)

        mod_suffix = ''
        if inc_term:
            mod_suffix += f" × {inc_term}"
        if more_term:
            mod_suffix += f" × {more_term}"

        base_params = {
            'centienergy': stat_value,
            'source_stat': stat_name,
        }
        if inc_evidence:
            base_params['inc_evidence'] = inc_evidence
        if more_evidence:
            base_params['more_evidence'] = more_evidence

        # monster_power 型
        m = STAT_PATTERN_MONSTER_POWER.match(stat_name)
        if m:
            trigger_event = m.group(3) if m.lastindex >= 3 else 'unknown'
            has_ailment_threshold = AILMENT_THRESHOLD_PHRASE in desc_text if desc_text else False
            has_per_power = any(p in desc_text for p in PER_POWER_PHRASES) if desc_text else True

            base_params['trigger_event'] = trigger_event
            base_params['has_enemy_power'] = has_per_power
            base_params['has_ailment_threshold'] = has_ailment_threshold

            if has_ailment_threshold:
                return {
                    'subtype': 'SubA',
                    'formula_text': f"energy = enemy_power × ({stat_value}/100) × (hit_damage / ailment_threshold){mod_suffix}",
                    'params': base_params,
                    'description': desc_text or f"per Power, modified by Ailment Threshold ({trigger_event})",
                    'confidence': 0.95 if desc_text else 0.70,
                    'notes': 'SubA: enemy_power缩放 + ailment_threshold修正',
                }
            elif has_per_power:
                return {
                    'subtype': 'SubB',
                    'formula_text': f"energy = enemy_power × ({stat_value}/100){mod_suffix}",
                    'params': base_params,
                    'description': desc_text or f"per Power of enemies ({trigger_event})",
                    'confidence': 0.90 if desc_text else 0.70,
                    'notes': 'SubB: 仅enemy_power缩放',
                }
            else:
                return {
                    'subtype': 'SubC',
                    'formula_text': f"energy = ({stat_value}/100){mod_suffix}",
                    'params': base_params,
                    'description': desc_text or f"fixed energy per event ({trigger_event})",
                    'confidence': 0.85 if desc_text else 0.60,
                    'notes': 'SubC: stat名含monster_power但无"per Power"',
                }

        # minion_death 型
        m = STAT_PATTERN_MINION_DEATH.match(stat_name)
        if m:
            base_params['base_energy'] = 50
            base_params['has_minion_power'] = True
            return {
                'subtype': 'SubF',
                'formula_text': f"energy = base_energy × (minion_power_ratio){mod_suffix}",
                'params': base_params,
                'description': desc_text or "base Energy when Minion killed, modified by Minion's Power",
                'confidence': 0.90 if desc_text else 0.65,
                'notes': 'SubF: minion_death型, base_energy=50',
            }

        # 固定值型
        m = STAT_PATTERN_FIXED_EVENT.match(stat_name)
        if m:
            event = m.group(3)
            base_params['trigger_event'] = event
            return {
                'subtype': 'SubD',
                'formula_text': f"energy = ({stat_value}/100){mod_suffix}",
                'params': base_params,
                'description': desc_text or f"fixed energy on {event}",
                'confidence': 0.90 if desc_text else 0.70,
                'notes': f'SubD: 固定值型, 事件={event}',
            }

        # 连续/计量型
        m = STAT_PATTERN_CONTINUOUS.match(stat_name)
        if m:
            unit = m.group(3)
            base_params['unit'] = unit
            return {
                'subtype': 'SubE',
                'formula_text': f"energy = ({stat_value}/100) × {unit}_measure{mod_suffix}",
                'params': base_params,
                'description': desc_text or f"energy per {unit}",
                'confidence': 0.85 if desc_text else 0.60,
                'notes': f'SubE: 连续/计量型, 按{unit}计量',
            }

        return None

    def _extract_energy_gain(self, entity_id: str, entity_name: str, data: Dict,
                             modifiers: List[EnergyModifier]):
        """从实体数据提取能量获取公式"""
        constant_stats = self._normalize_stat_pairs(
            data.get('constant_stats', data.get('constantStats', []))
        )

        for stat_name, stat_value in constant_stats:
            if 'centienergy' not in stat_name and 'energy_per' not in stat_name:
                continue

            classification = self._classify_energy_stat(stat_name, int(stat_value), modifiers)
            if classification:
                params = classification['params']

                all_stat_sources = [stat_name]
                for m in modifiers:
                    if m.stat_name not in all_stat_sources:
                        all_stat_sources.append(m.stat_name)

                self.gap_formulas.append(GapFormula(
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
                    notes=f"[{classification['subtype']}] {classification['notes']}"
                ))
                break

    def _extract_max_energy(self, entity_id: str, entity_name: str, data: Dict, support_data: Dict):
        """提取最大能量公式"""
        all_constant_stats = []

        sup_constants = support_data.get('constant_stats', support_data.get('constantStats',
                         support_data.get('data', {}).get('constant_stats',
                         support_data.get('data', {}).get('constantStats', []))))
        if isinstance(sup_constants, dict):
            sup_constants = [[k, v] for k, v in sup_constants.items()]
        all_constant_stats.extend(sup_constants)

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

                    self.gap_formulas.append(GapFormula(
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

                    self.gap_formulas.append(GapFormula(
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
            self.gap_formulas.append(GapFormula(
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

    def save_gap_formulas(self):
        """保存缺口公式到数据库"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        # 清空旧数据
        cursor.execute('DELETE FROM gap_formulas')

        for f in self.gap_formulas:
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

    def diagnose_gap_formulas(self):
        """诊断输出缺口公式"""
        total = len(self.gap_formulas)
        by_type = {}
        by_entity = {}
        for f in self.gap_formulas:
            by_type[f.formula_type] = by_type.get(f.formula_type, 0) + 1
            by_entity[f.entity_id] = by_entity.get(f.entity_id, 0) + 1

        print(f"\n--- 缺口公式统计 ---")
        print(f"  总公式数: {total}")
        print(f"  覆盖实体: {len(by_entity)}")

        if total > 0:
            print(f"  平均置信度: {sum(f.confidence for f in self.gap_formulas) / total:.2f}")

        print(f"\n  按类型:")
        for ftype, count in sorted(by_type.items()):
            print(f"    {ftype}: {count}")

        if self.gap_formulas:
            print(f"\n  样本:")
            for f in self.gap_formulas[:5]:
                print(f"    [{f.entity_name}] {f.formula_type}: {f.formula_text[:80]}...")

    def get_gap_formulas_stats(self) -> Dict:
        """获取缺口公式统计信息（用于formula_index调用）"""
        total = len(self.gap_formulas)
        by_type = {}
        by_entity = {}
        for f in self.gap_formulas:
            by_type[f.formula_type] = by_type.get(f.formula_type, 0) + 1
            by_entity[f.entity_id] = by_entity.get(f.entity_id, 0) + 1

        return {
            'total': total,
            'entities_covered': len(by_entity),
            'by_type': by_type,
            'avg_confidence': sum(f.confidence for f in self.gap_formulas) / max(total, 1)
        }


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='公式提取器 v7')
    parser.add_argument('pob_path', help='POB数据目录路径')
    parser.add_argument('--db', default='formulas.db', help='公式库数据库路径')
    parser.add_argument('--entities-db', help='实体库路径')
    parser.add_argument('--lua-only', action='store_true', help='仅提取Lua函数')
    parser.add_argument('--gap-only', action='store_true', help='仅提取缺口公式')

    args = parser.parse_args()

    extractor = FormulaExtractor(
        pob_path=args.pob_path,
        db_path=args.db,
        entities_db_path=args.entities_db
    )

    if not args.gap_only:
        print("\n" + "=" * 70)
        print("Phase 1: Lua函数提取")
        print("=" * 70)
        formulas = extractor.extract_all_functions()
        print(f"\n完成！共提取 {len(formulas)} 个Lua函数公式")

    if not args.lua_only and args.entities_db:
        print("\n" + "=" * 70)
        print("Phase 2: 缺口公式提取")
        print("=" * 70)
        gap_formulas = extractor.extract_gap_formulas()
        extractor.save_gap_formulas()
        extractor.diagnose_gap_formulas()
        print(f"\n完成！共提取 {len(gap_formulas)} 个缺口公式")


if __name__ == "__main__":
    main()
