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

CACHE_DIR = Path(__file__).parent.parent.parent.parent / ".codebuddy" / "cache" / "pob-build-analyzer" / "builds"

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


def _merge_enemy_zone(skill_data: dict) -> bool:
    """对旧格式缓存做敌人乘区后处理合并。

    旧缓存可能包含按元素展开的 Enemy_{dt}_DamageTaken_mult 和 {dt}_EffMult，
    需要合并为 Enemy_DamageTaken_mult 和 EffMult_weighted。
    返回是否修改了数据。
    """
    db = skill_data.get("dps_breakdown", {})
    if not db:
        return False
    items = db.get("formula_items", [])
    if not items:
        return False

    DT_NAMES = {"Lightning", "Cold", "Fire", "Physical", "Chaos"}
    changed = False

    # 1. 合并 DamageTaken
    dt_entries = {}
    for fi in items:
        key = fi["key"]
        if key.startswith("Enemy_") and key.endswith("_DamageTaken_mult"):
            dt = key[len("Enemy_"):-len("_DamageTaken_mult")]
            if dt in DT_NAMES:
                dt_entries[dt] = fi

    if len(dt_entries) >= 2:
        values = [fi["total_value"] for fi in dt_entries.values()]
        if max(values) - min(values) < 0.001:
            merged_value = values[0]
            seen = set()
            merged_sources = []
            for fi in dt_entries.values():
                for s in fi.get("sources", []):
                    src_key = (s.get("source", ""), s.get("mod_name", ""))
                    if src_key not in seen:
                        seen.add(src_key)
                        merged_sources.append(s)
            to_remove = {fi["key"] for fi in dt_entries.values()}
            db["formula_items"] = [fi for fi in items if fi["key"] not in to_remove]
            db["formula_items"].append({
                "key": "Enemy_DamageTaken_mult",
                "formula_name": "敌人受伤增加",
                "total_value": merged_value,
                "display_value": f"x{merged_value:.4f}",
                "category_summary": {},
                "sources": merged_sources,
                "formula_detail": f"所有伤害类型共享 x{merged_value:.4f}",
            })
            items = db["formula_items"]
            changed = True

    # 2. 合并 EffMult 为加权
    dc = db.get("damage_composition", [])
    eff_entries = {}
    for fi in items:
        key = fi["key"]
        if key.endswith("_EffMult") and key != "EffMult_weighted":
            dt = key[:-len("_EffMult")]
            if dt in DT_NAMES:
                eff_entries[dt] = fi
            elif dt == "Enemy":
                # 旧格式全局 EffMult（如 Enemy_EffMult），直接重命名为 EffMult_weighted
                fi["key"] = "EffMult_weighted"
                fi["formula_name"] = "敌人抗性乘区"
                changed = True

    if len(eff_entries) >= 2 and dc:
        # hit_avg 已包含 EffMult，用 pre-EffMult 伤害作为权重
        pre_eff_map = {}
        for e in dc:
            elem = e.get("element", "")
            if elem in eff_entries:
                eff_val = eff_entries[elem]["total_value"]
                pre_eff_map[elem] = e.get("hit_avg", 0) / eff_val if eff_val > 0 else 0
        total_pre_eff = sum(pre_eff_map.values())
        if total_pre_eff > 0:
            weight_map = {elem: pre_eff / total_pre_eff for elem, pre_eff in pre_eff_map.items()}
            if weight_map:
                weighted = 0.0
                sources = []
                mod_sources = []
                seen_mods = set()
                for dt, weight in sorted(weight_map.items(), key=lambda x: -x[1]):
                    eff_fi = eff_entries[dt]
                    eff_val = eff_fi["total_value"]
                    weighted += eff_val * weight
                    dt_label = {"Lightning": "闪电", "Cold": "冰霜", "Fire": "火焰",
                                "Physical": "物理", "Chaos": "混沌"}.get(dt, dt)
                    detail = eff_fi.get("formula_detail", "")
                    sources.append({
                        "source": dt,
                        "label": f"{dt_label} x{eff_val:.4f} (占{weight*100:.1f}%)",
                        "category": "Enemy",
                        "value": eff_val,
                        "weight_pct": round(weight * 100, 1),
                        "formula_detail": detail,
                    })
                    # 聚合 mod sources（穿透/减抗来源）
                    for s in eff_fi.get("sources", []):
                        src_key = (s.get("source", ""), s.get("mod_name", ""))
                        if src_key not in seen_mods:
                            seen_mods.add(src_key)
                            mod_sources.append({
                                "source": s.get("source", ""),
                                "mod_name": s.get("mod_name", ""),
                                "category": s.get("category", "Other"),
                                "value": s.get("value", 0),
                                "element": dt_label,
                            })
                to_remove = {fi["key"] for fi in eff_entries.values()}
                db["formula_items"] = [fi for fi in items if fi["key"] not in to_remove]
                # 旧格式 total_value 是绝对 effMult，需转换为增益百分比
                # 加权基础乘区 = 各元素 (1 - originalResist/100) 的加权平均
                # originalResist = 反转前的抗性值
                weighted_base = 0.0
                for dt_val, weight in sorted(weight_map.items(), key=lambda x: -x[1]):
                    # 从 per-element source 的 formula_detail 提取 original resist
                    eff_fi = eff_entries[dt_val]
                    resist_val = 0
                    invert_chance = eff_fi.get("_invert_chance", 0)
                    for s in eff_fi.get("sources", []):
                        if s.get("mod_name", "").endswith("Resist"):
                            resist_val = s.get("value", 0)
                            break
                    # resist_val 已是反转后的值，需要恢复原始值用于 base 计算
                    # 原始抗性: original_resist = resist / (1 - 2*invertChance)
                    original_resist = resist_val
                    if invert_chance > 0 and abs(1 - 2 * invert_chance) > 0.001:
                        original_resist = resist_val / (1 - 2 * invert_chance)
                    weighted_base += (1 - original_resist / 100) * weight
                if abs(weighted_base) > 0.001:
                    weighted_gain_pct = (weighted / weighted_base - 1) * 100
                else:
                    weighted_gain_pct = 0.0

                rep_detail = sources[0].get("formula_detail", "") if sources else ""
                # 检查是否有抗性反转
                has_invert = any(s.get("category") == "ResistInvert" for s in mod_sources)
                if has_invert:
                    invert_info_parts = []
                    pen_info_parts = []
                    for ms in mod_sources:
                        if ms.get("category") == "ResistInvert":
                            invert_info_parts.append(f"{ms.get('element', '')} {ms.get('value', 0):.0f}%")
                        elif ms.get("category") == "Penetration":
                            pen_info_parts.append(f"{ms.get('element', '')} +{ms.get('value', 0):.0f}%")
                    rep_detail = "抗性反转: " + ", ".join(invert_info_parts)
                    if pen_info_parts:
                        rep_detail += "  |  穿透: " + ", ".join(pen_info_parts) + " (无效: 抗性≤0)"
                elif not rep_detail:
                    rep_detail = f"按伤害构成加权: +{weighted_gain_pct:.1f}%"
                db["formula_items"].append({
                    "key": "EffMult_weighted",
                    "formula_name": "敌人抗性乘区 (加权)",
                    "total_value": weighted_gain_pct,
                    "display_value": f"+{weighted_gain_pct:.1f}%",
                    "_eff_mult_abs": weighted,
                    "category_summary": {s.get("category", "Other"): s.get("value", 0) for s in mod_sources},
                    "sources": sources,
                    "mod_sources": mod_sources,
                    "formula_detail": rep_detail or f"按伤害构成加权: +{weighted_gain_pct:.1f}%",
                })
                db["eff_mult_weighted"] = weighted_gain_pct
                changed = True

    return changed


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
    # 关键：如果 ws1/skills/ 数据缺少 dps_breakdown 新字段（如 crit_chance），
    # 从扁平 analysis_*.json 回退补全 dps_breakdown，最终从 baseline 提取
    # 补全后写回磁盘，确保数据源头正确，避免每次生成 HTML 都需重新修补
    _BASELINE_TO_DB_MAP = {
        "crit_chance": "CritChance",
        "crit_multiplier": "CritMultiplier",
        "speed": "Speed",
    }

    def _backfill_dps_breakdown(skill_data: dict, flat_data: dict = None):
        """补全 dps_breakdown 中缺失的字段。
        crit_chance/crit_multiplier/speed 始终从自身 baseline 映射（每个技能/套装独立），
        即使已存在也以 baseline 为准修正。
        dps_flow_stages/damage_composition 从 flat_data.dps_breakdown 补全。"""
        db = skill_data.get("dps_breakdown", {})
        if not db:
            return False
        changed = False
        # 第一步：crit_chance/crit_multiplier/speed 始终从自身 baseline 映射
        # 这些值是每个技能+套装组合独立的，不能用其他套装的 flat_data 覆盖
        bl = skill_data.get("baseline", {})
        for db_key, bl_key in _BASELINE_TO_DB_MAP.items():
            if bl_key in bl:
                expected = bl[bl_key]
                current = db.get(db_key)
                if current is None or (isinstance(expected, (int, float))
                                       and isinstance(current, (int, float))
                                       and abs(expected - current) > 0.01):
                    db[db_key] = expected
                    changed = True
        # 第二步：结构型字段从 flat_data.dps_breakdown 补全
        if flat_data:
            flat_db = flat_data.get("dps_breakdown", {})
            for new_key in ("dps_flow_stages", "damage_composition"):
                if new_key in flat_db and new_key not in db:
                    db[new_key] = flat_db[new_key]
                    changed = True
            # 第三步：敌人乘区从 flat_data 覆盖旧格式条目
            # flat_data（full_analysis 产出）有正确的合并后数据，
            # ws1 数据（full_build_analysis 产出）可能有旧格式或错误值
            _ENEMY_KEYS = {"Enemy_DamageTaken_mult", "EffMult_weighted"}
            flat_enemy_items = [fi for fi in flat_db.get("formula_items", [])
                                if fi["key"] in _ENEMY_KEYS]
            if flat_enemy_items:
                # 移除 db 中所有敌人乘区条目（旧格式 + _merge_enemy_zone 产生的）
                db["formula_items"] = [
                    fi for fi in db.get("formula_items", [])
                    if not (fi["key"].startswith("Enemy_") or fi["key"].endswith("_EffMult"))
                ]
                # 注入 flat_data 的正确条目（去重）
                existing_keys = {fi["key"] for fi in db["formula_items"]}
                for fi in flat_enemy_items:
                    if fi["key"] not in existing_keys:
                        db["formula_items"].append(fi)
                        existing_keys.add(fi["key"])
                if "eff_mult_weighted" in flat_db:
                    db["eff_mult_weighted"] = flat_db["eff_mult_weighted"]
                changed = True
        return changed

    skills_data = {}
    if skills is None:
        # 自动发现：ws1/skills/ 优先，扁平路径回退
        ws1_skills_dir = build_dir / "ws1" / "skills"
        if ws1_skills_dir.exists():
            for f in ws1_skills_dir.glob("*.json"):
                try:
                    d = json.loads(f.read_text(encoding="utf-8"))
                    display = d.get("display_name") or f.stem
                    if d and ws1_global:
                        for gk in ("aura_spirit", "jewel_diagnosis"):
                            if gk not in d and gk in ws1_global:
                                d[gk] = ws1_global[gk]
                    # 补全 dps_breakdown 新字段
                    flat_path = build_dir / f"analysis_{f.stem}.json"
                    flat_d = None
                    if flat_path.exists():
                        try:
                            flat_d = json.loads(flat_path.read_text(encoding="utf-8"))
                        except (json.JSONDecodeError, OSError):
                            pass
                    # 先清理旧格式敌人乘区，再从 flat_data 补全正确数据
                    _merge_enemy_zone(d)
                    if _backfill_dps_breakdown(d, flat_d):
                        # 写回磁盘，避免每次都需要修补
                        try:
                            f.write_text(json.dumps(d, ensure_ascii=False, default=str),
                                         encoding="utf-8")
                        except OSError:
                            pass
                    elif _backfill_dps_breakdown(d, flat_d):
                        try:
                            f.write_text(json.dumps(d, ensure_ascii=False, default=str),
                                         encoding="utf-8")
                        except OSError:
                            pass
                    skills_data[display] = d
                except (json.JSONDecodeError, OSError):
                    pass
        if not skills_data:
            # 回退到扁平格式
            for f in build_dir.glob("analysis_*.json"):
                skill_slug = f.stem.replace("analysis_", "")
                data = _load_analysis(build_dir, skill_slug)
                if data is not None:
                    _merge_enemy_zone(data)
                    _backfill_dps_breakdown(data)
                    display = data.get("display_name") or skill_slug
                    skills_data[display] = data
    else:
        # 指定技能列表
        for skill in skills:
            data = _load_analysis(build_dir, skill)
            if data is None:
                ws1_path = build_dir / "ws1" / "skills" / f"{skill}.json"
                if ws1_path.exists():
                    try:
                        data = json.loads(ws1_path.read_text(encoding="utf-8"))
                        if data and ws1_global:
                            for gk in ("aura_spirit", "jewel_diagnosis"):
                                if gk not in data and gk in ws1_global:
                                    data[gk] = ws1_global[gk]
                        # 补全 dps_breakdown 新字段
                        flat_path = build_dir / f"analysis_{skill}.json"
                        flat_d = None
                        if flat_path.exists():
                            try:
                                flat_d = json.loads(flat_path.read_text(encoding="utf-8"))
                            except (json.JSONDecodeError, OSError):
                                pass
                        _merge_enemy_zone(data)
                        if _backfill_dps_breakdown(data, flat_d):
                            try:
                                ws1_path.write_text(
                                    json.dumps(data, ensure_ascii=False, default=str),
                                    encoding="utf-8")
                            except OSError:
                                pass
                        elif _backfill_dps_breakdown(data):
                            try:
                                ws1_path.write_text(
                                    json.dumps(data, ensure_ascii=False, default=str),
                                    encoding="utf-8")
                            except OSError:
                                pass
                    except (json.JSONDecodeError, OSError):
                        pass
            if data is not None:
                _merge_enemy_zone(data)
                _backfill_dps_breakdown(data)
                display = data.get("display_name") or skill
                skills_data[display] = data

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
                ws2_skill = json.loads(f.read_text(encoding="utf-8"))
                display = ws2_skill.get("display_name") or f.stem
                # 同样补全 dps_breakdown 新字段
                flat_path = build_dir / f"analysis_{f.stem}.json"
                flat_d = None
                if flat_path.exists():
                    try:
                        flat_d = json.loads(flat_path.read_text(encoding="utf-8"))
                    except (json.JSONDecodeError, OSError):
                        pass
                _merge_enemy_zone(ws2_skill)
                if _backfill_dps_breakdown(ws2_skill, flat_d):
                    try:
                        f.write_text(json.dumps(ws2_skill, ensure_ascii=False, default=str),
                                     encoding="utf-8")
                    except OSError:
                        pass
                elif _backfill_dps_breakdown(ws2_skill):
                    try:
                        f.write_text(json.dumps(ws2_skill, ensure_ascii=False, default=str),
                                     encoding="utf-8")
                    except OSError:
                        pass
                ws2_skills_data[display] = ws2_skill
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
  --bg-primary: #1e1f26;
  --bg-card: #282a33;
  --bg-elevated: #32353f;
  --text-primary: #f0f1f3;
  --text-secondary: #a8abb5;
  --text-muted: #6c6f7e;
  --accent: #5b9aff;
  --accent-light: rgba(91, 154, 255, 0.12);
  --accent-hover: #7ab3ff;
  --border: rgba(255,255,255,0.07);
  --border-light: rgba(255,255,255,0.04);
  --red: #ff6b6b;
  --green: #5bda6e;
  --orange: #ffa94d;
  --purple: #b197fc;
  --cyan: #66d9e8;
  --yellow: #ffe066;
  --radius: 8px;
  --radius-lg: 12px;
}
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
  background-color: var(--bg-primary);
  color: var(--text-primary);
  line-height: 1.5;
  padding: 24px 32px;
  min-height: 100vh;
  min-width: 0;
}
@media (max-width: 900px) {
  body { padding: 16px; }
}

