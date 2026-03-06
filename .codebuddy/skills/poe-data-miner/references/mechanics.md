# POE Skill Mechanics Reference

## Meta Skills

Meta Skills are a special category of skills that generate Energy and trigger socketed skills.

### Energy Generation Types

| Skill | Trigger | Base Energy |
|-------|---------|-------------|
| Cast on Critical | Critical Hit | 100 centienergy/monster power |
| Cast on Block | Block | 2500 centienergy (25 energy) |
| Cast on Elemental Ailment | Freeze/Shock/Ignite | Scales with damage |
| Cast on Dodge | Dodge | Variable |
| Cast on Minion Death | Minion Death | Variable |

### Energy Formula

```
Energy = (HitDamage / AilmentThreshold) × BaseEnergy × (1 + IncBonus) × MoreMods
```

Where:
- **HitDamage**: Pre-mitigation hit damage
- **AilmentThreshold**: Threshold for the ailment type
- **BaseEnergy**: Base energy from skill (see table)
- **IncBonus**: Sum of all "increased" modifiers (additive)
- **MoreMods**: Product of "more/less" modifiers (multiplicative)

### Energy Scaling Sources

| Source | Effect |
|--------|--------|
| Skill Level | +3% energy_generated_+% per level |
| Boundless Energy I | +35% energy generated |
| Boundless Energy II | +45% energy generated |
| Passive Tree | +8%/+15%/+20%/+25%/+35% more energy |

---

## Triggered Spell Energy Restriction

### Default Behavior
Triggered spells (SkillType.Triggered) cannot generate energy for Meta Skills.

**Root Cause**: In `CalcActiveSkill.lua`, when a skill has `Triggered` type, the energy generation calculation returns 0.

```lua
-- Simplified logic
function calcEnergyGeneration(skill)
    if skill.skillTypes[SkillType.Triggered] then
        return 0  -- Blocked!
    end
    return baseEnergy * modifiers
end
```

### Exception: Doedre's Undoing

**How it works:**
1. Doedre's Undoing is a curse support gem
2. When you cast a curse, it creates a **Hazard zone** on the ground
3. When enemies enter the zone, it triggers an explosion
4. The explosion damage is **NOT** attributed to the trigger event
5. Therefore, the explosion can generate energy for Meta Skills

**Why this bypasses the restriction:**
- The trigger source is the Hazard zone (environmental), not the skill itself
- Damage is attributed to the player's action (creating the zone), not a response
- This differs from response-based triggers like Mana Flare

**Works with:**
- Cast on Critical (暴击释放)
- Cast on Elemental Ailment (异常释放)

**Does NOT work with:**
- Mana Flare (responds to mana spent)
- Elemental Discharge (responds to elemental buildup)
- Other response-based triggers

### Key Distinction: Trigger Source

| Trigger Type | Source | Damage Attribution | Energy Generation |
|--------------|--------|-------------------|-------------------|
| Hazard Zone | Environmental | Player action | ✓ Allowed |
| Skill Event | Skill response | Trigger response | ✗ Blocked |

---

## Stat Modifiers

### Common Stats

| Stat | Description |
|------|-------------|
| `energy_generated_+%` | Increased energy generation |
| `base_reservation_efficiency_+%` | Reservation efficiency |
| `cast_on_crit_gain_X_centienergy_per_monster_power_on_crit` | Base energy per power |
| `cast_on_block_gain_X_centienergy_on_block` | Block energy |
| `spirit_reservation_flat` | Flat spirit reservation |

### Stat Location

Stats are defined in:
- `constantStats`: Fixed values (always active)
- `stats`: Scaled values (per level, with interpolation)

### Stat Interpolation

```lua
levels = {
    [1] = { value, statInterpolation = { 1 }, actorLevel = 1 },
    [20] = { value, statInterpolation = { 1 }, actorLevel = 97.7 },
}
```

Interpolation types:
- `1`: Linear interpolation
- `2`: Exponential interpolation
- `3`: Polynomial interpolation

---

## Skill Types Reference

