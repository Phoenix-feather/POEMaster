# Spark 构筑全面分析报告

## 0. 执行摘要

### 维度概览

| 维度 | 关键指标 |
|------|---------|
| 进攻 | TotalDPS **302,301** |
| 防御 | TotalEHP **15,312**（最短板: Chaos） |
| 资源 | Spirit 占用 **191%** |
| 恢复 | 生命恢复 **224/s** |


### 关键发现

1. ⚠️ **混沌抗性/防御是最短板**（承伤仅 5,613，为最强的 19%）
2. ⚠️ 混沌抗性差 **75%** 未满
3. 🔴 精魄预算非常紧张（191% 占用）
4. ⚠️ 17 个已分配天赋对 DPS 和 EHP 均无可测量影响
5. 💡 **crit_multi_base** 对 DPS 影响最大（每 1% 提升 0.69% DPS）

### 优化方向 Top 3

1. **crit_multi_base** (BASE): 每 1% 提升 0.69% DPS，需要 +28% 达到 +20% DPS
2. **cast_speed_inc** (INC): 每 1% 提升 0.39% DPS，需要 +52% 达到 +20% DPS
3. **crit_multi_inc** (INC): 每 1% 提升 0.23% DPS，需要 +87% 达到 +20% DPS

## 1. 构筑基线

### 构筑修饰符

| 修饰符 | 总量 | 天赋 | 装备 | 珠宝 |
|--------|------|------|------|------|
| 施法速度 INC | 82% | +28% | +54% | — |
| 伤害 INC | 322% | +140% | +62% | +80% |
| 元素伤害 INC | 121% | +100% | +21% | — |
| 暴击率 INC | 224% | +200% | +24% | — |
| 暴击伤害 INC | 204% | +192% | +12% | — |

### 构筑属性

| 属性 | 数值 |
|------|------|
| 总属性 | 411 |
| 力量 | 116 |
| 敏捷 | 103 |
| 智力 | 192 |
| 命中 | 1,206 |

### 技能 KPI

| 指标 | 数值 |
|------|------|
| 主技能 | Spark |
| 技能类型 | 法术, 投射物 |
| TotalDPS | **302,301** |
| AverageHit | 82,339 |
| Speed | 3.67/s |
| CritChance | 79.2% |
| CritMultiplier | 4.04x |
| TotalEHP | 15,312 |
| 最短板承伤 | **5,613** (混沌) |

## 2. DPS 来源拆解

活跃伤害类型: Lightning, Cold

### 通用伤害 INC (Lightning,Cold) = 322%

**类别汇总**: Tree: +140.0 | Jewel: +80.0 | Item: +62.0 | Skill: +40.0

| 来源 | 类别 | 值 |
|------|------|-----|
| Thin Ice | Tree | +50.0 |
| Dynamism | Tree | +40.0 |
| Mysticism II | Skill | +40.0 |
| Potent Incantation | Tree | +30.0 |
| Sorrow Finger, Unset Ring (Ring 1) | Item | +25.0 |
| Rage Turn, Unset Ring (Ring 2) | Item | +25.0 |
| Megalomaniac, Diamond → Harness the Elements | Jewel | +20.0 |
| Megalomaniac, Diamond → Harness the Elements | Jewel | +20.0 |
| Megalomaniac, Diamond → Harness the Elements | Jewel | +20.0 |
| Megalomaniac, Diamond → Harness the Elements | Jewel | +20.0 |
| Damage on Critical | Tree | +20.0 |
| Bramble Cut, Sapphire (Jewel) | Item | +12.0 |

### 元素伤害 INC (Lightning,Cold) = 121%

**类别汇总**: Tree: +100.0 | Item: +21.0

| 来源 | 类别 | 值 |
|------|------|-----|
| Stormcharged | Tree | +40.0 |
| All Natural | Tree | +30.0 |
| Yoke of Suffering, Bloodstone Amulet (Amulet) | Item | +21.0 |
| Elemental Damage | Tree | +10.0 |
| Elemental Damage | Tree | +10.0 |
| Elemental Damage | Tree | +10.0 |

### 闪电伤害 INC (Lightning) = 24%

**类别汇总**: Item: +24.0

| 来源 | 类别 | 值 |
|------|------|-----|
| Sorrow Finger, Unset Ring (Ring 1) | Item | +24.0 |

