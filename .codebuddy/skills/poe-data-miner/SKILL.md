---
name: poe-data-miner
description: POB数据分析汇总服务 - 提供Path of Exile游戏数据的查询、分析、对比、辅助匹配推荐能力。支持实体查询、机制解读、辅助搭配、数值分析、公式链路、Stat反查。
---

# POE Data Miner v3

**POB 数据分析汇总服务**

从POB（Path of Building）数据文件中提取、分析和汇总Path of Exile游戏数据，提供面向场景的结构化数据问答能力。

---

## ⚠️ 重要说明：能力边界

### ✅ 能做什么

- **实体查询与概览**：查询技能、宝石、物品、天赋节点的属性定义，提供人话摘要和核心机制解读
- **数值分析**：查看技能各等级数值成长、stat 详情、常量属性
- **机制解读**：查询 44 个游戏机制的行为描述、公式摘要、受影响 stat、机制间关联关系
- **辅助搭配推荐**：基于 skill_types 兼容矩阵的辅助宝石匹配，含 DPS 增益分类、工具型辅助、潜力推荐
- **对比分析**：并排对比两个同类型实体的属性差异
- **Stat 反查**：反查所有能影响指定 stat 的来源（stat_mappings + 技能内置 + 装备天赋）
- **公式查询与链路**：查询通用计算公式、stat 映射，展示公式间的引用链路（树形结构）
- **数据统计**：获取知识库的完整统计信息

### ❌ 不能做什么

- **实时游戏数据**：无法查询当前赛季胜率、交易市场价格等 POB 以外的数据
- **主观 Build 推荐**：无法说"这个 Build 好不好"、"推荐什么天赋配点"
- **隐含组合效果推理**：无法推断多技能组合后的未被 POB 数据描述的交互效果
- **游戏逻辑验证**：无法验证某个机制在实际游戏中是否按预期工作
- **版本对比**：无法对比不同游戏版本之间的数据变化

**核心原则**：基于 POB 数据的分析与汇总，不提供超出数据范围的逻辑推理。

---

## 问题类型识别与调用策略

用户的问题分为 8 种类型。AI 应根据识别规则判断类型，然后按对应的调用策略获取数据。一个问题可能同时属于多个类型（组合调用）。

### Type A: 概览（"这个东西是什么"）

**识别关键词**：是什么、介绍、概览、overview、基本信息、简介

**场景示例**：
- "Arc 是什么技能？"
- "介绍一下 Spark"
- "Headhunter 是什么装备？"

**调用策略**：
```bash
python scripts/kb_query.py entity <entity_id> --detail summary
```

**返回 response_type**：`entity_overview`

**何时使用**：用户想要快速了解某个实体的基本信息，不需要详细数值。

---

### Type B: 数值分析（"具体数据是多少"）

**识别关键词**：数值、伤害、成长、等级、多少、DPS、damage、level、数据

**场景示例**：
- "Arc 各等级的伤害数值"
- "Spark 20 级的 stat 数据"
- "这个技能 1 级到 20 级怎么成长的？"

**调用策略**：
```bash
# 等级数值成长
python scripts/kb_query.py entity <entity_id> --detail levels

# 完整 stat 详情
python scripts/kb_query.py entity <entity_id> --detail stats

# 配合公式查询理解数值含义
python scripts/kb_query.py formula --entity <entity_id>
```

**返回 response_type**：`numeric_table`（levels）/ `stat_detail`（stats）/ `formula_query`

**何时使用**：用户关心具体的数值和成长曲线。通常先用 levels 看成长，再用 formula 查公式理解数值含义。

---

### Type C: 机制详解（"这个怎么工作"）

**识别关键词**：怎么工作、机制、触发、原理、mechanism、trigger、如何生效、行为、效果

**场景示例**：
- "生命偷取是怎么工作的？"
- "触发机制有哪些？"
- "InstantLifeLeech 和 LifeLeech 有什么关系？"

**调用策略**：
```bash
# 机制行为描述
python scripts/kb_query.py mechanism <mechanism_id> --detail behavior

# 机制关联关系
python scripts/kb_query.py mechanism <mechanism_id> --detail relations

# 完整信息（行为+关系+来源）
python scripts/kb_query.py mechanism <mechanism_id> --detail full

# 搜索机制
python scripts/kb_query.py mechanism --search "leech"

# 列出所有机制
python scripts/kb_query.py mechanism --all
```

**返回 response_type**：`mechanism_behavior` / `mechanism_relations` / `mechanism_full` / `mechanism_list`

**何时使用**：用户想理解某个游戏机制的运作方式。先用 behavior 看行为描述，如果涉及多个机制的交互关系，再用 relations。

---

### Type D: 辅助搭配（"用什么辅助好"）

**识别关键词**：辅助、搭配、配什么、support、支援、辅助宝石、怎么选、推荐

**场景示例**：
- "Arc 用什么辅助好？"
- "Spark 的 DPS 辅助有哪些？"
- "这个技能有什么工具型辅助？"

**调用策略**：
```bash
# DPS 增益辅助 — 紧凑摘要模式（推荐，~30KB 输出）
python scripts/kb_query.py supports <skill_id> --mode dps --summary

# DPS 增益辅助 — 展开单个辅助完整详情
python scripts/kb_query.py supports <skill_id> --mode dps --detail <support_id>

# DPS 增益辅助 — 完整原始数据（~100KB，仅调试用）
python scripts/kb_query.py supports <skill_id> --mode dps

# 工具型辅助（不可量化但有用）
python scripts/kb_query.py supports <skill_id> --mode utility

# 潜力推荐（机制协同但需手动判断价值）
python scripts/kb_query.py supports <skill_id> --mode potential

# 所有兼容辅助完整列表
python scripts/kb_query.py supports <skill_id> --mode all
```

**返回 response_type**：`support_dps` / `support_utility` / `support_potential` / `support_all`

