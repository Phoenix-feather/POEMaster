# Comet 构筑全面分析报告

## 0. 执行摘要

### 维度概览

| 维度 | 关键指标 |
|------|---------|
| 进攻 | TotalDPS **25,527** |
| 防御 | TotalEHP **9,834**（最短板: Chaos） |
| 资源 | Spirit 占用 **195%** |
| 恢复 | 生命恢复 **284/s** |


### 关键发现

1. ⚠️ **混沌抗性/防御是最短板**（承伤仅 4,439，为最强的 24%）
2. ⚠️ 混沌抗性差 **75%** 未满
3. 🔴 精魄预算非常紧张（195% 占用）
4. ⚠️ 25 个已分配天赋对 DPS 和 EHP 均无可测量影响
5. 💡 **crit_chance_base** 对 DPS 影响最大（每 1% 提升 3.80% DPS）

### 优化方向 Top 3

1. **crit_chance_base** (BASE): 每 1% 提升 3.80% DPS，需要 +6% 达到 +20% DPS
2. **crit_multi_base** (BASE): 每 1% 提升 0.45% DPS，需要 +44% 达到 +20% DPS
3. **spell_damage_inc** (INC): 每 1% 提升 0.36% DPS，需要 +55% 达到 +20% DPS

## 1. 构筑基线

### 构筑修饰符

| 修饰符 | 总量 | 天赋 | 装备 | 珠宝 |
|--------|------|------|------|------|
| 施法速度 INC | 78% | +27% | +51% | — |
| 伤害 INC | 66% | +66% | — | — |
| 元素伤害 INC | 101% | +72% | +29% | — |
| 暴击率 INC | 66% | +66% | — | — |
| 暴击伤害 INC | 205% | +205% | — | — |

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
| 主技能 | Comet |
| 技能类型 | 法术 |
| TotalDPS | **25,527** |
| AverageHit | 36,872 |
| Speed | 0.69/s |
| CritChance | 27.2% |
| CritMultiplier | 4.05x |
| TotalEHP | 9,834 |
| 最短板承伤 | **4,439** (混沌) |

## 2. DPS 来源拆解

活跃伤害类型: Lightning, Cold

### 通用伤害 INC (Lightning,Cold) = 66%

**类别汇总**: Tree: +66.0

| 来源 | 类别 | 值 |
|------|------|-----|
| Potent Incantation | Tree | +30.0 |
| Triggered Spell Damage | Tree | +16.0 |
| Triggered Spell Damage | Tree | +14.0 |
| Life Spell Damage and Costs | Tree | +6.0 |

### 元素伤害 INC (Lightning,Cold) = 101%

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

### 通用伤害 MORE (Lightning,Cold) = -9.0%

**类别汇总**: Skill: +-30% | Other: +30%

| 来源 | 类别 | 值 |
|------|------|-----|
| Spell Cascade | Skill | +-30.0% MORE |
| Zenith_II_sim | Other | +30.0% MORE |

### 元素伤害 MORE (Lightning,Cold) = +169.0%

**类别汇总**: Other: +72% | Skill: +56%

| 来源 | 类别 | 值 |
|------|------|-----|
| Trinity | Skill | +56.0% MORE |
| UA_Unbound | Other | +40.0% MORE |
| EC_sim | Other | +23.0% MORE |

### Speed Base = 0.69/s

**类别汇总**: Skill: +0.7

| 来源 | 类别 | 值 |
|------|------|-----|
| Trigger Rate (computed) | Skill | +0.7 |

### Speed INC = 125%

**类别汇总**: Item: +51.0 | Tree: +27.0 | Other: +25.0 | Skill: +22.0

