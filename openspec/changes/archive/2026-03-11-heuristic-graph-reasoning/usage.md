# 启发式关联图推理系统 - 使用说明

## 系统概述

启发式关联图推理系统已成功实现，提供三层推理能力：

1. **查询能力**（Query）：快速检索已知边
2. **发现能力**（Discovery）：从零开始推理发现新关系
3. **扩散能力**（Diffusion）：从已知边扩散发现相似边

## 快速开始

### 1. 构建知识库（首次使用）

运行初始化脚本构建包含新节点类型（类型层、属性层、触发层）的知识库：

```bash
cd g:/POEMaster/.codebuddy/skills/poe-data-miner/scripts
python init_knowledge_base.py
```

这将：
- 扩展节点类型：type_node, property_node, trigger_mechanism
- 扩展边类型：implies, produces, triggers_via, bypasses 等
- 构建三层节点：类型层、属性层、触发层
- 创建推理边：implies, produces, triggers_via 等

### 2. 运行测试

验证系统功能：

```bash
python test_heuristic_reasoning.py
```

## 核心功能使用

### 统一接口：HeuristicReason

```python
from heuristic_reason import HeuristicReason

# 初始化推理器
reason = HeuristicReason('path/to/graph.db')

# 查询绕过某个约束
result = reason.query_bypass(
    constraint='EnergyCycleLimit',
    mode='auto'  # 可选: 'query', 'discover', 'diffuse', 'auto'
)

# 查看结果
print(f"已知绕过边: {result['summary']['known_count']}")
print(f"发现的绕过边: {result['summary']['discovered_count']}")
print(f"扩散的绕过边: {result['summary']['diffused_count']}")

# 推荐绕过方案
suggestions = reason.suggest_bypasses('EnergyCycleLimit', top_k=5)

# 解释为什么某个实体能绕过约束
explanation = reason.explain_bypass('SpearfieldPlayer', 'EnergyCycleLimit')

reason.close()
```

### 查询能力：HeuristicQuery

```python
from heuristic_query import HeuristicQuery

query = HeuristicQuery('path/to/graph.db')

# 查询已知绕过边
bypasses = query.query_bypasses('EnergyCycleLimit')

# 查询约束的成因
causes = query.query_constraint_causes('EnergyCycleLimit')

# 获取节点统计
stats = query.get_node_stats('MetaCastOnCritPlayer')

query.close()
```

### 发现能力：HeuristicDiscovery

```python
from heuristic_discovery import HeuristicDiscovery

discovery = HeuristicDiscovery('path/to/graph.db')

# 从零发现绕过边
bypasses = discovery.discover_bypass_paths('EnergyCycleLimit')

# 查看推理链
chain = discovery.get_reasoning_chain()

discovery.close()
```

### 扩散能力：HeuristicDiffuse

```python
from heuristic_diffuse import HeuristicDiffuse

diffuse = HeuristicDiffuse('path/to/graph.db')

# 从已知绕过边扩散
known_bypass = {
    'source': 'SpearfieldPlayer',
    'target': 'EnergyCycleLimit'
}

new_bypasses = diffuse.diffuse_from_bypass(known_bypass, similarity_threshold=0.7)

# 提取实体特征
features = diffuse.extract_key_features('SpearfieldPlayer')

# 查找相似实体
similar = diffuse.find_similar_entities(features, threshold=0.7)

diffuse.close()
```

## 命令行工具

### 统一接口命令行

```bash
# 查询绕过边
python heuristic_reason.py graph.db --bypass EnergyCycleLimit --mode auto

# 解释绕过机制
python heuristic_reason.py graph.db --explain SpearfieldPlayer EnergyCycleLimit

# 推荐绕过方案
python heuristic_reason.py graph.db --suggest EnergyCycleLimit --top-k 5
```

### 查询能力命令行

```bash
# 查询绕过边
python heuristic_query.py graph.db --bypass EnergyCycleLimit

# 查询约束成因
python heuristic_query.py graph.db --causes EnergyCycleLimit

# 获取节点统计
python heuristic_query.py graph.db --stats MetaCastOnCritPlayer
```

### 发现能力命令行

```bash
# 从零发现绕过边
python heuristic_discovery.py graph.db --discover EnergyCycleLimit
```

