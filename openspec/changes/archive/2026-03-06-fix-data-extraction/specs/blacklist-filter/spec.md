## ADDED Requirements

### Requirement: Filter non-game data directories
The system SHALL skip files in lua/, Classes/, and Update/ directories during scanning.

#### Scenario: Skip lua directory
- **WHEN** a file path contains `\lua\` or `/lua/`
- **THEN** the file is excluded from scanning

#### Scenario: Skip Classes directory
- **WHEN** a file path contains `\Classes\` or `/Classes/`
- **THEN** the file is excluded from scanning

#### Scenario: Skip Update directory
- **WHEN** a file path contains `\Update\` or `/Update/`
- **THEN** the file is excluded from scanning

#### Scenario: Keep game data directories
- **WHEN** a file is in Data/, Modules/, or TreeData/ directories
- **THEN** the file is included for scanning

### Requirement: Dynamic TreeData version detection
The system SHALL dynamically detect the latest TreeData version and only scan that version.

#### Scenario: Detect latest version
- **WHEN** TreeData contains versions 0_1, 0_2, 0_3, 0_4
- **THEN** the system identifies 0_4 as the latest version

#### Scenario: Skip old versions
- **WHEN** scanning TreeData directory
- **THEN** only tree.lua from the latest version is scanned

#### Scenario: Handle future versions
- **WHEN** a new version 0_5 is added
- **THEN** the system automatically detects it as the latest version without code changes
