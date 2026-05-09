# Comet 构筑全面分析报告

## 0. 执行摘要

### 维度概览

| 维度 | 关键指标 |
|------|---------|
| 进攻 | TotalDPS **492,350** |
| 防御 | TotalEHP **13,499**（最短板: Chaos） |
| 资源 | Spirit 占用 **131%** |
| 恢复 | 生命恢复 **269/s** |


### 关键发现

1. ⚠️ **混沌抗性/防御是最短板**（承伤仅 5,615，为最强的 23%）
2. ⚠️ 火焰抗性差 **15%** 未满
3. ⚠️ 闪电抗性差 **22%** 未满
4. ⚠️ 混沌抗性差 **75%** 未满
5. 🔴 精魄预算非常紧张（131% 占用）

### 优化方向 Top 3

1. **elemental_pen** (BASE): 每 1% 提升 1.72% DPS，需要 +12% 达到 +20% DPS
2. **cold_pen** (BASE): 每 1% 提升 1.17% DPS，需要 +18% 达到 +20% DPS
3. **crit_multi_base** (BASE): 每 1% 提升 0.74% DPS，需要 +26% 达到 +20% DPS

## 1. 构筑基线

### 构筑修饰符

| 修饰符 | 总量 | 天赋 | 装备 | 珠宝 |
|--------|------|------|------|------|
| 施法速度 INC | 78% | +12% | +66% | — |
| 伤害 INC | 520% | +338% | +62% | +80% |
| 元素伤害 INC | 161% | +140% | +21% | — |
| 暴击率 INC | 249% | +225% | +24% | — |
| 暴击伤害 INC | 262% | +250% | +12% | — |

### 构筑属性

| 属性 | 数值 |
|------|------|
| 总属性 | 339 |
| 力量 | 82 |
| 敏捷 | 93 |
| 智力 | 164 |
| 命中 | 1,146 |

### 技能 KPI

| 指标 | 数值 |
|------|------|
| 主技能 | Comet |
| 技能类型 | 法术 |
| TotalDPS | **492,350** |
| AverageHit | 686,955 |
| Speed | 0.72/s |
| CritChance | 85.3% |
| CritMultiplier | 4.62x |
| TotalEHP | 13,499 |
| 最短板承伤 | **5,615** (混沌) |

## 2. DPS 来源拆解

活跃伤害类型: Lightning, Cold, Fire

### 通用伤害 INC (Lightning,Cold,Fire) = 548%

**类别汇总**: Tree: +338.0 | Jewel: +80.0 | Item: +62.0 | Skill: +40.0 | Triggered: +28.0

| 来源 | 类别 | 值 |
|------|------|-----|
| Thin Ice | Tree | +50.0 |
| Sacrificial Blood | Tree | +40.0 |
| Dynamism | Tree | +40.0 |
| Mysticism II | Skill | +40.0 |
| Potent Incantation | Tree | +30.0 |
| Sorrow Finger, Unset Ring (Ring 1) | Item | +25.0 |
| Rage Turn, Unset Ring (Ring 2) | Item | +25.0 |
| Deadly Force | Tree | +25.0 |
| Stormbreaker | Tree | +20.0 |
| Stormbreaker | Tree | +20.0 |
| Stormbreaker | Tree | +20.0 |
| Stormbreaker | Tree | +20.0 |
| Megalomaniac, Diamond → Harness the Elements | Jewel | +20.0 |
| Megalomaniac, Diamond → Harness the Elements | Jewel | +20.0 |
| Megalomaniac, Diamond → Harness the Elements | Jewel | +20.0 |
| Megalomaniac, Diamond → Harness the Elements | Jewel | +20.0 |
| Damage on Critical | Tree | +20.0 |
| Damage on Critical | Tree | +20.0 |
| Critical Overload | Tree | +15.0 |
| Triggered Spell Damage | Triggered | +14.0 |
| Triggered Spell Damage | Triggered | +14.0 |
| Bramble Cut, Sapphire (Jewel) | Item | +12.0 |
| Life Spell Damage | Tree | +12.0 |
| Life Spell Damage and Costs | Tree | +6.0 |

### 元素伤害 INC (Lightning,Cold,Fire) = 161%

**类别汇总**: Tree: +140.0 | Item: +21.0

| 来源 | 类别 | 值 |
|------|------|-----|
| Stormcharged | Tree | +40.0 |
| All Natural | Tree | +30.0 |
| Yoke of Suffering, Bloodstone Amulet (Amulet) | Item | +21.0 |
| Elemental Damage | Tree | +10.0 |
| Elemental Damage | Tree | +10.0 |
| Elemental Damage | Tree | +10.0 |
| Elemental Damage | Tree | +10.0 |
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

