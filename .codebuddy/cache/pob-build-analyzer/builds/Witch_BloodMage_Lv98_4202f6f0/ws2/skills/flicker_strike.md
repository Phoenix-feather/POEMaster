# Flicker Strike 构筑全面分析报告

## 0. 执行摘要

### 维度概览

| 维度 | 关键指标 |
|------|---------|
| 进攻 | TotalDPS **423,409** |
| 防御 | TotalEHP **17,330**（最短板: Physical） |
| 资源 | Spirit 占用 **75%** |


### 关键发现

1. ⚠️ **物理抗性/防御是最短板**（承伤仅 8,355，为最强的 28%）
2. ⚠️ 混沌抗性差 **33%** 未满
3. ⚠️ 精魄预算紧张（75% 占用）
4. ⚠️ 18 个已分配天赋对 DPS 和 EHP 均无可测量影响
5. 💡 **crit_multi_base** 对 DPS 影响最大（每 1% 提升 0.73% DPS）

### 优化方向 Top 3

1. **crit_multi_base** (BASE): 每 1% 提升 0.73% DPS，需要 +28% 达到 +20% DPS
2. **attack_speed_inc** (INC): 每 1% 提升 0.64% DPS，需要 +32% 达到 +20% DPS
3. **flat_lightning_attack** (BASE): 每 1 提升 0.23% DPS，需要 +88 达到 +20% DPS

## 1. 构筑基线

### 构筑修饰符

| 修饰符 | 总量 | 天赋 | 装备 | 珠宝 |
|--------|------|------|------|------|
| 施法速度 INC | 33% | +17% | +16% | — |
| 暴击率 INC | 140% | +140% | — | — |
| 暴击伤害 INC | 291% | +291% | — | — |

### 构筑属性

| 属性 | 数值 |
|------|------|
| 总属性 | 452 |
| 力量 | 83 |
| 敏捷 | 123 |
| 智力 | 246 |

### 技能 KPI

| 指标 | 数值 |
|------|------|
| 主技能 | Flicker Strike |
| 技能类型 | 攻击 |
| TotalDPS | **423,409** |
| AverageHit | 0 |
| Speed | 1.11/s |
| CritChance | 73.8% |
| CritMultiplier | 8.24x |
| TotalEHP | 17,330 |
| 最短板承伤 | **8,355** (物理) |

## 2. DPS 来源拆解

### 施法速度 = 1.40/s

**类别汇总**: Skill: +1.4

| 来源 | 类别 | 值 |
|------|------|-----|
| 武器攻击频率 | Skill | +1.4 |

### Speed INC = 59%

**类别汇总**: Sim: +26.0 | Tree: +17.0 | Item: +16.0

| 来源 | 类别 | 值 |
|------|------|-----|
| ⚠ CI speed (模拟) | Sim | +26.0 |
| Hateforge, Moulded Mitts (Gloves) | Item | +16.0 |
| Whirling Assault | Tree | +8.0 |
| Quarterstaff Speed | Tree | +3.0 |
| Quarterstaff Speed | Tree | +3.0 |
| Quarterstaff Speed | Tree | +3.0 |

### CritChance BASE = 73.8% (POB实际, 手动推算=48.8%)

**类别汇总**: Skill: +15.0 | Tree: +1.0

| 来源 | 类别 | 值 |
|------|------|-----|
| 基础暴击率 | Skill | +15.0 |
| Struck Through | Tree | +1.0 |

### CritChance INC = 140%

**类别汇总**: Tree: +140.0

| 来源 | 类别 | 值 |
|------|------|-----|
| Critical Exploit | Tree | +25.0 |
| True Strike | Tree | +20.0 |
| Heartstopping | Tree | +20.0 |
| Throatseeker | Tree | -20.0 |
| Stormcharged | Tree | +15.0 |
| Critical Chance | Tree | +10.0 |
| Critical Chance | Tree | +10.0 |
| Quarterstaff Critical Chance | Tree | +10.0 |
| Critical Chance | Tree | +10.0 |
| Deadly Force | Tree | +10.0 |
| Critical Chance | Tree | +10.0 |
| Critical Chance | Tree | +10.0 |
| Quarterstaff Critical Chance | Tree | +10.0 |

