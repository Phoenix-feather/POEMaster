# Lightning Arrow 构筑全面分析报告

## 0. 执行摘要

### 维度概览

| 维度 | 关键指标 |
|------|---------|
| 进攻 | TotalDPS **63,178** |
| 防御 | TotalEHP **24,553**（最短板: Physical） |
| 资源 | Spirit 占用 **123%** |


### 关键发现

1. ⚠️ **物理抗性/防御是最短板**（承伤仅 4,473，为最强的 29%）
2. 🔴 精魄预算非常紧张（123% 占用）
3. ⚠️ 7 个已分配天赋对 DPS 和 EHP 均无可测量影响
4. 💡 **elemental_pen** 对 DPS 影响最大（每 1% 提升 1.79% DPS）

### 优化方向 Top 3

1. **elemental_pen** (BASE): 每 1% 提升 1.79% DPS，需要 +10% 达到 +20% DPS
2. **lightning_pen** (BASE): 每 1% 提升 1.79% DPS，需要 +12% 达到 +20% DPS
3. **crit_chance_base** (BASE): 每 1% 提升 1.52% DPS，需要 +14% 达到 +20% DPS

## 1. 构筑基线

### 构筑修饰符

| 修饰符 | 总量 | 天赋 | 装备 | 珠宝 |
|--------|------|------|------|------|
| 攻击速度 INC | 119% | +39% | +80% | — |
| 伤害 INC | 522% | +347% | +175% | — |
| 元素伤害 INC | 32% | +32% | — | — |
| 暴击率 INC | 34% | — | +34% | — |

### 构筑属性

| 属性 | 数值 |
|------|------|
| 总属性 | 341 |
| 力量 | 52 |
| 敏捷 | 177 |
| 智力 | 112 |

### 技能 KPI

| 指标 | 数值 |
|------|------|
| 主技能 | Lightning Arrow |
| 技能类型 | 攻击, 投射物 |
| TotalDPS | **63,178** |
| AverageHit | 0 |
| Speed | 2.64/s |
| CritChance | 7.8% |
| CritMultiplier | 2.00x |
| TotalEHP | 24,553 |
| 最短板承伤 | **4,473** (物理) |

## 2. DPS 来源拆解

活跃伤害类型: Physical, Lightning, Cold, Fire

### Physical Base Damage = 839-1429 (x3.51 base mult)

**类别汇总**: Skill: +300.0 | Item: +23.0

| 来源 | 类别 | 值 |
|------|------|-----|
| 技能基础 | Skill | +300.0 (220-380) |
| Hate Spiral, Breach Ring (Ring 1) | Item | +23.0 (+19-27) |

### Lightning Base Damage = 46-1320 (x3.51 base mult)

**类别汇总**: Item: +124.5 | Skill: +47.5 | Other: +22.5

| 来源 | 类别 | 值 |
|------|------|-----|
| Hate Spiral, Breach Ring (Ring 1) | Item | +48.0 (+5-91) |
| 技能基础 | Skill | +47.5 (3-92) |
| Vengeance Circle, Breach Ring (Ring 2) | Item | +40.0 (+1-79) |
| Victory Barb, Volant Quiver | Item | +36.5 (+3-70) |
| Many Sources:64% Quiver Bonus Effect | Other | +22.5 (+1-44) |

### Cold Base Damage = 130-204 (x3.51 base mult)

**类别汇总**: Item: +47.5

| 来源 | 类别 | 值 |
|------|------|-----|
| Hate Spiral, Breach Ring (Ring 1) | Item | +24.5 (+20-29) |
| Mind Fingers, Stalking Bracers (Gloves) | Item | +23.0 (+17-29) |

### Fire Base Damage = 56-112 (x3.51 base mult)

**类别汇总**: Item: +24.0

| 来源 | 类别 | 值 |
|------|------|-----|
| Mind Fingers, Stalking Bracers (Gloves) | Item | +24.0 (+16-32) |

### 通用伤害 INC (Physical,Lightning,Cold,Fire) = 594%

**类别汇总**: Tree: +347.0 | Item: +175.0 | Other: +72.0

