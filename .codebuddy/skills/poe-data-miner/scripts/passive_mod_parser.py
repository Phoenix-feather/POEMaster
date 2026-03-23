#!/usr/bin/env python3
"""
passive_mod_parser.py - 天赋/升华 stat 描述文本解析器

从 POB ModParser.lua 的 formList + modNameList 提取核心模式，
将 "50% more Critical Damage Bonus" 解析为 {type: MORE, value: 50, name: CritMultiplier}

设计原则：
- 只解析天赋/升华实际出现的 stat 文本（~300种）
- 不追求 100% 覆盖 ModParser.lua 的全部模式（6000+行），按需扩展
- 无法解析的文本保持原样返回（parsed=False）

v1: 2026-03-20 初版
"""

import re
import json
import sqlite3
from typing import Optional
from pathlib import Path

# ============================================================
# formList: 识别 modifier 形式（MORE/LESS/INC/BASE 等）
# 从 ModParser.lua:62-152 提取，转为 Python 正则
# 顺序很重要：更具体的模式必须在前面
# ============================================================

FORM_PATTERNS = [
    # MORE / LESS
    (r'^(\d+)% more\b', 'MORE'),
    (r'^you have (\d+)% more\b', 'MORE'),
    (r'^(\d+)% less\b', 'LESS'),
    (r'^you have (\d+)% less\b', 'LESS'),
    # INC / RED
    (r'^(\d+)% increased\b', 'INC'),
    (r'^(\d+)% faster\b', 'INC'),
    (r'^(\d+)% reduced\b', 'RED'),
    (r'^(\d+)% slower\b', 'RED'),
    # Penetration
    (r'penetrates? (\d+)% of enemy\b', 'PEN'),
    (r'penetrates? (\d+)% of\b', 'PEN'),
    (r'penetrates? (\d+)%', 'PEN'),
    # Regen
    (r'^([\d.]+)% (.+) regenerated per second', 'REGENPERCENT'),
    (r'^([\d.]+)% of (.+) regenerated per second', 'REGENPERCENT'),
    (r'^([\d.]+)% (.+) regeneration per second', 'REGENPERCENT'),
    (r'^([\d.]+)% of (.+) regeneration per second', 'REGENPERCENT'),
    (r'^regenerate ([\d.]+)% (.+) per second', 'REGENPERCENT'),
    (r'^regenerate ([\d.]+)% of (.+) per second', 'REGENPERCENT'),
    (r'^regenerate ([\d.]+) (.+) per second', 'REGENFLAT'),
    (r'^([\d.]+) (.+) regeneration per second', 'REGENFLAT'),
    # Damage added
    (r'adds (\d+) to (\d+) (\w+) damage to spells and attacks', 'DMGBOTH'),
    (r'adds (\d+) to (\d+) (\w+) damage to attacks and spells', 'DMGBOTH'),
    (r'adds (\d+) to (\d+) (\w+) damage to hits', 'DMGBOTH'),
    (r'adds (\d+)-(\d+) (\w+) damage to spells and attacks', 'DMGBOTH'),
    (r'adds (\d+)-(\d+) (\w+) damage to attacks and spells', 'DMGBOTH'),
    (r'adds (\d+)-(\d+) (\w+) damage to hits', 'DMGBOTH'),
    (r'adds (\d+) to (\d+) (\w+) damage to spells', 'DMGSPELLS'),
    (r'adds (\d+)-(\d+) (\w+) damage to spells', 'DMGSPELLS'),
    (r'adds (\d+) to (\d+) (\w+) spell damage', 'DMGSPELLS'),
    (r'adds (\d+)-(\d+) (\w+) spell damage', 'DMGSPELLS'),
    (r'adds (\d+) to (\d+) (\w+) damage to attacks', 'DMGATTACKS'),
    (r'adds (\d+)-(\d+) (\w+) damage to attacks', 'DMGATTACKS'),
    (r'adds (\d+) to (\d+) (\w+) attack damage', 'DMGATTACKS'),
    (r'adds (\d+)-(\d+) (\w+) attack damage', 'DMGATTACKS'),
    (r'adds (\d+) to (\d+) (\w+) damage', 'DMG'),
    (r'adds (\d+)-(\d+) (\w+) damage', 'DMG'),
    (r'^(\d+) to (\d+) (\w+) damage', 'DMG'),
    (r'^(\d+)-(\d+) (\w+) damage', 'DMG'),
    # GAIN / LOSE (percentage)
    (r'^you gain ([\d.]+)%', 'GAIN'),
    (r'^gains? ([\d.]+)% of their\b', 'GAIN'),
    (r'^gains? ([\d.]+)% of\b', 'GAIN'),
    (r'^gains? ([\d.]+)', 'GAIN'),
    (r'^gain ([\d.]+)% of\b', 'GAIN'),
    (r'^you lose ([\d.]+)', 'LOSE'),
    (r'^loses? ([\d.]+)% of\b', 'LOSE'),
    (r'^lose ([\d.]+)', 'LOSE'),
    # BASE (with sign)
    (r'^([+-][\d.]+)%? to\b', 'BASE'),
    (r'^([+-][\d.]+)%? base\b', 'BASE'),
    (r'^([+-]?[\d.]+)%? additional\b', 'BASE'),
    (r'^([+-][\d.]+)%?\b', 'BASE'),
    # CHANCE
    (r'^([+-]?\d+)% chance\b', 'CHANCE'),
    (r'^([+-]?\d+)% additional chance\b', 'CHANCE'),
    # FLAG (qualitative)
    (r'^you have\b', 'FLAG'),
    (r'^have\b', 'FLAG'),
    (r'^you are\b', 'FLAG'),
    (r'^are\b', 'FLAG'),
    (r'^gain\b', 'FLAG'),
    (r'^you gain\b', 'FLAG'),
    # OVERRIDE
    (r'is (-?\d+)%?\b', 'OVERRIDE'),
    (r'is doubled', 'DOUBLED'),
    (r'doubles?', 'DOUBLED'),
    # Catch-all number
    (r'^(\d+)\b', 'BASE'),
]

