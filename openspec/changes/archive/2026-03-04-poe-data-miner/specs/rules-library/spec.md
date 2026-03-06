## ADDED Requirements

### Requirement: 三层规则提取
系统必须使用分层策略提取规则：Layer 1从stats组合，Layer 2从SkillStatMap，Layer 3从计算代码。

#### Scenario: Layer 1提取实体属性
- **WHEN** 分析实体数据
- **THEN** 系统提取每个实体拥有的stats属性

#### Scenario: Layer 2提取属性关系
- **WHEN** 分析SkillStatMap
- **THEN** 系统提取属性与效果之间的精确映射关系

#### Scenario: Layer 3提取条件规则
- **WHEN** 分析CalcActiveSkill.lua等计算代码
- **THEN** 系统提取条件判断和计算公式

### Requirement: 规则存储格式
系统必须将规则存储到SQLite的rules表中，包含ID、名称、条件、效果、公式等字段。

#### Scenario: 存储条件规则
- **WHEN** 提取到条件规则
- **THEN** 系统将条件、效果、描述存储到rules表

#### Scenario: 存储公式规则
- **WHEN** 提取到计算公式
- **THEN** 系统将公式、影响因素、适用范围存储到rules表

### Requirement: 规则与实体关联
系统必须能够查询与特定实体相关的所有规则。

#### Scenario: 查询实体相关规则
- **WHEN** 查询"Cast on Critical"相关的规则
- **THEN** 系统返回能量生成规则、触发规则、限制规则等