| 来源 | 类别 | 值 |
|------|------|-----|
| Victory Barb, Volant Quiver | Item | +49.0 |
| Killer Instinct | Tree | +40.0 |
| Victory Barb, Volant Quiver | Item | +38.0 |
| Many Sources:64% Quiver Bonus Effect | Other | +31.0 |
| Victory Barb, Volant Quiver | Item | +27.0 |
| Maiming Strike | Tree | +25.0 |
| Many Sources:64% Quiver Bonus Effect | Other | +24.0 |
| Empyrean Star, Emerald (Jewel) | Item | +19.0 |
| Many Sources:64% Quiver Bonus Effect | Other | +17.0 |
| Kite Runner | Tree | +15.0 |
| Hypnotic Shine, Emerald (Jewel) | Item | +15.0 |
| Kite Runner | Tree | +15.0 |
| Hypnotic Shine, Emerald (Jewel) | Item | +14.0 |
| Empyrean Star, Emerald (Jewel) | Item | +13.0 |
| Damage and Companion Damage | Tree | +12.0 |
| Companion Damage | Tree | +12.0 |
| Companion Damage | Tree | +12.0 |
| Companion Damage | Tree | +12.0 |
| Companion Damage | Tree | +12.0 |
| Damage with Companion in Presence | Tree | +12.0 |
| Herald Damage | Tree | +12.0 |
| Damage with Companion in Presence | Tree | +12.0 |
| Damage with Companion in Presence | Tree | +12.0 |
| Bow Damage | Tree | +12.0 |
| Herald Damage | Tree | +12.0 |
| Damage with Companion in Presence | Tree | +12.0 |
| Projectile Speed | Tree | +10.0 |
| Projectile Speed | Tree | +10.0 |
| Damage and Companion Damage | Tree | +10.0 |
| Projectile Damage | Tree | +10.0 |
| Attack Damage | Tree | +10.0 |
| Bow Damage | Tree | +10.0 |
| Projectile Damage | Tree | +10.0 |
| Attack Damage | Tree | +10.0 |
| Attack Damage | Tree | +10.0 |
| Projectile Damage | Tree | +10.0 |
| Attack Damage and Movement Speed | Tree | +8.0 |

### 元素伤害 INC (Lightning,Cold,Fire) = 32%

**类别汇总**: Tree: +32.0

| 来源 | 类别 | 值 |
|------|------|-----|
| Catalysis | Tree | +20.0 |
| Elemental Attack Damage | Tree | +12.0 |

### 闪电伤害 INC (Lightning) = 130%

**类别汇总**: Tree: +88.0 | Item: +42.0

| 来源 | 类别 | 值 |
|------|------|-----|
| Vengeance Circle, Breach Ring (Ring 2) | Item | +42.0 |
| Coming Calamity | Tree | +40.0 |
| Lightning Damage | Tree | +12.0 |
| Lightning Damage | Tree | +12.0 |
| Lightning Damage | Tree | +12.0 |
| Lightning Damage | Tree | +12.0 |

### 元素伤害 MORE (Lightning,Cold,Fire) = +25.0%

**类别汇总**: Support: +25%

| 来源 | 类别 | 值 |
|------|------|-----|
| Elemental Armament II | Support | +25.0% MORE |

### 冰霜伤害 MORE (Cold) = -50.0%

**类别汇总**: Support: +-50%

| 来源 | 类别 | 值 |
|------|------|-----|
| Lightning Attunement | Support | +-50.0% MORE |

### 火焰伤害 MORE (Fire) = -50.0%

**类别汇总**: Support: +-50%

| 来源 | 类别 | 值 |
|------|------|-----|
| Lightning Attunement | Support | +-50.0% MORE |

### 攻击速度 = 1.28/s

**类别汇总**: Skill: +1.3

| 来源 | 类别 | 值 |
|------|------|-----|
| 武器攻击频率 | Skill | +1.3 |

### Speed INC = 129%

**类别汇总**: Item: +80.0 | Tree: +39.0 | Other: +10.0

