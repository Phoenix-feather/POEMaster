"""天赋价值与珠宝分析模块。

职责：
- passive_node_analysis: 已分配天赋价值分析
- passive_node_exploration: 未分配天赋探索
- diagnose_jewels: 珠宝诊断
"""
import logging
from .calculator import calculate

logger = logging.getLogger(__name__)


# =============================================================================
# 天赋价值分析
# =============================================================================


def _get_notable_nodes(lua) -> list[dict]:
    """获取构筑中已分配的 Notable / Keystone 天赋节点列表。"""
    result = lua.execute('''
        local build = _spike_build
        local nodes = {}
        for id, node in pairs(build.spec.allocNodes) do
            if node.type == "Notable" or node.type == "Keystone" then
                local desc = node.sd and table.concat(node.sd, "; ") or ""
                nodes[#nodes+1] = tostring(id) .. "|" .. (node.dn or "?") .. "|" .. (node.type or "?") .. "|" .. desc
            end
        end
        return table.concat(nodes, "\\n")
    ''')
    nodes = []
    if result:
        for line in str(result).strip().split('\n'):
            parts = line.split('|', 3)
            if len(parts) >= 3:
                nodes.append({
                    'id': int(parts[0]),
                    'name': parts[1],
                    'type': parts[2],
                    'description': parts[3] if len(parts) > 3 else '',
                })
    return nodes


def _get_unallocated_nodes(lua, include_normal: bool = False) -> list[dict]:
    """获取天赋树上未分配的节点列表。

    Args:
        lua: LuaRuntime
        include_normal: 是否包含 Normal 类型的小天赋节点

    Returns:
        [{id, name, type, mod_key, description}, ...]
        mod_key: 节点修饰语的序列化指纹，相同 mod_key 的节点效果相同
        description: 天赋效果描述（来自 node.sd）
    """
    type_filter = ""
    if include_normal:
        type_filter = "if node.type == 'Notable' or node.type == 'Keystone' or node.type == 'Normal' then"
    else:
        type_filter = "if node.type == 'Notable' or node.type == 'Keystone' then"

    result = lua.execute(f'''
        local build = _spike_build
        local nodes = {{}}
        for id, node in pairs(build.spec.nodes) do
            if not build.spec.allocNodes[id] then
                {type_filter}
                    -- 排除升华节点（不同升华的节点不应混入）
                    if not node.ascendancyName or node.ascendancyName == build.spec.curAscendClassName then
                        local desc = node.sd and table.concat(node.sd, "; ") or ""
                        nodes[#nodes+1] = tostring(id) .. "|" .. (node.dn or "?") .. "|" .. (node.type or "?") .. "|" .. (node.modKey or "") .. "|" .. desc
                    end
                end
            end
        end
        return table.concat(nodes, "\\n")
    ''')
    nodes = []
    if result:
        for line in str(result).strip().split('\n'):
            if not line:
                continue
            parts = line.split('|', 4)
            if len(parts) >= 4:
                try:
                    nodes.append({
                        'id': int(parts[0]),
                        'name': parts[1],
                        'type': parts[2],
                        'mod_key': parts[3],
                        'description': parts[4] if len(parts) > 4 else '',
                    })
                except ValueError:
                    pass
    return nodes


