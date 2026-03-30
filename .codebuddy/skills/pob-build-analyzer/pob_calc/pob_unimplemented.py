"""POB 未实现效果管理模块。

用途：
- POB 的 SkillStatMap.lua 未映射某些技能的 stats，导致 DPS 计算缺失
- 本模块从配置文件读取这些效果，提供统一的注入和估算接口
- 在升华分析、what_if 等多处可用

配置文件：config/pob_unimplemented_effects.yaml
"""

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_config_cache = None


def load_config() -> dict:
    """加载 POB 未实现效果配置（带缓存）。"""
    global _config_cache
    if _config_cache is not None:
        return _config_cache
    
    try:
        import yaml
        config_path = Path(__file__).parent.parent / "config" / "pob_unimplemented_effects.yaml"
        if not config_path.exists():
            logger.warning("POB 未实现效果配置文件不存在: %s", config_path)
            _config_cache = {}
            return _config_cache
        
        with open(config_path, encoding='utf-8') as f:
            _config_cache = yaml.safe_load(f) or {}
        logger.info("已加载 POB 未实现效果配置: %d 个技能", len(_config_cache.get("skills", {})))
        return _config_cache
    except Exception as e:
        logger.error("加载 POB 未实现效果配置失败: %s", e)
        _config_cache = {}
        return _config_cache


def detect_unimplemented_skills(lua, build=None) -> list[dict]:
    """检测构筑中有哪些 POB 未实现的技能。
    
    Args:
        lua: LuaRuntime 实例
        build: Lua build 对象（可选，默认用 _spike_build）
    
    Returns:
        [{skill_name, effects, asc_pattern, description}, ...]
    """
    config = load_config()
    if not config.get("skills"):
        return []
    
    # 获取构筑中的技能列表
    build_var = build or "_spike_build"
    skill_names_result = lua.execute(f'''
        local names = {{}}
        local build = {build_var}
        if build.skillsTab and build.skillsTab.socketGroupList then
            for _, g in ipairs(build.skillsTab.socketGroupList) do
                if g.gemList then
                    for _, gem in ipairs(g.gemList) do
                        if gem.gemData and gem.gemData.name then
                            names[#names+1] = gem.gemData.name
                        end
                    end
                end
            end
        end
        return table.concat(names, "|")
    ''')
    
    build_skills = set(str(skill_names_result).split("|")) if skill_names_result else set()
    
    # 匹配配置中的技能
    detected = []
    for skill_name, skill_config in config["skills"].items():
        detect = skill_config.get("detect", {})
        detect_type = detect.get("type", "gem_name")
        
        matched = False
        if detect_type == "gem_name":
            matched = detect.get("name", skill_name) in build_skills
        elif detect_type == "stat_pattern":
            # TODO: 支持通过 constantStats 模式匹配
            pass
        
        if matched:
            effects = skill_config.get("effects", [])
            if effects:
                asc_node = skill_config.get("ascendancy_node", {})
                desc = effects[0].get("description", skill_name) if effects else skill_name
                detected.append({
                    "skill_name": skill_name,
                    "effects": effects,
                    "asc_pattern": asc_node.get("pattern", ""),
                    "description": desc,
                })
                logger.info("检测到 POB 未实现技能: %s (%d 个效果)", skill_name, len(effects))
    
    return detected


def get_effects_for_skill(skill_name: str) -> list[dict]:
    """获取指定技能的未实现效果列表。
    
    Args:
        skill_name: 技能名称
    
    Returns:
        [{type, mod_name, mod_type, value, source, description}, ...]
    """
    config = load_config()
    skill_config = config.get("skills", {}).get(skill_name, {})
    return skill_config.get("effects", [])


def inject_effects_to_lua(lua, effects: list[dict], env_var: str = "env") -> str:
    """生成注入效果到 Lua modDB 的代码。
    
    Args:
        lua: LuaRuntime（用于转义）
        effects: 效果列表
        env_var: Lua 环境变量名（默认 'env'）
    
    Returns:
        Lua 代码片段
    """
    if not effects:
        return ""
    
    lines = []
    for eff in effects:
        if eff.get("type") != "mod":
            continue
        
        mod_name = eff.get("mod_name", "")
        mod_type = eff.get("mod_type", "BASE")
        value = eff.get("value", 0)
        source = eff.get("source", "unimpl_config")
        
        # 数值类型处理
        if isinstance(value, float):
            value_str = f"{value}"
        elif isinstance(value, int):
            value_str = f"{value}"
        else:
            value_str = f'"{value}"'
        
        lines.append(f'{env_var}.player.modDB:NewMod("{mod_name}", "{mod_type}", {value_str}, "{source}")')
    
    return "\n".join(lines)


