# 硬编码依赖分析文档

## 硬编码问题清单

### 1. 数据类型名称硬编码

| 文件 | 硬编码 | 依赖源 | 风险 |
|------|--------|--------|------|
| init_knowledge_base.py | `type='mod_definition'` | data_scanner.py DataType | 类型名称不匹配 |
| init_knowledge_base.py | `type='calculation_module'` | data_scanner.py DataType | 类型名称不匹配 |
| init_knowledge_base.py | `type='stat_mapping'` | data_scanner.py DataType | 类型名称不匹配 |
| attribute_graph.py | `type='mechanism'` | 内部定义 | 类型名称不一致 |

### 2. 数据字段名称硬编码

| 文件 | 期望字段 | 实际字段 | 风险 |
|------|----------|----------|------|
| rules_extractor.py | `stat_name` | `name` | 字段名不匹配 |
| rules_extractor.py | `target`, `mods` | `mod_data` | 字段名不匹配 |
| attribute_graph.py | `stats` (list) | `stats` (dict) | 类型不匹配 |

### 3. 过滤条件硬编码

| 文件 | 条件 | 问题 |
|------|------|------|
| rules_extractor.py | `len(expression) > 15` | 可能遗漏短公式 |
| rules_extractor.py | `calc_keywords` | 可能遗漏状态判断 |

---

## 依赖关系图

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    数据依赖关系                                           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  [POB 数据源]                                                           │
│       │                                                                 │
│       ▼                                                                 │
│  [data_scanner.py]                                                      │
│       │                                                                 │
│       ├── DataType 枚举 ──────────────────────────────────────┐        │
│       │   ├── skill_definition                                │        │
│       │   ├── gem_definition                                  │        │
│       │   ├── stat_mapping  ◀── 硬编码点: type='mod_definition'       │
│       │   ├── calculation_module                              │        │
│       │   └── ...                                             │        │
│       │                                                       │        │
│       ▼                                                       │        │
│  [entity_index.py]                                           │        │
│       │                                                       │        │
│       │  实体数据格式                                          │        │
│       │  ├── id, name, type                                   │        │
│       │  ├── skill_types (list)                               │        │
│       │  ├── stats (list/dict) ◀── 硬编码点: 期望 list         │        │
│       │  └── ...                                              │        │
│       │                                                       │        │
│       ▼                                                       │        │
│  [rules_extractor.py]                                        │        │
│       │                                                       │        │
│       │  期望格式:                                             │        │
│       │  ├── stat_name  ◀── 实际: name (不匹配)               │        │
│       │  ├── target      ◀── 实际: 无 (不匹配)                │        │
│       │  └── mods        ◀── 实际: mod_data (不匹配)          │        │
│       │                                                       │        │
│       ▼                                                       │        │
│  [attribute_graph.py]                                        │        │
│       │                                                       │        │
│       │  期望格式:                                             │        │
│       │  └── stats (list) ◀── 实际: dict (类型不匹配)         │        │
│       │                                                       │        │
│       ▼                                                       │        │
│  [知识库数据库]                                               │        │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 改进方案

### 方案 A: 依赖注册机制

创建依赖配置文件，记录所有硬编码关系：

```yaml
# dependencies.yaml
data_types:
  - name: stat_mapping
    used_as: mod_definition  # 历史遗留问题
    files:
      - init_knowledge_base.py:243
    auto_fix: true

field_mappings:
  - expected: stat_name
    actual: name
    files:
      - rules_extractor.py:197
    auto_fix: true

  - expected: mods
    actual: mod_data
    files:
      - rules_extractor.py:213
    auto_fix: true

type_expectations:
  - field: stats
    expected: list
    actual: [list, dict]
    files:
      - attribute_graph.py:431
    auto_fix: true
```

### 方案 B: 宽松匹配策略

修改代码，采用宽松匹配而非严格匹配：

```python
# 宽松匹配示例
def extract_layer2_statmap(self, stat_mappings: List[Dict]) -> List[Rule]:
    for mapping in stat_mappings:
        # 宽松匹配：尝试多种可能的字段名
        stat_name = (
            mapping.get('stat_name') or 
            mapping.get('name') or 
            mapping.get('id', '')
        )
        
        mods = (
            mapping.get('mods') or 
            mapping.get('mod_data') or 
            []
        )
        # ...
```

### 方案 C: 数据格式适配层

创建适配层，统一不同格式的数据：

```python
class StatMappingAdapter:
    """属性映射适配器"""
    
    @staticmethod
    def adapt(data: Dict) -> Dict:
        """适配不同格式的数据"""
        return {
            'stat_name': data.get('stat_name') or data.get('name') or data.get('id'),
            'target': data.get('target'),
            'mods': data.get('mods') or data.get('mod_data') or [],
            'type': data.get('type')
        }
```

---

## 推荐实施

| 阶段 | 方案 | 内容 |
|------|------|------|
| **立即修复** | B | 修改代码使用宽松匹配 |
| **短期优化** | A | 创建依赖配置文件 |
| **长期改进** | C | 添加适配层 |

---

## 变更触发机制

当检测到数据格式变化时：

1. **自动检测**: 扫描数据源，检测格式变化
2. **报告警告**: 记录不匹配的依赖关系
3. **自动适配**: 使用宽松匹配或适配层处理
4. **人工确认**: 关键变更需要人工确认

```python
def check_dependencies():
    """检查依赖关系"""
    warnings = []
    
    # 检查数据类型
    expected_types = ['stat_mapping', 'calculation_module']
    for t in expected_types:
        count = db.execute("SELECT COUNT(*) FROM entities WHERE type=?", (t,))
        if count == 0:
            warnings.append(f"数据类型 '{t}' 不存在")
    
    # 检查字段格式
    # ...
    
    return warnings
```
