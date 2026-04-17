## ADDED Requirements

### Requirement: 技能页显示伤害组成饼图
技能页（SkillTab）在 KPI 卡片下方 SHALL 显示伤害组成饼图，基于 POB 输出的 per-element HitAverage 数据。饼图 SHALL 使用 SVG 实现，不依赖外部库。

#### Scenario: 三元素构筑
- **WHEN** 技能造成 Lightning/Cold/Fire 三种伤害
- **THEN** 饼图显示三个扇区，面积比例与各元素 HitAverage 成正比，每个扇区标注元素名和占比百分比

#### Scenario: 单元素构筑
- **WHEN** 技能仅造成一种元素伤害
- **THEN** 饼图显示单个扇区占满 100%

#### Scenario: 无伤害数据
- **WHEN** dps_breakdown 中无 damage_composition 数据
- **THEN** 饼图组件不渲染（返回 null）

### Requirement: Lucky Hits 合并显示
FormulaBreakdown 中，多个 `{Element}_Lucky` 条目 SHALL 合并为单行显示。

#### Scenario: 三元素 Lucky
- **WHEN** 存在 Lightning_Lucky=20、Cold_Lucky=20、Fire_Lucky=20
- **THEN** FormulaBreakdown 显示单行 "Lucky Hits +60% (3 元素 × 20%)"，展开后显示去重的 source 列表

### Requirement: 条形图图例显示 top-3 source 名称
FormulaBreakdown 的分类条形图图例 SHALL 显示每个分类中 value 最大的前 3 个 source 的名称，而非纯数字汇总。

#### Scenario: Tree 分类有 18 个来源
- **WHEN** CritChance_INC 的 Tree 分类有 18 个 source
- **THEN** 图例显示 "Tree: Critical Exploit, Careful Assassin, True Strike +15" 格式（前 3 名 + 剩余汇总）

### Requirement: dps_breakdown 包含 damage_composition
`dps_breakdown()` 函数返回值 SHALL 包含 `damage_composition` 字段，结构与 `_extract_damage_composition` 输出一致。

#### Scenario: 调用 dps_breakdown
- **WHEN** 调用 `dps_breakdown(lua, calcs, baseline=baseline)`
- **THEN** 返回值包含 `damage_composition` 列表，每项含 element/hit_avg/crit_avg/enemy_damage/weight_pct 字段
