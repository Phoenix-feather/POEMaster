# Flicker Strike 构筑全面分析报告

## 0. 执行摘要

### 维度概览

| 维度 | 关键指标 |
|------|---------|
| 进攻 | TotalDPS **12,050,363** |
| 防御 | TotalEHP **17,967**（最短板: Physical） |
| 资源 | Spirit 占用 **75%** |


### 关键发现

1. ⚠️ **物理抗性/防御是最短板**（承伤仅 8,303，为最强的 28%）
2. ⚠️ 混沌抗性差 **33%** 未满
3. ⚠️ 精魄预算紧张（75% 占用）
4. ⚠️ 16 个已分配天赋对 DPS 和 EHP 均无可测量影响
5. 💡 **crit_chance_base** 对 DPS 影响最大（每 1% 提升 5.81% DPS）

### 优化方向 Top 3

1. **crit_chance_base** (BASE): 每 1% 提升 5.81% DPS，需要 +4% 达到 +20% DPS
2. **crit_multi_base** (BASE): 每 1% 提升 0.69% DPS，需要 +28% 达到 +20% DPS
3. **attack_speed_inc** (INC): 每 1% 提升 0.54% DPS，需要 +38% 达到 +20% DPS

## 1. 构筑基线

### 构筑修饰符

| 修饰符 | 总量 | 天赋 | 装备 | 珠宝 |
|--------|------|------|------|------|
| 攻击速度 INC | 33% | +17% | +16% | — |
| 伤害 INC | 188% | +188% | — | — |
| 元素伤害 INC | 207% | +90% | +117% | — |
| 暴击率 INC | 146% | +146% | — | — |
| 暴击伤害 INC | 351% | +351% | — | — |

### 构筑属性

| 属性 | 数值 |
|------|------|
| 总属性 | 452 |
| 力量 | 79 |
| 敏捷 | 143 |
| 智力 | 230 |

### 技能 KPI

| 指标 | 数值 |
|------|------|
| 主技能 | Flicker Strike |
| 技能类型 | 攻击 |
| TotalDPS | **12,050,363** |
| AverageHit | 0 |
| Speed | 1.30/s |
| CritChance | 64.2% |
| CritMultiplier | 7.74x |
| TotalEHP | 17,967 |
| 最短板承伤 | **8,303** (物理) |

## 2. DPS 来源拆解

活跃伤害类型: Physical, Lightning, Cold, Fire

### Physical Base Damage = 215-860 (x7.41 base mult)

**类别汇总**: Skill: +72.5

| 来源 | 类别 | 值 |
|------|------|-----|
| 技能基础 | Skill | +72.5 (29-116) |

### Lightning Base Damage = 185-6536 (x7.41 base mult)

**类别汇总**: Aura: +204.0 | Item: +199.0 | Skill: +50.5

| 来源 | 类别 | 值 |
|------|------|-----|
| Charged Staff | Aura | +204.0 (+24-384) |
| Mind of the Council, Death Mask (Helmet) | Item | +199.0 (+0-398) |
| 技能基础 | Skill | +50.5 (1-100) |

### Cold Base Damage = 978-1526 (x7.41 base mult)

**类别汇总**: Skill: +169.0

| 来源 | 类别 | 值 |
|------|------|-----|
| 技能基础 | Skill | +169.0 (132-206) |

### Fire Base Damage = 1193-1897 (x7.41 base mult)

**类别汇总**: Skill: +192.0 | Item: +16.5

| 来源 | 类别 | 值 |
|------|------|-----|
| 技能基础 | Skill | +192.0 (150-234) |
| Honour Whorl, Breach Ring (Ring 2) | Item | +16.5 (+11-22) |

### 通用伤害 INC (Physical,Lightning,Cold,Fire) = 188%

**类别汇总**: Tree: +188.0

| 来源 | 类别 | 值 |
|------|------|-----|
| Crashing Wave | Tree | +36.0 |
| Deadly Force | Tree | +30.0 |
| Damage on Critical | Tree | +20.0 |
| Damage on Critical | Tree | +20.0 |
| Damage and Companion Damage | Tree | +12.0 |
| Damage and Companion Damage | Tree | +12.0 |
| Damage and Companion Damage | Tree | +12.0 |
| Damage and Companion Damage | Tree | +12.0 |
| Herald Damage | Tree | +12.0 |
| Herald Damage | Tree | +12.0 |
| Attack Damage | Tree | +10.0 |