# ============================================================
# modNameList: 属性名映射
# 从 ModParser.lua:155-950 提取，覆盖天赋/升华常见的属性
# key: 小写描述文本片段, value: 内部名称
# ============================================================

MOD_NAME_MAP = {
    # Attributes
    "strength": "Str",
    "dexterity": "Dex",
    "intelligence": "Int",
    "strength and dexterity": "StrDex",
    "strength and intelligence": "StrInt",
    "dexterity and intelligence": "DexInt",
    "all attributes": "AllAttributes",
    "attributes": "AllAttributes",
    "devotion": "Devotion",
    "spirit": "Spirit",
    "maximum spirit": "Spirit",
    # Life / Mana / ES
    "life": "Life",
    "maximum life": "Life",
    "life regeneration rate": "LifeRegen",
    "life regeneration": "LifeRegen",
    "mana": "Mana",
    "maximum mana": "Mana",
    "mana regeneration rate": "ManaRegen",
    "mana regeneration": "ManaRegen",
    "life and mana regeneration rate": "LifeManaRegen",
    "maximum energy shield": "EnergyShield",
    "energy shield": "EnergyShield",
    "energy shield recharge rate": "EnergyShieldRecharge",
    "armour": "Armour",
    "evasion": "Evasion",
    "evasion rating": "Evasion",
    "armour and evasion": "ArmourAndEvasion",
    "armour and evasion rating": "ArmourAndEvasion",
    "armour and energy shield": "ArmourAndEnergyShield",
    "evasion and energy shield": "EvasionAndEnergyShield",
    "armour, evasion and energy shield": "Defences",
    "defences": "Defences",
    "ward": "Ward",
    # Resistances
    "fire resistance": "FireResist",
    "cold resistance": "ColdResist",
    "lightning resistance": "LightningResist",
    "chaos resistance": "ChaosResist",
    "elemental resistances": "ElementalResist",
    "elemental resistance": "ElementalResist",
    "all elemental resistances": "ElementalResist",
    "all resistances": "AllResist",
    "maximum fire resistance": "FireResistMax",
    "maximum cold resistance": "ColdResistMax",
    "maximum lightning resistance": "LightningResistMax",
    "maximum chaos resistance": "ChaosResistMax",
    "all maximum elemental resistances": "ElementalResistMax",
    # Damage taken
    "damage taken": "DamageTaken",
    "damage taken when hit": "DamageTakenWhenHit",
    "damage taken from hits": "DamageTakenWhenHit",
    "physical damage taken": "PhysicalDamageTaken",
    "fire damage taken": "FireDamageTaken",
    "cold damage taken": "ColdDamageTaken",
    "lightning damage taken": "LightningDamageTaken",
    "chaos damage taken": "ChaosDamageTaken",
    "elemental damage taken": "ElementalDamageTaken",
    "damage over time taken": "DamageTakenOverTime",
    "physical damage reduction": "PhysicalDamageReduction",
    "damage taken from mana before life": "DamageTakenFromManaBeforeLife",
    "damage is taken from mana before life": "DamageTakenFromManaBeforeLife",
    # Damage
    "damage": "Damage",
    "physical damage": "PhysicalDamage",
    "fire damage": "FireDamage",
    "cold damage": "ColdDamage",
    "lightning damage": "LightningDamage",
    "chaos damage": "ChaosDamage",
    "elemental damage": "ElementalDamage",
    "attack damage": "Damage_Attack",
    "spell damage": "SpellDamage",
    "melee damage": "Damage_Melee",
    "projectile damage": "Damage_Projectile",
    "area damage": "Damage_Area",
    "damage over time": "Damage_DoT",
    "damage over time multiplier": "DotMultiplier",
    "physical damage over time multiplier": "PhysicalDotMultiplier",
    "fire damage over time multiplier": "FireDotMultiplier",
    "cold damage over time multiplier": "ColdDotMultiplier",
    "chaos damage over time multiplier": "ChaosDotMultiplier",
    "burning damage": "FireDamage_Dot",
    "non-chaos damage": "NonChaosDamage",
    # Crit
    "critical hit chance": "CritChance",
    "critical damage bonus": "CritMultiplier",
    "critical spell damage bonus": "CritMultiplier_Spell",
    "attack critical hit chance": "CritChance_Attack",
    "accuracy": "Accuracy",
    "accuracy rating": "Accuracy",
    # Speed
    "attack speed": "Speed_Attack",
    "cast speed": "Speed_Cast",
    "attack and cast speed": "Speed",
    "skill speed": "Speed",
    "movement speed": "MovementSpeed",
    "action speed": "ActionSpeed",
    # Area / Duration / Projectile
    "area of effect": "AreaOfEffect",
    "area of effect of skills": "AreaOfEffect",
    "area of effect of area skills": "AreaOfEffect",
    "duration": "Duration",
    "skill effect duration": "Duration",
    "cooldown recovery": "CooldownRecovery",
    "cooldown recovery rate": "CooldownRecovery",
    "cooldown recovery speed": "CooldownRecovery",
    "projectile speed": "ProjectileSpeed",
    "projectile": "ProjectileCount",
    "projectiles": "ProjectileCount",
    # Totem / Trap / Mine
    "totem life": "TotemLife",
    "totem duration": "TotemDuration",
    "totem placement speed": "TotemPlacementSpeed",
    "maximum number of summoned totems": "ActiveTotemLimit",
    "trap throwing speed": "TrapThrowingSpeed",
    "trap duration": "TrapDuration",
    "mine laying speed": "MineLayingSpeed",
    "mine duration": "MineDuration",
    # Minion
    "minion damage": "Damage_Minion",
    "minion life": "Life_Minion",
    "minion speed": "Speed_Minion",
    "minion duration": "Duration_Minion",
    # Ailments
    "chance to shock": "EnemyShockChance",
    "shock chance": "EnemyShockChance",
    "chance to freeze": "EnemyFreezeChance",
    "freeze chance": "EnemyFreezeChance",
    "chance to ignite": "EnemyIgniteChance",
    "ignite chance": "EnemyIgniteChance",
    "magnitude of shock you inflict": "EnemyShockMagnitude",
    "magnitude of chill you inflict": "EnemyChillMagnitude",
    "magnitude of ignite you inflict": "IgniteMagnitude",
    "magnitude of ailments you inflict": "AilmentMagnitude",
    "chill duration": "EnemyChillDuration",
    "chill duration on enemies": "EnemyChillDuration",
    "freeze duration": "EnemyFreezeDuration",
    "shock duration": "EnemyShockDuration",
    "ignite duration": "EnemyIgniteDuration",
    "duration of ailments you inflict": "EnemyAilmentDuration",
    "effect of non-damaging ailments you inflict": "NonDamageAilmentEffect",
    "effect of non-damaging ailments": "NonDamageAilmentEffect",
    "freeze buildup": "EnemyFreezeBuildup",
    "stun buildup": "EnemyHeavyStunBuildup",
    "electrocute buildup": "EnemyElectrocuteBuildup",
    # Charges
    "maximum power charges": "PowerChargesMax",
    "maximum power charge": "PowerChargesMax",
    "maximum frenzy charges": "FrenzyChargesMax",
    "maximum frenzy charge": "FrenzyChargesMax",
    "maximum endurance charges": "EnduranceChargesMax",
    "maximum endurance charge": "EnduranceChargesMax",
    "charge duration": "ChargeDuration",
    # Aura / Curse / Buff
    "aura effect": "AuraEffect",
    "effect of auras on you": "AuraEffectOnSelf",
    "curse effect": "CurseEffect",
    "effect of your curses": "CurseEffect",
    "buff effect": "BuffEffect",
    "effect of arcane surge on you": "ArcaneSurgeEffect",
    "effect of tailwind on you": "TailwindEffectOnSelf",
    "effect of elusive on you": "ElusiveEffect",
    "reservation efficiency": "ReservationEfficiency",
    "reservation efficiency of skills": "ReservationEfficiency",
    "mana reservation efficiency of skills": "ManaReservationEfficiency",
    "life reservation efficiency of skills": "LifeReservationEfficiency",
    "spirit reservation efficiency of skills": "SpiritReservationEfficiency",
    "maximum rage": "MaximumRage",
    # Avoidance
    "to block": "BlockChance",
    "to block attacks": "BlockChance",
    "to block attack damage": "BlockChance",
    "to block spells": "SpellBlockChance",
    "to block spell damage": "SpellBlockChance",
    "to dodge attacks": "AttackDodgeChance",
    "to dodge attack hits": "AttackDodgeChance",
    "to suppress spell damage": "SpellSuppressionChance",
    "chance to evade": "EvadeChance",
    "to evade attacks": "EvadeChance",
    "to avoid being stunned": "AvoidStun",
    "to avoid elemental ailments": "AvoidElementalAilments",
    # Recovery
    "life gained on kill": "LifeOnKill",
    "mana gained on kill": "ManaOnKill",
    "life recovery rate": "LifeRecoveryRate",
    "mana recovery rate": "ManaRecoveryRate",
    "energy shield recovery rate": "EnergyShieldRecoveryRate",
    "damage taken recouped as life": "LifeRecoup",
    "ailment threshold": "AilmentThreshold",
    # Flask
    "flask effect duration": "FlaskDuration",
    "flask charges gained": "FlaskChargesGained",
    "effect of flasks": "FlaskEffect",
    # Penetration targets
    "fire resistance": "FireResist",
    "cold resistance": "ColdResist",
    "lightning resistance": "LightningResist",
    "elemental resistances": "ElementalResist",
    # Misc
    "light radius": "LightRadius",
    "rarity of items found": "LootRarity",
    "quantity of items found": "LootQuantity",
    "weapon range": "WeaponRange",
    "melee strike range": "MeleeWeaponRange",
    "to deal double damage": "DoubleDamageChance",
    "impale effect": "ImpaleEffect",
    "to impale enemies on hit": "ImpaleChance",
    "stun duration": "EnemyStunDuration",
    "stun threshold": "StunThreshold",
    "presence area of effect": "PresenceArea",
}