### 通用伤害 MORE (Lightning,Cold,Fire) = -9.0%

**类别汇总**: Skill: +-30% | Sim: +30%

| 来源 | 类别 | 值 |
|------|------|-----|
| Spell Cascade | Skill | +-30.0% MORE |
| ⚠ Zenith II (模拟) | Sim | +30.0% MORE |

### 元素伤害 MORE (Lightning,Cold,Fire) = +310.0%

**类别汇总**: Sim: +163% | Skill: +56%

| 来源 | 类别 | 值 |
|------|------|-----|
| ⚠ PoP (模拟) | Sim | +119.0% MORE |
| Trinity | Skill | +56.0% MORE |
| ⚠ EC (模拟) | Sim | +20.0% MORE |

### 施法速度 = 1.00/s

**类别汇总**: Skill: +1.0

| 来源 | 类别 | 值 |
|------|------|-----|
| 基础施法频率 (1/1s) | Skill | +1.0 |

### Speed INC = 153%

**类别汇总**: Item: +66.0 | Skill: +49.0 | Sim: +26.0 | Tree: +12.0

| 来源 | 类别 | 值 |
|------|------|-----|
| Charge Infusion | Skill | +27.0 |
| ⚠ CI speed (模拟) | Sim | +26.0 |
| Rage Turn, Unset Ring (Ring 2) | Item | +24.0 |
| Sorrow Finger, Unset Ring (Ring 1) | Item | +22.0 |
| Trinity | Skill | +22.0 |
| Adonia's Ego, Siphoning Wand | Item | +20.0 |
| Sudden Escalation | Tree | +8.0 |
| Practiced Signs | Tree | +6.0 |
| Potent Incantation | Tree | -5.0 |
| Cast Speed | Tree | +3.0 |

### CritChance BASE = 85.3% (base 15.0% + added 0%)

**类别汇总**: Skill: +15.0

| 来源 | 类别 | 值 |
|------|------|-----|
| 基础暴击率 | Skill | +15.0 |

### CritChance INC = 249%

**类别汇总**: Tree: +225.0 | Item: +24.0

| 来源 | 类别 | 值 |
|------|------|-----|
| Careful Assassin | Tree | +50.0 |
| Evocational Practitioner | Tree | +25.0 |
| True Strike | Tree | +20.0 |
| Throatseeker | Tree | -20.0 |
| Sudden Escalation | Tree | +16.0 |
| Stormcharged | Tree | +15.0 |
| Critical Overload | Tree | +15.0 |
| Blight Wound, Sapphire (Jewel) | Item | +14.0 |
| Spell Critical Chance | Tree | +12.0 |
| Spell Critical Chance | Tree | +12.0 |
| Bramble Cut, Sapphire (Jewel) | Item | +10.0 |
| Spell Critical Chance | Tree | +10.0 |
| Critical Chance | Tree | +10.0 |
| Critical Chance | Tree | +10.0 |
| Spell Critical Chance | Tree | +10.0 |
| Spell Critical Chance | Tree | +10.0 |
| Deadly Force | Tree | +10.0 |
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

### CritMultiplier INC = 262%

**类别汇总**: Tree: +250.0 | Item: +12.0

| 来源 | 类别 | 值 |
|------|------|-----|
| Throatseeker | Tree | +60.0 |
| Gore Spike | Tree | +35.0 |
| For the Jugular | Tree | +25.0 |
| Critical Damage when consuming a Power Charge | Tree | +20.0 |
| Critical Damage when consuming a Power Charge | Tree | +20.0 |
| Careful Assassin | Tree | -20.0 |
| Critical Damage when consuming a Power Charge | Tree | +20.0 |
| Critical Damage | Tree | +15.0 |
| Critical Damage | Tree | +15.0 |
| Spell Critical Damage | Tree | +15.0 |
| Spell Critical Damage | Tree | +15.0 |
| Critical Damage | Tree | +15.0 |
| Critical Damage | Tree | +15.0 |
| Heart of the Well, Diamond (Jewel) | Item | +12.0 |

### Cold → Lightning Conversion/Gain = Cold → Lightning: 增益 5.0%

**类别汇总**: Item: +5.0

| 来源 | 类别 | 值 |
|------|------|-----|
| Adonia's Ego, Siphoning Wand | Item | +5.0 (Gain as Lightning) |

