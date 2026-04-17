# Frost Bomb 构筑全面分析报告

## 0. 执行摘要

### 维度概览

| 维度 | 关键指标 |
|------|---------|
| 进攻 | TotalDPS **61,229** |
| 防御 | TotalEHP **13,649**（最短板: Chaos） |
| 资源 | Spirit 占用 **131%** |
| 恢复 | 生命恢复 **269/s** |


### 关键发现

1. ⚠️ **混沌抗性/防御是最短板**（承伤仅 5,101，为最强的 19%）
2. ⚠️ 混沌抗性差 **75%** 未满
3. 🔴 精魄预算非常紧张（131% 占用）
4. ⚠️ 17 个已分配天赋对 DPS 和 EHP 均无可测量影响
5. 💡 **crit_chance_base** 对 DPS 影响最大（每 1% 提升 3.96% DPS）

### 优化方向 Top 3

1. **crit_chance_base** (BASE): 每 1% 提升 3.96% DPS，需要 +4% 达到 +20% DPS
2. **elemental_pen** (BASE): 每 1% 提升 1.72% DPS，需要 +12% 达到 +20% DPS
3. **cold_pen** (BASE): 每 1% 提升 1.17% DPS，需要 +18% 达到 +20% DPS

## 1. 构筑基线

### 构筑修饰符

| 修饰符 | 总量 | 天赋 | 装备 | 珠宝 |
|--------|------|------|------|------|
| 施法速度 INC | 78% | +12% | +66% | — |
| 伤害 INC | 520% | +338% | +62% | +80% |
| 元素伤害 INC | 161% | +140% | +21% | — |
| 暴击率 INC | 249% | +225% | +24% | — |
| 暴击伤害 INC | 202% | +190% | +12% | — |

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
| 主技能 | Frost Bomb |
| 技能类型 | 法术 |
| TotalDPS | **61,229** |
| AverageHit | 141,297 |
| Speed | 0.43/s |
| CritChance | 66.5% |
| CritMultiplier | 4.02x |
| TotalEHP | 13,649 |
| 最短板承伤 | **5,101** (混沌) |

## 2. DPS 来源拆解

活跃伤害类型: Lightning, Cold, Fire

### 通用伤害 INC (Lightning,Cold,Fire) = 520%

**类别汇总**: Tree: +338.0 | Jewel: +80.0 | Item: +62.0 | Skill: +40.0

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
| Short Fuse II | Skill | +-30.0% MORE |
| ⚠ Zenith II (模拟) | Sim | +30.0% MORE |

### 元素伤害 MORE (Lightning,Cold,Fire) = +324.0%

**类别汇总**: Sim: +172% | Skill: +56%

| 来源 | 类别 | 值 |
|------|------|-----|
| ⚠ PoP (模拟) | Sim | +119.0% MORE |
| Trinity | Skill | +56.0% MORE |
| ⚠ EC (模拟) | Sim | +24.0% MORE |

### 施法速度 = 1.25/s

**类别汇总**: Skill: +1.2

| 来源 | 类别 | 值 |
|------|------|-----|
| 基础施法频率 (1/0.8s) | Skill | +1.2 |

### Speed INC = 126%

**类别汇总**: Item: +66.0 | Sim: +26.0 | Skill: +22.0 | Tree: +12.0

| 来源 | 类别 | 值 |
|------|------|-----|
| ⚠ CI speed (模拟) | Sim | +26.0 |
| Rage Turn, Unset Ring (Ring 2) | Item | +24.0 |
| Sorrow Finger, Unset Ring (Ring 1) | Item | +22.0 |
| Trinity | Skill | +22.0 |
| Adonia's Ego, Siphoning Wand (Weapon 1) | Item | +20.0 |
| Sudden Escalation | Tree | +8.0 |
| Practiced Signs | Tree | +6.0 |
| Potent Incantation | Tree | -5.0 |
| Cast Speed | Tree | +3.0 |

### Speed MORE = -30.0%

**类别汇总**: Skill: +-30%

| 来源 | 类别 | 值 |
|------|------|-----|
| Spell Echo | Skill | +-30.0% MORE |

