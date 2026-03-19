## ADDED Requirements

### Requirement: Support-skill compatibility matrix
系统 SHALL 在初始化时预计算所有主动技能与辅助宝石的兼容矩阵，存入 `support_compatibility` 表。兼容性基于辅助的 require_skill_types / exclude_skill_types 与主动技能的 skill_types 进行标签匹配。

#### Scenario: Compatible support
- **WHEN** ArcPlayer 的 skill_types 包含 Spell 且辅助的 require_skill_types 包含 Spell
- **THEN** support_compatibility 记录 SHALL 标记 compatible=true，match_reason 说明匹配原因

#### Scenario: Incompatible support
- **WHEN** 辅助的 exclude_skill_types 包含 Chaining 且技能有 Chaining 标签
- **THEN** support_compatibility 记录 SHALL 标记 compatible=false

### Requirement: Support effect classification
系统 SHALL 为每个辅助宝石预计算效果分类（`support_effects` 表），包含 effect_category（damage_more/damage_added/speed/aoe/chain/projectile/duration/crit/dot/utility/defense）、quantifiable 标记、key_stats（关键 stat 和数值 JSON）、formula_impact（对 DPS 公式的影响位置描述）。

#### Scenario: Quantifiable damage support
- **WHEN** 辅助提供 `support_damage_+%_final` stat（如 Controlled Destruction）
- **THEN** effect_category SHALL 为 "damage_more"，quantifiable=true，key_stats 包含 MORE 值，formula_impact 描述 "AverageDamage 中的 more 乘数项"

#### Scenario: Chain support with trade-off
- **WHEN** 辅助增加连锁次数但减少每次连锁伤害
- **THEN** key_stats SHALL 包含连锁增加值和伤害减少值，formula_impact SHALL 描述净效果公式（"ChainMax 增加但每次连锁 damage 减少"）

### Requirement: Support potential recommendations
系统 SHALL 为不可量化但机制适配的辅助-技能组合生成潜力推荐，存入 `support_potential` 表，包含 potential_reason（适配原因）和 synergy_type（mechanic_match/tag_synergy/stat_amplify）。

#### Scenario: Mechanic synergy
- **WHEN** 辅助的效果与技能核心机制形成协同（如 Spell Echo 与 Arc 的连锁清图）
- **THEN** support_potential 记录 SHALL 标记 synergy_type="mechanic_match"，potential_reason 说明协同原因

### Requirement: Support query modes
系统 SHALL 支持 `supports <skill_id>` 子命令，提供 4 种查询模式：all（所有兼容辅助列表）、dps（按可量化增益分类）、utility（工具型辅助）、potential（潜力推荐）。

#### Scenario: DPS mode query
- **WHEN** `supports ArcPlayer --mode dps`
- **THEN** 返回所有 quantifiable=true 的兼容辅助，按 effect_category 分组，附带 key_stats 和 formula_impact

#### Scenario: Potential mode query
- **WHEN** `supports ArcPlayer --mode potential`
- **THEN** 返回 support_potential 表中该技能的所有潜力推荐，附带 potential_reason 和 synergy_type

### Requirement: Support level scaling
系统 SHALL 在 support_effects 中记录辅助宝石的等级成长关键点（`level_scaling` JSON 字段），包含 1 级、10 级、20 级的关键 stat 数值。

#### Scenario: Level scaling data
- **WHEN** 查询辅助的 level_scaling
- **THEN** SHALL 包含至少 3 个等级点（1/10/20）的关键 stat 数值变化
