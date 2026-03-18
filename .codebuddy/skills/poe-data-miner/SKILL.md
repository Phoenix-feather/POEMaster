---
name: poe-data-miner
description: POB数据问答服务 - 提供Path of Exile游戏数据的查询和分析能力。支持实体查询、公式查询、机制查询。
---

# POE Data Miner v2

**POB数据问答服务**

从POB（Path of Building）数据文件中提取和分析Path of Exile游戏数据，提供快速的数据查询服务。

---

## ⚠️ 重要说明：能力边界

### ✅ 能做什么

- **实体查询**：查询技能、宝石、物品、天赋节点的属性和定义
- **公式查询**：查询stat的计算公式和映射关系
- **机制查询**：查询游戏机制（如触发机制、能量机制）的定义和来源
- **数据统计**：获取知识库的数据统计信息

### ❌ 不能做什么

- **机制绕过推理**：无法推断某个技能是否能绕过游戏限制
- **隐含关系发现**：无法发现实体之间的隐含关系或组合效果
- **组合效果预测**：无法预测多个技能/物品组合后的效果
- **游戏逻辑验证**：无法验证某个机制在游戏中是否真实有效

**核心原则**：提供静态数据查询，不提供逻辑推理。

---

## 快速开始

### 查询知识库统计信息

```bash
python scripts/kb_query.py stats
```

### 实体查询

```bash
# 查询所有Meta技能
python scripts/kb_query.py entity --meta

# 搜索包含"Cast"的实体
python scripts/kb_query.py entity --search "Cast"

# 按类型查询
python scripts/kb_query.py entity --type skill_definition

# 查询特定实体详情
python scripts/kb_query.py entity ArcPlayer
```

### 公式查询

```bash
# 查询公式统计
python scripts/kb_query.py formula --stats

# 按问题查询公式
python scripts/kb_query.py formula --query "护甲减伤公式"

# 按实体查询公式
python scripts/kb_query.py formula --entity ArcPlayer

# 按stat名称查询映射
python scripts/kb_query.py formula --stat "energy_generated_+%"
```

### 机制查询

```bash
# 列出所有机制
python scripts/kb_query.py mechanism --all

# 搜索机制
python scripts/kb_query.py mechanism --search "trigger"

# 查询特定机制详情
python scripts/kb_query.py mechanism InstantLifeLeech
```

---

## 初始化知识库

### 完整初始化（4步流程）

```bash
python scripts/init_knowledge_base.py <pob_data_dir>
```

初始化流程：
1. **实体索引初始化** - 扫描POB数据文件，提取实体定义
2. **公式索引初始化** - 提取计算公式和stat映射
3. **机制提取** - 从ModCache.lua提取游戏机制
4. **版本信息更新** - 记录知识库版本

### 数据源

POB数据文件位于以下目录：

```
POBData/
├── Data/
│   ├── Skills/           # 技能定义
│   │   ├── act_*.lua    # 主动技能
│   │   └── sup_*.lua    # 辅助技能
│   ├── Uniques/         # 唯一物品
│   ├── Bases/           # 物品基础
│   ├── Gems.lua         # 宝石定义
│   ├── ModCache.lua     # Mod缓存
│   ├── SkillStatMap.lua # Stat映射
│   └── StatDescriptions/ # Stat描述
├── Modules/             # 计算模块
│   ├── CalcTriggers.lua # 触发计算
│   ├── CalcActiveSkill.lua # 主动技能计算
│   └── ...
└── TreeData/{version}/  # 天赋树数据
```

---

## 核心模块

### 1. 数据扫描器 (`data_scanner.py`)

扫描和缓存POB数据文件：
- Lua文件遍历和内容读取
- 数据类型识别（技能、物品、天赋等）
- 版本信息提取
- 扫描结果缓存

### 2. 实体索引 (`entity_index.py`)

SQLite-based实体存储：
- 实体数据提取和存储
- 按ID、类型、技能类型查询
- 全文搜索（名称、描述）

### 3. 公式索引 (`formula_index.py`)

三级公式索引系统：
- **通用公式**：适用于所有实体的通用计算公式
- **Stat映射**：技能特定的stat到modifier映射
- **缺口公式**：Meta技能的能量生成公式

### 4. 机制提取器 (`mechanism_extractor.py`)

从ModCache.lua提取游戏机制：
- 机制识别（基于stat ID）
- 来源追踪
- 实体关联

### 5. 索引系统 (`indexes/`)

四级索引加速查询：
- **StatIndex**：Stat名称快速查找
- **SkillTypeIndex**：技能类型过滤
- **FunctionIndex**：函数调用关系
- **SemanticIndex**：语义相似度

---

## 查询接口

### `kb_query.py` - 统一查询工具

#### 实体查询

```python
from kb_query import KnowledgeBaseQuery

kb = KnowledgeBaseQuery()

# 获取单个实体
entity = kb.get_entity('ArcPlayer')
print(entity['name'], entity['skill_types'])

# 搜索实体
results = kb.search_entities('Cast')
for r in results:
    print(r['id'], r['name'])

# 按类型获取
skills = kb.get_entities_by_type('skill_definition')

# 按技能类型获取
meta_skills = kb.get_entities_by_skill_type('Meta')
```

#### 公式查询

```python
# 按问题查询
result = kb.query_formula("Arc的DPS怎么算")
print(result['universal'])      # 通用公式
print(result['stat_mappings'])  # stat映射
print(result['gap_formulas'])   # 缺口公式

# 按实体查询
result = kb.query_formula("", entity_id="ArcPlayer")

# 按stat查询
mappings = kb.search_formulas_by_stat("energy_generated_+%")
```