### 元素伤害 INC (Lightning,Cold,Fire) = 207%

**类别汇总**: Item: +117.0 | Tree: +90.0

| 来源 | 类别 | 值 |
|------|------|-----|
| Dread Gnarl, Bolting Quarterstaff | Item | +117.0 |
| Stormcharged | Tree | +40.0 |
| All Natural | Tree | +30.0 |
| Elemental Damage | Tree | +10.0 |
| Elemental Damage | Tree | +10.0 |

### 闪电伤害 INC (Lightning) = 29%

**类别汇总**: Item: +29.0

| 来源 | 类别 | 值 |
|------|------|-----|
| Behemoth Whorl, Breach Ring (Ring 1) | Item | +29.0 |

### 攻击速度 = 1.40/s

**类别汇总**: Skill: +1.4

| 来源 | 类别 | 值 |
|------|------|-----|
| 武器攻击频率 | Skill | +1.4 |

### Speed INC = 86%

**类别汇总**: Aura: +27.0 | Sim: +26.0 | Tree: +17.0 | Item: +16.0

| 来源 | 类别 | 值 |
|------|------|-----|
| Charge Infusion | Aura | +27.0 |
| ⚠ CI speed (模拟) | Sim | +26.0 |
| Hateforge, Moulded Mitts (Gloves) | Item | +16.0 |
| Whirling Assault | Tree | +8.0 |
| Quarterstaff Speed | Tree | +3.0 |
| Quarterstaff Speed | Tree | +3.0 |
| Quarterstaff Speed | Tree | +3.0 |

### CritChance BASE = 64.2% (base 15.0% + added 1%)

**类别汇总**: Skill: +15.0 | Tree: +1.0

| 来源 | 类别 | 值 |
|------|------|-----|
| 基础暴击率 | Skill | +15.0 |
| Struck Through | Tree | +1.0 |

### CritChance INC = 146%

**类别汇总**: Tree: +146.0

| 来源 | 类别 | 值 |
|------|------|-----|
| Critical Exploit | Tree | +25.0 |
| Stormcharged | Tree | +20.0 |
| True Strike | Tree | +20.0 |
| Throatseeker | Tree | -20.0 |
| Heartstopping | Tree | +15.0 |
| Quarterstaff Critical Chance | Tree | +12.0 |
| Deadly Force | Tree | +12.0 |
| Quarterstaff Critical Chance | Tree | +12.0 |
| Critical Chance | Tree | +10.0 |
| Critical Chance | Tree | +10.0 |
| Critical Chance | Tree | +10.0 |
| Critical Chance | Tree | +10.0 |
| Critical Chance | Tree | +10.0 |

### CritChance MORE = +63.0%

**类别汇总**: Aura: +28% | Sim: +27%

| 来源 | 类别 | 值 |
|------|------|-----|
| Charge Infusion | Aura | +28.0% MORE |
| ⚠ CI crit (模拟) | Sim | +27.0% MORE |

### CritMultiplier BASE = 115

**类别汇总**: Base: +100.0 | Item: +15.0

| 来源 | 类别 | 值 |
|------|------|-----|
| Base | Base | +100.0 |
| Dread Gnarl, Bolting Quarterstaff | Item | +15.0 |

### CritMultiplier INC = 351%

**类别汇总**: Tree: +351.0

| 来源 | 类别 | 值 |
|------|------|-----|
| Throatseeker | Tree | +60.0 |
| Martial Artistry | Tree | +25.0 |
| Heartbreaking | Tree | +25.0 |
| For the Jugular | Tree | +25.0 |
| Critical Damage when consuming a Power Charge | Tree | +20.0 |
| Critical Damage when consuming a Power Charge | Tree | +20.0 |
| Critical Damage when consuming a Power Charge | Tree | +20.0 |
| Quarterstaff Critical Damage | Tree | +18.0 |
| Quarterstaff Critical Damage | Tree | +18.0 |
| Critical Damage | Tree | +15.0 |
| Critical Damage | Tree | +15.0 |
| Critical Damage | Tree | +15.0 |
| Critical Damage | Tree | +15.0 |
| Attack Critical Damage | Tree | +15.0 |
| Critical Damage | Tree | +15.0 |
| Critical Damage | Tree | +15.0 |
| Critical Damage | Tree | +15.0 |

