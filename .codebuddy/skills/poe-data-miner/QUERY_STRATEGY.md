# 查询策略指南

## 决策标准：三问法

在处理用户问题时，先问自己三个问题：

### 问题1：这是"是什么"问题还是"如何关联"问题？

| 问题类型 | 特征 | 查询方法 |
|---------|------|---------|
| "是什么" | 属性、数值、定义 | 数据查询 |
| "如何关联" | 关系、影响、路径 | 关联图 |

**示例**：
- "CoC的能量公式是什么？" → 数据查询
- "有哪些技能会影响CoC？" → 关联图

---

### 问题2：是否需要发现隐含关系？

| 需求类型 | 特征 | 查询方法 |
|---------|------|---------|
| 显式信息 | 用户明确问某个属性 | 数据查询 |
| 隐式关系 | 用户问"有什么关系"、"如何影响" | 关联图 |

**示例**：
- "CoC的能量生成率是多少？" → 数据查询（显式）
- "能量生成受哪些因素影响？" → 关联图（隐式）

---

### 问题3：是否存在绕过或异常的可能？

| 问题类型 | 特征 | 查询方法 |
|---------|------|---------|
| 常规机制 | 标准规则、正常流程 | 数据查询 |
| 绕过机制 | "能否绕过"、"是否有例外" | **必须用关联图** |

**示例**：
- "CoC如何触发技能？" → 数据查询（常规）
- "是否能绕过Triggerable限制？" → 关联图（绕过）

---

## 查询方法对照表

### 数据查询（Direct Query）

**适用场景**：
- 查询实体属性 → `entities.db`
- 查询规则约束 → `rules.db`
- 查询公式定义 → `formulas.db`
- 验证假设

**SQL模板**：
```sql
-- 查询实体属性
SELECT id, name, data_json FROM entities WHERE name LIKE '%CoC%'

-- 查询规则约束
SELECT condition, effect FROM rules WHERE source_entity = 'MetaCastOnCritPlayer'

-- 查询公式
SELECT formula_text FROM gap_formulas WHERE entity_id LIKE '%MetaCastOnCrit%'
```

---

### 关联图查询（Graph Query）

**适用场景**：
- 发现隐含关系
- 多跳推理（A → B → C）
- 探索绕过路径
- 发现共同特征

**SQL模板**：
```sql
-- 发现影响某属性的所有实体
SELECT source_node, edge_type FROM graph_edges WHERE target_node = 'energy_generated_+%'

-- 发现某实体的所有关系
SELECT edge_type, target_node FROM graph_edges WHERE source_node = 'MetaCastOnCritPlayer'

-- 发现某个标签的来源
SELECT source_node FROM graph_edges WHERE target_node = 'Triggerable' AND edge_type = 'addSkillTypes'

-- 发现绕过或异常
SELECT * FROM graph_edges WHERE edge_type IN ('bypass', 'overrides', 'excludes')
```

---

## 混合查询策略

对于复杂问题，应该**同时使用两种方法**：

### 处理流程：

```
用户问题
    ↓
Step 1: 判断问题类型（三问法）
    ↓
Step 2: 数据查询（获取基础信息）
    ├─ 查询相关实体
    ├─ 查询相关规则
    └─ 查询相关公式
    ↓
Step 3: 关联图查询（发现隐含关系）
    ├─ 找出所有相关边
    ├─ 发现影响关系
    └─ 探索绕过路径
    ↓
Step 4: 综合推理
    └─ 数据 + 关系 → 完整结论
```

---

## 示例：重新处理"CoC能量自循环"

### 问题分析：
```
问题："暴击释放如何实现能量自循环"

三问法判断：
1. "如何实现" → 可能涉及关系 → 需要关联图
2. "自循环" → 隐含绕过机制 → 必须用关联图
3. 是否存在绕过？ → 是 → 必须用关联图
```

### 执行流程：

#### Step 1: 数据查询
```sql
-- 查询CoC基础信息
SELECT id, name, data_json FROM entities WHERE id = 'MetaCastOnCritPlayer'

-- 查询CoC触发规则
SELECT condition, effect FROM rules WHERE source_entity = 'MetaCastOnCritPlayer'

-- 查询能量公式
SELECT formula_text FROM gap_formulas WHERE entity_id = 'MetaCastOnCritPlayer'
```

#### Step 2: 关联图查询
```sql
-- 发现CoC的所有关系
SELECT edge_type, target_node FROM graph_edges WHERE source_node = 'MetaCastOnCritPlayer'

-- 发现影响energy_generated_+%的所有实体
SELECT source_node, edge_type FROM graph_edges WHERE target_node = 'energy_generated_+%'

-- 探索是否有绕过Triggerable限制的方法
SELECT source_node FROM graph_edges WHERE target_node = 'Triggerable' AND edge_type = 'addSkillTypes'

-- 发现Meta技能的共同特征
SELECT edge_type, target_node FROM graph_edges WHERE source_node LIKE '%Meta%Player'
```

#### Step 3: 综合推理
```
数据查询结果：
- CoC需要Triggerable标签
- Meta技能没有Triggerable标签

关联图发现：
- Meta技能都有"cannot be triggered"边
- 没有技能能添加Triggerable标签给Meta
- 支持技能会排除Meta技能

结论：CoC无法触发Meta技能，无法实现自循环
```

---

## 常见错误及修正

### 错误1：只查数据，不用图

**症状**：回答了"是什么"，但没有回答"如何关联"

**修正**：看到"如何"、"影响"、"关系"等词时，必须用关联图

---

### 错误2：忽略绕过路径

**症状**：只回答了"正常情况"，没有探索"是否存在例外"

**修正**：遇到限制性规则时，应该探索是否有绕过方法

---

### 错误3：单一数据源

**症状**：只查了一个数据库，信息不完整

**修正**：复杂问题应该同时查询entities、rules、formulas、graph

---

## 检查清单

每次回答问题前，检查：

- [ ] 是否使用了三问法判断？
- [ ] 是否查询了所有相关数据源？
- [ ] 是否使用了关联图发现隐含关系？
- [ ] 是否探索了绕过路径？
- [ ] 是否综合了所有信息？

---

## 版本历史

- v1.0 (2026-03-12): 初始版本，基于CoC问题的反思
