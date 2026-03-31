## ADDED Requirements

### Requirement: Support effects query method
The system SHALL provide a method `get_support_effects(support_id: str) -> list[dict]` that returns a list of effects with conditions for a support gem, parsed from the `constant_stats` field.

#### Scenario: Query Dialla's Desire effects
- **WHEN** calling `get_support_effects("SupportDiallasDesirePlayer")`
- **THEN** returns a list with two effects: +1 level (no condition) and +10% quality (no condition)

#### Scenario: Query Uhtred's Omen effects
- **WHEN** calling `get_support_effects("SupportUhtredOmenPlayer")`
- **THEN** returns a list with one effect: +3 level with condition "1个其他辅助"

#### Scenario: Query support without constant_stats
- **WHEN** calling `get_support_effects("SupportWithNoConstantStats")`
- **THEN** returns empty list `[]`

### Requirement: Support name to ID mapping method
The system SHALL provide a method `get_support_by_name(name: str) -> str | None` that maps support gem display names to entity IDs using fuzzy matching.

#### Scenario: Exact name match
- **WHEN** calling `get_support_by_name("Dialla's Desire")`
- **THEN** returns `"SupportDiallasDesirePlayer"`

#### Scenario: Fuzzy name match
- **WHEN** calling `get_support_by_name("Uhtreds Omen")` (no apostrophe)
- **THEN** returns `"SupportUhtredOmenPlayer"` via LIKE pattern matching

#### Scenario: Non-existent name
- **WHEN** calling `get_support_by_name("Non Existent Support")`
- **THEN** returns `None`
