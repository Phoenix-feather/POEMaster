---
name: pob-build-analyzer
description: POB构筑分析器 - 解码POB分享码，通过Python驱动POB的Lua计算引擎，进行构筑数值计算、What-If对比分析和优化建议。
---

# POB Build Analyzer v1

**POB 构筑运行时分析器**

解码 POB（Path of Building）分享码，通过 Python-Lua 互操作（lupa + Lua 5.4）驱动 POB 的原生计算引擎，对构筑进行精确数值计算、What-If 对比和优化分析。

> **⚠️ POE2 前提声明**
>
> 本技能基于 **POE2** 数据（GameVersions `0_x` 版本体系），所有公式和机制均以 POB 的 POE2 计算模块组为准：
>
> | 模块 | 职责 |
> |------|------|
> | `Calcs.lua` | 计算系统入口，加载并协调所有子模块 |
> | `CalcSetup.lua` | 环境初始化（modDB、敌人配置、override） |
> | `CalcPerform.lua` | 编排 offence/defence 计算流程 |
> | `CalcActiveSkill.lua` | 主动技能构建（flag、tag、辅助链接） |
> | `CalcOffence.lua` | 进攻计算（伤害公式、转换/增益、暴击、穿透、DPS 组装） |
> | `CalcDefence.lua` | 防御计算（生命/ES/护甲/闪避/抗性/EHP） |
> | `CalcTriggers.lua` | 触发系统（触发速率、CD、元技能能量） |
> | `CalcMirages.lua` | 幻影（Mirage）技能计算 |
> | `CalcTools.lua` | 工具函数（`calcLib.mod`、`armourReductionF` 等） |
> | `CalcBreakdown.lua` | UI 展示用的 breakdown 生成器 |
> | `CalcSections.lua` | Calcs 标签页 UI section 定义 |
>
> 已确认的 POE2 特征：Spirit 系统、Crossbow/Bolt/Reload 系统、Grenade 机制、ArmourBreak、物理专属吸血（`LifeLeechBasedOnElementalDamage` 转换）。
> POE1 残留代码（SpellDodgeChanceMax、SiphoningCharges 等）均为死代码，值恒为 0，不影响计算。

---

## ⚠️ 光环模拟前提

**光环/精魄技能模拟使用动态数据读取**，包括：

- **DPS 贡献测试（7A）**：移除光环时，效果参数（EC MORE 值、Charge 数量）从构筑实际数据动态读取
- **候选光环推荐（7B）**：添加光环时，使用满级数据（maxLevel），精魄消耗从 `spiritReservationFlat` 动态读取
- **精魄辅助推荐（7C）**：辅助效果按满级计算，精魄消耗动态读取
- **数据一致性校验（7E）**：自动检测 EC 等级非标准、Charge 数量异常等情况并发出警告

**动态读取规则**：
1. EC MORE 值：从构筑 EC 宝石实际等级 + `statSets` 表读取（非硬编码 59%）
2. Charge 数量：从 `env.player.output.{Type}ChargesMax` 读取（非硬编码 3）
3. 精魄消耗：从 `grantedEffect.levels[maxLevel].spiritReservationFlat` 读取（非硬编码值）

**报告标注**：模拟值后会标注实际等级，如 `59% MORE (Lv21)`，非标准等级会触发一致性警告

---

## ⚠️ 重要说明：能力边界

### ✅ 能做什么

- **构筑加载与计算**：解码 POB 分享码 → 加载天赋/装备/技能/配置 → 运行 POB 计算引擎 → 获取完整 output
- **数值精度验证**：将计算结果与 POB 桌面版 PlayerStats 逐项对比
- **What-If 分析**：临时增删天赋点、替换装备、修改技能宝石，对比前后数值变化
- **灵敏度分析**：向 modDB 注入 modifier，使用 33 个语义正确的 profile 覆盖伤害/暴击/速度/穿透/投射物等维度（含 flag-based 类型如 spell/attack/melee/projectile/dot damage 和 cast/attack speed），等基准对比（固定 DPS 目标反算所需投入），含每单位 DPS 贡献率
- **完整分析流程**：`full_analysis()` 一次调用完成灵敏度 + 天赋价值 + 天赋探索 + 珠宝诊断
- **珠宝诊断**：检查每个珠宝的加载状态、mod 解析、GrantedPassive（Megalomaniac 等）、DPS 贡献
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