# ============================================================
# Condition/qualifier patterns for "per X" / "while Y" / "when Z"
# ============================================================

CONDITION_PATTERNS = [
    (r'\bwhile (.+)', 'while'),
    (r'\bwhen (.+)', 'when'),
    (r'\bduring (.+)', 'during'),
    (r'\bif (.+)', 'if'),
    (r'\bagainst (.+)', 'against'),
    (r'\bvs (.+)', 'against'),
    (r'\bper (.+)', 'per'),
    (r'\bfor each (.+)', 'per'),
    (r'\bon (.+)', 'on'),
    (r'\bwith (.+)', 'with'),
    (r'\bto enemies (.+)', 'to_enemies'),
    (r'\bfrom (.+)', 'from'),
]

# ============================================================
# Special full-line patterns (Grants Skill, conversions, etc.)
# ============================================================

SPECIAL_PATTERNS = [
    # Grants Skill
    (r'^grants?\s+skill:\s*(.+)', 'grants_skill'),
    # Damage conversion
    (r'^(\d+)% of (.+?) (?:is )?converted to (.+?)$', 'conversion'),
    (r'^(\d+)% of (.+?) (?:is )?taken as (.+?)$', 'damage_shift'),
    (r'^gain (\d+)% of (.+?) as extra (.+?)$', 'extra_damage'),
    (r'^(\d+)% of (.+?) damage taken as (.+?) damage$', 'damage_shift'),
    # Triggers
    (r'^trigger (.+?) on (.+)', 'trigger'),
    # "X also applies to Y"
    (r'^(.+?) also applies to (.+)', 'also_applies'),
    # "All Damage from Hits Contributes to X"
    (r'^all damage from hits contributes to (.+)', 'contributes_to'),
    # "Cannot X" / "Can X"
    (r'^cannot (.+)', 'cannot'),
    (r'^can (.+)', 'can'),
    # "Skills fire additional projectile"
    (r'^skills? fire (?:an )?additional projectiles?$', 'additional_proj'),
    # "X does not Y"
    (r'^(.+?) (?:does not|do not) (.+)', 'negation'),
    # "Strikes deal Splash Damage"
    (r'^strikes deal splash damage', 'splash'),
]


