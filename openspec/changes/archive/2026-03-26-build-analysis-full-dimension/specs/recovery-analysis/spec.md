## ADDED Requirements

### Requirement: Life recovery composition
The system SHALL aggregate all life recovery sources from baseline output and display them sorted by contribution. Sources SHALL include: `LifeRegenRecovery`, `LifeLeech` + `LifeLeechInstantRate`, `LifeRecoup` + elemental Recoup, `LifeOnHitRate`, `LifeRecharge`. Each source SHALL show per-second value and percentage of total recovery.

#### Scenario: Leech is primary recovery
- **WHEN** `LifeLeech=120`, `LifeRegenRecovery=45`, `LifeRecoup=8.3`
- **THEN** the system SHALL show Leech as 69% of total recovery (173.3/s), Regen as 26%, Recoup as 5%

#### Scenario: Zero leech build
- **WHEN** `LifeLeech=0`, `LifeRegenRecovery=200`
- **THEN** the system SHALL show Regen as 100% of total recovery, Leech row shows 0/s

### Requirement: Leech detail display
For builds with LifeLeech > 0, the system SHALL display leech details: total leech per second, instant leech portion, max leech rate cap, current leech utilization rate, and leech instances (concurrent leech buffs).

#### Scenario: Leech below cap
- **WHEN** `LifeLeech=120`, `MaxLifeLeechRate=324`
- **THEN** the system SHALL show leech cap utilization at 37% and note room for improvement

### Requirement: Recoup detail display
For builds with LifeRecoup > 0, the system SHALL display recoup breakdown by damage type (PhysicalLifeRecoup, FireLifeRecoup, etc.).

#### Scenario: Mixed recoup sources
- **WHEN** `PhysicalLifeRecoup=1.2`, `FireLifeRecoup=2.8`, `ChaosLifeRecoup=4.3`
- **THEN** the system SHALL show each damage type's recoup contribution and highlight Chaos as the largest

### Requirement: Mana recovery composition
Same structure as life recovery, for Mana sources: `ManaRegenRecovery`, `ManaLeech`, `ManaRecoup`, `ManaOnHitRate`.

#### Scenario: Mana sustain through regen only
- **WHEN** `ManaRegenRecovery=12`, `ManaLeech=0`
- **THEN** the system SHALL show Regen as 100% of mana recovery
