"""光环与精魄分析模块（Section 7）。

职责：
- aura_spirit_analysis: 光环贡献分析主函数
- 所有子函数: config_test, mod_sim, skill_info, spirit_support 等
"""
import logging
from .calculator import calculate
from .data_bridge import POEDataBridge
from .sensitivity import _cap_all_gem_qualities

logger = logging.getLogger(__name__)

# =============================================================================
# Section 7: 光环与精魄分析 (Aura & Spirit Analysis)
# =============================================================================
#
# 设计文档（explore 模式确认）：
#   7A — 现有光环/精魄移除测试
#   7B — 潜在光环推荐（6 个非 Herald 候选）
#   7C — 精魄辅助推荐（DPS 相关 + 估算）
#   7D — Spirit Budget 汇总
#
# 机制确认：
#   - Blasphemy 已排除（太复杂）
#   - Herald 已排除（攻击构筑特有，用户自带）
#   - Direstrike Low Life 条件：按满足条件计算，标注
#   - Refraction III：纳入但标记为估算
#   - Precision：POB 完整支持 Accuracy → HitChance → DPS 链路
#   - Deadly Herald：仅限 Herald 技能，8A 已覆盖
#
# 候选光环（8B，6 个）：
#   Trinity(100), Archmage(100), Charge Infusion(60),
#   Attrition(60), Berserk(60), Elemental Conflux(60)
#
# 候选精魄辅助（8C，4+1 个）：
#   Direstrike I(20), Direstrike II(40), Precision I(10), Precision II(20),
#   Refraction III(30, 估算)

# 光环预设配置映射（7A 测试时需要启用条件配置）
# key = 光环名称, value = [{"var": "configVar", "value": bool|int}, ...]
# Charge 数量在运行时从构筑 output 动态读取（见 _resolve_charge_configs）
_AURA_PRE_CONFIGS = {
    "Charge Infusion": [
        {"var": "useFrenzyCharges", "value": True},
        {"var": "overrideFrenzyCharges", "value": None},  # 动态: FrenzyChargesMax
        {"var": "usePowerCharges", "value": True},
        {"var": "overridePowerCharges", "value": None},   # 动态: PowerChargesMax
        {"var": "useEnduranceCharges", "value": True},
        {"var": "overrideEnduranceCharges", "value": None},  # 动态: EnduranceChargesMax
    ],
}

# 需要通过注入 mod 模拟的光环（POB 不计算的动态效果）
# 格式：{"mod": {...}, "expect_factor": 期望系数}
# mod.value 在运行时从构筑实际宝石等级动态填充（见 _resolve_ec_more_value）
_AURA_INJECT_MODS = {
    "Elemental Conflux": {
        "mod": {
            # value 在运行时从构筑 EC 宝石等级动态读取（statSets[1].levels[level][1]）
            # Level 20=59%, Level 21=60% 等
            "name": "ElementalDamage", "type": "MORE", "value": None,
        },
        "stat_skill_id": "ElementalConfluxPlayer",
        "expect_factor": 1/3,  # 简化：假设构筑只用一种元素
        "description": "每8秒随机选择火/冰/电，给该元素 MORE 伤害。期望收益 = MORE * 元素占比",
    },
}


def _merge_unimplemented_effects(lua) -> dict:
    """检测构筑中的 POB 未实现技能，合并到注入配置。
    
    Args:
        lua: LuaRuntime 实例
    
    Returns:
        合并后的 _AURA_INJECT_MODS
    """
    try:
        from .pob_unimplemented import detect_unimplemented_skills
        
        # 检测构筑中的未实现技能
        detected = detect_unimplemented_skills(lua)
        
        # 转换为 _AURA_INJECT_MODS 格式
        merged = dict(_AURA_INJECT_MODS)  # 复制
        
        for item in detected:
            skill_name = item["skill_name"]
            effects = item.get("effects", [])
            
            if effects and skill_name not in merged:
                # 取第一个 mod 效果
                for eff in effects:
                    if eff.get("type") == "mod":
                        merged[skill_name] = {
                            "mod": {
                                "name": eff.get("mod_name"),
                                "type": eff.get("mod_type"),
                                "value": eff.get("value"),
                                "source": eff.get("source", ""),
                            },
                            "description": eff.get("description", skill_name),
                            "stat_skill_id": item.get("stat_skill_id", ""),
                            "expect_factor": item.get("expect_factor", 1.0),
                            "level_index": eff.get("level_index", 1),
                            "all_effects": [e for e in effects if e.get("type") == "mod"],
                        }
                        logger.info("从配置加载未实现效果: %s -> %s (%d effects)",
                                   skill_name, eff.get("mod_name"),
                                   len([e for e in effects if e.get("type") == "mod"]))
                        break
        return merged
    except Exception as e:
        logger.debug("加载未实现效果配置失败: %s", e)
        return _AURA_INJECT_MODS

# 光环/精魄候选数据
_AURA_CANDIDATES = [
    {
        "key": "trinity",
        "name": "Trinity",
        "name_cn": "三位一体",
        "skill_id": "TrinityPlayer",
        "spirit": 100,
        "description": "三属性穿透（需要 ResonanceCount 配置）",
    },
    {
        "key": "archmage",
        "name": "Archmage",
        "name_cn": "大法师",
        "skill_id": "ArchmagePlayer",
        "spirit": 100,
        "description": "Mana 转附加闪电伤害",
    },
    {
        "key": "charge_infusion",
        "name": "Charge Infusion",
        "name_cn": "充能灌注",
        "skill_id": "ChargeRegulationPlayer",
        "spirit": 60,
        "description": "Frenzy/Power/Endurance Charge 增益",
        "charge_configs": [
            {"var": "useFrenzyCharges", "type": "check", "value": True},
            {"var": "overrideFrenzyCharges", "type": "count", "value": None},  # 动态
            {"var": "usePowerCharges", "type": "check", "value": True},
            {"var": "overridePowerCharges", "type": "count", "value": None},   # 动态
            {"var": "useEnduranceCharges", "type": "check", "value": True},
            {"var": "overrideEnduranceCharges", "type": "count", "value": None},  # 动态
        ],
    },
    {
        "key": "attrition",
        "name": "Attrition",
        "name_cn": "损耗",
        "skill_id": "AttritionPlayer",
        "spirit": 60,
        "description": "命中附带 Wither 叠层",
    },
    {
        "key": "berserk",
        "name": "Berserk",
        "name_cn": "狂暴",
        "skill_id": "BerserkPlayer",
        "spirit": 60,
        "description": "MORE Damage + 受伤增加",
    },
    {
        "key": "elemental_conflux",
        "name": "Elemental Conflux",
        "name_cn": "元素交融",
        "skill_id": "ElementalConfluxPlayer",
        "spirit": 60,
        "description": "元素异常状态同步",
    },
]

# ==============================================================================
# 精魄辅助候选配置（混合方案）
# ==============================================================================
#
# 本列表包含高价值的精魄辅助，提供精确的中文名称和详细说明。
# 
# 混合方案说明：
#   1. 硬编码候选（本列表）: 5 个核心辅助，有详细标注
#   2. 动态扫描候选: 从 POB data.gems 自动发现所有精魄辅助
#   3. 合并去重: 使用 merge_candidates() 函数合并，优先保留硬编码版本
#
# 工作流程：
#   discover_spirit_supports(lua)  →  动态扫描发现 25+ 个辅助
#          ↓
#   merge_candidates(硬编码, 动态)  →  合并并去重
#          ↓
#   filter_spirit_supports()       →  根据构筑类型过滤
#          ↓
#   测试并返回 Top 5               →  只显示最有效的结果
#
# 优势：
#   - 硬编码候选: 用户友好的中文名称、详细说明、已知条件标注
#   - 动态扫描候选: 自动发现新宝石，无需手动维护
#   - 去重机制: 避免重复，硬编码版本优先（更好的描述）
#
# 示例：
#   硬编码: "猛击 I" (Direstrike I, 有中文标注)
#   动态扫描: "Direstrike I" (无中文标注)
#   合并结果: 保留硬编码版本
#
# 参考：
#   - discover_spirit_supports(): 动态扫描函数
#   - merge_candidates(): 合并去重函数
#   - filter_spirit_supports(): 智能过滤函数
#
# 维护说明：
#   - 只需添加高价值、需要详细标注的辅助
#   - 其他辅助会自动从 POB 数据库发现
#   - POB 更新后无需手动同步
# ==============================================================================

_SPIRIT_SUPPORT_CANDIDATES = [
    {
        "key": "direstrike_1",
        "name": "Direstrike I",
        "name_cn": "猛击 I",
        "skill_id": "SupportDirestrikePlayer",
        "spirit": 20,
        "description": "攻击伤害 INC 50%",
        "condition": "Low Life",
        "note": "需要 Low Life 状态",
    },
    {
        "key": "direstrike_2",
        "name": "Direstrike II",
        "name_cn": "猛击 II",
        "skill_id": "SupportDirestrikePlayerTwo",
        "spirit": 40,
        "description": "攻击伤害 INC 70%",
        "condition": "Low Life",
        "note": "需要 Low Life 状态",
    },
    {
        "key": "precision_1",
        "name": "Precision I",
        "name_cn": "精准 I",
        "skill_id": "SupportPrecisionPlayer",
        "spirit": 10,
        "description": "命中 INC 30%",
        "condition": "仅攻击构筑",
        "note": "",
    },
    {
        "key": "precision_2",
        "name": "Precision II",
        "name_cn": "精准 II",
        "skill_id": "SupportPrecisionPlayerTwo",
        "spirit": 20,
        "description": "命中 INC 50%",
        "condition": "仅攻击构筑",
        "note": "",
    },
    {
        "key": "refraction_3",
        "name": "Refraction III",
        "name_cn": "折射 III",
        "skill_id": "SupportRefractionPlayerThree",
        "spirit": 30,
        "description": "每 1000 护甲 +2 元素暴露",
        "condition": "需要 Banner",
        "note": "POB 可能无法计算，标记为估算",
        "estimated": True,
    },
]


def _generate_support_description(gem_data: dict, granted_effect: dict) -> str:
    """为动态发现的精魄辅助生成描述。
    
    Args:
        gem_data: POB data.gems 中的宝石数据
        granted_effect: POB data.skills 中的 grantedEffect 数据
    
    Returns:
        描述字符串
    """
    # 优先使用 grantedEffect.description
    if granted_effect and granted_effect.get("description"):
        return granted_effect["description"]
    
    # 其次尝试从 statDescription 提取
    if granted_effect and granted_effect.get("statDescription"):
        # 简化：只取第一行
        stat_desc = granted_effect["statDescription"]
        if isinstance(stat_desc, str):
            return stat_desc.split("\n")[0]
    
    # 最后生成默认描述
    name = gem_data.get("name", "Unknown Support")
    return f"{name}: 精魄辅助效果"


def discover_spirit_supports(lua) -> list[dict]:
    """动态发现所有精魄辅助宝石。
    
    扫描 POB 的 data.gems 数据库，找出所有消耗精魄的辅助宝石。
    
    Args:
        lua: LuaRuntime 实例
    
    Returns:
        [{name, skill_id, spirit, description}, ...]
        - name: 宝石名称
        - skill_id: grantedEffectId
        - spirit: 精魄消耗
        - description: 效果描述
    """
    import time
    start_time = time.time()
    
    result = lua.execute('''
        local discovered = {}
        local idx = 1
        local count = 0
        
        -- 扫描 data.skills 而不是 data.gems
        -- 精魄辅助定义在 data.skills 中
        for skill_id, skill in pairs(data.skills) do
            -- 只处理 Support 技能
            if skill.support and skill.levels then
                -- 从最高等级读取精魄消耗
                local maxLevel = 0
                for lvl, _ in pairs(skill.levels) do
                    if lvl > maxLevel then maxLevel = lvl end
                end
                
                if maxLevel > 0 then
                    local levelData = skill.levels[maxLevel]
                    if levelData and levelData.spiritReservationFlat then
                        local spiritCost = levelData.spiritReservationFlat
                        
                        -- 只保留精魄消耗 > 0 的技能
                        if spiritCost > 0 then
                            count = count + 1
                            local desc = skill.description or ""
                            
                            discovered[idx] = {
                                name = skill.name or skill_id,
                                skill_id = skill_id,
                                spirit = spiritCost,
                                description = desc,
                            }
                            idx = idx + 1
                        end
                    end
                end
            end
        end
        
        -- 返回计数和列表
        return count, discovered
    ''')
    
    elapsed_ms = (time.time() - start_time) * 1000
    
    # 处理双重返回值 (count, table)
    logger.info("Lua 返回值类型: %s", type(result))
    logger.info("Lua 返回值: %s", result)
    
    if not result:
        logger.info("动态扫描发现 0 个精魄辅助 (%.0fms) - result 为空", elapsed_ms)
        return []
    
    # 检查是否是 tuple (多个返回值)
    if isinstance(result, tuple):
        logger.info("Lua 返回了 %d 个值", len(result))
        if len(result) < 2:
            logger.info("动态扫描发现 0 个精魄辅助 (%.0fms) - 返回值不足", elapsed_ms)
            return []
        count = result[0]
        table = result[1]
    else:
        # 可能是单返回值（table），检查结构
        logger.info("Lua 返回单个值，检查结构...")
        # 假设返回的是 {count, discovered}
        if hasattr(result, '__len__') and len(result) >= 2:
            count = result[0]
            table = result[1]
        else:
            logger.info("动态扫描发现 0 个精魄辅助 (%.0fms) - 无法解析返回值", elapsed_ms)
            return []
    
    logger.info("count = %s, table type = %s", count, type(table))
    
    if not table or count == 0:
        logger.info("动态扫描发现 0 个精魄辅助 (%.0fms) - count=0 或 table 为空", elapsed_ms)
        return []
    
    # 转换为 Python dict 列表
    # Lua 返回的 table，直接遍历
    discovered = []
    try:
        # 方法：使用 lupa 的 items() 遍历
        if hasattr(table, 'items'):
            logger.debug("使用 items() 遍历 Lua table")
            for key, item in table.items():
                # item 是 LuaTable，使用 [] 访问字段
                if item:
                    try:
                        # LuaTable 使用 [] 访问字段
                        name = item["name"] if "name" in item else ""
                        skill_id = item["skill_id"] if "skill_id" in item else ""
                        spirit = item["spirit"] if "spirit" in item else 0
                        description = item["description"] if "description" in item else ""
                        
                        discovered.append({
                            "name": str(name) if name else "",
                            "skill_id": str(skill_id) if skill_id else "",
                            "spirit": int(spirit) if spirit else 0,
                            "description": str(description) if description else "",
                        })
                    except Exception as e:
                        logger.warning("处理单个 item 失败: %s", e)
        else:
            # 备用方法：直接用索引遍历
            logger.debug("使用索引遍历 Lua table")
            i = 1
            while i <= count:
                try:
                    item = table[i]
                    if item:
                        name = item["name"] if "name" in item else ""
                        skill_id = item["skill_id"] if "skill_id" in item else ""
                        spirit = item["spirit"] if "spirit" in item else 0
                        description = item["description"] if "description" in item else ""
                        
                        discovered.append({
                            "name": str(name) if name else "",
                            "skill_id": str(skill_id) if skill_id else "",
                            "spirit": int(spirit) if spirit else 0,
                            "description": str(description) if description else "",
                        })
                except Exception as e:
                    logger.debug("索引 %d 失败: %s", i, e)
                i += 1
    except Exception as e:
        logger.error("遍历 Lua 结果失败: %s", e)
        import traceback
        traceback.print_exc()
    
    logger.info("动态扫描发现 %d 个精魄辅助 (%.0fms)", 
                len(discovered), elapsed_ms)
    
    return discovered


def filter_spirit_supports(candidates: list[dict], 
                          is_attack: bool, 
                          is_spell: bool,
                          skill_tags: dict = None) -> list[dict]:
    """根据构筑特征过滤精魄辅助候选。
    
    Args:
        candidates: 候选列表 [{name, skill_id, spirit, description, ...}, ...]
        is_attack: 是否为攻击构筑
        is_spell: 是否为法术构筑
        skill_tags: 技能标签字典（可选）
    
    Returns:
        过滤后的候选列表
    """
    filtered = []
    skipped_count = 0
    
    for candidate in candidates:
        skip = False
        reason = ""
        
        # 1. 硬编码候选的已知条件过滤
        condition = candidate.get("condition", "")
        if condition:
            # 精确匹配已知条件
            if "仅攻击构筑" in condition and not is_attack:
                skip = True
                reason = "仅攻击构筑"
            elif "Low Life" in condition and is_spell:
                # 法术构筑通常不是 Low Life 构筑
                skip = True
                reason = "需要 Low Life"
        
        # 2. 基于名称的启发式过滤（动态候选）
        name = candidate.get("name", "").lower()
        skill_id = candidate.get("skill_id", "").lower()
        
        if not skip and is_spell:
            # 法术构筑：过滤攻击专属辅助
            attack_keywords = ["precision", "direstrike", "melee", "attack speed"]
            if any(kw in name or kw in skill_id for kw in attack_keywords):
                # 进一步检查：如果名字里明确标注是攻击相关
                if "precision" in name or "direstrike" in name:
                    skip = True
                    reason = "攻击专属辅助"
        
        if not skip and is_attack:
            # 攻击构筑：过滤法术专属辅助
            spell_keywords = ["spell damage", "cast speed", "arcane"]
            if any(kw in name or kw in skill_id for kw in spell_keywords):
                # 进一步检查：如果名字里明确标注是法术相关
                if "spell damage" in name and "attack" not in name:
                    skip = True
                    reason = "法术专属辅助"
        
        if skip:
            skipped_count += 1
            logger.debug("过滤候选: %s (原因: %s)", candidate.get("name"), reason)
        else:
            filtered.append(candidate)
    
    logger.info("过滤精魄辅助: %d 个候选，跳过 %d 个，保留 %d 个",
                len(candidates), skipped_count, len(filtered))
    
    return filtered


