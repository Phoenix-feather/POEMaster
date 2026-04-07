"""DPS 来源拆解模块。

职责：
- dps_breakdown: 从 POB tabulation 解析 DPS 公式
- _classify_source / _source_label_fallback
- 所有 _parse_* / _compute_* 辅助函数
"""
import logging
import re
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
    prefix = source.split(":")[0] if ":" in source else source
    if prefix == "Tree" and jewel_node_ids:
        node_id = source.split(":")[1] if ":" in source else ""
        if node_id in jewel_node_ids:
            return "Jewel"
    if prefix in ("Base", "Tree", "Item", "Skill", "Config"):
        return prefix
    return "Other"


def _source_label_fallback(source: str) -> str:
    """当 Lua 端未返回 label 时的 fallback 转换。"""
    if not source:
        return "未知"
    if source == "Base":
        return "基础值"
    if source == "Config":
        return "配置"
    prefix = source.split(":")[0] if ":" in source else source
    rest = source[len(prefix)+1:] if ":" in source else ""
    if prefix == "Tree":
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
        if build.itemsTab and build.itemsTab.items then
            for id, item in pairs(build.itemsTab.items) do
                if item.name then
                    itemNames[tostring(id)] = item.name
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
        -- 每条: modName\1source\1value\1label
        local function tabStr(modType, ...)
            local tab = skillModList:Tabulate(modType, cfg, ...)
            local parts = {}
            for _, entry in ipairs(tab) do
                if entry.value ~= 0 then
                    local m = entry.mod
                    local src = m.source or "Unknown"
                    local name = type(m.name) == "string" and m.name or "?"
                    local lbl = resolveLabel(src)
                    parts[#parts+1] = name .. "\1" .. src .. "\1" .. tostring(entry.value) .. "\1" .. lbl
                end
            end
            return table.concat(parts, "\2")
        end

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
            -- 基础速度（非 modDB 中的值）
            local baseSpeed = 0
            local baseSpeedLabel = "Base"
            -- 判断是否攻击技能：ModFlag.Attack = 0x01
            local isAttack = cfg.flags and (cfg.flags & 0x01) ~= 0
            if isAttack and damageSource and damageSource.AttackRate then
                baseSpeed = damageSource.AttackRate
                baseSpeedLabel = "Weapon Attack Rate"
            elseif ms.skillData.castTimeOverride then
                baseSpeed = 1 / ms.skillData.castTimeOverride
                baseSpeedLabel = "Cast Time Override"
            elseif ms.skillData.castTime then
                baseSpeed = 1 / ms.skillData.castTime
                baseSpeedLabel = "Base Cast Rate"
            else
                -- 触发技能等：castTime 不可用，使用 output.Speed（已含 INC/MORE）
                baseSpeed = output.Speed
                baseSpeedLabel = "Trigger Rate (computed)"
            end
            lines[#lines+1] = "SPEED_BASE|Speed|" .. tostring(baseSpeed) .. "|" .. baseSpeedLabel
            local sInc = skillModList:Sum("INC", cfg, "Speed")
            lines[#lines+1] = "SPEED_INC|Speed|" .. tostring(sInc) .. "|" .. tabStr("INC", "Speed")
            local sMore = skillModList:More(cfg, "Speed")
            lines[#lines+1] = "SPEED_MORE|Speed|" .. tostring(sMore) .. "|" .. tabStr("MORE", "Speed")
        end

        -- === 5. CritChance ===
        if (output.CritChance or 0) > 0 then
            -- 宝石/武器固有基础暴击率（不在 modDB 中）
            local baseCrit = ms.skillData.CritChance or damageSource.CritChance or 0
            local ccB = skillModList:Sum("BASE", cfg, "CritChance")
            lines[#lines+1] = "CRIT_BASE|CritChance|" .. tostring(ccB) .. "|" .. tostring(baseCrit) .. "|" .. tabStr("BASE", "CritChance")
            local ccI = skillModList:Sum("INC", cfg, "CritChance")
            lines[#lines+1] = "CRIT_INC|CritChance|" .. tostring(ccI) .. "|" .. tabStr("INC", "CritChance")
            local ccM = skillModList:More(cfg, "CritChance")
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
        -- 从 MAIN 模式 env 直接读取数据（避免 CALCS 模式的 Lua 5.4 兼容问题）
        -- env.mode_effective = true（MAIN 模式默认），所以抗性/穿透计算已生效
        local enemyDB = env.enemyDB

        if enemyDB and env.mode_effective then
            for _, dt in ipairs(activeDT) do
                local takenInc = enemyDB:Sum("INC", cfg, "DamageTaken", dt.."DamageTaken")
                local takenMore = enemyDB:More(cfg, "DamageTaken", dt.."DamageTaken")
                local resist = 0
                local pen = 0
                -- 元素追加 ElementalDamageTaken
                if isElemental[dt] then
                    takenInc = takenInc + enemyDB:Sum("INC", cfg, "ElementalDamageTaken")
                    pen = skillModList:Sum("BASE", cfg, dt.."Penetration", "ElementalPenetration")
                elseif dt == "Chaos" then
                    pen = skillModList:Sum("BASE", cfg, "ChaosPenetration")
                end
                -- 获取敌人抗性
                if dt == "Physical" then
                    resist = enemyDB:Sum("BASE", nil, "PhysicalDamageReduction")
                else
                    resist = enemyDB:Sum("BASE", nil, dt.."Resist")
                end
                -- 计算 effMult（与 CalcOffence.lua:3816-3821 一致）
                local effectiveResist = resist > 0 and math.max(resist - pen, 0) or resist
                local effMult = (1 + takenInc / 100) * takenMore * (1 - effectiveResist / 100)
                if effMult ~= 0 and (math.abs(effMult - 1) > 0.001 or pen > 0) then
                    -- 格式: EFF_MULT|dt|effMult|resist|pen|takenInc|takenMore
                    lines[#lines+1] = "EFF_MULT|" .. dt .. "|"
                        .. string.format("%.6f", effMult) .. "|"
                        .. string.format("%.1f", resist) .. "|"
                        .. string.format("%.1f", pen) .. "|"
                        .. string.format("%.1f", takenInc) .. "|"
                        .. string.format("%.6f", takenMore)
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

    active_types = []
    jewel_node_ids = set()  # 珠宝槽位节点 ID 集合
    formula_items = []
    _conv_mult_data = {}  # fromType → convMult（未转换比例）

    if not result:
        return _empty_breakdown(baseline)

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
            # 特殊格式: CRIT_BASE|CritChance|ccB|baseCrit|tabEntries
            parts = line.split('|', 4)
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
            # 格式: EFF_MULT|dt|effMult|resist|pen|takenInc|takenMore
            parts = line.split('|')
            _parse_eff_mult(parts, formula_items)

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

        elif section == "COMBINED_DPS":
            # 格式: COMBINED_DPS|totalDPS|dotDPS|impaleDPS|mirageDPS|cullMult|resDpsMult|combinedDPS|bleedDPS|poisonDPS|igniteDPS
            parts = line.split('|')
            _parse_combined_dps(parts, formula_items)

    # 过滤掉没有来源的非 base-damage 空项
    formula_items = [fi for fi in formula_items
                     if fi.get("_is_base") or fi.get("_no_sources_ok") or fi["sources"]]
    # 清理内部标记
    for fi in formula_items:
        fi.pop("_is_base", None)
        fi.pop("_no_sources_ok", None)

    # === 计算 DPS 乘区流程（供报告渲染使用） ===
    flow_stages = _compute_dps_flow_stages(formula_items, baseline)

    return {
        "total_dps": baseline.get("TotalDPS", 0),
        "average_hit": baseline.get("AverageHit", 0),
        "speed": baseline.get("Speed", 0),
        "combined_dps": baseline.get("CombinedDPS", 0),
        "active_damage_types": active_types,
        "formula_items": formula_items,
        "dps_flow_stages": flow_stages,
        "damage_composition": _extract_damage_composition(baseline),
    }


def _compute_dps_flow_stages(formula_items: list, baseline: dict) -> list:
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
    crit_base_val = sum(it["total_value"] for it in crit if it["key"] == "CritChance_BASE")
    crit_inc_val = sum(it["total_value"] for it in crit if it["key"] == "CritChance_INC")
    crit_more_val = 1.0
    for it in crit:
        if it["key"] == "CritChance_MORE":
            crit_more_val *= it["total_value"]
    crit_multi_inc_val = sum(it["total_value"] for it in crit if it["key"] == "CritMultiplier_INC")
    # 暴击率 = base% × (1 + INC/100) × MORE，上限 100%
    cc = min(crit_base_val * (1 + crit_inc_val / 100) * crit_more_val, 100) / 100
    # 暴击倍率 = (100 + CritMultiplier_BASE + CritMultiplier_INC) / 100
    cm_base = sum(it["total_value"] for it in crit if it["key"] == "CritMultiplier_BASE")
    cm = (cm_base + crit_multi_inc_val) / 100
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

    # 7) 敌人抗性（EffMult）
    eff = [it for it in formula_items if it["key"].endswith("_EffMult")]

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
    if eff:
        _add("敌人抗性",
         ", ".join(f"{it['formula_name']} ×{it['total_value']:.2f}" for it in eff),
         "已内含在 AvgHit 中", "#e05555", eff)
    speed_label = "施法速度" if baseline.get("Speed_INC", 0) >= 0 and not any(
        it["key"] == "Speed_BASE" and "attack" in it.get("formula_name", "").lower()
        for it in speed_items) else "攻击速度"
    _add(speed_label, f"{spd:.2f}/s",
         f"\u00d7{spd:.2f}", "#44bbcc", speed_items)
    _add("Total DPS", f"{base_avg:,.0f} \u00d7 {spd:.2f} = {total_dps:,.0f}",
         "POB \u5b9e\u9645\u8f93\u51fa", "#d4a843", [])

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
                if p[1] in min_by_source:
                    min_by_source[p[1]]["value"] += val
                else:
                    min_by_source[p[1]] = {
                        "mod_name": p[0], "value": val, "label": p[3]
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
                if p[1] in max_by_source:
                    max_by_source[p[1]]["value"] += val
                else:
                    max_by_source[p[1]] = {
                        "mod_name": p[0], "value": val, "label": p[3]
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
                label = p[3] if len(p) > 3 else _source_label_fallback(p[1])
                sources.append({
                    "source": p[1],
                    "label": label,
                    "category": _classify_source(p[1], jewel_node_ids),
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
    """解析 CritChance BASE 行（含宝石固有 baseCrit）。

    格式: CRIT_BASE|CritChance|ccB|baseCrit|tabEntries
    - ccB: skillModList:Sum("BASE", "CritChance") — 额外加的 flat crit
    - baseCrit: 宝石/武器固有暴击率（不在 modDB 中）
    """
    if len(parts) < 4:
        return
    try:
        added_base = float(parts[2])
        gem_base = float(parts[3])
    except (ValueError, IndexError):
        return

    sources = []

    # 宝石/武器固有基础暴击率
    if gem_base > 0:
        sources.append({
            "source": "gem",
            "label": "技能基础暴击率",
            "category": "Skill",
            "value": gem_base,
            "mod_name": "gem_base_crit",
        })

    # 额外 BASE mod (Tabulate 结果)
    tab_data = parts[4] if len(parts) > 4 else ""
    if tab_data:
        for entry in tab_data.split('\2'):
            p = entry.split('\1')
            if len(p) >= 3:
                try:
                    val = float(p[2])
                except ValueError:
                    continue
                label = p[3] if len(p) > 3 else _source_label_fallback(p[1])
                sources.append({
                    "source": p[1],
                    "label": label,
                    "category": _classify_source(p[1], jewel_node_ids),
                    "value": val,
                    "mod_name": p[0],
                })

    sources.sort(key=lambda s: abs(s["value"]), reverse=True)

    cat_sum = {}
    for s in sources:
        cat = s["category"]
        cat_sum[cat] = cat_sum.get(cat, 0.0) + s["value"]

    total = gem_base + added_base
    formula_items.append({
        "key": "CritChance_BASE",
        "formula_name": "CritChance BASE",
        "total_value": total,
        "display_value": f"{total:.1f}% (base {gem_base:.1f}% + added {added_base:.0f}%)",
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
    sources = [{
        "source": "gem",
        "label": label,
        "category": "Skill",
        "value": base_speed,
        "mod_name": "base_speed",
    }]

    formula_items.append({
        "key": "Speed_BASE",
        "formula_name": "Speed Base",
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
                    label = p[3] if len(p) > 3 else _source_label_fallback(p[1])
                    sources.append({
                        "source": p[1],
                        "label": label,
                        "category": _classify_source(p[1], jewel_node_ids),
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
    """解析 EFF_MULT 行（有效 DPS 乘数：穿透/抗性/受伤增加）。

    格式: EFF_MULT|dt|effMult|resist|pen|takenInc|takenMore
    """
    if len(parts) < 7:
        return
    try:
        dt = parts[1]
        eff_mult = float(parts[2])
        resist = float(parts[3])
        pen = float(parts[4])
        taken_inc = float(parts[5])
        taken_more = float(parts[6])
    except (ValueError, IndexError):
        return

    sources = []

    if resist != 0:
        sources.append({
            "source": "enemy",
            "label": f"敌人 {dt} 抗性",
            "category": "Enemy",
            "value": resist,
            "mod_name": f"{dt}Resist",
        })

    if pen != 0:
        sources.append({
            "source": "player",
            "label": f"{dt} 穿透",
            "category": "Penetration",
            "value": pen,
            "mod_name": f"{dt}Penetration",
        })

    if taken_inc != 0:
        sources.append({
            "source": "enemy",
            "label": f"敌人受到 {dt} 伤害增加",
            "category": "Enemy",
            "value": taken_inc,
            "mod_name": f"{dt}DamageTaken_INC",
        })

    if taken_more != 1:
        sources.append({
            "source": "enemy",
            "label": f"敌人受到 {dt} 伤害 MORE",
            "category": "Enemy",
            "value": (taken_more - 1) * 100,
            "mod_name": f"{dt}DamageTaken_MORE",
        })

    # 公式: effMult = (1 + takenInc/100) × takenMore × (1 - max(resist-pen, 0)/100)
    formula_detail = f"(1+{taken_inc:.0f}/100) × {taken_more:.4f}"
    if resist != 0 or pen != 0:
        effective_resist = max(resist - pen, 0)
        formula_detail += f" × (1-{effective_resist:.0f}/100)"

    formula_items.append({
        "key": f"{dt}_EffMult",
        "formula_name": f"{dt} Effective DPS Multiplier",
        "total_value": eff_mult,
        "display_value": f"x{eff_mult:.4f}",
        "category_summary": {s["category"]: s["value"] for s in sources},
        "sources": sources,
        "_no_sources_ok": True,
        "formula_detail": formula_detail,
    })


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


def _empty_breakdown(baseline: dict) -> dict:
    """空结构。"""
    return {
        "total_dps": baseline.get("TotalDPS", 0),
        "average_hit": baseline.get("AverageHit", 0),
        "speed": baseline.get("Speed", 0),
        "combined_dps": baseline.get("CombinedDPS", 0),
        "active_damage_types": [],
        "formula_items": [],
    }


