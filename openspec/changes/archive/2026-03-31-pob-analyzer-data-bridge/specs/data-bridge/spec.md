## ADDED Requirements

### Requirement: Data bridge module exists
The system SHALL provide a `POEDataBridge` class in `pob_calc/data_bridge.py` that encapsulates all queries to `poe-data-miner/knowledge_base/entities.db`.

#### Scenario: Module import
- **WHEN** importing `from pob_calc.data_bridge import POEDataBridge`
- **THEN** the class is available without error

### Requirement: Skill stat at level query
The system SHALL provide a method `get_skill_stat_at_level(skill_id: str, level: int, stat_index: int = 0) -> float` that returns the stat value at a specific level.

#### Scenario: Query Trinity MORE value at level 20
- **WHEN** calling `get_skill_stat_at_level("TrinityPlayer", 20, 0)`
- **THEN** returns `6.0` (6% MORE per 50 resonance)

#### Scenario: Query Trinity MORE value at level 23
- **WHEN** calling `get_skill_stat_at_level("TrinityPlayer", 23, 0)`
- **THEN** returns `7.0` (7% MORE per 50 resonance)

#### Scenario: Query non-existent skill
- **WHEN** calling `get_skill_stat_at_level("NonExistentSkill", 20, 0)`
- **THEN** returns `0.0`

### Requirement: Support level bonus query
The system SHALL provide a method `get_support_level_bonus(support_id: str) -> int` that returns the level bonus provided by a support gem.

#### Scenario: Query Dialla's Desire level bonus
- **WHEN** calling `get_support_level_bonus("SupportDiallasDesirePlayer")`
- **THEN** returns `1` (+1 level)

#### Scenario: Query Uhtred's Omen level bonus
- **WHEN** calling `get_support_level_bonus("SupportUhtredOmenPlayer")`
- **THEN** returns `3` (+3 level when one other support)

#### Scenario: Query non-support skill
- **WHEN** calling `get_support_level_bonus("TrinityPlayer")`
- **THEN** returns `0`

### Requirement: Quality speed query
The system SHALL provide a method `get_quality_speed_per_q(skill_id: str) -> float` that returns the speed INC per quality point.

#### Scenario: Query Trinity quality speed
- **WHEN** calling `get_quality_speed_per_q("TrinityPlayer")`
- **THEN** returns `0.75` (0.75% speed INC per quality)

#### Scenario: Query skill without quality speed
- **WHEN** calling `get_quality_speed_per_q("SparkPlayer")`
- **THEN** returns `0.0`

### Requirement: Entity query
The system SHALL provide a method `get_entity(entity_id: str) -> dict | None` that returns the full entity data.

#### Scenario: Query Trinity entity
- **WHEN** calling `get_entity("TrinityPlayer")`
- **THEN** returns a dict with keys `id`, `name`, `type`, `stat_sets`, `quality_stats`, etc.

#### Scenario: Query non-existent entity
- **WHEN** calling `get_entity("NonExistentSkill")`
- **THEN** returns `None`

### Requirement: Database path resolution
The system SHALL automatically resolve the database path relative to the module location, without requiring environment variables or configuration.

#### Scenario: Default path resolution
- **WHEN** creating `POEDataBridge()`
- **THEN** the instance connects to `../poe-data-miner/knowledge_base/entities.db` relative to `pob_calc/` directory

#### Scenario: Database not found
- **WHEN** the database file does not exist
- **THEN** the constructor raises `FileNotFoundError` with a helpful error message

### Requirement: what_if.py integration
The system SHALL use `POEDataBridge` instead of Lua queries for all data lookups in `what_if.py`.

#### Scenario: No Lua query functions remain
- **WHEN** inspecting `what_if.py`
- **THEN** the following functions do NOT exist:
  - `_get_skill_stat_at_level`
  - `_get_support_level_bonus`
  - `_get_quality_speed_per_q`

#### Scenario: aura_spirit_analysis uses POEDataBridge
- **WHEN** running `full_analysis()`
- **THEN** the `aura_spirit_analysis()` step uses `POEDataBridge` for data queries