| 来源 | 类别 | 值 |
|------|------|-----|
| Mind Fingers, Stalking Bracers (Gloves) | Item | +48.0 |
| Victory Barb, Volant Quiver | Item | +16.0 |
| Foe Rain, Gemini Bow | Item | +11.0 |
| Acceleration | Tree | +10.0 |
| Many Sources:64% Quiver Bonus Effect | Other | +10.0 |
| Flow Like Water | Tree | +8.0 |
| Flow State | Tree | +5.0 |
| Skill Speed | Tree | +4.0 |
| Empyrean Star, Emerald (Jewel) | Item | +3.0 |
| Skill Speed | Tree | +3.0 |
| Skill Speed | Tree | +3.0 |
| Skill Speed | Tree | +3.0 |
| Skill Speed | Tree | +3.0 |
| Hypnotic Shine, Emerald (Jewel) | Item | +2.0 |

### CritChance BASE = 7.8% (base 5.0% + added 0%)

**类别汇总**: Skill: +5.0

| 来源 | 类别 | 值 |
|------|------|-----|
| 基础暴击率 | Skill | +5.0 |

### CritChance INC = 55%

**类别汇总**: Item: +34.0 | Other: +21.0

| 来源 | 类别 | 值 |
|------|------|-----|
| Victory Barb, Volant Quiver | Item | +34.0 |
| Many Sources:64% Quiver Bonus Effect | Other | +21.0 |

### CritMultiplier BASE = 100

**类别汇总**: Base: +100.0

| 来源 | 类别 | 值 |
|------|------|-----|
| Base | Base | +100.0 |

### Lucky Hits (Physical,Lightning,Cold,Fire) = 20%

| 来源 | 类别 | 值 |
|------|------|-----|
| The Spring Hare | Tree | +20.0 |
| The Spring Hare | Tree | +20.0 |
| The Spring Hare | Tree | +20.0 |
| The Spring Hare | Tree | +20.0 |

### 点燃 DPS = 1

**公式**: `× 0.0层 × effMult 0.6000  (持续 4.00s, 几率 0.2%)`

**类别汇总**: Tree: +142.0 | Item: +82.0 | Other: +31.0

| 来源 | 类别 | 值 |
|------|------|-----|
| Victory Barb, Volant Quiver | Item | +49.0 |
| Many Sources:64% Quiver Bonus Effect | Other | +31.0 |
| Empyrean Star, Emerald | Item | +19.0 |
| Hypnotic Shine, Emerald | Item | +14.0 |
| Damage and Companion Damage | Tree | +12.0 |
| Companion Damage | Tree | +12.0 |
| Companion Damage | Tree | +12.0 |
| Companion Damage | Tree | +12.0 |
| Companion Damage | Tree | +12.0 |
| Damage with Companion in Presence | Tree | +12.0 |
| Herald Damage | Tree | +12.0 |
| Damage with Companion in Presence | Tree | +12.0 |
| Damage with Companion in Presence | Tree | +12.0 |
| Herald Damage | Tree | +12.0 |
| Damage with Companion in Presence | Tree | +12.0 |
| Damage and Companion Damage | Tree | +10.0 |

### DPS Multiplier = x1.03

**类别汇总**: Skill: +1.0

| 来源 | 类别 | 值 |
|------|------|-----|
| 技能 DPS 乘数 | Skill | +1.0 |

### Combined DPS = 63,179

**类别汇总**: Hit: +63177.9 | DOT: +1.3

| 来源 | 类别 | 值 |
|------|------|-----|
| Hit DPS | Hit | +63,178 |
| 点燃 DPS | DOT | +1.3 |

### Beam 感电几率 MORE = +40.0%

**类别汇总**: SkillEffect: +40%

| 来源 | 类别 | 值 |
|------|------|-----|
| Beam效果 | SkillEffect | +40.0% MORE |

### 敌人受伤增加 = x1.2000

**公式**: `所有伤害类型共享 x1.2000`

**类别汇总**: Ailment: +20.0

| 来源 | 类别 | 值 |
|------|------|-----|
| Shock: 受伤+20%（最小值） | Ailment | +20.0 |

### 敌人抗性乘区 (加权) = +0.0%

**公式**: `+0.0%  (抗性 50% - 穿透 0% = 有效 50%)`

