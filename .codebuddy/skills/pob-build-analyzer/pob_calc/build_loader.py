#!/usr/bin/env python3
"""
构筑数据加载器：将 BuildInfo 灌入 Lua build 对象。

职责：
  - init_build_object:  创建 Lua 端 _spike_build 最小 build 对象
  - load_tree:          加载天赋树数据 + 分配节点
  - load_skills:        加载技能组 + gem 解析
  - load_items:         加载装备 + armourData/spirit 修复
  - load_config:        加载 Config 输入 + 模拟 BuildModList
  - load_all:           按正确顺序调用全部加载函数
"""
import logging
from .decoder import decode_tree_url
from .compat import parse_item_spec_values, postprocess_unparsed_mods

logger = logging.getLogger(__name__)


def init_build_object(lua, build_info: dict):
    """在 Lua 端创建最小 build 对象 _spike_build。

    构造 skillsTab, itemsTab, spec, configTab, calcsTab, partyTab 等
    CalcSetup.initEnv 所需的全部字段。

    从 build_info 读取 classId/ascendClassId，不硬编码任何职业。
    tree.classes 的完整数据由 load_tree 从 tree.lua 填充。
    """
    # 从 XML 解析出的 classId（POB 内部 0-based index）
    class_id = int(build_info.get('classId', '0'))
    ascend_class_id = int(build_info.get('ascendClassId', '0'))
    class_name = build_info.get('className', '')
    ascend_class_name = build_info.get('ascendClassName', '')

    lua.execute('''
        local build = {}
        build.data = data
        build.characterLevel = ''' + str(build_info['level']) + '''
        build.mainSocketGroup = ''' + str(build_info['mainSocketGroup']) + '''

        -- configTab
        build.configTab = {
            input = {},
            placeholder = {},
            modList = new("ModList"),
            enemyModList = new("ModList"),
            enemyLevel = nil,
        }

        -- calcsTab
        build.calcsTab = {
            input = {},
            mainEnv = nil,
        }

        -- partyTab
        local partyModDB = new("ModDB")
        build.partyTab = {
            enemyModList = new("ModList"),
            enableExportBuffs = false,
            actor = {
                modDB = partyModDB,
                output = {},
                weaponData1 = {},
                Aura = {},
                Curse = {},
                Warcry = {},
                Link = {},
            },
        }

        -- itemsTab
        build.itemsTab = {
            activeItemSet = { useSecondWeaponSet = false },
            lastWeaponFlagState = {},
            orderedSlots = {},
            items = {},
            slots = {},
            ValidateWeaponSlots = function(self, state) end,
        }

        -- spec（classId/ascendClassId 从 XML 读取，不硬编码）
        build.spec = {
            nodes = {},
            allocNodes = {},
            jewels = {},
            allocSubgraphNodes = {},
            masterySelections = {},
            curClassId = ''' + str(class_id) + ''',
            curAscendClassId = ''' + str(ascend_class_id) + ''',
            curSecondaryAscendClassId = 0,
            curClassName = "''' + class_name.replace('"', '\\"') + '''",
            curAscendClassName = "''' + ascend_class_name.replace('"', '\\"') + '''",
            treeVersion = "0_4",
            allocatedNotableCount = 0,
            allocatedSmithBodyArmourNodeCount = 0,
            allocatedMasteryCount = 0,
            allocatedMasteryTypeCount = 0,
            allocatedMasteryTypes = {},
            tree = {
                characterData = nil,
                classes = {},
                notableMap = {},
                ascendNameMap = {},
                keystoneMap = {},
                classNameMap = {},
                classIntegerIdMap = {},
            },
        }

        -- skillsTab
        build.skillsTab = {
            socketGroupList = {},
            displayGroup = nil,
            ProcessSocketGroup = function(self, group)
                if group and group.gemList then
                    for _, gem in ipairs(group.gemList) do
                        _spike_process_gem(gem)
                    end
                end
            end,
        }

        _spike_build = build
    ''')


def load_skills(lua, build_info: dict) -> int:
    """将 XML 中的技能组加载到 Lua 端，用 data.gems 填充 gemData。

    Returns:
        成功加载的技能组数量
    """
    skill_groups = build_info.get('skillGroups', [])
    if not skill_groups:
        return 0

    # 注册 gem 处理辅助函数
    lua.execute('''
        function _spike_process_gem(gemInstance)
            gemInstance.color = "^8"
            gemInstance.nameSpec = gemInstance.nameSpec or ""
            if gemInstance.gemId then
                gemInstance.gemData = data.gems[gemInstance.gemId]
                if not gemInstance.gemData then
                    local fixed = gemInstance.gemId:gsub("/Gem/", "/Gems/")
                    if fixed ~= gemInstance.gemId then
                        gemInstance.gemData = data.gems[fixed]
                        if gemInstance.gemData then
                            gemInstance.gemId = fixed
                        end
                    end
                end
                if not gemInstance.gemData and data.gemsByGameId[gemInstance.gemId] then
                    for variantId, gem in pairs(data.gemsByGameId[gemInstance.gemId]) do
                        gemInstance.gemData = gem
                        gemInstance.gemId = gem.id
                        break
                    end
                end
                if gemInstance.gemData then
                    if not string.match(gemInstance.nameSpec, "^Companion:") and not string.match(gemInstance.nameSpec, "^Spectre:") then
                        gemInstance.nameSpec = gemInstance.gemData.name
                    end
                    gemInstance.skillId = gemInstance.gemData.grantedEffectId
                end
            elseif gemInstance.skillId then
                local skillEffect = data.skills[gemInstance.skillId]
                local gemId = skillEffect and data.gemForSkill[skillEffect]
                if gemId then
                    gemInstance.gemData = data.gems[gemId]
                else
                    gemInstance.grantedEffect = skillEffect or data.skills[gemInstance.skillId]
                end
                if gemInstance.triggered and gemInstance.grantedEffect then
                    if gemInstance.grantedEffect.levels[gemInstance.level] then
                        gemInstance.grantedEffect.levels[gemInstance.level].cost = {}
                    end
                end
            end
            if gemInstance.gemData and gemInstance.gemData.grantedEffect and gemInstance.gemData.grantedEffect.unsupported then
                gemInstance.gemData = nil
            end
            if gemInstance.gemData or gemInstance.grantedEffect then
                local grantedEffect = gemInstance.grantedEffect or gemInstance.gemData.grantedEffect
                if grantedEffect.color == 1 then gemInstance.color = colorCodes.STRENGTH
                elseif grantedEffect.color == 2 then gemInstance.color = colorCodes.DEXTERITY
                elseif grantedEffect.color == 3 then gemInstance.color = colorCodes.INTELLIGENCE
                else gemInstance.color = colorCodes.NORMAL end
                calcLib.validateGemLevel(gemInstance)
                if gemInstance.gemData then
                    gemInstance.reqLevel = grantedEffect.levels[gemInstance.level] and grantedEffect.levels[gemInstance.level].levelRequirement or 0
                    gemInstance.reqStr = calcLib.getGemStatRequirement(gemInstance.reqLevel, gemInstance.gemData.reqStr, grantedEffect.support)
                    gemInstance.reqDex = calcLib.getGemStatRequirement(gemInstance.reqLevel, gemInstance.gemData.reqDex, grantedEffect.support)
                    gemInstance.reqInt = calcLib.getGemStatRequirement(gemInstance.reqLevel, gemInstance.gemData.reqInt, grantedEffect.support)
                end
            end
        end
    ''')

    loaded = 0
    for i, group in enumerate(skill_groups):
        gems_lua = []
        for gem in group.get('gems', []):
            gem_id = gem.get('gemId', '').replace("'", "\\'")
            skill_id = gem.get('skillId', '').replace("'", "\\'")
            name = gem.get('nameSpec', '').replace("'", "\\'")
            level = int(gem.get('level', '1'))
            quality = int(gem.get('quality', '0'))
            enabled = gem.get('enabled', 'true') == 'true'
            eg1 = gem.get('enableGlobal1', 'true') == 'true'
            eg2 = gem.get('enableGlobal2', 'false') == 'true'
            count_str = gem.get('count', '1')
            count = int(count_str) if count_str and count_str != 'nil' else 1
            skill_minion = gem.get('skillMinion', '')
            skill_minion_skill = gem.get('skillMinionSkill', '')

            gems_lua.append(f'''{{
                gemId = "{gem_id}",
                skillId = "{skill_id}",
                nameSpec = "{name}",
                level = {level},
                quality = {quality},
                enabled = {str(enabled).lower()},
                enableGlobal1 = {str(eg1).lower()},
                enableGlobal2 = {str(eg2).lower()},
                count = {count},
                statSet = {{}},
                statSetCalcs = {{}},
                skillMinionSkillStatSetIndexLookup = {{}},
                skillMinionSkillStatSetIndexLookupCalcs = {{}},
                {f'skillMinion = "{skill_minion}",' if skill_minion else ''}
                {f'skillMinionSkill = {skill_minion_skill},' if skill_minion_skill and skill_minion_skill != '' else ''}
            }}''')

        gems_str = ',\n                '.join(gems_lua)

        enabled = group.get('enabled', 'true') == 'true'
        include_dps = group.get('includeInFullDPS', 'nil')
        include_dps_lua = 'true' if include_dps == 'true' else ('false' if include_dps == 'false' else 'nil')
        main_skill = group.get('mainActiveSkill', '1')
        main_skill = int(main_skill) if main_skill and main_skill != 'nil' else 1
        main_skill_calcs = group.get('mainActiveSkillCalcs', '1')
        main_skill_calcs = int(main_skill_calcs) if main_skill_calcs and main_skill_calcs != 'nil' else 1
        slot = group.get('slot', '')
        source = group.get('source', '').replace("'", "\\'")
        label = group.get('label', '').replace("'", "\\'")

        try:
            lua.execute(f'''
                local group = {{
                    enabled = {str(enabled).lower()},
                    includeInFullDPS = {include_dps_lua},
                    label = '{label}',
                    slot = {f'"{slot}"' if slot else 'nil'},
                    source = {f"'{source}'" if source else 'nil'},
                    mainActiveSkill = {main_skill},
                    mainActiveSkillCalcs = {main_skill_calcs},
                    displaySkillList = {{}},
                    displaySkillListCalcs = {{}},
                    displayGemList = {{}},
                    gemList = {{
                        {gems_str}
                    }},
                }}
                for _, gem in ipairs(group.gemList) do
                    _spike_process_gem(gem)
                end
                table.insert(_spike_build.skillsTab.socketGroupList, group)
            ''')
            loaded += 1
        except Exception as e:
            label_info = label or f"group#{i+1}"
            logger.warning("技能组加载失败 [%s]: %s", label_info, e)

    return loaded


