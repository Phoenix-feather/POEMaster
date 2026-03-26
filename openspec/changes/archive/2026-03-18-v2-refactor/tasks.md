## Task List

### Phase 1: 备份和安全检查

- [ ] **T1.1**: 备份 `knowledge_base/` 目录到 `knowledge_base_backup/`
- [ ] **T1.2**: 备份 `schemas/schemas.json` 到 `schemas/schemas.json.backup`
- [ ] **T1.3**: 运行 `python scripts/init_knowledge_base.py` 确认当前流程正常
- [ ] **T1.4**: 运行 `python scripts/kb_query.py stats` 记录当前数据统计

### Phase 2: 删除数据库文件

- [ ] **T2.1**: 删除 `knowledge_base/graph.db`
- [ ] **T2.2**: 删除 `knowledge_base/rules.db`
- [ ] **T2.3**: 验证剩余数据库：entities.db、formulas.db、mechanisms.db 存在

### Phase 3: 删除配置文件

- [ ] **T3.1**: 删除 `config/predefined_edges.yaml`
- [ ] **T3.2**: 删除 `config/edge_semantics.yaml`
- [ ] **T3.3**: 删除 `config/rule_templates.yaml`
- [ ] **T3.4**: 删除 `config/mechanisms/` 目录（如果非空）
- [ ] **T3.5**: 验证保留的配置：extraction_patterns.yaml、universal_formulas.yaml、index_config.yaml

### Phase 4: 删除关联图系统

- [ ] **T4.1**: 删除 `scripts/attribute_graph.py`（4,395 行）
- [ ] **T4.2**: 搜索并清理所有 `import attribute_graph` 的引用

### Phase 5: 删除规则系统

- [ ] **T5.1**: 删除 `scripts/rules_extractor.py`（855 行）
- [ ] **T5.2**: 搜索并清理所有 `import rules_extractor` 的引用

### Phase 6: 删除验证系统

- [ ] **T6.1**: 删除 `scripts/verification/` 目录（5 个文件）
- [ ] **T6.2**: 删除 `scripts/verification_cli.py`
- [ ] **T6.3**: 删除 `scripts/test_verification.py`
- [ ] **T6.4**: 删除 `scripts/test_verification_extended.py`
- [ ] **T6.5**: 搜索并清理所有 `from verification` 的引用

### Phase 7: 删除启发推理系统

- [ ] **T7.1**: 删除 `scripts/heuristic_query.py`
- [ ] **T7.2**: 删除 `scripts/heuristic_discovery.py`
- [ ] **T7.3**: 删除 `scripts/heuristic_diffuse.py`
- [ ] **T7.4**: 删除 `scripts/heuristic_reason.py`
- [ ] **T7.5**: 搜索并清理所有 `import heuristic_` 的引用

### Phase 8: 删除约束系统

- [ ] **T8.1**: 删除 `scripts/constraint_identifier.py`
- [ ] **T8.2**: 删除 `scripts/tag_source_finder.py`
- [ ] **T8.3**: 搜索并清理所有相关引用

### Phase 9: 删除查询引擎

- [ ] **T9.1**: 删除 `scripts/query_router.py`
- [ ] **T9.2**: 删除 `scripts/query_engine.py`
- [ ] **T9.3**: 删除 `scripts/knowledge_manager.py`
- [ ] **T9.4**: 搜索并清理所有相关引用

### Phase 10: 删除临时分析脚本

- [ ] **T10.1**: 删除 `scripts/analyze_databases.py`
- [ ] **T10.2**: 删除 `scripts/analyze_mechanics.py`
- [ ] **T10.3**: 删除 `scripts/check_mod_def.py`
- [ ] **T10.4**: 删除 `scripts/check_rebuild.py`
- [ ] **T10.5**: 删除 `scripts/check_tasks.py`
- [ ] **T10.6**: 删除 `scripts/check_unique_sources.py`
- [ ] **T10.7**: 删除 `scripts/check_workflow.py`
- [ ] **T10.8**: 删除 `scripts/compare_data.py`
- [ ] **T10.9**: 删除 `scripts/complete_db_analysis.py`
- [ ] **T10.10**: 删除 `scripts/simple_db_analysis.py`
- [ ] **T10.11**: 删除 `scripts/verify_ascendancy.py`
- [ ] **T10.12**: 删除 `scripts/verify_db.py`
- [ ] **T10.13**: 删除 `scripts/verify_unique_fix.py`
- [ ] **T10.14**: 删除 `scripts/generate_coverage_report.py`
- [ ] **T10.15**: 删除 `scripts/parse_json_data.py`

### Phase 11: 删除文档目录

- [ ] **T11.1**: 删除整个 `docs/` 目录（17 个文件）
- [ ] **T11.2**: 删除 `exploration/` 目录
- [ ] **T11.3**: 删除根目录下的临时报告文件：
  - `analysis_report_final.txt`
  - `analysis_report.txt`
  - `entity_fields_report_final.txt`
  - `entity_fields_report.txt`
  - `mechanisms_rules_report.txt`

### Phase 12: 修改 init_knowledge_base.py

- [ ] **T12.1**: 读取当前 `init_knowledge_base.py` 内容
- [ ] **T12.2**: 删除 Step 4（规则提取）相关代码
- [ ] **T12.3**: 删除 Step 5（关联图构建）相关代码
- [ ] **T12.4**: 删除 `from rules_extractor import RulesExtractor`
- [ ] **T12.5**: 删除 `from attribute_graph import GraphBuilder`
- [ ] **T12.6**: 更新 `main()` 函数，移除步骤 4 和 5 的调用
- [ ] **T12.7**: 更新文档字符串，说明新的 4 步流程

