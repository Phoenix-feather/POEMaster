## Context

当前 `full_analysis()` 对每个技能生成独立的 `analysis_{skill}.json`，包含全部数据（baseline、dps_breakdown、defence_overview、resource_overview 等）。报告（`report_{skill}.md`）和网页（`report.html`）均为单技能视图。

问题：
1. 全局数据（防御/资源/恢复）只在第一个分析的技能 JSON 中存在，后续技能缺失
2. 网页缺少多技能页签和技能标识
3. DPS 向和构筑级数据没有分层展示

现有数据结构：
- `analysis_{skill}.json`: baseline, main_skill, dps_breakdown, sensitivity, talent_value, talent_exploration, jewel_diagnosis, aura_spirit, defence_overview, resource_overview, recovery...
- `dps_breakdown.formula_items[].sources[].category`: 已有 Tree/Item/Jewel/Skill/Base/Enemy 分类

## Goals / Non-Goals

**Goals:**
- 数据分层：全局数据（`global.json`）与技能专属数据（`analysis_{skill}.json`）分离
- 修饰符按 source category 自动分类：非 Skill 类别 → 通用 → global.json
- 网页全局区展示构筑基线（不随页签变化），页签区展示技能专属数据
- 每技能的 Markdown 报告为"全局 + 技能"合成版
- 珠宝在全局区显示概览（名称/插槽/granted），在页签区显示 DPS% 诊断

**Non-Goals:**
- 不做跨技能 modifier 数值对比（不做"最小公约数"拆分）
- 不改 POB Lua 计算逻辑
- 不改 dps_breakdown 的核心分析算法

## Decisions

### D1: 数据分类规则

**选择**: 按 source.category 直接分类，分析时即可判断

| category | 归属 | 说明 |
|----------|------|------|
| Skill | 技能专属 | 技能宝石自带的基础值/效果 |
| Tree | 通用 | 天赋节点（极少数有技能标签限制，暂忽略） |
| Item | 通用 | 装备附词 |
| Jewel | 通用 | 珠宝 granted passives |
| Base | 通用 | 角色基础值 |
| Enemy | 通用 | 敌人抗性 |

**备选**: 跨技能对比后分类 → 放弃（需要先分析所有技能再统一分类，流程复杂）

### D2: 全局数据存储方式

**选择**: 独立 `global.json` 文件

```
cache/builds/{build_id}/
├── global.json              ← 新增
├── analysis_spark.json      ← 去掉全局字段
├── analysis_comet.json      ← 去掉全局字段
├── report_spark.md          ← 合成报告
├── report_comet.md          ← 合成报告
└── report.html              ← 汇总网页
```

**备选**: 全局数据写入每个技能 JSON → 放弃（数据冗余）

### D3: 修饰符汇总数据来源

**选择**: 从构筑主技能（通常最高 DPS）的 `dps_breakdown.formula_items` 提取通用修饰符

取主技能的原因：modifier 汇总已由 POB 正确计算，且所有技能的通用 modifier 理论上数值相同。

### D4: global.json 结构

```json
{
  "build_modifiers": {
    "Speed_INC": { "total": 75, "sources": [{"category":"Tree","value":25,"label":"..."}] },
    "Damage_INC": { "total": 147, "sources": [...] },
    ...
  },
  "build_attributes": {
    "TotalAttr": 346, "Str": 87, "Dex": 86, "Int": 173,
    "Accuracy": 1134
  },
  "defence_overview": { ... },
  "resource_overview": { ... },
  "life_recovery": { ... },
  "mana_recovery": { ... },
  "jewel_overview": [
    { "name": "...", "slot_name": "...", "granted_passives": [...], "base_type": "...", "rarity": "..." }
  ]
}
```

### D5: 网页布局

```
[Header: 构筑标题 + Build ID]
[全局区: 构筑基线 + 防御面(可展开) + 资源(可展开) + 珠宝概览(可展开)]
[页签: Skill1 | Skill2 | ...]
[技能区: KPI(DPS/AvgHit/Speed) + DPS流程 + DPS拆解 + 灵敏度 + 光环 + 天赋 + 珠宝诊断]
```

### D6: 珠宝数据双份

- 全局区 `jewel_overview`: 名称/插槽/granted_passives（不含 DPS%）
- 页签区 `jewel_diagnosis`: 含 DPS%（当前实现不变）

## Risks / Trade-offs

| 风险 | 缓解 |
|------|------|
| 部分天赋 modifier 有技能标签限制（如"增加 Lightning 法术伤害"），被错误标记为通用 | 标注"基于主技能计算"，后续可精细化 |
| 旧缓存结构不兼容（缺少 global.json） | report_generator 加 fallback：无 global.json 时从第一个技能 JSON 提取 |
| format_report 需要改签名 | 保持向后兼容，新增 global_data 可选参数 |