### CritChance MORE = +27.0%

**类别汇总**: Sim: +27%

| 来源 | 类别 | 值 |
|------|------|-----|
| ⚠ CI crit (模拟) | Sim | +27.0% MORE |

### CritMultiplier BASE = 115

**类别汇总**: Base: +100.0 | Item: +15.0

| 来源 | 类别 | 值 |
|------|------|-----|
| Base | Base | +100.0 |
| Dread Gnarl, Bolting Quarterstaff (Weapon 1 Swap) | Item | +15.0 |

### CritMultiplier INC = 291%

**类别汇总**: Tree: +291.0

| 来源 | 类别 | 值 |
|------|------|-----|
| Throatseeker | Tree | +60.0 |
| Martial Artistry | Tree | +25.0 |
| Heartbreaking | Tree | +25.0 |
| For the Jugular | Tree | +25.0 |
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

### CritMultiplier MORE = +61.2%

**类别汇总**: Skill: +30% | Other: +24%

| 来源 | 类别 | 值 |
|------|------|-----|
| Overextend | Skill | +30.0% MORE |
| Bifurcated Crit Damage Bonus | Other | +23.8% MORE |

### 点燃 DPS = 11,846

**公式**: `× effMult 0.6000  (持续 4.00s, 几率 39.1%)`

**类别汇总**: Tree: +173.0

| 来源 | 类别 | 值 |
|------|------|-----|
| Crashing Wave | Tree | +36.0 |
| Deadly Force | Tree | +25.0 |
| Damage on Critical | Tree | +20.0 |
| Damage on Critical | Tree | +20.0 |
| Companion Damage | Tree | +12.0 |
| Companion Damage | Tree | +12.0 |
| Companion Damage | Tree | +12.0 |
| Companion Damage | Tree | +12.0 |
| Herald Damage | Tree | +12.0 |
| Herald Damage | Tree | +12.0 |

### 流血 DPS = 30,264

**公式**: `× 0.6层 × effMult 1.2000  (持续 5.00s, 几率 11.1%)`

**类别汇总**: Tree: +173.0

| 来源 | 类别 | 值 |
|------|------|-----|
| Crashing Wave | Tree | +36.0 |
| Deadly Force | Tree | +25.0 |
| Damage on Critical | Tree | +20.0 |
| Damage on Critical | Tree | +20.0 |
| Companion Damage | Tree | +12.0 |
| Companion Damage | Tree | +12.0 |
| Companion Damage | Tree | +12.0 |
| Companion Damage | Tree | +12.0 |
| Herald Damage | Tree | +12.0 |
| Herald Damage | Tree | +12.0 |

### Combined DPS = 380,421

**类别汇总**: Hit: +423409.0 | DOT: +42111.0

| 来源 | 类别 | 值 |
|------|------|-----|
| Hit DPS | Hit | +423,409 |
| 流血 DPS | DOT | +30,264 |
| 点燃 DPS | DOT | +11,846 |

## 3. 灵敏度分析

### 3A. 进攻灵敏度（DPS）

