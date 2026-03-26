## ADDED Requirements

### Requirement: Resistance balance check
The system SHALL compare each elemental resistance (Fire, Cold, Lightning, Chaos) against its max cap and report the gap. Status SHALL be: "capped" (at or above max), "near cap" (within 5% of max), "uncapped" (more than 5% below max). Overcapped resistances SHALL show the overcap amount.

#### Scenario: Lightning uncapped
- **WHEN** `LightningResist=72`, `LightningResistMax=76`
- **THEN** the system SHALL report Lightning as "uncapped" with a 4% gap

#### Scenario: Fire overcapped
- **WHEN** `FireResist=82`, `FireResistMax=76`
- **THEN** the system SHALL report Fire as "overcapped" with +6% excess

### Requirement: Redundancy detection
The system SHALL detect redundant allocations: passive nodes with zero DPS and EHP impact (< 0.1%), jewels with zero DPS and EHP contribution (< 0.1%), and auras with zero DPS and EHP contribution (< 0.1%).

#### Scenario: Zero-impact passive nodes
- **WHEN** 3 passive nodes have `dps_pct` and `ehp_pct` both below 0.1% in absolute value
- **THEN** the system SHALL list these nodes with their names as "redundant allocations"

#### Scenario: Zero-impact jewels
- **WHEN** a jewel has `dps_pct` and `ehp_pct` both below 0.1% in absolute value
- **THEN** the system SHALL flag it as potentially redundant
