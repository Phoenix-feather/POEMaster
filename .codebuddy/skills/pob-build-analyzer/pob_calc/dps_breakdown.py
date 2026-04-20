"""DPS 来源拆解模块。

职责：
- dps_breakdown: 从 POB tabulation 解析 DPS 公式
- _classify_source / _source_label_fallback
- 所有 _parse_* / _compute_* 辅助函数
"""
import logging
import re
from pathlib import Path
from .calculator import calculate

logger = logging.getLogger(__name__)


def _find_best_dps_socket_group(lua, calcs) -> tuple:
    """延迟导入 full_analysis 避免循环依赖。"""
    from .full_analysis import _find_best_dps_socket_group as _impl
    return _impl(lua, calcs)


def _extract_damage_composition(baseline: dict) -> list:
    """延迟导入 full_analysis 避免循环依赖。"""
    from .full_analysis import _extract_damage_composition as _impl
    return _impl(baseline)


# =============================================================================
# DPS 来源拆解（v1.0.11）
# =============================================================================
#
# 设计原则：
#   1. Output-driven：从 output 非零值判断哪些公式项活跃
#   2. Tabulate 拆解：对每个活跃公式项调用 skillModList:Tabulate() 获取 mod 级来源
#   3. 两层粒度：第一层按公式项分组，第二层每组内按 source 展开全部 mod
#   4. Source 分类：mod.source 前缀 — Base/Tree/Item/Skill/Config
#   5. Label 可读化：Tree→天赋名，Item→物品名，Skill→技能名
#   6. category_summary：每个公式项内按 category 聚合的汇总值
#
# Spike 确认（本轮探索）：
#   - Tabulate("MORE") 的 entry.value 是百分比原值（如 39，不是 1.39）
#     MoreInternal 内部做 result *= (1 + value/100)
#   - node.dn 可靠（PassiveTree.lua 构建时设置，_get_notable_nodes 已验证）
#   - Base Damage 由三部分组成：
#     宝石/武器基础: source[{Type}Min/Max]
#     added damage 词缀: skillModList:Sum("BASE", cfg, "{Type}Min/Max") → 可 Tabulate
#     baseMultiplier: grantedEffectLevel.baseMultiplier
#
# POB mod.source 格式：
#   "Base"                    → 游戏常量
#   "Tree:{nodeId}"           → 被动天赋
#   "Item:{itemId}:{name}"    → 装备/珠宝
#   "Skill:{skillId}"         → 技能宝石
#   "Config"                  → 面板设置


def _classify_source(source: str, jewel_node_ids: set = None) -> str:
    """将 mod.source 字符串分类为来源类型。

    珠宝半径效果的 source 格式为 "Tree:{nodeId}"，其中 nodeId 是珠宝槽位。
    通过 jewel_node_ids 集合识别这些节点，将其分类为 "Jewel" 而非 "Tree"。
    """
    if not source:
        return "Other"
    # sim mods（我们模拟注入的 POB 未实现效果）
    if "sim" in source.lower():
        return "Sim"
    prefix = source.split(":")[0] if ":" in source else source
    if prefix == "Tree" and jewel_node_ids:
        node_id = source.split(":")[1] if ":" in source else ""
        if node_id in jewel_node_ids:
            return "Jewel"
    if prefix in ("Base", "Tree", "Item", "Skill", "Config"):
        return prefix
    return "Other"


def _source_label_fallback(source: str, node_names: dict = None) -> str:
    """当 Lua 端未返回 label 时的 fallback 转换。"""
    if not source:
        return "未知"
    if "sim" in source.lower():
        # sim mods 的人类可读名称
        clean = source.replace("_sim", "").replace("_", " ")
        return f"⚠ {clean} (模拟)"
    if source == "Base":
        return "基础值"
    if source == "Config":
        return "配置"
    prefix = source.split(":")[0] if ":" in source else source
    rest = source[len(prefix)+1:] if ":" in source else ""
    if prefix == "Tree":
        # 优先使用天赋名称映射
        if node_names and rest in node_names:
            return node_names[rest]
        return f"天赋#{rest}"
    if prefix == "Item":
        name = rest.split(":", 1)[-1] if ":" in rest else rest
        return name if name else f"物品#{rest}"
    if prefix == "Skill":
        return f"技能#{rest}"
    if prefix == "Jewel":
        return f"珠宝#{rest}"
    return source