### 冰霜伤害 INC (Cold) = 10%

**类别汇总**: Tree: +10.0

| 来源 | 类别 | 值 |
|------|------|-----|
| Cold Damage | Tree | +10.0 |

### 通用伤害 MORE (Lightning,Cold) = +56.0%

**类别汇总**: Sim: +30% | Skill: +20%

| 来源 | 类别 | 值 |
|------|------|-----|
| ⚠ Zenith II (模拟) | Sim | +30.0% MORE |
| Deliberation | Skill | +20.0% MORE |

### 元素伤害 MORE (Lightning,Cold) = +457.6%

**类别汇总**: Sim: +163% | Skill: +112%

| 来源 | 类别 | 值 |
|------|------|-----|
| ⚠ PoP (模拟) | Sim | +119.0% MORE |
| Trinity | Skill | +56.0% MORE |
| Rising Tempest | Skill | +36.0% MORE |
| ⚠ EC (模拟) | Sim | +20.0% MORE |

### 施法速度 = 1.43/s

**类别汇总**: Skill: +1.4

| 来源 | 类别 | 值 |
|------|------|-----|
| 基础施法频率 (1/0.7s) | Skill | +1.4 |

### Speed INC = 157%

**类别汇总**: Item: +54.0 | Skill: +49.0 | Tree: +28.0 | Sim: +26.0

| 来源 | 类别 | 值 |
|------|------|-----|
| Charge Infusion | Skill | +27.0 |
| ⚠ CI speed (模拟) | Sim | +26.0 |
| Rage Turn, Unset Ring (Ring 2) | Item | +24.0 |
| Sorrow Finger, Unset Ring (Ring 1) | Item | +22.0 |
| Trinity | Skill | +22.0 |
| Acceleration | Tree | +10.0 |
| Hysseg's Claw, Familial Talisman | Item | +8.0 |
| Sudden Escalation | Tree | +8.0 |
| Practiced Signs | Tree | +6.0 |
| Potent Incantation | Tree | -5.0 |
| Skill Speed | Tree | +3.0 |
| Cast Speed | Tree | +3.0 |
| Skill Speed | Tree | +3.0 |

### CritChance BASE = 79.2% (base 15.0% + added 0%)

**类别汇总**: Skill: +15.0

| 来源 | 类别 | 值 |
|------|------|-----|
| 基础暴击率 | Skill | +15.0 |

### CritChance INC = 224%

**类别汇总**: Tree: +200.0 | Item: +24.0

| 来源 | 类别 | 值 |
|------|------|-----|
| Careful Assassin | Tree | +50.0 |
| Evocational Practitioner | Tree | +25.0 |
| True Strike | Tree | +20.0 |
| Throatseeker | Tree | -20.0 |
| Sudden Escalation | Tree | +16.0 |
| Stormcharged | Tree | +15.0 |
| Blight Wound, Sapphire (Jewel) | Item | +14.0 |
| Spell Critical Chance | Tree | +12.0 |
| Spell Critical Chance | Tree | +12.0 |
| Bramble Cut, Sapphire (Jewel) | Item | +10.0 |
| Spell Critical Chance | Tree | +10.0 |
| Critical Chance | Tree | +10.0 |
| Critical Chance | Tree | +10.0 |
| Spell Critical Chance | Tree | +10.0 |
| Spell Critical Chance | Tree | +10.0 |
| Critical Chance | Tree | +10.0 |
| Energy and Critical Chance | Tree | +5.0 |
| Energy and Critical Chance | Tree | +5.0 |

### CritChance MORE = +63.0%

**类别汇总**: Skill: +28% | Sim: +27%

| 来源 | 类别 | 值 |
|------|------|-----|
| Charge Infusion | Skill | +28.0% MORE |
| ⚠ CI crit (模拟) | Sim | +27.0% MORE |

### CritMultiplier BASE = 100

**类别汇总**: Base: +100.0

| 来源 | 类别 | 值 |
|------|------|-----|
| Base | Base | +100.0 |

### CritMultiplier INC = 204%

**类别汇总**: Tree: +192.0 | Item: +12.0

