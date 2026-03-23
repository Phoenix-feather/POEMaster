#!/usr/bin/env python3
"""
What-If 分析模块。

职责：
  - what_if_mod:     向 modDB 注入 modifier 并对比
  - what_if_nodes:   临时增删天赋点并对比
  - what_if_item:    临时替换装备并对比
  - _diff_outputs:   对比两个 output dict，返回差异
"""
from .calculator import calculate


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


def what_if_mod(lua, calcs, mod_name: str, mod_type: str, value: float,
                baseline: dict = None) -> dict:
    """向 modDB 注入 modifier 并对比前后变化。

    Args:
        mod_name: modifier 名称 (如 "Life", "Evasion")
        mod_type: modifier 类型 (如 "BASE", "INC", "MORE")
        value: 数值
        baseline: 基线 output，若为 None 则自动计算

    Returns:
        {stat: (before, after, delta)} 差异字典
    """
    if baseline is None:
        baseline = calculate(lua, calcs)

    # 注入 modifier 后重算
    result = lua.execute(f'''
        local build = _spike_build
        local env = calcs.initEnv(build, "MAIN")
        env.modDB:NewMod("{mod_name}", "{mod_type}", {value}, "WhatIf")
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
    add_lua = '{' + ','.join(
        f'[_spike_build.spec.nodes[{nid}]] = true' for nid in add
    ) + '}' if add else '{}'

    remove_lua = '{' + ','.join(
        f'[_spike_build.spec.nodes[{nid}]] = true' for nid in remove
    ) + '}' if remove else '{}'

    result = lua.execute(f'''
        local build = _spike_build
        local override = {{
            addNodes = {add_lua},
            removeNodes = {remove_lua},
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


def what_if_item(lua, calcs, slot_name: str, item_raw_text: str,
                 baseline: dict = None) -> dict:
    """临时替换装备并对比。

    使用 POB 原生 override.repSlotName / override.repItem 机制。

    Args:
        slot_name: 装备槽位名称 (如 "Helmet", "Body Armour")
        item_raw_text: 新装备的原始文本
        baseline: 基线 output

    Returns:
        {stat: (before, after, delta)} 差异字典
    """
    if baseline is None:
        baseline = calculate(lua, calcs)

    raw_escaped = item_raw_text.replace('\\', '\\\\').replace("'", "\\'").replace('\n', '\\n').replace('\r', '')
    slot_escaped = slot_name.replace("'", "\\'")

    result = lua.execute(f'''
        local build = _spike_build
        local rawText = '{raw_escaped}'
        local ok, newItem = pcall(new, "Item", rawText)
        if not ok or not newItem or not newItem.base then
            return nil
        end
        local override = {{
            repSlotName = '{slot_escaped}',
            repItem = newItem,
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