**何时使用**：用户选择辅助宝石时。典型流程：先用 `dps --summary` 模式总览所有可量化辅助（每辅助一行摘要），对感兴趣的辅助用 `dps --detail <id>` 展开完整数据，再用 potential 看潜力推荐。

**⚠️ 输出显示规则**（回答 Type D 问题时必须遵守）：

输出由 **5 个固定区块** 按顺序组成，每个区块的结构不可改变。AI 可以自由决定推荐哪些辅助、展开几个、以什么顺序排列，但**每个区块的骨架格式必须严格遵守**。

> **内部字段与用户输出分离原则**：数据层字段 `category`、`dps_type`、impact 中的 `[xxx]` 前缀标签仅供 AI 决策使用，**一律不出现在用户可见输出中**。

---

#### 区块 0：技能头部（固定格式）

```
# ⚡ {skill_name} 辅助推荐

> {entity.description 原文}
> **标签**：{skill_types 用 / 分隔，不翻译}
```

---

#### 区块 1：DPS 增益辅助（固定格式）

区块标题固定为：

```
## 一、DPS 增益辅助
```

其中每个辅助使用**卡片格式**，每张卡片结构如下：

```
### {emoji} {English name}

**效果**：{一句话说明}

| ✅ 正面 | ❌ 代价 |
|---------|--------|
| {正面效果} | {负面效果，无则写 "—"} |

**公式**：{impact 字段去掉 [xxx] 前缀标签后的内容}

**📊 期望**：{efficiency 字段，如 "x0.82 (伤害 x0.70 | 目标 x1.17)" 或 "x1.25~x4.20 (伤害 x1.25~x4.20)"}
```

**卡片字段规则**：

| 字段 | 规则 |
|------|------|
| emoji | AI 自选，每张卡片有且仅有 1 个 |
| English name | 辅助宝石的**英文原名**（如 `Controlled Destruction`、`Chain I`） |
| **效果** | AI 自由改写，**必须是 1 句话中文** |
| ✅ 正面 | AI 可改写 pos 内容使其更易读，**每个 pos 项一行** |
| ❌ 代价 | AI 可改写 neg 内容，**无负面时固定写 "—"** |
| **公式** | 从 impact 字段复制，但**去掉所有 `[xxx]` 方括号标签**（如 `[damage_more]`、`[chain]`） |
| **📊 期望** | 从 efficiency 字段直接复制，无 efficiency 时写 "—" |

**公式行清洗规则**：
- impact 原文：`[damage_more] 伤害独立乘区 (LESS -30%) | [chain] 连锁次数 (+1)`
- 清洗后输出：`伤害独立乘区 (LESS -30%) | 连锁次数 (+1)`
- 清洗方式：正则 `\[[\w]+\]\s*` 全部删除

**示例卡片**：

```
### 🔗 Chain I

**效果**：技能命中后额外连锁到附近敌人，扩大清图覆盖范围。

| ✅ 正面 | ❌ 代价 |
|---------|--------|
| +1 连锁次数 | 30% LESS 命中伤害 |

**公式**：伤害独立乘区 (LESS -30%) | 连锁次数 (+1)

**📊 期望**：x0.82 (伤害 x0.70 | 目标 x1.17 (连锁 6→7))
```

**示例卡片**（无代价类型）：

```
### 🔥 Controlled Destruction

**效果**：放弃暴击能力，换取法术伤害提升。

| ✅ 正面 | ❌ 代价 |
|---------|--------|
| 25% MORE 法术伤害 | ⚠️ 不能暴击 |

**公式**：伤害独立乘区 (MORE +25%) | 暴击率/暴击伤害 | ⚠️ 不能暴击

**📊 期望**：x1.25 (伤害 x1.25)
```

---

#### 区块 2：工具型辅助（固定格式）

区块标题固定为：

```
## 二、工具型辅助
```

内容固定为 **3 列表格**：

```
| 辅助 | 效果 | 备注 |
|------|------|------|
| {English name} | {AI 改写的一句话效果} | {适用场景或注意事项} |
```

---

#### 区块 3：潜力推荐（固定格式）

区块标题固定为：

```
## 三、潜力推荐
```

内容固定为 **3 列表格**：

```
| 辅助 | 协同点 | 理由 |
|------|--------|------|
| {English name} | {用中文描述协同点} | {AI 改写的理由} |
```

---

#### 区块 4：推荐填槽方案（固定格式）

按不同 build 场景分组推荐，每组恰好 5 个辅助。至少给出 **2 个场景**，最多 **4 个场景**。

```
## 📋 推荐填槽

### 🎯 {场景 A 名称}（5/5）
1. **{English name}** — {一句话效果}
2. **{English name}** — {一句话效果}
3. **{English name}** — {一句话效果}
4. **{English name}** — {一句话效果}
5. **{English name}** — {一句话效果}

> 📊 组合效率：{将 5 个辅助的 efficiency 中的 damage/speed/target 分别相乘得到组合总倍率}

### 🎯 {场景 B 名称}（5/5）
1. **{English name}** — {一句话效果}
2. **{English name}** — {一句话效果}
3. **{English name}** — {一句话效果}
4. **{English name}** — {一句话效果}
5. **{English name}** — {一句话效果}

> 📊 组合效率：{同上}

> 💡 {一句话总结不同场景的选择依据}
```

**填槽规则**：
- 每个场景**恰好 5 行**，不多不少
- 场景名称用中文描述 build 方向（如"电震流"、"纯伤害"、"Boss 单体"、"清图效率"）
- 至少 2 个场景，最多 4 个场景
- 每行格式固定：`**{English name}** — {效果}`

---

#### 输出规则汇总

1. **5 个区块按顺序输出**，不可缺少、不可调换顺序
2. **正面和负面效果必须分列展示**，绝不能省略负面效果（含 Flag 限制）
3. **无负面效果时固定写 "—"**，不写"无代价"
4. **公式行去掉 `[xxx]` 方括号标签后输出**，不保留内部分类前缀
5. **推荐填槽按场景分组**，每组恰好 5 个辅助，至少 2 组
6. **辅助名称使用英文原名**，不翻译
7. **内部字段（category、dps_type、impact 标签）仅供 AI 决策，不出现在输出中**
8. **📊 期望行**从 efficiency 字段直接复制，无 efficiency 数据时写 "—"
9. **推荐填槽组合效率**：将该组 5 个辅助的 damage/speed/target 倍率分别相乘，给出总效率倍率