### Cold → Cold Self-Gain = Cold Self-Gain: 增益 35.0%

**类别汇总**: Skill: +30.0 | Item: +5.0

| 来源 | 类别 | 值 |
|------|------|-----|
| Freezing Mark | Skill | +30.0 (Gain as Cold) |
| Adonia's Ego, Siphoning Wand | Item | +5.0 (Gain as Cold) |

### Cold → Fire Conversion/Gain = Cold → Fire: 增益 65.0%

**类别汇总**: Item: +65.0

| 来源 | 类别 | 值 |
|------|------|-----|
| Sacred Flame, Shrine Sceptre | Item | +60.0 (Gain as Fire) |
| Adonia's Ego, Siphoning Wand | Item | +5.0 (Gain as Fire) |

### 点燃 DPS = 50,197

**公式**: `基础 32508-48777 × 效果 1.1100 × effMult 1.1200  (持续 3.56s, 几率 89.4%)`

**类别汇总**: Skill: -3100.0 | Sim: +2900.0 | Tree: +185.0 | Jewel: +80.0 | Item: +11.0

| 来源 | 类别 | 值 |
|------|------|-----|
| 技能#SupportSpellCascadePlayer | Skill | -3,100 |
| ⚠ Zenith II (模拟) | Sim | +2,900 |
| Dynamism | Tree | +40.0 |
| Deadly Force | Tree | +25.0 |
| Stormbreaker | Tree | +20.0 |
| Stormbreaker | Tree | +20.0 |
| Stormbreaker | Tree | +20.0 |
| Stormbreaker | Tree | +20.0 |
| Harness the Elements | Jewel | +20.0 |
| Harness the Elements | Jewel | +20.0 |
| Harness the Elements | Jewel | +20.0 |
| Harness the Elements | Jewel | +20.0 |
| Damage on Critical | Tree | +20.0 |
| Damage on Critical | Tree | +20.0 |
| Blight Wound, Sapphire | Item | +11.0 |

### Combined DPS = 686,955

**类别汇总**: Hit: +492350.0 | DOT: +50196.9

| 来源 | 类别 | 值 |
|------|------|-----|
| Hit DPS | Hit | +492,350 |
| 点燃 DPS | DOT | +50,197 |

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
| 冰霜 +16.0% (占66.1%) | Enemy | +16.0 |
| 火焰 +16.0% (占31.4%) | Enemy | +16.0 |
| 闪电 +16.0% (占2.5%) | Enemy | +16.0 |

## 3. 灵敏度分析

### 3A. 进攻灵敏度（DPS）

| # | 维度 | 类型 | 所需值 | 单位 | 效果/单位 | 当前值 | 公式 |
|---|------|------|--------|------|----------|--------|------|
| 1 | elemental_pen | BASE | +12.0% | % | 1.72%/% | 8 | 需要 +12% 穿透 → DPS +20.7% |
| 2 | cold_pen | BASE | +17.5% | % | 1.17%/% | 0 | 需要 +18% 穿透 → DPS +20.5% |
| 3 | crit_multi_base | BASE | +26.5% | % | 0.74%/% | 100 | CritBase 100→126, 需要 +26 → DPS +19.6% |
| 4 | fire_pen | BASE | +36.5% | % | 0.53%/% | 0 | 需要 +36% 穿透 → DPS +19.5% |
| 5 | crit_multi_inc | INC | +95.5% | % | 0.21%/% | 262 | INC 262%→358%, 需要 +96 → DPS +20.0% |
| 6 | spell_damage_inc | INC | +163.5% | % | 0.12%/% | 719 | INC 719%→882%, 需要 +164 → DPS +20.0% |
| 7 | elemental_damage_inc | INC | +163.5% | % | 0.12%/% | 719 | INC 719%→882%, 需要 +164 → DPS +20.0% |
| 8 | cold_damage_inc | INC | +248.0% | % | 0.08%/% | 719 | INC 719%→967%, 需要 +248 → DPS +20.0% |

**无影响维度**: physical_damage_inc, fire_damage_inc, lightning_damage_inc, chaos_damage_inc, crit_chance_inc, crit_chance_base, cast_speed_inc, lightning_pen, chaos_pen, projectile_count, aoe_inc, duration_inc

### 3B. 防御灵敏度（EHP）

