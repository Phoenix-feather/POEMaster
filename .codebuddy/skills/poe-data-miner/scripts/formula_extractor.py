#!/usr/bin/env python3
"""
公式提取器 - 从POB的Lua文件中提取所有计算函数

核心功能：
1. 解析Lua函数定义
2. 提取stat特征
3. 推断标签
4. 建立调用关系
5. 存储到formulas.db
"""

import os
import re
import json
import sqlite3
from pathlib import Path
from typing import Dict, List, Any, Optional, Set, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime


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


class FormulaExtractor:
    """公式提取器"""
    
    def __init__(self, pob_path: str, db_path: str, entities_db_path: str = None):
        """
        初始化公式提取器
        
        Args:
            pob_path: POB数据目录路径
            db_path: 公式库数据库路径
            entities_db_path: 实体库路径（用于加载官方stat ID）
        """
        self.pob_path = Path(pob_path)
        self.db_path = Path(db_path)
        self.entities_db_path = Path(entities_db_path) if entities_db_path else None
        
        # 加载官方stat ID
        self.official_stats = self._load_official_stats()
        
        # 初始化数据库
        self._init_database()
        
        print(f"[初始化] 公式提取器")
        print(f"  POB路径: {self.pob_path}")
        print(f"  数据库: {self.db_path}")
        print(f"  官方Stat ID数量: {len(self.official_stats)}")
    
    def _load_official_stats(self) -> Set[str]:
        """从实体库和SkillStatMap加载官方stat ID
        
        两个来源：
        1. 实体库 entities.db 中 stat_mapping 实体的 mod_data[].name (555个官方stat)
        2. SkillStatMap.lua 中的 skill/mod/flag 映射名称 (POB内部modifier)
        """
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
                
                # 提取 skill("name", ...) 中的name
                for m in re.finditer(r'skill\(\s*"(\w+)"', content):
                    official_stats.add(m.group(1))
                
                # 提取 mod("name", ...) 中的name
                for m in re.finditer(r'mod\(\s*"(\w+)"', content):
                    official_stats.add(m.group(1))
                
                # 提取 flag("name", ...) 中的name
                for m in re.finditer(r'flag\(\s*"(\w+)"', content):
                    official_stats.add(m.group(1))
                
                # 提取方括号中的官方stat key: ["stat_key_name"]
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
    
    def _init_database(self):
        """初始化数据库表"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        # 创建formulas表
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
        
        conn.commit()
        conn.close()
        
        print(f"[OK] 数据库初始化完成: {self.db_path}")
    
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
        seen_positions = set()  # 避免重复提取同一位置的函数
        
        # 统一的函数定义模式匹配
        # 支持：
        #   function name(params)
        #   local function name(params)
        #   function module.name(params)
        #   function module:name(params)
        patterns = [
            # local function name(params)
            (r'local\s+function\s+(\w+)\s*\(([^)]*)\)', True),
            # function module.name(params) 或 function module:name(params)
            (r'(?<!local\s)function\s+([\w.:]+)\s*\(([^)]*)\)', False),
        ]
        
        for pattern, is_local in patterns:
            for match in re.finditer(pattern, content):
                start_pos = match.start()
                
                # 避免重复（local function 已被第一个pattern匹配）
                if start_pos in seen_positions:
                    continue
                
                # 对于非local pattern，检查前面是否有local
                if not is_local:
                    prefix_start = max(0, start_pos - 10)
                    prefix = content[prefix_start:start_pos].strip()
                    if prefix.endswith('local'):
                        continue  # 跳过，让local pattern处理
                
                seen_positions.add(start_pos)
                
                func_name = match.group(1)
                params_str = match.group(2)
                params = [p.strip() for p in params_str.split(',') if p.strip()]
                
                # 提取函数体
                body = self._extract_function_body(content, start_pos)
                
                if body and len(body) > 10:  # 过滤掉空函数
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
        """提取Lua函数体（使用function...end关键字平衡）
        
        Lua的block结构：
        - function...end
        - if...then...end
        - for...do...end  
        - while...do...end
        - repeat...until(expr)
        - do...end
        """
        # 从start_pos开始，跳过 function name(params) 到函数体
        # 函数体从 function 关键字开始，到匹配的 end 结束
        
        # 使用tokenize方式追踪嵌套深度
        # block开始关键字：function, if, for, while, do, repeat
        # block结束关键字：end, until
        
        length = len(content)
        i = start_pos
        depth = 0
        in_string = False
        string_char = None
        in_comment = False
        in_block_comment = False
        
        # 预编译关键字集合
        block_start_keywords = {'function', 'if', 'for', 'while', 'do', 'repeat'}
        # 注意：then/else/elseif不增加深度，它们是if块内部的
        # do在for/while后面也不增加深度（已经由for/while计数）
        
        while i < length:
            # 处理block注释 --[[ ... ]]
            if in_block_comment:
                if content[i:i+2] == ']]':
                    in_block_comment = False
                    i += 2
                    continue
                i += 1
                continue
            
            # 处理行注释 --
            if in_comment:
                if content[i] == '\n':
                    in_comment = False
                i += 1
                continue
            
            # 处理字符串
            if in_string:
                if content[i] == '\\':
                    i += 2  # 跳过转义字符
                    continue
                if content[i] == string_char:
                    in_string = False
                i += 1
                continue
            
            # 检测注释开始
            if content[i:i+2] == '--':
                if content[i+2:i+4] == '[[':
                    in_block_comment = True
                    i += 4
                    continue
                else:
                    in_comment = True
                    i += 2
                    continue
            
            # 检测字符串开始
            if content[i] in ('"', "'"):
                in_string = True
                string_char = content[i]
                i += 1
                continue
            
            # 检测长字符串 [[ ... ]]
            if content[i:i+2] == '[[':
                # 找到匹配的 ]]
                end_pos = content.find(']]', i + 2)
                if end_pos != -1:
                    i = end_pos + 2
                    continue
                i += 2
                continue
            
            # 检测关键字（需要确保是完整的词，不是标识符的一部分）
            if content[i].isalpha() or content[i] == '_':
                # 提取标识符
                word_start = i
                while i < length and (content[i].isalnum() or content[i] == '_'):
                    i += 1
                word = content[word_start:i]
                
                if word == 'end':
                    depth -= 1
                    if depth == 0:
                        # 找到匹配的end，提取完整函数体
                        return content[start_pos:i]
                elif word == 'until':
                    # repeat...until 的结束
                    depth -= 1
                    if depth == 0:
                        # 跳过until后面的条件表达式
                        # 找到行尾或下一个语句
                        while i < length and content[i] != '\n':
                            i += 1
                        return content[start_pos:i]
                elif word in block_start_keywords:
                    depth += 1
                    # 特殊处理：for...do 和 while...do 中的 do 不再额外计数
                    # 因为 for/while 已经增加了depth
                    if word in ('for', 'while'):
                        # 跳到 do 关键字，但不增加depth
                        # 从当前位置寻找do
                        j = i
                        temp_depth = 0
                        while j < length:
                            if content[j].isalpha() or content[j] == '_':
                                ws = j
                                while j < length and (content[j].isalnum() or content[j] == '_'):
                                    j += 1
                                w = content[ws:j]
                                if w == 'do' and temp_depth == 0:
                                    i = j  # 跳过do
                                    break
                                elif w == 'function':
                                    temp_depth += 1
                                elif w == 'end':
                                    temp_depth -= 1
                                continue
                            elif content[j] in ('"', "'"):
                                # 跳过字符串
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
        
        # 没有找到匹配的end
        return None
    
    def _extract_formula(self, func: LuaFunction, source_file: Path) -> Optional[Dict]:
        """提取公式并分析特征"""
        # 提取特征
        features = self._extract_features(func.body)
        
        # 生成公式ID
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
        
        # 1. 提取stat名称
        stat_names = self._extract_stat_names(code)
        
        # 2. 分类为精确/模糊
        for stat_name in stat_names:
            if stat_name in self.official_stats:
                features.exact_stats.append(stat_name)
            else:
                features.fuzzy_stats.append(stat_name)
        
        # 3. 推断标签
        features.inferred_tags = self._infer_tags(code)
        
        # 4. 提取函数调用
        features.calls = self._extract_function_calls(code)
        
        return features
    
    def _extract_stat_names(self, code: str) -> List[str]:
        """从代码中提取stat名称（覆盖全部11种POB stat引用模式）
        
        两套平行API：
        - skillModList:* (技能级别)
        - modDB:* (角色/全局级别)
        
        引用频率（从高到低）：
        1. output.xxx           ~1920次
        2. skillData.xxx        ~428次  
        3. modDB:Sum(           ~337次
        4. modDB:Flag(          ~326次
        5. skillModList:Sum(    ~280次
        6. skillModList:Flag(   ~185次
        7. calcLib.mod(         ~159次
        8. modDB:Override(      ~72次
        9. skillModList:More(   ~68次
        10. modDB:More(         ~50次
        11. skillModList:Override( ~26次
        """
        stats = set()
        
        # 模式1: output.xxx (最频繁 ~1920次)
        for m in re.finditer(r'output\.(\w+)', code):
            stats.add(m.group(1))
        
        # 模式2: skillData.xxx (多种前缀: skill., activeSkill., env.player.mainSkill.)
        for m in re.finditer(r'(?:\w+\.)?skillData\.(\w+)', code):
            stats.add(m.group(1))
        
        # 模式3: skillModList:Sum("BASE"/"INC", cfg, "StatName")
        for m in re.finditer(r'skillModList:Sum\(\s*"(\w+)"\s*,\s*[^,]+,\s*"(\w+)"', code):
            stats.add(m.group(2))
        
        # 模式4: skillModList:Flag(cfg, "StatName")
        for m in re.finditer(r'skillModList:Flag\(\s*[^,]+,\s*"(\w+)"', code):
            stats.add(m.group(1))
        
        # 模式5: skillModList:More(cfg, "StatName")
        for m in re.finditer(r'skillModList:More\(\s*[^,]+,\s*"(\w+)"', code):
            stats.add(m.group(1))
        
        # 模式6: skillModList:Override(cfg, "StatName")
        for m in re.finditer(r'skillModList:Override\(\s*[^,]+,\s*"(\w+)"', code):
            stats.add(m.group(1))
        
        # 模式7: modDB:Sum("BASE"/"INC", cfg/nil, "StatName")
        for m in re.finditer(r'modDB:Sum\(\s*"(\w+)"\s*,\s*[^,]+,\s*"(\w+)"', code):
            stats.add(m.group(2))
        
        # 模式8: modDB:Flag(cfg/nil, "StatName")
        for m in re.finditer(r'modDB:Flag\(\s*[^,]+,\s*"(\w+)"', code):
            stats.add(m.group(1))
        
        # 模式9: modDB:More(cfg/nil, "StatName")
        for m in re.finditer(r'modDB:More\(\s*[^,]+,\s*"(\w+)"', code):
            stats.add(m.group(1))
        
        # 模式10: modDB:Override(cfg/nil, "StatName")
        for m in re.finditer(r'modDB:Override\(\s*[^,]+,\s*"(\w+)"', code):
            stats.add(m.group(1))
        
        # 模式11: calcLib.mod(modList, cfg, "StatName1", "StatName2", ...)
        for m in re.finditer(r'calcLib\.mod\([^)]*', code):
            # 提取所有引号中的stat名称
            for s in re.finditer(r'"(\w+)"', m.group(0)):
                stat_name = s.group(1)
                # 排除非stat名称（如 BASE, INC, MORE 等修饰符）
                if stat_name not in ('BASE', 'INC', 'MORE', 'FLAG', 'OVERRIDE', 'LIST'):
                    stats.add(stat_name)
        
        # 模式12: skillModList:Tabulate("INC"/"MORE", cfg, "StatName")
        for m in re.finditer(r'skillModList:Tabulate\(\s*"(\w+)"\s*,\s*[^,]+,\s*"(\w+)"', code):
            stats.add(m.group(2))
        
        # 模式13: modDB:Tabulate("INC"/"MORE", cfg, "StatName")
        for m in re.finditer(r'modDB:Tabulate\(\s*"(\w+)"\s*,\s*[^,]+,\s*"(\w+)"', code):
            stats.add(m.group(2))
        
        # 模式14: skillModList:NewMod("StatName", ...)
        for m in re.finditer(r'(?:skillModList|modDB):NewMod\(\s*"(\w+)"', code):
            stats.add(m.group(1))
        
        # 过滤掉明显不是stat的名称
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
        
        # 触发机制标签
        trigger_rules = [
            (r'triggerSource|triggeredBy|\.triggered\b', 'triggered'),
            (r'triggerRate|triggerCD|TriggerRateCap', 'trigger_rate'),
            (r'CastWhileChannelling|CWC', 'cwc'),
            (r'CastOnCrit|CoC', 'coc'),
            (r'CastOnDeath', 'cod'),
            (r'CastOnMeleeKill|COMK', 'comk'),
        ]
        
        # 技能类型标签
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
        
        # 伤害类型标签
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
        
        # 防御/计算标签
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
        
        # 匹配 functionName( 格式
        pattern = r'\b(\w+)\s*\('
        matches = re.findall(pattern, code)
        
        # 过滤掉Lua关键字和内置函数
        keywords = {'if', 'for', 'while', 'function', 'return', 'local', 'end', 'then', 'else', 'elseif', 'do', 'repeat', 'until'}
        builtin = {'print', 'pairs', 'ipairs', 'next', 'type', 'tostring', 'tonumber', 'math', 'table', 'string'}
        
        for match in matches:
            if match not in keywords and match not in builtin:
                calls.append(match)
        
        return list(set(calls))  # 去重
    
    def _save_formulas(self, formulas: List[Dict]):
        """保存公式到数据库"""
        print("\n保存公式到数据库...")
        
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        # 批量插入
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
                
                # 插入特征索引
                formula_id = formula['id']
                
                # 精确stat
                for stat in json.loads(formula['exact_stats']):
                    cursor.execute("""
                        INSERT OR IGNORE INTO formula_features
                        (formula_id, feature_type, feature_value, confidence)
                        VALUES (?, 'exact', ?, 1.0)
                    """, (formula_id, stat))
                
                # 模糊stat
                for stat in json.loads(formula['fuzzy_stats']):
                    cursor.execute("""
                        INSERT OR IGNORE INTO formula_features
                        (formula_id, feature_type, feature_value, confidence)
                        VALUES (?, 'fuzzy', ?, 0.7)
                    """, (formula_id, stat))
                
                # 标签
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


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='公式提取器')
    parser.add_argument('pob_path', help='POB数据目录路径')
    parser.add_argument('--db', default='formulas.db', help='公式库数据库路径')
    parser.add_argument('--entities-db', help='实体库路径（用于加载官方stat ID）')
    
    args = parser.parse_args()
    
    # 创建提取器
    extractor = FormulaExtractor(
        pob_path=args.pob_path,
        db_path=args.db,
        entities_db_path=args.entities_db
    )
    
    # 提取所有函数
    formulas = extractor.extract_all_functions()
    
    print(f"\n完成！共提取 {len(formulas)} 个公式")


if __name__ == "__main__":
    main()