def merge_candidates(hardcoded: list[dict], discovered: list[dict]) -> list[dict]:
    """合并硬编码和动态发现的候选，去重并优先保留硬编码。
    
    Args:
        hardcoded: 硬编码候选列表（有详细标注）
        discovered: 动态发现的候选列表
    
    Returns:
        合并后的候选列表
    """
    # 使用 skill_id 作为去重键
    merged = {}
    
    # 先添加动态发现的（优先级低）
    for candidate in discovered:
        skill_id = candidate.get("skill_id", "")
        if skill_id:
            merged[skill_id] = {
                **candidate,
                "source": "dynamic",  # 标记来源
            }
    
    # 再添加硬编码的（覆盖动态发现，优先级高）
    for candidate in hardcoded:
        skill_id = candidate.get("skill_id", "")
        if skill_id:
            merged[skill_id] = {
                **candidate,
                "source": "hardcoded",  # 标记来源
            }
    
    result = list(merged.values())
    logger.info("合并候选: 硬编码 %d + 动态 %d = 合并后 %d",
                len(hardcoded), len(discovered), len(result))
    
    return result


# POB ConfigOptions 中 count 类型的可测试范围上限。
# apply 函数内部用 m_max(m_min(val, N), 0) 做 clamp，
# 测试时传入 99999 让 clamp 自动截断，再从 modDB 读回实际值即可得到真实上限。
_PROBE_MAX = 99999


def _rebuild_config_tab_modlist(lua):
    """重建 build.configTab.modList / enemyModList。

    与 lua_env.LuaEnvManager.rebuild_modlist() 共享相同的 Lua 全局变量
    （_env_sim_mods），确保两套调用路径的状态一致。

    首次调用时从当前 modList 提取 sim mods（source 含 "sim"），
    之后每次：遍历 ConfigOptions 重建 + 追加 sim mods。

    ⚠️ 必须与 POB 原版 ConfigTabClass:BuildModList() 保持一致：
    - count/integer/float 类型：先查 input，再回退到 placeholder
    - check 类型：先查 input，再回退到 defaultState
    - list 类型：先查 input，再回退到 defaultIndex
    如果遗漏 placeholder 回退，auto_configure 设置的 count 配置项
    （如 WitheredStack、DemonFlameStacks 等）在重建时会丢失，
    导致基线偏低约 10.9%。
    """
    lua.execute('''
        local build = _spike_build
        local configSettings = LoadModule("Modules/ConfigOptions")
        if not configSettings then return end

        -- 首次调用时提取 sim mods（与 lua_env.py 共享全局变量名）
        if not _env_sim_mods then
            _env_sim_mods = new("ModList")
            _env_sim_enemy_mods = new("ModList")
            local ml = build.configTab.modList
            if ml then
                for _, m in ipairs(ml) do
                    local src = m.source or ""
                    if src:find("sim") then
                        _env_sim_mods:AddMod(m)
                    end
                end
            end
            local eml = build.configTab.enemyModList
            if eml then
                for _, m in ipairs(eml) do
                    local src = m.source or ""
                    if src:find("sim") then
                        _env_sim_enemy_mods:AddMod(m)
                    end
                end
            end
        end

        -- 遍历 ConfigOptions 重建 modList
        -- 与 POB ConfigTabClass:BuildModList() 保持一致：包含 placeholder 回退
        local modList = new("ModList")
        local enemyModList = new("ModList")
        local input = build.configTab.input
        local placeholder = build.configTab.placeholder or {}
        for _, varData in ipairs(configSettings) do
            if varData.apply then
                local varName = varData.var
                if varData.type == "check" then
                    local val = input[varName]
                    if val == nil and varData.defaultState then val = true end
                    if val then pcall(varData.apply, true, modList, enemyModList, build) end
                elseif varData.type == "count" or varData.type == "integer"
                    or varData.type == "countAllowZero" or varData.type == "float" then
                    local val = input[varName]
                    if val and (val ~= 0 or varData.type ~= "count") then
                        pcall(varData.apply, val, modList, enemyModList, build)
                    elseif placeholder[varName] and (placeholder[varName] ~= 0 or varData.type ~= "count") then
                        pcall(varData.apply, placeholder[varName], modList, enemyModList, build)
                    end
                elseif varData.type == "list" then
                    local val = input[varName]
                    if val == nil and varData.list and varData.defaultIndex then
                        local de = varData.list[varData.defaultIndex]
                        if de then val = de.val end
                    end
                    if val then pcall(varData.apply, val, modList, enemyModList, build) end
                end
            end
        end

        -- ConfigOptions mods + sim mods
        build.configTab.modList = modList
        build.configTab.enemyModList = enemyModList
        if _env_sim_mods then
            build.configTab.modList:AddList(_env_sim_mods)
        end
        if _env_sim_enemy_mods then
            build.configTab.enemyModList:AddList(_env_sim_enemy_mods)
        end
    ''')


def _set_config_and_rebuild(lua, config_var: str, config_type: str, value):
    """设置一个 ConfigTab 配置值并重建 modList。

    Args:
        config_var: 配置变量名（如 'configResonanceCount'）
        config_type: 'count' 或 'check' 或 'list'
        value: 要设置的值
    """
    lua.execute(f'_spike_build.configTab.input["{config_var}"] = {value}')
    _rebuild_config_tab_modlist(lua)


def _discover_ifskill_configs(lua, aura_names: set[str]) -> list[dict]:
    """动态扫描 ConfigOptions，发现所有与构筑光环匹配的 ifSkill count 配置。

    通过 Lua 端遍历 ConfigSettings，匹配 ifSkill 条件（支持字符串和表两种格式），
    返回所有 count/integer/countAllowZero 类型的配置条目。

    Args:
        aura_names: 构筑中光环/精魄预留技能的名称集合

    Returns:
        [{
            "config_var": str,      # 配置变量名
            "config_type": str,     # 'count'/'integer'/'countAllowZero'
            "aura_name": str,       # 匹配的光环名称
            "label": str,           # POB 配置标签
            "actual_max": float,    # apply 函数 clamp 后的真实上限
        }, ...]
    """
    if not aura_names:
        return []

    # 构建 Lua 端的光环名称查找表
    aura_list = ",".join(aura_names)
    lua.execute(f'_aura_names_list = "{aura_list}"')
    result = lua.execute('''
        local configSettings = LoadModule("Modules/ConfigOptions")
        if not configSettings then return "" end

        local auraNames = {}
        for n in _aura_names_list:gmatch("[^,]+") do
            auraNames[n:match("^%s*(.-)%s*$")] = true
        end

        local lines = {}
        for _, varData in ipairs(configSettings) do
            if not varData.var then goto next end

            -- 只处理 count 类型（有范围的数值参数）
            if varData.type ~= "count" and varData.type ~= "integer"
               and varData.type ~= "countAllowZero" then
                goto next
            end

            -- 检查 ifSkill 条件是否匹配
            local matchedAura = nil
            local ifSkill = varData.ifSkill
            if type(ifSkill) == "string" then
                if auraNames[ifSkill] then matchedAura = ifSkill end
            elseif type(ifSkill) == "table" then
                for _, s in ipairs(ifSkill) do
                    if auraNames[s] then matchedAura = s; break end
                end
            end

            if matchedAura then
                lines[#lines+1] = varData.var .. "|" .. varData.type .. "|"
                    .. matchedAura .. "|" .. tostring(varData.label or "")
            end
            ::next::
        end
        return table.concat(lines, "\\n")
    ''')

    configs = []
    if not result:
        return configs

    for line in str(result).split('\n'):
        if not line.strip() or '|' not in line:
            continue
        parts = line.split('|')
        if len(parts) < 4:
            continue
        config_var, config_type, aura_name, label = parts[0], parts[1], parts[2], parts[3]

        # 用 _PROBE_MAX 探测真实上限：用临时 ModList 避免污染 configTab.modList
        # ConfigOptions 的 apply 对 count 类型做 m_max(m_min(val, max), 0)，
        # Sum(BASE, Multiplier:*) 返回 clamp 后的实际最大值。
        # 先保存原始值（保护 auto_configure_combat 设置的值）
        lua.execute(f'_discover_saved_val_{config_var} = _spike_build.configTab.input["{config_var}"]')
        actual_max = lua.execute(f'''
            local configSettings = LoadModule("Modules/ConfigOptions")
            local probeList = new("ModList")
            for _, varData in ipairs(configSettings) do
                if varData.apply and varData.var and varData.var == "{config_var}" then
                    pcall(varData.apply, {_PROBE_MAX}, probeList, nil, _spike_build)
                    break
                end
            end
            -- Sum 正确合并所有同名 mod（ModList 内部双视图不影响 Sum 值）
            local s = 0
            for k, v in pairs(probeList) do
                if type(v) == "table" then
                    for _, mod in ipairs(v) do
                        if type(mod) == "table" and mod.name and mod.name:match("^Multiplier:") then
                            s = math.max(s, tonumber(mod.value) or 0)
                        end
                    end
                end
            end
            return tostring(math.floor(s + 0.5))
        ''')
        try:
            actual_max = float(actual_max)
        except (ValueError, TypeError):
            actual_max = 0.0

        # 恢复探测前的原始值（保护 auto_configure_combat 设置的值）
        lua.execute(f'''
            if _discover_saved_val_{config_var} ~= nil then
                _spike_build.configTab.input["{config_var}"] = _discover_saved_val_{config_var}
            end
            _discover_saved_val_{config_var} = nil
        ''')

        configs.append({
            "config_var": config_var,
            "config_type": config_type,
            "aura_name": aura_name,
            "label": label,
            "actual_max": max(actual_max, 1),
        })

    return configs


def _inject_ifskill_defaults(lua, calcs,
                              aura_configs: list[dict] | None = None):
    """为所有条件光环注入参数中间值（基线配置）。

    动态发现或使用已传入的配置列表，对每个 count 配置注入 min~max 的中间值。
    """
    if aura_configs is None:
        # 动态发现构筑中所有光环名称
        skills_info = _query_active_skills_info(lua, calcs)
        aura_names = {si["main_skill_name"] for si in skills_info if si["is_aura"]}
        aura_configs = _discover_ifskill_configs(lua, aura_names)

    for cfg in aura_configs:
        config_var = cfg["config_var"]
        config_type = cfg["config_type"]
        actual_max = cfg["actual_max"]
        mid = int(actual_max / 2)

        current = lua.execute(f'''
            return tostring(_spike_build.configTab.input["{config_var}"] or "nil")
        ''')
        if str(current) == "nil":
            _set_config_and_rebuild(lua, config_var, config_type, mid)
            logger.info("已注入 %s %s=%d（范围 0~%d）",
                        cfg["aura_name"], config_var, mid, int(actual_max))


def _test_aura_config_range(lua, calcs, aura_name: str,
                            baseline: dict,
                            aura_configs: list[dict] | None = None,
                            no_aura_dps: float = None,
                            group_idx: int = None,
                            spirit_support_ids: set[str] | None = None) -> list[dict]:
    """测试条件光环所有可配置参数在最小/最大值时的 DPS 范围。

    同时测试带辅助和不带辅助的 DPS，返回双列数据。
    精魄辅助不计入"辅助增益"列——辅助增益仅包含普通辅助的贡献。
    使用单个 Lua 代码块完成所有测试，避免 gem.enabled 跨调用恢复问题。

    Args:
        aura_name: 光环名称
        baseline: 当前 baseline（用于恢复状态）
        aura_configs: 已发现的配置列表（避免重复扫描）
        no_aura_dps: 无该光环时的 DPS（作为百分比计算基准）
        group_idx: 光环组索引（用于裸光环测试时禁用辅助）
        spirit_support_ids: 精魄辅助 skill_id 集合，恢复辅助时排除这些

    Returns:
        [{"config_var", "label", "aura_name", "actual_max",
          "dps_pct_min", "dps_pct_max",  // 带辅助（不含精魄辅助）
          "bare_pct_min", "bare_pct_max", // 裸光环（无辅助）
          "spirit_pct_min", "spirit_pct_max", // 精魄辅助独立贡献
          "dps_min", "dps_max", "mid"}, ...]
    """
    if aura_configs is None:
        aura_configs = _discover_ifskill_configs(lua, {aura_name})

    matched = [c for c in aura_configs if c["aura_name"] == aura_name]
    if not matched:
        return []

    base_dps = no_aura_dps if no_aura_dps else baseline.get("TotalDPS", 0)
    bare_base_dps = base_dps  # 裸光环和带辅助用同一个 no_aura_dps 作基准

    from .calculator import calculate as calc_fn

    # Python 循环，每组先测裸光环再测带辅助
    results = []
    for cfg in matched:
        config_var = cfg["config_var"]
        config_type = cfg["config_type"]
        actual_max = cfg["actual_max"]
        mid = int(actual_max / 2)

        # 保存原始值（可能是 auto_configure_combat 设置的）
        original_val = lua.execute(f'''
            return _spike_build.configTab.input["{config_var}"]
        ''')
        try:
            original_val = int(original_val) if original_val is not None else mid
        except (ValueError, TypeError):
            original_val = mid

        # Phase 1: 禁用辅助 → 测裸光环
        lua.execute(f'''
            local build = _spike_build
            local targetName = "{aura_name}"
            local function isAuraGem(gem)
                local ge = gem.grantedEffect or (gem.gemData and gem.gemData.grantedEffect)
                if (ge and ge.name == targetName) or gem.nameSpec == targetName or gem.skillId == targetName then return true end
                if gem.skillId and data.skills[gem.skillId] and data.skills[gem.skillId].name == targetName then return true end
                return false
            end
            for i = 1, #build.skillsTab.socketGroupList do
                local group = build.skillsTab.socketGroupList[i]
                if not group.enabled then goto nextDS end
                local hasAura = false
                for gi, gem in ipairs(group.gemList or {{}}) do
                    if isAuraGem(gem) then hasAura = true; break end
                end
                if not hasAura then goto nextDS end
                for gi, gem in ipairs(group.gemList or {{}}) do
                    if not isAuraGem(gem) then gem.enabled = false end
                end
                ::nextDS::
            end
        ''')

        # 裸光环 min
        _set_config_and_rebuild(lua, config_var, config_type, 0)
        bare_min_out = calc_fn(lua, calcs)
        bare_min_dps = bare_min_out.get("TotalDPS", 0)
        bare_min_speed_inc = bare_min_out.get("Speed_INC", 0)

        # 裸光环 max
        _set_config_and_rebuild(lua, config_var, config_type, actual_max)
        bare_max_out = calc_fn(lua, calcs)
        bare_max_dps = bare_max_out.get("TotalDPS", 0)
        bare_max_speed_inc = bare_max_out.get("Speed_INC", 0)

        # 恢复辅助（排除精魄辅助——精魄辅助不算在光环辅助增益中）
        ss_ids_lua = "{}"
        if spirit_support_ids:
            items = ', '.join(f'"{sid}"' for sid in spirit_support_ids)
            ss_ids_lua = "{" + items + "}"
        lua.execute(f'''
            local build = _spike_build
            local ssIds = {ss_ids_lua}
            local function isSpiritSupport(gem)
                if gem.skillId then
                    for _, sid in ipairs(ssIds) do
                        if gem.skillId == sid then return true end
                    end
                end
                return false
            end
            for i = 1, #build.skillsTab.socketGroupList do
                local g = build.skillsTab.socketGroupList[i]
                for _, gem in ipairs(g.gemList or {{}}) do
                    if isSpiritSupport(gem) then
                        gem.enabled = false  -- 精魄辅助不参与"辅助增益"
                    else
                        gem.enabled = true   -- 普通辅助恢复
                    end
                end
            end
        ''')

        # Phase 2: 带辅助测试（仅普通辅助，精魄辅助仍禁用）
        # real min
        _set_config_and_rebuild(lua, config_var, config_type, 0)
        real_min_out = calc_fn(lua, calcs)
        real_min_dps = real_min_out.get("TotalDPS", 0)

        # real max
        _set_config_and_rebuild(lua, config_var, config_type, actual_max)
        real_max_out = calc_fn(lua, calcs)
        real_max_dps = real_max_out.get("TotalDPS", 0)
        real_max_speed_inc = real_max_out.get("Speed_INC", 0)

        # Phase 3: 精魄辅助独立贡献（光环+精魄辅助 vs 裸光环）
        spirit_pct_min = 0
        spirit_pct_max = 0
        if spirit_support_ids:
            # 恢复精魄辅助
            lua.execute(f'''
                local build = _spike_build
                local ssIds = {ss_ids_lua}
                for i = 1, #build.skillsTab.socketGroupList do
                    local g = build.skillsTab.socketGroupList[i]
                    for _, gem in ipairs(g.gemList or {{}}) do
                        if gem.skillId then
                            for _, sid in ipairs(ssIds) do
                                if gem.skillId == sid then gem.enabled = true end
                            end
                        end
                    end
                end
            ''')
            # 精魄辅助 min (光环+普通辅助+精魄辅助 vs 光环+普通辅助)
            _set_config_and_rebuild(lua, config_var, config_type, 0)
            spirit_min_out = calc_fn(lua, calcs)
            spirit_min_dps = spirit_min_out.get("TotalDPS", 0)
            spirit_pct_min = ((spirit_min_dps - real_min_dps) / real_min_dps * 100) if real_min_dps > 0 else 0

            # 精魄辅助 max
            _set_config_and_rebuild(lua, config_var, config_type, actual_max)
            spirit_max_out = calc_fn(lua, calcs)
            spirit_max_dps = spirit_max_out.get("TotalDPS", 0)
            spirit_pct_max = ((spirit_max_dps - real_max_dps) / real_max_dps * 100) if real_max_dps > 0 else 0

            # 禁用精魄辅助（恢复 Phase 2 状态）
            lua.execute(f'''
                local build = _spike_build
                local ssIds = {ss_ids_lua}
                for i = 1, #build.skillsTab.socketGroupList do
                    local g = build.skillsTab.socketGroupList[i]
                    for _, gem in ipairs(g.gemList or {{}}) do
                        if gem.skillId then
                            for _, sid in ipairs(ssIds) do
                                if gem.skillId == sid then gem.enabled = false end
                            end
                        end
                    end
                end
            ''')

        # 恢复原始值（不是 mid，保护 auto_configure_combat 设置的值）
        _set_config_and_rebuild(lua, config_var, config_type, original_val)

        # 恢复所有辅助（包括精魄辅助）
        lua.execute('''
            local build = _spike_build
            for i = 1, #build.skillsTab.socketGroupList do
                local g = build.skillsTab.socketGroupList[i]
                for _, gem in ipairs(g.gemList or {}) do gem.enabled = true end
            end
        ''')

        cfg["dps_min"] = real_min_dps
        cfg["dps_max"] = real_max_dps
        cfg["dps_pct_min"] = ((real_min_dps - base_dps) / base_dps * 100) if base_dps > 0 else 0
        cfg["dps_pct_max"] = ((real_max_dps - base_dps) / base_dps * 100) if base_dps > 0 else 0

        # 裸光环百分比
        cfg["bare_pct_min"] = ((bare_min_dps - bare_base_dps) / bare_base_dps * 100) if bare_base_dps > 0 else 0
        cfg["bare_pct_max"] = ((bare_max_dps - bare_base_dps) / bare_base_dps * 100) if bare_base_dps > 0 else 0

        # 精魄辅助独立贡献
        cfg["spirit_pct_min"] = spirit_pct_min
        cfg["spirit_pct_max"] = spirit_pct_max

        # Speed INC（用带辅助的 max 端点）
        if real_max_speed_inc is not None:
            cfg["speed_inc_max"] = real_max_speed_inc
        if bare_max_speed_inc is not None:
            cfg["speed_inc_min_bare"] = bare_max_speed_inc  # 裸光环 max 端点
        if bare_min_speed_inc is not None:
            cfg["speed_inc_min"] = bare_min_speed_inc

        cfg["mid"] = mid
        cfg["actual_max"] = actual_max
        cfg["aura_name"] = aura_name
        cfg["config_var"] = config_var
        cfg["config_type"] = config_type
        cfg["label"] = cfg.get("label", config_var)

        results.append(cfg)

    return results