def passive_node_analysis(lua, calcs, baseline: dict = None,
                          dps_stat: str = "TotalDPS",
                          ehp_stat: str = "TotalEHP") -> list[dict]:
    """天赋价值分析：逐个移除已分配的 Notable/Keystone，评估 DPS 和 EHP 影响。

    Returns:
        按 DPS 损失降序排列：
        [{id, name, type, dps_pct, ehp_pct, category}, ...]
        category: "进攻" / "防御" / "混合" / "无效"
    """
    if baseline is None:
        baseline = calculate(lua, calcs)

    nodes = _get_notable_nodes(lua)
    logger.info("天赋价值分析: %d 个 Notable/Keystone", len(nodes))

    base_dps = baseline.get(dps_stat, 0)
    base_ehp = baseline.get(ehp_stat, 0)

    results = []
    for node in nodes:
        nid = node['id']
        diff = what_if_nodes(lua, calcs, remove=[nid], baseline=baseline)

        dps_entry = diff.get(dps_stat)
        ehp_entry = diff.get(ehp_stat)

        dps_after = dps_entry[1] if dps_entry else base_dps
        dps_delta = dps_entry[2] if dps_entry else 0
        dps_pct = (dps_delta / base_dps * 100) if base_dps != 0 else 0

        ehp_after = ehp_entry[1] if ehp_entry else base_ehp
        ehp_delta = ehp_entry[2] if ehp_entry else 0
        ehp_pct = (ehp_delta / base_ehp * 100) if base_ehp != 0 else 0

        has_dps = abs(dps_pct) > 0.1
        has_ehp = abs(ehp_pct) > 0.1
        if has_dps and has_ehp:
            category = "兼顾"
        elif has_dps:
            category = "输出"
        elif has_ehp:
            category = "生存"
        else:
            category = "无收益"

        results.append({
            "id": nid, "name": node['name'], "type": node['type'],
            "dps_before": base_dps, "dps_after": dps_after,
            "dps_delta": dps_delta, "dps_pct": dps_pct,
            "ehp_before": base_ehp, "ehp_after": ehp_after,
            "ehp_delta": ehp_delta, "ehp_pct": ehp_pct,
            "category": category,
            "description": node.get('description', ''),
        })

    results.sort(key=lambda x: abs(x["dps_pct"]), reverse=True)
    return results