| 来源 | 类别 | 值 |
|------|------|-----|
| CI_speed_sim | Other | +25.0 |
| Damnation Grip, Unset Ring (Ring 2) | Item | +24.0 |
| Trinity | Skill | +22.0 |
| Torment Band, Unset Ring (Ring 1) | Item | +19.0 |
| Acceleration | Tree | +10.0 |
| Hysseg's Claw, Familial Talisman (Weapon 1 Swap) | Item | +8.0 |
| Flow Like Water | Tree | +8.0 |
| Potent Incantation | Tree | -5.0 |
| Skill Speed | Tree | +4.0 |
| Skill Speed | Tree | +4.0 |
| Skill Speed | Tree | +3.0 |
| Skill Speed | Tree | +3.0 |

### CritChance BASE = 13.0% (base 13.0% + added 0%)

**类别汇总**: Skill: +13.0

| 来源 | 类别 | 值 |
|------|------|-----|
| 技能基础暴击率 | Skill | +13.0 |

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

### CritChance MORE = +26.0%

**类别汇总**: Other: +26%

| 来源 | 类别 | 值 |
|------|------|-----|
| CI_crit_sim | Other | +26.0% MORE |

### CritMultiplier BASE = 100

**类别汇总**: Base: +100.0

| 来源 | 类别 | 值 |
|------|------|-----|
| Base | Base | +100.0 |

### CritMultiplier INC = 205%

**类别汇总**: Tree: +205.0

| 来源 | 类别 | 值 |
|------|------|-----|
| Throatseeker | Tree | +60.0 |
| For the Jugular | Tree | +25.0 |
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

### Cold → Lightning Conversion/Gain = Cold → Lightning: 增益 22.0%

**类别汇总**: Item: +12.0 | Tree: +10.0

| 来源 | 类别 | 值 |
|------|------|-----|
| Heart of the Well, Diamond (Jewel) | Item | +12.0 (Gain as Lightning) |
| I am the Thunder... | Tree | +10.0 (Gain as Lightning) |

### Cold → Cold Self-Gain = Cold Self-Gain: 增益 10.0%

**类别汇总**: Tree: +10.0

| 来源 | 类别 | 值 |
|------|------|-----|
| I am the Blizzard... | Tree | +10.0 (Gain as Cold) |

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

### Combined DPS = 36,872

**类别汇总**: Hit: +25526.6

| 来源 | 类别 | 值 |
|------|------|-----|
| Hit DPS | Hit | +25,527 |

## 3. 灵敏度分析

### 3A. 进攻灵敏度（DPS）

| # | 维度 | 类型 | 所需值 | 单位 | 效果/单位 | 当前值 | 公式 |
|---|------|------|--------|------|----------|--------|------|
| 1 | crit_chance_base | BASE | +5.5% | % | 3.80%/% | 0 | baseCrit 0.0%→5.5%, 需要 +5.5% → DPS +20.9% |
| 2 | crit_multi_base | BASE | +44.5% | % | 0.45%/% | 100 | CritBase 100→144, 需要 +44 → DPS +19.9% |
| 3 | spell_damage_inc | INC | +55.0% | % | 0.36%/% | 177 | INC 177%→232%, 需要 +55 → DPS +20.0% |
| 4 | elemental_damage_inc | INC | +55.0% | % | 0.36%/% | 177 | INC 177%→232%, 需要 +55 → DPS +20.0% |
| 5 | cold_damage_inc | INC | +66.5% | % | 0.30%/% | 177 | INC 177%→244%, 需要 +66 → DPS +20.1% |
| 6 | crit_chance_inc | INC | +73.5% | % | 0.27%/% | 66 | INC 66%→140%, 需要 +74 → DPS +20.1% |
| 7 | crit_multi_inc | INC | +134.5% | % | 0.15%/% | 205 | INC 205%→340%, 需要 +134 → DPS +19.9% |
| 8 | cast_speed_inc | INC | +265.5% | % | 0.08%/% | 125 | INC 125%→390%, 需要 +266 → DPS +20.0% |
| 9 | lightning_damage_inc | INC | +331.0% | % | 0.06%/% | 167 | INC 167%→498%, 需要 +331 → DPS +20.0% |

**无影响维度**: physical_damage_inc, fire_damage_inc, chaos_damage_inc, lightning_pen, fire_pen, cold_pen, elemental_pen, chaos_pen, projectile_count, aoe_inc, duration_inc