def _query_active_skills_info(lua, calcs) -> list[dict]:
    """查询构筑中所有活跃技能组信息，识别光环和精魄辅助。

    检测逻辑：
    - is_aura: 基于 skillTypes 判断是否为 Aura/Persistent+Buff 精魄预留技能，
      或组内包含精魄辅助宝石（spirit support gems）
    - spirit_cost: 所有宝石的精魄消耗总和

    Returns:
        [{
            "group_idx": int,          # 技能组索引 (1-based)
            "label": str,               # 用户标签
            "main_skill_name": str,     # 主技能名称
            "is_aura": bool,            # 是否是光环/精魄预留 (8A 测试目标)
            "spirit_cost": float,       # 总精魄消耗
            "gems": [                  # 宝石列表
                {
                    "name": str,
                    "skill_id": str,
                    "is_support": bool,
                    "enabled": bool,
                    "spirit": float,
                }, ...
            ],
            "spirit_supports": [       # 精魄辅助宝石列表
                {"name": str, "skill_id": str, "spirit": float}, ...
            ],
        }, ...]
    """
    result = lua.execute('''
        local build = _spike_build
        local groups = build.skillsTab.socketGroupList
        local lines = {}

        for gi = 1, #groups do
            local group = groups[gi]
            if not group.enabled then
                lines[#lines+1] = tostring(gi) .. "||disabled"
                goto next_group
            end

            local label = group.label or ""
            local mainSkillName = ""
            local totalSpirit = 0
            local isAuraOrSpiritReserved = false
            local hasTriggeredDPS = false
            local triggeredSkillName = ""

            -- 收集所有宝石信息
            local gemInfos = {}
            local spiritSupports = {}

            for j = 1, #group.gemList do
                local gem = group.gemList[j]
                if not gem.enabled then goto next_gem end

                local gName = gem.nameSpec or "?"
                local gSkillId = gem.skillId or "?"
                local gSupport = false
                local gSpirit = 0

                -- 获取技能效果数据
                local grantedEffect = gem.grantedEffect
                    or (gem.gemData and gem.gemData.grantedEffect)
                if not grantedEffect then
                    if gem.skillId and data.skills[gem.skillId] then
                        grantedEffect = data.skills[gem.skillId]
                    end
                end

                if grantedEffect then
                    gSupport = grantedEffect.support or false
                    gName = grantedEffect.name or gName

                    -- 检查精魄消耗（从 levels 中获取 spiritReservationFlat）
                    local lvl = grantedEffect.levels and grantedEffect.levels[gem.level]
                    if lvl and type(lvl.spiritReservationFlat) == "number" then
                        gSpirit = lvl.spiritReservationFlat
                    end

                    -- 累加总精魄消耗
                    if gSpirit > 0 then
                        totalSpirit = totalSpirit + gSpirit
                    end

                    -- 收集精魄辅助信息（有精魄消耗的辅助宝石）
                    if gSupport and gSpirit > 0 then
                        spiritSupports[#spiritSupports+1] = gName .. "|" .. (gem.skillId or "?") .. "|" .. tostring(gSpirit)
                        -- 有精魄辅助 = 光环/精魄预留组
                        isAuraOrSpiritReserved = true
                    end

                    -- 确认是否是主技能
                    if j == (group.mainActiveSkill or 1) then
                        mainSkillName = gName

                        -- ═══════════════════════════════════════════════════════
                        -- 技能分类标准：基于 DPS 输出能力（非硬编码标签）
                        -- ═══════════════════════════════════════════════════════
                        --
                        -- 核心判据：技能是否有 DPS 输出
                        --   有 DPS → 按技能分析（isAuraOrSpiritReserved = false）
                        --   无 DPS → 按增益光环分析（isAuraOrSpiritReserved = true）
                        --
                        -- 三层判定：
                        --   1. SkillType 快速路径：Attack/DoT/Herald → 有 DPS
                        --   2. statSets 触发检测：statSets 中含 triggerable_in_any_set
                        --      或 chance_to_trigger_* 的子技能 → 游戏中有 DPS 但 POB 未实现
                        --   3. 标签匹配：Aura / Per+Buf+Res → 无 DPS 的纯增益
                        --
                        -- 触发子技能标注（hasTriggeredDPS / triggeredSkillName）：
                        --   即使分类为光环，也标注其触发攻击子技能信息，
                        --   报告中显示"此技能有触发攻击但 POB 未实现 DPS 计算"
                        --
                        -- ═══════════════════════════════════════════════════════
                        local st = grantedEffect.skillTypes
                        if st then
                            local isAuraSkill = (st[SkillType.Aura] ~= nil)
                            local isPer = (st[SkillType.Persistent] ~= nil)
                            local isBuff = (st[SkillType.Buff] ~= nil)
                            local isRes = (st[SkillType.HasReservation] ~= nil)
                            local isMovement = (st[SkillType.Movement] ~= nil)
                            local isMinion = (st[SkillType.CreatesMinion] ~= nil)
                            local isCurse = (st[SkillType.AppliesCurse] ~= nil)
                            local isTriggered = (st[SkillType.Triggered] ~= nil)
                            local isRemnant = (st[SkillType.GeneratesRemnants] ~= nil)
                            local isDodge = (st[SkillType.DodgeReplacement] ~= nil)
                            local isHerald = (st[SkillType.Herald] ~= nil)
                            local isAttack = (st[SkillType.Attack] ~= nil)
                            local isDoT = (st[SkillType.DamageOverTime] ~= nil)
                            local hasDPSType = isAttack or isDoT or isHerald



                            -- 触发子技能检测已移到分类判定之后（见下方）

                            -- 决策逻辑：有 DPS 输出 → 按技能分析；无 → 按光环分析
                            -- 非攻击型特殊技能（诅咒/触发/移动/闪避）→ 不属于光环
                            if isCurse or isTriggered or isMovement or isDodge then
                                isAuraOrSpiritReserved = false
                            -- 有 DPS 输出 → 按技能分析
                            elseif hasDPSType then
                                isAuraOrSpiritReserved = false
                            -- 有触发攻击但 POB 未实现 → 仍按光环分析，但标注
                            --   （hasTriggeredDPS 会在输出中标记）
                            -- 无 DPS 的 Aura → 纯增益光环
                            elseif isAuraSkill then
                                isAuraOrSpiritReserved = true
                            -- 无 DPS 的 Per+Buf+Res → 精魄预留增益
                            elseif isPer and isBuff and isRes and not isMinion and not isRemnant then
                                isAuraOrSpiritReserved = true
                            end

                            -- 检测触发攻击子技能
                            -- 对于 Per+Buf+Res 且无 Atk/DoT/Herald 的技能，
                            -- 查找 POB 中的 Triggered{SkillId} 子技能
                            -- 如 WindDancerPlayer → TriggeredWindDancerPlayer (Gale Force)
                            if not hasDPSType and isAuraOrSpiritReserved and gem.skillId then
                                local trigId = "Triggered" .. gem.skillId
                                local trigSkill = data.skills[trigId]
                                if trigSkill then
                                    local tst = trigSkill.skillTypes or {}
                                    local tAtk = tst[SkillType.Attack] or tst[SkillType.DamageOverTime]
                                    if tAtk then
                                        hasTriggeredDPS = true
                                        triggeredSkillName = trigSkill.name or trigId
                                    end
                                end
                                -- 也检查 statSets 内的触发子技能
                                -- (部分技能的触发效果在同一 skillId 的后续 statSets 中)
                                if not hasTriggeredDPS and grantedEffect.statSets then
                                    for si = 2, #grantedEffect.statSets do
                                        local ss = grantedEffect.statSets[si]
                                        local hasTrigger = false
                                        if ss.stats then
                                            for _, stat in ipairs(ss.stats) do
                                                if stat == "triggerable_in_any_set" then
                                                    hasTrigger = true
                                                end
                                            end
                                        end
                                        if ss.constantStats then
                                            for _, cs in ipairs(ss.constantStats) do
                                                if type(cs[1]) == "string" and string.find(cs[1], "chance_to_trigger") then
                                                    hasTrigger = true
                                                end
                                            end
                                        end
                                        if hasTrigger and ss.baseFlags then
                                            local subAtk = ss.baseFlags.attack or ss.baseFlags.nonWeaponAttack
                                            if subAtk then
                                                hasTriggeredDPS = true
                                                triggeredSkillName = ss.label or ("statSet" .. tostring(si))
                                            end
                                        end
                                    end
                                end
                            end
                        end
                    end
                end

                gemInfos[#gemInfos+1] = gName .. "|" .. (gem.skillId or "?") .. "|" .. tostring(gSupport) .. "|true|" .. tostring(gSpirit) .. "|" .. tostring(gem.level or 0) .. "|" .. tostring(gem.quality or 0)
                ::next_gem::
            end

            lines[#lines+1] = tostring(gi) .. "||"
                .. label .. "||"
                .. mainSkillName .. "||"
                .. tostring(isAuraOrSpiritReserved) .. "||"
                .. tostring(totalSpirit) .. "||"
                .. tostring(hasTriggeredDPS) .. "||"
                .. triggeredSkillName .. "||"
                .. table.concat(gemInfos, ";;") .. "||"
                .. table.concat(spiritSupports, ";;")

            ::next_group::
        end

        return table.concat(lines, "\\n")
    ''')

    if not result:
        return []

    skills_info = []
    for line in str(result).split('\n'):
        if not line.strip():
            continue
        parts = line.split('||')
        if len(parts) < 7:
            # disabled 组
            if len(parts) >= 2 and parts[1] == "disabled":
                continue
            continue

        gi = int(parts[0])
        label = parts[1]
        main_name = parts[2]
        is_aura = parts[3] == "true"
        spirit_cost = float(parts[4])
        # 新字段：触发攻击标注
        has_triggered_dps = parts[5] == "true" if len(parts) > 5 else False
        triggered_skill_name = parts[6] if len(parts) > 6 else ""

        gems = []
        gem_parts_idx = 7
        if len(parts) > gem_parts_idx and parts[gem_parts_idx]:
            for gem_str in parts[gem_parts_idx].split(';;'):
                gp = gem_str.split('|')
                if len(gp) >= 4:
                    gems.append({
                        "name": gp[0],
                        "skill_id": gp[1],
                        "is_support": gp[2] == "true",
                        "enabled": gp[3] == "true",
                        "spirit": float(gp[4]) if len(gp) > 4 and gp[4] else 0,
                        "level": int(gp[5]) if len(gp) > 5 and gp[5] else 0,
                        "quality": int(gp[6]) if len(gp) > 6 and gp[6] else 0,
                    })

        spirit_supports = []
        ss_parts_idx = 8
        if len(parts) > ss_parts_idx and parts[ss_parts_idx]:
            for ss_str in parts[ss_parts_idx].split(';;'):
                sp = ss_str.split('|')
                if len(sp) >= 3:
                    spirit_supports.append({
                        "name": sp[0],
                        "skill_id": sp[1],
                        "spirit": float(sp[2]) if sp[2] not in ('true', 'false', 'nil', '') else 0,
                    })

        skills_info.append({
            "group_idx": gi,
            "label": label,
            "main_skill_name": main_name,
            "is_aura": is_aura,
            "spirit_cost": spirit_cost,
            "has_triggered_dps": has_triggered_dps,
            "triggered_skill_name": triggered_skill_name,
            "gems": gems,
            "spirit_supports": spirit_supports,
        })

    return skills_info


def _query_total_spirit(lua, calcs) -> float:
    """查询构筑的总精魄和已用精魄。

    Returns:
        (total_spirit, reserved_spirit) 元组
    """
    result = lua.execute('''
        local build = _spike_build
        local env = calcs.initEnv(build, "MAIN")
        calcs.perform(env)
        local total = env.player.output.Spirit or 0
        local reserved = env.player.output.SpiritReserved or 0
        return tostring(total) .. "|" .. tostring(reserved)
    ''')
    if result:
        parts = str(result).split('|')
        try:
            return float(parts[0]), float(parts[1])
        except (ValueError, IndexError):
            pass
    return 0, 0