def dps_breakdown(lua, calcs, baseline: dict = None) -> dict:
    """DPS 来源拆解 — 将当前 DPS 的每个公式项拆解到具体来源。

    Output-driven：从 output.* 非零值判断活跃公式组件，
    对每个组件调用 skillModList:Tabulate() 获取 mod 来源。
    两层粒度：按公式项分组，每组内按 source 分类。
    Label 可读化：天赋→名称，装备→物品名，技能→宝石名。

    Args:
        lua: LuaRuntime
        calcs: POB calcs 模块
        baseline: 基线 output（None 则重新计算）

    Returns:
        {
            "total_dps": float,
            "average_hit": float,
            "speed": float,
            "combined_dps": float,
            "active_damage_types": [str],
            "formula_items": [
                {
                    "key": str,
                    "formula_name": str,
                    "total_value": float,
                    "display_value": str,
                    "category_summary": {category: float},
                    "sources": [{source, label, category, value, mod_name}, ...]
                }, ...
            ]
        }
    """
    if baseline is None:
        baseline = calculate(lua, calcs)

    # 如果 TotalDPS=0，自动切换到最大 DPS 的技能组
    if baseline.get("TotalDPS", 0) == 0:
        best_group, best_dps = _find_best_dps_socket_group(lua, calcs)
        if best_group is not None and best_dps > 0:
            lua.execute(f'_spike_build.mainSocketGroup = {best_group}')
            baseline = calculate(lua, calcs)
            logger.info("dps_breakdown: 自动切换到技能组 %d (DPS=%.0f)", best_group, best_dps)

    # 一次 Lua 调用完成全部查询
    # 输出格式：每行 SECTION|... 用 \n 分隔
    # Tabulate entries: modName\1source\1value\1label 用 \2 分隔
    lua_script = r'''
        local build = _spike_build
        local env = calcs.initEnv(build, "MAIN")
        calcs.perform(env)
        local ms = env.player.mainSkill
        if not ms then return "" end

        local cfg = ms.skillCfg
        local skillModList = ms.skillModList
        local output = env.player.output
        local lines = {}

        -- === 建立 source → 可读名 映射 ===
        local nodeNames = {}
        for id, node in pairs(build.spec.allocNodes) do
            nodeNames[tostring(id)] = node.dn or ("Node "..tostring(id))
        end
        -- 未分配节点也查（可能有 granted passive 等）
        if build.spec.tree and build.spec.tree.nodes then
            for id, node in pairs(build.spec.tree.nodes) do
                if not nodeNames[tostring(id)] then
                    nodeNames[tostring(id)] = node.dn or ("Node "..tostring(id))
                end
            end
        end

        local skillNames = {}
        if env.player.activeSkillList then
            for _, sk in ipairs(env.player.activeSkillList) do
                local ge = sk.activeEffect and sk.activeEffect.grantedEffect
                if ge then
                    local modSrc = ge.modSource or ""
                    local sid = modSrc:match("Skill:(.+)")
                    if sid and ge.name then
                        skillNames[sid] = ge.name
                    end
                end
                -- 辅助宝石也纳入映射
                if sk.supportList then
                    for _, sup in ipairs(sk.supportList) do
                        local sge = sup.grantedEffect
                        if sge then
                            local sms = sge.modSource or ""
                            local ssid = sms:match("Skill:(.+)")
                            if ssid and sge.name then
                                skillNames[ssid] = sge.name
                            end
                        end
                    end
                end
            end
        end

        -- 物品名映射 + slot 部位映射
        local itemNames = {}
        local itemNameToSlot = {} -- "物品名, 基底" → slotName（用于标注部位）
        -- 物品 ActorCondition 映射：item source → {ActorCondition var 列表}
        -- 用于检测 "per elemental ailment" 类效果（如 Yoke of Suffering）
        -- POB 的 Tabulate 解包 EnemyModifier 后子 mod 丢失 ActorCondition tag，
        -- 所以需要从 item.modList 原始数据中提取
        local itemActorConds = {} -- source → "Cond1,Cond2,..."
        if build.itemsTab and build.itemsTab.items then
            for id, item in pairs(build.itemsTab.items) do
                if item.name then
                    itemNames[tostring(id)] = item.name
                end
                -- 从 item.modList 提取 ActorCondition 条件
                if item.modList then
                    local conds = {}
                    for mi = 1, #item.modList do
                        local m = item.modList[mi]
                        if m.name == "EnemyModifier" then
                            local j = 1
                            while m[j] do
                                local t = m[j]
                                if type(t) == "table" and t.type == "ActorCondition" and t.actor == "enemy" then
                                    conds[#conds+1] = tostring(t.var or "")
                                end
                                j = j + 1
                            end
                        end
                    end
                    if #conds > 0 then
                        -- item 的 mod source 格式: "Item:-1:物品名, 基底"
                        -- item.name 通常已含基底（如 "Yoke of Suffering, Bloodstone Amulet"）
                        -- 但 item.baseName 可能重复追加，所以用完整名称
                        local srcKey = "Item:-1:" .. (item.name or "")
                        if item.baseName and not (item.name and item.name:find(item.baseName, 1, true)) then
                            srcKey = srcKey .. ", " .. item.baseName
                        end
                        itemActorConds[srcKey] = table.concat(conds, ",")
                    end
                end
            end
        end
        -- 通过 orderedSlots 建立 物品名 → slotName 映射
        -- 因为 mod source 中 itemId 始终是 -1 (Item.lua:1760)，只能用名称匹配
        if build.itemsTab and build.itemsTab.orderedSlots then
            for _, slot in ipairs(build.itemsTab.orderedSlots) do
                if slot.selItemId and slot.selItemId ~= 0 and slot.slotName then
                    local sItem = build.itemsTab.items[slot.selItemId]
                    if sItem and sItem.name then
                        -- key = "物品名" (不含基底)
                        itemNameToSlot[sItem.name] = slot.slotName
                        -- 也存 "物品名, 基底" 格式（mod source 中的 name 含基底）
                        if sItem.baseName then
                            itemNameToSlot[sItem.name .. ", " .. sItem.baseName] = slot.slotName
                        end
                    end
                end
            end
        end

        -- 珠宝节点映射：nodeId → 物品名
        -- 珠宝半径效果的 mod 使用 source="Tree:{nodeId}"，需要识别为 Jewel 而非 Tree
        -- 同时需要识别 GrantedPassive（如 Megalomaniac "Allocates"）分配的天赋节点
        local jewelNodeMap = {}
        if build.itemsTab and build.itemsTab.orderedSlots then
            for _, slot in ipairs(build.itemsTab.orderedSlots) do
                local sn = slot.slotName or ""
                if sn:find("^Jewel ") and slot.nodeId and slot.selItemId then
                    local jItem = build.itemsTab.items[slot.selItemId]
                    if jItem and jItem.name then
                        -- 珠宝槽位本身
                        jewelNodeMap[tostring(slot.nodeId)] = jItem.name

                        -- GrantedPassive 分配的天赋节点
                        -- (source="Tree:{grantedNodeId}"，需要用 notableMap 查找)
                        if jItem.modList then
                            for mi = 1, #jItem.modList do
                                local m = jItem.modList[mi]
                                local mName = type(m.name) == "string" and m.name or (type(m[1]) == "string" and m[1] or "")
                                if mName == "GrantedPassive" and m.value then
                                    local gpName = tostring(m.value)
                                    -- 通过 notableMap 找到节点 ID
                                    if build.spec.tree and build.spec.tree.notableMap then
                                        local gpNode = build.spec.tree.notableMap[gpName]
                                        if gpNode and gpNode.id then
                                            jewelNodeMap[tostring(gpNode.id)] = jItem.name .. " → " .. (gpNode.dn or gpName)
                                        end
                                    end
                                end
                            end
                        end
                    end
                end
            end
        end

        local function resolveLabel(src)
            if not src or src == "" then return "Unknown" end
            if src == "Base" then return "Base" end
            if src == "Config" then return "Config" end
            local prefix, rest = src:match("^([^:]+):(.+)$")
            if not prefix then return src end
            if prefix == "Tree" then
                -- 检查是否是珠宝相关节点（珠宝槽位半径效果 或 GrantedPassive 天赋）
                if jewelNodeMap[rest] then
                    return jewelNodeMap[rest]
                end
                return nodeNames[rest] or ("Node "..rest)
            end
            if prefix == "Item" then
                local itemId = rest:match("^(%-?%d+)")
                if itemId then
                    -- source format: "Item:-1:Heart of the Well, Diamond" or "Item:3:xxx" or "Item:3"
                    local nameFromSrc = rest:match("^%-?%d+:(.+)$")
                    local displayName = nameFromSrc
                    if not displayName or displayName == "" then
                        displayName = itemNames[itemId] or ("Item "..itemId)
                    end
                    -- 附加 slot 部位标签（通过物品名匹配）
                    local slotLabel = itemNameToSlot[displayName]
                    if not slotLabel then
                        -- 尝试只用逗号前的名称部分匹配
                        local shortName = displayName:match("^([^,]+)")
                        if shortName then
                            slotLabel = itemNameToSlot[shortName]
                        end
                    end
                    if slotLabel then
                        -- 简化 "Jewel 61834" → "Jewel"
                        local displaySlot = slotLabel:match("^Jewel ") and "Jewel" or slotLabel
                        displayName = displayName .. " (" .. displaySlot .. ")"
                    end
                    return displayName
                end
                return rest
            end
            if prefix == "Skill" then
                return skillNames[rest] or ("Skill "..rest)
            end
            return src
        end

        -- === 序列化 Tabulate ===
        -- 每条: modName\1source\1value\1label\1conditionTag
        local function tabStr(modType, ...)
            local tab = skillModList:Tabulate(modType, cfg, ...)
            local parts = {}
            for _, entry in ipairs(tab) do
                if entry.value ~= 0 then
                    local m = entry.mod
                    local src = m.source or "Unknown"
                    local name = type(m.name) == "string" and m.name or "?"
                    local lbl = resolveLabel(src)
                    -- 检测条件标签：SkillType.Triggered 等条件限制
                    local condTag = ""
                    local idx = 1
                    while m[idx] do
                        local tag = m[idx]
                        if type(tag) == "table" and tag.type == "SkillType" then
                            if tag.skillType == SkillType.Triggered then
                                condTag = "Triggered"
                            end
                        end
                        idx = idx + 1
                    end
                    parts[#parts+1] = name .. "\1" .. src .. "\1" .. tostring(entry.value) .. "\1" .. lbl .. "\1" .. condTag
                end
            end
            return table.concat(parts, "\2")
        end

        -- enemyDB（全局，供 CritChance 和 effMult 等段使用）
        local enemyDB = env.enemyDB

        -- === 1. 识别活跃伤害类型 ===
        local dmgTypes = {"Physical", "Lightning", "Cold", "Fire", "Chaos"}
        local activeDT = {}
        for _, dt in ipairs(dmgTypes) do
            if (output[dt.."HitAverage"] or 0) > 0 then
                activeDT[#activeDT+1] = dt
            end
        end
        lines[#lines+1] = "META|active_types|" .. table.concat(activeDT, ",")

        -- 输出珠宝节点 ID 列表（Python 端用于区分 Tree vs Jewel）
        local jnIds = {}
        for nid, _ in pairs(jewelNodeMap) do
            jnIds[#jnIds+1] = nid
        end
        if #jnIds > 0 then
            lines[#lines+1] = "META|jewel_nodes|" .. table.concat(jnIds, ",")
        end

        -- damageStatsForTypes 逻辑 (CalcOffence.lua:52-63)
        local dtFlags = {
            Physical=0x01, Lightning=0x02, Cold=0x04,
            Fire=0x08, Elemental=0x0E, Chaos=0x10,
        }
        local dtOrder = {"Physical","Lightning","Cold","Fire","Elemental","Chaos"}

        local function getModNames(tf)
            local mn = {"Damage"}
            for _, tp in ipairs(dtOrder) do
                local f = dtFlags[tp]
                if f and (tf & f) ~= 0 then
                    mn[#mn+1] = tp .. "Damage"
                end
            end
            return mn
        end

        -- === 2. Base Damage 拆解 ===
        local damageSource = ms.skillData.sourceInstance or (env.player.weaponData1 or {})
        local baseMultiplier = 1
        if ms.activeEffect and ms.activeEffect.grantedEffectLevel then
            baseMultiplier = ms.activeEffect.grantedEffectLevel.baseMultiplier or ms.skillData.baseMultiplier or 1
        end
        for _, dt in ipairs(activeDT) do
            local dtMin = dt.."Min"
            local dtMax = dt.."Max"
            -- 宝石/武器基础
            local gemMin = damageSource[dtMin] or 0
            local gemMax = damageSource[dtMax] or 0
            -- added damage (可 Tabulate)
            local addedMinSum = skillModList:Sum("BASE", cfg, dtMin)
            local addedMaxSum = skillModList:Sum("BASE", cfg, dtMax)
            local addedMinTab = tabStr("BASE", dtMin)
            local addedMaxTab = tabStr("BASE", dtMax)
            -- addedMult
            local addedMult = 1
            local addedMultINC = skillModList:Sum("INC", cfg, "Added"..dt.."Damage", "AddedDamage")
            local addedMultMORE = skillModList:More(cfg, "Added"..dt.."Damage", "AddedDamage")
            if addedMultINC ~= 0 or addedMultMORE ~= 1 then
                addedMult = (1 + addedMultINC / 100) * addedMultMORE
            end
            -- 总 base = (gem + added*addedMult) * baseMultiplier
            local totalMin = (gemMin + addedMinSum * addedMult) * baseMultiplier
            local totalMax = (gemMax + addedMaxSum * addedMult) * baseMultiplier
            if totalMin > 0 or totalMax > 0 then
                -- 格式: BASE_DMG|type|totalMin|totalMax|gemMin|gemMax|addedMult|baseMultiplier|addedMinTab|addedMaxTab
                lines[#lines+1] = "BASE_DMG|" .. dt .. "|"
                    .. tostring(totalMin) .. "|" .. tostring(totalMax) .. "|"
                    .. tostring(gemMin) .. "|" .. tostring(gemMax) .. "|"
                    .. tostring(addedMult) .. "|" .. tostring(baseMultiplier) .. "|"
                    .. addedMinTab .. "|" .. addedMaxTab
            end
        end

        -- === 3. Damage INC/MORE (按 mod 类别分组，不按伤害类型重复) ===
        -- 收集所有活跃伤害类型涉及的 mod 名称（去重）
        -- 例如 Lightning+Cold+Fire → {"Damage", "LightningDamage", "ColdDamage", "FireDamage", "ElementalDamage"}
        local allModNames = {}
        local seenModName = {}
        -- 同时记录每个 modName 影响的伤害类型
        local modNameAffects = {} -- modName → {dt1, dt2, ...}
        for _, dt in ipairs(activeDT) do
            local tf = dtFlags[dt]
            local mn = getModNames(tf)
            for _, m in ipairs(mn) do
                if not seenModName[m] then
                    seenModName[m] = true
                    allModNames[#allModNames+1] = m
                    modNameAffects[m] = {}
                end
                modNameAffects[m][#modNameAffects[m]+1] = dt
            end
        end
        -- 按优先级排序: Damage(通用) > ElementalDamage > 特定元素Damage
        local modNameOrder = {Damage=1, ElementalDamage=2, PhysicalDamage=3,
            LightningDamage=4, ColdDamage=5, FireDamage=6, ChaosDamage=7}
        table.sort(allModNames, function(a, b)
            return (modNameOrder[a] or 99) < (modNameOrder[b] or 99)
        end)
        -- 每个 modName 单独 Tabulate
        for _, modName in ipairs(allModNames) do
            local incSum = skillModList:Sum("INC", cfg, modName)
            local incTab = tabStr("INC", modName)
            local affects = table.concat(modNameAffects[modName], ",")
            if incSum ~= 0 or (incTab and incTab ~= "") then
                -- 格式: DMG_INC_BY_MOD|modName|incSum|affects|tabEntries
                lines[#lines+1] = "DMG_INC_BY_MOD|" .. modName .. "|" .. tostring(incSum) .. "|" .. affects .. "|" .. incTab
            end
        end
        -- MORE 类似处理（但通常只有 Damage MORE，特定元素 MORE 很少见）
        for _, modName in ipairs(allModNames) do
            local moreVal = skillModList:More(cfg, modName)
            local moreTab = tabStr("MORE", modName)
            if moreVal ~= 1 or (moreTab and moreTab ~= "") then
                local affects = table.concat(modNameAffects[modName], ",")
                lines[#lines+1] = "DMG_MORE_BY_MOD|" .. modName .. "|" .. tostring(moreVal) .. "|" .. affects .. "|" .. moreTab
            end
        end

        -- === 4. Speed ===
        if (output.Speed or 0) > 0 then
            local baseSpeed = 0
            local baseSpeedLabel = "Base"
            local isAttack = cfg.flags and (cfg.flags & 0x01) ~= 0
            local isTrigger = false
            local baseCastTime = 0
            if isAttack and damageSource and damageSource.AttackRate then
                baseSpeed = damageSource.AttackRate
                baseCastTime = 1 / baseSpeed
                baseSpeedLabel = "武器攻击频率"
            elseif ms.skillData.castTimeOverride then
                baseCastTime = ms.skillData.castTimeOverride
                baseSpeed = 1 / baseCastTime
                baseSpeedLabel = "施法时间(Override)"
            elseif ms.activeEffect.grantedEffect.castTime
                   and ms.activeEffect.grantedEffect.castTime > 0
                   and not ms.skillData.triggered then
                baseCastTime = ms.activeEffect.grantedEffect.castTime
                baseSpeed = 1 / baseCastTime
                baseSpeedLabel = "基础施法频率 (1/" .. baseCastTime .. "s)"
            elseif ms.skillData.triggerRate then
                baseSpeed = ms.skillData.triggerRate
                isTrigger = true
                baseSpeedLabel = "触发频率"
            elseif ms.skillData.triggerTime then
                local cdRec = 1 + skillModList:Sum("INC", cfg, "CooldownRecovery") / 100
                local linked = skillModList:Sum("BASE", cfg, "ActiveSkillsLinkedToTrigger")
                local trigTime = ms.skillData.triggerTime / cdRec
                if linked > 0 then trigTime = trigTime * linked end
                baseSpeed = 1 / trigTime
                isTrigger = true
                baseSpeedLabel = "触发频率 (cd=" .. string.format("%.3f", ms.skillData.triggerTime) .. "s)"
            else
                baseSpeed = output.Speed
                isTrigger = true
                baseSpeedLabel = "最终速度(POB计算)"
            end
            -- 输出 base
            lines[#lines+1] = "SPEED_BASE|Speed|" .. string.format("%.4f", baseSpeed) .. "|" .. baseSpeedLabel
            -- INC
            local sInc = skillModList:Sum("INC", cfg, "Speed")
            lines[#lines+1] = "SPEED_INC|Speed|" .. tostring(sInc) .. "|" .. tabStr("INC", "Speed")
            -- MORE
            local sMore = skillModList:More(cfg, "Speed")
            lines[#lines+1] = "SPEED_MORE|Speed|" .. tostring(sMore) .. "|" .. tabStr("MORE", "Speed")
            -- 额外信息：触发标记、最终速度、ActionSpeedMod
            lines[#lines+1] = "SPEED_META|" .. tostring(isTrigger) .. "|" .. tostring(output.Speed)
                .. "|" .. tostring(output.ActionSpeedMod or 1)
                .. "|" .. tostring(baseCastTime)
                .. "|" .. (output.Cooldown and tostring(output.Cooldown) or "0")
        end

        -- === 5. CritChance ===
        if (output.CritChance or 0) > 0 then
            -- POB 的 baseCrit 有多种来源（critOverride/CritChanceBase/source），
            -- 直接从 POB 计算后推断，避免遗漏
            local baseCrit = ms.skillData.CritChance or damageSource.CritChance or 0
            -- CritChanceBase override（如升华15%锁定）
            local baseCritOverride = skillModList:Override(cfg, "CritChanceBase")
            if baseCritOverride then baseCrit = baseCritOverride end
            -- CritChance override（100%暴击等）
            local critOverride = skillModList:Override(cfg, "CritChance")
            if critOverride then baseCrit = critOverride end
            local ccB = skillModList:Sum("BASE", cfg, "CritChance")
                + (env.mode_effective and enemyDB:Sum("BASE", nil, "SelfCritChance") or 0)
            local ccI = skillModList:Sum("INC", cfg, "CritChance")
                + (env.mode_effective and enemyDB:Sum("INC", nil, "SelfCritChance") or 0)
            local ccM = skillModList:More(cfg, "CritChance")
            -- 格式: CRIT_BASE|CritChance|ccB|baseCrit|actualCC|ccI|ccM|tabEntries
            -- actualCC/ccI/ccM 放在 tabEntries 之前，避免 tabEntries 中的 | 干扰 split
            local actualCC = output.CritChance or 0
            lines[#lines+1] = "CRIT_BASE|CritChance|" .. tostring(ccB) .. "|" .. tostring(baseCrit) .. "|" .. tostring(actualCC) .. "|" .. tostring(ccI) .. "|" .. tostring(ccM) .. "|" .. tabStr("BASE", "CritChance")
            lines[#lines+1] = "CRIT_INC|CritChance|" .. tostring(ccI) .. "|" .. tabStr("INC", "CritChance")
            lines[#lines+1] = "CRIT_MORE|CritChance|" .. tostring(ccM) .. "|" .. tabStr("MORE", "CritChance")
        end

        -- === 6. CritMultiplier ===
        if (output.CritMultiplier or 0) > 0 and not skillModList:Flag(cfg, "NoCritMultiplier") then
            local cmB = skillModList:Sum("BASE", cfg, "CritMultiplier")
            lines[#lines+1] = "CRITMULTI_BASE|CritMultiplier|" .. tostring(cmB) .. "|" .. tabStr("BASE", "CritMultiplier")
            local cmI = skillModList:Sum("INC", cfg, "CritMultiplier")
            lines[#lines+1] = "CRITMULTI_INC|CritMultiplier|" .. tostring(cmI) .. "|" .. tabStr("INC", "CritMultiplier")
            local cmM = skillModList:More(cfg, "CritMultiplier")
            lines[#lines+1] = "CRITMULTI_MORE|CritMultiplier|" .. tostring(cmM) .. "|" .. tabStr("MORE", "CritMultiplier")
        end

        -- === 7. Lucky ===
        for _, dt in ipairs(activeDT) do
            local lc = 0
            if skillModList:Flag(cfg, "LuckyHits")
            or skillModList:Flag(cfg, "ElementalLuckHits")
            or skillModList:Flag(cfg, "CritLucky") then
                lc = 100
            else
                lc = skillModList:Sum("BASE", cfg, dt.."LuckyHitsChance", "LuckyHitsChance")
            end
            if lc > 0 then
                lines[#lines+1] = "LUCKY|" .. dt .. "|" .. tostring(lc) .. "|" .. tabStr("BASE", dt.."LuckyHitsChance", "LuckyHitsChance")
            end
        end

        -- === 8. Conversion & Gain 表 ===
        -- 只输出对当前构筑有实际 DPS 贡献的条目
        -- 判断依据：fromType 有基础伤害（output[fromType.."MinBase"] > 0）
        -- 注意：Self-Gain（如 Cold→Cold 15%）是 POB 支持的机制
        --       calcGainedDamage() 遍历所有 otherType（包括 self），
        --       DamageGainAsCold 等通用 mod 会产生 gainTable[Cold][Cold] > 0
        local isElemental = {Lightning=true, Cold=true, Fire=true}
        if ms.conversionTable and ms.gainTable then
            -- 收集每种 fromType 是否有基础伤害
            local hasBase = {}
            for _, dt in ipairs(dmgTypes) do
                local minB = output[dt.."MinBase"] or 0
                local maxB = output[dt.."MaxBase"] or 0
                hasBase[dt] = (minB > 0 or maxB > 0)
            end
            for _, fromType in ipairs(dmgTypes) do
                if hasBase[fromType] then
                    for _, toType in ipairs(dmgTypes) do
                        -- Conversion: 跳过 self（同类型转换无意义）
                        -- Gain: 允许 self（Cold→Cold self-gain 是真实机制）
                        local convPct = 0
                        local gainPct = 0
                        if fromType ~= toType and ms.conversionTable[fromType] then
                            convPct = (ms.conversionTable[fromType][toType] or 0) * 100
                        end
                        if ms.gainTable[fromType] then
                            gainPct = (ms.gainTable[fromType][toType] or 0) * 100
                        end
                        if convPct > 0.01 or gainPct > 0.01 then
                            -- Gain mod 来源 Tabulate
                            local gainTab = ""
                            if gainPct > 0.01 then
                                -- 通用 Gain mods（对所有 fromType→toType 都生效，包括 self-gain）
                                local gainMods = {
                                    "DamageAs"..toType,
                                    "DamageGainAs"..toType,
                                }
                                -- 特定类型 Gain mods（仅 fromType != toType 时有意义）
                                if fromType ~= toType then
                                    gainMods[#gainMods+1] = fromType.."DamageAs"..toType
                                    gainMods[#gainMods+1] = fromType.."DamageGainAs"..toType
                                end
                                if isElemental[fromType] then
                                    gainMods[#gainMods+1] = "ElementalDamageAs"..toType
                                    gainMods[#gainMods+1] = "ElementalDamageGainAs"..toType
                                end
                                if fromType ~= "Chaos" then
                                    gainMods[#gainMods+1] = "NonChaosDamageAs"..toType
                                    gainMods[#gainMods+1] = "NonChaosDamageGainAs"..toType
                                end
                                gainTab = tabStr("BASE", table.unpack(gainMods))
                            end
                            local labelSuffix = (fromType == toType) and " (Self-Gain)" or ""
                            lines[#lines+1] = "CONV_GAIN|" .. fromType .. "|" .. toType .. "|"
                                .. string.format("%.2f", convPct) .. "|"
                                .. string.format("%.2f", gainPct) .. "|"
                                .. gainTab
                        end
                    end
                    -- convMult（未转换比例）
                    if ms.conversionTable[fromType] then
                        local convMult = ms.conversionTable[fromType].mult or 1
                        if convMult < 0.999 then
                            lines[#lines+1] = "CONV_MULT|" .. fromType .. "|" .. string.format("%.4f", convMult)
                        end
                    end
                end
            end
        end

        -- === 9. effMult（穿透 / 抗性 / 受伤增加） ===
        -- POB 对每种伤害类型独立计算 takenInc（CalcOffence.lua:3722-3795）:
        --   takenInc = enemyDB:Sum("INC", cfg, "DamageTaken", dt.."DamageTaken")
        --   元素额外加: + enemyDB:Sum("INC", cfg, "ElementalDamageTaken")
        -- 因此不同元素的 takenInc 可能不同（如 Shock 只给 LightningDamageTaken）
        -- 我们的修复：按每种伤害类型独立输出 DamageTaken，不再有"全局共享"

        if enemyDB and env.mode_effective then
            -- 输出敌人异常状态条件（供条件型来源说明使用）
            -- 从 POB 数据动态读取元素异常列表，不再硬编码
            -- data.elementalAilmentTypeList = {"Ignite","Chill","Freeze","Shock"} (POE1 基础)
            -- POE2 新增 Electrocuted，ModParser 中 Yoke 等效果包含它
            -- 合并策略：取 elementalAilmentTypeList + 检测 Electrocuted 条件是否存在于 modDB
            local elemAilList = {}
            if data and data.elementalAilmentTypeList then
                for _, a in ipairs(data.elementalAilmentTypeList) do elemAilList[#elemAilList+1] = a end
            else
                -- POE2 fallback: 包含 Electrocuted（POB 可能不把它放在 elementalAilmentTypeList 中）
                elemAilList = {"Ignite", "Chill", "Freeze", "Shock", "Electrocuted"}
            end
            -- POE2 扩展：Electrocuted 不在 elementalAilmentTypeList 中但属于元素异常
            -- 通过检测 modDB 中是否有 Condition:Electrocuted 定义来判断 POB 是否支持
            local hasElectrocutedSupport = false
            if enemyDB:Flag(nil, "Condition:Electrocuted") or enemyDB:Sum("BASE", nil, "ElectrocuteBuildupAvg") then
                hasElectrocutedSupport = true
            end
            if hasElectrocutedSupport then
                elemAilList[#elemAilList+1] = "Electrocuted"
            end

            local enemyAilments = {}
            local enemyAilmentDetails = {}  -- 存储完整列表（含非活跃）供 Python 端使用
            for _, cond in ipairs(elemAilList) do
                -- elementalAilmentTypeList 用动词形式 (Ignite/Chill/Freeze/Shock)
                -- POB Condition 用形容词/被动形式 (Ignited/Chilled/Frozen/Shocked)
                local condName = cond
                if cond == "Ignite" then condName = "Ignited"
                elseif cond == "Chill" then condName = "Chilled"
                elseif cond == "Freeze" then condName = "Frozen"
                elseif cond == "Shock" then condName = "Shocked"
                end
                enemyAilmentDetails[#enemyAilmentDetails+1] = condName
                if enemyDB:Flag(nil, "Condition:"..condName) then
                    enemyAilments[#enemyAilments+1] = condName
                end
            end
            -- Shock 效果值（当前值和最大值）
            local shockEffect = enemyDB:Sum("BASE", nil, "ShockEffect") or 0
            lines[#lines+1] = "ENEMY_AILMENTS|" .. table.concat(enemyAilments, ",") .. "|" .. tostring(shockEffect) .. "|" .. table.concat(enemyAilmentDetails, ",")

            for _, dt in ipairs(activeDT) do
                local isElem = isElemental[dt]

                -- 9a. 本类型的 takenInc/takenMore（与 POB 一致）
                local takenInc = enemyDB:Sum("INC", cfg, "DamageTaken", dt.."DamageTaken")
                local takenMore = enemyDB:More(cfg, "DamageTaken", dt.."DamageTaken")
                if isElem then
                    takenInc = takenInc + enemyDB:Sum("INC", cfg, "ElementalDamageTaken")
                    takenMore = takenMore * enemyDB:More(cfg, "ElementalDamageTaken")
                end

                local takenMult = (1 + takenInc / 100) * takenMore

                -- 输出本类型的 DamageTaken 乘区
                if takenMult ~= 1 then
                    -- Tabulate INC 来源
                    local dtTabParts = {}
                    local dtBaseTab = enemyDB:Tabulate("INC", cfg, "DamageTaken", dt.."DamageTaken")
                    for _, entry in ipairs(dtBaseTab) do
                        if entry.value ~= 0 then
                            local m = entry.mod
                            -- 提取条件标签（mod[1], mod[2]... 是 tag 列表）
                            local tags = {}
                            local i = 1
                            local maxIter = 20
                            while m[i] and maxIter > 0 do
                                local t = m[i]
                                if type(t) == "string" and t:find("Condition:") then
                                    tags[#tags+1] = t
                                elseif type(t) == "table" then
                                    if t.type == "Condition" then
                                        tags[#tags+1] = "Cond:"..tostring(t.var or "")
                                    elseif t.type == "ActorCondition" then
                                        tags[#tags+1] = "ActorCond:"..tostring(t.actor or "?")..":"..tostring(t.var or "")
                                    end
                                end
                                i = i + 1
                                maxIter = maxIter - 1
                            end
                            -- 补充从 item.modList 提取的 ActorCondition（Tabulate 解包后丢失）
                            local mSrc = m.source or ""
                            if itemActorConds[mSrc] then
                                for cond in itemActorConds[mSrc]:gmatch("[^,]+") do
                                    tags[#tags+1] = "ActorCond:enemy:"..cond
                                end
                            end
                            local tagStr = #tags > 0 and table.concat(tags, ",") or ""
                            dtTabParts[#dtTabParts+1] = (type(m.name)=="string" and m.name or "?").."\1"..(m.source or "Unknown").."\1"..tostring(entry.value).."\1"..tagStr
                        end
                    end
                    if isElem then
                        local elTab = enemyDB:Tabulate("INC", cfg, "ElementalDamageTaken")
                        for _, entry in ipairs(elTab) do
                            if entry.value ~= 0 then
                                local m = entry.mod
                                local tags = {}
                                local i = 1
                                local maxIter = 20
                                while m[i] and maxIter > 0 do
                                    local t = m[i]
                                    if type(t) == "string" and t:find("Condition:") then
                                        tags[#tags+1] = t
                                    elseif type(t) == "table" then
                                        if t.type == "Condition" then
                                            tags[#tags+1] = "Cond:"..tostring(t.var or "")
                                        elseif t.type == "ActorCondition" then
                                            tags[#tags+1] = "ActorCond:"..tostring(t.actor or "?")..":"..tostring(t.var or "")
                                        end
                                    end
                                    i = i + 1
                                end
                                -- 补充从 item.modList 提取的 ActorCondition
                                local mSrc = m.source or ""
                                if itemActorConds[mSrc] then
                                    for cond in itemActorConds[mSrc]:gmatch("[^,]+") do
                                        tags[#tags+1] = "ActorCond:enemy:"..cond
                                    end
                                end
                                local tagStr = #tags > 0 and table.concat(tags, ",") or ""
                                dtTabParts[#dtTabParts+1] = "ElementalDamageTaken\1"..(m.source or "Unknown").."\1"..tostring(entry.value).."\1"..tagStr
                            end
                        end
                    end
                    -- MORE 来源
                    local dtMoreParts = {}
                    local dtBaseMoreTab = enemyDB:Tabulate("MORE", cfg, "DamageTaken", dt.."DamageTaken")
                    for _, entry in ipairs(dtBaseMoreTab) do
                        if entry.value ~= 0 then
                            local m = entry.mod
                            local tags = {}
                            local i = 1
                            local maxIter = 20
                            while m[i] and maxIter > 0 do
                                local t = m[i]
                                if type(t) == "string" and t:find("Condition:") then
                                    tags[#tags+1] = t
                                elseif type(t) == "table" then
                                    if t.type == "Condition" then
                                        tags[#tags+1] = "Cond:"..tostring(t.var or "")
                                    elseif t.type == "ActorCondition" then
                                        tags[#tags+1] = "ActorCond:"..tostring(t.actor or "?")..":"..tostring(t.var or "")
                                    end
                                end
                                i = i + 1
                            end
                            -- 补充从 item.modList 提取的 ActorCondition
                            local mSrc = m.source or ""
                            if itemActorConds[mSrc] then
                                for cond in itemActorConds[mSrc]:gmatch("[^,]+") do
                                    tags[#tags+1] = "ActorCond:enemy:"..cond
                                end
                            end
                            local tagStr = #tags > 0 and table.concat(tags, ",") or ""
                            dtMoreParts[#dtMoreParts+1] = (type(m.name)=="string" and m.name or "?").."\1"..(m.source or "Unknown").."\1"..tostring(entry.value).."\1"..tagStr
                        end
                    end
                    if isElem then
                        local elMoreTab = enemyDB:Tabulate("MORE", cfg, "ElementalDamageTaken")
                        for _, entry in ipairs(elMoreTab) do
                            if entry.value ~= 0 then
                                local m = entry.mod
                                local tags = {}
                                local i = 1
                                local maxIter = 20
                                while m[i] and maxIter > 0 do
                                    local t = m[i]
                                    if type(t) == "string" and t:find("Condition:") then
                                        tags[#tags+1] = t
                                    elseif type(t) == "table" then
                                        if t.type == "Condition" then
                                            tags[#tags+1] = "Cond:"..tostring(t.var or "")
                                        elseif t.type == "ActorCondition" then
                                            tags[#tags+1] = "ActorCond:"..tostring(t.actor or "?")..":"..tostring(t.var or "")
                                        end
                                    end
                                    i = i + 1
                                end
                                -- 补充从 item.modList 提取的 ActorCondition
                                local mSrc = m.source or ""
                                if itemActorConds[mSrc] then
                                    for cond in itemActorConds[mSrc]:gmatch("[^,]+") do
                                        tags[#tags+1] = "ActorCond:enemy:"..cond
                                    end
                                end
                                local tagStr = #tags > 0 and table.concat(tags, ",") or ""
                                dtMoreParts[#dtMoreParts+1] = "ElementalDamageTaken\1"..(m.source or "Unknown").."\1"..tostring(entry.value).."\1"..tagStr
                            end
                        end
                    end

                    -- 格式: ENEMY_TAKEN_DT|dt|takenInc|takenMore|takenMult|incTab|moreTab
                    lines[#lines+1] = "ENEMY_TAKEN_DT|" .. dt .. "|"
                        .. string.format("%.1f", takenInc) .. "|"
                        .. string.format("%.6f", takenMore) .. "|"
                        .. string.format("%.6f", takenMult) .. "|"
                        .. table.concat(dtTabParts, "\2") .. "|"
                        .. table.concat(dtMoreParts, "\2")
                end

                -- 9b. 本类型的抗性/穿透乘区（EffMult = takenMult × resistMult）
                local resist = 0
                local pen = 0
                if isElem then
                    pen = skillModList:Sum("BASE", cfg, dt.."Penetration", "ElementalPenetration")
                elseif dt == "Chaos" then
                    pen = skillModList:Sum("BASE", cfg, "ChaosPenetration")
                end
                if dt == "Physical" then
                    resist = enemyDB:Sum("BASE", nil, "PhysicalDamageReduction")
                else
                    resist = enemyDB:Sum("BASE", nil, dt.."Resist")
                end
                local effectiveResist = resist > 0 and math.max(resist - pen, 0) or resist
                -- effMult: 抗性/穿透对伤害的影响
                -- 有效抗性 > 0 时，伤害被减免为 (1 - effectiveResist/100)
                -- 有效抗性 < 0 时（如诅咒减抗超过抗性），伤害增加为 (1 - effectiveResist/100)
                local effMult = 1 - effectiveResist / 100
                -- takenMult 已在 Enemy_Taken 区域单独处理，不应混入 effMult
                if math.abs(effMult) > 0.001 or pen > 0 then
                    -- 格式: EFF_MULT|dt|effMult|resist|pen|takenMult
                    lines[#lines+1] = "EFF_MULT|" .. dt .. "|"
                        .. string.format("%.6f", effMult) .. "|"
                        .. string.format("%.1f", resist) .. "|"
                        .. string.format("%.1f", pen) .. "|"
                        .. string.format("%.6f", takenMult)
                end
            end
        end

        -- === 9.5. DoT DPS 拆解（Ignite/Bleed/Poison） ===
        -- 从 globalOutput 读取 DoT DPS，逐 ailment 拆解关键乘区
        -- 公式: ailmentDPS = baseVal × effectMod × rateMod × activeAilments × effMult
        do
            local dotAilments = {"Ignite", "Bleed", "Poison"}
            for _, ailment in ipairs(dotAilments) do
                local ailDPS = output[ailment .. "DPS"] or 0
                if ailDPS > 0 then
                    local ailCfg = ms[ailment:lower() .. "Cfg"]

                    -- 基础伤害（Min/Max）
                    local ailMin = output[ailment .. "FireMin"] or output[ailment .. "PhysicalMin"] or output[ailment .. "ChaosMin"] or 0
                    local ailMax = output[ailment .. "FireMax"] or output[ailment .. "PhysicalMax"] or output[ailment .. "ChaosMax"] or 0

                    -- 点燃效果 mod
                    local effectMod = output[ailment .. "MagnitudeEffect"] or 1

                    -- 速率 mod (Faster/Slower)
                    local rateMod = 1
                    if ailCfg then
                        rateMod = (calcLib.mod(skillModList, ailCfg, ailment .. "Faster") + enemyDB:Sum("INC", nil, "Self" .. ailment .. "Faster") / 100) / calcLib.mod(skillModList, ailCfg, ailment .. "Slower")
                    end

                    -- 活跃层数
                    local activeAilments = math.min(output[ailment .. "StackPotential"] or 1, output[ailment .. "StacksMax"] or 1)

                    -- effMult（抗性×受伤增加）
                    local effMult = output[ailment .. "EffMult"] or 1

                    -- 持续时间
                    local duration = output[ailment .. "Duration"] or 0

                    -- 几率
                    local chance = output[ailment .. "ChancePerHit"] or 0

                    -- Tabulate 点燃效果的 INC/MORE 来源（如果有 ailCfg）
                    local effectIncTab = ""
                    local effectMoreTab = ""
                    if ailCfg then
                        local eInc = skillModList:Tabulate("INC", ailCfg, "AilmentMagnitude")
                        local eParts = {}
                        for _, entry in ipairs(eInc) do
                            if entry.value ~= 0 then
                                local m = entry.mod
                                eParts[#eParts+1] = (type(m.name)=="string" and m.name or "?").."\1"..(m.source or "Unknown").."\1"..tostring(entry.value)
                            end
                        end
                        effectIncTab = table.concat(eParts, "\2")

                        local eMore = skillModList:Tabulate("MORE", ailCfg, "AilmentMagnitude")
                        local eMParts = {}
                        for _, entry in ipairs(eMore) do
                            if entry.value ~= 0 then
                                local m = entry.mod
                                eMParts[#eMParts+1] = (type(m.name)=="string" and m.name or "?").."\1"..(m.source or "Unknown").."\1"..tostring(entry.value)
                            end
                        end
                        effectMoreTab = table.concat(eMParts, "\2")
                    end

                    -- Tabulate DoT INC/MORE 来源（DotDamage、AilmentDamage 等）
                    local dotIncTab = ""
                    local dotMoreTab = ""
                    if ailCfg then
                        local dInc = skillModList:Tabulate("INC", ailCfg, "Damage")
                        local dParts = {}
                        for _, entry in ipairs(dInc) do
                            if entry.value ~= 0 then
                                local m = entry.mod
                                dParts[#dParts+1] = (type(m.name)=="string" and m.name or "?").."\1"..(m.source or "Unknown").."\1"..tostring(entry.value)
                            end
                        end
                        dotIncTab = table.concat(dParts, "\2")

                        local dMore = skillModList:Tabulate("MORE", ailCfg, "Damage")
                        local dMParts = {}
                        for _, entry in ipairs(dMore) do
                            if entry.value ~= 0 then
                                local m = entry.mod
                                dMParts[#dMParts+1] = (type(m.name)=="string" and m.name or "?").."\1"..(m.source or "Unknown").."\1"..tostring(entry.value)
                            end
                        end
                        dotMoreTab = table.concat(dMParts, "\2")
                    end

                    lines[#lines+1] = "DOT_BREAKDOWN|" .. ailment .. "|"
                        .. string.format("%.1f", ailDPS) .. "|"
                        .. string.format("%.1f", ailMin) .. "|"
                        .. string.format("%.1f", ailMax) .. "|"
                        .. string.format("%.6f", effectMod) .. "|"
                        .. string.format("%.6f", rateMod) .. "|"
                        .. string.format("%.2f", activeAilments) .. "|"
                        .. string.format("%.6f", effMult) .. "|"
                        .. string.format("%.2f", duration) .. "|"
                        .. string.format("%.1f", chance) .. "|"
                        .. effectIncTab .. "|"
                        .. effectMoreTab .. "|"
                        .. dotIncTab .. "|"
                        .. dotMoreTab
                end
            end
        end

        -- === 10. Double/Triple Damage ===
        local doubleDmgChance = output.DoubleDamageChance or 0
        local tripleDmgChance = output.TripleDamageChance or 0
        local scaledDmgEffect = output.ScaledDamageEffect or 1
        if scaledDmgEffect ~= 1 or doubleDmgChance > 0 or tripleDmgChance > 0 then
            lines[#lines+1] = "DOUBLE_TRIPLE|"
                .. string.format("%.1f", doubleDmgChance) .. "|"
                .. string.format("%.1f", tripleDmgChance) .. "|"
                .. string.format("%.6f", scaledDmgEffect)
        end

        -- === 11. HitChance ===
        local hitChance = output.HitChance or 100
        if hitChance < 100 then
            local accHitChance = output.AccuracyHitChance or 100
            local enemyBlock = output.enemyBlockChance or 0
            lines[#lines+1] = "HITCHANCE|"
                .. string.format("%.2f", hitChance) .. "|"
                .. string.format("%.2f", accHitChance) .. "|"
                .. string.format("%.2f", enemyBlock)
        end

        -- === 12. DPS Multiplier ===
        local dpsMultiplier = ms.skillData and ms.skillData.dpsMultiplier or 1
        if dpsMultiplier ~= 1 then
            lines[#lines+1] = "DPS_MULT|" .. string.format("%.4f", dpsMultiplier)
        end

        -- === 13. CombinedDPS 构成 ===
        do
            local globalOutput = env.player.output
            local totalDPS = globalOutput.TotalDPS or 0
            local totalDotDPS = globalOutput.TotalDotDPS or 0
            local impaleDPS = globalOutput.ImpaleDPS or 0
            local mirageDPS = globalOutput.MirageDPS or 0
            local cullMult = globalOutput.CullMultiplier or 1
            local resDpsMult = globalOutput.ReservationDpsMultiplier or 1
            local combinedDPS = globalOutput.CombinedDPS or 0
            local bleedDPS = globalOutput.BleedDPS or globalOutput.TotalBleedDPS or 0
            local poisonDPS = globalOutput.PoisonDPS or globalOutput.TotalPoisonDPS or 0
            local igniteDPS = globalOutput.IgniteDPS or globalOutput.TotalIgniteDPS or 0
            if combinedDPS > totalDPS or totalDotDPS > 0 or impaleDPS > 0 or cullMult > 1 then
                lines[#lines+1] = "COMBINED_DPS|"
                    .. string.format("%.1f", totalDPS) .. "|"
                    .. string.format("%.1f", totalDotDPS) .. "|"
                    .. string.format("%.1f", impaleDPS) .. "|"
                    .. string.format("%.1f", mirageDPS) .. "|"
                    .. string.format("%.6f", cullMult) .. "|"
                    .. string.format("%.6f", resDpsMult) .. "|"
                    .. string.format("%.1f", combinedDPS) .. "|"
                    .. string.format("%.1f", bleedDPS) .. "|"
                    .. string.format("%.1f", poisonDPS) .. "|"
                    .. string.format("%.1f", igniteDPS)
            end
        end

        return table.concat(lines, "\n")
    '''

    result = lua.execute(lua_script)

    # 获取天赋节点名称映射（用于 DoT 拆解的天赋来源可读化）
    node_names = {}
    try:
        nn_result = lua.execute('''
            local build = _spike_build
            local ns = {}
            if build and build.spec then
                for id, node in pairs(build.spec.allocNodes or {}) do
                    ns[tostring(id)] = node.dn or ("Node "..tostring(id))
                end
                if build.spec.tree and build.spec.tree.nodes then
                    for id, node in pairs(build.spec.tree.nodes) do
                        if not ns[tostring(id)] then
                            ns[tostring(id)] = node.dn or ("Node "..tostring(id))
                        end
                    end
                end
            end
            local parts = {}
            for k, v in pairs(ns) do parts[#parts+1] = k.."="..v end
            return table.concat(parts, "\\1")
        ''')
        if nn_result:
            for part in str(nn_result).split('\1'):
                eq = part.find('=')
                if eq > 0:
                    node_names[part[:eq]] = part[eq+1:]
    except Exception:
        pass

    active_types = []
    jewel_node_ids = set()  # 珠宝槽位节点 ID 集合
    formula_items = []
    _conv_mult_data = {}  # fromType → convMult（未转换比例）

    if not result:
        return _empty_breakdown(baseline)

    # 速度构成元数据（由 SPEED_META 行填充）
    speed_meta = {"is_trigger": False, "final_speed": 0, "action_speed": 1,
                  "base_cast_time": 0, "cooldown": 0}

    raw = str(result).replace('\r', '')
    for line in raw.split('\n'):
        if not line.strip():
            continue

        # 先用 maxsplit=1 取 section，再按 section 类型决定分割策略
        section = line.split('|', 1)[0]

        if section == "META":
            parts = line.split('|')
            if len(parts) > 2:
                if parts[1] == "active_types":
                    active_types = [t.strip() for t in parts[2].split(',') if t.strip()]
                elif parts[1] == "jewel_nodes":
                    jewel_node_ids = {nid.strip() for nid in parts[2].split(',') if nid.strip()}

        elif section == "BASE_DMG":
            # 格式: BASE_DMG|type|totalMin|totalMax|gemMin|gemMax|addedMult|baseMult|addedMinTab|addedMaxTab
            # addedMaxTab（最后一个字段）可能含 |，用 maxsplit=9 保护
            parts = line.split('|', 9)
            _parse_base_damage(parts, formula_items, jewel_node_ids)

        elif section == "SPEED_BASE":
            # 格式: SPEED_BASE|Speed|baseSpeed|label
            parts = line.split('|', 3)
            _parse_speed_base(parts, formula_items)

        elif section == "SPEED_META":
            # 格式: SPEED_META|isTrigger|finalSpeed|actionSpeedMod|baseCastTime|cooldown
            meta_parts = line.split('|')
            if len(meta_parts) >= 6:
                speed_meta["is_trigger"] = meta_parts[1] == "true"
                try:
                    speed_meta["final_speed"] = float(meta_parts[2])
                except ValueError:
                    pass
                try:
                    speed_meta["action_speed"] = float(meta_parts[3])
                except ValueError:
                    pass
                try:
                    speed_meta["base_cast_time"] = float(meta_parts[4])
                except ValueError:
                    pass
                try:
                    speed_meta["cooldown"] = float(meta_parts[5])
                except ValueError:
                    pass

        elif section in ("DMG_INC_BY_MOD", "DMG_MORE_BY_MOD",
                         "SPEED_INC", "SPEED_MORE",
                         "CRIT_INC", "CRIT_MORE",
                         "CRITMULTI_BASE", "CRITMULTI_INC", "CRITMULTI_MORE",
                         "LUCKY"):
            if section in ("DMG_INC_BY_MOD", "DMG_MORE_BY_MOD"):
                # 新格式: SECTION|modName|total|affects|entries
                parts = line.split('|', 4)
                mod_name = parts[1] if len(parts) > 1 else "?"
                affects = parts[3] if len(parts) > 3 else ""
                # 将 affects 列入 formula_name 显示
                affects_label = f" ({affects})" if affects else ""
                # 人类可读名称映射
                mod_display = {
                    "Damage": "通用伤害",
                    "ElementalDamage": "元素伤害",
                    "PhysicalDamage": "物理伤害",
                    "LightningDamage": "闪电伤害",
                    "ColdDamage": "冰霜伤害",
                    "FireDamage": "火焰伤害",
                    "ChaosDamage": "混沌伤害",
                }.get(mod_name, mod_name)
                if section == "DMG_INC_BY_MOD":
                    # 将 affects 和 tabEntries 打包为标准格式
                    # 构造与 _parse_tabulate_item 兼容的 parts
                    std_parts = [section, mod_name,
                                 parts[2] if len(parts) > 2 else "0",
                                 parts[4] if len(parts) > 4 else ""]
                    _parse_tabulate_item(std_parts, "INC", formula_items,
                                         f"{mod_display} INC{affects_label}",
                                         f"{mod_name}_INC",
                                         jewel_node_ids)
                else:
                    std_parts = [section, mod_name,
                                 parts[2] if len(parts) > 2 else "1",
                                 parts[4] if len(parts) > 4 else ""]
                    _parse_tabulate_item(std_parts, "MORE", formula_items,
                                         f"{mod_display} MORE{affects_label}",
                                         f"{mod_name}_MORE",
                                         jewel_node_ids)
            else:
                # 标准格式: SECTION|subkey|total_value|entries
                # entries（最后一个字段）可能含 |，用 maxsplit=3 保护
                parts = line.split('|', 3)
                dt = parts[1] if len(parts) > 1 else "?"

                if section == "SPEED_INC":
                    _parse_tabulate_item(parts, "INC", formula_items,
                                         "Speed INC", "Speed_INC",
                                         jewel_node_ids)
                elif section == "SPEED_MORE":
                    _parse_tabulate_item(parts, "MORE", formula_items,
                                         "Speed MORE", "Speed_MORE",
                                         jewel_node_ids)
                elif section == "CRIT_INC":
                    _parse_tabulate_item(parts, "INC", formula_items,
                                         "CritChance INC", "CritChance_INC",
                                         jewel_node_ids)
                elif section == "CRIT_MORE":
                    _parse_tabulate_item(parts, "MORE", formula_items,
                                         "CritChance MORE", "CritChance_MORE",
                                         jewel_node_ids)
                elif section == "CRITMULTI_BASE":
                    _parse_tabulate_item(parts, "BASE", formula_items,
                                         "CritMultiplier BASE", "CritMultiplier_BASE",
                                         jewel_node_ids)
                elif section == "CRITMULTI_INC":
                    _parse_tabulate_item(parts, "INC", formula_items,
                                         "CritMultiplier INC", "CritMultiplier_INC",
                                         jewel_node_ids)
                elif section == "CRITMULTI_MORE":
                    _parse_tabulate_item(parts, "MORE", formula_items,
                                         "CritMultiplier MORE", "CritMultiplier_MORE",
                                         jewel_node_ids)
                elif section == "LUCKY":
                    _parse_tabulate_item(parts, "BASE", formula_items,
                                         f"{dt} Lucky Hits", f"{dt}_Lucky",
                                         jewel_node_ids)

        elif section == "CRIT_BASE":
            # 格式: CRIT_BASE|CritChance|ccB|baseCrit|actualCC|ccI|ccM|tabEntries
            # tabEntries 可能含 |，用 maxsplit=7 保护
            parts = line.split('|', 7)
            _parse_crit_base(parts, formula_items, jewel_node_ids)

        elif section == "CONV_GAIN":
            # 格式: CONV_GAIN|fromType|toType|convPct|gainPct|gainTab
            parts = line.split('|', 5)
            _parse_conv_gain(parts, formula_items, jewel_node_ids)

        elif section == "CONV_MULT":
            # 格式: CONV_MULT|fromType|convMult
            # 存储为元信息，不作为 formula_item
            parts = line.split('|')
            if len(parts) >= 3:
                _conv_mult_data[parts[1]] = float(parts[2])

        elif section == "EFF_MULT":
            # 格式: EFF_MULT|dt|effMult|resist|pen|takenMult
            parts = line.split('|')
            _parse_eff_mult(parts, formula_items)

        elif section == "ENEMY_AILMENTS":
            # 格式: ENEMY_AILMENTS|active_ailments_csv|shockEffect|all_elem_ailments_csv
            _parse_enemy_ailments(line, formula_items)

        elif section == "ENEMY_TAKEN_DT":
            # 格式: ENEMY_TAKEN_DT|dt|takenInc|takenMore|takenMult|incTab|moreTab
            parts = line.split('|', 6)
            _parse_enemy_taken_dt(parts, formula_items)

        elif section == "ENEMY_TAKEN":
            # 格式: ENEMY_TAKEN|takenMult|takenInc|takenMore|dtIncTab|dtMoreTab
            parts = line.split('|', 5)
            _parse_enemy_taken(parts, formula_items)

        elif section == "DOUBLE_TRIPLE":
            # 格式: DOUBLE_TRIPLE|doublePct|triplePct|scaledEffect
            parts = line.split('|')
            _parse_double_triple(parts, formula_items)

        elif section == "HITCHANCE":
            # 格式: HITCHANCE|hitChance|accHitChance|enemyBlock
            parts = line.split('|')
            _parse_hitchance(parts, formula_items)

        elif section == "DPS_MULT":
            # 格式: DPS_MULT|multiplier
            parts = line.split('|')
            _parse_dps_mult(parts, formula_items)

        elif section == "DOT_BREAKDOWN":
            # 格式: DOT_BREAKDOWN|ailment|dps|min|max|effectMod|rateMod|activeAilments|effMult|duration|chance|effectIncTab|effectMoreTab|dotIncTab|dotMoreTab
            parts = line.split('|', 14)
            _parse_dot_breakdown(parts, formula_items, jewel_node_ids, node_names)

        elif section == "COMBINED_DPS":
            # 格式: COMBINED_DPS|totalDPS|dotDPS|impaleDPS|mirageDPS|cullMult|resDpsMult|combinedDPS|bleedDPS|poisonDPS|igniteDPS
            parts = line.split('|')
            _parse_combined_dps(parts, formula_items)

    # 过滤掉没有来源的非 base-damage 空项（保留临时上下文条目）
    formula_items = [fi for fi in formula_items
                     if fi.get("key","").startswith("_") or fi.get("_is_base") or fi.get("_no_sources_ok") or fi.get("sources")]
    # 清理内部标记和临时上下文
    for fi in formula_items:
        fi.pop("_is_base", None)
        fi.pop("_no_sources_ok", None)
    # === 后处理：合并敌人乘区 ===（清理 _ENEMY_AILMENTS_CTX 在最后）
    damage_composition = _extract_damage_composition(baseline)
    _merge_enemy_taken_entries(formula_items)
    eff_mult_weighted = _compute_weighted_eff_mult(formula_items, damage_composition)

    # 清理临时上下文（合并完成后再删除）
    formula_items[:] = [fi for fi in formula_items if fi.get("key") != "_ENEMY_AILMENTS_CTX"]

    # === 计算 DPS 乘区流程（供报告渲染使用） ===
    flow_stages = _compute_dps_flow_stages(formula_items, baseline, speed_meta)

    # === 一致性断言：检测"手动重算 POB 已计算值"反模式 ===
    # 如果 dps_breakdown 输出的 crit_chance/crit_multiplier/speed 与 baseline 不一致，
    # 说明有人修改了代码绕过了"直接读 POB 输出"的原则
    _assert_pob_output_consistency(formula_items, baseline)

    return {
        "total_dps": baseline.get("TotalDPS", 0),
        "average_hit": baseline.get("AverageHit", 0),
        "speed": baseline.get("Speed", 0),
        "crit_chance": baseline.get("CritChance", 0),
        "crit_multiplier": baseline.get("CritMultiplier", 1),
        "combined_dps": baseline.get("CombinedDPS", 0),
        "active_damage_types": active_types,
        "formula_items": formula_items,
        "dps_flow_stages": flow_stages,
        "damage_composition": damage_composition,
        "eff_mult_weighted": eff_mult_weighted,
    }