| 来源 | 类别 | 值 |
|------|------|-----|
| Throatseeker | Tree | +60.0 |
| Gore Spike | Tree | +37.0 |
| For the Jugular | Tree | +25.0 |
| Careful Assassin | Tree | -20.0 |
| Critical Damage | Tree | +15.0 |
| Critical Damage | Tree | +15.0 |
| Spell Critical Damage | Tree | +15.0 |
| Spell Critical Damage | Tree | +15.0 |
| Critical Damage | Tree | +15.0 |
| Critical Damage | Tree | +15.0 |
| Heart of the Well, Diamond (Jewel) | Item | +12.0 |

### Lucky Hits (Lightning,Cold) = 20%

| 来源 | 类别 | 值 |
|------|------|-----|
| The Spring Hare | Tree | +20.0 |
| The Spring Hare | Tree | +20.0 |

### Lightning → Cold Conversion/Gain = Lightning → Cold: 增益 30.0%

**类别汇总**: Skill: +30.0

| 来源 | 类别 | 值 |
|------|------|-----|
| Freezing Mark | Skill | +30.0 (Gain as Cold) |

### Cold-Infused 弹体数量 BASE = 17

**类别汇总**: SkillEffect: +17.0

| 来源 | 类别 | 值 |
|------|------|-----|
| Cold-Infused效果 | SkillEffect | +17.0 |

### 敌人受伤增加 = x2.2400

**公式**: `所有伤害类型共享 x2.2400`

**类别汇总**: Item: +96.0 | Ailment: +28.0

| 来源 | 类别 | 值 |
|------|------|-----|
| Shock: 受伤+28% | Ailment | +28.0 |
| Yoke of Suffering: 每种元素异常+24%，当前4种=+96%（最多5种=+120%） | Item | +96.0 |

### 敌人抗性乘区 (加权) = +16.0%

**公式**: `+16.0%  (抗性 50% - 穿透 8% = 有效 42%)`

**类别汇总**: Enemy: +50.0 | Penetration: +8.0

| 来源 | 类别 | 值 |
|------|------|-----|
| 闪电 +16.0% (占77.3%) | Enemy | +16.0 |
| 冰霜 +16.0% (占22.7%) | Enemy | +16.0 |

## 3. 灵敏度分析

### 3A. 进攻灵敏度（DPS）

| # | 维度 | 类型 | 所需值 | 单位 | 效果/单位 | 当前值 | 公式 |
|---|------|------|--------|------|----------|--------|------|
| 1 | crit_multi_base | BASE | +28.5% | % | 0.69%/% | 100 | CritBase 100→128, 需要 +28 → DPS +19.8% |
| 2 | cast_speed_inc | INC | +51.5% | % | 0.39%/% | 157 | INC 157%→208%, 需要 +52 → DPS +20.2% |
| 3 | crit_multi_inc | INC | +87.0% | % | 0.23%/% | 204 | INC 204%→291%, 需要 +87 → DPS +20.2% |
| 4 | spell_damage_inc | INC | +113.0% | % | 0.18%/% | 467 | INC 467%→580%, 需要 +113 → DPS +20.0% |
| 5 | projectile_damage_inc | INC | +113.0% | % | 0.18%/% | 467 | INC 467%→580%, 需要 +113 → DPS +20.0% |
| 6 | elemental_damage_inc | INC | +113.0% | % | 0.18%/% | 467 | INC 467%→580%, 需要 +113 → DPS +20.0% |
| 7 | lightning_damage_inc | INC | +146.5% | % | 0.14%/% | 467 | INC 467%→614%, 需要 +146 → DPS +20.0% |
| 8 | cold_damage_inc | INC | +488.0% | % | 0.04%/% | 453 | INC 453%→941%, 需要 +488 → DPS +20.0% |

**无影响维度**: physical_damage_inc, fire_damage_inc, chaos_damage_inc, crit_chance_inc, crit_chance_base, lightning_pen, fire_pen, cold_pen, elemental_pen, chaos_pen, projectile_count, aoe_inc, duration_inc

### 3B. 防御灵敏度（EHP）

