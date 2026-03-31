# Spark 构筑全面分析报告

## 0. 执行摘要

### 维度概览

| 维度 | 关键指标 |
|------|---------|
| 进攻 | TotalDPS **11,661** |
| 防御 | TotalEHP **9,591**（最短板: Chaos） |
| 资源 | Spirit 占用 **129%** |
| 恢复 | 生命恢复 **341/s** |


### 关键发现

1. ⚠️ **混沌抗性/防御是最短板**（承伤仅 4,406，为最强的 24%）
2. ⚠️ 混沌抗性差 **75%** 未满
3. 🔴 精魄预算非常紧张（129% 占用）
4. ⚠️ 22 个已分配天赋对 DPS 和 EHP 均无可测量影响
5. 💡 **crit_chance_base** 对 DPS 影响最大（每 1% 提升 5.94% DPS）

### 优化方向 Top 3

1. **crit_chance_base** (BASE): 每 1% 提升 5.94% DPS，需要 +4% 达到 +20% DPS
2. **cast_speed_inc** (INC): 每 1% 提升 0.56% DPS，需要 +34% 达到 +20% DPS
3. **crit_multi_base** (BASE): 每 1% 提升 0.46% DPS，需要 +42% 达到 +20% DPS

## 1. 基线概览

| 指标 | 数值 |
|------|------|
| 主技能 | Spark |
| 技能类型 | 法术, 投射物 |
| TotalDPS | **11,661** |
| AverageHit | 4,664 |
| Speed | 2.50/s |
| CritChance | 29.3% |
| CritMultiplier | 4.00x |
| TotalEHP | 9,591 |
| 最短板承伤 | **4,406** (混沌) |

## 2. DPS 来源拆解

活跃伤害类型: Lightning, Cold, Fire

### 通用伤害 INC (Lightning,Cold,Fire) = 36%

**类别汇总**: Tree: +36.0

| 来源 | 类别 | 值 |
|------|------|-----|
| Potent Incantation | Tree | +30.0 |
| Life Spell Damage and Costs | Tree | +6.0 |

### 元素伤害 INC (Lightning,Cold,Fire) = 101%

**类别汇总**: Tree: +72.0 | Item: +29.0

| 来源 | 类别 | 值 |
|------|------|-----|
| All Natural | Tree | +30.0 |
| Rapture Shard, Sapphire (Jewel) | Item | +15.0 |
| Chimeric Spark, Sapphire (Jewel) | Item | +14.0 |
| Elemental Damage | Tree | +12.0 |
| Elemental Damage | Tree | +10.0 |
| Elemental Damage | Tree | +10.0 |
| Elemental Damage | Tree | +10.0 |

### 冰霜伤害 INC (Cold) = 10%

**类别汇总**: Tree: +10.0

| 来源 | 类别 | 值 |
|------|------|-----|
| Cold Damage | Tree | +10.0 |

### 通用伤害 MORE (Lightning,Cold,Fire) = x 1.20

**类别汇总**: Skill: +20.0

| 来源 | 类别 | 值 |
|------|------|-----|
| Deliberation | Skill | +20.0 |

### Speed Base = 2.50/s

**类别汇总**: Skill: +2.5

| 来源 | 类别 | 值 |
|------|------|-----|
| Trigger Rate (computed) | Skill | +2.5 |

### Speed INC = 75%

**类别汇总**: Item: +64.0 | Tree: +11.0

| 来源 | 类别 | 值 |
|------|------|-----|
| Damnation Grip, Unset Ring (Ring 2) | Item | +24.0 |
| Adonia's Ego, Siphoning Wand (Weapon 1) | Item | +21.0 |
| Torment Band, Unset Ring (Ring 1) | Item | +19.0 |
| Flow Like Water | Tree | +8.0 |
| Potent Incantation | Tree | -5.0 |
| Skill Speed | Tree | +4.0 |
| Skill Speed | Tree | +4.0 |

### CritChance BASE = 9.0% (base 9.0% + added 0%)

**类别汇总**: Skill: +9.0

| 来源 | 类别 | 值 |
|------|------|-----|
| 技能基础暴击率 | Skill | +9.0 |

### CritChance INC = 226%

**类别汇总**: Tree: +206.0 | Item: +20.0

