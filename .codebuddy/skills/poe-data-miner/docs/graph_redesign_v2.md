# 关联图重新设计方案 v2

> 创建日期：2026-03-16
> 状态：探索阶段，方案记录

## 一、设计目标

### 核心定位
图 = **完整的正常运行逻辑**（可查询任何机制问题）+ 基于正常逻辑发现的**异常突破点**

### 三个核心功能
1. **机制查询**：回答"Meta触发怎么工作""伤害转换链是什么"
2. **异常发现**：找到"哪些实体/组合可以突破正常逻辑的限制"（高价值发现）
3. **实体定位**：具体实体属于集合，查具体机制时最终取到实体数据

### 关键认知
- 实体不被替代，实体**归属于**集合节点（可属于多个集合）
- 集合之间通过**机制边**表达正常运行逻辑
- 异常 = 某些实体/辅助/天赋/装备组合走出一条"按正常规则走不通但实际能走通"的路径
- 关键是**标签在路径上的传播和变化**——改变标签就可能改变路径可达性

## 二、SkillType 六大语义层

从 153 个唯一 skillType 分析得出：

| 语义层 | 种类数 | 总使用次数 | 角色 |
|--------|--------|-----------|------|
| **SKILL_CLASS** | 7 | 543 | 技能是什么 → **集合划分主轴** |
| **DELIVERY_METHOD** | 8 | 514 | 怎么释放 → 子分类维度 |
| **ELEMENT** | 5 | 242 | 元素类型 → 伤害转换链 |
| **META_BEHAVIOR** | 9 | 401 | Meta行为特征 → 触发/能量机制核心 |
| **COMPATIBILITY** | 6 | 394 | 能被什么方式使用 → 约束判断依据 |
| **MECHANIC_TAG** | 35 | 907 | 具体机制行为 → 标签传播对象 |

### 三者区分

```
集合 (Category):     实体的"身份"   → 静态归属，决定图上的位置
维度 (Dimension):    实体的"属性"   → 静态属性，决定约束是否满足
运行时标签 (Tag):    实体的"状态"   → 动态获得/失去，改变路径可达性
```

## 三、集合划分方案

### 一级集合定义

| # | 一级集合 | 定义条件 | 预估成员数 | 图中角色 |
|---|---------|---------|-----------|---------|
| 1 | **MeleeAttack** | Attack ∧ Melee | ~67 | 近战攻击 |
| 2 | **RangedAttack** | Attack ∧ (Ranged ∨ Projectile ∨ Bow) | ~80+ | 远程攻击 |
| 3 | **Spell** | Spell（排除Curse子集） | ~150 | 法术 |
| 4 | **Curse** | AppliesCurse（Spell的子集） | 9 | 诅咒 |
| 5 | **MetaTrigger+Energy** | Meta ∧ Triggers ∧ GeneratesEnergy | 11 | 触发型Meta（能量系统） |
| 6 | **Invocation** | Meta ∧ Invocation | 5 | 调用型Meta |
| 7 | **Totem** | Meta ∧ SummonsTotem 相关 | 3+ | 图腾Meta |
| 8 | **Blasphemy** | Meta ∧ IsBlasphemy | 1 | 诅咒→光环转换 |
| 9 | **Aura** | HasReservation ∧ Buff ∧ Persistent | ~40+ | 光环 |
| 10 | **Minion** | Minion | ~59 | 召唤物 |
| 11 | **Trap** | Trappable 系统 | 间接 | 陷阱投放 |
| 12 | **Mine** | Mineable 系统 | 间接 | 地雷投放 |
| 13 | **Warcry** | Warcry | ~14 | 战吼 |
| 14 | **Herald** | Herald | ~5 | 先驱 |
| 15 | **Guard** | Guard | ~1 | 防御技能 |

### 决策记录
- **Attack 拆分为 Melee/Ranged** ✅ 已确认
- **Trap/Mine 不合并** ✅ 已确认
- 一个实体可以 `belongs_to` 多个集合（如诅咒同时属于 Curse 和 Spell）

### 集合层级关系

集合之间存在 `is_subset_of` 关系：

```
Curse ──is_subset_of──> Spell        （所有诅咒都是法术）
Invocation ──is_subset_of──> Meta    （调用是Meta的子类）
Totem ──is_subset_of──> Meta         （图腾是Meta的子类）
Blasphemy ──is_subset_of──> Meta     （亵渎是Meta的子类）
MetaTrigger+Energy ──is_subset_of──> Meta
MeleeAttack ──is_subset_of──> Attack（虚拟父级）
RangedAttack ──is_subset_of──> Attack（虚拟父级）
```

层级关系的意义：
- 父集合的机制边可以被子集合继承
- 子集合可以有自己的特殊机制边
- 异常可能出现在子集合覆盖/绕过父集合规则时

## 四、节点类型

| 节点类型 | 说明 | 数量级 |
|---------|------|-------|
| `category` | 一级集合节点 | ~15-20 |
| `entity` | 具体技能/辅助/物品/天赋 | ~16,000 |
| `constraint` | 约束条件（路径通行条件） | ~50-100 |
| `tag` | 运行时标签（动态获得/失去） | ~30-50 |

## 五、边类型

### 结构边
| 边类型 | 含义 | 示例 |
|--------|------|------|
| `belongs_to` | 实体归属集合 | CastOnCrit → MetaTrigger+Energy |
| `is_subset_of` | 子集合关系 | Curse → Spell |

### 机制边（集合之间的正常逻辑）
| 边类型 | 含义 | 示例 |
|--------|------|------|
| `triggers` | 触发关系 | MetaTrigger → Spell |
| `produces_energy` | 产生能量 | MeleeAttack → MetaTrigger |
| `converts_to` | 伤害转换 | （预留，对应伤害转换链） |
| `summons` | 召唤关系 | （预留，Minion相关） |
| `reserves` | 预留资源 | Aura → Spirit/Mana |
| `deploys_as` | 部署方式 | Trap/Mine → 目标技能 |
| `grants_buff` | 给予增益 | Aura → 影响范围内实体 |
| `applies_effect` | 施加效果 | Curse → 诅咒效果 |

### 约束边
| 边类型 | 含义 | 示例 |
|--------|------|------|
| `requires_tag` | 需要目标有某标签 | triggers边要求 target 有 Triggerable |
| `adds_tag` | 给目标添加标签 | triggers边给 target 添加 Triggered |
| `blocks_when` | 条件阻断 | Triggered标签阻断 produces_energy |
| `excludes_tag` | 排除某标签 | triggers边排除 InbuiltTrigger |

### 改变者边
| 边类型 | 含义 | 属性 |
|--------|------|------|
| `modifies` | 改变标签/机制 | modifier_source, scope, effect |

**改变者表达方式已确认**：统一 `modifies` 边 + 属性区分（方案A）。 ✅

> **modifies 边的属性字段**（统一方案）：
> - `modifier_source`: "support" \| "passive" \| "item" \| "mod_affix"
> - `scope`: "linked_skill"（仅被辅助技能）\| "all_skills"（全局）\| "category"（整个集合）
> - `effect`: 具体效果描述

