# Spark 构筑 DPS 优化报告

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

### 有效维度（按性价比排序）

| # | 维度 | 类型 | 所需值 | 单位 | DPS/单位 | 当前值 | 公式 |
|---|------|------|--------|------|----------|--------|------|
| 1 | crit_chance_base | BASE | +3.5% | % | 5.94%/% | 0 | baseCrit 0.0%→3.5%, 需要 +3.5% → DPS +20.8% |
| 2 | speed_inc | INC | +34.5% | % | 0.56%/% | 75 | INC 75%→110%, 需要 +34 → DPS +19.4% |
| 3 | cast_speed_inc | INC | +34.5% | % | 0.56%/% | 75 | INC 75%→110%, 需要 +34 → DPS +19.4% |
| 4 | crit_multi_base | BASE | +42.5% | % | 0.46%/% | 100 | CritBase 100→142, 需要 +42 → DPS +19.7% |
| 5 | damage_inc | INC | +48.0% | % | 0.42%/% | 137 | INC 137%→185%, 需要 +48 → DPS +20.2% |
| 6 | spell_damage_inc | INC | +48.0% | % | 0.42%/% | 137 | INC 137%→185%, 需要 +48 → DPS +20.2% |
| 7 | elemental_damage_inc | INC | +48.0% | % | 0.42%/% | 137 | INC 137%→185%, 需要 +48 → DPS +20.2% |
| 8 | projectile_damage_inc | INC | +48.0% | % | 0.42%/% | 137 | INC 137%→185%, 需要 +48 → DPS +20.2% |
| 9 | lightning_damage_inc | INC | +77.0% | % | 0.26%/% | 137 | INC 137%→214%, 需要 +77 → DPS +20.1% |
| 10 | crit_multi_inc | INC | +128.5% | % | 0.16%/% | 200 | INC 200%→328%, 需要 +128 → DPS +20.1% |
| 11 | crit_chance_inc | INC | +139.5% | % | 0.14%/% | 226 | INC 226%→366%, 需要 +140 → DPS +20.0% |
| 12 | fire_damage_inc | INC | +155.0% | % | 0.13%/% | 137 | INC 137%→292%, 需要 +155 → DPS +20.0% |

### 无影响维度

| 维度 | 类型 | 说明 |
|------|------|------|
| physical_damage_inc | INC | 物理伤害增加，仅对物理伤害生效 |
| cold_damage_inc | INC | 冰霜伤害增加 |
| chaos_damage_inc | INC | 混沌伤害增加 |
| lightning_pen | BASE | 闪电抗性穿透（敌人负抗时无效） |
| fire_pen | BASE | 火焰抗性穿透（敌人负抗时无效） |
| cold_pen | BASE | 冰霜抗性穿透（敌人负抗时无效） |
| elemental_pen | BASE | 元素抗性穿透（对火/冰/电都生效，敌人负抗时无效） |
| chaos_pen | BASE | 混沌抗性穿透（敌人负抗时无效） |
| projectile_count | BASE | 额外投射物数量（ProjectileCount没有INC类型） |
| aoe_inc | INC | 影响范围增加（对半径是平方根关系） |
| duration_inc | INC | 技能持续时间增加 |

## 4. 已分配天赋价值

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

## 5. 未分配天赋探索

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

## 6. 珠宝诊断

### Rapture Shard (Sapphire, RARE)

- **DPS 贡献**: -6.3% | **状态**: ok | **槽位**: Jewel 61834

| Mod | 类型 | 值 | DPS% |
|-----|------|-----|------|
| EnergyShield | INC | 17 | +0.0% |
| ElementalDamage | INC | 15 | -6.3% |
| CurseActivation | INC | 14 | +0.0% |

### Chimeric Spark (Sapphire, RARE)

- **DPS 贡献**: -5.9% | **状态**: ok | **槽位**: Jewel 7960

| Mod | 类型 | 值 | DPS% |
|-----|------|-----|------|
| EnergyShield | INC | 15 | +0.0% |
| ElementalDamage | INC | 14 | -5.9% |
| CurseActivation | INC | 15 | +0.0% |

### Heart of the Well (Diamond, UNIQUE)

- **DPS 贡献**: -5.8% | **状态**: ok | **槽位**: Jewel 32763

| Mod | 类型 | 值 | DPS% |
|-----|------|-----|------|
| DamageGainAsLightning | BASE | 12 | -5.8% |
| ManaOnKill | BASE | 1 | +0.0% |
| HybridManaAndLifeCost_Life | BASE | 3 | +0.0% |
| InstantEnergyShieldLeech | BASE | 15 | +0.0% |
| InstantManaLeech | BASE | 15 | +0.0% |
| InstantLifeLeech | BASE | 15 | +0.0% |

### Megalomaniac (Diamond, UNIQUE)

- **DPS 贡献**: -5.7% | **状态**: ok | **槽位**: Jewel 21984
- **分配天赋**: the spring hare, savoured blood (DPS -5.7%)

| Mod | 类型 | 值 | DPS% |
|-----|------|-----|------|
| GrantedPassive | LIST | the spring hare | -5.7% |
| GrantedPassive | LIST | savoured blood | +0.0% |

