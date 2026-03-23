---
name: pob-build-analyzer
description: POB构筑分析器 - 解码POB分享码，通过Python驱动POB的Lua计算引擎，进行构筑数值计算、What-If对比分析和优化建议。
---

# POB Build Analyzer v1

**POB 构筑运行时分析器**

解码 POB（Path of Building）分享码，通过 Python-Lua 互操作（lupa + Lua 5.4）驱动 POB 的原生计算引擎，对构筑进行精确数值计算、What-If 对比和优化分析。

---

## ⚠️ 重要说明：能力边界

### ✅ 能做什么

- **构筑加载与计算**：解码 POB 分享码 → 加载天赋/装备/技能/配置 → 运行 POB 计算引擎 → 获取完整 output
- **数值精度验证**：将计算结果与 POB 桌面版 PlayerStats 逐项对比
- **What-If 分析**：临时增删天赋点、替换装备、修改技能宝石，对比前后数值变化
- **灵敏度分析**：向 modDB 注入 modifier，使用 26 个语义正确的 profile 覆盖伤害/暴击/速度/穿透/投射物等维度，等基准对比（固定 DPS 目标反算所需投入）
- **多构筑对比**：加载多个分享码，横向对比 DPS/EHP/生存等维度

### ❌ 不能做什么

- **静态数据查询**：不提供实体/机制/公式的百科式查询（那是 `poe-data-miner` 的能力）
- **自动寻优**：不会自动搜索最优天赋配点或装备组合（需人工指导 what-if 方向）
- **实时游戏数据**：无法查询赛季数据、交易市场等 POB 以外的信息
- **UI 交互**：不模拟 POB 桌面版的 UI 操作，仅驱动计算引擎

---

## 依赖关系

### 与 poe-data-miner 的关系

| | poe-data-miner | pob-build-analyzer (本技能) |
|--|----------------|---------------------------|
| **定位** | 静态数据提取与索引 | 运行时计算与优化 |
| **数据源** | POBData/ 目录下的 Lua 源文件 | POB 分享码（Base64 编码） |
| **是否运行引擎** | ❌ 不运行 | ✅ calcs.initEnv + perform |
| **依赖 lupa** | 仅 StatDescriber | 核心依赖 |
| **输出** | entities.db, formulas.db 等 | 计算结果 dict、diff 对比 |

两个技能**互不依赖**，可独立使用。未来可通过 poe-data-miner 的实体/公式数据辅助解读 what-if 结果。

### Python 依赖

```
lupa>=2.0        # Python-Lua 互操作（Lua 5.4 运行时）
```

---

## 模块结构

```
pob-build-analyzer/
├── SKILL.md              # 本文件
├── requirements.txt      # Python 依赖
├── pob_calc/             # 核心包
│   ├── __init__.py       # 公开 API: POBCalculator
│   ├── decoder.py        # 分享码编解码 + 天赋树 URL 解码
│   ├── runtime.py        # Lua 运行时创建 + C 层 stub + POB 模块加载
│   ├── compat.py         # Lua 5.4/LuaJIT 兼容补丁 + mod 修复
│   ├── build_parser.py   # XML → BuildInfo 解析
│   ├── build_loader.py   # BuildInfo → Lua build 对象灌入
│   ├── calculator.py     # initEnv + perform + output 读取
│   └── what_if.py        # override 封装 (节点/装备/技能/mod)
└── tests/                # 测试
    └── test_compare.py   # 精度对比测试
```

### 模块职责与依赖

```
__init__.py (POBCalculator)
    ├── decoder.py        (无依赖)
    ├── runtime.py        (无依赖)
    │   └── compat.py     (被 runtime 调用)
    ├── build_parser.py   (无依赖)
    ├── build_loader.py   (依赖 compat.py, decoder.py)
    ├── calculator.py     (无依赖)
    └── what_if.py        (依赖 calculator.py)
```

严格单向依赖，无循环引用。

---

## 使用方式

### 基本计算

```python
from pob_calc import POBCalculator

calc = POBCalculator(share_code="eNrtfWlz4ziyJv...")
result = calc.calculate()

print(f"Life: {result['Life']}")
print(f"DPS: {result['TotalDPS']}")
print(f"EHP: {result['TotalEHP']}")
```

