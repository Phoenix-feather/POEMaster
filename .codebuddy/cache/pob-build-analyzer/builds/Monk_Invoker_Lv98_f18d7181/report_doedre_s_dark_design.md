# Doedre's Dark Design 构筑全面分析报告

## 0. 执行摘要

### 维度概览

| 维度 | 关键指标 |
|------|---------|
| 进攻 | TotalDPS **29,662** |
| 防御 | TotalEHP **6,834**（最短板: Chaos） |
| 资源 | Spirit 占用 **129%** |
| 恢复 | 生命恢复 **341/s** |


### 关键发现

1. ⚠️ **混沌抗性/防御是最短板**（承伤仅 4,558，为最强的 53%）
2. ⚠️ 火焰抗性差 **35%** 未满
3. ⚠️ 冰霜抗性差 **36%** 未满
4. ⚠️ 闪电抗性差 **43%** 未满
5. ⚠️ 混沌抗性差 **75%** 未满

### 优化方向 Top 3

1. **crit_chance_base** (BASE): 每 1% 提升 8.76% DPS，需要 +3% 达到 +20% DPS
2. **crit_multi_base** (BASE): 每 1% 提升 0.61% DPS，需要 +33% 达到 +20% DPS
3. **cast_speed_inc** (INC): 每 1% 提升 0.39% DPS，需要 +52% 达到 +20% DPS

## 1. 构筑基线

### 构筑修饰符

| 修饰符 | 总量 | 天赋 | 装备 | 珠宝 |
|--------|------|------|------|------|
| 施法速度 INC | 83% | +19% | +64% | — |
| 伤害 INC | 267% | +227% | — | — |
| 元素伤害 INC | 101% | +72% | +29% | — |
| 暴击率 INC | 251% | +231% | +20% | — |
| 暴击伤害 INC | 260% | +260% | — | — |
| 伤害 MORE | -30.0% | — | — | — |

### 构筑属性

| 属性 | 数值 |
|------|------|
| 总属性 | 346 |
| 力量 | 87 |
| 敏捷 | 92 |
| 智力 | 167 |
| 命中 | 1,134 |

### 技能 KPI

| 指标 | 数值 |
|------|------|
| 主技能 | Doedre's Dark Design |
| 技能类型 | 法术 |
| TotalDPS | **29,662** |
| AverageHit | 11,587 |
| Speed | 2.56/s |
| CritChance | 62.9% |
| CritMultiplier | 3.52x |
| TotalEHP | 6,834 |
| 最短板承伤 | **4,558** (混沌) |

## 2. DPS 来源拆解

活跃伤害类型: Lightning, Cold, Fire, Chaos

### 通用伤害 INC (Lightning,Cold,Fire,Chaos) = 333%

**类别汇总**: Tree: +221.0 | Triggered: +72.0 | Support: +40.0

| 来源 | 类别 | 值 |
|------|------|-----|
| Thin Ice | Tree | +50.0 |
| Dynamism | Tree | +40.0 |
| Mysticism II | Support | +40.0 |
| Crashing Wave | Tree | +36.0 |
| Potent Incantation | Tree | +30.0 |
| Deadly Force | Tree | +25.0 |
| Damage on Critical | Tree | +20.0 |
| Damage on Critical | Tree | +20.0 |
| Triggered Spell Damage | Triggered | +16.0 |
| Triggered Spell Damage | Triggered | +14.0 |
| Triggered Spell Damage | Triggered | +14.0 |
| Triggered Spell Damage | Triggered | +14.0 |
| Triggered Spell Damage | Triggered | +14.0 |

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

### 通用伤害 MORE (Lightning,Cold,Fire,Chaos) = +30.0%

**类别汇总**: Sim: +30%

| 来源 | 类别 | 值 |
|------|------|-----|
| ⚠ Zenith II (模拟) | Sim | +30.0% MORE |

### 元素伤害 MORE (Lightning,Cold,Fire) = +519.0%

**类别汇总**: Sim: +183% | Aura: +56% | Other: +40%

| 来源 | 类别 | 值 |
|------|------|-----|
| ⚠ PoP (模拟) | Sim | +136.0% MORE |
| Trinity | Aura | +56.0% MORE |
| UA_Unbound | Other | +40.0% MORE |
| ⚠ EC (模拟) | Sim | +20.0% MORE |

### 施法速度 = 1.00/s

**类别汇总**: Skill: +1.0

