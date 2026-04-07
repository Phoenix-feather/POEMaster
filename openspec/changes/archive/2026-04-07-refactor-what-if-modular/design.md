## Architecture

### 目标文件结构

```
pob_calc/
├── __init__.py              ~600   POBCalculator 入口（改造）
├── lua_env.py               ~300   NEW: Lua 状态管理器
├── full_analysis.py         ~400   NEW: 多技能×套装编排层
├── sensitivity.py          ~1200   提取自 what_if.py L80-1290
├── dps_breakdown.py        ~1600   提取自 what_if.py L2250-3820
├── aura_analysis.py        ~2000   提取自 what_if.py L3820-6620
├── passive_analysis.py      ~600   提取自 what_if.py L1520-2250
├── defence.py               ~500   提取自 what_if.py L6250-6560
├── report_formatter.py     ~1300   提取自 what_if.py L7300-8593
├── what_if.py               ~100   RE-EXPORT 兼容层
├── calculator.py            ~160   不变
├── build_loader.py         ~1350   不变
├── build_parser.py          ~150   不变
├── build_cache.py           ~600   改造：ws 子目录
├── decoder.py               ~120   不变
├── runtime.py               ~250   不变
├── compat.py                ~200   不变
├── data_bridge.py           ~300   不变
└── pob_unimplemented.py     ~340   不变
```

### LuaEnvManager 设计

```
class LuaEnvManager:
    lua: LuaRuntime
    calcs: module
    _sim_mods_snapshot: list      # 首次 rebuild 时提取的 sim mods

    ── 核心方法 ──

    calc() → dict                 # 计算当前状态 output
    rebuild_modlist()             # 唯一 modList 重建入口

    ── 上下文管理器 ──

    config_scope()                # 保护 configTab.input + modList
    gem_scope()                   # 保护 gem.enabled + group.enabled
    skill_scope(name)             # 切换 mainSocketGroup
    weapon_set_scope(ws)          # 切换武器套装

    ── sim mods ──

    strip_sim_mods() → token      # 暂移除 sim mods（用于 mod 注入测试）
    restore_sim_mods(token)       # 恢复
```

**状态快照机制**：通过 Lua 全局表保存/恢复，每个 scope 层级独立，支持嵌套。

```lua
-- config_scope 快照
_env_snapshots[token] = {
    input = deep_copy(configTab.input),
    modList = configTab.modList,         -- 引用保存
    enemyModList = configTab.enemyModList,
}

-- gem_scope 快照
_env_gem_snapshots[token] = {
    gems = { {groupIdx=1, gemIdx=1, enabled=true}, ... },
    groups = { {idx=1, enabled=true}, ... },
}
```

### 分析编排流程

```
full_build_analysis(env, skills?, weapon_sets?)
│
├─ Phase 0: 全局分析（每套装一次，不随技能变）
│  for ws in weapon_sets:
│    with env.weapon_set_scope(ws):
│      global_baseline = env.calc()
│      defence = defence_overview(global_baseline)
│      resource = resource_overview(global_baseline)
│      recovery = life/mana_recovery(global_baseline)
│      jewels = diagnose_jewels(env)
│      aura = aura_spirit_analysis(env)
│
├─ Phase 1: 技能分析（每技能×每套装）
│  for ws in weapon_sets:
│    with env.weapon_set_scope(ws):
│      for skill in skills:
│        with env.skill_scope(skill):
│          baseline = env.calc()
│          sensitivity = sensitivity_analysis(env)
│          passives = passive_node_analysis(env)
│          dps_bd = dps_breakdown(env)
│
├─ Phase 2: 对比（如果多套装）
│  comparison = compare_weapon_sets(ws1_data, ws2_data)
│
└─ Phase 3: 持久化 + 报告生成
   save(global, skills, comparison)
   generate_html_report(build_id)
```

### 武器套装切换实现