**类别汇总**: Enemy: +50.0

| 来源 | 类别 | 值 |
|------|------|-----|
| 闪电 +0.0% (占93.2%) | Enemy | +0.0 |
| 冰霜 +0.0% (占3.3%) | Enemy | +0.0 |
| 物理 +0.0% (占2.3%) | Enemy | +0.0 |
| 火焰 +0.0% (占1.1%) | Enemy | +0.0 |

## 3. 灵敏度分析

### 3A. 进攻灵敏度（DPS）

| # | 维度 | 类型 | 所需值 | 单位 | 效果/单位 | 当前值 | 公式 |
|---|------|------|--------|------|----------|--------|------|
| 1 | elemental_pen | BASE | +10.5% | % | 1.79%/% | 0 | 需要 +10% 穿透 → DPS +18.8% |
| 2 | lightning_pen | BASE | +12.0% | % | 1.79%/% | 0 | 需要 +12% 穿透 → DPS +21.5% |
| 3 | crit_chance_base | BASE | +13.5% | % | 1.52%/% | 0 | baseCrit 0.0%→13.5%, 需要 +13.5% → DPS +20.6% |
| 4 | attack_speed_inc | INC | +45.5% | % | 0.44%/% | 129 | INC 129%→174%, 需要 +46 → DPS +20.1% |
| 5 | flat_physical_attack | BASE | +73.5 |  | 0.27%/1 | 0 | 需要添加 74-147 基础伤害 → DPS +20.1% |
| 6 | flat_lightning_attack | BASE | +75.5 |  | 0.27%/1 | 0 | 需要添加 76-151 基础伤害 → DPS +20.2% |
| 7 | flat_fire_attack | BASE | +115.5 |  | 0.17%/1 | 0 | 需要添加 116-231 基础伤害 → DPS +20.1% |
| 8 | flat_cold_attack | BASE | +115.5 |  | 0.17%/1 | 0 | 需要添加 116-231 基础伤害 → DPS +20.1% |
| 9 | attack_damage_inc | INC | +164.0% | % | 0.12%/% | 594 | INC 594%→758%, 需要 +164 → DPS +20.1% |
| 10 | projectile_damage_inc | INC | +164.0% | % | 0.12%/% | 594 | INC 594%→758%, 需要 +164 → DPS +20.1% |
| 11 | elemental_damage_inc | INC | +181.5% | % | 0.11%/% | 594 | INC 594%→776%, 需要 +182 → DPS +20.1% |
| 12 | lightning_damage_inc | INC | +191.5% | % | 0.10%/% | 594 | INC 594%→786%, 需要 +192 → DPS +20.0% |
| 13 | crit_multi_inc | INC | +271.0% | % | 0.07%/% | 0 | INC 0%→271%, 需要 +271 → DPS +20.0% |
| 14 | crit_chance_inc | INC | +422.0% | % | 0.05%/% | 55 | INC 55%→477%, 需要 +422 → DPS +20.0% |

**无影响维度**: physical_damage_inc, fire_damage_inc, cold_damage_inc, chaos_damage_inc, melee_damage_inc, crit_multi_base, fire_pen, cold_pen, chaos_pen, projectile_count, aoe_inc, duration_inc

### 3B. 防御灵敏度（EHP）

| 维度 | 类型 | 所需值 | 每单位 EHP 提升 | 公式 |
|------|------|--------|---------------|------|
| 法术格挡概率 | BASE | 32.5% | +0.61%/单位 | BASE 0→32, 需要 +32 → EHP +19.8% |
| 格挡概率 | BASE | 32.5% | +0.61%/单位 | BASE 0→32, 需要 +32 → EHP +19.8% |
| 生命上限 | INC | 58.5% | +0.34%/单位 | INC 5%→64%, 需要 +58 → EHP +20.0% |
| 闪避增加 | INC | 163.5% | +0.14%/单位 | INC 346%→510%, 需要 +164 → EHP +22.5% |
| 闪避值 | BASE | 1089.5 | +0.02%/单位 | BASE 871→1960, 需要 +1090 → EHP +22.5% |
| 护甲固定值 | BASE | 4648.5 | +0.00%/单位 | BASE 0→4648, 需要 +4648 → EHP +19.7% |

