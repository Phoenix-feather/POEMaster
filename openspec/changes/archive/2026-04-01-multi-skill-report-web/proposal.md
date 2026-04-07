## Why

当前报告系统只支持单技能分析，网页只展示一个技能的数据且缺少技能标识。多技能构筑无法统一查看对比。此外，报告和网页中混入了"不受技能切换变化的构筑级数据"（防御、资源、恢复等），没有做全局/技能专属的数据分层。

## What Changes

- **数据分层**：将分析数据拆分为全局数据（`global.json`，防御/资源/恢复/构筑修饰符/珠宝概览）和技能专属数据（`analysis_{skill}.json`）
- **修饰符分类**：分析时按 source category 区分通用修饰符（Tree/Item/Jewel/Base/Enemy）和技能专属修饰符（Skill），通用修饰符写入 global.json
- **多技能页签**：网页支持多技能页签切换，DPS 向内容（DPS拆解、灵敏度、天赋价值、光环、珠宝诊断）跟随页签变化
- **全局区固定**：网页顶部展示构筑基线属性（不随页签变化），下方才是技能页签区
- **合成报告**：每个技能的 Markdown 报告为"全局数据 + 技能分析"的合成版本
- **网页汇总**：`report.html` 读取 global.json + 所有技能 JSON，全局区 + 页签区

## Capabilities

### New Capabilities

- `global-build-data`: 构筑级全局数据的提取与存储（global.json 生成逻辑，修饰符通用性分类，防御/资源/恢复/珠宝概览数据结构）
- `multi-skill-web`: 多技能网页布局（全局区组件 + 技能页签组件，数据读取与合成逻辑）

### Modified Capabilities

## Impact

- `pob_calc/what_if.py`: full_analysis 拆分全局/技能数据，format_report 接受 global+skill 参数
- `pob_calc/__init__.py`: 生成 global.json + 各技能合成 report_{skill}.md
- `report_generator.py`: 读取 global.json，布局拆分为全局区 + 页签区
- `cache` 目录结构新增 global.json
