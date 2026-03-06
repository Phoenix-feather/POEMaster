# 功能阶段分类文档

## 初始化阶段 (init_knowledge_base.py)

这些功能在 `init_knowledge_base.py` 中**需要调用**：

### 数据构建类
| 模块 | 类/函数 | 用途 |
|------|---------|------|
| data_scanner.py | POBDataScanner | 扫描 POB 数据文件 |
| entity_index.py | EntityIndex | 构建实体索引 |
| rules_extractor.py | RulesExtractor.extract_layerX_xxx() | 提取规则 (Layer 1/2/3) |
| attribute_graph.py | AttributeGraph.build_from_xxx() | 构建关联图 |
| mechanism_extractor.py | MechanismExtractor | 提取机制 |

### 数据导入类
| 模块 | 函数 | 用途 |
|------|------|------|
| init_knowledge_base.py | import_heuristic_records() | 导入启发记录 |

---

## 运行时阶段 (查询/交互)

这些功能在 `init_knowledge_base.py` 中**不需要调用**：

### 查询接口类
| 模块 | 类/函数 | 用途 | 原因 |
|------|---------|------|------|
| query_engine.py | QueryEngine | 问答引擎 | 运行时交互 |
| query_engine.py | QuestionAnalyzer | 问题分析 | 运行时交互 |
| kb_query.py | KnowledgeBaseQuery | 查询工具 | 运行时查询 |
| entity_index.py | get_entity_by_id() | 实体查询 | 运行时查询 |
| rules_extractor.py | get_rules_by_category() | 规则查询 | 运行时查询 |
| attribute_graph.py | find_path() | 路径查找 | 运行时查询 |
| attribute_graph.py | find_bypass_paths() | 绕过查找 | 运行时查询 |
| attribute_graph.py | get_neighbors() | 邻居查询 | 运行时查询 |

### 交互学习类
| 模块 | 类 | 用途 | 原因 |
|------|------|------|------|
| knowledge_manager.py | IncrementalLearning | 增量学习 | 运行时交互 |
| knowledge_manager.py | RecoveryMechanism | 错误恢复 | 运行时维护 |

---

## 判断标准

### 需要在初始化阶段调用的特征：
1. **构建数据**：创建数据库、表、索引
2. **导入数据**：从文件读取并写入数据库
3. **提取数据**：解析源文件生成结构化数据
4. **构建关系**：创建节点、边、关联

### 不需要在初始化阶段调用的特征：
1. **查询数据**：get_*, search_*, find_*
2. **交互操作**：需要用户输入或确认
3. **运行时分析**：问题分析、意图识别
4. **维护操作**：恢复、同步、校验

---

## 误判案例

| 案例 | 错误判断 | 正确判断 |
|------|----------|----------|
| QueryEngine | "未实现" | 已实现，运行时使用 |
| IncrementalLearning | "未使用" | 运行时交互使用 |
| get_neighbors() | "未充分使用" | 运行时查询接口 |
