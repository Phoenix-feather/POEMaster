## ADDED Requirements

### Requirement: Entity summary pre-computation
系统 SHALL 在初始化时为每个实体预计算 `summary` 字段。summary 从以下来源提取：技能专属 statMap 覆盖（前缀为技能名的 stat）、实体 description 字段、constantStats 中的特色值。如果提炼不出独特性，summary SHALL 为空（不做无意义的描述）。

#### Scenario: Skill with unique statMap
- **WHEN** 实体有专属 statMap 覆盖（如 ArcPlayer 有 `arc_damage_+%_final_for_each_remaining_chain`）
- **THEN** summary SHALL 包含该技能的核心机制描述（如"连锁闪电法术，每次连锁剩余次数增加 MORE 伤害加成"）

#### Scenario: Entity without unique features
- **WHEN** 实体是普通天赋节点（纯 +10 Str 等数值加成）
- **THEN** summary SHALL 为 null

### Requirement: Key mechanics pre-computation
系统 SHALL 在初始化时为有独特机制的实体预计算 `key_mechanics` 字段（JSON 数组），每个元素包含 name（机制名）、stat（关联 stat）、formula（公式表达）、effect（效果描述）。

#### Scenario: Arc key mechanics
- **WHEN** 查询 ArcPlayer 的 key_mechanics
- **THEN** SHALL 包含"连锁"机制（含 ChainMax 公式）和"闪电灌注消耗"机制（含消耗效果）

### Requirement: Display stats via StatDescriber bridge
系统 SHALL 使用 lupa 运行 POB 原始 StatDescriber.lua 代码，将实体的 stats + constantStats 转换为人类可读的描述文本数组，存入 `display_stats` 字段。

#### Scenario: Stat description generation
- **WHEN** 初始化时处理 ArcPlayer（20 级数据）
- **THEN** display_stats SHALL 包含精确的 POB 格式描述（如 "Chains 9 Times", "50% increased Shock Effect"）

#### Scenario: StatDescriber bridge failure fallback
- **WHEN** lupa 加载 StatDescription 文件失败（OOM 或超时）
- **THEN** 系统 SHALL 记录警告并将 display_stats 置为 null，不中断初始化流程

### Requirement: Entity type-based field filtering
系统 SHALL 在实体查询时按类型裁剪返回字段，只返回该类型相关的字段集（去除 null 噪音），但 data_json 始终可用作完整兜底。

#### Scenario: Skill definition query
- **WHEN** 查询 type=skill_definition 的实体
- **THEN** 返回字段集 SHALL 包含 id/name/description/skill_types/cast_time/stats/constant_stats/levels/stat_sets/reservation/support/is_trigger/hidden/require_skill_types/add_skill_types/exclude_skill_types/summary/key_mechanics/display_stats
- **AND** SHALL 不包含 ascendancy_name/is_notable/is_keystone/mod_tags/weight_keys/affix_type 等无关字段

#### Scenario: Full detail mode
- **WHEN** 查询使用 `--detail full` 参数
- **THEN** SHALL 返回所有非 null 字段 + data_json

### Requirement: Unified JSON field parsing
系统 SHALL 在实体查询时统一解析所有 20 个 JSON 字段（skill_types/constant_stats/stats/reservation/data_json/mod_tags/weight_keys/mod_data/quality_stats/levels/stat_sets/require_skill_types/add_skill_types/exclude_skill_types/tags/variant/stats_node/reminder_text/stat_descriptions/additional_granted_effect_ids），确保返回的数据全部是已解析的 Python 对象。

#### Scenario: JSON field consistency
- **WHEN** 通过任何查询方法获取实体数据
- **THEN** 所有 JSON 字段 SHALL 返回为已解析的 Python 列表/字典，不得返回原始 JSON 字符串

### Requirement: Entity detail levels
系统 SHALL 支持 4 种实体查询详情级别：summary（精简卡片）、levels（等级数值表）、stats（stat 详解）、full（完整数据）。

#### Scenario: Summary detail level
- **WHEN** `entity <id> --detail summary`
- **THEN** 返回 summary + skill_types + cast_time + reservation + key_mechanics 的精简卡片

#### Scenario: Levels detail level
- **WHEN** `entity <id> --detail levels`
- **THEN** 返回 levels JSON 展开为等级数值表（每级的关键 stat 值）

#### Scenario: Stats detail level
- **WHEN** `entity <id> --detail stats`
- **THEN** 返回 display_stats + key_mechanics + constant_stats 的 stat 详解视图
