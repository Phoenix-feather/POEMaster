## ADDED Requirements

### Requirement: Recovery sensitivity profiles
The system SHALL add ~8 recovery-focused profiles to `SENSITIVITY_PROFILES`. Each profile SHALL target a specific recovery output key (not an aggregated metric). Profiles SHALL include: `life_regen` (LifeRegen, BASE), `life_leech` (PhysicalLifeLeech, BASE), `life_recoup` (LifeRecoup, BASE), `life_recovery_rate` (LifeRecoveryRate, INC), `flask_effect` (FlaskEffect, INC), `mana_regen` (ManaRegen, BASE), `mana_leech` (PhysicalManaLeech, BASE), `mana_recovery_rate` (ManaRecoveryRate, INC).

#### Scenario: LifeLeech sensitivity
- **WHEN** recovery sensitivity is run with profile `life_leech`
- **THEN** the system SHALL inject PhysicalLifeLeech BASE modifier and report LifeLeech gain per unit

#### Scenario: Flask effect sensitivity
- **WHEN** recovery sensitivity is run with profile `flask_effect`
- **THEN** the system SHALL inject FlaskEffect INC modifier and report LifeRegenRecovery gain per unit
