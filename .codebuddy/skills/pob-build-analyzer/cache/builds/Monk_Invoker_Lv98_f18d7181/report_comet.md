# Comet 构筑 DPS 优化报告

## 1. 基线概览

| 指标 | 数值 |
|------|------|
| 主技能 | Comet |
| 技能类型 | 法术 |
| TotalDPS | **27,060** |
| AverageHit | 42,524 |
| Speed | 0.64/s |
| CritChance | 42.4% |
| CritMultiplier | 4.00x |
| TotalEHP | 9,591 |

## 2. DPS 来源拆解

活跃伤害类型: Lightning, Cold, Fire

### 通用伤害 INC (Lightning,Cold,Fire) = 108%

**类别汇总**: Tree: +108.0

| 来源 | 类别 | 值 |
|------|------|-----|
| Potent Incantation | Tree | +30.0 |
| Triggered Spell Damage | Tree | +16.0 |
| Triggered Spell Damage | Tree | +14.0 |
| Triggered Spell Damage | Tree | +14.0 |
| Triggered Spell Damage | Tree | +14.0 |
| Triggered Spell Damage | Tree | +14.0 |
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

### 通用伤害 MORE (Lightning,Cold,Fire) = x 0.70

**类别汇总**: Skill: -30.0

| 来源 | 类别 | 值 |
|------|------|-----|
| Spell Cascade | Skill | -30.0 |

### Speed Base = 0.64/s

**类别汇总**: Skill: +0.6

| 来源 | 类别 | 值 |
|------|------|-----|
| Trigger Rate (computed) | Skill | +0.6 |

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

### CritChance BASE = 13.0% (base 13.0% + added 0%)

**类别汇总**: Skill: +13.0

| 来源 | 类别 | 值 |
|------|------|-----|
| 技能基础暴击率 | Skill | +13.0 |

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

### Cold → Lightning Conversion/Gain = Cold → Lightning: 增益 27.0%

**类别汇总**: Item: +17.0 | Tree: +10.0

| 来源 | 类别 | 值 |
|------|------|-----|
| Heart of the Well, Diamond (Jewel) | Item | +12.0 (Gain as Lightning) |
| I am the Thunder... | Tree | +10.0 (Gain as Lightning) |
| Adonia's Ego, Siphoning Wand (Weapon 1) | Item | +5.0 (Gain as Lightning) |

### Cold → Cold Self-Gain = Cold Self-Gain: 增益 15.0%

**类别汇总**: Tree: +10.0 | Item: +5.0

| 来源 | 类别 | 值 |
|------|------|-----|
| I am the Blizzard... | Tree | +10.0 (Gain as Cold) |
| Adonia's Ego, Siphoning Wand (Weapon 1) | Item | +5.0 (Gain as Cold) |

### Cold → Fire Conversion/Gain = Cold → Fire: 增益 63.0%

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

### Combined DPS = 42,524

**类别汇总**: Hit: +27060.4 | DOT: +545.2

| 来源 | 类别 | 值 |
|------|------|-----|
| Hit DPS | Hit | +27,060 |
| 点燃 DPS | DOT | +545.2 |

## 3. 灵敏度分析

### 有效维度（按性价比排序）