def _test_remove_skill_group(lua, calcs, group_idx: int,
                             baseline: dict, skill_name: str = None,
                             pre_configs: list = None,
                             inject_mods: list = None,
                             aura_only: bool = False,
                             spirit_support_ids: set[str] | None = None) -> dict:
    """测试禁用指定技能组后的 DPS 变化。

    按主技能名称匹配，禁用所有同名副本组（包括 item-granted 副本）。
    pre_configs: 预设配置（如 Charge）
    inject_mods: 需要注入的 mod 列表（用于模拟 POB 不计算的动态效果）
                [{"name": str, "type": "MORE"|"INC"|"BASE", "value": float}, ...]
    因为 POB 构筑中同一技能可能存在 socketed 和 item-granted 两个版本。

    Args:
        group_idx: 技能组索引 (1-based)
        skill_name: 主技能名称（用于匹配所有副本）。若为 None，只禁用指定组。
        aura_only: True 时只禁用主技能（光环）宝石，保留辅助宝石。
                    返回 dict 中额外包含 supports_dps_pct 字段。
        spirit_support_ids: 精魄辅助 skill_id 集合。当 aura_only=True 时，
                    精魄辅助不计入辅助增益，单独记录 spirit_support_pct。

    Returns:
        {"dps_before", "dps_after", "dps_pct", "ehp_pct", "simulated": bool,
         "supports_dps_pct": float,  # 仅 aura_only=True 时
         "spirit_support_pct": float}  # 精魄辅助独立贡献
    """
    base_dps = baseline.get("TotalDPS", 0)
    base_ehp = baseline.get("TotalEHP", 0)

    # 预设条件配置（如 Charge），并重算 baseline
    if pre_configs:
        for cfg in pre_configs:
            var, val = cfg["var"], cfg["value"]
            if isinstance(val, bool):
                lua_val = "true" if val else "false"
            else:
                lua_val = val
            lua.execute(f'_spike_build.configTab.input["{var}"] = {lua_val}')
        _rebuild_config_tab_modlist(lua)
        from .calculator import calculate as calc_fn
        charged_bl = calc_fn(lua, calcs)
        base_dps = charged_bl.get("TotalDPS", 0)
        base_ehp = charged_bl.get("TotalEHP", 0)

    # 构建 Lua 代码：按名称禁用所有同名组
    if skill_name:
        lua_name = skill_name.replace("\\", "\\\\").replace('"', '\\"')
        if aura_only:
            # 裸光环模式：四步测试
            # Step 1: baseline（排除精魄辅助，只有光环+普通辅助）
            # Step 2: 仅禁辅助（裸光环）
            # Step 3: 禁全组（无光环）
            # Step 4: 恢复精魄辅助（测精魄辅助独立贡献）
            ss_ids_lua = "{}"
            if spirit_support_ids:
                items = ', '.join(f'"{sid}"' for sid in spirit_support_ids)
                ss_ids_lua = "{" + items + "}"

            lua_code = f'''
                local build = _spike_build
                local targetName = "{lua_name}"
                local ssIds = {ss_ids_lua}
                local function calcDPS()
                    local env = calcs.initEnv(build, "MAIN")
                    pcall(calcs.perform, env)
                    return env.player.output
                end

                -- 辅助函数：按名字判断是否为主技能(光环)宝石
                local function isAuraGem(gem)
                    local ge = gem.grantedEffect or (gem.gemData and gem.gemData.grantedEffect)
                    if (ge and ge.name == targetName) or gem.nameSpec == targetName or gem.skillId == targetName then return true end
                    if gem.skillId and data.skills[gem.skillId] and data.skills[gem.skillId].name == targetName then return true end
                    return false
                end

                -- 辅助函数：判断是否为精魄辅助
                local function isSpiritSupport(gem)
                    if gem.skillId then
                        for _, sid in ipairs(ssIds) do
                            if gem.skillId == sid then return true end
                        end
                    end
                    return false
                end

                -- === Step 0: 禁用所有精魄辅助（贯穿 Step 1-3） ===
                local spiritDisabled = {{}}
                for i = 1, #build.skillsTab.socketGroupList do
                    local group = build.skillsTab.socketGroupList[i]
                    for gi, gem in ipairs(group.gemList or {{}}) do
                        if isSpiritSupport(gem) and gem.enabled then
                            gem.enabled = false
                            spiritDisabled[#spiritDisabled+1] = {{groupIdx=i, gemIdx=gi}}
                        end
                    end
                end

                -- === Step 1: baseline（光环+普通辅助，无精魄辅助） ===
                local baseOutput = calcDPS()
                local baseDPS = baseOutput.TotalDPS or 0

                -- === Step 2: 仅禁同名组内的辅助宝石（保留光环）→ 裸光环 DPS ===
                local supportDisabled = {{}}
                for i = 1, #build.skillsTab.socketGroupList do
                    local group = build.skillsTab.socketGroupList[i]
                    if not group.enabled then goto nextSup end
                    local hasAura = false
                    for gi, gem in ipairs(group.gemList or {{}}) do
                        if isAuraGem(gem) then hasAura = true; break end
                    end
                    if not hasAura then goto nextSup end
                    for gi, gem in ipairs(group.gemList or {{}}) do
                        if not isAuraGem(gem) and gem.enabled then
                            gem.enabled = false
                            supportDisabled[#supportDisabled+1] = {{groupIdx=i, gemIdx=gi}}
                        end
                    end
                    ::nextSup::
                end
                local bareOutput = calcDPS()
                local bareDPS = bareOutput.TotalDPS or 0

                -- 收集辅助宝石名称列表（仅普通辅助，不含精魄辅助）
                local supportNames = {{}}
                for i = 1, #build.skillsTab.socketGroupList do
                    local group = build.skillsTab.socketGroupList[i]
                    if not group.enabled then goto nextSN end
                    local hasAura = false
                    for gi, gem in ipairs(group.gemList or {{}}) do
                        if isAuraGem(gem) then hasAura = true; break end
                    end
                    if not hasAura then goto nextSN end
                    for gi, gem in ipairs(group.gemList or {{}}) do
                        if not isAuraGem(gem) and not isSpiritSupport(gem) then
                            local sn = gem.nameSpec or ''
                            if gem.grantedEffect and gem.grantedEffect.name then sn = gem.grantedEffect.name end
                            if sn == '' and gem.skillId and data.skills[gem.skillId] then sn = data.skills[gem.skillId].name end
                            supportNames[#supportNames+1] = sn
                        end
                    end
                    ::nextSN::
                end

                -- === Step 3: 禁整个同名组（光环+辅助全部禁用） ===
                local groupDisabled = {{}}
                for i = 1, #build.skillsTab.socketGroupList do
                    local group = build.skillsTab.socketGroupList[i]
                    if not group.enabled then goto nextGrp end
                    local mainIdx = group.mainActiveSkill or 1
                    local gem = group.gemList[mainIdx]
                    if not gem then goto nextGrp end
                    if isAuraGem(gem) then
                        group.enabled = false
                        groupDisabled[#groupDisabled+1] = i
                    end
                    ::nextGrp::
                end
                local noAuraOutput = calcDPS()

                -- === Step 4: 恢复精魄辅助，测精魄辅助独立贡献 ===
                -- 先恢复 Step 2-3 的修改
                for _, idx in ipairs(groupDisabled) do
                    build.skillsTab.socketGroupList[idx].enabled = true
                end
                for _, sd in ipairs(supportDisabled) do
                    build.skillsTab.socketGroupList[sd.groupIdx].gemList[sd.gemIdx].enabled = true
                end
                -- 恢复精魄辅助
                for _, sd in ipairs(spiritDisabled) do
                    build.skillsTab.socketGroupList[sd.groupIdx].gemList[sd.gemIdx].enabled = true
                end
                local spiritOutput = calcDPS()
                local spiritDPS = spiritOutput.TotalDPS or 0

                -- base=光环+普通辅助, bare=裸光环, noAura=无光环, spirit=全开(含精魄辅助)
                baseDPS = baseOutput.TotalDPS or 0
                bareDPS = bareOutput.TotalDPS or 0
                local noAuraDPS = noAuraOutput.TotalDPS or 0
                local baseEHP = baseOutput.TotalEHP or 0
                local noAuraEHP = noAuraOutput.TotalEHP or 0
                local supStr = table.concat(supportNames, ',')
                return string.format("%.2f|%.2f|%.2f|%.2f|%.2f|%s|%.2f", baseDPS, bareDPS, noAuraDPS, baseEHP, noAuraEHP, supStr, spiritDPS)
            '''
        else:
            # 原始模式：禁用整个组
            lua_code = f'''
            local build = _spike_build
            local targetName = "{lua_name}"
            local disabled = {{}}

            -- 禁用所有同名组（通过 nameSpec 或 skillId 匹配）
            -- build_loader 不设 grantedEffect，必须用 nameSpec/skillId
            for i = 1, #build.skillsTab.socketGroupList do
                local group = build.skillsTab.socketGroupList[i]
                if not group.enabled then goto next end
                local mainIdx = group.mainActiveSkill or 1
                local gem = group.gemList[mainIdx]
                if not gem then goto next end
                -- Try grantedEffect name first (fallback), then nameSpec, then skillId
                local ge = gem.grantedEffect or (gem.gemData and gem.gemData.grantedEffect)
                local matched = false
                if ge and ge.name == targetName then
                    matched = true
                elseif gem.nameSpec == targetName then
                    matched = true
                elseif gem.skillId == targetName then
                    matched = true
                else
                    -- Also check grantedEffect via data.skills lookup
                    local sid = gem.skillId
                    if sid and data.skills[sid] and data.skills[sid].name == targetName then
                        matched = true
                    end
                end
                if matched then
                    group.enabled = false
                    disabled[#disabled+1] = i
                end
                ::next::
            end

            local ok, env = pcall(function()
                return calcs.initEnv(build, "MAIN")
            end)
            local result = ""
            if ok then
                pcall(calcs.perform, env)
                result = tostring(env.player.output.TotalDPS or 0) .. "|" .. tostring(env.player.output.TotalEHP or 0)
            else
                result = "ERROR"
            end

            -- 恢复
            for _, idx in ipairs(disabled) do
                build.skillsTab.socketGroupList[idx].enabled = true
            end

            return result
        '''
    else:
        lua_code = f'''
            local build = _spike_build
            local gi = {group_idx}
            local group = build.skillsTab.socketGroupList[gi]
            if not group then return "ERROR" end
            local origEnabled = group.enabled
            group.enabled = false
            local ok, env = pcall(function()
                return calcs.initEnv(build, "MAIN")
            end)
            local result = ""
            if ok then
                pcall(calcs.perform, env)
                result = tostring(env.player.output.TotalDPS or 0) .. "|" .. tostring(env.player.output.TotalEHP or 0)
            else
                result = "ERROR"
            end
            group.enabled = origEnabled
            return result
        '''

    result = lua.execute(lua_code)

    def _restore_pre_configs():
        if pre_configs:
            for cfg in pre_configs:
                lua.execute(f'_spike_build.configTab.input["{cfg["var"]}"] = nil')
            _rebuild_config_tab_modlist(lua)

    if not result or result == "ERROR":
        _restore_pre_configs()
        return {"dps_before": base_dps, "dps_after": base_dps, "dps_pct": 0, "ehp_pct": 0, "simulated": bool(pre_configs)}

    parts = str(result).split('|')

    if aura_only and len(parts) >= 6:
        # aura_only 模式返回: baseDPS|bareDPS|noAuraDPS|baseEHP|noAuraEHP|supportNames|spiritDPS
        # baseDPS = 光环+普通辅助（不含精魄辅助）
        # bareDPS = 裸光环（无任何辅助）
        # noAuraDPS = 无光环
        # spiritDPS = 全开（含精魄辅助），可选
        try:
            base_dps_v = float(parts[0])
            bare_dps = float(parts[1])       # 裸光环（无辅助）
            no_aura_dps = float(parts[2])    # 无光环
            base_ehp_v = float(parts[3])
            no_aura_ehp = float(parts[4])
        except (ValueError, IndexError):
            _restore_pre_configs()
            return {"dps_before": base_dps, "dps_after": base_dps, "dps_pct": 0, "ehp_pct": 0, "simulated": False}
        # 解析辅助宝石名称列表（仅普通辅助）
        support_names = []
        if len(parts) >= 6 and parts[5]:
            support_names = [n.strip() for n in parts[5].split(',') if n.strip()]
        # 解析精魄辅助 DPS
        spirit_dps = base_dps_v  # 默认无精魄辅助数据
        if len(parts) >= 7:
            try:
                spirit_dps = float(parts[6])
            except (ValueError, IndexError):
                spirit_dps = base_dps_v
        # 裸光环贡献: bareDPS vs noAuraDPS
        bare_dps_pct = ((bare_dps - no_aura_dps) / no_aura_dps * 100) if no_aura_dps > 0 else 0
        # 真实光环贡献: baseDPS vs noAuraDPS（含普通辅助，不含精魄辅助）
        real_dps_pct = ((base_dps_v - no_aura_dps) / no_aura_dps * 100) if no_aura_dps > 0 else 0
        # 辅助额外贡献: 真实贡献 - 裸光环贡献（仅普通辅助）
        supports_extra_pct = real_dps_pct - bare_dps_pct
        # 精魄辅助独立贡献: spiritDPS vs baseDPS
        spirit_support_pct = ((spirit_dps - base_dps_v) / base_dps_v * 100) if base_dps_v > 0 else 0
        ehp_pct = ((base_ehp_v - no_aura_ehp) / no_aura_ehp * 100) if no_aura_ehp > 0 else 0
        _restore_pre_configs()
        return {
            "dps_before": base_dps_v,
            "dps_after": no_aura_dps,
            "bare_dps_pct": bare_dps_pct,       # 裸光环（无辅助）贡献
            "dps_pct": real_dps_pct,            # 真实光环（含普通辅助，不含精魄辅助）贡献
            "supports_extra_pct": supports_extra_pct,  # 普通辅助额外贡献
            "spirit_support_pct": spirit_support_pct,  # 精魄辅助独立贡献
            "support_names": support_names,      # 普通辅助宝石名称列表
            "ehp_pct": ehp_pct,
            "simulated": bool(pre_configs),
        }

    try:
        new_dps = float(parts[0])
        new_ehp = float(parts[1])
    except (ValueError, IndexError):
        _restore_pre_configs()
        return {"dps_before": base_dps, "dps_after": base_dps, "dps_pct": 0, "ehp_pct": 0, "simulated": bool(pre_configs)}

    # dps_pct 表示光环贡献（正值=增加 DPS）
    # 基数统一用"移除光环后"的 DPS（即无该效果的 baseline）
    dps_pct = ((base_dps - new_dps) / new_dps * 100) if new_dps > 0 else 0
    ehp_pct = ((base_ehp - new_ehp) / new_ehp * 100) if new_ehp > 0 else 0

    _restore_pre_configs()
    return {
        "dps_before": base_dps,
        "dps_after": new_dps,
        "dps_pct": dps_pct,
        "ehp_pct": ehp_pct,
        "simulated": bool(pre_configs),
    }


def _resolve_charge_map(lua, calcs) -> dict:
    """从构筑 output 读取最大充能球数。

    Returns:
        {"FrenzyCharges": int, "PowerCharges": int, "EnduranceCharges": int}
    """
    charges = lua.execute('''
        local env = calcs.initEnv(_spike_build, "MAIN")
        calcs.perform(env)
        local out = env.player.output
        return string.format("%d|%d|%d",
            tonumber(out.FrenzyChargesMax or 0),
            tonumber(out.PowerChargesMax or 0),
            tonumber(out.EnduranceChargesMax or 0))
    ''')
    if charges and str(charges) != "nil" and "|" in str(charges):
        parts = str(charges).split("|")
        return {
            "FrenzyCharges": int(parts[0]) if parts[0].isdigit() else 3,
            "PowerCharges": int(parts[1]) if parts[1].isdigit() else 3,
            "EnduranceCharges": int(parts[2]) if parts[2].isdigit() else 3,
        }
    logger.warning("无法读取构筑充能球数，使用默认值 3")
    return {"FrenzyCharges": 3, "PowerCharges": 3, "EnduranceCharges": 3}


def _fill_charge_configs(configs: list, charge_map: dict,
                        context: str = "") -> list:
    """将 configs 中 value=None 的项用 charge_map 填充。"""
    resolved = []
    for cfg in configs:
        cfg = dict(cfg)
        if cfg.get("value") is None:
            var = cfg["var"]
            for charge_type, max_val in charge_map.items():
                if charge_type in var:
                    cfg["value"] = max_val
                    logger.info("动态设置 %s: %s = %d", context, var, max_val)
                    break
            if cfg.get("value") is None:
                cfg["value"] = 0
        resolved.append(cfg)
    return resolved


def _resolve_pre_configs(lua, calcs, aura_name: str):
    """动态解析光环的预设配置，填充 None 值为构筑实际数据。

    对于 Charge Infusion：从构筑 output 读取最大充能球数。

    Returns:
        tuple: (configs_list, charge_counts_dict) 或 None
    """
    base_configs = _AURA_PRE_CONFIGS.get(aura_name)
    if not base_configs:
        return None

    if not any(c["value"] is None for c in base_configs):
        return (base_configs, None)

    charge_map = _resolve_charge_map(lua, calcs)
    resolved = _fill_charge_configs(base_configs, charge_map, context=aura_name)
    return (resolved, charge_map)