| 维度 | 类型 | 所需值 | 每单位 EHP 提升 | 公式 |
|------|------|--------|---------------|------|
| 法术格挡概率 | BASE | 29.5% | +0.69%/单位 | BASE 0→30, 需要 +30 → EHP +20.3% |
| 格挡概率 | BASE | 29.5% | +0.69%/单位 | BASE 0→30, 需要 +30 → EHP +20.3% |
| 混沌抗性 | BASE | 55.0% | +0.37%/单位 | BASE 0→55, 需要 +55 → EHP +20.1% |
| 生命上限 | INC | 83.0% | +0.24%/单位 | INC 5%→88%, 需要 +83 → EHP +20.1% |
| 闪避值 | BASE | 1641.5 | +0.01%/单位 | BASE 142→1784, 需要 +1642 → EHP +21.1% |
| 护甲固定值 | BASE | 2292.0 | +0.01%/单位 | BASE 0→2292, 需要 +2292 → EHP +20.4% |

**无法达到目标**: 闪电抗性, 生命固定值, 全元素抗性, 冰霜抗性, 物理减伤, 护甲增加, 闪避增加, 火焰抗性

### 3C. 恢复增强灵敏度

注入多少恢复属性可使对应恢复指标提升 **20%**：

| 增强属性 | 所需注入 | 当前总值 | 公式 |
|---------|---------|---------|------|
| 生命再生 | 7.5/s | — | BASE 0→8, 需要 +8 → 生命恢复 +21.4% |
| 魔力再生 | 7.5/s | 35.8 | BASE 36→43, 需要 +8 → 魔力恢复 +22.3% |
| 魔力恢复速率 | 20.0% | — | INC 0%→20%, 需要 +20 → 魔力恢复 +20.1% |
| 生命恢复速率 | 20.5% | — | INC 0%→20%, 需要 +20 → 生命恢复 +20.4% |

## 4. 防御面

### 4A. 生命池构成

| 资源 | 数值 | 备注 |
|------|------|------|
| Life | 1,865 | — |
| Energy Shield | 5,706 | — |
| Mana | 895 | 可用 895 |
| MoM | 100% | 魔力优先承受伤害 |

### 4B. 减伤层

| 层 | 数值 |
|------|------|
| 护甲 | 0 |
| 闪避 | 763 |
| 攻击格挡 | 0% |
| 法术格挡 | 0% |

### 4C. 抗性面板

| 元素 | 当前 | 上限 | 状态 |
|------|------|------|------|
| 火焰 | 75% | 75% | 满 (+55%溢出) |
| 冰霜 | 75% | 75% | 满 (+64%溢出) |
| 闪电 | 75% | 75% | 满 (+48%溢出) |
| 混沌 | 0% | 75% | 未满 (差 75%) |

未满抗性: 混沌 — 优先补满可显著提升对应元素 EHP。

过度堆叠: 火焰, 冰霜, 闪电 — 超出上限 20%+，可考虑将属性分配到其他维度。

### 4D. 最大承伤 (MaxHitTaken)

**TotalEHP = 15,312**（平均承受 3.6 次攻击）

| 伤害类型 | MaxHitTaken | 占最强% |
|----------|-------------|--------|
| Physical | 8,466 | 28% |
| 火焰 | 30,236 | 100% |
| 冰霜 | 30,236 | 100% |
| 闪电 | 30,236 | 100% |
| 混沌 | 5,613 | 19% ← 最短板 |

**最短板**: 混沌（仅承受 5,613 伤害，为最强的 19%）

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
| Physical | 8,466 |
| 火焰 | 33,864 |
| 冰霜 | 33,864 |
| 闪电 | 33,864 |
| 混沌 | 5,613 |


## 5. 资源面

### 5A. 资源预算

| 资源 | 总量 | 可用 | 占用率 |
|------|------|------|--------|
| Life | 1,865 | 1,865 | — |
| Mana | 895 | 895 | 0% |
| Spirit | 277 | -253 | 🔴 191% |
| ES | 5,706 | 5,706 | — |

### 5B. 生命恢复能力

总恢复速率: **223.8/s**（回满约 8.3s）
偷取上限利用率: 45%（上限 418/s）

| # | 来源 | 每秒恢复 | 占比 |
|---|------|---------|------|
| 1 | 偷取 | 186.5/s | 83% |
| 2 | 再生 | 37.3/s | 17% |

### 5C. 魔力恢复能力

总恢复速率: **17.9/s**（回满可用 895 约需 50.0s）

| # | 来源 | 每秒恢复 | 占比 |
|---|------|---------|------|
| 1 | 再生 | 17.9/s | 100% |