### 3B. 防御灵敏度（EHP）

| 维度 | 类型 | 所需值 | 每单位 EHP 提升 | 公式 |
|------|------|--------|---------------|------|
| 法术格挡概率 | BASE | 31.5% | +0.65%/单位 | BASE 0→32, 需要 +32 → EHP +20.5% |
| 格挡概率 | BASE | 31.5% | +0.65%/单位 | BASE 0→32, 需要 +32 → EHP +20.5% |
| 生命上限 | INC | 45.0% | +0.45%/单位 | INC 5%→50%, 需要 +45 → EHP +20.2% |
| 混沌抗性 | BASE | 68.5% | +0.29%/单位 | BASE 0→68, 需要 +68 → EHP +19.8% |
| 闪避值 | BASE | 1719.0 | +0.01%/单位 | BASE 7→1726, 需要 +1719 → EHP +20.6% |

**无法达到目标**: 闪电抗性, 护甲增加, 生命固定值, 冰霜抗性, 火焰抗性, 闪避增加, 物理减伤, 全元素抗性, 护甲固定值

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
| Energy Shield | 1,514 | — |
| Mana | 1,410 | 可用 1,410 |
| MoM | 100% | 魔力优先承受伤害 |

### 4B. 减伤层

| 层 | 数值 |
|------|------|
| 护甲 | 0 |
| 闪避 | 533 |
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

**TotalEHP = 9,834**（平均承受 2.3 次攻击）

| 伤害类型 | MaxHitTaken | 占最强% |
|----------|-------------|--------|
| Physical | 5,196 | 28% |
| 火焰 | 18,557 | 100% |
| 冰霜 | 18,557 | 100% |
| 闪电 | 18,557 | 100% |
| 混沌 | 4,439 | 24% ← 最短板 |

**最短板**: 混沌（仅承受 4,439 伤害，为最强的 24%）

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
| Physical | 5,196 |
| 火焰 | 20,784 |
| 冰霜 | 20,784 |
| 闪电 | 20,784 |
| 混沌 | 4,439 |


## 5. 资源面

### 5A. 资源预算

| 资源 | 总量 | 可用 | 占用率 |
|------|------|------|--------|
| Life | 2,272 | 2,272 | — |
| Mana | 1,410 | 1,410 | 0% |
| Spirit | 292 | -278 | 🔴 195% |
| ES | 1,514 | 1,514 | — |

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

| # | 天赋 | 类型 | 移除后 DPS% | 移除后 EHP% | 分类 |
|---|------|------|-------------|-------------|------|
| 1 | All Natural | Notable | -10.9% | +0.0% | 进攻 |
| 2 | Potent Incantation | Notable | -10.3% | +0.0% | 进攻 |
| 3 | I am the Blizzard... | Notable | -7.6% | +0.0% | 进攻 |
| 4 | I am the Thunder... | Notable | -7.3% | +0.0% | 进攻 |
| 5 | True Strike | Notable | -5.5% | +0.0% | 进攻 |
| 6 | Throatseeker | Notable | -4.5% | +0.0% | 进攻 |
| 7 | Sudden Escalation | Notable | -4.4% | +0.0% | 进攻 |
| 8 | For the Jugular | Notable | -3.7% | -0.4% | 混合 |
| 9 | Acceleration | Notable | -1.4% | +0.0% | 进攻 |
| 10 | The Spring Hare | Notable | -1.3% | +0.0% | 进攻 |
| 11 | Flow Like Water | Notable | -1.1% | -0.2% | 混合 |

### 纯防御天赋

| 天赋 | 移除后 EHP% |
|------|-------------|
| Melding | -2.3% |
| Mind Over Matter | -29.2% |
| Heavy Buffer | -5.4% |

### 无效天赋 (25 个)