两个技能现已**联动**：`pob-build-analyzer` 通过 `data_bridge.py` 直接读取 `poe-data-miner` 的 `entities.db` 获取结构化游戏数据（技能等级数值、辅助宝石效果等）。

### Python 依赖

```
lupa>=2.0        # Python-Lua 互操作（Lua 5.4 运行时）
```

---

## AI 模型操作指南

> **本文档面向 AI 模型**，定义了操作本技能时的唯一正确流程。
> 违反此处规则的任何操作都是错误的，不依赖 AI 模型的"判断"。

### 标准分析流程

```
from pob_calc import POBCalculator

# 1. 创建计算器（from_current / from_build_id / 构造函数）
calc = POBCalculator.from_current()

# 2. 运行完整分析
result = calc.full_analysis(skill_name="spark")

# 3. 生成报告并保存
report = POBCalculator.format_report(result)
report_path = calc.get_report_path("spark")
with open(report_path, 'w', encoding='utf-8') as f:
    f.write(report)

# 4. 在 CodeBuddy 内置浏览器中打开预览 ← 必须！
preview_url(f"file:///{report_path}")
```

### 禁止事项

| 禁止 | 正确做法 |
|------|---------|
| 创建 `_*.py` 临时脚本 | 用 `python -c "..."` 内联执行 |
| 创建 `_*.json` 临时数据文件 | 使用 BuildCache 或 API |
| 只在对话中读取报告内容展示 | `preview_url()` 打开预览 |
| 创建 `_new.py` / `_v2.py` 替代旧文件 | 在原文件上迭代更新 |

### 调试流程

```
1. 读 lints → 识别错误
2. 读取源文件 → 直接修改源文件
3. 重新运行分析（python -c 内联）
4. preview_url 打开报告验证修复
```

### 报告预览路径格式

```
file:///g:/POEMaster/.codebuddy/skills/pob-build-analyzer/cache/builds/{build_id}/report_{skill}.md
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
│   ├── data_bridge.py    # 数据桥接器 (从 poe-data-miner 读取结构化数据)
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
    ├── data_bridge.py    (依赖 sqlite3, 读取 poe-data-miner/entities.db)
    └── what_if.py        (依赖 calculator.py, data_bridge.py)
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

### 完整分析（一次调用）

```python
# 完整分析：灵敏度 + 天赋价值 + 天赋探索 + 珠宝诊断
report = calc.full_analysis(target_pct=20.0)

# 灵敏度排序（含每单位 DPS 贡献）
for r in report["sensitivity"]:
    print(f"{r['label']:40s} {r['mod_type']:4s} needed={r['needed_value']}{r['unit']}  "
          f"dps/unit={r['dps_per_unit']:.3f}%")

# 珠宝诊断（检查 Megalomaniac 等）
for j in report["jewel_diagnosis"]:
    print(f"{j['name']:25s} mods={j['mod_count']}  DPS={j['dps_pct']:+.1f}%  "
          f"granted={j['granted_passives']}")
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

### v1.0.18 (2026-03-25)

光环与精魄分析（Section 7）— 完整实现光环 DPS 贡献测试、条件参数范围分析、动态 ifSkill 配置发现：

- **`aura_spirit_analysis()` 新增 API**：一次调用完成 4 个子分析：
  - **7A 现有光环移除测试**：逐一禁用构筑中的光环/精魄保留技能，测量 DPS/EHP 变化。正确区分 Aura(Purity of Fire)、POE2 spirit-reserved persistent(Trinity/Charge Infusion/Elemental Conflux)，排除 Blink(DodgeReplacement)、Life Remnants/Siphon Elements(GeneratesRemnants)、Curse(AppliesCurse)、Triggered(Triggered)
  - **7B 潜在光环推荐**：测试 6 个候选光环（Archmage、Trinity、Charge Infusion、Charge Regulation、Attrition、Elemental Conflux），精魄不足时标记"精魄不足"
  - **7C 精魄辅助推荐**：测试向现有光环添加精魄辅助（Haste/Zealotry/Wrath/Anger/Precision），按光环×辅助矩阵组合
  - **7D Spirit Budget 汇总**：总精魄、已用精魄、可用精魄、推荐精魄