| 来源 | 类别 | 值 |
|------|------|-----|
| Careful Assassin | Tree | +50.0 |
| Critical Exploit | Tree | +25.0 |
| Adonia's Ego, Siphoning Wand (Weapon 1) | Item | +20.0 |
| True Strike | Tree | +20.0 |
| Throatseeker | Tree | -20.0 |
| Sudden Escalation | Tree | +16.0 |
| Moment of Truth | Tree | +15.0 |
| Critical Chance | Tree | +10.0 |
| Critical Chance | Tree | +10.0 |
| Critical Chance | Tree | +10.0 |
| Critical Chance | Tree | +10.0 |
| Spell Critical Chance | Tree | +10.0 |
| Critical Chance | Tree | +10.0 |
| Deadly Force | Tree | +10.0 |
| Critical Chance | Tree | +10.0 |
| Critical Chance | Tree | +10.0 |
| Energy and Critical Chance | Tree | +5.0 |
| Energy and Critical Chance | Tree | +5.0 |

### CritMultiplier BASE = 100

**类别汇总**: Base: +100.0

| 来源 | 类别 | 值 |
|------|------|-----|
| Base | Base | +100.0 |

### CritMultiplier INC = 200%

**类别汇总**: Tree: +200.0

| 来源 | 类别 | 值 |
|------|------|-----|
| Throatseeker | Tree | +60.0 |
| For the Jugular | Tree | +25.0 |
| Careful Assassin | Tree | -20.0 |
| Critical Damage | Tree | +15.0 |
| Critical Damage | Tree | +15.0 |
| Critical Damage | Tree | +15.0 |
| Critical Damage | Tree | +15.0 |
| Spell Critical Damage | Tree | +15.0 |
| Critical Damage | Tree | +15.0 |
| Critical Damage | Tree | +15.0 |
| Critical Damage | Tree | +15.0 |
| Critical Damage | Tree | +15.0 |

### Lightning Lucky Hits = 20

**类别汇总**: Jewel: +20.0

| 来源 | 类别 | 值 |
|------|------|-----|
| Megalomaniac, Diamond → The Spring Hare | Jewel | +20.0 |

### Cold Lucky Hits = 20

**类别汇总**: Jewel: +20.0

| 来源 | 类别 | 值 |
|------|------|-----|
| Megalomaniac, Diamond → The Spring Hare | Jewel | +20.0 |

### Fire Lucky Hits = 20

**类别汇总**: Jewel: +20.0

| 来源 | 类别 | 值 |
|------|------|-----|
| Megalomaniac, Diamond → The Spring Hare | Jewel | +20.0 |

### Lightning → Lightning Self-Gain = Lightning Self-Gain: 增益 27.0%

**类别汇总**: Item: +17.0 | Tree: +10.0

| 来源 | 类别 | 值 |
|------|------|-----|
| Heart of the Well, Diamond (Jewel) | Item | +12.0 (Gain as Lightning) |
| I am the Thunder... | Tree | +10.0 (Gain as Lightning) |
| Adonia's Ego, Siphoning Wand (Weapon 1) | Item | +5.0 (Gain as Lightning) |

### Lightning → Cold Conversion/Gain = Lightning → Cold: 增益 15.0%

**类别汇总**: Tree: +10.0 | Item: +5.0

| 来源 | 类别 | 值 |
|------|------|-----|
| I am the Blizzard... | Tree | +10.0 (Gain as Cold) |
| Adonia's Ego, Siphoning Wand (Weapon 1) | Item | +5.0 (Gain as Cold) |

### Lightning → Fire Conversion/Gain = Lightning → Fire: 增益 63.0%

**类别汇总**: Item: +63.0

| 来源 | 类别 | 值 |
|------|------|-----|
| Sacred Flame, Shrine Sceptre (Weapon 2) | Item | +58.0 (Gain as Fire) |
| Adonia's Ego, Siphoning Wand (Weapon 1) | Item | +5.0 (Gain as Fire) |

### Lightning Effective DPS Multiplier = x0.5000

**公式**: `(1+0/100) × 1.0000 × (1-50/100)`

**类别汇总**: Enemy: +50.0

| 来源 | 类别 | 值 |
|------|------|-----|
| 敌人 Lightning 抗性 | Enemy | +50.0 |

### Cold Effective DPS Multiplier = x0.5000

**公式**: `(1+0/100) × 1.0000 × (1-50/100)`

**类别汇总**: Enemy: +50.0

| 来源 | 类别 | 值 |
|------|------|-----|
| 敌人 Cold 抗性 | Enemy | +50.0 |