| # | 维度 | 类型 | 所需值 | 单位 | 效果/单位 | 当前值 | 公式 |
|---|------|------|--------|------|----------|--------|------|
| 1 | crit_multi_base | BASE | +28.0% | % | 0.73%/% | 115 | CritBase 115→143, 需要 +28 → DPS +20.5% |
| 2 | attack_speed_inc | INC | +31.5% | % | 0.64%/% | 59 | INC 59%→90%, 需要 +32 → DPS +20.1% |
| 3 | flat_lightning_attack | BASE | +87.5 |  | 0.23%/1 | 0 | 需要添加 88-175 基础伤害 → DPS +20.1% |
| 4 | flat_fire_attack | BASE | +91.5 |  | 0.22%/1 | 0 | 需要添加 92-183 基础伤害 → DPS +20.1% |
| 5 | flat_cold_attack | BASE | +91.5 |  | 0.22%/1 | 0 | 需要添加 92-183 基础伤害 → DPS +20.1% |
| 6 | crit_multi_inc | INC | +93.0% | % | 0.22%/% | 291 | INC 291%→384%, 需要 +93 → DPS +20.1% |
| 7 | attack_damage_inc | INC | +96.5% | % | 0.21%/% | 183 | INC 183%→280%, 需要 +96 → DPS +20.1% |
| 8 | melee_damage_inc | INC | +96.5% | % | 0.21%/% | 183 | INC 183%→280%, 需要 +96 → DPS +20.1% |
| 9 | elemental_damage_inc | INC | +106.5% | % | 0.19%/% | 183 | INC 183%→290%, 需要 +106 → DPS +20.1% |
| 10 | flat_physical_attack | BASE | +172.5 |  | 0.12%/1 | 0 | 需要添加 172-345 基础伤害 → DPS +19.9% |
| 11 | lightning_damage_inc | INC | +248.5% | % | 0.08%/% | 183 | INC 183%→432%, 需要 +248 → DPS +20.0% |
| 12 | fire_damage_inc | INC | +287.5% | % | 0.07%/% | 183 | INC 183%→470%, 需要 +288 → DPS +20.0% |

**无影响维度**: physical_damage_inc, cold_damage_inc, chaos_damage_inc, crit_chance_inc, crit_chance_base, lightning_pen, fire_pen, cold_pen, elemental_pen, chaos_pen, projectile_count, aoe_inc, duration_inc

### 3B. 防御灵敏度（EHP）

| 维度 | 类型 | 所需值 | 每单位 EHP 提升 | 公式 |
|------|------|--------|---------------|------|
| 法术格挡概率 | BASE | 33.5% | +0.61%/单位 | BASE 0→34, 需要 +34 → EHP +20.5% |
| 格挡概率 | BASE | 33.5% | +0.61%/单位 | BASE 0→34, 需要 +34 → EHP +20.5% |
| 生命上限 | INC | 49.0% | +0.41%/单位 | INC 14%→63%, 需要 +49 → EHP +20.0% |
| 闪避值 | BASE | 1994.5 | +0.01%/单位 | BASE 7→2002, 需要 +1994 → EHP +18.6% |

**无法达到目标**: 护甲固定值, 全元素抗性, 冰霜抗性, 物理减伤, 生命固定值, 火焰抗性, 护甲增加, 闪避增加, 闪电抗性, 混沌抗性

### 3C. 恢复增强灵敏度

注入多少恢复属性可使对应恢复指标提升 **20%**：

| 增强属性 | 所需注入 | 当前总值 | 公式 |
|---------|---------|---------|------|
| 魔力恢复速率 | 34.0% | — | INC 0%→34%, 需要 +34 → 魔力恢复 +20.2% |
| 魔力再生 | 36.0/s | 178.2 | BASE 178→214, 需要 +36 → 魔力恢复 +20.2% |

## 4. 防御面

### 4A. 生命池构成

| 资源 | 数值 | 备注 |
|------|------|------|
| Life | 2,914 | — |
| Mana | 4,456 | 可用 4,456 |
| MoM | 100% | 魔力优先承受伤害 |

### 4B. 减伤层

| 层 | 数值 |
|------|------|
| 护甲 | 144 |
| 闪避 | 285 |
| 攻击格挡 | 0% |
| 法术格挡 | 0% |

### 4C. 抗性面板

