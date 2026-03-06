## 1. 项目结构搭建

- [x] 1.1 创建config目录和配置文件模板
- [x] 1.2 创建knowledge_base目录结构
- [x] 1.3 创建scripts目录结构
- [x] 1.4 创建references目录和参考文档

## 2. 配置文件实现

- [x] 2.1 实现config/predefined_edges.yaml（预置边定义）
- [x] 2.2 实现config/rule_templates.yaml（规则模板定义）
- [x] 2.3 实现config/extraction_patterns.yaml（提取模式定义）

## 3. 数据扫描模块 (data-scanner)

- [x] 3.1 实现Lua文件遍历和内容读取
- [x] 3.2 实现数据类型识别（技能定义、属性映射、计算模块）
- [x] 3.3 实现版本信息提取
- [x] 3.4 实现扫描结果缓存

## 4. 实体索引模块 (entity-index)

- [x] 4.1 设计SQLite表结构（entities表）
- [x] 4.2 实现实体数据提取和存储
- [x] 4.3 实现实体查询接口（按ID、类型、skillTypes）
- [x] 4.4 创建必要的索引

## 5. 规则提取模块 (rules-library)

- [x] 5.1 设计SQLite表结构（rules表）
- [x] 5.2 实现Layer 1：从stats组合提取实体属性
- [x] 5.3 实现Layer 2：从SkillStatMap提取属性关系
- [x] 5.4 实现Layer 3：从计算代码提取条件规则和公式
- [x] 5.5 实现规则与实体的关联查询

## 6. 关联图模块 (attribute-graph)

- [x] 6.1 设计SQLite表结构（graph_nodes、graph_edges表）
- [x] 6.2 实现节点创建（实体、机制、属性、约束节点）
- [x] 6.3 实现自动边构建（has_type、has_stat、modifies等）
- [x] 6.4 实现规则边构建（causes、blocks、bypasses等）
- [x] 6.5 实现预置边加载
- [x] 6.6 实现图遍历查询（BFS/DFS、递归CTE）
- [x] 6.7 创建必要的索引

## 7. 问答引擎模块 (query-engine)

- [x] 7.1 实现问题分析器（意图识别、实体提取、约束提取）
- [x] 7.2 实现实体查询主导模式
- [x] 7.3 实现规则查询主导模式
- [x] 7.4 实现关联图发散检索模式
- [x] 7.5 实现known_paths缓存查询
- [x] 7.6 实现结果整合器

## 8. 增量学习模块 (incremental-learning)

- [x] 8.1 设计heuristic_records.yaml结构
- [x] 8.2 设计pending_confirmations.yaml结构
- [x] 8.3 实现探索发现记录
- [x] 8.4 实现用户确认机制（集成ask_followup_question）
- [x] 8.5 实现确认后知识持久化
- [x] 8.6 实现待确认列表管理

## 9. 恢复机制模块 (recovery-mechanism)

- [x] 9.1 设计version.yaml结构
- [x] 9.2 设计unverified_list.yaml结构
- [x] 9.3 实现版本检测逻辑
- [x] 9.4 实现静态数据重建流程
- [x] 9.5 实现用户知识迁移和验证
- [x] 9.6 实现未确认列表管理
- [x] 9.7 实现数值变化自动验证
- [x] 9.8 实现机制变化提醒

## 10. 技能文档完善 (poe-data-miner-skill)

- [x] 10.1 更新SKILL.md完整说明
- [x] 10.2 编写references/mechanics.md（机制参考）
- [x] 10.3 编写references/data_structures.md（数据结构参考）

## 11. 集成测试

- [x] 11.1 测试数据扫描和实体索引
- [x] 11.2 测试规则提取和规则库
- [x] 11.3 测试关联图构建和查询
- [x] 11.4 测试问答引擎各模式
- [x] 11.5 测试增量学习流程
- [x] 11.6 测试恢复机制
- [x] 11.7 端到端测试：绕过触发限制的问答流程
