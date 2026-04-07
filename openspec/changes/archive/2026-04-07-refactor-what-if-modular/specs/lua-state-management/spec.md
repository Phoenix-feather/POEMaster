# lua-state-management

## Overview
统一 Lua 可变状态管理器，消除分散在各函数中的手动 save/restore 逻辑。

## Requirements

### R1: Config Scope
- `config_scope()` 上下文管理器保护 `configTab.input` 所有键值 + `configTab.modList` 引用
- 进入时快照当前 input 所有键值对，退出时完整恢复
- 支持嵌套调用（内层恢复不影响外层快照）

### R2: Gem Scope
- `gem_scope()` 上下文管理器保护所有 `gem.enabled` 和 `group.enabled` 状态
- 进入时遍历所有技能组和宝石记录 enabled 状态，退出时逐一恢复
- 不能用 `gem.enabled = true` 全局重置（会启用原本禁用的宝石）

### R3: Skill Scope
- `skill_scope(skill_name)` 切换 `mainSocketGroup` 到指定技能
- 通过技能名称模糊匹配查找对应的 socketGroup 索引
- 退出时恢复原始 `mainSocketGroup`

### R4: Weapon Set Scope
- `weapon_set_scope(use_second)` 切换武器套装
- 更新 `itemsTab.activeItemSet.useSecondWeaponSet`
- 更新天赋节点 `allocMode`（weaponSet=1 的节点在 ws2 下变为未分配，反之亦然）
- 退出时完整恢复装备、天赋、技能组状态

### R5: Rebuild Modlist
- `rebuild_modlist()` 是唯一的 modList 重建入口
- 首次调用时从当前 modList 提取 sim mods（source 含 "sim"）
- 之后每次：遍历 ConfigOptions 重建 + 追加 sim mods
- 不再保存完整 modList（避免 ConfigOptions mods 双重计算）

### R6: Sim Mods 隔离
- `strip_sim_mods()` 返回 token，暂时从 modList 移除 sim mods
- `restore_sim_mods(token)` 恢复
- 用于 `_test_mod_effect` 等需要测量"无该效果"DPS 的场景

### R7: Calc 快捷方法
- `env.calc()` 等价于 `calculate(lua, calcs)`，使用当前 Lua 状态