def load_items(lua, build_info: dict) -> int:
    """将 XML 中的装备加载到 Lua 端，用 new("Item") 解析。

    包含两个修复：
    1. armourData 覆盖：用原始文本的 spec 值覆盖 BuildModListForSlotNum 重算值
    2. spiritValue 覆盖：同上

    Returns:
        成功加载的装备数量
    """
    items = build_info.get('items', [])
    item_slots = build_info.get('itemSlots', {})
    if not items:
        return 0

    loaded = 0
    for item_data in items:
        item_id = item_data['id']
        raw_text = item_data['text']
        if not raw_text:
            continue

        spec_values = parse_item_spec_values(raw_text)
        raw_escaped = raw_text.replace('\\', '\\\\').replace("'", "\\'").replace('\n', '\\n').replace('\r', '')

        # armourData 覆盖
        armour_fix_lua = ""
        has_armour = any(k in spec_values for k in ('EnergyShield', 'Evasion', 'Armour', 'Ward'))
        if has_armour:
            overrides = []
            for key in ('EnergyShield', 'Evasion', 'Armour', 'Ward'):
                if key in spec_values:
                    overrides.append(f'item.armourData.{key} = {spec_values[key]}')
            armour_fix_lua = f'''
                    if item.armourData then
                        {"; ".join(overrides)}
                    end'''

        spirit_fix_lua = ""
        if 'Spirit' in spec_values:
            spirit_fix_lua = f'''
                    item.spiritValue = {spec_values["Spirit"]}'''

        try:
            result = lua.execute(f'''
                local rawText = '{raw_escaped}'
                local ok, item = pcall(new, "Item", rawText)
                if ok and item and item.base then
                    item.id = {item_id}
                    _spike_build.itemsTab.items[{item_id}] = item{armour_fix_lua}{spirit_fix_lua}
                    return tostring(item.name or "?")
                else
                    return nil
                end
            ''')
            if result:
                loaded += 1
        except Exception as e:
            logger.warning("装备加载失败 [id=%s]: %s", item_id, e)

    # 装备槽位
    slot_names = [
        "Weapon 1", "Weapon 2", "Helmet", "Body Armour", "Gloves",
        "Boots", "Amulet", "Ring 1", "Ring 2", "Ring 3", "Belt",
        "Weapon 1 Swap", "Weapon 2 Swap",
        "Flask 1", "Flask 2", "Flask 3", "Flask 4", "Flask 5",
        "Charm 1", "Charm 2", "Charm 3",
        "Arm 1", "Arm 2", "Leg 1", "Leg 2",
    ]

    for slot_name in slot_names:
        slot_info = item_slots.get(slot_name, {})
        sel_item_id = slot_info.get('itemId', 0) if slot_info else 0
        active = slot_info.get('active', False) if slot_info else False

        weapon_set = 'nil'
        if 'Swap' in slot_name:
            weapon_set = '2'
        elif slot_name.startswith('Weapon'):
            weapon_set = '1'

        slot_num = 1
        if '2' in slot_name and slot_name.startswith('Weapon'):
            slot_num = 2

        slot_name_escaped = slot_name.replace("'", "\\'")
        lua.execute(f'''
            local slot = {{
                slotName = '{slot_name_escaped}',
                selItemId = {sel_item_id},
                nodeId = nil,
                weaponSet = {weapon_set},
                slotNum = {slot_num},
                active = {str(active).lower()},
            }}
            table.insert(_spike_build.itemsTab.orderedSlots, slot)
            _spike_build.itemsTab.slots['{slot_name_escaped}'] = slot
        ''')

    # 珠宝插槽
    for socket in build_info.get('sockets', []):
        node_id = socket.get('nodeId', '')
        item_id_str = socket.get('itemId', '0')
        if node_id and item_id_str:
            lua.execute(f'''
                local slot = {{
                    slotName = 'Jewel {node_id}',
                    selItemId = {item_id_str},
                    nodeId = {node_id},
                    weaponSet = nil,
                    slotNum = 1,
                    active = true,
                }}
                table.insert(_spike_build.itemsTab.orderedSlots, slot)
                _spike_build.itemsTab.slots['Jewel {node_id}'] = slot
                _spike_build.spec.jewels[{node_id}] = {item_id_str}
            ''')

    return loaded


