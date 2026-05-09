# Living Bomb 构筑全面分析报告

## 0. 执行摘要

### 维度概览

| 维度 | 关键指标 |
|------|---------|
| 进攻 | TotalDPS **31,371** |
| 防御 | TotalEHP **10,596**（最短板: Chaos） |
| 资源 | Spirit 占用 **195%** |
| 恢复 | 生命恢复 **284/s** |


### 关键发现

1. ⚠️ **混沌抗性/防御是最短板**（承伤仅 4,598，为最强的 23%）
2. ⚠️ 混沌抗性差 **75%** 未满
3. 🔴 精魄预算非常紧张（195% 占用）
4. ⚠️ 22 个已分配天赋对 DPS 和 EHP 均无可测量影响
5. 💡 **crit_chance_base** 对 DPS 影响最大（每 1% 提升 6.60% DPS）

### 优化方向 Top 3

1. **crit_chance_base** (BASE): 每 1% 提升 6.60% DPS，需要 +4% 达到 +20% DPS
2. **crit_multi_base** (BASE): 每 1% 提升 0.41% DPS，需要 +50% 达到 +20% DPS
3. **cast_speed_inc** (INC): 每 1% 提升 0.39% DPS，需要 +52% 达到 +20% DPS

## 1. 构筑基线

### 构筑修饰符

| 修饰符 | 总量 | 天赋 | 装备 | 珠宝 |
|--------|------|------|------|------|
| 施法速度 INC | 86% | +35% | +51% | — |
| 伤害 INC | 202% | +162% | — | — |
| 元素伤害 INC | 101% | +72% | +29% | — |
| 暴击率 INC | 66% | +66% | — | — |
| 暴击伤害 INC | 265% | +265% | — | — |
| 伤害 MORE | -30.0% | — | — | — |

### 构筑属性

| 属性 | 数值 |
|------|------|
| 总属性 | 423 |
| 力量 | 131 |
| 敏捷 | 102 |
| 智力 | 190 |
| 命中 | 1,194 |

### 技能 KPI

| 指标 | 数值 |
|------|------|
| 主技能 | Living Bomb |
| 技能类型 | 法术 |
| TotalDPS | **31,371** |
| AverageHit | 7,267 |
| Speed | 4.32/s |
| CritChance | 18.6% |
| CritMultiplier | 4.65x |
| TotalEHP | 10,596 |
| 最短板承伤 | **4,598** (混沌) |

## 2. DPS 来源拆解

活跃伤害类型: Lightning, Cold, Fire

### 通用伤害 INC (Lightning,Cold,Fire) = 232%

**类别汇总**: Tree: +162.0 | Support: +40.0 | Triggered: +30.0

| 来源 | 类别 | 值 |
|------|------|-----|
| Thin Ice | Tree | +50.0 |
| Mysticism II | Support | +40.0 |
| Crashing Wave | Tree | +36.0 |
| Potent Incantation | Tree | +30.0 |
| Damage on Critical | Tree | +20.0 |
| Damage on Critical | Tree | +20.0 |
| Triggered Spell Damage | Triggered | +16.0 |
| Triggered Spell Damage | Triggered | +14.0 |
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

### 通用伤害 MORE (Lightning,Cold,Fire) = +30.0%

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

### 施法速度 = 1.67/s

**类别汇总**: Skill: +1.7

| 来源 | 类别 | 值 |
|------|------|-----|
| 基础施法频率 (1/0.6s) | Skill | +1.7 |

### Speed INC = 159%

**类别汇总**: Item: +51.0 | Aura: +48.0 | Tree: +35.0 | Sim: +25.0

