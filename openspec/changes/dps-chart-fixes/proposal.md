## Why

技能页的 DPS 分析存在 4 个展示问题：(1) 缺少伤害组成饼图，用户无法直观看出各元素占比；(2) Damage_MORE（辅助宝石 Deliberation +20%）因 Skill 来源被过滤而消失；(3) Lucky Hits 按元素拆成 3 行（每行 20%），看似重复计算；(4) 条形图图例只显示分类数字，不显示具体天赋名称。

## What Changes

- 技能页新增伤害组成饼图（基于 POB 输出的 per-element HitAverage）
- FormulaBreakdown 保留 Skill 类别来源（不再过滤辅助宝石贡献）
- Lucky Hits 按元素的多行合并为单行，标注每种元素独立概率
- 条形图图例从纯数字改为 top-3 source 名称

## Capabilities

### New Capabilities
- `damage-pie-chart`: 技能页伤害组成饼图组件

### Modified Capabilities

## Impact

- `pob_calc/what_if.py`: `dps_breakdown` 返回值新增 `damage_composition` 字段
- `report_generator.py`: 新增饼图组件、修改 FormulaBreakdown 排序/合并逻辑、修改 SourceList 展示
