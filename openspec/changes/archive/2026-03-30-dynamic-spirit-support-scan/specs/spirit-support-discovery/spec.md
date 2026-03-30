## ADDED Requirements

### Requirement: Dynamic spirit support discovery

The system SHALL dynamically discover all spirit support gems from POB's `data.gems` database during each analysis.

#### Scenario: Discover all spirit supports
- **WHEN** `aura_spirit_analysis()` is called
- **THEN** system scans `data.gems` for all gems with `spiritReservationFlat > 0` and `grantedEffectId` containing "Support"
- **AND** returns a list of candidates with `{name, skill_id, spirit, description}`

### Requirement: Hybrid candidate source

The system SHALL merge hardcoded and dynamically discovered spirit support candidates.

#### Scenario: Merge candidates with deduplication
- **WHEN** candidates are prepared for testing
- **THEN** system combines hardcoded candidates (with detailed annotations) and dynamic candidates
- **AND** removes duplicates based on `skill_id`
- **AND** prioritizes hardcoded candidates (they have better descriptions)

### Requirement: Intelligent filtering

The system SHALL filter spirit support candidates based on build characteristics.

#### Scenario: Filter by build type
- **WHEN** main skill is identified as spell (`is_spell=True, is_attack=False`)
- **THEN** system filters out attack-only supports (e.g., Precision)
- **AND** keeps spell-relevant and universal supports

#### Scenario: Filter by skill tags
- **WHEN** spirit support has incompatible `supportType` or `modTags` with main skill
- **THEN** system filters out the candidate
- **AND** logs the filtered candidate for debugging

### Requirement: Top 5 display

The system SHALL display only the top 5 most effective spirit support candidates.

#### Scenario: Display top 5 by DPS impact
- **WHEN** all candidates are tested
- **THEN** system filters results with `dps_pct > 0.1%`
- **AND** sorts by DPS impact (descending)
- **AND** displays only the top 5 results

#### Scenario: No effective candidates
- **WHEN** all tested candidates have `dps_pct <= 0.1%`
- **THEN** system displays "**无 DPS 影响：** N 个组合"
- **AND** logs full results for debugging

### Requirement: Real-time scanning

The system SHALL scan POB database in real-time during each analysis (no caching).

#### Scenario: Real-time scan on each analysis
- **WHEN** `aura_spirit_analysis()` is called multiple times
- **THEN** each call performs a fresh scan of `data.gems`
- **AND** scan completes within 200ms (target: <100ms)

### Requirement: Automatic description generation

The system SHALL automatically generate descriptions for dynamically discovered candidates.

#### Scenario: Extract description from POB
- **WHEN** a spirit support is discovered
- **THEN** system extracts description from `grantedEffect.description` or `statDescription`
- **AND** falls back to auto-generated description: "SupportName: Effect summary"