| 元素 | 当前 | 上限 | 状态 |
|------|------|------|------|
| 火焰 | 74% | 75% | 接近 (差 1%) |
| 冰霜 | 67% | 75% | 未满 (差 8%) |
| 闪电 | 75% | 75% | 满 (+5%溢出) |
| 混沌 | 42% | 75% | 未满 (差 33%) |

未满抗性: 火焰, 冰霜, 混沌 — 优先补满可显著提升对应元素 EHP。

### 4D. 最大承伤 (MaxHitTaken)

**TotalEHP = 17,330**（平均承受 4.1 次攻击）

| 伤害类型 | MaxHitTaken | 占最强% |
|----------|-------------|--------|
| Physical | 8,355 | 28% ← 最短板 |
| 火焰 | 28,763 | 97% |
| 冰霜 | 23,170 | 78% |
| 闪电 | 29,790 | 100% |
| 混沌 | 14,382 | 48% |

**最短板**: Physical（仅承受 8,355 伤害，为最强的 28%）

### 4E. 承伤乘数 (TakenHitMult)

数值越小越好，表示实际承受伤害占原始伤害的比例。

| 伤害类型 | 承伤乘数 | 含义 |
|----------|---------|------|
| Physical | 0.990 (99.0%) | 每承受 100 伤害实际受 99 ← 最短板 |
| 火焰 | 0.290 (29.0%) | 每承受 100 伤害实际受 29 |
| 冰霜 | 0.360 (36.0%) | 每承受 100 伤害实际受 36 |
| 闪电 | 0.280 (28.0%) | 每承受 100 伤害实际受 28 |
| 混沌 | 0.580 (58.0%) | 每承受 100 伤害实际受 58 |

### 4F. DOT 有效生命

| 伤害类型 | DotEHP |
|----------|--------|
| Physical | 7,370 |
| 火焰 | 28,346 |
| 冰霜 | 22,333 |
| 闪电 | 29,480 |
| 混沌 | 12,707 |


## 5. 资源面

### 5A. 资源预算

| 资源 | 总量 | 可用 | 占用率 |
|------|------|------|--------|
| Life | 2,914 | 2,914 | — |
| Mana | 4,456 | 4,456 | 0% |
| Spirit | 161 | 41 | ⚠️ 75% |

### 5C. 魔力恢复能力

总恢复速率: **162.7/s**（回满可用 4,456 约需 27.4s）

| # | 来源 | 每秒恢复 | 占比 |
|---|------|---------|------|
| 1 | 再生 | 149.7/s | 92% |
| 2 | 回收 | 13.0/s | 8% |

## 6. 已分配天赋价值

### DPS 影响天赋