def _compute_dps_flow_stages(formula_items: list, baseline: dict,
                             speed_meta: dict = None) -> list:
    """从 formula_items 生成展示用的 DPS 乘区分组。

    注意：不手动推导最终 DPS，而是展示各乘区的数值贡献。
    最终 DPS 以 POB 输出的 TotalDPS 为准。
    """
    from collections import OrderedDict

    def _items_by_suffix(suffixes: list) -> list:
        return [it for it in formula_items
                if any(it["key"].endswith(s) for s in suffixes)
                and it["total_value"] > 0]

    base_avg = baseline.get("AverageHit", 0)
    spd = baseline.get("Speed", 0) or 1
    total_dps = baseline.get("TotalDPS", 0)

    # 1) 伤害 INC — 排除 Crit*/Speed* 开头
    dmg_inc = [it for it in _items_by_suffix(["_INC"])
               if not it["key"].startswith("Crit") and not it["key"].startswith("Speed")]
    inc_pct = sum(it["total_value"] for it in dmg_inc)

    # 2) 伤害 MORE — 排除 Crit 开头
    more = [it for it in _items_by_suffix(["_MORE"])
            if not it["key"].startswith("Crit")]
    # MORE 是乘法：total_value 是乘数（如 1.56），显示为百分比 +56%
    more_total = 1.0
    for it in more:
        more_total *= it["total_value"]
    # 转换为百分比：1.56 → 56%
    more_pct = (more_total - 1) * 100

    # 3) 施法速度
    speed_items = [it for it in formula_items if it["key"].startswith("Speed")]

    # 4) 暴击
    crit_keys = {"CritChance_BASE", "CritChance_INC", "CritChance_MORE",
                 "CritMultiplier_BASE", "CritMultiplier_INC"}
    crit = [it for it in formula_items if it["key"] in crit_keys]

    # 暴击率和暴击倍率直接从 POB output 读取
    # 不手动计算——POB 内部有大量修正（AccuracyHitChance、CritChanceLucky、
    # enemyDB:SelfCritChance、CritChanceBase override 等），手动推导永远不完整
    cc = baseline.get("CritChance", 0) / 100
    cm = baseline.get("CritMultiplier", 1)
    # 暴击效应 = 1 - cc + cc × cm（非暴击概率 × 1 + 暴击概率 × 暴击倍率）
    crit_eff = 1 - cc + cc * cm

    # 5) Lucky（每种元素独立的 Lucky 概率，影响该元素伤害期望）
    lucky = _items_by_suffix(["_Lucky"]) + [it for it in formula_items if it["key"] == "LuckyHits"]
    # Lucky 不是加法汇总——每个元素的 Lucky 独立提升该元素的伤害期望
    lucky_count = len([it for it in lucky if it["total_value"] > 0])
    lucky_per_elem = lucky[0]["total_value"] if lucky else 0

    # 6) 伤害转换/自增益
    conv = [it for it in formula_items
            if "ConvGain" in it["key"] or "SelfGain" in it["key"]]

    # 7) 敌人乘区（DamageTaken + EffMult）
    dt_taken = [it for it in formula_items if it["key"].endswith("_DamageTaken_mult")
                 and it["key"].startswith("Enemy_")]
    eff = [it for it in formula_items if it["key"] == "EffMult_weighted" or it["key"].endswith("_EffMult")]

    # 构建阶段列表（AvgHit 组成展示 + 唯一乘区 Speed）
    # 注意：AvgHit 已包含 INC/MORE/Crit/Lucky/Conversion/EffMult 的全部效果
    # 唯一的正确推导: TotalDPS = AvgHit × Speed
    stages = []
    def _add(label, formula, factor_str, color, detail):
        stages.append(OrderedDict([
            ("label", label), ("formula", formula), ("factor", factor_str),
            ("color", color), ("detail_items", detail),
        ]))

    _add("AvgHit (POB)", f"{base_avg:,.0f}",
         "已含全部 INC/MORE/Crit", "#d4a843", [])
    _add("伤害 INC", f"+{inc_pct:.0f}%  [{len(dmg_inc)}项]",
         "\u5df2\u5185\u542b\u5728 AvgHit \u4e2d", "#55c078", dmg_inc)
    if more:
        _add("伤害 MORE", f"+{more_pct:.1f}%",
             "\u5df2\u5185\u542b\u5728 AvgHit \u4e2d", "#5588dd", more)
    _add("暴击效应", f"cc={cc*100:.1f}%  cm={cm:.2f}×  效应={crit_eff:.2f}×",
         "已内含在 AvgHit 中", "#e05555", crit)
    if lucky:
        _add("Lucky Hits",
             f"{lucky_count}种元素 各{lucky_per_elem:.0f}%概率(投两次取高→提升伤害期望)",
             "已内含在 AvgHit 中", "#cc5599", lucky)
    if conv:
        _add("伤害转换/自增益",
         ", ".join(f"{it['formula_name']} +{it['total_value']:.0f}%" for it in conv),
         "已内含在 AvgHit 中", "#dd8844", conv)
    if dt_taken:
        _add("敌人受伤增加",
         ", ".join(f"{it['formula_name']}: ×{it['total_value']:.2f}" for it in dt_taken),
         "已内含在 AvgHit 中", "#ff7744", dt_taken)
    if eff:
        _add("敌人抗性/穿透",
         ", ".join(f"{it['formula_name']}: +{it['total_value']:.1f}%" for it in eff),
         "已内含在 AvgHit 中", "#e05555", eff)

    # 8) DoT DPS（Ignite/Bleed/Poison）
    dot_items = [it for it in formula_items if it["key"].endswith("_DPS")
                 and it["key"] in ("Ignite_DPS", "Bleed_DPS", "Poison_DPS")]
    if dot_items:
        dot_labels = ", ".join(
            f"{it['formula_name']}: {it['total_value']:,.0f}" for it in dot_items)
        _add("DoT DPS", dot_labels,
             "POB 独立计算，已加到 CombinedDPS", "#cc66aa", dot_items)

    # Speed 标签和构成说明
    sm = speed_meta or {}
    is_trigger = sm.get("is_trigger", False)
    speed_inc_val = sum(it["total_value"] for it in speed_items if it["key"] == "Speed_INC")
    speed_more_val = 1.0
    for it in speed_items:
        if it["key"] == "Speed_MORE":
            try:
                speed_more_val = float(it["total_value"])
            except (ValueError, TypeError):
                pass
    base_ct = sm.get("base_cast_time", 0)
    cd = sm.get("cooldown", 0)
    trigger_note = " (触发)" if is_trigger else ""
    speed_label = f"施法速度{trigger_note}"

    # 构成公式
    formula_parts = []
    if is_trigger:
        formula_parts.append(f"= {spd:.2f}/s (由触发链路决定)")
        if speed_inc_val:
            formula_parts.append(f"构筑 Speed INC +{speed_inc_val:.0f}% (已内含)")
        if cd > 0:
            formula_parts.append(f"冷却 {cd:.3f}s")
    else:
        if base_ct > 0:
            base_rate = 1 / base_ct
            formula_parts.append(f"基础 1/{base_ct:.2f}s = {base_rate:.2f}/s")
        if speed_inc_val:
            formula_parts.append(f"× (1 + {speed_inc_val:.0f}%)")
        if speed_more_val != 1:
            formula_parts.append(f"× {speed_more_val:.2f}")
        formula_parts.append(f"= {spd:.2f}/s")
    speed_formula = "  ".join(formula_parts)
    _add(speed_label, speed_formula, f"×{spd:.2f}", "#44bbcc", speed_items)
    _add("Total DPS", f"{base_avg:,.0f} × {spd:.2f} = {total_dps:,.0f}",
         "POB 实际输出", "#d4a843", [])

    return stages