| 来源 | 类别 | 值 |
|------|------|-----|
| Charge Infusion | Aura | +26.0 |
| ⚠ CI speed (模拟) | Sim | +25.0 |
| Damnation Grip, Unset Ring (Ring 2) | Item | +24.0 |
| Trinity | Aura | +22.0 |
| Torment Band, Unset Ring (Ring 1) | Item | +19.0 |
| Acceleration | Tree | +10.0 |
| Hysseg's Claw, Familial Talisman | Item | +8.0 |
| Flow Like Water | Tree | +8.0 |
| Sudden Escalation | Tree | +8.0 |
| Potent Incantation | Tree | -5.0 |
| Skill Speed | Tree | +4.0 |
| Skill Speed | Tree | +4.0 |
| Skill Speed | Tree | +3.0 |
| Skill Speed | Tree | +3.0 |

### CritChance BASE = 18.6% (base 7.0% + added 0%)

**类别汇总**: Skill: +7.0

| 来源 | 类别 | 值 |
|------|------|-----|
| 基础暴击率 | Skill | +7.0 |

### CritChance INC = 66%

**类别汇总**: Tree: +66.0

| 来源 | 类别 | 值 |
|------|------|-----|
| True Strike | Tree | +20.0 |
| Throatseeker | Tree | -20.0 |
| Sudden Escalation | Tree | +16.0 |
| Critical Chance | Tree | +10.0 |
| Critical Chance | Tree | +10.0 |
| Spell Critical Chance | Tree | +10.0 |
| Critical Chance | Tree | +10.0 |
| Critical Chance | Tree | +10.0 |

### CritChance MORE = +60.0%

**类别汇总**: Aura: +27% | Sim: +26%

| 来源 | 类别 | 值 |
|------|------|-----|
| Charge Infusion | Aura | +27.0% MORE |
| ⚠ CI crit (模拟) | Sim | +26.0% MORE |

### CritMultiplier BASE = 100

**类别汇总**: Base: +100.0

| 来源 | 类别 | 值 |
|------|------|-----|
| Base | Base | +100.0 |

### CritMultiplier INC = 265%

**类别汇总**: Tree: +265.0

| 来源 | 类别 | 值 |
|------|------|-----|
| Throatseeker | Tree | +60.0 |
| For the Jugular | Tree | +25.0 |
| Critical Damage when consuming a Power Charge | Tree | +20.0 |
| Critical Damage when consuming a Power Charge | Tree | +20.0 |
| Critical Damage when consuming a Power Charge | Tree | +20.0 |
| Critical Damage | Tree | +15.0 |
| Critical Damage | Tree | +15.0 |
| Critical Damage | Tree | +15.0 |
| Spell Critical Damage | Tree | +15.0 |
| Critical Damage | Tree | +15.0 |
| Critical Damage | Tree | +15.0 |
| Critical Damage | Tree | +15.0 |
| Critical Damage | Tree | +15.0 |

### Lucky Hits (Lightning,Cold,Fire) = 20%

| 来源 | 类别 | 值 |
|------|------|-----|
| The Spring Hare | Jewel | +20.0 |
| The Spring Hare | Jewel | +20.0 |
| The Spring Hare | Jewel | +20.0 |

### Fire → Lightning Conversion/Gain = Fire → Lightning: 增益 22.0%

**类别汇总**: Item: +12.0 | Tree: +10.0

| 来源 | 类别 | 值 |
|------|------|-----|
| Heart of the Well, Diamond (Jewel) | Item | +12.0 (Gain as Lightning) |
| I am the Thunder... | Tree | +10.0 (Gain as Lightning) |

### Fire → Cold Conversion/Gain = Fire → Cold: 增益 10.0%

**类别汇总**: Tree: +10.0

| 来源 | 类别 | 值 |
|------|------|-----|
| I am the Blizzard... | Tree | +10.0 (Gain as Cold) |

### 点燃 DPS = 796

**公式**: `基础 1603-2439 × 0.4层 × effMult 1.5996  (持续 4.40s, 几率 2.3%)`

**类别汇总**: Sim: +2900.0 | Tree: +76.0

