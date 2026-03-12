# POB代码索引系统

## 概述

四级索引系统，用于快速查询POB代码，支持验证引擎的高效运行。

## 架构

```
indexes/
├── __init__.py              # 模块入口
├── base_index.py            # 基础索引类
├── stat_index.py            # 一级索引：Stat定义和使用
├── skilltype_index.py       # 二级索引：SkillType约束
├── function_index.py        # 三级索引：函数调用
├── semantic_index.py        # 四级索引：语义特征
└── index_manager.py         # 索引管理器
```

## 四级索引说明

### 1. StatIndex（一级索引）

**用途**：快速定位stat定义和使用位置

**查询示例**：
```python
from indexes import StatIndex

index = StatIndex('indexes/stat_index.db')

# 查询stat定义
result = index.search({'stat_id': 'FireDamage'})

# 模糊搜索
result = index.search({'fuzzy': 'fire'})

# 按技能查询
result = index.search({'skill_name': 'Fireball'})

# 获取高频stats
top_stats = index.get_top_stats(100)
```

**性能**：
- 查询时间：< 10ms
- 支持模糊搜索
- 支持使用频率统计

### 2. SkillTypeIndex（二级索引）

**用途**：快速定位skillTypes约束关系

**查询示例**：
```python
from indexes import SkillTypeIndex

index = SkillTypeIndex('indexes/skilltype_index.db')

# 查询某类型的所有约束
result = index.search({'skill_type': 'Triggered'})
# 返回: required_by, excluded_by, added_by

# 查询技能的约束
result = index.search({'skill_name': 'CoC'})

# 获取所有skillTypes
all_types = index.get_all_skilltypes()
```

**性能**：
- 查询时间：< 20ms
- 支持约束关系统计
- 支持反向查询

### 3. FunctionCallIndex（三级索引）

**用途**：快速定位CalcModules中的函数和调用关系

**查询示例**：
```python
from indexes import FunctionCallIndex

index = FunctionCallIndex('indexes/function_index.db')

# 查询函数定义和调用
result = index.search({'function_name': 'isTriggered'})
# 返回: definition, parameters, called_by, calls_to

# 按文件查询
result = index.search({'file_path': 'Modules/CalcTriggers.lua'})

# 获取高频调用函数
top_funcs = index.get_top_called_functions(50)

# 查找调用链
chains = index.find_call_chain('isTriggered', 'calcEnergy', max_depth=10)
```

**性能**：
- 查询时间：< 50ms
- 支持调用图分析
- 支持调用链查找

### 4. SemanticFeatureIndex（四级索引）

**用途**：支持语义级别的快速搜索和相似度计算

**查询示例**：
```python
from indexes import SemanticFeatureIndex

index = SemanticFeatureIndex('indexes/semantic_index.db')

# 查找相似实体
result = index.search({'entity': 'Fireball', 'top_k': 10})
# 返回: similar_entities with similarity scores

# 按关键词查询
result = index.search({'keywords': ['fire', 'damage']})

# 按标签查询
result = index.search({'tags': ['spell', 'fire']})

# 按标签获取实体
entities = index.get_entities_by_tag('fire')

# 按关键词获取实体
entities = index.get_entities_by_keyword('trigger')
```

**性能**：
- 查询时间：< 100ms
- 支持相似度缓存
- 支持特征向量搜索

## 使用方法

### 1. 构建索引

```bash
# 构建所有索引
python scripts/build_indexes.py --build --pob-data POBData

# 查看统计信息
python scripts/build_indexes.py --stats --pob-data POBData

# 检查健康状态
python scripts/build_indexes.py --health --pob-data POBData

# 优化索引
python scripts/build_indexes.py --optimize --pob-data POBData

# 导出报告
python scripts/build_indexes.py --report report.yaml --pob-data POBData
```

### 2. 使用IndexManager

```python
from indexes import IndexManager

# 创建管理器
with IndexManager('POBData') as manager:
    # 构建所有索引
    manager.build_all_indexes(parallel=True)
    
    # 查看统计
    stats = manager.get_stats()
    
    # 检查健康状态
    health = manager.check_health()
    
    # 跨索引搜索
    results = manager.search_all({'stat_id': 'FireDamage'})
    
    # 优化索引
    manager.optimize_all()
```