**无法达到目标**: 物理减伤, 混沌抗性, 火焰抗性, 闪电抗性, 全元素抗性, 护甲增加, 生命固定值, 冰霜抗性

### 3C. 恢复增强灵敏度

注入多少恢复属性可使对应恢复指标提升 **20%**：

| 增强属性 | 所需注入 | 当前总值 | 公式 |
|---------|---------|---------|------|
| 魔力再生 | 5.5/s | 27.5 | BASE 27→33, 需要 +6 → 魔力恢复 +21.9% |
| 魔力恢复速率 | 37.0% | — | INC 0%→37%, 需要 +37 → 魔力恢复 +20.3% |

## 4. 防御面

### 4A. 生命池构成

| 资源 | 数值 | 备注 |
|------|------|------|
| Life | 1,488 | — |
| Energy Shield | 2,824 | — |
| Mana | 687 | 可用 687 |

### 4B. 减伤层

| 层 | 数值 |
|------|------|
| 护甲 | 0 |
| 闪避 | 13,273 |
| 攻击格挡 | 0% |
| 法术格挡 | 0% |
| 偏转 | 30% |

### 4C. 抗性面板

| 元素 | 当前 | 上限 | 状态 |
|------|------|------|------|
| 火焰 | 75% | 75% | 满 (+4%溢出) |
| 冰霜 | 75% | 75% | 满 |
| 闪电 | 75% | 75% | 满 (+18%溢出) |
| 混沌 | 75% | 75% | 满 (+5%溢出) |

### 4D. 最大承伤 (MaxHitTaken)

**TotalEHP = 24,553**（平均承受 5.8 次攻击）

| 伤害类型 | MaxHitTaken | 占最强% |
|----------|-------------|--------|
| Physical | 4,473 | 29% ← 最短板 |
| 火焰 | 15,400 | 100% |
| 冰霜 | 15,400 | 100% |
| 闪电 | 15,400 | 100% |
| 混沌 | 11,600 | 75% |

**最短板**: Physical（仅承受 4,473 伤害，为最强的 29%）

### 4E. 承伤乘数 (TakenHitMult)

数值越小越好，表示实际承受伤害占原始伤害的比例。

| 伤害类型 | 承伤乘数 | 含义 |
|----------|---------|------|
| Physical | 1.000 (100.0%) | 每承受 100 伤害实际受 100 ← 最短板 |
| 火焰 | 0.280 (28.0%) | 每承受 100 伤害实际受 28 |
| 冰霜 | 0.280 (28.0%) | 每承受 100 伤害实际受 28 |
| 闪电 | 0.280 (28.0%) | 每承受 100 伤害实际受 28 |
| 混沌 | 0.250 (25.0%) | 每承受 100 伤害实际受 25 |

### 4F. DOT 有效生命

| 伤害类型 | DotEHP |
|----------|--------|
| Physical | 4,312 |
| 火焰 | 17,248 |
| 冰霜 | 17,248 |
| 闪电 | 17,248 |
| 混沌 | 11,600 |


## 5. 资源面

### 5A. 资源预算

| 资源 | 总量 | 可用 | 占用率 |
|------|------|------|--------|
| Life | 1,488 | 1,488 | — |
| Mana | 687 | 687 | 0% |
| Spirit | 150 | -35 | 🔴 123% |
| ES | 2,824 | 2,824 | — |

### 5C. 魔力恢复能力

总恢复速率: **50.3/s**（回满可用 687 约需 13.7s）

| # | 来源 | 每秒恢复 | 占比 |
|---|------|---------|------|
| 1 | 再生 | 50.3/s | 100% |

## 6. 已分配天赋价值

### DPS 影响天赋