| 维度 | 类型 | 所需值 | 每单位 EHP 提升 | 公式 |
|------|------|--------|---------------|------|
| 法术格挡概率 | BASE | 37.0% | +0.54%/单位 | BASE 0→37, 需要 +37 → EHP +20.1% |
| 格挡概率 | BASE | 37.0% | +0.54%/单位 | BASE 0→37, 需要 +37 → EHP +20.1% |
| 生命上限 | INC | 90.5% | +0.22%/单位 | INC 5%→96%, 需要 +90 → EHP +20.0% |
| 闪避值 | BASE | 1818.5 | +0.01%/单位 | BASE 142→1960, 需要 +1818 → EHP +19.4% |
| 护甲固定值 | BASE | 4763.5 | +0.00%/单位 | BASE 0→4764, 需要 +4764 → EHP +20.4% |

**无法达到目标**: 闪电抗性, 生命固定值, 全元素抗性, 冰霜抗性, 物理减伤, 混沌抗性, 护甲增加, 闪避增加, 火焰抗性

### 3C. 恢复增强灵敏度

注入多少恢复属性可使对应恢复指标提升 **20%**：

| 增强属性 | 所需注入 | 当前总值 | 公式 |
|---------|---------|---------|------|
| 魔力再生 | 7.5/s | 38.8 | BASE 39→46, 需要 +8 → 魔力恢复 +20.6% |
| 生命再生 | 14.5/s | — | BASE 0→14, 需要 +14 → 生命恢复 +19.5% |
| 魔力恢复速率 | 20.5% | — | INC 0%→20%, 需要 +20 → 魔力恢复 +20.6% |
| 生命恢复速率 | 25.5% | — | INC 0%→26%, 需要 +26 → 生命恢复 +20.3% |

## 4. 防御面

### 4A. 生命池构成

| 资源 | 数值 | 备注 |
|------|------|------|
| Life | 1,793 | — |
| Energy Shield | 5,706 | — |
| Mana | 969 | 可用 969 |
| MoM | 100% | 魔力优先承受伤害 |

### 4B. 减伤层

| 层 | 数值 |
|------|------|
| 护甲 | 0 |
| 闪避 | 706 |
| 攻击格挡 | 0% |
| 法术格挡 | 0% |

### 4C. 抗性面板

| 元素 | 当前 | 上限 | 状态 |
|------|------|------|------|
| 火焰 | 60% | 75% | 未满 (差 15%) |
| 冰霜 | 69% | 75% | 未满 (差 6%) |
| 闪电 | 53% | 75% | 未满 (差 22%) |
| 混沌 | 0% | 75% | 未满 (差 75%) |

未满抗性: 火焰, 冰霜, 闪电, 混沌 — 优先补满可显著提升对应元素 EHP。

### 4D. 最大承伤 (MaxHitTaken)

**TotalEHP = 13,499**（平均承受 3.2 次攻击）

| 伤害类型 | MaxHitTaken | 占最强% |
|----------|-------------|--------|
| Physical | 8,468 | 34% |
| 火焰 | 19,693 | 79% |
| 冰霜 | 24,906 | 100% |
| 闪电 | 16,936 | 68% |
| 混沌 | 5,615 | 23% ← 最短板 |

**最短板**: 混沌（仅承受 5,615 伤害，为最强的 23%）

### 4E. 承伤乘数 (TakenHitMult)

数值越小越好，表示实际承受伤害占原始伤害的比例。

| 伤害类型 | 承伤乘数 | 含义 |
|----------|---------|------|
| Physical | 1.000 (100.0%) | 每承受 100 伤害实际受 100 |
| 火焰 | 0.430 (43.0%) | 每承受 100 伤害实际受 43 |
| 冰霜 | 0.340 (34.0%) | 每承受 100 伤害实际受 34 |
| 闪电 | 0.500 (50.0%) | 每承受 100 伤害实际受 50 |
| 混沌 | 1.000 (100.0%) | 每承受 100 伤害实际受 100 ← 最短板 |

### 4F. DOT 有效生命

| 伤害类型 | DotEHP |
|----------|--------|
| Physical | 8,468 |
| 火焰 | 21,170 |
| 冰霜 | 27,316 |
| 闪电 | 18,017 |
| 混沌 | 5,615 |


## 5. 资源面

### 5A. 资源预算

| 资源 | 总量 | 可用 | 占用率 |
|------|------|------|--------|
| Life | 1,793 | 1,793 | — |
| Mana | 969 | 969 | 0% |
| Spirit | 405 | -125 | 🔴 131% |
| ES | 5,706 | 5,706 | — |

### 5B. 生命恢复能力

总恢复速率: **269.0/s**（回满约 6.7s）
偷取上限利用率: 45%（上限 402/s）