def passive_node_exploration(lua, calcs, baseline: dict = None,
                             dps_stat: str = "TotalDPS",
                             ehp_stat: str = "TotalEHP",
                             min_dps_pct: float = 0.5,
                             include_normal: bool = False) -> list[dict]:
    """天赋探索分析：逐个添加未分配节点，评估 DPS 和 EHP 收益。

    使用 POB 原生 override.addNodes 机制临时添加节点，不修改 build 对象。
    注意：由于绕过了路径连通性检查，部分节点在实际游戏中可能无法直接点出。

    优化：
    - Lua 批量计算：单次 Lua 调用完成所有节点评估，避免 Python↔Lua 往返开销
    - modKey 缓存：相同 modKey 的节点只计算一次（如多个 +10% 伤害小天赋共享结果）
    - Normal 小天赋：默认关闭（include_normal=False），小天赋收益极低且计算量大

    Args:
        baseline: 基线 output
        dps_stat: DPS 指标名（默认 TotalDPS）
        ehp_stat: EHP 指标名（默认 TotalEHP）
        min_dps_pct: 最小 DPS 变化百分比阈值（低于此值不显示，默认 0.5%）
        include_normal: 是否包含 Normal 小天赋节点（默认 False，小天赋收益低且计算量大）

    Returns:
        按 DPS 增益降序排列：
        [{id, name, type, dps_pct, ehp_pct, category, mod_key}, ...]
        category: "进攻" / "防御" / "混合" / "无效"
    """
    if baseline is None:
        baseline = calculate(lua, calcs)

    base_dps = baseline.get(dps_stat, 0)
    base_ehp = baseline.get(ehp_stat, 0)

    # Lua 批量计算：单次调用完成所有节点评估
    # 在 Lua 端重新计算 baseline 以确保获取正确的 baseDPS/baseEHP
    node_type_filter = 'true' if include_normal else '(node.type == "Notable" or node.type == "Keystone")'
    lua_code = '''
local calcs = ...
local b = _spike_build
local dpsStat = "''' + dps_stat + '''"
local ehpStat = "''' + ehp_stat + '''"
-- 重新计算基线以获取正确的 baseDPS/baseEHP
local baseEnv = calcs.initEnv(b, "CALCULATOR", {})
calcs.perform(baseEnv)
local baseDPS = baseEnv.player.output[dpsStat] or 0
local baseEHP = baseEnv.player.output[ehpStat] or 0
local minPct = ''' + str(min_dps_pct) + '''
local includeNormal = ''' + str(include_normal).lower() + '''
local cache = {}
local lines = {}
local nodeCount = 0
local cacheHits = 0
local uniqueKeys = 0
local nodes = b.spec.nodes
for nid, node in pairs(nodes) do
    if ''' + node_type_filter + '''
       and not node.alloc
       and node.modKey ~= ""
       and not node.ascendancyName then
        nodeCount = nodeCount + 1
        local mk = node.modKey
        local dpsAfter, dpsDelta, ehpAfter, ehpDelta
        if cache[mk] then
            dpsAfter, dpsDelta, ehpAfter, ehpDelta = cache[mk][1], cache[mk][2], cache[mk][3], cache[mk][4]
            cacheHits = cacheHits + 1
        else
            local env = calcs.initEnv(b, "CALCULATOR", {addNodes={[node]=true}})
            calcs.perform(env)
            local out = env.player.output
            dpsAfter = out[dpsStat] or baseDPS
            ehpAfter = out[ehpStat] or baseEHP
            dpsDelta = dpsAfter - baseDPS
            ehpDelta = ehpAfter - baseEHP
            cache[mk] = {dpsAfter, dpsDelta, ehpAfter, ehpDelta}
            uniqueKeys = uniqueKeys + 1
        end
        local dpsPct = baseDPS ~= 0 and dpsDelta / baseDPS * 100 or 0
        local ehpPct = baseEHP ~= 0 and ehpDelta / baseEHP * 100 or 0
        if math.abs(dpsPct) >= minPct or math.abs(ehpPct) >= minPct then
            local cat = "none"
            if math.abs(dpsPct) > 0.1 and math.abs(ehpPct) > 0.1 then cat = "both"
            elseif math.abs(dpsPct) > 0.1 then cat = "dps"
            elseif math.abs(ehpPct) > 0.1 then cat = "ehp" end
            lines[#lines+1] = nid.."\\t"..node.dn.."\\t"..node.type.."\\t"
                ..string.format("%.6f", dpsAfter).."\\t"..string.format("%.6f", dpsDelta).."\\t"..string.format("%.4f", dpsPct).."\\t"
                ..string.format("%.6f", ehpAfter).."\\t"..string.format("%.6f", ehpDelta).."\\t"..string.format("%.4f", ehpPct).."\\t"
                ..cat.."\\t"..mk.."\\t"..(node.sd and table.concat(node.sd, "; ") or "")
        end
    end
end
return tostring(nodeCount).."\\n"..tostring(cacheHits).."\\n"..tostring(uniqueKeys).."\\n"..table.concat(lines, "\\n")
'''
    raw = str(lua.execute(lua_code, calcs))
    header_lines = raw.split('\n', 3)
    node_count = int(header_lines[0])
    cache_hits = int(header_lines[1])
    unique_modkeys = int(header_lines[2])
    data_lines = header_lines[3].split('\n') if len(header_lines) > 3 and header_lines[3] else []

    logger.info("天赋探索: %d 个未分配节点, Lua 批量计算完成 (缓存命中: %d, unique modKeys: %d)",
                node_count, cache_hits, unique_modkeys)

    _CAT_MAP = {"both": "兼顾", "dps": "输出", "ehp": "生存", "none": "无收益"}

    results = []
    for line in data_lines:
        if not line.strip():
            continue
        parts = line.split('\t')
        if len(parts) < 11:
            continue
        try:
            results.append({
                "id": int(parts[0]),
                "name": parts[1],
                "type": parts[2],
                "dps_before": base_dps,
                "dps_after": float(parts[3]),
                "dps_delta": float(parts[4]),
                "dps_pct": round(float(parts[5]), 2),
                "ehp_before": base_ehp,
                "ehp_after": float(parts[6]),
                "ehp_delta": float(parts[7]),
                "ehp_pct": round(float(parts[8]), 2),
                "category": _CAT_MAP.get(parts[9], parts[9]),
                "mod_key": parts[10],
                "description": parts[11] if len(parts) > 11 else '',
            })
        except (ValueError, IndexError):
            continue

    logger.info("天赋探索完成: %d 个有效结果, 缓存: %d unique modKeys / %d 次命中",
                len(results), unique_modkeys, cache_hits)

    results.sort(key=lambda x: x["dps_pct"], reverse=True)
    return results


# =============================================================================
# 珠宝诊断
# =============================================================================


