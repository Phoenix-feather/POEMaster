## MODIFIED Requirements

### Requirement: Extract gem_definition entities
The system SHALL extract gem data from Gems.lua including skill_types, stats, and other relevant fields.

#### Scenario: Extract gem with skill association
- **WHEN** Gems.lua contains a gem entry with associated skill
- **THEN** the system extracts skill_types and stats from the gem

#### Scenario: Parse gem tags
- **WHEN** a gem has tags field
- **THEN** the system extracts tags as an array

### Requirement: Extract minion_definition entities
The system SHALL extract complete minion data from Minions.lua and Spectres.lua.

#### Scenario: Extract minion stats
- **WHEN** Minions.lua contains a minion with life, damage, armour fields
- **THEN** the system extracts all numeric stats

#### Scenario: Extract minion skills
- **WHEN** a minion has a skills array
- **THEN** the system extracts the skill list

#### Scenario: Extract spectre data
- **WHEN** Spectres.lua contains spectre definitions
- **THEN** the system extracts using same logic as Minions.lua
