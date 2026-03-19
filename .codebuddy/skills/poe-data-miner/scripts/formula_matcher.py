#!/usr/bin/env python3
"""
公式匹配器 v2 — 3类公式索引查询引擎

查询路由:
  1. entity_id → 类型B (stat_mappings) + 类型C (gap_formulas)
  2. 关键词   → 类型A (universal_formulas)
  3. 混合     → 先entity查找个性化映射，再关键词匹配通用公式

取代旧版 Jaccard 匹配器。
"""

import sqlite3
import json
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
from dataclasses import dataclass, field


@dataclass
class FormulaResult:
    """查询结果"""
    id: str
    name: str
    formula_type: str       # "universal" / "stat_mapping" / "gap_formula"
    formula_text: str
    domain: str
    score: float            # 匹配分数 (0-1)
    details: Dict = field(default_factory=dict)


@dataclass
class FormulaQueryResult:
    """完整查询结果"""
    query: str
    entity_id: Optional[str]
    universal: List[FormulaResult]      # 类型A: 通用公式
    stat_mappings: List[FormulaResult]  # 类型B: 个性化映射
    gap_formulas: List[FormulaResult]   # 类型C: 缺口公式


class FormulaMatcher:
    """公式匹配器 v2"""

    # 关键词→领域映射（用于查询路由）
    DOMAIN_KEYWORDS = {
        'offence': [
            'dps', '伤害', 'damage', '攻击', 'attack', '法术', 'spell',
            '暴击', 'crit', '命中', 'hit', 'accuracy', 'dot', '持续伤害',
            '点燃', 'ignite', '中毒', 'poison', '流血', 'bleed',
            '转换', 'conversion', '速度', 'speed', '施法', 'cast',
            '冷却', 'cooldown', '持续时间', 'duration', '范围', 'area', 'aoe',
            '弩', 'crossbow', '战吼', 'warcry', '双持', 'dual wield',
        ],
        'defence': [
            '护甲', 'armour', 'armor', '闪避', 'evasion', 'evade',
            '能量护盾', 'energy shield', 'es', '抗性', 'resistance', '抗',
            '格挡', 'block', '压制', 'suppression', '减伤', 'reduction',
            '受击', 'taken', 'ehp', '有效生命', '坦度',
            '生命', 'life', '魔力', 'mana', 'hp', 'mp',
        ],
        'recovery': [
            '偷取', 'leech', '再生', 'regen', '回充', 'recharge',
            '恢复', 'recovery', '回复', '药剂', 'flask',
        ],
        'meta': [
            '能量', 'energy', '元技能', 'meta', '触发', 'trigger',
            '最大能量', 'max energy', '满能量',
        ],
        'general': [
            'inc', 'more', 'increased', '加成', '叠加', '乘法',
        ],
    }

    def __init__(self, formulas_db_path: str, entities_db_path: str = None):
        self.formulas_db_path = Path(formulas_db_path)
        self.entities_db_path = Path(entities_db_path) if entities_db_path else None

        # 预加载通用公式关键词索引
        self._keyword_index: Dict[str, List[str]] = {}  # keyword → [formula_id, ...]
        self._universal_formulas: Dict[str, Dict] = {}
        self._load_universal_index()

    def _load_universal_index(self):
        """加载通用公式的关键词索引"""
        if not self.formulas_db_path.exists():
            return

        conn = sqlite3.connect(str(self.formulas_db_path))
        cursor = conn.cursor()

        try:
            cursor.execute('SELECT id, name, name_en, domain, category, keywords, formula, parameters, notes, source_file, source_lines FROM universal_formulas')
        except sqlite3.OperationalError:
            conn.close()
            return

        for row in cursor.fetchall():
            fid = row[0]
            keywords = json.loads(row[5]) if row[5] else []
            self._universal_formulas[fid] = {
                'id': fid,
                'name': row[1],
                'name_en': row[2],
                'domain': row[3],
                'category': row[4],
                'keywords': keywords,
                'formula': row[6],
                'parameters': row[7],
                'notes': row[8],
                'source_file': row[9],
                'source_lines': row[10],
            }

            # 建立关键词→公式ID索引
            for kw in keywords:
                kw_lower = kw.lower()
                if kw_lower not in self._keyword_index:
                    self._keyword_index[kw_lower] = []
                self._keyword_index[kw_lower].append(fid)

        conn.close()

    def query(self, question: str, entity_id: str = None) -> FormulaQueryResult:
        """
        统一查询接口

        Args:
            question: 用户问题（如"Arc的DPS怎么算"、"护甲减伤公式"）
            entity_id: 可选的实体ID（直接指定）

        Returns:
            FormulaQueryResult 包含3类匹配结果
        """
        # Step 1: 解析问题
        parsed_entity_id, keywords = self._parse_question(question, entity_id)

        result = FormulaQueryResult(
            query=question,
            entity_id=parsed_entity_id,
            universal=[],
            stat_mappings=[],
            gap_formulas=[]
        )

        # Step 2: 关键词→通用公式 (类型A)
        if keywords:
            result.universal = self._match_universal(keywords)

        # Step 3: entity_id→个性化映射 (类型B) + 缺口公式 (类型C)
        if parsed_entity_id:
            result.stat_mappings = self._query_stat_mappings(parsed_entity_id)
            result.gap_formulas = self._query_gap_formulas(parsed_entity_id)

        return result

    def _parse_question(self, question: str, entity_id: str = None) -> Tuple[Optional[str], List[str]]:
        """
        解析问题，提取entity_id和关键词

        Returns:
            (entity_id_or_None, keywords_list)
        """
        # 如果已提供entity_id则直接用
        if entity_id:
            keywords = self._extract_keywords(question)
            return entity_id, keywords

        # 尝试从问题中识别技能名
        detected_entity_id = self._detect_entity_name(question)

        # 提取关键词
        keywords = self._extract_keywords(question)

        return detected_entity_id, keywords

    def _detect_entity_name(self, question: str) -> Optional[str]:
        """从问题中检测技能名并映射到entity_id"""
        if not self.entities_db_path or not self.entities_db_path.exists():
            return None

        # 提取可能的技能名（英文单词或CamelCase）
        # 常见模式: "Arc的DPS", "Cast on Critical能量获取"
        candidates = []

        # 英文单词/短语
        en_matches = re.findall(r'[A-Z][a-z]+(?:\s+(?:on|of|the|in|and|or|with)\s+[A-Z]?[a-z]+)*', question)
        candidates.extend(en_matches)

        # CamelCase
        camel_matches = re.findall(r'[A-Z][a-zA-Z]+', question)
        candidates.extend(camel_matches)

        if not candidates:
            return None

        conn = sqlite3.connect(str(self.entities_db_path))
        cursor = conn.cursor()

        for candidate in candidates:
            # 精确匹配
            cursor.execute(
                "SELECT id FROM entities WHERE name = ? OR id = ? LIMIT 1",
                (candidate, candidate)
            )
            row = cursor.fetchone()
            if row:
                conn.close()
                return row[0]

            # 模糊匹配
            pattern = f'%{candidate}%'
            cursor.execute(
                "SELECT id FROM entities WHERE (name LIKE ? OR id LIKE ?) AND type = 'skill_definition' LIMIT 1",
                (pattern, pattern)
            )
            row = cursor.fetchone()
            if row:
                conn.close()
                return row[0]

        conn.close()
        return None

    def _extract_keywords(self, question: str) -> List[str]:
        """从问题中提取关键词"""
        q_lower = question.lower()

        keywords = []

        # 匹配已知关键词
        for domain, domain_kws in self.DOMAIN_KEYWORDS.items():
            for kw in domain_kws:
                if kw in q_lower:
                    keywords.append(kw)

        # 提取英文单词作为额外关键词
        words = re.findall(r'[a-z]+', q_lower)
        for w in words:
            if len(w) >= 3 and w not in {'the', 'and', 'for', 'how', 'what', 'does'}:
                keywords.append(w)

        return list(set(keywords))

    def _match_universal(self, keywords: List[str]) -> List[FormulaResult]:
        """关键词匹配通用公式"""
        scores: Dict[str, float] = {}
        matched_keywords: Dict[str, List[str]] = {}

        for kw in keywords:
            kw_lower = kw.lower()

            # 精确关键词匹配
            if kw_lower in self._keyword_index:
                for fid in self._keyword_index[kw_lower]:
                    scores[fid] = scores.get(fid, 0) + 1.0
                    if fid not in matched_keywords:
                        matched_keywords[fid] = []
                    matched_keywords[fid].append(kw)

            # 部分匹配（关键词包含在公式关键词中，或反之）
            for idx_kw, fids in self._keyword_index.items():
                if kw_lower != idx_kw and (kw_lower in idx_kw or idx_kw in kw_lower):
                    for fid in fids:
                        scores[fid] = scores.get(fid, 0) + 0.5
                        if fid not in matched_keywords:
                            matched_keywords[fid] = []
                        matched_keywords[fid].append(f"{kw}(partial)")

        if not scores:
            return []

        # 归一化分数
        max_score = max(scores.values())
        results = []

        for fid, score in sorted(scores.items(), key=lambda x: -x[1]):
            if fid not in self._universal_formulas:
                continue

            uf = self._universal_formulas[fid]
            norm_score = score / max(max_score, 1)

            results.append(FormulaResult(
                id=fid,
                name=uf['name'],
                formula_type='universal',
                formula_text=uf['formula'],
                domain=uf['domain'],
                score=norm_score,
                details={
                    'name_en': uf.get('name_en'),
                    'category': uf.get('category'),
                    'parameters': uf.get('parameters'),
                    'notes': uf.get('notes'),
                    'source_file': uf.get('source_file'),
                    'source_lines': uf.get('source_lines'),
                    'matched_keywords': matched_keywords.get(fid, []),
                }
            ))

        return results

    def _query_stat_mappings(self, entity_id: str) -> List[FormulaResult]:
        """查询实体的stat映射（类型B）"""
        conn = sqlite3.connect(str(self.formulas_db_path))
        cursor = conn.cursor()

        try:
            # 查询该技能的内联映射
            cursor.execute('''
                SELECT stat_name, modifier_code, scope, skill_id, domain, source_file, source_line,
                       is_flag, is_skill_data, has_div, div_value
                FROM stat_mappings
                WHERE skill_id = ? OR skill_id LIKE ?
            ''', (entity_id, f'%{entity_id}%'))

            results = []
            for row in cursor.fetchall():
                stat_name, mod_code, scope, skill_id, domain, src_file, src_line, is_flag, is_skill, has_div, div_val = row

                results.append(FormulaResult(
                    id=f"sm_{stat_name}",
                    name=stat_name,
                    formula_type='stat_mapping',
                    formula_text=mod_code or '',
                    domain=domain or 'unknown',
                    score=1.0,  # 直接匹配
                    details={
                        'scope': scope,
                        'skill_id': skill_id,
                        'source_file': src_file,
                        'source_line': src_line,
                        'is_flag': is_flag,
                        'is_skill_data': is_skill,
                        'has_div': has_div,
                        'div_value': div_val,
                    }
                ))

            conn.close()
            return results

        except sqlite3.OperationalError:
            conn.close()
            return []

    def _query_gap_formulas(self, entity_id: str) -> List[FormulaResult]:
        """查询实体的缺口公式（类型C）"""
        conn = sqlite3.connect(str(self.formulas_db_path))
        cursor = conn.cursor()

        try:
            cursor.execute('''
                SELECT id, entity_name, formula_type, formula_text, parameters,
                       stat_sources, description, confidence, pob_status, notes
                FROM gap_formulas
                WHERE entity_id = ? OR entity_id LIKE ?
            ''', (entity_id, f'%{entity_id}%'))

            results = []
            for row in cursor.fetchall():
                gf_id, name, ftype, formula, params, sources, desc, conf, status, notes = row

                results.append(FormulaResult(
                    id=gf_id,
                    name=f"{name} - {ftype}",
                    formula_type='gap_formula',
                    formula_text=formula,
                    domain='meta',
                    score=conf or 0.8,
                    details={
                        'formula_sub_type': ftype,
                        'parameters': params,
                        'stat_sources': sources,
                        'description': desc,
                        'confidence': conf,
                        'pob_status': status,
                        'notes': notes,
                    }
                ))

            conn.close()
            return results

        except sqlite3.OperationalError:
            conn.close()
            return []

    def query_by_stat(self, stat_name: str) -> List[FormulaResult]:
        """按stat名称查询映射"""
        conn = sqlite3.connect(str(self.formulas_db_path))
        cursor = conn.cursor()

        results = []
        try:
            cursor.execute('''
                SELECT stat_name, modifier_code, scope, skill_id, domain, source_file, source_line
                FROM stat_mappings
                WHERE stat_name = ? OR stat_name LIKE ?
            ''', (stat_name, f'%{stat_name}%'))

            for row in cursor.fetchall():
                sn, mod_code, scope, skill_id, domain, src_file, src_line = row
                results.append(FormulaResult(
                    id=f"sm_{sn}",
                    name=sn,
                    formula_type='stat_mapping',
                    formula_text=mod_code or '',
                    domain=domain or 'unknown',
                    score=1.0 if sn == stat_name else 0.8,
                    details={
                        'scope': scope,
                        'skill_id': skill_id,
                        'source_file': src_file,
                        'source_line': src_line,
                    }
                ))
        except sqlite3.OperationalError:
            pass

        conn.close()
        return results