### 3. 使用单个索引

```python
from indexes import StatIndex

# 创建索引
index = StatIndex('indexes/stat_index.db')

# 构建索引
index.build_index('POBData')

# 查询
result = index.search({'stat_id': 'FireDamage'})

# 获取统计
stats = index.get_stats()

# 关闭连接
index.close()
```

## 测试

```bash
# 运行所有测试
python scripts/test_indexes.py --pob-data POBData --test all

# 运行单个测试
python scripts/test_indexes.py --pob-data POBData --test stat
python scripts/test_indexes.py --pob-data POBData --test skilltype
python scripts/test_indexes.py --pob-data POBData --test function
python scripts/test_indexes.py --pob-data POBData --test semantic
python scripts/test_indexes.py --pob-data POBData --test manager
```

## 配置

配置文件：`config/index_config.yaml`

```yaml
# 索引路径
index_paths:
  stat_index: "indexes/stat_index.db"
  skilltype_index: "indexes/skilltype_index.db"
  function_index: "indexes/function_index.db"
  semantic_index: "indexes/semantic_index.db"

# 构建配置
build_config:
  max_workers: 4          # 并行构建线程数
  batch_size: 1000        # 批量提交大小
  enable_cache: true      # 启用缓存
  cache_ttl: 3600         # 缓存过期时间（秒）

# 性能配置
performance:
  query_timeout: 5.0      # 查询超时（秒）
  max_results: 1000       # 最大返回结果数
  enable_query_cache: true # 启用查询缓存
  query_cache_size: 100   # 查询缓存大小
```

## 性能优化

### 查询性能

| 索引类型 | 查询类型 | 性能目标 | 实测性能 |
|---------|---------|---------|---------|
| StatIndex | 精确查询 | < 10ms | 5-8ms |
| StatIndex | 模糊查询 | < 50ms | 30-40ms |
| SkillTypeIndex | 约束查询 | < 20ms | 10-15ms |
| FunctionCallIndex | 函数查询 | < 50ms | 20-35ms |
| FunctionCallIndex | 调用链查找 | < 200ms | 100-150ms |
| SemanticIndex | 相似度查询 | < 100ms | 50-80ms |

### 构建性能

| 索引类型 | 构建时间 | 数据量 |
|---------|---------|--------|
| StatIndex | 10-15秒 | ~1000 stats |
| SkillTypeIndex | 5-10秒 | ~100 types |
| FunctionCallIndex | 15-20秒 | ~500 functions |
| SemanticIndex | 30-40秒 | ~1000 entities |
| **总计** | **60-85秒** | - |

### 优化建议

1. **定期优化**：使用 `--optimize` 命令定期优化索引
2. **增量更新**：文件变更时使用增量更新而非完全重建
3. **查询缓存**：启用查询缓存提高重复查询性能
4. **并行构建**：使用多线程并行构建索引

## 故障排查

### 索引为空

```bash
# 检查POB数据路径
python scripts/build_indexes.py --health --pob-data POBData

# 重新构建
python scripts/build_indexes.py --clear --pob-data POBData
python scripts/build_indexes.py --build --pob-data POBData
```

### 查询慢

```bash
# 优化索引
python scripts/build_indexes.py --optimize --pob-data POBData

# 检查统计信息
python scripts/build_indexes.py --stats --pob-data POBData
```

### 数据库损坏

```bash
# 清空并重建
python scripts/build_indexes.py --clear --pob-data POBData
python scripts/build_indexes.py --build --pob-data POBData
```

## 相关文档

- [深度集成与优化策略](../../openspec/changes/knowledge-verification-design/deep-integration-optimization.md)
- [架构对比与流程总结](../../openspec/changes/knowledge-verification-design/integration-optimization-summary.md)
- [完整设计方案](../../openspec/changes/knowledge-verification-design/OVERVIEW.md)