## 六、改变者识别方案 ✅ 已确认

### POB 数据处理链（核心发现）

POB 内部有完整的 **文本 → 结构化修饰符** 处理链：

```
Layer A: 原始文本描述
  天赋 tree.json:  stats: ["Invocation Skills instead Trigger Spells every 2 seconds"]
  唯一物品 Uniques/*.lua:  "Enemies Ignited by you take Chaos Damage instead of Fire"
  Mod词缀:  "10% of Physical Damage Converted to Cold Damage"
  
  ↓ ModParser.lua 解析 ↓

Layer B: ModCache.lua — 结构化修饰符缓存（6,251条目）
  86% (5,391) 被解析为 {name, type, value, flags, keywordFlags, conditions}
  14% (860) 为 nil（POB 自身也未实现，只保留文本）
  
  ↓ 被计算模块引用 ↓

Layer C: SkillStatMap.lua + Calc*.lua — 实际计算
```

### 改变者的四个来源

| 来源 | 数据来源 | 识别方法 | 数量 | 自动化 |
|------|---------|---------|------|--------|
| **Support** | `add_skill_types` 字段 | 直接读取结构化数据 | 63 真实改变者 | 全自动 |
| **Passive** | `stat_descriptions` → ModCache | 查表获取结构化 mod | 5,384 有解析 (94%) | 全自动 |
| **Unique** | Uniques/*.lua 词缀文本 → ModCache | 查表获取结构化 mod | 待提取 | 全自动 |
| **Mod词缀** | `stat_descriptions` → 关键词匹配 | 匹配率低(2%)，走兜底 | ~27 机制相关 | 半自动 |

### 三层识别策略

```
Layer 1（全自动，100%置信度）:
  Support add_skill_types → 63个改变者
  直接获取添加的标签，精确知道机制改变内容

Layer 2（全自动，94%置信度）:
  天赋/唯一 stat_descriptions → ModCache 查表
  天赋命中率 99%，其中 94% 有结构化 mod
  从结构化 mod 提取：
    - type="FLAG" → 开关型改变（如 NoEnergyShieldRecharge）
    - type="LIST" + SkillType → 技能类型级改变
    - name含"Convert" → 转换类改变
    - conditions含SkillType → 精确知道影响哪个集合

Layer 3（半自动，文本兜底）:
  ModCache nil 条目（~80条需关注）
  分类：instead(51) + trigger(23) + count_as(3) + restriction(45)
  这些是 POB 自身也未模拟的效果
  用精确关键词模式提取，少量人工确认
```

### 判断标准：哪些是"机制改变者"？

```
✅ 是改变者（参与图的 modifies 边）：
  - FLAG 型 mod：改变开关状态
  - 含 SkillType 条件的 mod：改变特定类型技能的行为
  - name 含 Convert/Transform 的 mod：改变伤害/行为类型
  - instead/count as 文本（nil 兜底）：行为替换

❌ 不是改变者（不参与图）：
  - BASE/INC/MORE 型纯数值 mod："20% increased damage"
  - 无 SkillType 条件的通用数值加成
```

### 数据匹配率验证

| 实体类型 | 描述条目总数 | ModCache 命中率 | 结构化解析率 |
|---------|------------|---------------|------------|
| passive_node | 5,709 | **99%** (5,689) | 94% (5,384) |
| mod_affix | 2,829 | 2% (80) | — 格式不匹配 |
| unique_item | — | — | 需从 Uniques/*.lua 提取 |

### 待补充扫描

```
唯一物品：
  当前 entities.db 的 unique_item.stats 存的是 Mod ID（装备模板），
  不是唯一物品特殊词缀。
  需要从 POBData/Data/Uniques/*.lua 提取文本词缀行，
  然后走 Layer 2/3 流程。
```

### 天赋改变集合行为的关键例子
```
Ritual Cadence: 
  "Invocation Skills instead Trigger Spells every 2 seconds"
  "Invocation Skills cannot gain Energy while Triggering Spells"
  → ModCache: nil（POB未实现模拟）
  → 走 Layer 3 文本匹配兜底
  → 识别为改变者：scope=category(Invocation), effect=behavior_replace
```

## 七、异常发现机制

### 原理
1. 图上有 ~125 条 blocks_when 约束（四层自动提取）
2. 每条约束定义了"什么条件下路径被阻断"
3. 改变者（Support/天赋/装备）可以修改标签传播
4. 如果修改后约束不再生效 → 路径打通 → 异常发现

### 搜索基础

blocks_when 约束是异常发现的**搜索起点**。图初始化后自动拥有 ~125 条约束，
不需要手动种子。bypasses 异常是算法的**输出**，不是输入。

```
图初始化完成后的状态：
  集合节点: ~15-20
  实体节点: ~1,400 参与图结构
  机制边: ~150+（triggers/deploys_as/reserves/applies_effect/produces_energy）
  blocks_when 约束: ~125（四层自动提取）
  改变者 modifies 边: ~300+（Support 63 + 天赋 184 + 装备/Mod）
  bypasses 异常: 0（待算法发现）
```

### 经典案例：德瑞+诅咒绕过能量限制

```
正常路径（被阻断）：
  MetaTrigger --triggers--> Spell --[adds Triggered tag]
  Spell(Triggered) --produces_energy--> MetaTrigger
    ↑ blocked_by: con_triggered_no_energy

异常路径（Doedre's Undoing打通）：
  Doedre's Undoing --modifies--> Curse集合
    effect: add_tag(Hazard)
    scope: linked_skill
    
  Curse ∈ Spell（子集关系）
  MetaTrigger(CurseOnBlock) --triggers--> Curse --[adds Hazard tag, 非Triggered路径]
  Curse(Hazard) --produces_energy--> MetaTrigger ✅
    约束 con_triggered_no_energy 不生效（因为标签是Hazard不是Triggered）
```

### 异常发现算法
详见**第十五节**。核心流程：step9 恢复存档 → step10 暴力遍历 → 后处理回写存档。

## 八、适用的机制领域

| 机制领域 | 涉及的集合 | 核心机制边 |
|---------|-----------|-----------|
| 触发+能量 | MetaTrigger, Spell, MeleeAttack, RangedAttack, Curse | triggers, produces_energy |
| 防御机制 | Guard, Aura, 天赋 | applies_defense, mitigates |
| 召唤物 | Minion | summons, inherits |
| 光环/保留 | Aura, Herald, Blasphemy | reserves, grants_buff |
| 陷阱/地雷 | Trap, Mine | deploys_as, detonates |
| 诅咒系统 | Curse, Blasphemy | applies_effect, curse_limit |

### 决策记录
- **mechanisms.db 的44个机制**（伤害转换/承受转换等）**暂不作为机制边** ✅ 已确认
  - 理由：这些是数值计算层面的机制，不是技能交互层面的机制
  - 后续可以作为独立的"伤害计算图"补充

## 九、数据来源映射

| 图中的数据 | 来源 |
|-----------|------|
| 集合定义 | skillTypes 组合模式（半自动+人工确认） |
| 实体归属 | entities.db 的 skillTypes 字段（全自动） |
| 机制边 | skillTypes标签推导 + CalcTriggers configTable + centienergy stat（全自动+半自动） |
| 约束（requires/excludes） | requireSkillTypes / excludeSkillTypes（全自动） |
| 约束（blocks_when） | exclude_skill_types + SkillStatMap cannot + Calc代码 + stat_descriptions（四层，~125条） |
| 标签传播 | addSkillTypes（全自动） |
| Support改变者 | entities.db add_skill_types（全自动） |
| 天赋改变者 | stat_descriptions → **ModCache.lua 查表** → 结构化 mod（全自动94%） |
| 装备改变者 | Uniques/*.lua 词缀文本 → **ModCache.lua 查表**（全自动） |
| Mod词缀改变者 | stat_descriptions 关键词匹配（半自动） |
| 未解析的改变者 | ModCache nil 条目 → 文本模式匹配兜底（半自动，~80条） |
| bypasses异常 | GraphBuilder step9恢复存档 + step10暴力遍历发现（图构建后运行） |

## 十、约束提取方案

### 数据来源

约束来自 entities.db 的三个字段，仅 `skill_definition` 类型有值（537个实体）：

| 字段 | 语义 | 作用 |
|------|------|------|
| `require_skill_types` | 目标必须有这些标签 | 入口约束（能不能走这条边） |
| `exclude_skill_types` | 目标不能有这些标签 | 阻断约束（有这个标签就走不通） |
| `add_skill_types` | 给目标添加这些标签 | 标签传播（走过之后状态改变） |

### AND/OR 逻辑

- **默认 OR**：`["Damage", "Attack", "CrossbowAmmoSkill"]` → 有任意一个即可
- **显式 AND**：`["Attack", "Bow", "AND"]` → 必须同时满足（87个实体用 AND）
- **偶尔 NOT**：`["Triggered", ..., "NOT", "AND"]` → 极少数（Rally等）

### 标签→集合映射表 ✅ 已确认

```yaml
tag_to_category:
  # 核心集合映射
  Attack: [MeleeAttack, RangedAttack]
  Melee: [MeleeAttack]
  RangedAttack: [RangedAttack]
  Spell: [Spell]
  AppliesCurse: [Curse]
  SummonsTotem: [Totem]
  Warcry: [Warcry]
  CreatesMinion: [Minion]
  Herald: [Herald]
  
  # 非集合标签（维度/兼容性/武器限定）
  Damage: null            # 兼容性
  Projectile: null        # 投放方式
  CrossbowAmmoSkill: null # 武器限定
  CrossbowSkill: null     # 武器限定
  Persistent: null        # 行为特征
  Buff: null              # 行为特征
  Triggerable: null       # 兼容性
  # ... 其余按同样逻辑分类
```

### 约束归纳规则 ✅ 已确认：合并

537个实体级约束 → 归纳为集合级约束。

归纳逻辑：相同 require 模式的多个实体 → 一条集合级约束。例：
- 53个 Support 都 require `[Damage,Attack,CrossbowAmmoSkill]` → **"弩箭Support群 → 只对Attack集合有效"**
- 8个 Meta 都 require `[Triggerable,Spell,AND]` → **"MetaTrigger集合 → 只能触发Spell且Triggerable"**

### Meta约束特殊处理 ✅ 已确认

Meta 约束不是普通的"Support能不能辅助某技能"，而是定义了**集合间机制边的通行条件**。

处理方式：
1. Meta 的 require → 成为 `triggers` 机制边的 **requires_tag** 属性
2. Meta 的 exclude → 成为 `triggers` 机制边的 **excludes_tag** 属性
3. Meta 的 add → 成为 `triggers` 机制边的 **adds_tag** 属性（标签传播）

```
MetaCastOnCrit:
  require: [Triggerable, Spell, AND]
  exclude: [InbuiltTrigger]
  add: [Triggered]

→ 图中表达为：
  MetaTrigger+Energy集合 --[triggers]--> Spell集合
    requires_tag: [Triggerable, Spell]  (AND)
    excludes_tag: [InbuiltTrigger]
    adds_tag: [Triggered]
```

而普通 Support 的约束表达为实体属性：
```
SupportBlindI:
  require: [Damage, Attack, CrossbowAmmoSkill]

→ 图中表达为：
  SupportBlindI 实体节点上的属性：
    constraint: {require: [Damage, Attack, CrossbowAmmoSkill], logic: OR}
```

### 约束提取流程（全自动部分）

```
Step 1: 读取 entities.db 所有 require/exclude/add 字段
Step 2: 识别 AND/OR/NOT 逻辑
Step 3: 通过 tag_to_category 映射表，将标签转换为集合引用
Step 4: 分类：
  - 含 Meta skillType 的实体 → Meta约束（特殊处理）
  - 其余 → Support约束（普通处理）
Step 5: 合并相同模式的约束 → 集合级约束
Step 6: Meta约束 → 附加到集合间的机制边上
Step 7: Support约束 → 附加到实体节点上（或归纳为Support群的共性约束）
```

## 十一、成员归属方案 ✅ 已确认

### 参与范围

并非所有 16,000+ 实体都需要 `belongs_to` 集合。只有**直接参与技能交互**的实体需要：

| 实体类型 | 数量 | 参与方式 |
|---------|------|---------|
| Active skill_definition（非Support） | ~344 | `belongs_to` 集合 |
| Support skill_definition | ~556 | 不属于集合，见 Support 参与规则 |
| Minion skill_definition | ~496 | `belongs_to` Minion |
| passive_node | ~4,313 | 仅机制改变者参与（~184个） |
| unique_item | ~474 | 仅机制改变者参与 |
| mod_affix | ~2,570 | 仅机制改变者参与（~27个） |
| 其他 | ~7,000+ | 不参与图结构 |

### 归属规则（全自动）

Active 技能通过 `skillTypes` 直接匹配集合定义条件：

```
规则示例：
  skillTypes 含 Attack ∧ Melee → belongs_to MeleeAttack
  skillTypes 含 Attack ∧ (Ranged ∨ Projectile ∨ Bow) → belongs_to RangedAttack
  skillTypes 含 Spell → belongs_to Spell
  skillTypes 含 AppliesCurse → belongs_to Curse（同时也 belongs_to Spell）
  skillTypes 含 Meta ∧ Triggers ∧ GeneratesEnergy → belongs_to MetaTrigger+Energy
```

- 多集合归属正常（111个实体属于 2+ 集合）
- skill_definition 的 skillTypes 数据完整，无需 gem_definition 补充

### 集合粒度与约束的关系 ✅ 已确认

**不需要为行为标签建子集合**。约束系统已精确过滤：

```
例：88个法术中只有60个(68%)有 Triggerable 标签
  MetaTrigger --[triggers]--> Spell
    requires_tag: [Triggerable]  ← 这个约束过滤掉了 Channel/Sustained 等
  
  → 不需要建 TriggerableSpell 子集合
```

子集合只用于有**独立机制域**的情况（如 Curse ⊂ Spell 有独立诅咒机制）。

## 十二、Support 图参与规则 ✅ 已确认

Support 不属于任何集合，但按三层参与图：

| 层次 | 条件 | 数量 | 参与方式 |
|------|------|------|---------|
| **标签改变者** | `add_skill_types` 有真实机制标签（非 SupportedByX） | ~63 | `modifies` 边 |
| **约束载体** | `require_skill_types` 有值 | 537 | 约束信息归纳到集合级 |
| **纯数值** | 无 add，仅数值增减 | ~480 | **不参与图** |

### 区分标准

```
改变者：改变了技能的标签集合 → 可能改变路径可达性
  例：Doedre's Undoing adds [Hazard, Limit] → 绕过 Triggered 约束

纯数值：只有 more/less/increased/decreased → 路径可达性不变
  例：Added Fire Damage Support → 20% more Fire Damage
```

### Support 添加的标签 TOP 分布

| 添加的标签 | Support数量 | 机制影响 |
|-----------|------------|---------|
| Duration | 25 | 给技能加上持续时间行为 |
| Cooldown | 8 | 给技能加上冷却 |
| Area | 7 | 给技能加上范围属性 |
| CreatesGroundEffect | 5 | 改变投放方式 |
| ComboStacking | 4 | 改变成连击机制 |
| HasSeals | 4 | 改变成蓄力机制 |
| Hazard + Limit | 1 | **高价值**：绕过 Triggered 约束 |
| Triggers | 1 | **高价值**：添加触发能力 |

## 十三、自动化程度总览

| 自动化任务 | 输入 | 自动化程度 | 状态 |
|-----------|------|-----------|------|
| 约束提取 | entities.db require/exclude/add | **全自动** | 方案已确认 ✅ |
| 成员归属 | entities.db skillTypes | **全自动** | 方案已确认 ✅ |
| Support参与分层 | add_skill_types 是否有真实标签 | **全自动** | 方案已确认 ✅ |
| 集合粒度 | 约束系统过滤 vs 子集合 | 设计决策 | 已确认：约束过滤 ✅ |
| 一级集合识别 | skillTypes组合模式 | 半自动+人工 | 待讨论 |
| 机制边发现 | skillTypes标签 + CalcTriggers configTable + centienergy stat | **Step1-2全自动 + Step3半自动** | 方案已确认 ✅ |
| blocks_when 约束 | exclude_skill_types + SkillStatMap + Calc代码 + stat_descriptions | **Layer1-2全自动 + Layer3-4半自动** | 方案已确认 ✅ |
| 改变者识别 | add_skill_types + ModCache查表 + 文本兜底 | **全自动(94%) + 半自动(6%)** | 方案已确认 ✅ |
| 异常路径发现 | GraphBuilder step9恢复+step10暴力遍历 | 全自动 | 方案已确认 ✅ |

## 十四、机制边发现方案 ✅ 已确认

### 核心原则

**不需要分析代码执行分支，只需从实体的声明式数据中提取。**

CalcTriggers.lua 的 `configTable`（第881-1416行）是整个 Modules 目录中唯一的声明式配置表。
其他机制（Trap/Mine/Totem/Aura/Curse/Minion/Blasphemy）全部是散布多文件的过程式 `if skillFlags.xxx` 分支，
但它们的"谁对谁生效"关系已编码在 skillTypes 标签中，不需要解析代码。

### 四步提取方案

#### Step 1（全自动，零难度）: skillTypes 标签推导

数据源：entities.db skillTypes 字段

| 机制边 | 推导逻辑 | 预估数量 |
|--------|---------|---------|
| `deploys_as` → Trap | skillTypes 含 Trappable | ~75 技能 |
| `deploys_as` → Mine | skillTypes 含 Mineable | ~70 技能 |
| `summons_for` → Totem | skillTypes 含 Totemable | ~83 技能 |
| `reserves` | skillTypes 含 HasReservation | 79 技能（74 Aura + 5 Herald）|
| `applies_effect` → Curse | skillTypes 含 AppliesCurse | 9 技能 |
| `converts_to` | Blasphemy 的 addSkillTypes 含 HasReservation, Aura | 1（Curse → Aura 转换）|

#### Step 2（全自动，低难度）: CalcTriggers configTable 解析

数据源：CalcTriggers.lua 第881-1416行，约40个声明式条目

方法：正则提取 `triggerSkillCond` 中的 `SkillType.XXX` 条件

```lua
-- 示例：Cast on Critical Strike (第1089-1091行)
["cast on critical strike"] = function()
    return {
        triggerSkillCond = function(env, skill)
            return skill.skillTypes[SkillType.Attack] and slotMatch(env, skill)
        end,
        triggeredSkillCond = function(env, skill)
            return skill.skillData.triggeredByCoc and slotMatch(env, skill)
        end
    }
end,
```

产出：triggers 机制边（~40条），每条包含源集合条件和目标集合条件

关键 triggerSkillCond 中出现的 SkillType：
- `Attack` — 最常见（Mjolner, Cast on Crit, Manaforged Arrows 等）
- `Melee` — 近战触发（Cospri's, Shockwave, Battlemage's Cry）
- `Damage` — 通用伤害型（常组合 `Damage or Attack`）
- `Spell` — 被触发侧（Poet's Pen, Asenath's Chant）
- `Hex` — 诅咒触发（Vixen's Entrapment, Doom Blast）
- `RangedAttack` — Maloney's Mechanism 被触发侧

#### Step 3（半自动，~10个）: Meta centienergy stat 解析 → produces_energy

数据源：Data/Skills/act_*.lua 中 Meta 技能的 constantStats

每个 Meta 技能在 constantStats 中声明 centienergy stat，名称编码了能量获取条件：

| Meta 技能 | centienergy stat | 产能条件 | 来源集合 |
|-----------|-----------------|---------|---------|
| Cast on Critical | `..._on_crit` | 暴击时 | MeleeAttack + RangedAttack + Spell |
| Cast on Melee Kill | `..._on_melee_kill` | 近战击杀 | MeleeAttack |
| Cast on Block | `..._on_block` | 格挡时 | 被动行为 |
| Cast on Melee Stun | `..._on_melee_stun` | 近战眩晕 | MeleeAttack |
| Feral Invocation | `..._per_mana_spent` | 消耗法力 | 所有耗蓝技能 |
| Barrier Invocation | `..._per_ES_damage_taken` | 受ES伤害 | 被动行为 |
| Cast on Dodge Roll | `..._per_unit_travelled` | 翻滚距离 | 翻滚行为 |

**注意**：centienergy stat 名称给出方向但不完全精确。
例如 `on_crit` 是"暴击时"，**法术和攻击都能暴击**，不限于 Attack。
每个 Meta 技能（约10个）需要手动确认精确的产能来源集合。

可与 Step 2 的 CalcTriggers triggerSkillCond 交叉验证（但注意 triggerSkillCond 是 POB 触发速率计算条件，不完全等于游戏的产能条件）。

#### Step 4（四层自动提取）: blocks_when 约束 ✅ 已确认

**关键发现**：blocks_when 约束远不止最初以为的 1 条，实际上有 ~125 条，
而且绝大部分可以自动提取。数据源比预想的丰富得多。

**Layer 1（全自动，100%结构化）: exclude_skill_types**

数据源：entities.db exclude_skill_types 字段
数量：204个实体，85种排除标签

exclude_skill_types **本身就是结构化的 blocks_when**——
"有这个标签就不能被该 Support 辅助"直接映射为阻断约束。

```
排除频率 TOP（与机制直接相关）：
  Persistent:   103 → 持续效果 blocks 这些Support辅助
  Triggered:    100 → 已触发   blocks 这些Support辅助
  UsedByTotem:   97 → 图腾使用 blocks 这些Support辅助
  SummonsTotem:  76 → 召唤图腾 blocks 这些Support辅助
  Trapped:       47 → 陷阱化   blocks 这些Support辅助
  RemoteMined:   47 → 地雷化   blocks 这些Support辅助
  Minion:        41 → 召唤物   blocks 这些Support辅助
  Channel:       18 → 引导     blocks 这些Support辅助
  Meta:          13 → 元技能   blocks 这些Support辅助
  HasReservation:12 → 保留技能 blocks 这些Support辅助
```

归纳方法：相同排除模式的实体合并为集合级约束（与约束提取方案一致）。

**Layer 2（全自动，结构化）: SkillStatMap cannot stat**

数据源：SkillStatMap.lua
数量：35+ 个 cannot/never/dealNo stat 映射

```
游戏引擎级阻断：
  global_cannot_crit        → NeverCrit        → blocks 暴击
  deal_no_elemental_damage  → DealNoFire/Cold/Lightning → blocks 元素伤害
  cannot_pierce             → CannotPierce     → blocks 穿透
  cannot_inflict_status_ailments → CannotShock/Ignite/Freeze → blocks 异常施加
  cannot_be_stunned         → StunImmune       → blocks 被眩晕
  cannot_recharge_energy_shield → NoESRecharge → blocks ES充能
  ... 共 35+ 条
```

**Layer 3（半自动，一次性提取）: Calc 代码中的 if-not 模式**

数据源：CalcOffence / CalcPerform / CalcTriggers / CalcDefence
数量：~15 条

```
核心代码阻断：
  trap/mine/totem → blocks 标准吸取     (CalcOffence:3893)
  trap/mine/totem → blocks 击中回复     (CalcOffence:4021)
  trap/mine/totem → blocks 击杀回复     (CalcOffence:4035)
  trap/mine/totem/triggered → blocks "最近"条件 (CalcPerform:249)
  Triggered → blocks 触发源资格         (CalcTriggers:40)
  totem → blocks Buff传递给玩家         (CalcPerform:1821)
```

一次性提取后固化，不需要反复解析代码。

**Layer 4（半自动，与改变者识别共用管道）: stat_descriptions cannot/instead/immune**

数据源：entities.db stat_descriptions → ModCache 查表
数量：~70 条（28 cannot + 31 instead + 12 immune）

```
天赋/装备级阻断：
  "Invocation Skills cannot gain Energy while Triggering Spells"  (Ritual Cadence)
  "Cannot gain Spirit from Equipment"                             (Lead me through Grace)
  "Cannot Dodge Roll or Sprint"                                   (Unwavering Stance)
  "Cannot use Life Flasks"                                        (Vaal Pact)
  "Your Life cannot change while you have Energy Shield"          (Eternal Life)
  "Immune to Poison"                                              (Toxic Tolerance)
  "Immune to Chaos Damage and Bleeding"                           (Chaos Inoculation)
  "Offerings affect you instead of your Minions"                  (Blackened Heart)
  "Ignite deals Chaos Damage instead of Fire Damage"              (Blackflame Covenant)
  ... 共 ~70 条
```

这些与改变者识别的 Layer 3（ModCache nil 兜底）使用同一个文本管道。

**约束总量预估**：

```
Layer 1: ~25 条（exclude_skill_types 归纳后）
Layer 2: ~35 条（SkillStatMap cannot stat）
Layer 3: ~15 条（Calc 代码一次性提取）
Layer 4: ~50 条（stat_descriptions 文本提取）
——————————————————————————————
合计: ~125 条 blocks_when 约束
```

#### Step 5: predefined_edges.yaml — 异常发现存档，参与图构建 ✅

**角色**：异常发现的**持久化存档**，版本更新重建时**恢复历史异常到图中**。

每次图重建都可能因数据变化导致算法跑不出之前确认过的异常，但这些异常在游戏中
可能仍然成立。predefined_edges.yaml 保证已发现的知识不会因重建而丢失。

**在构建流程中的位置**：step9（恢复）+ step10（发现）后的后处理

```
构建时：
  step9_restore_archive():
    加载 predefined_edges.yaml → 历史异常写入图（恢复完整性）

  step10_discover_anomalies():
    暴力遍历 → 发现新异常 → 写入图

后处理：
  _postprocess_archive():
    对比 step10 结果与存档 → 合并状态 → 回写 predefined_edges.yaml
    三种状态：
      存档有 ∩ 算法有 → confirmed（双重验证，高置信）
      存档有 ∩ 算法没有 → pending_review（数据可能变了，仍在图中）
      算法有 ∩ 存档没有 → new_discovery（新发现）
```

**predefined_edges.yaml v2 结构**：

```yaml
metadata:
  version: "2.0.0"
  last_updated: "2026-03-17"
  game_version: "0.4.0"
  description: "异常发现存档 — 版本更新重建时恢复历史异常"

anomalies:
  - id: "hazard_bypasses_triggered"
    constraint: "con_triggered_no_energy"
    modifier: "Doedre's Undoing"
    mechanism: "Hazard标签替代Triggered，绕过产能约束"
    value_score: 3
    status: "confirmed"          # confirmed / pending_review / new_discovery
    discovered_version: "0.4.0"
    last_verified_version: "0.4.0"
```

**与 v1 的区别**：
- v1 存各种种子边（triggers/blocks/reserves/formula）→ 全部被自动提取覆盖，已移除
- v2 **只存 anomalies（异常路径）**，这是唯一无法从数据自动重现的知识
- v1 的 `_load_predefined_edges()` 方法重写为存档合并逻辑

### 代码解析架构对比

| 机制 | 有集中配置表？ | 代码模式 | 机制边提取方式 |
|------|--------------|---------|-------------|
| **Trigger** | ✅ configTable | 声明式 | 解析 configTable |
| **Trap/Mine** | ❌ | `if skillFlags.trap/mine` 散布 4+ 文件 | skillTypes 标签 |
| **Totem** | ❌ | `if skillFlags.totem` 散布 5+ 文件 | skillTypes 标签 |
| **Aura/Reserve** | ❌ | 过程式大函数 ~140行 | skillTypes 标签 |
| **Curse** | ❌ | 嵌入 buff 处理循环 | skillTypes 标签 |
| **Minion** | ❌ | CalcActiveSkill 200行过程式 | skillTypes 标签 |
| **Blasphemy** | ❌ | 嵌入 reservation/curse 分支 | skillTypes 标签 |
| **Energy** | ❌ | **POB 大部分未实现** | centienergy stat + 手动确认 |

### 自动化程度

```
Step 1: 100% 自动 — skillTypes 标签直接查询
Step 2: 100% 自动 — 正则提取 configTable
Step 3:  半自动  — stat 名称解析 + ~10个手动确认
Step 4: Layer 1-2 全自动 + Layer 3-4 半自动 — ~125条约束
Step 5: 自动   — predefined_edges.yaml 存档恢复+合并（step7内执行）
```

## 十五、异常路径发现算法 ✅ 已确认

### 核心思路：暴力遍历

在当前规模下（~125 blocks_when × ~300 modifiers = 37,500 组合），暴力遍历完全可行，
**不做优化以避免功能错误**。

### 算法流程

分三个阶段，对应 GraphBuilder 的 step9 + step10 + 后处理：

```
=== step9_restore_archive() — 构建时恢复 ===

Input: config/predefined_edges.yaml 存档
Logic:
  for each archived_anomaly in archive:
    写入 graph.db（bypasses 边 + anomaly_paths 表）
    标记 source = "archive"
Output: 图中包含所有历史已知异常


=== step10_discover_anomalies() — 暴力遍历发现 ===

Input:
  constraints: 图中 blocks_when 边（~125条）
  modifiers: 图中 modifies 边（~300+条）

Logic:
  for each constraint in constraints:
    for each modifier in modifiers:
      if modifier.effect 能影响 constraint.condition_tag:
        new_tag_state = simulate_tag_propagation(modifier)
        if not constraint.evaluate(new_tag_state):
          discovered.append({constraint, modifier, path})

  for each anomaly in discovered:
    if not already_in_graph(anomaly):    # 排除 step9 已恢复的
      写入 graph.db（bypasses 边 + anomaly_paths 表）
      标记 source = "algorithm"

Output: 图中补充新发现的异常


=== _postprocess_archive() — 后处理回写 ===

Input:
  step10 发现结果
  当前 predefined_edges.yaml 存档

Logic:
  对比合并：
    存档有 ∩ 算法有 → status = "confirmed"（双重验证）
    存档有 ∩ 算法没有 → status = "pending_review"（数据可能变了）
    算法有 ∩ 存档没有 → status = "new_discovery"（新发现）
  
  累积更新回写 predefined_edges.yaml

Output: 存档文件更新
```

### 价值评分

| 异常类型 | 分值 | 说明 |
|---------|------|------|
| **形成循环** | 高 (3) | 例：触发→产能→触发，形成自循环引擎 |
| **多路径解锁** | 中 (2) | 一个改变者同时绕过多条约束 |
| **单条件绕过** | 低 (1) | 只绕过单一约束 |

### 性能估算

```
组合数: ~125 × ~300 = 37,500
每次检查: O(1)（标签集合比较）
总计: ~37,500 次简单操作 → 毫秒级完成
```

### 验证基准

算法应能自动发现以下已知异常：
- Doedre's Undoing + Curse → Hazard 绕过 Triggered 产能约束
- （更多异常由算法发现后补充）

## 十六、具体实现方案 ✅ 已确认

### 核心原则：在老文件上修改，不创建多余新文件

### 三个维度

#### 维度一：数据库变更

| 数据库 | 操作 | 说明 |
|--------|------|------|
| **entities.db** | 不变 | 数据来源，不修改 |
| **formulas.db** | 不变 | 公式库，不修改 |
| **graph.db** | 删除重建 | 新 Schema，4种节点类型，15种边类型 |
| **rules.db** | 保留，不参与图构建 ✅ | rules_extractor.py 独立运行 |
| **mechanisms.db** | 保留 | 44个机制，后续可独立使用 |

#### graph.db 新 Schema

```sql
-- 节点表
CREATE TABLE graph_nodes (
    node_id TEXT PRIMARY KEY,
    node_type TEXT NOT NULL,      -- category / entity / constraint / tag
    name TEXT NOT NULL,
    properties TEXT,              -- JSON: 集合定义条件、约束条件等
    source TEXT,                  -- 数据来源标记
    created_at TEXT DEFAULT (datetime('now'))
);

-- 边表
CREATE TABLE graph_edges (
    edge_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    edge_type TEXT NOT NULL,      -- 15种边类型
    properties TEXT,              -- JSON: requires_tag, adds_tag 等
    confidence REAL DEFAULT 1.0,
    source TEXT,                  -- 数据来源标记
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (source_id) REFERENCES graph_nodes(node_id),
    FOREIGN KEY (target_id) REFERENCES graph_nodes(node_id)
);

-- 异常路径表（新增）
CREATE TABLE anomaly_paths (
    anomaly_id TEXT PRIMARY KEY,
    constraint_id TEXT NOT NULL,  -- 被绕过的约束
    modifier_id TEXT NOT NULL,    -- 触发绕过的改变者
    mechanism TEXT NOT NULL,      -- 绕过机制描述
    path_description TEXT,        -- 完整路径描述
    value_score INTEGER,          -- 价值评分 (1-3)
    discovered_at TEXT DEFAULT (datetime('now')),
    verified BOOLEAN DEFAULT 0
);

-- 索引
CREATE INDEX idx_nodes_type ON graph_nodes(node_type);
CREATE INDEX idx_edges_source ON graph_edges(source_id);
CREATE INDEX idx_edges_target ON graph_edges(target_id);
CREATE INDEX idx_edges_type ON graph_edges(edge_type);
CREATE INDEX idx_anomaly_value ON anomaly_paths(value_score DESC);
```

#### 维度二：脚本变更

| 脚本 | 操作 | 说明 |
|------|------|------|
| **attribute_graph.py** | 在原文件上重写 | GraphBuilder 替代 AttributeGraph，含异常发现逻辑 |
| **init_knowledge_base.py** | 修改 Step 4 | 调用 GraphBuilder 替代旧逻辑，删除 Step 5-8 旧函数 |
| `build_type_layer()` 等 | 删除 | init_knowledge_base.py 中的旧 Step 6-8 函数 |
| **seed_knowledge_verifier.py** | 删除 | 旧的种子验证，功能被自动提取覆盖 |
| **generate_graph_from_rules.py** | 删除 | 旧的规则→图，被 GraphBuilder 替代 |
| **heuristic_*.py（5个文件）** | 全部删除 ✅ | heuristic_query/discovery/diffuse/reason/config_loader |
| **test_phase2_integration.py** | 删除 | heuristic 测试，随 heuristic 一起清理 |
| **test_heuristic_reasoning.py** | 删除 | heuristic 测试 |
| **config/predefined_edges.yaml** | 重写为 v2 格式 | 异常发现存档，参与 step7 合并+恢复 |
| **config/heuristic_config.yaml** | 删除 | heuristic 配置 |
| **config/heuristic_records.yaml** | 删除 | heuristic 记录 |

**不创建新文件**：
- ~~anomaly_scanner.py~~ → 异常发现逻辑直接写在 `attribute_graph.py` 的 GraphBuilder 中
- ~~graph_builder.py~~ → 直接在 `attribute_graph.py` 上重写

#### GraphBuilder（在 attribute_graph.py 中实现）

```python
class GraphBuilder:
    """关联图构建器 — v2 方案
    
    在 attribute_graph.py 中替代旧的 AttributeGraph 类。
    10 步构建 + 后处理。
    """
    
    def build(self):
        """完整构建流程"""
        # 基础图结构
        self.step1_create_categories()          # 集合节点 + is_subset_of
        self.step2_assign_membership()          # 实体→集合归属
        self.step3_build_mechanism_edges()      # 标签推导的机制边
        self.step4_parse_triggers()             # configTable → triggers 边
        self.step5_parse_energy()               # centienergy → produces_energy 边
        
        # 约束 + 改变者 + 标签传播
        self.step6_extract_blocks_when()        # 四层 blocks_when 约束
        self.step7_build_modifiers()            # Support+天赋+装备改变者
        self.step8_extract_tag_propagation()    # adds_tag 附加到机制边
        
        # 异常发现
        self.step9_restore_archive()            # 加载存档 → 恢复历史异常到图
        self.step10_discover_anomalies()        # 暴力遍历 → 发现新异常 → 写入图
        
        # 后处理
        self._postprocess_archive()             # 对比存档 → 回写 predefined_edges.yaml
```

#### 每步的输入输出和代码来源

```
step1_create_categories():
  输入: 硬编码的 15 个集合定义（从设计方案第三节）
  输出: 15-20 个 category 节点 + is_subset_of 边
  复杂度: 低，静态定义

step2_assign_membership():
  输入: entities.db skillTypes 字段
  输出: ~1,400 条 belongs_to 边
  逻辑: tag_to_category 映射表 + skillTypes 匹配
  复杂度: 低

step3_build_mechanism_edges():
  输入: entities.db skillTypes（Trappable/Mineable/Totemable/HasReservation/AppliesCurse）
  输出: deploys_as/summons_for/reserves/applies_effect/converts_to 边
  复杂度: 低

step4_parse_triggers():
  输入: CalcTriggers.lua configTable（第881-1416行）
  输出: ~40 条 triggers 边
  方法: 正则提取 SkillType.XXX
  代码来源: Modules/CalcTriggers.lua:881-1416
  复杂度: 中（需要 Lua 正则解析）

step5_parse_energy():
  输入: Data/Skills/act_*.lua 中 Meta 技能的 constantStats
  输出: ~10 条 produces_energy 边
  方法: 搜索 centienergy stat + 手动确认表
  代码来源: Data/Skills/act_dex.lua, act_int.lua, act_str.lua
  复杂度: 低（Meta 数量少）

step6_extract_blocks_when():
  Layer 1: entities.db exclude_skill_types → ~25 条（归纳后）
  Layer 2: SkillStatMap.lua cannot stat → ~35 条
  Layer 3: 预定义的 Calc 代码阻断列表（固化） → ~15 条
  Layer 4: entities.db stat_descriptions cannot/instead/immune → ~50 条
  输出: ~125 条 blocks_when 边
  代码来源: Data/SkillStatMap.lua, Modules/CalcOffence.lua, CalcPerform.lua, CalcDefence.lua
  复杂度: Layer 1-2 低，Layer 3 一次性，Layer 4 中（需 ModCache 查表）

step7_build_modifiers():
  Layer 1: entities.db add_skill_types（Support） → 63 条 modifies 边
  Layer 2: stat_descriptions → ModCache → 结构化 mod → modifies 边
  Layer 3: ModCache nil 兜底 → ~80 条
  输出: ~300+ 条 modifies 边
  代码来源: Data/ModCache.lua
  复杂度: 中（ModCache 查表管道）

step8_extract_tag_propagation():
  输入: entities.db add_skill_types
  输出: adds_tag 属性附加到机制边上
  复杂度: 低

step9_restore_archive():
  输入: config/predefined_edges.yaml 存档
  输出: 历史异常恢复到图（bypasses 边 + anomaly_paths）
  复杂度: 低

step10_discover_anomalies():
  输入: 图内数据（~125 blocks_when × ~300 modifiers）
  输出: 新发现的异常写入图
  复杂度: 低（暴力遍历 37,500 组合，毫秒级）

_postprocess_archive():
  输入: step10 发现结果 + 存档
  逻辑: 对比合并（confirmed / pending_review / new_discovery）
  输出: 回写 predefined_edges.yaml 累积更新
```

#### 维度三：四阶段实施

```
Phase A: 基础框架（可独立运行）
  1. attribute_graph.py 上重写 → GraphBuilder 类骨架
  2. 实现 step1 + step2 + step3（全部从 entities.db，最简单）
  3. graph.db v2 schema 在 attribute_graph.py 中定义
  4. 修改 init_knowledge_base.py Step 4 调用 GraphBuilder
  5. 删除 init_knowledge_base.py 旧 Step 5-8 函数
  → 验证：图中有集合节点、成员归属、基础机制边

Phase B: 触发+能量
  1. 实现 step4_parse_triggers()（CalcTriggers configTable 正则解析）
  2. 实现 step5_parse_energy()（centienergy stat 解析）
  → 验证：MetaTrigger 的触发关系完整

Phase C: 约束+改变者+标签传播
  1. 实现 step6_extract_blocks_when() — 四层 blocks_when
  2. 实现 step7_build_modifiers() — Support/天赋/装备
  3. 实现 step8_extract_tag_propagation() — adds_tag 附加到机制边
  → 验证：~125 约束 + ~300 改变者 + 机制边带标签传播属性

Phase D: 异常发现 + 清理旧代码
  1. 实现 step9_restore_archive()（加载 predefined_edges.yaml 存档到图）
  2. 实现 step10_discover_anomalies()（暴力遍历）
  3. 实现 _postprocess_archive()（对比+回写存档）
  4. 更新 config/predefined_edges.yaml 为 v2 格式
  5. 删除 seed_knowledge_verifier.py、generate_graph_from_rules.py
  6. 删除 heuristic_*.py（5个）+ 相关测试（2个）+ 相关配置（2个）
  → 验证：Hazard绕过Triggered案例被自动发现，存档正确回写
```

### 文件清理清单

**要删除的文件（Phase D 统一清理）**：

```
scripts/
  seed_knowledge_verifier.py      # 旧种子验证
  generate_graph_from_rules.py    # 旧规则→图
  heuristic_query.py              # 启发式查询
  heuristic_discovery.py          # 启发式发现
  heuristic_diffuse.py            # 启发式扩散
  heuristic_reason.py             # 启发式推理
  heuristic_config_loader.py      # 启发式配置加载
  test_phase2_integration.py      # 启发式集成测试
  test_heuristic_reasoning.py     # 启发式推理测试

config/
  heuristic_config.yaml           # 启发式配置
  heuristic_records.yaml          # 启发式记录

knowledge_base/
  pending_confirmations.yaml      # 启发式待确认（如果存在）
```

**要重写的文件**：

```
config/
  predefined_edges.yaml           # v1→v2：从种子边改为异常发现存档
```

### 旧→新枚举映射

attribute_graph.py 重写时，枚举类型的变化：

**NodeType（8→4）**：
```
旧                          新
─────────────────────────────────────
ENTITY                  →   entity（保留）
MECHANISM               →   删除（被 category 替代）
ATTRIBUTE               →   删除
CONSTRAINT              →   constraint（保留）
HEURISTIC               →   删除
TYPE_NODE               →   category（替代）
PROPERTY_NODE           →   删除
TRIGGER_MECHANISM       →   删除
（新增）                →   tag
```

**EdgeType（25→15）**：
```
旧                          新
─────────────────────────────────────
REQUIRES                →   requires_tag
BLOCKS                  →   blocks_when
BYPASSES                →   bypasses（保留）
MODIFIES                →   modifies（保留）
TRIGGERS                →   triggers（保留）
HAS_TYPE / HAS_STAT     →   删除（被 belongs_to 替代）
CAUSES / ENHANCES / REDUCES → 删除（纯数值）
（新增）                →   belongs_to / is_subset_of / produces_energy /
                            converts_to / summons / reserves / deploys_as /
                            grants_buff / applies_effect / adds_tag / excludes_tag
```

**VerificationStatus / EvidenceType 枚举**：
- 被 verification/ 系统（3个文件）大量使用
- 验证系统设计上保留 → 这两个枚举**必须保留在 attribute_graph.py 中**
- 重写时保留枚举定义，但不再在 GraphBuilder 内部使用

### import 影响范围

attribute_graph.py 重写后，以下文件的 import 需要更新：

| 文件 | 当前 import | 需要改为 |
|------|-----------|---------|
| **init_knowledge_base.py** | `from attribute_graph import AttributeGraph` | `from attribute_graph import GraphBuilder` |
| **query_engine.py** | `AttributeGraph, NodeType, EdgeType` | `GraphBuilder, NodeType, EdgeType`（枚举名变化） |
| **verification/verification_engine.py** | `AttributeGraph, VerificationStatus, EvidenceType` | 保留 `VerificationStatus, EvidenceType`，去掉 `AttributeGraph` 或改为 `GraphBuilder` |
| **verification/verification_query_engine.py** | `AttributeGraph, VerificationStatus` | 同上 |
| **verification/evidence_evaluator.py** | `VerificationStatus, EvidenceType` | 无变化（只用枚举） |
| **test_integration.py** | `AttributeGraph` | `GraphBuilder` |
| **test_verification.py** | `AttributeGraph, VerificationStatus, EvidenceType` | 更新 |
| **test_verification_extended.py** | 同上 | 更新 |
| **run_full_init.py** | 引用 `import_heuristic_records` | 删除该引用 |

**init_knowledge_base.py 额外清理**：
- 第744行 `from seed_knowledge_verifier import verify_and_get_property_mappings` → 删除
- 第992行 `from seed_knowledge_verifier import verify_and_get_trigger_mechanisms` → 删除
- `import_heuristic_records` 函数 → 删除

### 额外遗留文件清理

以下文件在主清理清单外，也需要处理：

```
scripts/
  data_scanner_new_methods.py     # 临时文件，方法已合并到 data_scanner.py → 删除
  _deprecated_rules_extractor.py  # 已标记废弃 → 删除
  init_formula_library.py         # 冗余入口，使用 init_knowledge_base.py → 删除
  hypothesis_manager.py           # 启发式系统一部分（非 heuristic_* 命名）→ 删除
  migrate_graph_db.py             # graph.db 重建后迁移脚本无用 → 删除

knowledge_base/
  heuristic_records.yaml          # config/ 下也有一份，两处都删
  learning_log.yaml               # 启发式系统产物 → 删除
  unverified_list.yaml            # 启发式系统产物 → 删除
  query_lessons.md                # 启发式系统产物 → 删除
  entities_backup.db              # 备份文件，按需保留
  rules_backup.db                 # 备份文件，按需保留
  test_formulas.db                # 测试用 → 删除
  init_log.txt                    # 旧日志 → 删除
```

## 十七、待决策事项

1. ~~一级集合划分~~ → Attack拆分Melee/Ranged, Trap/Mine不合并 ✅
2. ~~集合层级关系~~ → 需要表达 is_subset_of ✅
3. ~~改变者表达方式~~ → 统一 modifies + 属性区分（方案A） ✅
4. ~~mechanisms.db~~ → 暂不作为机制边 ✅
5. ~~约束提取~~ → 全自动 + 合并归纳 + Meta特殊处理 ✅
6. ~~成员归属~~ → 全自动，~1,400实体参与，skillTypes直接匹配 ✅
7. ~~Support参与规则~~ → 三层分级（改变者63/约束载体537/纯数值480不参与图） ✅
8. ~~集合粒度~~ → 约束已精确过滤，不需要行为标签子集合 ✅
9. ~~改变者识别~~ → ModCache查表(94%结构化) + 文本兜底(6%) ✅
10. ~~机制边发现~~ → 四步提取（标签推导/configTable/centienergy/blocks_when四层自动） ✅
11. ~~异常路径发现算法~~ → 暴力遍历（37,500组合），不做优化 ✅
12. ~~具体实现方案~~ → 四阶段实施，老文件修改不新建，rules.db保留不参与图，启发系统全删 ✅

**所有设计决策已全部确认。可以进入实施。**

## 十八、与现有系统的关系

现有 graph.db 需要重建，其他系统处理方式：

| 系统 | 处理 | 说明 |
|------|------|------|
| **entities.db** | 保留，不修改 | 图的核心数据来源 |
| **rules.db** | 保留，不参与图构建 ✅ | rules_extractor.py 独立运行 |
| **mechanisms.db** | 保留 | 44个机制，后续可独立使用 |
| **formulas.db** | 保留 | 用于数值计算 |
| **验证系统** | 保留 | POBCodeSearcher 等，用于验证异常发现 |
| **attribute_graph.py** | 在原文件上重写 | GraphBuilder 替代旧的 AttributeGraph |
| **init_knowledge_base.py** | 修改 | Step 4 重写，旧 Step 5-8 函数删除 |
| **predefined_edges.yaml** | 重写为 v2 ✅ | 异常发现存档，step9 恢复 + 后处理回写 |
| **heuristic_*.py（5个）** | 全部删除 ✅ | 核心功能被 GraphBuilder step9-10 替代 |
| **seed_knowledge_verifier.py** | 删除 ✅ | 功能被自动提取覆盖 |
| **generate_graph_from_rules.py** | 删除 ✅ | 被 GraphBuilder 替代 |
| **heuristic 配置/记录（2个）** | 删除 ✅ | 随启发系统一起清理 |