def load_tree(lua, build_info: dict) -> int:
    """加载天赋树数据到 Lua 端，解析所有节点的 modifiers 并分配。

    Returns:
        已分配的节点数量
    """
    node_ids, mastery_selections = decode_tree_url(build_info.get('treeURL', ''))
    if not node_ids:
        return 0

    tree_version = build_info.get('treeVersion', '0_4')

    # Step 1: 加载 tree.lua，处理所有节点
    loaded = lua.execute(f'''
        local treeFile = io.open(GetScriptPath() .. "TreeData/{tree_version}/tree.lua", "r")
        if not treeFile then
            return "ERR:tree.lua not found"
        end
        local treeText = treeFile:read("*a")
        treeFile:close()

        local treeData = assert(load(treeText))()

        for i = 0, 6 do
            treeData.classes[i] = treeData.classes[i + 1]
            treeData.classes[i + 1] = nil
        end

        local classNameMap = {{}}
        local classIntegerIdMap = {{}}
        local ascendNameMap = {{}}
        local keystoneMap = {{}}
        local notableMap = {{}}
        local ascendancyMap = {{}}

        for classId, class in pairs(treeData.classes) do
            class.classes = class.ascendancies
            class.classes[0] = {{ name = "None" }}
            classNameMap[class.name] = classId
            classIntegerIdMap[class.integerId] = classId
            for ascId, asc in pairs(class.classes) do
                ascendNameMap[asc.id or asc.name] = {{
                    classId = classId,
                    class = class,
                    ascendClassId = ascId,
                    ascendClass = asc
                }}
            end
        end

        local nodeMap = {{}}
        local mastery_effects = {{}}
        treeData.nodes.root = nil

        for _, node in pairs(treeData.nodes) do
            node.id = node.skill
            node.g = node.group
            node.o = node.orbit
            node.oidx = node.orbitIndex
            node.dn = node.name
            node.sd = node.stats
            node.__index = node
            node.linkedId = {{}}
            node.allocMode = 0
            node.alloc = false
            node.nodesInRadius = node.nodesInRadius or {{}}
            nodeMap[node.id] = node

            node.modKey = ""
            node.mods = {{}}
            node.modList = new("ModList")
            if node.sd then
                -- 先处理换行符
                local si = 1
                while node.sd[si] do
                    if node.sd[si]:match("\\n") then
                        local line = node.sd[si]
                        local il = si
                        table.remove(node.sd, si)
                        for part in line:gmatch("[^\\n]+") do
                            table.insert(node.sd, il, part)
                            il = il + 1
                        end
                    end
                    si = si + 1
                end

                -- 使用 POB 桌面版 ProcessStats 相同的多行合并逻辑
                local i = 1
                while node.sd[i] do
                    local line = node.sd[i]
                    local list, extra = modLib.parseMod(line)
                    if not list or extra then
                        -- 尝试合并后续行再解析
                        local endI = i + 1
                        while node.sd[endI] do
                            local comb = line
                            for ci = i + 1, endI do
                                comb = comb .. " " .. node.sd[ci]
                            end
                            list, extra = modLib.parseMod(comb, true)
                            if list and not extra then
                                -- 成功，为被合并的行设置空 mod
                                for ci = i + 1, endI do
                                    node.mods[ci] = {{ list = {{}} }}
                                end
                                break
                            end
                            endI = endI + 1
                        end
                    end
                    if list and not extra then
                        node.mods[i] = {{ list = list, extra = extra }}
                        for _, mod in ipairs(list) do
                            node.modKey = node.modKey .. modLib.formatMod(mod) .. "&"
                        end
                    elseif list then
                        node.mods[i] = {{ list = list, extra = extra }}
                    end
                    i = i + 1
                    while node.mods[i] do
                        i = i + 1
                    end
                end
                -- 构建最终 modList（仅无 extra 的行）
                for mi = 1, #node.sd do
                    local mod = node.mods[mi]
                    if mod and mod.list and not mod.extra then
                        for _, m in ipairs(mod.list) do
                            m = modLib.setSource(m, "Tree:"..node.id)
                            node.modList:AddMod(m)
                        end
                    end
                end
            end

            if node.classesStart then
                node.type = "ClassStart"
            elseif node.isAscendancyStart then
                node.type = "AscendClassStart"
            elseif node.isOnlyImage then
                node.type = "OnlyImage"
            elseif node.isJewelSocket then
                node.type = "Socket"
            elseif node.ks or node.isKeystone then
                node.type = "Keystone"
                keystoneMap[node.dn] = node
                keystoneMap[node.dn:lower()] = node
                node.keystoneMod = modLib.createMod("Keystone", "LIST", node.dn, "Tree:"..node.id)
            elseif node["not"] or node.isNotable then
                node.type = "Notable"
                if node.ascendancyName then
                    ascendancyMap[node.dn:lower()] = node
                else
                    notableMap[node.dn:lower()] = node
                end
            elseif node.isMastery then
                node.type = "Mastery"
                if node.masteryEffects then
                    for _, effect in ipairs(node.masteryEffects) do
                        mastery_effects[effect.effect] = effect.stats
                    end
                end
            else
                node.type = "Normal"
            end
        end

        local tree = _spike_build.spec.tree
        tree.nodes = nodeMap
        tree.classes = treeData.classes
        tree.classNameMap = classNameMap
        tree.classIntegerIdMap = classIntegerIdMap
        tree.ascendNameMap = ascendNameMap
        tree.keystoneMap = keystoneMap
        tree.notableMap = notableMap
        tree.ascendancyMap = ascendancyMap
        tree.masteryEffects = mastery_effects

        -- 处理 isAttribute 节点的 options
        for _, node in pairs(nodeMap) do
            if (node.isSwitchable or node.isAttribute) and node.options then
                for optKey, switchNode in pairs(node.options) do
                    if node.isAttribute then
                        switchNode.id = node.id
                    end
                    switchNode.dn = switchNode.name
                    switchNode.sd = switchNode.stats
                    switchNode.modKey = ""
                    switchNode.mods = {{}}
                    switchNode.modList = new("ModList")
                    if switchNode.sd then
                        -- 先处理换行符
                        local si = 1
                        while switchNode.sd[si] do
                            if switchNode.sd[si]:match("\\n") then
                                local sline = switchNode.sd[si]
                                local il = si
                                table.remove(switchNode.sd, si)
                                for part in sline:gmatch("[^\\n]+") do
                                    table.insert(switchNode.sd, il, part)
                                    il = il + 1
                                end
                            end
                            si = si + 1
                        end

                        -- 多行合并解析（同主节点逻辑）
                        local i = 1
                        while switchNode.sd[i] do
                            local line = switchNode.sd[i]
                            local list, extra = modLib.parseMod(line)
                            if not list or extra then
                                local endI = i + 1
                                while switchNode.sd[endI] do
                                    local comb = line
                                    for ci = i + 1, endI do
                                        comb = comb .. " " .. switchNode.sd[ci]
                                    end
                                    list, extra = modLib.parseMod(comb, true)
                                    if list and not extra then
                                        for ci = i + 1, endI do
                                            switchNode.mods[ci] = {{ list = {{}} }}
                                        end
                                        break
                                    end
                                    endI = endI + 1
                                end
                            end
                            if list and not extra then
                                switchNode.mods[i] = {{ list = list, extra = extra }}
                                for _, mod in ipairs(list) do
                                    switchNode.modKey = switchNode.modKey .. modLib.formatMod(mod) .. "&"
                                end
                            elseif list then
                                switchNode.mods[i] = {{ list = list, extra = extra }}
                            end
                            i = i + 1
                            while switchNode.mods[i] do
                                i = i + 1
                            end
                        end
                        for mi = 1, #switchNode.sd do
                            local mod = switchNode.mods[mi]
                            if mod and mod.list and not mod.extra then
                                for _, m in ipairs(mod.list) do
                                    m = modLib.setSource(m, "Tree:"..switchNode.id)
                                    switchNode.modList:AddMod(m)
                                end
                            end
                        end
                    end
                end
            end
        end

        _spike_build.spec.nodes = nodeMap

        local classInternalId = ''' + str(build_info.get('classInternalId', '10')) + '''
        local newClassId = classIntegerIdMap[classInternalId]
        if newClassId then
            _spike_build.spec.curClassId = newClassId
        end

        local count = 0
        for _ in pairs(nodeMap) do count = count + 1 end
        return count
    ''')

    if isinstance(loaded, str) and str(loaded).startswith("ERR:"):
        return 0

    # Step 2: AttributeOverride + 分配节点
    node_ids_lua = '{' + ','.join(str(n) for n in node_ids) + '}'

    mastery_lua = '{'
    for nid, eid in mastery_selections.items():
        mastery_lua += f'[{nid}]={eid},'
    mastery_lua += '}'

    weapon_sets = build_info.get('weaponSets', {})
    ws_lua = '{'
    for nid, ws in weapon_sets.items():
        ws_lua += f'[{nid}]={ws},'
    ws_lua += '}'

    attr_override = build_info.get('attrOverride', {'str': [], 'dex': [], 'int': []})
    str_nodes = '{' + ','.join(str(n) for n in attr_override['str']) + '}'
    dex_nodes = '{' + ','.join(str(n) for n in attr_override['dex']) + '}'
    int_nodes = '{' + ','.join(str(n) for n in attr_override['int']) + '}'

    result = lua.execute(f'''
        local allocNodeIds = {node_ids_lua}
        local masterySelections = {mastery_lua}
        local weaponSets = {ws_lua}
        local strOverrides = {str_nodes}
        local dexOverrides = {dex_nodes}
        local intOverrides = {int_nodes}
        local nodeMap = _spike_build.spec.nodes
        local tree = _spike_build.spec.tree

        local hashOverrides = {{}}
        local function switchAttributeNode(nodeId, attributeIndex)
            local node = nodeMap[nodeId]
            if node and node.isAttribute and node.options then
                local option = node.options[attributeIndex]
                if option then
                    node.dn = option.dn or option.name
                    node.sd = option.sd or option.stats
                    node.mods = option.mods or {{}}
                    node.modKey = option.modKey or ""
                    node.modList = new("ModList")
                    if option.modList then
                        node.modList:AddList(option.modList)
                    end
                    hashOverrides[nodeId] = node
                end
            end
        end

        for _, nid in ipairs(strOverrides) do switchAttributeNode(nid, 1) end
        for _, nid in ipairs(dexOverrides) do switchAttributeNode(nid, 2) end
        for _, nid in ipairs(intOverrides) do switchAttributeNode(nid, 3) end

        _spike_build.spec.hashOverrides = hashOverrides

        local allocNodes = {{}}
        local allocNotableCount = 0
        local allocMasteryCount = 0
        _spike_build.spec.masterySelections = masterySelections

        for _, nodeId in ipairs(allocNodeIds) do
            local node = nodeMap[nodeId]
            if node then
                node.alloc = true
                node.allocMode = weaponSets[nodeId] or 0
                allocNodes[nodeId] = node

                local masteryEffectId = masterySelections[nodeId]
                if masteryEffectId and tree.masteryEffects[masteryEffectId] then
                    local stats = tree.masteryEffects[masteryEffectId]
                    for _, line in ipairs(stats) do
                        local list, extra = modLib.parseMod(line)
                        if list then
                            for _, mod in ipairs(list) do
                                node.modList:AddMod(mod)
                            end
                        end
                    end
                end

                if node.type == "Notable" then
                    allocNotableCount = allocNotableCount + 1
                elseif node.type == "Mastery" then
                    allocMasteryCount = allocMasteryCount + 1
                end
            end
        end

        _spike_build.spec.allocNodes = allocNodes
        _spike_build.spec.allocatedNotableCount = allocNotableCount
        _spike_build.spec.allocatedMasteryCount = allocMasteryCount
        _spike_build.spec.allocatedMasteryTypes = {{}}
        _spike_build.spec.allocatedMasteryTypeCount = 0

        local alloc_count = 0
        for _ in pairs(allocNodes) do alloc_count = alloc_count + 1 end
        return alloc_count
    ''')

    return int(result) if result and not isinstance(result, str) else 0