def _resolve_inject_mods(lua, calcs, inject_config: dict, aura_name: str) -> dict:
    """动态解析注入 mod 的值（从构筑实际数据读取）。

    对于 EC：从 statSets[1].levels[actual_gem_level][1] 读取 MORE 百分比。
    """
    config = dict(inject_config)  # 浅拷贝避免修改原数据
    mod = dict(config["mod"])
    stat_skill_id = config.get("stat_skill_id")

    if mod["value"] is None and stat_skill_id:
        # 动态读取：从构筑中找到该光环的宝石等级
        actual_level = lua.execute(f'''
            local build = _spike_build
            for gi = 1, #build.skillsTab.socketGroupList do
                local group = build.skillsTab.socketGroupList[gi]
                for j = 1, #group.gemList do
                    local gem = group.gemList[j]
                    local ge = gem.grantedEffect
                        or (gem.gemData and gem.gemData.grantedEffect)
                    if ge and ge.name and ge.name:find("{aura_name}") then
                        return tostring(gem.level)
                    end
                end
            end
            return nil
        ''')
        if actual_level and str(actual_level) != "nil":
            lvl = int(actual_level)
            # 从 data.skills[skillId].statSets[1].levels[level][1] 读取
            more_val = lua.execute(f'''
                local data = _spike_build.data
                local sk = data.skills["{stat_skill_id}"]
                if sk and sk.statSets and sk.statSets[1] and sk.statSets[1].levels then
                    local lvldata = sk.statSets[1].levels[{lvl}]
                    if lvldata and lvldata[1] then
                        local base = lvldata[1]
                        -- 加品质增量
                        local qbonus = 0
                        if sk.qualityStats then
                            for _, sg in ipairs(data.skills and data.skills["{stat_skill_id}"] and {{}} or {{}}) do
                                if sg == nil then break end
                            end
                            -- 需要从构筑中找到实际品质
                            for _, sg in ipairs(_spike_build.skillsTab.socketGroupList or {{}}) do
                                for _, gem in ipairs(sg.gems or sg.gemList or {{}}) do
                                    if gem.skillId == "{stat_skill_id}" then
                                        local q = gem.quality or 0
                                        for _, qs in ipairs(sk.qualityStats or {{}}) do
                                            local sn = qs[1] or ""
                                            if sn:find("damage") or sn:find("more") or sn:find("inc") then
                                                qbonus = qbonus + q * (qs[2] or 0)
                                            end
                                        end
                                    end
                                end
                            end
                        end
                        return tostring(base + qbonus)
                    end
                end
                return nil
            ''')
            if more_val and str(more_val) != "nil":
                mod["value"] = float(more_val)
                config["gem_level"] = lvl  # 保存实际宝石等级
                logger.info("动态读取 %s MORE: Lv%d = %.0f%%", aura_name, lvl, mod["value"])
            else:
                # 回退到 statSets 第一个有数据的等级
                logger.warning("无法从 statSets 读取 %s Lv%d MORE，使用默认值", aura_name, lvl)
                mod["value"] = 0
        else:
            logger.warning("构筑中未找到 %s，跳过动态 MORE 读取", aura_name)
            mod["value"] = 0

    config["mod"] = mod
    return config


def _test_mod_effect(lua, calcs, baseline: dict,
                     aura_config: dict, skill_name: str) -> dict:
    """测试注入 mod 后的 DPS 变化（用于模拟 POB 不计算的动态效果）。

    用于 Elemental Conflux 等需要手动注入 mod 的光环。
    对于 EC，会根据主技能的伤害类型分布计算加权期望。

    这些技能的 sim mod 已经通过 _inject_unimplemented_mods 注入到
    configTab.modList 中。本函数需要：
    1. 暂存并移除 configTab 中的 sim mods
    2. 计算 no_mod DPS（真正无该技能效果的状态）
    3. 在临时 env 中注入模拟效果，计算 with_mod DPS
    4. 恢复 sim mods

    Args:
        aura_config: 光环配置
            {"mod": {"name": str, "type": "MORE"|"INC"|"BASE", "value": float},
             "expect_factor": float (默认期望系数，会被实际计算覆盖)}
        skill_name: 光环名称（用于报告）

    Returns:
        {"dps_before", "dps_after", "dps_pct", "ehp_pct", "simulated": True}
    """
    from .calculator import calculate as calc_fn

    mod = aura_config["mod"]
    default_expect_factor = aura_config.get("expect_factor", 1.0)
    source_tag = aura_config.get("source", "")

    # 暂存 configTab.modList 中的 sim mods 并移除（避免双重计算）
    # 使用 Lua 全局变量暂存原始 modList 引用
    lua.execute(r"""
        _saved_aura_modlist = _spike_build.configTab.modList
        _saved_aura_enemyModList = _spike_build.configTab.enemyModList
        -- 创建不含 sim mod 的新 modList
        local newML = new("ModList")
        local oldML = _saved_aura_modlist
        if oldML then
            for _, m in ipairs(oldML) do
                local src = m.source or ""
                if not src:find("sim") then
                    newML:AddMod(m)
                end
            end
        end
        _spike_build.configTab.modList = newML
    """)

    try:
        return _test_mod_effect_inner(lua, calcs, baseline, mod, aura_config,
                                      skill_name, default_expect_factor, source_tag)
    finally:
        # 恢复原始 modList
        lua.execute('_spike_build.configTab.modList = _saved_aura_modlist')
        lua.execute('_spike_build.configTab.enemyModList = _saved_aura_enemyModList')


def _test_mod_effect_inner(lua, calcs, baseline: dict,
                           mod: dict, aura_config: dict,
                           skill_name: str, default_expect_factor: float,
                           source_tag: str) -> dict:
    """_test_mod_effect 的实际逻辑（在移除 sim mod 后调用）。"""

    # 对于 EC，分别注入每个元素 60% MORE，三次计算取平均
    if skill_name == "Elemental Conflux":
        raw_value = mod["value"]
        if raw_value is None:
            # 动态读取 EC MORE 值（base + quality bonus）
            try:
                ec_val = lua.execute(r"""
                    local sk = _spike_build.data.skills and _spike_build.data.skills['ElementalConfluxPlayer']
                    if not sk or not sk.statSets then return 0 end
                    for _, ss in ipairs(sk.statSets) do
                        if ss.levels then
                            for _, sg in ipairs(_spike_build.skillsTab.socketGroupList or {}) do
                                for _, gem in ipairs(sg.gems or sg.gemList or {}) do
                                    if gem.skillId == 'ElementalConfluxPlayer' then
                                        local lv = gem.level or 1
                                        local q = gem.quality or 0
                                        local base = ss.levels[lv] and ss.levels[lv][1] or 0
                                        local qbonus = 0
                                        if sk.qualityStats then
                                            for _, qs in ipairs(sk.qualityStats) do
                                                qbonus = qbonus + q * (qs[2] or 0)
                                            end
                                        end
                                        return base + qbonus
                                    end
                                end
                            end
                        end
                    end
                    return 0
                """)
                raw_value = float(ec_val) if ec_val else 0
            except Exception:
                raw_value = 0
        # 获取伤害构成
        damage_breakdown = lua.execute(r'''
            local env = calcs.initEnv(_spike_build, "MAIN")
            calcs.perform(env)
            local o = env.player.output
            local f = o.FireStoredCombinedAvg or 0
            local c = o.ColdStoredCombinedAvg or 0
            local l = o.LightningStoredCombinedAvg or 0
            local t = f + c + l
            return string.format("%.4f|%.4f|%.4f|%.4f",
                t > 0 and (f/t) or 0, t > 0 and (c/t) or 0,
                t > 0 and (l/t) or 0, t > 0 and 1.0 or 0)
        ''')
        parts = str(damage_breakdown).split('|')
        fire_pct = float(parts[0]) * 100 if len(parts) > 0 else 0
        cold_pct = float(parts[1]) * 100 if len(parts) > 1 else 0
        lightning_pct = float(parts[2]) * 100 if len(parts) > 2 else 0
        elemental_pct = float(parts[3]) * 100 if len(parts) > 3 else 0

        # 三次分别注入：FireDamage MORE / ColdDamage MORE / LightningDamage MORE
        ec_results = lua.execute(r'''
            local raw_val = ''' + str(raw_value) + r'''
            local elements = {"FireDamage", "ColdDamage", "LightningDamage"}
            local envs = {}
            for _, elem in ipairs(elements) do
                local env = calcs.initEnv(_spike_build, "MAIN")
                env.player.modDB:NewMod(elem, "MORE", raw_val, "EC_sim")
                calcs.perform(env)
                envs[#envs+1] = env.player.output.TotalDPS or 0
            end
            return table.concat(envs, "|")
        ''')
        ec_parts = str(ec_results).split('|')
        dps_fire = float(ec_parts[0]) if len(ec_parts) > 0 else 0
        dps_cold = float(ec_parts[1]) if len(ec_parts) > 1 else 0
        dps_lightning = float(ec_parts[2]) if len(ec_parts) > 2 else 0
        base_dps = (dps_fire + dps_cold + dps_lightning) / 3

        # 无 EC 的基准 DPS
        no_mod_result = lua.execute(r'''
            local env = calcs.initEnv(_spike_build, "MAIN")
            calcs.perform(env)
            return tostring(env.player.output.TotalDPS or 0)
        ''')
        no_mod_dps = float(no_mod_result)
        no_mod_ehp = 0  # EC 无 EHP 效果

        dps_pct = ((base_dps - no_mod_dps) / no_mod_dps * 100) if no_mod_dps > 0 else 0
        ehp_pct = 0
        base_ehp = 0

        result = {
            "dps_before": base_dps,
            "dps_after": no_mod_dps,
            "dps_pct": dps_pct,
            "ehp_pct": ehp_pct,
            "simulated": True,
            "expect_factor": 1.0 / 3,
            "raw_value": raw_value,
            "gem_level": aura_config.get("gem_level"),
            "damage_breakdown": {
                "fire": fire_pct,
                "cold": cold_pct,
                "lightning": lightning_pct,
                "elemental_total": elemental_pct,
            },
        }
        result["ec_detail"] = {
            "fire_more_dps": dps_fire,
            "cold_more_dps": dps_cold,
            "lightning_more_dps": dps_lightning,
        }
        return result

    # 非 EC 模拟
    mod_value = mod["value"]
    if mod_value is None:
        # 动态读取：从 skillData.statSets.levels 读取
        stat_skill_id = aura_config.get("stat_skill_id", "")
        level_idx = aura_config.get("level_index", 1)
        if stat_skill_id:
            try:
                dynamic_val = lua.execute(f"""
                    local sk = _spike_build.data.skills and _spike_build.data.skills['{stat_skill_id}']
                    if not sk or not sk.statSets then return 0 end
                    for _, ss in ipairs(sk.statSets) do
                        if ss.levels then
                            for _, sg in ipairs(_spike_build.skillsTab.socketGroupList or {{}}) do
                                for _, gem in ipairs(sg.gems or sg.gemList or {{}}) do
                                    if gem.skillId == '{stat_skill_id}' then
                                        local lv = gem.level or 1
                                        if ss.levels[lv] then
                                            return ss.levels[lv][{level_idx}] or 0
                                        end
                                    end
                                end
                            end
                        end
                    end
                    return 0
                """)
                mod_value = float(dynamic_val) if dynamic_val else 0
            except Exception:
                mod_value = 0
        else:
            mod_value = 0
    expected_value = mod_value * default_expect_factor

    # 收集所有需要注入的 mod（支持多 effect，如 Charge Infusion）
    all_effects = aura_config.get("all_effects", [])
    if not all_effects:
        all_effects = [{"mod_name": mod["name"], "mod_type": mod["type"],
                        "value": mod_value, "source": source_tag,
                        "level_index": aura_config.get("level_index", 1)}]

    # 动态解析每个 effect 的 value（如果为 null）
    stat_skill_id = aura_config.get("stat_skill_id", "")
    for eff in all_effects:
        if eff.get("value") is not None:
            continue
        if not stat_skill_id:
            eff["value"] = 0
            continue
        eff_idx = eff.get("level_index", 1)
        try:
            dyn = lua.execute(f"""
                local sk = _spike_build.data.skills and _spike_build.data.skills['{stat_skill_id}']
                if not sk or not sk.statSets then return 0 end
                for _, ss in ipairs(sk.statSets) do
                    if ss.levels then
                        for _, sg in ipairs(_spike_build.skillsTab.socketGroupList or {{}}) do
                            for _, gem in ipairs(sg.gems or sg.gemList or {{}}) do
                                if gem.skillId == '{stat_skill_id}' then
                                    local lv = gem.level or 1
                                    if ss.levels[lv] then
                                        return ss.levels[lv][{eff_idx}] or 0
                                    end
                                end
                            end
                        end
                    end
                end
                return 0
            """)
            eff["value"] = float(dyn) if dyn else 0
        except Exception:
            eff["value"] = 0

    # 构建注入 Lua 代码
    inject_lines = []
    for eff in all_effects:
        eff_name = eff.get("mod_name", mod["name"])
        eff_type = eff.get("mod_type", mod["type"])
        eff_val = eff.get("value", mod_value)
        if eff_val is None:
            continue
        eff_expect = eff_val * (1.0 if len(all_effects) > 1 else default_expect_factor)
        inject_lines.append(
            f'env.player.modDB:NewMod("{eff_name}", "{eff_type}", '
            f'{eff_expect}, "{skill_name} (期望)")')

    inject_lua = "\n".join(inject_lines)
    lua.execute(f'''
        local env = calcs.initEnv(_spike_build, "MAIN")
        {inject_lua}
        calcs.perform(env)
        _spike_base_dps = env.player.output.TotalDPS or 0
        _spike_base_ehp = env.player.output.TotalEHP or 0
    ''')
    base_dps = float(lua.eval('_spike_base_dps') or 0)
    base_ehp = float(lua.eval('_spike_base_ehp') or 0)

    lua.execute(r'''
        local env = calcs.initEnv(_spike_build, "MAIN")
        calcs.perform(env)
        _spike_no_mod_dps = env.player.output.TotalDPS or 0
        _spike_no_mod_ehp = env.player.output.TotalEHP or 0
    ''')
    no_mod_dps = float(lua.eval('_spike_no_mod_dps') or 0)
    no_mod_ehp = float(lua.eval('_spike_no_mod_ehp') or 0)

    lua.execute('_spike_base_dps, _spike_base_ehp, _spike_no_mod_dps, _spike_no_mod_ehp = nil, nil, nil, nil')

    dps_pct = ((base_dps - no_mod_dps) / no_mod_dps * 100) if no_mod_dps > 0 else 0
    ehp_pct = ((base_ehp - no_mod_ehp) / no_mod_ehp * 100) if no_mod_ehp > 0 else 0

    result = {
        "dps_before": base_dps,
        "dps_after": no_mod_dps,
        "dps_pct": dps_pct,
        "ehp_pct": ehp_pct,
        "simulated": True,
        "expect_factor": default_expect_factor,
        "raw_value": mod["value"],
        "gem_level": aura_config.get("gem_level"),
    }

    return result



def _get_candidate_sim_effects(aura_name: str, skill_id: str) -> list[dict]:
    """从 YAML 配置中获取候选光环的 Sim 注入效果。

    用于 POB 原生不计算的动态/条件性效果（如 Attrition 的叠加 MORE、
    Berserk 的 Rage 增强）。

    Args:
        aura_name: 光环名称（如 "Attrition"）
        skill_id: 光环的 skill_id（如 "AttritionPlayer"）

    Returns:
        效果列表 [{type, mod_name, mod_type, value, source, ...}, ...]
        或空列表（如 YAML 中无配置或 skill_type 不是 active）
    """
    try:
        from .pob_unimplemented import load_config
        config = load_config()
        skills_config = config.get("skills", {})

        # 优先按名称查找，其次按 skill_id 查找
        skill_cfg = skills_config.get(aura_name)
        if not skill_cfg:
            for name, cfg in skills_config.items():
                detect = cfg.get("detect", {})
                if detect.get("skill_id") == skill_id:
                    skill_cfg = cfg
                    break

        if not skill_cfg:
            return []

        # 对 skill_type=active 或 skill_type=aura 的技能注入 Sim
        # spirit_support 由 _test_add_spirit_support 处理
        # active_native 表示 POB 原生计算（如已装备的 Berserk），候选测试时仍需 Sim
        skill_type = skill_cfg.get("skill_type", "")
        if skill_type == "spirit_support":
            return []

        effects = skill_cfg.get("effects", [])
        # 接受 mod 类型（有非空 value）和 config 类型的效果
        sim_effects = [e for e in effects if (
            (e.get("type") == "mod" and e.get("value") is not None) or
            e.get("type") == "config"
        )]
        if sim_effects:
            logger.info("候选光环 %s: 从 YAML 加载 %d 个 Sim 效果", aura_name, len(sim_effects))
        return sim_effects
    except Exception as e:
        logger.debug("获取候选光环 Sim 效果失败: %s", e)
        return []