### CritChance BASE = 66.5% (base 15.0% + added 0%)

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

### CritChance MORE = +27.0%

**类别汇总**: Sim: +27%

| 来源 | 类别 | 值 |
|------|------|-----|
| ⚠ CI crit (模拟) | Sim | +27.0% MORE |

### CritMultiplier BASE = 100

**类别汇总**: Base: +100.0

| 来源 | 类别 | 值 |
|------|------|-----|
| Base | Base | +100.0 |

### CritMultiplier INC = 202%

**类别汇总**: Tree: +190.0 | Item: +12.0

| 来源 | 类别 | 值 |
|------|------|-----|
| Throatseeker | Tree | +60.0 |
| Gore Spike | Tree | +35.0 |
| For the Jugular | Tree | +25.0 |
| Careful Assassin | Tree | -20.0 |
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
| Adonia's Ego, Siphoning Wand (Weapon 1) | Item | +5.0 (Gain as Lightning) |

### Cold → Cold Self-Gain = Cold Self-Gain: 增益 35.0%

**类别汇总**: Skill: +30.0 | Item: +5.0

| 来源 | 类别 | 值 |
|------|------|-----|
| Freezing Mark | Skill | +30.0 (Gain as Cold) |
| Adonia's Ego, Siphoning Wand (Weapon 1) | Item | +5.0 (Gain as Cold) |

### Cold → Fire Conversion/Gain = Cold → Fire: 增益 65.0%

**类别汇总**: Item: +65.0

| 来源 | 类别 | 值 |
|------|------|-----|
| Sacred Flame, Shrine Sceptre (Weapon 2) | Item | +60.0 (Gain as Fire) |
| Adonia's Ego, Siphoning Wand (Weapon 1) | Item | +5.0 (Gain as Fire) |

### 点燃 DPS = 1,881

**公式**: `基础 9100-13621 × 效果 1.1100 × 0.2层 × effMult 1.1200  (持续 3.56s, 几率 23.4%)`

**类别汇总**: Skill: -3100.0 | Sim: +2900.0 | Tree: +185.0 | Jewel: +80.0 | Item: +11.0

| 来源 | 类别 | 值 |
|------|------|-----|
| 技能#SupportShortFusePlayerTwo | Skill | -3,100 |
| ⚠ Zenith II (模拟) | Sim | +2,900 |
| 天赋#3688 | Tree | +40.0 |
| 天赋#13724 | Tree | +25.0 |
| 天赋#43139 | Tree | +20.0 |
| 天赋#43139 | Tree | +20.0 |
| 天赋#43139 | Tree | +20.0 |
| 天赋#43139 | Tree | +20.0 |
| 天赋#12611 | Jewel | +20.0 |
| 天赋#12611 | Jewel | +20.0 |
| 天赋#12611 | Jewel | +20.0 |
| 天赋#12611 | Jewel | +20.0 |
| 天赋#4346 | Tree | +20.0 |
| 天赋#4519 | Tree | +20.0 |
| Blight Wound, Sapphire | Item | +11.0 |

### Combined DPS = 63,110

**类别汇总**: Hit: +61228.8 | DOT: +1881.2

| 来源 | 类别 | 值 |
|------|------|-----|
| Hit DPS | Hit | +61,229 |
| 点燃 DPS | DOT | +1,881 |

### 敌人受伤增加 = x2.2400

**公式**: `所有伤害类型共享 x2.2400`

**类别汇总**: Item: +96.0 | Ailment: +28.0

| 来源 | 类别 | 值 |
|------|------|-----|
| Shock: 受伤+28%（范围 20%~50%） | Ailment | +28.0 |
| Yoke of Suffering: 每种元素异常+24%，当前4种=+96%（最多5种=+120%） | Item | +96.0 |

### 敌人抗性乘区 (加权) = +16.0%

**公式**: `+16.0%  (抗性 50% - 穿透 8% = 有效 42%)`

**类别汇总**: Penetration: +16.0

| 来源 | 类别 | 值 |
|------|------|-----|
| 冰霜 +16.0% (占66.1%) | Enemy | +16.0 |
| 火焰 +16.0% (占31.4%) | Enemy | +16.0 |
| 闪电 +16.0% (占2.5%) | Enemy | +16.0 |