### CritMultiplier MORE = +30.0%

**类别汇总**: Support: +30%

| 来源 | 类别 | 值 |
|------|------|-----|
| Overextend | Support | +30.0% MORE |

### Lucky Hits (Physical,Lightning,Cold,Fire) = 20%

| 来源 | 类别 | 值 |
|------|------|-----|
| The Spring Hare | Jewel | +20.0 |
| The Spring Hare | Jewel | +20.0 |
| The Spring Hare | Jewel | +20.0 |
| The Spring Hare | Jewel | +20.0 |

### 点燃 DPS = 15,423

**公式**: `× effMult 0.6000  (持续 4.00s, 几率 36.2%)`

**类别汇总**: Tree: +178.0

| 来源 | 类别 | 值 |
|------|------|-----|
| Crashing Wave | Tree | +36.0 |
| Deadly Force | Tree | +30.0 |
| Damage on Critical | Tree | +20.0 |
| Damage on Critical | Tree | +20.0 |
| Damage and Companion Damage | Tree | +12.0 |
| Damage and Companion Damage | Tree | +12.0 |
| Damage and Companion Damage | Tree | +12.0 |
| Damage and Companion Damage | Tree | +12.0 |
| Herald Damage | Tree | +12.0 |
| Herald Damage | Tree | +12.0 |

### 流血 DPS = 117,510

**公式**: `× effMult 1.2000  (持续 5.00s, 几率 9.6%)`

**类别汇总**: Tree: +178.0

| 来源 | 类别 | 值 |
|------|------|-----|
| Crashing Wave | Tree | +36.0 |
| Deadly Force | Tree | +30.0 |
| Damage on Critical | Tree | +20.0 |
| Damage on Critical | Tree | +20.0 |
| Damage and Companion Damage | Tree | +12.0 |
| Damage and Companion Damage | Tree | +12.0 |
| Damage and Companion Damage | Tree | +12.0 |
| Damage and Companion Damage | Tree | +12.0 |
| Herald Damage | Tree | +12.0 |
| Herald Damage | Tree | +12.0 |

### DPS Multiplier = x17.00

**类别汇总**: Skill: +17.0

| 来源 | 类别 | 值 |
|------|------|-----|
| 技能 DPS 乘数 | Skill | +17.0 |

### Combined DPS = 544,428

**类别汇总**: Hit: +12050362.6 | DOT: +132933.7

| 来源 | 类别 | 值 |
|------|------|-----|
| Hit DPS | Hit | +12,050,363 |
| 流血 DPS | DOT | +117,510 |
| 点燃 DPS | DOT | +15,423 |

### 敌人受伤增加 = x1.2000

**公式**: `所有伤害类型共享 x1.2000`

**类别汇总**: Ailment: +20.0

| 来源 | 类别 | 值 |
|------|------|-----|
| Shock: 受伤+20%（最小值） | Ailment | +20.0 |

### 敌人抗性乘区 (加权) = +170.1%

**公式**: `抗性反转: 闪电 100%`

**类别汇总**: ResistInvert: +100.0 | Enemy: +50.0

| 来源 | 类别 | 值 |
|------|------|-----|
| 闪电 +200.0% (占60.2%) | Enemy | +200.0 |
| 火焰 +200.0% (占21.1%) | Enemy | +200.0 |
| 冰霜 +200.0% (占10.6%) | Enemy | +200.0 |
| 物理 +0.0% (占8.1%) | Enemy | +0.0 |

## 3. 灵敏度分析

### 3A. 进攻灵敏度（DPS）

