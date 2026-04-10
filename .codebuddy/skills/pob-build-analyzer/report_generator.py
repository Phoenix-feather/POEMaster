#!/usr/bin/env python3
"""HTML 报告生成器 — 将 analysis JSON 渲染为自包含交互式网页。

用法:
    python -m report_generator --build-id Monk_Invoker_Lv98_f18d7181 --skills spark comet
"""

import json
import sys
import argparse
import copy
import urllib.request
from pathlib import Path

CACHE_DIR = Path(__file__).parent / "cache" / "builds"

# CDN 库本地缓存目录
_LIBS_DIR = Path(__file__).parent / "cache" / "libs"

# CDN URL → 本地文件名映射
_CDN_LIBS = {
    "react": "https://unpkg.com/react@18/umd/react.production.min.js",
    "react-dom": "https://unpkg.com/react-dom@18/umd/react-dom.production.min.js",
    "prop-types": "https://unpkg.com/prop-types@15/prop-types.min.js",
    "recharts": "https://unpkg.com/recharts@2.15.0/umd/Recharts.js",
}


def _ensure_libs():
    """确保本地缓存了 CDN 库文件，缺失则下载。"""
    _LIBS_DIR.mkdir(parents=True, exist_ok=True)
    for name, url in _CDN_LIBS.items():
        local = _LIBS_DIR / f"{name}.min.js"
        if not local.exists():
            try:
                urllib.request.urlretrieve(url, str(local))
                print(f"Downloaded {name}")
            except Exception as e:
                print(f"Warning: Failed to download {name}: {e}")


def _inline_lib(name: str) -> str:
    """读取本地缓存的库文件内容。"""
    local = _LIBS_DIR / f"{name}.min.js"
    if local.exists():
        return local.read_text(encoding="utf-8")
    return f"// Failed to load {name}"


def _strip_sample_diff(data: dict) -> dict:
    """移除 sample_diff 字段以减小 HTML 体积。"""
    data = copy.deepcopy(data)
    for entry in data.get("sensitivity", []):
        entry.pop("sample_diff", None)
    return data


def _load_analysis(build_dir: Path, skill: str) -> dict | None:
    """加载 analysis JSON 并精简数据。"""
    path = build_dir / f"analysis_{skill}.json"
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return _strip_sample_diff(json.load(f))


def _load_meta(build_dir: Path) -> dict | None:
    """加载 meta.json。"""
    path = build_dir / "meta.json"
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _load_global(build_dir: Path) -> dict | None:
    """加载 global.json。"""
    path = build_dir / "global.json"
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def generate_html_report(build_id: str, skills: list[str] | None = None) -> str | None:
    """生成自包含 HTML 报告。

    同时支持新格式（ws1/skills/*.json）和旧格式（analysis_*.json）。

    Args:
        build_id: 构筑 ID
        skills: 技能名列表（小写，下划线分隔）。None = 尝试自动发现。

    Returns:
        HTML 字符串，或 None（如果 build 不存在）
    """
    build_dir = CACHE_DIR / build_id
    if not build_dir.exists():
        return None

    meta = _load_meta(build_dir)
    if meta is None:
        meta = {}

    global_data = _load_global(build_dir)

    # 加载 ws1 全局数据（供技能数据合并 + global_data 回退）
    ws1_global = None
    ws1_global_path = build_dir / "ws1" / "global.json"
    if ws1_global_path.exists():
        try:
            ws1_global = json.loads(ws1_global_path.read_text(encoding="utf-8"))
            if ws1_global and not global_data:
                global_data = ws1_global
        except (json.JSONDecodeError, OSError):
            pass

    # 自动发现已分析的技能（优先 ws1/skills/，回退到扁平格式）
    if skills is None:
        skills = []
        ws1_skills_dir = build_dir / "ws1" / "skills"
        if ws1_skills_dir.exists():
            for f in ws1_skills_dir.glob("*.json"):
                skills.append(f.stem)
        if not skills:
            for f in build_dir.glob("analysis_*.json"):
                skill_name = f.stem.replace("analysis_", "")
                skills.append(skill_name)

    # 加载数据（扁平 analysis_*.json 优先，ws1/skills/ 回退）
    skills_data = {}
    for skill in skills:
        data = _load_analysis(build_dir, skill)
        if data is None:
            ws1_path = build_dir / "ws1" / "skills" / f"{skill}.json"
            if ws1_path.exists():
                try:
                    data = json.loads(ws1_path.read_text(encoding="utf-8"))
                    # 合并全局字段（aura_spirit, jewel_diagnosis）
                    if data and ws1_global:
                        for gk in ("aura_spirit", "jewel_diagnosis"):
                            if gk not in data and gk in ws1_global:
                                data[gk] = ws1_global[gk]
                except (json.JSONDecodeError, OSError):
                    pass
        if data is not None:
            skills_data[skill] = data

    if not skills_data:
        return None

    # 加载套装对比数据（如果存在）
    comparison = None
    comp_path = build_dir / "comparison.json"
    if comp_path.exists():
        try:
            comparison = json.loads(comp_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

    # 检查是否有 ws2 数据
    ws2_skills_data = {}
    ws2_global_data = {}
    ws2_dir = build_dir / "ws2"
    ws2_skills_dir = ws2_dir / "skills"
    if ws2_skills_dir.exists():
        for f in ws2_skills_dir.glob("*.json"):
            try:
                ws2_skills_data[f.stem] = json.loads(
                    f.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
    ws2_global_path = ws2_dir / "global.json"
    if ws2_global_path.exists():
        try:
            ws2_global_data = json.loads(
                ws2_global_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

    # 注入 weapon_sets 到 meta
    if ws2_skills_data or comparison:
        meta["weapon_sets"] = [1, 2]
    else:
        meta["weapon_sets"] = [1]

    # 确保库文件已缓存
    _ensure_libs()

    # 嵌入数据到 HTML
    html = HTML_TEMPLATE.replace(
        "/*__BUILD_META__*/null", json.dumps(meta)
    ).replace(
        "/*__SKILLS_DATA__*/null", json.dumps(skills_data)
    ).replace(
        "/*__GLOBAL_DATA__*/null", json.dumps(global_data)
    ).replace(
        "/*__WS2_GLOBAL_DATA__*/null", json.dumps(ws2_global_data or {})
    ).replace(
        "/*__WS2_SKILLS_DATA__*/null", json.dumps(ws2_skills_data or {})
    ).replace(
        "/*__COMPARISON_DATA__*/null", json.dumps(comparison)
    )

    # 将 CDN 外链替换为内嵌脚本
    for name in ["react", "react-dom", "prop-types", "recharts"]:
        tag = f'<script src="https://unpkg.com/'
        idx = html.find(tag)
        if idx >= 0:
            end = html.find("</script>", idx) + len("</script>")
            inline = f"<script>\n{_inline_lib(name)}\n</script>"
            html = html[:idx] + inline + html[end:]

    # 自动验证：用 Node.js 检查 JS 语法
    _validate_html_js(html)

    return html


def _validate_html_js(html: str) -> None:
    """用 Node.js 检查内嵌 JS 的语法正确性，失败则抛出异常。"""
    import subprocess
    import re
    import shutil
    import tempfile
    import os
    blocks = re.findall(r'<script>([\s\S]*?)</script>', html)
    if not blocks:
        raise ValueError("HTML 中未找到任何 <script> 块")
    node = shutil.which("node")
    if not node:
        print("Warning: node not found, skipping JS validation")
        return
    # 验证 Block 5+（数据和 App 代码）
    check_blocks = blocks[4:] if len(blocks) > 4 else blocks
    for i, code in enumerate(check_blocks):
        fd, tmp = tempfile.mkstemp(suffix=".js")
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
                f.write("new Function(" + repr(code) + ");\n")
            result = subprocess.run(
                [node, tmp],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode != 0:
                raise ValueError(
                    f"JS 语法错误（Block {i+5}）:\n{result.stderr.strip()}"
                )
        finally:
            os.unlink(tmp)
    print(f"JS 验证通过 ({len(blocks)} blocks)")


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>POB Build Analysis</title>
<script src="https://unpkg.com/react@18/umd/react.production.min.js" crossorigin></script>
<script src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js" crossorigin></script>
<script src="https://unpkg.com/prop-types@15/prop-types.min.js"></script>
<script src="https://unpkg.com/recharts@2.15.0/umd/Recharts.js"></script>
<style>
:root {
  --bg-primary: #0f0f1a;
  --bg-secondary: #1a1a2e;
  --bg-tertiary: #252540;
  --bg-card: #1e1e36;
  --text-primary: #e8e8f0;
  --text-secondary: #a0a0b8;
  --text-muted: #6e6e88;
  --accent: #d4a843;
  --accent-dim: #b8922e;
  --accent-glow: rgba(212, 168, 67, 0.15);
  --red: #e05555;
  --green: #55c078;
  --blue: #5588dd;
  --purple: #9966cc;
  --orange: #dd8844;
  --cyan: #44bbcc;
  --pink: #cc5599;
  --border: #2e2e4a;
  --radius: 8px;
}
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
  font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
  background: var(--bg-primary);
  color: var(--text-primary);
  line-height: 1.6;
  padding: 20px 32px;
  min-height: 100vh;
}
.header {
  text-align: center;
  padding: 20px 0 16px;
  border-bottom: 1px solid var(--border);
  margin-bottom: 20px;
}
.header h1 { font-size: 24px; font-weight: 600; color: var(--accent); }
.header .subtitle { color: var(--text-secondary); font-size: 14px; margin-top: 4px; }
.tabs {
  display: flex;
  gap: 4px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}
.tab {
  padding: 8px 20px;
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: var(--radius) var(--radius) 0 0;
  color: var(--text-secondary);
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  transition: all 0.15s;
  user-select: none;
}
.tab:hover { background: var(--bg-tertiary); color: var(--text-primary); }
.tab.active {
  background: var(--bg-tertiary);
  color: var(--accent);
  border-bottom-color: var(--bg-tertiary);
  border-top: 2px solid var(--accent);
}
.kpi-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 12px;
  margin-bottom: 24px;
}
.kpi-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 14px 16px;
}
.kpi-card .label { font-size: 11px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px; }
.kpi-card .value { font-size: 22px; font-weight: 700; color: var(--accent); margin-top: 2px; }
.kpi-card .value.warn { color: var(--red); }
.chart-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 24px;
}
.chart-box {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 16px;
}
.chart-box.full-width { grid-column: 1 / -1; }
.chart-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 12px;
  display: flex;
  align-items: center;
  gap: 6px;
}
.chart-title .dot {
  width: 8px; height: 8px;
  border-radius: 50%;
  background: var(--accent);
}
.recharts-text { fill: var(--text-secondary) !important; font-size: 12px !important; }
.recharts-cartesian-axis-tick-value { fill: var(--text-muted) !important; font-size: 11px !important; }
details {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  margin-bottom: 12px;
}
details summary {
  padding: 12px 16px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-secondary);
  list-style: none;
  display: flex;
  align-items: center;
  gap: 8px;
}
details summary::before {
  content: '▸';
  font-size: 12px;
  transition: transform 0.15s;
}
details[open] summary::before { transform: rotate(90deg); }
details[open] summary { border-bottom: 1px solid var(--border); color: var(--accent); }
.detail-content { padding: 12px 16px; overflow-x: auto; }
table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
th {
  text-align: left;
  padding: 8px 12px;
  color: var(--text-muted);
  font-weight: 500;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  border-bottom: 1px solid var(--border);
}
td {
  padding: 6px 12px;
  border-bottom: 1px solid rgba(46,46,74,0.5);
  color: var(--text-primary);
}
tr:hover td { background: rgba(212,168,67,0.04); }
</style>
</head>
<body>
<div id="root"></div>
<script>
const BUILD_META = /*__BUILD_META__*/null;
const SKILLS_DATA = /*__SKILLS_DATA__*/null;
const GLOBAL_DATA = /*__GLOBAL_DATA__*/null;
const WS2_GLOBAL_DATA = /*__WS2_GLOBAL_DATA__*/null;
const WS2_SKILLS_DATA = /*__WS2_SKILLS_DATA__*/null;
const COMPARISON_DATA = /*__COMPARISON_DATA__*/null;
</script>
<script>
const h = React.createElement;
const { useState, useMemo } = React;
const {
  BarChart, Bar, ScatterChart, Scatter,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer
} = Recharts;

