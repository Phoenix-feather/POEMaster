## ADDED Requirements

### Requirement: 确认问题格式
系统必须使用ask_followup_question工具展示确认选项。

#### Scenario: 展示确认选项
- **WHEN** 需要用户确认发现
- **THEN** 系统使用ask_followup_question展示选项：有效/无效/不确定

#### Scenario: 多选项支持
- **WHEN** 需要用户选择
- **THEN** 系统提供至少3个选项：确认有效、确认无效、跳过

### Requirement: 确认状态管理
系统必须管理确认过程中的状态。

#### Scenario: 待确认状态
- **WHEN** 发现新知识但未确认
- **THEN** 系统标记status=pending

#### Scenario: 已确认状态
- **WHEN** 用户确认有效
- **THEN** 系统标记status=confirmed

#### Scenario: 已拒绝状态
- **WHEN** 用户确认无效
- **THEN** 系统标记status=rejected

### Requirement: 待确认项持久化
系统必须将待确认项持久化存储，支持跨会话使用。

#### Scenario: 存储待确认项
- **WHEN** 创建新的待确认项
- **THEN** 系统存储到pending_confirmations.yaml

#### Scenario: 加载待确认项
- **WHEN** 系统启动
- **THEN** 系统加载pending_confirmations.yaml中的待确认项

### Requirement: 重复推荐机制
系统必须支持对未确认项的重复推荐。

#### Scenario: 首次推荐
- **WHEN** 存在asked_count=0的待确认项
- **THEN** 系统推荐该项并递增asked_count

#### Scenario: 再次推荐
- **WHEN** 存在asked_count>0但status仍为pending的项
- **THEN** 系统继续推荐该项

### Requirement: 确认后的知识更新
系统必须在用户确认后更新知识库。

#### Scenario: 确认后更新关联图
- **WHEN** 用户确认新的关联
- **THEN** 系统将边插入graph_edges表

#### Scenario: 确认后更新启发记录
- **WHEN** 用户确认
- **THEN** 系统创建或更新启发记录