def main():
    """命令行入口"""
    import argparse
    import sys

    SCRIPTS_DIR = Path(__file__).parent
    sys.path.insert(0, str(SCRIPTS_DIR))
    from pob_paths import get_knowledge_base_path

    parser = argparse.ArgumentParser(description='公式匹配器 v2')
    parser.add_argument('--formulas-db', help='公式库路径')
    parser.add_argument('--entities-db', help='实体库路径')
    parser.add_argument('--query', '-q', help='问题查询')
    parser.add_argument('--entity', '-e', help='实体ID查询')
    parser.add_argument('--stat', '-s', help='stat名称查询')

    args = parser.parse_args()

    kb_path = get_knowledge_base_path()
    formulas_db = args.formulas_db or str(kb_path / 'formulas.db')
    entities_db = args.entities_db or str(kb_path / 'entities.db')

    matcher = FormulaMatcher(formulas_db, entities_db)

    if args.query:
        result = matcher.query(args.query, args.entity)

        print(f"\n查询: {result.query}")
        if result.entity_id:
            print(f"识别实体: {result.entity_id}")

        if result.universal:
            print(f"\n--- 通用公式 ({len(result.universal)}个) ---")
            for r in result.universal[:5]:
                print(f"  [{r.score:.2f}] {r.name}")
                print(f"    公式: {r.formula_text}")
                if r.details.get('notes'):
                    notes_short = r.details['notes'][:100]
                    print(f"    备注: {notes_short}")

        if result.stat_mappings:
            print(f"\n--- Stat映射 ({len(result.stat_mappings)}个) ---")
            for r in result.stat_mappings[:10]:
                print(f"  [{r.domain}] {r.name}")
                print(f"    → {r.formula_text[:100]}")

        if result.gap_formulas:
            print(f"\n--- 缺口公式 ({len(result.gap_formulas)}个) ---")
            for r in result.gap_formulas:
                print(f"  ⚠️ [{r.details.get('formula_sub_type')}] {r.formula_text}")
                print(f"    置信度: {r.details.get('confidence', 0):.2f}")
                print(f"    状态: {r.details.get('pob_status')}")

    elif args.stat:
        results = matcher.query_by_stat(args.stat)
        print(f"\nstat: {args.stat}")
        print(f"找到 {len(results)} 条映射:")
        for r in results[:10]:
            scope_tag = f"[{r.details.get('scope', '?')}]"
            skill_tag = f" ({r.details.get('skill_id', 'global')})" if r.details.get('skill_id') else ""
            print(f"  {scope_tag}{skill_tag} {r.formula_text[:100]}")

    elif args.entity:
        result = matcher.query("", args.entity)
        print(f"\n实体: {args.entity}")

        if result.stat_mappings:
            print(f"\n--- Stat映射 ({len(result.stat_mappings)}个) ---")
            for r in result.stat_mappings:
                print(f"  [{r.domain}] {r.name}")

        if result.gap_formulas:
            print(f"\n--- 缺口公式 ({len(result.gap_formulas)}个) ---")
            for r in result.gap_formulas:
                print(f"  ⚠️ {r.details.get('formula_sub_type')}: {r.formula_text}")

    else:
        print("请指定查询参数: --query, --entity, 或 --stat")


if __name__ == '__main__':
    main()
