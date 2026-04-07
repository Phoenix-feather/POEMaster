## Why

`what_if.py` 已增长到 8593 行（82 个函数），占整个 `pob_calc` 包的 68%。这导致：
1. AI 模型无法在上下文窗口中完整持有文件语义，修改一处频繁破坏另一处
2. `configTab.modList` 的管理职责分散在 `auto_configure_combat`、`_rebuild_config_tab_modlist`、`_test_mod_effect` 三处，互相踩脚导致数值计算错误
3. Lua 可变状态（`configTab.input`、`gem.enabled`、`group.enabled`、`mainSocketGroup`）缺少统一的 save/restore 机制，测试函数的副作用泄漏到后续流程
4. 无法支持武器套装切换分析——当前所有分析假设 `useSecondWeaponSet=false`，没有状态隔离能力

## What Changes

- **拆分 `what_if.py`**：将 8593 行拆为 8 个职责单一的模块文件，每个 ≤2000 行
- **新增 `lua_env.py`**：统一 Lua 状态管理器（`LuaEnvManager`），提供 `config_scope`/`gem_scope`/`skill_scope`/`weapon_set_scope` 上下文管理器
- **新增 `full_analysis.py`**：分析编排层，实现 Phase 0（全局）→ Phase 1（逐技能）→ Phase 2（武器套装对比）的三阶段流程
- **改造分析函数签名**：从 `(lua, calcs, ...)` 统一为 `(env: LuaEnvManager, ...)`
- **保持 `what_if.py` 作为 re-export 入口**：`from what_if import X` 继续可用，零破坏
- **扩展 `build_cache.py`**：支持 `ws1/`、`ws2/` 子目录结构
- **扩展 `report_generator.py`**：支持武器套装 tabs + 对比面板

## Capabilities

### New Capabilities
- `lua-state-management`: 统一 Lua 可变状态管理器 LuaEnvManager，提供 save/restore 上下文管理器
- `weapon-set-analysis`: 武器套装切换分析，支持在两个套装间干净切换并对比
- `multi-phase-orchestration`: 三阶段分析编排（全局→逐技能→对比），消除重复计算

### Modified Capabilities
（无现有 spec 需要修改）

## Impact

- **代码文件**：`pob_calc/what_if.py` 拆为 8 个文件 + 1 个 re-export 入口
- **新增文件**：`lua_env.py`、`full_analysis.py`、`sensitivity.py`、`dps_breakdown.py`、`aura_analysis.py`、`passive_analysis.py`、`defence.py`、`report_formatter.py`
- **改造文件**：`__init__.py`（增加 `full_build_analysis` 入口）、`build_cache.py`（ws 子目录）、`report_generator.py`（套装 tabs）
- **向后兼容**：`what_if.py` 保留所有现有 import 路径
- **缓存格式**：从扁平结构变为 `ws1/`、`ws2/` 子目录，旧缓存需重新生成