| 来源 | 类别 | 值 |
|------|------|-----|
| ⚠ Zenith II (模拟) | Sim | +2,900 |
| Crashing Wave | Tree | +36.0 |
| Damage on Critical | Tree | +20.0 |
| Damage on Critical | Tree | +20.0 |

### Combined DPS = 7,268

**类别汇总**: Hit: +31371.4 | DOT: +796.5

| 来源 | 类别 | 值 |
|------|------|-----|
| Hit DPS | Hit | +31,371 |
| 点燃 DPS | DOT | +796.5 |

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
| 火焰 +0.0% (占75.7%) | Enemy | +0.0 |
| 闪电 +0.0% (占16.3%) | Enemy | +0.0 |
| 冰霜 +0.0% (占8.0%) | Enemy | +0.0 |

## 3. 灵敏度分析

### 3A. 进攻灵敏度（DPS）

| # | 维度 | 类型 | 所需值 | 单位 | 效果/单位 | 当前值 | 公式 |
|---|------|------|--------|------|----------|--------|------|
| 1 | crit_chance_base | BASE | +3.5% | % | 6.60%/% | 0 | baseCrit 0.0%→3.5%, 需要 +3.5% → DPS +23.1% |
| 2 | crit_multi_base | BASE | +49.5% | % | 0.41%/% | 100 | CritBase 100→150, 需要 +50 → DPS +20.3% |
| 3 | cast_speed_inc | INC | +51.5% | % | 0.39%/% | 159 | INC 159%→210%, 需要 +52 → DPS +20.1% |
| 4 | crit_chance_inc | INC | +82.5% | % | 0.24%/% | 66 | INC 66%→148%, 需要 +82 → DPS +20.1% |
| 5 | spell_damage_inc | INC | +87.5% | % | 0.23%/% | 333 | INC 333%→420%, 需要 +88 → DPS +20.2% |
| 6 | elemental_damage_inc | INC | +87.5% | % | 0.23%/% | 333 | INC 333%→420%, 需要 +88 → DPS +20.2% |
| 7 | fire_damage_inc | INC | +114.5% | % | 0.17%/% | 333 | INC 333%→448%, 需要 +114 → DPS +20.0% |
| 8 | crit_multi_inc | INC | +181.0% | % | 0.11%/% | 265 | INC 265%→446%, 需要 +181 → DPS +20.0% |

**无影响维度**: physical_damage_inc, cold_damage_inc, lightning_damage_inc, chaos_damage_inc, lightning_pen, fire_pen, cold_pen, elemental_pen, chaos_pen, projectile_count, aoe_inc, duration_inc

### 3B. 防御灵敏度（EHP）

| 维度 | 类型 | 所需值 | 每单位 EHP 提升 | 公式 |
|------|------|--------|---------------|------|
| 格挡概率 | BASE | 31.5% | +0.65%/单位 | BASE 0→32, 需要 +32 → EHP +20.4% |
| 法术格挡概率 | BASE | 31.5% | +0.65%/单位 | BASE 0→32, 需要 +32 → EHP +20.4% |
| 生命上限 | INC | 48.0% | +0.42%/单位 | INC 5%→53%, 需要 +48 → EHP +20.2% |
| 混沌抗性 | BASE | 69.5% | +0.29%/单位 | BASE 0→70, 需要 +70 → EHP +20.1% |
| 闪避值 | BASE | 1456.0 | +0.01%/单位 | BASE 7→1463, 需要 +1456 → EHP +20.8% |
| 护甲固定值 | BASE | 4852.5 | +0.00%/单位 | BASE 0→4852, 需要 +4852 → EHP +19.8% |

**无法达到目标**: 生命固定值, 冰霜抗性, 闪避增加, 全元素抗性, 物理减伤, 火焰抗性, 护甲增加, 闪电抗性

### 3C. 恢复增强灵敏度

注入多少恢复属性可使对应恢复指标提升 **20%**：