---

### Type E: 对比分析（"A 和 B 哪个好"）

**识别关键词**：对比、比较、和…比、哪个好、区别、差异、compare、vs、versus

**场景示例**：
- "Arc 和 Spark 有什么区别？"
- "这两个唯一装备哪个好？"
- "对比 Fireball 和 Lava Lash"

**调用策略**：
```bash
# 摘要级对比（快速看核心差异）
python scripts/kb_query.py compare <id1> <id2> --detail summary

# stat 级对比（详细数值差异）
python scripts/kb_query.py compare <id1> <id2> --detail stats

# 完整对比
python scripts/kb_query.py compare <id1> <id2> --detail full
```

**返回 response_type**：`comparison`

**何时使用**：用户要比较两个实体时。注意仅支持同类型对比（如两个 skill_definition 之间）。如果类型不同，返回中会标注 `same_type: false`，应告知用户仅支持同类型对比。

---

### Type F: Stat 反查（"什么能提高 X"）

**识别关键词**：什么能加、来源、怎么提高、怎么堆、哪些影响、reverse、反查、提升

**场景示例**：
- "什么能提高 chain 次数？"
- "哪些装备能加暴击率？"
- "CritChance 的来源有哪些？"

**调用策略**：
```bash
python scripts/kb_query.py reverse-stat <stat_name>
```

**返回 response_type**：`reverse_stat`

**何时使用**：用户想知道某个属性可以从哪些途径获得。返回两部分：①stat_mappings 中的 modifier 映射 ②entities 中包含该 stat 的实体（技能内置、装备、天赋等）。

---

### Type G: 公式查询（"怎么算的"）

**识别关键词**：公式、怎么算、计算、formula、计算方式、算法、推导

**场景示例**：
- "DPS 怎么算的？"
- "护甲减伤公式是什么？"
- "Arc 的伤害计算公式"

**调用策略**：
```bash
# 按问题搜索公式
python scripts/kb_query.py formula --query "DPS计算"

# 按实体查询相关公式
python scripts/kb_query.py formula --entity <entity_id>

# 展示公式引用链路（公式间引用关系树）
python scripts/kb_query.py formula --query "DPS" --chain

# 按 stat 查映射
python scripts/kb_query.py formula --stat <stat_name>

# 公式索引统计
python scripts/kb_query.py formula --stats
```

**返回 response_type**：`formula_query` / `formula_chain` / `stat_mapping` / `formula_stats`

**何时使用**：用户想了解某个计算公式。返回三层：universal（通用公式）、stat_mappings（stat 到 modifier 映射）、gap_formulas（缺口公式）。使用 `--chain` 展示公式间的引用关系树。

---

### Type H: 列表查询（"有哪些"）

**识别关键词**：所有、列出、有哪些、列表、list、全部、搜索、找

**场景示例**：
- "所有的元技能有哪些？"
- "有哪些火焰相关的技能？"
- "列出所有唯一法杖"

**调用策略**：
```bash
# 搜索实体
python scripts/kb_query.py entity --search "<keyword>"

# 按实体类型列出
python scripts/kb_query.py entity --type <entity_type>

# 按技能类型列出
python scripts/kb_query.py entity --skill-type "<skill_type>"

# 列出所有元技能
python scripts/kb_query.py entity --meta

# 列出所有机制
python scripts/kb_query.py mechanism --all

# 搜索机制
python scripts/kb_query.py mechanism --search "<keyword>"

# 统计总览
python scripts/kb_query.py stats
```

**返回 response_type**：`entity_list` / `mechanism_list` / `kb_stats`

**何时使用**：用户想获取某类实体的列表或进行模糊搜索。

---

### 组合调用示例

有些问题涉及多个类型，需要组合多个子命令：

**"Arc 的数值和伤害机制"** → Type B + Type C
```bash
python scripts/kb_query.py entity ArcPlayer --detail levels
python scripts/kb_query.py formula --entity ArcPlayer
```

**"Arc 和 Spark 的辅助宝石选择对比"** → Type D + Type E
```bash
python scripts/kb_query.py supports ArcPlayer --mode dps
python scripts/kb_query.py supports SparkPlayer --mode dps
python scripts/kb_query.py compare ArcPlayer SparkPlayer --detail summary
```

**"怎么提高 Arc 的连锁次数"** → Type F + Type A
```bash
python scripts/kb_query.py reverse-stat chain
python scripts/kb_query.py entity ArcPlayer --detail stats
```

---

## 输出格式模板

以下模板指引 AI 如何将 raw JSON 数据格式化为用户友好的回答。每种 response_type 对应一个模板。

### entity_overview（实体概览卡片）

**数据字段**：id, name, type, description, summary, key_mechanics, display_stats, skill_types, cast_time 等

**格式模板**：
```
## 🎯 {name}

**类型**：{type}
**技能标签**：{skill_types（逗号分隔）}

{summary（如果存在，作为核心描述段落）}

{display_stats（如果存在，以列表展示人话stat描述）}

{key_mechanics（如果存在，以列表展示核心机制）}
```

**Few-shot 示例**：

假设查询 `entity ArcPlayer --detail summary` 返回：
```json
{
  "id": "ArcPlayer",
  "name": "Arc",
  "type": "skill_definition",
  "skill_types": ["Spell", "Chaining", "Lightning", "Intelligence"],
  "cast_time": 0.7,
  "summary": "闪电连锁法术，击中时自动连锁到附近敌人",
  "key_mechanics": [{"name": "连锁", "stat": "chain", "effect": "每次连锁伤害递增"}],
  "response_type": "entity_overview"
}
```