| 来源 | 类别 | 值 |
|------|------|-----|
| 基础施法频率 (1/1s) | Skill | +1.0 |

### Speed INC = 156%

**类别汇总**: Item: +64.0 | Aura: +48.0 | Sim: +25.0 | Tree: +19.0

| 来源 | 类别 | 值 |
|------|------|-----|
| Charge Infusion | Aura | +26.0 |
| ⚠ CI speed (模拟) | Sim | +25.0 |
| Damnation Grip, Unset Ring (Ring 2) | Item | +24.0 |
| Trinity | Aura | +22.0 |
| Adonia's Ego, Siphoning Wand | Item | +21.0 |
| Torment Band, Unset Ring (Ring 1) | Item | +19.0 |
| Flow Like Water | Tree | +8.0 |
| Sudden Escalation | Tree | +8.0 |
| Potent Incantation | Tree | -5.0 |
| Skill Speed | Tree | +4.0 |
| Skill Speed | Tree | +4.0 |

### CritChance BASE = 62.9% (base 7.0% + added 0%)

**类别汇总**: Skill: +7.0

| 来源 | 类别 | 值 |
|------|------|-----|
| 基础暴击率 | Skill | +7.0 |

### CritChance INC = 251%

**类别汇总**: Tree: +231.0 | Item: +20.0

| 来源 | 类别 | 值 |
|------|------|-----|
| Careful Assassin | Tree | +50.0 |
| Critical Exploit | Tree | +25.0 |
| Evocational Practitioner | Tree | +25.0 |
| Adonia's Ego, Siphoning Wand | Item | +20.0 |
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

### CritChance MORE = +156.0%

**类别汇总**: Support: +60% | Aura: +27% | Sim: +26%

| 来源 | 类别 | 值 |
|------|------|-----|
| Pinpoint Critical | Support | +60.0% MORE |
| Charge Infusion | Aura | +27.0% MORE |
| ⚠ CI crit (模拟) | Sim | +26.0% MORE |

### CritMultiplier BASE = 100

**类别汇总**: Base: +100.0

| 来源 | 类别 | 值 |
|------|------|-----|
| Base | Base | +100.0 |

### CritMultiplier INC = 260%

**类别汇总**: Tree: +260.0

| 来源 | 类别 | 值 |
|------|------|-----|
| Throatseeker | Tree | +60.0 |
| For the Jugular | Tree | +25.0 |
| Critical Damage when consuming a Power Charge | Tree | +20.0 |
| Careful Assassin | Tree | -20.0 |
| Critical Damage when consuming a Power Charge | Tree | +20.0 |
| Critical Damage when consuming a Power Charge | Tree | +20.0 |
| Critical Damage | Tree | +15.0 |
| Critical Damage | Tree | +15.0 |
| Critical Damage | Tree | +15.0 |
| Critical Damage | Tree | +15.0 |
| Spell Critical Damage | Tree | +15.0 |
| Critical Damage | Tree | +15.0 |
| Critical Damage | Tree | +15.0 |
| Critical Damage | Tree | +15.0 |
| Critical Damage | Tree | +15.0 |

### CritMultiplier MORE = -30.0%

**类别汇总**: Support: +-30%

| 来源 | 类别 | 值 |
|------|------|-----|
| Pinpoint Critical | Support | +-30.0% MORE |

### Lucky Hits (Lightning,Cold,Fire,Chaos) = 20%

| 来源 | 类别 | 值 |
|------|------|-----|
| The Spring Hare | Jewel | +20.0 |
| The Spring Hare | Jewel | +20.0 |
| The Spring Hare | Jewel | +20.0 |
| The Spring Hare | Jewel | +20.0 |

### Chaos → Lightning Conversion/Gain = Chaos → Lightning: 增益 27.0%

**类别汇总**: Item: +17.0 | Tree: +10.0

| 来源 | 类别 | 值 |
|------|------|-----|
| Heart of the Well, Diamond (Jewel) | Item | +12.0 (Gain as Lightning) |
| I am the Thunder... | Tree | +10.0 (Gain as Lightning) |
| Adonia's Ego, Siphoning Wand | Item | +5.0 (Gain as Lightning) |

### Chaos → Cold Conversion/Gain = Chaos → Cold: 增益 15.0%

**类别汇总**: Tree: +10.0 | Item: +5.0