def _parse_base_damage(parts: list, formula_items: list,
                       jewel_node_ids: set = None):
    """解析 BASE_DMG 行。

    格式: BASE_DMG|type|totalMin|totalMax|gemMin|gemMax|addedMult|baseMult|addedMinTab|addedMaxTab
    """
    if len(parts) < 9:
        return
    try:
        dt = parts[1]
        total_min = float(parts[2])
        total_max = float(parts[3])
        gem_min = float(parts[4])
        gem_max = float(parts[5])
        added_mult = float(parts[6])
        base_mult = float(parts[7])
    except (ValueError, IndexError):
        return

    sources = []

    # 宝石/武器基础
    if gem_min > 0 or gem_max > 0:
        avg = (gem_min + gem_max) / 2
        sources.append({
            "source": "gem",
            "label": "技能基础",
            "category": "Skill",
            "value": avg,
            "mod_name": "gem_base",
            "detail": f"{gem_min:.0f}-{gem_max:.0f}",
        })

    # added damage (Tabulate 结果)
    # parts[8] = addedMinTab, parts[9] = addedMaxTab
    added_min_tab = parts[8] if len(parts) > 8 else ""
    added_max_tab = parts[9] if len(parts) > 9 else ""
    _merge_added_damage_sources(sources, added_min_tab, added_max_tab, jewel_node_ids)

    # 排序
    sources.sort(key=lambda s: abs(s["value"]), reverse=True)

    # category_summary
    cat_sum = {}
    for s in sources:
        cat = s["category"]
        cat_sum[cat] = cat_sum.get(cat, 0.0) + s["value"]

    total_avg = (total_min + total_max) / 2
    if total_avg < 0.01:
        return  # 浮点精度噪声，跳过
    display = f"{total_min:.0f}-{total_max:.0f}"
    if base_mult != 1:
        display += f" (x{base_mult:.2f} base mult)"

    formula_items.append({
        "key": f"{dt}_Base_Damage",
        "formula_name": f"{dt} Base Damage",
        "total_value": total_avg,
        "display_value": display,
        "category_summary": cat_sum,
        "sources": sources,
        "_is_base": True,
    })