Invocated Echoes, ...and I Shall Rage, Impending Doom, Blood Transfusion, Critical Exploit, Thin Ice, Energise, Heavy Frost, Dynamism, Breaking Point, Marked Agility, Shimmering, Efficient Inscriptions, The Power Within, Overflowing Power, Evocational Practitioner, Moment of Truth, Deadly Force, Careful Assassin, Infusion of Power, Marked for Sickness, Stormwalker, Frostwalker, The Soul Springs Eternal, Crashing Wave

## 7. 未分配天赋探索

| # | 天赋 | 类型 | DPS% | EHP% | 分类 |
|---|------|------|------|------|------|
| 1 | Endless Blizzard | Notable | +16.8% | +0.0% | 进攻 |
| 2 | Arcane Intensity | Notable | +15.2% | +0.0% | 进攻 |
| 3 | Jack of all Trades | Notable | +14.5% | +0.0% | 进攻 |
| 4 | Invocated Efficiency | Notable | +14.5% | +0.0% | 进攻 |
| 5 | Sacrificial Blood | Notable | +14.5% | +0.0% | 进攻 |
| 6 | Calculated Hunter | Notable | +12.9% | +0.0% | 进攻 |
| 7 | Ruin | Notable | +12.7% | +0.0% | 进攻 |
| 8 | Spellblade | Notable | +11.6% | +0.0% | 进攻 |
| 9 | Inspiring Ally | Notable | +11.3% | +0.0% | 进攻 |
| 10 | Dispatch Foes | Notable | +10.9% | +0.0% | 进攻 |

*（另有 146 个候选天赋未显示）*

## 8. 珠宝诊断

### Heart of the Well (Diamond, UNIQUE)

- **DPS 贡献**: +14.3% | **EHP 贡献**: -0.0% | **状态**: ok | **槽位**: Jewel 32763

| Mod | 类型 | 值 | DPS% | EHP% |
|-----|------|-----|------|------|
| DamageGainAsLightning | BASE | 12 | +14.3% | -0.0% |
| ManaOnKill | BASE | 1 | +6.0% | -0.0% |
| HybridManaAndLifeCost_Life | BASE | 3 | +6.0% | -0.0% |
| InstantEnergyShieldLeech | BASE | 15 | +6.0% | -0.0% |
| InstantManaLeech | BASE | 15 | +6.0% | -0.0% |
| InstantLifeLeech | BASE | 15 | +6.0% | -0.0% |

### Rapture Shard (Sapphire, RARE)

- **DPS 贡献**: +11.1% | **EHP 贡献**: +2.1% | **状态**: ok | **槽位**: Jewel 61834

| Mod | 类型 | 值 | DPS% | EHP% |
|-----|------|-----|------|------|
| EnergyShield | INC | 17 | +6.0% | +2.1% |
| ElementalDamage | INC | 15 | +11.1% | -0.0% |
| CurseActivation | INC | 14 | +6.0% | -0.0% |

### Chimeric Spark (Sapphire, RARE)

- **DPS 贡献**: +10.8% | **EHP 贡献**: +1.9% | **状态**: ok | **槽位**: Jewel 7960

| Mod | 类型 | 值 | DPS% | EHP% |
|-----|------|-----|------|------|
| EnergyShield | INC | 15 | +6.0% | +1.9% |
| ElementalDamage | INC | 14 | +10.8% | -0.0% |
| CurseActivation | INC | 15 | +6.0% | -0.0% |

### Megalomaniac (Diamond, UNIQUE)

- **DPS 贡献**: +7.2% | **EHP 贡献**: -0.0% | **状态**: ok | **槽位**: Jewel 21984
- **分配天赋**: the spring hare, savoured blood (DPS +7.2%, EHP -0.0%)

| Mod | 类型 | 值 | DPS% | EHP% |
|-----|------|-----|------|------|
| GrantedPassive | LIST | the spring hare | +7.2% | -0.0% |
| GrantedPassive | LIST | savoured blood | +6.0% | -0.0% |

### Controlled Metamorphosis (Diamond, UNIQUE)

- **DPS 贡献**: +6.0% | **EHP 贡献**: -0.0% | **状态**: ok | **槽位**: Jewel 61419