#### 机制查询

```python
# 获取所有机制
mechanisms = kb.get_all_mechanisms()

# 搜索机制
results = kb.search_mechanisms('trigger')

# 获取机制详情
mech = kb.get_mechanism('InstantLifeLeech')
print(mech['sources'])
```

---

## 数据库结构

### entities.db - 实体库

```sql
CREATE TABLE entities (
    id TEXT PRIMARY KEY,
    name TEXT,
    type TEXT,
    skill_types TEXT,      -- JSON数组
    description TEXT,
    data_json TEXT,        -- 完整数据
    -- ... 其他字段
);
```

实体类型：
- `skill_definition` - 技能定义（1,248个）
- `gem_definition` - 宝石定义（900个）
- `stat_mapping` - Stat映射（5,230个）
- `passive_node` - 天赋节点（4,313个）
- `unique_item` - 唯一物品（474个）
- `item_base` - 物品基础（1,171个）
- `mod_affix` - Mod词缀（2,570个）
- `minion_definition` - 召唤物定义（496个）
- `calculation_module` - 计算模块（59个）

### formulas.db - 公式库

```sql
-- 通用公式
CREATE TABLE universal_formulas (
    id TEXT PRIMARY KEY,
    name TEXT,
    formula_text TEXT,
    domain TEXT,
    -- ...
);

-- Stat映射
CREATE TABLE stat_mappings (
    id TEXT PRIMARY KEY,
    name TEXT,
    formula_text TEXT,
    domain TEXT,
    -- ...
);

-- 缺口公式
CREATE TABLE gap_formulas (
    id TEXT PRIMARY KEY,
    entity_id TEXT,
    name TEXT,
    formula_text TEXT,
    -- ...
);
```

### mechanisms.db - 机制库

```sql
CREATE TABLE mechanisms (
    id TEXT PRIMARY KEY,
    name TEXT,
    stat_name TEXT,
    source_count INTEGER,
    -- ...
);

CREATE TABLE mechanism_sources (
    id INTEGER PRIMARY KEY,
    mechanism_id TEXT,
    source_type TEXT,
    source_id TEXT,
    -- ...
);
```

---

## 配置文件

### extraction_patterns.yaml

数据提取模式配置：
- Lua文件解析模式
- 字段提取规则
- 数据类型识别

### universal_formulas.yaml

通用公式定义：
- DPS计算公式
- 伤害转换公式
- 属性计算公式

### index_config.yaml

索引系统配置：
- 索引数据库路径
- 性能参数
- 缓存设置

---

## Schema管理系统

### 概述

Schema管理系统确保数据结构定义与其消费者之间的一致性。

### 核心文件

- `schemas/schemas.json` - 结构定义中心存储
- `scripts/schema_manager.py` - 核心管理函数
- `scripts/schema_validator.py` - 验证和队列处理

### 使用方法

```python
from schema_manager import SchemaManager

manager = SchemaManager('schemas/schemas.json')

# 查询文件角色
role = manager.get_file_role('entity_index.py')
# {'definitions': ['entities'], 'consumptions': []}

# 检查队列
if not manager.is_queue_empty():
    # 处理待处理项
    pass

# 保存变更
manager.save()
```

---

## 常见问题

### Q: 如何更新知识库到最新版本？

```bash
# 重新初始化
python scripts/init_knowledge_base.py <pob_data_dir>
```

### Q: 如何查询特定技能的详细属性？

```bash
python scripts/kb_query.py entity <skill_id>
```

### Q: 如何找到某个stat的计算公式？

```bash
python scripts/kb_query.py formula --stat <stat_name>
```

### Q: 知识库数据从哪里来？

所有数据都从POB（Path of Building）的源文件提取，包括：
- Lua数据文件（技能、物品、天赋定义）
- 计算模块（公式、逻辑）
- Stat映射和描述

### Q: 数据多久更新一次？

知识库不会自动更新，需要手动重新初始化以获取最新的POB数据。

---

## 项目统计

### 数据规模（2026-03-18）

| 组件 | 数量 |
|------|------|
| 实体总数 | 16,461 |
| 公式总数 | 1,486 |
| 机制总数 | 44 |

### 代码规模

| 类别 | 文件数 | 代码行数 |
|------|--------|----------|
| 核心脚本 | ~20 | ~6,000 |
| 索引系统 | 8 | ~1,500 |
| 测试脚本 | 5 | ~500 |

---

## 版本历史

### v2.0.0 (2026-03-18)

**重大重构：从"游戏逻辑探索"转为"数据问答服务"**

删除系统：
- 关联图系统（graph.db、attribute_graph.py）
- 规则系统（rules.db、rules_extractor.py）
- 验证系统（verification/目录）
- 启发推理系统（heuristic_*.py）
- 查询引擎（query_router.py、query_engine.py）

保留系统：
- 实体库（entities.db）
- 公式库（formulas.db）
- 机制库（mechanisms.db）
- 索引系统

优势：
- 清晰的能力边界
- 更简单的查询接口
- 更低的维护成本
- 更快的查询性能

### v1.0.0

初始版本，包含完整的推理和验证系统。

---

## 贡献指南

本项目用于Path of Exile游戏数据分析，欢迎贡献：
- 数据提取脚本改进
- 查询接口优化
- 文档完善
- Bug修复

---

## 许可证

本项目仅供学习和研究使用。