### What-If 分析

```python
# 天赋点增删
diff = calc.what_if_nodes(add=[48524], remove=[45918])
# diff = {"Life": (2180, 2280, +100), "TotalEHP": (9591, 9800, +209), ...}

# 装备替换
diff = calc.what_if_item("Helmet", "Rarity: Unique\nName: ...")

# modDB 注入
diff = calc.what_if_mod("Life", "BASE", 100)
diff = calc.what_if_mod("Evasion", "INC", 50)
```

### 精度验证

```python
# 与 POB 桌面版 PlayerStats 对比
pob_stats = calc.get_pob_player_stats()  # 从 XML 中提取
spike_stats = calc.calculate()
for stat in ["Life", "Mana", "TotalEHP"]:
    print(f"{stat}: POB={pob_stats[stat]}, Calc={spike_stats[stat]}")
```

---

## CLI 命令

```bash
# 基本计算（从分享码文件）
python -m pob_calc --share-code-file cache/share_code.txt

# 精度对比
python -m pob_calc --compare cache/share_code.txt

# What-If: 添加天赋点
python -m pob_calc --share-code-file cache/share_code.txt --add-node 48524

# 灵敏度分析
python -m pob_calc --share-code-file cache/share_code.txt --sensitivity
```

---

## 技术架构

### 核心流程

```
Share Code (Base64)
    ↓ decoder.py
XML Text
    ↓ build_parser.py
BuildInfo (Python dict)
    ↓ build_loader.py
Lua build 对象 (_spike_build)
    ↓ calculator.py (calcs.initEnv + calcs.perform)
env.player.output (Lua table)
    ↓ calculator.py (读取)
Python dict {stat: value}
```

### Lua 运行时架构

```
Python (lupa)
    ↓
Lua 5.4 VM
    ├── C 层 stub (LoadModule, Inflate, 渲染 stub 等)
    ├── Lua 5.4 兼容补丁 (tostring, bit 库)
    ├── POB 核心模块
    │   ├── GameVersions.lua
    │   ├── Common.lua (OOP: new/newClass)
    │   ├── Data.lua (全局数据: gems, skills, bases)
    │   ├── ModTools.lua (mod 解析)
    │   ├── ItemTools.lua (物品处理)
    │   ├── CalcTools.lua (计算工具)
    │   └── Calcs.lua (initEnv/perform)
    └── build 对象
        ├── skillsTab.socketGroupList
        ├── itemsTab.items/slots
        ├── spec.allocNodes/tree
        └── configTab.input/modList
```

### What-If 机制

POB 原生支持两种 what-if 模式：

1. **override 模式**（无侵入）：
   ```lua
   calcs.initEnv(build, "CALCULATOR", {
       addNodes = { [nodeObj] = true },
       removeNodes = { [nodeObj] = true },
       repSlotName = "Helmet",
       repItem = newItemObject,
   })
   ```

2. **直接修改 build 模式**（侵入式）：
   ```lua
   -- 修改 socketGroupList / allocNodes / slots 等
   -- 重新 initEnv + perform
   ```

每次 `initEnv` 从 build 对象全量重建 env，所以多次调用完全安全。

---

## 已知限制

### 精度（基于单构筑测试 22/24 = 92%）

| Stat | 状态 | 说明 |
|------|------|------|
| Life, Mana, ES, Armour, Evasion | ✅ 精确匹配 | |
| Str, Dex, Int | ✅ 精确匹配 | |
| 三抗 + 混沌抗 | ✅ 精确匹配 | |
| 所有 MaximumHitTaken | ✅ 精确匹配 | |
| MovementSpeed | ✅ 精确匹配 | |
| LifeRegenRecovery | ⚠️ +125% | buff 条件差异（Vitality 光环状态） |
| TotalEHP | ⚠️ -1.1% | LifeRegen 差异下游影响 |

⚠️ **单构筑局限**：以上精度仅基于一个 Monk/Invoker 构筑测试，其他职业和构筑类型的精度未知。