AI 应输出：
```
## 🎯 Arc

**类型**：技能定义（skill_definition）
**技能标签**：Spell, Chaining, Lightning, Intelligence
**施法时间**：0.7s

闪电连锁法术，击中时自动连锁到附近敌人。

**核心机制**：
- 🔗 连锁（chain）：每次连锁伤害递增
```

---

### numeric_table（数值表格）

**数据字段**：id, name, levels, constant_stats, quality_stats

**格式模板**：
```
## 📊 {name} 等级数值

{constant_stats 以"固定属性"列表展示}

### 等级成长
| 等级 | {stat_1} | {stat_2} | ... |
|------|----------|----------|-----|
| 1    | {值}     | {值}     | ... |
| ...  | ...      | ...      | ... |
| 20   | {值}     | {值}     | ... |

{quality_stats 以"品质加成"列表展示}
```

**Few-shot 示例**：

假设查询 `entity ArcPlayer --detail levels` 返回了 levels 字段包含各等级数据，AI 应提取关键 stat 组成表格：
```
## 📊 Arc 等级数值

**固定属性**：
- 连锁次数（chain）：7

### 等级成长
| 等级 | 基础伤害 | 暴击率 | 法力消耗 |
|------|---------|--------|---------|
| 1    | 8-23    | 6%     | 4       |
| 10   | 45-135  | 6%     | 10      |
| 20   | 165-496 | 6%     | 20      |

> 注：以上数值从 POB 数据提取，实际游戏内可能受其他因素影响。
```

---

### stat_detail（Stat 详情）

**数据字段**：id, name, stats, constant_stats, stat_sets, stat_descriptions, mod_data

**格式模板**：
```
## 📋 {name} Stat 详情

### 常量 Stats
{constant_stats 列表}

### 动态 Stats
{stats 列表，含 stat 名和值}

### Stat 描述
{stat_descriptions 或 display_stats 人话描述}
```

---

### skill_full / gem_full / item_full / passive_full / mod_full（完整实体数据）

**格式模板**：
```
## 📦 {name} 完整数据

**基本信息**
{id, type, description 等基础字段}

**属性数据**
{按类型展示相关字段，如技能展示 skill_types/cast_time/reservation，物品展示 implicits/stats 等}

**详细数据**
{stat_sets, levels 等大型数据结构，展示关键部分并注明完整数据可通过 data_json 获取}
```

**何时使用**：用户明确要求"完整数据"或"所有信息"时。注意数据量可能很大，应提取关键部分展示并告知用户。

---

### mechanism_behavior（机制行为描述）

**数据字段**：id, name, friendly_name, mechanism_category, behavior_description, formula_abstract, affected_stats

**格式模板**：
```
## ⚙️ {friendly_name}（{id}）

**分类**：{mechanism_category}

### 行为描述
{behavior_description}

### 公式
{formula_abstract（如果存在）}

### 影响的 Stats
{affected_stats 列表}
```

**Few-shot 示例**：

假设查询 `mechanism InstantLifeLeech --detail behavior` 返回：
```json
{
  "id": "InstantLifeLeech",
  "friendly_name": "即时生命偷取",
  "mechanism_category": "leech",
  "behavior_description": "使生命偷取效果变为即时恢复，而非随时间恢复。跳过正常的偷取实例队列。",
  "formula_abstract": "life_leeched = damage * leech_rate; heal(life_leeched) -- 即时",
  "affected_stats": ["instant_life_leech", "life_leech_rate"],
  "response_type": "mechanism_behavior"
}
```

AI 应输出：
```
## ⚙️ 即时生命偷取（InstantLifeLeech）

**分类**：leech（偷取类）

### 行为描述
使生命偷取效果变为即时恢复，而非随时间恢复。跳过正常的偷取实例队列。

### 公式
```
life_leeched = damage * leech_rate
heal(life_leeched) -- 即时恢复
```

### 影响的 Stats
- instant_life_leech
- life_leech_rate
```

---

### mechanism_relations（机制关联关系）

**数据字段**：id, name, friendly_name, mechanism_category, relations[]

**格式模板**：
```
## 🔗 {friendly_name} 的关联机制

{relations 表格或列表}
| 关联机制 | 关系类型 | 说明 |
|---------|---------|------|
| {related_mechanism} | {relation_type} | {description} |
```

---

### mechanism_full（机制完整信息）

**格式模板**：组合 mechanism_behavior + mechanism_relations 的模板，额外添加"来源"部分：
```
### 来源（{sources 数量}个）
{每个 source 列出 source_type 和 source_id}
```

---

### mechanism_list（机制列表）

**格式模板**：
```
## 📋 机制列表

| 机制 | 中文名 | 分类 | 来源数 |
|------|--------|------|-------|
| {id} | {friendly_name} | {category} | {source_count} |
```

---

### support_all（所有兼容辅助）

**数据字段**：skill_id, supports[](support_id, name, category, quantifiable, match_reason)

**格式模板**：
```
## 💎 {skill_id} 的兼容辅助（共 {total} 个）

### 按效果分类
{按 category 分组展示}

**伤害类**：{damage_more 和 damage_added 类辅助}
**速度类**：{speed 类辅助}
**暴击类**：{crit 类辅助}
**工具类**：{utility, defense 等非量化辅助}
...
```

---

### support_dps（DPS 增益辅助）

**数据字段**：skill_id, by_category{category: [{support_id, name, formula_impact, key_stats, level_scaling}]}

**格式模板**：
```
## 📈 {skill_id} 的 DPS 辅助

{按 by_category 分组展示，每组内列出辅助名、公式影响、关键数值}

### {category}（{count}个）
| 辅助 | 公式影响位置 | 关键 Stat（Lv20） |
|------|-------------|------------------|
| {name} | {formula_impact} | {key_stats 中 Lv20 值} |
```

**Few-shot 示例**：