def _merge_added_damage_sources(sources: list, min_tab: str, max_tab: str,
                                jewel_node_ids: set = None):
    """合并 Min/Max Tabulate 结果为单条 source（取均值）。

    同一 source 的多条 mod 会累加（如装备同时给 +10 和 +20 flat damage）。
    """
    # 解析 min tab — 同 source 累加
    min_by_source = {}
    if min_tab:
        for entry in min_tab.split('\2'):
            p = entry.split('\1')
            if len(p) >= 4:
                try:
                    val = float(p[2])
                except ValueError:
                    continue
                cond_tag = p[4] if len(p) > 4 else ""
                if p[1] in min_by_source:
                    min_by_source[p[1]]["value"] += val
                else:
                    min_by_source[p[1]] = {
                        "mod_name": p[0], "value": val, "label": p[3], "cond_tag": cond_tag
                    }

    # 解析 max tab — 同 source 累加
    max_by_source = {}
    if max_tab:
        for entry in max_tab.split('\2'):
            p = entry.split('\1')
            if len(p) >= 4:
                try:
                    val = float(p[2])
                except ValueError:
                    continue
                cond_tag = p[4] if len(p) > 4 else ""
                if p[1] in max_by_source:
                    max_by_source[p[1]]["value"] += val
                else:
                    max_by_source[p[1]] = {
                        "mod_name": p[0], "value": val, "label": p[3], "cond_tag": cond_tag
                    }

    # 合并同 source 的 min/max
    all_sources = set(min_by_source.keys()) | set(max_by_source.keys())
    for src in all_sources:
        mi = min_by_source.get(src, {}).get("value", 0)
        mx = max_by_source.get(src, {}).get("value", 0)
        lbl = min_by_source.get(src, max_by_source.get(src, {})).get("label", "")
        mn = min_by_source.get(src, max_by_source.get(src, {})).get("mod_name", "?")
        avg = (mi + mx) / 2
        if avg == 0:
            continue
        sources.append({
            "source": src,
            "label": lbl or _source_label_fallback(src),
            "category": _classify_source(src, jewel_node_ids),
            "value": avg,
            "mod_name": mn,
            "detail": f"+{mi:.0f}-{mx:.0f}",
        })


def _parse_tabulate_item(parts: list, mod_type: str, formula_items: list,
                         formula_name: str, key: str,
                         jewel_node_ids: set = None):
    """解析标准 Tabulate 行。

    格式: SECTION|subkey|total_value|entries
    entries: modName\1source\1value\1label\2modName\1source\1value\1label
    """
    if len(parts) < 3:
        return
    try:
        total_value = float(parts[2])
    except (ValueError, IndexError):
        return

    sources = []
    if len(parts) >= 4 and parts[3]:
        for entry in parts[3].split('\2'):
            p = entry.split('\1')
            if len(p) >= 3:
                try:
                    val = float(p[2])
                except ValueError:
                    continue
                category = _classify_source(p[1], jewel_node_ids)
                label = (_source_label_fallback(p[1]) if category == "Sim"
                         else (p[3] if len(p) > 3 else _source_label_fallback(p[1])))
                # 条件标签（第5字段）：如 "Triggered" 表示仅对触发技能生效
                cond_tag = p[4] if len(p) > 4 else ""
                if cond_tag == "Triggered":
                    category = "Triggered"
                sources.append({
                    "source": p[1],
                    "label": label,
                    "category": category,
                    "value": val,
                    "mod_name": p[0],
                })

    sources.sort(key=lambda s: abs(s["value"]), reverse=True)

    # category_summary
    cat_sum = {}
    for s in sources:
        cat = s["category"]
        if mod_type == "MORE":
            # MORE 是乘法：值是百分比（如 20 = +20% MORE = ×1.20）
            # category 汇总用乘积展示
            if cat not in cat_sum:
                cat_sum[cat] = 1.0
            cat_sum[cat] *= (1 + s["value"] / 100)
        else:
            cat_sum[cat] = cat_sum.get(cat, 0.0) + s["value"]

    # 对于 MORE 类型：
    # total_value 是乘数（如 1.56），value 是百分比（如 20）
    # display 用乘数格式
    actual_total = total_value
    if mod_type == "MORE" and total_value != 1:
        # total_value 是乘数，转换为百分比：1.56 → +56%，0.91 → -9%
        pct = (total_value - 1) * 100
        display = f"{pct:+.1f}%"
    elif mod_type == "INC":
        display = f"{actual_total:.0f}%"
    elif mod_type == "BASE":
        display = f"{actual_total:.0f}"
    else:
        display = f"{actual_total:.1f}"

    formula_items.append({
        "key": key,
        "formula_name": formula_name,
        "total_value": actual_total,  # 使用转换后的值
        "display_value": display,
        "category_summary": cat_sum,
        "sources": sources,
    })


def _parse_crit_base(parts: list, formula_items: list,
                     jewel_node_ids: set = None):
    """解析 CritChance BASE 行（含宝石固有 baseCrit + POB 实际 CC）。

    格式: CRIT_BASE|CritChance|ccB|baseCrit|tabEntries|actualCC|ccI|ccM
    - ccB: skillModList:Sum("BASE", "CritChance") + enemyDB SelfCritChance
    - baseCrit: 基础暴击率（可能含 CritChanceBase override，如升华锁定15%）
    - actualCC: POB output.CritChance（含 AccuracyHitChance/Lucky 等全部修正）
    - ccI: 总 INC（含 enemyDB SelfCritChance）
    - ccM: 总 MORE
    """
    if len(parts) < 4:
        return
    try:
        added_base = float(parts[2])
        gem_base = float(parts[3])
    except (ValueError, IndexError):
        return

    # 新格式: parts[4]=actualCC, parts[5]=ccI, parts[6]=ccM, parts[7]=tabEntries
    actual_cc = 0.0
    cc_inc_total = 0.0
    cc_more_total = 1.0
    try:
        if len(parts) > 4:
            actual_cc = float(parts[4])
        if len(parts) > 5:
            cc_inc_total = float(parts[5])
        if len(parts) > 6:
            cc_more_total = float(parts[6])
    except (ValueError, IndexError):
        pass

    sources = []

    # 基础暴击率（含 override）
    if gem_base > 0:
        sources.append({
            "source": "gem",
            "label": "基础暴击率",
            "category": "Skill",
            "value": gem_base,
            "mod_name": "base_crit",
        })

    # 额外 BASE mod (Tabulate 结果)
    tab_data = parts[7] if len(parts) > 7 else ""
    if tab_data:
        for entry in tab_data.split('\2'):
            p = entry.split('\1')
            if len(p) >= 3:
                try:
                    val = float(p[2])
                except ValueError:
                    continue
                category = _classify_source(p[1], jewel_node_ids)
                label = (_source_label_fallback(p[1]) if category == "Sim"
                         else (p[3] if len(p) > 3 else _source_label_fallback(p[1])))
                sources.append({
                    "source": p[1],
                    "label": label,
                    "category": category,
                    "value": val,
                    "mod_name": p[0],
                })

    sources.sort(key=lambda s: abs(s["value"]), reverse=True)

    cat_sum = {}
    for s in sources:
        cat = s["category"]
        cat_sum[cat] = cat_sum.get(cat, 0.0) + s["value"]

    # total_value 用 POB 的实际 CC（而非手动推算）
    total = actual_cc if actual_cc > 0 else gem_base + added_base
    # 手动推算值（供参考对比）
    manual_cc = (gem_base + added_base) * (1 + cc_inc_total / 100) * cc_more_total
    manual_cc = min(manual_cc, 100)

    # 显示说明
    if actual_cc > 0 and abs(actual_cc - manual_cc) > 0.5:
        # POB 实际值和手动推算有差异——说明有额外修正（Accuracy/Lucky等）
        display = f"{actual_cc:.1f}% (POB实际, 手动推算={manual_cc:.1f}%)"
    else:
        display = f"{total:.1f}% (base {gem_base:.1f}% + added {added_base:.0f}%)"

    formula_items.append({
        "key": "CritChance_BASE",
        "formula_name": "CritChance BASE",
        "total_value": total,
        "display_value": display,
        "category_summary": cat_sum,
        "sources": sources,
    })


def _parse_speed_base(parts: list, formula_items: list):
    """解析 Speed BASE 行（基础攻击/施法速度）。

    格式: SPEED_BASE|Speed|baseSpeed|label
    """
    if len(parts) < 4:
        return
    try:
        base_speed = float(parts[2])
    except (ValueError, IndexError):
        return
    if base_speed <= 0:
        return

    label = parts[3] if len(parts) > 3 else "Base"
    base_speed = round(base_speed, 2)
    sources = [{
        "source": "gem",
        "label": label,
        "category": "Skill",
        "value": base_speed,
        "mod_name": "base_speed",
    }]

    formula_items.append({
        "key": "Speed_BASE",
        "formula_name": "施法速度",
        "total_value": base_speed,
        "display_value": f"{base_speed:.2f}/s",
        "category_summary": {"Skill": base_speed},
        "sources": sources,
    })


