#!/usr/bin/env python3
"""
Lua 5.4 / LuaJIT 兼容性补丁与 mod 修复。

职责：
  - apply_lua54_patches:          tostring float→int 等兼容补丁
  - register_item_fix_functions:  注册 Lua 侧物品修复函数
  - postprocess_unparsed_mods:    后处理 ModParser 无法解析的 mod
  - parse_item_spec_values:       从物品原始文本预解析防御/Spirit 值
"""
import re


def apply_lua54_patches(lua):
    """应用 Lua 5.4 兼容性补丁。

    根因：Lua 5.4 的 / 运算符总是返回 float（即使 4400/100=44.0），
    而 LuaJIT（POB desktop）中 / 对整数结果返回 integer。
    这导致 tostring(44.0) = "44.0" 而 LuaJIT 中 tostring(44) = "44"
    影响链：applyRange → formatValue → roundSymmetric → 除法 → float →
    tostring → "44.0" → parseMod 返回 extra → processModLine 跳过该 mod
    """
    lua.execute('''
        local _orig_tostring = tostring
        function tostring(v, ...)
            if type(v) == "number" and math.type(v) == "float" and v == math.floor(v)
               and v >= -2^53 and v <= 2^53 then
                return _orig_tostring(math.tointeger(v))
            end
            return _orig_tostring(v, ...)
        end
    ''')


def register_item_fix_functions(lua):
    """注册 Lua 侧物品 mod 修复函数 _spike_fix_extra_mods。

    Item.lua processModLine (line 1776) 跳过 modLines where extra ~= nil。
    此函数遍历被跳过的 modLine，将有效 mods 注入 item.modList。
    """
    lua.execute('''
        function _spike_fix_extra_mods(item, isArmourItem)
            if not item then return 0 end

            local localDefenceNames = {
                ["Armour"] = true, ["Evasion"] = true, ["EnergyShield"] = true,
                ["Ward"] = true, ["ArmourAndEvasion"] = true,
                ["EvasionAndEnergyShield"] = true, ["ArmourAndEnergyShield"] = true,
                ["Defences"] = true, ["Spirit"] = true,
            }

            local localWeaponNames = {
                ["PhysicalDamage"] = true, ["LightningDamage"] = true,
                ["ColdDamage"] = true, ["FireDamage"] = true,
                ["ChaosDamage"] = true, ["AttackSpeed"] = true,
                ["CritChance"] = true, ["Quality"] = true,
            }

            local injected = 0
            local modSource = "Item:" .. tostring(item.id or -1) .. ":" .. (item.name or "?")

            local function processSkippedModLines(modLines, targetList)
                if not modLines or not targetList then return end
                for _, modLine in ipairs(modLines) do
                    if modLine.extra and modLine.modList and #modLine.modList > 0 then
                        local origLine = modLine.line
                        if origLine:find("\\n") then
                            origLine = origLine:gsub("\\n", " ")
                        end
                        local correctList, correctExtra = modLib.parseMod(origLine)
                        local modsToInject = (correctList and not correctExtra) and correctList or modLine.modList
                        for _, mod in ipairs(modsToInject) do
                            local skip = false
                            if isArmourItem and localDefenceNames[mod.name] then
                                skip = true
                            end
                            if item.base and item.base.weapon and localWeaponNames[mod.name] then
                                skip = true
                            end
                            if not skip then
                                mod = modLib.setSource(mod, modSource)
                                table.insert(targetList, mod)
                                injected = injected + 1
                            end
                        end
                    end
                end
            end

            if item.slotModList then
                for slotNum, targetList in pairs(item.slotModList) do
                    processSkippedModLines(item.explicitModLines, targetList)
                    processSkippedModLines(item.implicitModLines, targetList)
                    processSkippedModLines(item.enchantModLines, targetList)
                    processSkippedModLines(item.runeModLines, targetList)
                    processSkippedModLines(item.classRequirementModLines, targetList)
                end
            elseif item.modList then
                processSkippedModLines(item.explicitModLines, item.modList)
                processSkippedModLines(item.implicitModLines, item.modList)
                processSkippedModLines(item.enchantModLines, item.modList)
                processSkippedModLines(item.runeModLines, item.modList)
                processSkippedModLines(item.classRequirementModLines, item.modList)
            end

            return injected
        end
    ''')


def parse_item_spec_values(raw_text: str) -> dict:
    """从物品原始文本解析 spec 行的防御值和 Spirit 值。

    这些值在 Item 构造函数中被正确解析到 self.armourData，
    但随后 BuildModListForSlotNum 用 base + calcLocal 重算并覆盖。
    由于 processModLine 跳过 extra 非 nil 的 modLine，calcLocal 找不到
    INC mod，重算值偏低。

    修复策略：在 Python 端预解析原始文本，Item 构造后在 Lua 侧覆盖。
    """
    specs = {}
    for line in raw_text.split('\n'):
        line = line.strip()
        m = re.match(r'^(Energy Shield|Evasion Rating|Evasion|Armour|Ward):\s*(\d+)', line)
        if m:
            key = m.group(1)
            val = int(m.group(2))
            if key == 'Energy Shield':
                specs['EnergyShield'] = val
            elif key in ('Evasion Rating', 'Evasion'):
                specs['Evasion'] = val
            elif key == 'Armour':
                specs['Armour'] = val
            elif key == 'Ward':
                specs['Ward'] = val
        m2 = re.match(r'^Spirit:\s*(\d+)', line)
        if m2:
            specs['Spirit'] = int(m2.group(1))
    return specs


def postprocess_unparsed_mods(lua, build_info: dict) -> int:
    """后处理：修复 ModParser 无法解析的 mod。

    已知问题：
    1. "Allies in your Presence Regenerate X% of their Maximum Life per second"
       ModParser 只认 "your Maximum Life"，不认 "their Maximum Life"。
       修复：直接注入 LifeRegenPercent BASE X 到 item 的 modList。
    """
    items = build_info.get('items', [])
    fixes = []

    for item_data in items:
        raw_text = item_data.get('text', '')
        if not raw_text:
            continue
        item_id = item_data['id']

        m = re.search(
            r'Allies in your Presence Regenerate ([0-9.]+)% of their Maximum Life per second',
            raw_text
        )
        if m:
            regen_pct = float(m.group(1))
            fixes.append((item_id, 'LifeRegenPercent', regen_pct, 'their Maximum Life'))

    if not fixes:
        return 0

    injected = 0
    for item_id, mod_name, mod_value, desc in fixes:
        try:
            result = lua.execute(f'''
                local item = _spike_build.itemsTab.items[{item_id}]
                if item then
                    local modSource = "Item:{item_id}:" .. tostring(item.name or "?")
                    local mod = modLib.createMod("{mod_name}", "BASE", {mod_value}, modSource)
                    if item.slotModList then
                        for slotNum, targetList in pairs(item.slotModList) do
                            table.insert(targetList, mod)
                        end
                    elseif item.modList then
                        table.insert(item.modList, mod)
                    end
                    return "OK:" .. tostring(item.name or "?")
                end
                return "SKIP:item not found"
            ''')
            if result and str(result).startswith('OK:'):
                injected += 1
        except Exception:
            pass

    return injected