### Fire Effective DPS Multiplier = x0.5000

**公式**: `(1+0/100) × 1.0000 × (1-50/100)`

**类别汇总**: Enemy: +50.0

| 来源 | 类别 | 值 |
|------|------|-----|
| 敌人 Fire 抗性 | Enemy | +50.0 |

### Combined DPS = 11,687

**类别汇总**: Hit: +11661.2 | DOT: +26.0

| 来源 | 类别 | 值 |
|------|------|-----|
| Hit DPS | Hit | +11,661 |
| 点燃 DPS | DOT | +26.0 |

## 3. 灵敏度分析

### 3A. 进攻灵敏度（DPS）

| # | 维度 | 类型 | 所需值 | 单位 | 效果/单位 | 当前值 | 公式 |
|---|------|------|--------|------|----------|--------|------|
| 1 | crit_chance_base | BASE | +3.5% | % | 5.94%/% | 0 | baseCrit 0.0%→3.5%, 需要 +3.5% → DPS +20.8% |
| 2 | cast_speed_inc | INC | +34.5% | % | 0.56%/% | 75 | INC 75%→110%, 需要 +34 → DPS +19.4% |
| 3 | crit_multi_base | BASE | +42.5% | % | 0.46%/% | 100 | CritBase 100→142, 需要 +42 → DPS +19.7% |
| 4 | spell_damage_inc | INC | +48.0% | % | 0.42%/% | 137 | INC 137%→185%, 需要 +48 → DPS +20.2% |
| 5 | projectile_damage_inc | INC | +48.0% | % | 0.42%/% | 137 | INC 137%→185%, 需要 +48 → DPS +20.2% |
| 6 | elemental_damage_inc | INC | +48.0% | % | 0.42%/% | 137 | INC 137%→185%, 需要 +48 → DPS +20.2% |
| 7 | lightning_damage_inc | INC | +77.0% | % | 0.26%/% | 137 | INC 137%→214%, 需要 +77 → DPS +20.1% |
| 8 | crit_multi_inc | INC | +128.5% | % | 0.16%/% | 200 | INC 200%→328%, 需要 +128 → DPS +20.1% |
| 9 | crit_chance_inc | INC | +139.5% | % | 0.14%/% | 226 | INC 226%→366%, 需要 +140 → DPS +20.0% |
| 10 | fire_damage_inc | INC | +155.0% | % | 0.13%/% | 137 | INC 137%→292%, 需要 +155 → DPS +20.0% |

**无影响维度**: physical_damage_inc, cold_damage_inc, chaos_damage_inc, lightning_pen, fire_pen, cold_pen, elemental_pen, chaos_pen, projectile_count, aoe_inc, duration_inc

### 3B. 防御灵敏度（EHP）

| 维度 | 类型 | 所需值 | 每单位 EHP 提升 | 公式 |
|------|------|--------|---------------|------|
| 格挡概率 | BASE | 24.5% | +0.79%/单位 | BASE 0→24, 需要 +24 → EHP +19.4% |
| 法术格挡概率 | BASE | 24.5% | +0.79%/单位 | BASE 0→24, 需要 +24 → EHP +19.4% |
| 生命上限 | INC | 36.5% | +0.55%/单位 | INC 10%→46%, 需要 +36 → EHP +20.2% |
| 混沌抗性 | BASE | 55.0% | +0.37%/单位 | BASE 0→55, 需要 +55 → EHP +20.2% |
| 闪避值 | BASE | 1537.5 | +0.01%/单位 | BASE 7→1544, 需要 +1538 → EHP +20.7% |
| 护甲固定值 | BASE | 4096.5 | +0.00%/单位 | BASE 0→4096, 需要 +4096 → EHP +19.6% |

**无法达到目标**: 生命固定值, 火焰抗性, 闪避增加, 物理减伤, 冰霜抗性, 闪电抗性, 全元素抗性, 护甲增加

### 3C. 恢复增强灵敏度

注入多少恢复属性可使对应恢复指标提升 **20%**：

| 增强属性 | 所需注入 | 当前总值 | 公式 |
|---------|---------|---------|------|
| 魔力再生 | 2.0/s | 63.0 | BASE 63→65, 需要 +2 → 魔力恢复 +21.0% |
| 魔力恢复速率 | 5.5% | — | INC 0%→6%, 需要 +6 → 魔力恢复 +20.2% |
| 生命再生 | 14.0/s | — | BASE 0→14, 需要 +14 → 生命恢复 +20.1% |
| 生命恢复速率 | 17.0% | — | INC 0%→17%, 需要 +17 → 生命恢复 +20.2% |

