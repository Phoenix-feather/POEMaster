## ADDED Requirements

### Requirement: Support effects query method
The system SHALL provide a method `get_support_effects(support_id: str) -> list[dict]` that returns a list of effects with conditions for a support gem.

#### Scenario: Query Dialla's Desire effects
- **WHEN** calling `get_support_effects("SupportDiallasDesirePlayer")`
- **THEN** returns:
  ```python
  [
    {"effect": "+1 level", "condition": None, "stat": "supported_active_skill_gem_level_+", "value": 1},
    {"effect": "+10% quality", "condition": None, "stat": "supported_active_skill_gem_quality_%", "value": 10}
  ]
  ```

#### Scenario: Query Uhtred's Omen effects
- **WHEN** calling `get_support_effects("SupportUhtredOmenPlayer")`
- **THEN** returns:
  ```python
  [
    {"effect": "+3 level", "condition": "1个其他辅助", "stat": "supported_active_skill_gem_level_+_if_one_other_support", "value": 3}
  ]
  ```

#### Scenario: Query non-existent support
- **WHEN** calling `get_support_effects("NonExistentSupport")`
- **THEN** returns empty list `[]`

### Requirement: Support name to ID mapping
The system SHALL provide a method `get_support_by_name(name: str) -> str | None` that maps support gem names to entity IDs.

#### Scenario: Map Dialla's Desire name to ID
- **WHEN** calling `get_support_by_name("Dialla's Desire")`
- **THEN** returns `"SupportDiallasDesirePlayer"`

#### Scenario: Map Uhtred's Omen name to ID
- **WHEN** calling `get_support_by_name("Uhtred's Omen")`
- **THEN** returns `"SupportUhtredOmenPlayer"`

#### Scenario: Fuzzy match with different formatting
- **WHEN** calling `get_support_by_name("Uhtreds Omen")` (no apostrophe)
- **THEN** returns `"SupportUhtredOmenPlayer"` (still matches)

#### Scenario: Non-existent support name
- **WHEN** calling `get_support_by_name("Non Existent Support")`
- **THEN** returns `None`

### Requirement: Condition parsing from stat names
The system SHALL parse condition information from stat names using pattern matching.

#### Scenario: Parse unconditional stat
- **WHEN** parsing `"supported_active_skill_gem_level_+"` with value `1`
- **THEN** returns `("1 level", None)`

#### Scenario: Parse conditional stat with "if_one_other_support"
- **WHEN** parsing `"supported_active_skill_gem_level_+_if_one_other_support"` with value `3`
- **THEN** returns `("+3 level", "1个其他辅助")`

#### Scenario: Parse conditional stat with "if_no_other_supports"
- **WHEN** parsing `"supported_active_skill_gem_level_+_if_no_other_supports"` with value `3`
- **THEN** returns `("+3 level", "无其他辅助")`

#### Scenario: Parse unknown condition format
- **WHEN** parsing `"supported_active_skill_gem_level_+_if_unknown_condition"` with value `1`
- **THEN** returns `("+1 level", "unknown condition")` (falls back to raw string)

### Requirement: Report display of support effects
The system SHALL display support gem effects and conditions in the collapsible details section of aura analysis.

#### Scenario: Display support with conditions
- **WHEN** generating report for Trinity with Dialla's Desire and Uhtred's Omen supports
- **THEN** the "辅助贡献" section shows:
  ```markdown
  - **Dialla's Desire**: +1 level, +10% quality
  - **Uhtred's Omen**: +3 level (条件: 1个其他辅助)
  ```

#### Scenario: Display support without conditions
- **WHEN** generating report for a support with no conditions
- **THEN** the support entry shows only the effect without condition clause

#### Scenario: Handle name lookup failure gracefully
- **WHEN** a support name cannot be mapped to an ID
- **THEN** the report still displays the support name (fallback to Lua-provided name)