def diagnose_jewels(lua, calcs, baseline: dict = None,
                    dps_stat: str = "TotalDPS",
                    ehp_stat: str = "TotalEHP") -> list[dict]:
    """诊断构筑中所有珠宝的加载状态和 DPS+EHP 贡献。

    检查每个珠宝是否正确加载、mod 是否被解析、是否影响 DPS 和 EHP。
    特别关注 Megalomaniac 等通过 "Allocates" 分配天赋的珠宝。

    Returns:
        [{
            "slot_name": 槽位名,
            "node_id": 天赋树节点 ID,
            "item_id": 物品 ID,
            "name": 物品名称（如 "Megalomaniac"）,
            "base_type": 基础类型（如 "Large Jewel"）,
            "rarity": 稀有度,
            "mod_count": mod 数量,
            "mods": mod 列表 [{"name", "type", "value", "source"}],
            "granted_passives": 分配的天赋节点名称列表,
            "dps_pct": 移除此珠宝后 DPS 下降百分比（正值=正向贡献）,
            "ehp_pct": 移除此珠宝后 EHP 下降百分比（正值=正向贡献）,
            "status": "ok" / "empty" / "no_base" / "no_mods",
        }, ...]
    """
    if baseline is None:
        baseline = calculate(lua, calcs)

    base_dps = baseline.get(dps_stat, 0)
    base_ehp = baseline.get(ehp_stat, 0)

    # 从 Lua 端获取所有珠宝槽位信息
    result = lua.execute('''
        local build = _spike_build
        local lines = {}

        for _, slot in ipairs(build.itemsTab.orderedSlots) do
            local sn = slot.slotName or ""
            if sn:find("^Jewel ") then
                local itemId = slot.selItemId or 0
                local nodeId = slot.nodeId or 0
                local item = build.itemsTab.items[itemId]
                if item and item.base then
                    local name = item.title or item.name or "?"
                    local baseType = item.base.name or item.baseName or "?"
                    local rarity = item.rarity or "?"

                    -- 收集 mod 信息（mod 结构: {name=str, type=str, value=...}）
                    -- 注意：m.name 或 m[1] 可能是 table（如 tag 列表），需用 tostring 安全转换
                    local modTexts = {}
                    local grantedPassives = {}
                    if item.modList then
                        for i = 1, #item.modList do
                            local m = item.modList[i]
                            local mName = type(m.name) == "string" and m.name
                                or type(m[1]) == "string" and m[1]
                                or tostring(m.name or m[1] or "?")
                            local mType = tostring(m.type or "?")
                            local mVal = tostring(m.value or 0)
                            modTexts[#modTexts+1] = mName .. "|" .. mType .. "|" .. mVal

                            -- 检查 GrantedPassive（Megalomaniac / Forbidden Flame 等）
                            if mName == "GrantedPassive" and mType == "LIST" then
                                grantedPassives[#grantedPassives+1] = tostring(m.value or "?")
                            end
                        end
                    end

                    -- 检查 variant 信息（Megalomaniac 用 3-variant 系统）
                    local variantInfo = ""
                    if item.variant then
                        variantInfo = tostring(item.variant)
                    end
                    if item.variantAlt then
                        variantInfo = variantInfo .. "," .. tostring(item.variantAlt)
                    end
                    if item.variantAlt2 then
                        variantInfo = variantInfo .. "," .. tostring(item.variantAlt2)
                    end

                    lines[#lines+1] = tostring(nodeId) .. "@@"
                        .. tostring(itemId) .. "@@"
                        .. name .. "@@"
                        .. baseType .. "@@"
                        .. rarity .. "@@"
                        .. tostring(#modTexts) .. "@@"
                        .. table.concat(modTexts, ";;") .. "@@"
                        .. table.concat(grantedPassives, ";;") .. "@@"
                        .. variantInfo
                elseif itemId > 0 then
                    -- 物品存在但没有 base（解析失败）
                    lines[#lines+1] = tostring(nodeId) .. "@@"
                        .. tostring(itemId) .. "@@?@@?@@?@@0@@@@@@no_base"
                else
                    -- 空槽位
                    lines[#lines+1] = tostring(nodeId) .. "@@0@@@@@@@@0@@@@@@empty"
                end
            end
        end
        return table.concat(lines, "\\n")
    ''')

    jewels = []
    if result:
        for line in str(result).strip().split('\n'):
            if not line:
                continue
            parts = line.split('@@')
            if len(parts) < 9:
                continue

            node_id = int(parts[0]) if parts[0].isdigit() else 0
            item_id = int(parts[1]) if parts[1].isdigit() else 0
            name = parts[2] or "?"
            base_type = parts[3] or "?"
            rarity = parts[4] or "?"
            mod_count = int(parts[5]) if parts[5].isdigit() else 0
            variant_info = parts[8] if len(parts) > 8 else ""

            # 解析 mod 列表
            mods = []
            if parts[6]:
                for mod_text in parts[6].split(';;'):
                    if '|' in mod_text:
                        mp = mod_text.split('|', 2)
                        mods.append({
                            "name": mp[0],
                            "type": mp[1] if len(mp) > 1 else "?",
                            "value": mp[2] if len(mp) > 2 else "0",
                        })

            # 解析 GrantedPassive
            granted_passives = []
            if parts[7]:
                granted_passives = [p for p in parts[7].split(';;') if p]

            # 判断状态
            if variant_info == "no_base":
                status = "no_base"
            elif variant_info == "empty" or item_id == 0:
                status = "empty"
            elif mod_count == 0:
                status = "no_mods"
            else:
                status = "ok"

            jewels.append({
                "slot_name": f"Jewel {node_id}",
                "node_id": node_id,
                "item_id": item_id,
                "name": name,
                "base_type": base_type,
                "rarity": rarity,
                "mod_count": mod_count,
                "mods": mods,
                "granted_passives": granted_passives,
                "variant_info": variant_info,
                "dps_pct": 0.0,
                "status": status,
            })

    # 对每个有效珠宝测试 DPS 贡献
    #
    # 两种测试方式：
    #   1) 普通珠宝（rare/magic/unique 无 GrantedPassive）：
    #      临时将 slot.selItemId=0 + spec.jewels[nodeId]=nil，移除珠宝物品
    #      CalcSetup:838 在 allocNodes[nodeId] 存在时处理珠宝 mod，
    #      同时清除 spec.jewels 确保 CalcSetup 不会从中读取物品。
    #
    #   2) GrantedPassive 珠宝（Megalomaniac, Forbidden Flame 等）：
    #      这类珠宝的核心收益来自 "Allocates X" 分配的天赋节点，
    #      仅移除物品不会影响 DPS（因为天赋已经被分配到 allocNodes 中）。
    #      需要额外通过 override.removeNodes 移除 granted 节点来评估。
    #      使用双 key 格式：removeNodes[node]=true + removeNodes[node.id]=true
    #      以兼容 CalcSetup:734（普通天赋）和 CalcSetup:1291（GrantedPassive）。
    for jewel in jewels:
        if jewel["status"] != "ok" or base_dps == 0:
            continue

        node_id = jewel["node_id"]
        slot_name = jewel["slot_name"]

        # 测试1：移除珠宝物品（对 rare jewel mods 有效）
        try:
            diff_result = lua.execute(f'''
                local build = _spike_build
                local slot = build.itemsTab.slots['{slot_name}']
                if not slot then return "ERR" end
                local originalId = slot.selItemId
                local originalJewel = build.spec.jewels[{node_id}]
                slot.selItemId = 0
                build.spec.jewels[{node_id}] = nil
                local env = calcs.initEnv(build, "MAIN")
                calcs.perform(env)
                local dps = env.player.output.TotalDPS or 0
                local ehp = env.player.output.TotalEHP or 0
                slot.selItemId = originalId
                build.spec.jewels[{node_id}] = originalJewel
                return tostring(dps) .. "|" .. tostring(ehp)
            ''')
            if diff_result and str(diff_result) != "ERR" and "|" in str(diff_result):
                parts = str(diff_result).split("|")
                after_dps = float(parts[0]) if parts else base_dps
                after_ehp = float(parts[1]) if len(parts) > 1 else base_ehp
            else:
                after_dps = base_dps
                after_ehp = base_ehp
            dps_delta = after_dps - base_dps
            ehp_delta = after_ehp - base_ehp
            # dps_pct/ehp_pct 表示珠宝的贡献（正值=正向贡献）
            jewel["dps_pct"] = round(-dps_delta / base_dps * 100, 2) if base_dps != 0 else 0.0
            jewel["ehp_pct"] = round(-ehp_delta / base_ehp * 100, 2) if base_ehp != 0 else 0.0
        except Exception as e:
            logger.warning("珠宝 DPS 诊断失败 %s: %s", slot_name, e)

        # 测试2：对有 GrantedPassive 的珠宝，额外测试移除 granted 节点的 DPS
        if jewel.get("granted_passives"):
            granted_names = jewel["granted_passives"]
            try:
                # 在 Lua 端查找 notableMap 中对应的节点 ID
                names_lua = ', '.join(f'"{name}"' for name in granted_names)
                granted_diff = lua.execute(f'''
                    local build = _spike_build
                    local tree = build.spec.tree
                    local removeNodes = {{}}
                    local names = {{ {names_lua} }}
                    for _, name in ipairs(names) do
                        local node = tree.notableMap[name]
                        if node then
                            removeNodes[node] = true
                            removeNodes[node.id] = true
                        end
                    end
                    local override = {{ removeNodes = removeNodes }}
                    local env = calcs.initEnv(build, "CALCULATOR", override)
                    calcs.perform(env)
                    return tostring(env.player.output.TotalDPS or 0) .. "|"
                           .. tostring(env.player.output.TotalEHP or 0)
                ''')
                if granted_diff and "|" in str(granted_diff):
                    parts = str(granted_diff).split("|")
                    gp_after_dps = float(parts[0])
                    gp_after_ehp = float(parts[1]) if len(parts) > 1 else base_ehp
                else:
                    gp_after_dps = base_dps
                    gp_after_ehp = base_ehp
                gp_dps_delta = gp_after_dps - base_dps
                gp_ehp_delta = gp_after_ehp - base_ehp
                # dps_pct/ehp_pct 表示贡献（正值=正向贡献）
                gp_dps_pct = round(-gp_dps_delta / base_dps * 100, 2) if base_dps != 0 else 0.0
                gp_ehp_pct = round(-gp_ehp_delta / base_ehp * 100, 2) if base_ehp != 0 else 0.0

                jewel["granted_dps_pct"] = gp_dps_pct
                jewel["granted_ehp_pct"] = gp_ehp_pct
                # 取物品移除和节点移除中影响更大的作为总 DPS 贡献
                if abs(gp_dps_pct) > abs(jewel["dps_pct"]):
                    jewel["dps_pct"] = gp_dps_pct
                    jewel["dps_source"] = "granted_passives"
                else:
                    jewel["dps_source"] = "item_mods"
                # 取物品移除和节点移除中影响更大的作为总 EHP 贡献
                if abs(gp_ehp_pct) > abs(jewel["ehp_pct"]):
                    jewel["ehp_pct"] = gp_ehp_pct
            except Exception as e:
                logger.warning("GrantedPassive DPS 诊断失败 %s: %s", slot_name, e)

    # 逐 mod DPS 测试：对每颗有效珠宝的每个 mod 逐个禁用后计算 DPS
    for jewel in jewels:
        if jewel["status"] != "ok" or base_dps == 0:
            continue
        if not jewel.get("mods"):
            continue

        node_id = jewel["node_id"]
        slot_name = jewel["slot_name"]
        mods = jewel["mods"]

        # 分离 GrantedPassive 和普通 mod
        granted_names = []
        granted_indices = []
        normal_indices = []
        for i, m in enumerate(mods):
            if m.get("name") == "GrantedPassive" and m.get("type") == "LIST":
                granted_names.append(m.get("value", ""))
                granted_indices.append(i)
            else:
                normal_indices.append(i)

        # 普通 mod：在 Lua 端对 item.modList 逐个禁用测试
        if normal_indices:
            # 构建 Lua 端需要测试的索引列表（1-based）
            lua_indices = ",".join(str(i + 1) for i in normal_indices)
            try:
                per_mod_result = lua.execute(f'''
                    local build = _spike_build
                    local slot = build.itemsTab.slots['{slot_name}']
                    if not slot then return "" end
                    local item = build.itemsTab.items[slot.selItemId]
                    if not item or not item.modList then return "" end

                    local results = {{}}
                    local ml = item.modList
                    local testIndices = {{{lua_indices}}}

                    for _, idx in ipairs(testIndices) do
                        local m = ml[idx]
                        if not m then
                            results[#results+1] = "ERR"
                        else
                            local origVal = m.value
                            local origType = m.type
                            local canZero = (origType == "BASE" or origType == "INC"
                                             or origType == "MORE")
                                            and type(origVal) == "number"
                            if canZero then
                                m.value = 0
                                local ok, dps, ehp = pcall(function()
                                    local env = calcs.initEnv(build, "MAIN")
                                    calcs.perform(env)
                                    return env.player.output.TotalDPS or 0,
                                           env.player.output.TotalEHP or 0
                                end)
                                m.value = origVal
                                if ok then
                                    results[#results+1] = tostring(dps) .. "|" .. tostring(ehp)
                                else
                                    results[#results+1] = "ERR"
                                end
                            else
                                table.remove(ml, idx)
                                local ok, dps, ehp = pcall(function()
                                    local env = calcs.initEnv(build, "MAIN")
                                    calcs.perform(env)
                                    return env.player.output.TotalDPS or 0,
                                           env.player.output.TotalEHP or 0
                                end)
                                table.insert(ml, idx, m)
                                if ok then
                                    results[#results+1] = tostring(dps) .. "|" .. tostring(ehp)
                                else
                                    results[#results+1] = "ERR"
                                end
                            end
                        end
                    end
                    return table.concat(results, ",")
                ''')

                if per_mod_result:
                    mod_values = str(per_mod_result).split(",")
                    for j, val_str in enumerate(mod_values):
                        if j < len(normal_indices) and val_str != "ERR" and "|" in val_str:
                            try:
                                parts = val_str.split("|")
                                after_dps = float(parts[0])
                                after_ehp = float(parts[1]) if len(parts) > 1 else base_ehp
                                # dps_pct/ehp_pct 表示贡献（正值=正向贡献）
                                mods[normal_indices[j]]["dps_pct"] = round(
                                    -(after_dps - base_dps) / base_dps * 100, 2) if base_dps != 0 else 0.0
                                mods[normal_indices[j]]["ehp_pct"] = round(
                                    -(after_ehp - base_ehp) / base_ehp * 100, 2) if base_ehp != 0 else 0.0
                            except (ValueError, ZeroDivisionError):
                                mods[normal_indices[j]]["dps_pct"] = None
                                mods[normal_indices[j]]["ehp_pct"] = None
                        elif j < len(normal_indices):
                            mods[normal_indices[j]]["dps_pct"] = None
                            mods[normal_indices[j]]["ehp_pct"] = None
            except Exception as e:
                logger.warning("珠宝普通 mod DPS 诊断失败 %s: %s", slot_name, e)

        # GrantedPassive mod：用 override.removeNodes 逐个天赋节点移除
        for gi, gname in zip(granted_indices, granted_names):
            if not gname:
                mods[gi]["dps_pct"] = None
                mods[gi]["ehp_pct"] = None
                continue
            try:
                # 用单行 Lua 避免多行字符串嵌套问题
                lua_code = (
                    'local build = _spike_build; '
                    'local tree = build.spec.tree; '
                    f'local node = tree.notableMap["{gname}"]; '
                    'if not node then return "NOT_FOUND" end; '
                    'local removeNodes = {}; '
                    'removeNodes[node] = true; '
                    'removeNodes[node.id] = true; '
                    'local override = { removeNodes = removeNodes }; '
                    'local env = calcs.initEnv(build, "CALCULATOR", override); '
                    'calcs.perform(env); '
                    'return tostring(env.player.output.TotalDPS or 0) .. "|"'
                    '.. tostring(env.player.output.TotalEHP or 0)'
                )
                r = lua.execute(lua_code)
                if r and str(r) != "NOT_FOUND" and "|" in str(r):
                    parts = str(r).split("|")
                    after_dps = float(parts[0])
                    after_ehp = float(parts[1]) if len(parts) > 1 else base_ehp
                    # dps_pct/ehp_pct 表示贡献（正值=正向贡献）
                    mods[gi]["dps_pct"] = round(
                        -(after_dps - base_dps) / base_dps * 100, 2) if base_dps != 0 else 0.0
                    mods[gi]["ehp_pct"] = round(
                        -(after_ehp - base_ehp) / base_ehp * 100, 2) if base_ehp != 0 else 0.0
                else:
                    mods[gi]["dps_pct"] = None
                    mods[gi]["ehp_pct"] = None
            except Exception as e:
                logger.warning("GrantedPassive 逐条 DPS 诊断失败 %s[%s]: %s",
                               slot_name, gname, e)
                mods[gi]["dps_pct"] = None
                mods[gi]["ehp_pct"] = None

    # 按 DPS+EHP 综合贡献降序排列
    jewels.sort(key=lambda x: abs(x.get("dps_pct", 0)) + abs(x.get("ehp_pct", 0)), reverse=True)
    return jewels