def load_config(lua, build_info: dict) -> int:
    """将 XML Config 加载到 Lua 端并模拟 ConfigTab:BuildModList。

    Returns:
        成功加载的配置项数量
    """
    config_inputs = build_info.get('configInputs', [])
    g = lua.globals()
    build = g._spike_build
    config_tab = build.configTab

    loaded = 0
    for inp in config_inputs:
        name = inp['name']
        target = config_tab.input if inp['type'] == 'Input' else config_tab.placeholder
        try:
            if inp['boolean'] is not None:
                target[name] = inp['boolean'] == 'true'
                loaded += 1
            elif inp['number'] is not None:
                target[name] = float(inp['number'])
                loaded += 1
            elif inp['string'] is not None:
                target[name] = inp['string']
                loaded += 1
        except Exception as e:
            logger.warning("配置项加载失败 [%s]: %s", name, e)

    # 模拟 ConfigTab:BuildModList
    lua.execute('''
        local configSettings = LoadModule("Modules/ConfigOptions")
        if not configSettings then return end

        local modList = new("ModList")
        local enemyModList = new("ModList")
        local input = _spike_build.configTab.input
        local placeholder = _spike_build.configTab.placeholder

        for _, varData in ipairs(configSettings) do
            if varData.apply then
                local varName = varData.var
                if varData.type == "check" then
                    local val = input[varName]
                    if val == nil and varData.defaultState then
                        val = true
                    end
                    if val then
                        pcall(varData.apply, true, modList, enemyModList, _spike_build)
                    end
                elseif varData.type == "count" or varData.type == "integer" or varData.type == "countAllowZero" or varData.type == "float" then
                    local val = input[varName]
                    if val and (val ~= 0 or varData.type ~= "count") then
                        pcall(varData.apply, val, modList, enemyModList, _spike_build)
                    elseif placeholder[varName] and (placeholder[varName] ~= 0 or varData.type ~= "count") then
                        pcall(varData.apply, placeholder[varName], modList, enemyModList, _spike_build)
                    end
                elseif varData.type == "list" then
                    local val = input[varName]
                    if val == nil and varData.list and varData.defaultIndex then
                        local defaultEntry = varData.list[varData.defaultIndex]
                        if defaultEntry then
                            val = defaultEntry.val
                        end
                    end
                    if val then
                        pcall(varData.apply, val, modList, enemyModList, _spike_build)
                    end
                elseif varData.type == "text" then
                    if input[varName] then
                        pcall(varData.apply, input[varName], modList, enemyModList, _spike_build)
                    end
                end
            end
        end

        _spike_build.configTab.modList = modList
        _spike_build.configTab.enemyModList = enemyModList
    ''')

    return loaded