| # | 来源 | 每秒恢复 | 占比 |
|---|------|---------|------|
| 1 | 偷取 | 179.3/s | 67% |
| 2 | 再生 | 89.7/s | 33% |

### 5C. 魔力恢复能力

总恢复速率: **19.4/s**（回满可用 969 约需 49.9s）

| # | 来源 | 每秒恢复 | 占比 |
|---|------|---------|------|
| 1 | 再生 | 19.4/s | 100% |

## 6. 已分配天赋价值

### DPS 影响天赋

| # | 天赋 | 类型 | 移除后 DPS% | 移除后 EHP% | 分类 | 效果 |
|---|------|------|-------------|-------------|------|------|
| 1 | Sunder the Flesh | Notable | -10.1% | +0.0% | 输出 | Base Critical Hit Chance for Spells is 15% |
| 2 | Stormbreaker | Notable | -9.8% | +0.0% | 输出 | 20% increased Damage for each type of Elemental Ailment on Enemy |
| 3 | Throatseeker | Notable | -8.9% | +0.0% | 输出 | 60% increased Critical Damage Bonus; 20% reduced Critical Hit Chance |
| 4 | Stormcharged | Notable | -8.0% | +0.0% | 输出 | 40% increased Elemental Damage if you've dealt a Critical Hit Recently; 15% increased Critical Hit Chance |
| 5 | Gore Spike | Notable | -7.3% | +0.0% | 输出 | 1% increased Critical Damage Bonus per 50 current Life |
| 6 | Careful Assassin | Notable | -7.2% | +0.0% | 输出 | 20% reduced Critical Damage Bonus; 50% increased Critical Hit Chance |
| 7 | Thin Ice | Notable | -6.1% | +0.0% | 输出 | 20% increased Freeze Buildup; 50% increased Damage with Hits against Frozen Enemies |
| 8 | Evocational Practitioner | Notable | -5.4% | +0.0% | 输出 | 25% increased Critical Hit Chance if you've Triggered a Skill Recently; Meta Skills gain 25% increased Energy if you've dealt a Critical Hit Recently |
| 9 | For the Jugular | Notable | -5.2% | -0.2% | 兼顾 | 25% increased Critical Damage Bonus; +10 to Intelligence |
| 10 | Deadly Force | Notable | -5.2% | +0.0% | 输出 | 25% increased Damage if you've dealt a Critical Hit in the past 8 seconds; 10% increased Critical Hit Chance |
| 11 | Critical Overload | Notable | -5.0% | +0.0% | 输出 | 15% increased Critical Hit Chance for Spells; 15% increased Spell Damage if you've dealt a Critical Hit Recently |
| 12 | Sacrificial Blood | Notable | -4.9% | +0.0% | 输出 | 15% increased Life Cost of Skills; 40% increased Spell Damage with Spells that cost Life |
| 13 | Dynamism | Notable | -4.9% | +0.0% | 输出 | 40% increased Damage if you've Triggered a Skill Recently; Meta Skills gain 15% increased Energy |
| 14 | Sudden Escalation | Notable | -4.3% | +0.0% | 输出 | 16% increased Critical Hit Chance for Spells; 8% increased Cast Speed if you've dealt a Critical Hit Recently |
| 15 | True Strike | Notable | -4.3% | +0.0% | 输出 | +10 to Dexterity; 20% increased Critical Hit Chance |
| 16 | All Natural | Notable | -3.7% | -5.3% | 兼顾 | +5% to all Elemental Resistances; 30% increased Elemental Damage |
| 17 | Potent Incantation | Notable | -3.1% | +0.0% | 输出 | 30% increased Spell Damage; 5% reduced Cast Speed |
| 18 | Breaking Point | Notable | -2.7% | +0.0% | 输出 | 10% increased Duration of Elemental Ailments on Enemies; 30% increased Magnitude of Non-Damaging Ailments you inflict |
| 19 | Practiced Signs | Notable | -0.7% | +0.0% | 输出 | 6% increased Cast Speed |

### 纯防御天赋

| 天赋 | 移除后 EHP% | 效果 |
|------|-------------|------|
| Melding | -6.2% | 40% increased maximum Energy Shield; 10% reduced maximum Mana |
| Overflowing Power | +12.5% | +2 to Maximum Power Charges |
| Mind Over Matter | -12.5% | All Damage is taken from Mana before Life; 50% less Mana Recovery Rate |
| Dampening Shield | -5.2% | 28% increased maximum Energy Shield; Gain additional Ailment Threshold equal to 12% of maximum Energy Shield; Gain additional Stun Threshold equal to 12% of maximum Energy Shield |
| Pure Energy | -5.9% | 30% increased maximum Energy Shield; +10 to Intelligence |
| Heavy Buffer | -8.0% | 40% increased maximum Energy Shield; 5% of Damage taken bypasses Energy Shield |