| # | 天赋 | 类型 | 移除后 DPS% | 移除后 EHP% | 分类 | 效果 |
|---|------|------|-------------|-------------|------|------|
| 1 | Eldritch Battery | Keystone | -14.9% | -8.9% | 兼顾 | Converts all Energy Shield to Mana; Doubles Mana Costs |
| 2 | Stormcharged | Notable | -12.7% | +0.0% | 输出 | 40% increased Elemental Damage if you've dealt a Critical Hit Recently; 15% increased Critical Hit Chance |
| 3 | Martial Artistry | Notable | -12.4% | +0.0% | 输出 | 25% increased Accuracy Rating with Quarterstaves; 25% increased Critical Damage Bonus with Quarterstaves; +25 to Dexterity |
| 4 | Throatseeker | Notable | -11.0% | +0.0% | 输出 | 60% increased Critical Damage Bonus; 20% reduced Critical Hit Chance |
| 5 | Inspiring Ally | Notable | -10.0% | +0.0% | 输出 | Increases and Reductions to Companion Damage also apply to you |
| 6 | Critical Exploit | Notable | -9.3% | +0.0% | 输出 | 25% increased Critical Hit Chance |
| 7 | Deadly Force | Notable | -8.8% | +0.0% | 输出 | 25% increased Damage if you've dealt a Critical Hit in the past 8 seconds; 10% increased Critical Hit Chance |
| 8 | Heartstopping | Notable | -7.7% | -0.3% | 兼顾 | +10 to Intelligence; 20% increased Critical Hit Chance |
| 9 | Crashing Wave | Notable | -7.5% | +0.0% | 输出 | 36% increased Damage if you've dealt a Critical Hit in the past 8 seconds |
| 10 | True Strike | Notable | -7.5% | +0.0% | 输出 | +10 to Dexterity; 20% increased Critical Hit Chance |
| 11 | For the Jugular | Notable | -5.7% | -0.3% | 兼顾 | 25% increased Critical Damage Bonus; +10 to Intelligence |
| 12 | All Natural | Notable | -5.6% | -4.4% | 兼顾 | +5% to all Elemental Resistances; 30% increased Elemental Damage |
| 13 | Struck Through | Notable | -5.6% | +0.0% | 输出 | Attacks have +1% to Critical Hit Chance |
| 14 | Heartbreaking | Notable | -5.5% | -0.4% | 兼顾 | 25% increased Critical Damage Bonus; +10 to Strength |
| 15 | Whirling Assault | Notable | -5.0% | +0.0% | 输出 | 8% increased Attack Speed with Quarterstaves; Knocks Back Enemies if you get a Critical Hit with a Quarterstaff |
| 16 | Material Solidification | Notable | -2.4% | +0.0% | 输出 | Gain 8% of Damage as Extra Physical Damage; 15% increased effect of Fully Broken Armour |
| 17 | The Howling Primate | Notable | -0.2% | -0.3% | 兼顾 | 15% increased Presence Area of Effect; Aura Skills have 10% increased Magnitudes; +10 to Intelligence |

### 纯防御天赋

| 天赋 | 移除后 EHP% | 效果 |
|------|-------------|------|
| Mind Over Matter | -53.4% | All Damage is taken from Mana before Life; 50% less Mana Recovery Rate |
| Chakra of Life | -1.2% | 3% increased maximum Life; 10% increased Life Recovery rate |
| Crimson Power | -20.3% | Gain additional maximum Life equal to 100% of the Item Energy Shield on Equipped Body Armour |
| Grasping Wounds | -11.6% | 25% of Life Loss from Hits is prevented, then that much Life is lost over 4 seconds instead |

### 无效天赋 (18 个)

Sanguimancy, One with the Storm, Blood Barbs, Flow State, Stupefy, Blackflame Covenant, Falcon Dive, The Power Within, Overflowing Power, The Fabled Stag, Tenfold Attacks, Chakra of Thought, Sanguine Tides, Flow Like Water, Acceleration, Dizzying Hits, Deep Trance, Primal Hunger

## 7. 未分配天赋探索

| # | 天赋 | 类型 | DPS% | EHP% | 分类 |
|---|------|------|------|------|------|
| 1 | Cooked | Notable | +12.9% | -1.0% | 兼顾 |
| 2 | Comradery | Notable | +12.5% | +0.0% | 输出 |
| 3 | Stimulants | Notable | +10.1% | +0.0% | 输出 |
| 4 | Barbaric Strength | Notable | +9.7% | +0.4% | 兼顾 |
| 5 | Imbibed Power | Notable | +9.2% | +0.0% | 输出 |
| 6 | Serrated Edges | Notable | +8.6% | +0.0% | 输出 |
| 7 | Killer Instinct | Notable | +8.3% | +0.0% | 输出 |
| 8 | Bringer of Order | Notable | +8.3% | +0.0% | 输出 |
| 9 | Crystal Elixir | Notable | +7.5% | +0.0% | 输出 |
| 10 | Crushing Verdict | Notable | +6.9% | +0.0% | 输出 |

*（另有 159 个候选天赋未显示）*

## 8. 珠宝诊断

### Heart of the Well (Diamond, UNIQUE)