| # | 维度 | 类型 | 所需值 | 单位 | 效果/单位 | 当前值 | 公式 |
|---|------|------|--------|------|----------|--------|------|
| 1 | crit_chance_base | BASE | +3.5% | % | 5.81%/% | 1 | baseCrit 1.0%→4.5%, 需要 +3.5% → DPS +20.3% |
| 2 | crit_multi_base | BASE | +28.5% | % | 0.69%/% | 115 | CritBase 115→144, 需要 +28 → DPS +19.8% |
| 3 | attack_speed_inc | INC | +38.0% | % | 0.54%/% | 86 | INC 86%→124%, 需要 +38 → DPS +20.4% |
| 4 | crit_chance_inc | INC | +60.5% | % | 0.33%/% | 146 | INC 146%→206%, 需要 +60 → DPS +20.0% |
| 5 | attack_damage_inc | INC | +100.0% | % | 0.20%/% | 188 | INC 188%→288%, 需要 +100 → DPS +20.1% |
| 6 | melee_damage_inc | INC | +100.0% | % | 0.20%/% | 188 | INC 188%→288%, 需要 +100 → DPS +20.1% |
| 7 | elemental_damage_inc | INC | +106.5% | % | 0.19%/% | 188 | INC 188%→294%, 需要 +106 → DPS +20.0% |
| 8 | crit_multi_inc | INC | +110.5% | % | 0.18%/% | 351 | INC 351%→462%, 需要 +110 → DPS +19.9% |
| 9 | flat_lightning_attack | BASE | +117.0 |  | 0.17%/1 | 0 | 需要添加 117-234 基础伤害 → DPS +20.0% |
| 10 | flat_fire_attack | BASE | +122.0 |  | 0.17%/1 | 0 | 需要添加 122-244 基础伤害 → DPS +20.2% |
| 11 | flat_cold_attack | BASE | +122.0 |  | 0.17%/1 | 0 | 需要添加 122-244 基础伤害 → DPS +20.2% |
| 12 | lightning_damage_inc | INC | +166.0% | % | 0.12%/% | 188 | INC 188%→354%, 需要 +166 → DPS +20.0% |
| 13 | flat_physical_attack | BASE | +191.5 |  | 0.10%/1 | 0 | 需要添加 192-383 基础伤害 → DPS +20.1% |
| 14 | fire_damage_inc | INC | +447.0% | % | 0.04%/% | 188 | INC 188%→635%, 需要 +447 → DPS +20.0% |

**无影响维度**: physical_damage_inc, cold_damage_inc, chaos_damage_inc, lightning_pen, fire_pen, cold_pen, elemental_pen, chaos_pen, projectile_count, aoe_inc, duration_inc

### 3B. 防御灵敏度（EHP）

| 维度 | 类型 | 所需值 | 每单位 EHP 提升 | 公式 |
|------|------|--------|---------------|------|
| 法术格挡概率 | BASE | 32.5% | +0.59%/单位 | BASE 0→32, 需要 +32 → EHP +19.0% |
| 格挡概率 | BASE | 32.5% | +0.59%/单位 | BASE 0→32, 需要 +32 → EHP +19.0% |
| 生命上限 | INC | 49.0% | +0.41%/单位 | INC 14%→63%, 需要 +49 → EHP +20.1% |
| 闪避值 | BASE | 1598.5 | +0.01%/单位 | BASE 7→1606, 需要 +1598 → EHP +18.6% |
| 护甲固定值 | BASE | 3406.5 | +0.00%/单位 | BASE 0→3406, 需要 +3406 → EHP +15.7% |

**无法达到目标**: 生命固定值, 护甲增加, 闪避增加, 全元素抗性, 火焰抗性, 物理减伤, 混沌抗性, 冰霜抗性, 闪电抗性

### 3C. 恢复增强灵敏度

注入多少恢复属性可使对应恢复指标提升 **20%**：

| 增强属性 | 所需注入 | 当前总值 | 公式 |
|---------|---------|---------|------|
| 魔力恢复速率 | 34.0% | — | INC 0%→34%, 需要 +34 → 魔力恢复 +20.2% |
| 魔力再生 | 36.0/s | 176.5 | BASE 177→213, 需要 +36 → 魔力恢复 +20.4% |

## 4. 防御面

### 4A. 生命池构成

| 资源 | 数值 | 备注 |
|------|------|------|
| Life | 2,905 | — |
| Mana | 4,413 | 可用 4,413 |
| MoM | 100% | 魔力优先承受伤害 |

### 4B. 减伤层

| 层 | 数值 |
|------|------|
| 护甲 | 174 |
| 闪避 | 345 |
| 攻击格挡 | 0% |
| 法术格挡 | 0% |

### 4C. 抗性面板

| 元素 | 当前 | 上限 | 状态 |
|------|------|------|------|
| 火焰 | 74% | 75% | 接近 (差 1%) |
| 冰霜 | 75% | 75% | 满 (+1%溢出) |
| 闪电 | 75% | 75% | 满 (+5%溢出) |
| 混沌 | 42% | 75% | 未满 (差 33%) |

未满抗性: 火焰, 混沌 — 优先补满可显著提升对应元素 EHP。

