## ADDED Requirements

### Requirement: Global data extraction and storage
系统 SHALL 在分析技能时将不随技能切换变化的数据提取到 `global.json`。

#### Scenario: Full analysis generates global.json
- **WHEN** 用户对一个构筑运行 full_analysis 并分析至少一个技能
- **THEN** 系统在 `cache/builds/{build_id}/global.json` 中存储：defence_overview, resource_overview, life_recovery, mana_recovery, build_modifiers, build_attributes, jewel_overview

#### Scenario: Global data separated from skill data
- **WHEN** 系统完成技能分析
- **THEN** `analysis_{skill}.json` 中不再包含 defence_overview, resource_overview, life_recovery, mana_recovery 字段（已迁移到 global.json）

### Requirement: Modifier universality classification
系统 SHALL 在分析时按 source.category 自动分类修饰符为通用或技能专属。

#### Scenario: Category-based classification
- **WHEN** 提取 `dps_breakdown.formula_items[].sources` 到 global.json
- **THEN** category 为 Tree/Item/Jewel/Base/Enemy 的 source 归入通用修饰符，category 为 Skill 的归入技能专属数据

#### Scenario: Build modifiers structure
- **WHEN** global.json 的 build_modifiers 字段被写入
- **THEN** 每个修饰符 key（如 Speed_INC）包含 total 和 sources 列表，sources 中不包含 category=Skill 的条目

### Requirement: Jewel overview in global data
系统 SHALL 在 global.json 中提供不含 DPS% 的珠宝概览。

#### Scenario: Jewel overview structure
- **WHEN** global.json 被生成
- **THEN** jewel_overview 数组中每个元素包含 name, slot_name, base_type, rarity, granted_passives，不包含 dps_pct

### Requirement: Backward compatibility for global.json
系统 SHALL 在 global.json 缺失时提供 fallback 行为。

#### Scenario: Missing global.json fallback
- **WHEN** report_generator 读取数据但 global.json 不存在（旧缓存）
- **THEN** 系统从第一个可用技能的 analysis JSON 中提取全局数据（defence_overview 等），并在控制台输出 warning