| # | 天赋 | 类型 | 移除后 DPS% | 移除后 EHP% | 分类 | 效果 |
|---|------|------|-------------|-------------|------|------|
| 1 | Feathered Fletching | Notable | -17.2% | +0.0% | 输出 | Increases and Reductions to Projectile Speed also apply to Damage with Bows |
| 2 | Inspiring Ally | Notable | -11.3% | +0.0% | 输出 | Increases and Reductions to Companion Damage also apply to you |
| 3 | Wrapped Quiver | Notable | -10.4% | +0.0% | 输出 | 20% increased bonuses gained from Equipped Quiver |
| 4 | Master Fletching | Notable | -10.4% | +0.0% | 输出 | 20% increased bonuses gained from Equipped Quiver |
| 5 | Killer Instinct | Notable | -4.9% | +0.0% | 输出 | 40% increased Attack Damage while on Full Life; 60% increased Attack Damage while on Low Life |
| 6 | Acceleration | Notable | -4.4% | +0.0% | 输出 | 3% increased Movement Speed; 10% increased Skill Speed |
| 7 | Coming Calamity | Notable | -4.2% | +0.0% | 输出 | 40% increased Cold Damage while affected by Herald of Ice; 40% increased Fire Damage while affected by Herald of Ash; 40% increased Lightning Damage while affected by Herald of Thunder |
| 8 | Kite Runner | Notable | -3.7% | +0.0% | 输出 | 3% increased Movement Speed; 15% increased Projectile Speed; 15% increased Projectile Damage |
| 9 | Wild Storm | Notable | -3.6% | +0.0% | 输出 | Gain 4% of Damage as Extra Cold Damage; Gain 4% of Damage as Extra Lightning Damage; +10 to Dexterity |
| 10 | Flow Like Water | Notable | -3.5% | +0.0% | 输出 | 8% increased Attack and Cast Speed; +5 to Dexterity and Intelligence |
| 11 | The Spring Hare | Notable | -3.2% | +0.0% | 输出 | 20% chance for Damage of Enemies Hitting you to be Unlucky; 20% chance for Damage with Hits to be Lucky |
| 12 | Maiming Strike | Notable | -3.1% | +0.0% | 输出 | 25% increased Attack Damage; Attacks have 25% chance to Maim on Hit |
| 13 | Catalysis | Notable | -2.2% | -1.9% | 兼顾 | 20% increased Elemental Damage with Attacks; 5% of Physical Damage from Hits taken as Damage of a Random Element |
| 14 | Flow State | Notable | -2.2% | +0.0% | 输出 | 5% increased Skill Speed; 15% increased Mana Regeneration Rate |

### 纯防御天赋

| 天赋 | 移除后 EHP% | 效果 |
|------|-------------|------|
| Escape Velocity | -4.8% | 3% increased Movement Speed; 30% increased Evasion Rating |
| Spectral Ward | -6.6% | +1 to Maximum Energy Shield per 12 Item Evasion Rating on Equipped Body Armour |
| Enhanced Reflexes | -5.7% | 20% increased Evasion Rating; Gain Deflection Rating equal to 5% of Evasion Rating; 8% increased Dexterity |
| Blur | -4.4% | 4% increased Movement Speed; 20% increased Evasion Rating; +10 to Dexterity |
| Mindful Awareness | -10.5% | 24% increased Evasion Rating; 24% increased maximum Energy Shield |

### 无效天赋 (7 个)

Gathering Winds, Light on your Feet, Momentum, Shimmering, Step Like Mist, Endless Munitions, Projectile Proximity Specialisation

## 7. 未分配天赋探索

| # | 天赋 | 类型 | DPS% | EHP% | 分类 |
|---|------|------|------|------|------|
| 1 | Electric Amplification | Notable | +36.9% | +0.0% | 输出 |
| 2 | Exposed to the Storm | Notable | +32.3% | +0.0% | 输出 |
| 3 | Dimensional Weakspot | Notable | +28.2% | +0.0% | 输出 |
| 4 | Forces of Nature | Notable | +28.2% | +0.0% | 输出 |
| 5 | Storm Surge | Notable | +27.4% | +0.0% | 输出 |
| 6 | Breath of Lightning | Notable | +26.9% | +0.0% | 输出 |
| 7 | Flash Storm | Notable | +26.9% | +0.0% | 输出 |
| 8 | Surging Currents | Notable | +26.9% | +0.0% | 输出 |
| 9 | Overload | Notable | +26.9% | +0.0% | 输出 |
| 10 | Primal Sundering | Notable | +22.5% | +0.0% | 输出 |

