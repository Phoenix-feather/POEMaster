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
    
    # 获取构筑中的技能列表（同时收集 gemData.name 和 skillId）
    build_var = build or "_spike_build"
    result = lua.execute(f'''
        local names = {{}}
        local ids = {{}}
        local build = {build_var}
        if build.skillsTab and build.skillsTab.socketGroupList then
            for _, g in ipairs(build.skillsTab.socketGroupList) do
                local gemList = g.gems or g.gemList or {{}}
                for _, gem in ipairs(gemList) do
                    -- 优先 gem.name，其次 gem.gemData.name，最后 gem.skillId
                    local n = gem.name
                        or (gem.gemData and gem.gemData.name)
                        or nil
                    if n then names[#names+1] = n end
                    if gem.skillId then ids[#ids+1] = gem.skillId end
                end
            end
        end
        return table.concat(names, "|") .. "||" .. table.concat(ids, "|")
    ''')
    
    parts = str(result).split("||", 1)
    build_skills = set(parts[0].split("|")) if parts[0] else set()
    build_skill_ids = set(parts[1].split("|")) if len(parts) > 1 and parts[1] else set()
    
    # 匹配配置中的技能
    detected = []
    for skill_name, skill_config in config["skills"].items():
        # 跳过精魄辅助：已装备的精魄辅助 POB 会原生计算其效果，
        # 不需要在光环分析中重复注入。精魄辅助的模拟仅用于推荐测试
        # （_test_add_spirit_support 中对未装备辅助的效果预估）。
        if skill_config.get("skill_type") == "spirit_support":
            continue
        # 跳过原生计算的主动技能：POB 已原生计算其效果，注入会导致双倍计算
        if skill_config.get("skill_type") == "active_native":
            continue

        detect = skill_config.get("detect", {})
        detect_type = detect.get("type", "gem_name")
        
        matched = False
        if detect_type == "gem_name":
            matched = detect.get("name", skill_name) in build_skills
        elif detect_type == "skill_id":
            matched = detect.get("skill_id", "") in build_skill_ids
        elif detect_type == "stat_pattern":
            # TODO: 支持通过 constantStats 模式匹配
            pass
        
        if matched:
            effects = skill_config.get("effects", [])
            if effects:
                # 解析动态值
                resolved_effects = _resolve_dynamic_values(
                    lua, effects, skill_config, build_var)
                
                asc_node = skill_config.get("ascendancy_node", {})
                desc = resolved_effects[0].get("description", skill_name) if resolved_effects else skill_name
                detected.append({
                    "skill_name": skill_name,
                    "effects": resolved_effects,
                    "asc_pattern": asc_node.get("pattern", ""),
                    "description": desc,
                    "stat_skill_id": skill_config.get("stat_skill_id", ""),
                    "expect_factor": skill_config.get("expect_factor", 1.0),
                })
                logger.info("检测到 POB 未实现技能: %s (%d 个效果)", skill_name, len(resolved_effects))
    
    return detected


def _resolve_dynamic_values(lua, effects: list[dict], skill_config: dict,
                            build_var: str = "_spike_build") -> list[dict]:
    """解析效果中的动态值（如 charge_based、stack_based）。

    对于 value=null 的效果，根据 dynamic_value 配置从构筑数据中计算实际值。

    Args:
        lua: LuaRuntime
        effects: 原始效果列表
        skill_config: 技能配置（含 dynamic_value）
        build_var: Lua build 变量名

    Returns:
        解析后的效果列表（value 已填充）
    """
    dynamic_cfg = skill_config.get("dynamic_value")
    if not dynamic_cfg:
        # 无动态配置，直接返回（value=null 的效果保持不变）
        return effects

    resolved = []
    for eff in effects:
        eff = dict(eff)  # 浅拷贝
        if eff.get("value") is not None:
            resolved.append(eff)
            continue

        dyn_type = dynamic_cfg.get("type", "")

        if dyn_type == "charge_based":
            # 从构筑 output 读取 charge 数量
            charge_stat = dynamic_cfg.get("charge_stat", "PowerChargesMax")
            per_charge = dynamic_cfg.get("per_charge_value", 0)
            quality_per = dynamic_cfg.get("quality_per_charge", 0)

            # 读取构筑的 charge 数量和宝石品质
            charge_count, quality = _read_charge_and_quality(
                lua, skill_config, charge_stat, build_var)

            if charge_count > 0:
                value = charge_count * (per_charge + quality * quality_per)
                eff["value"] = round(value, 2)
                eff["description"] = (
                    f"{charge_count:.0f} × ({per_charge}%"
                    f"{f' + {quality:.0f}×{quality_per}%' if quality_per and quality else ''})"
                    f" = {value:.0f}% MORE 元素伤害（{charge_stat}）")
                logger.info("动态值解析: %s -> %s = %.1f",
                           skill_config.get("detect", {}).get("skill_id", "?"),
                           charge_stat, value)
            else:
                eff["value"] = 0
                eff["description"] = f"无 {charge_stat}，效果为 0"

        elif dyn_type == "stack_based":
            # TODO: 实现层数型动态值（如 Demon Form）
            pass

        resolved.append(eff)

    return resolved


