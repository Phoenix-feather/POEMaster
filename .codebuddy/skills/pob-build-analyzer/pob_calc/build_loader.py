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