def _inject_unimplemented_mods(lua, input_json: str) -> int:
    """从 pob_unimplemented_effects.yaml 读取配置，为满足条件的未实现效果注入 mod。

    通用逻辑：
    1. 加载 YAML 配置
    2. 检测构筑中存在的技能（通过 skillId）
    3. 检查 require_build_condition 是否被 input 满足
    4. 满足条件则注入 mod 到 configTab.modList

    Returns:
        注入的 mod 数量
    """
    import json
    from pathlib import Path

    # 加载 YAML 配置
    config_path = Path(__file__).parent.parent / "config" / "pob_unimplemented_effects.yaml"
    if not config_path.exists():
        return 0

    try:
        import yaml
        with open(config_path, encoding='utf-8') as f:
            config = yaml.safe_load(f) or {}
    except Exception as e:
        logger.warning("加载未实现效果配置失败: %s", e)
        return 0

    skills_config = config.get("skills", {})
    if not skills_config:
        return 0

    # 从 input JSON 获取已配置的条件
    try:
        input_data = json.loads(input_json)
    except (json.JSONDecodeError, TypeError):
        input_data = {}

    # 构建条件映射：require_build_condition → input key → 是否满足
    condition_map = {
        "FullMana": input_data.get("conditionFullMana", False),
        "FullLife": input_data.get("conditionFullLife", False),
        "LowLife": input_data.get("conditionLowLife", False),
        "FullEnergyShield": input_data.get("conditionFullEnergyShield", False),
    }

    # 注入列表
    inject_list = []
    for skill_name, skill_config in skills_config.items():
        # 跳过精魄辅助：已装备的精魄辅助 POB 会原生计算其效果，
        # 不需要模拟注入。模拟仅用于推荐测试（_test_add_spirit_support）。
        if skill_config.get("skill_type") == "spirit_support":
            continue

        effects = skill_config.get("effects", [])
        if not effects:
            continue

        # 检查检测条件
        detect = skill_config.get("detect", {})
        detect_type = detect.get("type", "gem_name")

        # 构造 Lua 检测代码（返回 boolean 表达式，不用 return）
        if detect_type == "skill_id":
            skill_id = detect.get("skill_id", "")
            check_lua = f'skillIds["{skill_id}"] == true'
        elif detect_type == "gem_name":
            name = detect.get("name", skill_name)
            check_lua = f'skillNames["{name}"] == true'
        else:
            continue

        # 检查 build condition
        req_cond = skill_config.get("require_build_condition", "")
        if req_cond and not condition_map.get(req_cond, False):
            continue

        # 收集要注入的 mod
        for eff in effects:
            if eff.get("type") != "mod":
                continue
            mod_name = eff.get("mod_name", "")
            mod_type = eff.get("mod_type", "BASE")
            value = eff.get("value")
            source = eff.get("source", "unimpl_config")
            mod_flag = eff.get("mod_flag", "")
            if mod_name is None:
                continue

            if value is not None:
                # 固定值
                inject_list.append({
                    "skill_name": skill_name,
                    "detect_lua": check_lua,
                    "mod_name": mod_name,
                    "mod_type": mod_type,
                    "value": int(value) if isinstance(value, (int, float)) else value,
                    "source": source,
                    "mod_flag": mod_flag,
                })
            else:
                # value=null: 检查 dynamic_value 配置
                dynamic_cfg = skill_config.get("dynamic_value", {})
                dyn_type = dynamic_cfg.get("type", "")

                if dyn_type == "charge_based":
                    # 电荷型动态值：PowerChargesMax × (per_charge + quality × quality_per_charge)
                    charge_stat = dynamic_cfg.get("charge_stat", "PowerChargesMax")
                    per_charge = dynamic_cfg.get("per_charge_value", 0)
                    quality_per = dynamic_cfg.get("quality_per_charge", 0)
                    inject_list.append({
                        "skill_name": skill_name,
                        "detect_lua": check_lua,
                        "mod_name": mod_name,
                        "mod_type": mod_type,
                        "value": None,
                        "source": source,
                        "mod_flag": mod_flag,
                        "dynamic_type": "charge_based",
                        "charge_stat": charge_stat,
                        "per_charge_value": per_charge,
                        "quality_per_charge": quality_per,
                        "stat_skill_id": detect.get("skill_id", ""),
                    })
                else:
                    # 原有逻辑：从 statSets.levels 读取
                    stat_skill_id = skill_config.get("stat_skill_id", "")
                    if not stat_skill_id:
                        if detect_type == "skill_id":
                            stat_skill_id = detect.get("skill_id", "")
                    if not stat_skill_id:
                        continue
                    inject_list.append({
                        "skill_name": skill_name,
                        "detect_lua": check_lua,
                        "mod_name": mod_name,
                        "mod_type": mod_type,
                        "value": None,  # 动态值标记
                        "source": source,
                        "mod_flag": mod_flag,
                        "stat_skill_id": stat_skill_id,
                        "expect_factor": skill_config.get("expect_factor", 1.0),
                        "level_index": eff.get("level_index", 1),
                    })

    if not inject_list:
        return 0

    # 分离固定值和动态值
    fixed_items = [it for it in inject_list if it["value"] is not None]
    dynamic_items = [it for it in inject_list if it["value"] is None]
    charge_items = [it for it in dynamic_items if it.get("dynamic_type") == "charge_based"]
    statset_items = [it for it in dynamic_items if it.get("dynamic_type") != "charge_based"]

    # 批量注入固定值 mod 到 Lua
    inject_lua_lines = [r"""
local build = _spike_build
local modList = build.configTab.modList
if not modList then return 0 end

-- 重新收集技能 ID
local skillIds = {}
local skillNames = {}
if build.skillsTab and build.skillsTab.socketGroupList then
    for _, sg in ipairs(build.skillsTab.socketGroupList) do
        local gemList = sg.gems or sg.gemList or {}
        for _, gem in ipairs(gemList) do
            if gem.skillId then skillIds[gem.skillId] = true end
            local n = gem.name or (gem.gemData and gem.gemData.name)
            if n then skillNames[n] = true end
        end
    end
end

-- 通用函数：读取宝石品质，含 POB bug 补偿
-- POB CalcSetup.lua 硬编码 fromItem 技能 quality=0，不传递武器品质
-- 本函数在 gem.quality=0 时，遍历武器 slot 检查物品的 grantedSkills
local function getGemQuality(skillId)
    local gemQuality = 0
    for _, sg in ipairs(build.skillsTab.socketGroupList or {}) do
        for _, gem in ipairs(sg.gems or sg.gemList or {}) do
            if gem.skillId == skillId then
                gemQuality = gem.quality or 0
                break
            end
        end
        if gemQuality ~= 0 then break end
    end
    -- POB bug 补偿: gem.quality=0 时，从武器物品读取品质
    if gemQuality == 0 then
        local weaponSlotNames = {"Weapon 1", "Weapon 2", "Weapon 1 Swap", "Weapon 2 Swap"}
        for _, sn in ipairs(weaponSlotNames) do
            local slot = build.itemsTab.slots[sn]
            if slot then
                local it = build.itemsTab.items[slot.selItemId]
                if it and it.grantedSkills then
                    for _, gs in ipairs(it.grantedSkills) do
                        if gs.skillId == skillId then
                            gemQuality = it.quality or 0
                            break
                        end
                    end
                end
            end
            if gemQuality > 0 then break end
        end
    end
    return gemQuality
end

local injected = 0
"""]

    for item in fixed_items:
        inject_lua_lines.append(f"""if {item['detect_lua']} then
    modList:NewMod("{item['mod_name']}", "{item['mod_type']}", {item['value']}, "{item['source']}")
    injected = injected + 1
end
""")

    # 动态值（charge_based）：从 output 读取 charge 数量并计算
    if charge_items:
        for item in charge_items:
            charge_stat = item.get("charge_stat", "PowerChargesMax")
            per_charge = item.get("per_charge_value", 0)
            quality_per = item.get("quality_per_charge", 0)
            sid = item.get("stat_skill_id", "")
            # 使用 format 避免复杂的 f-string 转义
            lua_template = """
-- charge_based 动态值: {skill_name} ({sid})
do
    local gemQuality = getGemQuality("{sid}")
    if {detect_lua} then
        -- 先计算一次获取 output 中的 charge 数量
        local env = calcs.initEnv(build, "MAIN")
        calcs.perform(env)
        local chargeCount = env.player.output.{charge_stat} or 0
        if chargeCount > 0 then
            local perVal = {per_charge} + gemQuality * {quality_per}
            local totalVal = math.floor(chargeCount * perVal)
            if totalVal > 0 then
                modList:NewMod("{mod_name}", "{mod_type}", totalVal, "{source}")
                injected = injected + 1
            end
        end
    end
end
"""
            inject_lua_lines.append(lua_template.format(
                skill_name=item['skill_name'],
                sid=sid,
                detect_lua=item['detect_lua'],
                charge_stat=charge_stat,
                per_charge=per_charge,
                quality_per=quality_per,
                mod_name=item['mod_name'],
                mod_type=item['mod_type'],
                source=item['source'],
            ))

    # 动态值（statSet based）：从 Lua 读取宝石等级和对应的 stat 值
    if statset_items:
        # 为每个需要动态值的技能，从 skillData.statSets.levels 读取
        for item in statset_items:
            sid = item["stat_skill_id"]
            factor = item.get("expect_factor", 1.0)
            lv_idx = item.get("level_index", 1)
            inject_lua_lines.append(f"""
-- 动态值: {item['skill_name']} ({sid})
do
    local gemLevel = nil
    local gemQuality = getGemQuality("{sid}")
    for _, sg in ipairs(build.skillsTab.socketGroupList or {{}}) do
        for _, gem in ipairs(sg.gems or sg.gemList or {{}}) do
            if gem.skillId == "{sid}" then
                gemLevel = gem.level or 1
                break
            end
        end
        if gemLevel then break end
    end
    if {item['detect_lua']} and gemLevel then
        local baseVal = 0
        local sk = build.data.skills and build.data.skills["{sid}"]
        if sk and sk.statSets then
            for _, ss in ipairs(sk.statSets) do
                if ss.levels and ss.levels[gemLevel] then
                    baseVal = ss.levels[gemLevel][{lv_idx}] or 0
                    break
                end
            end
        end
        -- 品质增量（从 qualityStats 读取每品质点增量）
        -- 仅当 qualityStats 的 stat 名称与 mod_name 匹配时才添加
        local qualityBonus = 0
        if sk and sk.qualityStats then
            for _, qs in ipairs(sk.qualityStats) do
                local statName = qs[1] or ""
                -- 简单启发：如果 stat 名称包含 mod_name 关键词或 "damage"/"more"/"inc"，才计入品质
                local snl = statName:lower()
                if snl:find("damage") or snl:find("more") or snl:find("inc") or snl:find("crit") or snl:find("speed") or snl:find("defence") then
                    qualityBonus = qualityBonus + gemQuality * (qs[2] or 0)
                end
            end
        end
        local totalVal = baseVal + qualityBonus
        local finalVal = math.max(0, math.floor(totalVal * {factor}))
        if finalVal > 0 then
            modList:NewMod("{item['mod_name']}", "{item['mod_type']}", finalVal, "{item['source']}")
            injected = injected + 1
        end
    end
end
""")

    inject_lua_lines.append("return injected")
    inject_lua = "\n".join(inject_lua_lines)

    try:
        result = lua.execute(inject_lua)
        injected_count = int(result) if result else 0
    except Exception as e:
        logger.warning("注入未实现效果失败: %s", e)
        injected_count = 0

    return injected_count


