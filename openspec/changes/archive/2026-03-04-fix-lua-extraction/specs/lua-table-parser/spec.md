## ADDED Requirements

### Requirement: 括号平衡解析
系统必须使用括号平衡算法正确提取嵌套Lua表结构。

#### Scenario: 提取单层嵌套表
- **WHEN** 解析 `skills["id"] = { field = { nested = true } }`
- **THEN** 系统提取完整的表内容，包括嵌套部分

#### Scenario: 提取多层嵌套表
- **WHEN** 解析包含3层以上嵌套的Lua表
- **THEN** 系统正确识别所有层级的边界

#### Scenario: 忽略字符串中的花括号
- **WHEN** 表中包含字符串值如 `name = "test { value }"`
- **THEN** 系统不将字符串内的花括号计入平衡

### Requirement: 技能类型提取
系统必须正确提取 `[SkillType.XXX] = true` 格式的技能类型。

#### Scenario: 提取技能类型列表
- **WHEN** 解析 `skillTypes = { [SkillType.Meta] = true, [SkillType.Triggers] = true }`
- **THEN** 系统返回 `["Meta", "Triggers"]`

### Requirement: 常量属性提取
系统必须正确提取 `constantStats = { { "stat_name", value } }` 格式的属性。

#### Scenario: 提取常量属性
- **WHEN** 解析 `constantStats = { { "spirit_reservation_flat", 100 } }`
- **THEN** 系统返回 `[["spirit_reservation_flat", 100]]`

### Requirement: statSets嵌套提取
系统必须正确提取 `statSets[1]` 嵌套结构中的属性。

#### Scenario: 提取statSets中的stats
- **WHEN** 解析包含statSets嵌套的技能定义
- **THEN** 系统从statSets[1]中提取stats和constantStats

### Requirement: 提取结果验证
系统必须验证提取结果的关键字段非空。

#### Scenario: 验证技能ID
- **WHEN** 提取技能定义
- **THEN** 系统确保id字段非空

#### Scenario: 跳过无效实体
- **WHEN** 提取的实体缺少必要字段
- **THEN** 系统跳过该实体并记录警告