### 无效天赋 (15 个)

Invocated Echoes, The Spring Hare, Blood Transfusion, Echoing Thunder, Energise, Heavy Frost, Echoing Frost, Invocated Efficiency, Echoing Flames, Sanguine Tides, Vitality Siphon, Marked Agility, Acceleration, Infusion of Power, Sanguimancy

## 7. 未分配天赋探索

| # | 天赋 | 类型 | DPS% | EHP% | 分类 |
|---|------|------|------|------|------|
| 1 | Dimensional Weakspot | Notable | +25.9% | +0.0% | 输出 |
| 2 | Glaciation | Notable | +24.4% | +0.0% | 输出 |
| 3 | Primal Sundering | Notable | +20.7% | +0.0% | 输出 |
| 4 | Exposed to the Cosmos | Notable | +20.5% | +0.0% | 输出 |
| 5 | Storm Swell | Notable | +17.4% | +0.0% | 输出 |
| 6 | Snowpiercer | Notable | +17.1% | +0.2% | 兼顾 |
| 7 | Breath of Ice | Notable | +17.1% | +0.2% | 兼顾 |
| 8 | Endless Blizzard | Notable | +14.9% | +0.0% | 输出 |
| 9 | Deep Freeze | Notable | +13.8% | +0.0% | 输出 |
| 10 | Cremation | Notable | +13.6% | +0.0% | 输出 |

*（另有 179 个候选天赋未显示）*

## 8. 珠宝诊断

### Megalomaniac (Diamond, UNIQUE)

- **DPS 贡献**: +9.8% | **EHP 贡献**: -0.0% | **状态**: ok | **槽位**: Jewel 21984
- **分配天赋**: invocated limit, harness the elements (DPS +9.8%, EHP -0.0%)

| Mod | 类型 | 值 | DPS% | EHP% |
|-----|------|-----|------|------|
| GrantedPassive | LIST | invocated limit | -0.0% | -0.0% |
| GrantedPassive | LIST | harness the elements | +9.8% | -0.0% |

### Blight Wound (Sapphire, RARE)

- **DPS 贡献**: +3.9% | **EHP 贡献**: +3.7% | **状态**: ok | **槽位**: Jewel 7960

| Mod | 类型 | 值 | DPS% | EHP% |
|-----|------|-----|------|------|
| EnergyShield | INC | 20 | -0.0% | +3.7% |
| CritChance | INC | 14 | +3.0% | -0.0% |
| AilmentMagnitude | INC | 11 | +0.9% | -0.0% |

### Bramble Cut (Sapphire, RARE)

- **DPS 贡献**: +3.6% | **EHP 贡献**: +3.2% | **状态**: ok | **槽位**: Jewel 61834

| Mod | 类型 | 值 | DPS% | EHP% |
|-----|------|-----|------|------|
| Damage | INC | 12 | +1.5% | -0.0% |
| EnergyShield | INC | 17 | -0.0% | +3.2% |
| CritChance | INC | 10 | +2.2% | -0.0% |

### Controlled Metamorphosis (Diamond, UNIQUE)

- **DPS 贡献**: -0.0% | **EHP 贡献**: -4.9% | **状态**: ok | **槽位**: Jewel 61419

| Mod | 类型 | 值 | DPS% | EHP% |
|-----|------|-----|------|------|
| JewelData | LIST | (complex data) | -0.0% | -0.0% |
| JewelData | LIST | (complex data) | -0.0% | -0.0% |
| ElementalResist | BASE | -6 | -0.0% | -4.9% |

### Heart of the Well (Diamond, UNIQUE)

- **DPS 贡献**: +2.5% | **EHP 贡献**: -0.0% | **状态**: ok | **槽位**: Jewel 32763

| Mod | 类型 | 值 | DPS% | EHP% |
|-----|------|-----|------|------|
| CritMultiplier | INC | 12 | +2.5% | -0.0% |
| PierceChance | BASE | 47 | -0.0% | -0.0% |
| ManaOnKill | BASE | 1 | -0.0% | -0.0% |
| InstantEnergyShieldLeech | BASE | 14 | -0.0% | -0.0% |
| InstantManaLeech | BASE | 14 | -0.0% | -0.0% |
| InstantLifeLeech | BASE | 14 | -0.0% | -0.0% |