def _read_charge_and_quality(lua, skill_config: dict, charge_stat: str,
                             build_var: str = "_spike_build") -> tuple:
    """从构筑中读取 charge 数量和宝石品质。

    对于装备附带的技能（fromItem/Grants Skill），POB 硬编码 quality=0，
    不会将武器品质传递给 Grants Skill。本函数补偿这个 POB bug：
    如果 gem.quality=0，从武器物品读取品质。

    补偿策略：遍历所有武器 slot（Weapon 1, Weapon 2, Weapon 1 Swap, Weapon 2 Swap），
    检查其物品的 grantedSkills 是否包含目标 skillId。

    Returns:
        (charge_count, quality)
    """
    skill_id = skill_config.get("detect", {}).get("skill_id", "")

    # 先计算一次 baseline 获取 output，同时读取 gem 品质
    # 使用 .format() 避免 f-string 中 Lua 大括号转义问题
    lua_code = """
        local build = {build_var}
        local env = calcs.initEnv(build, "MAIN")
        calcs.perform(env)
        local charges = env.player.output.{charge_stat} or 0
        local gemQuality = 0
        local weaponQuality = 0

        -- 查找该技能的 gem quality
        for _, g in ipairs(build.skillsTab.socketGroupList) do
            for _, gem in ipairs(g.gemList or {{}}) do
                if gem.skillId == "{skill_id}" then
                    gemQuality = gem.quality or 0
                    break
                end
            end
            if gemQuality ~= 0 then break end
        end

        -- POB bug 补偿: gem.quality=0 时，从武器物品读取品质
        if gemQuality == 0 then
            local weaponSlotNames = {{"Weapon 1", "Weapon 2", "Weapon 1 Swap", "Weapon 2 Swap"}}
            for _, sn in ipairs(weaponSlotNames) do
                local slot = build.itemsTab.slots[sn]
                if slot then
                    local it = build.itemsTab.items[slot.selItemId]
                    if it and it.grantedSkills then
                        for _, gs in ipairs(it.grantedSkills) do
                            if gs.skillId == "{skill_id}" then
                                weaponQuality = it.quality or 0
                                break
                            end
                        end
                    end
                end
                if weaponQuality > 0 then break end
            end
        end

        return tostring(charges) .. "|" .. tostring(gemQuality) .. "|" .. tostring(weaponQuality)
    """.format(build_var=build_var, charge_stat=charge_stat, skill_id=skill_id)

    charge_result = lua.execute(lua_code)

    if charge_result and str(charge_result) != "nil":
        parts = str(charge_result).split("|")
        try:
            charge_count = float(parts[0])
            gem_quality = float(parts[1]) if len(parts) > 1 else 0
            weapon_quality = float(parts[2]) if len(parts) > 2 else 0

            # POB bug 补偿：gem quality=0 时，使用武器品质
            if gem_quality == 0 and weapon_quality > 0:
                logger.info("POB bug 补偿: %s gem.quality=0, 使用武器品质=%.0f",
                           skill_id, weapon_quality)
                gem_quality = weapon_quality

            return charge_count, gem_quality
        except (ValueError, IndexError):
            pass

    return 0, 0


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
