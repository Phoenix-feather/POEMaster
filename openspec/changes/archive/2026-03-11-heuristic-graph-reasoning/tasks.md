# Tasks: 启发式关联图推理系统

## Phase 1: 基础扩展

### Task 1.1: 扩展节点类型枚举
- **文件**: `scripts/attribute_graph.py`
- **内容**:
  - 添加 `TYPE_NODE = "type_node"`
  - 添加 `PROPERTY_NODE = "property_node"`
  - 添加 `TRIGGER_MECHANISM = "trigger_mechanism"`
- **验证**: 运行 `python -c "from attribute_graph import NodeType; print(NodeType.TYPE_NODE)"`

### Task 1.2: 扩展边类型枚举
- **文件**: `scripts/attribute_graph.py`
- **内容**:
  - 添加 `IMPLIES`, `PRODUCES`, `PREVENTS`, `BYPASSES`
  - 添加 `TRIGGERS_VIA`, `CREATES`, `CONSTRAINED_BY`
  - 添加 `INCOMPATIBLE_WITH`, `ENABLES`
- **验证**: 运行 `python -c "from attribute_graph import EdgeType; print(EdgeType.BYPASSES)"`

### Task 1.3: 创建边语义配置文件
- **文件**: `config/edge_semantics.yaml`
- **内容**:
  - 定义所有边类型的语义
  - 定义传递性规则
  - 定义推理规则
- **验证**: 检查 YAML 文件格式正确

---

## Phase 2: 图构建扩展

### Task 2.1: 添加类型节点构建函数
- **文件**: `scripts/init_knowledge_base.py`
- **内容**:
  - 从 entities.db 提取所有唯一的 skill_types
  - 为每个 skill_type 创建 type_node 节点
  - 创建 `build_type_layer()` 函数
- **验证**: 查询 graph.db 中 type_node 数量

### Task 2.2: 添加属性节点构建函数
- **文件**: `scripts/init_knowledge_base.py`
- **内容**:
  - 定义类型到属性的映射规则（如 Meta → UsesEnergySystem）
  - 创建 property_node 节点
  - 创建 `implies` 边连接 type_node 和 property_node
  - 创建 `build_property_layer()` 函数
- **验证**: 查询 graph.db 中 property_node 数量和 implies 边数量

### Task 2.3: 添加触发机制节点构建函数
- **文件**: `scripts/init_knowledge_base.py`
- **内容**:
  - 定义触发机制类型（MetaTrigger, HazardTrigger, CreationTrigger）
  - 创建 trigger_mechanism 节点
  - 创建 `produces` 边（MetaTrigger → Triggered）
  - 创建 `triggers_via` 边（实体 → 触发机制）
  - 创建 `build_trigger_layer()` 函数
- **验证**: 查询 graph.db 中 trigger_mechanism 数量和 produces 边数量

### Task 2.4: 集成到初始化流程
- **文件**: `scripts/init_knowledge_base.py`
- **内容**:
  - 在 `init_attribute_graph()` 中调用三个构建函数
  - 添加增量构建支持（只添加新节点）
- **验证**: 重建关联图并统计新增节点/边数量

---

## Phase 3: 查询能力实现

### Task 3.1: 创建基础查询类
- **文件**: `scripts/heuristic_query.py`
- **内容**:
  - 实现 `HeuristicQuery` 类
  - 实现 `query_bypasses(constraint)` 方法
  - 实现 `query_constraint_causes(constraint)` 方法
- **验证**: 测试查询已知绕过边

### Task 3.2: 添加图遍历辅助函数
- **文件**: `scripts/heuristic_query.py`
- **内容**:
  - 实现 `trace_back_to_entity(node)` 方法
  - 实现 `get_all_paths(source, target)` 方法
  - 实现 `get_neighbors_by_edge_type(node, edge_type)` 方法
- **验证**: 测试从 property_node 反向追溯到 entity

---

## Phase 4: 发现能力实现

### Task 4.1: 实现反向推理算法
- **文件**: `scripts/heuristic_discovery.py`
- **内容**:
  - 实现 `analyze_constraint_causes(constraint)` 方法
  - 实现 `trace_causal_chain(node)` 方法
  - 实现 `identify_key_factors(causes)` 方法
- **验证**: 测试分析 EnergyCycleLimit 的成因

### Task 4.2: 实现反常检测算法
- **文件**: `scripts/heuristic_discovery.py`
- **内容**:
  - 实现 `find_anomalies(causes)` 方法
  - 实现 `get_normal_pattern(factor)` 方法
  - 实现 `matches_pattern(entity, pattern)` 方法
