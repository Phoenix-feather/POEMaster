## MODIFIED Requirements

### Requirement: 实体数据提取
系统必须正确提取Lua文件中的实体数据。

#### Scenario: 提取技能实体
- **WHEN** 扫描包含技能定义的Lua文件
- **THEN** 系统提取完整的技能实体，包括name、skillTypes、constantStats

#### Scenario: 提取属性映射
- **WHEN** 扫描SkillStatMap.lua文件
- **THEN** 系统提取stat到modifier的映射关系

### Requirement: 数据类型识别
系统必须正确识别Lua文件的数据类型。

#### Scenario: 识别技能定义文件
- **WHEN** 扫描包含 `skills["xxx"] = {` 模式的文件
- **THEN** 系统识别为 `skill_definition` 类型

#### Scenario: 识别属性映射文件
- **WHEN** 扫描包含 `skill(` 或 `mod(` 调用的文件
- **THEN** 系统识别为 `stat_mapping` 类型