### 4D. 最大承伤 (MaxHitTaken)

**TotalEHP = 17,967**（平均承受 4.2 次攻击）

| 伤害类型 | MaxHitTaken | 占最强% |
|----------|-------------|--------|
| Physical | 8,303 | 28% ← 最短板 |
| 火焰 | 28,574 | 97% |
| 冰霜 | 29,594 | 100% |
| 闪电 | 29,594 | 100% |
| 混沌 | 14,287 | 48% |

**最短板**: Physical（仅承受 8,303 伤害，为最强的 28%）

### 4E. 承伤乘数 (TakenHitMult)

数值越小越好，表示实际承受伤害占原始伤害的比例。

| 伤害类型 | 承伤乘数 | 含义 |
|----------|---------|------|
| Physical | 0.980 (98.0%) | 每承受 100 伤害实际受 98 ← 最短板 |
| 火焰 | 0.290 (29.0%) | 每承受 100 伤害实际受 29 |
| 冰霜 | 0.280 (28.0%) | 每承受 100 伤害实际受 28 |
| 闪电 | 0.280 (28.0%) | 每承受 100 伤害实际受 28 |
| 混沌 | 0.580 (58.0%) | 每承受 100 伤害实际受 58 |

### 4F. DOT 有效生命

| 伤害类型 | DotEHP |
|----------|--------|
| Physical | 7,318 |
| 火焰 | 28,146 |
| 冰霜 | 29,272 |
| 闪电 | 29,272 |
| 混沌 | 12,617 |


## 5. 资源面

### 5A. 资源预算

| 资源 | 总量 | 可用 | 占用率 |
|------|------|------|--------|
| Life | 2,905 | 2,905 | — |
| Mana | 4,413 | 4,413 | 0% |
| Spirit | 161 | 41 | ⚠️ 75% |

### 5C. 魔力恢复能力

总恢复速率: **161.3/s**（回满可用 4,413 约需 27.4s）

| # | 来源 | 每秒恢复 | 占比 |
|---|------|---------|------|
| 1 | 再生 | 148.3/s | 92% |
| 2 | 回收 | 13.0/s | 8% |

## 6. 已分配天赋价值

### DPS 影响天赋

| # | 天赋 | 类型 | 移除后 DPS% | 移除后 EHP% | 分类 | 效果 |
|---|------|------|-------------|-------------|------|------|
| 1 | Stormcharged | Notable | -13.6% | +0.0% | 输出 | 40% increased Elemental Damage if you've dealt a Critical Hit Recently; 20% increased Critical Hit Chance |
| 2 | Eldritch Battery | Keystone | -11.2% | -5.0% | 兼顾 | Converts all Energy Shield to Mana; Doubles Mana Costs |
| 3 | Deadly Force | Notable | -9.7% | +0.0% | 输出 | 30% increased Damage if you've dealt a Critical Hit in the past 8 seconds; 12% increased Critical Hit Chance |
| 4 | Inspiring Ally | Notable | -9.6% | +0.0% | 输出 | Increases and Reductions to Companion Damage also apply to you |
| 5 | Critical Exploit | Notable | -8.3% | +0.0% | 输出 | 25% increased Critical Hit Chance |
| 6 | Martial Artistry | Notable | -7.9% | +0.0% | 输出 | 25% increased Accuracy Rating with Quarterstaves; 25% increased Critical Damage Bonus with Quarterstaves; +25 to Dexterity |
| 7 | Crashing Wave | Notable | -7.2% | +0.0% | 输出 | 36% increased Damage if you've dealt a Critical Hit in the past 8 seconds |
| 8 | True Strike | Notable | -6.6% | +0.0% | 输出 | +10 to Dexterity; 20% increased Critical Hit Chance |
| 9 | Overflowing Power | Notable | -6.0% | +0.0% | 输出 | +2 to Maximum Power Charges |
| 10 | All Natural | Notable | -5.6% | -4.2% | 兼顾 | +5% to all Elemental Resistances; 30% increased Elemental Damage |
| 11 | Heartstopping | Notable | -5.1% | -0.3% | 兼顾 | +10 to Intelligence; 15% increased Critical Hit Chance |
| 12 | Struck Through | Notable | -5.1% | +0.0% | 输出 | Attacks have +1% to Critical Hit Chance |
| 13 | Throatseeker | Notable | -5.0% | +0.0% | 输出 | 60% increased Critical Damage Bonus; 20% reduced Critical Hit Chance |
| 14 | For the Jugular | Notable | -4.6% | -0.3% | 兼顾 | 25% increased Critical Damage Bonus; +10 to Intelligence |
| 15 | Heartbreaking | Notable | -4.5% | -0.4% | 兼顾 | 25% increased Critical Damage Bonus; +10 to Strength |
| 16 | Whirling Assault | Notable | -4.3% | +0.0% | 输出 | 8% increased Attack Speed with Quarterstaves; Knocks Back Enemies if you get a Critical Hit with a Quarterstaff |
| 17 | The Power Within | Notable | -3.0% | +0.0% | 输出 | 20% increased Critical Damage Bonus if you've gained a Power Charge Recently; +1 to Maximum Power Charges |
| 18 | Material Solidification | Notable | -1.9% | +0.0% | 输出 | Gain 8% of Damage as Extra Physical Damage; 15% increased effect of Fully Broken Armour |
| 19 | The Howling Primate | Notable | -0.2% | -0.3% | 兼顾 | 15% increased Presence Area of Effect; Aura Skills have 10% increased Magnitudes; +10 to Intelligence |