| 来源 | 类别 | 值 |
|------|------|-----|
| I am the Blizzard... | Tree | +10.0 (Gain as Cold) |
| Adonia's Ego, Siphoning Wand | Item | +5.0 (Gain as Cold) |

### Chaos → Fire Conversion/Gain = Chaos → Fire: 增益 63.0%

**类别汇总**: Item: +63.0

| 来源 | 类别 | 值 |
|------|------|-----|
| Sacred Flame, Shrine Sceptre | Item | +58.0 (Gain as Fire) |
| Adonia's Ego, Siphoning Wand | Item | +5.0 (Gain as Fire) |

### 点燃 DPS = 343

**公式**: `基础 988-1848 × 0.2层 × effMult 1.6770  (持续 4.40s, 几率 2.0%)`

**类别汇总**: Sim: +2900.0 | Tree: +141.0

| 来源 | 类别 | 值 |
|------|------|-----|
| ⚠ Zenith II (模拟) | Sim | +2,900 |
| Dynamism | Tree | +40.0 |
| Crashing Wave | Tree | +36.0 |
| Deadly Force | Tree | +25.0 |
| Damage on Critical | Tree | +20.0 |
| Damage on Critical | Tree | +20.0 |

### Combined DPS = 30,005

**类别汇总**: Hit: +29661.7 | DOT: +343.1

| 来源 | 类别 | 值 |
|------|------|-----|
| Hit DPS | Hit | +29,662 |
| 点燃 DPS | DOT | +343.1 |

### 敌人受伤增加 = x1.2900

**公式**: `所有伤害类型共享 x1.2900`

**类别汇总**: Ailment: +29.0

| 来源 | 类别 | 值 |
|------|------|-----|
| Shock: 受伤+29% | Ailment | +29.0 |

### 敌人抗性乘区 (加权) = +0.0%

**公式**: `+0.0%  (抗性 50% - 穿透 0% = 有效 50%)`

**类别汇总**: Enemy: +50.0

| 来源 | 类别 | 值 |
|------|------|-----|
| 火焰 +0.0% (占56.6%) | Enemy | +0.0 |
| 闪电 +0.0% (占24.9%) | Enemy | +0.0 |
| 冰霜 +0.0% (占13.9%) | Enemy | +0.0 |
| 混沌 +0.0% (占4.6%) | Enemy | +0.0 |

## 3. 灵敏度分析

### 3A. 进攻灵敏度（DPS）

| # | 维度 | 类型 | 所需值 | 单位 | 效果/单位 | 当前值 | 公式 |
|---|------|------|--------|------|----------|--------|------|
| 1 | crit_chance_base | BASE | +3.0% | % | 8.76%/% | 0 | baseCrit 0.0%→3.0%, 需要 +3.0% → DPS +26.3% |
| 2 | crit_multi_base | BASE | +33.0% | % | 0.61%/% | 100 | CritBase 100→133, 需要 +33 → DPS +20.2% |
| 3 | cast_speed_inc | INC | +51.5% | % | 0.39%/% | 156 | INC 156%→208%, 需要 +52 → DPS +20.3% |
| 4 | spell_damage_inc | INC | +105.5% | % | 0.19%/% | 434 | INC 434%→540%, 需要 +106 → DPS +20.2% |
| 5 | crit_chance_inc | INC | +114.5% | % | 0.17%/% | 251 | INC 251%→366%, 需要 +114 → DPS +20.0% |
| 6 | elemental_damage_inc | INC | +118.0% | % | 0.17%/% | 434 | INC 434%→552%, 需要 +118 → DPS +20.1% |
| 7 | crit_multi_inc | INC | +118.0% | % | 0.17%/% | 260 | INC 260%→378%, 需要 +118 → DPS +20.2% |
| 8 | fire_damage_inc | INC | +197.5% | % | 0.10%/% | 434 | INC 434%→632%, 需要 +198 → DPS +20.0% |
| 9 | lightning_damage_inc | INC | +449.0% | % | 0.04%/% | 434 | INC 434%→883%, 需要 +449 → DPS +20.0% |

**无影响维度**: physical_damage_inc, cold_damage_inc, chaos_damage_inc, lightning_pen, fire_pen, cold_pen, elemental_pen, chaos_pen, projectile_count, aoe_inc, duration_inc

### 3B. 防御灵敏度（EHP）

