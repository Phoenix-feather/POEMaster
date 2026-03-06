## ADDED Requirements

### Requirement: 完整的SKILL.md
技能必须包含完整的使用说明、数据结构说明、配置说明。

#### Scenario: 使用说明
- **WHEN** 用户阅读SKILL.md
- **THEN** 用户能够了解技能的功能和使用方式

#### Scenario: 数据结构说明
- **WHEN** 用户阅读SKILL.md
- **THEN** 用户能够了解知识库的数据结构

### Requirement: 功能脚本实现
技能必须提供实现核心功能的脚本。

#### Scenario: 数据扫描脚本
- **WHEN** 运行数据扫描脚本
- **THEN** 脚本扫描POB数据并提取实体

#### Scenario: 查询脚本
- **WHEN** 运行查询脚本
- **THEN** 脚本接受问题并返回答案

## MODIFIED Requirements

### Requirement: 技能目录结构
技能目录结构必须扩展以支持新的数据文件。

**原有内容**: 基础的scripts/和references/目录
**修改后内容**:
```
poe-data-miner/
├── SKILL.md
├── scripts/
│   ├── data_scanner.py
│   ├── entity_index.py
│   ├── rules_extractor.py
│   ├── graph_builder.py
│   └── query_engine.py
├── config/
│   ├── predefined_edges.yaml
│   ├── rule_templates.yaml
│   └── extraction_patterns.yaml
├── knowledge_base/
│   ├── data.db
│   ├── heuristic_records.yaml
│   ├── pending_confirmations.yaml
│   ├── unverified_list.yaml
│   ├── learning_log.yaml
│   └── version.yaml
└── references/
    ├── mechanics.md
    └── data_structures.md
```

#### Scenario: 目录结构验证
- **WHEN** 技能初始化
- **THEN** 系统检查所有必要目录和文件是否存在
