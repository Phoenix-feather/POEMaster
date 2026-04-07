## Context

技能页（SkillTab）的 DPS 分析区包含 KPI 卡片、DPSFlowTable、FormulaBreakdown、灵敏度图表等组件。当前 `dps_breakdown` 返回 `formula_items`（含所有 INC/MORE/BASE/Lucky/ConvGain）和 `dps_flow_stages`，但不包含按元素的伤害构成数据。

`damage_composition` 已在 `_extract_damage_composition` 中实现（模块级常量 `_ELEM_HIT_CONFIG`），但仅在 `extract_global_data` 中调用，写入 global.json，在全局区显示表格。技能页无法访问。

## Goals / Non-Goals

**Goals:**
- 技能页新增伤害组成饼图（SVG/Canvas，无外部依赖）
- FormulaBreakdown 保留 Skill 来源（辅助宝石贡献不再丢失）
- Lucky Hits 多行合并为单行
- 条形图图例显示 top-3 source 名称

**Non-Goals:**
- 不改变 `extract_global_data` 的全局区伤害构成表格
- 不引入外部图表库（Chart.js 等）

## Decisions

### 1. 饼图实现：纯 SVG，无依赖
选择 SVG `<circle>` + `stroke-dasharray` 实现，与现有 DefenceRadar 的 Canvas 方案保持独立。饼图数据来源为 baseline 的 per-element `HitAverage`。

### 2. damage_composition 放入 dps_breakdown 返回值
在 `dps_breakdown()` 函数中调用 `_extract_damage_composition(baseline)`，作为返回值的一个字段。不修改 baseline 传入方式。

### 3. Lucky 合并策略
在 FormulaBreakdown 的排序/过滤阶段，将所有 `{Element}_Lucky` 合并为一个虚拟条目，formula_name 为 "Lucky Hits (各元素独立)"，total_value 为最大值（因为每种元素独立），sources 取去重后的集合。

### 4. FormulaBreakdown 不过滤 Skill 来源
当前 FormulaBreakdown 的 `items.filter` 不按 category 过滤（只过滤 CombinedDPS 和 EffMult）。Skill 来源的消失实际发生在 `_extract_build_modifiers`（全局区），不影响技能页。确认 FormulaBreakdown 渲染时保留了 Skill 来源。

### 5. 条形图图例改为 top-3 source 名称
在 FormulaBreakdown 的 catEntries 渲染中，从 sources 中取 value 最大的 3 个的 label，替代 `catKey catValue` 格式。

## Risks / Trade-offs

- [SVG 饼图在 5+ 元素时标签重叠] → 限制标签显示（仅显示占比 > 5% 的元素名）
- [Lucky 合并后 sources 去重可能丢失元素信息] → 在 formula_name 中标注 "×N 元素"