## 3. 灵敏度分析

### 3A. 进攻灵敏度（DPS）

| # | 维度 | 类型 | 所需值 | 单位 | 效果/单位 | 当前值 | 公式 |
|---|------|------|--------|------|----------|--------|------|
| 1 | crit_chance_base | BASE | +4.5% | % | 3.96%/% | 0 | baseCrit 0.0%→4.5%, 需要 +4.5% → DPS +17.8% |
| 2 | elemental_pen | BASE | +12.0% | % | 1.72%/% | 8 | 需要 +12% 穿透 → DPS +20.7% |
| 3 | cold_pen | BASE | +17.5% | % | 1.17%/% | 0 | 需要 +18% 穿透 → DPS +20.5% |
| 4 | crit_multi_base | BASE | +30.0% | % | 0.67%/% | 100 | CritBase 100→130, 需要 +30 → DPS +20.1% |
| 5 | fire_pen | BASE | +36.5% | % | 0.53%/% | 0 | 需要 +36% 穿透 → DPS +19.5% |
| 6 | crit_multi_inc | INC | +90.5% | % | 0.22%/% | 202 | INC 202%→292%, 需要 +90 → DPS +20.1% |
| 7 | crit_chance_inc | INC | +105.0% | % | 0.19%/% | 249 | INC 249%→354%, 需要 +105 → DPS +20.1% |
| 8 | spell_damage_inc | INC | +158.0% | % | 0.13%/% | 691 | INC 691%→849%, 需要 +158 → DPS +20.0% |
| 9 | elemental_damage_inc | INC | +158.0% | % | 0.13%/% | 691 | INC 691%→849%, 需要 +158 → DPS +20.0% |
| 10 | cold_damage_inc | INC | +240.0% | % | 0.08%/% | 691 | INC 691%→931%, 需要 +240 → DPS +20.1% |
| 11 | fire_damage_inc | INC | +497.5% | % | 0.04%/% | 681 | INC 681%→1178%, 需要 +498 → DPS +20.0% |

**无影响维度**: physical_damage_inc, lightning_damage_inc, chaos_damage_inc, cast_speed_inc, lightning_pen, chaos_pen, projectile_count, aoe_inc, duration_inc

### 3B. 防御灵敏度（EHP）

| 维度 | 类型 | 所需值 | 每单位 EHP 提升 | 公式 |
|------|------|--------|---------------|------|
| 法术格挡概率 | BASE | 37.5% | +0.55%/单位 | BASE 0→38, 需要 +38 → EHP +20.5% |
| 格挡概率 | BASE | 37.5% | +0.55%/单位 | BASE 0→38, 需要 +38 → EHP +20.5% |
| 混沌抗性 | BASE | 68.0% | +0.30%/单位 | BASE 0→68, 需要 +68 → EHP +20.4% |
| 生命上限 | INC | 78.5% | +0.26%/单位 | INC 5%→84%, 需要 +78 → EHP +20.0% |
| 闪避值 | BASE | 2015.5 | +0.01%/单位 | BASE 142→2158, 需要 +2016 → EHP +20.6% |
| 护甲固定值 | BASE | 4051.0 | +0.01%/单位 | BASE 0→4051, 需要 +4051 → EHP +20.5% |

**无法达到目标**: 闪避增加, 闪电抗性, 物理减伤, 火焰抗性, 全元素抗性, 生命固定值, 冰霜抗性, 护甲增加

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
| Energy Shield | 4,677 | — |
| Mana | 969 | 可用 969 |
| MoM | 100% | 魔力优先承受伤害 |

### 4B. 减伤层

| 层 | 数值 |
|------|------|
| 护甲 | 0 |
| 闪避 | 579 |
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

**TotalEHP = 13,649**（平均承受 3.2 次攻击）

| 伤害类型 | MaxHitTaken | 占最强% |
|----------|-------------|--------|
| Physical | 7,439 | 28% |
| 火焰 | 26,568 | 100% |
| 冰霜 | 26,568 | 100% |
| 闪电 | 26,568 | 100% |
| 混沌 | 5,101 | 19% ← 最短板 |

