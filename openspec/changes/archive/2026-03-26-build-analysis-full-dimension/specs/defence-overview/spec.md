## ADDED Requirements

### Requirement: Defence overview panel
The system SHALL read baseline output to build a defence overview panel containing: Pool composition (Life/ES/Mana/Ward), mitigation layers (Armour/Evasion/Block/SpellSuppression), 5 damage-type MaxHitTaken (Physical/Fire/Cold/Lightning/Chaos), resistance panel (current vs max for each element), and DotEHP for each damage type.

#### Scenario: Monk Invoker build
- **WHEN** a Monk Invoker build is analyzed and baseline output contains `Life=3245`, `ChaosResist=-10`, `ChaosMaximumHitTaken=2100`
- **THEN** the defence overview SHALL display Chaos as the weakest link with `MaxHitTaken=2100` highlighted

#### Scenario: Build with ES and Ward
- **WHEN** baseline output contains `EnergyShield=1200`, `Ward=500`
- **THEN** the Pool composition SHALL show all four pools with their values

#### Scenario: Resistances not capped
- **WHEN** baseline output contains `LightningResist=72`, `LightningResistMax=76`
- **THEN** the resistance panel SHALL show Lightning as uncapped with a gap of 4%

### Requirement: Defence sensitivity analysis
The system SHALL reuse the existing `sensitivity_analysis()` framework with ~14 defence profiles and `target_stat="TotalEHP"`. Profiles SHALL include: life_inc, life_flat, armour_inc, armour_flat, evasion_inc, evasion_flat, fire_resist, cold_resist, lightning_resist, chaos_resist, all_elemental_resist, block_chance, spell_block, damage_reduction.

#### Scenario: Chaos resistance most valuable
- **WHEN** a build has `ChaosResist=-10` and `TotalEHP=28400`
- **THEN** the chaos_resist profile SHALL show the highest EHP marginal gain per unit among all defence profiles

#### Scenario: Armour diminishing returns
- **WHEN** a build already has high armour (e.g. 50000)
- **THEN** the armour_inc profile SHALL show diminishing marginal EHP returns compared to resist profiles
