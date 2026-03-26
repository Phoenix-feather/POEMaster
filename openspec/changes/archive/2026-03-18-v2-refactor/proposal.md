## Why

当前 POEMaster 定位为"游戏逻辑探索工具"，核心功能是通过关联图发现机制绕过和隐含关系。但实践证明：

1. **POB 模拟数据无法还原游戏逻辑**：大量"绕过机制"假设无法验证
2. **312条 bypass 记录全部为 new_discovery 状态**：无一条验证通过
3. **推理系统消耗大量资源**：关联图（4,395行）+ 规则系统（855行）+ 验证系统（2,310行）
4. **用户期望错位**：用户以为是游戏机制分析工具，实际只能提供静态数据

这些问题导致系统复杂度高、维护成本大、实际价值低。

## What Changes

### 系统定位转变

- **旧定位**：游戏逻辑探索工具 → 发现机制绕过、隐含关系
- **新定位**：POB 数据问答服务 → 提供静态数据查询和公式查询

### 删除的系统（约 10,000 行代码）

1. **关联图系统**
   - `graph.db` 数据库
   - `attribute_graph.py`（4,395 行）
   - `predefined_edges.yaml`（312 条未验证 bypass）

2. **规则系统**
   - `rules.db` 数据库
   - `rules_extractor.py`（855 行）

3. **验证系统**
   - `scripts/verification/` 目录（5 个文件，2,310 行）
   - `verification_cli.py`、测试文件等

4. **启发推理系统**
   - `heuristic_query.py`
   - `heuristic_discovery.py`
   - `heuristic_diffuse.py`
   - `heuristic_reason.py`

5. **约束系统**
   - `constraint_identifier.py`
   - `tag_source_finder.py`

6. **查询引擎**
   - `query_router.py`
   - `query_engine.py`

7. **文档和配置**
   - `docs/` 目录（17 个文件）
   - `edge_semantics.yaml`、`rule_templates.yaml`

### 保留的系统

1. **实体库**：`entities.db`（16,461 实体）
2. **公式库**：`formulas.db`（1,486 公式）
3. **机制库**：`mechanisms.db`（44 机制）
4. **索引系统**：StatIndex、SkillTypeIndex、FunctionIndex、SemanticIndex
5. **Schema 管理**：保证数据结构一致性

### 修改的文件

1. **init_knowledge_base.py**：从 7 步简化为 4 步
2. **kb_query.py**：删除规则和图查询，保留实体和公式查询
3. **SKILL.md**：重写为"数据问答服务"定位
4. **schemas.json**：清理 graph 和 rules 相关定义

## Capabilities

### Removed Capabilities

- `mechanism-bypass-discovery`：机制绕过发现
- `implicit-relation-inference`：隐含关系推理
- `verification-system`：假设验证系统
- `constraint-analysis`：约束分析

### Preserved Capabilities

- `entity-query`：实体属性查询
- `formula-query`：公式定义查询
- `stat-mapping`：Stat 映射查询
- `data-extraction`：POB 数据提取

## Impact

### 节省资源

- 代码行数：删除约 10,000 行
- 文件大小：节省约 13.5MB
- 维护成本：大幅降低

### 功能边界

**能做什么**：
- 实体属性查询："这个技能的属性是什么？"
- 公式查询："这个 stat 的计算公式是什么？"
- 技能过滤："有哪些 Meta 技能？"

**不能做什么**：
- 机制绕过推理："这个技能能否绕过触发限制？"
- 隐含关系发现："A 技能和 B 技能有什么隐含关系？"
- 组合效果预测："这个组合会有什么效果？"

### 用户影响

- 用户需要调整期望：从"探索工具"到"参考手册"
- 查询接口更简单直接
- 文档更清晰明确