假设查询 `supports ArcPlayer --mode dps` 返回：
```json
{
  "skill_id": "ArcPlayer",
  "mode": "dps",
  "by_category": {
    "damage_more": [
      {"support_id": "SupportControlledDestruction", "name": "Controlled Destruction", "formula_impact": "multiplier on spell damage", "key_stats": {"spell_damage_+%_final": 44}},
      {"support_id": "SupportAddedLightningDamage", "name": "Added Lightning Damage", "formula_impact": "flat added damage", "key_stats": {"attack_minimum_added_lightning_damage": 15, "attack_maximum_added_lightning_damage": 291}}
    ],
    "speed": [
      {"support_id": "SupportFasterCasting", "name": "Faster Casting", "formula_impact": "cast speed multiplier", "key_stats": {"cast_speed_+%": 39}}
    ],
    "chain": [
      {"support_id": "SupportChain", "name": "Chain", "formula_impact": "additional chains", "key_stats": {"number_of_chains": 3}}
    ]
  },
  "total": 4,
  "response_type": "support_dps"
}
```

AI 应输出：
```
## 📈 Arc 的 DPS 辅助（共 4 个）

### 🔴 Damage More（2个）
| 辅助 | 公式影响 | 关键数值（Lv20） |
|------|---------|-----------------|
| Controlled Destruction | 法术伤害乘区 | spell_damage +44% |
| Added Lightning Damage | 基础附加伤害 | 附加 15-291 闪电伤害 |

### 🟡 Speed（1个）
| 辅助 | 公式影响 | 关键数值（Lv20） |
|------|---------|-----------------|
| Faster Casting | 施法速度乘区 | cast_speed +39% |

### 🔵 Chain（1个）
| 辅助 | 公式影响 | 关键数值（Lv20） |
|------|---------|-----------------|
| Chain | 额外连锁次数 | +3 连锁 |
```

---

### support_utility（工具型辅助）

**数据字段**：skill_id, supports[](support_id, name, category, formula_impact, match_reason)

**格式模板**：
```
## 🔧 {skill_id} 的工具型辅助（共 {total} 个）

| 辅助 | 效果分类 | 影响描述 |
|------|---------|---------|
| {name} | {category} | {formula_impact} |
```

---

### support_potential（潜力推荐）

**数据字段**：skill_id, potentials[](support_id, name, synergy_type, potential_reason, effect_category)

**格式模板**：
```
## 💡 {skill_id} 的潜力辅助推荐

{按 synergy_type 分组}

### {synergy_type}
| 辅助 | 效果分类 | 推荐理由 |
|------|---------|---------|
| {name} | {effect_category} | {potential_reason} |
```

**Few-shot 示例**：

假设查询 `supports ArcPlayer --mode potential` 返回数据，AI 应输出：
```
## 💡 Arc 的潜力辅助推荐

### mechanic_match（机制匹配）
| 辅助 | 效果分类 | 推荐理由 |
|------|---------|---------|
| Awakened Chain | chain | 辅助含 chain stat，技能含 Chaining 标签 |

### tag_synergy（标签协同）
| 辅助 | 效果分类 | 推荐理由 |
|------|---------|---------|
| Lightning Penetration | utility | 辅助含 lightning_penetration stat，技能含 Lightning 标签 |
```

---

### comparison（对比结果）

**数据字段**：entity_1, entity_2, same_type, differences, same, only_in_entity_1, only_in_entity_2

**格式模板**：
```
## ⚖️ {entity_1.name} vs {entity_2.name}

**类型**：{type}（{same_type ? "同类型，可对比" : "⚠️ 不同类型，仅展示差异"}）

### 核心差异
| 属性 | {entity_1.name} | {entity_2.name} |
|------|-----------------|-----------------|
| {差异字段} | {entity_1 的值} | {entity_2 的值} |

### 相同属性
{same 中的重要字段}

### 独有属性
- **仅 {entity_1.name}**：{only_in_entity_1 的字段列表}
- **仅 {entity_2.name}**：{only_in_entity_2 的字段列表}
```

**Few-shot 示例**：

假设查询 `compare ArcPlayer SparkPlayer --detail summary` 返回数据，AI 应输出：
```
## ⚖️ Arc vs Spark

**类型**：skill_definition（同类型，可对比）

### 核心差异
| 属性 | Arc | Spark |
|------|-----|-------|
| 技能标签 | Spell, Chaining, Lightning | Spell, Projectile, Lightning |
| 施法时间 | 0.7s | 0.65s |
| 核心机制 | 连锁递增伤害 | 投射物散射覆盖 |

### 相同属性
- 类型：skill_definition
- 元素：Lightning

> Arc 侧重单目标连锁递增，Spark 侧重多投射物覆盖面积。
```

---

### reverse_stat（Stat 反查结果）

**数据字段**：stat_name, stat_mappings[], entities[], total_mappings, total_entities

**格式模板**：
```
## 🔍 反查：{stat_name}

### Stat 映射（{total_mappings} 条）
| Stat 名称 | Modifier 代码 | 来源文件 |
|-----------|--------------|---------|
| {stat_name} | {modifier_code（截取关键部分展示）} | {source_file} |

### 含有该 Stat 的实体（{total_entities} 个）
| 实体 | 名称 | 类型 | Stat 来源 | 数值 |
|------|------|------|----------|------|
| {id} | {name} | {type} | {stat_source} | {stat_value} |
```

**Few-shot 示例**：

假设查询 `reverse-stat chain` 返回数据，AI 应输出：
```
## 🔍 反查：chain

### Stat 映射（3 条）
| Stat 名称 | Modifier 代码 | 来源文件 |
|-----------|--------------|---------|
| number_of_chains | mod.listMod("ChainCountMax", ...) | SkillStatMap.lua |
| chain_damage_+% | mod.listMod("ChainDamage", ...) | SkillStatMap.lua |

### 含有该 Stat 的实体（5 个）
| 实体 | 名称 | 类型 | 来源 | 数值 |
|------|------|------|------|------|
| ArcPlayer | Arc | skill_definition | constant_stats | 7 |
| SupportChain | Chain Support | skill_definition | constant_stats | 3 |
| Deadeye_ChainProjectile | 连锁 | passive_node | stats_node | 1 |

> 可以通过技能内置、辅助宝石、天赋节点获得额外连锁次数。
```