```lua
-- env.weapon_set_scope 内部 Lua 操作：
function switch_weapon_set(use_second)
    -- 1. 更新 itemsTab
    build.itemsTab.activeItemSet.useSecondWeaponSet = use_second

    -- 2. 更新天赋 allocMode
    --    weaponSet=1 的节点在 ws2 下变为未分配
    --    weaponSet=2 的节点在 ws1 下变为未分配
    for nodeId, node in pairs(build.spec.nodes) do
        if node.weaponSet then
            if use_second then
                node.alloc = (node.weaponSet == 2)
            else
                node.alloc = (node.weaponSet == 1)
            end
        end
    end

    -- 3. 技能组：slot 绑定的 weaponSet 决定可用性
    --    "Weapon 1" slot → ws1 专属
    --    "Weapon 1 Swap" slot → ws2 专属
    --    无 slot → 两套装通用
end
```

### 缓存格式

```
cache/builds/{build_id}/
├── meta.json
├── build.xml
├── global.json              # 套装无关（build_modifiers, attributes）
├── ws1/
│   ├── global.json          # 套装1 全局（defence, aura, jewels）
│   └── skills/
│       ├── spark.json       # 套装1×spark
│       ├── spark.md
│       ├── comet.json
│       └── comet.md
├── ws2/                     # 如果有
│   ├── global.json
│   └── skills/
│       └── cackling_companions.json
├── comparison.json          # 套装对比
└── report.html
```

### 函数签名迁移

```python
# 旧签名（散在 what_if.py 中）
def sensitivity_analysis(lua, calcs, profiles=None, target_pct=20.0, baseline=None)
def aura_spirit_analysis(lua, calcs, baseline=None, skill_flags=None, dps_breakdown=None)
def _test_remove_skill_group(lua, calcs, group_idx, baseline, ...)

# 新签名（各自模块中）
def sensitivity_analysis(env: LuaEnvManager, profiles=None, target_pct=20.0, baseline=None)
def aura_spirit_analysis(env: LuaEnvManager, baseline=None, skill_flags=None, dps_breakdown=None)
def _test_remove_skill_group(env: LuaEnvManager, group_idx, baseline, ...)
```

所有内部 `lua.execute(...)` 和 `calc_fn(lua, calcs)` 改为 `env._lua.execute(...)` 和 `env.calc()`。

`_test_aura_config_range`、`_test_mod_effect` 等需要临时修改状态的函数，改用 `env.config_scope()` / `env.gem_scope()`。

### 向后兼容

```python
# what_if.py (re-export 入口, ~100 行)
from .sensitivity import sensitivity_analysis, SENSITIVITY_PROFILES
from .dps_breakdown import dps_breakdown
from .aura_analysis import aura_spirit_analysis
from .passive_analysis import passive_node_analysis, passive_node_exploration, diagnose_jewels
from .defence import defence_overview, resource_overview, life_recovery_analysis, mana_recovery_analysis
from .report_formatter import format_report
from .full_analysis import full_analysis
from .lua_env import LuaEnvManager

# 兼容旧的 (lua, calcs, ...) 调用方式
# 每个模块的公共函数接受 env 或 (lua, calcs)
```

## Decisions

| 决策 | 选择 | 理由 |
|------|------|------|
| 状态管理器形态 | 统一 Manager 类 | 状态间有关联（切套装影响 config+gem+modList），统一管理更安全 |
| what_if.py 保留方式 | re-export 入口 | 零破坏现有 import |
| 拆分执行方式 | 一次全做 | 渐进拆分会导致中间态不一致 |
| 光环分析子模块 | 不再拆 _config_test/_mod_sim | 保持 aura_analysis.py 一个文件 ~2000 行，可管理 |
| 缓存格式 | ws1/ws2 子目录 | 清晰，支持未来更多套装 |
| HTML 报告 | 增加套装层级 tabs | 在技能 tabs 之上增加套装选择 |

## Risks

- **拆分过程中测试覆盖不足**：当前无自动化测试，只能靠 `full_analysis` 端到端验证
- **Lua 状态快照的完整性**：configTab.input 可能有嵌套对象，deep copy 在 Lua 端的实现需要验证
- **武器套装切换的 POB 兼容性**：`calcs.initEnv` 内部可能对 weaponSet 有额外逻辑，需要验证
