# Proposal: 启发式关联图推理系统

## 概述

重新设计关联图架构，使其具备三层推理能力：
1. **查询能力** - 快速获取已知边
2. **发现能力** - 从零推理生成新边
3. **扩散能力** - 从已知边发现类似边

## 背景与动机

### 问题

当前关联图设计存在以下缺陷：

1. **因果链断裂** - 无法推理"为什么 Triggered 技能不能为 CoC 提供能量"
2. **隐含属性缺失** - Hazard 标签隐含"不使用能量"，但关联图无法推理
3. **只有查询能力** - 无法从零发现新关系
4. **无法扩散思考** - 发现一个绕过边后，无法自动发现类似的绕过边

### 根本原因

```
当前设计：
  只存储"是什么" → 查询式回答

需要的设计：
  理解"为什么" → 因果推理
  推理"怎么样" → 发现能力
  扩散"还有吗" → 类比推理
```

### 关键案例

**能量循环问题**：

```
问题：暴击时触发的法术无法为 CoC 提供能量，如何绕开？

当前关联图：
  - 有 Hazard 标签节点
  - 无法推理出 Hazard 可以绕过限制
  - 需要预置边才能回答

目标能力：
  - 从零推理：分析约束成因 → 发现反常点 → 验证假设 → 生成绕过边
  - 扩散思考：从 Hazard 绕过边 → 发现 CreationTrigger 也能绕过
```

## 解决方案

### 核心设计

**不新增数据库，直接在关联图内完成推理**

```
┌─────────────────────────────────────────────────────────────────┐
│                    启发式关联图架构                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  查询接口 (heuristic_reason.py)                                 │
│       │                                                         │
│       ▼                                                         │
│  关联图 (graph.db + attribute_graph.py)                         │
│       │                                                         │
│       ▼                                                         │
│  边语义配置 (edge_semantics.yaml)                                │
│                                                                 │
│  推理 = 图遍历 + 边语义理解                                       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 扩展内容

#### 1. 节点类型扩展

```python
class NodeType(Enum):
    # 现有
    ENTITY = "entity"
    MECHANISM = "mechanism"
    ATTRIBUTE = "attribute"
    CONSTRAINT = "constraint"
    
    # 新增
    TYPE_NODE = "type_node"          # 类型节点（Meta, Hazard）
    PROPERTY_NODE = "property_node"   # 属性节点
    TRIGGER_MECHANISM = "trigger_mechanism"  # 触发机制节点
```

#### 2. 边类型扩展

```python
class EdgeType(Enum):
    # 现有
    HAS_TYPE = "has_type"
    HAS_STAT = "has_stat"
    REQUIRES = "requires"
    EXCLUDES = "excludes"
    PROVIDES = "provides"
    
    # 新增
    IMPLIES = "implies"              # 隐含关系
    PRODUCES = "produces"            # 产生
    PREVENTS = "prevents"            # 阻止
    BYPASSES = "bypasses"            # 绕过
    TRIGGERS_VIA = "triggers_via"    # 通过...触发
    CREATES = "creates"              # 创建
    CONSTRAINED_BY = "constrained_by" # 受...约束
```

#### 3. 三层推理能力

```python
class HeuristicGraph:
    def query_bypass(self, constraint, mode='auto'):
        """
        三层能力统一接口
        
        mode='query': 查询已知边
        mode='discover': 从零发现新边
        mode='diffuse': 从已知扩散
        mode='auto': 自动组合三种能力
        """
```

### 关键算法

#### 发现算法

```python
def discover_bypass_paths(graph, constraint):
    """从零开始发现绕过路径"""
    
    # 1. 反向推理：分析约束成因
    causes = analyze_constraint_causes(graph, constraint)
    
    # 2. 反常检测：寻找异常点
    anomalies = find_anomalies(graph, causes)
    
    # 3. 类比推理：分析差异特征
    features = analyze_differences(graph, anomalies)
    
    # 4. 假设生成与验证
    for anomaly in anomalies:
        if verify_hypothesis(graph, anomaly, constraint):
            # 5. 生成新边
            create_bypass_edge(anomaly, constraint)
```

#### 扩散算法

```python
def diffuse_from_bypass(graph, known_bypass_edge):
    """从一条已知的绕过边，发现类似的绕过边"""
    
    # 1. 提取关键特征
    features = extract_features(graph, known_bypass_edge.source)
    
    # 2. 寻找相似实体
    similar_entities = find_similar_entities(graph, features)
    
    # 3. 验证是否能绕过
    for entity in similar_entities:
        if verify_bypass(graph, entity, known_bypass_edge.target):
            # 4. 生成新边
            create_bypass_edge(entity, known_bypass_edge.target)
```

## 实施计划

### Phase 1: 基础扩展（优先）

1. **扩展节点类型** - `attribute_graph.py`
2. **扩展边类型** - `attribute_graph.py`
3. **添加边语义配置** - `config/edge_semantics.yaml`

### Phase 2: 图构建扩展

4. **构建类型层** - `init_knowledge_base.py`
5. **构建属性层** - `init_knowledge_base.py`
6. **构建触发机制层** - `init_knowledge_base.py`

### Phase 3: 推理能力实现

7. **查询能力** - `heuristic_reason.py`
8. **发现能力** - `heuristic_discovery.py`
9. **扩散能力** - `heuristic_diffuse.py`

### Phase 4: 验证与测试

10. **能量循环案例验证** - 测试三层能力
11. **其他场景测试** - 验证通用性

## 预期成果

1. **能够从零推理** - 不依赖预置边，自己发现绕过关系
2. **能够扩散思考** - 从一个发现自动发现更多
3. **保持简洁架构** - 不新增数据库，只在关联图内实现
4. **支持人类思维过程** - 反向推理、反常检测、类比推理、假设验证

## 风险与缓解

| 风险 | 缓解措施 |
|------|----------|
| 发现算法可能生成错误边 | 添加假设验证机制，标记置信度 |
| 性能问题（图遍历） | 优化查询，添加索引 |
| 复杂度增加 | 保持接口简单，三种能力统一入口 |

## 参考案例

**能量循环绕过问题的完整推理链**：

```
Phase 1: 反向推理
  能量生成失败 ← Triggered 标签 ← MetaTrigger

Phase 2: 反常检测
  正常：Meta + Triggers + GeneratesEnergy
  反常：Hazard + Duration（无 GeneratesEnergy）

Phase 3: 类比推理
  Meta 产生 Triggered，Hazard 不产生 → 可能绕过

Phase 4: 假设验证
  假设：Hazard 不产生 Triggered
  验证：Hazard 是自身触发机制 → 假设成立

Phase 5: 生成新边
  Hazard --[implies]--> DoesNotUseEnergy
  DoesNotUseEnergy --[bypasses]--> EnergyCycleLimit

Phase 6: 扩散发现
  从 Hazard 特征 → 发现 CreationTrigger 也类似
  → Doedre's Undoing 也能绕过
```