### 纯防御天赋

| 天赋 | 移除后 EHP% | 效果 |
|------|-------------|------|
| Mind Over Matter | -53.3% | All Damage is taken from Mana before Life; 50% less Mana Recovery Rate |
| Chakra of Life | -1.2% | 3% increased maximum Life; 10% increased Life Recovery rate |
| Crimson Power | -20.4% | Gain additional maximum Life equal to 100% of the Item Energy Shield on Equipped Body Armour |
| Grasping Wounds | -11.7% | 25% of Life Loss from Hits is prevented, then that much Life is lost over 4 seconds instead |

### 无效天赋 (16 个)

Sanguimancy, One with the Storm, Blood Barbs, Flow State, Stupefy, Blackflame Covenant, Falcon Dive, The Fabled Stag, Tenfold Attacks, Chakra of Thought, Sanguine Tides, Flow Like Water, Acceleration, Dizzying Hits, Deep Trance, Walker of the Wilds

## 7. 未分配天赋探索

| # | 天赋 | 类型 | DPS% | EHP% | 分类 |
|---|------|------|------|------|------|
| 1 | Careful Assassin | Notable | +12.2% | +0.0% | 输出 |
| 2 | The Frenzied Bear | Notable | +11.7% | +0.4% | 兼顾 |
| 3 | Cooked | Notable | +10.9% | -0.5% | 兼顾 |
| 4 | Overwhelming Strike | Notable | +10.5% | +0.0% | 输出 |
| 5 | Vulgar Methods | Notable | +9.6% | -3.6% | 兼顾 |
| 6 | Serrated Edges | Notable | +9.5% | +0.0% | 输出 |
| 7 | Stimulants | Notable | +8.6% | +0.0% | 输出 |
| 8 | Wild Storm | Notable | +8.6% | +0.0% | 输出 |
| 9 | Imbibed Power | Notable | +8.4% | +0.0% | 输出 |
| 10 | Tainted Strike | Notable | +8.3% | +0.0% | 输出 |

*（另有 154 个候选天赋未显示）*

## 8. 珠宝诊断

### Heart of the Well (Diamond, UNIQUE)

- **DPS 贡献**: +16.9% | **EHP 贡献**: -0.0% | **状态**: ok | **槽位**: Jewel 21984

| Mod | 类型 | 值 | DPS% | EHP% |
|-----|------|-----|------|------|
| DamageGainAsFire | BASE | 14 | +8.5% | -0.0% |
| DamageGainAsLightning | BASE | 13 | +8.3% | -0.0% |
| ManaOnKill | BASE | 1 | -0.0% | -0.0% |
| Condition:CanGainRage | FLAG | true | -0.0% | -0.0% |

### Megalomaniac (Diamond, UNIQUE)

- **DPS 贡献**: +4.0% | **EHP 贡献**: -0.0% | **状态**: ok | **槽位**: Jewel 61834
- **分配天赋**: the spring hare, blood of rage (DPS +4.0%, EHP -0.0%)

| Mod | 类型 | 值 | DPS% | EHP% |
|-----|------|-----|------|------|
| GrantedPassive | LIST | the spring hare | +4.0% | -0.0% |
| GrantedPassive | LIST | blood of rage | -0.0% | -0.0% |

