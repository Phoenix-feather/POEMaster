## ADDED Requirements

### Requirement: Mechanism friendly name
系统 SHALL 为所有 44 个机制提供中文友好名称（`friendly_name` 字段），替代当前 name=id 的做法。

#### Scenario: Mechanism display name
- **WHEN** 查询 InstantLifeLeech 机制
- **THEN** friendly_name SHALL 为 "立即生命偷取"，而非 "InstantLifeLeech"

### Requirement: Mechanism behavior description
系统 SHALL 为所有 44 个机制提供完整的行为描述（`behavior_description` 字段），从 POB 代码逆向提炼。按三类策略提取：Flag 型（从 CalcOffence/CalcDefence 的 Flag 检查点）、数值型（从 Sum/Mod 使用点）、触发型（从 CalcTriggers.configTable）。

#### Scenario: Flag-type mechanism
- **WHEN** 查询 GhostReaver 机制
- **THEN** behavior_description SHALL 描述 "将所有生命偷取转换为能量护盾偷取" 及其与偷取上限、即时偷取的交互

#### Scenario: Numeric-type mechanism
- **WHEN** 查询 InstantLifeLeech 机制
- **THEN** behavior_description SHALL 包含即时偷取比例的完整公式和恢复机制说明

#### Scenario: Trigger-type mechanism
- **WHEN** 查询 CastOnCriticalStrike 触发机制
- **THEN** behavior_description SHALL 包含触发条件、冷却计算、服务器 tick 对齐、技能要求

### Requirement: Mechanism category classification
系统 SHALL 为每个机制分配类别（`mechanism_category` 字段），枚举值包括 leech/block/suppress/trigger/immunity/conversion/resource/damage_modifier。

#### Scenario: Category query
- **WHEN** 搜索 category=trigger 的机制
- **THEN** SHALL 返回所有触发类机制（CastOnCrit/CWDT/CWC/Focus 等）

### Requirement: Mechanism abstract formula
系统 SHALL 为有计算逻辑的机制提供抽象公式（`formula_abstract` 字段），公式结构完整但使用变量名而非具体数值。

#### Scenario: Leech formula
- **WHEN** 查询 InstantLifeLeech 的 formula_abstract
- **THEN** SHALL 包含 "即时恢复 = 总偷取量 × InstantLifeLeech% / 100" 等完整公式

### Requirement: Mechanism affected stats
系统 SHALL 为每个机制记录影响/被影响的 stat 列表（`affected_stats` 字段，JSON 数组），表达双向关系。

#### Scenario: Affected stats query
- **WHEN** 查询 GhostReaver 的 affected_stats
- **THEN** SHALL 包含 LifeLeech（被修改）、EnergyShieldLeech（被增加）、MaxEnergyShieldLeechRate（新约束）等

### Requirement: Mechanism relations table
系统 SHALL 新增 `mechanism_relations` 表，存储机制间的关系。关系类型枚举：mutually_exclusive（互斥）、modifies（修改）、requires（依赖）、overrides（覆盖）、converts（转换）、stacks_with（叠加）。每条关系有方向（a_to_b/b_to_a/both）和描述文本。

#### Scenario: Mutual exclusion
- **WHEN** 查询 CannotBlockAttacks 的关系
- **THEN** SHALL 显示与 BlockChance 的 mutually_exclusive 关系

#### Scenario: Conversion relation
- **WHEN** 查询 GhostReaver 的关系
- **THEN** SHALL 显示与 InstantLifeLeech 的 converts 关系，说明偷取类型转换

### Requirement: Mechanism detail levels
系统 SHALL 支持机制查询的 3 种详情级别：behavior（行为描述+公式）、relations（关系网）、full（全部）。

#### Scenario: Behavior detail
- **WHEN** `mechanism <id> --detail behavior`
- **THEN** 返回 friendly_name + behavior_description + formula_abstract + affected_stats

#### Scenario: Relations detail
- **WHEN** `mechanism <id> --detail relations`
- **THEN** 返回该机制的所有关系记录（关联机制 + 关系类型 + 描述）
