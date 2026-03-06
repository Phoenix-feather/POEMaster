## ADDED Requirements

### Requirement: 探索发现记录
系统必须记录探索过程中的新发现，标记为待确认状态。

#### Scenario: 记录新发现
- **WHEN** 问答引擎发现新的机制关联
- **THEN** 系统创建待确认记录，存储到pending_confirmations.yaml

#### Scenario: 记录启发信息
- **WHEN** 发现经过用户确认
- **THEN** 系统创建启发记录，存储问题和发现内容

### Requirement: 用户确认机制
系统必须使用ask_followup_question工具请求用户确认。

#### Scenario: 请求确认发现
- **WHEN** 发现新的绕过路径
- **THEN** 系统使用ask_followup_question展示选项：有效/无效/不确定

#### Scenario: 确认有效
- **WHEN** 用户选择"有效"
- **THEN** 系统将发现存入知识库，创建新边

#### Scenario: 确认无效
- **WHEN** 用户选择"无效"
- **THEN** 系统记录排除项，避免重复推荐

#### Scenario: 用户无响应
- **WHEN** 用户不进行确认
- **THEN** 系统保持待确认状态，下次继续推荐

### Requirement: 知识持久化
系统必须将确认的知识持久化存储。

#### Scenario: 存储新边
- **WHEN** 用户确认新的关联
- **THEN** 系统将边插入graph_edges表，标记confirmed=true

#### Scenario: 更新启发记录
- **WHEN** 用户确认后
- **THEN** 系统更新heuristic_records.yaml，记录确认信息

### Requirement: 待确认列表管理
系统必须管理待确认列表，支持查看和处理。

#### Scenario: 查看待确认列表
- **WHEN** 用户请求查看待确认项
- **THEN** 系统展示所有pending状态的发现

#### Scenario: 处理待确认项
- **WHEN** 用户处理某待确认项
- **THEN** 系统更新状态为confirmed或rejected