def estimate_dps_impact(lua, calcs, effects: list[dict], 
                        baseline_dps: float = None,
                        build_var: str = "_spike_build",
                        mode: str = "MAIN") -> dict:
    """估算注入未实现效果后的 DPS 变化。
    
    Args:
        lua: LuaRuntime 实例
        calcs: POB calcs 模块
        effects: 效果列表
        baseline_dps: 基准 DPS（可选，不传则自动计算）
        build_var: Lua build 变量名
        mode: POB 计算模式
    
    Returns:
        {
            "baseline_dps": float,
            "estimated_dps": float,
            "delta_pct": float,
            "description": str
        }
    """
    if not effects:
        return {
            "baseline_dps": baseline_dps or 0,
            "estimated_dps": baseline_dps or 0,
            "delta_pct": 0,
            "description": "无未实现效果"
        }
    
    # 计算 baseline
    if baseline_dps is None:
        result = lua.execute(f'''
            local build = {build_var}
            local env = calcs.initEnv(build, "{mode}")
            calcs.perform(env)
            return env.player.output.TotalDPS or 0
        ''')
        baseline_dps = float(result) if result else 0
    
    # 注入效果并计算
    inject_code = inject_effects_to_lua(lua, effects, env_var="env2")
    
    result = lua.execute(f'''
        local build = {build_var}
        local env2 = calcs.initEnv(build, "{mode}")
        {inject_code}
        calcs.perform(env2)
        return env2.player.output.TotalDPS or 0
    ''')
    estimated_dps = float(result) if result else 0
    
    delta_pct = (estimated_dps - baseline_dps) / baseline_dps * 100 if baseline_dps > 0 else 0
    
    # 描述
    desc = effects[0].get("description", "") if effects else ""
    
    return {
        "baseline_dps": baseline_dps,
        "estimated_dps": estimated_dps,
        "delta_pct": delta_pct,
        "description": desc
    }


def format_estimate_report(estimate: dict, node_name: str = "") -> list[str]:
    """格式化预估效果报告。
    
    Args:
        estimate: estimate_dps_impact 的返回值
        node_name: 关联的节点名称（可选）
    
    Returns:
        报告行列表
    """
    lines = []
    if estimate["delta_pct"] == 0:
        return lines
    
    lines.append(f"**⚠️ POB 未实现效果预估**: {node_name or '技能效果'}")
    lines.append(f"- {estimate['description']}")
    lines.append(f"- 预估收益: **+{estimate['delta_pct']:.1f}%** DPS")
    lines.append("")
    
    return lines


def scan_pob_for_unimplemented_stats(pob_data_dir: str) -> list[dict]:
    """扫描 POB 数据目录，找出所有在 SkillStatMap 中未映射的 stats。
    
    Args:
        pob_data_dir: POB Data 目录路径
    
    Returns:
        [{stat_name, skill_name, value, file}, ...]
    """
    import re
    from pathlib import Path
    
    pob_path = Path(pob_data_dir)
    if not pob_path.exists():
        logger.error("POB 数据目录不存在: %s", pob_data_dir)
        return []
    
    # 1. 加载 SkillStatMap 中的所有已映射 stats
    ssm_path = pob_path / "Data" / "SkillStatMap.lua"
    mapped_stats = set()
    if ssm_path.exists():
        with open(ssm_path, encoding='utf-8') as f:
            content = f.read()
            # 匹配 ["stat_name"] = { ... }
            matches = re.findall(r'\["([^"]+)"\]\s*=', content)
            mapped_stats = set(matches)
        logger.info("SkillStatMap 中已映射 %d 个 stats", len(mapped_stats))
    
    # 2. 扫描所有技能文件的 constantStats
    unimplemented = []
    skills_dir = pob_path / "Data" / "Skills"
    
    if skills_dir.exists():
        for skill_file in skills_dir.glob("*.lua"):
            try:
                with open(skill_file, encoding='utf-8') as f:
                    content = f.read()
                
                # 匹配 constantStats = { {"stat_name", value}, ... }
                # 找所有 constantStats 块
                pattern = r'constantStats\s*=\s*\{([^}]+)\}'
                for match in re.finditer(pattern, content, re.DOTALL):
                    stats_block = match.group(1)
                    # 提取 {"stat_name", value}
                    stat_matches = re.findall(r'\{\s*"([^"]+)"\s*,\s*([^}\s]+)', stats_block)
                    
                    for stat_name, value in stat_matches:
                        if stat_name not in mapped_stats:
                            # 跳过 display_ 开头的（通常只是显示用）
                            if stat_name.startswith("display_"):
                                continue
                            
                            # 尝试找技能名
                            skill_name = "?"
                            name_match = re.search(r'label\s*=\s*"([^"]+)"', content[match.start()-500:match.start()])
                            if name_match:
                                skill_name = name_match.group(1)
                            
                            unimplemented.append({
                                "stat_name": stat_name,
                                "skill_name": skill_name,
                                "value": value,
                                "file": str(skill_file.name)
                            })
            except Exception as e:
                logger.debug("扫描文件失败 %s: %s", skill_file, e)
    
    logger.info("发现 %d 个未映射的 stats（来自 %d 个技能文件）", 
                len(unimplemented), len(set(u["file"] for u in unimplemented)))
    
    # 去重并排序
    seen = set()
    unique = []
    for u in unimplemented:
        key = (u["stat_name"], u["skill_name"])
        if key not in seen:
            seen.add(key)
            unique.append(u)
    
    unique.sort(key=lambda x: (x["skill_name"], x["stat_name"]))
    
    return unique
