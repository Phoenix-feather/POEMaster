# 启发式推理系统代码审查报告

**审查时间**: 2026-03-11  
**审查范围**: heuristic_graph_reasoning 系统实现  
**审查标准**: TODO标记、空实现、简化实现、硬编码、异常处理

---

## 发现的问题清单

### 🔴 高优先级问题

#### 1. 组合类型未实现（init_knowledge_base.py）

**位置**: `build_property_layer()` 函数，第806-808行

**问题**:
```python
# 对于组合类型，我们需要更复杂的逻辑
# 这里简化处理：为第一个类型创建 implies 边
if len(types) == 1:
    # ... 处理单类型
```

**影响**: 组合类型属性映射（如 "Meta + GeneratesEnergy" → "UsesEnergySystem"）完全未实现

**建议修复**:
```python
# 创建 implies 边（从 type_node 到 property_node）
for type_combo, mapping in type_property_mappings.items():
    # 解析组合类型
    types = [t.strip() for t in type_combo.split('+')]
    
    # 为每个属性创建 implies 边
    for prop in mapping['properties']:
        # 处理单类型
        if len(types) == 1:
            type_node_id = f"type_{types[0].lower().replace(' ', '_')}"
            prop_node_id = f"prop_{prop.lower().replace(' ', '_')}"
            # ... 创建 implies 边
        
        # 处理组合类型（新增）
        elif len(types) > 1:
            # 创建组合类型节点
            combo_node_id = f"type_combo_{'_'.join([t.lower() for t in types])}"
            # ... 创建组合节点和 implies 边
```

---

#### 2. 硬编码的触发机制映射（init_knowledge_base.py）

**位置**: `build_trigger_layer()` 函数，第867-879行

**问题**:
```python
entity_trigger_mapping = {
    # Meta 技能使用 MetaTrigger
    'MetaCastOnCritPlayer': 'MetaTrigger',
    'MetaCastOnMeleeKillPlayer': 'MetaTrigger',
    # ... 硬编码列表
}
```

**影响**: 
- 新增技能需要手动添加映射
- 无法自动识别新的触发机制类型
- 维护成本高

**建议修复**:
```python
def detect_trigger_mechanism(entity_data: dict) -> str:
    """从实体数据自动识别触发机制"""
    skill_types = entity_data.get('skill_types', [])
    stats = entity_data.get('stats', [])
    
    # Meta 技能特征：Meta标签 + GeneratesEnergy
    if 'Meta' in skill_types and any('Energy' in s for s in stats):
        return 'MetaTrigger'
    
    # Hazard 技能特征：Hazard标签 + 无能量生成
    if 'Hazard' in skill_types:
        return 'HazardTrigger'
    
    # 其他触发机制...
    return 'Unknown'

# 使用自动检测
cursor.execute('SELECT id, skill_types, stats FROM entities')
for row in cursor.fetchall():
    entity_id = row[0]
    entity_data = {
        'skill_types': json.loads(row[1]) if row[1] else [],
        'stats': json.loads(row[2]) if row[2] else []
    }
    trigger_mech = detect_trigger_mechanism(entity_data)
    # ... 创建 triggers_via 边
```

---

### 🟡 中优先级问题

#### 3. 硬编码的属性映射（init_knowledge_base.py）

**位置**: `build_property_layer()` 函数，第729-765行

**问题**:
```python
type_property_mappings = {
    'Meta': {
        'properties': ['UsesTriggerMechanism'],
        'description': 'Meta技能使用触发机制'
    },
    # ... 硬编码映射
}
```

**影响**:
- 新的类型-属性关系需要手动添加
- 无法从POB数据自动发现新的属性映射

**建议修复**:
```python
# 将映射规则提取到配置文件
# config/type_property_mappings.yaml

mappings:
  Meta:
    properties:
      - UsesTriggerMechanism
    description: "Meta技能使用触发机制"
  
  Hazard:
    properties:
      - DoesNotUseEnergy
      - DoesNotProduceTriggered
    description: "Hazard不使用能量系统"
```

然后在代码中加载：
```python
import yaml

def load_type_property_mappings(config_path: str) -> dict:
    """从配置文件加载类型-属性映射"""
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    return config.get('mappings', {})
```