---

### formula_query（公式查询结果）

**数据字段**：query, entity_id, universal[], stat_mappings[], gap_formulas[]

**格式模板**：
```
## 📐 公式查询：{query}

### 通用公式（{universal 数量}条）
{每个公式展示 name + formula（代码块）+ domain}

### Stat 映射（{stat_mappings 数量}条）
{每个映射展示 stat_name → modifier}

### 缺口公式（{gap_formulas 数量}条）
{每个公式展示 name + formula + 关联实体}
```

---

### formula_chain（公式引用链路）

**数据字段**：formula_chains[{root, chain[{depth, name, formula}]}]

**格式模板**：
```
## 🔗 公式链路

{每个 chain 用缩进树形展示}

{root_name}
├── {depth=1 的子公式 name}
│   ├── {depth=2 的子公式}
│   └── ...
└── {另一个 depth=1 的子公式}
```

**Few-shot 示例**：
```
## 🔗 公式链路：DPS 核心公式

dps_core
├── average_hit（平均单次伤害）
│   ├── base_damage（基础伤害）
│   └── damage_effectiveness（伤害效能）
├── speed_calc（攻速/施法速度计算）
│   └── cast_time_override（施法时间覆盖检查）
└── crit_multiplier（暴击乘区）
    └── crit_chance（暴击率计算）
```

---

### stat_mapping（单条 Stat 映射）

**格式模板**：
```
**[{domain}]** {stat_name}
→ `{modifier（完整代码）}`
```

---

### formula_stats（公式索引统计）

**格式模板**：
```
## 📊 公式索引统计

| 表 | 数量 |
|----|------|
| 通用公式 | {universal_formulas} |
| Stat 映射 | {stat_mappings} |
| 缺口公式 | {gap_formulas} |
```

---

### entity_list（实体列表）

**格式模板**：
```
## 📋 查询结果（{count}条）

| ID | 名称 | 类型 |
|----|------|------|
| {id} | {name} | {type} |
```

---

### kb_stats（知识库统计）

**格式模板**：
```
## 📊 POE 知识库统计

### 实体库
- 总计：{entities.total} 个实体
- 类型分布：{by_type 各项}

### 机制库
- 机制：{mechanisms.total} 个
- 来源：{mechanisms.sources} 条
- 关系：{mechanisms.relations} 条

### 公式库
- 通用公式：{formulas.universal_formulas} 条
- Stat 映射：{formulas.stat_mappings} 条
- 缺口公式：{formulas.gap_formulas} 条

### 辅助匹配
- 兼容对：{supports.compatibility} 对
- 辅助效果：{supports.effects} 个
- 可量化：{supports.quantifiable} 个
- 潜力推荐：{supports.potentials} 条
```

---

## CLI 完整参考

### 实体查询

```bash
# 查询单个实体（4 种 detail 级别）
python scripts/kb_query.py entity <entity_id>
python scripts/kb_query.py entity <entity_id> --detail summary
python scripts/kb_query.py entity <entity_id> --detail levels
python scripts/kb_query.py entity <entity_id> --detail stats
python scripts/kb_query.py entity <entity_id> --detail full     # 默认

# 搜索实体（按名称/ID模糊匹配）
python scripts/kb_query.py entity --search "<keyword>"

# 按实体类型查询
python scripts/kb_query.py entity --type <entity_type>
# 可选类型：skill_definition, gem_definition, unique_item, passive_node, mod_affix,
#           item_base, stat_mapping, minion_definition, calculation_module

# 按技能类型查询
python scripts/kb_query.py entity --skill-type "<skill_type>"
# 常见技能类型：Spell, Attack, Meta, Projectile, Chaining, Lightning, Fire, Cold, ...

# 列出所有元技能
python scripts/kb_query.py entity --meta
```

### 机制查询

```bash
# 查询单个机制（3 种 detail 级别）
python scripts/kb_query.py mechanism <mechanism_id> --detail behavior   # 行为+公式+影响stat
python scripts/kb_query.py mechanism <mechanism_id> --detail relations  # 关联关系
python scripts/kb_query.py mechanism <mechanism_id> --detail full       # 全部（默认）

# 搜索机制
python scripts/kb_query.py mechanism --search "<keyword>"

# 列出所有机制
python scripts/kb_query.py mechanism --all
```

### 辅助匹配查询

```bash
# 查询技能的兼容辅助（4 种模式）
python scripts/kb_query.py supports <skill_id> --mode all         # 所有兼容辅助（默认）
python scripts/kb_query.py supports <skill_id> --mode dps         # DPS 增益（按效果分组）
python scripts/kb_query.py supports <skill_id> --mode utility     # 工具型辅助
python scripts/kb_query.py supports <skill_id> --mode potential   # 潜力推荐

# 紧凑摘要模式（推荐用于 dps 模式，输出从 ~100KB 压缩到 ~30KB）
python scripts/kb_query.py supports <skill_id> --mode dps --summary

# 展开单个辅助的完整详情
python scripts/kb_query.py supports <skill_id> --mode dps --detail <support_id>

# 限制返回数量
python scripts/kb_query.py supports <skill_id> --mode all --limit 20
```

### 对比查询

```bash
# 对比两个实体（3 种 detail 级别）
python scripts/kb_query.py compare <id1> <id2>
python scripts/kb_query.py compare <id1> <id2> --detail summary   # 摘要对比（默认）
python scripts/kb_query.py compare <id1> <id2> --detail stats     # stat 级对比
python scripts/kb_query.py compare <id1> <id2> --detail full      # 完整对比
```

### Stat 反查

```bash
# 反查影响指定 stat 的所有来源
python scripts/kb_query.py reverse-stat <stat_name>

# 限制结果数量
python scripts/kb_query.py reverse-stat <stat_name> --limit 50
```

### 公式查询