| 维度 | 类型 | 所需值 | 每单位 EHP 提升 | 公式 |
|------|------|--------|---------------|------|
| 全元素抗性 | BASE | 18.5% | +1.03%/单位 | BASE -29→-10, 需要 +18 → EHP +19.0% |
| 格挡概率 | BASE | 31.5% | +0.65%/单位 | BASE 0→32, 需要 +32 → EHP +20.4% |
| 法术格挡概率 | BASE | 31.5% | +0.65%/单位 | BASE 0→32, 需要 +32 → EHP +20.4% |
| 生命上限 | INC | 49.0% | +0.41%/单位 | INC 5%→54%, 需要 +49 → EHP +20.1% |
| 闪避值 | BASE | 1701.0 | +0.01%/单位 | BASE 7→1708, 需要 +1701 → EHP +20.6% |

**无法达到目标**: 生命固定值, 冰霜抗性, 闪避增加, 混沌抗性, 护甲固定值, 物理减伤, 火焰抗性, 护甲增加, 闪电抗性

### 3C. 恢复增强灵敏度

注入多少恢复属性可使对应恢复指标提升 **20%**：

| 增强属性 | 所需注入 | 当前总值 | 公式 |
|---------|---------|---------|------|
| 魔力再生 | 12.0/s | 60.2 | BASE 60→72, 需要 +12 → 魔力恢复 +20.0% |
| 生命再生 | 19.5/s | — | BASE 0→20, 需要 +20 → 生命恢复 +20.4% |
| 生命恢复速率 | 25.5% | — | INC 0%→26%, 需要 +26 → 生命恢复 +20.4% |
| 魔力恢复速率 | 41.0% | — | INC 0%→41%, 需要 +41 → 魔力恢复 +19.8% |

## 4. 防御面

### 4A. 生命池构成

| 资源 | 数值 | 备注 |
|------|------|------|
| Life | 2,180 | — |
| Energy Shield | 1,745 | — |
| Mana | 1,505 | 可用 1,505 |
| MoM | 100% | 魔力优先承受伤害 |

### 4B. 减伤层

| 层 | 数值 |
|------|------|
| 护甲 | 0 |
| 闪避 | 537 |
| 攻击格挡 | 0% |
| 法术格挡 | 0% |

### 4C. 抗性面板

| 元素 | 当前 | 上限 | 状态 |
|------|------|------|------|
| 火焰 | 40% | 75% | 未满 (差 35%) |
| 冰霜 | 39% | 75% | 未满 (差 36%) |
| 闪电 | 32% | 75% | 未满 (差 43%) |
| 混沌 | 0% | 75% | 未满 (差 75%) |

未满抗性: 火焰, 冰霜, 闪电, 混沌 — 优先补满可显著提升对应元素 EHP。

### 4D. 最大承伤 (MaxHitTaken)

**TotalEHP = 6,834**（平均承受 1.6 次攻击）

| 伤害类型 | MaxHitTaken | 占最强% |
|----------|-------------|--------|
| Physical | 5,430 | 63% |
| 火焰 | 8,619 | 100% |
| 冰霜 | 8,484 | 98% |
| 闪电 | 7,648 | 89% |
| 混沌 | 4,558 | 53% ← 最短板 |

**最短板**: 混沌（仅承受 4,558 伤害，为最强的 53%）

### 4E. 承伤乘数 (TakenHitMult)

数值越小越好，表示实际承受伤害占原始伤害的比例。

| 伤害类型 | 承伤乘数 | 含义 |
|----------|---------|------|
| Physical | 1.000 (100.0%) | 每承受 100 伤害实际受 100 |
| 火焰 | 0.630 (63.0%) | 每承受 100 伤害实际受 63 |
| 冰霜 | 0.640 (64.0%) | 每承受 100 伤害实际受 64 |
| 闪电 | 0.710 (71.0%) | 每承受 100 伤害实际受 71 |
| 混沌 | 1.000 (100.0%) | 每承受 100 伤害实际受 100 ← 最短板 |

### 4F. DOT 有效生命

| 伤害类型 | DotEHP |
|----------|--------|
| Physical | 5,430 |
| 火焰 | 9,050 |
| 冰霜 | 8,902 |
| 闪电 | 7,985 |
| 混沌 | 4,558 |


## 5. 资源面

### 5A. 资源预算

| 资源 | 总量 | 可用 | 占用率 |
|------|------|------|--------|
| Life | 2,180 | 2,180 | — |
| Mana | 1,505 | 1,505 | 0% |
| Spirit | 425 | -125 | 🔴 129% |
| ES | 1,745 | 1,745 | — |

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