### 扩散能力命令行

```bash
# 从已知边扩散
python heuristic_diffuse.py graph.db --diffuse SpearfieldPlayer EnergyCycleLimit --threshold 0.7
```

## 数据结构

### 新增节点类型

- **type_node**: 类型节点（如 Meta, Hazard, Triggered）
- **property_node**: 属性节点（如 UsesEnergy, DoesNotUseEnergy）
- **trigger_mechanism**: 触发机制节点（如 MetaTrigger, HazardTrigger）

### 新增边类型

- **implies**: 隐含关系（A 隐含 B）
- **produces**: 产生（触发机制产生标签）
- **triggers_via**: 通过...触发
- **creates**: 创建（创建效果而非触发）
- **prevents**: 阻止
- **bypasses**: 绕过
- **constrained_by**: 受...约束
- **enables**: 启用

## 典型使用场景

### 场景1: 探索如何绕过能量循环限制

```python
reason = HeuristicReason('knowledge_base/graph.db')

# 自动查询+发现+扩散
result = reason.query_bypass('EnergyCycleLimit', mode='auto')

# 查看所有绕过方案
for bypass in result['known_bypasses'] + result['discovered_bypasses'] + result['diffused_bypasses']:
    print(f"{bypass['source']} can bypass {bypass['target']}")
    print(f"  Evidence: {bypass['evidence']}")
```

### 场景2: 理解为什么Hazard能绕过能量限制

```python
reason = HeuristicReason('knowledge_base/graph.db')

# 详细解释
explanation = reason.explain_bypass('SpearfieldPlayer', 'EnergyCycleLimit')

print("实体特征:")
print(explanation['features'])

print("关键因素:")
print(explanation['key_factors'])

print("证据:")
print(explanation['evidence'])
```

### 场景3: 发现所有可能的能量循环绕过方案

```python
reason = HeuristicReason('knowledge_base/graph.db')

# 推荐前10个方案
suggestions = reason.suggest_bypasses('EnergyCycleLimit', top_k=10)

for i, sug in enumerate(suggestions, 1):
    print(f"{i}. {sug['source']}")
    print(f"   置信度: {sug.get('confidence', 'N/A')}")
    print(f"   相似度: {sug.get('similarity', 'N/A')}")
```

## 配置文件

### 边语义配置: config/edge_semantics.yaml

定义了所有边类型的语义、传递性和推理规则。

## 下一步

1. **重建知识库**: 运行 `init_knowledge_base.py` 构建包含新节点类型的图
2. **验证系统**: 运行 `test_heuristic_reasoning.py` 验证功能
3. **探索数据**: 使用统一接口或命令行工具探索绕过路径

## 文件列表

### 核心模块
- `attribute_graph.py`: 扩展节点/边类型枚举
- `init_knowledge_base.py`: 添加三层节点构建逻辑
- `heuristic_query.py`: 查询能力实现
- `heuristic_discovery.py`: 发现能力实现
- `heuristic_diffuse.py`: 扩散能力实现
- `heuristic_reason.py`: 统一接口实现

### 配置文件
- `config/edge_semantics.yaml`: 边语义配置

### 测试文件
- `test_heuristic_reasoning.py`: 系统测试脚本

## 实现成果总结

✅ **Phase 1**: 基础扩展完成
- 扩展节点类型：type_node, property_node, trigger_mechanism
- 扩展边类型：implies, produces, triggers_via 等
- 创建边语义配置文件

✅ **Phase 2**: 图构建扩展完成
- 实现类型层构建函数
- 实现属性层构建函数
- 实现触发机制层构建函数
- 集成到初始化流程

✅ **Phase 3**: 查询能力实现完成
- 实现基础查询类
- 实现图遍历辅助函数

✅ **Phase 4**: 发现能力实现完成
- 实现反向推理算法
- 实现反常检测算法
- 实现假设验证算法
- 实现新边生成

✅ **Phase 5**: 扩散能力实现完成
- 实现特征提取
- 实现相似度计算
- 实现扩散推理

✅ **Phase 6**: 统一接口实现完成
- 创建统一接口类
- 实现自动模式

✅ **Phase 7**: 验证与测试完成
- 创建测试脚本
- 验证系统功能
