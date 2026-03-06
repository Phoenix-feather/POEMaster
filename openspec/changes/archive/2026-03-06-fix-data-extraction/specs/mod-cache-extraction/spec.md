## ADDED Requirements

### Requirement: Extract ModCache.lua data
The system SHALL extract all entries from ModCache.lua, including simple mappings and mod data entries.

#### Scenario: Simple mapping extraction
- **WHEN** ModCache.lua contains `c["描述"] = {nil, "描述"}`
- **THEN** the system creates an entity with id="描述", type="mod_definition", mod_data=[]

#### Scenario: Mod data extraction
- **WHEN** ModCache.lua contains `c["描述"] = {{[1]={type="MORE", name="Damage", value=100}}, "描述"}`
- **THEN** the system creates an entity with mod_data containing the parsed mod information

#### Scenario: Multiple mods per entry
- **WHEN** ModCache.lua contains multiple mods in one entry
- **THEN** the system extracts all mods into the mod_data array

### Requirement: Parse mod data structure
The system SHALL parse the following mod data fields: type, name, value, flags, keywordFlags, globalLimit, globalLimitKey.

#### Scenario: Parse all mod fields
- **WHEN** mod data contains type="MORE", name="Damage", value=100, globalLimit=100
- **THEN** the system extracts all fields into a structured format

#### Scenario: Handle missing optional fields
- **WHEN** mod data only contains required fields (type, name)
- **THEN** the system successfully creates entity with optional fields set to None

### Requirement: Handle ModCache.lua format variations
The system SHALL handle the specific ModCache.lua format with `c["..."]` prefix.

#### Scenario: Match c["..."] prefix
- **WHEN** parsing ModCache.lua content
- **THEN** the regex matches `c\s*\[\s*"([^"]+)"\s*\]\s*=\s*\{` pattern

#### Scenario: Handle nested braces
- **WHEN** mod data contains nested `{...}` structures
- **THEN** the system uses brace-balancing algorithm to extract complete content