| # | 天赋 | 类型 | 移除后 DPS% | 移除后 EHP% | 分类 | 效果 |
|---|------|------|-------------|-------------|------|------|
| 1 | Thin Ice | Notable | -9.5% | +0.0% | 输出 | 20% increased Freeze Buildup; 50% increased Damage with Hits against Frozen Enemies |
| 2 | I am the Blizzard... | Notable | -9.2% | +0.0% | 输出 | Gain 10% of Damage as Extra Cold Damage; On Freezing Enemies create Chilled Ground |
| 3 | I am the Thunder... | Notable | -9.0% | +0.0% | 输出 | Gain 10% of Damage as Extra Lightning Damage; 25% chance on Shocking Enemies to created Shocked Ground |
| 4 | Dynamism | Notable | -7.6% | +0.0% | 输出 | 40% increased Damage if you've Triggered a Skill Recently; Meta Skills gain 15% increased Energy |
| 5 | Throatseeker | Notable | -7.3% | +0.0% | 输出 | 60% increased Critical Damage Bonus; 20% reduced Critical Hit Chance |
| 6 | Crashing Wave | Notable | -6.9% | +0.0% | 输出 | 36% increased Damage if you've dealt a Critical Hit in the past 8 seconds |
| 7 | Deadly Force | Notable | -6.4% | +0.0% | 输出 | 25% increased Damage if you've dealt a Critical Hit in the past 8 seconds; 10% increased Critical Hit Chance |
| 8 | Sudden Escalation | Notable | -5.8% | +0.0% | 输出 | 16% increased Critical Hit Chance for Spells; 8% increased Cast Speed if you've dealt a Critical Hit Recently |
| 9 | Careful Assassin | Notable | -5.8% | +0.0% | 输出 | 20% reduced Critical Damage Bonus; 50% increased Critical Hit Chance |
| 10 | All Natural | Notable | -5.1% | -4.2% | 兼顾 | +5% to all Elemental Resistances; 30% increased Elemental Damage |
| 11 | Breaking Point | Notable | -4.7% | +0.0% | 输出 | 10% increased Duration of Elemental Ailments on Enemies; 30% increased Magnitude of Non-Damaging Ailments you inflict |
| 12 | For the Jugular | Notable | -4.4% | -0.4% | 兼顾 | 25% increased Critical Damage Bonus; +10 to Intelligence |
| 13 | Critical Exploit | Notable | -4.4% | +0.0% | 输出 | 25% increased Critical Hit Chance |
| 14 | Evocational Practitioner | Notable | -4.4% | +0.0% | 输出 | 25% increased Critical Hit Chance if you've Triggered a Skill Recently; Meta Skills gain 25% increased Energy if you've dealt a Critical Hit Recently |
| 15 | Potent Incantation | Notable | -3.9% | +0.0% | 输出 | 30% increased Spell Damage; 5% reduced Cast Speed |
| 16 | True Strike | Notable | -3.5% | +0.0% | 输出 | +10 to Dexterity; 20% increased Critical Hit Chance |
| 17 | Flow Like Water | Notable | -3.1% | -0.2% | 兼顾 | 8% increased Attack and Cast Speed; +5 to Dexterity and Intelligence |
| 18 | Moment of Truth | Notable | -2.6% | +0.0% | 输出 | 25% increased Critical Damage Bonus if you've dealt a Non-Critical Hit Recently; 15% increased Critical Hit Chance |
| 19 | The Spring Hare | Notable | -1.9% | +0.0% | 输出 | 20% chance for Damage of Enemies Hitting you to be Unlucky; 20% chance for Damage with Hits to be Lucky |

### 纯防御天赋

| 天赋 | 移除后 EHP% | 效果 |
|------|-------------|------|
| Melding | -3.0% | 40% increased maximum Energy Shield; 10% reduced maximum Mana |
| The Power Within | +9.7% | 20% increased Critical Damage Bonus if you've gained a Power Charge Recently; +1 to Maximum Power Charges |
| Overflowing Power | +21.6% | +2 to Maximum Power Charges |
| Mind Over Matter | -29.8% | All Damage is taken from Mana before Life; 50% less Mana Recovery Rate |
| Heavy Buffer | -6.1% | 40% increased maximum Energy Shield; 5% of Damage taken bypasses Energy Shield |

### 无效天赋 (15 个)

