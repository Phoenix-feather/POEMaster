"""Lua 可变状态统一管理器。

职责：
- 提供 configTab.input / modList / gem.enabled / group.enabled / mainSocketGroup
  的 save/restore 上下文管理器
- 作为所有分析模块的唯一 Lua 交互入口（env.calc(), env.rebuild_modlist() 等）
- 提供武器套装切换能力

设计原则：
- 所有状态修改必须通过 scope 上下文管理器保护
- scope 支持嵌套（每层独立快照）
- rebuild_modlist 是唯一的 modList 重建入口
"""

import logging
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# 自增 token 计数器，确保嵌套 scope 的快照键唯一
_token_counter = 0


def _next_token(prefix: str) -> str:
    global _token_counter
    _token_counter += 1
    return f"{prefix}_{_token_counter}"


class LuaEnvManager:
    """Lua 可变状态的统一管理器。

    所有需要临时修改 Lua 状态的分析函数，都应使用本类提供的 scope 上下文管理器，
    而非直接操作 configTab.input / gem.enabled 等。
    """

    def __init__(self, lua, calcs):
        self._lua = lua
        self._calcs = calcs

    # ── 属性访问 ──

    @property
    def lua(self):
        return self._lua

    @property
    def calcs(self):
        return self._calcs

    # ── 计算 ──

    def calc(self, mode: str = "MAIN") -> dict:
        """运行 POB 计算引擎，返回 output dict。"""
        from .calculator import calculate
        return calculate(self._lua, self._calcs, mode)

    # ── config_scope: 保护 configTab.input + modList ──

    @contextmanager
    def config_scope(self):
        """保护 configTab.input 所有键值 + modList/enemyModList 引用。

        进入时快照当前状态，退出时完整恢复。支持嵌套。
        """
        token = _next_token("cfg")
        self._lua.execute(f'''
            if not _env_config_snapshots then _env_config_snapshots = {{}} end
            local snap = {{}}
            local input = _spike_build.configTab.input
            -- deep copy input（只含 boolean/number/string 类型）
            snap.input = {{}}
            for k, v in pairs(input) do
                snap.input[k] = v
            end
            -- 保存 modList/enemyModList 引用
            snap.modList = _spike_build.configTab.modList
            snap.enemyModList = _spike_build.configTab.enemyModList
            _env_config_snapshots["{token}"] = snap
        ''')
        try:
            yield
        finally:
            self._lua.execute(f'''
                local snap = _env_config_snapshots and _env_config_snapshots["{token}"]
                if snap then
                    -- 恢复 input
                    local input = _spike_build.configTab.input
                    -- 清空当前 input
                    for k in pairs(input) do input[k] = nil end
                    -- 写回快照值
                    for k, v in pairs(snap.input) do input[k] = v end
                    -- 恢复 modList 引用
                    _spike_build.configTab.modList = snap.modList
                    _spike_build.configTab.enemyModList = snap.enemyModList
                    _env_config_snapshots["{token}"] = nil
                end
            ''')

    # ── gem_scope: 保护 gem.enabled + group.enabled ──

    @contextmanager
    def gem_scope(self):
        """保护所有技能组和宝石的 enabled 状态。

        退出时逐一恢复到进入时的状态（不会把原本禁用的宝石错误启用）。
        """
        token = _next_token("gem")
        self._lua.execute(f'''
            if not _env_gem_snapshots then _env_gem_snapshots = {{}} end
            local snap = {{groups = {{}}, gems = {{}}}}
            for gi, group in ipairs(_spike_build.skillsTab.socketGroupList) do
                snap.groups[gi] = group.enabled
                snap.gems[gi] = {{}}
                for ji, gem in ipairs(group.gemList or {{}}) do
                    snap.gems[gi][ji] = gem.enabled
                end
            end
            _env_gem_snapshots["{token}"] = snap
        ''')
        try:
            yield
        finally:
            self._lua.execute(f'''
                local snap = _env_gem_snapshots and _env_gem_snapshots["{token}"]
                if snap then
                    for gi, group in ipairs(_spike_build.skillsTab.socketGroupList) do
                        if snap.groups[gi] ~= nil then
                            group.enabled = snap.groups[gi]
                        end
                        if snap.gems[gi] then
                            for ji, gem in ipairs(group.gemList or {{}}) do
                                if snap.gems[gi][ji] ~= nil then
                                    gem.enabled = snap.gems[gi][ji]
                                end
                            end
                        end
                    end
                    _env_gem_snapshots["{token}"] = nil
                end
            ''')

    # ── skill_scope: 切换/恢复 mainSocketGroup ──

    @contextmanager
    def skill_scope(self, skill_name: str):
        """切换主技能到指定名称，退出时恢复原始 mainSocketGroup。

        Args:
            skill_name: 技能名称（大小写不敏感，支持部分匹配）
        """
        original = self._lua.execute(
            'return _spike_build.mainSocketGroup')
        group_idx = self._find_skill_group(skill_name)
        if group_idx is not None:
            self._lua.execute(
                f'_spike_build.mainSocketGroup = {group_idx}')
        try:
            yield
        finally:
            if original is not None:
                self._lua.execute(
                    f'_spike_build.mainSocketGroup = {int(original)}')

    @contextmanager
    def skill_group_scope(self, group_idx: int, active_skill_idx: int = None):
        """直接按组索引切换主技能，退出时恢复原始 mainSocketGroup。

        用于同名技能出现在不同组时的精确切换。
        当 active_skill_idx 指定时，同时设置组内的 mainActiveSkill，
        用于在元触发技能组中选择特定的被触发法术。

        Args:
            group_idx: socketGroup 索引（1-based）
            active_skill_idx: 组内技能索引（1-based），None 则不修改
        """
        original_group = self._lua.execute(
            'return _spike_build.mainSocketGroup')
        # 保存原始 mainActiveSkill
        original_active = None
        if active_skill_idx is not None:
            original_active = self._lua.execute(
                f'return _spike_build.skillsTab.socketGroupList[{group_idx}].mainActiveSkill')
        self._lua.execute(
            f'_spike_build.mainSocketGroup = {group_idx}')
        if active_skill_idx is not None:
            self._lua.execute(
                f'_spike_build.skillsTab.socketGroupList[{group_idx}].mainActiveSkill = {active_skill_idx}')
        try:
            yield
        finally:
            if original_group is not None:
                self._lua.execute(
                    f'_spike_build.mainSocketGroup = {int(original_group)}')
            if active_skill_idx is not None and original_active is not None:
                self._lua.execute(
                    f'_spike_build.skillsTab.socketGroupList[{group_idx}].mainActiveSkill = {int(original_active)}')

    def _find_skill_group(self, skill_name: str) -> int | None:
        """按技能名称模糊匹配查找 socketGroup 索引。"""
        needle = skill_name.strip().lower()
        result = self._lua.execute(f'''
            local build = _spike_build
            local needle = "{needle}"
            local best_idx = nil
            local best_name = nil
            local best_dps = -1

            for i = 1, #build.skillsTab.socketGroupList do
                local group = build.skillsTab.socketGroupList[i]
                if not group.enabled then goto next end
                for _, gem in ipairs(group.gemList or {{}}) do
                    local ge = gem.grantedEffect
                        or (gem.gemData and gem.gemData.grantedEffect)
                    local name = (ge and ge.name) or gem.nameSpec or ""
                    if name ~= "" and name:lower():find(needle, 1, true) then
                        -- 计算该组的 DPS
                        local orig = build.mainSocketGroup
                        build.mainSocketGroup = i
                        local ok, env = pcall(calcs.initEnv, build, "MAIN")
                        if ok then
                            pcall(calcs.perform, env)
                            local dps = env.player.output.TotalDPS or 0
                            if dps > best_dps then
                                best_dps = dps
                                best_idx = i
                                best_name = name
                            end
                        end
                        build.mainSocketGroup = orig
                        goto next
                    end
                end
                ::next::
            end
            if best_idx then
                return tostring(best_idx)
            end
            return nil
        ''')
        if result and str(result) != "nil":
            return int(result)
        return None

    # ── rebuild_modlist: 唯一的 modList 重建入口 ──

    def rebuild_modlist(self):
        """重建 configTab.modList。

        首次调用时从当前 modList 中提取 sim mods（source 含 "sim"）。
        之后每次调用：遍历 ConfigOptions 重建 + 追加 sim mods。

        ⚠️ 必须与 POB 原版 ConfigTabClass:BuildModList() 保持一致：
        - count/integer/float 类型：先查 input，再回退到 placeholder
        - check 类型：先查 input，再回退到 defaultState
        - list 类型：先查 input，再回退到 defaultIndex
        如果遗漏 placeholder 回退，auto_configure 设置的 count 配置项
        （如 WitheredStack、DemonFlameStacks 等）在重建时会丢失。
        """
        self._lua.execute('''
            local build = _spike_build
            local configSettings = LoadModule("Modules/ConfigOptions")
            if not configSettings then return end

            -- 首次调用时提取 sim mods
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
                        if val == nil and varData.defaultState then
                            val = true
                        end
                        if val then
                            pcall(varData.apply, true,
                                  modList, enemyModList, build)
                        end
                    elseif varData.type == "count"
                        or varData.type == "integer"
                        or varData.type == "countAllowZero"
                        or varData.type == "float" then
                        local val = input[varName]
                        if val and (val ~= 0
                                    or varData.type ~= "count") then
                            pcall(varData.apply, val,
                                  modList, enemyModList, build)
                        elseif placeholder[varName] and (placeholder[varName] ~= 0 or varData.type ~= "count") then
                            pcall(varData.apply, placeholder[varName],
                                  modList, enemyModList, build)
                        end
                    elseif varData.type == "list" then
                        local val = input[varName]
                        if val == nil and varData.list
                           and varData.defaultIndex then
                            local de = varData.list[varData.defaultIndex]
                            if de then val = de.val end
                        end
                        if val then
                            pcall(varData.apply, val,
                                  modList, enemyModList, build)
                        end
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

    def set_config_and_rebuild(self, config_var: str,
                               config_type: str, value):
        """设置一个 ConfigTab 配置值并重建 modList。"""
        self._lua.execute(
            f'_spike_build.configTab.input["{config_var}"] = {value}')
        self.rebuild_modlist()

    # ── sim mods 隔离 ──

    @contextmanager
    def without_sim_mods(self):
        """上下文管理器：暂时从 modList 移除 sim mods。

        用于 _test_mod_effect 等需要测量"无该效果"DPS 的场景。
        退出时恢复原始 modList 引用。
        """
        token = _next_token("sim")
        self._lua.execute(f'''
            if not _env_sim_snapshots then _env_sim_snapshots = {{}} end
            _env_sim_snapshots["{token}"] = {{
                modList = _spike_build.configTab.modList,
                enemyModList = _spike_build.configTab.enemyModList,
            }}
            -- 创建不含 sim mod 的新 modList
            local newML = new("ModList")
            local oldML = _spike_build.configTab.modList
            if oldML then
                for _, m in ipairs(oldML) do
                    local src = m.source or ""
                    if not src:find("sim") then
                        newML:AddMod(m)
                    end
                end
            end
            _spike_build.configTab.modList = newML
        ''')
        try:
            yield
        finally:
            self._lua.execute(f'''
                local snap = _env_sim_snapshots
                    and _env_sim_snapshots["{token}"]
                if snap then
                    _spike_build.configTab.modList = snap.modList
                    _spike_build.configTab.enemyModList = snap.enemyModList
                    _env_sim_snapshots["{token}"] = nil
                end
            ''')

    # ── weapon_set_scope: 切换武器套装 ──

    @contextmanager
    def weapon_set_scope(self, use_second: bool):
        """切换武器套装。

        更新 itemsTab.activeItemSet.useSecondWeaponSet，
        调整天赋节点 allocMode，更新技能组可用性。
        退出时完整恢复。
        """
        token = _next_token("ws")
        self._lua.execute(f'''
            if not _env_ws_snapshots then _env_ws_snapshots = {{}} end
            local build = _spike_build
            local snap = {{}}
            -- 保存 useSecondWeaponSet
            snap.useSecond = build.itemsTab.activeItemSet.useSecondWeaponSet
            -- 保存所有组的 enabled
            snap.groups = {{}}
            for gi, group in ipairs(build.skillsTab.socketGroupList) do
                snap.groups[gi] = group.enabled
            end
            _env_ws_snapshots["{token}"] = snap

            -- 切换 useSecondWeaponSet（POB 的 calcs.initEnv 会据此选择武器和天赋）
            build.itemsTab.activeItemSet.useSecondWeaponSet
                = {"true" if use_second else "false"}
            -- 调整技能组可用性（slot 绑定武器的组）
            for gi, group in ipairs(build.skillsTab.socketGroupList) do
                local slot = group.slot or ""
                if slot:find("Swap") then
                    group.enabled = {"true" if use_second else "false"}
                elseif slot:find("Weapon") then
                    group.enabled = {"false" if use_second else "true"}
                end
            end
        ''')
        try:
            yield
        finally:
            self._lua.execute(f'''
                local snap = _env_ws_snapshots
                    and _env_ws_snapshots["{token}"]
                if snap then
                    local build = _spike_build
                    build.itemsTab.activeItemSet.useSecondWeaponSet
                        = snap.useSecond
                    for gi, origEnabled in pairs(snap.groups) do
                        if build.skillsTab.socketGroupList[gi] then
                            build.skillsTab.socketGroupList[gi].enabled
                                = origEnabled
                        end
                    end
                    _env_ws_snapshots["{token}"] = nil
                end
            ''')

    # ── 查询工具 ──

    def has_weapon_set_2(self) -> bool:
        """检测构筑是否有第二套武器。"""
        result = self._lua.execute('''
            local slots = _spike_build.itemsTab.slots
            local swapSlot = slots and slots["Weapon 1 Swap"]
            if swapSlot and swapSlot.selItemId
               and swapSlot.selItemId > 0 then
                return "true"
            end
            return "false"
        ''')
        return str(result) == "true"

    def get_weapon_set_skills(self, ws: int) -> list[str]:
        """获取指定套装下可用的、DPS>0 的技能名称列表。"""
        use_second = ws == 2
        result = self._lua.execute(f'''
            local build = _spike_build
            local names = {{}}
            local origMsg = build.mainSocketGroup
            for i, group in ipairs(build.skillsTab.socketGroupList) do
                if not group.enabled then goto next end
                -- 检查 slot 是否与套装兼容
                local slot = group.slot or ""
                if {"true" if use_second else "false"} then
                    if slot:find("Weapon") and not slot:find("Swap") then
                        goto next
                    end
                else
                    if slot:find("Swap") then goto next end
                end
                -- 计算 DPS
                build.mainSocketGroup = i
                local ok, env = pcall(calcs.initEnv, build, "MAIN")
                if ok then
                    pcall(calcs.perform, env)
                    local dps = env.player.output.TotalDPS or 0
                    if dps > 0 then
                        local ms = env.player.mainSkill
                        local name = ms and ms.activeEffect
                            and ms.activeEffect.grantedEffect
                            and ms.activeEffect.grantedEffect.name
                        if name then names[#names+1] = name end
                    end
                end
                ::next::
            end
            build.mainSocketGroup = origMsg
            -- 去重
            local seen = {{}}
            local unique = {{}}
            for _, n in ipairs(names) do
                if not seen[n] then
                    seen[n] = true
                    unique[#unique+1] = n
                end
            end
            return table.concat(unique, "|")
        ''')
        if result and str(result) != "":
            return str(result).split("|")
        return []

    def get_config_value(self, config_var: str):
        """读取 configTab.input 的值。"""
        result = self._lua.execute(f'''
            local v = _spike_build.configTab.input["{config_var}"]
            if v == nil then return "nil" end
            return tostring(v)
        ''')
        s = str(result)
        if s == "nil":
            return None
        if s == "true":
            return True
        if s == "false":
            return False
        try:
            return int(s)
        except ValueError:
            try:
                return float(s)
            except ValueError:
                return s

    def set_config_value(self, config_var: str, value):
        """设置 configTab.input 的值（不重建 modList）。"""
        if isinstance(value, bool):
            lua_val = "true" if value else "false"
        elif value is None:
            lua_val = "nil"
        else:
            lua_val = str(value)
        self._lua.execute(
            f'_spike_build.configTab.input["{config_var}"] = {lua_val}')
