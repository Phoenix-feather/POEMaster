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
- **灵敏度分析**：向 modDB 注入 modifier（+100 Life、+50% INC Evasion 等），观察各项输出变化
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
| LifeRegenRecovery | ⚠️ +125% | buff 条件差异 |
| TotalEHP | ⚠️ -1.1% | LifeRegen 差异下游影响 |

### Lua 5.4 兼容性

POB 桌面版使用 LuaJIT（5.1 兼容），Spike 使用 Lua 5.4。已修复：
- `tostring` float→int 行为差异
- `bit` 库 API 兼容层
- `unpack` → `table.unpack` 映射

### 未验证的机制类型

- 召唤物（minion）actor
- 图腾/陷阱/地雷
- 多 ConfigSet 构筑
- 触发技能（triggered skills）的完整链路

---

## 版本历史

### v1.0.0 (2026-03-23)

从 `poe-data-miner/scripts/_spike_step*.py` 提炼为独立技能。

核心能力：
- 分享码解码与 XML 解析
- Lua 运行时创建与 POB 模块加载
- 构筑完整加载（天赋树/技能/装备/配置）
- POB 计算引擎驱动（initEnv + perform）
- 灵敏度分析（modDB 注入）
- What-If 框架（天赋/装备/技能 override）