**最短板**: 混沌（仅承受 5,101 伤害，为最强的 19%）

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
| Physical | 7,439 |
| 火焰 | 29,756 |
| 冰霜 | 29,756 |
| 闪电 | 29,756 |
| 混沌 | 5,100 |


## 5. 资源面

### 5A. 资源预算

| 资源 | 总量 | 可用 | 占用率 |
|------|------|------|--------|
| Life | 1,793 | 1,793 | — |
| Mana | 969 | 969 | 0% |
| Spirit | 405 | -125 | 🔴 131% |
| ES | 4,677 | 4,677 | — |

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

| # | 天赋 | 类型 | 移除后 DPS% | 移除后 EHP% | 分类 |
|---|------|------|-------------|-------------|------|
| 1 | Throatseeker | Notable | -10.2% | +0.0% | 输出 |
| 2 | Stormbreaker | Notable | -10.2% | +0.0% | 输出 |
| 3 | Sunder the Flesh | Notable | -8.9% | +0.0% | 输出 |
| 4 | Stormcharged | Notable | -7.8% | +0.0% | 输出 |
| 5 | Gore Spike | Notable | -7.7% | +0.0% | 输出 |
| 6 | Thin Ice | Notable | -6.3% | +0.0% | 输出 |
| 7 | Careful Assassin | Notable | -5.8% | +0.0% | 输出 |
| 8 | For the Jugular | Notable | -5.5% | -0.3% | 兼顾 |
| 9 | Sacrificial Blood | Notable | -5.1% | +0.0% | 输出 |
| 10 | Dynamism | Notable | -5.1% | +0.0% | 输出 |
| 11 | Deadly Force | Notable | -5.0% | +0.0% | 输出 |
| 12 | Evocational Practitioner | Notable | -4.8% | +0.0% | 输出 |
| 13 | Critical Overload | Notable | -4.7% | +0.0% | 输出 |
| 14 | True Strike | Notable | -3.8% | +0.0% | 输出 |
| 15 | Potent Incantation | Notable | -3.8% | +0.0% | 输出 |
| 16 | All Natural | Notable | -3.8% | +0.0% | 输出 |
| 17 | Sudden Escalation | Notable | -3.1% | +0.0% | 输出 |
| 18 | Breaking Point | Notable | -2.7% | +0.0% | 输出 |

### 纯防御天赋

| 天赋 | 移除后 EHP% |
|------|-------------|
| Melding | -5.6% |
| Mind Over Matter | -14.5% |
| Dampening Shield | -5.0% |
| Pure Energy | -5.6% |
| Heavy Buffer | -7.7% |

### 无效天赋 (17 个)

Invocated Echoes, The Spring Hare, Blood Transfusion, Practiced Signs, Echoing Thunder, Energise, Heavy Frost, Echoing Frost, Invocated Efficiency, Overflowing Power, Echoing Flames, Sanguine Tides, Vitality Siphon, Marked Agility, Acceleration, Infusion of Power, Sanguimancy

## 7. 未分配天赋探索

| # | 天赋 | 类型 | DPS% | EHP% | 分类 |
|---|------|------|------|------|------|
| 1 | Dimensional Weakspot | Notable | +25.9% | +0.0% | 输出 |
| 2 | Glaciation | Notable | +24.3% | +0.0% | 输出 |
| 3 | Primal Sundering | Notable | +20.7% | +0.0% | 输出 |
| 4 | Exposed to the Cosmos | Notable | +20.5% | +0.0% | 输出 |
| 5 | Storm Swell | Notable | +17.4% | +0.0% | 输出 |
| 6 | Snowpiercer | Notable | +17.1% | +0.3% | 兼顾 |
| 7 | Breath of Ice | Notable | +17.1% | +0.3% | 兼顾 |
| 8 | Endless Blizzard | Notable | +14.3% | +0.0% | 输出 |
| 9 | Deep Freeze | Notable | +13.8% | +0.0% | 输出 |
| 10 | Cremation | Notable | +13.5% | +0.0% | 输出 |

*（另有 584 个候选天赋未显示）*

## 8. 珠宝诊断