## 4. 防御面

### 4A. 生命池构成

| 资源 | 数值 | 备注 |
|------|------|------|
| Life | 2,180 | — |
| Energy Shield | 1,442 | — |
| Mana | 1,505 | 可用 1,505 |
| MoM | 100% | 魔力优先承受伤害 |

### 4B. 减伤层

| 层 | 数值 |
|------|------|
| 护甲 | 0 |
| 闪避 | 444 |
| 攻击格挡 | 0% |
| 法术格挡 | 0% |

### 4C. 抗性面板

| 元素 | 当前 | 上限 | 状态 |
|------|------|------|------|
| 火焰 | 75% | 75% | 满 (+45%溢出) |
| 冰霜 | 75% | 75% | 满 (+44%溢出) |
| 闪电 | 75% | 75% | 满 (+37%溢出) |
| 混沌 | 0% | 75% | 未满 (差 75%) |

未满抗性: 混沌 — 优先补满可显著提升对应元素 EHP。

过度堆叠: 火焰, 冰霜, 闪电 — 超出上限 20%+，可考虑将属性分配到其他维度。

### 4D. 最大承伤 (MaxHitTaken)

**TotalEHP = 9,591**（平均承受 2.3 次攻击）

| 伤害类型 | MaxHitTaken | 占最强% |
|----------|-------------|--------|
| 火焰 | 18,311 | 100% |
| 冰霜 | 18,311 | 100% |
| 闪电 | 18,311 | 100% |
| 混沌 | 4,406 | 24% ← 最短板 |

**最短板**: 混沌（仅承受 4,406 伤害，为最强的 24%）

### 4E. 承伤乘数 (TakenHitMult)

数值越小越好，表示实际承受伤害占原始伤害的比例。

| 伤害类型 | 承伤乘数 | 含义 |
|----------|---------|------|
| 火焰 | 0.280 (28.0%) | 每承受 100 伤害实际受 28 |
| 冰霜 | 0.280 (28.0%) | 每承受 100 伤害实际受 28 |
| 闪电 | 0.280 (28.0%) | 每承受 100 伤害实际受 28 |
| 混沌 | 1.000 (100.0%) | 每承受 100 伤害实际受 100 ← 最短板 |

### 4F. DOT 有效生命

| 伤害类型 | DotEHP |
|----------|--------|
| 火焰 | 20,508 |
| 冰霜 | 20,508 |
| 闪电 | 20,508 |
| 混沌 | 4,406 |


## 5. 资源面

### 5A. 资源预算

| 资源 | 总量 | 可用 | 占用率 |
|------|------|------|--------|
| Life | 2,180 | 2,180 | — |
| Mana | 1,505 | 1,505 | 0% |
| Spirit | 425 | -125 | 🔴 129% |
| ES | 1,442 | 1,442 | — |

### 5B. 生命恢复能力

总恢复速率: **340.6/s**（回满约 6.4s）
偷取上限利用率: 37%（上限 589/s）

| # | 来源 | 每秒恢复 | 占比 |
|---|------|---------|------|
| 1 | 偷取 | 218.0/s | 64% |
| 2 | 再生 | 122.6/s | 36% |

### 5C. 魔力恢复能力

总恢复速率: **62.0/s**（回满可用 1,505 约需 24.3s）

| # | 来源 | 每秒恢复 | 占比 |
|---|------|---------|------|
| 1 | 再生 | 62.0/s | 100% |

## 6. 已分配天赋价值

### DPS 影响天赋