| Mod | 类型 | 值 | DPS% | EHP% |
|-----|------|-----|------|------|
| JewelData | LIST | (complex data) | +6.0% | -0.0% |
| JewelData | LIST | (complex data) | +6.0% | -0.0% |
| ElementalResist | BASE | -6 | +6.0% | -0.0% |

## 9. 光环与精魄分析

### 9A. 现有光环 DPS 贡献

| # | 光环 | 裸光环 DPS | 真实 DPS | EHP | 精魄 |
|---|------|------------|----------|-----|------|
| 1 | Trinity | +51.4% | +61.3% (辅助+9.9%) (条件: Total Resonance Count=150) | +0.0% | 100 |

<details>
<summary><b>Trinity 详细数据</b></summary>

### 条件参数范围

| 端点 | 裸光环 | 真实 | 辅助增益 | Speed INC |
|------|--------|------|----------|-----------|
| Total Resonance Count=0 | +0.0% | +0.0% | — | 103% |
| Total Resonance Count=300 | +63.9% | +75.6% | +11.7% | 103%→125% |

### 辅助贡献

- **Dialla's Desire**: +1 level, +10% quality
- **Uhtred's Omen**: +3 level (条件: 1个其他辅助)
- 总辅助贡献: **+9.9%** DPS（Total Resonance Count=150时）
- 端点差异: Total Resonance Count=0时+0.0%，Total Resonance Count=300时+11.7%

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

| 3 | Charge Infusion | +14.8% | +14.8% ⚠️模拟 | +0.0% | 30 |

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

- **Elemental Conflux** (Lv21): 分别注入 70% MORE 到火/冰/电取平均。伤害构成：火 0.0% / 冰 83.8% / 电 16.2%
  三次模拟 DPS：火 13075 / 冰 20748 / 电 14553
- **Charge Infusion** (Lv21): 需启用 Charge 配置才能生效，已模拟 F=3/P=7/E=3

**模拟方法说明：**

- **等级前提**：光环模拟基于构筑实际宝石等级数据（非固定 Level 20）
- **裸光环 DPS**：仅光环宝石效果（禁用所有辅助宝石），用于和「潜在光环推荐」对比。真实 DPS 含辅助宝石额外增益，标注在括号中
- **DPS 贡献计算**：移除光环后 DPS 下降百分比（正值=正向贡献）。条件光环需注入参数才能生效，默认注入参数最大值的 50%，标注在真实 DPS 括号中
- **构筑已有 modifier**：施法速度 INC 125%（来自 POB skillModList），总 MORE ×0.91。INC 叠加为加法（新增边际递减），MORE 叠加为乘法
- **品质上限**：所有宝石品质按 20% 上限计算（游戏实际上限）。构筑中超品质宝石已自动降级
- **条件范围计算**：设置参数绝对值（0 和 max），对比「无光环」DPS。Speed 门槛效果从 POB skillModList 读取端点 INC 差值，边际 = 新增INC / (1+已有INC)
- **期望收益计算**：对于 EC 等随机效果光环，期望 = 效果值 × 受影响技能元素占比之和 ÷ 3（因为随机选择火/冰/电之一）

**DPS/EHP 影响未检测到** (1 个)：

这些光环可能提供非DPS收益（如生存/功能性），或其效果依赖动态条件（如Frenzy Charge）而POB未完全计算。

- **Purity of Fire**: 精魄 130

### 9B. 潜在光环推荐

| # | 光环 | 精魄 | DPS% | EHP% | 说明 |
|---|------|------|------|------|------|
| 1 | Archmage（大法师） | 100 | +32.5% | +0.0% | 需精魄 100（缺 100）; Mana 转附加闪电伤害 |

**无 DPS 影响：**

- Attrition（损耗）
- Berserk（狂暴）

### 9C. 精魄辅助推荐

| # | 精魄辅助 | 精魄 | DPS% | 条件 | 来源 |
|---|----------|------|------|------|------|
| 1 | Mysticism II | 30 | +10.9% | 需精魄 30（缺 30） ⚠️估算 | 动态扫描 |
| 2 | Mysticism I | 15 | +4.1% | 需精魄 15（缺 15） ⚠️估算 | 动态扫描 |