def auto_configure_combat(lua) -> int:
    """自动配置战斗条件：扫描构筑技能/天赋，设置合理的战斗默认值。

    策略：
    1. 技能专属条件：扫描技能组，为匹配的 ifSkill 条件设置默认值
    2. 通用战斗条件：FullLife、FullMana、CastSpellRecently 等
    3. 重新运行 BuildModList 使配置生效
    4. 注入 YAML 配置的未实现效果（条件满足时）

    Returns:
        自动设置的配置项数量
    """
    auto_lua = r'''
        local build = _spike_build
        local input = build.configTab.input
        local count = 0

        -- === 1. 收集构筑中所有技能名称、skillId 和 skillTypes ===
        local skillNames = {}
        local skillIds = {}
        local hasCold = false
        local hasLightning = false
        local hasFire = false
        local hasChaos = false
        local hasPhysical = false
        local hasBleed = false
        local hasPoison = false
        local hasIgnite = false
        local hasChill = false
        local hasFreeze = false
        local hasShock = false
        local hasCurse = false
        local hasStun = false

        if build.skillsTab and build.skillsTab.socketGroupList then
            for _, sg in ipairs(build.skillsTab.socketGroupList) do
                local gemList = sg.gems or sg.gemList or {}
                for _, gem in ipairs(gemList) do
                    -- gem.name 可能为 nil，使用 skillId 和 grantedEffect.name
                    local name = gem.name
                        or (gem.grantedEffect and gem.grantedEffect.name)
                        or (gem.skillSpec and gem.skillSpec and gem.skillSpec.name)
                        or nil
                    if name then skillNames[name] = true end
                    if gem.skillId then skillIds[gem.skillId] = true end

                    -- 收集 skillTypes（元素/伤害类型标签）
                    local ge = gem.grantedEffect
                        or (gem.gemData and gem.gemData.grantedEffect)
                        or nil
                    if ge and ge.skillTypes then
                        if ge.skillTypes[SkillType.Cold] then hasCold = true end
                        if ge.skillTypes[SkillType.Lightning] then hasLightning = true end
                        if ge.skillTypes[SkillType.Fire] then hasFire = true end
                        if ge.skillTypes[SkillType.Chaos] then hasChaos = true end
                        if ge.skillTypes[SkillType.Physical] then hasPhysical = true end
                        -- ElementalStatus: 能造成元素异常
                        if ge.skillTypes[SkillType.ElementalStatus] then
                            hasIgnite = true
                            hasChill = true
                            hasShock = true
                        end
                        -- CausesBurning: 能造成燃烧（点燃）
                        if ge.skillTypes[SkillType.CausesBurning] then hasIgnite = true end
                    end
                    -- 额外从 skillId 推断（某些 fromItem 技能可能没有 grantedEffect.skillTypes）
                    local sid = gem.skillId or ""
                    local sidl = sid:lower()
                    if sidl:find("cold") or sidl:find("frost") or sidl:find("ice") or sidl:find("freeze") or sidl:find("chill") then
                        hasCold = true
                    end
                    if sidl:find("lightning") or sidl:find("thunder") or sidl:find("shock") or sidl:find("electrocut") then
                        hasLightning = true
                    end
                    if sidl:find("fire") or sidl:find("flame") or sidl:find("ignite") or sidl:find("burn") then
                        hasFire = true
                    end
                    if sidl:find("chaos") then hasChaos = true end
                    if sidl:find("physical") then hasPhysical = true end
                    if sidl:find("bleed") then hasBleed = true end
                    if sidl:find("poison") then hasPoison = true end
                    if sidl:find("curse") then hasCurse = true end
                    if sidl:find("stun") then hasStun = true end
                end
            end
        end

        -- 从 skillNames 进一步推断（辅助宝石和光环）
        -- 冰霜光环 -> Cold
        if skillNames["Hatred"] or skillNames["Wrath"] or skillNames["Anger"] then
            -- Hatred=Cold, Wrath=Lightning, Anger=Fire — 已由 skillTypes 覆盖
        end
        -- 诅咒类技能
        for sn, _ in pairs(skillNames) do
            if sn:find("Curse") or sn:find("Vulnerability") or sn:find("Enfeeble") or sn:find("Temporal Chains") or sn:find("Despair") or sn:find("Elemental Weakness") or sn:find("Flammability") or sn:find("Frostbite") or sn:find("Conductivity") or sn:find("Punishment") then
                hasCurse = true
                break
            end
        end

        -- 辅助：通过 skillId 模糊匹配检查
        local function hasSkillIdFragment(frag)
            for id, _ in pairs(skillIds) do
                if id:find(frag, 1, true) then return true end
            end
            return false
        end

        -- === 2. 技能专属自动配置 ===

        -- Rising Tempest: 如果有此辅助，默认所有元素类型都触发
        if skillNames["Rising Tempest"] or hasSkillIdFragment("RisingTempest") or hasSkillIdFragment("TempestuousTempo") then
            if input["risingTempestLightning"] == nil then input["risingTempestLightning"] = true; count = count + 1 end
            if input["risingTempestCold"] == nil then input["risingTempestCold"] = true; count = count + 1 end
            if input["risingTempestFire"] == nil then input["risingTempestFire"] = true; count = count + 1 end
        end

        -- Trinity: 默认 250（门槛值，触发 Trinity Speed 效果）
        if skillNames["Trinity"] or hasSkillIdFragment("Trinity") then
            if input["configResonanceCount"] == nil then input["configResonanceCount"] = 250; count = count + 1 end
        end

        -- Twister: 默认所有元素
        if skillNames["Twister"] or hasSkillIdFragment("Twister") then
            if input["twisterCold"] == nil then input["twisterCold"] = true; count = count + 1 end
            if input["twisterFire"] == nil then input["twisterFire"] = true; count = count + 1 end
        end

        -- Sigil of Power: 默认 1 stage
        if skillNames["Sigil of Power"] or hasSkillIdFragment("SigilOfPower") then
            if input["sigilOfPowerStages"] == nil then input["sigilOfPowerStages"] = 1; count = count + 1 end
        end

        -- Thirst for Blood: 默认 1 个流血敌人
        if skillNames["Thirst for Blood"] or hasSkillIdFragment("ThirstForBlood") then
            if input["nearbyBleedingEnemies"] == nil then input["nearbyBleedingEnemies"] = 1; count = count + 1 end
        end

        -- Corrupting Cry: 默认 1 stack
        if skillNames["Corrupting Cry"] or hasSkillIdFragment("CorruptingCry") then
            if input["conditionCorruptingCryStages"] == nil then input["conditionCorruptingCryStages"] = 1; count = count + 1 end
        end

        -- Zenith: 有此辅助时启用 FullMana（already handled below, but explicit)
        if hasSkillIdFragment("Zenith") then
            -- Zenith needs >90% mana, ensure conditionFullMana is true
            if input["conditionFullMana"] == nil then input["conditionFullMana"] = true; count = count + 1 end
        end

        -- Frost Bomb: 默认 1 阶段
        if skillNames["Frost Bomb"] or hasSkillIdFragment("FrostBomb") then
            if input["frostBombStage"] == nil then input["frostBombStage"] = 1; count = count + 1 end
        end

        -- Comet
        if skillNames["Comet"] or hasSkillIdFragment("Comet") then
            if input["cometStage"] == nil then input["cometStage"] = 1; count = count + 1 end
        end

        -- Charge Infusion / Charge Regulation: 需要充能球才能触发 MORE 效果
        if hasSkillIdFragment("ChargeRegulation") or skillNames["Charge Infusion"] or skillNames["Charge Regulation"] then
            -- 读取构筑的充能球上限，默认设为最大值
            local env = calcs.initEnv(build, "MAIN")
            calcs.perform(env)
            local o = env.player.output
            if input["powerCharges"] == nil then
                input["powerCharges"] = o.PowerChargesMax or 8; count = count + 1
            end
            if input["frenzyCharges"] == nil then
                input["frenzyCharges"] = o.FrenzyChargesMax or 3; count = count + 1
            end
            if input["enduranceCharges"] == nil then
                input["enduranceCharges"] = o.EnduranceChargesMax or 3; count = count + 1
            end
        end

        -- === 2.5. 敌人状态自动推断 ===
        -- 根据构筑技能的 skillTypes 标签，自动设置合理的敌人异常状态条件
        -- 原理：如果构筑有冰霜技能 -> 敌人会被冰缓; 有闪电技能 -> 敌人会被感电; 等
        -- 这使得条件天赋（如 "对冰缓敌人增加伤害"）能正确反映其 DPS 贡献

        -- 冰霜类：Cold 技能能造成冰缓，部分能冰冻
        if hasCold then
            hasChill = true
            if input["conditionEnemyChilled"] == nil then
                input["conditionEnemyChilled"] = true; count = count + 1
            end
            -- 有 Cold 技能不一定能冰冻（需要足够伤害），但大部分法术型 Cold 技能都能
            -- 只在有明确的 Freeze 相关技能或 ColdDamageOverTime 时设冰冻
            -- 安全做法：不自动设冰冻（因为 Boss 免疫冰冻），只设冰缓
        end

        -- 闪电类：Lightning 技能能造成感电
        if hasLightning then
            hasShock = true
            if input["conditionEnemyShocked"] == nil then
                input["conditionEnemyShocked"] = true; count = count + 1
            end
        end

        -- 火焰类：Fire 技能能造成点燃 -> 敌人燃烧
        if hasFire then
            hasIgnite = true
            if input["conditionEnemyIgnited"] == nil then
                input["conditionEnemyIgnited"] = true; count = count + 1
            end
            -- Ignited 暗含 Burning
        end

        -- 物理类：Physical 技能能造成流血
        if hasPhysical then
            hasBleed = true
            if input["conditionEnemyBleeding"] == nil then
                input["conditionEnemyBleeding"] = true; count = count + 1
            end
        end

        -- 混沌类：Chaos 技能能造成中毒
        if hasChaos then
            hasPoison = true
            if input["conditionEnemyPoisoned"] == nil then
                input["conditionEnemyPoisoned"] = true; count = count + 1
            end
        end

        -- 诅咒类：如果构筑有诅咒，敌人被视为被诅咒
        -- 注意：POB 自动在有诅咒技能时设 Cursed，但这里是显式确认
        if hasCurse then
            if input["conditionEnemyCursed"] == nil then
                input["conditionEnemyCursed"] = true; count = count + 1
            end
        end

        -- 敌人是 Rare/Unique（Boss 战默认）
        if input["conditionEnemyRareOrUnique"] == nil then
            input["conditionEnemyRareOrUnique"] = true; count = count + 1
        end

        -- 敌人在移动（流血相关加成需要）
        if hasBleed then
            if input["conditionEnemyMoving"] == nil then
                input["conditionEnemyMoving"] = true; count = count + 1
            end
        end

        -- === 3. 通用战斗条件 ===

        -- Full Life: 战斗开始时满血（不与 LowLife 冲突时才启用）
        if input["conditionFullLife"] == nil and input["conditionLowLife"] ~= true then
            input["conditionFullLife"] = true; count = count + 1
        end

        -- Full Energy Shield: 理论值测试假设满 ES（不与 LowLife 冲突时才启用）
        if input["conditionFullEnergyShield"] == nil and input["conditionLowLife"] ~= true then
            input["conditionFullEnergyShield"] = true; count = count + 1
        end

        -- Full Mana: 战斗开始时满蓝（用于 Zenith 等 "above 90% mana" 条件）
        if input["conditionFullMana"] == nil then
            input["conditionFullMana"] = true; count = count + 1
        end

        -- === 3b. 战斗行为条件（基于构筑特征推断） ===

        -- Crit Recently: 如果构筑暴击率 > 0（几乎所有法术构筑都有暴击）
        -- 注意：conditionCritRecently 会同时设置 CritRecently + SkillCritRecently + CritInPast8Sec
        -- 这会激活 "if you've dealt a Critical Hit Recently" 和 "in the past 8 seconds" 条件天赋
        local hasCritChance = false
        if build.configTab and build.configTab.modList then
            local critVal = build.configTab.modList:Sum("INC", nil, "CritChance")
            if critVal and critVal > 0 then hasCritChance = true end
        end
        -- 法术构筑几乎必然暴击（Spark 等多 hit 技能暴击概率极高）
        if hasCritChance or hasFire or hasLightning or hasCold then
            if input["conditionCritRecently"] == nil then
                input["conditionCritRecently"] = true; count = count + 1
            end
        end

        -- Cast Spell Recently: 法术构筑战斗中必然施法
        if input["conditionCastSpellRecently"] == nil then
            input["conditionCastSpellRecently"] = true; count = count + 1
        end

        -- Hit Recently: 主动攻击必然命中
        if input["conditionHitRecently"] == nil then
            input["conditionHitRecently"] = true; count = count + 1
        end

        -- Hit with Spell Recently: 法术构筑必然法术命中
        if input["conditionHitSpellRecently"] == nil then
            input["conditionHitSpellRecently"] = true; count = count + 1
        end

        -- Skills Used Recently: 默认 2（大部分构筑战斗中使用多种技能）
        if input["multiplierSkillUsedRecently"] == nil then
            input["multiplierSkillUsedRecently"] = 2; count = count + 1
        end

        -- Used a Skill Recently: 战斗中必然使用技能
        if input["conditionUsedSkillRecently"] == nil then
            input["conditionUsedSkillRecently"] = true; count = count + 1
        end

        -- Killed Recently: 清图场景默认击杀
        if input["conditionKilledRecently"] == nil then
            input["conditionKilledRecently"] = true; count = count + 1
        end

        -- Killed in Past 4s: 同上
        if input["conditionKilledInPast4s"] == nil then
            input["conditionKilledInPast4s"] = true; count = count + 1
        end

        -- Triggered a Skill Recently: 如果构筑有触发技能
        if hasSkillIdFragment("Trigger") or hasSkillIdFragment("CastOn") then
            if input["conditionTriggeredSkillRecently"] == nil then
                input["conditionTriggeredSkillRecently"] = true; count = count + 1
            end
        end

        -- Summoned Totem Recently: 如果构筑有图腾技能
        if hasSkillIdFragment("Totem") then
            if input["conditionSummonedTotemRecently"] == nil then
                input["conditionSummonedTotemRecently"] = true; count = count + 1
            end
        end

        -- Consumed a Power Charge Recently: 如果构筑有 Pinnacle of Power 或消耗充能技能
        if hasSkillIdFragment("Pinnacle") or hasSkillIdFragment("ChargeRegulation") then
            if input["conditionConsumedPowerChargeRecently"] == nil then
                input["conditionConsumedPowerChargeRecently"] = true; count = count + 1
            end
        end

        -- Champion Intimidate: 默认启用
        if input["conditionChampionIntimidate"] == nil then
            input["conditionChampionIntimidate"] = true; count = count + 1
        end

        -- === 4. 重新运行 BuildModList ===
        if count > 0 then
            local configSettings = LoadModule("Modules/ConfigOptions")
            if configSettings then
                local modList = new("ModList")
                local enemyModList = new("ModList")
                local placeholder = build.configTab.placeholder

                for _, varData in ipairs(configSettings) do
                    if varData.apply then
                        local varName = varData.var
                        if varData.type == "check" then
                            local val = input[varName]
                            if val == nil and varData.defaultState then val = true end
                            if val then pcall(varData.apply, true, modList, enemyModList, build) end
                        elseif varData.type == "count" or varData.type == "integer" or varData.type == "countAllowZero" or varData.type == "float" then
                            local val = input[varName]
                            if val and (val ~= 0 or varData.type ~= "count") then
                                pcall(varData.apply, val, modList, enemyModList, build)
                            elseif placeholder[varName] and (placeholder[varName] ~= 0 or varData.type ~= "count") then
                                pcall(varData.apply, placeholder[varName], modList, enemyModList, build)
                            end
                        elseif varData.type == "list" then
                            local val = input[varName]
                            if val == nil and varData.list and varData.defaultIndex then
                                local defaultEntry = varData.list[varData.defaultIndex]
                                if defaultEntry then val = defaultEntry.val end
                            end
                            if val then pcall(varData.apply, val, modList, enemyModList, build) end
                        elseif varData.type == "text" then
                            if input[varName] then pcall(varData.apply, input[varName], modList, enemyModList, build) end
                        end
                    end
                end

                build.configTab.modList = modList
                build.configTab.enemyModList = enemyModList
                build.buildFlag = true
            end
        end

        -- 序列化 input 为 JSON（仅 boolean/number 类型值）
        local inputParts = {}
        for k, v in pairs(input) do
            if type(v) == "boolean" then
                inputParts[#inputParts+1] = '"' .. tostring(k) .. '":' .. tostring(v)
            elseif type(v) == "number" then
                inputParts[#inputParts+1] = '"' .. tostring(k) .. '":' .. tostring(v)
            end
        end
        local inputStr = "{" .. table.concat(inputParts, ",") .. "}"

        -- 序列化 skillIds 为 JSON
        local idParts = {}
        for id, _ in pairs(skillIds) do
            idParts[#idParts+1] = '"' .. id .. '":true'
        end
        local idsStr = "{" .. table.concat(idParts, ",") .. "}"

        return tostring(count) .. "|||" .. inputStr .. "|||" .. idsStr
    '''

    result = lua.execute(auto_lua)
    try:
        parts = str(result).split("|||", 2)
        count = int(parts[0])
        input_json = parts[1] if len(parts) > 1 else "{}"
    except (ValueError, TypeError, IndexError):
        count = 0
        input_json = "{}"

    # === 第5步：注入 YAML 配置的未实现效果 ===
    injected = _inject_unimplemented_mods(lua, input_json)

    total = count + injected
    if total > 0:
        logger.info("auto_configure_combat: 自动设置 %d 个战斗条件 + %d 个未实现效果",
                    count, injected)
    return total