### Undying Hate (Timeless Jewel, UNIQUE)

- **DPS 贡献**: -0.0% | **EHP 贡献**: +3.7% | **状态**: ok | **槽位**: Jewel 61419

| Mod | 类型 | 值 | DPS% | EHP% |
|-----|------|-----|------|------|
| ColdResist | BASE | 9 | -0.0% | +3.7% |
| JewelFunc | LIST | (complex data) | -0.0% | -0.0% |
| JewelData | LIST | (complex data) | -0.0% | -0.0% |

### From Nothing (Diamond, UNIQUE)

- **DPS 贡献**: -0.0% | **EHP 贡献**: -0.0% | **状态**: ok | **槽位**: Jewel 7960

| Mod | 类型 | 值 | DPS% | EHP% |
|-----|------|-----|------|------|
| JewelData | LIST | (complex data) | -0.0% | -0.0% |
| FromNothingKeystones | LIST | (complex data) | -0.0% | -0.0% |

### Maelstrom Hope (Time-Lost Emerald, RARE)

- **DPS 贡献**: -0.0% | **EHP 贡献**: -0.0% | **状态**: ok | **槽位**: Jewel 32763

| Mod | 类型 | 值 | DPS% | EHP% |
|-----|------|-----|------|------|
| JewelData | LIST | (complex data) | -0.0% | -0.0% |
| JewelFunc | LIST | (complex data) | -0.0% | -0.0% |
| JewelFunc | LIST | (complex data) | -0.0% | -0.0% |
| JewelFunc | LIST | (complex data) | -0.0% | -0.0% |

## 9. 光环与精魄分析

### 9A. 现有光环 DPS 贡献

| # | 光环 | 裸光环 DPS | 真实 DPS | EHP | 精魄 |
|---|------|------------|----------|-----|------|
| 1 | Charge Infusion | +40.4% | +42.6% ⚠️模拟 (辅助+2.2%) | +0.5% | 30 |

<details>
<summary><b>Charge Infusion 详细数据</b></summary>

### 辅助贡献

- **Uhtred's Exodus**: +3 level (条件: 无其他辅助)
- 总辅助贡献: **+2.2%** DPS

### 基础数值

- 有效等级: **Lv26** (基础 Lv23 + 辅助 +3)
- MORE per 30 Resonance: **27%**

</details>