### Lua 5.4 兼容性

POB 桌面版使用 LuaJIT（5.1 兼容），Spike 使用 Lua 5.4。已修复：
- `tostring` float→int 行为差异
- `bit` 库 API 兼容层
- `unpack` → `table.unpack` 映射

⚠️ 可能存在其他未发现的 5.1 vs 5.4 行为差异。

### 未验证的机制类型

- 召唤物（minion）actor
- 图腾/陷阱/地雷
- 多 ConfigSet 构筑
- 触发技能（triggered skills）的完整链路
- DOT 构筑（Poison/Bleed/Ignite）

### 环境配置

- **POBData 路径**：自动探测 `POB_DATA_PATH` 环境变量 → 常见安装位置
- **依赖**：需要 `lupa>=2.0`，底层依赖 Lua 5.4 C 库

---

## 改进路线

### Phase 1: 多构筑测试（提升覆盖率）

- [ ] 收集多职业构筑 share code（Warrior/Witch/Ranger/Mercenary/Sorceress/Monk）
- [ ] 验证非 Monk 职业的基础属性和升华是否正确
- [ ] 测试 DOT/召唤/图腾构筑
- [ ] 建立回归测试套件

### Phase 2: 数据加载完善

- [ ] 多 ConfigSet 支持
- [ ] Minion actor 计算链路
- [ ] 触发技能完整链路
- [ ] Flask/Charm 效果

### Phase 3: What-If 增强

- [ ] 宝石等级/品质调整
- [ ] 技能组重排
- [ ] 批量敏感度分析（自动扫描所有有意义的 modifier）

---

## 版本历史

### v1.0.6 (2026-03-23)

等基准灵敏度分析重设计 + INC 合并查询修复 + 双语输出：

- **INC 合并查询修复**：
  - 问题：`_query_mod_totals()` 对每个 stat 单独查询（如 `Damage INC=36%`、`ElementalDamage INC=101%`、`LightningDamage INC=0%`），但 POB 在 calcDamage() 中是合并查询的
  - 根因：CalcOffence.lua:135-136 通过 `damageStatsForTypes[typeFlags]` 自动合并 mod 名称（如 Lightning → `{"Damage", "LightningDamage", "ElementalDamage"}`），然后执行一次 `Sum("INC", cfg, unpack(modNames))`
  - 修复：新增 `_query_all_merged_inc()` 在 Lua 端复现 damageStatsForTypes 合并逻辑，自动检测主伤害类型并返回正确的合并 INC 值
  - 影响：所有伤害类 INC profile 的 `current_total` 现在显示相同的合并值，与 POB 一致

- **等基准对比设计**：
  - 问题：旧版注入固定值（+50 INC、+20 MORE、+2 BASE 等），不同维度注入量不同，DPS% 变化无法直接横向比较
  - 新设计：固定 DPS 目标（默认 +30%），通过二分搜索反算每个维度达到该目标所需的注入值
  - 结果含义：`needed_value` 越小 = 性价比越高 = 优化杠杆越大
  - 示例解读："需要 +59 INC Damage 达到 DPS +30%" vs "需要 +176 INC CritMultiplier 达到 DPS +30%" → Damage INC 性价比更高
  - 技术细节：二分搜索 max_iters=20，精度 0.5，每维度最多 22 次 Lua 计算

- **双语输出保留**：
  - 每个 profile 同时返回 `label`（英文游戏词缀）和 `description`（中文说明）
  - 之前版本误删了英文 label，现在两者同时保留

- **API 变更**：
  - `sensitivity_analysis()` 新增 `target_pct` 参数（默认 30.0）
  - 返回结构变更：`value` → `needed_value`，`target_before/after/delta/target_pct` → `needed_value/target_pct/actual_pct/current_total`
  - `SENSITIVITY_PROFILES` 从 tuple 改为 dict，新增 `search_max` 字段

- **内部重构**：
  - `_run_multi_mod()` → `_inject_and_calc()` 通用注入函数
  - `_query_mod_totals()` → `_query_mod_total_single()` + `_query_all_merged_inc()`
  - 新增 `_inject_profile()` 和 `_binary_search_needed_value()` 等基准搜索函数

