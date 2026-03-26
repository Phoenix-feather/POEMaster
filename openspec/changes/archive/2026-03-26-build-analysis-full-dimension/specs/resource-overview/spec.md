## ADDED Requirements

### Requirement: Resource budget overview
The system SHALL display a resource budget table for Life, Mana, Spirit, and Energy Shield, showing: total amount, reserved amount, available amount, and utilization rate. Spirit budget SHALL show a breakdown of which auras/spirits consume it.

#### Scenario: Spirit budget tight
- **WHEN** `Spirit=300`, `SpiritUnreserved=50`
- **THEN** the resource overview SHALL show Spirit utilization at 83% with a warning indicator

#### Scenario: No Spirit reservation
- **WHEN** `Spirit=300`, `SpiritUnreserved=300`
- **THEN** the resource overview SHALL show Spirit utilization at 0% with no warning
