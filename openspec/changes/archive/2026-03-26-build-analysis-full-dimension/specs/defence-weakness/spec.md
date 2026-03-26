## ADDED Requirements

### Requirement: Defence weakness diagnosis
The system SHALL read the damage taken chain from baseline output for each of 5 damage types: Physical, Fire, Cold, Lightning, Chaos. For each type it SHALL read: resist, armour reduction, block chance, spell suppression, effective taken multiplier, and MaximumHitTaken. The weakest link SHALL be identified as the type with the lowest MaxHitTaken.

#### Scenario: Chaos is the weakest link
- **WHEN** `ChaosMaximumHitTaken=2100` is the minimum among all 5 MaxHitTaken values
- **THEN** the system SHALL mark Chaos as the weakest link and show its damage taken chain breakdown

#### Scenario: All MaxHitTaken similar
- **WHEN** all 5 MaxHitTaken values are within 10% of each other
- **THEN** the system SHALL note "balanced defence" without highlighting a specific weakest link

### Requirement: Damage taken chain breakdown
For each damage type, the system SHALL display the mitigation chain: resist% → armour reduction% → block% → spell suppression% → taken multiplier → MaxHitTaken.

#### Scenario: Physical damage chain
- **WHEN** a build has `PhysicalResist=75%`, `Armour=12400`, `BlockChance=45%`
- **THEN** the breakdown SHALL show each layer's contribution to the final MaxHitTaken