```bash
# 按问题搜索公式
python scripts/kb_query.py formula --query "<question>"

# 按实体查询相关公式
python scripts/kb_query.py formula --entity <entity_id>

# 展示公式引用链路
python scripts/kb_query.py formula --query "<question>" --chain
python scripts/kb_query.py formula --entity <entity_id> --chain

# 按 stat 名称查映射
python scripts/kb_query.py formula --stat <stat_name>

# 公式索引统计
python scripts/kb_query.py formula --stats
```

### 统计信息

```bash
# 获取知识库完整统计
python scripts/kb_query.py stats
```

---

## 初始化知识库

### 完整初始化（5步流程）

```bash
python scripts/init_knowledge_base.py <pob_data_dir>
```

初始化流程：
1. **实体索引初始化** - 扫描POB数据文件，提取实体定义（16,461 个实体）
2. **实体解读层预计算** - 生成 summary / key_mechanics / display_stats（覆盖率 51%/3%/50%）
3. **公式索引初始化** - 提取通用公式、stat 映射、缺口公式
4. **机制提取** - 从 ModCache.lua 提取 44 个机制 + 行为描述 + 19 条关系
5. **辅助匹配预计算** - 生成兼容矩阵、效果分类、潜力推荐

### 数据源

POB数据文件位于以下目录：

```
POBData/
├── Data/
│   ├── Skills/           # 技能定义
│   │   ├── act_*.lua    # 主动技能
│   │   └── sup_*.lua    # 辅助技能
│   ├── Uniques/         # 唯一物品
│   ├── Bases/           # 物品基础
│   ├── Gems.lua         # 宝石定义
│   ├── ModCache.lua     # Mod缓存
│   ├── SkillStatMap.lua # Stat映射
│   └── StatDescriptions/ # Stat描述
├── Modules/             # 计算模块
│   ├── CalcTriggers.lua # 触发计算
│   ├── CalcActiveSkill.lua # 主动技能计算
│   ├── CalcOffence.lua  # 进攻计算
│   ├── CalcDefence.lua  # 防御计算
│   └── ...
└── TreeData/{version}/  # 天赋树数据
```

---

## 核心模块

### 1. 数据扫描器 (`data_scanner.py`)

扫描和缓存POB数据文件：
- Lua文件遍历和内容读取
- 数据类型识别（技能、物品、天赋等）
- 版本信息提取
- 扫描结果缓存

### 2. 实体索引 (`entity_index.py`)

SQLite-based实体存储：
- 实体数据提取和存储（48 列 DDL）
- 22 个 JSON 字段统一解析
- 解读层预计算：summary / key_mechanics / display_stats
- 按ID、类型、技能类型查询

### 3. StatDescriber 适配层 (`stat_describer_bridge.py`)

lupa LuaRuntime 运行 POB 原始 StatDescriber.lua：
- 注入 LoadModule / copyTable / round / floor / ConPrintf 适配函数
- 批量预加载公共 scope（stat_descriptions / skill_stat_descriptions）
- 优雅降级：lupa 不可用时返回 None + 警告日志

### 4. 公式索引 (`formula_index.py`)

三级公式索引系统：
- **通用公式**：适用于所有实体的通用计算公式
- **Stat映射**：技能特定的stat到modifier映射（无截断）
- **缺口公式**：Meta技能的能量生成公式

### 5. 机制提取器 (`mechanism_extractor.py`)

从ModCache.lua提取游戏机制：
- 机制识别（基于stat ID）
- 三型行为提取：Flag / Numeric / Trigger
- 中文名、分类、公式摘要、受影响 stat
- 机制间关系建模（6 种关系类型）
- YAML 补充描述合并

### 6. 辅助匹配器 (`support_matcher.py`)

辅助宝石匹配预计算引擎：
- RPN 表达式求值（处理 POB 的 require/exclude skill_types）
- 兼容矩阵：556 support × 344 active skills
- 效果分类：15 个 effect_category + 可量化标记
- 等级缩放：1/10/20 级关键 stat 数值
- 潜力推荐：8 条机制协同规则

### 7. 索引系统 (`indexes/`)

四级索引加速查询：
- **StatIndex**：Stat名称快速查找
- **SkillTypeIndex**：技能类型过滤
- **FunctionIndex**：函数调用关系
- **SemanticIndex**：语义相似度

---

## 数据库结构

### entities.db - 实体库

```sql
CREATE TABLE entities (
    id TEXT PRIMARY KEY,
    name TEXT,
    type TEXT,
    skill_types TEXT,      -- JSON数组
    description TEXT,
    -- 解读层预计算字段
    summary TEXT,          -- 独特性提炼
    key_mechanics TEXT,    -- 核心机制 JSON [{name, stat, formula, effect}]
    display_stats TEXT,    -- 人话 stat 描述
    -- ... 其他 48 列
);
```

实体类型：
- `skill_definition` - 技能定义（~1,248个）
- `gem_definition` - 宝石定义（~900个）
- `stat_mapping` - Stat映射（~5,230个）
- `passive_node` - 天赋节点（~4,313个）
- `unique_item` - 唯一物品（~474个）
- `item_base` - 物品基础（~1,171个）
- `mod_affix` - Mod词缀（~2,570个）
- `minion_definition` - 召唤物定义（~496个）
- `calculation_module` - 计算模块（~59个）

### formulas.db - 公式库

```sql
CREATE TABLE universal_formulas (
    id TEXT PRIMARY KEY,
    name TEXT,
    formula_text TEXT,
    domain TEXT
);

CREATE TABLE stat_mappings (
    id TEXT PRIMARY KEY,
    stat_name TEXT,
    modifier_code TEXT,    -- 完整 modifier 代码（无截断）
    source_file TEXT,
    domain TEXT
);

CREATE TABLE gap_formulas (
    id TEXT PRIMARY KEY,
    entity_id TEXT,
    name TEXT,
    formula_text TEXT
);
```

### mechanisms.db - 机制库