## 6. 已分配天赋价值

### DPS 影响天赋

| # | 天赋 | 类型 | 移除后 DPS% | 移除后 EHP% | 分类 | 效果 |
|---|------|------|-------------|-------------|------|------|
| 1 | Heavy Frost | Notable | -42.0% | +0.0% | 输出 | 20% increased Freeze Buildup; Hits ignore non-negative Elemental Resistances of Frozen Enemies |
| 2 | Sunder the Flesh | Notable | -28.3% | +0.0% | 输出 | Base Critical Hit Chance for Spells is 15% |
| 3 | Throatseeker | Notable | -10.4% | +0.0% | 输出 | 60% increased Critical Damage Bonus; 20% reduced Critical Hit Chance |
| 4 | Stormcharged | Notable | -10.1% | +0.0% | 输出 | 40% increased Elemental Damage if you've dealt a Critical Hit Recently; 15% increased Critical Hit Chance |
| 5 | Thin Ice | Notable | -8.9% | +0.0% | 输出 | 20% increased Freeze Buildup; 50% increased Damage with Hits against Frozen Enemies |
| 6 | Gore Spike | Notable | -8.6% | +0.0% | 输出 | 1% increased Critical Damage Bonus per 50 current Life |
| 7 | Dynamism | Notable | -7.1% | +0.0% | 输出 | 40% increased Damage if you've Triggered a Skill Recently; Meta Skills gain 15% increased Energy |
| 8 | Careful Assassin | Notable | -7.0% | +0.0% | 输出 | 20% reduced Critical Damage Bonus; 50% increased Critical Hit Chance |
| 9 | Sudden Escalation | Notable | -6.5% | +0.0% | 输出 | 16% increased Critical Hit Chance for Spells; 8% increased Cast Speed if you've dealt a Critical Hit Recently |
| 10 | For the Jugular | Notable | -5.8% | -0.3% | 兼顾 | 25% increased Critical Damage Bonus; +10 to Intelligence |
| 11 | The Spring Hare | Notable | -5.7% | +0.0% | 输出 | 20% chance for Damage of Enemies Hitting you to be Unlucky; 20% chance for Damage with Hits to be Lucky |
| 12 | Evocational Practitioner | Notable | -5.5% | +0.0% | 输出 | 25% increased Critical Hit Chance if you've Triggered a Skill Recently; Meta Skills gain 25% increased Energy if you've dealt a Critical Hit Recently |
| 13 | All Natural | Notable | -5.3% | +0.0% | 输出 | +5% to all Elemental Resistances; 30% increased Elemental Damage |
| 14 | True Strike | Notable | -4.4% | +0.0% | 输出 | +10 to Dexterity; 20% increased Critical Hit Chance |
| 15 | Acceleration | Notable | -3.9% | +0.0% | 输出 | 3% increased Movement Speed; 10% increased Skill Speed |
| 16 | Potent Incantation | Notable | -3.5% | +0.0% | 输出 | 30% increased Spell Damage; 5% reduced Cast Speed |
| 17 | Breaking Point | Notable | -2.7% | +0.0% | 输出 | 10% increased Duration of Elemental Ailments on Enemies; 30% increased Magnitude of Non-Damaging Ailments you inflict |
| 18 | Practiced Signs | Notable | -2.3% | +0.0% | 输出 | 6% increased Cast Speed |

### 纯防御天赋

| 天赋 | 移除后 EHP% | 效果 |
|------|-------------|------|
| Melding | -3.0% | 40% increased maximum Energy Shield; 10% reduced maximum Mana |
| Mind Over Matter | -12.2% | All Damage is taken from Mana before Life; 50% less Mana Recovery Rate |
| Dampening Shield | -3.1% | 28% increased maximum Energy Shield; Gain additional Ailment Threshold equal to 12% of maximum Energy Shield; Gain additional Stun Threshold equal to 12% of maximum Energy Shield |
| Pure Energy | -3.6% | 30% increased maximum Energy Shield; +10 to Intelligence |
| Heavy Buffer | -3.3% | 40% increased maximum Energy Shield; 5% of Damage taken bypasses Energy Shield |

### 无效天赋 (17 个)

