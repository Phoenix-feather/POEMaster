## ADDED Requirements

### Requirement: Multi-skill tab switching
网页 SHALL 支持多技能页签切换，当存在多个技能分析数据时显示页签栏。

#### Scenario: Multiple skills show tabs
- **WHEN** `report.html` 加载且 SKILLS_DATA 包含 2 个以上技能
- **THEN** 页面显示技能名称页签栏，用户点击可切换技能

#### Scenario: Single skill no tabs
- **WHEN** SKILLS_DATA 只包含 1 个技能
- **THEN** 页面不显示页签栏，直接展示该技能数据

### Requirement: Skill identity display
技能专属区 SHALL 清晰标识当前展示的是哪个技能的数据。

#### Scenario: Skill KPI shows skill name
- **WHEN** 用户查看某技能页签
- **THEN** 页签区顶部显示该技能的 TotalDPS, AverageHit, Speed，以及技能名称标识

### Requirement: Global section fixed display
网页顶部 SHALL 展示不随页签变化的构筑级数据。

#### Scenario: Global section content
- **WHEN** 页面加载
- **THEN** 全局区展示：构筑修饰符汇总（施法速度 INC、伤害 INC、暴击率/暴击伤害等按来源分类）、构筑属性（TotalAttr/Str/Dex/Int/Accuracy）、防御面详情（可展开）、资源与恢复（可展开）、珠宝概览（可展开）

#### Scenario: Global section does not change on tab switch
- **WHEN** 用户在不同技能页签之间切换
- **THEN** 全局区内容保持不变

### Requirement: Skill-specific content follows tab
DPS 向内容 SHALL 跟随页签切换，展示当前技能的数据。

#### Scenario: Skill tab shows per-skill data
- **WHEN** 用户切换到某技能页签
- **THEN** 展示该技能的：DPS 计算流程、DPS 来源拆解、灵敏度分析、光环与精魄、天赋价值、天赋探索、珠宝诊断（含该技能的 DPS%）

### Requirement: Jewel diagnosis per skill
珠宝诊断 SHALL 在页签区显示，包含当前技能的 DPS% 增益。

#### Scenario: Jewel DPS% changes with skill
- **WHEN** 用户从 Spark 切换到 Comet
- **THEN** 珠宝诊断中每个珠宝的 dps_pct 显示为 Comet 技能的数值

### Requirement: Report is combined global + skill
每个技能的 Markdown 报告 SHALL 为"全局数据 + 技能分析"的合成版本。

#### Scenario: Report structure
- **WHEN** 生成 report_{skill}.md
- **THEN** 报告包含：执行摘要、构筑基线（防御/资源/恢复/修饰符汇总/珠宝概览）、{技能名}技能分析（DPS拆解/灵敏度/光环/天赋/珠宝诊断）、总结与建议