*（另有 215 个候选天赋未显示）*

## 8. 珠宝诊断

### Heart of the Well (Diamond, UNIQUE)

- **DPS 贡献**: +9.5% | **EHP 贡献**: -0.0% | **状态**: ok | **槽位**: Jewel 60735

| Mod | 类型 | 值 | DPS% | EHP% |
|-----|------|-----|------|------|
| DamageGainAsLightning | BASE | 15 | +9.5% | -0.0% |
| LifeOnKill | BASE | 1 | -0.0% | -0.0% |
| ManaOnKill | BASE | 1 | -0.0% | -0.0% |

### Empyrean Star (Emerald, RARE)

- **DPS 贡献**: +5.2% | **EHP 贡献**: -0.0% | **状态**: ok | **槽位**: Jewel 46882

| Mod | 类型 | 值 | DPS% | EHP% |
|-----|------|-----|------|------|
| Speed | INC | 3 | +1.3% | -0.0% |
| MovementSpeed | INC | 2 | -0.0% | -0.0% |
| Damage | INC | 13 | +1.6% | -0.0% |
| MinionModifier | LIST | (complex data) | +2.3% | -0.0% |

### Hypnotic Shine (Emerald, RARE)

- **DPS 贡献**: +4.4% | **EHP 贡献**: -0.0% | **状态**: ok | **槽位**: Jewel 32763

| Mod | 类型 | 值 | DPS% | EHP% |
|-----|------|-----|------|------|
| MinionModifier | LIST | (complex data) | +1.7% | -0.0% |
| MovementSpeed | INC | 2 | -0.0% | -0.0% |
| Damage | INC | 15 | +1.8% | -0.0% |
| Speed | INC | 2 | +0.9% | -0.0% |

### From Nothing (Diamond, UNIQUE)

- **DPS 贡献**: -0.0% | **EHP 贡献**: -0.0% | **状态**: ok | **槽位**: Jewel 61834

| Mod | 类型 | 值 | DPS% | EHP% |
|-----|------|-----|------|------|
| JewelData | LIST | (complex data) | -0.0% | -0.0% |
| FromNothingKeystones | LIST | (complex data) | -0.0% | -0.0% |

## 9. 光环与精魄分析

### 9A. 现有光环 DPS 贡献