- **条件参数范围测试**：
  - `_discover_ifskill_configs()`：动态扫描 ConfigOptions.lua 中所有 `ifSkill` + `count` 类型配置，匹配当前构筑光环。支持 string 和 table 两种 ifSkill 格式。通过 `_PROBE_MAX=99999` 探测实际 clamp 上限
  - `_test_aura_config_range()`：对每个条件配置测试 min(0) 和 max(actual_max) 端点，展示 DPS 范围（如 Trinity Resonance 0~300: 37468~66616）
  - `_set_config_and_rebuild()`：通用 ConfigTab 值设置 + modList 重建（支持 check/count/integer/countAllowZero/float/list）
  - 完全动态化，POB 未来新增光环自动适配

- **报告格式增强**：
  - 7A 表格新增"条件参数范围"列，显示参数范围和对应 DPS
  - Section 编号修正：光环分析 Section 7，总结与建议 Section 8

- **构建缓存增强**：
  - `BuildCache.save_report()` / `get_report_path()` / `load_report()`：报告持久化到构筑目录
  - `POBCalculator.full_analysis()` 通过缓存工厂方法创建时自动持久化

- **已知限制**：
  - 当前测试构筑精魄 425/425（无空闲），7B/7C 的实际 DPS 测试未被触发
  - Charge Infusion/Elemental Conflux 显示 0% DPS 变化（POB 可能未完全计算动态效果）

### v1.0.17 (2026-03-24)

DPS 来源拆解大幅扩展 — 补全 15 个缺失公式组件：

- **POE2 前提声明**：在 SKILL.md 头部写入 POE2 前提，明确所有公式以 POE2 CalcOffence.lua 为准

- **新增 7 个 Section（Lua 端查询 + Python 端解析 + 报告渲染）**：
  - **CONV_GAIN**：伤害转换（`conversionTable`）+ 伤害增益（`gainTable`），解决 `DamageGainAsLightning` 等 mod 不出现在拆解中的问题
    - 转换支持两步处理：技能转换 → 全局转换
    - Gain 支持全部 mod 名格式：`DamageGainAs{Type}`、`{From}DamageGainAs{To}`、`ElementalDamageGainAs{Type}`、`NonChaosDamageGainAs{Type}`、`SkillDamageGainAs{Type}`
    - 每条 Gain 输出 Tabulate 来源（可追溯到具体装备/天赋）
  - **CONV_MULT**：每种伤害类型的未转换比例（`conversionTable[type].mult`）
  - **EFF_MULT**：有效 DPS 乘数 = 穿透/抗性/受伤增加
    - 公式：`effMult = (1+takenInc/100) × takenMore × (1 - max(resist-pen, 0)/100)`
    - 物理使用护甲减伤公式（含 ArmourBreak POE2 机制）
    - 以 CALCS 模式运行以获取 `output[dt.."EffMult"]`
  - **DOUBLE_TRIPLE**：双倍/三倍伤害概率 + ScaledDamageEffect
  - **HITCHANCE**：命中率（准确度 × 格挡）
  - **DPS_MULT**：技能 DPS 乘数（`skillData.dpsMultiplier`）
  - **COMBINED_DPS**：组合 DPS 构成 = Hit + DOT(Bleed/Poison/Ignite) + Impale + Mirage + Cull + Reservation

- **报告增强**：
  - 新增 `formula_detail` 字段显示公式计算过程
  - 大数值自动使用逗号分隔（>1000）

- **已知限制**：
  - effMult 的敌人抗性值来自 `enemyDB:Sum("BASE")`，不含 curse 等动态 debuff 的全部细节
  - 转换表只展示最终结果（两步处理后），不展示中间步骤

### v1.0.16 (2026-03-24)

报告自动持久化 — 分析结果与缓存构筑一一对应：

- **`BuildCache.save_report()`**：将分析数据 + 报告写入构筑目录
  - `analysis_{skill}.json`：原始分析数据（可二次查询）
  - `report_{skill}.md`：格式化 Markdown 报告（可直接阅读）
  - 技能名规范化：`Ball Lightning` → `ball_lightning`