| 增强属性 | 所需注入 | 当前总值 | 公式 |
|---------|---------|---------|------|
| 生命再生 | 9.5/s | — | BASE 0→10, 需要 +10 → 生命恢复 +22.0% |
| 魔力再生 | 12.0/s | 56.4 | BASE 56→68, 需要 +12 → 魔力恢复 +21.3% |
| 生命恢复速率 | 25.5% | — | INC 0%→26%, 需要 +26 → 生命恢复 +20.4% |
| 魔力恢复速率 | 41.5% | — | INC 0%→42%, 需要 +42 → 魔力恢复 +20.1% |

## 4. 防御面

### 4A. 生命池构成

| 资源 | 数值 | 备注 |
|------|------|------|
| Life | 2,272 | — |
| Energy Shield | 1,832 | — |
| Mana | 1,410 | 可用 1,410 |
| MoM | 100% | 魔力优先承受伤害 |

### 4B. 减伤层

| 层 | 数值 |
|------|------|
| 护甲 | 0 |
| 闪避 | 645 |
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

**TotalEHP = 10,596**（平均承受 2.5 次攻击）

| 伤害类型 | MaxHitTaken | 占最强% |
|----------|-------------|--------|
| Physical | 5,514 | 28% |
| 火焰 | 19,693 | 100% |
| 冰霜 | 19,693 | 100% |
| 闪电 | 19,693 | 100% |
| 混沌 | 4,598 | 23% ← 最短板 |

**最短板**: 混沌（仅承受 4,598 伤害，为最强的 23%）

### 4E. 承伤乘数 (TakenHitMult)

数值越小越好，表示实际承受伤害占原始伤害的比例。

| 伤害类型 | 承伤乘数 | 含义 |
|----------|---------|------|
| Physical | 1.000 (100.0%) | 每承受 100 伤害实际受 100 |
| 火焰 | 0.280 (28.0%) | 每承受 100 伤害实际受 28 |
| 冰霜 | 0.280 (28.0%) | 每承受 100 伤害实际受 28 |
| 闪电 | 0.280 (28.0%) | 每承受 100 伤害实际受 28 |
| 混沌 | 1.000 (100.0%) | 每承受 100 伤害实际受 100 ← 最短板 |

### 4F. DOT 有效生命

| 伤害类型 | DotEHP |
|----------|--------|
| Physical | 5,514 |
| 火焰 | 22,056 |
| 冰霜 | 22,056 |
| 闪电 | 22,056 |
| 混沌 | 4,598 |


## 5. 资源面

### 5A. 资源预算

| 资源 | 总量 | 可用 | 占用率 |
|------|------|------|--------|
| Life | 2,272 | 2,272 | — |
| Mana | 1,410 | 1,410 | 0% |
| Spirit | 292 | -278 | 🔴 195% |
| ES | 1,832 | 1,832 | — |

### 5B. 生命恢复能力

总恢复速率: **284.0/s**（回满约 8.0s）
偷取上限利用率: 37%（上限 613/s）

| # | 来源 | 每秒恢复 | 占比 |
|---|------|---------|------|
| 1 | 偷取 | 227.2/s | 80% |
| 2 | 再生 | 56.8/s | 20% |

### 5C. 魔力恢复能力

总恢复速率: **58.1/s**（回满可用 1,410 约需 24.3s）

| # | 来源 | 每秒恢复 | 占比 |
|---|------|---------|------|
| 1 | 再生 | 58.1/s | 100% |

## 6. 已分配天赋价值

### DPS 影响天赋