| # | 光环 | 裸光环 DPS | 真实 DPS | EHP | 精魄 |
|---|------|------------|----------|-----|------|
| 1 | Wind Dancer ⚔️Gale Force(POB未算) | +0.0% | +0.0% (条件: # of Wind Dancer Stacks=49999) | +15.6% | 30 |

<details>
<summary><b>Wind Dancer 详细数据</b></summary>

### 条件参数范围

| 端点 | 裸光环 | 真实 | 辅助增益 | Speed INC |
|------|--------|------|----------|-----------|
| # of Wind Dancer Stacks=0 | +0.0% | +0.0% | — | 129% |
| # of Wind Dancer Stacks=99999 | +0.0% | +0.0% | — | 129% |

### 基础数值

- 有效等级: **Lv19**
- MORE per 30 Resonance: **1140%**

</details>

| 2 | Ghost Dance | +0.0% | +0.0% | +0.0% | 30 |

<details>
<summary><b>Ghost Dance 详细数据</b></summary>

### 基础数值

- 有效等级: **Lv19**
- MORE per 30 Resonance: **6200%**

</details>


**纯防御光环**（移除后 EHP 下降）：

- **Wind Dancer**: EHP +15.6%, 精魄 30

**DPS/EHP 影响未检测到** (1 个)：

这些光环可能提供非DPS收益（如生存/功能性），或其效果依赖动态条件（如Frenzy Charge）而POB未完全计算。

- **Ghost Dance**: 精魄 30

### 9B. 潜在光环推荐

| # | 光环 | 精魄 | DPS% | EHP% | 说明 |
|---|------|------|------|------|------|
| 1 | Trinity（三位一体） | 100 | +93.9% | +0.0% | 需精魄 100（缺 100）; 三属性穿透（需要 ResonanceCount 配置） |
| 2 | Attrition（损耗） | 30 | +60.3% | +0.0% | 需精魄 30（缺 30）; 命中附带 Wither 叠层 |
| 3 | Elemental Conflux（元素交融） | 60 | +18.8% | +0.0% | 需精魄 60（缺 60）; 元素异常状态同步 |
| 4 | Berserk（狂暴） | 30 | +17.3% | +0.0% | 需精魄 30（缺 30）; MORE Damage + 受伤增加 |
| 5 | Charge Infusion（充能灌注） | 30 | +15.8% | +32.4% | 需精魄 30（缺 30）; Frenzy/Power/Endurance Charge 增益 |

**无 DPS 影响：**

- Archmage（大法师）

### 9C. 精魄辅助推荐

| # | 精魄辅助 | 精魄 | DPS% | 条件 | 来源 |
|---|----------|------|------|------|------|
| 1 | Direstrike II（猛击 II） | 40 | +8.6% | 需精魄 40（缺 40）; Low Life | 硬编码 |
| 2 | Direstrike I（猛击 I） | 20 | +6.1% | 需精魄 20（缺 20）; Low Life | 硬编码 |

### 9D. 精魄预算

| 项目 | 精魄 |
|------|------|
| 总精魄 | 150 |
| 已用精魄 | 150 |
| 可用精魄 | 0 |
| 推荐光环消耗 | 250 |
| 推荐后剩余 | -250 |

**注意**: 推荐光环的精魄总消耗超过可用精魄，需要根据优先级取舍。

### 9E. 数据一致性检查

**⚠️ 以下项目需要人工确认：**

- Archmage 无明显 DPS 影响：可能因为构筑条件不满足或模拟环境限制

## 10. 总结与建议

当前 **Lightning Arrow** TotalDPS = **63,178**，AverageHit = 0，Speed = 2.64/s，CritChance = 7.8%，CritMultiplier = 2.00x。

### ⚔️ 进攻面

**DPS 灵敏度 Top 5**（所需投入越少 = 性价比越高）：

| # | 维度 | 类型 | 当前值 | 所需值 | 公式 |
|---|------|------|--------|--------|------|
| 1 | elemental_pen | BASE | 0 | +10% | 需要 +10% 穿透 → DPS +18.8% |
| 2 | lightning_pen | BASE | 0 | +12% | 需要 +12% 穿透 → DPS +21.5% |
| 3 | crit_chance_base | BASE | 0 | +14% | baseCrit 0.0%→13.5%, 需要 +13.5% → DPS +20.6% |
| 4 | attack_speed_inc | INC | 129 | +46% | INC 129%→174%, 需要 +46 → DPS +20.1% |
| 5 | flat_physical_attack | BASE | 0 | +74 | 需要添加 74-147 基础伤害 → DPS +20.1% |

*穿透维度均无影响（敌人抗性已为负值），面对高抗 Boss 时会成为有效优化方向。*

### 🛡️ 防御面

**最短板**: Physical（承伤仅为最强的 29%）

**防御性价比最高**: 法术格挡概率，需要 +32% 即可提升 EHP +20%

### 💧 资源与恢复

**⚠️ 精魄超载**: 占用 123%，需要缩减光环或精魄辅助

**恢复增强 Top 3**：

1. 魔力再生: BASE 27→33, 需要 +6 → 魔力恢复 +21.9%
2. 魔力恢复速率: INC 0%→37%, 需要 +37 → 魔力恢复 +20.3%

### 🌳 天赋

**推荐点出 Top 5**：

1. **Electric Amplification**: DPS +36.9%
2. **Exposed to the Storm**: DPS +32.3%
3. **Dimensional Weakspot**: DPS +28.2%
4. **Forces of Nature**: DPS +28.2%
5. **Storm Surge**: DPS +27.4%

**⚠️ 7 个无效天赋**: Gathering Winds, Light on your Feet, Momentum, Shimmering, Step Like Mist, Endless Munitions, Projectile Proximity Specialisation

### 💎 珠宝

**最佳**: Heart of the Well (DPS +9.5%, EHP -0.0%)
**可替换**: From Nothing