- **`BuildCache.load_report()` / `get_report_path()`**：读取已保存的报告
- **`POBCalculator.full_analysis()` 自动持久化**：通过缓存工厂方法创建的实例，分析完成后自动保存报告到构筑目录
- **`POBCalculator.get_report()` / `get_report_path()`**：便捷读取已保存报告
- 消除临时文件：不再需要 `_run.py`、`_report.md`、`_r.json`

### v1.0.15 (2026-03-24)

构筑缓存系统 + 表格格式报告：

- **`BuildCache` 构筑缓存管理器**（`build_cache.py`）：
  - `save(share_code)` → 解码 XML + 生成 `{class}_{ascendancy}_Lv{level}_{hash[:8]}` ID + 缓存到 `cache/builds/`
  - `current.txt` 指针文件标识当前活跃构筑
  - `meta.json` 存储元信息 + 静态提取的技能列表（不启动 Lua）
  - LRU 自动淘汰（默认保留 10 个），幂等保存（XML hash 去重）
  - 序号删除（"3", "2-5", "1,3,5"）+ 全部清理

- **`POBCalculator` 缓存便捷入口**：
  - `save_build(share_code)` → 保存到缓存
  - `from_current()` → 从当前活跃构筑创建计算器（无需 share code）
  - `from_build_id(build_id)` → 指定构筑加载
  - `list_builds()` → 格式化表格（含 ★ 标记当前构筑）
  - `remove_builds(indices)` / `clear_builds()` → 清理

- **`format_report(data)` 表格格式报告**：
  - 所有详细来源均以 `| 来源 | 类别 | 值 |` 表格展示
  - 6 个 section：基线概览、DPS 来源拆解、灵敏度分析、天赋价值、天赋探索、珠宝诊断

### v1.0.14 (2026-03-24)

主技能指定 — 支持自然语言指定分析目标技能：

- **`skill_name` 参数**：`full_analysis(skill_name="ball lightning")` 按名称模糊匹配技能组
  - 大小写不敏感，支持部分匹配（"ball" 可匹配 "Ball Lightning"）
  - 精确匹配优先，部分匹配在多候选时选 DPS 最高者
  - 未找到匹配时 fallback 到默认逻辑（构筑默认 → 自动最高 DPS）
- **三级优先级**：用户指定 skill_name > 构筑 XML 默认 mainSocketGroup > 自动扫描最高 DPS
- **API 签名变更**：
  - `what_if.full_analysis(lua, calcs, ..., skill_name=None)`
  - `POBCalculator.full_analysis(..., skill_name=None)`

### v1.0.13 (2026-03-24)

DPS 来源拆解优化 — INC 按伤害类型分组 + Item 部位标注 + 珠宝来源分类修复：

- **INC/MORE 按 mod 类别分组（不再按伤害类型重复）**：
  - 旧逻辑：对每个活跃伤害类型（Lightning/Cold/Fire）分别 Tabulate，产生 3 组几乎相同的 INC 来源（共享 `Damage` + `ElementalDamage`），15 个 formula items
  - 新逻辑：按 mod 名称类别（`Damage` / `ElementalDamage` / `ColdDamage` 等）独立 Tabulate，每类只出现一次，13 个 formula items
  - 每个类别标注影响的伤害类型，如 `通用伤害 INC (Lightning,Cold,Fire)`、`冰霜伤害 INC (Cold)`
  - 还原了 POB 的 INC 合并语义：`Damage INC` 对所有类型生效，`ElementalDamage INC` 对元素类型生效，`ColdDamage INC` 仅对冰霜生效

- **Item 来源加部位标注**：
  - 通过 `build.itemsTab.orderedSlots` 建立物品名 → slot 映射（因 mod source 中 itemId 恒为 -1）
  - label 格式：`"Rapture Shard, Sapphire (Jewel)"`, `"Damnation Grip, Unset Ring (Ring 2)"`, `"Adonia's Ego, Siphoning Wand (Weapon 1)"`
  - 珠宝 slot 名简化：`"Jewel 61834"` → `"Jewel"`