| # | 天赋 | 类型 | 移除后 DPS% | 移除后 EHP% | 分类 |
|---|------|------|-------------|-------------|------|
| 1 | All Natural | Notable | -12.6% | +0.0% | 进攻 |
| 2 | Potent Incantation | Notable | -10.1% | +0.0% | 进攻 |
| 3 | Throatseeker | Notable | -7.1% | +0.0% | 进攻 |
| 4 | The Spring Hare | Notable | -5.7% | +0.0% | 进攻 |
| 5 | I am the Blizzard... | Notable | -5.1% | +0.0% | 进攻 |
| 6 | I am the Thunder... | Notable | -4.9% | +0.0% | 进攻 |
| 7 | Flow Like Water | Notable | -4.6% | -0.2% | 混合 |
| 8 | Careful Assassin | Notable | -4.5% | +0.0% | 进攻 |
| 9 | For the Jugular | Notable | -3.9% | -0.5% | 混合 |
| 10 | Critical Exploit | Notable | -3.6% | +0.0% | 进攻 |
| 11 | True Strike | Notable | -2.9% | +0.0% | 进攻 |
| 12 | Sudden Escalation | Notable | -2.3% | +0.0% | 进攻 |
| 13 | Moment of Truth | Notable | -2.2% | +0.0% | 进攻 |
| 14 | Deadly Force | Notable | -1.4% | +0.0% | 进攻 |

### 纯防御天赋

| 天赋 | 移除后 EHP% |
|------|-------------|
| Melding | -2.1% |
| Mind Over Matter | -31.7% |
| Heavy Buffer | -5.4% |

### 无效天赋 (22 个)

Invocated Echoes, ...and I Shall Rage, Impending Doom, Blood Transfusion, Thin Ice, Energise, Heavy Frost, Dynamism, Breaking Point, Marked Agility, Shimmering, Efficient Inscriptions, The Power Within, Overflowing Power, Evocational Practitioner, Infusion of Power, Marked for Sickness, Acceleration, Stormwalker, Frostwalker, The Soul Springs Eternal, Crashing Wave

## 7. 未分配天赋探索

| # | 天赋 | 类型 | DPS% | EHP% | 分类 |
|---|------|------|------|------|------|
| 1 | Arcane Intensity | Notable | +18.9% | +0.0% | 进攻 |
| 2 | Stand and Deliver | Notable | +17.4% | +0.0% | 进攻 |
| 3 | Heavy Ammunition | Notable | +16.8% | +0.0% | 进攻 |
| 4 | Sacrificial Blood | Notable | +16.8% | +0.0% | 进攻 |
| 5 | Jack of all Trades | Notable | +14.3% | +0.0% | 进攻 |
| 6 | Lucky Rabbit Foot | Notable | +12.6% | +0.0% | 进攻 |
| 7 | Cower Before the First Ones | Notable | +12.6% | +0.0% | 进攻 |
| 8 | Comradery | Notable | +12.6% | +0.0% | 进攻 |
| 9 | Imbibed Power | Notable | +10.5% | +0.0% | 进攻 |
| 10 | Master of Hexes | Notable | +10.0% | +0.0% | 进攻 |

*（另有 147 个候选天赋未显示）*

## 8. 珠宝诊断

### Rapture Shard (Sapphire, RARE)

- **DPS 贡献**: +6.3% | **EHP 贡献**: +2.1% | **状态**: ok | **槽位**: Jewel 61834

| Mod | 类型 | 值 | DPS% | EHP% |
|-----|------|-----|------|------|
| EnergyShield | INC | 17 | -0.0% | +2.1% |
| ElementalDamage | INC | 15 | +6.3% | -0.0% |
| CurseActivation | INC | 14 | -0.0% | -0.0% |

### Chimeric Spark (Sapphire, RARE)

- **DPS 贡献**: +5.9% | **EHP 贡献**: +1.9% | **状态**: ok | **槽位**: Jewel 7960

| Mod | 类型 | 值 | DPS% | EHP% |
|-----|------|-----|------|------|
| EnergyShield | INC | 15 | -0.0% | +1.9% |
| ElementalDamage | INC | 14 | +5.9% | -0.0% |
| CurseActivation | INC | 15 | -0.0% | -0.0% |

### Heart of the Well (Diamond, UNIQUE)

- **DPS 贡献**: +5.8% | **EHP 贡献**: -0.0% | **状态**: ok | **槽位**: Jewel 32763

| Mod | 类型 | 值 | DPS% | EHP% |
|-----|------|-----|------|------|
| DamageGainAsLightning | BASE | 12 | +5.8% | -0.0% |
| ManaOnKill | BASE | 1 | -0.0% | -0.0% |
| HybridManaAndLifeCost_Life | BASE | 3 | -0.0% | -0.0% |
| InstantEnergyShieldLeech | BASE | 15 | -0.0% | -0.0% |
| InstantManaLeech | BASE | 15 | -0.0% | -0.0% |
| InstantLifeLeech | BASE | 15 | -0.0% | -0.0% |

### Megalomaniac (Diamond, UNIQUE)