Invocated Echoes, ...and I Shall Rage, Impending Doom, Blood Transfusion, Energise, Heavy Frost, Marked Agility, Shimmering, Efficient Inscriptions, Infusion of Power, Marked for Sickness, Acceleration, Stormwalker, Frostwalker, The Soul Springs Eternal

## 7. 未分配天赋探索

| # | 天赋 | 类型 | DPS% | EHP% | 分类 |
|---|------|------|------|------|------|
| 1 | Avatar of Fire | Keystone | +19.7% | +0.0% | 输出 |
| 2 | Dark Entries | Notable | +19.7% | +0.0% | 输出 |
| 3 | Stormbreaker | Notable | +15.2% | +0.0% | 输出 |
| 4 | Harness the Elements | Notable | +15.2% | +0.0% | 输出 |
| 5 | Cooked | Notable | +10.2% | -4.6% | 兼顾 |
| 6 | The Frenzied Bear | Notable | +9.9% | +0.4% | 兼顾 |
| 7 | Stormcharged | Notable | +9.6% | +0.0% | 输出 |
| 8 | Power of the Storm | Notable | +9.5% | +0.0% | 输出 |
| 9 | Master of Hexes | Notable | +9.1% | +0.0% | 输出 |
| 10 | Arcane Intensity | Notable | +8.6% | +0.0% | 输出 |

*（另有 173 个候选天赋未显示）*

## 8. 珠宝诊断

### Heart of the Well (Diamond, UNIQUE)

- **DPS 贡献**: +10.7% | **EHP 贡献**: -0.0% | **状态**: ok | **槽位**: Jewel 32763

| Mod | 类型 | 值 | DPS% | EHP% |
|-----|------|-----|------|------|
| DamageGainAsLightning | BASE | 12 | +10.7% | -0.0% |
| ManaOnKill | BASE | 1 | -0.0% | -0.0% |
| HybridManaAndLifeCost_Life | BASE | 3 | -0.0% | -0.0% |
| InstantEnergyShieldLeech | BASE | 15 | -0.0% | -0.0% |
| InstantManaLeech | BASE | 15 | -0.0% | -0.0% |
| InstantLifeLeech | BASE | 15 | -0.0% | -0.0% |

### Controlled Metamorphosis (Diamond, UNIQUE)

- **DPS 贡献**: -0.0% | **EHP 贡献**: -5.6% | **状态**: ok | **槽位**: Jewel 61419

| Mod | 类型 | 值 | DPS% | EHP% |
|-----|------|-----|------|------|
| JewelData | LIST | (complex data) | -0.0% | -0.0% |
| JewelData | LIST | (complex data) | -0.0% | -0.0% |
| ElementalResist | BASE | -6 | -0.0% | -5.6% |

### Rapture Shard (Sapphire, RARE)

- **DPS 贡献**: +2.5% | **EHP 贡献**: +2.4% | **状态**: ok | **槽位**: Jewel 61834

| Mod | 类型 | 值 | DPS% | EHP% |
|-----|------|-----|------|------|
| EnergyShield | INC | 17 | -0.0% | +2.4% |
| ElementalDamage | INC | 15 | +2.5% | -0.0% |
| CurseActivation | INC | 14 | -0.0% | -0.0% |

### Chimeric Spark (Sapphire, RARE)

- **DPS 贡献**: +2.4% | **EHP 贡献**: +2.1% | **状态**: ok | **槽位**: Jewel 7960

| Mod | 类型 | 值 | DPS% | EHP% |
|-----|------|-----|------|------|
| EnergyShield | INC | 15 | -0.0% | +2.1% |
| ElementalDamage | INC | 14 | +2.4% | -0.0% |
| CurseActivation | INC | 15 | -0.0% | -0.0% |

### Megalomaniac (Diamond, UNIQUE)

- **DPS 贡献**: +1.9% | **EHP 贡献**: -0.0% | **状态**: ok | **槽位**: Jewel 21984
- **分配天赋**: the spring hare, savoured blood (DPS +1.9%, EHP -0.0%)

| Mod | 类型 | 值 | DPS% | EHP% |
|-----|------|-----|------|------|
| GrantedPassive | LIST | the spring hare | +1.9% | -0.0% |
| GrantedPassive | LIST | savoured blood | -0.0% | -0.0% |

## 9. 光环与精魄分析

### 9A. 现有光环 DPS 贡献