| # | 天赋 | 类型 | 移除后 DPS% | 移除后 EHP% | 分类 | 效果 |
|---|------|------|-------------|-------------|------|------|
| 1 | Thin Ice | Notable | -11.6% | +0.0% | 输出 | 20% increased Freeze Buildup; 50% increased Damage with Hits against Frozen Enemies |
| 2 | Crashing Wave | Notable | -8.3% | +0.0% | 输出 | 36% increased Damage if you've dealt a Critical Hit in the past 8 seconds |
| 3 | I am the Blizzard... | Notable | -8.0% | +0.0% | 输出 | Gain 10% of Damage as Extra Cold Damage; On Freezing Enemies create Chilled Ground |
| 4 | I am the Thunder... | Notable | -7.2% | +0.0% | 输出 | Gain 10% of Damage as Extra Lightning Damage; 25% chance on Shocking Enemies to created Shocked Ground |
| 5 | All Natural | Notable | -6.9% | +0.0% | 输出 | +5% to all Elemental Resistances; 30% increased Elemental Damage |
| 6 | Sudden Escalation | Notable | -6.9% | +0.0% | 输出 | 16% increased Critical Hit Chance for Spells; 8% increased Cast Speed if you've dealt a Critical Hit Recently |
| 7 | Potent Incantation | Notable | -5.1% | +0.0% | 输出 | 30% increased Spell Damage; 5% reduced Cast Speed |
| 8 | True Strike | Notable | -4.9% | +0.0% | 输出 | +10 to Dexterity; 20% increased Critical Hit Chance |
| 9 | Breaking Point | Notable | -4.7% | +0.0% | 输出 | 10% increased Duration of Elemental Ailments on Enemies; 30% increased Magnitude of Non-Damaging Ailments you inflict |
| 10 | Acceleration | Notable | -3.9% | +0.0% | 输出 | 3% increased Movement Speed; 10% increased Skill Speed |
| 11 | Flow Like Water | Notable | -3.1% | -0.2% | 兼顾 | 8% increased Attack and Cast Speed; +5 to Dexterity and Intelligence |
| 12 | For the Jugular | Notable | -2.8% | -0.4% | 兼顾 | 25% increased Critical Damage Bonus; +10 to Intelligence |
| 13 | Throatseeker | Notable | -2.6% | +0.0% | 输出 | 60% increased Critical Damage Bonus; 20% reduced Critical Hit Chance |
| 14 | The Spring Hare | Notable | -1.3% | +0.0% | 输出 | 20% chance for Damage of Enemies Hitting you to be Unlucky; 20% chance for Damage with Hits to be Lucky |

### 纯防御天赋

| 天赋 | 移除后 EHP% | 效果 |
|------|-------------|------|
| Melding | -3.1% | 40% increased maximum Energy Shield; 10% reduced maximum Mana |
| Mind Over Matter | -27.4% | All Damage is taken from Mana before Life; 50% less Mana Recovery Rate |
| Heavy Buffer | -6.0% | 40% increased maximum Energy Shield; 5% of Damage taken bypasses Energy Shield |

### 无效天赋 (22 个)

Invocated Echoes, ...and I Shall Rage, Impending Doom, Blood Transfusion, Critical Exploit, Energise, Heavy Frost, Dynamism, Marked Agility, Shimmering, Efficient Inscriptions, The Power Within, Overflowing Power, Evocational Practitioner, Moment of Truth, Deadly Force, Careful Assassin, Infusion of Power, Marked for Sickness, Stormwalker, Frostwalker, The Soul Springs Eternal

## 7. 未分配天赋探索

| # | 天赋 | 类型 | DPS% | EHP% | 分类 |
|---|------|------|------|------|------|
| 1 | Stormbreaker | Notable | +18.4% | +0.0% | 输出 |
| 2 | Harness the Elements | Notable | +18.4% | +0.0% | 输出 |
| 3 | Stormcharged | Notable | +13.2% | +0.0% | 输出 |
| 4 | Power of the Storm | Notable | +11.5% | +0.0% | 输出 |
| 5 | The Frenzied Bear | Notable | +11.0% | +0.4% | 兼顾 |
| 6 | Calculated Hunter | Notable | +10.0% | +0.0% | 输出 |
| 7 | Master of Hexes | Notable | +9.7% | +0.0% | 输出 |
| 8 | Arcane Intensity | Notable | +9.7% | +0.0% | 输出 |
| 9 | Jack of all Trades | Notable | +9.2% | +0.0% | 输出 |
| 10 | Invocated Efficiency | Notable | +9.2% | +0.0% | 输出 |