### v1.0.5 (2026-03-23)

POE2 flat damage 修正 + 简洁公式字段 + Flag 审计 + POE1/POE2 数据分离验证：

- **POE2 法术不受固定伤害加成**：
  - POE2 中法术技能不存在 "Adds X to Y damage to Spells" 词缀（POE1 遗留机制）
  - 根因：`modDB:NewMod("LightningMin", "BASE", 50, "WhatIf")` 创建 `flags=0` 的 mod，而 ModDB 匹配逻辑 `band(cfg.flags, mod.flags) == mod.flags` 中 `band(任何值, 0) == 0` 恒为 true，无 flag 的 mod 通过所有 flag 检查
  - 修正：flat damage profile 改为攻击专属（`flat_*_attack`），法术构筑自动排除
- **Flag 审计**：审查全部 26 个 profile，确认仅 flat damage（4个）存在 flag 问题。其余 22 个 profile 的真实游戏 mod 也是 `flags=0`，注入行为与真实 mod 完全一致
- **自动技能类型检测**：`_detect_is_spell()` 检查 `env.player.mainSkill.skillFlags.spell`
- **简洁公式字段**：`sensitivity_analysis()` 返回 `formula` 字段（替代旧 `explanation`），为每个 profile 生成一行增量公式：
  - INC: `(1+288%)/(1+238%) = 1.210x`
  - MORE: `×1.20 独立乘区`
  - CritMulti INC: `(1+250%)/(1+200%) = 1.167x → CritEffect ×1.078`
  - CritMulti BASE: `CritBase 100→125, ×1.250 → CritMulti 4.00→4.75 → CritEffect ×1.117`
  - 穿透: `穿透 +15%（敌人负抗时无效）`
  - Flat: `添加 50-100 基础伤害`
- **CritMultiplier 公式澄清**：
  - POE2 默认 `BASE=100`（Misc.lua `characterConstants.base_critical_hit_damage_bonus`）
  - 公式：`CritMulti = 1 + (ΣBASE/100) × (1+ΣINC/100) × ΠMORE`
  - 该构筑 BASE=100, INC=200 → CritMulti = 1 + 1×3 = 4.0
  - INC +50 → CritMulti = 4.5（+12.5%），但 DPS 变化经 CritEffect 稀释为 +7.8%（critChance=29.3%）
- **POE1/POE2 数据分离审计**：
  - ✅ `GameVersions.lua` 已适配 POE2（0_x 版本体系，无 POE1 的 3_x 版本号）
  - ✅ `Data/Misc.lua` characterConstants 数值正确（POE2 角色升级不获得属性点、充能无内建加成）
  - ✅ `CalcPerform.lua` 充能系统无 POE1 内建 per-charge 加成硬编码
  - ✅ `build_loader.py` 已含 POE2 专属槽位（Charm/Ring 3/Arm/Leg）、树版本 0_4
  - ✅ `what_if.py` flat damage 已限制攻击专属
  - ⚠️ `CalcSetup.lua` 残留 3 项 POE1 死代码（SpellDodgeChanceMax=75、SiphoningCharges/ChallengerCharges/BlitzCharges/CrabBarriers=0），值为 0 无实际影响
  - ⚠️ `ModParser.lua` 残留 DMGSPELLS 匹配模式（POE2 物品不会生成此类文本，不影响正常解析）
  - **结论：所有 POE1 残留均为死代码，不影响 POE2 计算精度**

### v1.0.4 (2026-03-23)

Mod 类型语义层 + 灵敏度分析：
- **`SENSITIVITY_PROFILES` 测试集**：26 个 DPS 相关 profile，每个对应一个游戏内真实词缀（正确的 BASE/INC/MORE 类型）。涵盖：通用/元素/物理伤害（INC/MORE）、暴击率/暴击伤害（INC/BASE）、施法速度（INC/MORE）、穿透（BASE）、投射物/AoE/持续时间、固定伤害（Min+Max）。
- **`sensitivity_analysis()` 函数**：批量注入 modifier 并排序，支持指定 profile 子集和目标 stat。
- **穿透 0 影响根因确认**：
  - 最初怀疑穿透需要 EFFECTIVE 模式
  - **实际发现**：`initEnv(build, "MAIN")` 默认 `buffMode = "EFFECTIVE"`（CalcSetup.lua:579），`mode_effective = true`，穿透和敌人抗性计算已包含
  - **真正原因**：该构筑的 POB 配置中敌人元素抗性 = 50（基础）- 80（ElementalResist BASE）= -30%，穿透无法进一步降低负抗性（CalcOffence.lua:3821）