## 9. 光环与精魄分析

### 9A. 现有光环 DPS 贡献

| # | 光环 | 裸光环 DPS | 真实 DPS | EHP | 精魄 |
|---|------|------------|----------|-----|------|
| 1 | Trinity | +58.8% | +60.1% (辅助+1.3%) (条件: Total Resonance Count=150) | +0.0% | 100 |

<details>
<summary><b>Trinity 详细数据</b></summary>

### 条件参数范围

| 端点 | 裸光环 | 真实 | 辅助增益 | Speed INC |
|------|--------|------|----------|-----------|
| Total Resonance Count=0 | +0.0% | +0.0% | — | 131% |
| Total Resonance Count=300 | +73.2% | +74.5% | +1.4% | 131%→153% |

### 辅助贡献

- **Dialla's Desire**: +1 level, +10% quality
- **Lightning Mastery**: +1 level
- 总辅助贡献: **+1.3%** DPS（Total Resonance Count=150时）
- 端点差异: Total Resonance Count=0时+0.0%，Total Resonance Count=300时+1.4%

### 基础数值

- 有效等级: **Lv24** (基础 Lv23 + 辅助 +1)
- MORE per 30 Resonance: **7%**
- Speed INC per quality: **0.75%** (q20 = 15.0% INC)

</details>

| 2 | Elemental Conflux | +24.7% | +24.7% ⚠️模拟 | +0.0% | 60 |

<details>
<summary><b>Elemental Conflux 详细数据</b></summary>

### 基础数值

- 有效等级: **Lv28** (基础 Lv25 + 辅助 +3)
- MORE per 30 Resonance: **67%**

</details>

| 3 | Charge Infusion | +23.2% | +23.2% ⚠️模拟 | +0.0% | 30 |

<details>
<summary><b>Charge Infusion 详细数据</b></summary>

### 基础数值

- 有效等级: **Lv27** (基础 Lv24 + 辅助 +3)
- MORE per 30 Resonance: **27%**

</details>

| 4 | Purity of Fire | +0.0% | +0.0% | +15.4% | 130 |

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

- **Elemental Conflux** (Lv25): 分别注入 74% MORE 到火/冰/电取平均。伤害构成：火 31.4% / 冰 66.1% / 电 2.5%
  三次模拟 DPS：火 144130 / 冰 174114 / 电 119087
- **Charge Infusion** (Lv24): 需启用 Charge 配置才能生效，已模拟 F=3/P=7/E=3

**模拟方法说明：**

- **等级前提**：光环模拟基于构筑实际宝石等级数据（非固定 Level 20）
- **裸光环 DPS**：仅光环宝石效果（禁用所有辅助宝石），用于和「潜在光环推荐」对比。真实 DPS 含辅助宝石额外增益，标注在括号中
- **DPS 贡献计算**：移除光环后 DPS 下降百分比（正值=正向贡献）。条件光环需注入参数才能生效，默认注入参数最大值的 50%，标注在真实 DPS 括号中
- **构筑已有 modifier**：施法速度 INC 153%（来自 POB skillModList），总 MORE ×0.91。INC 叠加为加法（新增边际递减），MORE 叠加为乘法
- **品质上限**：所有宝石品质按 20% 上限计算（游戏实际上限）。构筑中超品质宝石已自动降级
- **条件范围计算**：设置参数绝对值（0 和 max），对比「无光环」DPS。Speed 门槛效果从 POB skillModList 读取端点 INC 差值，边际 = 新增INC / (1+已有INC)
- **期望收益计算**：对于 EC 等随机效果光环，期望 = 效果值 × 受影响技能元素占比之和 ÷ 3（因为随机选择火/冰/电之一）

**纯防御光环**（移除后 EHP 下降）：

- **Purity of Fire**: EHP +15.4%, 精魄 130

**DPS/EHP 影响未检测到** (1 个)：

这些光环可能提供非DPS收益（如生存/功能性），或其效果依赖动态条件（如Frenzy Charge）而POB未完全计算。

- **Combat Frenzy**: 精魄 30

### 9B. 潜在光环推荐

| # | 光环 | 精魄 | DPS% | EHP% | 说明 |
|---|------|------|------|------|------|
| 1 | Attrition（损耗） | 30 | +59.2% | +0.0% | 需精魄 30（缺 30）; 命中附带 Wither 叠层 |
| 2 | Archmage（大法师） | 100 | +17.9% | +0.0% | 需精魄 100（缺 100）; Mana 转附加闪电伤害 |

