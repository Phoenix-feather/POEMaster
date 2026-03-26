## ADDED Requirements

### Requirement: Defence sensitivity profiles
The system SHALL add ~14 defence-focused profiles to the `SENSITIVITY_PROFILES` dictionary, each targeting TotalEHP as the optimization metric. Each profile SHALL specify: `mod_name`, `mod_type`, `label`, `description`, `search_max`, and `unit`.

#### Scenario: Life INC profile
- **WHEN** `sensitivity_analysis(profiles=["life_inc"], target_stat="TotalEHP")` is called
- **THEN** the system SHALL inject `Life` INC modifier and binary-search for EHP impact per unit

#### Scenario: Fire resist profile
- **WHEN** `sensitivity_analysis(profiles=["fire_resist"], target_stat="TotalEHP")` is called
- **THEN** the system SHALL inject `FireResist` BASE modifier and report EHP gain per resist point

#### Scenario: Exclude fixed-source profiles
- **WHEN** defence sensitivity is run for a spell build
- **THEN** profiles that require attack flags SHALL be excluded (consistent with DPS sensitivity behavior)
