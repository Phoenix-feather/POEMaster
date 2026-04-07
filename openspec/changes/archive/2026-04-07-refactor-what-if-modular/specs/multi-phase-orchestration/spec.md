# multi-phase-orchestration

## Overview
三阶段分析编排，消除重复计算，支持多技能×多套装。

## Requirements

### R1: Phase 0 — 全局分析
- 每个套装只运行一次，不随技能变化
- 包含：defence、resource、recovery、aura_spirit、jewels
- 输出 `global.json`（套装级）

### R2: Phase 1 — 技能分析
- 每个技能×每个套装运行一次
- 包含：baseline、sensitivity、passive_node、dps_breakdown
- 输出 `{skill}.json`（技能×套装级）

### R3: Phase 2 — 对比（可选）
- 多套装时自动生成对比数据
- 输出 `comparison.json`

### R4: Phase 3 — 报告生成
- Markdown 报告：每个技能一份，引用全局数据
- HTML 报告：一份汇总，包含所有技能 tabs + 套装选择 + 对比面板
- 报告在所有分析完成后一次性生成（不再每次 full_analysis 都重建 HTML）

### R5: 自动发现
- 如果未指定技能列表，自动扫描构筑中所有 DPS>0 的技能组
- 如果未指定套装列表，自动检测是否有第二套武器

### R6: 向后兼容
- `calc.full_analysis(skill_name="spark")` 继续可用，内部委托给新编排层
- 新增 `calc.full_build_analysis(skills=..., weapon_sets=...)` 入口
