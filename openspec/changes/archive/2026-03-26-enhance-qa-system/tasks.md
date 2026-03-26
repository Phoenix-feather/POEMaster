## 1. 数据层修复（Phase 1）

- [x] 1.1 统一 `entity_index.py` 的 `_row_to_dict` 方法，解析所有 20 个 JSON 字段（与 `kb_query.py` 的 `get_entity` 保持一致）
- [x] 1.2 移除 `formula_matcher.py` 中 stat_mappings modifier_code 的 200 字符截断
- [x] 1.3 在 `kb_query.py` 中实现按实体类型裁剪返回字段（定义 5 种类型的字段集映射：skill_definition/gem_definition/unique_item/passive_node/mod_affix）
- [x] 1.4 更新 `schemas/schemas.json` 反映 entities 表的字段变更，触发 schema 管理通知

## 2. StatDescriber 适配层（Phase 2 前置）

- [x] 2.1 创建 `scripts/stat_describer_bridge.py`：初始化 lupa LuaRuntime，注入 LoadModule/copyTable/round/floor/ConPrintf 等适配函数
- [x] 2.2 实现 LoadModule 模拟：`loadfile(pob_root..path..".lua")(...)`，工作目录指向 POBData/
- [x] 2.3 从 `POBData/Modules/Common.lua` 提取 copyTable/round/floor 的 Lua 代码并注入 runtime
- [x] 2.4 加载 StatDescriber.lua 并验证基本调用（用 Arc 的 stats 测试 describe_stats 函数）
- [x] 2.5 实现批量处理优化：预加载公共 scope（stat_descriptions/skill_stat_descriptions），避免重复加载大文件
- [x] 2.6 实现优雅降级：lupa 不可用或加载失败时返回 null + 警告日志

## 3. 实体解读层预计算（Phase 2a）

- [x] 3.1 在 `entity_index.py` 中新增 `summary`、`key_mechanics`、`display_stats` 三个 TEXT 字段到 entities 表 DDL
- [x] 3.2 实现 summary 提取逻辑：检测技能专属 statMap 覆盖（前缀匹配技能名的 stat）→ 提炼核心机制描述；无独特性则置 null
- [x] 3.3 实现 key_mechanics 提取逻辑：从 statMap 专属覆盖提取结构化机制列表（name/stat/formula/effect JSON 数组）
- [x] 3.4 集成 stat_describer_bridge：在实体入库时调用 describe_stats 生成 display_stats
- [x] 3.5 在 `init_knowledge_base.py` 的 Step 2 中集成 summary/key_mechanics/display_stats 的预计算流程
- [x] 3.6 更新 schemas.json 新增 summary/key_mechanics/display_stats schema 定义

## 4. 机制库增强（Phase 2b）

- [x] 4.1 在 `mechanism_extractor.py` 的 mechanisms 表中新增 5 个字段：friendly_name/behavior_description/mechanism_category/formula_abstract/affected_stats
- [x] 4.2 扩展 known_mechanisms 字典覆盖全部 44 个机制的中文名
- [x] 4.3 实现 Flag 型机制行为描述提取：扫描 CalcOffence/CalcDefence 中的 Flag 检查点
- [x] 4.4 实现数值型机制行为描述提取：扫描 Sum/Mod 使用点，提取完整公式
- [x] 4.5 实现触发型机制行为描述提取：解析 CalcTriggers.configTable 中每个触发器的配置
- [x] 4.6 创建 `config/mechanism_descriptions.yaml` 补充无法自动提取的机制描述
- [x] 4.7 新增 `mechanism_relations` 表（DDL + 数据填充逻辑），存储互斥/依赖/修改/覆盖/转换/叠加关系
- [x] 4.8 更新 schemas.json 反映 mechanisms 表的字段变更和 mechanism_relations 新表

## 5. 辅助匹配系统（Phase 2d）

- [x] 5.1 创建 `scripts/support_matcher.py`：SupportMatcher 类，负责辅助匹配预计算
- [x] 5.2 实现 support_compatibility 表：扫描所有 support=1 的实体，与主动技能做 skill_types 标签匹配
- [x] 5.3 实现 support_effects 表：分析辅助的 statMap/levels，归类 effect_category + quantifiable + key_stats + formula_impact
- [x] 5.4 实现 support_potential 表：识别不可量化但机制适配的辅助-技能组合，生成 potential_reason 和 synergy_type
- [x] 5.5 实现 level_scaling 提取：从辅助的 levels 数据中提取 1/10/20 级的关键 stat 数值
- [x] 5.6 在 `init_knowledge_base.py` 新增 Step 5 调用 SupportMatcher
- [x] 5.7 在 schemas.json 中注册 supports.db 的 3 个表 schema

## 6. 查询输出层（Phase 3）

- [x] 6.1 在 `kb_query.py` 中扩展 entity 子命令：新增 `--detail` 参数（summary/levels/stats/full），实现 4 种详情级别的返回逻辑
- [x] 6.2 在 `kb_query.py` 中扩展 mechanism 子命令：新增 `--detail` 参数（behavior/relations/full），集成 mechanism_relations 查询
- [x] 6.3 在 `kb_query.py` 中新增 `supports` 子命令：实现 `--mode` 参数（all/dps/utility/potential），查询 supports.db
- [x] 6.4 在 `kb_query.py` 中新增 `compare` 子命令：并排对比两个同类型实体
- [x] 6.5 在 `kb_query.py` 中新增 `reverse-stat` 子命令：反查 stat_mappings + entities 中影响指定 stat 的来源
- [x] 6.6 在 `kb_query.py` 中新增 `formula --chain` 选项：展示公式引用链路
- [x] 6.7 所有查询返回结果附加 `response_type` 字段

## 7. skill.md 重写（Phase 3b）

- [x] 7.1 更新能力边界声明：从"静态数据查询"改为"数据分析汇总服务"
- [x] 7.2 编写 8 种问题类型的识别规则（关键词 + 场景示例）
- [x] 7.3 编写每种类型的调用策略（使用哪些子命令 + 参数组合）
- [x] 7.4 编写每种 response_type 的输出格式模板（含 few-shot 示例）
- [x] 7.5 更新 CLI 用法文档（新增的子命令和参数）

## 8. 完整性校验与收尾

- [x] 8.1 在 `init_knowledge_base.py` 新增 Step 7 完整性校验：检查 summary 覆盖率、behavior_description 覆盖率、support_compatibility 完整性
- [x] 8.2 运行完整初始化流程，验证所有新增字段和表的数据质量
- [x] 8.3 用 Arc/Spark/CWDT 等典型场景做端到端测试（8 种问题类型各测一个）
- [x] 8.4 清理临时文件（temp_gap_formulas.py、temp_query_test.py）
- [x] 8.5 更新 version.yaml 版本号为 3.0.0
