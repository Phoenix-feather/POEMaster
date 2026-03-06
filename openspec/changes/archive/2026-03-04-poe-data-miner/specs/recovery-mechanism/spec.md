## ADDED Requirements

### Requirement: 版本检测
系统必须在启动时检测POB数据版本是否变化。

#### Scenario: 版本未变化
- **WHEN** 当前版本与记录版本相同
- **THEN** 系统跳过重建，直接加载已有知识库

#### Scenario: 版本已变化
- **WHEN** 当前版本与记录版本不同
- **THEN** 系统触发重建流程

### Requirement: 静态数据重建
系统必须在版本更新后完全重建静态数据索引。

#### Scenario: 重建entities表
- **WHEN** 触发重建
- **THEN** 系统重新扫描所有Lua文件，重建entities表

#### Scenario: 重建rules表
- **WHEN** 触发重建
- **THEN** 系统重新提取规则，重建rules表

### Requirement: 用户知识迁移
系统必须迁移用户确认的知识，并进行验证。

#### Scenario: 验证启发记录
- **WHEN** 重建关联图
- **THEN** 系统使用启发记录重新探索，验证知识有效性

#### Scenario: 知识有效
- **WHEN** 重新探索结果与原记录一致
- **THEN** 系统保留该知识，标记verified

#### Scenario: 知识失效
- **WHEN** 重新探索结果与原记录不一致
- **THEN** 系统将知识移入未确认列表

### Requirement: 未确认列表管理
系统必须维护未确认列表，支持持久化存储。

#### Scenario: 存储未确认项
- **WHEN** 检测到机制变化
- **THEN** 系统创建未确认项，存储到unverified_list.yaml

#### Scenario: 处理未确认项
- **WHEN** 用户验证未确认项
- **THEN** 系统更新状态，从列表中移除

### Requirement: 数值变化自动验证
系统必须自动验证数值变化，不提醒用户。

#### Scenario: 数值调整
- **WHEN** 检测到基础能量从100变为120
- **THEN** 系统自动更新，不创建未确认项

### Requirement: 机制变化提醒
系统必须在机制变化时提醒用户需要重新验证。

#### Scenario: 标签类型变化
- **WHEN** 检测到skillTypes变化
- **THEN** 系统创建未确认项，提醒用户重新探索

#### Scenario: 计算公式变化
- **WHEN** 检测到能量公式变化
- **THEN** 系统创建未确认项，提醒用户确认