# --- what_if API (used by passive analysis) ---

def _diff_outputs(before: dict, after: dict, threshold: float = 0.001) -> dict:
    """对比两个 output dict，返回有变化的字段。

    Returns:
        {stat: (before_val, after_val, delta)} 仅包含有变化的字段
    """
    diff = {}
    all_keys = set(before.keys()) | set(after.keys())
    for k in all_keys:
        v1 = before.get(k, 0.0)
        v2 = after.get(k, 0.0)
        delta = v2 - v1
        if abs(delta) > threshold:
            diff[k] = (v1, v2, delta)
    return diff


# =============================================================================
# DPS 变化公式生成器（v1.0.6 等基准版本）
# =============================================================================
#
# 为每个 sensitivity profile 生成一行简洁的增量公式，
# 说明达到目标 DPS 增幅所需的投入。
#
# 示例：
#   Damage INC:          "INC 238%→297%, 需要 +59 → DPS +30.0%"
#   Damage MORE:         "需要 ×1.30 独立乘区 (+30) → DPS +30.0%"
#   CritMulti INC:       "INC 200%→376%, 需要 +176 → DPS +30.0%"
#   Speed INC:           "INC 50%→95%, 需要 +45 → DPS +30.0%"
#   Penetration:         "无法在搜索范围内达到目标"