// ── Utilities ──
function fmt(n, decimals=1) {
  if (n == null || isNaN(n)) return '—';
  const abs = Math.abs(n);
  if (abs >= 10000) return n.toLocaleString('en-US', {maximumFractionDigits: decimals});
  if (abs >= 100) return n.toFixed(decimals);
  return n.toFixed(Math.min(decimals + 1, 3));
}
function fmtSign(n, decimals=1) {
  if (n == null || isNaN(n)) return '—';
  return (n >= 0 ? '+' : '') + fmt(n, decimals) + '%';
}
function fmtComma(n) {
  if (n == null) return '—';
  return n.toLocaleString('en-US');
}

const CAT_COLORS = {
  Tree: '#55c078', Item: '#5588dd', Skill: '#d4a843',
  Base: '#a0a0b8', Jewel: '#cc5599', Other: '#6e6e88',
  Sim: '#ff9800'
};
const CATEGORY_COLORS = {
  '进攻': '#e05555', '防御': '#5588dd', '混合': '#9966cc', '无效': '#6e6e88'
};

// ── KPI Cards ──
// ── Global Build Baseline Section (does not change with skill tabs) ──
function GlobalBaselineSection({ activeWS }) {
  var g = (activeWS === 2 && WS2_GLOBAL_DATA && Object.keys(WS2_GLOBAL_DATA).length > 0)
    ? WS2_GLOBAL_DATA : (GLOBAL_DATA || {});
  var def = g.defence_overview || {};
  var res = g.resource_overview || {};
  var bm = g.build_modifiers || {};
  var ba = g.build_attributes || {};

  // Category color map
  var catClr = { Tree: '#44bbcc', Item: '#dd8844', Jewel: '#cc5599', Skill: '#d4a843', Sim: '#ff9800', Base: '#8888aa', Gem: '#55c078' };

  // Element emoji/icon map for affects display
  var elemIcons = { Lightning: '\u26a1', Cold: '\u2744', Fire: '\ud83d\udd25', Physical: '\u2694', Chaos: '\ud83d\udd2e' };
  var elemColors = { Lightning: '#a78bfa', Cold: '#60a5fa', Fire: '#f97316', Physical: '#d4d4d8', Chaos: '#c084fc' };

  // Build modifiers — div-based layout with expandable rows
  // Use display order: Speed first, then INC, then MORE, then others
  var bmDisplayOrder = ['Speed_INC', 'Speed_MORE', 'Damage_INC', 'ElementalDamage_INC', 'LightningDamage_INC', 'ColdDamage_INC', 'FireDamage_INC', 'PhysicalDamage_INC', 'ChaosDamage_INC', 'CritChance_INC', 'CritMultiplier_INC', 'Damage_MORE'];
  var bmKeys = Object.keys(bm).filter(function(k) { return bm[k] && bm[k].total !== 0; });
  bmKeys.sort(function(a, b) {
    var ai = bmDisplayOrder.indexOf(a), bi = bmDisplayOrder.indexOf(b);
    return (ai === -1 ? 999 : ai) - (bi === -1 ? 999 : bi);
  });
  var bmCards = bmKeys.map(function(key) {
    var m = bm[key];
    var isMore = key.indexOf('MORE') >= 0;
    var suffix = key.indexOf('INC') >= 0 ? '%' : '';
    var srcs = m.sources || [];
    var tree = 0, item = 0, jewel = 0, support = 0;
    if (isMore) {
      tree = 1; item = 1; jewel = 1; support = 1;
      srcs.forEach(function(s) {
        var v = s.value || 0;
        if (s.category === 'Tree') tree *= (1 + v / 100);
        else if (s.category === 'Item') item *= (1 + v / 100);
        else if (s.category === 'Jewel') jewel *= (1 + v / 100);
        else if (s.category === 'Skill') support *= (1 + v / 100);
      });
    } else {
      srcs.forEach(function(s) {
        if (s.category === 'Tree') tree += s.value || 0;
        else if (s.category === 'Item') item += s.value || 0;
        else if (s.category === 'Jewel') jewel += s.value || 0;
        else if (s.category === 'Skill') support += s.value || 0;
      });
    }
    // Build affects tag from data
    var affects = m.affects || '';
    var affectsTag = '';
    if (affects) {
      var elems = affects.split(',');
      affectsTag = h('span', { style: { marginLeft: 6, fontSize: 11 } },
        elems.map(function(e) { return e.trim(); }).map(function(e, ei) {
          return h('span', { key: ei, style: { color: elemColors[e] || '#6e6e88', marginRight: 2 } },
            elemIcons[e] || '');
        }).concat([
          h('span', { style: { color: '#555570', fontSize: 10, marginLeft: 2 } }, affects.replace(/,/g, '/'))
        ])
      );
    }
    // Determine label from formula_name if available
    var label = m.formula_name || key;
    // Clean up formula_name — remove the affects suffix for the main label
    if (m.formula_name && m.formula_name.indexOf('(') > 0) {
      label = m.formula_name.substring(0, m.formula_name.indexOf('(')).trim();
    }
    return h('div', { key: key },
      // Summary row
      h('div', { style: { display: 'flex', alignItems: 'center', gap: 12, padding: '5px 8px', borderBottom: '1px solid rgba(46,46,74,0.25)' } },
        h('span', { style: { width: 140, color: '#c0c0d0', fontSize: 12, fontWeight: 600, flexShrink: 0, display: 'flex', alignItems: 'center', gap: 4 } },
          h('span', null, label),
          affectsTag
        ),
        h('span', { style: { width: 70, textAlign: 'right', color: '#55c078', fontFamily: 'monospace', fontSize: 12 } }, isMore ? ((m.total >= 1 ? '+' : '') + Math.round((m.total - 1) * 100) + '%') : ('+' + Math.round(m.total) + suffix)),
        h('span', { style: { width: 70, textAlign: 'right', color: (isMore ? tree !== 1 : tree) ? '#44bbcc' : '#6e6e88', fontFamily: 'monospace', fontSize: 12 } }, isMore ? (tree !== 1 ? (tree >= 1 ? '+' : '') + Math.round((tree - 1) * 100) + '%' : '\u2014') : (tree ? '+' + Math.round(tree) + suffix : '\u2014')),
        h('span', { style: { width: 70, textAlign: 'right', color: (isMore ? item !== 1 : item) ? '#dd8844' : '#6e6e88', fontFamily: 'monospace', fontSize: 12 } }, isMore ? (item !== 1 ? (item >= 1 ? '+' : '') + Math.round((item - 1) * 100) + '%' : '\u2014') : (item ? '+' + Math.round(item) + suffix : '\u2014')),
        h('span', { style: { width: 70, textAlign: 'right', color: (isMore ? jewel !== 1 : jewel) ? '#cc5599' : '#6e6e88', fontFamily: 'monospace', fontSize: 12 } }, isMore ? (jewel !== 1 ? (jewel >= 1 ? '+' : '') + Math.round((jewel - 1) * 100) + '%' : '\u2014') : (jewel ? '+' + Math.round(jewel) + suffix : '\u2014')),
        h('span', { style: { width: 70, textAlign: 'right', color: (isMore ? support !== 1 : support) ? '#d4a843' : '#6e6e88', fontFamily: 'monospace', fontSize: 12 } }, isMore ? (support !== 1 ? (support >= 1 ? '+' : '') + Math.round((support - 1) * 100) + '%' : '\u2014') : (support ? '+' + Math.round(support) + suffix : '\u2014')),
        srcs.length > 0 && h('span', { style: { flex: 1, textAlign: 'right', color: '#6e6e88', fontSize: 10 } }, srcs.length + ' \u6761')
      ),
      // Expandable source detail
      srcs.length > 0 && h('div', { style: { paddingLeft: 20, paddingTop: 2, paddingBottom: 6, borderBottom: '1px solid rgba(46,46,74,0.15)' } },
        h('div', { style: { display: 'flex', gap: 6, fontSize: 10, color: '#555570', marginBottom: 2, fontWeight: 600 } },
          h('span', { style: { width: 36 } }, '\u7C7B\u578B'),
          h('span', { style: { width: 50, textAlign: 'right' } }, '\u6570\u503C'),
          h('span', null, '\u6765\u6E90')
        ),
        srcs.sort(function(a, b) { return Math.abs(b.value || 0) - Math.abs(a.value || 0); }).map(function(s, si) {
          var detail = s.detail ? ' \u2192 ' + s.detail : '';
          return h('div', { key: si, style: { display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, lineHeight: '18px' } },
            h('span', { style: { width: 36, color: catClr[s.category] || '#6e6e88', fontSize: 10 } }, s.category),
            h('span', { style: { width: 50, textAlign: 'right', color: (s.value || 0) >= 0 ? '#55c078' : '#e05555', fontFamily: 'monospace', fontSize: 11 } }, (s.value >= 0 ? '+' : '') + (s.value || 0) + suffix),
            h('span', { style: { flex: 1, color: '#a0a0b8' } }, (s.label || s.source || '') + detail)
          );
        })
      )
    );
  });

  // Build attributes — simple key-value rows
  var attrLabels = {
    TotalAttr: '\u603B\u5C5E\u6027', Str: '\u529B\u91CF', Dex: '\u654F\u6377', Int: '\u667A\u529B',
    Accuracy: '\u547D\u4E2D'
  };
  var attrItems = Object.keys(attrLabels).filter(function(k) { return ba[k] != null && ba[k] !== 0; }).map(function(k) {
    return h('div', { key: k, style: { display: 'flex', justifyContent: 'space-between', fontSize: 12, padding: '3px 8px' } },
      h('span', { style: { color: '#a0a0b8' } }, attrLabels[k]),
      h('span', { style: { color: '#e8e8f0', fontFamily: 'monospace' } }, Math.round(ba[k]).toLocaleString())
    );
  });

  // Defence rows
  var resistData = def.resistances || {};
  var mhtData = def.max_hit_taken || {};
  var thmData = def.taken_hit_mult || {};
  var poolsData = def.pools || {};
  var blockData = def.block || {};
  var defItems = [
    { l: '\u751F\u547D', v: (poolsData.Life || 0).toLocaleString() },
    { l: 'ES', v: (poolsData.EnergyShield || 0).toLocaleString() },
    { l: 'Mana (MoM)', v: (poolsData.Mana || 0).toLocaleString() + (poolsData.MoMPct === 100 ? ' (100%)' : '') },
    { l: '\u62A4\u7532', v: (def.armour || 0).toLocaleString() },
    { l: '\u95EA\u907F', v: (def.evasion || 0).toLocaleString() },
    { l: '\u6781\u6027\u6297\u706B', v: resistData.Fire && resistData.Fire.Resist != null ? resistData.Fire.Resist + '%' : '-' },
    { l: '\u6781\u6027\u6297\u51B0', v: resistData.Cold && resistData.Cold.Resist != null ? resistData.Cold.Resist + '%' : '-' },
    { l: '\u6781\u6027\u6297\u96F7', v: resistData.Lightning && resistData.Lightning.Resist != null ? resistData.Lightning.Resist + '%' : '-' },
    { l: '\u6DF7\u6C8C\u6297', v: resistData.Chaos && resistData.Chaos.Resist != null ? resistData.Chaos.Resist + '%' : '-' },
    { l: '\u6700\u5927\u627F\u4F24(\u706B)', v: (mhtData.Fire || 0).toLocaleString() },
    { l: '\u6700\u5927\u627F\u4F24(\u51B0)', v: (mhtData.Cold || 0).toLocaleString() },
    { l: '\u6700\u5927\u627F\u4F24(\u96F7)', v: (mhtData.Lightning || 0).toLocaleString() },
    { l: '\u6700\u5927\u627F\u4F24(\u6DF7\u6C8C)', v: (mhtData.Chaos || 0).toLocaleString() },
    { l: '\u627F\u4F24\u4E58\u6570(\u706B)', v: fmt(thmData.Fire || 1, 2) },
    { l: '\u627F\u4F24\u4E58\u6570(\u6DF7\u6C8C)', v: fmt(thmData.Chaos || 1, 2) },
    { l: '\u6321\u683C', v: (blockData.BlockChance || 0) + '% / ' + (blockData.SpellBlockChance || 0) + '%' },
  ];

  // Resource rows
  var spiritData = res.spirit || {};
  var resItems = [
    { l: '\u751F\u547D', v: (res.life && res.life.total || 0).toLocaleString() + ' / \u5269\u4F59 ' + (res.life && res.life.unreserved || 0) },
    { l: 'Mana', v: (res.mana && res.mana.total || 0).toLocaleString() + ' / \u5269\u4F59 ' + (res.mana && res.mana.unreserved || 0) },
    { l: '\u7CBE\u9B42', v: (spiritData.total || 0) + ' / \u9884\u7EA6 ' + (spiritData.reserved_pct != null ? spiritData.reserved_pct.toFixed(1) + '%' : '-') + ' / \u5269\u4F59 ' + (spiritData.unreserved || 0) },
    { l: 'ES', v: (res.es && res.es.total || 0).toLocaleString() },
  ];

  // Jewel overview
  var jewels = g.jewel_overview || [];

  return h('div', null,
    // Build modifiers
    bmCards.length > 0 && h('div', { className: 'chart-box full-width' },
      h('div', { className: 'chart-title' }, h('span', { className: 'dot' }), '\u6784\u7B51\u4FEE\u9970\u7B26'),
      // Column header
      h('div', { style: { display: 'flex', alignItems: 'center', gap: 12, padding: '4px 8px', borderBottom: '1px solid rgba(46,46,74,0.4)', marginBottom: 2 } },
        h('span', { style: { width: 140, color: '#6e6e88', fontSize: 11, fontWeight: 600, flexShrink: 0 } }, '\u4FEE\u9970\u7B26'),
        h('span', { style: { width: 70, textAlign: 'right', color: '#6e6e88', fontSize: 11, fontWeight: 600 } }, '\u603B\u91CF'),
        h('span', { style: { width: 70, textAlign: 'right', color: '#6e6e88', fontSize: 11, fontWeight: 600 } }, '\u5929\u8D4B'),
        h('span', { style: { width: 70, textAlign: 'right', color: '#6e6e88', fontSize: 11, fontWeight: 600 } }, '\u88C5\u5907'),
        h('span', { style: { width: 70, textAlign: 'right', color: '#6e6e88', fontSize: 11, fontWeight: 600 } }, '\u73E0\u5B9D'),
        h('span', { style: { width: 70, textAlign: 'right', color: '#6e6e88', fontSize: 11, fontWeight: 600 } }, '\u8F85\u52A9')
      ),
      h('div', null, bmCards)
    ),
    // Build attributes
    attrItems.length > 0 && h('div', { className: 'chart-box' },
      h('div', { className: 'chart-title' }, h('span', { className: 'dot' }), '\u6784\u7B51\u5C5E\u6027'),
      h('div', null, attrItems)
    ),
    // Defence (expandable)
    defItems.length > 0 && h('div', { className: 'chart-box full-width' },
      h('details', { open: false },
        h('summary', { className: 'chart-title', style: { cursor: 'pointer', userSelect: 'none' } },
          h('span', { className: 'dot' }), '\u9632\u5FA1\u9762', ' \u25B6'
        ),
        h('div', { style: { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '2px 20px', padding: '8px 4px' } },
          defItems.map(function(r, i) {
            return h('div', { key: i, style: { display: 'flex', justifyContent: 'space-between', fontSize: 12, padding: '3px 0' } },
              h('span', { style: { color: '#a0a0b8' } }, r.l),
              h('span', { style: { color: '#e8e8f0', fontFamily: 'monospace' } }, r.v)
            );
          })
        )
      )
    ),
    // Resource (expandable)
    resItems.length > 0 && h('div', { className: 'chart-box full-width' },
      h('details', { open: false },
        h('summary', { className: 'chart-title', style: { cursor: 'pointer', userSelect: 'none' } },
          h('span', { className: 'dot' }), '\u8D44\u6E90\u9762', ' \u25B6'
        ),
        h('div', { style: { display: 'flex', flexDirection: 'column', gap: '2px', padding: '8px 4px' } },
          resItems.map(function(r, i) {
            return h('div', { key: i, style: { display: 'flex', justifyContent: 'space-between', fontSize: 12, padding: '3px 0' } },
              h('span', { style: { color: '#a0a0b8' } }, r.l),
              h('span', { style: { color: '#e8e8f0', fontFamily: 'monospace' } }, r.v)
            );
          })
        )
      )
    ),
    // Jewel overview (expandable per jewel)
    jewels.length > 0 && h('div', { className: 'chart-box full-width' },
      h('details', { open: false },
        h('summary', { className: 'chart-title', style: { cursor: 'pointer', userSelect: 'none' } },
          h('span', { className: 'dot' }), '\u73E0\u5B9D\u6982\u89C8 (' + jewels.length + ')', ' \u25B6'
        ),
        h('div', { style: { display: 'flex', flexDirection: 'column', gap: 6, padding: '8px 4px' } },
          jewels.map(function(j, i) {
            var mods = j.mods || [];
            var passives = (j.granted_passives || []).join(', ');
            var dpsTotal = j.dps_pct || 0;
            var ehpTotal = 0;
            mods.forEach(function(m) { ehpTotal += (m.ehp_pct || 0); });
            var rarityColor = j.rarity === 'UNIQUE' ? '#d4a843' : '#a0a0b8';
            return h('details', { key: i, style: { borderBottom: '1px solid rgba(46,46,74,0.3)', paddingBottom: 4 } },
              h('summary', { style: { cursor: 'pointer', fontSize: 12, color: '#c0c0d0', listStyle: 'none', display: 'flex', alignItems: 'center', gap: 8, padding: '2px 0' } },
                h('span', { style: { color: '#cc5599' } }, '\u25B8'),
                h('span', { style: { fontWeight: 600, color: rarityColor } }, j.name || j.base_type),
                h('span', { style: { color: '#6e6e88', fontSize: 11 } }, j.base_type),
                h('span', { style: { color: '#6e6e88', fontSize: 11 } }, j.slot_name),
                dpsTotal > 0.01 ? h('span', { style: { color: '#55c078', fontFamily: 'monospace', fontSize: 11, marginLeft: 'auto' } }, '+' + dpsTotal.toFixed(2) + '%') : null
              ),
              mods.length > 0 && h('div', { style: { marginLeft: 20, marginTop: 2 } },
                // Header row
                h('div', { style: { display: 'flex', alignItems: 'center', gap: 8, fontSize: 10, color: '#555570', fontWeight: 600, borderBottom: '1px solid rgba(46,46,74,0.2)', marginBottom: 2, paddingBottom: 2 } },
                  h('span', { style: { minWidth: 160 } }, '\u8bcd\u7f00'),
                  h('span', { style: { minWidth: 40 } }, '\u503c'),
                  h('span', { style: { minWidth: 30 } }, '\u7c7b\u578b'),
                  h('span', { style: { minWidth: 55, textAlign: 'right' } }, 'DPS%'),
                  h('span', { style: { minWidth: 55, textAlign: 'right' } }, 'EHP%')
                ),
                mods.map(function(m, mi) {
                  var dpsVal = m.dps_pct || 0;
                  var ehpVal = m.ehp_pct || 0;
                  var suffix = (m.type === 'INC') ? '%' : '';
                  var hasImpact = dpsVal > 0.01 || ehpVal > 0.01;
                  return h('div', { key: mi, style: { display: 'flex', alignItems: 'center', gap: 8, fontSize: 11, lineHeight: '18px' } },
                    h('span', { style: { color: hasImpact ? '#c0c0d0' : '#555570', minWidth: 160, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' } }, m.name),
                    h('span', { style: { color: '#e8e8f0', fontFamily: 'monospace', minWidth: 40 } }, '+' + m.value + suffix),
                    h('span', { style: { color: '#6e6e88', minWidth: 30, fontSize: 10 } }, m.type),
                    h('span', { style: { color: dpsVal > 0.01 ? '#55c078' : '#444460', fontFamily: 'monospace', minWidth: 55, textAlign: 'right' } }, dpsVal > 0.01 ? '+' + dpsVal.toFixed(2) + '%' : '-'),
                    h('span', { style: { color: ehpVal > 0.01 ? '#44bbcc' : '#444460', fontFamily: 'monospace', minWidth: 55, textAlign: 'right' } }, ehpVal > 0.01 ? '+' + ehpVal.toFixed(2) + '%' : '-')
                  );
                }),
                passives && h('div', { style: { marginTop: 2, fontSize: 11, color: '#555570' } }, '\u8D4B\u4E88\u5929\u8D4B: ', passives)
              )
            );
          })
        )
      )
    )
  );
}

var TH_STYLE = { fontSize: 11, color: '#6e6e88', fontWeight: 400, textAlign: 'left', padding: '4px 8px', borderBottom: '1px solid rgba(46,46,74,0.4)' };

// ── Source List (reusable) ──
function SourceList({ sources }) {
  if (!sources || sources.length === 0) return null;
  return h('div', { style: { display: 'flex', flexDirection: 'column', gap: 1, marginTop: 2, marginBottom: 2 } },
    sources.map((s, si) =>
      h('div', { key: si, style: { fontSize: 12, color: '#a0a0b8', display: 'flex', gap: 8, paddingLeft: 8 } },
        h('span', { style: { width: 50, color: CAT_COLORS[s.category] || '#6e6e88', fontSize: 11 } }, s.category),
        h('span', { style: { width: 50, textAlign: 'right', color: (s.value || 0) >= 0 ? '#e8e8f0' : '#e05555', fontFamily: 'monospace' } }, (s.value >= 0 ? '+' : '') + s.value),
        h('span', { style: { flex: 1 } }, s.label || '')
      )
    )
  );
}

// ── DPS Calculation Flow (renders pre-computed stages from Python) ──
function DPSFlowTable({ data }) {
  var stages = (data && data.dps_flow_stages) || [];
  if (stages.length === 0) return null;
  // Total DPS is the last stage's formula text (already formatted by Python)
  var totalLine = stages[stages.length - 1];

  return h('div', { className: 'chart-box full-width' },
    h('div', { className: 'chart-title' }, h('span', { className: 'dot' }), 'DPS 计算流程'),
    h('div', { style: { display: 'flex', flexDirection: 'column' } },
      stages.slice(0, -1).map(function(r, i) {
        var detail = r.detail_items;
        var hasDetail = detail && detail.length > 0;
        var isTotal = r.label === 'Total DPS';
        return h('div', { key: i, style: {
          borderBottom: '1px solid rgba(46,46,74,0.4)', padding: '6px 10px',
          background: isTotal ? 'rgba(212,168,67,0.06)' : 'transparent'
        }},
          h('div', { style: { display: 'flex', alignItems: 'center', gap: 12 } },
            h('div', { style: { width: 110, fontSize: 13, fontWeight: 500, color: r.color } }, r.label),
            h('div', { style: { flex: 1, fontSize: 12, color: '#a0a0b8', fontFamily: 'monospace' } }, r.formula),
            h('div', { style: { width: 160, textAlign: 'right', fontSize: 12, color: '#6e6e88' } }, r.factor)
          ),
          hasDetail ? h('details', { style: { paddingLeft: 122, marginTop: 2 } },
            h('summary', { style: { fontSize: 11, color: '#6e6e88', cursor: 'pointer', userSelect: 'none' } },
              '\u25B6 ' + detail.length + ' \u4e2a\u5b50\u9879'
            ),
            detail.map(function(it, j) {
              var isM = it.key && it.key.includes('_MORE');
              var valStr = isM ? ('+' + fmt((it.total_value - 1) * 100, 1) + '%') : ('+' + (it.total_value < 10 ? fmt(it.total_value, 1) : Math.round(it.total_value)) + '%');
              return h('div', { key: j, style: { padding: '2px 0' } },
                h('div', { style: { fontSize: 12, color: '#c0c0d0' } },
                  h('span', { style: { fontWeight: 500 } }, it.formula_name),
                  h('span', { style: { color: r.color, marginLeft: 8, fontFamily: 'monospace' } },
                    valStr
                  )
                ),
                h(SourceList, { sources: it.sources })
              );
            })
          ) : null
        );
      })
    ),
    h('div', { style: { marginTop: 8, padding: '8px 12px', background: 'rgba(212,168,67,0.08)', borderRadius: 4, textAlign: 'center' } },
      h('span', { style: { color: '#a0a0b8', fontSize: 13 } }, 'Total DPS = '),
      h('span', { style: { color: '#d4a843', fontSize: 16, fontWeight: 700 } }, totalLine.formula)
    )
  );
}

// ── Formula Items Breakdown ──
function FormulaBreakdown({ data }) {
  if (!data || !data.formula_items) return null;

  const catColors = { Tree: '#55c078', Item: '#5588dd', Skill: '#d4a843', Base: '#a0a0b8', Jewel: '#cc5599', Enemy: '#e05555', Sim: '#ff9800' };
  const elemIcons = { Lightning: '\u26a1', Cold: '\u2744', Fire: '\ud83d\udd25', Physical: '\u2694', Chaos: '\ud83d\udd2e' };

  // Merge {Element}_Lucky rows into single entry
  const items = data.formula_items.filter(it =>
    it.total_value !== undefined && it.total_value !== 0
    && it.key !== 'CombinedDPS' && !it.key.endsWith('EffMult')
  );
  const luckyItems = items.filter(it => it.key.endsWith('_Lucky'));
  const nonLucky = items.filter(it => !it.key.endsWith('_Lucky'));

  let merged = [...nonLucky];
  if (luckyItems.length > 0) {
    // Merge Lucky rows
    const totalLucky = luckyItems.reduce((s, it) => s + it.total_value, 0);
    const seenSrcs = new Map();
    luckyItems.forEach(it => (it.sources || []).forEach(s => {
      const k = s.source;
      if (!seenSrcs.has(k) || Math.abs(s.value) > Math.abs(seenSrcs.get(k).value)) seenSrcs.set(k, s);
    }));
    merged.push({
      key: 'Lucky_Hits_Merged',
      formula_name: 'Lucky Hits (' + luckyItems.length + ' \u5143\u7d20 \u00d7 ' + luckyItems[0].total_value + '%)',
      total_value: totalLucky,
      sources: Array.from(seenSrcs.values()),
      category_summary: luckyItems[0].category_summary || {},
    });
  }

  const sorted = merged.sort((a, b) => {
    const order = { '_INC': 0, '_MORE': 1, '_BASE': 2, 'Lucky': 3, 'ConvGain': 4, 'SelfGain': 5 };
    const aType = Object.keys(order).find(k => a.key.includes(k)) || 'zz';
    const bType = Object.keys(order).find(k => b.key.includes(k)) || 'zz';
    return (order[aType] || 9) - (order[bType] || 9) || Math.abs(b.total_value) - Math.abs(a.total_value);
  });

  if (sorted.length === 0) return null;

  return h('div', { className: 'chart-box full-width' },
    h('div', { className: 'chart-title' }, h('span', { className: 'dot' }), 'DPS \u4e58\u533a\u6765\u6e90\u62c6\u89e3'),
    h('div', { style: { display: 'flex', flexDirection: 'column', gap: 0 } },
      sorted.map((it, idx) => {
        const cats = it.category_summary || {};
        const isMore = it.key.includes('_MORE');
        const total = Math.abs(it.total_value);
        const catKeys = Object.keys(cats).filter(k => cats[k] !== 0);
        const catEntries = catKeys.map(k => ({ key: k, value: Math.abs(cats[k]), color: catColors[k] || '#6e6e88' }));
        catEntries.sort((a, b) => b.value - a.value);

        // MORE: category 用乘法计算贡献比（每个 cat 的 (val-1)/(total-1)）
        // INC/BASE: category 用加法
        let catSum, catPcts;
        if (isMore) {
          catSum = total - 1 || 1;
          catPcts = catEntries.map(c => ({ ...c, pct: (c.value - 1) / catSum * 100 }));
        } else {
          catSum = catEntries.reduce((s, c) => s + c.value, 0) || 1;
          catPcts = catEntries.map(c => ({ ...c, pct: c.value / catSum * 100 }));
        }

        // 显示值: MORE 用百分比 +56%/-9%, 其他用 +N%
        let displayStr;
        if (isMore) {
          const pct = (it.total_value - 1) * 100;
          displayStr = (pct >= 0 ? '+' : '') + fmt(pct, 1) + '%';
        } else {
          var suffix = it.key.includes('Lucky') ? '%' : (it.key.includes('Speed') || it.total_value < 10) ? '%' : '%';
          displayStr = (it.total_value >= 0 ? '+' : '') + (it.key.includes('Speed') || it.total_value < 10 ? fmt(it.total_value, 1) : Math.round(it.total_value)) + suffix;
        }

        // Build top-3 source names per category for legend
        var catLegend = catPcts.map(function(c) {
          var topSrcs = (it.sources || []).filter(function(s) { return s.category === c.key; });
          topSrcs.sort(function(a, b) { return Math.abs(b.value || 0) - Math.abs(a.value || 0); });
          var names = topSrcs.slice(0, 3).map(function(s) { return s.label || s.source; });
          if (names.length === 0) return h('span', { key: c.key, style: { fontSize: 11, color: c.color } }, c.key + (isMore ? ' +' + fmt((c.value - 1) * 100, 0) + '%' : ' ' + fmt(c.value, 0)));
          var rest = topSrcs.length - 3;
          var label = names.join(', ') + (rest > 0 ? ' +' + rest : '');
          return h('span', { key: c.key, style: { fontSize: 11, color: c.color, maxWidth: 280, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }, title: label }, label);
        });

        return h('div', { key: idx, style: { borderBottom: '1px solid rgba(46,46,74,0.4)' } },
          h('div', { style: { display: 'flex', alignItems: 'center', gap: 10, padding: '8px 4px' } },
            h('div', { style: { minWidth: 260, fontSize: 13, color: '#e8e8f0' } },
              h('span', { style: { fontWeight: 500 } }, it.formula_name),
              h('span', { style: { color: '#d4a843', fontWeight: 700, marginLeft: 8 } },
                displayStr
              )
            ),
            h('div', { style: { flex: 1, height: 16, display: 'flex', borderRadius: 3, overflow: 'hidden' } },
              catPcts.map((c, ci) =>
                h('div', { key: ci, style: { width: c.pct + '%', background: c.color, opacity: 0.7 }, title: c.key + (isMore ? ' +' + fmt((c.value - 1) * 100, 0) + '%' : ': ' + fmt(c.value, 1)) })
              )
            ),
            h('div', { style: { display: 'flex', gap: 8, minWidth: 200, justifyContent: 'flex-end', flexWrap: 'wrap' } }, catLegend)
          ),
          (it.sources && it.sources.length > 0) ? h('details', { style: { paddingLeft: 12, paddingBottom: 4 } },
            h('summary', { style: { fontSize: 11, color: '#6e6e88', cursor: 'pointer', userSelect: 'none' } }, '\u25bc ' + it.sources.length + ' \u4e2a\u6765\u6e90'),
            h('div', { style: { display: 'flex', flexDirection: 'column', gap: 1, marginTop: 2 } },
              it.sources.map((s, si) =>
                h('div', { key: si, style: { fontSize: 12, color: '#a0a0b8', display: 'flex', gap: 8, paddingLeft: 8 } },
                  h('span', { style: { width: 50, color: catColors[s.category] || '#6e6e88', fontSize: 11 } }, s.category),
                  h('span', { style: { width: 50, textAlign: 'right', color: (s.value || 0) >= 0 ? '#e8e8f0' : '#e05555', fontFamily: 'monospace' } }, (s.value >= 0 ? '+' : '') + s.value),
                  h('span', { style: { flex: 1 } }, s.label || s.source)
                )
              )
            )
          ) : null
        );
      })
    )
  );
}

// ── Damage Composition Donut Chart (SVG) + Detail Table ──
function DamagePieChart({ data }) {
  var dc = (data && data.damage_composition) || [];
  if (dc.length === 0) return null;

  var _pieIcons = { Lightning: '\u26a1', Cold: '\u2744', Fire: '\ud83d\udd25', Physical: '\u2694', Chaos: '\ud83d\udd2e' };
  var avgHit = (data && data.average_hit) || 0;
  var speed = (data && data.speed) || 1;
  var totalDPS = (data && data.total_dps) || 0;

  // Donut geometry
  var size = 130;
  var cx = size / 2, cy = size / 2;
  var outerR = 54, innerR = 34;
  var thickness = outerR - innerR;
  var midR = (outerR + innerR) / 2;
  var circumference = 2 * Math.PI * midR;
  var totalHit = dc.reduce(function(s, e) { return s + e.hit_avg; }, 0) || 1;

  // Build donut slices
  var slices = [];
  var offset = 0;
  for (var i = 0; i < dc.length; i++) {
    var pct = dc[i].hit_avg / totalHit;
    var dashLen = pct * circumference;
    var gapLen = circumference - dashLen;
    slices.push(h('circle', {
      key: i, cx: cx, cy: cy, r: midR,
      fill: 'none', stroke: dc[i].color || '#6e6e88',
      strokeWidth: thickness,
      strokeDasharray: dashLen.toFixed(2) + ' ' + gapLen.toFixed(2),
      strokeDashoffset: (-offset).toFixed(2),
      style: { opacity: 0.85 }
    }));
    offset += dashLen;
  }

  // Center label
  var centerText = h('text', { x: cx, y: cy - 6, textAnchor: 'middle', fill: '#e8e8f0', fontSize: 16, fontWeight: 700, fontFamily: 'monospace' }, Math.round(totalDPS).toLocaleString());
  var centerSub = h('text', { x: cx, y: cy + 12, textAnchor: 'middle', fill: '#6e6e88', fontSize: 10 }, 'Total DPS');

  // Detail table
  var rows = dc.map(function(e, i) {
    var hitPct = e.hit_avg / totalHit * 100;
    var elemCombined = avgHit * (e.hit_avg / totalHit);
    var elemDPS = elemCombined * speed;
    var icon = _pieIcons[e.element] || '';
    var clr = e.color || '#6e6e88';
    return h('div', { key: i, style: { display: 'flex', alignItems: 'center', gap: 8, padding: '3px 0', borderBottom: i < dc.length - 1 ? '1px solid rgba(46,46,74,0.15)' : 'none' } },
      h('div', { style: { width: 10, height: 10, borderRadius: 2, background: clr, flexShrink: 0 } }),
      h('span', { style: { color: clr, fontWeight: 500, minWidth: 85, fontSize: 12 } }, icon + ' ' + e.element),
      h('span', { style: { color: '#c0c0d0', fontFamily: 'monospace', minWidth: 50, textAlign: 'right', fontSize: 12 } }, fmt(hitPct, 1) + '%'),
      h('span', { style: { color: '#a0a0b8', fontFamily: 'monospace', minWidth: 60, textAlign: 'right', fontSize: 11 } }, e.crit_avg > 0 ? Math.round(e.crit_avg).toLocaleString() : '-'),
      h('span', { style: { color: '#e8e8f0', fontFamily: 'monospace', minWidth: 60, textAlign: 'right', fontSize: 12, fontWeight: 600 } }, Math.round(elemDPS).toLocaleString())
    );
  });

  return h('div', { className: 'chart-box full-width' },
    h('div', { className: 'chart-title' }, h('span', { className: 'dot' }), '\u4f24\u5bb3\u6784\u6210'),
    h('div', { style: { display: 'flex', alignItems: 'center', gap: 20, padding: '8px 4px' } },
      h('svg', { width: size, height: size, viewBox: '0 0 ' + size + ' ' + size, style: { flexShrink: 0 } },
        slices, centerText, centerSub
      ),
      h('div', { style: { flex: 1, display: 'flex', flexDirection: 'column', gap: 0 } },
        h('div', { style: { display: 'flex', alignItems: 'center', gap: 8, padding: '2px 0 4px', borderBottom: '1px solid rgba(46,46,74,0.4)' } },
          h('span', { style: { width: 10 } }),
          h('span', { style: { minWidth: 85, color: '#6e6e88', fontSize: 10, fontWeight: 600 } }, '\u5143\u7d20'),
          h('span', { style: { minWidth: 50, textAlign: 'right', color: '#6e6e88', fontSize: 10, fontWeight: 600 } }, '\u547d\u4e2d\u5360\u6bd4'),
          h('span', { style: { minWidth: 60, textAlign: 'right', color: '#6e6e88', fontSize: 10, fontWeight: 600 } }, '\u66b4\u51fb\u547d\u4e2d'),
          h('span', { style: { minWidth: 60, textAlign: 'right', color: '#6e6e88', fontSize: 10, fontWeight: 600 } }, 'DPS')
        ),
        rows
      )
    )
  );
}

// ── Sensitivity Ranking ──
function SensitivityChart({ sensitivity }) {
  if (!sensitivity || sensitivity.length === 0) return null;
  var sorted = sensitivity.filter(function(s) { return s.needed_value != null && s.needed_value < 9999; })
    .sort(function(a, b) { return a.needed_value - b.needed_value; }).slice(0, 15);

  if (sorted.length === 0) return null;

  // 进度条表示性价比（DPS/单位投入），性价比最高 = 100%
  var maxDpsPU = Math.max.apply(null, sorted.map(function(s) { return s.dps_per_unit || 0; })) || 1;

  var rows = sorted.map(function(s, i) {
    var label = s.label || s.key;
    var needed = s.needed_value;
    var dpsPU = s.dps_per_unit || 0;
    var modType = s.mod_type || '';
    var barPct = Math.min(dpsPU / maxDpsPU * 100, 100);
    var typeLabel = modType === 'INC' ? 'INC' : (modType === 'MORE' ? 'MORE' : (modType === 'BASE' ? 'BASE' : modType));
    var typeColor = modType === 'MORE' ? '#5588dd' : (modType === 'INC' ? '#55c078' : '#d4a843');
    var rank = i + 1;
    return h('div', { key: i, style: { display: 'flex', alignItems: 'center', gap: 8, padding: '4px 0', borderBottom: '1px solid rgba(46,46,74,0.15)' } },
      h('span', { style: { width: 24, textAlign: 'center', color: i < 3 ? '#d4a843' : '#6e6e88', fontSize: 12, fontWeight: i < 3 ? 700 : 400 } }, rank),
      h('div', { style: { flex: 1, minWidth: 0 } },
        h('div', { style: { display: 'flex', alignItems: 'baseline', gap: 6 } },
          h('span', { style: { color: '#e8e8f0', fontSize: 12, fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' } }, label),
          h('span', { style: { color: typeColor, fontSize: 10, fontWeight: 600, flexShrink: 0 } }, typeLabel)
        ),
        h('div', { style: { height: 4, borderRadius: 2, marginTop: 3, background: 'rgba(46,46,74,0.3)' } },
          h('div', { style: { height: '100%', borderRadius: 2, width: barPct + '%', background: 'linear-gradient(90deg, #d4a843 0%, #f0c860 100%)', opacity: 0.7 } })
        )
      ),
      h('span', { style: { width: 75, textAlign: 'right', color: '#c0c0d0', fontFamily: 'monospace', fontSize: 12, flexShrink: 0 } }, fmt(needed, 1)),
      h('span', { style: { width: 85, textAlign: 'right', color: '#55c078', fontFamily: 'monospace', fontSize: 11, flexShrink: 0 } }, '+' + fmt(dpsPU, 3) + '%/unit')
    );
  });

  return h('div', { className: 'chart-box full-width' },
    h('div', { className: 'chart-title' }, h('span', { className: 'dot' }), '\u4f18\u5316\u6760\u6746\u6392\u540d'),
    h('div', { style: { display: 'flex', alignItems: 'center', gap: 8, padding: '2px 0 4px', borderBottom: '1px solid rgba(46,46,74,0.4)' } },
      h('span', { style: { width: 24 } }),
      h('span', { style: { flex: 1, color: '#6e6e88', fontSize: 10, fontWeight: 600 } }, '\u4fee\u9970\u7b26'),
      h('span', { style: { width: 75, textAlign: 'right', color: '#6e6e88', fontSize: 10, fontWeight: 600 } }, '\u6240\u9700\u6295\u5165'),
      h('span', { style: { width: 85, textAlign: 'right', color: '#6e6e88', fontSize: 10, fontWeight: 600 } }, 'DPS/\u5355\u4f4d')
    ),
    rows
  );
}

// ── Aura Table (条件端点展示) ──
function AuraChart({ auras }) {
  if (!auras || auras.length === 0) return null;
  const aurasWithRange = auras.filter(a => a.config_ranges && a.config_ranges.length > 0);
  const aurasStatic = auras.filter(a => !a.config_ranges || a.config_ranges.length === 0);

  const rows = [];
  aurasWithRange.forEach(aura => {
    const cr = aura.config_ranges[0];
    const paramLabel = cr.label ? cr.label.replace(':', '') : 'Value';
    const maxVal = cr.actual_max || 300;
    const pctMin = cr.dps_pct_min || 0;
    const pctMax = cr.dps_pct_max || 0;
    const bareMin = cr.bare_pct_min != null ? cr.bare_pct_min : pctMin;
    const bareMax = cr.bare_pct_max != null ? cr.bare_pct_max : pctMax;
    const supMin = pctMin - bareMin;
    const supMax = pctMax - bareMax;
    const spiritMin = cr.spirit_pct_min || 0;
    const spiritMax = cr.spirit_pct_max || 0;
    // Min 端点
    rows.push({
      name: aura.name + (aura.simulated ? ' ⚠' : ''),
      endpoint: paramLabel + '=0',
      bare: bareMin, real: pctMin, support: supMin,
      spiritSup: spiritMin,
      ehp: aura.ehp_pct || 0, spirit: Math.round(aura.spirit_cost || 0)
    });
    // Max 端点
    rows.push({
      name: '', endpoint: paramLabel + '=' + maxVal,
      bare: bareMax, real: pctMax, support: supMax,
      spiritSup: spiritMax,
      ehp: '', spirit: ''
    });
  });
  aurasStatic.forEach(a => {
    rows.push({
      name: a.name + (a.simulated ? ' ⚠' : ''),
      endpoint: '—',
      bare: a.bare_dps_pct || 0, real: a.dps_pct || 0,
      support: a.supports_extra_pct || 0,
      spiritSup: a.spirit_support_pct || 0,
      ehp: a.ehp_pct || 0, spirit: Math.round(a.spirit_cost || 0)
    });
  });

  return h('div', { className: 'chart-box full-width' },
    h('div', { className: 'chart-title' }, h('span', { className: 'dot' }), '光环贡献分析'),
    h('table', null,
      h('thead', null, h('tr', null,
        h('th', null, '光环'), h('th', null, '条件'), h('th', null, '裸光环'), h('th', null, '真实'),
        h('th', null, '辅助增益'), h('th', null, '精魄辅助'), h('th', null, 'EHP'), h('th', null, '精魄')
      )),
      h('tbody', null, rows.map((r, i) => h('tr', { key: i },
        h('td', { style: r.name ? {} : { opacity: 0 } }, r.name),
        h('td', { style: { color: '#a0a0b8' } }, r.endpoint),
        h('td', null, fmtSign(r.bare)),
        h('td', { style: { color: '#55c078', fontWeight: 500 } }, fmtSign(r.real)),
        h('td', { style: { color: '#cc5599' } }, Math.abs(r.support) >= 0.05 ? fmtSign(r.support, 2) : '—'),
        h('td', { style: { color: '#e8a838' } }, Math.abs(r.spiritSup) >= 0.05 ? fmtSign(r.spiritSup, 2) : '—'),
        h('td', null, r.ehp !== '' ? fmtSign(r.ehp) : ''),
        h('td', null, r.spirit !== '' ? r.spirit : '')
      )))
    )
  );
}

// ── 候选光环推荐 + 精魄辅助 + 精魄预算 ──
function CandidateAurasTable({ aura_spirit, baseline }) {
  if (!aura_spirit) return null;
  var candidates = aura_spirit.candidate_auras || [];
  var spiritTests = aura_spirit.spirit_support_tests || [];
  var budget = aura_spirit.spirit_budget || {};
  var existing = aura_spirit.existing_auras || [];

  // 精魄辅助推荐：排除已有辅助，按名称去重，取 top 5
  var existingSupportNames = {};
  existing.forEach(function(a) {
    (a.spirit_supports || []).forEach(function(s) { existingSupportNames[s.name] = true; });
  });
  var effectiveTests = spiritTests.filter(function(t) {
    return (t.dps_pct || 0) > 0.1 && !existingSupportNames[t.name];
  });
  effectiveTests.sort(function(a, b) { return (b.dps_pct || 0) - (a.dps_pct || 0); });
  var seenNames = {};
  var topTests = [];
  effectiveTests.forEach(function(t) {
    var key = t.name || '?';
    if (!seenNames[key]) {
      seenNames[key] = true;
      topTests.push(t);
    }
  });
  topTests = topTests.slice(0, 5);

  // 现有光环的精魄辅助列表
  var spiritSupports = [];
  existing.forEach(function(a) {
    if (a.spirit_supports && a.spirit_supports.length > 0) {
      spiritSupports.push({ aura: a.name, supports: a.spirit_supports, spirit: a.spirit_cost });
    }
  });

  var hasCandidates = candidates.length > 0;
  var hasSpirit = spiritSupports.length > 0;
  var hasBudget = budget.total > 0;

  if (!hasCandidates && !hasSpirit && !hasBudget && topTests.length === 0) return null;

  return h('div', { className: 'chart-box full-width' },
    // 精魄预算
    hasBudget && h('div', { style: { marginBottom: 12 } },
      h('div', { className: 'chart-title' }, h('span', { className: 'dot' }), '\u7CBE\u9B42\u9884\u7B97'),
      h('div', { style: { display: 'flex', gap: 20, fontSize: 13, padding: '4px 8px' } },
        h('span', null, '\u603B\u8BA1: ', h('b', null, Math.round(budget.total || 0))),
        h('span', null, '\u5DF2\u7528: ', h('b', { style: { color: '#dd8844' } }, Math.round(budget.reserved || 0))),
        h('span', null, '\u53EF\u7528: ', h('b', { style: { color: budget.available > 0 ? '#55c078' : '#e05555' } }, Math.round(budget.available || 0)))
      )
    ),
    // 现有光环的精魄辅助
    hasSpirit && h('div', { style: { marginBottom: 12 } },
      h('div', { className: 'chart-title' }, h('span', { className: 'dot' }), '\u7CBE\u9B42\u8F85\u52A9\u5B9D\u77F3'),
      h('table', null,
        h('thead', null, h('tr', null,
          h('th', null, '\u5149\u73AF'), h('th', null, '\u8F85\u52A9'), h('th', null, '\u7CBE\u9B42'), h('th', null, '\u6548\u679C')
        )),
        h('tbody', null,
          spiritSupports.map(function(sp) {
            return sp.supports.map(function(s, si) {
              return h('tr', { key: sp.aura + si },
                si === 0 ? h('td', { rowSpan: sp.supports.length, style: { color: '#d4a843', fontWeight: 500 } }, sp.aura) : null,
                h('td', null, s.name),
                h('td', null, Math.round(s.spirit || 0)),
                h('td', { style: { color: '#a0a0b8', fontSize: 11 } },
                  (function() {
                    var bl = baseline || {};
                    var baseDps = bl.TotalDPS || 1;
                    var baseEhp = bl.TotalEHP || 1;
                    var parts = [];
                    if (s.dps_delta && Math.abs(s.dps_delta) > 0.5) parts.push('DPS ' + (s.dps_delta > 0 ? '+' : '') + (s.dps_delta / baseDps * 100).toFixed(1) + '%');
                    if (s.ehp_delta && Math.abs(s.ehp_delta) > 0.5) parts.push('EHP ' + (s.ehp_delta > 0 ? '+' : '') + (s.ehp_delta / baseEhp * 100).toFixed(1) + '%');
                    if (s.regen_delta && Math.abs(s.regen_delta) > 0.1) parts.push('\u751F\u547D\u6062\u590D ' + (s.regen_delta > 0 ? '+' : '') + s.regen_delta.toFixed(1) + '/s');
                    return parts.length > 0 ? parts.join(', ') : '\u9632\u5FA1\u6548\u679C';
                  })()
                )
              );
            });
          }).flat()
        )
      )
    ),
    // 候选光环推荐
    hasCandidates && h('div', { style: { marginBottom: 12 } },
      h('div', { className: 'chart-title' }, h('span', { className: 'dot' }), '\u6F5C\u5728\u5149\u73AF\u63A8\u8350'),
      h('table', null,
        h('thead', null, h('tr', null,
          h('th', null, '\u5149\u73AF'), h('th', null, 'DPS'), h('th', null, '\u7CBE\u9B42'), h('th', null, '\u5907\u6CE8')
        )),
        h('tbody', null,
          candidates.map(function(c, i) {
            return h('tr', { key: i },
              h('td', null, c.name),
              h('td', { style: { color: (c.dps_pct || 0) > 0 ? '#55c078' : '#e05555' } }, fmtSign(c.dps_pct || 0)),
              h('td', null, Math.round(c.spirit || 0)),
              h('td', { style: { color: '#a0a0b8', fontSize: 11 } }, c.spirit_note || '')
            );
          })
        )
      )
    ),
    // 精魄辅助推荐 Top 5
    topTests.length > 0 && h('div', null,
      h('div', { className: 'chart-title' }, h('span', { className: 'dot' }), '\u7CBE\u9B42\u8F85\u52A9\u63A8\u8350 Top ' + topTests.length),
      h('table', null,
        h('thead', null, h('tr', null,
          h('th', null, '\u8F85\u52A9'), h('th', null, '\u76EE\u6807\u5149\u73AF'), h('th', null, 'DPS'), h('th', null, '\u7CBE\u9B42')
        )),
        h('tbody', null,
          topTests.map(function(t, i) {
            return h('tr', { key: i },
              h('td', null, t.name || ''),
              h('td', { style: { color: '#a0a0b8' } }, t.target_aura || ''),
              h('td', { style: { color: '#55c078' } }, fmtSign(t.dps_pct || 0)),
              h('td', null, Math.round(t.spirit || 0))
            );
          })
        )
      )
    )
  );
}

// ── Talent Scatter ──
function TalentScatter({ talents }) {
  if (!talents || talents.length === 0) return null;
  const data = talents.filter(t => Math.abs(t.dps_pct) > 0.01 || Math.abs(t.ehp_pct) > 0.01)
    .map(t => ({
      name: t.name, type: t.type, x: t.dps_pct, y: t.ehp_pct,
      category: t.category || '无效', color: CATEGORY_COLORS[t.category] || CATEGORY_COLORS['无效']
    }));

  if (data.length === 0) return null;
  const CustomTooltip = ({ active, payload }) => {
    if (!active || !payload || !payload[0]) return null;
    const d = payload[0].payload;
    return h('div', { style: { background: '#252540', border: '1px solid #2e2e4a', borderRadius: 6, padding: '8px 12px', fontSize: 13 } },
      h('div', { style: { fontWeight: 600, color: d.color } }, d.name, ' (', d.type, ')'),
      h('div', null, 'DPS: ', h('span', { style: { color: '#e8e8f0' } }, fmtSign(d.x))),
      h('div', null, 'EHP: ', h('span', { style: { color: '#e8e8f0' } }, fmtSign(d.y))),
      h('div', { style: { color: '#a0a0b8', fontSize: 11 } }, d.category)
    );
  };

  return h('div', { className: 'chart-box' },
    h('div', { className: 'chart-title' }, h('span', { className: 'dot' }), '天赋价值矩阵'),
    h(ResponsiveContainer, { width: '100%', height: 300 },
      h(ScatterChart, { margin: { top: 5, right: 20, left: 10, bottom: 5 } },
        h(CartesianGrid, { strokeDasharray: '3 3', stroke: '#2e2e4a' }),
        h(XAxis, { dataKey: 'x', tick: { fill: '#6e6e88', fontSize: 11 }, tickFormatter: v => fmtSign(v, 0), label: { value: 'DPS%', position: 'insideBottom', offset: -2, fill: '#a0a0b8', fontSize: 11 } }),
        h(YAxis, { dataKey: 'y', tick: { fill: '#6e6e88', fontSize: 11 }, tickFormatter: v => fmtSign(v, 0), label: { value: 'EHP%', angle: -90, position: 'insideLeft', fill: '#a0a0b8', fontSize: 11 } }),
        h(Tooltip, { content: CustomTooltip }),
        h(Scatter, { data, fill: '#d4a843', opacity: 0.8 })
      )
    )
  );
}

// ── Defence Radar (SVG) ──
function DefenceRadar({ baseline }) {
  if (!baseline) return null;
  const metrics = [
    { key: 'Life', max: 5000, value: baseline.Life || 0 },
    { key: 'ES', max: 3000, value: baseline.EnergyShield || 0 },
    { key: 'Evasion', max: 10000, value: baseline.MeleeEvasion || 0 },
    { key: 'Armour', max: 20000, value: baseline.ArmourDefense || 0 },
    { key: 'EHP', max: 15000, value: baseline.TotalEHP || 0 },
    { key: 'Mana', max: 3000, value: baseline.Mana || 0 },
  ];
  const n = metrics.length;
  const cx = 140, cy = 130, r = 90;
  const levels = [0.25, 0.5, 0.75, 1.0];
  const angle = (i) => (Math.PI * 2 * i / n) - Math.PI / 2;

  return h('div', { className: 'chart-box', style: { display: 'flex', flexDirection: 'column', alignItems: 'center' } },
    h('div', { className: 'chart-title' }, h('span', { className: 'dot' }), '防御属性雷达图'),
    h('svg', { width: 300, height: 280, viewBox: '0 0 300 280' },
      // Grid
      levels.map(lv => {
        const pts = [];
        for (let i = 0; i < n; i++) {
          const a = angle(i);
          pts.push(`${cx + Math.cos(a) * r * lv},${cy + Math.sin(a) * r * lv}`);
        }
        return h('polygon', { key: lv, points: pts.join(' '), fill: 'none', stroke: '#2e2e4a', strokeWidth: 1 });
      }),
      // Axes
      metrics.map((m, i) => {
        const a = angle(i);
        const x2 = cx + Math.cos(a) * r;
        const y2 = cy + Math.sin(a) * r;
        return h('line', { key: m.key, x1: cx, y1: cy, x2, y2, stroke: '#2e2e4a', strokeWidth: 1 });
      }),
      // Data polygon
      (() => {
        const pts = metrics.map((m, i) => {
          const a = angle(i);
          const val = Math.min(m.value / m.max, 1);
          return `${cx + Math.cos(a) * r * val},${cy + Math.sin(a) * r * val}`;
        });
        return h('polygon', { points: pts.join(' '), fill: 'rgba(212,168,67,0.15)', stroke: '#d4a843', strokeWidth: 2 });
      })(),
      // Data points + labels
      metrics.map((m, i) => {
        const a = angle(i);
        const val = Math.min(m.value / m.max, 1);
        const px = cx + Math.cos(a) * r * val;
        const py = cy + Math.sin(a) * r * val;
        const lx = cx + Math.cos(a) * (r + 22);
        const ly = cy + Math.sin(a) * (r + 22);
        const anchor = Math.abs(Math.cos(a)) < 0.1 ? 'middle' : (Math.cos(a) > 0 ? 'start' : 'end');
        return h('g', { key: m.key },
          h('circle', { cx: px, cy: py, r: 4, fill: '#d4a843' }),
          h('text', { x: lx, y: ly + 4, textAnchor: anchor, fill: '#a0a0b8', fontSize: 11 },
            m.key, ' (', Math.round(m.value).toLocaleString(), ')')
        );
      })
    )
  );
}

// ── Detail Tables ──
function DetailSection({ title, children, defaultOpen }) {
  return h('details', { open: defaultOpen },
    h('summary', null, title),
    h('div', { className: 'detail-content' }, children)
  );
}

function TalentValueTable({ talents }) {
  if (!talents) return null;
  return h(DetailSection, { title: `天赋价值 (${talents.length})`, defaultOpen: false },
    h('table', null,
      h('thead', null, h('tr', null, h('th', null, '名称'), h('th', null, '类型'), h('th', null, 'DPS%'), h('th', null, 'EHP%'), h('th', null, '分类'))),
      h('tbody', null,
        [...talents].sort((a, b) => a.dps_pct - b.dps_pct).map(t =>
          h('tr', { key: t.id || t.name },
            h('td', null, t.name),
            h('td', null, t.type),
            h('td', { style: { color: t.dps_pct >= 0 ? '#55c078' : '#e05555' } }, fmtSign(t.dps_pct)),
            h('td', { style: { color: t.ehp_pct >= 0 ? '#55c078' : '#e05555' } }, fmtSign(t.ehp_pct)),
            h('td', null, h('span', { style: { color: CATEGORY_COLORS[t.category] || '#a0a0b8' } }, t.category))
          )
        )
      )
    )
  );
}

function SensitivityTable({ sensitivity }) {
  if (!sensitivity) return null;
  return h(DetailSection, { title: `灵敏度分析 (${sensitivity.length})`, defaultOpen: false },
    h('table', null,
      h('thead', null, h('tr', null, h('th', null, '维度'), h('th', null, '类型'), h('th', null, '所需'), h('th', null, 'DPS/单位'), h('th', null, '公式'))),
      h('tbody', null, sensitivity.map((s, i) =>
        h('tr', { key: i },
          h('td', null, s.label),
          h('td', null, s.mod_type),
          h('td', null, s.needed_value != null ? fmt(s.needed_value, 1) + (s.unit || '') : '—'),
          h('td', null, s.dps_per_unit ? s.dps_per_unit.toFixed(3) + '%' : '—'),
          h('td', { style: { color: '#a0a0b8', fontSize: 11 } }, s.formula || '')
        )
      ))
    )
  );
}

function TalentExplorationTable({ talents }) {
  if (!talents || talents.length === 0) return null;

  // 分离输出和生存节点
  var offence = talents.filter(function(t) {
    return t.category === '\u8f93\u51fa' || t.category === '\u517c\u987e';
  }).sort(function(a, b) { return b.dps_pct - a.dps_pct; }).slice(0, 10);

  var defence = talents.filter(function(t) {
    return t.category === '\u751f\u5b58' || t.category === '\u517c\u987e';
  }).sort(function(a, b) { return b.ehp_pct - a.ehp_pct; }).slice(0, 10);

  // 去重：已在输出榜的兼顾节点不重复出现在生存榜
  var offenceIds = new Set(offence.map(function(t) { return t.id; }));
  var defenceFiltered = defence.filter(function(t) {
    return !(t.category === '\u517c\u987e' && offenceIds.has(t.id));
  }).slice(0, 10);

  function makeTable(title, items, sortKey) {
    if (items.length === 0) return null;
    return h(DetailSection, { title: title, defaultOpen: false },
      h('table', null,
        h('thead', null, h('tr', null, h('th', null, '\u540d\u79f0'), h('th', null, '\u7c7b\u578b'), h('th', null, 'DPS%'), h('th', null, 'EHP%'))),
        h('tbody', null,
          items.map(function(t) {
            return h('tr', { key: t.id || t.name },
              h('td', null, t.name),
              h('td', { style: { color: '#6e6e88', fontSize: 11 } }, t.type),
              h('td', { style: { color: '#55c078' } }, fmtSign(t.dps_pct)),
              h('td', { style: { color: t.ehp_pct >= 0 ? '#55c078' : '#e05555' } }, fmtSign(t.ehp_pct))
            );
          })
        )
      )
    );
  }

  return h('div', null,
    h('div', { style: { color: '#6e6e88', fontSize: 11, marginBottom: 4 } },
      '\u603b\u5019\u9009 ' + talents.length + ' \u4e2a\uff0c\u5206\u522b\u5c55\u793a\u8fdb\u653b/\u9632\u5fa1 TOP 10'),
    makeTable('\u8f93\u51fa TOP 10', offence, 'dps_pct'),
    makeTable('\u751f\u5b58 TOP 10', defenceFiltered, 'ehp_pct')
  );
}

function JewelDiagnosisTable({ jewels }) {
  if (!jewels || jewels.length === 0) return null;
  var sorted = jewels.slice().sort(function(a, b) { return Math.abs(b.dps_pct || 0) - Math.abs(a.dps_pct || 0); });
  var gridStyle = { display: 'grid', gridTemplateColumns: '180px 100px 70px 70px 50px', gap: '8px', alignItems: 'center' };
  var headerStyle = { color: '#6e6e88', fontSize: 11, fontWeight: 600, padding: '4px 0' };
  var cellStyle = { padding: '3px 0' };
  
  return h(DetailSection, { title: '\u73e0\u5b9d\u8bca\u65ad (' + jewels.length + ')', defaultOpen: false },
    h('div', { style: { display: 'flex', flexDirection: 'column', gap: 0 } },
      // Header
      h('div', { style: Object.assign({}, gridStyle, { borderBottom: '1px solid rgba(46,46,74,0.4)' }) },
        h('span', { style: headerStyle }, '\u540d\u79f0'),
        h('span', { style: headerStyle }, '\u7c7b\u578b'),
        h('span', { style: Object.assign({}, headerStyle, { textAlign: 'right' }) }, 'DPS%'),
        h('span', { style: Object.assign({}, headerStyle, { textAlign: 'right' }) }, 'EHP%'),
        h('span', { style: Object.assign({}, headerStyle, { textAlign: 'right' }) }, '\u8bcd')
      ),
      sorted.map(function(j, i) {
        var mods = j.mods || [];
        var dpsTotal = j.dps_pct || 0;
        var ehpTotal = 0;
        mods.forEach(function(m) { ehpTotal += (m.ehp_pct || 0); });
        var rarityColor = j.rarity === 'UNIQUE' ? '#d4a843' : '#a0a0b8';
        var hasMods = mods.length > 0;
        return h('div', { key: i },
          // Summary row
          h('div', { style: Object.assign({}, gridStyle, { borderBottom: '1px solid rgba(46,46,74,0.2)', padding: '4px 0' }) },
            h('span', { style: Object.assign({}, cellStyle, { color: rarityColor, fontSize: 12, fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }) }, j.name || '\u2014'),
            h('span', { style: Object.assign({}, cellStyle, { color: '#6e6e88', fontSize: 11, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }) }, (j.base_type || '') + ' \u00b7 ' + (j.slot_name || '')),
            h('span', { style: Object.assign({}, cellStyle, { textAlign: 'right', color: '#55c078', fontFamily: 'monospace', fontSize: 12 }) }, fmtSign(dpsTotal)),
            h('span', { style: Object.assign({}, cellStyle, { textAlign: 'right', color: ehpTotal > 0.01 ? '#44bbcc' : '#6e6e88', fontFamily: 'monospace', fontSize: 12 }) }, fmtSign(ehpTotal)),
            h('span', { style: Object.assign({}, cellStyle, { textAlign: 'right', color: '#555570', fontSize: 10 }) }, hasMods ? mods.length : '')
          ),
          // Mod details - same grid layout (no paddingLeft, use prefix in first column)
          hasMods && h('div', { style: { borderBottom: '1px solid rgba(46,46,74,0.15)' } },
            mods.map(function(m, mi) {
              var dpsVal = m.dps_pct || 0;
              var ehpVal = m.ehp_pct || 0;
              var suffix = (m.type === 'INC') ? '%' : '';
              var hasImpact = dpsVal > 0.01 || ehpVal > 0.01;
              return h('div', { key: mi, style: Object.assign({}, gridStyle, { padding: '2px 0', background: 'rgba(46,46,74,0.05)' }) },
                h('span', { style: { color: hasImpact ? '#c0c0d0' : '#555570', fontSize: 11, paddingLeft: 12, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' } }, '\u2022 ' + m.name),
                h('span', { style: { color: '#e8e8f0', fontFamily: 'monospace', fontSize: 11 } }, '+' + m.value + suffix + ' ' + (m.type || '')),
                h('span', { style: { textAlign: 'right', color: dpsVal > 0.01 ? '#55c078' : '#444460', fontFamily: 'monospace', fontSize: 11 } }, dpsVal > 0.01 ? '+' + dpsVal.toFixed(2) + '%' : '-'),
                h('span', { style: { textAlign: 'right', color: ehpVal > 0.01 ? '#44bbcc' : '#444460', fontFamily: 'monospace', fontSize: 11 } }, ehpVal > 0.01 ? '+' + ehpVal.toFixed(2) + '%' : '-'),
                h('span', null)
              );
            })
          )
        );
      })
    )
  );
}

// ── Main App ──
function App() {
  const weaponSets = (BUILD_META && BUILD_META.weapon_sets) || [1];
  const hasWS2 = weaponSets.length > 1 && WS2_SKILLS_DATA && Object.keys(WS2_SKILLS_DATA).length > 0;
  const [activeWS, setActiveWS] = useState(1);

  // 根据当前套装选择数据源
  const currentSkillsData = activeWS === 2 && hasWS2 ? WS2_SKILLS_DATA : SKILLS_DATA;
  const skillNames = useMemo(() => Object.keys(currentSkillsData || {}), [activeWS]);
  const [activeTab, setActiveTab] = useState(skillNames[0] || '');

  // 套装切换时重置技能 tab
  const switchWS = function(ws) {
    setActiveWS(ws);
    var sd = ws === 2 ? WS2_SKILLS_DATA : SKILLS_DATA;
    var names = Object.keys(sd || {});
    setActiveTab(names[0] || '');
  };

  // 当前技能 tab 不存在时回退
  var data = currentSkillsData[activeTab] || currentSkillsData[skillNames[0]] || {};

  const metaTitle = BUILD_META
    ? (BUILD_META.class_name || '') + ' ' + (BUILD_META.ascendancy || '') + ' Lv' + (BUILD_META.level || '')
    : 'POB Build Analysis';

  var bl = data.baseline || {};
  var skillDps = Math.round(bl.TotalDPS || 0);
  var avgHit = Math.round(bl.AverageHit || 0);
  var speed = bl.Speed || 0;
  var cc = bl.CritChance || 0;
  var cm = bl.CritMultiplier || 0;

  return h('div', null,
    // Header
    h('div', { className: 'header' },
      h('h1', null, metaTitle),
      BUILD_META ? h('div', { className: 'subtitle' }, 'Build ID: ', BUILD_META.build_id) : null
    ),
    // Weapon Set tabs (only show if has WS2)
    hasWS2 && h('div', { className: 'tabs', style: { marginBottom: 4, borderBottom: '2px solid #555' } },
      weaponSets.map(function(ws) {
        return h('div', {
          key: 'ws' + ws,
          className: 'tab' + (activeWS === ws ? ' active' : ''),
          style: { fontWeight: 'bold', fontSize: 14 },
          onClick: function() { switchWS(ws); }
        }, '\u2694\uFE0F Weapon Set ' + ws);
      })
    ),
    // Comparison panel
    activeWS === 'cmp' && COMPARISON_DATA ? h(ComparisonPanel, { data: COMPARISON_DATA }) :
    h('div', null,
      // Global section (does not change with skill tabs)
      h(GlobalBaselineSection, { activeWS: activeWS }),
      // Skill tabs
      h('div', { className: 'tabs' },
        skillNames.map(function(name) {
          return h('div', {
            key: name,
            className: 'tab' + (activeTab === name ? ' active' : ''),
            onClick: function() { setActiveTab(name); }
          }, name.charAt(0).toUpperCase() + name.slice(1).replace('_', ' '));
        })
      ),
      // Skill KPI cards (per-tab)
      h('div', { className: 'kpi-row' },
        [
          { label: 'TotalDPS', value: fmtComma(skillDps), warn: false },
          { label: 'AverageHit', value: fmtComma(avgHit), warn: false },
          { label: 'Speed', value: fmt(speed, 2) + '/s', warn: false },
          { label: 'CritChance', value: fmt(cc, 1) + '%', warn: false },
          { label: 'CritMultiplier', value: fmt(cm, 2) + 'x', warn: false },
        ].map(function(k) {
          return h('div', { className: 'kpi-card', key: k.label },
            h('div', { className: 'label' }, k.label),
            h('div', { className: 'value' + (k.warn ? ' warn' : '') }, k.value)
          );
        })
      ),
      // Skill-specific sections
      h(DamagePieChart, { data: data.dps_breakdown }),
      h(DPSFlowTable, { data: data.dps_breakdown }),
      h(FormulaBreakdown, { data: data.dps_breakdown }),
      h('div', { className: 'chart-grid' },
        h(SensitivityChart, { sensitivity: data.sensitivity }),
        h(AuraChart, { auras: (data.aura_spirit || {}).existing_auras }),
        h(CandidateAurasTable, { aura_spirit: data.aura_spirit || {}, baseline: data.baseline || {} }),
        h(TalentScatter, { talents: data.talent_value }),
        h(DefenceRadar, { baseline: data.baseline })
      ),
      h(TalentValueTable, { talents: data.talent_value }),
      h(SensitivityTable, { sensitivity: data.sensitivity }),
      h(TalentExplorationTable, { talents: data.talent_exploration }),
      h(JewelDiagnosisTable, { jewels: data.jewel_diagnosis })
    )
  );
}

// Comparison panel component
function ComparisonPanel({ data }) {
  if (!data) return null;
  var d = data.defence || {};
  var r = data.resource || {};
  var skills = data.skills || {};
  var shared = data.shared_skills || [];
  var ws1Only = data.ws1_only_skills || [];
  var ws2Only = data.ws2_only_skills || [];

  return h('div', { style: { padding: 20 } },
    h('h2', null, '\u2694\uFE0F Weapon Set Comparison'),
    // Defence comparison
    h('div', { className: 'chart-box full-width' },
      h('h3', null, 'Defence'),
      h('table', null,
        h('thead', null, h('tr', null,
          h('th', null, ''), h('th', null, 'WS1'), h('th', null, 'WS2'), h('th', null, 'Delta')
        )),
        h('tbody', null,
          h('tr', null,
            h('td', null, 'EHP'),
            h('td', null, fmtComma(Math.round(d.ehp_ws1 || 0))),
            h('td', null, fmtComma(Math.round(d.ehp_ws2 || 0))),
            h('td', { style: { color: (d.delta_pct || 0) >= 0 ? '#66bb6a' : '#ff5252' } },
              (d.delta_pct >= 0 ? '+' : '') + fmt(d.delta_pct || 0, 1) + '%')
          ),
          h('tr', null,
            h('td', null, 'Spirit'),
            h('td', null, Math.round(r.spirit_ws1 || 0)),
            h('td', null, Math.round(r.spirit_ws2 || 0)),
            h('td', null, '')
          )
        )
      )
    ),
    // Skill DPS comparison
    shared.length > 0 && h('div', { className: 'chart-box full-width' },
      h('h3', null, 'Shared Skills DPS'),
      h('table', null,
        h('thead', null, h('tr', null,
          h('th', null, 'Skill'), h('th', null, 'WS1 DPS'), h('th', null, 'WS2 DPS'), h('th', null, 'Delta')
        )),
        h('tbody', null,
          shared.map(function(name) {
            var s = skills[name] || {};
            return h('tr', { key: name },
              h('td', null, name),
              h('td', null, fmtComma(Math.round(s.dps_ws1 || 0))),
              h('td', null, fmtComma(Math.round(s.dps_ws2 || 0))),
              h('td', { style: { color: (s.delta_pct || 0) >= 0 ? '#66bb6a' : '#ff5252' } },
                (s.delta_pct >= 0 ? '+' : '') + fmt(s.delta_pct || 0, 1) + '%')
            );
          })
        )
      )
    ),
    // WS-exclusive skills
    ws1Only.length > 0 && h('div', { className: 'chart-box' },
      h('h3', null, 'WS1 Only'), h('p', null, ws1Only.join(', '))
    ),
    ws2Only.length > 0 && h('div', { className: 'chart-box' },
      h('h3', null, 'WS2 Only'), h('p', null, ws2Only.join(', '))
    )
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(h(App));
</script>
</body>
</html>"""


def main():
    parser = argparse.ArgumentParser(description="Generate HTML report from analysis data")
    parser.add_argument("--build-id", required=True, help="Build ID")
    parser.add_argument("--skills", nargs="+", help="Skill names (lowercase, underscore)")
    parser.add_argument("--output", help="Output path (default: auto)")
    args = parser.parse_args()

    html = generate_html_report(args.build_id, args.skills)
    if html is None:
        print(f"Error: Build '{args.build_id}' not found or no analysis data")
        sys.exit(1)

    if args.output:
        out_path = Path(args.output)
    else:
        out_path = CACHE_DIR / args.build_id / "report.html"

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    print(f"Report generated: {out_path}")


if __name__ == "__main__":
    main()
