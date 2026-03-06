## ADDED Requirements

### Requirement: 扫描POB所有Lua文件
系统必须扫描POB目录下的所有.lua文件，不依赖文件名过滤，通过内容模式识别数据类型。

#### Scenario: 识别技能定义文件
- **WHEN** 文件内容包含 `skills["..."] = {` 模式
- **THEN** 系统识别为技能定义文件，提取所有技能数据

#### Scenario: 识别SkillStatMap文件
- **WHEN** 文件内容包含 `["stat_name"] = {` 模式且包含skill/mod函数
- **THEN** 系统识别为属性映射文件，提取所有映射关系

#### Scenario: 识别计算模块文件
- **WHEN** 文件内容包含 `function calc` 或 `function compute` 模式
- **THEN** 系统识别为计算模块文件，提取计算逻辑

### Requirement: 数据类型分类
系统必须将扫描结果按数据类型分类：实体数据、映射数据、计算逻辑、配置数据。

#### Scenario: 分类技能数据
- **WHEN** 扫描到技能定义
- **THEN** 系统分类为实体数据，标记来源文件

#### Scenario: 分类SkillStatMap数据
- **WHEN** 扫描到属性映射
- **THEN** 系统分类为映射数据，标记来源文件

### Requirement: 版本信息提取
系统必须从POB数据中提取版本信息，用于后续版本检测。

#### Scenario: 提取GameVersions版本
- **WHEN** 存在GameVersions.lua文件
- **THEN** 系统提取版本号并记录

#### Scenario: 无版本文件时的处理
- **WHEN** 不存在版本文件
- **THEN** 系统使用文件修改时间作为版本标识