- **DPS 贡献**: +22.0% | **EHP 贡献**: -0.0% | **状态**: ok | **槽位**: Jewel 21984

| Mod | 类型 | 值 | DPS% | EHP% |
|-----|------|-----|------|------|
| DamageGainAsFire | BASE | 14 | +11.1% | -0.0% |
| DamageGainAsLightning | BASE | 13 | +10.9% | -0.0% |
| ManaOnKill | BASE | 1 | -0.0% | -0.0% |
| Condition:CanGainRage | FLAG | true | -0.0% | -0.0% |

### Megalomaniac (Diamond, UNIQUE)

- **DPS 贡献**: +3.5% | **EHP 贡献**: -0.0% | **状态**: ok | **槽位**: Jewel 61834
- **分配天赋**: the spring hare, blood of rage (DPS +3.5%, EHP -0.0%)

| Mod | 类型 | 值 | DPS% | EHP% |
|-----|------|-----|------|------|
| GrantedPassive | LIST | the spring hare | +3.5% | -0.0% |
| GrantedPassive | LIST | blood of rage | -0.0% | -0.0% |

### ? (?, ?)

- **DPS 贡献**: +0.0% | **EHP 贡献**: +0.0% | **状态**: no_base | **槽位**: Jewel 61419

### ? (?, ?)

- **DPS 贡献**: +0.0% | **EHP 贡献**: +0.0% | **状态**: no_base | **槽位**: Jewel 7960

### ? (?, ?)

- **DPS 贡献**: +0.0% | **EHP 贡献**: +0.0% | **状态**: no_base | **槽位**: Jewel 32763

## 9. 光环与精魄分析

### 9A. 现有光环 DPS 贡献

| # | 光环 | 裸光环 DPS | 真实 DPS | EHP | 精魄 |
|---|------|------------|----------|-----|------|
| 1 | Charge Infusion | +46.8% | +46.8% ⚠️模拟 | +0.0% | 30 |

<details>
<summary><b>Charge Infusion 详细数据</b></summary>

### 基础数值

- 有效等级: **Lv26** (基础 Lv23 + 辅助 +3)
- MORE per 30 Resonance: **27%**

</details>

| 2 | Herald of Thunder | +5.3% | +5.3% | +0.0% | 30 |

<details>
<summary><b>Herald of Thunder 详细数据</b></summary>

### 基础数值

- 有效等级: **Lv18**
- MORE per 30 Resonance: **3%**

</details>

