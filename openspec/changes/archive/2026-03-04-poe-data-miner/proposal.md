## Why

POE2游戏数据分散在POB的Lua文件中，缺乏结构化的知识索引和智能问答能力。玩家需要深入理解游戏机制（如元技能能量生成、触发限制绕过等），但现有的数据格式难以直接回答复杂的机制问题。需要一个能够自动提取数据、建立知识关联、支持发散式检索的问答引擎。

## What Changes

- **新增**: POE数据矿工技能的完整实现
  - 数据扫描和索引系统（实体索引、规则库、关联图）
  - SQLite + YAML混合存储架构
  - 分层规则提取机制（SkillStatMap、stats组合、计算代码分析）
  - 智能问答引擎（链式索引 + 关联图发散检索）
  - 增量学习机制（用户确认、启发记录）
  - 版本更新恢复机制（启发记录重建、未确认列表）
  - 确认交互机制（ask_followup_question）

- **修改**: 现有poe-data-miner技能结构
  - 扩展SKILL.md为完整的技能说明
  - 更新脚本实现真实的数据提取和分析功能

## Capabilities

### New Capabilities

- `data-scanner`: 扫描POB所有Lua文件，识别数据类型，提取实体数据、映射数据、计算逻辑
- `entity-index`: SQLite实体索引，存储技能、物品、天赋等实体的完整属性
- `rules-library`: 规则库，从SkillStatMap、stats组合、计算代码三层提取规则
- `attribute-graph`: 属性关联图，存储机制节点和关系边，支持图遍历查询
- `query-engine`: 问答引擎，链式索引 + 关联图发散检索，三源联动（实体+规则+关联图）
- `incremental-learning`: 增量学习，探索发现→待确认→用户确认→存入知识库
- `recovery-mechanism`: 恢复机制，版本检测、启发记录重建、未确认列表管理
- `confirmation-interaction`: 确认交互，使用ask_followup_question进行用户确认

### Modified Capabilities

- `poe-data-miner-skill`: 扩展现有技能的SKILL.md和脚本实现

## Impact

- **新增文件**:
  - `knowledge_base/data.db` - SQLite数据库
  - `knowledge_base/heuristic_records.yaml` - 启发记录
  - `knowledge_base/pending_confirmations.yaml` - 待确认项
  - `knowledge_base/unverified_list.yaml` - 未确认列表
  - `knowledge_base/learning_log.yaml` - 学习日志
  - `knowledge_base/version.yaml` - 版本信息
  - `config/predefined_edges.yaml` - 预置边
  - `config/rule_templates.yaml` - 规则模板
  - `config/extraction_patterns.yaml` - 提取模式

- **修改文件**:
  - `SKILL.md` - 完整技能说明
  - `scripts/` - 实现真实功能

- **依赖**:
  - Python标准库: sqlite3, re, json, yaml
  - 无需第三方依赖
