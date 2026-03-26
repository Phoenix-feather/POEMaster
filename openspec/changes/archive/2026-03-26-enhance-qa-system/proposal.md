## Why

当前 POE Data Miner 的问答能力停留在"原始数据查询"层面，存在 5 个核心问题：

1. **数据不完整**：JSON 字段解析不一致（5/20），stat_mapping modifier 被截断 200 字符
2. **可读性差**：实体查询返回 53 列宽表（含大量 null），机制描述是模板化的 `"机制: {id}"`，缺少解读和总结
3. **输出格式单一**：所有查询一律 `json.dumps`，无法根据问题类型适配展示
4. **公式缺链路**：公式之间的引用关系没有表达，用户无法看到完整计算链
5. **机制问答薄弱**：44 个机制中只有 9 个有中文名（且未入库），行为描述为零，机制关系未建模

系统需要从"静态数据查询服务"升级为"数据分析汇总服务"，让用户用自然语言提问并得到结构化、有深度的回答。

## What Changes

### 数据层修复
- 统一所有 20 个 JSON 字段的解析逻辑
- 移除 stat_mapping modifier 的 200 字符截断限制
- 实体查询按类型裁剪返回字段（skill_definition/gem_definition/unique_item/passive_node/mod_affix 各有独立字段集），去除 null 噪音

### 解读层新建（预计算入库）
- entities 表新增 `summary`（独特性提炼）、`key_mechanics`（核心机制 JSON）、`display_stats`（人话 stat 描述）3 个预计算字段
- 使用 lupa 搭建 StatDescriber.lua 适配层（注入 LoadModule/copyTable/round/floor 等），直接运行 POB 原始代码生成精确的 stat 描述文本
- mechanisms 表增强：新增 `friendly_name`（中文名）、`behavior_description`（行为描述，从代码逆向提炼）、`mechanism_category`（分类）、`formula_abstract`（抽象公式）、`affected_stats`（影响的 stat 列表）
- 新增 `mechanism_relations` 表：表达机制间的互斥/依赖/修改/覆盖/转换/叠加关系

### 辅助匹配系统（新增 supports.db）
- `support_compatibility` 表：主动技能-辅助宝石兼容矩阵（基于 skill_types 匹配预计算）
- `support_effects` 表：辅助效果分类（damage_more/speed/chain/crit/utility 等）+ 可量化标记 + 关键 stat + 对 DPS 公式的影响位置
- `support_potential` 表：不可量化但机制适配的潜力推荐列表

### 输出层构建
- CLI 扩展：`entity --detail summary|levels|stats|full`、`mechanism --detail behavior|relations|full`、`supports <skill_id> --mode all|dps|utility|potential`、`compare <id1> <id2>`、`reverse-stat <stat_name>`、`formula --chain`
- 查询返回附加 `response_type` 字段，指示数据类型
- 公式查询新增链路展示（公式间引用关系）

### skill.md 重写
- 能力边界升级：从"静态数据查询"→"数据分析汇总服务"
- 新增 8 类问题类型的识别规则和调用策略（概览/数值分析/机制详解/辅助搭配/对比分析/Stat反查/公式查询/通用列表）
- 每种类型配套输出格式模板（含 few-shot 示例）

## Capabilities

### New Capabilities
- `entity-enrichment`: 实体数据的解读层增强——预计算 summary/key_mechanics/display_stats 字段，按类型裁剪返回，统一 JSON 解析
- `mechanism-enrichment`: 机制库全面增强——行为描述、中文名、分类、公式、机制关系表
- `support-matching`: 辅助宝石匹配系统——兼容矩阵预计算、效果分类量化、潜力推荐
- `query-output-layer`: 查询输出层——面向场景的 CLI 子命令、response_type 路由、格式化模板
- `stat-describer-bridge`: lupa StatDescriber 适配层——在 Python 中运行 POB 原始 Lua StatDescriber 代码生成精确 stat 描述

### Modified Capabilities
（无已有 spec 需要修改）

## Impact

### 数据库变更
- `entities.db`: entities 表新增 3 个字段（summary, key_mechanics, display_stats）
- `mechanisms.db`: mechanisms 表新增 5 个字段 + 新增 mechanism_relations 表
- `formulas.db`: 移除 modifier 截断 + 新增 formula_chains 表
- 新增 `supports.db`（3 个表）
- **触发 schema 管理系统更新**

### 代码变更
- `kb_query.py`: 扩展 CLI 子命令、按类型裁剪、response_type 附加
- `entity_index.py`: 统一 JSON 解析、新字段入库逻辑
- `mechanism_extractor.py`: 行为描述提取、关系建模
- `formula_matcher.py`: 移除截断、链路查询
- `lua_parser.py`: StatDescriber 适配层
- `init_knowledge_base.py`: 新增 Step 5（辅助匹配）+ Step 7（完整性校验）
- `skill.md`: 全面重写

### 新增文件
- `scripts/support_matcher.py`: 辅助匹配预计算引擎
- `scripts/stat_describer_bridge.py`: lupa StatDescriber 适配层
- `config/mechanism_descriptions.yaml`（可选）: 机制行为描述的人工补充

### 依赖
- `lupa>=2.0`: 已有依赖，需增强使用（搭建 StatDescriber 运行环境）