Invocated Echoes, Sacrificial Blood, Blood Transfusion, Echoing Thunder, Energise, Echoing Frost, Invocated Efficiency, Overflowing Power, Echoing Flames, Stormbreaker, Deadly Force, Sanguine Tides, Vitality Siphon, Marked Agility, Critical Overload, Infusion of Power, Sanguimancy

## 7. 未分配天赋探索

| # | 天赋 | 类型 | DPS% | EHP% | 分类 |
|---|------|------|------|------|------|
| 1 | Stand and Deliver | Notable | +14.1% | +0.0% | 输出 |
| 2 | Cooked | Notable | +13.9% | -3.9% | 兼顾 |
| 3 | Barbaric Strength | Notable | +10.5% | +0.3% | 兼顾 |
| 4 | The Frenzied Bear | Notable | +9.4% | +0.3% | 兼顾 |
| 5 | Power of the Storm | Notable | +8.9% | +0.0% | 输出 |
| 6 | Calculated Hunter | Notable | +8.8% | +0.0% | 输出 |
| 7 | Sitting Duck | Notable | +7.6% | +0.0% | 输出 |
| 8 | Pure Power | Notable | +7.4% | +0.0% | 输出 |
| 9 | Jack of all Trades | Notable | +7.1% | +0.0% | 输出 |
| 10 | Heavy Ammunition | Notable | +7.1% | +0.0% | 输出 |

*（另有 162 个候选天赋未显示）*

## 8. 珠宝诊断

### Megalomaniac (Diamond, UNIQUE)

- **DPS 贡献**: +14.2% | **EHP 贡献**: -0.0% | **状态**: ok | **槽位**: Jewel 21984
- **分配天赋**: invocated limit, harness the elements (DPS +14.2%, EHP -0.0%)

| Mod | 类型 | 值 | DPS% | EHP% |
|-----|------|-----|------|------|
| GrantedPassive | LIST | invocated limit | -0.0% | -0.0% |
| GrantedPassive | LIST | harness the elements | +14.2% | -0.0% |

### Bramble Cut (Sapphire, RARE)

- **DPS 贡献**: +4.3% | **EHP 贡献**: +2.0% | **状态**: ok | **槽位**: Jewel 61834

| Mod | 类型 | 值 | DPS% | EHP% |
|-----|------|-----|------|------|
| Damage | INC | 12 | +2.1% | -0.0% |
| EnergyShield | INC | 17 | -0.0% | +2.0% |
| CritChance | INC | 10 | +2.2% | -0.0% |

### Blight Wound (Sapphire, RARE)

- **DPS 贡献**: +3.9% | **EHP 贡献**: +2.3% | **状态**: ok | **槽位**: Jewel 7960

| Mod | 类型 | 值 | DPS% | EHP% |
|-----|------|-----|------|------|
| EnergyShield | INC | 20 | -0.0% | +2.3% |
| CritChance | INC | 14 | +3.0% | -0.0% |
| AilmentMagnitude | INC | 11 | +0.9% | -0.0% |

### Heart of the Well (Diamond, UNIQUE)

- **DPS 贡献**: +2.8% | **EHP 贡献**: -0.0% | **状态**: ok | **槽位**: Jewel 32763

| Mod | 类型 | 值 | DPS% | EHP% |
|-----|------|-----|------|------|
| CritMultiplier | INC | 12 | +2.8% | -0.0% |
| PierceChance | BASE | 47 | -0.0% | -0.0% |
| ManaOnKill | BASE | 1 | -0.0% | -0.0% |
| InstantEnergyShieldLeech | BASE | 14 | -0.0% | -0.0% |
| InstantManaLeech | BASE | 14 | -0.0% | -0.0% |
| InstantLifeLeech | BASE | 14 | -0.0% | -0.0% |

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
| 1 | Trinity | +65.8% | +70.5% (辅助+4.6%) (条件: Total Resonance Count=150) | +0.0% | 100 |

<details>
<summary><b>Trinity 详细数据</b></summary>

### 条件参数范围

| 端点 | 裸光环 | 真实 | 辅助增益 | Speed INC |
|------|--------|------|----------|-----------|
| Total Resonance Count=0 | +0.0% | +0.0% | — | 135% |
| Total Resonance Count=300 | +80.8% | +85.9% | +5.1% | 135%→157% |

### 辅助贡献