**无 DPS 影响：**

- Berserk（狂暴）

### 9C. 精魄辅助推荐

| # | 精魄辅助 | 精魄 | DPS% | 条件 | 来源 |
|---|----------|------|------|------|------|
| 1 | Mysticism II | 30 | +4.9% | 需精魄 30（缺 30） ⚠️估算 | 动态扫描 |
| 2 | Mysticism I | 15 | +3.7% | 需精魄 15（缺 15） ⚠️估算 | 动态扫描 |

### 9D. 精魄预算

| 项目 | 精魄 |
|------|------|
| 总精魄 | 405 |
| 已用精魄 | 405 |
| 可用精魄 | 0 |
| 推荐光环消耗 | 130 |
| 推荐后剩余 | -130 |

**注意**: 推荐光环的精魄总消耗超过可用精魄，需要根据优先级取舍。

### 9E. 数据一致性检查

**⚠️ 以下项目需要人工确认：**

- Elemental Conflux 使用构筑实际等级 Lv25（效果值=74），非满级 Lv20
- Charge Infusion 使用构筑实际等级 Lv24（效果值=27），非满级 Lv20
- Berserk 无明显 DPS 影响：可能因为构筑条件不满足或模拟环境限制

### 9F. POB 未实现效果预估

**⚠️ 以下技能效果在 POB 中未实现，已通过配置模拟：**

| 技能 | 效果描述 | DPS 预估 |
|------|----------|----------|
| **Pinnacle of Power** | 7 × (15% + 20×0.1%) = 119% MORE 元素伤害（PowerChargesMax） | **+119.0%** |
| **Elemental Conflux** | 元素伤害 MORE（期望 59%×1/3≈20%，等级20，简化模拟） | **+20.0%** |

**注**: 这些效果由 `config/pob_unimplemented_effects.yaml` 配置，
实际游戏效果可能因条件触发方式不同而有差异。

## 10. 总结与建议

当前 **Comet** TotalDPS = **492,350**，AverageHit = 686,955，Speed = 0.72/s，CritChance = 85.3%，CritMultiplier = 4.62x。

### ⚔️ 进攻面

**DPS 灵敏度 Top 5**（所需投入越少 = 性价比越高）：

| # | 维度 | 类型 | 当前值 | 所需值 | 公式 |
|---|------|------|--------|--------|------|
| 1 | elemental_pen | BASE | 8 | +12% | 需要 +12% 穿透 → DPS +20.7% |
| 2 | cold_pen | BASE | 0 | +18% | 需要 +18% 穿透 → DPS +20.5% |
| 3 | crit_multi_base | BASE | 100 | +26% | CritBase 100→126, 需要 +26 → DPS +19.6% |
| 4 | fire_pen | BASE | 0 | +36% | 需要 +36% 穿透 → DPS +19.5% |
| 5 | crit_multi_inc | INC | 262 | +96% | INC 262%→358%, 需要 +96 → DPS +20.0% |

*穿透维度均无影响（敌人抗性已为负值），面对高抗 Boss 时会成为有效优化方向。*

### 🛡️ 防御面

**最短板**: Chaos（承伤仅为最强的 23%）

**防御性价比最高**: 法术格挡概率，需要 +37% 即可提升 EHP +20%

### 💧 资源与恢复

**⚠️ 精魄超载**: 占用 131%，需要缩减光环或精魄辅助

**恢复增强 Top 3**：

1. 魔力再生: BASE 39→46, 需要 +8 → 魔力恢复 +20.6%
2. 生命再生: BASE 0→14, 需要 +14 → 生命恢复 +19.5%
3. 魔力恢复速率: INC 0%→20%, 需要 +20 → 魔力恢复 +20.6%

### 🌳 天赋

**推荐点出 Top 5**：

1. **Dimensional Weakspot**: DPS +25.9%
2. **Glaciation**: DPS +24.4%
3. **Primal Sundering**: DPS +20.7%
4. **Exposed to the Cosmos**: DPS +20.5%
5. **Storm Swell**: DPS +17.4%

**⚠️ 15 个无效天赋**: Invocated Echoes, The Spring Hare, Blood Transfusion, Echoing Thunder, Energise, Heavy Frost, Echoing Frost, Invocated Efficiency 等 15 个

### 💎 珠宝

**最佳**: Megalomaniac (DPS +9.8%, EHP -0.0%)