- **CritMultiplier 类型修正**：之前错误使用 `BASE 50`（被 200% INC 放大 → +23.4%），修正为 `INC 50`（线性叠加 → +7.8%），排名从 #1 降到 #14
- **灵敏度排名**（Spark DPS=11661）：
  1. 固定冰伤 50-100 (+23.9%)
  2. 固定闪电伤 50-100 (+23.4%)
  3. 固定火伤 50-100 (+23.4%)
  4. 伤害 INC 50 (+21.0%)
  5. 元素伤害 INC 50 (+21.0%)
  6. 伤害 MORE 20 (+20.0%)

### v1.0.3 (2026-03-23)

天赋节点多行 mod 解析修复：
- **多行 stat 合并逻辑移植**：POB 桌面版 `PassiveTree:ProcessStats()` 在单行 `parseMod` 失败时，会尝试合并后续行再解析（如 Wildsurge Incantation 的 4 行 stat 合并为 1 行）。`build_loader.py` 之前缺少此逻辑，导致多行 mod 的条件 tag 丢失。
- **Bug 影响**：Wildsurge Incantation 的 `"Storm and Plant Spells: deal 50% more damage"` 被拆分为单行解析，变成无条件 `Damage MORE 50`，对所有技能生效（应该仅对 Storm/Plant Spell 生效）。
- **修复方式**：在 `build_loader.py` 的两处天赋节点 stat 解析位置（主节点 + switchNode），完整移植 POB 桌面版的多行合并+dummy mod+modLib.setSource 逻辑。
- **验证**：
  - Spark（非 Storm Spell，SkillType 无 255）添加 Wildsurge 后 DPS 无变化 ✅
  - Wildsurge modList 从 1 个无条件 mod → 3 个带 `{ type = "SkillType", skillTypeList = {Storm=255, Plant=252} }` tag 的 mod ✅
  - 防御面板精度不变：22/24 (92%) ✅

### v1.0.2 (2026-03-23)

DPS 计算修复：
- **math.pow 兼容补丁**：Lua 5.4 移除了 `math.pow`，导致 `CalcOffence.lua` 中 `m_pow = math.pow` 为 nil，所有伤害技能的 offence 计算静默失败，DPS 全部为 0。添加 `math.pow = function(x,y) return x^y end` 兼容层修复。
- 验证：切换主技能到 Spark 后 TotalDPS=11661、AverageHit=4664、Speed=2.5 正常输出
- 防御面板精度不变：22/24 (92%)

### v1.0.1 (2026-03-23)

风险修复：
- **静默异常处理**：4 处 `except Exception: pass` → 添加 `logging.warning` 日志记录
- **POB 路径硬编码**：移除 `G:/POEMaster/POBData` 硬编码，改为环境变量 `POB_DATA_PATH` + 自动探测
- **默认职业硬编码**：移除 Monk 硬编码，从 XML `classId`/`ascendClassId` 动态读取
- **zlib 解压失败**：返回空 bytes 而非 None，避免下游 nil 访问崩溃
- **load_all 返回值**：新增 `warnings` 字段，收集加载过程中的异常信息
- **SKILL.md**：补充完整风险说明和改进路线

### v1.0.0 (2026-03-23)

从 `poe-data-miner/scripts/_spike_step*.py` 提炼为独立技能。

核心能力：
- 分享码解码与 XML 解析
- Lua 运行时创建与 POB 模块加载
- 构筑完整加载（天赋树/技能/装备/配置）
- POB 计算引擎驱动（initEnv + perform）
- 灵敏度分析（modDB 注入）
- What-If 框架（天赋/装备/技能 override）