| # | 维度 | 类型 | 所需值 | 单位 | DPS/单位 | 当前值 | 公式 |
|---|------|------|--------|------|----------|--------|------|
| 1 | crit_chance_base | BASE | +4.5% | % | 3.83%/% | 0 | baseCrit 0.0%→4.5%, 需要 +4.5% → DPS +17.2% |
| 2 | crit_multi_base | BASE | +35.5% | % | 0.57%/% | 100 | CritBase 100→136, 需要 +36 → DPS +20.2% |
| 3 | damage_inc | INC | +63.5% | % | 0.32%/% | 219 | INC 219%→282%, 需要 +64 → DPS +20.2% |
| 4 | spell_damage_inc | INC | +63.5% | % | 0.32%/% | 219 | INC 219%→282%, 需要 +64 → DPS +20.2% |
| 5 | elemental_damage_inc | INC | +63.5% | % | 0.32%/% | 219 | INC 219%→282%, 需要 +64 → DPS +20.2% |
| 6 | crit_multi_inc | INC | +107.5% | % | 0.19%/% | 200 | INC 200%→308%, 需要 +108 → DPS +20.2% |
| 7 | cold_damage_inc | INC | +112.5% | % | 0.18%/% | 219 | INC 219%→332%, 需要 +112 → DPS +20.1% |
| 8 | crit_chance_inc | INC | +116.5% | % | 0.17%/% | 226 | INC 226%→342%, 需要 +116 → DPS +20.0% |
| 9 | speed_inc | INC | +148.5% | % | 0.14%/% | 75 | INC 75%→224%, 需要 +148 → DPS +20.1% |
| 10 | cast_speed_inc | INC | +148.5% | % | 0.14%/% | 75 | INC 75%→224%, 需要 +148 → DPS +20.1% |
| 11 | fire_damage_inc | INC | +205.0% | % | 0.10%/% | 209 | INC 209%→414%, 需要 +205 → DPS +20.0% |
| 12 | lightning_damage_inc | INC | +478.0% | % | 0.04%/% | 209 | INC 209%→687%, 需要 +478 → DPS +20.0% |

### 无影响维度

| 维度 | 类型 | 说明 |
|------|------|------|
| physical_damage_inc | INC | 物理伤害增加，仅对物理伤害生效 |
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
| 1 | All Natural | Notable | -9.5% | +0.0% | 进攻 |
| 2 | Potent Incantation | Notable | -8.6% | +0.0% | 进攻 |
| 3 | Throatseeker | Notable | -8.4% | +0.0% | 进攻 |
| 4 | Careful Assassin | Notable | -5.4% | +0.0% | 进攻 |
| 5 | I am the Blizzard... | Notable | -5.0% | +0.0% | 进攻 |
| 6 | I am the Thunder... | Notable | -4.8% | +0.0% | 进攻 |
| 7 | For the Jugular | Notable | -4.7% | -0.5% | 混合 |
| 8 | Critical Exploit | Notable | -4.3% | +0.0% | 进攻 |
| 9 | True Strike | Notable | -3.4% | +0.0% | 进攻 |
| 10 | Sudden Escalation | Notable | -2.7% | +0.0% | 进攻 |
| 11 | Moment of Truth | Notable | -2.6% | +0.0% | 进攻 |
| 12 | Deadly Force | Notable | -1.7% | +0.0% | 进攻 |
| 13 | Flow Like Water | Notable | -1.7% | -0.2% | 混合 |
| 14 | The Spring Hare | Notable | -1.3% | +0.0% | 进攻 |

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
| 1 | Endless Blizzard | Notable | +16.8% | +0.0% | 进攻 |
| 2 | Arcane Intensity | Notable | +14.3% | +0.0% | 进攻 |
| 3 | Invocated Efficiency | Notable | +12.7% | +0.0% | 进攻 |
| 4 | Sacrificial Blood | Notable | +12.7% | +0.0% | 进攻 |
| 5 | Cooked | Notable | +11.2% | -4.2% | 混合 |
| 6 | Ruin | Notable | +11.1% | +0.0% | 进攻 |
| 7 | Jack of all Trades | Notable | +10.8% | +0.0% | 进攻 |
| 8 | Master of Hexes | Notable | +10.0% | +0.0% | 进攻 |
| 9 | Lucky Rabbit Foot | Notable | +9.5% | +0.0% | 进攻 |
| 10 | Cower Before the First Ones | Notable | +9.5% | +0.0% | 进攻 |

*（另有 143 个候选天赋未显示）*

## 6. 珠宝诊断

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

### Rapture Shard (Sapphire, RARE)

- **DPS 贡献**: -4.8% | **状态**: ok | **槽位**: Jewel 61834

| Mod | 类型 | 值 | DPS% |
|-----|------|-----|------|
| EnergyShield | INC | 17 | +0.0% |
| ElementalDamage | INC | 15 | -4.8% |
| CurseActivation | INC | 14 | +0.0% |