class PassiveModParser:
    """解析天赋/升华 stat 描述文本为结构化 modifier"""

    def __init__(self):
        # Pre-compile form patterns
        self._form_patterns = [(re.compile(p, re.IGNORECASE), f) for p, f in FORM_PATTERNS]
        # Pre-compile special patterns
        self._special_patterns = [(re.compile(p, re.IGNORECASE), f) for p, f in SPECIAL_PATTERNS]
        # Pre-compile condition patterns
        self._condition_patterns = [(re.compile(p, re.IGNORECASE), f) for p, f in CONDITION_PATTERNS]
        # Sort mod names by length (longest first for greedy matching)
        self._mod_names_sorted = sorted(MOD_NAME_MAP.keys(), key=len, reverse=True)

    def parse_line(self, line: str) -> dict:
        """
        解析单行 stat 描述文本。

        Returns:
            {
                "original": str,        # 原始文本
                "parsed": bool,         # 是否成功解析
                "type": str,            # MORE/LESS/INC/RED/BASE/FLAG/...
                "value": float|None,    # 数值
                "name": str|None,       # 内部属性名（如 CritMultiplier）
                "form": str|None,       # 原始 form（如 MORE）
                "conditions": list,     # 条件列表 [{type, text}]
                "special": str|None,    # 特殊类型（grants_skill, conversion, etc）
                "special_data": dict,   # 特殊类型附加数据
            }
        """
        line = line.strip()
        if not line:
            return {"original": line, "parsed": False}

        result = {
            "original": line,
            "parsed": False,
            "type": None,
            "value": None,
            "name": None,
            "form": None,
            "conditions": [],
            "special": None,
            "special_data": {},
        }

        # Step 1: Check special patterns first
        line_lower = line.lower()
        for pat, special_type in self._special_patterns:
            m = pat.match(line_lower)
            if m:
                result["parsed"] = True
                result["special"] = special_type
                if special_type == 'grants_skill':
                    # Preserve original case for skill name
                    orig_m = re.match(r'^grants?\s+skill:\s*(.+)', line, re.IGNORECASE)
                    result["special_data"] = {"skill_name": orig_m.group(1).strip() if orig_m else m.group(1).strip()}
                    result["type"] = "FLAG"
                elif special_type == 'conversion':
                    result["special_data"] = {"percent": float(m.group(1)), "from": m.group(2), "to": m.group(3)}
                    result["type"] = "CONVERSION"
                    result["value"] = float(m.group(1))
                elif special_type == 'damage_shift':
                    result["special_data"] = {"percent": float(m.group(1)), "from": m.group(2), "to": m.group(3)}
                    result["type"] = "DAMAGE_SHIFT"
                    result["value"] = float(m.group(1))
                elif special_type == 'extra_damage':
                    result["special_data"] = {"percent": float(m.group(1)), "source": m.group(2), "as": m.group(3)}
                    result["type"] = "EXTRA_DAMAGE"
                    result["value"] = float(m.group(1))
                elif special_type == 'trigger':
                    result["special_data"] = {"skill": m.group(1), "condition": m.group(2)}
                    result["type"] = "FLAG"
                elif special_type in ('contributes_to', 'also_applies', 'cannot', 'can',
                                      'negation', 'splash', 'additional_proj'):
                    result["type"] = "FLAG"
                    result["special_data"] = {"text": line}
                return result

        # Step 2: Extract conditions (per/while/when/if...) from the end
        remaining = line_lower
        conditions = []
        for pat, cond_type in self._condition_patterns:
            m = pat.search(remaining)
            if m:
                conditions.append({"type": cond_type, "text": m.group(1).strip() if m.lastindex else m.group(0).strip()})
                # Remove the condition from remaining text for form matching
                remaining = remaining[:m.start()].strip()
                break  # Only extract the outermost condition

        result["conditions"] = conditions

        # Step 3: Try form matching
        form = None
        value = None
        remainder_after_form = remaining

        for pat, form_type in self._form_patterns:
            m = pat.search(remaining)
            if m:
                form = form_type
                if m.lastindex and m.lastindex >= 1:
                    try:
                        value = float(m.group(1))
                    except (ValueError, IndexError):
                        value = None
                # The remainder is everything after the form match
                remainder_after_form = remaining[m.end():].strip()
                break

        if form is None:
            # No form matched — treat as qualitative FLAG
            result["type"] = "FLAG"
            result["parsed"] = True  # Still "parsed" — just qualitative
            result["special"] = "qualitative"
            result["special_data"] = {"text": line}
            return result

        # Step 4: Map form to final type
        final_type = form
        if form == 'RED':
            final_type = 'INC'
            if value is not None:
                value = -value
        elif form == 'LESS':
            final_type = 'MORE'
            if value is not None:
                value = -value
        elif form == 'LOSE':
            final_type = 'BASE'
            if value is not None:
                value = -value
        elif form in ('GAIN', 'GRANTS', 'GRANTS_GLOBAL'):
            final_type = 'BASE'
        elif form == 'CHANCE':
            final_type = 'CHANCE'
        elif form in ('DOUBLED',):
            final_type = 'FLAG'
            value = None

        result["form"] = form
        result["type"] = final_type
        result["value"] = value

        # Step 5: Match mod name from remainder
        name = self._match_mod_name(remainder_after_form)
        if name:
            result["name"] = name
            result["parsed"] = True
        else:
            # Try matching from the full line (some patterns need full context)
            name = self._match_mod_name(remaining)
            if name:
                result["name"] = name
                result["parsed"] = True
            else:
                # We have a form+value but no recognized name
                # Still mark as parsed if we have value — the name is just unrecognized
                result["parsed"] = (value is not None)
                result["name"] = self._extract_raw_name(remainder_after_form)

        return result

    def _match_mod_name(self, text: str) -> Optional[str]:
        """Try to match a mod name from text using the MOD_NAME_MAP.
        
        When multiple keys match, prefer the one occurring earliest in the text.
        Among equal positions, prefer the longest match.
        """
        text = text.strip().lower()
        # Remove common prefixes/suffixes that are not part of the mod name
        text = re.sub(r'^(of |to |the |your |for |with )', '', text).strip()

        best_match = None
        best_pos = len(text) + 1
        best_len = 0

        for key in self._mod_names_sorted:
            pos = text.find(key)
            if pos >= 0:
                if pos < best_pos or (pos == best_pos and len(key) > best_len):
                    best_match = MOD_NAME_MAP[key]
                    best_pos = pos
                    best_len = len(key)

        return best_match

    def _extract_raw_name(self, text: str) -> str:
        """Extract a raw name from text when no MOD_NAME_MAP match is found."""
        text = text.strip()
        # Remove common filler words
        text = re.sub(r'^(of |to |the |your |for |with |in )', '', text).strip()
        # Clean up
        text = re.sub(r'\s+', ' ', text).strip()
        return text if text else None

    def parse_node_stats(self, stats: list) -> list:
        """
        解析一个天赋节点的全部 stats。

        Args:
            stats: stats_node 字段的列表（如 ["50% more Critical Damage Bonus", "Grants Skill: X"]）

        Returns:
            list of parsed mod dicts
        """
        results = []
        for stat_line in stats:
            parsed = self.parse_line(stat_line)
            results.append(parsed)
        return results

    def categorize_mod(self, mod: dict) -> str:
        """
        将解析后的 mod 分类到维度。

        Returns:
            dimension: 'damage' / 'speed' / 'crit' / 'defense' / 'utility' / 'resource' / 'qualitative'
        """
        if not mod.get("parsed"):
            return "qualitative"

        name = mod.get("name", "") or ""
        mod_type = mod.get("type", "")
        special = mod.get("special", "")

        # Grants Skill is always qualitative
        if special == "grants_skill":
            return "qualitative"

        # Extra damage / conversion
        if mod_type in ("EXTRA_DAMAGE", "CONVERSION", "DAMAGE_SHIFT"):
            return "damage"

        # Damage names
        damage_names = {"Damage", "PhysicalDamage", "FireDamage", "ColdDamage", "LightningDamage",
                        "ChaosDamage", "ElementalDamage", "NonChaosDamage", "SpellDamage",
                        "Damage_Attack", "Damage_Melee", "Damage_Projectile", "Damage_Area",
                        "Damage_DoT", "Damage_Minion", "DotMultiplier", "PhysicalDotMultiplier",
                        "FireDotMultiplier", "ColdDotMultiplier", "ChaosDotMultiplier",
                        "FireDamage_Dot", "DoubleDamageChance"}
        if name in damage_names:
            return "damage"

        # Crit
        crit_names = {"CritChance", "CritMultiplier", "CritChance_Attack", "CritMultiplier_Spell"}
        if name in crit_names:
            return "crit"

        # Speed
        speed_names = {"Speed", "Speed_Attack", "Speed_Cast", "MovementSpeed", "ActionSpeed",
                       "Speed_Minion", "CooldownRecovery", "TotemPlacementSpeed",
                       "TrapThrowingSpeed", "MineLayingSpeed"}
        if name in speed_names:
            return "speed"

        # Defense
        defense_names = {"Life", "Mana", "EnergyShield", "Armour", "Evasion", "Ward",
                         "ArmourAndEvasion", "ArmourAndEnergyShield", "EvasionAndEnergyShield",
                         "Defences", "LifeRegen", "ManaRegen", "LifeManaRegen",
                         "BlockChance", "SpellBlockChance", "AttackDodgeChance",
                         "SpellSuppressionChance", "EvadeChance", "AvoidStun",
                         "AvoidElementalAilments", "PhysicalDamageReduction",
                         "DamageTaken", "DamageTakenWhenHit", "PhysicalDamageTaken",
                         "FireDamageTaken", "ColdDamageTaken", "LightningDamageTaken",
                         "ChaosDamageTaken", "ElementalDamageTaken", "DamageTakenOverTime",
                         "DamageTakenFromManaBeforeLife",
                         "LifeOnKill", "ManaOnKill", "LifeRecoveryRate", "ManaRecoveryRate",
                         "EnergyShieldRecoveryRate", "LifeRecoup", "AilmentThreshold",
                         "StunThreshold"}
        if name in defense_names:
            return "defense"

        # Resource (mana cost, reservation, charges, spirit)
        resource_names = {"Spirit", "ManaCost", "Cost", "ReservationEfficiency",
                          "ManaReservationEfficiency", "LifeReservationEfficiency",
                          "SpiritReservationEfficiency", "PowerChargesMax", "FrenzyChargesMax",
                          "EnduranceChargesMax", "ChargeDuration", "MaximumRage"}
        if name in resource_names:
            return "resource"

        # Resistances go to defense
        resist_names = {"FireResist", "ColdResist", "LightningResist", "ChaosResist",
                        "ElementalResist", "AllResist", "FireResistMax", "ColdResistMax",
                        "LightningResistMax", "ChaosResistMax", "ElementalResistMax"}
        if name in resist_names:
            return "defense"

        # Penetration is damage
        if mod_type == "PEN":
            return "damage"

        # Penetration target names (when used as PEN form) — still damage
        pen_targets = {"FireResist", "ColdResist", "LightningResist", "ElementalResist", "ChaosResist"}
        if name in pen_targets and form == "PEN":
            return "damage"

        # Ailment-related — utility
        ailment_names = {"EnemyShockChance", "EnemyFreezeChance", "EnemyIgniteChance",
                         "EnemyShockMagnitude", "EnemyChillMagnitude", "IgniteMagnitude",
                         "AilmentMagnitude", "NonDamageAilmentEffect",
                         "EnemyChillDuration", "EnemyFreezeDuration", "EnemyShockDuration",
                         "EnemyIgniteDuration", "EnemyAilmentDuration",
                         "EnemyFreezeBuildup", "EnemyHeavyStunBuildup", "EnemyElectrocuteBuildup"}
        if name in ailment_names:
            return "utility"

        # Aura/Buff effects — utility
        buff_names = {"AuraEffect", "AuraEffectOnSelf", "CurseEffect", "BuffEffect",
                      "ArcaneSurgeEffect", "TailwindEffectOnSelf", "ElusiveEffect",
                      "PresenceArea"}
        if name in buff_names:
            return "utility"

        # Area / Duration / Projectile — utility
        aoe_names = {"AreaOfEffect", "Duration", "ProjectileSpeed", "ProjectileCount",
                     "WeaponRange", "MeleeWeaponRange"}
        if name in aoe_names:
            return "utility"

        # FLAG type is qualitative
        if mod_type == "FLAG":
            return "qualitative"

        return "utility"