### Phase 13: 修改 kb_query.py

- [ ] **T13.1**: 读取当前 `kb_query.py` 内容
- [ ] **T13.2**: 删除 `get_rule()` 方法
- [ ] **T13.3**: 删除 `get_graph_neighbors()` 方法
- [ ] **T13.4**: 删除 `find_bypass_path()` 方法
- [ ] **T13.5**: 删除 `check_constraints()` 方法（如果存在）
- [ ] **T13.6**: 删除 `__init__` 中的 `self.rules_db` 和 `self.graph_db`
- [ ] **T13.7**: 更新 `stats` 命令，移除 rules 和 graph 统计

### Phase 14: 重写 SKILL.md

- [ ] **T14.1**: 读取当前 `SKILL.md` 内容
- [ ] **T14.2**: 删除"强制规则 2：验证流程"章节
- [ ] **T14.3**: 删除"强制规则 4：知识状态管理"章节
- [ ] **T14.4**: 删除"增量学习"章节
- [ ] **T14.5**: 简化"Schema 管理系统"章节
- [ ] **T14.6**: 删除所有绕过机制示例
- [ ] **T14.7**: 删除关联图查询章节
- [ ] **T14.8**: 更新系统定位为"POB 数据问答服务"
- [ ] **T14.9**: 添加"能力边界"章节，明确说明能做什么、不能做什么
- [ ] **T14.10**: 更新架构图

### Phase 15: 清理 schemas.json

- [ ] **T15.1**: 读取当前 `schemas.json` 内容
- [ ] **T15.2**: 删除 `rules` 表定义
- [ ] **T15.3**: 删除 `graph_nodes` 表定义
- [ ] **T15.4**: 删除 `graph_edges` 表定义
- [ ] **T15.5**: 删除 `constraints` 表定义（如果存在）
- [ ] **T15.6**: 删除 `verification_history` 表定义（如果存在）
- [ ] **T15.7**: 更新相关文件的依赖关系定义

### Phase 16: 修改 QUERY_STRATEGY.md

- [ ] **T16.1**: 读取当前 `QUERY_STRATEGY.md` 内容
- [ ] **T16.2**: 删除"三问法"中的绕过检测
- [ ] **T16.3**: 删除关联图查询方法
- [ ] **T16.4**: 删除混合查询策略
- [ ] **T16.5**: 删除验证流程
- [ ] **T16.6**: 简化为实体查询和公式查询两种方法

### Phase 17: 清理 import 和依赖

- [ ] **T17.1**: 搜索所有 `.py` 文件中的 `import rules_extractor`
- [ ] **T17.2**: 搜索所有 `.py` 文件中的 `import attribute_graph`
- [ ] **T17.3**: 搜索所有 `.py` 文件中的 `from verification`
- [ ] **T17.4**: 搜索所有 `.py` 文件中的 `import heuristic_`
- [ ] **T17.5**: 清理所有找到的 import 语句
- [ ] **T17.6**: 检查 `scripts/indexes/` 目录是否有依赖问题

### Phase 18: 测试和验证

- [ ] **T18.1**: 运行 `python scripts/init_knowledge_base.py`，确认 4 步流程成功
- [ ] **T18.2**: 运行 `python scripts/kb_query.py stats`，验证数据统计正确
- [ ] **T18.3**: 运行 `python scripts/kb_query.py entity ArcPlayer`，测试实体查询
- [ ] **T18.4**: 运行 `python scripts/kb_query.py formula --search energy`，测试公式查询
- [ ] **T18.5**: 检查所有保留的测试脚本是否正常运行
- [ ] **T18.6**: 运行 Schema 验证，确认无循环依赖

### Phase 19: 文档更新

- [ ] **T19.1**: 更新 `CODEBUDDY.md`，说明新的项目定位
- [ ] **T19.2**: 创建 `docs/` 目录（重新建立）
- [ ] **T19.3**: 创建 `docs/getting-started.md`，说明如何使用新的查询服务
- [ ] **T19.4**: 创建 `docs/data-sources.md`，说明数据来源和提取方法
- [ ] **T19.5**: 创建 `docs/query-examples.md`，提供查询示例

### Phase 20: 最终清理

- [ ] **T20.1**: 删除备份目录 `knowledge_base_backup/`（确认一切正常后）
- [ ] **T20.2**: 删除 `schemas/schemas.json.backup`（确认一切正常后）
- [ ] **T20.3**: 运行最终的统计报告
- [ ] **T20.4**: 创建变更完成报告

## Estimated Effort

- **Phase 1-11**: 删除文件（约 1 小时）
- **Phase 12-17**: 修改代码（约 2 小时）
- **Phase 18**: 测试验证（约 1 小时）
- **Phase 19-20**: 文档更新（约 1 小时）

**总计**: 约 5 小时

## Dependencies

- Phase 2-11 可以并行执行（都是删除操作）
- Phase 12-17 必须等删除完成后再执行（修改代码）
- Phase 18 必须在所有代码修改后执行
- Phase 19-20 可以在验证通过后执行

## Rollback Plan

如果出现问题，可以：

1. 恢复 `knowledge_base_backup/` 目录
2. 恢复 `schemas/schemas.json.backup`
3. 使用 git 回退到变更前的提交
