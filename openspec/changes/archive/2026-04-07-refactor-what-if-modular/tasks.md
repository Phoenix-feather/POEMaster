# Tasks

## Phase 1: lua_env.py + 基础设施

- [x] **1.1** 创建 `lua_env.py` — `LuaEnvManager` 类骨架（`__init__`、`calc()`、属性访问）
- [x] **1.2** 实现 `config_scope()` — 快照/恢复 `configTab.input` + `modList` 引用
- [x] **1.3** 实现 `gem_scope()` — 快照/恢复所有 `gem.enabled` + `group.enabled`
- [x] **1.4** 实现 `skill_scope(name)` — 切换/恢复 `mainSocketGroup`
- [x] **1.5** 实现 `rebuild_modlist()` — 唯一 modList 重建入口（提取 sim mods，ConfigOptions 重建 + 追加 sim mods）
- [x] **1.6** 实现 `strip_sim_mods()` / `restore_sim_mods()` — sim mods 隔离（实现为 `without_sim_mods()` 上下文管理器）
- [x] **1.7** 实现 `weapon_set_scope(ws)` — 切换装备+天赋+技能组可用性

## Phase 2: 拆分 what_if.py

- [x] **2.1** 提取 `sensitivity.py` — 灵敏度分析（`sensitivity_analysis` + profiles 定义 + 辅助函数），函数签名改为 `(env, ...)`
- [x] **2.2** 提取 `dps_breakdown.py` — DPS 拆解（`dps_breakdown` + 所有 `_parse_*` 函数），签名改为 `(env, ...)`
- [x] **2.3** 提取 `aura_analysis.py` — 光环/精魄分析（`aura_spirit_analysis` + 所有子函数），签名改为 `(env, ...)`；内部 `_test_aura_config_range`/`_test_mod_effect` 等使用 `env.config_scope()`/`env.gem_scope()` 替代手动 save/restore
- [x] **2.4** 提取 `passive_analysis.py` — 天赋/珠宝分析（`passive_node_analysis`、`passive_node_exploration`、`diagnose_jewels`），签名改为 `(env, ...)`
- [x] **2.5** 提取 `defence.py` — 防御/资源/恢复（`defence_overview`、`resource_overview`、`life_recovery_analysis`、`mana_recovery_analysis`），这些是纯读 baseline 的函数，签名不变
- [x] **2.6** 提取 `report_formatter.py` — 报告格式化（`format_report`、`_format_section7`、`_format_section_defence` 等）
- [x] **2.7** 创建 `full_analysis.py` — 编排层（`full_analysis`、`extract_global_data`、`strip_global_data`），调用各模块
- [x] **2.8** 改造 `what_if.py` 为 re-export 入口 — 从各模块 re-export 所有公共函数，保持旧 import 兼容
- [x] **2.9** 验证：`calc.full_analysis(skill_name='spark')` 端到端输出不变

## Phase 3: 多技能 + 武器套装

- [x] **3.1** 在 `full_analysis.py` 中实现 `full_build_analysis(env, skills, weapon_sets)` — Phase 0/1/2/3 编排
- [x] **3.2** 改造 `build_cache.py` — 支持 `ws1/skills/`、`ws2/skills/` 子目录结构
- [x] **3.3** 在 `__init__.py` 增加 `POBCalculator.full_build_analysis()` 入口
- [x] **3.4** 实现 `_compare_weapon_sets()` — 套装对比数据生成
- [x] **3.5** 改造 `report_generator.py` — 支持套装层级 tabs + 对比面板
- [x] **3.6** 验证：对当前构筑运行 `full_build_analysis`，生成含两套装数据的报告
