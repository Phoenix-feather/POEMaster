## ADDED Requirements

### Requirement: 节点创建
系统必须创建四种类型的节点：实体节点、机制节点、属性节点、约束节点。

#### Scenario: 从skillTypes创建机制节点
- **WHEN** 扫描实体skillTypes
- **THEN** 系统为每个唯一的skillType创建机制节点

#### Scenario: 从stats创建属性节点
- **WHEN** 扫描实体stats
- **THEN** 系统为每个唯一的stat创建属性节点

#### Scenario: 从规则创建约束节点
- **WHEN** 提取条件规则
- **THEN** 系统为规则中的约束条件创建约束节点

### Requirement: 边构建
系统必须创建多种类型的边：has_type、has_stat、causes、blocks、bypasses等。

#### Scenario: 创建实体-机制边
- **WHEN** 实体拥有某个skillType
- **THEN** 系统创建 entity ──has_type──▶ mechanism 边

#### Scenario: 创建约束边
- **WHEN** 规则条件阻止某个效果
- **THEN** 系统创建 condition ──blocks──▶ effect 边

#### Scenario: 创建绕过边
- **WHEN** 发现机制可以绕过限制
- **THEN** 系统创建 mechanism ──bypasses──▶ constraint 边

### Requirement: 图遍历查询
系统必须支持BFS/DFS图遍历，用于路径搜索和关联发现。

#### Scenario: 路径搜索
- **WHEN** 查询两个节点之间的路径
- **THEN** 系统使用递归CTE返回所有路径

#### Scenario: 邻居查询
- **WHEN** 查询某节点的所有邻居
- **THEN** 系统返回所有相连的节点和边类型

### Requirement: 预置边加载
系统必须从config/predefined_edges.yaml加载预置边。

#### Scenario: 加载预置边
- **WHEN** 初始化关联图
- **THEN** 系统加载预置边并标记来源为predefined
