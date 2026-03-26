## Why

当前 pob-build-analyzer 的报告仅有 DPS 单轴视角（8 Section 平铺），EHP 仅作为 Section 1/4/5/7 的附带数字出现，缺乏拆解、灵敏度分析和弱点诊断。玩家无法通过报告回答"我的防御最短板是什么""该优先提升抗性还是护甲""我的生命恢复能力是否足够"等关键问题。需要从"DPS 单轴优化报告"升级为"DPS+EHP+资源 全面构筑分析报告"。

## What Changes

- 新增 **防御面分析（Part 2）**：防御概览面板（Pool/减伤层/MaxHitTaken/抗性）+ 防御灵敏度分析（Life/Armour/Evasion/Resist/Block 的 EHP 边际收益）+ 防御弱点诊断（承伤链分解，找最短板）
- 新增 **资源面分析（Part 3）**：资源预算（Life/Mana/Spirit/ES 预留 vs 可用）+ 恢复能力分析（Regen + Leech + Recoup + OnHit + Recharge 来源构成）+ 恢复增强灵敏度（各恢复来源的边际收益）
- 新增 **构筑审计（Part 5）**：抗性平衡检测（各元素 vs 上限）+ 冗余检测（零贡献天赋/珠宝/光环）
- 新增 **执行摘要（Part 0）**：自动生成评分、关键发现、优化建议 Top 5
- 升级 **配置优化（Part 4）**：天赋/珠宝/光环诊断从 DPS-only 升级为 DPS+EHP 双维度
- **报告结构重构**：从 8 Section 平铺改为 Part 0-5 分层结构

## Capabilities

### New Capabilities
- `defence-overview`: 防御概览面板 — 从 baseline output 读取 Pool 构成、减伤层（护甲/闪避/格挡/法术压制）、5种 MaxHitTaken（按类型）、抗性面板（vs 上限）、DotEHP
- `defence-sensitivity`: 防御灵敏度分析 — 复用 sensitivity_analysis 框架，新增 ~14 个防御 profile（life_inc, armour_inc, evasion_inc, xxx_resist, block, damage_reduction 等），target_stat=TotalEHP
- `defence-weakness`: 防御弱点诊断 — 读取承伤链数据（抗性→护甲→格挡→压制→承伤），按伤害类型分解，标注最短板
- `resource-overview`: 资源预算 — Life/Mana/Spirit/ES 总量 vs 预留 vs 可用，精魄预算占比
- `recovery-analysis`: 恢复能力分析 — 聚合所有恢复来源（Regen + Leech + Recoup + OnHit + Recharge），按贡献排序，展示偷取细节和回收细节
- `recovery-sensitivity`: 恢复增强灵敏度 — LifeRegen/LifeLeech/LifeRecoup/FlaskEffect 等恢复维度的边际收益分析
- `build-audit`: 构筑审计 — 抗性平衡检测（各元素 Resist vs ResistMax）、冗余检测（零贡献天赋/珠宝/光环）
- `executive-summary`: 执行摘要 — 自动生成进攻/防御/资源评分、关键发现 Top 5、优化建议优先级排序

### Modified Capabilities
<!-- 无已有 spec 需要修改 -->

## Impact

- **核心文件**: `.codebuddy/skills/pob-build-analyzer/pob_calc/what_if.py`（5,727行 → ~8,400行，+46%）
- **新增数据**: 约 14 个防御灵敏度 profile、~10 个恢复灵敏度 profile
- **报告格式**: 从 8 Section 平铺重构为 Part 0-5 分层，**BREAKING** 旧缓存报告格式不兼容
- **POB 依赖**: 所有新增 output key 均已在 CalcDefence.lua / CalcOffence.lua 中存在，无需 POB 代码修改
- **性能**: full_analysis 新增 ~3-5 次 initEnv 调用（防御灵敏度），总运行时间从 ~30s 增至 ~45s
