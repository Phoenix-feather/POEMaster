## ADDED Requirements

### Requirement: Auto-generated executive summary
The system SHALL auto-generate a Part 0 executive summary containing: offence/defence/resource ratings (A/B/C/D scale), top 3-5 key findings, and top 5 optimization suggestions sorted by priority.

#### Scenario: Offence rating calculation
- **WHEN** a build has `TotalDPS=145230` and no DPS sensitivity profile shows "unreachable" status
- **THEN** the offence rating SHALL be A or B based on DPS magnitude relative to typical benchmarks

#### Scenario: Defence rating based on weakest link
- **WHEN** `TotalEHP=28400` but `ChaosMaximumHitTaken=2100` (lowest)
- **THEN** the defence rating SHALL reflect the weakest MaxHitTaken relative to total pool, likely C or D

#### Scenario: Key findings extraction
- **WHEN** chaos resistance is at -10% (weakest link) and 3 passive nodes are zero-impact
- **THEN** the key findings SHALL include "chaos is the weakest defence link" and "3 passive nodes have no measurable impact"

#### Scenario: Optimization suggestions from sensitivity
- **WHEN** defence sensitivity shows chaos_resist gives highest EHP gain per unit
- **THEN** the optimization suggestions SHALL include "increase chaos resistance" as a high-priority item

### Requirement: Dual-dimension upgrade for configuration analysis
The `diagnose_jewels()` function SHALL accept an `ehp_stat` parameter (default `"TotalEHP"`) and report both DPS and EHP impact for each jewel. The report format SHALL show dual columns for DPS% and EHP%.

#### Scenario: Jewel with high DPS but negative EHP
- **WHEN** a jewel contributes +6.3% DPS but -2.1% EHP (removing it increases EHP)
- **THEN** the report SHALL display both values and allow the user to evaluate the tradeoff