def _parse_conv_gain(parts: list, formula_items: list,
                     jewel_node_ids: set = None):
    """解析 CONV_GAIN 行（伤害转换与增益）。

    格式: CONV_GAIN|fromType|toType|convPct|gainPct|gainTab
    """
    if len(parts) < 5:
        return
    try:
        from_type = parts[1]
        to_type = parts[2]
        conv_pct = float(parts[3])
        gain_pct = float(parts[4])
    except (ValueError, IndexError):
        return

    sources = []

    if conv_pct > 0.01:
        sources.append({
            "source": "conversion",
            "label": f"{from_type} → {to_type} 转换",
            "category": "Conversion",
            "value": conv_pct,
            "mod_name": f"{from_type}DamageConvertTo{to_type}",
        })

    if gain_pct > 0.01:
        # 解析 gain mod 来源
        gain_tab = parts[5] if len(parts) > 5 else ""
        if gain_tab:
            for entry in gain_tab.split('\2'):
                p = entry.split('\1')
                if len(p) >= 3:
                    try:
                        val = float(p[2])
                    except ValueError:
                        continue
                    category = _classify_source(p[1], jewel_node_ids)
                    label = (_source_label_fallback(p[1]) if category == "Sim"
                             else (p[3] if len(p) > 3 else _source_label_fallback(p[1])))
                    sources.append({
                        "source": p[1],
                        "label": label,
                        "category": category,
                        "value": val,
                        "mod_name": p[0],
                        "detail": f"Gain as {to_type}",
                    })
        else:
            # 没有详细来源，用总值
            sources.append({
                "source": "gain",
                "label": f"{from_type} → {to_type} 额外获得",
                "category": "Gain",
                "value": gain_pct,
                "mod_name": f"{from_type}DamageGainAs{to_type}",
            })

    if not sources:
        return

    sources.sort(key=lambda s: abs(s["value"]), reverse=True)
    cat_sum = {}
    for s in sources:
        cat = s["category"]
        cat_sum[cat] = cat_sum.get(cat, 0.0) + s["value"]

    total = conv_pct + gain_pct
    display_parts = []
    if conv_pct > 0.01:
        display_parts.append(f"转换 {conv_pct:.1f}%")
    if gain_pct > 0.01:
        display_parts.append(f"增益 {gain_pct:.1f}%")
    if from_type == to_type:
        display = f"{from_type} Self-Gain: {' + '.join(display_parts)}"
    else:
        display = f"{from_type} → {to_type}: {' + '.join(display_parts)}"

    key_suffix = "SelfGain" if from_type == to_type else "ConvGain"
    formula_items.append({
        "key": f"{from_type}_to_{to_type}_{key_suffix}",
        "formula_name": f"{from_type} → {to_type} {'Self-Gain' if from_type == to_type else 'Conversion/Gain'}",
        "total_value": total,
        "display_value": display,
        "category_summary": cat_sum,
        "sources": sources,
        "_no_sources_ok": True,
    })


def _parse_eff_mult(parts: list, formula_items: list):
    """解析 EFF_MULT 行（各伤害类型的抗性/穿透乘区）。

    格式: EFF_MULT|dt|effMult|resist|pen|takenMult
    takenMult 由 ENEMY_TAKEN 行提供，这里只展示抗性/穿透部分。
    """
    if len(parts) < 6:
        return
    try:
        dt = parts[1]
        eff_mult = float(parts[2])
        resist = float(parts[3])
        pen = float(parts[4])
        taken_mult = float(parts[5])
    except (ValueError, IndexError):
        return

    resist_sources = []
    if resist != 0:
        resist_sources.append({
            "source": "enemy",
            "label": f"敌人 {dt} 抗性",
            "category": "Enemy",
            "value": resist,
            "mod_name": f"{dt}Resist",
        })
    if pen != 0:
        resist_sources.append({
            "source": "player",
            "label": f"{dt} 穿透",
            "category": "Penetration",
            "value": pen,
            "mod_name": f"{dt}Penetration",
        })

    effective_resist = max(resist - pen, 0) if resist > 0 else resist

    # 计算穿透/减抗带来的边际增益（相对于原始抗性）
    # 原始抗性下伤害 = (1 - resist/100)，穿透后伤害 = effMult
    # 增益 = effMult / (1 - resist/100) - 1
    base_mult = (1 - resist / 100) if resist >= 0 else (1 - resist / 100)
    if abs(base_mult) > 0.001:
        gain_pct = (eff_mult / base_mult - 1) * 100
    else:
        gain_pct = 0.0

    formula_detail = f"+{gain_pct:.1f}%"
    if effective_resist != 0:
        formula_detail += f"  (抗性 {resist:.0f}% - 穿透 {pen:.0f}% = 有效 {effective_resist:.0f}%)"
    elif resist < 0:
        formula_detail += f"  (敌人负抗性 {resist:.0f}%)"

    cat_sum = {s["category"]: s["value"] for s in resist_sources}

    formula_items.append({
        "key": f"{dt}_EffMult",
        "formula_name": f"{dt} 抗性穿透增益",
        "total_value": gain_pct,
        "display_value": f"+{gain_pct:.1f}%",
        "_eff_mult_abs": eff_mult,  # 保留绝对值供加权计算用
        "_resist": resist,
        "category_summary": cat_sum,
        "sources": resist_sources,
        "_no_sources_ok": True,
        "formula_detail": formula_detail,
    })


def _parse_enemy_taken(parts: list, formula_items: list):
    """解析 ENEMY_TAKEN 行（敌人受伤增加乘区，所有伤害类型共享）。

    格式: ENEMY_TAKEN|takenMult|takenInc|takenMore|dtIncTab|dtMoreTab
    """
    if len(parts) < 4:
        return
    try:
        taken_mult = float(parts[1])
        taken_inc = float(parts[2])
        taken_more = float(parts[3])
    except (ValueError, IndexError):
        return

    # 解析 DamageTaken INC 来源
    dt_inc_tab = parts[4] if len(parts) > 4 else ""
    dt_more_tab = parts[5] if len(parts) > 5 else ""

    taken_sources = []
    if dt_inc_tab:
        for entry in dt_inc_tab.split('\2'):
            p = entry.split('\1')
            if len(p) >= 3:
                try:
                    val = float(p[2])
                except ValueError:
                    continue
                src = p[1]
                mod_name = p[0]
                tags = p[3] if len(p) > 3 else ""
                label = _eff_source_effect_label(mod_name, val, src, "", tags, formula_items)
                taken_sources.append({
                    "source": src,
                    "label": label,
                    "category": _classify_enemy_source(src),
                    "value": val,
                    "mod_name": mod_name,
                    "tags": tags,
                })
    if dt_more_tab:
        for entry in dt_more_tab.split('\2'):
            p = entry.split('\1')
            if len(p) >= 3:
                try:
                    val = float(p[2])
                except ValueError:
                    continue
                src = p[1]
                mod_name = p[0]
                tags = p[3] if len(p) > 3 else ""
                label = _eff_source_effect_label(mod_name, val, src, "", tags, formula_items)
                taken_sources.append({
                    "source": src,
                    "label": label,
                    "category": _classify_enemy_source(src),
                    "value": (val - 1) * 100 if abs(val) > 10 else val,
                    "mod_name": mod_name,
                    "tags": tags,
                })

    if not taken_sources and taken_inc != 0:
        taken_sources.append({
            "source": "enemy",
            "label": "敌人受到伤害增加 (汇总)",
            "category": "Enemy",
            "value": taken_inc,
            "mod_name": "DamageTaken_INC",
        })

    taken_sources.sort(key=lambda s: abs(s["value"]), reverse=True)
    cat_sum = {}
    for s in taken_sources:
        cat = s["category"]
        cat_sum[cat] = cat_sum.get(cat, 0.0) + s["value"]

    formula_items.append({
        "key": "Enemy_DamageTaken_mult",
        "formula_name": "敌人受伤增加 (全元素共享)",
        "total_value": taken_mult,
        "display_value": f"x{taken_mult:.4f}  (INC合计 {taken_inc:+.0f}%, 等效 +{(taken_mult-1)*100:.0f}% MORE)",
        "category_summary": cat_sum,
        "sources": taken_sources,
        "_no_sources_ok": True,
        "formula_detail": f"(1+{taken_inc:.0f}/100) × {taken_more:.4f} = {taken_mult:.4f}  (INC加法合并后乘法生效)",
    })




def _parse_enemy_taken_dt(parts: list, formula_items: list):
    """解析 ENEMY_TAKEN_DT 行（按伤害类型独立的受伤增加乘区）。

    格式: ENEMY_TAKEN_DT|dt|takenInc|takenMore|takenMult|incTab|moreTab

    与旧 ENEMY_TAKEN 不同：每种伤害类型独立输出，因为 POB 对每种类型
    独立查询 takenInc（Shock 只给 LightningDamageTaken，不影响冰霜/火焰）。
    """
    if len(parts) < 5:
        return
    try:
        dt = parts[1]
        taken_inc = float(parts[2])
        taken_more = float(parts[3])
        taken_mult = float(parts[4])
    except (ValueError, IndexError):
        return

    # 解析 INC 来源
    inc_tab = parts[5] if len(parts) > 5 else ""
    more_tab = parts[6] if len(parts) > 6 else ""

    taken_sources = []
    if inc_tab:
        for entry in inc_tab.split('\2'):
            p = entry.split('\1')
            if len(p) >= 3:
                try:
                    val = float(p[2])
                except ValueError:
                    continue
                src = p[1]
                mod_name = p[0]
                tags = p[3] if len(p) > 3 else ""
                label = _eff_source_effect_label(mod_name, val, src, dt, tags, formula_items)
                taken_sources.append({
                    "source": src,
                    "label": label,
                    "category": _classify_enemy_source(src),
                    "value": val,
                    "mod_name": mod_name,
                    "tags": tags,
                })
    if more_tab:
        for entry in more_tab.split('\2'):
            p = entry.split('\1')
            if len(p) >= 3:
                try:
                    val = float(p[2])
                except ValueError:
                    continue
                src = p[1]
                mod_name = p[0]
                tags = p[3] if len(p) > 3 else ""
                label = _eff_source_effect_label(mod_name, val, src, dt, tags, formula_items)
                taken_sources.append({
                    "source": src,
                    "label": label,
                    "category": _classify_enemy_source(src),
                    "value": (val - 1) * 100 if abs(val) > 10 else val,
                    "mod_name": mod_name,
                    "tags": tags,
                })

    if not taken_sources and taken_inc != 0:
        taken_sources.append({
            "source": "enemy",
            "label": f"敌人受到{dt}伤害增加 (汇总)",
            "category": "Enemy",
            "value": taken_inc,
            "mod_name": "DamageTaken_INC",
        })

    taken_sources.sort(key=lambda s: abs(s["value"]), reverse=True)
    cat_sum = {}
    for s in taken_sources:
        cat = s["category"]
        cat_sum[cat] = cat_sum.get(cat, 0.0) + s["value"]

    # 元素类型标签
    dt_names = {"Lightning": "闪电", "Cold": "冰霜", "Fire": "火焰",
                "Physical": "物理", "Chaos": "混沌"}
    dt_label = dt_names.get(dt, dt)

    formula_items.append({
        "key": f"Enemy_{dt}_DamageTaken_mult",
        "formula_name": f"{dt_label}受伤增加",
        "total_value": taken_mult,
        "display_value": f"x{taken_mult:.4f}  (INC合计 {taken_inc:+.0f}%)",
        "category_summary": cat_sum,
        "sources": taken_sources,
        "_no_sources_ok": True,
        "formula_detail": f"(1+{taken_inc:.0f}/100) × {taken_more:.4f} = {taken_mult:.4f}",
    })


def _parse_enemy_ailments(line: str, formula_items: list):
    """解析 ENEMY_AILMENTS 行，存储为全局上下文供条件描述使用。
    
    格式: ENEMY_AILMENTS|active_ailments_csv|shockEffect|all_elem_ailments_csv
    - active_ailments: 当前构筑实际可触发的元素异常（条件已满足）
    - shockEffect: Shock 效果值
    - all_elem_ailments: POB 定义的所有元素异常类型（从 data.elementalAilmentTypeList 动态读取）
    """
    parts = line.split('|')
    if len(parts) < 3:
        return
    ailments_str = parts[1] if len(parts) > 1 else ""
    shock_effect = 0
    try:
        shock_effect = float(parts[2]) if parts[2] else 0
    except ValueError:
        pass
    # 第4个字段：POB 定义的完整元素异常列表（供 max_ailments 计算使用）
    all_elem_ailments = []
    if len(parts) > 3 and parts[3]:
        all_elem_ailments = [a.strip() for a in parts[3].split(',') if a.strip()]
    # 存储到全局上下文（供 _eff_source_effect_label 使用）
    formula_items.append({
        "key": "_ENEMY_AILMENTS_CTX",
        "ailments": [a.strip() for a in ailments_str.split(',') if a.strip()],
        "shock_effect": shock_effect,
        "all_elem_ailments": all_elem_ailments,
    })


def _eff_source_label(source: str, dt: str) -> str:
    """将 enemyDB mod source 转为可读标签。"""
    if not source:
        return "Unknown"
    # "Shock" → "Shock 效果"
    if source == "Shock":
        return "Shock 效果"
    if source == "Chill":
        return "Chill 效果"
    if source == "Freeze":
        return "Freeze 效果"
    # "Item:-1:Yoke of Suffering, Bloodstone Amulet"
    if source.startswith("Item:"):
        parts = source.split(":", 2)
        if len(parts) >= 3:
            return parts[2]
        return source
    # "Config" → "配置"
    if source == "Config":
        return "配置"
    return source


def _get_ailments_ctx(formula_items: list) -> dict:
    """从 formula_items 中提取异常状态上下文。"""
    for fi in formula_items:
        if fi.get("key") == "_ENEMY_AILMENTS_CTX":
            return fi
    return {}


def _parse_actor_condition_tags(tags: str) -> list:
    """从 tags 字符串中提取 ActorCondition 条件名列表。
    
    格式: "ActorCond:enemy:Frozen,ActorCond:enemy:Shocked" → ["Frozen", "Shocked"]
    """
    conditions = []
    if not tags:
        return conditions
    for part in tags.split(','):
        if part.startswith("ActorCond:enemy:"):
            conditions.append(part[len("ActorCond:enemy:"):])
    return conditions


def _eff_source_effect_label(mod_name: str, value: float, source: str, dt: str,
                              tags: str = "", formula_items: list = None) -> str:
    """构建敌人受伤来源的效果描述标签。

    展示效果说明（如 "Yoke: 每种元素异常+24%，当前4种=+96%"、"Shock: 受伤+28%"），
    而非原始词条（如 "DamageTaken +24"）。
    
    通用检测"per elemental ailment"类型效果：
    - 从 mod 的 ActorCondition tag 动态推断（而非硬编码物品名）
    - 如果 mod 带有 ActorCond:enemy:xxx 条件且 xxx 属于元素异常，
      则自动计算"每种元素异常+X%"
    """
    dt_names = {"Lightning": "闪电", "Cold": "冰霜", "Fire": "火焰",
                "Physical": "物理", "Chaos": "混沌"}
    dt_label = dt_names.get(dt, "") if dt else ""

    # 来源名（缩短物品名）
    src_label = _eff_source_label(source, dt)
    if ',' in src_label:
        src_label = src_label.split(',')[0].strip()

    # 获取异常状态上下文
    ctx = _get_ailments_ctx(formula_items) if formula_items else {}
    ailments = ctx.get("ailments", [])
    all_elem_ailments = ctx.get("all_elem_ailments", [])

    # mod_name 判断效果类型
    is_elemental = mod_name == "ElementalDamageTaken"

    # Shock 效果
    if source == "Shock":
        eff_pct = abs(value)
        if eff_pct >= 100:
            range_info = "（最大值）"
        elif eff_pct <= 20:
            range_info = "（最小值）"
        else:
            range_info = ""
        return f"Shock: 受伤+{eff_pct:.0f}%{range_info}"

    # 通用检测："per elemental ailment" 类型效果
    # 通过 ActorCondition tag 动态判断，不硬编码物品名
    actor_conds = _parse_actor_condition_tags(tags)
    # 筛选出属于元素异常的 ActorCondition
    elem_ailment_conds = [c for c in actor_conds if c in all_elem_ailments] if all_elem_ailments else []
    if elem_ailment_conds:
        # 这是"每种元素异常+X%"类型的 mod
        n_covered = len(elem_ailment_conds)
        active_ailments = [a for a in ailments if a in all_elem_ailments]
        n_active = len(active_ailments)
        max_ailments = len(all_elem_ailments)
        per = abs(value) / n_covered  # 每种异常的单值
        
        if n_covered > 1:
            # 合并后的多条目：展示"每种元素异常+X%，当前N种=+Y%"
            current = per * n_active
            maximum = per * max_ailments
            if n_active > 0:
                if n_active >= max_ailments:
                    return f"{src_label}: 每种元素异常+{per:.0f}%，{n_active}种=+{current:.0f}%（已达上限）"
                return (f"{src_label}: 每种元素异常+{per:.0f}%，"
                        f"当前{n_active}种=+{current:.0f}%（最多{max_ailments}种=+{maximum:.0f}%）")
            return f"{src_label}: 元素异常受伤+{abs(value):.0f}%"
        else:
            # 单条目（未合并）：只展示该条件的贡献值和 per-value 信息
            cond_name = elem_ailment_conds[0]
            cond_names = {"Frozen": "冰冻", "Chilled": "冰缓", "Ignited": "点燃",
                          "Shocked": "感电", "Electrocuted": "电刑",
                          "Scorched": "灼烧", "Brittle": "脆弱", "Sapped": "枯萎"}
            cond_cn = cond_names.get(cond_name, cond_name)
            if n_active > 0:
                return f"{src_label}: {cond_cn}异常受伤+{per:.0f}%（共{n_active}种异常=+{per*n_active:.0f}%）"
            return f"{src_label}: {cond_cn}异常受伤+{abs(value):.0f}%"

    if is_elemental:
        effect_desc = f"元素受伤+{abs(value):.0f}%"
    else:
        if dt_label:
            effect_desc = f"{dt_label}受伤+{abs(value):.0f}%"
        else:
            effect_desc = f"受伤+{abs(value):.0f}%"

    return f"{src_label}: {effect_desc}"