其余 19 个辅助无可模拟的 DPS 效果。

### 9D. 精魄预算

| 项目 | 精魄 |
|------|------|
| 总精魄 | 292 |
| 已用精魄 | 292 |
| 可用精魄 | 0 |
| 推荐光环消耗 | 100 |
| 推荐后剩余 | -100 |

**注意**: 推荐光环的精魄总消耗超过可用精魄，需要根据优先级取舍。

### 9E. 数据一致性检查

**⚠️ 以下项目需要人工确认：**

- EC 使用构筑实际等级 Lv21（MORE=70%），非满级 Lv20
- Charge Infusion 使用非默认 Charge 数量: PowerCharges=7
- Attrition 无 DPS 影响：需要命中敌人才能叠加 Wither，纯模拟可能无法体现
- Berserk 无 DPS 影响：可能因为构筑已通过其他方式获得 Rage 效果

### 9F. POB 未实现效果预估

**⚠️ 以下技能效果在 POB 中未实现，已通过配置模拟：**

| 技能 | 效果描述 | DPS 预估 |
|------|----------|----------|
| **Unbound Avatar** | 40% MORE 元素伤害（Unbound 状态） | **+31.5%** |

**注**: 这些效果由 `config/pob_unimplemented_effects.yaml` 配置，
实际游戏效果可能因条件触发方式不同而有差异。

## 10. 总结与建议

当前 **Comet** TotalDPS = **25,527**，AverageHit = 36,872，Speed = 0.69/s，CritChance = 27.2%，CritMultiplier = 4.05x。

### ⚔️ 进攻面

**DPS 灵敏度 Top 5**（所需投入越少 = 性价比越高）：

| # | 维度 | 类型 | 当前值 | 所需值 | 公式 |
|---|------|------|--------|--------|------|
| 1 | crit_chance_base | BASE | 0 | +6% | baseCrit 0.0%→5.5%, 需要 +5.5% → DPS +20.9% |
| 2 | crit_multi_base | BASE | 100 | +44% | CritBase 100→144, 需要 +44 → DPS +19.9% |
| 3 | spell_damage_inc | INC | 177 | +55% | INC 177%→232%, 需要 +55 → DPS +20.0% |
| 4 | elemental_damage_inc | INC | 177 | +55% | INC 177%→232%, 需要 +55 → DPS +20.0% |
| 5 | cold_damage_inc | INC | 177 | +66% | INC 177%→244%, 需要 +66 → DPS +20.1% |

*穿透维度均无影响（敌人抗性已为负值），面对高抗 Boss 时会成为有效优化方向。*

### 🛡️ 防御面

**最短板**: Chaos（承伤仅为最强的 24%）

**防御性价比最高**: 法术格挡概率，需要 +32% 即可提升 EHP +20%

### 💧 资源与恢复

**⚠️ 精魄超载**: 占用 195%，需要缩减光环或精魄辅助

**恢复增强 Top 3**：

1. 生命再生: BASE 0→10, 需要 +10 → 生命恢复 +22.0%
2. 魔力再生: BASE 56→68, 需要 +12 → 魔力恢复 +21.3%
3. 生命恢复速率: INC 0%→26%, 需要 +26 → 生命恢复 +20.4%

### 🌳 天赋

**推荐点出 Top 5**：

1. **Endless Blizzard**: DPS +16.8%
2. **Arcane Intensity**: DPS +15.2%
3. **Jack of all Trades**: DPS +14.5%
4. **Invocated Efficiency**: DPS +14.5%
5. **Sacrificial Blood**: DPS +14.5%

**⚠️ 25 个无效天赋**: Invocated Echoes, ...and I Shall Rage, Impending Doom, Blood Transfusion, Critical Exploit, Thin Ice, Energise, Heavy Frost 等 25 个

### 💎 珠宝

**最佳**: Heart of the Well (DPS +14.3%, EHP -0.0%)
