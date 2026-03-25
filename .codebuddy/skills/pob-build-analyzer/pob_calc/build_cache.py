#!/usr/bin/env python3
"""
构筑缓存管理器。

职责：
  - 将 share code 解码为 XML 并缓存到磁盘
  - 维护 current.txt 指针，标识当前活跃构筑
  - 支持列表、删除（按序号/范围）、全部清理
  - LRU 自动淘汰，默认保留最近 10 个构筑

目录结构：
  cache/
  ├── current.txt                           ← 当前活跃 build_id
  └── builds/
      ├── Monk_Invoker_Lv98_a3f7b2c1/
      │   ├── build.xml                     ← 解码后 XML
      │   └── meta.json                     ← 元信息 + 技能列表
      └── ...
"""
from __future__ import annotations
import hashlib
import json
import logging
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

from .decoder import decode_share_code
from .build_parser import parse_build_xml

logger = logging.getLogger(__name__)

# 默认 cache 根目录：技能目录下的 cache/
_DEFAULT_CACHE_DIR = Path(__file__).parent.parent / "cache"

_MAX_BUILDS = 10


class BuildCache:
    """构筑缓存管理器。

    Args:
        cache_dir: 缓存根目录，默认为技能目录下的 cache/
        max_builds: 最大保留构筑数，默认 10
    """

    def __init__(self, cache_dir: Path = None, max_builds: int = _MAX_BUILDS):
        self._cache_dir = Path(cache_dir) if cache_dir else _DEFAULT_CACHE_DIR
        self._builds_dir = self._cache_dir / "builds"
        self._current_file = self._cache_dir / "current.txt"
        self._max_builds = max_builds

        # 确保目录存在
        self._builds_dir.mkdir(parents=True, exist_ok=True)

    # -----------------------------------------------------------------
    # 保存
    # -----------------------------------------------------------------

    def save(self, share_code: str) -> str:
        """解码 share code 并缓存，设为当前活跃构筑。

        如果同一构筑已存在（XML hash 相同），跳过写入（幂等），
        但仍更新 current 指针和 last_used。

        Args:
            share_code: POB 分享码

        Returns:
            build_id 字符串
        """
        # 1. 解码
        xml_text = decode_share_code(share_code)

        # 2. 解析 XML 提取元数据
        build_info = parse_build_xml(xml_text)

        # 3. 生成 build_id
        build_id = self._make_build_id(build_info, xml_text)

        # 4. 写入（幂等）
        build_dir = self._builds_dir / build_id
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")

        if build_dir.exists():
            # 已存在，仅更新 last_used
            self._update_last_used(build_dir, now)
            logger.info("构筑已存在，更新 last_used: %s", build_id)
        else:
            build_dir.mkdir(parents=True, exist_ok=True)

            # 写 build.xml
            (build_dir / "build.xml").write_text(xml_text, encoding="utf-8")

            # 写 meta.json
            meta = self._build_meta(build_id, build_info, now)
            (build_dir / "meta.json").write_text(
                json.dumps(meta, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            logger.info("新构筑已缓存: %s", build_id)

        # 5. 设为当前
        self._set_current(build_id)

        # 6. LRU 清理
        self._prune()

        return build_id

    # -----------------------------------------------------------------
    # 加载
    # -----------------------------------------------------------------

    def load_current(self) -> str:
        """加载当前活跃构筑的 XML 文本。

        Returns:
            XML 文本

        Raises:
            FileNotFoundError: 无活跃构筑或文件缺失
        """
        build_id = self.get_current_id()
        if not build_id:
            raise FileNotFoundError("没有活跃构筑，请先调用 save() 缓存一个构筑")
        return self.load(build_id)

    def load(self, build_id: str) -> str:
        """加载指定构筑的 XML 文本。

        Args:
            build_id: 构筑 ID

        Returns:
            XML 文本
        """
        xml_file = self._builds_dir / build_id / "build.xml"
        if not xml_file.exists():
            raise FileNotFoundError(f"构筑不存在: {build_id}")

        # 更新 last_used
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self._update_last_used(self._builds_dir / build_id, now)

        return xml_file.read_text(encoding="utf-8")

    # -----------------------------------------------------------------
    # 当前构筑指针
    # -----------------------------------------------------------------

    def get_current_id(self) -> str | None:
        """获取当前活跃构筑的 build_id。"""
        if not self._current_file.exists():
            return None
        bid = self._current_file.read_text(encoding="utf-8").strip()
        if not bid:
            return None
        # 验证对应目录存在
        if not (self._builds_dir / bid).exists():
            logger.warning("current 指向不存在的构筑: %s", bid)
            self._current_file.unlink(missing_ok=True)
            return None
        return bid

    def set_current(self, build_id: str):
        """切换当前活跃构筑。

        Args:
            build_id: 目标构筑 ID

        Raises:
            FileNotFoundError: 构筑不存在
        """
        if not (self._builds_dir / build_id).exists():
            raise FileNotFoundError(f"构筑不存在: {build_id}")
        self._set_current(build_id)

    # -----------------------------------------------------------------
    # 列表
    # -----------------------------------------------------------------

    def list(self) -> list[dict]:
        """列出所有缓存的构筑，按 last_used 降序排列。

        Returns:
            [meta_dict, ...]，每个包含 build_id, class_name, ascendancy,
            level, created_at, last_used, skills, is_current
        """
        current_id = self.get_current_id()
        result = []

        for build_dir in sorted(self._builds_dir.iterdir()):
            if not build_dir.is_dir():
                continue
            meta_file = build_dir / "meta.json"
            if not meta_file.exists():
                continue
            try:
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue

            meta["is_current"] = (meta.get("build_id") == current_id)
            result.append(meta)

        # 按 last_used 降序
        result.sort(key=lambda m: m.get("last_used", ""), reverse=True)
        return result

    # -----------------------------------------------------------------
    # 删除
    # -----------------------------------------------------------------

    def remove(self, indices: str):
        """按序号删除构筑。

        序号基于 list() 的结果（1-based）。
        支持格式: "3", "2-5", "1,3,5", "2-4,7"

        Args:
            indices: 序号表达式
        """
        builds = self.list()
        to_remove = self._parse_indices(indices, len(builds))

        current_id = self.get_current_id()
        removed = []

        for idx in sorted(to_remove, reverse=True):
            meta = builds[idx]
            build_id = meta["build_id"]
            build_dir = self._builds_dir / build_id
            if build_dir.exists():
                shutil.rmtree(build_dir)
                removed.append(build_id)
                logger.info("已删除构筑: %s", build_id)

                # 如果删的是当前构筑，清除指针
                if build_id == current_id:
                    self._current_file.unlink(missing_ok=True)

        return removed

    def clear_all(self):
        """清空全部缓存（包括 current 指针）。"""
        if self._builds_dir.exists():
            shutil.rmtree(self._builds_dir)
            self._builds_dir.mkdir(parents=True, exist_ok=True)
        self._current_file.unlink(missing_ok=True)
        logger.info("已清空全部构筑缓存")

    # -----------------------------------------------------------------
    # 报告持久化
    # -----------------------------------------------------------------

    def save_report(self, build_id: str, skill_name: str,
                    analysis_data: dict, report_md: str):
        """将分析结果和格式化报告持久化到构筑目录。

        文件命名：analysis_{skill}.json / report_{skill}.md
        skill 名称规范化：小写，空格→下划线，去除特殊字符。

        Args:
            build_id: 构筑 ID
            skill_name: 技能名称（如 "Spark", "Ball Lightning"）
            analysis_data: full_analysis() 的返回值
            report_md: format_report() 生成的 Markdown 字符串
        """
        build_dir = self._builds_dir / build_id
        if not build_dir.exists():
            raise FileNotFoundError(f"构筑不存在: {build_id}")

        slug = self._normalize_skill_name(skill_name)

        # 写 analysis JSON
        json_path = build_dir / f"analysis_{slug}.json"
        json_path.write_text(
            json.dumps(analysis_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        # 写 report MD
        md_path = build_dir / f"report_{slug}.md"
        md_path.write_text(report_md, encoding="utf-8")

        logger.info("报告已保存: %s → %s, %s", build_id, json_path.name, md_path.name)

    def get_report_path(self, build_id: str, skill_name: str,
                        fmt: str = "md") -> Path | None:
        """获取报告文件的绝对路径。

        Args:
            build_id: 构筑 ID
            skill_name: 技能名称
            fmt: "md" 或 "json"

        Returns:
            文件路径，若不存在则返回 None
        """
        build_dir = self._builds_dir / build_id
        slug = self._normalize_skill_name(skill_name)
        prefix = "report" if fmt == "md" else "analysis"
        path = build_dir / f"{prefix}_{slug}.{fmt}"
        return path if path.exists() else None

    def load_report(self, build_id: str, skill_name: str,
                    fmt: str = "md") -> str | None:
        """读取已保存的报告。

        Args:
            build_id: 构筑 ID
            skill_name: 技能名称
            fmt: "md"（Markdown 报告）或 "json"（原始 JSON 数据）

        Returns:
            文件内容字符串，不存在则返回 None
        """
        path = self.get_report_path(build_id, skill_name, fmt)
        if path is None:
            return None
        return path.read_text(encoding="utf-8")

    @staticmethod
    def _normalize_skill_name(name: str) -> str:
        """规范化技能名为文件名安全的 slug。

        "Ball Lightning" → "ball_lightning"
        "Spark" → "spark"
        """
        slug = name.lower().strip()
        slug = re.sub(r'[^a-z0-9]+', '_', slug)
        slug = slug.strip('_')
        return slug or "unknown"

    # -----------------------------------------------------------------
    # 内部方法
    # -----------------------------------------------------------------

    def _make_build_id(self, build_info: dict, xml_text: str) -> str:
        """生成 build_id: {class}_{ascendancy}_Lv{level}_{hash[:8]}"""
        cls = build_info.get("className", "Unknown") or "Unknown"
        asc = build_info.get("ascendClassName", "") or ""
        level = build_info.get("level", 0)
        xml_hash = hashlib.sha256(xml_text.encode("utf-8")).hexdigest()[:8]

        # 清理非法文件名字符
        cls = re.sub(r'[^\w]', '', cls)
        asc = re.sub(r'[^\w]', '', asc)

        if asc:
            return f"{cls}_{asc}_Lv{level}_{xml_hash}"
        else:
            return f"{cls}_Lv{level}_{xml_hash}"

    def _build_meta(self, build_id: str, build_info: dict,
                    now: str) -> dict:
        """构建 meta.json 内容。"""
        # 静态提取技能列表（不需要 Lua）
        skills = []
        for i, group in enumerate(build_info.get("skillGroups", []), 1):
            gems = group.get("gems", [])
            gem_names = [
                g.get("nameSpec", g.get("skillId", "?"))
                for g in gems
            ]
            if gem_names:
                skills.append({
                    "group": i,
                    "gems": gem_names,
                })

        xml_hash = build_id.rsplit("_", 1)[-1] if "_" in build_id else ""

        return {
            "build_id": build_id,
            "class_name": build_info.get("className", ""),
            "ascendancy": build_info.get("ascendClassName", ""),
            "level": build_info.get("level", 0),
            "hash": xml_hash,
            "created_at": now,
            "last_used": now,
            "main_socket_group": build_info.get("mainSocketGroup", 1),
            "skills": skills,
        }

    def _set_current(self, build_id: str):
        """写入 current.txt。"""
        self._current_file.write_text(build_id, encoding="utf-8")

    def _update_last_used(self, build_dir: Path, now: str):
        """更新 meta.json 的 last_used 字段。"""
        meta_file = build_dir / "meta.json"
        if not meta_file.exists():
            return
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            meta["last_used"] = now
            meta_file.write_text(
                json.dumps(meta, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("更新 last_used 失败: %s", e)

    def _prune(self):
        """LRU 清理：超过 max_builds 时删除最旧的。"""
        builds = self.list()
        if len(builds) <= self._max_builds:
            return

        current_id = self.get_current_id()

        # 从最旧的开始删，不删当前活跃的
        to_delete = builds[self._max_builds:]
        for meta in to_delete:
            build_id = meta["build_id"]
            if build_id == current_id:
                continue  # 不删当前活跃构筑
            build_dir = self._builds_dir / build_id
            if build_dir.exists():
                shutil.rmtree(build_dir)
                logger.info("LRU 淘汰: %s", build_id)

    @staticmethod
    def _parse_indices(expr: str, total: int) -> list[int]:
        """解析序号表达式为 0-based 索引列表。

        支持: "3", "2-5", "1,3,5", "2-4,7"
        """
        indices = set()
        for part in expr.split(","):
            part = part.strip()
            if "-" in part:
                a, b = part.split("-", 1)
                start = int(a.strip())
                end = int(b.strip())
                for i in range(start, end + 1):
                    if 1 <= i <= total:
                        indices.add(i - 1)
            else:
                i = int(part)
                if 1 <= i <= total:
                    indices.add(i - 1)
        return sorted(indices)


def format_build_list(builds: list[dict]) -> str:
    """将构筑列表格式化为可读的表格字符串。

    Args:
        builds: BuildCache.list() 的返回值

    Returns:
        Markdown 表格字符串
    """
    if not builds:
        return "（无缓存构筑）"

    lines = []
    lines.append("| # | 构筑 | 等级 | 主要技能 | 最后使用 |")
    lines.append("|---|------|------|----------|----------|")

    for i, m in enumerate(builds, 1):
        bid = m.get("build_id", "?")
        marker = " ★" if m.get("is_current") else ""
        level = m.get("level", "?")

        # 提取主要技能名（每组第一个宝石，过滤辅助类）
        skill_names = []
        for sg in m.get("skills", []):
            gems = sg.get("gems", [])
            if gems:
                skill_names.append(gems[0])
        # 去重保持顺序，最多显示 5 个
        seen = set()
        unique = []
        for name in skill_names:
            if name not in seen:
                seen.add(name)
                unique.append(name)
        display_skills = ", ".join(unique[:5])
        if len(unique) > 5:
            display_skills += f" +{len(unique)-5}"

        # 时间
        last_used = m.get("last_used", "")
        if last_used:
            try:
                dt = datetime.fromisoformat(last_used)
                diff = datetime.now(timezone.utc) - dt
                if diff.days > 0:
                    time_str = f"{diff.days} 天前"
                elif diff.seconds > 3600:
                    time_str = f"{diff.seconds // 3600} 小时前"
                elif diff.seconds > 60:
                    time_str = f"{diff.seconds // 60} 分钟前"
                else:
                    time_str = "刚刚"
            except (ValueError, TypeError):
                time_str = last_used[:10]
        else:
            time_str = "?"

        lines.append(f"| {i} | {bid}{marker} | {level} | {display_skills} | {time_str} |")

    return "\n".join(lines)
