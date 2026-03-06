## ADDED Requirements

### Requirement: 问题分析
系统必须分析用户问题，提取意图、实体、约束等关键信息。

#### Scenario: 提取实体
- **WHEN** 用户问"Cast on Critical的能量怎么计算"
- **THEN** 系统提取实体"Cast on Critical"，意图"计算"

#### Scenario: 提取约束
- **WHEN** 用户问"如何绕过触发限制"
- **THEN** 系统提取意图"绕过"，约束"触发限制"

### Requirement: 三源联动查询
系统必须协调实体索引、规则库、关联图进行联动查询。

#### Scenario: 实体查询主导
- **WHEN** 问题是"某技能有什么属性"
- **THEN** 系统主要查询entities表

#### Scenario: 规则查询主导
- **WHEN** 问题是"能量怎么计算"
- **THEN** 系统查询rules表，用entities补充数值

#### Scenario: 关联查询主导
- **WHEN** 问题是"如何绕过限制"
- **THEN** 系统在关联图中搜索bypasses路径

### Requirement: 链式索引查询
对于已知问题，系统必须使用链式索引快速返回结果。

#### Scenario: 已知路径查询
- **WHEN** 问题匹配known_paths中的路径
- **THEN** 系统直接返回缓存的答案

### Requirement: 发散式检索
对于未知问题，系统必须使用关联图进行发散式检索。

#### Scenario: 寻找绕过路径
- **WHEN** 用户问"如何绕过X限制"
- **THEN** 系统在关联图中搜索所有bypasses边指向X的路径

#### Scenario: 寻找关联机制
- **WHEN** 用户问"X和Y有什么关系"
- **THEN** 系统在关联图中搜索X和Y之间的路径

### Requirement: 结果整合
系统必须整合多源数据，生成结构化的回答。

#### Scenario: 整合实体和规则
- **WHEN** 查询结果包含实体数据和规则数据
- **THEN** 系统整合后生成包含数值和公式的完整回答