*（另有 172 个候选天赋未显示）*

## 8. 珠宝诊断

### Heart of the Well (Diamond, UNIQUE)

- **DPS 贡献**: +8.5% | **EHP 贡献**: -0.0% | **状态**: ok | **槽位**: Jewel 32763

| Mod | 类型 | 值 | DPS% | EHP% |
|-----|------|-----|------|------|
| DamageGainAsLightning | BASE | 12 | +8.5% | -0.0% |
| ManaOnKill | BASE | 1 | -0.0% | -0.0% |
| HybridManaAndLifeCost_Life | BASE | 3 | -0.0% | -0.0% |
| InstantEnergyShieldLeech | BASE | 15 | -0.0% | -0.0% |
| InstantManaLeech | BASE | 15 | -0.0% | -0.0% |
| InstantLifeLeech | BASE | 15 | -0.0% | -0.0% |

### Rapture Shard (Sapphire, RARE)

- **DPS 贡献**: +3.5% | **EHP 贡献**: +2.4% | **状态**: ok | **槽位**: Jewel 61834

| Mod | 类型 | 值 | DPS% | EHP% |
|-----|------|-----|------|------|
| EnergyShield | INC | 17 | -0.0% | +2.4% |
| ElementalDamage | INC | 15 | +3.5% | -0.0% |
| CurseActivation | INC | 14 | -0.0% | -0.0% |

### Chimeric Spark (Sapphire, RARE)

- **DPS 贡献**: +3.2% | **EHP 贡献**: +2.1% | **状态**: ok | **槽位**: Jewel 7960

| Mod | 类型 | 值 | DPS% | EHP% |
|-----|------|-----|------|------|
| EnergyShield | INC | 15 | -0.0% | +2.1% |
| ElementalDamage | INC | 14 | +3.2% | -0.0% |
| CurseActivation | INC | 15 | -0.0% | -0.0% |

### Megalomaniac (Diamond, UNIQUE)

- **DPS 贡献**: +1.3% | **EHP 贡献**: -0.0% | **状态**: ok | **槽位**: Jewel 21984
- **分配天赋**: the spring hare, savoured blood (DPS +1.3%, EHP -0.0%)

| Mod | 类型 | 值 | DPS% | EHP% |
|-----|------|-----|------|------|
| GrantedPassive | LIST | the spring hare | +1.3% | -0.0% |
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

| # | 光环 | 裸光环 DPS | 真实 DPS | EHP | 精魄 |
|---|------|------------|----------|-----|------|
| 1 | Trinity | +57.5% | +70.7% (辅助+13.2%) (条件: Total Resonance Count=150) | +0.0% | 100 |

<details>
<summary><b>Trinity 详细数据</b></summary>

### 条件参数范围

| 端点 | 裸光环 | 真实 | 辅助增益 | Speed INC |
|------|--------|------|----------|-----------|
| Total Resonance Count=0 | +0.0% | +0.0% | — | 137% |
| Total Resonance Count=300 | +70.2% | +85.8% | +15.6% | 137%→159% |

### 辅助贡献

- **Dialla's Desire**: +1 level, +10% quality
- **Uhtred's Omen**: +3 level (条件: 1个其他辅助)
- 总辅助贡献: **+13.2%** DPS（Total Resonance Count=150时）
- 端点差异: Total Resonance Count=0时+0.0%，Total Resonance Count=300时+15.6%

### 基础数值

- 有效等级: **Lv24** (基础 Lv20 + 辅助 +4)
- MORE per 30 Resonance: **7%**
- Speed INC per quality: **0.75%** (q20 = 15.0% INC)

</details>