def _classify_enemy_source(source: str) -> str:
    """将 enemyDB mod source 分类。"""
    if not source:
        return "Other"
    if source in ("Shock", "Chill", "Freeze", "Ignite"):
        return "Ailment"
    if source.startswith("Item:"):
        return "Item"
    if source == "Config":
        return "Config"
    return "Other"


def _merge_enemy_taken_entries(formula_items: list):
    """合并相同 takenMult 的按元素展开的受伤增加条目。

    当所有活跃伤害类型的 takenMult 相同时（如通用 ElementalDamageTaken 效果），
    合并为单一条目，避免重复展示。若不同类型有不同 takenMult（如 Shock 仅影响闪电），
    则保留分开的条目。
    """
    _DT_NAMES = {"Lightning": "闪电", "Cold": "冰霜", "Fire": "火焰",
                 "Physical": "物理", "Chaos": "混沌"}

    dt_entries = {}
    for fi in formula_items:
        key = fi["key"]
        if key.startswith("Enemy_") and key.endswith("_DamageTaken_mult"):
            dt = key[len("Enemy_"):-len("_DamageTaken_mult")]
            if dt in _DT_NAMES:
                dt_entries[dt] = fi

    if len(dt_entries) < 2:
        return

    values = [fi["total_value"] for fi in dt_entries.values()]
    if max(values) - min(values) > 0.001:
        return

    merged_value = values[0]

    # 按 source+mod_name 合并来源，累加 value
    # 注意："per elemental ailment" 类型效果（如 Yoke）对每种异常各生成一个 mod（带 ActorCondition）
    # 例如 3 种活跃异常 × 3 种元素 = 9 个 mod entry，但实际只有 3 个独立来源（每异常一个）
    # 策略：先在单个元素类型内累加同 source+mod_name 的值并合并 ActorCondition tags，
    # 然后跨元素类型去重（取第一个元素类型的累加结果，避免重复计数）
    per_dt_accum = {}  # dt → {src_key: (first_source_dict, acc_value, merged_tags, entry_count)}
    for dt, fi in dt_entries.items():
        accum = {}
        for s in fi.get("sources", []):
            src_key = (s.get("source", ""), s.get("mod_name", ""))
            if src_key in accum:
                first_s, old_acc, old_tags, old_count = accum[src_key]
                # 合并 ActorCondition tags（避免重复）
                new_tags = old_tags
                for cond in _parse_actor_condition_tags(s.get("tags", "")):
                    tag_str = f"ActorCond:enemy:{cond}"
                    if tag_str not in new_tags:
                        new_tags = new_tags + ("," + tag_str if new_tags else tag_str)
                accum[src_key] = (first_s, old_acc + s.get("value", 0), new_tags, old_count + 1)
            else:
                accum[src_key] = (s, s.get("value", 0), s.get("tags", ""), 1)
        per_dt_accum[dt] = accum

    # 跨元素类型合并：取第一个元素类型的累加结果（因为所有元素的来源相同）
    # 但需要收集所有元素类型中该 source 的 ActorCondition tags 和 entry_count
    src_accum = {}
    first_dt = next(iter(per_dt_accum), None)
    if first_dt:
        src_accum = per_dt_accum[first_dt]
    
    # 跨元素类型补充 ActorCondition tags
    if len(per_dt_accum) > 1:
        for dt, accum in per_dt_accum.items():
            if dt == first_dt:
                continue
            for src_key, (first_s, acc_value, merged_tags, entry_count) in accum.items():
                if src_key in src_accum:
                    orig_first_s, orig_acc, orig_tags, orig_count = src_accum[src_key]
                    # 合并 ActorCondition tags
                    new_tags = orig_tags
                    for cond in _parse_actor_condition_tags(merged_tags):
                        tag_str = f"ActorCond:enemy:{cond}"
                        if tag_str not in new_tags:
                            new_tags = new_tags + ("," + tag_str if new_tags else tag_str)
                    src_accum[src_key] = (orig_first_s, orig_acc, new_tags, orig_count)

    merged_sources = []
    for src_key, (first_s, acc_value, merged_tags, entry_count) in src_accum.items():
        # 推断"per elemental ailment"效果：
        # 如果同一 source+mod_name 在单元素类型中出现多次（entry_count > 1），
        # 且 acc_value 能被 entry_count 整除（每个条目值相同），
        # 则说明这是"per N conditions"类型的效果
        is_per_ailment = False
        per_value = abs(acc_value) / entry_count if entry_count > 1 else abs(acc_value)
        if entry_count > 1 and abs(acc_value - per_value * entry_count) < 0.001:
            # 每个条目的值相同，说明是 per-condition 效果
            ctx = _get_ailments_ctx(formula_items) if formula_items else {}
            all_elem_ailments = ctx.get("all_elem_ailments", [])
            ailments = ctx.get("ailments", [])
            active_ailments = [a for a in ailments if a in all_elem_ailments] if all_elem_ailments else []
            if active_ailments and entry_count == len(active_ailments):
                # 条目数等于活跃元素异常数，确认是 per elemental ailment 效果
                is_per_ailment = True
                n_active = len(active_ailments)
                max_ailments = len(all_elem_ailments) if all_elem_ailments else n_active
                src_label = _eff_source_label(first_s.get("source", ""), "")
                if ',' in src_label:
                    src_label = src_label.split(',')[0].strip()
                if n_active >= max_ailments:
                    new_label = f"{src_label}: 每种元素异常+{per_value:.0f}%，{n_active}种=+{acc_value:.0f}%（已达上限）"
                else:
                    maximum = per_value * max_ailments
                    new_label = (f"{src_label}: 每种元素异常+{per_value:.0f}%，"
                                f"当前{n_active}种=+{acc_value:.0f}%（最多{max_ailments}种=+{maximum:.0f}%）")
            else:
                new_label = _eff_source_effect_label(
                    first_s.get("mod_name", ""), acc_value, first_s.get("source", ""), "",
                    merged_tags, formula_items)
        else:
            new_label = _eff_source_effect_label(
                first_s.get("mod_name", ""), acc_value, first_s.get("source", ""), "",
                merged_tags, formula_items)
        merged_sources.append({
            **first_s,
            "value": acc_value,
            "label": new_label,
            "tags": merged_tags,
            "entry_count": entry_count,
        })

    cat_sum = {}
    for s in merged_sources:
        cat = s.get("category", "Other")
        cat_sum[cat] = cat_sum.get(cat, 0.0) + s.get("value", 0)

    # 移除按元素展开的条目
    to_remove = {fi["key"] for fi in dt_entries.values()}
    formula_items[:] = [fi for fi in formula_items if fi["key"] not in to_remove]

    formula_items.append({
        "key": "Enemy_DamageTaken_mult",
        "formula_name": "敌人受伤增加",
        "total_value": merged_value,
        "display_value": f"x{merged_value:.4f}",
        "category_summary": cat_sum,
        "sources": merged_sources,
        "formula_detail": f"所有伤害类型共享 x{merged_value:.4f}",
    })


def _compute_weighted_eff_mult(formula_items: list, damage_composition: list):
    """计算加权 EffMult，替换按元素展开的 EffMult 条目。

    抗性收益按当前伤害构成计算真实期望：
    weightedEffMult = sum(weight_i * effMult_i)
    其中 weight_i 是该元素在总伤害中的占比。
    """
    _DT_NAMES = {"Lightning": "闪电", "Cold": "冰霜", "Fire": "火焰",
                 "Physical": "物理", "Chaos": "混沌"}

    eff_entries = {}
    for fi in formula_items:
        key = fi["key"]
        if key.endswith("_EffMult") and key != "EffMult_weighted":
            dt = key[:-len("_EffMult")]
            if dt in _DT_NAMES:
                eff_entries[dt] = fi

    if not eff_entries or not damage_composition:
        return None

    # hit_avg 已包含 EffMult（POB CalcOffence.lua:3825 damageTypeHitAvg = damageTypeHitAvg * effMult）
    # 用 pre-EffMult 伤害作为权重才能正确反映真实伤害构成
    # 注意: total_value 现在是增益百分比，需要用 _eff_mult_abs 计算加权
    pre_eff_map = {}
    for e in damage_composition:
        elem = e.get("element", "")
        if elem in eff_entries:
            eff_abs = eff_entries[elem].get("_eff_mult_abs", 1.0)
            if eff_abs > 0:
                pre_eff_map[elem] = e.get("hit_avg", 0) / eff_abs
            else:
                pre_eff_map[elem] = 0

    total_pre_eff = sum(pre_eff_map.values())
    if total_pre_eff <= 0:
        return None

    weight_map = {}
    for elem, pre_eff in pre_eff_map.items():
        weight_map[elem] = pre_eff / total_pre_eff

    if not weight_map:
        return None

    weighted_abs = 0.0
    for dt, weight in weight_map.items():
        weighted_abs += eff_entries[dt].get("_eff_mult_abs", 1.0) * weight

    # 计算加权增益百分比：用加权绝对 effMult 除以加权基础乘区
    # 加权基础乘区 = 各元素 (1 - resist/100) 按同样权重加权
    weighted_base = 0.0
    for dt, weight in weight_map.items():
        resist = eff_entries[dt].get("_resist", 0)
        weighted_base += (1 - resist / 100) * weight
    if abs(weighted_base) > 0.001:
        weighted_gain_pct = (weighted_abs / weighted_base - 1) * 100
    else:
        weighted_gain_pct = 0.0

    # 每个元素的 EffMult 作为来源，附带占比
    per_element_sources = []
    for dt, weight in sorted(weight_map.items(), key=lambda x: -x[1]):
        eff_fi = eff_entries[dt]
        gain_val = eff_fi["total_value"]  # 增益百分比
        dt_label = _DT_NAMES.get(dt, dt)
        detail = eff_fi.get("formula_detail", "")
        per_element_sources.append({
            "source": dt,
            "label": f"{dt_label} +{gain_val:.1f}% (占{weight*100:.1f}%)",
            "category": "Enemy",
            "value": gain_val,
            "weight_pct": round(weight * 100, 1),
            "formula_detail": detail,
        })

    # 聚合各元素的原始 sources（穿透/减抗 mod 来源），去重合并
    # 这些才是真正的加成来源，如 "Config: 穿透 8%"、"Item: XXX 减抗"
    mod_sources = []
    seen_mods = set()
    for dt, _ in sorted(weight_map.items(), key=lambda x: -x[1]):
        eff_fi = eff_entries[dt]
        for s in eff_fi.get("sources", []):
            src_key = (s.get("source", ""), s.get("mod_name", ""))
            if src_key not in seen_mods:
                seen_mods.add(src_key)
                mod_sources.append({
                    "source": s.get("source", ""),
                    "mod_name": s.get("mod_name", ""),
                    "category": s.get("category", "Other"),
                    "value": s.get("value", 0),
                    "element": _DT_NAMES.get(dt, dt),
                })

    # 移除按元素的 EffMult 条目
    to_remove = {fi["key"] for fi in eff_entries.values()}
    formula_items[:] = [fi for fi in formula_items if fi["key"] not in to_remove]

    # formula_detail 取代表性元素（占比最高）的抗性说明
    rep_detail = ""
    if per_element_sources:
        rep_detail = per_element_sources[0].get("formula_detail", "")

    formula_items.append({
        "key": "EffMult_weighted",
        "formula_name": "敌人抗性乘区 (加权)",
        "total_value": weighted_gain_pct,
        "display_value": f"+{weighted_gain_pct:.1f}%",
        "_eff_mult_abs": weighted_abs,
        "category_summary": {"Penetration": round(weighted_gain_pct, 1)},
        "sources": per_element_sources,
        "mod_sources": mod_sources,
        "formula_detail": rep_detail or f"按伤害构成加权: +{weighted_gain_pct:.1f}%",
    })

    return weighted_gain_pct


def _parse_double_triple(parts: list, formula_items: list):
    """解析 DOUBLE_TRIPLE 行。

    格式: DOUBLE_TRIPLE|doublePct|triplePct|scaledEffect
    """
    if len(parts) < 4:
        return
    try:
        double_pct = float(parts[1])
        triple_pct = float(parts[2])
        scaled_effect = float(parts[3])
    except (ValueError, IndexError):
        return

    if scaled_effect == 1 and double_pct == 0 and triple_pct == 0:
        return

    sources = []
    if double_pct > 0:
        sources.append({
            "source": "player",
            "label": f"双倍伤害 {double_pct:.1f}%",
            "category": "DoubleDamage",
            "value": double_pct,
            "mod_name": "DoubleDamageChance",
        })
    if triple_pct > 0:
        sources.append({
            "source": "player",
            "label": f"三倍伤害 {triple_pct:.1f}%",
            "category": "TripleDamage",
            "value": triple_pct,
            "mod_name": "TripleDamageChance",
        })

    formula_items.append({
        "key": "ScaledDamageEffect",
        "formula_name": "Scaled Damage Effect (Double/Triple)",
        "total_value": scaled_effect,
        "display_value": f"x{scaled_effect:.4f}",
        "category_summary": {s["category"]: s["value"] for s in sources},
        "sources": sources,
        "_no_sources_ok": True,
    })


def _parse_hitchance(parts: list, formula_items: list):
    """解析 HITCHANCE 行。

    格式: HITCHANCE|hitChance|accHitChance|enemyBlock
    """
    if len(parts) < 4:
        return
    try:
        hit_chance = float(parts[1])
        acc_hit_chance = float(parts[2])
        enemy_block = float(parts[3])
    except (ValueError, IndexError):
        return

    sources = []
    if acc_hit_chance < 100:
        sources.append({
            "source": "player",
            "label": "命中率（准确度）",
            "category": "Accuracy",
            "value": acc_hit_chance,
            "mod_name": "AccuracyHitChance",
        })
    if enemy_block > 0:
        sources.append({
            "source": "enemy",
            "label": "敌人格挡率",
            "category": "Enemy",
            "value": -enemy_block,
            "mod_name": "enemyBlockChance",
        })

    formula_items.append({
        "key": "HitChance",
        "formula_name": "Hit Chance",
        "total_value": hit_chance,
        "display_value": f"{hit_chance:.1f}%",
        "category_summary": {s["category"]: s["value"] for s in sources},
        "sources": sources,
        "_no_sources_ok": True,
    })


def _parse_dps_mult(parts: list, formula_items: list):
    """解析 DPS_MULT 行。

    格式: DPS_MULT|multiplier
    """
    if len(parts) < 2:
        return
    try:
        mult = float(parts[1])
    except (ValueError, IndexError):
        return

    if mult == 1:
        return

    sources = [{
        "source": "skill",
        "label": "技能 DPS 乘数",
        "category": "Skill",
        "value": mult,
        "mod_name": "dpsMultiplier",
    }]

    formula_items.append({
        "key": "DPS_Multiplier",
        "formula_name": "DPS Multiplier",
        "total_value": mult,
        "display_value": f"x{mult:.2f}",
        "category_summary": {"Skill": mult},
        "sources": sources,
        "_no_sources_ok": True,
    })