- **Dialla's Desire**: +1 level, +10% quality
- **Lightning Mastery**: +1 level
- 总辅助贡献: **+4.6%** DPS（Total Resonance Count=150时）
- 端点差异: Total Resonance Count=0时+0.0%，Total Resonance Count=300时+5.1%

### 基础数值

- 有效等级: **Lv24** (基础 Lv23 + 辅助 +1)
- MORE per 30 Resonance: **7%**
- Speed INC per quality: **0.75%** (q20 = 15.0% INC)

</details>

| 2 | Charge Infusion | +31.2% | +31.2% ⚠️模拟 | +0.0% | 30 |

<details>
<summary><b>Charge Infusion 详细数据</b></summary>

### 基础数值

- 有效等级: **Lv27** (基础 Lv24 + 辅助 +3)
- MORE per 30 Resonance: **27%**

</details>

| 3 | Elemental Conflux | +24.7% | +24.7% ⚠️模拟 | +0.0% | 60 |

<details>
<summary><b>Elemental Conflux 详细数据</b></summary>

### 基础数值

- 有效等级: **Lv28** (基础 Lv25 + 辅助 +3)
- MORE per 30 Resonance: **67%**

</details>

| 4 | Purity of Fire | +0.0% | +0.0% | +0.0% | 130 |

<details>
<summary><b>Purity of Fire 详细数据</b></summary>

### 基础数值

- 有效等级: **Lv20**
- MORE per 30 Resonance: **41%**

</details>

| 5 | Combat Frenzy | +0.0% | +0.0% | +0.0% | 30 |

<details>
<summary><b>Combat Frenzy 详细数据</b></summary>

### 基础数值

- 有效等级: **Lv13**
- MORE per 30 Resonance: **6800%**

</details>


**⚠️模拟值说明：**

- **Charge Infusion** (Lv24): 需启用 Charge 配置才能生效，已模拟 F=3/P=4/E=3
- **Elemental Conflux** (Lv25): 分别注入 74% MORE 到火/冰/电取平均。伤害构成：火 0.0% / 冰 22.7% / 电 77.3%
  三次模拟 DPS：火 67457 / 冰 78781 / 电 106058

**模拟方法说明：**

- **等级前提**：光环模拟基于构筑实际宝石等级数据（非固定 Level 20）
- **裸光环 DPS**：仅光环宝石效果（禁用所有辅助宝石），用于和「潜在光环推荐」对比。真实 DPS 含辅助宝石额外增益，标注在括号中
- **DPS 贡献计算**：移除光环后 DPS 下降百分比（正值=正向贡献）。条件光环需注入参数才能生效，默认注入参数最大值的 50%，标注在真实 DPS 括号中
- **构筑已有 modifier**：施法速度 INC 157%（来自 POB skillModList），总 MORE ×1.56。INC 叠加为加法（新增边际递减），MORE 叠加为乘法
- **品质上限**：所有宝石品质按 20% 上限计算（游戏实际上限）。构筑中超品质宝石已自动降级
- **条件范围计算**：设置参数绝对值（0 和 max），对比「无光环」DPS。Speed 门槛效果从 POB skillModList 读取端点 INC 差值，边际 = 新增INC / (1+已有INC)
- **期望收益计算**：对于 EC 等随机效果光环，期望 = 效果值 × 受影响技能元素占比之和 ÷ 3（因为随机选择火/冰/电之一）

**DPS/EHP 影响未检测到** (2 个)：

这些光环可能提供非DPS收益（如生存/功能性），或其效果依赖动态条件（如Frenzy Charge）而POB未完全计算。

- **Purity of Fire**: 精魄 130
- **Combat Frenzy**: 精魄 30

### 9B. 潜在光环推荐

| # | 光环 | 精魄 | DPS% | EHP% | 说明 |
|---|------|------|------|------|------|
| 1 | Attrition（损耗） | 30 | +59.2% | +0.0% | 需精魄 30（缺 30）; 命中附带 Wither 叠层 |
| 2 | Archmage（大法师） | 100 | +24.7% | +0.0% | 需精魄 100（缺 100）; Mana 转附加闪电伤害 |

**无 DPS 影响：**

- Berserk（狂暴）

### 9C. 精魄辅助推荐

