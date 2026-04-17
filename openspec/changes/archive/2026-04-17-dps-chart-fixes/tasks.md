## 1. 数据层（what_if.py）

- [x] 1.1 `dps_breakdown()` 返回值新增 `damage_composition` 字段，调用 `_extract_damage_composition(baseline)`

## 2. 报告组件（report_generator.py）

- [x] 2.1 新增 `DamagePieChart` 组件：纯 SVG 饼图，按元素 HitAverage 比例渲染扇区，标注元素名+占比
- [x] 2.2 FormulaBreakdown 中合并 `{Element}_Lucky` 多行为单行，标注 "N 元素 × X%"
- [x] 2.3 FormulaBreakdown 条形图图例从 `catKey catValue` 改为 top-3 source 名称 + 剩余汇总
- [x] 2.4 SkillTab 中 KPI 卡片下方插入 `DamagePieChart` 组件

## 3. 验证

- [x] 3.1 重新生成报告，验证饼图正确显示各元素占比
- [x] 3.2 验证 Lucky 合并为单行，Damage_MORE 的 Skill 来源保留显示
- [x] 3.3 验证条形图图例显示 top-3 source 名称
