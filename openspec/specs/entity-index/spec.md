## ADDED Requirements

### Requirement: 实体数据存储
系统必须将技能、物品、天赋等实体数据存储到SQLite的entities表中。

#### Scenario: 存储技能实体
- **WHEN** 扫描到技能数据
- **THEN** 系统将技能ID、名称、skillTypes、stats、constantStats存储到entities表

#### Scenario: 存储物品实体
- **WHEN** 扫描到物品数据
- **THEN** 系统将物品ID、名称、类型、属性存储到entities表

### Requirement: 实体查询接口
系统必须提供实体查询接口，支持按ID、类型、skillTypes查询。

#### Scenario: 按ID查询实体
- **WHEN** 查询实体ID为"Cast on Critical"
- **THEN** 系统返回该实体的完整数据

#### Scenario: 按skillTypes查询实体
- **WHEN** 查询skillTypes包含"Meta"的所有实体
- **THEN** 系统返回所有Meta类型的实体列表

### Requirement: 索引优化
系统必须为常用查询字段创建索引，包括id、type、skillTypes。

#### Scenario: ID索引查询
- **WHEN** 使用ID查询
- **THEN** 查询在10ms内完成

#### Scenario: skillTypes全文索引
- **WHEN** 使用skillTypes模糊匹配查询
- **THEN** 查询在50ms内完成