.header {
  text-align: left;
  margin-bottom: 28px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--border);
}
.header h1 {
  font-size: 26px;
  font-weight: 800;
  color: #fff;
  margin-bottom: 4px;
}
.header .subtitle {
  color: var(--text-muted);
  font-size: 14px;
}

/* 标签风格 */
.tabs {
  display: flex;
  gap: 10px;
  margin-bottom: 24px;
  flex-wrap: wrap;
}
.tab {
  padding: 6px 18px;
  background-color: rgba(255,255,255,0.04);
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 20px;
  color: var(--text-secondary);
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  transition: all 0.2s ease;
}
.tab:hover {
  background-color: rgba(255,255,255,0.07);
  color: var(--text-primary);
}
.tab.active {
  background-color: var(--accent);
  border-color: var(--accent);
  color: #fff;
  font-weight: 600;
  box-shadow: 0 2px 10px rgba(91, 154, 255, 0.3);
}

.skill-selector {
  display: inline-flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 32px;
}
.skill-selector label {
  color: var(--text-secondary);
  font-size: 15px;
  font-weight: 600;
}

/* KPI Cards */
.kpi-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 16px;
  margin-bottom: 32px;
  min-width: 0;
}
@media (max-width: 700px) {
  .kpi-row { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 400px) {
  .kpi-row { grid-template-columns: 1fr; }
}
.kpi-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.2);
  display: flex;
  flex-direction: column;
  position: relative;
  overflow: hidden;
  transition: transform 0.2s, box-shadow 0.2s;
}
.kpi-card:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 14px rgba(0,0,0,0.3);
}

.kpi-card::before {
  content: ''; position: absolute; left: 0; top: 0; bottom: 0; width: 4px;
}
.kpi-card:nth-child(1)::before { background: var(--accent); }
.kpi-card:nth-child(2)::before { background: var(--orange); }
.kpi-card:nth-child(3)::before { background: var(--cyan); }
.kpi-card:nth-child(4)::before { background: var(--purple); }
.kpi-card:nth-child(5)::before { background: var(--green); }

.kpi-card:nth-child(1) {
  background: linear-gradient(135deg, rgba(91,154,255,0.15) 0%, var(--bg-card) 100%);
  border-color: rgba(91,154,255,0.25);
}
.kpi-card:nth-child(1) .label { color: var(--accent); }
.kpi-card:nth-child(1) .value { color: var(--accent); font-size: 34px; }

.kpi-card .label {
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 8px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.8px;
}
.kpi-card .value {
  font-size: 26px;
  font-weight: 800;
  color: #fff;
  letter-spacing: -0.3px;
}
.kpi-card .value.warn { color: var(--red); }

/* Chart/Data box */
.chart-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  margin-bottom: 28px;
}
@media (max-width: 900px) {
  .chart-grid { grid-template-columns: 1fr; }
}
.chart-box {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 24px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.15);
  overflow-x: auto;
}
.chart-box.full-width { grid-column: 1 / -1; }
.chart-title {
  font-size: 16px;
  font-weight: 700;
  color: #fff;
  margin-bottom: 20px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  gap: 10px;
}

/* Details/Tables */
details {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  margin-bottom: 12px;
  overflow: hidden;
}
details summary {
  padding: 12px 16px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  list-style: none;
  display: flex;
  align-items: center;
  gap: 8px;
  background-color: rgba(255,255,255,0.03);
  border-bottom: 1px solid transparent;
}
details[open] summary { border-bottom-color: var(--border); }
details summary::before {
  content: '▸';
  font-size: 12px;
  color: var(--text-muted);
  transition: transform 0.2s;
}
details[open] summary::before { transform: rotate(90deg); color: var(--accent); }
.detail-content { padding: 16px; }

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
  text-align: left;
  min-width: 500px;
}
th {
  padding: 10px 14px;
  color: var(--text-muted);
  font-weight: 600;
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  border-bottom: 1px solid var(--border);
  background-color: rgba(255,255,255,0.02);
  white-space: nowrap;
}
td {
  padding: 10px 14px;
  border-bottom: 1px solid var(--border-light);
  color: var(--text-primary);
}
tr:last-child td { border-bottom: none; }
tr:hover td { background-color: rgba(255,255,255,0.03); }

.recharts-text { fill: var(--text-secondary) !important; font-size: 12px !important; }
.recharts-cartesian-axis-tick-value { fill: var(--text-muted) !important; }