def parse_all_passives(db_path: str, verbose: bool = False) -> dict:
    """
    解析 entities.db 中所有 passive_node 的 stats_node，写入 parsed_mods 字段。

    Returns:
        stats dict with counts
    """
    parser = PassiveModParser()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Ensure parsed_mods column exists
    try:
        cursor.execute("ALTER TABLE entities ADD COLUMN parsed_mods TEXT")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # Column already exists

    # Read all passive nodes
    cursor.execute(
        "SELECT id, name, stats_node, ascendancy_name, is_notable, is_keystone "
        "FROM entities WHERE type = 'passive_node'"
    )
    rows = cursor.fetchall()

    stats = {
        "total": len(rows),
        "parsed_count": 0,
        "partial_count": 0,
        "unparsed_count": 0,
        "total_stats": 0,
        "parsed_stats": 0,
        "unparsed_stats": 0,
        "by_dimension": {},
    }

    for row in rows:
        node_id, name, stats_node_raw, asc_name, is_notable, is_keystone = row

        if not stats_node_raw or stats_node_raw == "[]":
            stats["unparsed_count"] += 1
            continue

        try:
            stat_lines = json.loads(stats_node_raw)
        except (json.JSONDecodeError, TypeError):
            stats["unparsed_count"] += 1
            continue

        if not stat_lines:
            stats["unparsed_count"] += 1
            continue

        mods = parser.parse_node_stats(stat_lines)
        stats["total_stats"] += len(mods)

        # Categorize each mod
        for mod in mods:
            dim = parser.categorize_mod(mod)
            mod["dimension"] = dim
            stats["by_dimension"][dim] = stats["by_dimension"].get(dim, 0) + 1
            if mod["parsed"]:
                stats["parsed_stats"] += 1
            else:
                stats["unparsed_stats"] += 1

        # Check node-level parse status
        all_parsed = all(m["parsed"] for m in mods)
        any_parsed = any(m["parsed"] for m in mods)

        if all_parsed:
            stats["parsed_count"] += 1
        elif any_parsed:
            stats["partial_count"] += 1
        else:
            stats["unparsed_count"] += 1

        # Serialize: strip "original" to save space (it's already in stats_node)
        slim_mods = []
        for mod in mods:
            slim = {}
            if mod.get("type"):
                slim["type"] = mod["type"]
            if mod.get("value") is not None:
                slim["value"] = mod["value"]
            if mod.get("name"):
                slim["name"] = mod["name"]
            if mod.get("dimension"):
                slim["dimension"] = mod["dimension"]
            if mod.get("conditions"):
                slim["conditions"] = mod["conditions"]
            if mod.get("special"):
                slim["special"] = mod["special"]
            if mod.get("special_data"):
                slim["special_data"] = mod["special_data"]
            if not mod.get("parsed"):
                slim["parsed"] = False
                slim["original"] = mod["original"]
            slim_mods.append(slim)

        cursor.execute(
            "UPDATE entities SET parsed_mods = ? WHERE id = ?",
            (json.dumps(slim_mods, ensure_ascii=False), node_id)
        )

        if verbose and (is_notable or is_keystone) and asc_name:
            status = "✅" if all_parsed else ("⚠️" if any_parsed else "❌")
            print(f"  {status} [{asc_name}] {name}: {len(mods)} mods")
            for mod in mods:
                if mod["parsed"]:
                    val_str = f" {mod['value']}" if mod['value'] is not None else ""
                    print(f"      {mod['type']}{val_str} → {mod['name']} [{mod['dimension']}]")
                else:
                    print(f"      ❌ {mod['original']}")

    conn.commit()
    conn.close()
    return stats