- **验证**: 测试发现 Hazard 作为反常点

### Task 4.3: 实现假设验证算法
- **文件**: `scripts/heuristic_discovery.py`
- **内容**:
  - 实现 `verify_bypass(entity, constraint)` 方法
  - 实现 `gather_evidence(entity, constraint)` 方法
  - 实现 `get_constraint_key_factors(constraint)` 方法
- **验证**: 测试验证 Hazard 能否绕过 EnergyCycleLimit

### Task 4.4: 实现新边生成
- **文件**: `scripts/heuristic_discovery.py`
- **内容**:
  - 实现 `create_bypass_edge(source, target)` 方法
  - 实现推理链记录
  - 实现置信度计算
- **验证**: 测试生成新的 bypasses 边

---

## Phase 5: 扩散能力实现

### Task 5.1: 实现特征提取
- **文件**: `scripts/heuristic_diffuse.py`
- **内容**:
  - 实现 `extract_key_features(entity)` 方法
  - 实现 `get_implied_properties(entity)` 方法
- **验证**: 测试提取 Hazard 的关键特征

### Task 5.2: 实现相似度计算
- **文件**: `scripts/heuristic_diffuse.py`
- **内容**:
  - 实现 `find_similar_entities(features, exclude)` 方法
  - 实现 `calculate_similarity(features1, features2)` 方法
  - 实现 Jaccard 相似度算法
- **验证**: 测试从 Hazard 发现相似的 CreationTrigger

### Task 5.3: 实现扩散推理
- **文件**: `scripts/heuristic_diffuse.py`
- **内容**:
  - 实现 `diffuse_from_bypass(known_bypass_edge)` 方法
  - 实现批量扩散
  - 实现扩散深度控制
- **验证**: 测试从已知绕过边扩散发现新边

---

## Phase 6: 统一接口实现

### Task 6.1: 创建统一接口类
- **文件**: `scripts/heuristic_reason.py`
- **内容**:
  - 实现 `HeuristicReason` 类
  - 集成 query, discovery, diffuse 三个能力
  - 实现 `query_bypass(constraint, mode='auto')` 方法
- **验证**: 测试三种模式分别工作

### Task 6.2: 实现自动模式
- **文件**: `scripts/heuristic_reason.py`
- **内容**:
  - 实现智能选择逻辑
  - 有已知边 → 扩散
  - 无已知边 → 发现
  - 结果去重和排序
- **验证**: 测试 auto 模式完整流程

---

## Phase 7: 验证与测试

### Task 7.1: 能量循环案例验证
- **内容**:
  - 测试从零发现 Hazard 绕过 EnergyCycleLimit
  - 测试从 Hazard 扩散发现 CreationTrigger
  - 验证推理链完整性
- **预期结果**:
  - 发现能力：生成 1 条新边
  - 扩散能力：从 1 条边扩散出 2-3 条新边

### Task 7.2: 其他场景测试
- **内容**:
  - 测试 Triggered 标签限制
  - 测试 Meta 技能约束
  - 测试被动技能限制
- **预期结果**: 系统能发现绕过路径

### Task 7.3: 性能测试
- **内容**:
  - 测试大规模图遍历性能
  - 测试发现算法性能
  - 测试扩散算法性能
- **预期结果**: 单次推理 < 5 秒

---

## 完成标准

- [x] Phase 1: 基础扩展完成 ✅
- [x] Phase 2: 图构建扩展完成 ✅
- [x] Phase 3: 查询能力实现 ✅
- [x] Phase 4: 发现能力实现 ✅
- [x] Phase 5: 扩散能力实现 ✅
- [x] Phase 6: 统一接口实现 ✅
- [x] Phase 7: 验证与测试通过 ✅

## 依赖关系

```
Phase 1 (基础扩展)
    ↓
Phase 2 (图构建) ← 需要 Phase 1 的节点/边类型
    ↓
Phase 3 (查询能力) ← 需要 Phase 2 的图数据
    ↓
Phase 4 (发现能力) ← 需要 Phase 3 的基础查询
    ↓
Phase 5 (扩散能力) ← 需要 Phase 4 的验证逻辑
    ↓
Phase 6 (统一接口) ← 需要 Phase 3-5 的所有能力
    ↓
Phase 7 (验证测试)
```

## 优先级

1. **P0 (最高)**: Phase 1, Phase 2 - 基础架构
2. **P1 (高)**: Phase 4 - 发现能力（核心功能）
3. **P2 (中)**: Phase 3, Phase 5 - 查询和扩散
4. **P3 (低)**: Phase 6, Phase 7 - 集成和测试
