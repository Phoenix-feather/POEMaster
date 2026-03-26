## Context

当前光环分析（Section 7）的 `_AURA_INJECT_MODS`、`_AURA_PRE_CONFIGS`、`_AURA_CANDIDATES`、`_SPIRIT_SUPPORT_CANDIDATES` 四个数据常量包含多处硬编码值。DPS 计算本身通过 POB 全量引擎执行（正确），但注入的前提数值可能错误（如 EC MORE=59 是 Level 20 值，构筑实际可能是 Level 15 的 47%）。此外，精魄不足的候选光环被标记为 error 降到"精魄不足"分区显示，用户难以直接对比。

## Goals / Non-Goals

**Goals:**
- EC MORE 值从构筑实际宝石等级动态读取
- Charge Infusion 充能球数量从构筑实际最大值读取
- 7B/7C 精魄消耗从 POB 数据动态读取
- 报告中标注构筑实际宝石等级（替代硬编码 "Lv20"）
- 7B/7C 候选光环不再因精魄不足标记 error，统一展示
- 分析完成后自动校验数据一致性（条件满足性、等级匹配）

**Non-Goals:**
- 不动态发现候选光环列表（仍使用 `_AURA_CANDIDATES` 硬编码的 6 个候选）
- 不修改候选光环的等级策略（7B/7C 仍使用 maxLevel=20）
- 不修改 DPS 计算流程（继续使用 POB 全量引擎）
- 不处理 `_AURA_INJECT_MODS` 中除 EC 外的其他条目（当前只有 EC）

## Decisions

### D1: EC MORE 值动态读取方式

**选择**: 从构筑中 EC 宝石的 `grantedEffect.levels[gem.level]` 读取实际 MORE 值。

**替代方案**: 仍用 Level 20 满级值但在报告中标注差异。
**否决理由**: 7A 的目的是"当前光环对当前构筑的实际贡献"，应该用实际等级。

**实现**: 在 `_test_mod_effect` 中，对 EC 特殊处理：
1. 遍历构筑 skillGroups 找到 EC 宝石的实际等级
2. 从 `grantedEffect.levels[level]` 读取该等级的 stat 值
3. 用该值替代硬编码的 59

### D2: Charge 数量动态读取

**选择**: 从构筑 `env.player.output` 读取 `MaximumFrenzyCharges` / `MaximumPowerCharges` / `MaximumEnduranceCharges`。

**替代方案**: 从 `configTab.input` 读取 override 值。
**否决理由**: output 值是天赋+装备+配置的最终结果，更准确。

### D3: 精魄消耗动态读取（7B/7C）

**选择**: 在 `_test_add_candidate_aura` 和 `_test_add_spirit_support` 中，从 `ge.levels[maxLevel].spiritReservationFlat` 读取精魄消耗。

**实现**: 在 Lua 端创建新 gem 对象时，同时读取 `levels[maxLevel].spiritReservationFlat` 并返回给 Python 端。

### D4: 精魄限制解除

**选择**: 7B/7C 不再因精魄不足设置 `error` 字段，改为设置 `spirit_note` 字段。报告格式化时统一展示在主表格，精魄不足在备注列标注。

**理由**: 候选光环的 DPS 是理论值，不应被精魄预算影响对比。

### D5: 一致性校验框架

**选择**: 在 `aura_spirit_analysis` 返回结果中新增 `warnings` 列表。校验规则：
- EC 实际等级 vs maxLevel → 如果差异 > 2，警告
- Charge Infusion 模拟值 vs 构筑最大充能 → 如果模拟值 > 最大值，警告
- Direstrike "无影响" → 检查构筑是否满足 Low Life，不满足则警告
- 精魄不足的候选 → 标注但不标记为 error

## Risks / Trade-offs

- **[风险] EC stat 值在 levels 表中的 key 可能不确定** → 先验证 POB 数据结构，确认 key 名称
- **[风险] Charge 模拟值 vs 最大值的比较可能不准确** → Charge 的 override 是临时配置，实际战斗中维持多个 Charge 依赖击杀率，但 POB 的 override 模式假设恒定维持
- **[Trade-off] 候选光环列表仍硬编码** → 如果 POB 新增光环需要手动更新列表，但这是低频事件