| # | 光环 | 裸光环 DPS | 真实 DPS | EHP | 精魄 |
|---|------|------------|----------|-----|------|
| 1 | Trinity | +48.7% | +60.3% (辅助+11.5%) (条件: Total Resonance Count=150) | +0.0% | 100 |

<details>
<summary><b>Trinity 详细数据</b></summary>

### 条件参数范围

| 端点 | 裸光环 | 真实 | 辅助增益 | Speed INC |
|------|--------|------|----------|-----------|
| Total Resonance Count=0 | +0.0% | +0.0% | — | 134% |
| Total Resonance Count=300 | +59.2% | +72.7% | +13.5% | 134%→156% |

### 辅助贡献

- **Dialla's Desire**: +1 level, +10% quality
- **Uhtred's Omen**: +3 level (条件: 1个其他辅助)
- 总辅助贡献: **+11.5%** DPS（Total Resonance Count=150时）
- 端点差异: Total Resonance Count=0时+0.0%，Total Resonance Count=300时+13.5%

### 基础数值

- 有效等级: **Lv24** (基础 Lv20 + 辅助 +4)
- MORE per 30 Resonance: **7%**
- Speed INC per quality: **0.75%** (q20 = 15.0% INC)

</details>

| 2 | Charge Infusion | +26.9% | +26.9% ⚠️模拟 | +0.0% | 30 |

<details>
<summary><b>Charge Infusion 详细数据</b></summary>

### 基础数值

- 有效等级: **Lv24** (基础 Lv21 + 辅助 +3)
- MORE per 30 Resonance: **26%**

</details>

| 3 | Elemental Conflux | +16.9% | +16.9% ⚠️模拟 | +0.0% | 60 |

<details>
<summary><b>Elemental Conflux 详细数据</b></summary>

### 基础数值

- 有效等级: **Lv21**
- MORE per 30 Resonance: **60%**

</details>

| 4 | Purity of Fire | +0.0% | +0.0% | +11.2% | 130 |

<details>
<summary><b>Purity of Fire 详细数据</b></summary>

### 基础数值

- 有效等级: **Lv20**
- MORE per 30 Resonance: **41%**

</details>


**⚠️模拟值说明：**

- **Charge Infusion** (Lv21): 需启用 Charge 配置才能生效，已模拟 F=3/P=8/E=3
- **Elemental Conflux** (Lv21): 分别注入 70% MORE 到火/冰/电取平均。伤害构成：火 59.4% / 冰 14.6% / 电 26.0%
  三次模拟 DPS：火 7428 / 冰 6132 / 电 6469

**模拟方法说明：**

- **等级前提**：光环模拟基于构筑实际宝石等级数据（非固定 Level 20）
- **裸光环 DPS**：仅光环宝石效果（禁用所有辅助宝石），用于和「潜在光环推荐」对比。真实 DPS 含辅助宝石额外增益，标注在括号中
- **DPS 贡献计算**：移除光环后 DPS 下降百分比（正值=正向贡献）。条件光环需注入参数才能生效，默认注入参数最大值的 50%，标注在真实 DPS 括号中
- **构筑已有 modifier**：施法速度 INC 156%（来自 POB skillModList），总 MORE ×1.30。INC 叠加为加法（新增边际递减），MORE 叠加为乘法
- **品质上限**：所有宝石品质按 20% 上限计算（游戏实际上限）。构筑中超品质宝石已自动降级
- **条件范围计算**：设置参数绝对值（0 和 max），对比「无光环」DPS。Speed 门槛效果从 POB skillModList 读取端点 INC 差值，边际 = 新增INC / (1+已有INC)
- **期望收益计算**：对于 EC 等随机效果光环，期望 = 效果值 × 受影响技能元素占比之和 ÷ 3（因为随机选择火/冰/电之一）

**纯防御光环**（移除后 EHP 下降）：

- **Purity of Fire**: EHP +11.2%, 精魄 130

### 9B. 潜在光环推荐

| # | 光环 | 精魄 | DPS% | EHP% | 说明 |
|---|------|------|------|------|------|
| 1 | Attrition（损耗） | 30 | +59.2% | +0.0% | 需精魄 30（缺 30）; 命中附带 Wither 叠层 |
| 2 | Archmage（大法师） | 100 | +53.4% | +0.0% | 需精魄 100（缺 100）; Mana 转附加闪电伤害 |

**无 DPS 影响：**

- Berserk（狂暴）

### 9C. 精魄辅助推荐