### Megalomaniac (Diamond, UNIQUE)

- **DPS 贡献**: +10.2% | **EHP 贡献**: -0.0% | **状态**: ok | **槽位**: Jewel 21984
- **分配天赋**: invocated limit, harness the elements (DPS +10.2%, EHP -0.0%)

| Mod | 类型 | 值 | DPS% | EHP% |
|-----|------|-----|------|------|
| GrantedPassive | LIST | invocated limit | -0.0% | -0.0% |
| GrantedPassive | LIST | harness the elements | +10.2% | -0.0% |

### Blight Wound (Sapphire, RARE)

- **DPS 贡献**: +3.5% | **EHP 贡献**: +3.5% | **状态**: ok | **槽位**: Jewel 7960

| Mod | 类型 | 值 | DPS% | EHP% |
|-----|------|-----|------|------|
| EnergyShield | INC | 20 | -0.0% | +3.5% |
| CritChance | INC | 14 | +2.7% | -0.0% |
| AilmentMagnitude | INC | 11 | +0.9% | -0.0% |

### Bramble Cut (Sapphire, RARE)

- **DPS 贡献**: +3.4% | **EHP 贡献**: +3.0% | **状态**: ok | **槽位**: Jewel 61834

| Mod | 类型 | 值 | DPS% | EHP% |
|-----|------|-----|------|------|
| Damage | INC | 12 | +1.5% | -0.0% |
| EnergyShield | INC | 17 | -0.0% | +3.0% |
| CritChance | INC | 10 | +1.9% | -0.0% |

### Heart of the Well (Diamond, UNIQUE)

- **DPS 贡献**: +2.6% | **EHP 贡献**: -0.0% | **状态**: ok | **槽位**: Jewel 32763

| Mod | 类型 | 值 | DPS% | EHP% |
|-----|------|-----|------|------|
| CritMultiplier | INC | 12 | +2.6% | -0.0% |
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
| 1 | Trinity | +55.9% | +55.9% (条件: Total Resonance Count=150) | +0.0% | 100 |

<details>
<summary><b>Trinity 详细数据</b></summary>

### 条件参数范围

| 端点 | 裸光环 | 真实 | 辅助增益 | Speed INC |
|------|--------|------|----------|-----------|
| Total Resonance Count=0 | +0.0% | +0.0% | — | 104% |
| Total Resonance Count=300 | +69.9% | +69.9% | — | 104%→126% |

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

| 3 | Charge Infusion | +16.5% | +16.5% ⚠️模拟 | +0.0% | 30 |

<details>
<summary><b>Charge Infusion 详细数据</b></summary>

### 基础数值

- 有效等级: **Lv27** (基础 Lv24 + 辅助 +3)
- MORE per 30 Resonance: **27%**

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

- **Elemental Conflux** (Lv25): 分别注入 74% MORE 到火/冰/电取平均。伤害构成：火 31.4% / 冰 66.1% / 电 2.5%
  三次模拟 DPS：火 31599 / 冰 38178 / 电 26110
- **Charge Infusion** (Lv24): 需启用 Charge 配置才能生效，已模拟 F=3/P=7/E=3

**模拟方法说明：**

- **等级前提**：光环模拟基于构筑实际宝石等级数据（非固定 Level 20）
- **裸光环 DPS**：仅光环宝石效果（禁用所有辅助宝石），用于和「潜在光环推荐」对比。真实 DPS 含辅助宝石额外增益，标注在括号中
- **DPS 贡献计算**：移除光环后 DPS 下降百分比（正值=正向贡献）。条件光环需注入参数才能生效，默认注入参数最大值的 50%，标注在真实 DPS 括号中
- **构筑已有 modifier**：施法速度 INC 126%（来自 POB skillModList），总 MORE ×0.91。INC 叠加为加法（新增边际递减），MORE 叠加为乘法
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
| 2 | Berserk（狂暴） | 30 | +20.0% | +0.0% | 需精魄 30（缺 30）; MORE Damage + 受伤增加 |
| 3 | Archmage（大法师） | 100 | +17.9% | +0.0% | 需精魄 100（缺 100）; Mana 转附加闪电伤害 |

