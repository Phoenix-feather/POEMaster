## ADDED Requirements

### Requirement: Response type annotation
系统 SHALL 在每个查询结果中附加 `response_type` 字段，指示数据类型（entity_card/level_table/stat_detail/entity_full/mechanism_behavior/mechanism_relations/mechanism_full/support_list/support_dps/support_potential/formula_result/formula_chain/entity_list/comparison/reverse_stat）。

#### Scenario: Entity summary returns entity_card type
- **WHEN** `entity ArcPlayer --detail summary`
- **THEN** 返回 JSON SHALL 包含 `"response_type": "entity_card"`

### Requirement: Compare subcommand
系统 SHALL 支持 `compare <id1> <id2>` 子命令，并排对比两个同类型实体的属性差异。

#### Scenario: Skill comparison
- **WHEN** `compare ArcPlayer SparkPlayer`
- **THEN** 返回两者的类型差异、数值对比（damage/cast_time/skill_types）、机制差异，response_type="comparison"

#### Scenario: Cross-type comparison rejection
- **WHEN** 对比不同类型实体（如 skill_definition vs passive_node）
- **THEN** SHALL 返回错误提示，说明仅支持同类型对比

### Requirement: Reverse stat lookup
系统 SHALL 支持 `reverse-stat <stat_name>` 子命令，反查所有能影响该 stat 的来源（技能内置/装备词缀/天赋节点）。

#### Scenario: ChainCountMax reverse lookup
- **WHEN** `reverse-stat ChainCountMax`
- **THEN** 返回所有影响 ChainCountMax 的来源：技能内置 stat（number_of_chains）、stat_mappings 中的条目、ModParser 中匹配的词缀模式

### Requirement: Formula chain display
系统 SHALL 支持 `formula --chain <formula_id>` 子命令，展示公式之间的引用链路（树形结构）。

#### Scenario: DPS formula chain
- **WHEN** `formula --chain dps_core`
- **THEN** 返回 DPS 核心公式 → 引用的子公式（average_hit, speed_calc 等）→ 子公式的子公式，形成完整引用树

### Requirement: Modifier no truncation
系统 SHALL 在 stat_mappings 查询中返回完整的 modifier_code，不做任何截断。

#### Scenario: Long modifier code
- **WHEN** 查询一个 modifier_code 超过 200 字符的 stat_mapping
- **THEN** SHALL 返回完整的 modifier_code，不截断

### Requirement: skill.md problem type routing
skill.md SHALL 定义 8 种问题类型的识别规则和对应的调用策略：

| 类型 | 识别关键词示例 | 调用策略 |
|------|--------------|---------|
| A 概览 | "是什么""介绍" | entity --detail summary |
| B 数值 | "数值""伤害成长""等级" | entity --detail levels + formula --entity |
| C 机制 | "怎么工作""机制""触发" | mechanism --detail behavior |
| D 搭配 | "辅助""搭配""配什么" | supports --mode dps + supports --mode potential |
| E 对比 | "对比""和...比""哪个好" | compare |
| F 反查 | "什么能加""来源""怎么提高" | reverse-stat |
| G 公式 | "公式""怎么算""计算" | formula --query + formula --chain |
| H 列表 | "所有""列出""有哪些" | entity --search/--type/--skill-type |

#### Scenario: Natural language routing
- **WHEN** 用户问 "Arc的辅助宝石怎么选"
- **THEN** AI SHALL 识别为 Type D（搭配）并调用 `supports ArcPlayer --mode dps` 和 `supports ArcPlayer --mode potential`

#### Scenario: Multi-type question
- **WHEN** 用户问 "Arc的数值和伤害机制"
- **THEN** AI SHALL 识别为 Type B + Type C 的组合，依次调用相关子命令

### Requirement: skill.md output format templates
skill.md SHALL 为每种 response_type 提供输出格式模板（含 few-shot 示例），指引 AI 如何将 raw JSON 数据格式化为用户友好的回答。

#### Scenario: Entity card format
- **WHEN** AI 收到 response_type="entity_card" 的数据
- **THEN** AI SHALL 按 skill.md 中的卡片模板格式化：技能名+类型标签+核心机制+基础属性

#### Scenario: Support recommendation format
- **WHEN** AI 收到 response_type="support_dps" 的数据
- **THEN** AI SHALL 按分组展示：每个辅助名称+效果分类+对公式的影响位置+关键数值

### Requirement: Updated capability boundary
skill.md SHALL 声明系统为"POB 数据分析汇总服务"，能力范围包括数据查询、数值分析、机制解读、辅助匹配推荐、对比分析、Stat 反查、公式查询。明确排除不在 POB 数据中的游戏知识、实时状态、主观 Build 推荐。

#### Scenario: Capability boundary check
- **WHEN** 用户问 "Arc 当前版本的胜率"
- **THEN** AI SHALL 回答该问题超出能力范围（实时游戏数据不在 POB 中）