- **DPS 贡献**: +5.7% | **EHP 贡献**: -0.0% | **状态**: ok | **槽位**: Jewel 21984
- **分配天赋**: the spring hare, savoured blood (DPS +5.7%, EHP -0.0%)

| Mod | 类型 | 值 | DPS% | EHP% |
|-----|------|-----|------|------|
| GrantedPassive | LIST | the spring hare | +5.7% | -0.0% |
| GrantedPassive | LIST | savoured blood | -0.0% | -0.0% |

### Controlled Metamorphosis (Diamond, UNIQUE)

- **DPS 贡献**: -0.0% | **EHP 贡献**: -0.0% | **状态**: ok | **槽位**: Jewel 61419

| Mod | 类型 | 值 | DPS% | EHP% |
|-----|------|-----|------|------|
| JewelData | LIST | (complex data) | -0.0% | -0.0% |
| JewelData | LIST | (complex data) | -0.0% | -0.0% |
| ElementalResist | BASE | -6 | -0.0% | -0.0% |

## 9. 光环与精魄分析

### 9A. 现有光环 DPS 贡献

| # | 光环 | 裸光环 DPS | 真实 DPS | EHP | 精魄 | 条件参数范围 |
|---|------|------------|----------|-----|------|-------------|
| 1 | Trinity | +30.0% | +35.0% (辅助+3.9%: Dialla's Desire, Uhtred's Omen) (条件: Total Resonance Count=150) | +0.0% | 100 | Total Resonance Count=300: 裸+73.7% / 实+91.3% (SpeedINC: 裸+15%/实+22%, 边际: 裸8.6%/实12.6%); 辅助+3.9%: Dialla's Desire, Uhtred's Omen; [Lv20→24, 7% MORE/30, Speed 15.0%INC(q20)] |
| 2 | Charge Infusion | +29.5% | +30.8% ⚠️模拟 (辅助+1.0%: Uhtred's Exodus) | +7.3% | 30 | - |
| 3 | Elemental Conflux | +20.0% | +20.0% ⚠️模拟 | +0.0% | 60 | - |
| 4 | Purity of Fire | +0.0% | +0.0% | +0.0% | 130 | - |

**⚠️模拟值说明：**

- **Charge Infusion** (Lv21): 需启用 Charge 配置才能生效，已模拟 F=3/P=8/E=3
- **Elemental Conflux** (Lv21): 分别注入 60% MORE 到火/冰/电取平均。伤害构成：火 30.7% / 冰 7.6% / 电 61.7%
  三次模拟 DPS：火 17940 / 冰 15855 / 电 20768

**模拟方法说明：**

- **等级前提**：光环模拟基于构筑实际宝石等级数据（非固定 Level 20）
- **裸光环 DPS**：仅光环宝石效果（禁用所有辅助宝石），用于和「潜在光环推荐」对比。真实 DPS 含辅助宝石额外增益，标注在括号中
- **DPS 贡献计算**：移除光环后 DPS 下降百分比（正值=正向贡献）。条件光环需注入参数才能生效，默认注入参数最大值的 50%，标注在真实 DPS 括号中
- **构筑已有 modifier**：施法速度 INC 75%（来自 POB skillModList），总 MORE ×1.20。INC 叠加为加法（新增边际递减），MORE 叠加为乘法
- **品质上限**：所有宝石品质按 20% 上限计算（游戏实际上限）。构筑中超品质宝石已自动降级
- **条件范围计算**：设置参数绝对值（0 和 max），对比「无光环」DPS。Speed 门槛效果从 POB skillModList 读取端点 INC 差值，边际 = 新增INC / (1+已有INC)
- **期望收益计算**：对于 EC 等随机效果光环，期望 = 效果值 × 受影响技能元素占比之和 ÷ 3（因为随机选择火/冰/电之一）

**DPS/EHP 影响未检测到** (1 个)：

这些光环可能提供非DPS收益（如生存/功能性），或其效果依赖动态条件（如Frenzy Charge）而POB未完全计算。

- **Purity of Fire**: 精魄 130

### 9B. 潜在光环推荐

| # | 光环 | 精魄 | DPS% | EHP% | 说明 |
|---|------|------|------|------|------|
| 1 | Archmage（大法师） | 100 | +24.3% | +0.0% | 需精魄 100（缺 100）; Mana 转附加闪电伤害 |

**无 DPS 影响：**

- Attrition（损耗）
- Berserk（狂暴）

### 9C. 精魄辅助推荐

| # | 精魄辅助 | 精魄 | DPS% | 条件 | 来源 |
|---|----------|------|------|------|------|
| 1 | Mysticism II | 30 | +16.6% | 需精魄 30（缺 30） ⚠️估算 | 动态扫描 |
| 2 | Mysticism I | 15 | +8.4% | 需精魄 15（缺 15） ⚠️估算 | 动态扫描 |

其余 19 个辅助无可模拟的 DPS 效果。

### 9D. 精魄预算

| 项目 | 精魄 |
|------|------|
| 总精魄 | 525 |
| 已用精魄 | 525 |
| 可用精魄 | 0 |
| 推荐光环消耗 | 100 |
| 推荐后剩余 | -100 |

**注意**: 推荐光环的精魄总消耗超过可用精魄，需要根据优先级取舍。

### 9E. 数据一致性检查

**⚠️ 以下项目需要人工确认：**

- EC 使用构筑实际等级 Lv21（MORE=60%），非满级 Lv20
- Charge Infusion 使用非默认 Charge 数量: PowerCharges=8
- Attrition 无 DPS 影响：需要命中敌人才能叠加 Wither，纯模拟可能无法体现
- Berserk 无 DPS 影响：可能因为构筑已通过其他方式获得 Rage 效果

### 9F. POB 未实现效果预估

**⚠️ 以下技能效果在 POB 中未实现，已通过配置模拟：**

| 技能 | 效果描述 | DPS 预估 |
|------|----------|----------|
| **Unbound Avatar** | 40% MORE 元素伤害（Unbound 状态） | **+34.8%** |

**注**: 这些效果由 `config/pob_unimplemented_effects.yaml` 配置，
实际游戏效果可能因条件触发方式不同而有差异。

## 10. 总结与建议

当前 **Spark** TotalDPS = **11,661**，AverageHit = 4,664，Speed = 2.50/s，CritChance = 29.3%，CritMultiplier = 4.00x。

### ⚔️ 进攻面

**DPS 灵敏度 Top 5**（所需投入越少 = 性价比越高）：

| # | 维度 | 类型 | 当前值 | 所需值 | 公式 |
|---|------|------|--------|--------|------|
| 1 | crit_chance_base | BASE | 0 | +4% | baseCrit 0.0%→3.5%, 需要 +3.5% → DPS +20.8% |
| 2 | cast_speed_inc | INC | 75 | +34% | INC 75%→110%, 需要 +34 → DPS +19.4% |
| 3 | crit_multi_base | BASE | 100 | +42% | CritBase 100→142, 需要 +42 → DPS +19.7% |
| 4 | spell_damage_inc | INC | 137 | +48% | INC 137%→185%, 需要 +48 → DPS +20.2% |
| 5 | projectile_damage_inc | INC | 137 | +48% | INC 137%→185%, 需要 +48 → DPS +20.2% |

*穿透维度均无影响（敌人抗性已为负值），面对高抗 Boss 时会成为有效优化方向。*

### 🛡️ 防御面

**最短板**: Chaos（承伤仅为最强的 24%）

**防御性价比最高**: 格挡概率，需要 +24% 即可提升 EHP +20%

### 💧 资源与恢复

**⚠️ 精魄超载**: 占用 129%，需要缩减光环或精魄辅助

**恢复增强 Top 3**：

1. 魔力再生: BASE 63→65, 需要 +2 → 魔力恢复 +21.0%
2. 魔力恢复速率: INC 0%→6%, 需要 +6 → 魔力恢复 +20.2%
3. 生命再生: BASE 0→14, 需要 +14 → 生命恢复 +20.1%

### 🌳 天赋

**推荐点出 Top 5**：

1. **Arcane Intensity**: DPS +18.9%
2. **Stand and Deliver**: DPS +17.4%
3. **Heavy Ammunition**: DPS +16.8%
4. **Sacrificial Blood**: DPS +16.8%
5. **Jack of all Trades**: DPS +14.3%

**⚠️ 22 个无效天赋**: Invocated Echoes, ...and I Shall Rage, Impending Doom, Blood Transfusion, Thin Ice, Energise, Heavy Frost, Dynamism 等 22 个

### 💎 珠宝

**最佳**: Rapture Shard (DPS +6.3%, EHP +2.1%)
**可替换**: Controlled Metamorphosis