| 3 | Wind Dancer | +0.0% | +0.0% (条件: # of Wind Dancer Stacks=49999) | +1.1% | 30 |

<details>
<summary><b>Wind Dancer 详细数据</b></summary>

### 条件参数范围

| 端点 | 裸光环 | 真实 | 辅助增益 | Speed INC |
|------|--------|------|----------|-----------|
| # of Wind Dancer Stacks=0 | +0.0% | +0.0% | — | 59% |
| # of Wind Dancer Stacks=99999 | +0.0% | +0.0% | — | 59% |

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
- **构筑已有 modifier**：施法速度 INC 59%（来自 POB skillModList），总 MORE ×1.00。INC 叠加为加法（新增边际递减），MORE 叠加为乘法
- **品质上限**：所有宝石品质按 20% 上限计算（游戏实际上限）。构筑中超品质宝石已自动降级
- **条件范围计算**：设置参数绝对值（0 和 max），对比「无光环」DPS。Speed 门槛效果从 POB skillModList 读取端点 INC 差值，边际 = 新增INC / (1+已有INC)
- **期望收益计算**：对于 EC 等随机效果光环，期望 = 效果值 × 受影响技能元素占比之和 ÷ 3（因为随机选择火/冰/电之一）

**纯防御光环**（移除后 EHP 下降）：

- **Wind Dancer**: EHP +1.1%, 精魄 30

### 9B. 潜在光环推荐

| # | 光环 | 精魄 | DPS% | EHP% | 说明 |
|---|------|------|------|------|------|
| 1 | Attrition（损耗） | 30 | +59.1% | +0.0% | 命中附带 Wither 叠层 |

**无 DPS 影响：**

- Trinity（三位一体）
- Archmage（大法师）
- Berserk（狂暴）
- Elemental Conflux（元素交融）

### 9C. 精魄辅助推荐

| # | 精魄辅助 | 精魄 | DPS% | 条件 | 来源 |
|---|----------|------|------|------|------|
| 1 | Direstrike II（猛击 II） | 40 | +14.6% | Low Life | 硬编码 |
| 2 | Direstrike I（猛击 I） | 20 | +10.4% | Low Life | 硬编码 |

### 9D. 精魄预算

| 项目 | 精魄 |
|------|------|
| 总精魄 | 161 |
| 已用精魄 | 120 |
| 可用精魄 | 41 |
| 推荐光环消耗 | 30 |
| 推荐后剩余 | 11 |

### 9E. 数据一致性检查

**⚠️ 以下项目需要人工确认：**

- Charge Infusion 使用非默认 Charge 数量: PowerCharges=8
- Trinity 无明显 DPS 影响：可能因为构筑条件不满足或模拟环境限制
- Archmage 无明显 DPS 影响：可能因为构筑条件不满足或模拟环境限制
- Berserk 无明显 DPS 影响：可能因为构筑条件不满足或模拟环境限制
- Elemental Conflux 无明显 DPS 影响：可能因为构筑条件不满足或模拟环境限制

## 10. 总结与建议

当前 **Flicker Strike** TotalDPS = **423,409**，AverageHit = 0，Speed = 1.11/s，CritChance = 73.8%，CritMultiplier = 8.24x。

### ⚔️ 进攻面

**DPS 灵敏度 Top 5**（所需投入越少 = 性价比越高）：

| # | 维度 | 类型 | 当前值 | 所需值 | 公式 |
|---|------|------|--------|--------|------|
| 1 | crit_multi_base | BASE | 115 | +28% | CritBase 115→143, 需要 +28 → DPS +20.5% |
| 2 | attack_speed_inc | INC | 59 | +32% | INC 59%→90%, 需要 +32 → DPS +20.1% |
| 3 | flat_lightning_attack | BASE | 0 | +88 | 需要添加 88-175 基础伤害 → DPS +20.1% |
| 4 | flat_fire_attack | BASE | 0 | +92 | 需要添加 92-183 基础伤害 → DPS +20.1% |
| 5 | flat_cold_attack | BASE | 0 | +92 | 需要添加 92-183 基础伤害 → DPS +20.1% |

*穿透维度均无影响（敌人抗性已为负值），面对高抗 Boss 时会成为有效优化方向。*

### 🛡️ 防御面

**最短板**: Physical（承伤仅为最强的 28%）

**防御性价比最高**: 法术格挡概率，需要 +34% 即可提升 EHP +20%

### 💧 资源与恢复

**恢复增强 Top 3**：

1. 魔力恢复速率: INC 0%→34%, 需要 +34 → 魔力恢复 +20.2%
2. 魔力再生: BASE 178→214, 需要 +36 → 魔力恢复 +20.2%

### 🌳 天赋

**推荐点出 Top 5**：

1. **Cooked**: DPS +12.9%，EHP -1.0%
2. **Comradery**: DPS +12.5%
3. **Stimulants**: DPS +10.1%
4. **Barbaric Strength**: DPS +9.7%，EHP +0.4%
5. **Imbibed Power**: DPS +9.2%

**⚠️ 18 个无效天赋**: Sanguimancy, One with the Storm, Blood Barbs, Flow State, Stupefy, Blackflame Covenant, Falcon Dive, The Power Within 等 18 个

### 💎 珠宝

**最佳**: Heart of the Well (DPS +22.0%, EHP -0.0%)
