## ADDED Requirements

### Requirement: Aura table collapsible sections
The system SHALL format the aura analysis table (Section 9A) with collapsible detail sections for each aura, using HTML `<details>` elements.

#### Scenario: Trinity aura has collapsible details
- **WHEN** the report includes Trinity aura analysis
- **THEN** the output contains:
  - A summary table row with key metrics (name, DPS, EHP, spirit)
  - A `<details>` block with detailed information

#### Scenario: Details section structure
- **WHEN** an aura has detailed data (config ranges, support contributions, level info)
- **THEN** the `<details>` block contains:
  - `<summary>` with aura name
  - "条件参数范围" subsection (if applicable)
  - "辅助贡献" subsection (if supports contributed)
  - "基础数值" subsection (level, MORE per 30, quality speed)

### Requirement: Summary table columns
The system SHALL reduce the main summary table to essential columns only.

#### Scenario: Aura table columns
- **WHEN** generating the aura summary table
- **THEN** the columns are: `#`, `光环`, `裸光环 DPS`, `真实 DPS`, `EHP`, `精魄`
- **AND** the "条件参数范围" column is REMOVED from the main table

### Requirement: Details visible in collapsible blocks
The system SHALL ensure all detailed information previously in the "条件参数范围" column is now in collapsible blocks.

#### Scenario: Config range details in collapsible
- **WHEN** an aura has config ranges (e.g., Trinity Resonance 0-300)
- **THEN** the "条件参数范围" subsection in the details block shows:
  - A table with endpoint values
  - Speed INC changes (if applicable)
  - Marginal contribution calculations

#### Scenario: Support contribution details in collapsible
- **WHEN** an aura has support contributions
- **THEN** the "辅助贡献" subsection shows:
  - Each support name and its effect (e.g., "+1 等级")
  - Total support contribution percentage

#### Scenario: Level info details in collapsible
- **WHEN** an aura has level/skill data
- **THEN** the "基础数值" subsection shows:
  - Effective level (base + support bonus)
  - MORE per 30 resonance (for Trinity)
  - Speed INC per quality

### Requirement: Markdown compatibility
The system SHALL generate valid Markdown that renders correctly in standard Markdown viewers.

#### Scenario: GitHub Markdown rendering
- **WHEN** the report is viewed on GitHub
- **THEN** `<details>` blocks render as collapsible sections
- **AND** all content is readable

#### Scenario: CodeBuddy preview rendering
- **WHEN** the report is opened in CodeBuddy's built-in browser
- **THEN** `<details>` blocks render as collapsible sections

### Requirement: HTML extensibility
The system SHALL structure the Markdown output to be easily convertible to HTML.

#### Scenario: HTML conversion
- **WHEN** converting the report to HTML
- **THEN** `<details>` elements are preserved
- **AND** additional CSS/JS can be added for enhanced interactivity

### Requirement: Sensitivity table optimization
The system SHALL apply similar collapsible formatting to the sensitivity analysis table.

#### Scenario: Top results in main table
- **WHEN** generating sensitivity analysis
- **THEN** the main table shows Top 5-10 results
- **AND** a collapsible section contains the full list

### Requirement: Jewel diagnosis optimization
The system SHALL apply similar collapsible formatting to the jewel diagnosis section.

#### Scenario: Jewel summary in main table
- **WHEN** generating jewel diagnosis
- **THEN** the main table shows jewel names and DPS contribution
- **AND** a collapsible section per jewel shows mod details

### Requirement: Backward compatibility
The system SHALL preserve all data that was in the previous report format.

#### Scenario: No data loss
- **WHEN** comparing old and new report formats
- **THEN** all numerical data (DPS%, EHP%, spirit, etc.) is preserved
- **AND** all text descriptions are preserved
