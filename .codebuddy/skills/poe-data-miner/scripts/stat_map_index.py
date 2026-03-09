#!/usr/bin/env python3
"""
Stat映射索引提取器

从两个来源提取stat→modifier映射:
1. SkillStatMap.lua — 全局映射(~884条)
2. 各技能文件内联statMap — 技能专属映射(253+块)

输出到 formulas.db 的 stat_mappings 表
"""

import re
import sqlite3
import json
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, asdict


@dataclass
class StatMapping:
    """单条stat→modifier映射"""
    stat_name: str           # 官方stat名称
    modifier_code: str       # POB modifier代码（原始Lua文本）
    scope: str               # "global" 或 "inline"
    skill_id: Optional[str]  # 仅inline有：所属技能ID
    source_file: str         # 来源Lua文件路径
    source_line: int         # 来源行号
    domain: str              # 领域标签: offence/defence/recovery/utility/display
    has_div: bool            # 是否有div除数
    div_value: Optional[float]  # div值
    is_flag: bool            # 是否是flag()类型
    is_skill_data: bool      # 是否是skill()类型（注入skillData）


class StatMapIndex:
    """Stat映射索引构建器"""

    # 领域分类关键词
    DOMAIN_PATTERNS = {
        'offence': [
            'damage', 'attack', 'spell', 'cast', 'crit', 'hit', 'projectile',
            'chain', 'pierce', 'fork', 'area_of_effect', 'aoe', 'weapon',
            'bleed', 'poison', 'ignite', 'shock', 'freeze', 'chill',
            'penetrat', 'exposure', 'impale', 'brand', 'totem', 'mine', 'trap',
            'warcry', 'minion_damage', 'dot_', 'burning'
        ],
        'defence': [
            'armour', 'evasion', 'energy_shield', 'resist', 'block',
            'dodge', 'suppress', 'ward', 'defences', 'deflect',
            'damage_taken', 'phys_reduction', 'damage_reduction',
            'fortif', 'endurance'
        ],
        'recovery': [
            'leech', 'regen', 'life_on', 'mana_on', 'recharge',
            'recovery', 'flask', 'heal', 'recoup', 'overleech'
        ],
        'utility': [
            'speed', 'duration', 'cooldown', 'reservation', 'spirit',
            'radius', 'range', 'cost', 'charge', 'aura', 'curse',
            'buff', 'debuff', 'stun', 'knockback', 'blind', 'taunt',
            'summon', 'minion_life', 'gem_level', 'quality'
        ],
        'display': [
            'display', 'quality_display'
        ]
    }

    def __init__(self, pob_path: str, db_path: str):
        self.pob_path = Path(pob_path)
        self.db_path = Path(db_path)
        self.mappings: List[StatMapping] = []

    def extract_all(self) -> List[StatMapping]:
        """提取所有stat映射"""
        self.mappings = []

        # Phase 1: 全局映射
        print("  提取全局映射 (SkillStatMap.lua)...")
        global_count = self._extract_global_statmap()
        print(f"    全局映射: {global_count} 条")

        # Phase 2: 内联映射
        print("  提取内联映射 (Skills/*.lua)...")
        inline_count = self._extract_inline_statmaps()
        print(f"    内联映射: {inline_count} 条")

        print(f"  总计: {len(self.mappings)} 条映射")
        return self.mappings

    def _extract_global_statmap(self) -> int:
        """从SkillStatMap.lua提取全局映射"""
        statmap_file = self.pob_path / 'Data' / 'SkillStatMap.lua'
        if not statmap_file.exists():
            print(f"    [WARN] 文件不存在: {statmap_file}")
            return 0

        content = statmap_file.read_text(encoding='utf-8', errors='replace')
        lines = content.split('\n')
        rel_path = str(statmap_file.relative_to(self.pob_path))

        count = 0
        i = 0
        while i < len(lines):
            line = lines[i]

            # 匹配 ["stat_name"] = { 模式
            match = re.match(r'^\s*\["([^"]+)"\]\s*=\s*\{', line)
            if match:
                stat_name = match.group(1)
                start_line = i + 1  # 1-indexed

                # 收集完整的映射块（直到匹配的 },）
                block_lines = [line]
                brace_depth = line.count('{') - line.count('}')
                j = i + 1
                while j < len(lines) and brace_depth > 0:
                    block_lines.append(lines[j])
                    brace_depth += lines[j].count('{') - lines[j].count('}')
                    j += 1

                block_text = '\n'.join(block_lines)

                # 解析映射内容
                mapping = self._parse_mapping_block(
                    stat_name=stat_name,
                    block_text=block_text,
                    scope='global',
                    skill_id=None,
                    source_file=rel_path,
                    source_line=start_line
                )
                if mapping:
                    self.mappings.append(mapping)
                    count += 1

                i = j
            else:
                i += 1

        return count

    def _extract_inline_statmaps(self) -> int:
        """从技能文件中提取内联statMap"""
        skills_dir = self.pob_path / 'Data' / 'Skills'
        if not skills_dir.exists():
            print(f"    [WARN] 目录不存在: {skills_dir}")
            return 0

        total_count = 0

        for lua_file in sorted(skills_dir.glob('*.lua')):
            file_count = self._extract_from_skill_file(lua_file)
            if file_count > 0:
                print(f"    {lua_file.name}: {file_count} 条映射")
            total_count += file_count

        return total_count

    def _extract_from_skill_file(self, lua_file: Path) -> int:
        """从单个技能文件提取内联statMap"""
        content = lua_file.read_text(encoding='utf-8', errors='replace')
        lines = content.split('\n')
        rel_path = str(lua_file.relative_to(self.pob_path))

        count = 0
        current_skill_id = None

        for i, line in enumerate(lines):
            # 追踪当前技能ID（name字段）
            name_match = re.match(r'\s*name\s*=\s*"([^"]+)"', line)
            if name_match:
                current_skill_id = name_match.group(1)

            # 查找 statMap = { 开始
            if re.match(r'\s*statMap\s*=\s*\{', line):
                # 收集整个 statMap 块
                brace_depth = line.count('{') - line.count('}')
                block_start = i
                block_lines = [line]
                j = i + 1

                while j < len(lines) and brace_depth > 0:
                    block_lines.append(lines[j])
                    brace_depth += lines[j].count('{') - lines[j].count('}')
                    j += 1

                # 解析statMap块中的每个stat条目
                block_text = '\n'.join(block_lines)
                stat_entries = self._parse_statmap_block(block_text)

                for stat_name, modifier_text, rel_line in stat_entries:
                    mapping = self._parse_mapping_block(
                        stat_name=stat_name,
                        block_text=modifier_text,
                        scope='inline',
                        skill_id=current_skill_id,
                        source_file=rel_path,
                        source_line=block_start + rel_line + 1
                    )
                    if mapping:
                        self.mappings.append(mapping)
                        count += 1

        return count

    def _parse_statmap_block(self, block_text: str) -> List[Tuple[str, str, int]]:
        """解析statMap块，提取所有stat条目
        
        Returns:
            [(stat_name, modifier_block_text, relative_line), ...]
        """
        entries = []
        lines = block_text.split('\n')

        i = 0
        while i < len(lines):
            match = re.match(r'\s*\["([^"]+)"\]\s*=\s*\{', lines[i])
            if match:
                stat_name = match.group(1)
                entry_start = i

                # 收集条目块
                entry_lines = [lines[i]]
                brace_depth = lines[i].count('{') - lines[i].count('}')
                j = i + 1
                while j < len(lines) and brace_depth > 0:
                    entry_lines.append(lines[j])
                    brace_depth += lines[j].count('{') - lines[j].count('}')
                    j += 1

                entry_text = '\n'.join(entry_lines)
                entries.append((stat_name, entry_text, entry_start))
                i = j
            else:
                i += 1

        return entries

    def _parse_mapping_block(
        self,
        stat_name: str,
        block_text: str,
        scope: str,
        skill_id: Optional[str],
        source_file: str,
        source_line: int
    ) -> Optional[StatMapping]:
        """解析单条映射块"""

        # 提取modifier代码（去掉外层包装）
        modifier_code = block_text.strip()

        # 检查是否是Display Only
        if re.search(r'--\s*Display\s*(Only|only)', block_text):
            domain = 'display'
        else:
            domain = self._classify_domain(stat_name, block_text)

        # 检查div
        div_match = re.search(r'div\s*=\s*(\d+)', block_text)
        has_div = div_match is not None
        div_value = float(div_match.group(1)) if div_match else None

        # 检查类型
        is_flag = 'flag(' in block_text
        is_skill_data = 'skill(' in block_text

        return StatMapping(
            stat_name=stat_name,
            modifier_code=modifier_code,
            scope=scope,
            skill_id=skill_id,
            source_file=source_file,
            source_line=source_line,
            domain=domain,
            has_div=has_div,
            div_value=div_value,
            is_flag=is_flag,
            is_skill_data=is_skill_data
        )

    def _classify_domain(self, stat_name: str, block_text: str) -> str:
        """根据stat名称和modifier内容分类领域"""
        combined = (stat_name + ' ' + block_text).lower()

        # 优先匹配display
        for keyword in self.DOMAIN_PATTERNS['display']:
            if keyword in combined:
                return 'display'

        # 按优先级匹配其他领域
        scores = {}
        for domain, keywords in self.DOMAIN_PATTERNS.items():
            if domain == 'display':
                continue
            score = sum(1 for kw in keywords if kw in combined)
            if score > 0:
                scores[domain] = score

        if scores:
            return max(scores, key=scores.get)

        return 'utility'  # 默认

    def save_to_db(self):
        """保存映射到数据库"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        # 创建表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS stat_mappings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stat_name TEXT NOT NULL,
                modifier_code TEXT,
                scope TEXT NOT NULL,
                skill_id TEXT,
                source_file TEXT,
                source_line INTEGER,
                domain TEXT,
                has_div BOOLEAN,
                div_value REAL,
                is_flag BOOLEAN,
                is_skill_data BOOLEAN,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 创建索引
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_stat_mappings_stat_name ON stat_mappings(stat_name)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_stat_mappings_skill_id ON stat_mappings(skill_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_stat_mappings_scope ON stat_mappings(scope)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_stat_mappings_domain ON stat_mappings(domain)')

        # 清空旧数据
        cursor.execute('DELETE FROM stat_mappings')

        # 批量插入
        for m in self.mappings:
            cursor.execute('''
                INSERT INTO stat_mappings
                (stat_name, modifier_code, scope, skill_id, source_file, source_line,
                 domain, has_div, div_value, is_flag, is_skill_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                m.stat_name, m.modifier_code, m.scope, m.skill_id,
                m.source_file, m.source_line, m.domain,
                m.has_div, m.div_value, m.is_flag, m.is_skill_data
            ))

        conn.commit()
        conn.close()

    def get_stats(self) -> Dict:
        """获取统计信息"""
        total = len(self.mappings)
        global_count = sum(1 for m in self.mappings if m.scope == 'global')
        inline_count = sum(1 for m in self.mappings if m.scope == 'inline')

        # 按领域统计
        domain_counts = {}
        for m in self.mappings:
            domain_counts[m.domain] = domain_counts.get(m.domain, 0) + 1

        # 按技能统计内联映射
        skill_counts = {}
        for m in self.mappings:
            if m.skill_id:
                skill_counts[m.skill_id] = skill_counts.get(m.skill_id, 0) + 1

        # 特征统计
        flag_count = sum(1 for m in self.mappings if m.is_flag)
        skill_data_count = sum(1 for m in self.mappings if m.is_skill_data)

        return {
            'total': total,
            'global': global_count,
            'inline': inline_count,
            'by_domain': domain_counts,
            'skills_with_inline': len(skill_counts),
            'flag_mappings': flag_count,
            'skill_data_mappings': skill_data_count
        }

    def diagnose(self):
        """诊断输出"""
        stats = self.get_stats()

        print(f"\n--- Stat映射索引统计 ---")
        print(f"  总映射数: {stats['total']}")
        print(f"  全局映射: {stats['global']}")
        print(f"  内联映射: {stats['inline']}")
        print(f"  有内联映射的技能: {stats['skills_with_inline']}")
        print(f"  flag类型: {stats['flag_mappings']}")
        print(f"  skillData类型: {stats['skill_data_mappings']}")

        print(f"\n  按领域:")
        for domain, count in sorted(stats['by_domain'].items(), key=lambda x: -x[1]):
            print(f"    {domain}: {count}")


def main():
    """独立运行入口"""
    import argparse
    import sys

    SCRIPTS_DIR = Path(__file__).parent
    sys.path.insert(0, str(SCRIPTS_DIR))
    from pob_paths import get_pob_path, get_knowledge_base_path

    parser = argparse.ArgumentParser(description='Stat映射索引提取')
    parser.add_argument('--pob-path', help='POB数据目录路径')
    parser.add_argument('--db', help='输出数据库路径')
    parser.add_argument('--diagnose-only', action='store_true', help='仅诊断现有数据库')

    args = parser.parse_args()

    try:
        pob_path = Path(args.pob_path) if args.pob_path else get_pob_path()
    except FileNotFoundError as e:
        print(f"[ERROR] {e}")
        return

    kb_path = get_knowledge_base_path()
    db_path = args.db or str(kb_path / 'formulas.db')

    if args.diagnose_only:
        # 从数据库读取统计
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT COUNT(*) FROM stat_mappings')
            total = cursor.fetchone()[0]
            cursor.execute('SELECT scope, COUNT(*) FROM stat_mappings GROUP BY scope')
            scope_counts = dict(cursor.fetchall())
            cursor.execute('SELECT domain, COUNT(*) FROM stat_mappings GROUP BY domain')
            domain_counts = dict(cursor.fetchall())
            print(f"stat_mappings表: {total} 条")
            print(f"  按scope: {scope_counts}")
            print(f"  按domain: {domain_counts}")
        except sqlite3.OperationalError as e:
            print(f"[ERROR] 表不存在: {e}")
        conn.close()
        return

    print("=" * 60)
    print("Stat映射索引提取")
    print("=" * 60)

    indexer = StatMapIndex(str(pob_path), db_path)
    indexer.extract_all()
    indexer.save_to_db()
    indexer.diagnose()

    print(f"\n[OK] 已保存到 {db_path}")


if __name__ == '__main__':
    main()