- **v1.0.12 珠宝来源分类修复（同版合入）**：
  - GrantedPassive 珠宝 mod（如 Megalomaniac "Allocates X"）使用 `source="Tree:{grantedNodeId}"`，其中 grantedNodeId 是天赋节点自身 ID 而非珠宝插槽 nodeId
  - 扩展 Lua `jewelNodeMap`：遍历 `jItem.modList` 找 GrantedPassive，通过 `tree.notableMap` 查找 granted 节点 ID
  - `_classify_source()` 新增 `jewel_node_ids` 参数，正确分类为 `"Jewel"` 而非 `"Tree"`
  - Lucky Hits 现在正确标记为 `[Jewel] Megalomaniac, Diamond → The Spring Hare`

### v1.0.11 (2026-03-24)

DPS 来源拆解（DPS Source Breakdown）：

- **`dps_breakdown()` 新增 API**：
  - 将当前 DPS 的每个公式项拆解到具体来源（天赋/装备/宝石/配置）
  - **Output-driven**：从 `output.*` 非零值判断活跃公式组件，跳过未激活的部分
  - **两层粒度**：
    - 第一层：按公式项分组（Base Damage / Damage INC / Damage MORE / Speed / CritChance / CritMultiplier / Lucky Hits）
    - 第二层：每组内逐条列出 mod 来源和贡献值
  - **Label 可读化**：通过 Lua 端查表将 `Tree:58016` → `"Arcane Intensity"`，`Item:3:xxx` → 物品名，`Skill:xxx` → 宝石名
  - **category_summary**：每个公式项按来源类别（Tree/Item/Skill/Base/Config）汇总贡献值
  - 支持独立调用 `calc.dps_breakdown()` 和 `full_analysis()` 集成调用

- **Base Damage 完整拆解**：
  - 三来源分离：宝石/武器基础 + added flat damage（可 Tabulate）+ baseMultiplier
  - 公式：`base = (gem + Σ added × addedMult) × baseMultiplier`
  - Added damage 的 Min/Max 合并为均值展示，每条来源标注 `+min-max` 范围

- **Tabulate API 利用**：
  - 核心依赖 `ModStore:Tabulate(modType, cfg, ...)` 返回 `[{value, mod}]` 对
  - `entry.value` 是条件评估后的值（非原始 `mod.value`）
  - MORE 类型 `entry.value` 是百分比原值（如 39 = "39% more"），非乘数

- **集成到 `full_analysis()`**：新增 step 8，返回 `dps_breakdown` 字段

- **已知限制**：
  - 仅拆解 DPS 相关公式项，不含 EHP/防御
  - Lucky Hits 的 Flag-based 触发（如 LuckyHits/CritLucky）显示为固定 100%
  - damageStatsForTypes 合并逻辑在 Lua 端复现，与 CalcOffence.lua:52-63 一致

- **代码质量修复**（6 项）：
  1. **分隔符冲突**：`line.split('|')` 无限分割 → 按 section 类型使用 `maxsplit` 保护最后一个含 Tabulate 数据的字段
  2. **同 source 多 mod 覆盖**：`_merge_added_damage_sources` 中同一来源的多条 mod 从直接覆盖改为累加
  3. **CritChance 缺宝石基础暴击率**：`Tabulate("BASE", "CritChance")` 不含技能固有 baseCrit，新增专用解析器 `_parse_crit_base`，读取 `ms.skillData.CritChance` 作为 "技能基础暴击率" 显示
  4. **Speed 缺基础速度**：新增 `Speed_BASE` 公式项，攻击技能取 weaponData.AttackRate、法术取 1/castTime、触发技能取 output.Speed（computed trigger rate）
  5. **Lua `source` 变量名混淆**：重命名为 `damageSource`，避免与 mod source 概念冲突
  6. **`_is_base` 浮点保护**：`_parse_base_damage` 添加 `total_avg < 0.01` 阈值检查

### v1.0.10 (2026-03-24)

珠宝诊断修复 + GrantedPassive DPS 测试 + removeNodes key 格式修复：