def main():
    """CLI entry point."""
    import argparse
    ap = argparse.ArgumentParser(description="解析天赋/升华 stat 描述为结构化 modifier")
    ap.add_argument("--db", default=None, help="entities.db 路径")
    ap.add_argument("--verbose", "-v", action="store_true", help="显示详细解析过程")
    ap.add_argument("--test", action="store_true", help="测试模式：解析几条示例文本")
    args = ap.parse_args()

    if args.test:
        parser = PassiveModParser()
        test_lines = [
            "50% more Critical Damage Bonus",
            "25% less Magnitude of Shock you inflict",
            "20% increased Effect of Arcane Surge on you per ten percent missing Mana",
            "Grants Skill: Elemental Storm",
            "All Damage from Hits Contributes to Chill Magnitude",
            "+2 to Limit for Elemental Skills",
            "Gain 10% of Damage as Extra Cold Damage",
            "Enemies in your Presence are Slowed by 20%",
            "Skills have 33% chance to not consume a Cooldown when used",
            "20% of Cold Damage taken as Fire Damage",
            "Trigger Elemental Storm on Critical Hit with Spells",
            "Damage Penetrates 15% Cold Resistance",
            "12% increased Mana Regeneration Rate",
            "35% less Evasion Rating",
            "Meta Skills gain 35% more Energy",
            "+1 to Spirit for every 8 Item Energy Shield on Equipped Body Armour",
            "Critical Hits ignore non-negative Enemy Monster Elemental Resistances",
            "Strikes deal Splash Damage",
            "Skills fire an additional Projectile",
        ]
        print("=== 测试模式 ===\n")
        for line in test_lines:
            result = parser.parse_line(line)
            dim = parser.categorize_mod(result)
            status = "✅" if result["parsed"] else "❌"
            val = f" {result['value']}" if result.get('value') is not None else ""
            name = result.get('name') or result.get('special') or '?'
            cond = f" | cond: {result['conditions']}" if result['conditions'] else ""
            print(f"  {status} \"{line}\"")
            print(f"      → type={result['type']}, value={result.get('value')}, name={name}, dim={dim}{cond}")
            if result.get('special_data'):
                print(f"      → special_data={result['special_data']}")
            print()
        return

    # Default db path
    if not args.db:
        script_dir = Path(__file__).parent.parent
        args.db = str(script_dir / "knowledge_base" / "entities.db")

    print(f"解析 {args.db} 中的天赋/升华 stats...")
    stats = parse_all_passives(args.db, verbose=args.verbose)

    print(f"\n=== 解析统计 ===")
    print(f"天赋节点总数: {stats['total']}")
    print(f"  完全解析: {stats['parsed_count']}")
    print(f"  部分解析: {stats['partial_count']}")
    print(f"  未解析:   {stats['unparsed_count']}")
    print(f"\nStat 行总数: {stats['total_stats']}")
    print(f"  已解析: {stats['parsed_stats']} ({stats['parsed_stats']*100//max(stats['total_stats'],1)}%)")
    print(f"  未解析: {stats['unparsed_stats']}")
    print(f"\n按维度分布:")
    for dim, count in sorted(stats["by_dimension"].items(), key=lambda x: -x[1]):
        print(f"  {dim}: {count}")


if __name__ == "__main__":
    main()