def _get_yaml_config_ranges(aura_name: str, skill_id: str) -> list[dict]:
    """从 YAML 配置中获取候选光环的 config_ranges 定义。"""
    try:
        from .pob_unimplemented import load_config
        config = load_config()
        skills_config = config.get("skills", {})
        skill_cfg = skills_config.get(aura_name)
        if not skill_cfg:
            for name, cfg in skills_config.items():
                detect = cfg.get("detect", {})
                if detect.get("skill_id") == skill_id:
                    skill_cfg = cfg
                    break
        if skill_cfg:
            return skill_cfg.get("config_ranges", [])
        return []
    except Exception:
        return []


def _get_sim_condition(aura_name: str, skill_id: str) -> str:
    """从 YAML 配置中获取候选光环的条件描述。"""
    try:
        from .pob_unimplemented import load_config
        config = load_config()
        skills_config = config.get("skills", {})
        skill_cfg = skills_config.get(aura_name)
        if not skill_cfg:
            for name, cfg in skills_config.items():
                detect = cfg.get("detect", {})
                if detect.get("skill_id") == skill_id:
                    skill_cfg = cfg
                    break
        if skill_cfg:
            return skill_cfg.get("condition", "")
        return ""
    except Exception:
        return ""


def _test_add_candidate_aura(lua, calcs, aura: dict,
                              baseline: dict) -> dict:
    """测试添加候选光环后的 DPS 变化。

    通过向 Lua 添加一个新的 socket group 来测试光环效果。
    如果 aura 有 charge_configs 字段，在测试前先启用对应的 Charge 配置。
    如果 YAML 配置中有该光环的 Sim 注入效果，在添加光环后额外注入。

    Returns:
        {"name", "dps_before", "dps_after", "dps_pct", "spirit", "error"}
    """
    base_dps = baseline.get("TotalDPS", 0)
    base_ehp = baseline.get("TotalEHP", 0)
    skill_id = aura["skill_id"]

    # 查找 YAML Sim 注入效果（POB 原生不计算的动态/条件性效果）
    sim_effects = _get_candidate_sim_effects(aura["name"], skill_id)

    # 分离 config 类型效果（需要在 initEnv 前设置）和 mod 类型效果（在 initEnv 后注入）
    config_effects = [e for e in sim_effects if e.get("type") == "config"]
    mod_effects = [e for e in sim_effects if e.get("type") == "mod"]

    # 生成 Sim mod 注入的 Lua 代码
    sim_inject_code = ""
    if mod_effects:
        from .pob_unimplemented import inject_effects_to_lua
        sim_inject_code = inject_effects_to_lua(lua, mod_effects, env_var="env")

    # 获取条件配置模板
    charge_configs = aura.get("charge_configs", [])
    if charge_configs and any(c.get("value") is None for c in charge_configs):
        charge_map = _resolve_charge_map(lua, calcs)
        resolved_configs = _fill_charge_configs(charge_configs, charge_map, context=aura["name"])
    else:
        resolved_configs = list(charge_configs)  # 复制，避免修改原始数据

    # 将 config 类型的 Sim 效果追加到 resolved_configs
    # 这些配置（如 multiplierRage）需要在 initEnv 之前设置到 configTab.input
    for ce in config_effects:
        resolved_configs.append({
            "var": ce.get("var", ""),
            "value": ce.get("value", 0),
        })

    # ⚠️ 关键顺序：ifSkill 配置的设置时机
    # POB ConfigOptions 使用 ifSkill 过滤：只有当构筑中存在对应技能时才应用配置。
    # 例如 configResonanceCount 有 ifSkill="Trinity"，
    # 如果在添加 Trinity 技能组之前设置，ifSkill 检查会失败，配置不会生效。
    #
    # 正确流程：
    #   1. 在 Lua 中添加技能组（让 ifSkill 检查能找到技能）
    #   2. 设置 configTab.input（Python 端）
    #   3. 在 Lua 中 rebuild configTab.modList + initEnv
    #
    # 但由于 Lua execute 是原子的，我们无法在 Lua 执行中间插入 Python 代码。
    # 解决方案：将配置设置逻辑嵌入 Lua 代码中。

    # 生成 Lua 配置注入代码（直接追加 mod 到现有 modList，不重建）
    # ⚠️ 不重建 configTab.modList！重建会丢失 auto_configure 的条件配置，
    # 导致基线偏低（实测 -10.9%），使候选光环 DPS 增幅虚高。
    config_inject_code = ""
    config_cleanup_inject_code = ""

    for cfg in resolved_configs:
        var, val = cfg["var"], cfg["value"]
        if isinstance(val, bool):
            lua_val = "true" if val else "false"
        else:
            lua_val = str(val)
        config_inject_code += f'build.configTab.input["{var}"] = {lua_val}\n'
        config_inject_code += f'for _, vd in ipairs(LoadModule("Modules/ConfigOptions")) do if vd.var == "{var}" and vd.apply then pcall(vd.apply, {lua_val}, build.configTab.modList, build.configTab.enemyModList, build) break end end\n'

    # 检查是否需要 Trinity 的 ResonanceCount（自动检测并注入默认值）
    needs_resonance = skill_id == "TrinityPlayer" and not any(
        c.get("var") == "configResonanceCount" for c in resolved_configs
    )
    if needs_resonance:
        config_inject_code += 'build.configTab.input["configResonanceCount"] = 300\n'
        config_inject_code += 'for _, vd in ipairs(LoadModule("Modules/ConfigOptions")) do if vd.var == "configResonanceCount" and vd.apply then pcall(vd.apply, 300, build.configTab.modList, build.configTab.enemyModList, build) break end end\n'
        config_cleanup_inject_code += 'build.configTab.input["configResonanceCount"] = nil\n'

    result = lua.execute(f'''
        local build = _spike_build

        -- ⚠️ 保存原始 modList/enemyModList 的深拷贝，测试后恢复。
        -- 不能只保存引用！ConfigOptions.apply 会直接往 modList 追加 mod，
        -- 如果只保存引用，追加的 mod 也会出现在"原始" modList 中，
        -- 导致 mod 在候选测试之间累积。
        local savedModList = build.configTab.modList
        local savedEnemyModList = build.configTab.enemyModList
        local clonedModList = new("ModList")
        local clonedEnemyModList = new("ModList")
        for _, m in ipairs(savedModList) do clonedModList:AddMod(m) end
        for _, m in ipairs(savedEnemyModList) do clonedEnemyModList:AddMod(m) end
        -- 切换到克隆的 modList，这样原始的不会被修改
        build.configTab.modList = clonedModList
        build.configTab.enemyModList = clonedEnemyModList

        -- 查找候选光环的 skillId 对应的 grantedEffect
        local ge = nil
        -- 先尝试通过 data.gems 查找
        for gid, gem in pairs(data.gems) do
            if gem.grantedEffectId == "{skill_id}" then
                ge = gem.grantedEffect
                break
            end
        end
        -- 再尝试通过 data.skills 直接查找
        if not ge and data.skills["{skill_id}"] then
            ge = data.skills["{skill_id}"]
        end

        if not ge then
            return "NOT_FOUND|" .. "{skill_id}"
        end

        -- 创建新的技能组
        local maxLevel = 0
        for lvl, _ in pairs(ge.levels or {{}}) do
            if lvl > maxLevel then maxLevel = lvl end
        end
        if maxLevel == 0 then maxLevel = 1 end

        -- 动态读取精魄消耗
        local spiritCost = 0
        local maxLvData = ge.levels[maxLevel]
        if maxLvData and maxLvData.spiritReservationFlat then
            spiritCost = maxLvData.spiritReservationFlat
        end

        local newGroup = {{
            enabled = true,
            includeInFullDPS = true,
            label = "[WhatIf] {aura["name"]}",
            slot = nil,
            source = nil,
            mainActiveSkill = 1,
            mainActiveSkillCalcs = 1,
            displaySkillList = {{}},
            displaySkillListCalcs = {{}},
            displayGemList = {{}},
            gemList = {{
                {{
                    skillId = "{skill_id}",
                    nameSpec = ge.name or "{aura["name"]}",
                    level = maxLevel,
                    quality = 0,
                    enabled = true,
                    enableGlobal1 = true,
                    enableGlobal2 = true,
                    count = 1,
                    statSet = {{}},
                    statSetCalcs = {{}},
                    skillMinionSkillStatSetIndexLookup = {{}},
                    skillMinionSkillStatSetIndexLookupCalcs = {{}},
                    grantedEffect = ge,
                }},
            }},
        }}

        -- 注册到构建
        local origCount = #build.skillsTab.socketGroupList
        table.insert(build.skillsTab.socketGroupList, newGroup)

        -- 设置条件配置（必须在技能组添加后，因为 ifSkill 检查需要技能在构筑中）
        -- 例如 Trinity 的 configResonanceCount 有 ifSkill="Trinity"，
        -- 只有当 Trinity 已在 socketGroupList 中时，ConfigOptions 才会应用该配置
        --
        -- ⚠️ 关键：不重建 configTab.modList！
        -- 重建会丢失 auto_configure 设置的条件（如 CritRecently、FrenzyCharges 等），
        -- 导致基线偏低（实测 -10.9%），使候选光环 DPS 增幅虚高。
        -- 改为直接往现有 modList 追加条件 mod。
        {config_inject_code}

        -- 重新计算
        local ok, env = pcall(function()
            return calcs.initEnv(build, "MAIN")
        end)
        if not ok then
            build.skillsTab.socketGroupList[origCount + 1] = nil
            build.configTab.modList = savedModList
            build.configTab.enemyModList = savedEnemyModList
            return "ERROR|" .. tostring(env)
        end

        -- 注入 Sim mod（POB 原生不计算的动态效果）
        {sim_inject_code}

        pcall(calcs.perform, env)
        local newDps = env.player.output.TotalDPS or 0
        local newEhp = env.player.output.TotalEHP or 0

        -- 清理：恢复原始状态
        build.skillsTab.socketGroupList[origCount + 1] = nil
        build.configTab.modList = savedModList
        build.configTab.enemyModList = savedEnemyModList
        -- 清理 input（仅清理本次测试新增的配置）
        {config_cleanup_inject_code}

        return "OK|" .. tostring(newDps) .. "|" .. tostring(newEhp) .. "|" .. tostring(spiritCost)
    ''')

    def _restore_charge_configs():
        """恢复 charge 配置。

        正常情况下 Lua 代码内已恢复 modList，这里只清理 input。
        仅在 Lua 执行失败时需要手动清理。
        """
        if resolved_configs or needs_resonance:
            for cfg in resolved_configs:
                lua.execute(f'_spike_build.configTab.input["{cfg["var"]}"] = nil')
            if needs_resonance:
                lua.execute('_spike_build.configTab.input["configResonanceCount"] = nil')

    if not result:
        _restore_charge_configs()
        return {
            "name": aura["name"], "dps_before": base_dps, "dps_after": base_dps,
            "dps_pct": 0, "spirit": 0, "error": "Lua returned None",
        }

    parts = str(result).split('|')
    if parts[0] == "NOT_FOUND" or parts[0] == "ERROR":
        _restore_charge_configs()
        return {
            "name": aura["name"], "dps_before": base_dps, "dps_after": base_dps,
            "dps_pct": 0, "spirit": 0,
            "error": str(result),
        }

    try:
        new_dps = float(parts[1])
        new_ehp = float(parts[2]) if len(parts) > 2 else base_ehp
        spirit_cost = float(parts[3]) if len(parts) > 3 else 0
    except (ValueError, IndexError):
        _restore_charge_configs()
        return {
            "name": aura["name"], "dps_before": base_dps, "dps_after": base_dps,
            "dps_pct": 0, "spirit": 0, "error": "Parse error",
        }

    dps_pct = ((new_dps - base_dps) / base_dps * 100) if base_dps > 0 else 0
    ehp_pct = ((new_ehp - base_ehp) / base_ehp * 100) if base_ehp > 0 else 0

    return {
        "name": aura["name"],
        "name_cn": aura.get("name_cn", ""),
        "description": aura.get("description", ""),
        "dps_before": base_dps,
        "dps_after": new_dps,
        "dps_pct": dps_pct,
        "ehp_pct": ehp_pct,
        "spirit": spirit_cost,
        "sim_source": ", ".join(e.get("source", "") for e in sim_effects) if sim_effects else "",
        "sim_condition": _get_sim_condition(aura["name"], skill_id),
        "error": None,
    }