### 9C. 精魄辅助推荐

| # | 精魄辅助 | 精魄 | DPS% | 条件 | 来源 |
|---|----------|------|------|------|------|
| 1 | Mysticism II | 30 | +5.1% | 需精魄 30（缺 30） ⚠️估算 | 动态扫描 |
| 2 | Mysticism I | 15 | +3.8% | 需精魄 15（缺 15） ⚠️估算 | 动态扫描 |

其余 19 个辅助无可模拟的 DPS 效果。

### 9D. 精魄预算

| 项目 | 精魄 |
|------|------|
| 总精魄 | 405 |
| 已用精魄 | 405 |
| 可用精魄 | 0 |
| 推荐光环消耗 | 160 |
| 推荐后剩余 | -160 |

**注意**: 推荐光环的精魄总消耗超过可用精魄，需要根据优先级取舍。

### 9E. 数据一致性检查

**⚠️ 以下项目需要人工确认：**

- EC 使用构筑实际等级 Lv25（MORE=74%），非满级 Lv20
- Charge Infusion 使用非默认 Charge 数量: PowerCharges=7

### 9F. POB 未实现效果预估

**⚠️ 以下技能效果在 POB 中未实现，已通过配置模拟：**

| 技能 | 效果描述 | DPS 预估 |
|------|----------|----------|
| **Pinnacle of Power** | 7 × (15% + 20×0.1%) = 119% MORE 元素伤害（PowerChargesMax） | **+118.9%** |

**注**: 这些效果由 `config/pob_unimplemented_effects.yaml` 配置，
实际游戏效果可能因条件触发方式不同而有差异。

## 10. 总结与建议

当前 **Frost Bomb** TotalDPS = **61,229**，AverageHit = 141,297，Speed = 0.43/s，CritChance = 66.5%，CritMultiplier = 4.02x。

### ⚔️ 进攻面

**DPS 灵敏度 Top 5**（所需投入越少 = 性价比越高）：

| # | 维度 | 类型 | 当前值 | 所需值 | 公式 |
|---|------|------|--------|--------|------|
| 1 | crit_chance_base | BASE | 0 | +4% | baseCrit 0.0%→4.5%, 需要 +4.5% → DPS +17.8% |
| 2 | elemental_pen | BASE | 8 | +12% | 需要 +12% 穿透 → DPS +20.7% |
| 3 | cold_pen | BASE | 0 | +18% | 需要 +18% 穿透 → DPS +20.5% |
| 4 | crit_multi_base | BASE | 100 | +30% | CritBase 100→130, 需要 +30 → DPS +20.1% |
| 5 | fire_pen | BASE | 0 | +36% | 需要 +36% 穿透 → DPS +19.5% |

*穿透维度均无影响（敌人抗性已为负值），面对高抗 Boss 时会成为有效优化方向。*

### 🛡️ 防御面

**最短板**: Chaos（承伤仅为最强的 19%）

**防御性价比最高**: 法术格挡概率，需要 +38% 即可提升 EHP +20%

### 💧 资源与恢复

**⚠️ 精魄超载**: 占用 131%，需要缩减光环或精魄辅助

**恢复增强 Top 3**：

1. 魔力再生: BASE 39→46, 需要 +8 → 魔力恢复 +20.6%
2. 生命再生: BASE 0→14, 需要 +14 → 生命恢复 +19.5%
3. 魔力恢复速率: INC 0%→20%, 需要 +20 → 魔力恢复 +20.6%

### 🌳 天赋

**推荐点出 Top 5**：

1. **Dimensional Weakspot**: DPS +25.9%
2. **Glaciation**: DPS +24.3%
3. **Primal Sundering**: DPS +20.7%
4. **Exposed to the Cosmos**: DPS +20.5%
5. **Storm Swell**: DPS +17.4%

**⚠️ 17 个无效天赋**: Invocated Echoes, The Spring Hare, Blood Transfusion, Practiced Signs, Echoing Thunder, Energise, Heavy Frost, Echoing Frost 等 17 个

### 💎 珠宝

**最佳**: Megalomaniac (DPS +10.2%, EHP -0.0%)
**可替换**: Controlled Metamorphosis