def what_if_nodes(lua, calcs, add: list[int] = None, remove: list[int] = None,
                  baseline: dict = None) -> dict:
    """临时增删天赋点并对比。

    使用 POB 原生 override.addNodes / override.removeNodes 机制，
    不修改 build 对象。

    Args:
        add: 要临时添加的节点 ID 列表
        remove: 要临时移除的节点 ID 列表
        baseline: 基线 output

    Returns:
        {stat: (before, after, delta)} 差异字典
    """
    if baseline is None:
        baseline = calculate(lua, calcs)

    add = add or []
    remove = remove or []

    # 构建 override Lua 表达式
    # CalcSetup.lua 中 addNodes/removeNodes 使用两种不同的 key 格式：
    #   第 707 行：for node in pairs(override.addNodes) — node 对象作为 key
    #   第 734 行：override.removeNodes[node] — node 对象作为 key（普通天赋）
    #   第 1291 行：override.removeNodes[node.id] — 整数 node.id 作为 key（GrantedPassive）
    # 必须同时设置两种 key 才能正确处理 GrantedPassive 珠宝分配的天赋节点。
    add_ids = ','.join(str(nid) for nid in add)
    remove_ids = ','.join(str(nid) for nid in remove)

    result = lua.execute(f'''
        local build = _spike_build
        local addNodes = {{}}
        local removeNodes = {{}}

        -- addNodes: CalcSetup:707 uses `for node in pairs(override.addNodes)`
        -- key = node object
        for _, nid in ipairs({{ {add_ids} }}) do
            local node = build.spec.nodes[nid]
            if node then addNodes[node] = true end
        end

        -- removeNodes: CalcSetup has TWO key formats:
        --   line 734:  removeNodes[node]    (node object) — regular allocNodes
        --   line 1291: removeNodes[node.id] (integer)     — GrantedPassive nodes
        -- We set both keys so both code paths work correctly.
        for _, nid in ipairs({{ {remove_ids} }}) do
            local node = build.spec.nodes[nid]
            if node then
                removeNodes[node] = true     -- for CalcSetup:734 (regular passives)
                removeNodes[node.id] = true  -- for CalcSetup:1291 (GrantedPassive)
            end
        end

        local override = {{
            addNodes = addNodes,
            removeNodes = removeNodes,
        }}
        local env = calcs.initEnv(build, "CALCULATOR", override)
        calcs.perform(env)
        local output = env.player.output
        local lines = {{}}
        for k, v in pairs(output) do
            if type(v) == "number" then
                lines[#lines+1] = k .. "=" .. tostring(v)
            end
        end
        return table.concat(lines, "|")
    ''')

    after = {}
    if result:
        for pair in str(result).split('|'):
            if '=' in pair:
                k, v = pair.split('=', 1)
                try:
                    after[k] = float(v)
                except ValueError:
                    pass

    return _diff_outputs(baseline, after)