| Type | Description | Usage |
|------|-------------|-------|
| Meta | Meta skill container | Identifies meta skills |
| GeneratesEnergy | Can generate energy | Energy generation check |
| Triggers | Triggers socketed skills | Trigger behavior |
| HasReservation | Reserves spirit/mana | Reservation check |
| OngoingSkill | Persistent buff/debuff | Duration tracking |
| Persistent | Remains active | State management |
| Buff | Applies buff to player | Buff system |
| Invocation | Manual activation skill | Activation type |
| Triggered | Triggered by another skill | **Energy restriction** |
| Triggerable | Can be triggered | Trigger eligibility |
| Attack | Attack skill | Hit calculation |
| Spell | Spell skill | Hit calculation |
| Projectile | Projectile-based | Projectile behavior |
| Area | Area of effect | AoE calculation |
| Duration | Has duration | Duration scaling |
| Cooldown | Has cooldown | Cooldown management |

---

## Level Scaling

Skills scale with level based on:
1. Stat interpolation (defined per level)
2. Quality bonuses
3. Gem level requirements

Example level structure:
```lua
levels = {
    [1] = { levelRequirement = 0, spiritReservationFlat = 100 },
    [20] = { levelRequirement = 90, spiritReservationFlat = 100 }
}
```

### Level Requirements

```lua
-- Gem requirements
reqStr = 0
reqDex = 0
reqInt = 100
```

---

## Reservation

### Spirit Reservation
Meta Skills reserve Spirit (new POE2 resource):
- Typical flat reservation: 100 Spirit
- Modified by Reservation Efficiency

### Reservation Efficiency
- Base: 100%
- Increased efficiency reduces reservation
- Formula: `ActualReservation = BaseReservation × (100 / (100 + Efficiency))`

Example:
```
Base: 100 Spirit
Efficiency: +50%
Actual: 100 × (100 / 150) = 66.67 Spirit
```

---

## Damage Attribution

### Understanding Damage Attribution

When damage is dealt, it must be attributed to a source:

1. **Direct Skill Damage**: Attributed to the skill that dealt it
   - Example: Fireball hit → Fireball skill
   
2. **Triggered Damage**: Attributed to the triggering skill
   - Example: Cast on Critical trigger → Triggered skill (gets `Triggered` type)
   
3. **Hazard Damage**: Attributed to player action, not skill response
   - Example: Doedre's Undoing explosion → Player (no `Triggered` type)

### Why This Matters for Energy

```
┌─────────────────────────────────────────────────────────────────┐
│ Damage Attribution Flow                                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Player Casts Curse (with Doedre's Undoing)                    │
│       │                                                         │
│       ▼                                                         │
│  Creates Hazard Zone (environmental entity)                    │
│       │                                                         │
│       ▼                                                         │
│  Enemy enters zone                                              │
│       │                                                         │
│       ▼                                                         │
│  Explosion triggers                                             │
│       │                                                         │
│       ├──────────────────────────────────────────────┐          │
│       │                                              │          │
│       ▼                                              ▼          │
│  Damage Source: Hazard Zone        Damage Source: Triggered Skill │
│  Attribution: Player action        Attribution: Trigger response  │
│  Energy: ✓ Can generate            Energy: ✗ Cannot generate     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Calculation Code Reference

### Key Files

| File | Purpose |
|------|---------|
| `Modules/CalcActiveSkill.lua` | Active skill calculations |
| `Modules/CalcDefence.lua` | Defense calculations |
| `Modules/CalcOffence.lua` | Offence calculations |
| `Data/SkillStatMap.lua` | Stat to modifier mappings |

### Common Patterns

#### Energy Generation Check
```lua
-- In CalcActiveSkill.lua
if skill.skillTypes[SkillType.Triggered] then
    energy = 0
else
    energy = calcBaseEnergy(skill) * calcModifiers(skill)
end
```

#### Stat Application
```lua
-- In SkillStatMap.lua
["energy_generated_+%"] = {
    skill("EnergyGeneration", "INC", { mod = true }),
}
```

#### Modifier Calculation
```lua
-- INC modifiers: Additive
local total_inc = sum(all_inc_modifiers)

-- MORE modifiers: Multiplicative
local total_more = product(all_more_modifiers)

-- Final value
local result = base * (1 + total_inc/100) * total_more
```