/* 数值高亮色 */
.val-positive { color: var(--green) !important; font-weight: 600; }
.val-negative { color: var(--red) !important; font-weight: 600; }
.val-accent { color: var(--accent) !important; font-weight: 700; }
.val-orange { color: var(--orange) !important; font-weight: 600; }
.val-purple { color: var(--purple) !important; font-weight: 600; }
.val-cyan { color: var(--cyan) !important; font-weight: 600; }
.tag {
  display: inline-block;
  padding: 1px 8px;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 600;
}
.tag-blue { background: rgba(91,154,255,0.15); color: var(--accent); }
.tag-green { background: rgba(91,218,110,0.15); color: var(--green); }
.tag-red { background: rgba(255,107,107,0.15); color: var(--red); }
.tag-orange { background: rgba(255,169,77,0.15); color: var(--orange); }
.tag-purple { background: rgba(177,151,252,0.15); color: var(--purple); }
.tag-cyan { background: rgba(102,217,232,0.15); color: var(--cyan); }
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
  Tree: '#5bda6e', Item: '#5b9aff', Skill: '#ffa94d',
  Base: '#a8abb5', Jewel: '#b197fc', Other: '#6c6f7e',
  Sim: '#ff6b6b', SkillEffect: '#fbbf24'
};
const CATEGORY_COLORS = {
  '进攻': '#ff6b6b', '防御': '#5b9aff', '混合': '#b197fc', '无效': '#6c6f7e'
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
  var catClr = { Tree: '#5bda6e', Item: '#ffa94d', Jewel: '#b197fc', Skill: '#5b9aff', Sim: '#ff6b6b', Base: '#a8abb5', Gem: '#66d9e8', SkillEffect: '#fbbf24' };

  // Element emoji/icon map for affects display
  var elemIcons = { Lightning: '\u26a1', Cold: '\u2744', Fire: '\ud83d\udd25', Physical: '\u2694', Chaos: '\ud83d\udd2e' };
  var elemColors = { Lightning: '#b197fc', Cold: '#5b9aff', Fire: '#ffa94d', Physical: '#a8abb5', Chaos: '#b197fc' };

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
          return h('span', { key: ei, style: { color: elemColors[e] || 'var(--text-muted)', marginRight: 2 } },
            elemIcons[e] || '');
        }).concat([
          h('span', { style: { color: 'var(--text-muted)', fontSize: 10, marginLeft: 2 } }, affects.replace(/,/g, '/'))
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
      h('div', { style: { display: 'flex', alignItems: 'center', gap: 8, padding: '5px 8px', borderBottom: '1px solid rgba(255,255,255,0.06)', flexWrap: 'wrap' } },
        h('span', { style: { minWidth: 120, flex: '1 1 120px', color: 'var(--text-primary)', fontSize: 12, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 4 } },
          h('span', null, label),
          affectsTag
        ),
        h('span', { style: { minWidth: 55, textAlign: 'right', color: 'var(--green)', fontFamily: 'monospace', fontSize: 12, flex: '0 0 55px' } }, isMore ? ((m.total >= 1 ? '+' : '') + Math.round((m.total - 1) * 100) + '%') : ('+' + Math.round(m.total) + suffix)),
        h('span', { style: { minWidth: 55, textAlign: 'right', color: (isMore ? tree !== 1 : tree) ? 'var(--cyan)' : 'var(--text-muted)', fontFamily: 'monospace', fontSize: 12, flex: '0 0 55px' } }, isMore ? (tree !== 1 ? (tree >= 1 ? '+' : '') + Math.round((tree - 1) * 100) + '%' : '\u2014') : (tree ? '+' + Math.round(tree) + suffix : '\u2014')),
        h('span', { style: { minWidth: 55, textAlign: 'right', color: (isMore ? item !== 1 : item) ? 'var(--orange)' : 'var(--text-muted)', fontFamily: 'monospace', fontSize: 12, flex: '0 0 55px' } }, isMore ? (item !== 1 ? (item >= 1 ? '+' : '') + Math.round((item - 1) * 100) + '%' : '\u2014') : (item ? '+' + Math.round(item) + suffix : '\u2014')),
        h('span', { style: { minWidth: 55, textAlign: 'right', color: (isMore ? jewel !== 1 : jewel) ? 'var(--purple)' : 'var(--text-muted)', fontFamily: 'monospace', fontSize: 12, flex: '0 0 55px' } }, isMore ? (jewel !== 1 ? (jewel >= 1 ? '+' : '') + Math.round((jewel - 1) * 100) + '%' : '\u2014') : (jewel ? '+' + Math.round(jewel) + suffix : '\u2014')),
        h('span', { style: { minWidth: 55, textAlign: 'right', color: (isMore ? support !== 1 : support) ? 'var(--accent)' : 'var(--text-muted)', fontFamily: 'monospace', fontSize: 12, flex: '0 0 55px' } }, isMore ? (support !== 1 ? (support >= 1 ? '+' : '') + Math.round((support - 1) * 100) + '%' : '\u2014') : (support ? '+' + Math.round(support) + suffix : '\u2014')),
        srcs.length > 0 && h('span', { style: { flex: '0 0 auto', textAlign: 'right', color: 'var(--text-muted)', fontSize: 10 } }, srcs.length + ' \u6761')
      ),
      // Expandable source detail
      srcs.length > 0 && h('div', { style: { paddingLeft: 20, paddingTop: 2, paddingBottom: 6, borderBottom: '1px solid rgba(46,46,74,0.15)' } },
        h('div', { style: { display: 'flex', gap: 6, fontSize: 10, color: 'var(--text-muted)', marginBottom: 2, fontWeight: 600 } },
          h('span', { style: { width: 36 } }, '\u7C7B\u578B'),
          h('span', { style: { width: 50, textAlign: 'right' } }, '\u6570\u503C'),
          h('span', null, '\u6765\u6E90')
        ),
        srcs.sort(function(a, b) { return Math.abs(b.value || 0) - Math.abs(a.value || 0); }).map(function(s, si) {
          var detail = s.detail ? ' \u2192 ' + s.detail : '';
          return h('div', { key: si, style: { display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, lineHeight: '18px' } },
            h('span', { style: { width: 36, color: catClr[s.category] || 'var(--text-muted)', fontSize: 10 } }, s.category),
            h('span', { style: { width: 50, textAlign: 'right', color: (s.value || 0) >= 0 ? 'var(--green)' : 'var(--red)', fontFamily: 'monospace', fontSize: 11 } }, (s.value >= 0 ? '+' : '') + (s.value || 0) + suffix),
            h('span', { style: { flex: 1, color: 'var(--text-secondary)' } }, (s.label || s.source || '') + detail)
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
      h('span', { style: { color: 'var(--text-secondary)' } }, attrLabels[k]),
      h('span', { style: { color: 'var(--text-primary)', fontFamily: 'monospace' } }, Math.round(ba[k]).toLocaleString())
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
      h('div', { className: 'chart-title' }, '\ud83d\udcca \u6784\u7B51\u4FEE\u9970\u7B26'),
      // Column header
      h('div', { style: { display: 'flex', alignItems: 'center', gap: 8, padding: '4px 8px', borderBottom: '1px solid rgba(255,255,255,0.08)', marginBottom: 2, flexWrap: 'wrap' } },
        h('span', { style: { minWidth: 120, flex: '1 1 120px', color: 'var(--text-muted)', fontSize: 11, fontWeight: 600 } }, '\u4FEE\u9970\u7B26'),
        h('span', { style: { minWidth: 55, textAlign: 'right', color: 'var(--text-muted)', fontSize: 11, fontWeight: 600, flex: '0 0 55px' } }, '\u603B\u91CF'),
        h('span', { style: { minWidth: 55, textAlign: 'right', color: 'var(--text-muted)', fontSize: 11, fontWeight: 600, flex: '0 0 55px' } }, '\u5929\u8D4B'),
        h('span', { style: { minWidth: 55, textAlign: 'right', color: 'var(--text-muted)', fontSize: 11, fontWeight: 600, flex: '0 0 55px' } }, '\u88C5\u5907'),
        h('span', { style: { minWidth: 55, textAlign: 'right', color: 'var(--text-muted)', fontSize: 11, fontWeight: 600, flex: '0 0 55px' } }, '\u73E0\u5B9D'),
        h('span', { style: { minWidth: 55, textAlign: 'right', color: 'var(--text-muted)', fontSize: 11, fontWeight: 600, flex: '0 0 55px' } }, '\u8F85\u52A9')
      ),
      h('div', null, bmCards)
    ),
    // Build attributes
    attrItems.length > 0 && h('div', { className: 'chart-box' },
      h('div', { className: 'chart-title' }, '\ud83d\udd11 \u6784\u7B51\u5C5E\u6027'),
      h('div', null, attrItems)
    ),
    // Defence (expandable)
    defItems.length > 0 && h('div', { className: 'chart-box full-width' },
      h('details', { open: false },
        h('summary', { className: 'chart-title', style: { cursor: 'pointer', userSelect: 'none' } },
          '\ud83d\udee1\ufe0f \u9632\u5FA1\u9762'
        ),
        h('div', { style: { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '2px 20px', padding: '8px 4px' } },
          defItems.map(function(r, i) {
            return h('div', { key: i, style: { display: 'flex', justifyContent: 'space-between', fontSize: 12, padding: '3px 0' } },
              h('span', { style: { color: 'var(--text-secondary)' } }, r.l),
              h('span', { style: { color: 'var(--text-primary)', fontFamily: 'monospace' } }, r.v)
            );
          })
        )
      )
    ),
    // Resource (expandable)
    resItems.length > 0 && h('div', { className: 'chart-box full-width' },
      h('details', { open: false },
        h('summary', { className: 'chart-title', style: { cursor: 'pointer', userSelect: 'none' } },
          '\u26a1 \u8D44\u6E90\u9762'
        ),
        h('div', { style: { display: 'flex', flexDirection: 'column', gap: '2px', padding: '8px 4px' } },
          resItems.map(function(r, i) {
            return h('div', { key: i, style: { display: 'flex', justifyContent: 'space-between', fontSize: 12, padding: '3px 0' } },
              h('span', { style: { color: 'var(--text-secondary)' } }, r.l),
              h('span', { style: { color: 'var(--text-primary)', fontFamily: 'monospace' } }, r.v)
            );
          })
        )
      )
    ),
    // Jewel overview (expandable per jewel)
    jewels.length > 0 && h('div', { className: 'chart-box full-width' },
      h('details', { open: false },
        h('summary', { className: 'chart-title', style: { cursor: 'pointer', userSelect: 'none' } },
          '\ud83d\udc8e \u73E0\u5B9D\u6982\u89C8 (' + jewels.length + ')'
        ),
        h('div', { style: { display: 'flex', flexDirection: 'column', gap: 6, padding: '8px 4px' } },
          jewels.map(function(j, i) {
            var mods = j.mods || [];
            var passives = (j.granted_passives || []).join(', ');
            var dpsTotal = j.dps_pct || 0;
            var ehpTotal = 0;
            mods.forEach(function(m) { ehpTotal += (m.ehp_pct || 0); });
            var rarityColor = j.rarity === 'UNIQUE' ? 'var(--accent)' : 'var(--text-secondary)';
            return h('details', { key: i, style: { borderBottom: '1px solid rgba(46,46,74,0.3)', paddingBottom: 4 } },
              h('summary', { style: { cursor: 'pointer', fontSize: 12, color: 'var(--text-primary)', listStyle: 'none', display: 'flex', alignItems: 'center', gap: 8, padding: '2px 0' } },
                h('span', { style: { color: 'var(--purple)' } }, '\u25B8'),
                h('span', { style: { fontWeight: 600, color: rarityColor } }, j.name || j.base_type),
                h('span', { style: { color: 'var(--text-muted)', fontSize: 11 } }, j.base_type),
                h('span', { style: { color: 'var(--text-muted)', fontSize: 11 } }, j.slot_name),
                dpsTotal > 0.01 ? h('span', { style: { color: 'var(--green)', fontFamily: 'monospace', fontSize: 11, marginLeft: 'auto' } }, '+' + dpsTotal.toFixed(2) + '%') : null
              ),
              mods.length > 0 && h('div', { style: { marginLeft: 20, marginTop: 2 } },
                // Header row
                h('div', { style: { display: 'flex', alignItems: 'center', gap: 8, fontSize: 10, color: 'var(--text-muted)', fontWeight: 600, borderBottom: '1px solid rgba(46,46,74,0.2)', marginBottom: 2, paddingBottom: 2 } },
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
                    h('span', { style: { color: hasImpact ? 'var(--text-primary)' : 'var(--text-muted)', minWidth: 160, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' } }, m.name),
                    h('span', { style: { color: 'var(--text-primary)', fontFamily: 'monospace', minWidth: 40 } }, '+' + m.value + suffix),
                    h('span', { style: { color: 'var(--text-muted)', minWidth: 30, fontSize: 10 } }, m.type),
                    h('span', { style: { color: dpsVal > 0.01 ? 'var(--green)' : '#444460', fontFamily: 'monospace', minWidth: 55, textAlign: 'right' } }, dpsVal > 0.01 ? '+' + dpsVal.toFixed(2) + '%' : '-'),
                    h('span', { style: { color: ehpVal > 0.01 ? 'var(--cyan)' : '#444460', fontFamily: 'monospace', minWidth: 55, textAlign: 'right' } }, ehpVal > 0.01 ? '+' + ehpVal.toFixed(2) + '%' : '-')
                  );
                }),
                passives && h('div', { style: { marginTop: 2, fontSize: 11, color: 'var(--text-muted)' } }, '\u8D4B\u4E88\u5929\u8D4B: ', passives)
              )
            );
          })
        )
      )
    )
  );
}

var TH_STYLE = { fontSize: 11, color: 'var(--text-muted)', fontWeight: 400, textAlign: 'left', padding: '4px 8px', borderBottom: '1px solid rgba(46,46,74,0.4)' };

// ── Source List (reusable) ──
function SourceList({ sources }) {
  if (!sources || sources.length === 0) return null;
  return h('div', { style: { display: 'flex', flexDirection: 'column', gap: 1, marginTop: 2, marginBottom: 2 } },
    sources.map((s, si) =>
      h('div', { key: si, style: { fontSize: 12, color: 'var(--text-secondary)', display: 'flex', gap: 8, paddingLeft: 8 } },
        h('span', { style: { width: 50, color: CAT_COLORS[s.category] || 'var(--text-muted)', fontSize: 11 } }, s.category),
        h('span', { style: { width: 50, textAlign: 'right', color: (s.value || 0) >= 0 ? 'var(--text-primary)' : 'var(--red)', fontFamily: 'monospace' } }, (s.value >= 0 ? '+' : '') + s.value),
        h('span', { style: { flex: 1 } }, s.label || '')
      )
    )
  );
}

// ── Formula Items Breakdown ──
function FormulaBreakdown({ data }) {
  if (!data || !data.formula_items) return null;

  var catColors = { Tree: '#5bda6e', Item: '#5b9aff', Skill: '#ffa94d', Base: '#a8abb5', Jewel: '#b197fc', Enemy: '#ff6b6b', Sim: '#ffaa44', Ailment: '#cc66aa', Config: '#88aacc', ResistInvert: '#e879f9', Penetration: '#60a5fa', SkillEffect: '#fbbf24', Other: '#888899' };

  // 不再合并 Lucky，保持独立分组
  // 过滤旧格式按元素展开的敌人乘区条目（旧缓存兼容），
  // 只保留合并后的 Enemy_DamageTaken_mult 和 EffMult_weighted
  var items = data.formula_items.filter(function(it) {
    if (it.total_value === undefined || it.total_value === 0 || it.key === 'CombinedDPS') return false;
    // 过滤旧格式: Enemy_Lightning_DamageTaken_mult, Lightning_EffMult 等
    if (/^Enemy_(Lightning|Cold|Fire|Physical|Chaos)_DamageTaken_mult$/.test(it.key)) return false;
    if (/^(Lightning|Cold|Fire|Physical|Chaos)_EffMult$/.test(it.key)) return false;
    // 过滤 Base_Damage：基础伤害的绝对值（如 Physical_Base_Damage=2555.92），
    // 不是乘区修正，展示为百分比会极其误导（显示为 +2556%）
    // 基础伤害构成已在 DamagePieChart 中展示
    if (/_Base_Damage$/.test(it.key)) return false;
    return true;
  });

  // === 按乘区分组 ===
  // group_type: 'additive' = 加法叠加(如INC), 'multiplicative' = 乘法叠加(如MORE), 'mixed' = 混合(BASE+INC+MORE)
  var groups = [
    { id: 'dmg_inc', label: '\u4f24\u5bb3 INC', icon: '\ud83d\udcc8', color: '#55c078', group_type: 'additive',
      test: function(it) { return it.key.endsWith('_INC') && !it.key.startsWith('Crit') && !it.key.startsWith('Speed'); } },
    { id: 'skill_effect', label: '\u6280\u80fd\u6548\u679c', icon: '\u2728', color: '#fbbf24', group_type: 'info',
      test: function(it) { return (it.sources || []).some(function(s) { return s.category === 'SkillEffect'; }); } },
    { id: 'dmg_more', label: '\u4f24\u5bb3 MORE', icon: '\u26a1', color: '#5588dd', group_type: 'multiplicative',
      test: function(it) { return it.key.endsWith('_MORE') && !it.key.startsWith('Crit') && !it.key.startsWith('Speed'); } },
    { id: 'lucky', label: '\u5e78\u8fd0\u51fb\u4e2d', icon: '\ud83c\udfb2', color: '#cc5599', group_type: 'info',
      test: function(it) { return it.key.endsWith('_Lucky') || it.key === 'LuckyHits'; } },
    { id: 'crit', label: '\u66b4\u51fb', icon: '\ud83c\udfaf', color: '#e05555', group_type: 'mixed',
      test: function(it) { return it.key.startsWith('Crit'); } },
    { id: 'speed', label: '\u901f\u5ea6', icon: '\u23f1', color: '#44bbcc', group_type: 'mixed',
      test: function(it) { return it.key.startsWith('Speed'); } },
    { id: 'conv', label: '\u8f6c\u6362/\u589e\u76ca', icon: '\ud83d\udd04', color: '#dd8844', group_type: 'additive',
      test: function(it) { return it.key.includes('ConvGain') || it.key.includes('SelfGain'); } },
    { id: 'eff', label: '\u654c\u4eba\u4e58\u533a', icon: '\ud83d\udee1', color: '#ff6b6b', group_type: 'enemy',
      test: function(it) { return it.key === 'EffMult_weighted' || it.key === 'Enemy_DamageTaken_mult'; } },
    { id: 'dot', label: 'DoT DPS', icon: '\ud83d\udd25', color: '#cc66aa', group_type: 'info',
      test: function(it) { return it.key === 'Ignite_DPS' || it.key === 'Bleed_DPS' || it.key === 'Poison_DPS'; } },
  ];

  // 分配每个 item 到组
  var grouped = {};
  groups.forEach(function(g) { grouped[g.id] = []; });
  var ungrouped = [];
  items.forEach(function(it) {
    var assigned = false;
    for (var i = 0; i < groups.length; i++) {
      if (groups[i].test(it)) {
        grouped[groups[i].id].push(it);
        assigned = true;
        break;
      }
    }
    if (!assigned) ungrouped.push(it);
  });

  // 渲染单个 formula item（带条形图+来源折叠）
  function renderItem(it) {
    var isEffWeighted = it.key === 'EffMult_weighted';
    var isEnemyDT = it.key === 'Enemy_DamageTaken_mult';
    var cats = it.category_summary || {};
    var isMore = it.key.includes('_MORE');
    var total = Math.abs(it.total_value);
    var catKeys = Object.keys(cats).filter(function(k) { return cats[k] !== 0; });
    var catEntries = catKeys.map(function(k) { return { key: k, value: Math.abs(cats[k]), color: catColors[k] || 'var(--text-muted)' }; });
    catEntries.sort(function(a, b) { return b.value - a.value; });

    var catSum, catPcts;
    if (isEffWeighted || isEnemyDT || isDotDPS) {
      // 敌人乘区/DoT DPS：不展示分类条形图（category_summary 语义不匹配）
      catPcts = [];
    } else if (isMore) {
      catSum = total - 1 || 1;
      catPcts = catEntries.map(function(c) { return Object.assign({}, c, { pct: (c.value - 1) / catSum * 100 }); });
    } else {
      catSum = catEntries.reduce(function(s, c) { return s + c.value; }, 0) || 1;
      catPcts = catEntries.map(function(c) { return Object.assign({}, c, { pct: c.value / catSum * 100 }); });
    }

    var displayStr;
    var isDotDPS = it.key === 'Ignite_DPS' || it.key === 'Bleed_DPS' || it.key === 'Poison_DPS';
    if (isDotDPS) {
      displayStr = fmt(it.total_value, 0) + ' DPS';
    } else if (isMore) {
      // MORE 乘法项：显示乘数
      displayStr = '\u00d7' + fmt(it.total_value, 2);
    } else if (it.key.endsWith('_ProjectileCount') || it.key.endsWith('_SplitCount')) {
      // 弹体/分裂数量：绝对值
      displayStr = it.total_value + '\u4e2a';
    } else if (it.key.endsWith('_BASE') && (it.key.includes('Count') || it.key.includes('Multiplier'))) {
      // 计数型 BASE：绝对值
      displayStr = fmt(it.total_value, 0);
    } else if (it.key.includes('Multiplier:') && it.key.endsWith('MaxStages')) {
      // 最大阶段数
      displayStr = it.total_value + '\u9636\u6bb5';
    } else if (it.key === 'Enemy_DamageTaken_mult') {
      // 敌人受伤增加：显示乘数
      displayStr = '\u00d7' + fmt(it.total_value, 2);
    } else if (it.key === 'EffMult_weighted') {
      // EffMult_weighted total_value 已是增益百分比（如 16.0 表示 +16%）
      displayStr = '+' + fmt(it.total_value, 1) + '%';
    } else if (it.key === 'CritMultiplier_BASE') {
      // CritMultiplier_BASE=100 表示基础额外暴击伤害100%，即暴击×2.00
      displayStr = '\u00d7' + fmt(1 + it.total_value / 100, 2) + ' (\u57fa\u7840\u66b4\u51fb\u500d\u7387)';
    } else if (it.key === 'CritChance_BASE') {
      displayStr = fmt(it.total_value, 1) + '%';
    } else if (it.key.endsWith('_BASE')) {
      displayStr = fmt(it.total_value, 2);
    } else {
      displayStr = (it.total_value >= 0 ? '+' : '') + (it.total_value < 10 ? fmt(it.total_value, 1) : Math.round(it.total_value)) + '%';
    }

    var catLegend = catPcts.map(function(c) {
      var topSrcs = (it.sources || []).filter(function(s) { return s.category === c.key; });
      topSrcs.sort(function(a, b) { return Math.abs(b.value || 0) - Math.abs(a.value || 0); });
      var names = topSrcs.slice(0, 3).map(function(s) { return s.label || s.source; });
      if (names.length === 0) return h('span', { key: c.key, style: { fontSize: 11, color: c.color } }, c.key + (isMore ? ' \u00d7' + fmt(c.value, 2) : ' ' + fmt(c.value, 0)));
      var rest = topSrcs.length - 3;
      var label = names.join(', ') + (rest > 0 ? ' +' + rest : '');
      return h('span', { key: c.key, style: { fontSize: 11, color: c.color, maxWidth: 280, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }, title: label }, label);
    });

    // 技能效果条目添加未计入 DPS 提示
    var isSkillEffect = (it.sources || []).some(function(s) { return s.category === 'SkillEffect'; });
    var formulaName = it.formula_name;
    if (isSkillEffect) {
      formulaName = it.formula_name + ' (\u672a\u8ba1\u5165)';
    }

    return h('div', { key: it.key, style: { borderBottom: '1px solid rgba(46,46,74,0.25)' } },
      h('div', { style: { display: 'flex', alignItems: 'center', gap: 10, padding: '6px 4px' } },
        h('div', { style: { minWidth: 220, fontSize: 13, color: 'var(--text-primary)' } },
          h('span', { style: { fontWeight: 500 } }, formulaName),
          h('span', { style: { color: 'var(--accent)', fontWeight: 700, marginLeft: 8 } }, displayStr)
        ),
        h('div', { style: { flex: 1, height: 14, display: 'flex', borderRadius: 3, overflow: 'hidden' } },
          catPcts.map(function(c, ci) {
            return h('div', { key: ci, style: { width: c.pct + '%', background: c.color, opacity: 0.7 }, title: c.key + (isMore ? ' \u00d7' + fmt(c.value, 2) : ': ' + fmt(c.value, 1)) });
          })
        ),
        h('div', { style: { display: 'flex', gap: 8, minWidth: 180, justifyContent: 'flex-end', flexWrap: 'wrap' } }, catLegend)
      ),
      // 来源折叠：优先展示 mod_sources（穿透/减抗等真实来源），否则展示普通 sources
      (function() {
        var modSrcs = it.mod_sources || [];
        var plainSrcs = it.sources || [];
        if (modSrcs.length === 0 && plainSrcs.length === 0) return null;
        var useMod = modSrcs.length > 0;
        var srcs = useMod ? modSrcs : plainSrcs;
        // 来源数量较多时，只默认展示 Top 5，其余折叠
        var TOP_N = 5;
        var topSrcs = srcs.slice(0, TOP_N);
        var restSrcs = srcs.slice(TOP_N);
        var label = useMod ? '\u25bc \u6297\u6027/\u7a7f\u900f\u6765\u6e90 (' + srcs.length + ')' : '\u25bc ' + srcs.length + ' \u4e2a\u6765\u6e90';
        return h('details', { style: { paddingLeft: 12, paddingBottom: 2 } },
          h('summary', { style: { fontSize: 11, color: 'var(--text-muted)', cursor: 'pointer', userSelect: 'none' } }, label),
          h('div', { style: { display: 'flex', flexDirection: 'column', gap: 1, marginTop: 2 } },
            topSrcs.map(function(s, si) {
              var cat = s.category || (useMod ? 'Config' : 'Other');
              var val = s.value;
              var name = useMod ? (s.mod_name || s.source) : (s.label || s.source);
              var elem = s.element ? ' [' + s.element + ']' : '';
              return h('div', { key: si, style: { fontSize: 12, color: 'var(--text-secondary)', display: 'flex', gap: 8, paddingLeft: 8 } },
                h('span', { style: { width: 50, color: catColors[cat] || 'var(--text-muted)', fontSize: 11 } }, cat),
                h('span', { style: { width: 50, textAlign: 'right', color: (val || 0) >= 0 ? 'var(--text-primary)' : 'var(--red)', fontFamily: 'monospace' } }, (val >= 0 ? '+' : '') + val),
                h('span', { style: { flex: 1 } }, name + elem)
              );
            }),
            restSrcs.length > 0 ? h('details', { style: { paddingLeft: 8 } },
              h('summary', { style: { fontSize: 11, color: 'var(--text-muted)', cursor: 'pointer' } }, '\u5269\u4f59 ' + restSrcs.length + ' \u4e2a\u6765\u6e90'),
              restSrcs.map(function(s, si) {
                var cat = s.category || (useMod ? 'Config' : 'Other');
                var val = s.value;
                var name = useMod ? (s.mod_name || s.source) : (s.label || s.source);
                var elem = s.element ? ' [' + s.element + ']' : '';
                return h('div', { key: si + TOP_N, style: { fontSize: 12, color: 'var(--text-secondary)', display: 'flex', gap: 8, paddingLeft: 8 } },
                  h('span', { style: { width: 50, color: catColors[cat] || 'var(--text-muted)', fontSize: 11 } }, cat),
                  h('span', { style: { width: 50, textAlign: 'right', color: (val || 0) >= 0 ? 'var(--text-primary)' : 'var(--red)', fontFamily: 'monospace' } }, (val >= 0 ? '+' : '') + val),
                  h('span', { style: { flex: 1 } }, name + elem)
                );
              })
            ) : null
          )
        );
      })()
    );
  }

  // 渲染分组（可折叠，默认折叠）
  function renderGroup(g) {
    var gItems = grouped[g.id];
    if (!gItems || gItems.length === 0) return null;

    // 汇总值：统一显示 最终效应 乘数（百分比）
    var summary;
    var gType = g.group_type;
    if (gType === 'additive') {
      // INC/ConvGain: 加法叠加，总 = 1 + sum%
      var total = gItems.reduce(function(s, it) { return s + it.total_value; }, 0);
      var mult = 1 + total / 100;
      summary = '\u00d7' + fmt(mult, 2) + ' (+' + Math.round(total) + '%)';
    } else if (gType === 'multiplicative') {
      // MORE/EffMult/DamageTaken: 乘法叠加，只显示乘数
      var mult = 1;
      gItems.forEach(function(it) {
        if (it.key.endsWith('_MORE') || it.key === 'Enemy_DamageTaken_mult') {
          mult *= it.total_value;
        } else if (it.key === 'EffMult_weighted') {
          mult *= (1 + it.total_value / 100); // EffMult total_value 是增益百分比
        } else {
          mult *= (1 + it.total_value / 100); // Lucky 的 total_value 是百分比
        }
      });
      summary = '\u00d7' + fmt(mult, 2);
    } else if (gType === 'enemy') {
      // 敌人乘区：只显示总体乘数
      var effItem = gItems.find(function(it) { return it.key === 'EffMult_weighted'; });
      var dtItem = gItems.find(function(it) { return it.key === 'Enemy_DamageTaken_mult'; });
      var parts = [];
      if (dtItem) {
        parts.push('\u53d7\u4f24\u589e\u52a0 \u00d7' + fmt(dtItem.total_value, 2));
      }
      if (effItem) {
        parts.push('\u6297\u6027\u7a7f\u900f \u00d7' + fmt(1 + effItem.total_value / 100, 2));
      }
      if (dtItem && effItem) {
        var totalEff = dtItem.total_value * (1 + effItem.total_value / 100);
        parts.unshift('\u603b\u4f53 \u00d7' + fmt(totalEff, 2));
      }
      summary = parts.join(' | ') || gItems.length + '\u9879';
    } else if (g.id === 'lucky') {
      // Lucky: 每个 item 是一种元素的 Lucky 概率（法术构筑: Lightning_Lucky 等3个 items）
      // 或合并的 LuckyHits（攻击构筑: 1个 item，3个 sources 代表3种元素）
      // Lucky 效应已内含在 POB 的 AvgHit 计算中，这里仅展示信息
      var elemCount = gItems.reduce(function(s, it) {
        // 每个 item 的 source 可能代表多个元素
        return s + Math.max((it.sources || []).length, 1);
      }, 0);
      var luckyPct = gItems[0].total_value || 0;
      summary = elemCount + '\u79cd\u5143\u7d20 \u5404' + fmt(luckyPct, 0) + '%\u6982\u7387';
    } else if (g.id === 'dot') {
      // DoT DPS: 绝对值求和
      var total = gItems.reduce(function(s, it) { return s + it.total_value; }, 0);
      summary = fmt(total, 0) + ' DPS';
    } else if (g.id === 'skill_effect') {
      // 技能效果：展示各子效果（理论值，未计入 POB TotalDPS）
      var parts = [];
      gItems.forEach(function(it) {
        if (it.key.endsWith('_MORE')) {
          parts.push('\u00d7' + fmt(it.total_value, 1));
        } else if (it.key.endsWith('_ProjectileCount') || it.key.endsWith('_SplitCount')) {
          parts.push(it.total_value + '\u4e2a');
        } else if (it.key.endsWith('_BASE')) {
          parts.push(it.display_value || it.total_value);
        } else {
          parts.push(it.display_value || it.total_value);
        }
      });
      summary = parts.join(' | ') + ' (\u672a\u8ba1\u5165DPS)';
    } else {
      // mixed (Crit/Speed): 直接读 POB 实际输出值
      if (g.id === 'crit') {
        var cc = data.crit_chance || 0;
        var cm = data.crit_multiplier || 1;
        var critFactor = 1 - cc / 100 + (cc / 100) * cm;
        summary = '\u00d7' + fmt(critFactor, 2) + ' (cc=' + fmt(cc, 1) + '% cm=' + fmt(cm, 2) + '\u00d7)';
      } else if (g.id === 'speed') {
        var spd = data.speed || 0;
        summary = '\u00d7' + fmt(spd, 2) + '/s';
      } else {
        summary = gItems.length + '\u9879';
      }
    }

    // ── 构建分组级别的计算过程说明 ──
    var calcProcess = '';
    if (gType === 'multiplicative') {
      // MORE 乘区：遍历每个 item 的 sources，构建 乘项名(×乘数) 链
      var chainParts = [];
      gItems.forEach(function(it) {
        var srcs = (it.sources || []).slice();
        srcs.sort(function(a, b) { return Math.abs(b.value || 0) - Math.abs(a.value || 0); });
        srcs.forEach(function(s) {
          var name = (s.label || s.source || '?').replace(/\s*\(模拟\)\s*/, '');
          var multVal = it.key.endsWith('_MORE') ? (1 + (s.value || 0) / 100) : (1 + (s.value || 0) / 100);
          chainParts.push(name + '(\u00d7' + fmt(multVal, 2) + ')');
        });
      });
      if (chainParts.length > 1) {
        var mult = 1;
        gItems.forEach(function(it) {
          if (it.key.endsWith('_MORE') || it.key === 'Enemy_DamageTaken_mult') { mult *= it.total_value; }
          else { mult *= (1 + it.total_value / 100); }
        });
        calcProcess = chainParts.join(' \u00d7 ') + ' = \u00d7' + fmt(mult, 2);
      }
    } else if (gType === 'enemy') {
      // 敌人乘区：受伤增加来源 + 抗性穿透来源
      var dtItem = gItems.find(function(it) { return it.key === 'Enemy_DamageTaken_mult'; });
      var effItem = gItems.find(function(it) { return it.key === 'EffMult_weighted'; });
      var parts = [];
      if (dtItem) {
        var dtSrcs = (dtItem.sources || []).slice();
        dtSrcs.sort(function(a, b) { return Math.abs(b.value || 0) - Math.abs(a.value || 0); });
        var dtParts = dtSrcs.map(function(s) {
          var name = (s.label || s.source || '?').split(':')[0];
          return name + '(+' + fmt(s.value || 0, 0) + '%)';
        });
        if (dtParts.length > 1) parts.push(dtParts.join(' + ') + ' \u2192 \u53d7\u4f24\u00d7' + fmt(dtItem.total_value, 2));
      }
      if (effItem) {
        var effSrcs = (effItem.sources || []).slice();
        var invertSrcs = effSrcs.filter(function(s) { return s.category === 'ResistInvert'; });
        var penSrcs = effSrcs.filter(function(s) { return s.category === 'Penetration'; });
        var enemySrcs = effSrcs.filter(function(s) { return s.category === 'Enemy'; });
        var effParts = [];
        // 抗性反转
        if (invertSrcs.length > 0) {
          var invInfo = invertSrcs.map(function(s) {
            return s.label + ' ' + fmt(s.value, 0) + '%';
          }).join(', ');
          effParts.push('\u53cd\u8f6c: ' + invInfo);
        }
        // 敌人抗性
        if (enemySrcs.length > 0) {
          var enemyInfo = enemySrcs.map(function(s) {
            return s.label + ' ' + fmt(s.value, 0) + '%';
          }).join(', ');
          effParts.push(enemyInfo);
        }
        // 穿透（当抗性≤0时标注无效）
        if (penSrcs.length > 0) {
          var penInfo = penSrcs.map(function(s) {
            return s.label + ' +' + fmt(s.value, 0) + '%';
          }).join(', ');
          var detail = effItem.formula_detail || '';
          if (detail.indexOf('\u7a7f\u900f\u65e0\u6548') >= 0) {
            penInfo += ' (\u65e0\u6548: \u6297\u6027\u22640)';
          }
          effParts.push(penInfo);
        }
        if (effParts.length > 0) parts.push(effParts.join('  |  ') + ' \u2192 \u00d7' + fmt(1 + effItem.total_value / 100, 2));
      }
      if (dtItem && effItem) {
        var totalEff = dtItem.total_value * (1 + effItem.total_value / 100);
        parts.push('\u7efc\u5408: \u53d7\u4f24\u00d7' + fmt(dtItem.total_value, 2) + ' \u00d7 \u7a7f\u900f\u00d7' + fmt(1 + effItem.total_value / 100, 2) + ' = \u00d7' + fmt(totalEff, 2));
      }
      calcProcess = parts.join('  |  ');
    } else if (g.id === 'crit') {
      // 暴击乘区：cc = BASE × (1+INC/100) × MORE, cm = 1 + (BASE/100) × (1+INC/100)
      var ccBase = 0, ccInc = 0, ccMore = 1, cmBase = 0, cmInc = 0;
      gItems.forEach(function(it) {
        if (it.key === 'CritChance_BASE') ccBase = it.total_value;
        else if (it.key === 'CritChance_INC') ccInc = it.total_value;
        else if (it.key === 'CritChance_MORE') ccMore = it.total_value;
        else if (it.key === 'CritMultiplier_BASE') cmBase = it.total_value;
        else if (it.key === 'CritMultiplier_INC') cmInc = it.total_value;
      });
      var cc = data.crit_chance || 0;
      var cm = data.crit_multiplier || 1;
      var parts = [];
      parts.push('cc = ' + fmt(ccBase, 1) + '% \u00d7 (1+' + fmt(ccInc, 0) + '%/100) \u00d7 ' + fmt(ccMore, 2) + ' = ' + fmt(cc, 1) + '%');
      parts.push('cm = 1 + ' + fmt(cmBase, 0) + '%/100 \u00d7 (1+' + fmt(cmInc, 0) + '%/100) = ' + fmt(cm, 2) + '\u00d7');
      parts.push('\u66b4\u51fb\u4e58\u6570 = (1 - ' + fmt(cc, 1) + '%) + ' + fmt(cc, 1) + '% \u00d7 ' + fmt(cm, 2) + ' = \u00d7' + fmt(1 - cc/100 + cc/100 * cm, 2));
      calcProcess = parts.join('  |  ');
    } else if (g.id === 'speed') {
      // 速度乘区：speed = BASE × (1+INC/100)
      var spdBase = 0, spdInc = 0;
      var speedLabel = '\u65bd\u6cd5\u901f\u5ea6'; // 默认施法速度
      gItems.forEach(function(it) {
        if (it.key === 'Speed_BASE') {
          spdBase = it.total_value;
          // 从 formula_name 判断攻击/施法速度
          if (it.formula_name && it.formula_name.includes('\u653b\u51fb')) speedLabel = '\u653b\u51fb\u901f\u5ea6';
        }
        else if (it.key === 'Speed_INC') spdInc = it.total_value;
      });
      var spd = data.speed || 0;
      calcProcess = speedLabel + ' = ' + fmt(spdBase, 2) + ' \u00d7 (1+' + fmt(spdInc, 0) + '%/100) = ' + fmt(spd, 2) + '/s';
    }

    return h('details', { key: g.id, style: { marginBottom: 2 } },
      h('summary', { style: { display: 'flex', alignItems: 'center', gap: 10, padding: '8px 10px', cursor: 'pointer', userSelect: 'none', background: 'rgba(255,255,255,0.02)', borderRadius: 4 } },
        h('span', { style: { fontSize: 14 } }, g.icon),
        h('span', { style: { fontWeight: 700, fontSize: 14, color: g.color } }, g.label),
        h('span', { style: { fontSize: 13, color: 'var(--accent)', fontFamily: 'monospace', fontWeight: 600 } }, summary),
        h('span', { style: { fontSize: 11, color: 'var(--text-muted)' } }, gItems.length + ' \u4e2a\u5b50\u9879')
      ),
      // 技能效果分组：显示醒目提示（动态生成）
      g.id === 'skill_effect' ? h('div', { style: { margin: '4px 10px 4px 10px', padding: '8px 12px', background: 'rgba(251, 191, 36, 0.08)', border: '1px solid rgba(251, 191, 36, 0.25)', borderRadius: 6, fontSize: 12, lineHeight: 1.5, color: '#fbbf24' } },
        h('span', { style: { fontWeight: 700 } }, '\u26a0\ufe0f POB \u672a\u8ba1\u7b97\u6b64\u90e8\u5206\u4f24\u5bb3: '),
        gItems.length > 0 ? (function() {
          // 收集所有 STATSET_EFFECT 来源的技能名和 statSet
          var skillNames = {};
          gItems.forEach(function(it) {
            if (it.sources) {
              it.sources.forEach(function(s) {
                if (s.source && s.source.startsWith('unmapped:')) {
                  // unmapped stat — 来自活跃 statSet 但 SkillStatMap 未映射
                  var statName = s.source.replace('unmapped:', '');
                  skillNames[statName] = true;
                }
              });
            }
          });
          var hasUnmapped = Object.keys(skillNames).length > 0;
          if (hasUnmapped) {
            return '\u4ee5\u4e0b\u6548\u679c\u7684 stat \u672a\u88ab SkillStatMap \u6620\u5c04\uff0c\u5df2\u901a\u8fc7 Sim \u6ce8\u5165\u4fee\u590d\u3002';
          }
          return '\u4ee5\u4e0b\u6570\u636e\u4e3a\u6839\u636e\u6280\u80fd\u63cf\u8ff0\u63a8\u7b97\u7684\u7406\u8bba\u503c\uff0c\u5b9e\u9645\u6e38\u620f\u4e2d\u8fd9\u4e9b\u6548\u679c\u5f88\u5f3a\u3002';
        })() : '\u4ee5\u4e0b\u6570\u636e\u4e3a\u6839\u636e\u6280\u80fd\u63cf\u8ff0\u63a8\u7b97\u7684\u7406\u8bba\u503c\u3002'
      ) : null,
      // 展开后：计算过程说明（仅乘法/敌人乘区）
      calcProcess ? h('div', { style: { padding: '6px 10px 6px 38px', fontSize: 11, color: 'var(--text-muted)', fontFamily: 'monospace', lineHeight: 1.6, background: 'rgba(255,255,255,0.02)', borderRadius: 4, marginBottom: 4, borderLeft: '3px solid var(--border)' } },
        h('span', { style: { fontWeight: 600, color: 'var(--text-secondary)' } }, '\u8ba1\u7b97\u8fc7\u7a0b: '),
        calcProcess
      ) : null,
      h('div', { style: { paddingLeft: 24, paddingRight: 4 } },
        gItems.map(renderItem)
      )
    );
  }

  return h('div', { className: 'chart-box full-width' },
    h('div', { className: 'chart-title' }, '\u2694\ufe0f DPS \u4e58\u533a\u6765\u6e90\u62c6\u89e3'),
    h('div', { style: { display: 'flex', flexDirection: 'column', gap: 2 } },
      groups.map(renderGroup),
      ungrouped.length > 0 ? h('div', { style: { paddingLeft: 24, paddingRight: 4 } }, ungrouped.map(renderItem)) : null
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
      fill: 'none', stroke: dc[i].color || 'var(--text-muted)',
      strokeWidth: thickness,
      strokeDasharray: dashLen.toFixed(2) + ' ' + gapLen.toFixed(2),
      strokeDashoffset: (-offset).toFixed(2),
      style: { opacity: 0.85 }
    }));
    offset += dashLen;
  }

  // Center label
  var centerText = h('text', { x: cx, y: cy - 6, textAnchor: 'middle', fill: 'var(--text-primary)', fontSize: 16, fontWeight: 700, fontFamily: 'monospace' }, Math.round(totalDPS).toLocaleString());
  var centerSub = h('text', { x: cx, y: cy + 12, textAnchor: 'middle', fill: 'var(--text-muted)', fontSize: 10 }, 'Total DPS');

  // Detail table
  var rows = dc.map(function(e, i) {
    var hitPct = e.hit_avg / totalHit * 100;
    var elemCombined = avgHit * (e.hit_avg / totalHit);
    var elemDPS = elemCombined * speed;
    var icon = _pieIcons[e.element] || '';
    var clr = e.color || 'var(--text-muted)';
    return h('div', { key: i, style: { display: 'flex', alignItems: 'center', gap: 8, padding: '3px 0', borderBottom: i < dc.length - 1 ? '1px solid rgba(46,46,74,0.15)' : 'none' } },
      h('div', { style: { width: 10, height: 10, borderRadius: 2, background: clr, flexShrink: 0 } }),
      h('span', { style: { color: clr, fontWeight: 500, minWidth: 85, fontSize: 12 } }, icon + ' ' + e.element),
      h('span', { style: { color: 'var(--text-primary)', fontFamily: 'monospace', minWidth: 50, textAlign: 'right', fontSize: 12 } }, fmt(hitPct, 1) + '%'),
      h('span', { style: { color: 'var(--text-secondary)', fontFamily: 'monospace', minWidth: 60, textAlign: 'right', fontSize: 11 } }, e.crit_avg > 0 ? Math.round(e.crit_avg).toLocaleString() : '-'),
      h('span', { style: { color: 'var(--text-primary)', fontFamily: 'monospace', minWidth: 60, textAlign: 'right', fontSize: 12, fontWeight: 600 } }, Math.round(elemDPS).toLocaleString())
    );
  });

  return h('div', { className: 'chart-box full-width' },
    h('div', { className: 'chart-title' }, '\ud83c\udfaf \u4f24\u5bb3\u6784\u6210'),
    h('div', { style: { display: 'flex', alignItems: 'center', gap: 20, padding: '8px 4px' } },
      h('svg', { width: size, height: size, viewBox: '0 0 ' + size + ' ' + size, style: { flexShrink: 0 } },
        slices, centerText, centerSub
      ),
      h('div', { style: { flex: 1, display: 'flex', flexDirection: 'column', gap: 0 } },
        h('div', { style: { display: 'flex', alignItems: 'center', gap: 8, padding: '2px 0 4px', borderBottom: '1px solid rgba(46,46,74,0.4)' } },
          h('span', { style: { width: 10 } }),
          h('span', { style: { minWidth: 85, color: 'var(--text-muted)', fontSize: 10, fontWeight: 600 } }, '\u5143\u7d20'),
          h('span', { style: { minWidth: 50, textAlign: 'right', color: 'var(--text-muted)', fontSize: 10, fontWeight: 600 } }, '\u547d\u4e2d\u5360\u6bd4'),
          h('span', { style: { minWidth: 60, textAlign: 'right', color: 'var(--text-muted)', fontSize: 10, fontWeight: 600 } }, '\u66b4\u51fb\u547d\u4e2d'),
          h('span', { style: { minWidth: 60, textAlign: 'right', color: 'var(--text-muted)', fontSize: 10, fontWeight: 600 } }, 'DPS')
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
    var typeColor = modType === 'MORE' ? '#5b9aff' : (modType === 'INC' ? '#5bda6e' : '#ffa94d');
    var rank = i + 1;
    return h('div', { key: i, style: { display: 'flex', alignItems: 'center', gap: 8, padding: '4px 0', borderBottom: '1px solid rgba(46,46,74,0.15)' } },
      h('span', { style: { width: 24, textAlign: 'center', color: i < 3 ? 'var(--accent)' : 'var(--text-muted)', fontSize: 12, fontWeight: i < 3 ? 700 : 400 } }, rank),
      h('div', { style: { flex: 1, minWidth: 0 } },
        h('div', { style: { display: 'flex', alignItems: 'baseline', gap: 6 } },
          h('span', { style: { color: 'var(--text-primary)', fontSize: 12, fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' } }, label),
          h('span', { style: { color: typeColor, fontSize: 10, fontWeight: 600, flexShrink: 0 } }, typeLabel)
        ),
        h('div', { style: { height: 4, borderRadius: 2, marginTop: 3, background: 'var(--border)' } },
          h('div', { style: { height: '100%', borderRadius: 2, width: barPct + '%', background: 'linear-gradient(90deg, #5b9aff 0%, #7ab3ff 100%)', opacity: 0.8 } })
        )
      ),
      h('span', { style: { width: 75, textAlign: 'right', color: 'var(--text-primary)', fontFamily: 'monospace', fontSize: 12, flexShrink: 0 } }, fmt(needed, 1)),
      h('span', { style: { width: 85, textAlign: 'right', color: 'var(--green)', fontFamily: 'monospace', fontSize: 11, flexShrink: 0 } }, '+' + fmt(dpsPU, 3) + '%/unit')
    );
  });

  return h('div', { className: 'chart-box full-width' },
    h('div', { className: 'chart-title' }, '\u2696\ufe0f \u4f18\u5316\u6760\u6746\u6392\u540d'),
    h('div', { style: { display: 'flex', alignItems: 'center', gap: 8, padding: '2px 0 4px', borderBottom: '1px solid rgba(46,46,74,0.4)' } },
      h('span', { style: { width: 24 } }),
      h('span', { style: { flex: 1, color: 'var(--text-muted)', fontSize: 10, fontWeight: 600 } }, '\u4fee\u9970\u7b26'),
      h('span', { style: { width: 75, textAlign: 'right', color: 'var(--text-muted)', fontSize: 10, fontWeight: 600 } }, '\u6240\u9700\u6295\u5165'),
      h('span', { style: { width: 85, textAlign: 'right', color: 'var(--text-muted)', fontSize: 10, fontWeight: 600 } }, 'DPS/\u5355\u4f4d')
    ),
    rows
  );
}

// ── Aura Chart (清晰的数值行布局) ──
function AuraChart({ auras }) {
  if (!auras || auras.length === 0) return null;
  const aurasWithRange = auras.filter(a => a.config_ranges && a.config_ranges.length > 0);
  const aurasStatic = auras.filter(a => !a.config_ranges || a.config_ranges.length === 0);

  var auraCards = [];

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
    const ehp = aura.ehp_pct || 0;
    const spirit = Math.round(aura.spirit_cost || 0);

    auraCards.push(
      h('div', { key: aura.name, style: { background: 'rgba(255,255,255,0.03)', border: '1px solid var(--border)', borderRadius: 8, padding: '16px', marginBottom: 10 } },
        // Header: name + spirit cost
        h('div', { style: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 } },
          h('span', { style: { fontWeight: 700, fontSize: 15, color: '#fff' } },
            '\u2728 ' + aura.name + (aura.simulated ? ' \u26a0' : '')
          ),
          h('span', { className: 'tag tag-blue' }, '\u7CBE\u9B44\u6D88\u8017 ' + spirit)
        ),
        // Min endpoint row
        h('div', { style: { display: 'flex', alignItems: 'center', padding: '8px 12px', background: 'rgba(255,255,255,0.02)', borderRadius: 6, marginBottom: 6 } },
          h('span', { style: { color: 'var(--text-muted)', fontSize: 12, minWidth: 100 } }, paramLabel + ' = 0'),
          h('div', { style: { flex: 1, display: 'flex', gap: 16, justifyContent: 'flex-end', flexWrap: 'wrap' } },
            h('span', { style: { fontSize: 12 } }, h('span', { style: { color: 'var(--text-muted)' } }, 'DPS '), h('span', { style: { color: pctMin >= 0 ? 'var(--green)' : 'var(--red)', fontWeight: 700, fontFamily: 'monospace' } }, fmtSign(pctMin))),
            Math.abs(supMin) >= 0.05 ? h('span', { style: { fontSize: 12 } }, h('span', { style: { color: 'var(--text-muted)' } }, '\u5176\u4E2D\u8F85\u52A9 '), h('span', { style: { color: 'var(--purple)', fontWeight: 600, fontFamily: 'monospace' } }, fmtSign(supMin, 2))) : null,
            Math.abs(spiritMin) >= 0.05 ? h('span', { style: { fontSize: 12 } }, h('span', { style: { color: 'var(--text-muted)' } }, '\u5176\u4E2D\u7CBE\u9B44\u8F85\u52A9 '), h('span', { style: { color: 'var(--orange)', fontWeight: 600, fontFamily: 'monospace' } }, fmtSign(spiritMin, 2))) : null
          )
        ),
        // Max endpoint row
        h('div', { style: { display: 'flex', alignItems: 'center', padding: '8px 12px', background: 'rgba(255,255,255,0.02)', borderRadius: 6, marginBottom: 6 } },
          h('span', { style: { color: 'var(--text-muted)', fontSize: 12, minWidth: 100 } }, paramLabel + ' = ' + maxVal),
          h('div', { style: { flex: 1, display: 'flex', gap: 16, justifyContent: 'flex-end', flexWrap: 'wrap' } },
            h('span', { style: { fontSize: 12 } }, h('span', { style: { color: 'var(--text-muted)' } }, 'DPS '), h('span', { style: { color: pctMax >= 0 ? 'var(--green)' : 'var(--red)', fontWeight: 700, fontFamily: 'monospace' } }, fmtSign(pctMax))),
            Math.abs(supMax) >= 0.05 ? h('span', { style: { fontSize: 12 } }, h('span', { style: { color: 'var(--text-muted)' } }, '\u5176\u4E2D\u8F85\u52A9 '), h('span', { style: { color: 'var(--purple)', fontWeight: 600, fontFamily: 'monospace' } }, fmtSign(supMax, 2))) : null,
            Math.abs(spiritMax) >= 0.05 ? h('span', { style: { fontSize: 12 } }, h('span', { style: { color: 'var(--text-muted)' } }, '\u5176\u4E2D\u7CBE\u9B44\u8F85\u52A9 '), h('span', { style: { color: 'var(--orange)', fontWeight: 600, fontFamily: 'monospace' } }, fmtSign(spiritMax, 2))) : null
          )
        ),
        // EHP row
        ehp !== 0 ? h('div', { style: { fontSize: 12, color: 'var(--text-muted)', paddingLeft: 12 } }, 'EHP ', h('span', { style: { color: 'var(--cyan)', fontWeight: 600, fontFamily: 'monospace' } }, fmtSign(ehp))) : null
      )
    );
  });

  aurasStatic.forEach(a => {
    var dps = a.dps_pct || 0;
    var bare = a.bare_dps_pct || 0;
    var sup = a.supports_extra_pct || 0;
    var spiritSup = a.spirit_support_pct || 0;
    var ehp = a.ehp_pct || 0;
    var spirit = Math.round(a.spirit_cost || 0);

    auraCards.push(
      h('div', { key: a.name, style: { background: 'rgba(255,255,255,0.03)', border: '1px solid var(--border)', borderRadius: 8, padding: '16px', marginBottom: 10 } },
        // Header
        h('div', { style: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 } },
          h('span', { style: { fontWeight: 700, fontSize: 15, color: '#fff' } },
            '\u2728 ' + a.name + (a.simulated ? ' \u26a0' : '')
          ),
          h('span', { className: 'tag tag-blue' }, '\u7CBE\u9B44\u6D88\u8017 ' + spirit)
        ),
        // Data row
        h('div', { style: { display: 'flex', alignItems: 'center', gap: 20, flexWrap: 'wrap' } },
          h('span', { style: { fontSize: 14 } }, h('span', { style: { color: 'var(--text-muted)' } }, 'DPS '), h('span', { style: { color: dps >= 0 ? 'var(--green)' : 'var(--red)', fontWeight: 800, fontFamily: 'monospace', fontSize: 16 } }, fmtSign(dps))),
          Math.abs(bare) >= 0.05 ? h('span', { style: { fontSize: 12 } }, h('span', { style: { color: 'var(--text-muted)' } }, '\u88F8\u5149\u73AF '), h('span', { style: { color: 'var(--green)', fontWeight: 600, fontFamily: 'monospace' } }, fmtSign(bare))) : null,
          Math.abs(sup) >= 0.05 ? h('span', { style: { fontSize: 12 } }, h('span', { style: { color: 'var(--text-muted)' } }, '\u5176\u4E2D\u8F85\u52A9 '), h('span', { style: { color: 'var(--purple)', fontWeight: 600, fontFamily: 'monospace' } }, fmtSign(sup, 2))) : null,
          Math.abs(spiritSup) >= 0.05 ? h('span', { style: { fontSize: 12 } }, h('span', { style: { color: 'var(--text-muted)' } }, '\u5176\u4E2D\u7CBE\u9B44\u8F85\u52A9 '), h('span', { style: { color: 'var(--orange)', fontWeight: 600, fontFamily: 'monospace' } }, fmtSign(spiritSup, 2))) : null,
          ehp !== 0 ? h('span', { style: { fontSize: 12 } }, h('span', { style: { color: 'var(--text-muted)' } }, 'EHP '), h('span', { style: { color: 'var(--cyan)', fontWeight: 600, fontFamily: 'monospace' } }, fmtSign(ehp))) : null
        )
      )
    );
  });

  return h('div', { className: 'chart-box full-width' },
    h('div', { className: 'chart-title' }, '\u2728 \u5149\u73AF\u8D21\u732E\u5206\u6790'),
    h('div', null, auraCards)
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

  var effectiveCandidates = candidates.filter(function(c) { return (c.dps_pct || 0) > 0.1; });
  var zeroCandidates = candidates.filter(function(c) { return (c.dps_pct || 0) <= 0.1; });
  var hasCandidates = candidates.length > 0;
  var hasSpirit = spiritSupports.length > 0;
  var hasBudget = budget.total > 0;

  if (!hasCandidates && !hasSpirit && !hasBudget && topTests.length === 0) return null;

  return h('div', { className: 'chart-box full-width' },
    // 精魄预算
    hasBudget && h('div', { style: { marginBottom: 12 } },
      h('div', { className: 'chart-title' }, '\ud83d\udcb0 \u7CBE\u9B42\u9884\u7B97'),
      h('div', { style: { display: 'flex', gap: 20, fontSize: 13, padding: '4px 8px' } },
        h('span', null, '\u603B\u8BA1: ', h('b', null, Math.round(budget.total || 0))),
        h('span', null, '\u5DF2\u7528: ', h('b', { style: { color: 'var(--orange)' } }, Math.round(budget.reserved || 0))),
        h('span', null, '\u53EF\u7528: ', h('b', { style: { color: budget.available > 0 ? 'var(--green)' : 'var(--red)' } }, Math.round(budget.available || 0)))
      )
    ),
    // 现有光环的精魄辅助
    hasSpirit && h('div', { style: { marginBottom: 12 } },
      h('div', { className: 'chart-title' }, '\ud83d\uddff \u7CBE\u9B42\u8F85\u52A9\u5B9D\u77F3'),
      h('table', null,
        h('thead', null, h('tr', null,
          h('th', null, '\u5149\u73AF'), h('th', null, '\u8F85\u52A9'), h('th', null, '\u7CBE\u9B42'), h('th', null, '\u6548\u679C')
        )),
        h('tbody', null,
          spiritSupports.map(function(sp) {
            return sp.supports.map(function(s, si) {
              return h('tr', { key: sp.aura + si },
                si === 0 ? h('td', { rowSpan: sp.supports.length, style: { color: 'var(--accent)', fontWeight: 500 } }, sp.aura) : null,
                h('td', null, s.name),
                h('td', null, Math.round(s.spirit || 0)),
                h('td', { style: { color: 'var(--text-secondary)', fontSize: 11 } },
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
    // 候选光环推荐（过滤 0% DPS，分组显示）
    (effectiveCandidates.length > 0 || zeroCandidates.length > 0) && h('div', { style: { marginBottom: 12 } },
      h('div', { className: 'chart-title' }, '\ud83d\udca1 \u6F5C\u5728\u5149\u73AF\u63A8\u8350'),
      effectiveCandidates.length > 0 && h('table', null,
        h('thead', null, h('tr', null,
          h('th', null, '\u5149\u73AF'), h('th', null, 'DPS'), h('th', null, '\u7CBE\u9B42'), h('th', null, '\u6761\u4EF6/\u5907\u6CE8')
        )),
        h('tbody', null,
          effectiveCandidates.map(function(c, i) {
            var cond = c.sim_condition || '';
            var spiritNote = c.spirit_note ? '; ' + c.spirit_note : '';
            // 条件模拟范围
            var ranges = c.config_ranges || [];
            var rangeStr = ranges.map(function(r) {
              return r.condition_label + ': +' + (r.dps_pct_min || 0).toFixed(1) + '% ~ +' + (r.dps_pct_max || 0).toFixed(1) + '%';
            }).join('; ');
            var condDisplay = [cond, rangeStr, spiritNote ? spiritNote.slice(2) : ''].filter(function(s) { return s; }).join(' | ');
            return h('tr', { key: i },
              h('td', null, c.name),
              h('td', { style: { color: 'var(--green)' } },
                fmtSign(c.dps_pct || 0),
                ranges.length > 0 && h('span', { style: { fontSize: 10, color: 'var(--text-muted)', display: 'block' } },
                  '\u8303\u56F4: +' + fmt(ranges[0].dps_pct_min || 0, 1) + '% ~ +' + fmt(ranges[0].dps_pct_max || 0, 1) + '%')
              ),
              h('td', null, Math.round(c.spirit || 0)),
              h('td', { style: { color: 'var(--text-secondary)', fontSize: 11 } }, condDisplay)
            );
          })
        )
      ),
      zeroCandidates.length > 0 && h('div', { style: { marginTop: 6, fontSize: 12, color: 'var(--text-muted)' } },
        '\u65E0DPS\u5F71\u54CD: ' + zeroCandidates.map(function(c) { return c.name; }).join(', ')
      )
    ),
    // 精魄辅助推荐 Top 5
    topTests.length > 0 && h('div', null,
      h('div', { className: 'chart-title' }, '\ud83c\udfc6 \u7CBE\u9B42\u8F85\u52A9\u63A8\u8350 Top ' + topTests.length),
      h('table', null,
        h('thead', null, h('tr', null,
          h('th', null, '\u8F85\u52A9'), h('th', null, '\u76EE\u6807\u5149\u73AF'), h('th', null, 'DPS'), h('th', null, '\u7CBE\u9B42')
        )),
        h('tbody', null,
          topTests.map(function(t, i) {
            return h('tr', { key: i },
              h('td', null, t.name || ''),
              h('td', { style: { color: 'var(--text-secondary)' } }, t.target_aura || ''),
              h('td', { style: { color: 'var(--green)' } }, fmtSign(t.dps_pct || 0)),
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
    return h('div', { style: { background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: 6, padding: '8px 12px', fontSize: 13 } },
      h('div', { style: { fontWeight: 600, color: d.color } }, d.name, ' (', d.type, ')'),
      h('div', null, 'DPS: ', h('span', { style: { color: 'var(--text-primary)' } }, fmtSign(d.x))),
      h('div', null, 'EHP: ', h('span', { style: { color: 'var(--text-primary)' } }, fmtSign(d.y))),
      h('div', { style: { color: 'var(--text-secondary)', fontSize: 11 } }, d.category)
    );
  };

  return h('div', { className: 'chart-box' },
    h('div', { className: 'chart-title' }, '\ud83d\uddfa\ufe0f 天赋价值矩阵'),
    h(ResponsiveContainer, { width: '100%', height: 300 },
      h(ScatterChart, { margin: { top: 5, right: 20, left: 10, bottom: 5 } },
        h(CartesianGrid, { strokeDasharray: '3 3', stroke: 'var(--border)' }),
        h(XAxis, { dataKey: 'x', tick: { fill: 'var(--text-muted)', fontSize: 11 }, tickFormatter: v => fmtSign(v, 0), label: { value: 'DPS%', position: 'insideBottom', offset: -2, fill: 'var(--text-secondary)', fontSize: 11 } }),
        h(YAxis, { dataKey: 'y', tick: { fill: 'var(--text-muted)', fontSize: 11 }, tickFormatter: v => fmtSign(v, 0), label: { value: 'EHP%', angle: -90, position: 'insideLeft', fill: 'var(--text-secondary)', fontSize: 11 } }),
        h(Tooltip, { content: CustomTooltip }),
        h(Scatter, { data, fill: 'var(--accent)', opacity: 0.8 })
      )
    )
  );
}

// ── Defence Radar (SVG) ──
function DefenceRadar({ baseline }) {
  if (!baseline) return null;
  // Dynamic max: use 1.5× actual value (min 1) so radar scales to the build
  // No hardcoded POE1-era caps
  const dynMax = (v) => Math.max(Math.ceil((v || 0) * 1.5), 1);
  const metrics = [
    { key: 'Life', label: '生命', max: dynMax(baseline.Life), value: baseline.Life || 0 },
    { key: 'ES', label: '护盾', max: dynMax(baseline.EnergyShield), value: baseline.EnergyShield || 0 },
    { key: 'Evasion', label: '闪避', max: dynMax(baseline.MeleeEvasion), value: baseline.MeleeEvasion || 0 },
    { key: 'Armour', label: '护甲', max: dynMax(baseline.ArmourDefense), value: baseline.ArmourDefense || 0 },
    { key: 'EHP', label: '有效生命', max: dynMax(baseline.TotalEHP), value: baseline.TotalEHP || 0 },
    { key: 'Mana', label: '魔力', max: dynMax(baseline.Mana), value: baseline.Mana || 0 },
  ];
  const n = metrics.length;
  const cx = 160, cy = 150, r = 90;
  const levels = [0.25, 0.5, 0.75, 1.0];
  const angle = (i) => (Math.PI * 2 * i / n) - Math.PI / 2;

  return h('div', { className: 'chart-box', style: { display: 'flex', flexDirection: 'column', alignItems: 'center' } },
    h('div', { className: 'chart-title' }, '\ud83d\udce1 防御属性雷达图'),
    h('svg', { width: 340, height: 320, viewBox: '0 0 340 320', style: { overflow: 'visible' } },
      // Grid
      levels.map(lv => {
        const pts = [];
        for (let i = 0; i < n; i++) {
          const a = angle(i);
          pts.push(`${cx + Math.cos(a) * r * lv},${cy + Math.sin(a) * r * lv}`);
        }
        return h('polygon', { key: lv, points: pts.join(' '), fill: 'none', stroke: 'var(--border)', strokeWidth: 1 });
      }),
      // Axes
      metrics.map((m, i) => {
        const a = angle(i);
        const x2 = cx + Math.cos(a) * r;
        const y2 = cy + Math.sin(a) * r;
        return h('line', { key: m.key, x1: cx, y1: cy, x2, y2, stroke: 'var(--border)', strokeWidth: 1 });
      }),
      // Data polygon
      (() => {
        const pts = metrics.map((m, i) => {
          const a = angle(i);
          const val = Math.min(m.value / m.max, 1);
          return `${cx + Math.cos(a) * r * val},${cy + Math.sin(a) * r * val}`;
        });
        return h('polygon', { points: pts.join(' '), fill: 'rgba(91, 154, 255, 0.12)', stroke: 'var(--accent)', strokeWidth: 2 });
      })(),
      // Data points + labels
      metrics.map((m, i) => {
        const a = angle(i);
        const val = Math.min(m.value / m.max, 1);
        const px = cx + Math.cos(a) * r * val;
        const py = cy + Math.sin(a) * r * val;
        const lx = cx + Math.cos(a) * (r + 28);
        const ly = cy + Math.sin(a) * (r + 28);
        const anchor = Math.abs(Math.cos(a)) < 0.1 ? 'middle' : (Math.cos(a) > 0 ? 'start' : 'end');
        const labelText = (m.label || m.key) + ' (' + Math.round(m.value).toLocaleString() + ')';
        return h('g', { key: m.key },
          h('circle', { cx: px, cy: py, r: 4, fill: 'var(--accent)' }),
          h('text', { x: lx, y: ly + 4, textAnchor: anchor, fill: 'var(--text-secondary)', fontSize: 11 },
            labelText)
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
      h('thead', null, h('tr', null, h('th', null, '名称'), h('th', null, '类型'), h('th', null, 'DPS%'), h('th', null, 'EHP%'), h('th', null, '分类'), h('th', null, '效果'))),
      h('tbody', null,
        [...talents].sort((a, b) => a.dps_pct - b.dps_pct).map(t => {
          var desc = (t.description || '-').replace(/; /g, '\n');
          return h('tr', { key: t.id || t.name },
            h('td', { style: { fontWeight: 500, whiteSpace: 'nowrap' } }, t.name),
            h('td', { style: { whiteSpace: 'nowrap' } }, t.type),
            h('td', { style: { color: t.dps_pct >= 0 ? 'var(--green)' : 'var(--red)', fontFamily: 'monospace', fontSize: 12, whiteSpace: 'nowrap' } }, fmtSign(t.dps_pct)),
            h('td', { style: { color: t.ehp_pct >= 0 ? 'var(--green)' : 'var(--red)', fontFamily: 'monospace', fontSize: 12, whiteSpace: 'nowrap' } }, fmtSign(t.ehp_pct)),
            h('td', { style: { whiteSpace: 'nowrap' } }, h('span', { style: { color: CATEGORY_COLORS[t.category] || 'var(--text-secondary)' } }, t.category)),
            h('td', { style: { color: 'var(--text-muted)', fontSize: 11, whiteSpace: 'pre-line', lineHeight: 1.4 } }, desc)
          );
        })
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
          h('td', { style: { color: 'var(--text-secondary)', fontSize: 11 } }, s.formula || '')
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
  }).sort(function(a, b) { return b.dps_pct - a.dps_pct; }).slice(0, 20);

  var defence = talents.filter(function(t) {
    return t.category === '\u751f\u5b58' || t.category === '\u517c\u987e';
  }).sort(function(a, b) { return b.ehp_pct - a.ehp_pct; }).slice(0, 20);

  // 去重：已在输出榜的兼顾节点不重复出现在生存榜
  var offenceIds = new Set(offence.map(function(t) { return t.id; }));
  var defenceFiltered = defence.filter(function(t) {
    return !(t.category === '\u517c\u987e' && offenceIds.has(t.id));
  }).slice(0, 20);

  function makeTable(title, items, sortKey) {
    if (items.length === 0) return null;
    return h(DetailSection, { title: title, defaultOpen: false },
      h('table', null,
        h('thead', null, h('tr', null, h('th', null, '\u540d\u79f0'), h('th', null, '\u7c7b\u578b'), h('th', null, 'DPS%'), h('th', null, 'EHP%'), h('th', null, '\u6548\u679c'))),
        h('tbody', null,
          items.map(function(t) {
            var desc = (t.description || '-').replace(/; /g, '\n');
            return h('tr', { key: t.id || t.name },
              h('td', { style: { fontWeight: 500, whiteSpace: 'nowrap' } }, t.name),
              h('td', { style: { color: 'var(--text-muted)', fontSize: 11, whiteSpace: 'nowrap' } }, t.type),
              h('td', { style: { color: 'var(--green)', whiteSpace: 'nowrap' } }, fmtSign(t.dps_pct)),
              h('td', { style: { color: t.ehp_pct >= 0 ? 'var(--green)' : 'var(--red)', whiteSpace: 'nowrap' } }, fmtSign(t.ehp_pct)),
              h('td', { style: { color: 'var(--text-muted)', fontSize: 11, whiteSpace: 'pre-line', lineHeight: 1.4 } }, desc)
            );
          })
        )
      )
    );
  }

  return h('div', null,
    h('div', { style: { color: 'var(--text-muted)', fontSize: 11, marginBottom: 4 } },
      '\u603b\u5019\u9009 ' + talents.length + ' \u4e2a\uff0c\u5206\u522b\u5c55\u793a\u8fdb\u653b/\u9632\u5fa1 TOP 20'),
    makeTable('\u8f93\u51fa TOP 20', offence, 'dps_pct'),
    makeTable('\u751f\u5b58 TOP 20', defenceFiltered, 'ehp_pct')
  );
}

function JewelDiagnosisTable({ jewels }) {
  if (!jewels || jewels.length === 0) return null;
  var sorted = jewels.slice().sort(function(a, b) { return Math.abs(b.dps_pct || 0) - Math.abs(a.dps_pct || 0); });
  var gridStyle = { display: 'grid', gridTemplateColumns: '180px 100px 70px 70px 50px', gap: '8px', alignItems: 'center' };
  var headerStyle = { color: 'var(--text-muted)', fontSize: 11, fontWeight: 600, padding: '4px 0' };
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
        var rarityColor = j.rarity === 'UNIQUE' ? 'var(--accent)' : 'var(--text-secondary)';
        var hasMods = mods.length > 0;
        return h('div', { key: i },
          // Summary row
          h('div', { style: Object.assign({}, gridStyle, { borderBottom: '1px solid rgba(46,46,74,0.2)', padding: '4px 0' }) },
            h('span', { style: Object.assign({}, cellStyle, { color: rarityColor, fontSize: 12, fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }) }, j.name || '\u2014'),
            h('span', { style: Object.assign({}, cellStyle, { color: 'var(--text-muted)', fontSize: 11, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }) }, (j.base_type || '') + ' \u00b7 ' + (j.slot_name || '')),
            h('span', { style: Object.assign({}, cellStyle, { textAlign: 'right', color: 'var(--green)', fontFamily: 'monospace', fontSize: 12 }) }, fmtSign(dpsTotal)),
            h('span', { style: Object.assign({}, cellStyle, { textAlign: 'right', color: ehpTotal > 0.01 ? 'var(--cyan)' : 'var(--text-muted)', fontFamily: 'monospace', fontSize: 12 }) }, fmtSign(ehpTotal)),
            h('span', { style: Object.assign({}, cellStyle, { textAlign: 'right', color: 'var(--text-muted)', fontSize: 10 }) }, hasMods ? mods.length : '')
          ),
          // Mod details - same grid layout (no paddingLeft, use prefix in first column)
          hasMods && h('div', { style: { borderBottom: '1px solid rgba(46,46,74,0.15)' } },
            mods.map(function(m, mi) {
              var dpsVal = m.dps_pct || 0;
              var ehpVal = m.ehp_pct || 0;
              var suffix = (m.type === 'INC') ? '%' : '';
              var hasImpact = dpsVal > 0.01 || ehpVal > 0.01;
              return h('div', { key: mi, style: Object.assign({}, gridStyle, { padding: '2px 0', background: 'var(--border)' }) },
                h('span', { style: { color: hasImpact ? 'var(--text-primary)' : 'var(--text-muted)', fontSize: 11, paddingLeft: 12, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' } }, '\u2022 ' + m.name),
                h('span', { style: { color: 'var(--text-primary)', fontFamily: 'monospace', fontSize: 11 } }, '+' + m.value + suffix + ' ' + (m.type || '')),
                h('span', { style: { textAlign: 'right', color: dpsVal > 0.01 ? 'var(--green)' : '#444460', fontFamily: 'monospace', fontSize: 11 } }, dpsVal > 0.01 ? '+' + dpsVal.toFixed(2) + '%' : '-'),
                h('span', { style: { textAlign: 'right', color: ehpVal > 0.01 ? 'var(--cyan)' : '#444460', fontFamily: 'monospace', fontSize: 11 } }, ehpVal > 0.01 ? '+' + ehpVal.toFixed(2) + '%' : '-'),
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
      // Skill selector (dropdown)
      h('div', { className: 'skill-selector' },
        h('label', { htmlFor: 'skill-select' }, '\u2694\uFE0F 技能选择: '),
        h('select', {
          id: 'skill-select',
          value: activeTab,
          onChange: function(e) { setActiveTab(e.target.value); },
          style: {
            background: 'var(--bg-card)', color: 'var(--accent)',
            border: '2px solid rgba(91, 154, 255, 0.35)', borderRadius: '24px',
            padding: '10px 24px', fontSize: 15,
            fontWeight: '700', cursor: 'pointer',
            minWidth: 240, outline: 'none',
            boxShadow: '0 2px 10px rgba(91, 154, 255, 0.2)'
          }
        },
          skillNames.map(function(name) {
            var icon = '\ud83d\udcdd'; // default scroll
            // 从 damage_composition 推断主元素图标
            var skillData = currentSkillsData[name] || {};
            var dc = skillData.damage_composition || [];
            if (dc.length > 0) {
              var _elemIcons = { Lightning: '\u26a1', Cold: '\u2744', Fire: '\ud83d\udd25', Physical: '\u2694', Chaos: '\ud83d\udd2e' };
              var totalHit = dc.reduce(function(s, e) { return s + e.hit_avg; }, 0) || 1;
              var bestPct = 0, bestElem = '';
              for (var i = 0; i < dc.length; i++) {
                var pct = dc[i].hit_avg / totalHit;
                if (pct > bestPct) { bestPct = pct; bestElem = dc[i].element || ''; }
              }
              if (bestPct >= 0.4 && _elemIcons[bestElem]) icon = _elemIcons[bestElem];
            }
            var displayName = name.charAt(0).toUpperCase() + name.slice(1).replace(/_/g, ' ');
            displayName = displayName.replace(/\s*\((.+?)\)\s*/, ' \u2014 $1');
            return h('option', { key: name, value: name }, icon + ' ' + displayName);
          })
        )
      ),
      // Skill KPI cards (per-tab)
      h('div', { className: 'kpi-row' },
        [
          { label: 'TotalDPS', value: fmtComma(skillDps), cls: 'val-accent' },
          { label: 'AverageHit', value: fmtComma(avgHit), cls: 'val-orange' },
          { label: 'Speed', value: fmt(speed, 2) + '/s', cls: 'val-cyan' },
          { label: 'CritChance', value: fmt(cc, 1) + '%', cls: 'val-purple' },
          { label: 'CritMultiplier', value: fmt(cm, 2) + 'x', cls: 'val-positive' },
        ].map(function(k) {
          return h('div', { className: 'kpi-card', key: k.label },
            h('div', { className: 'label' }, k.label),
            h('div', { className: 'value ' + k.cls }, k.value)
          );
        })
      ),
      // Skill-specific sections
      h(DamagePieChart, { data: data.dps_breakdown }),
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
            h('td', { style: { color: (d.delta_pct || 0) >= 0 ? 'var(--green)' : 'var(--red)' } },
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
              h('td', { style: { color: (s.delta_pct || 0) >= 0 ? 'var(--green)' : 'var(--red)' } },
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