```sql
CREATE TABLE mechanisms (
    id TEXT PRIMARY KEY,
    name TEXT,
    friendly_name TEXT,           -- 中文名
    mechanism_category TEXT,      -- 分类
    behavior_description TEXT,    -- 行为描述
    formula_abstract TEXT,        -- 公式摘要
    affected_stats TEXT,          -- 影响的 stat (JSON)
    stat_names TEXT,
    source_count INTEGER
);

CREATE TABLE mechanism_sources (
    id INTEGER PRIMARY KEY,
    mechanism_id TEXT,
    source_type TEXT,
    source_id TEXT
);

CREATE TABLE mechanism_relations (
    id INTEGER PRIMARY KEY,
    mechanism_a TEXT,
    mechanism_b TEXT,
    relation_type TEXT,      -- mutually_exclusive/modifies/requires/overrides/converts/stacks_with
    direction TEXT,
    description TEXT
);
```

### supports.db - 辅助匹配库

```sql
CREATE TABLE support_compatibility (
    id INTEGER PRIMARY KEY,
    skill_id TEXT,
    support_id TEXT,
    compatible INTEGER,
    match_reason TEXT,
    UNIQUE(skill_id, support_id)
);

CREATE TABLE support_effects (
    support_id TEXT PRIMARY KEY,
    support_name TEXT,
    effect_category TEXT,    -- damage_more/speed/chain/crit/utility 等 15 种
    quantifiable INTEGER,    -- 1=可量化增益, 0=工具型
    key_stats TEXT,          -- 关键 stat (JSON)
    formula_impact TEXT,     -- 对 DPS 公式的影响描述
    level_scaling TEXT       -- 1/10/20 级数值 (JSON)
);

CREATE TABLE support_potential (
    id INTEGER PRIMARY KEY,
    skill_id TEXT,
    support_id TEXT,
    synergy_type TEXT,       -- mechanic_match/tag_synergy/stat_amplify
    potential_reason TEXT,
    UNIQUE(skill_id, support_id)
);
```

---

## 配置文件

### extraction_patterns.yaml

数据提取模式配置：Lua文件解析模式、字段提取规则、数据类型识别

### universal_formulas.yaml

通用公式定义：DPS计算公式、伤害转换公式、属性计算公式

### index_config.yaml

索引系统配置：索引数据库路径、性能参数、缓存设置

### mechanism_descriptions.yaml

机制行为描述的人工补充：33 条 YAML 描述，与代码提取结果合并

---

## Schema管理系统

### 概述

Schema管理系统确保数据结构定义与其消费者之间的一致性。

### 核心文件

- `schemas/schemas.json` - 结构定义中心存储
- `scripts/schema_manager.py` - 核心管理函数
- `scripts/schema_validator.py` - 验证和队列处理

### 使用方法

```python
from schema_manager import SchemaManager

manager = SchemaManager('schemas/schemas.json')

# 查询文件角色
role = manager.get_file_role('entity_index.py')

# 检查队列
if not manager.is_queue_empty():
    pass

manager.save()
```

---

## 项目统计

### 数据规模（v3.0.0）

| 组件 | 数量 |
|------|------|
| 实体总数 | 16,461 |
| 公式总数 | ~1,486 |
| 机制总数 | 44（71个含模式发现） |
| 机制关系 | 19 条 |
| 辅助兼容对 | 52,605 |
| 辅助效果 | 556 |
| 潜力推荐 | 9,762 |

### 代码规模

| 类别 | 文件数 | 代码行数 |
|------|--------|----------|
| 核心脚本 | ~25 | ~8,000 |
| 索引系统 | 8 | ~1,500 |
| 配置文件 | 4 | ~1,200 |

---

## 版本历史

### v3.0.0 (2026-03-19)

**系统升级：从"静态数据查询"升级为"数据分析汇总服务"**

新增能力：
- **实体解读层**：summary / key_mechanics / display_stats 预计算
- **StatDescriber 适配层**：lupa 运行 POB 原始 Lua 代码生成精确 stat 描述
- **机制库增强**：中文名、行为描述、分类、公式摘要、机制关系（6种关系类型）
- **辅助匹配系统**：兼容矩阵、效果分类（15种）、可量化标记、等级缩放、潜力推荐
- **查询输出层**：entity/mechanism --detail、supports、compare、reverse-stat、formula --chain
- **response_type 路由**：所有查询返回标注数据类型，指导格式化输出
- **8 种问题类型**：skill.md 定义识别规则和调用策略

修复：
- 统一 22 个 JSON 字段解析
- 移除 stat_mapping modifier 200 字符截断
- 按实体类型裁剪返回字段，去除 null 噪音

### v2.0.0 (2026-03-18)

**重大重构：从"游戏逻辑探索"转为"数据问答服务"**

删除系统：关联图、规则、验证、启发推理、查询引擎

保留系统：实体库、公式库、机制库、索引系统

### v1.0.0

初始版本，包含完整的推理和验证系统。

---

## 常见问题

### Q: 如何更新知识库到最新版本？

```bash
python scripts/init_knowledge_base.py <pob_data_dir>
```

### Q: 如何快速了解一个技能？

```bash
# 先看概览
python scripts/kb_query.py entity <skill_id> --detail summary

# 再看搭配
python scripts/kb_query.py supports <skill_id> --mode dps
```

### Q: 如何找到某个stat的计算公式？

```bash
python scripts/kb_query.py formula --stat <stat_name>
# 或
python scripts/kb_query.py reverse-stat <stat_name>
```

### Q: 如何对比两个技能？

```bash
python scripts/kb_query.py compare <id1> <id2> --detail summary
```

### Q: 知识库数据从哪里来？

所有数据都从POB（Path of Building）的源文件提取，包括：
- Lua数据文件（技能、物品、天赋定义）
- 计算模块（公式、逻辑）
- Stat映射和描述

### Q: 数据多久更新一次？

知识库不会自动更新，需要手动重新初始化以获取最新的POB数据。

---

## 许可证

本项目仅供学习和研究使用。