---

#### 4. 空异常处理（多处）

**位置**:
- `init_knowledge_base.py` 第796-797、828-829、909-910、922-923行
- 其他文件中的 `except Exception as e: pass`

**问题**:
```python
try:
    graph_cursor.execute(...)
    # ...
except Exception as e:
    pass  # 隐藏错误，难以调试
```

**影响**:
- 隐藏数据库错误
- 难以发现数据问题
- 调试困难

**建议修复**:
```python
import logging

logger = logging.getLogger(__name__)

try:
    graph_cursor.execute(...)
except sqlite3.IntegrityError as e:
    logger.warning(f"节点已存在，跳过: {node_id}")
except sqlite3.DatabaseError as e:
    logger.error(f"数据库错误: {e}")
    raise
except Exception as e:
    logger.error(f"未知错误: {e}")
    raise
```

---

### 🟢 低优先级问题

#### 5. 魔法数字（heuristic_diffuse.py）

**位置**: `calculate_similarity()` 函数

**问题**:
```python
weights = {
    'types': 0.3,
    'properties': 0.4,  # 魔法数字
    'trigger_mechanisms': 0.2,
    'stats': 0.05,
    'constraints': 0.05
}
```

**建议修复**:
```python
# 在配置文件或类常量中定义
class SimilarityWeights:
    TYPES = 0.3
    PROPERTIES = 0.4  # 属性权重最高
    TRIGGER_MECHANISMS = 0.2
    STATS = 0.05
    CONSTRAINTS = 0.05
```

---

#### 6. 硬编码的相似度阈值（多处）

**位置**:
- `heuristic_diffuse.py` 默认 `similarity_threshold=0.7`
- `heuristic_reason.py` 默认 `similarity_threshold=0.7`

**建议修复**:
```python
# 配置文件: config/heuristic_config.yaml
defaults:
  similarity_threshold: 0.7
  confidence_threshold: 0.8
  max_diffuse_results: 10
```

---

## 总结

### 问题统计

| 优先级 | 数量 | 关键问题 |
|--------|------|----------|
| 🔴 高 | 2 | 组合类型未实现、硬编码映射 |
| 🟡 中 | 2 | 硬编码配置、空异常处理 |
| 🟢 低 | 2 | 魔法数字、硬编码阈值 |
| **总计** | **6** | |

### 影响评估

**功能性影响**:
- ❌ 组合类型属性映射完全缺失（功能缺失）
- ⚠️ 硬编码映射导致维护困难（可维护性）
- ⚠️ 空异常处理导致调试困难（可调试性）

**可维护性影响**:
- 需要将硬编码配置提取到配置文件
- 需要实现自动化识别逻辑
- 需要改进异常处理和日志记录

### 建议行动计划

**立即修复** (P0):
1. 实现组合类型属性映射逻辑
2. 实现触发机制自动识别

**短期改进** (P1):
3. 将硬编码配置提取到配置文件
4. 改进异常处理，添加日志记录

**长期优化** (P2):
5. 提取魔法数字为配置项
6. 实现配置热重载机制

---

## 代码质量评分

| 维度 | 评分 | 说明 |
|------|------|------|
| 功能完整性 | 7/10 | 组合类型未实现 |
| 代码可读性 | 9/10 | 文档清晰，命名规范 |
| 可维护性 | 6/10 | 硬编码过多 |
| 异常处理 | 5/10 | 大量空catch块 |
| 测试覆盖 | 8/10 | 有测试脚本但不够全面 |
| **总体评分** | **7/10** | 良好，需要改进 |

---

## 附录：关键代码位置

### init_knowledge_base.py
- 第729-765行：硬编码的类型-属性映射
- 第806-808行：组合类型简化处理（未实现）
- 第867-879行：硬编码的触发机制映射
- 第796-797行：空异常处理

### heuristic_diffuse.py
- 第474-492行：硬编码的相似度权重

### heuristic_reason.py
- 第33-39行：硬编码的默认阈值

---

**审查人**: AI Assistant  
**审查日期**: 2026-03-11  
**下一步**: 根据优先级创建修复任务