def _test_candidate_config_range(lua, calcs, aura: dict,
                                   baseline: dict,
                                   base_dps: float) -> list[dict]:
    """测试候选光环的条件参数在 min/max 时的 DPS 范围。

    仅对有 ifSkill 条件配置的候选光环执行（如 Trinity 的 ResonanceCount）。
    简化实现：在 _test_add_candidate_aura 的基础上，仅改变条件配置值重新计算。

    Returns:
        [{"config_var", "label", "dps_min", "dps_max", "dps_pct_min", "dps_pct_max",
          "condition_label"}, ...]
    """
    skill_id = aura.get("skill_id", "")
    aura_name = aura.get("name", "")

    # 确定需要测试的配置变量
    config_specs = []

    if skill_id == "TrinityPlayer":
        config_specs.append({
            "var": "configResonanceCount",
            "label": "Resonance Count",
            "min": 0,
            "mid": 300,
            "max": 750,
            "condition_label": "共鸣值 0~750"
        })

    # 从 YAML 配置中读取 config_ranges 定义
    yaml_ranges = _get_yaml_config_ranges(aura_name, skill_id)
    for yr in yaml_ranges:
        # 如果 max 为 null，运行时从 baseline MaximumRage 读取
        max_val = yr.get("max")
        if max_val is None and yr.get("var") == "multiplierRage":
            max_val = int(baseline.get("MaximumRage", 0))
            if max_val <= 0:
                max_val = 30  # 默认最大 Rage
        if max_val is not None and max_val > 0:
            config_specs.append({
                "var": yr["var"],
                "label": yr.get("label", yr["var"]),
                "min": yr.get("min", 0),
                "mid": yr.get("mid", max_val // 2),
                "max": max_val,
                "condition_label": yr.get("condition_label", f'{yr.get("label", yr["var"])} {yr.get("min", 0)}~{max_val}'),
            })

    if not config_specs:
        # 对其他候选光环，尝试发现 ifSkill 配置
        try:
            configs = _discover_ifskill_configs(lua, {aura_name})
            for cfg in configs:
                if cfg.get("aura_name") == aura_name:
                    amax = int(cfg.get("actual_max", 0))
                    if amax > 0:
                        config_specs.append({
                            "var": cfg["config_var"],
                            "label": cfg.get("label", cfg["config_var"]),
                            "min": 0,
                            "mid": amax // 2,
                            "max": amax,
                            "condition_label": f'{cfg.get("label", cfg["config_var"])} 0~{amax}'
                        })
        except Exception as e:
            logger.debug("候选光环 %s 发现配置失败: %s", aura_name, e)

    if not config_specs:
        return []

    results = []

    for spec in config_specs:
        var = spec["var"]
        min_val, max_val = spec["min"], spec["max"]

        dps_at_min = None
        dps_at_max = None

        # 在 Lua 中执行：添加光环 → 设置配置 min → 计算 → 设置配置 max → 计算 → 恢复
        # 复用 _test_add_candidate_aura 的完整 socket group 结构
        result_str = lua.execute(f'''
            local build = _spike_build
            local savedModList = build.configTab.modList
            local savedEnemyModList = build.configTab.enemyModList
            local clonedModList = new("ModList")
            local clonedEnemyModList = new("ModList")
            for _, m in ipairs(savedModList) do clonedModList:AddMod(m) end
            for _, m in ipairs(savedEnemyModList) do clonedEnemyModList:AddMod(m) end
            build.configTab.modList = clonedModList
            build.configTab.enemyModList = clonedEnemyModList

            -- 查找 grantedEffect
            local ge = nil
            for gid, gem in pairs(data.gems) do
                if gem.grantedEffectId == "{skill_id}" then
                    ge = gem.grantedEffect
                    break
                end
            end
            if not ge and data.skills["{skill_id}"] then
                ge = data.skills["{skill_id}"]
            end
            if not ge then
                build.configTab.modList = savedModList
                build.configTab.enemyModList = savedEnemyModList
                return "NO_GE"
            end

            -- 创建技能组（完整结构）
            local maxLevel = 0
            for lvl, _ in pairs(ge.levels or {{}}) do
                if lvl > maxLevel then maxLevel = lvl end
            end
            if maxLevel == 0 then maxLevel = 1 end

            local newGroup = {{
                enabled = true,
                includeInFullDPS = true,
                label = "_range_test",
                slot = nil,
                source = nil,
                mainActiveSkill = 1,
                mainActiveSkillCalcs = 1,
                displaySkillList = {{}},
                displaySkillListCalcs = {{}},
                displayGemList = {{}},
                gemList = {{
                    {{
                        skillId = "{skill_id}",
                        nameSpec = ge.name or "{aura_name}",
                        level = maxLevel,
                        quality = 0,
                        enabled = true,
                        enableGlobal1 = true,
                        enableGlobal2 = true,
                        count = 1,
                        statSet = {{}},
                        statSetCalcs = {{}},
                        skillMinionSkillStatSetIndexLookup = {{}},
                        skillMinionSkillStatSetIndexLookupCalcs = {{}},
                        grantedEffect = ge,
                    }}
                }}
            }}

            local origCount = #build.skillsTab.socketGroupList

            -- === 测试 MIN 值 ===
            table.insert(build.skillsTab.socketGroupList, newGroup)
            build.configTab.input["{var}"] = {min_val}
            for _, vd in ipairs(LoadModule("Modules/ConfigOptions")) do
                if vd.var == "{var}" and vd.apply then
                    pcall(vd.apply, {min_val}, build.configTab.modList, build.configTab.enemyModList, build)
                    break
                end
            end
            local env1 = calcs.initEnv(build, "MAIN")
            calcs.perform(env1)
            local dpsMin = env1.player.output.TotalDPS or 0

            -- === 测试 MAX 值 ===
            -- 重建 modList（去除 min 值注入的 mod）
            local clonedModList2 = new("ModList")
            local clonedEnemyModList2 = new("ModList")
            for _, m in ipairs(savedModList) do clonedModList2:AddMod(m) end
            for _, m in ipairs(savedEnemyModList) do clonedEnemyModList2:AddMod(m) end
            build.configTab.modList = clonedModList2
            build.configTab.enemyModList = clonedEnemyModList2
            build.configTab.input["{var}"] = {max_val}
            for _, vd in ipairs(LoadModule("Modules/ConfigOptions")) do
                if vd.var == "{var}" and vd.apply then
                    pcall(vd.apply, {max_val}, build.configTab.modList, build.configTab.enemyModList, build)
                    break
                end
            end
            local env2 = calcs.initEnv(build, "MAIN")
            calcs.perform(env2)
            local dpsMax = env2.player.output.TotalDPS or 0

            -- === 清理 ===
            build.skillsTab.socketGroupList[origCount + 1] = nil
            build.configTab.modList = savedModList
            build.configTab.enemyModList = savedEnemyModList
            build.configTab.input["{var}"] = nil

            return tostring(dpsMin) .. "|" .. tostring(dpsMax)
        ''')

        if result_str and "|" in str(result_str):
            parts = str(result_str).split("|")
            try:
                dps_at_min = float(parts[0])
                dps_at_max = float(parts[1])
            except (ValueError, IndexError):
                pass

        if dps_at_min is not None and dps_at_max is not None:
            pct_min = ((dps_at_min - base_dps) / base_dps * 100) if base_dps > 0 else 0
            pct_max = ((dps_at_max - base_dps) / base_dps * 100) if base_dps > 0 else 0
            results.append({
                "config_var": var,
                "label": spec["label"],
                "dps_min": dps_at_min,
                "dps_max": dps_at_max,
                "dps_pct_min": pct_min,
                "dps_pct_max": pct_max,
                "condition_label": spec["condition_label"],
            })

    return results


def _check_build_has_skill_type(lua, skill_id: str) -> bool:
    """检查构筑的光环组中是否有技能满足精魄辅助的 requireSkillTypes。

    直接从 data.skills[skill_id].requireSkillTypes 读取要求，
    然后检查构筑中是否有技能（通过 data.skills 查找）匹配所有要求的类型。

    Args:
        lua: LuaRuntime
        skill_id: 精魄辅助的 skill_id（如 SupportDeadlyHeraldsPlayer）

    Returns:
        是否有匹配的技能
    """
    result = lua.execute(f'''
        local sid = "{skill_id}"
        local skill_def = data.skills[sid]
        if not skill_def or not skill_def.requireSkillTypes then
            return "YES"
        end

        -- 解析 requireSkillTypes：提取枚举值列表，处理 AND 逻辑
        local required = {{}}
        local has_and = false
        for _, t in ipairs(skill_def.requireSkillTypes) do
            if t == SkillType.AND then
                has_and = true
            else
                required[t] = true
            end
        end

        -- 收集构筑中所有 gem 的 skillTypes（从 data.skills 读取）
        local function collect_types(sk)
            local types = {{}}
            if sk.skillTypes then
                if #sk.skillTypes > 0 then
                    for _, st in ipairs(sk.skillTypes) do
                        types[st] = true
                    end
                else
                    for st, _ in pairs(sk.skillTypes) do
                        types[st] = true
                    end
                end
            end
            if sk.addSkillTypes then
                for _, st in ipairs(sk.addSkillTypes) do
                    types[st] = true
                end
            end
            return types
        end

        -- 检查构筑中每个 gem 是否匹配所有 required 类型
        for i = 1, #_spike_build.skillsTab.socketGroupList do
            local g = _spike_build.skillsTab.socketGroupList[i]
            if g.gemList then
                for j, gem in ipairs(g.gemList) do
                    local sid2 = gem.skillId
                    if sid2 and data.skills[sid2] then
                        local gem_types = collect_types(data.skills[sid2])
                        local match = true
                        for rt, _ in pairs(required) do
                            if not gem_types[rt] then
                                match = false
                                break
                            end
                        end
                        if match then
                            return "YES"
                        end
                    end
                end
            end
        end
        return "NO"
    ''')
    return str(result).strip() == "YES"




def _check_build_condition(lua, condition: str) -> bool:
    """检查构筑是否满足特定条件。

    Args:
        lua: LuaRuntime
        condition: 条件名（如 "FullEnergyShield"、"LowLife"）

    Returns:
        是否满足条件
    """
    result = lua.execute('''
        local build = _spike_build
        local env = calcs.initEnv(build, "MAIN")
        calcs.perform(env)
        local out = env.player.output
        local modDB = env.player.modDB

        local checks = {}
        -- FullEnergyShield: ES == MaxES
        if out.EnergyShield and out.MaximumEnergyShield then
            checks["FullEnergyShield"] = tostring(out.EnergyShield >= out.MaximumEnergyShield - 1)
        end
        -- LowLife
        checks["LowLife"] = tostring(modDB:Flag(nil, "LowLife"))

        local cond = "''' + condition + '''"
        return checks[cond] or "NO"
    ''')
    return str(result).strip() == "true"


def _get_spirit_support_sim_effects(skill_id: str,
                                     is_spell: bool = True,
                                     is_attack: bool = False,
                                     lua=None) -> list[dict]:
    """获取精魄辅助的模拟效果。

    数据来源：
    1. mod 效果 — 从 YAML 配置读取（pob_unimplemented_effects.yaml）
    2. requireSkillTypes — 从 POB data.skills 自动检查
    3. require_build_condition — 从 YAML 配置读取（如 FullEnergyShield、LowLife）
    """
    # 0. 检查 requireSkillTypes（从 POB 数据自动读取，非硬编码）
    if lua:
        can_attach = _check_build_has_skill_type(lua, skill_id)
        if not can_attach:
            logger.debug("精魄辅助 %s 跳过: 构筑中无匹配技能类型", skill_id)
            return []

    # 1. 从 YAML 配置读取 mod 效果和附加条件
    from .pob_unimplemented import load_config
    config = load_config()

    for name, skill_config in config.get("skills", {}).items():
        if skill_config.get("skill_type") != "spirit_support":
            continue
        if skill_config.get("detect", {}).get("skill_id") != skill_id:
            continue

        # 检查 require_flag（Spell/Attack）
        require_flag = skill_config.get("require_flag", "")
        if require_flag == "Spell" and not is_spell:
            return []
        if require_flag == "Attack" and not is_attack:
            return []

        # 检查 require_build_condition（如 FullEnergyShield、LowLife）
        required_condition = skill_config.get("require_build_condition", "")
        if required_condition and lua:
            meets = _check_build_condition(lua, required_condition)
            if not meets:
                logger.debug("精魄辅助 %s 跳过: 不满足条件 %s", skill_id, required_condition)
                return []

        # 读取 effects
        matched = []
        for eff in skill_config.get("effects", []):
            if eff.get("type") == "mod":
                matched.append({
                    "type": "mod",
                    "mod_name": eff.get("mod_name", ""),
                    "mod_type": eff.get("mod_type", "INC"),
                    "value": eff.get("value", 0),
                    "source": eff.get("source", "spirit_sim"),
                    "description": eff.get("description", ""),
                })
        if matched:
            logger.debug("精魄辅助 %s: 从 YAML 读取 %d 个 mod", skill_id, len(matched))
        return matched

    return []


def _test_add_spirit_support(lua, calcs, support: dict,
                             aura_group_idx: int,
                             baseline: dict,
                             skill_flags: dict = None) -> dict:
    """测试向指定光环技能组添加精魄辅助后的 DPS 变化。

    由于 POB 未完整实现精魄辅助的条件 buff 效果，
    本函数会从 pob_unimplemented_effects.yaml 读取模拟效果并注入。

    Args:
        support: 精魄辅助候选数据
        aura_group_idx: 目标光环技能组索引
        baseline: 基线 output
        skill_flags: 技能 flags（用于过滤攻击/法术专属）

    Returns:
        {"name", "dps_before", "dps_after", "dps_pct", "spirit",
         "target_aura", "condition", "note", "estimated", "error"}
    """
    base_dps = baseline.get("TotalDPS", 0)
    base_ehp = baseline.get("TotalEHP", 0)
    skill_id = support["skill_id"]
    is_spell = skill_flags.get("is_spell", True) if skill_flags else True
    is_attack = skill_flags.get("is_attack", False) if skill_flags else False

    # 查找该精魄辅助的模拟效果
    sim_effects = _get_spirit_support_sim_effects(skill_id, is_spell, is_attack, lua)
    inject_lua = ""
    if sim_effects:
        from .pob_unimplemented import inject_effects_to_lua
        inject_lua = inject_effects_to_lua(lua, sim_effects)

    result = lua.execute(f'''
        local build = _spike_build
        local gi = {aura_group_idx}
        local group = build.skillsTab.socketGroupList[gi]
        if not group then return "ERROR|group not found" end

        -- 查找精魄辅助的 grantedEffect
        local ge = nil
        for gid, gem in pairs(data.gems) do
            if gem.grantedEffectId == "{skill_id}" then
                ge = gem.grantedEffect
                break
            end
        end
        if not ge and data.skills["{skill_id}"] then
            ge = data.skills["{skill_id}"]
        end
        if not ge then
            return "NOT_FOUND|{skill_id}"
        end

        local maxLevel = 0
        for lvl, _ in pairs(ge.levels or {{}}) do
            if lvl > maxLevel then maxLevel = lvl end
        end
        if maxLevel == 0 then maxLevel = 1 end

        -- 动态读取精魄消耗
        local spiritCost = 0
        local maxLvData = ge.levels[maxLevel]
        if maxLvData and maxLvData.spiritReservationFlat then
            spiritCost = maxLvData.spiritReservationFlat
        end

        -- 创建精魄辅助宝石对象
        local supportGem = {{
            skillId = "{skill_id}",
            nameSpec = ge.name or "{support["name"]}",
            level = maxLevel,
            quality = 0,
            enabled = true,
            enableGlobal1 = true,
            enableGlobal2 = true,
            count = 1,
            statSet = {{}},
            statSetCalcs = {{}},
            skillMinionSkillStatSetIndexLookup = {{}},
            skillMinionSkillStatSetIndexLookupCalcs = {{}},
            grantedEffect = ge,
            color = "^8",
        }}

        -- 添加到技能组的 gemList
        local origGemCount = #group.gemList
        table.insert(group.gemList, supportGem)

        local ok, env = pcall(calcs.initEnv, build, "MAIN")
        if not ok then
            group.gemList[origGemCount + 1] = nil
            return "ERROR|" .. tostring(env)
        end
        -- 临时增加精魄（在 perform 之前，POB 的 Spirit 在 env.modDB 中）
        env.player.modDB:NewMod("Spirit", "BASE", 500, "SpiritBoost_test")

        -- 注入 POB 未实现的精魄辅助模拟效果（在 perform 之前）
        local HAS_SIM = {1 if inject_lua else 0}
        if HAS_SIM == 1 then
            {inject_lua}
        end

        pcall(calcs.perform, env)
        
        local newDps = env.player.output.TotalDPS or 0
        local newEhp = env.player.output.TotalEHP or 0

        -- 清理
        group.gemList[origGemCount + 1] = nil

        return "OK|" .. tostring(newDps) .. "|" .. tostring(newEhp) .. "|" .. tostring(spiritCost)
    ''')

    if not result:
        return {
            "name": support["name"], "dps_before": base_dps, "dps_after": base_dps,
            "dps_pct": 0, "spirit": 0, "target_aura": "",
            "condition": support.get("condition", ""), "note": support.get("note", ""),
            "description": support.get("description", ""),
            "skill_id": support.get("skill_id", ""),
            "source": support.get("source", ""),
            "estimated": support.get("estimated", False), "error": "Lua returned None",
        }

    parts = str(result).split('|')
    if parts[0] == "NOT_FOUND" or parts[0] == "ERROR":
        return {
            "name": support["name"], "dps_before": base_dps, "dps_after": base_dps,
            "dps_pct": 0, "spirit": 0, "target_aura": "",
            "condition": support.get("condition", ""), "note": support.get("note", ""),
            "description": support.get("description", ""),
            "skill_id": support.get("skill_id", ""),
            "source": support.get("source", ""),
            "estimated": support.get("estimated", False), "error": str(result),
        }

    try:
        new_dps = float(parts[1])
        new_ehp = float(parts[2]) if len(parts) > 2 else base_ehp
        spirit_cost = float(parts[3]) if len(parts) > 3 else 0
    except (ValueError, IndexError):
        return {
            "name": support["name"], "dps_before": base_dps, "dps_after": base_dps,
            "dps_pct": 0, "spirit": 0, "target_aura": "",
            "condition": support.get("condition", ""), "note": support.get("note", ""),
            "description": support.get("description", ""),
            "skill_id": support.get("skill_id", ""),
            "source": support.get("source", ""),
            "estimated": support.get("estimated", False), "error": "Parse error",
        }

    dps_pct = ((new_dps - base_dps) / base_dps * 100) if base_dps > 0 else 0
    ehp_pct = ((new_ehp - base_ehp) / base_ehp * 100) if base_ehp > 0 else 0

    # 获取目标光环名称
    target_aura = ""
    skills_info = _query_active_skills_info(lua, calcs)
    for si in skills_info:
        if si["group_idx"] == aura_group_idx:
            target_aura = si["main_skill_name"]
            break

    return {
        "name": support["name"],
        "name_cn": support.get("name_cn", ""),
        "description": support.get("description", ""),
        "skill_id": support.get("skill_id", ""),
        "source": support.get("source", ""),
        "dps_before": base_dps,
        "dps_after": new_dps,
        "dps_pct": dps_pct,
        "ehp_pct": ehp_pct,
        "spirit": spirit_cost,
        "target_aura": target_aura,
        "target_group_idx": aura_group_idx,
        "condition": support.get("condition", ""),
        "note": support.get("note", ""),
        "estimated": support.get("estimated", False) or bool(sim_effects),
        "error": None,
    }




def _validate_aura_consistency(aura_data: dict) -> list:
    """数据一致性校验，返回警告列表。

    校验规则：
    1. EC MORE 值非零（确保动态读取成功）
    2. Charge 数量与默认值 3 不同时标注
    3. 候选光环无 DPS 影响时检查可能原因
    """
    warnings = []

    existing = aura_data.get("existing_auras", [])
    candidates = aura_data.get("candidate_auras", [])

    # B1. EC MORE 值检查
    for a in existing:
        if a.get("name") == "Elemental Conflux" and a.get("simulated"):
            raw_val = a.get("raw_value", 0)
            gem_level = a.get("gem_level")
            if raw_val <= 0:
                warnings.append(f"EC MORE 值为 {raw_val}（动态读取可能失败），结果不可靠")
            elif gem_level and gem_level != 20:
                warnings.append(f"EC 使用构筑实际等级 Lv{gem_level}（MORE={raw_val:.0f}%），非满级 Lv20")

    # B2. Charge 数量标注
    for a in existing:
        if a.get("name") == "Charge Infusion" and a.get("simulated"):
            cc = a.get("charge_counts", {})
            if cc:
                parts = []
                for ct, val in cc.items():
                    if val != 3:
                        parts.append(f"{ct}={val}")
                if parts:
                    warnings.append(f"Charge Infusion 使用非默认 Charge 数量: {', '.join(parts)}")

    # B3. 空结果归因检查
    for c in candidates:
        if c.get("dps_pct", 0) <= 0.1:
            name = c.get("name", "?")
            warnings.append(f"{name} 无明显 DPS 影响：可能因为构筑条件不满足或模拟环境限制")

    # B4. 精魄辅助无影响检查
    ss_tests = aura_data.get("spirit_support_tests", [])
    zero_ss = [s for s in ss_tests if s.get("dps_pct", 0) <= 0.1]
    if len(zero_ss) == len(ss_tests) and len(ss_tests) > 0:
        warnings.append("所有精魄辅助测试均无 DPS 影响：可能是法术构筑（Direstrike/Precision 对攻击构筑无效）")

    return warnings





def aura_spirit_analysis(lua, calcs, baseline: dict = None,
                         skill_flags: dict = None,
                         dps_breakdown: dict = None,
                         spirit_support_results: list = None,
                         candidate_aura_results: list = None) -> dict:
    """Section 7: 光环与精魄分析。

    7A: 现有光环/精魄移除测试 — 逐一禁用构筑中的光环，测量 DPS 贡献
    7B: 潜在光环推荐 — 使用编排层预计算的结果（干净环境中执行，避免状态污染）
    7C: 精魄辅助推荐 — 使用编排层预计算的结果（干净环境中执行，避免状态污染）
    7D: Spirit Budget 汇总 — 总精魄、已用精魄、推荐精魄

    Args:
        lua: LuaRuntime
        calcs: POB calcs 模块
        baseline: 基线 output
        skill_flags: 技能 flags（用于过滤攻击/法术专属）
        dps_breakdown: DPS 拆解数据（含构筑已有 modifier 总量，如 Speed_INC）
        spirit_support_results: 精魄辅助推荐测试结果（由编排层在干净环境中预计算）
        candidate_aura_results: 候选光环推荐测试结果（由编排层在干净环境中预计算）
    """
    from .calculator import calculate as calc_fn

    # 创建数据桥接器（从 poe-data-miner 读取结构化数据）
    try:
        bridge = POEDataBridge()
    except FileNotFoundError:
        logging.warning("POEDataBridge failed to initialize, using Lua fallback")
        bridge = None

    # 应用品质上限（游戏实际上限 20%），确保分析基于标准品质
    _cap_all_gem_qualities(lua)

    # 预热 _rebuild_config_tab_modlist：首次调用会保存原始 modList 并应用 ConfigOptions。
    # 之后 _test_aura_config_range 等函数的 _set_config_and_rebuild 调用不会再改变基线。
    # 必须在此处完成，否则后续第一次 rebuild 时基线会突然变化。
    _rebuild_config_tab_modlist(lua)

    # 用预热后的环境重新计算 baseline（忽略 full_analysis 传入的旧值）
    baseline = calc_fn(lua, calcs)

    base_dps = baseline.get("TotalDPS", 0)
    is_attack = skill_flags.get("is_attack", False) if skill_flags else False
    is_spell = skill_flags.get("is_spell", True) if skill_flags else True

    # 先查询技能信息以获取光环名称列表
    skills_info = _query_active_skills_info(lua, calcs)
    aura_names = {si["main_skill_name"] for si in skills_info if si["is_aura"]}

    # 动态发现所有与构筑光环匹配的 ifSkill count 配置
    aura_configs = _discover_ifskill_configs(lua, aura_names)
    logger.info("发现 %d 个条件配置: %s",
                len(aura_configs),
                ", ".join(f"{c['aura_name']}/{c['config_var']}({int(c['actual_max'])})"
                          for c in aura_configs))

    # 注入条件中间值（仅当用户/auto_configure 未设置时）
    _inject_ifskill_defaults(lua, calcs, aura_configs=aura_configs)
    baseline = calc_fn(lua, calcs)
    base_dps = baseline.get("TotalDPS", 0)
    logger.info("光环分析基线: TotalDPS=%.0f", base_dps)

    logger.info("技能信息查询完成: %d 个技能组", len(skills_info))

    # 合并 POB 未实现效果配置
    inject_mods_config = _merge_unimplemented_effects(lua)

    # 查询精魄
    total_spirit, reserved_spirit = _query_total_spirit(lua, calcs)
    logger.info("精魄: 总计 %.0f, 已用 %.0f", total_spirit, reserved_spirit)

    # === 7A: 现有光环/精魄移除测试 ===
    existing_auras = []
    seen_aura_names = set()
    for si in skills_info:
        if not si["is_aura"]:
            continue
        # 跳过精魄消耗为 0 且无精魄辅助的组（重复/无效组）
        if si["spirit_cost"] <= 0 and not si["spirit_supports"]:
            continue
        # 跳过重复组（同名光环只保留第一个）
        aura_key = si["main_skill_name"]
        if aura_key in seen_aura_names:
            continue
        seen_aura_names.add(aura_key)

        # 检查是否需要预设配置（如 Charge）
        pre_resolve = _resolve_pre_configs(lua, calcs, si["main_skill_name"])
        pre_configs = pre_resolve[0] if pre_resolve else None
        charge_counts = pre_resolve[1] if pre_resolve else None

        # 检查是否需要注入 mod 模拟（如 Elemental Conflux、Unbound Avatar）
        inject_mods = inject_mods_config.get(si["main_skill_name"])

        # 提取精魄辅助 skill_id 集合（不计入光环辅助增益）
        spirit_support_ids = {ss["skill_id"] for ss in si.get("spirit_supports", []) if ss.get("skill_id")}

        if inject_mods:
            # 动态解析注入 mod 的值（如 EC MORE 从实际宝石等级读取）
            resolved_mods = _resolve_inject_mods(
                lua, calcs, inject_mods, si["main_skill_name"])
            # 使用 mod 注入方式测试
            result = _test_mod_effect(
                lua, calcs, baseline, resolved_mods,
                skill_name=si["main_skill_name"])
            # 模拟光环无辅助宝石可分离，裸光环 = 真实光环
            if "bare_dps_pct" not in result:
                result["bare_dps_pct"] = result.get("dps_pct", 0)
            if "spirit_support_pct" not in result:
                result["spirit_support_pct"] = 0
        else:
            # Step 1: 标准禁组模式（不修改 gem.enabled）获取 no_aura_dps
            # 必须先测 config range（需要干净的 gem 状态）
            # 因为 aura_only 的 gem.enabled 修改在 POB 中恢复不可靠
            simple_result = _test_remove_skill_group(
                lua, calcs, si["group_idx"], baseline,
                skill_name=si["main_skill_name"],
                pre_configs=pre_configs,
                aura_only=False)

            # Step 2: config range 测试（在 gem 状态干净时运行）
            no_aura_dps = simple_result.get("dps_after", baseline.get("TotalDPS", 0))
            config_range = _test_aura_config_range(
                lua, calcs, si["main_skill_name"], baseline,
                aura_configs=aura_configs,
                no_aura_dps=no_aura_dps,
                spirit_support_ids=spirit_support_ids)

            # Step 3: 裸光环测试（会修改 gem.enabled，放在最后）
            result = _test_remove_skill_group(
                lua, calcs, si["group_idx"], baseline,
                skill_name=si["main_skill_name"],
                pre_configs=pre_configs,
                aura_only=True,
                spirit_support_ids=spirit_support_ids)
            # 合并 config range 和 support names
            result["config_ranges"] = config_range

        # 附加精魄辅助的贡献数据（由编排层预计算）
        try:
            from .full_analysis import _test_spirit_support_contributions
            contribs = _test_spirit_support_contributions._cache
            for ss in si["spirit_supports"]:
                sid = ss.get("skill_id", "")
                if sid in contribs:
                    ss.update(contribs[sid])
        except (ImportError, AttributeError):
            pass

        aura_entry = {
            "name": si["main_skill_name"],
            "label": si["label"],
            "group_idx": si["group_idx"],
            "spirit_cost": si["spirit_cost"],
            "spirit_supports": si["spirit_supports"],
            "gems": [g["name"] for g in si["gems"] if g["enabled"]],
            "gem_level": 0,
            "gem_quality": 0,
            "effective_level": 0,
            "more_per_30": 0,
            "quality_speed_inc": 0,
            "has_triggered_dps": si.get("has_triggered_dps", False),
            "triggered_skill_name": si.get("triggered_skill_name", ""),
            **result,
        }

        # 计算有效等级（基础等级 + 辅助等级加成）
        main_gem = si["gems"][0] if si["gems"] else {}
        if main_gem:
            base_level = main_gem.get("level", 0)
            level_bonus = 0
            # 检查辅助宝石的 +level 效果（如 Dialla's +1）
            for g in si["gems"][1:]:
                sid = g.get("skill_id", "")
                # Dialla's Desire: supported_active_skill_gem_level_+ = 1
                # 从 POB data 读取 constantStats
                if sid and not g.get("is_support", False):
                    continue
                bonus = bridge.get_support_level_bonus(sid) if bridge else _get_support_level_bonus(lua, sid)
                level_bonus += bonus
            effective_level = base_level + level_bonus
            # 获取 MORE per 30 resonance（Trinity 的 stat index 0，注意 bridge 用 0-based）
            if bridge:
                more_val = bridge.get_skill_stat_at_level(main_gem.get("skill_id", ""), effective_level, 0)
            else:
                more_val = _get_skill_stat_at_level(lua, main_gem.get("skill_id", ""), 1, effective_level)
            # 获取 Speed INC per quality（从 qualityStats）
            speed_per_q = bridge.get_quality_speed_per_q(main_gem.get("skill_id", "")) if bridge else _get_quality_speed_per_q(lua, main_gem.get("skill_id", ""))
            aura_entry["gem_level"] = base_level
            aura_entry["gem_quality"] = main_gem.get("quality", 0)
            aura_entry["effective_level"] = effective_level
            aura_entry["level_bonus"] = level_bonus
            aura_entry["more_per_30"] = more_val
            aura_entry["quality_speed_inc"] = speed_per_q


        # 保存 Charge 数量供报告使用
        if charge_counts:
            aura_entry["charge_counts"] = charge_counts

        existing_auras.append(aura_entry)

    # 排序：按 DPS 影响绝对值降序
    existing_auras.sort(key=lambda x: abs(x["dps_pct"]), reverse=True)
    logger.info("8A 完成: %d 个光环测试", len(existing_auras))

    # === 7B: 潜在光环推荐 ===
    # 使用编排层在干净环境中预计算的结果（避免 _rebuild_config_tab_modlist 污染）
    available_spirit = total_spirit - reserved_spirit
    if candidate_aura_results is not None:
        candidate_auras = candidate_aura_results
        logger.info("7B 使用预计算结果: %d 个候选光环测试", len(candidate_auras))
    else:
        # 向后兼容：如果没有传入预计算结果，仍在内部执行（精度可能偏低）
        logger.warning("7B 未提供预计算结果，在内部执行（可能受状态污染影响）")
        candidate_auras = []
        for aura in _AURA_CANDIDATES:
            if aura["name"] in aura_names:
                continue
            result = _test_add_candidate_aura(lua, calcs, aura, baseline)
            actual_spirit = result.get("spirit", 0)
            if actual_spirit > available_spirit:
                shortfall = actual_spirit - available_spirit
                result["spirit_shortfall"] = shortfall
                result["spirit_note"] = f"需精魄 {actual_spirit:.0f}（缺 {shortfall:.0f}）"
            # 对有条件配置的候选光环，测试条件参数范围
            if result.get("dps_pct", 0) > 0.1 and result.get("error") is None:
                try:
                    config_range = _test_candidate_config_range(
                        lua, calcs, aura, baseline, base_dps)
                    if config_range:
                        result["config_ranges"] = config_range
                except Exception as e:
                    logger.debug("候选光环 %s 范围测试失败: %s", aura["name"], e)
            candidate_auras.append(result)
        candidate_auras.sort(key=lambda x: x.get("dps_pct", 0), reverse=True)

    logger.info("7B 完成: %d 个候选光环测试", len(candidate_auras))

    # === 7C: 精魄辅助推荐 ===
    # 使用编排层在干净环境中预计算的结果（避免 _rebuild_config_tab_modlist 污染）
    if spirit_support_results is not None:
        spirit_support_tests = spirit_support_results
        logger.info("7C 使用预计算结果: %d 个精魄辅助测试", len(spirit_support_tests))
    else:
        # 向后兼容：如果没有传入预计算结果，仍在内部执行（精度可能偏低）
        logger.warning("7C 未提供预计算结果，在内部执行（可能受状态污染影响）")
        spirit_support_tests = []

        aura_groups = [si for si in skills_info if si["is_aura"]]
        discovered_supports = discover_spirit_supports(lua)

        hardcoded_formatted = []
        for ss in _SPIRIT_SUPPORT_CANDIDATES:
            hardcoded_formatted.append({
                "key": ss.get("key", ""),
                "name": ss.get("name", ""),
                "name_cn": ss.get("name_cn", ""),
                "skill_id": ss.get("skill_id", ""),
                "spirit": ss.get("spirit", 0),
                "description": ss.get("description", ""),
                "condition": ss.get("condition", ""),
                "note": ss.get("note", ""),
                "estimated": ss.get("estimated", False),
            })

        merged_supports = merge_candidates(hardcoded_formatted, discovered_supports)
        filtered_supports = filter_spirit_supports(
            merged_supports, is_attack, is_spell, skill_flags)
        filtered_supports.sort(key=lambda x: x.get("spirit", 0))

        for ss in filtered_supports:
            for aura_si in aura_groups:
                result = _test_add_spirit_support(
                    lua, calcs, ss, aura_si["group_idx"], baseline, skill_flags)
                actual_spirit = result.get("spirit", 0)
                if actual_spirit > available_spirit:
                    shortfall = actual_spirit - available_spirit
                    result["spirit_shortfall"] = shortfall
                    result["spirit_note"] = (
                        f"需精魄 {actual_spirit:.0f}（缺 {shortfall:.0f}）")
                result["source"] = ss.get("source", "unknown")
                spirit_support_tests.append(result)

    # 过滤有效结果（DPS > 0.1%）并取 Top 5
    effective_tests = [t for t in spirit_support_tests if t.get("dps_pct", 0) > 0.1]
    effective_tests.sort(key=lambda x: -abs(x.get("dps_pct", 0)))
    top_5_tests = effective_tests[:5]

    logger.info("7C 完成: %d 个精魄辅助测试，%d 个有效，Top 5 已选择",
                len(spirit_support_tests), len(effective_tests))

    # === 7D: Spirit Budget ===
    # 计算推荐精魄消耗总和（含精魄不足项）
    recommended_spirit = 0
    for ca in candidate_auras:
        if ca.get("dps_pct", 0) > 0.1:
            recommended_spirit += ca.get("spirit", 0)

    spirit_budget = {
        "total": total_spirit,
        "reserved": reserved_spirit,
        "available": available_spirit,
        "recommended_total": recommended_spirit,
        "recommended_remaining": available_spirit - recommended_spirit,
    }

    # === 提取构筑已有 modifier 总量（来自 dps_breakdown） ===
    build_modifiers = {}
    if dps_breakdown:
        for item in dps_breakdown.get("formula_items", []):
            key = item.get("key", "")
            total = item.get("total_value", 0)
            display = item.get("display_value", "")
            # 提取关键 modifier：Speed_INC, ElementalDamage_INC, ElementalDamage_MORE 等
            if key and total:
                build_modifiers[key] = {"total": total, "display": display}

    # 运行一致性校验
    aura_data = {
        "existing_auras": existing_auras,
        "candidate_auras": candidate_auras,
        "spirit_support_tests": spirit_support_tests,
    }
    warnings = _validate_aura_consistency(aura_data)

    # 检测 POB 未实现的主动技能效果（非光环）
    from .pob_unimplemented import detect_unimplemented_skills, estimate_dps_impact, load_config
    unimpl_detected = detect_unimplemented_skills(lua)
    unimpl_estimates = []
    config = load_config()
    
    for item in unimpl_detected:
        skill_name = item.get("skill_name", "")
        skill_config = config.get("skills", {}).get(skill_name, {})
        skill_type = skill_config.get("skill_type", "active")
        
        # 只处理主动技能（光环已在上面处理）
        if skill_type != "active":
            continue
        
        # 估算 DPS 影响
        estimate = estimate_dps_impact(lua, calcs, item["effects"], baseline_dps=base_dps)
        if estimate["delta_pct"] > 0:
            unimpl_estimates.append({
                "skill_name": item["skill_name"],
                "description": item["description"],
                "delta_pct": estimate["delta_pct"],
                "baseline_dps": estimate["baseline_dps"],
                "estimated_dps": estimate["estimated_dps"],
            })

    return {
        "existing_auras": existing_auras,
        "candidate_auras": candidate_auras,
        "spirit_support_tests": spirit_support_tests,
        "spirit_budget": spirit_budget,
        "build_modifiers": build_modifiers,
        "warnings": warnings,
        "unimplemented_effects": unimpl_estimates,
    }