### Controlled Metamorphosis (Diamond, UNIQUE)

- **DPS 贡献**: +0.0% | **状态**: ok | **槽位**: Jewel 61419

| Mod | 类型 | 值 | DPS% |
|-----|------|-----|------|
| JewelData | LIST | (complex data) | +0.0% |
| JewelData | LIST | (complex data) | +0.0% |
| ElementalResist | BASE | -6 | +0.0% |

## 7. 光环与精魄分析

### 7A. 现有光环 DPS 贡献

| # | 光环 | DPS 贡献 | EHP 贡献 | 精魄消耗 | 条件参数范围 |
|---|------|----------|----------|----------|-------------|
| 1 | Trinity | -25.9% (条件: Total Resonance Count=150) | +0.0% | 100 | Total Resonance Count=0: +0.0%, Total Resonance Count=300: +93.3% |
| 2 | Charge Infusion | -23.5% ⚠️模拟 | -7.0% | 30 | - |
| 3 | Elemental Conflux | -16.7% ⚠️模拟 | +0.0% | 60 | - |
| 4 | Purity of Fire | +0.0% | +0.0% | 130 | - |

**⚠️模拟值说明：**

- **Charge Infusion** (Lv20): 需启用 Frenzy/Power/Endurance Charge 配置才能生效，已模拟 3 个各类型 Charge
- **Elemental Conflux**: Lv20 给选中元素 59% MORE。主技能伤害构成：火 30.6% / 冰 7.6% / 电 61.7%，元素总占比 100.0%。期望收益 = 59% × 100.0% ÷ 3 ≈ 19.7% MORE

**模拟方法说明：**

- **等级前提**：所有光环模拟均基于 Level 20 数据
- **DPS 贡献计算**：移除光环后 DPS 变化（分母=当前有光环 DPS）。条件光环需注入参数才能生效，默认注入参数最大值的 50%，标注在 DPS 贡献括号中
- **条件范围计算**：设置参数绝对值（0 和 max），对比「无光环」DPS，展示该光环在不同条件下的 DPS 贡献范围
- **期望收益计算**：对于 EC 等随机效果光环，期望 = 效果值 × 受影响技能元素占比之和 ÷ 3（因为随机选择火/冰/电之一）

**DPS/EHP 影响未检测到** (1 个)：

这些光环可能提供非DPS收益（如生存/功能性），或其效果依赖动态条件（如Frenzy Charge）而POB未完全计算。

- **Purity of Fire**: 精魄 130

### 7B. 潜在光环推荐

**精魄不足但有效（释放精魄后考虑）：**

| # | 光环 | 精魄 | DPS% | 说明 |
|---|------|------|------|------|
| 1 | Archmage（大法师） | 100 | +29.1% | 精魄不足 (需 100, 缺 100) |

**无 DPS 影响：**

- Attrition（损耗）
- Berserk（狂暴）

### 7C. 精魄辅助推荐

**无 DPS 影响：** 15 个组合

### 7D. 精魄预算

| 项目 | 精魄 |
|------|------|
| 总精魄 | 425 |
| 已用精魄 | 425 |
| 可用精魄 | 0 |

## 8. 总结与建议

当前 **Spark** TotalDPS = **11,661**，AverageHit = 4,664，Speed = 2.50/s，CritChance = 29.3%，CritMultiplier = 4.00x。

### 🎯 最高性价比优化方向

1. **crit_chance_base** (BASE): 每 1% 提升 5.94% DPS，当前 0，需要 +4% 达到 +20% DPS
2. **speed_inc** (INC): 每 1% 提升 0.56% DPS，当前 75，需要 +34% 达到 +20% DPS
3. **cast_speed_inc** (INC): 每 1% 提升 0.56% DPS，当前 75，需要 +34% 达到 +20% DPS

### 🌳 推荐点出的天赋

1. **Arcane Intensity**: DPS +18.9%
2. **Stand and Deliver**: DPS +17.4%
3. **Heavy Ammunition**: DPS +16.8%
4. **Sacrificial Blood**: DPS +16.8%
5. **Jack of all Trades**: DPS +14.3%

### ⚠️ 低效天赋

有 **22** 个已分配天赋对 DPS 和 EHP 均无可测量影响，可考虑重新规划路径或替换为高收益节点：

**Invocated Echoes**, **...and I Shall Rage**, **Impending Doom**, **Blood Transfusion**, **Thin Ice**, **Energise**, **Heavy Frost**, **Dynamism**, **Breaking Point**, **Marked Agility**
  …及其他 12 个

### 💎 珠宝建议

- 当前 DPS 贡献最高的珠宝: **Rapture Shard** (-6.3%)
- 无 DPS 贡献的珠宝: **Controlled Metamorphosis**，可考虑替换为伤害珠宝

### 🛡️ 敌人抗性说明

所有穿透维度均无影响 — 当前构筑配置下敌人抗性已为负值或零值，穿透无法进一步降低负抗。如果面对高抗性 Boss（抗性 > 0），穿透会成为有效优化维度。
