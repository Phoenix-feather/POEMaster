## Context

pob-build-analyzer 的核心模块 `what_if.py`（5,727行）提供构筑分析能力。当前报告覆盖 8 个 Section，但本质上只有 DPS 单轴视角。防御面仅有一个 TotalEHP 数字，无拆解、无灵敏度、无弱点诊断。资源面完全缺失。

已有的可复用基础设施：
- `sensitivity_analysis()` — 灵敏度二分搜索框架，支持任意 target_stat 和 profile 列表
- `SENSITIVITY_PROFILES` — 22 个 DPS profile 的定义字典
- `what_if_mod()` — 通用 modifier 注入对比函数
- `_diff_outputs()` — output diff 计算
- `passive_node_analysis()` — 已支持 `ehp_stat` 参数
- `aura_spirit_analysis()` — 已有 EHP 维度

POB CalcDefence.lua 提供了所有防御/恢复相关的 output key（MaxHitTaken, DotEHP, LifeLeech, Recoup 等），无需修改 POB 代码。

## Goals / Non-Goals

**Goals:**
- 新增防御面完整分析（概览 + 灵敏度 + 弱点诊断）
- 新增资源面分析（预算 + 恢复构成 + 恢复增强灵敏度）
- 新增构筑审计（抗性平衡 + 冗余检测）
- 将天赋/珠宝/光环诊断从 DPS-only 升级为 DPS+EHP 双维度
- 报告从 8 Section 平铺重构为 Part 0-5 分层结构，含执行摘要

**Non-Goals:**
- 技能组对比分析 — 分析器价值在深度而非广度，用户可通过 `skill_name` 参数切换
- 属性效率审计（Str/Dex/Int vs 需求） — 价值有限
- 药剂独立分析 — 药剂效果已通过 mod 系统融入其他分析
- 恢复灵敏度聚合 — 各恢复来源独立分析，不做多 key 聚合 target_stat
- UI 界面 — 仅 Markdown 报告

## Decisions

### D1: 防御灵敏度复用 sensitivity_analysis 框架

**选择**: 在 `SENSITIVITY_PROFILES` 中新增防御 profile，调用 `sensitivity_analysis(target_stat="TotalEHP")`

**替代方案**: 创建独立的 `defence_sensitivity_analysis()` 函数

**理由**: 现有框架已完美支持 — 二分搜索 + `_inject_profile` + `_diff_outputs`。只需添加 profile 字典条目并切换 target_stat。代码增量最小，维护成本最低。

**防御 profile 清单** (~14 个):
- `life_inc` (Life, INC, 500%), `life_flat` (Life, BASE, 500)
- `armour_inc` (Armour, INC, 300%), `armour_flat` (Armour, BASE, 5000)
- `evasion_inc` (Evasion, INC, 300%), `evasion_flat` (Evasion, BASE, 5000)
- `fire_resist` (FireResist, BASE, 75%), `cold_resist`, `lightning_resist`, `chaos_resist`
- `all_elemental_resist` (ElementalResist, BASE, 75%)
- `block_chance` (BlockChance, BASE, 75%), `spell_block` (SpellBlockChance, BASE, 75%)
- `damage_reduction` (DamageReduction, BASE, 90%)

### D2: 恢复分析各来源独立灵敏度，不做聚合

**选择**: 每个 recovery source key 独立作为 target_stat，不做多 key 求和

**替代方案**: 添加 `target_fn` 回调支持聚合 target_stat

**理由**: 聚合需要修改 `sensitivity_analysis` 核心逻辑（添加 target_fn 参数），复杂度高且违反当前框架设计。独立分析已足够有价值 — "+50% LifeLeech → 偷取从 120→180/s" 对用户就是明确的信息。聚合可以后续需要时再加。

**恢复 profile 清单** (~8 个):
- `life_regen` (LifeRegen, BASE, +20), `life_leech` (PhysicalLifeLeech, BASE, +50)
- `life_recoup` (LifeRecoup, BASE, +5), `life_recovery_rate` (LifeRecoveryRate, INC, +30)
- `flask_effect` (FlaskEffect, INC, +20)
- `mana_regen` (ManaRegen, BASE, +20), `mana_leech` (PhysicalManaLeech, BASE, +50)
- `mana_recovery_rate` (ManaRecoveryRate, INC, +30)

### D3: 防御概览和资源概览为纯 output 读取，零 Lua 注入

**选择**: 从 baseline output dict 直接读取，不执行额外 initEnv/perform

**理由**: 这些数据已经在第一次 baseline 计算中获取。零 Lua 交互 = 零风险、零性能开销。只有灵敏度分析需要多次 initEnv。

### D4: 报告重构为 Part 0-5 分层，增量迁移

**选择**: 新增 Part 0/2/3/5 作为新 section，现有 Section 1-8 映射到 Part 1/4，最后再调整格式

**替代方案**: 一次性重写整个 `format_report()`

**理由**: 增量迁移允许每个 Phase 独立交付和验证。一次性重写 5,700 行格式化代码风险过高。

**映射关系**:
- Part 0 (新): 执行摘要
- Part 1 = 原 S1 + S2 + S3 (进攻面)
- Part 2 (新): 防御面 (概览 + 灵敏度 + 弱点)
- Part 3 (新): 资源面 (预算 + 恢复 + 灵敏度)
- Part 4 = 原 S4 + S5 + S6 + S7 (配置优化，升级双维度)
- Part 5 (新): 构筑审计 (抗性平衡 + 冗余检测)

### D5: 执行摘要基于数据自动生成，非模板

**选择**: 从分析结果中提取关键指标自动生成摘要文本

**规则**:
- 进攻评分: A/B/C/D 基于 TotalDPS vs 灵敏度瓶颈
- 防御评分: A/B/C/D 基于 TotalEHP vs 最短板 MaxHitTaken
- 资源评分: A/B/C/D 基于 Spirit/Mana 占用率
- 关键发现: MaxHitTaken 最短板、抗性未满、零贡献天赋等
- 优化建议: 灵敏度边际收益最大的前 5 项（跨 DPS+EHP+恢复）

### D6: 珠宝诊断加 EHP 维度

**选择**: `diagnose_jewels()` 新增 `ehp_stat` 参数，默认 `"TotalEHP"`

**实现**: 移除珠宝时同时记录 DPS 和 EHP 变化，报告中双维度展示。

## Risks / Trade-offs

- **[性能] 灵敏度分析次数增加**: 防御 14 profile × ~15 步 + 恢复 8 profile × ~15 步 ≈ 330 次 initEnv（+20s）
  → 缓解: 防御灵敏度和恢复灵敏度作为可选参数，默认 `target_pct` 降低到 20%
- **[精度] TotalEHP 已知偏差**: cb_summary 中记录的 TotalEHP 计算存在 buff 状态差异
  → 缓解: 报告中标注"基于 POB 计算结果"，这是 POB 本身的问题
- **[复杂度] 报告文件过大**: 5,727 → ~8,400 行，单文件维护难度增加
  → 缓解: 分区清晰注释隔离（已有模式），暂不拆分文件
- **[兼容] 报告格式 BREAKING**: 旧缓存报告与新报告 Section 编号不同
  → 缓解: 清理旧缓存，报告中添加版本标记