def load_all(lua, build_info: dict):
    """按正确顺序加载全部构筑数据。

    顺序：
    1. init_build_object — 创建 build 骨架
    2. load_tree — 天赋树（必须在 skills 之前，Keystone 需要先注册）
    3. load_skills — 技能组
    4. load_items — 装备
    5. postprocess_unparsed_mods — mod 修复
    6. load_config — 配置（必须最后，因为 ConfigOptions 可能依赖 items/skills）
    7. 恢复 mainSocketGroup（第一次 initEnv 时被 clamp 到 1）

    Returns:
        dict: {tree_nodes, skill_groups, items, mod_fixes, config_inputs, warnings}
    """
    warnings = []

    init_build_object(lua, build_info)

    tree_count = load_tree(lua, build_info)
    if tree_count == 0:
        warnings.append("天赋树加载返回 0 节点，可能缺少 treeURL 或 tree.lua")

    skill_count = load_skills(lua, build_info)
    if skill_count == 0:
        warnings.append("技能组加载返回 0 组，构筑可能没有技能数据")

    item_count = load_items(lua, build_info)
    mod_fixes = postprocess_unparsed_mods(lua, build_info)
    config_count = load_config(lua, build_info)

    # 自动配置战斗条件（技能专属 + 通用战斗状态）
    auto_configure_combat(lua)

    # 恢复 mainSocketGroup
    msg = build_info['mainSocketGroup']
    lua.execute(f'_spike_build.mainSocketGroup = {msg}')

    if warnings:
        for w in warnings:
            logger.warning(w)

    return {
        'tree_nodes': tree_count,
        'skill_groups': skill_count,
        'items': item_count,
        'mod_fixes': mod_fixes,
        'config_inputs': config_count,
        'warnings': warnings,
    }
