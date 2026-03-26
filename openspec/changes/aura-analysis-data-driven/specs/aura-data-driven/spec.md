## ADDED Requirements

### Requirement: EC MORE 值动态读取
`_test_mod_effect` 函数对 Elemental Conflux 处理时，MUST 从构筑中 EC 宝石的实际等级读取 MORE 值，而非使用硬编码的 Level 20 值（59%）。报告中 MUST 标注实际使用的等级和数值。

#### Scenario: 构筑 EC 为 Level 15
- **WHEN** 构筑中 Elemental Conflux 宝石等级为 15
- **THEN** 使用 Level 15 对应的 MORE 值（如 47%）进行模拟和报告，报告标注 "Elemental Conflux (Lv15): 47% MORE"

#### Scenario: 构筑 EC 为 Level 20（满级）
- **WHEN** 构筑中 Elemental Conflux 宝石等级为 20
- **THEN** 使用 Level 20 的 MORE 值（59%）进行模拟和报告，报告标注 "Elemental Conflux (Lv20): 59% MORE"

### Requirement: Charge 数量动态读取
`_AURA_PRE_CONFIGS` 中 Charge Infusion 的充能球数量 MUST 从构筑实际最大充能球数读取，而非硬编码为 3×3。

#### Scenario: 构筑最大 Frenzy Charges 为 5
- **WHEN** 构筑的 MaximumFrenzyCharges 为 5
- **THEN** Charge Infusion 模拟使用 5 个 Frenzy Charges

#### Scenario: 无法读取最大充能球数
- **WHEN** POB output 中不存在 MaximumFrenzyCharges 等字段
- **THEN** 回退到默认值 3，并在警告中标注 "充能球数量使用默认值 3（未能读取构筑最大值）"

### Requirement: 候选光环精魄消耗动态读取
7B 和 7C 测试时，精魄消耗 MUST 从 POB 数据的 `grantedEffect.levels[maxLevel].spiritReservationFlat` 读取，替代 `_AURA_CANDIDATES` 和 `_SPIRIT_SUPPORT_CANDIDATES` 中的硬编码值。

#### Scenario: 精魄消耗与硬编码不同
- **WHEN** POB 数据中 Archmage 的 spiritReservationFlat 为 120（而非硬编码的 100）
- **THEN** 报告显示精魄消耗为 120

### Requirement: 精魄限制不影响候选展示
7B 和 7C 的候选光环 MUST 统一展示在主表格中，MUST NOT 因精魄不足设置 error 字段。精魄不足信息 MUST 以备注形式展示。

#### Scenario: 精魄不足的候选光环
- **WHEN** 候选光环需要 100 精魄但构筑仅剩 50
- **THEN** 该光环显示在主表格中，备注列标注 "需精魄 100（缺 50）"，dps_pct 正常计算和排序

#### Scenario: 精魄充足的候选光环
- **WHEN** 候选光环需要 60 精魄且构筑剩 200
- **THEN** 正常显示，无精魄相关备注

### Requirement: 一致性校验警告
`aura_spirit_analysis` 返回结果 MUST 包含 `warnings` 列表。分析完成后 MUST 自动运行校验规则，对不满足条件的情况生成警告。

#### Scenario: EC 等级远低于满级
- **WHEN** 构筑 EC 为 Level 10（远低于 maxLevel 20）
- **THEN** 生成警告 "Elemental Conflux 等级 Lv10 远低于满级 Lv20，DPS 贡献被低估"

#### Scenario: Direstrike 无影响但构筑不满足 Low Life
- **WHEN** 构筑未满足 Low Life 条件且 Direstrike DPS 影响为 0%
- **THEN** 生成警告 "Direstrike 无 DPS 影响 — 可能因构筑不满足 Low Life 条件"

#### Scenario: Charge 模拟值超过构筑最大值
- **WHEN** Charge Infusion 模拟 3 个 Power Charges 但构筑 MaximumPowerCharges 为 2
- **THEN** 生成警告 "Charge Infusion 模拟 3 个 Power Charges 超过构筑最大值 2"

### Requirement: 报告中标注实际等级
报告中所有模拟光环的说明 MUST 标注实际使用的宝石等级，MUST NOT 硬编码 "Lv20"。

#### Scenario: EC 模拟说明
- **WHEN** EC 模拟完成
- **THEN** 说明文本格式为 "Elemental Conflux (Lv{实际等级}): {实际值}% MORE"，而非硬编码 "Lv20"