- **`what_if_nodes()` removeNodes key 格式修复**：
  - 根因：CalcSetup.lua 中 `override.removeNodes` 使用**两种不同的 key 格式**：
    - 第 734 行（普通天赋）：`removeNodes[node]` — 使用节点**对象**作为 key
    - 第 1291 行（GrantedPassive）：`removeNodes[node.id]` — 使用整数 **node.id** 作为 key
  - 之前 `what_if_nodes()` 只设置了 `[node]=true`，对 GrantedPassive 天赋无效
  - 修复：同时设置两种 key（`removeNodes[node]=true` + `removeNodes[node.id]=true`），两条代码路径均可匹配
  - 影响：Megalomaniac 分配的天赋（The Spring Hare / Savoured Blood 等）现在可以正确通过 `what_if_nodes(remove=[...])` 移除并测试 DPS 影响

- **`diagnose_jewels()` 珠宝移除方式修复**：
  - 普通珠宝：同时清除 `slot.selItemId=0` **和** `build.spec.jewels[nodeId]=nil`（之前只清除 selItemId，CalcSetup 仍可能从 spec.jewels 读取物品数据）
  - 修复后稀有珠宝的 DPS 贡献正确反映（如 Chimeric Spark -4.5%, Rapture Shard -4.8%）

- **`diagnose_jewels()` GrantedPassive 珠宝 DPS 测试**：
  - 对包含 `GrantedPassive` 的珠宝（如 Megalomaniac），移除物品不会影响 DPS（天赋已分配）
  - 新增**节点移除测试**：通过 `notableMap[passive]` 查找 granted 节点，用 `override.removeNodes` 移除
  - 返回新增字段：
    - `granted_dps_pct`: 仅移除 granted 节点的 DPS 变化
    - `dps_source`: `"item_mods"` / `"granted_passives"`（标识主要 DPS 来源）
  - `dps_pct` 取物品移除和节点移除中影响更大的值

- **临时文件清理**：删除 `_diag_jewel.py` 和 `_diag_jewel2.py`

### v1.0.9 (2026-03-24)

完整分析流程 + 珠宝诊断 + 每单位 DPS 贡献：

- **`full_analysis()` 完整分析流程**：
  - 一次调用完成所有分析：基线计算 → 灵敏度分析 → 天赋价值 → 天赋探索 → 珠宝诊断
  - 消除了之前每次都需要临时生成脚本的问题
  - 返回结构化 dict，可直接用于构筑优化决策
  - API: `calc.full_analysis(target_pct=20.0, exploration_min_pct=0.5)`

- **`diagnose_jewels()` 珠宝诊断**：
  - 检查每个珠宝的加载状态：物品是否解析成功、mod 数量、GrantedPassive 列表
  - 特别关注 Megalomaniac 等通过 "Allocates" 分配天赋的珠宝
  - 通过替换空物品测试每个珠宝对 DPS 的贡献
  - 返回 variant 信息（Megalomaniac 的 3-variant 系统）
  - 状态标记：ok / empty / no_base / no_mods

- **`dps_per_unit` 每单位 DPS 贡献**：
  - 灵敏度分析结果新增 `dps_per_unit` 字段
  - 计算方式：`actual_pct / needed_value`（即每 1 单位注入带来多少 % DPS）
  - 例：CritChance BASE 的 dps_per_unit = 20% / 3.5 = 5.71，而 Fire Damage INC = 20% / 155 = 0.13
  - 值越大 = 每单位投资回报越高

### v1.0.8 (2026-03-23)

Flag-based profiles 补全 + 技能类型精确排除 + 天赋探索误报修复：

- **新增 5 个 flag-based profiles**：
  - `cast_speed_inc`: 施法速度 (`Speed INC + ModFlag.Cast=0x10`)，法术构筑专属
  - `attack_speed_inc`: 攻击速度 (`Speed INC + ModFlag.Attack=0x01`)，攻击构筑专属
  - `melee_damage_inc`: 近战伤害 (`Damage INC + ModFlag.Melee=0x100`)，攻击构筑专属
  - `projectile_damage_inc`: 投射物伤害 (`Damage INC + ModFlag.Projectile=0x400`)，投射物技能专属
  - `dot_damage_inc`: 持续伤害 (`Damage INC + ModFlag.Dot=0x08`)，DOT 构筑专属
  - POB 中 "cast speed" 不是 `CastSpeed INC`，而是 `Speed INC` + `flags=ModFlag.Cast`
  - POB 中 "melee damage" 不是 `MeleeDamage INC`，而是 `Damage INC` + `flags=ModFlag.Melee`
  - 其余同理，均通过 ModParser.lua modNameList 确认