| # | 精魄辅助 | 精魄 | DPS% | 条件 | 来源 |
|---|----------|------|------|------|------|
| 1 | Mysticism II | 30 | +7.6% | 需精魄 30（缺 30） ⚠️估算 | 动态扫描 |
| 2 | Mysticism I | 15 | +5.7% | 需精魄 15（缺 15） ⚠️估算 | 动态扫描 |

### 9D. 精魄预算

| 项目 | 精魄 |
|------|------|
| 总精魄 | 425 |
| 已用精魄 | 425 |
| 可用精魄 | 0 |
| 推荐光环消耗 | 130 |
| 推荐后剩余 | -130 |

**注意**: 推荐光环的精魄总消耗超过可用精魄，需要根据优先级取舍。

### 9E. 数据一致性检查

**⚠️ 以下项目需要人工确认：**

- Charge Infusion 使用构筑实际等级 Lv21（效果值=26），非满级 Lv20
- Elemental Conflux 使用构筑实际等级 Lv21（效果值=70），非满级 Lv20
- Berserk 无明显 DPS 影响：可能因为构筑条件不满足或模拟环境限制

### 9F. POB 未实现效果预估

**⚠️ 以下技能效果在 POB 中未实现，已通过配置模拟：**

| 技能 | 效果描述 | DPS 预估 |
|------|----------|----------|
| **Unbound Avatar** | 40% MORE 元素伤害（Unbound 状态） | **+35.3%** |
| **Pinnacle of Power** | 8 × (15% + 20×0.1%) = 136% MORE 元素伤害（PowerChargesMax） | **+119.8%** |
| **Elemental Conflux** | 元素伤害 MORE（期望 59%×1/3≈20%，等级20，简化模拟） | **+17.5%** |

**注**: 这些效果由 `config/pob_unimplemented_effects.yaml` 配置，
实际游戏效果可能因条件触发方式不同而有差异。

## 10. 总结与建议

当前 **Doedre's Dark Design** TotalDPS = **29,662**，AverageHit = 11,587，Speed = 2.56/s，CritChance = 62.9%，CritMultiplier = 3.52x。

### ⚔️ 进攻面

**DPS 灵敏度 Top 5**（所需投入越少 = 性价比越高）：

| # | 维度 | 类型 | 当前值 | 所需值 | 公式 |
|---|------|------|--------|--------|------|
| 1 | crit_chance_base | BASE | 0 | +3% | baseCrit 0.0%→3.0%, 需要 +3.0% → DPS +26.3% |
| 2 | crit_multi_base | BASE | 100 | +33% | CritBase 100→133, 需要 +33 → DPS +20.2% |
| 3 | cast_speed_inc | INC | 156 | +52% | INC 156%→208%, 需要 +52 → DPS +20.3% |
| 4 | spell_damage_inc | INC | 434 | +106% | INC 434%→540%, 需要 +106 → DPS +20.2% |
| 5 | crit_chance_inc | INC | 251 | +114% | INC 251%→366%, 需要 +114 → DPS +20.0% |

*穿透维度均无影响（敌人抗性已为负值），面对高抗 Boss 时会成为有效优化方向。*

### 🛡️ 防御面

**最短板**: Chaos（承伤仅为最强的 53%）

**防御性价比最高**: 全元素抗性，需要 +18% 即可提升 EHP +20%

### 💧 资源与恢复

**⚠️ 精魄超载**: 占用 129%，需要缩减光环或精魄辅助

**恢复增强 Top 3**：

1. 魔力再生: BASE 60→72, 需要 +12 → 魔力恢复 +20.0%
2. 生命再生: BASE 0→20, 需要 +20 → 生命恢复 +20.4%
3. 生命恢复速率: INC 0%→26%, 需要 +26 → 生命恢复 +20.4%

### 🌳 天赋

**推荐点出 Top 5**：

1. **Avatar of Fire**: DPS +19.7%
2. **Dark Entries**: DPS +19.7%
3. **Stormbreaker**: DPS +15.2%
4. **Harness the Elements**: DPS +15.2%
5. **Cooked**: DPS +10.2%，EHP -4.6%

**⚠️ 15 个无效天赋**: Invocated Echoes, ...and I Shall Rage, Impending Doom, Blood Transfusion, Energise, Heavy Frost, Marked Agility, Shimmering 等 15 个

### 💎 珠宝

**最佳**: Heart of the Well (DPS +10.7%, EHP -0.0%)