def _parse_dot_breakdown(parts: list, formula_items: list,
                         jewel_node_ids: set = None,
                         node_names: dict = None):
    """解析 DOT_BREAKDOWN 行（DoT DPS 拆解）。

    格式: DOT_BREAKDOWN|ailment|dps|min|max|effectMod|rateMod|activeAilments|effMult|duration|chance|effectIncTab|effectMoreTab|dotIncTab|dotMoreTab

    POB 的 DoT DPS 公式:
      ailmentDPS = baseVal × effectMod × rateMod × activeAilments × effMult
    其中:
      - baseVal: 基础伤害（加权平均×百分比基数，含暴击加权）
      - effectMod: 点燃效果mod (AilmentMagnitude)
      - rateMod: 速率mod (Faster/Slower)
      - activeAilments: 活跃层数
      - effMult: 抗性×受伤增加乘区
    """
    if len(parts) < 11:
        return
    try:
        ailment = parts[1]          # "Ignite" / "Bleed" / "Poison"
        ail_dps = float(parts[2])
        ail_min = float(parts[3])
        ail_max = float(parts[4])
        effect_mod = float(parts[5])
        rate_mod = float(parts[6])
        active_ailments = float(parts[7])
        eff_mult = float(parts[8])
        duration = float(parts[9])
        chance = float(parts[10])
    except (ValueError, IndexError):
        return

    # 解析 Tabulate 来源
    effect_inc_tab = parts[11] if len(parts) > 11 else ""
    effect_more_tab = parts[12] if len(parts) > 12 else ""
    dot_inc_tab = parts[13] if len(parts) > 13 else ""
    dot_more_tab = parts[14] if len(parts) > 14 else ""

    # 人类可读名称
    ail_names = {"Ignite": "点燃", "Bleed": "流血", "Poison": "中毒"}
    ail_label = ail_names.get(ailment, ailment)

    # 解析 AilmentMagnitude INC/MORE 来源
    effect_sources = []
    if effect_inc_tab:
        for entry in effect_inc_tab.split('\2'):
            p = entry.split('\1')
            if len(p) >= 3:
                try:
                    val = float(p[2])
                except ValueError:
                    continue
                category = _classify_source(p[1], jewel_node_ids)
                label = (_source_label_fallback(p[1], node_names) if category == "Sim"
                         else (_eff_source_label(p[1], "") if p[1].startswith(("Shock", "Chill", "Item:", "Config"))
                         else _source_label_fallback(p[1], node_names)))
                effect_sources.append({
                    "source": p[1],
                    "label": label,
                    "category": category,
                    "value": val,
                    "mod_name": p[0],
                })

    if effect_more_tab:
        for entry in effect_more_tab.split('\2'):
            p = entry.split('\1')
            if len(p) >= 3:
                try:
                    val = float(p[2])
                except ValueError:
                    continue
                category = _classify_source(p[1], jewel_node_ids)
                label = (_source_label_fallback(p[1], node_names) if category == "Sim"
                         else _source_label_fallback(p[1], node_names))
                effect_sources.append({
                    "source": p[1],
                    "label": label,
                    "category": category,
                    "value": (val - 1) * 100 if abs(val) > 10 else val,
                    "mod_name": p[0],
                })

    # 解析 DoT Damage INC/MORE 来源
    dot_sources = []
    if dot_inc_tab:
        for entry in dot_inc_tab.split('\2'):
            p = entry.split('\1')
            if len(p) >= 3:
                try:
                    val = float(p[2])
                except ValueError:
                    continue
                category = _classify_source(p[1], jewel_node_ids)
                label = (_source_label_fallback(p[1], node_names) if category == "Sim"
                         else _source_label_fallback(p[1], node_names))
                dot_sources.append({
                    "source": p[1],
                    "label": label,
                    "category": category,
                    "value": val,
                    "mod_name": p[0],
                })

    if dot_more_tab:
        for entry in dot_more_tab.split('\2'):
            p = entry.split('\1')
            if len(p) >= 3:
                try:
                    val = float(p[2])
                except ValueError:
                    continue
                category = _classify_source(p[1], jewel_node_ids)
                label = (_source_label_fallback(p[1], node_names) if category == "Sim"
                         else _source_label_fallback(p[1], node_names))
                dot_sources.append({
                    "source": p[1],
                    "label": label,
                    "category": category,
                    "value": (val - 1) * 100 if abs(val) > 10 else val,
                    "mod_name": p[0],
                })

    # 合并所有来源
    all_sources = effect_sources + dot_sources
    all_sources.sort(key=lambda s: abs(s["value"]), reverse=True)

    cat_sum = {}
    for s in all_sources:
        cat = s["category"]
        cat_sum[cat] = cat_sum.get(cat, 0.0) + s["value"]

    # 构建公式展示
    formula_parts = []
    if ail_min > 0 or ail_max > 0:
        formula_parts.append(f"基础 {ail_min:.0f}-{ail_max:.0f}")
    if effect_mod != 1:
        formula_parts.append(f"× 效果 {effect_mod:.4f}")
    if rate_mod != 1:
        formula_parts.append(f"× 速率 {rate_mod:.4f}")
    if active_ailments != 1:
        formula_parts.append(f"× {active_ailments:.1f}层")
    if eff_mult != 1:
        formula_parts.append(f"× effMult {eff_mult:.4f}")

    formula_detail = " ".join(formula_parts) if formula_parts else "DPS from POB"
    if duration > 0:
        formula_detail += f"  (持续 {duration:.2f}s, 几率 {chance:.1f}%)"

    formula_items.append({
        "key": f"{ailment}_DPS",
        "formula_name": f"{ail_label} DPS",
        "total_value": ail_dps,
        "display_value": f"{ail_dps:,.0f}",
        "category_summary": cat_sum,
        "sources": all_sources,
        "_no_sources_ok": True,
        "formula_detail": formula_detail,
    })


def _parse_combined_dps(parts: list, formula_items: list):
    """解析 COMBINED_DPS 行（组合 DPS 构成）。

    格式: COMBINED_DPS|totalDPS|dotDPS|impaleDPS|mirageDPS|cullMult|resDpsMult|combinedDPS|bleedDPS|poisonDPS|igniteDPS
    """
    if len(parts) < 8:
        return
    try:
        total_dps = float(parts[1])
        dot_dps = float(parts[2])
        impale_dps = float(parts[3])
        mirage_dps = float(parts[4])
        cull_mult = float(parts[5])
        res_dps_mult = float(parts[6])
        combined_dps = float(parts[7])
        bleed_dps = float(parts[8]) if len(parts) > 8 else 0
        poison_dps = float(parts[9]) if len(parts) > 9 else 0
        ignite_dps = float(parts[10]) if len(parts) > 10 else 0
    except (ValueError, IndexError):
        return

    sources = []
    if total_dps > 0:
        sources.append({
            "source": "hit",
            "label": "Hit DPS",
            "category": "Hit",
            "value": total_dps,
            "mod_name": "TotalDPS",
        })
    if bleed_dps > 0:
        sources.append({
            "source": "ailment",
            "label": "流血 DPS",
            "category": "DOT",
            "value": bleed_dps,
            "mod_name": "BleedDPS",
        })
    if poison_dps > 0:
        sources.append({
            "source": "ailment",
            "label": "中毒 DPS",
            "category": "DOT",
            "value": poison_dps,
            "mod_name": "PoisonDPS",
        })
    if ignite_dps > 0:
        sources.append({
            "source": "ailment",
            "label": "点燃 DPS",
            "category": "DOT",
            "value": ignite_dps,
            "mod_name": "IgniteDPS",
        })
    if dot_dps > 0 and (dot_dps - bleed_dps - poison_dps - ignite_dps) > 0.5:
        other_dot = dot_dps - bleed_dps - poison_dps - ignite_dps
        sources.append({
            "source": "dot",
            "label": "其他 DOT DPS",
            "category": "DOT",
            "value": other_dot,
            "mod_name": "OtherDotDPS",
        })
    if impale_dps > 0:
        sources.append({
            "source": "impale",
            "label": "穿刺 DPS",
            "category": "Impale",
            "value": impale_dps,
            "mod_name": "ImpaleDPS",
        })
    if mirage_dps > 0:
        sources.append({
            "source": "mirage",
            "label": "幻影 DPS",
            "category": "Mirage",
            "value": mirage_dps,
            "mod_name": "MirageDPS",
        })
    if cull_mult > 1:
        # Cull 额外 DPS
        base_before_cull = combined_dps / cull_mult / res_dps_mult if cull_mult > 1 else combined_dps
        cull_dps = base_before_cull * (cull_mult - 1)
        sources.append({
            "source": "cull",
            "label": f"处决 (x{cull_mult:.4f})",
            "category": "Cull",
            "value": cull_dps,
            "mod_name": "CullMultiplier",
        })
    if res_dps_mult > 1:
        base_before_res = combined_dps / res_dps_mult
        res_dps = base_before_res * (res_dps_mult - 1)
        sources.append({
            "source": "reservation",
            "label": f"保留 DPS 乘数 (x{res_dps_mult:.4f})",
            "category": "Reservation",
            "value": res_dps,
            "mod_name": "ReservationDpsMultiplier",
        })

    sources.sort(key=lambda s: abs(s["value"]), reverse=True)
    cat_sum = {}
    for s in sources:
        cat = s["category"]
        cat_sum[cat] = cat_sum.get(cat, 0.0) + s["value"]

    formula_items.append({
        "key": "CombinedDPS",
        "formula_name": "Combined DPS",
        "total_value": combined_dps,
        "display_value": f"{combined_dps:,.0f}",
        "category_summary": cat_sum,
        "sources": sources,
        "_no_sources_ok": True,
    })


def _assert_pob_output_consistency(formula_items: list, baseline: dict):
    """运行时一致性检查：确保关键值直接来自 POB 输出而非手动推算。

    检测"手动重算 POB 已计算值"反模式。如果有人把 CritChance_BASE.total_value
    改回手动推算值，或 JS/report 端从 BASE/INC/MORE 重算，此检查会捕获。

    触发 warning（不是 assert）以避免阻断正常流程，但每个 warning 都是需要修复的 bug。
    """
    cc_actual = baseline.get("CritChance", 0)
    cm_actual = baseline.get("CritMultiplier", 1)
    spd_actual = baseline.get("Speed", 0)

    for fi in formula_items:
        key = fi.get("key", "")
        tv = fi.get("total_value", 0)

        # CritChance_BASE.total_value 必须等于 POB 的 output.CritChance
        if key == "CritChance_BASE" and cc_actual > 0:
            if abs(tv - cc_actual) > 1.0:
                logger.warning(
                    "反模式检测: CritChance_BASE.total_value=%.2f 与 POB output.CritChance=%.2f "
                    "偏差超过 1%%。这通常意味着有人将 total_value 改回了手动推算值。"
                    "正确做法: total_value 必须使用 POB 的 output.CritChance。",
                    tv, cc_actual)

        # Speed: 如果 Speed_BASE 和 INC/MORE 手动推算的最终速度与 POB 不一致，说明缺少修正
        if key == "Speed_BASE" and spd_actual > 0:
            # 从 formula_items 收集 Speed 相关分量
            spd_base = tv
            spd_inc = 0
            spd_more = 1.0
            for fi2 in formula_items:
                if fi2.get("key") == "Speed_INC":
                    spd_inc = fi2.get("total_value", 0)
                elif fi2.get("key") == "Speed_MORE":
                    spd_more = fi2.get("total_value", 1.0)

            # 手动推算（仅用于对比检测，不用于实际显示）
            manual_spd = spd_base * (1 + spd_inc / 100) * spd_more
            if abs(manual_spd - spd_actual) > 0.1 and spd_base > 0:
                # 偏差存在是正常的（ActionSpeedMod、触发链路等），
                # 但如果有人用 manual_spd 替代 spd_actual 就是 bug
                logger.debug(
                    "Speed 一致性: POB实际=%.2f, 手动推算=%.2f (偏差=%.2f, "
                    "可能由 ActionSpeedMod/触发链路导致，属正常范围)",
                    spd_actual, manual_spd, spd_actual - manual_spd)


def validate_calculation_integrity(build_id: str = None) -> dict:
    """端到端验证：检查计算链路的完整性。

    验证项：
    1. Python 层: CritChance_BASE.total_value == POB output.CritChance
    2. Python 层: dps_breakdown.crit_chance/crit_multiplier/speed == baseline
    3. JS 层: 检查 report_generator.py 中是否还有手动重算模式

    Args:
        build_id: 指定构筑 ID，None 则用当前构筑

    Returns:
        {"passed": bool, "checks": [{name, passed, detail}, ...]}
    """
    checks = []

    # --- Check 1: Python 层 CritChance 一致性 ---
    try:
        calc = _get_calc_for_validation(build_id)
        result = calc.full_build_analysis() if calc else None
        if result is None:
            # fallback: try first available skill
            from .build_cache import BuildCache
            cache = BuildCache()
            builds = cache.list()
            if not builds:
                checks.append({"name": "Python CritChance", "passed": False,
                               "detail": "无缓存构筑可测试"})
                return {"passed": False, "checks": checks}
            bid = build_id or builds[0]["build_id"]
            calc = _get_calc_for_validation(bid)

        # 从 baseline 和 dps_breakdown 读取
        bl = result.get("baseline", {})
        db = result.get("dps_breakdown", {})

        cc_bl = bl.get("CritChance", 0)
        cc_db = db.get("crit_chance", 0)
        cc_match = abs(cc_bl - cc_db) < 0.01
        checks.append({"name": "Python CritChance baseline==dps_breakdown",
                       "passed": cc_match,
                       "detail": f"baseline={cc_bl:.2f} dps_breakdown={cc_db:.2f}"})

        # CritChance_BASE.total_value
        for fi in db.get("formula_items", []):
            if fi["key"] == "CritChance_BASE":
                cc_fi = fi["total_value"]
                cc_fi_match = abs(cc_fi - cc_bl) < 1.0
                checks.append({"name": "Python CritChance_BASE.total_value==POB",
                               "passed": cc_fi_match,
                               "detail": f"total_value={cc_fi:.2f} POB={cc_bl:.2f}"})

        # CM 一致性
        cm_bl = bl.get("CritMultiplier", 1)
        cm_db = db.get("crit_multiplier", 1)
        cm_match = abs(cm_bl - cm_db) < 0.01
        checks.append({"name": "Python CritMultiplier baseline==dps_breakdown",
                       "passed": cm_match,
                       "detail": f"baseline={cm_bl:.2f} dps_breakdown={cm_db:.2f}"})

        # Speed 一致性
        spd_bl = bl.get("Speed", 0)
        spd_db = db.get("speed", 0)
        spd_match = abs(spd_bl - spd_db) < 0.01
        checks.append({"name": "Python Speed baseline==dps_breakdown",
                       "passed": spd_match,
                       "detail": f"baseline={spd_bl:.2f} dps_breakdown={spd_db:.2f}"})

    except Exception as e:
        checks.append({"name": "Python 计算", "passed": False, "detail": str(e)})

    # --- Check 2: JS 层无手动重算模式 ---
    try:
        rg_path = Path(__file__).parent.parent / "report_generator.py"
        rg_code = rg_path.read_text(encoding="utf-8")

        # 检测已知的反模式
        anti_patterns = [
            ("cmBase/100", "CritMultiplier 从 BASE/INC 手动推算"),
            ("spdBase * (1", "Speed 从 BASE/INC/MORE 手动推算"),
            ("ccBase * (1 + ccInc", "CritChance 从 BASE/INC/MORE 手动推算"),
        ]
        for pattern, desc in anti_patterns:
            found = pattern in rg_code
            checks.append({"name": f"JS 无手动重算: {desc}",
                           "passed": not found,
                           "detail": f"{'发现' if found else '未发现'} 反模式 '{pattern}'"})

        # 检测正确模式
        correct_patterns = [
            ("data.crit_chance", "JS 使用 data.crit_chance"),
            ("data.crit_multiplier", "JS 使用 data.crit_multiplier"),
            ("data.speed", "JS 使用 data.speed"),
        ]
        for pattern, desc in correct_patterns:
            found = pattern in rg_code
            checks.append({"name": f"JS 正确模式: {desc}",
                           "passed": found,
                           "detail": f"{'已使用' if found else '未使用'} '{pattern}'"})

    except Exception as e:
        checks.append({"name": "JS 反模式检测", "passed": False, "detail": str(e)})

    all_passed = all(c["passed"] for c in checks)
    return {"passed": all_passed, "checks": checks}


def _get_calc_for_validation(build_id: str = None):
    """获取 POBCalculator 实例用于验证。"""
    from . import POBCalculator
    if build_id:
        return POBCalculator.from_build_id(build_id)
    return POBCalculator.from_current()


def _empty_breakdown(baseline: dict) -> dict:
    """空结构。"""
    return {
        "total_dps": baseline.get("TotalDPS", 0),
        "average_hit": baseline.get("AverageHit", 0),
        "speed": baseline.get("Speed", 0),
        "crit_chance": baseline.get("CritChance", 0),
        "crit_multiplier": baseline.get("CritMultiplier", 1),
        "combined_dps": baseline.get("CombinedDPS", 0),
        "active_damage_types": [],
        "formula_items": [],
    }