- **`_detect_skill_flags()` 精确排除**：
  - 新增完整技能 flag 检测：从 `skillCfg.flags` 位运算提取 spell/attack/dot/cast/melee/projectile/area
  - CalcActiveSkill.lua:446-467 确认：非攻击技能自动加 `ModFlag.Cast`，法术再加 `ModFlag.Spell`
  - 排除逻辑从简单的 spell/attack 二分 → 精确的多维排除：
    - 法术构筑：排除攻击/近战/flat damage + attack speed
    - 攻击构筑：排除法术/施法速度
    - 非投射物：排除 projectile damage
    - 非 DOT：排除 dot damage

- **天赋探索误报修复**：
  - v1.0.7 中报告的 "Doom Cast" (+15.8%), "Cruel Implement" (+14.2%), "Devastating Blows" (+14.2%) 误报已消失
  - 根因：v1.0.3 多行 stat 合并修复后，Keystone 的条件 tag 被正确解析，POB mod 系统的 flag/condition/SkillType 匹配正确过滤了不适用的 mod
  - 确认：POB 的 `SumInternal` + `EvalMod`（ModStore.lua）通过 `band(cfg.flags, mod.flags) == mod.flags` 匹配 ModFlag、通过 SkillType tag 匹配技能类型、通过 Condition tag 匹配装备条件
  - 验证：Spark 构筑 Top 20 未分配天赋全部合理（Arcane Intensity +18.9%, Stand and Deliver +17.4%, Heavy Ammunition +16.8%）

- **珠宝/涂油/妄想症审计**：
  - ✅ 珠宝已正确加载：`build_parser.py` 提取 socket 数据，`build_loader.py` 创建动态 `Jewel {nodeId}` 槽位，`CalcSetup.lua` 处理半径/Timeless 珠宝
  - ⚠️ 星团珠宝（Cluster Jewel）子图未构建：`BuildClusterJewelGraphs()` 未被调用，星团珠宝合成节点不会被创建（已知 gap）
  - ✅ POE2 没有涂油（Anoint）机制
  - ✅ "Allocates \<node\>" 装备词缀已正确处理：ModParser.lua 解析 → `GrantedPassive` mod → CalcSetup.lua 自动分配天赋节点

- **Profile 总数**: 26 → 33 个（新增 5 个 flag-based + 之前已有的 spell_damage 和 attack_damage）

### v1.0.7 (2026-03-23)

Spell/Attack Damage profile + 所需值单位 + 天赋探索：

- **新增 Spell/Attack Damage profile**：
  - `spell_damage_inc`: 法术伤害增加 (`Damage INC + ModFlag.Spell`)，法术构筑专属
  - `attack_damage_inc`: 攻击伤害增加 (`Damage INC + ModFlag.Attack`)，攻击构筑专属
  - POB 中 "increased spell damage" 不是 `SpellDamage INC`，而是 `Damage INC` + `flags=ModFlag.Spell(0x02)`
  - `_inject_profile()` 新增 `flags` 参数支持，通过 `env.modDB:NewMod(..., flags)` 注入带标志的 mod
  - 自动排除逻辑双向化：法术排除攻击专属，攻击排除法术专属

- **所需值单位**：
  - 每个 profile 新增 `unit` 字段（`"%"` / `""`）
  - `sensitivity_analysis()` 返回结果包含 `unit` 字段
  - INC/MORE/BASE(暴击/穿透等) → `"%"`，投射物/flat damage → `""`

- **天赋探索 (`passive_node_exploration`)**：
  - 新增 `_get_unallocated_notable_nodes()`: 获取全部未分配 Notable/Keystone（排除不同升华的节点）
  - 新增 `passive_node_exploration()`: 逐个添加未分配天赋，评估 DPS/EHP 收益
  - 使用 POB 原生 `override.addNodes` 机制，非破坏性
  - 支持 `min_dps_pct` 阈值过滤低影响节点
  - 发现该构筑 top 潜力天赋：Doom Cast (+15.8%), Cruel Implement (+14.2%), Devastating Blows (+14.2%)

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