| 2 | Wind Dancer ⚔️Gale Force(POB未算) | +0.0% | +0.0% (条件: # of Wind Dancer Stacks=49999) | +1.1% | 30 |

<details>
<summary><b>Wind Dancer 详细数据</b></summary>

### 条件参数范围

| 端点 | 裸光环 | 真实 | 辅助增益 | Speed INC |
|------|--------|------|----------|-----------|
| # of Wind Dancer Stacks=0 | +0.0% | +0.0% | — | 86% |
| # of Wind Dancer Stacks=99999 | +0.0% | +0.0% | — | 86% |

### 基础数值

- 有效等级: **Lv17**
- MORE per 30 Resonance: **1180%**

</details>


**⚠️模拟值说明：**

- **Charge Infusion** (Lv23): 需启用 Charge 配置才能生效，已模拟 F=3/P=8/E=3

**模拟方法说明：**

- **等级前提**：光环模拟基于构筑实际宝石等级数据（非固定 Level 20）
- **裸光环 DPS**：仅光环宝石效果（禁用所有辅助宝石），用于和「潜在光环推荐」对比。真实 DPS 含辅助宝石额外增益，标注在括号中
- **DPS 贡献计算**：移除光环后 DPS 下降百分比（正值=正向贡献）。条件光环需注入参数才能生效，默认注入参数最大值的 50%，标注在真实 DPS 括号中
- **构筑已有 modifier**：攻击速度 INC 86%（来自 POB skillModList），总 MORE ×1.00。INC 叠加为加法（新增边际递减），MORE 叠加为乘法
- **品质上限**：所有宝石品质按 20% 上限计算（游戏实际上限）。构筑中超品质宝石已自动降级
- **条件范围计算**：设置参数绝对值（0 和 max），对比「无光环」DPS。Speed 门槛效果从 POB skillModList 读取端点 INC 差值，边际 = 新增INC / (1+已有INC)
- **期望收益计算**：对于 EC 等随机效果光环，期望 = 效果值 × 受影响技能元素占比之和 ÷ 3（因为随机选择火/冰/电之一）

**纯防御光环**（移除后 EHP 下降）：

- **Wind Dancer**: EHP +1.1%, 精魄 30

### 9B. 潜在光环推荐

| # | 光环 | 精魄 | DPS% | EHP% | 说明 |
|---|------|------|------|------|------|
| 1 | Trinity（三位一体） | 100 | +96.4% | +0.0% | 需精魄 100（缺 59）; 三属性穿透（需要 ResonanceCount 配置） |
| 2 | Attrition（损耗） | 30 | +59.1% | +0.0% | 命中附带 Wither 叠层 |
| 3 | Elemental Conflux（元素交融） | 60 | +19.3% | +0.0% | 需精魄 60（缺 19）; 元素异常状态同步 |
| 4 | Berserk（狂暴） | 30 | +17.0% | +0.0% | MORE Damage + 受伤增加 |

**无 DPS 影响：**

- Archmage（大法师）

### 9C. 精魄辅助推荐

| # | 精魄辅助 | 精魄 | DPS% | 条件 | 来源 |
|---|----------|------|------|------|------|
| 1 | Direstrike II（猛击 II） | 40 | +14.1% | Low Life | 硬编码 |
| 2 | Direstrike I（猛击 I） | 20 | +10.0% | Low Life | 硬编码 |

### 9D. 精魄预算

| 项目 | 精魄 |
|------|------|
| 总精魄 | 161 |
| 已用精魄 | 120 |
| 可用精魄 | 41 |
| 推荐光环消耗 | 220 |
| 推荐后剩余 | -179 |

**注意**: 推荐光环的精魄总消耗超过可用精魄，需要根据优先级取舍。

### 9E. 数据一致性检查

**⚠️ 以下项目需要人工确认：**

- Archmage 无明显 DPS 影响：可能因为构筑条件不满足或模拟环境限制

## 10. 总结与建议

当前 **Flicker Strike** TotalDPS = **12,050,363**，AverageHit = 0，Speed = 1.30/s，CritChance = 64.2%，CritMultiplier = 7.74x。

### ⚔️ 进攻面

**DPS 灵敏度 Top 5**（所需投入越少 = 性价比越高）：

| # | 维度 | 类型 | 当前值 | 所需值 | 公式 |
|---|------|------|--------|--------|------|
| 1 | crit_chance_base | BASE | 1 | +4% | baseCrit 1.0%→4.5%, 需要 +3.5% → DPS +20.3% |
| 2 | crit_multi_base | BASE | 115 | +28% | CritBase 115→144, 需要 +28 → DPS +19.8% |
| 3 | attack_speed_inc | INC | 86 | +38% | INC 86%→124%, 需要 +38 → DPS +20.4% |
| 4 | crit_chance_inc | INC | 146 | +60% | INC 146%→206%, 需要 +60 → DPS +20.0% |
| 5 | attack_damage_inc | INC | 188 | +100% | INC 188%→288%, 需要 +100 → DPS +20.1% |

*穿透维度均无影响（敌人抗性已为负值），面对高抗 Boss 时会成为有效优化方向。*

### 🛡️ 防御面

**最短板**: Physical（承伤仅为最强的 28%）

**防御性价比最高**: 法术格挡概率，需要 +32% 即可提升 EHP +20%

### 💧 资源与恢复

**恢复增强 Top 3**：

1. 魔力恢复速率: INC 0%→34%, 需要 +34 → 魔力恢复 +20.2%
2. 魔力再生: BASE 177→213, 需要 +36 → 魔力恢复 +20.4%

### 🌳 天赋

**推荐点出 Top 5**：

1. **Careful Assassin**: DPS +12.2%
2. **The Frenzied Bear**: DPS +11.7%，EHP +0.4%
3. **Cooked**: DPS +10.9%，EHP -0.5%
4. **Overwhelming Strike**: DPS +10.5%
5. **Vulgar Methods**: DPS +9.6%，EHP -3.6%

**⚠️ 16 个无效天赋**: Sanguimancy, One with the Storm, Blood Barbs, Flow State, Stupefy, Blackflame Covenant, Falcon Dive, The Fabled Stag 等 16 个

### 💎 珠宝

**最佳**: Heart of the Well (DPS +16.9%, EHP -0.0%)
**可替换**: From Nothing, Maelstrom Hope