| # | 精魄辅助 | 精魄 | DPS% | 条件 | 来源 |
|---|----------|------|------|------|------|
| 1 | Mysticism II | 30 | +7.1% | 需精魄 30（缺 30） ⚠️估算 | 动态扫描 |
| 2 | Mysticism I | 15 | +5.3% | 需精魄 15（缺 15） ⚠️估算 | 动态扫描 |

### 9D. 精魄预算

| 项目 | 精魄 |
|------|------|
| 总精魄 | 277 |
| 已用精魄 | 277 |
| 可用精魄 | 0 |
| 推荐光环消耗 | 130 |
| 推荐后剩余 | -130 |

**注意**: 推荐光环的精魄总消耗超过可用精魄，需要根据优先级取舍。

### 9E. 数据一致性检查

**⚠️ 以下项目需要人工确认：**

- Charge Infusion 使用构筑实际等级 Lv24（效果值=27），非满级 Lv20
- Elemental Conflux 使用构筑实际等级 Lv25（效果值=74），非满级 Lv20
- Berserk 无明显 DPS 影响：可能因为构筑条件不满足或模拟环境限制

### 9F. POB 未实现效果预估

**⚠️ 以下技能效果在 POB 中未实现，已通过配置模拟：**

| 技能 | 效果描述 | DPS 预估 |
|------|----------|----------|
| **Pinnacle of Power** | 4 × (15% + 20×0.1%) = 68% MORE 元素伤害（PowerChargesMax） | **+68.1%** |
| **Elemental Conflux** | 元素伤害 MORE（期望 59%×1/3≈20%，等级20，简化模拟） | **+20.0%** |

**注**: 这些效果由 `config/pob_unimplemented_effects.yaml` 配置，
实际游戏效果可能因条件触发方式不同而有差异。

## 10. 总结与建议

当前 **Spark** TotalDPS = **302,301**，AverageHit = 82,339，Speed = 3.67/s，CritChance = 79.2%，CritMultiplier = 4.04x。

### ⚔️ 进攻面

**DPS 灵敏度 Top 5**（所需投入越少 = 性价比越高）：

| # | 维度 | 类型 | 当前值 | 所需值 | 公式 |
|---|------|------|--------|--------|------|
| 1 | crit_multi_base | BASE | 100 | +28% | CritBase 100→128, 需要 +28 → DPS +19.8% |
| 2 | cast_speed_inc | INC | 157 | +52% | INC 157%→208%, 需要 +52 → DPS +20.2% |
| 3 | crit_multi_inc | INC | 204 | +87% | INC 204%→291%, 需要 +87 → DPS +20.2% |
| 4 | spell_damage_inc | INC | 467 | +113% | INC 467%→580%, 需要 +113 → DPS +20.0% |
| 5 | projectile_damage_inc | INC | 467 | +113% | INC 467%→580%, 需要 +113 → DPS +20.0% |

*穿透维度均无影响（敌人抗性已为负值），面对高抗 Boss 时会成为有效优化方向。*

### 🛡️ 防御面

**最短板**: Chaos（承伤仅为最强的 19%）

**防御性价比最高**: 法术格挡概率，需要 +30% 即可提升 EHP +20%

### 💧 资源与恢复

**⚠️ 精魄超载**: 占用 191%，需要缩减光环或精魄辅助

**恢复增强 Top 3**：

1. 生命再生: BASE 0→8, 需要 +8 → 生命恢复 +21.4%
2. 魔力再生: BASE 36→43, 需要 +8 → 魔力恢复 +22.3%
3. 魔力恢复速率: INC 0%→20%, 需要 +20 → 魔力恢复 +20.1%

### 🌳 天赋

**推荐点出 Top 5**：

1. **Stand and Deliver**: DPS +14.1%
2. **Cooked**: DPS +13.9%，EHP -3.9%
3. **Barbaric Strength**: DPS +10.5%，EHP +0.3%
4. **The Frenzied Bear**: DPS +9.4%，EHP +0.3%
5. **Power of the Storm**: DPS +8.9%

**⚠️ 17 个无效天赋**: Invocated Echoes, Sacrificial Blood, Blood Transfusion, Echoing Thunder, Energise, Echoing Frost, Invocated Efficiency, Overflowing Power 等 17 个

### 💎 珠宝

**最佳**: Megalomaniac (DPS +14.2%, EHP -0.0%)
**可替换**: Controlled Metamorphosis