| 2 | Elemental Conflux | +23.3% | +23.3% ⚠️模拟 | +0.0% | 60 |

<details>
<summary><b>Elemental Conflux 详细数据</b></summary>

### 基础数值

- 有效等级: **Lv21**
- MORE per 30 Resonance: **60%**

</details>

| 3 | Charge Infusion | +20.8% | +20.8% ⚠️模拟 | +0.0% | 30 |

<details>
<summary><b>Charge Infusion 详细数据</b></summary>

### 基础数值

- 有效等级: **Lv24** (基础 Lv21 + 辅助 +3)
- MORE per 30 Resonance: **26%**

</details>

| 4 | Purity of Fire | +0.0% | +0.0% | +0.0% | 130 |

<details>
<summary><b>Purity of Fire 详细数据</b></summary>

### 基础数值

- 有效等级: **Lv20**
- MORE per 30 Resonance: **41%**

</details>


**⚠️模拟值说明：**

- **Elemental Conflux** (Lv21): 分别注入 70% MORE 到火/冰/电取平均。伤害构成：火 75.7% / 冰 8.0% / 电 16.3%
  三次模拟 DPS：火 7705 / 冰 5320 / 电 5613
- **Charge Infusion** (Lv21): 需启用 Charge 配置才能生效，已模拟 F=3/P=7/E=3

**模拟方法说明：**

- **等级前提**：光环模拟基于构筑实际宝石等级数据（非固定 Level 20）
- **裸光环 DPS**：仅光环宝石效果（禁用所有辅助宝石），用于和「潜在光环推荐」对比。真实 DPS 含辅助宝石额外增益，标注在括号中
- **DPS 贡献计算**：移除光环后 DPS 下降百分比（正值=正向贡献）。条件光环需注入参数才能生效，默认注入参数最大值的 50%，标注在真实 DPS 括号中
- **构筑已有 modifier**：施法速度 INC 159%（来自 POB skillModList），总 MORE ×1.30。INC 叠加为加法（新增边际递减），MORE 叠加为乘法
- **品质上限**：所有宝石品质按 20% 上限计算（游戏实际上限）。构筑中超品质宝石已自动降级
- **条件范围计算**：设置参数绝对值（0 和 max），对比「无光环」DPS。Speed 门槛效果从 POB skillModList 读取端点 INC 差值，边际 = 新增INC / (1+已有INC)
- **期望收益计算**：对于 EC 等随机效果光环，期望 = 效果值 × 受影响技能元素占比之和 ÷ 3（因为随机选择火/冰/电之一）

**DPS/EHP 影响未检测到** (1 个)：

这些光环可能提供非DPS收益（如生存/功能性），或其效果依赖动态条件（如Frenzy Charge）而POB未完全计算。

- **Purity of Fire**: 精魄 130

### 9B. 潜在光环推荐

| # | 光环 | 精魄 | DPS% | EHP% | 说明 |
|---|------|------|------|------|------|
| 1 | Attrition（损耗） | 30 | +59.2% | +0.0% | 需精魄 30（缺 30）; 命中附带 Wither 叠层 |
| 2 | Archmage（大法师） | 100 | +43.1% | +0.0% | 需精魄 100（缺 100）; Mana 转附加闪电伤害 |

**无 DPS 影响：**

- Berserk（狂暴）

### 9C. 精魄辅助推荐

| # | 精魄辅助 | 精魄 | DPS% | 条件 | 来源 |
|---|----------|------|------|------|------|
| 1 | Mysticism II | 30 | +9.2% | 需精魄 30（缺 30） ⚠️估算 | 动态扫描 |
| 2 | Mysticism I | 15 | +6.9% | 需精魄 15（缺 15） ⚠️估算 | 动态扫描 |

### 9D. 精魄预算

| 项目 | 精魄 |
|------|------|
| 总精魄 | 292 |
| 已用精魄 | 292 |
| 可用精魄 | 0 |
| 推荐光环消耗 | 130 |
| 推荐后剩余 | -130 |