### Chimeric Spark (Sapphire, RARE)

- **DPS 贡献**: -4.5% | **状态**: ok | **槽位**: Jewel 7960

| Mod | 类型 | 值 | DPS% |
|-----|------|-----|------|
| EnergyShield | INC | 15 | +0.0% |
| ElementalDamage | INC | 14 | -4.5% |
| CurseActivation | INC | 15 | +0.0% |

### Megalomaniac (Diamond, UNIQUE)

- **DPS 贡献**: -1.3% | **状态**: ok | **槽位**: Jewel 21984
- **分配天赋**: the spring hare, savoured blood (DPS -1.3%)

| Mod | 类型 | 值 | DPS% |
|-----|------|-----|------|
| GrantedPassive | LIST | the spring hare | -1.3% |
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
| 1 | Trinity | -25.9% | +0.0% | 100 | Total Resonance Count=0: +0.0%, Total Resonance Count=300: +77.8% |
| 2 | Charge Infusion | -18.1% ⚠️模拟 | -7.0% | 30 | - |
| 3 | Elemental Conflux | -16.7% ⚠️模拟 | +0.0% | 60 | - |
| 4 | Purity of Fire | +0.0% | +0.0% | 130 | - |

**⚠️模拟值说明：**

- **Charge Infusion**: 需启用 Frenzy/Power/Endurance Charge 配置才能生效，已模拟 3 个各类型 Charge
- **Elemental Conflux**: Lv20 给选中元素 59% MORE。主技能伤害构成：火 30.2% / 冰 56.9% / 电 12.9%，元素总占比 100.0%。期望收益 = 59% × 100.0% ÷ 3 ≈ 19.7% MORE

**DPS/EHP 影响未检测到** (1 个)：

这些光环可能提供非DPS收益（如生存/功能性），或其效果依赖动态条件（如Frenzy Charge）而POB未完全计算。

- **Purity of Fire**: 精魄 130

### 7B. 潜在光环推荐

**精魄不足但有效（释放精魄后考虑）：**

| # | 光环 | 精魄 | DPS% | 说明 |
|---|------|------|------|------|
| 1 | Archmage（大法师） | 100 | +28.7% | 精魄不足 (需 100, 缺 100) |

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

当前 **Comet** TotalDPS = **27,060**，AverageHit = 42,524，Speed = 0.64/s，CritChance = 42.4%，CritMultiplier = 4.00x。

### 🎯 最高性价比优化方向

1. **crit_chance_base** (BASE): 每 1% 提升 3.83% DPS，当前 0，需要 +4% 达到 +20% DPS
2. **crit_multi_base** (BASE): 每 1% 提升 0.57% DPS，当前 100，需要 +36% 达到 +20% DPS
3. **damage_inc** (INC): 每 1% 提升 0.32% DPS，当前 219，需要 +64% 达到 +20% DPS

### 🌳 推荐点出的天赋

1. **Endless Blizzard**: DPS +16.8%
2. **Arcane Intensity**: DPS +14.3%
3. **Invocated Efficiency**: DPS +12.7%
4. **Sacrificial Blood**: DPS +12.7%
5. **Cooked**: DPS +11.2%，EHP -4.2%

### ⚠️ 低效天赋

有 **22** 个已分配天赋对 DPS 和 EHP 均无可测量影响，可考虑重新规划路径或替换为高收益节点：

**Invocated Echoes**, **...and I Shall Rage**, **Impending Doom**, **Blood Transfusion**, **Thin Ice**, **Energise**, **Heavy Frost**, **Dynamism**, **Breaking Point**, **Marked Agility**
  …及其他 12 个

### 💎 珠宝建议

- 当前 DPS 贡献最高的珠宝: **Heart of the Well** (-5.8%)
- 无 DPS 贡献的珠宝: **Controlled Metamorphosis**，可考虑替换为伤害珠宝

### 🛡️ 敌人抗性说明

所有穿透维度均无影响 — 当前构筑配置下敌人抗性已为负值或零值，穿透无法进一步降低负抗。如果面对高抗性 Boss（抗性 > 0），穿透会成为有效优化维度。