**注意**: 推荐光环的精魄总消耗超过可用精魄，需要根据优先级取舍。

### 9E. 数据一致性检查

**⚠️ 以下项目需要人工确认：**

- Elemental Conflux 使用构筑实际等级 Lv21（效果值=70），非满级 Lv20
- Charge Infusion 使用构筑实际等级 Lv21（效果值=26），非满级 Lv20
- Berserk 无明显 DPS 影响：可能因为构筑条件不满足或模拟环境限制

### 9F. POB 未实现效果预估

**⚠️ 以下技能效果在 POB 中未实现，已通过配置模拟：**

| 技能 | 效果描述 | DPS 预估 |
|------|----------|----------|
| **Unbound Avatar** | 40% MORE 元素伤害（Unbound 状态） | **+40.1%** |
| **Pinnacle of Power** | 7 × (15% + 20×0.1%) = 119% MORE 元素伤害（PowerChargesMax） | **+119.0%** |
| **Elemental Conflux** | 元素伤害 MORE（期望 59%×1/3≈20%，等级20，简化模拟） | **+19.9%** |

**注**: 这些效果由 `config/pob_unimplemented_effects.yaml` 配置，
实际游戏效果可能因条件触发方式不同而有差异。

## 10. 总结与建议

当前 **Living Bomb** TotalDPS = **31,371**，AverageHit = 7,267，Speed = 4.32/s，CritChance = 18.6%，CritMultiplier = 4.65x。

### ⚔️ 进攻面

**DPS 灵敏度 Top 5**（所需投入越少 = 性价比越高）：

| # | 维度 | 类型 | 当前值 | 所需值 | 公式 |
|---|------|------|--------|--------|------|
| 1 | crit_chance_base | BASE | 0 | +4% | baseCrit 0.0%→3.5%, 需要 +3.5% → DPS +23.1% |
| 2 | crit_multi_base | BASE | 100 | +50% | CritBase 100→150, 需要 +50 → DPS +20.3% |
| 3 | cast_speed_inc | INC | 159 | +52% | INC 159%→210%, 需要 +52 → DPS +20.1% |
| 4 | crit_chance_inc | INC | 66 | +82% | INC 66%→148%, 需要 +82 → DPS +20.1% |
| 5 | spell_damage_inc | INC | 333 | +88% | INC 333%→420%, 需要 +88 → DPS +20.2% |

*穿透维度均无影响（敌人抗性已为负值），面对高抗 Boss 时会成为有效优化方向。*

### 🛡️ 防御面

**最短板**: Chaos（承伤仅为最强的 23%）

**防御性价比最高**: 格挡概率，需要 +32% 即可提升 EHP +20%

### 💧 资源与恢复

**⚠️ 精魄超载**: 占用 195%，需要缩减光环或精魄辅助

**恢复增强 Top 3**：

1. 生命再生: BASE 0→10, 需要 +10 → 生命恢复 +22.0%
2. 魔力再生: BASE 56→68, 需要 +12 → 魔力恢复 +21.3%
3. 生命恢复速率: INC 0%→26%, 需要 +26 → 生命恢复 +20.4%

### 🌳 天赋

**推荐点出 Top 5**：

1. **Stormbreaker**: DPS +18.4%
2. **Harness the Elements**: DPS +18.4%
3. **Stormcharged**: DPS +13.2%
4. **Power of the Storm**: DPS +11.5%
5. **The Frenzied Bear**: DPS +11.0%，EHP +0.4%

**⚠️ 22 个无效天赋**: Invocated Echoes, ...and I Shall Rage, Impending Doom, Blood Transfusion, Critical Exploit, Energise, Heavy Frost, Dynamism 等 22 个

### 💎 珠宝

**最佳**: Heart of the Well (DPS +8.5%, EHP -0.0%)
**可替换**: Controlled Metamorphosis
