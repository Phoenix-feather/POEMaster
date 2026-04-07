## ADDED Requirements

### Requirement: Self-contained HTML generation
The system SHALL provide a `generate_html_report()` function in `report_generator.py` that reads analysis JSON files from a build cache directory and produces a single self-contained HTML file with all data embedded.

#### Scenario: Generate report for single skill
- **WHEN** calling `generate_html_report(build_id="Monk_Invoker_Lv98_f18d7181", skills=["spark"])`
- **THEN** the system reads `cache/builds/{build_id}/analysis_spark.json` and `meta.json`
- **AND** outputs a single HTML file to `cache/builds/{build_id}/report.html`
- **AND** the HTML file contains all analysis data as an embedded JSON `<script>` block
- **AND** the HTML file renders correctly when opened directly in a browser (no server required)

#### Scenario: Generate report for multiple skills
- **WHEN** calling `generate_html_report(build_id="...", skills=["spark", "comet", "frost_bomb"])`
- **THEN** the system reads all corresponding `analysis_{skill}.json` files
- **AND** the HTML file contains a tab for each skill with its own complete analysis

#### Scenario: Missing analysis file
- **WHEN** a specified skill's `analysis_{skill}.json` does not exist
- **THEN** the system skips that skill and logs a warning
- **AND** the remaining skills are still rendered

### Requirement: Multi-skill tab navigation
The system SHALL render a tab bar at the top of the page with one tab per analyzed skill.

#### Scenario: Tab switching
- **WHEN** the user clicks on a skill tab (e.g., "Comet")
- **THEN** the page switches to display that skill's analysis (charts, KPI cards, tables)
- **AND** the previous skill's state is preserved for switching back

#### Scenario: Default tab
- **WHEN** the page first loads
- **THEN** the first skill tab is active by default

#### Scenario: Active tab indicator
- **WHEN** viewing the tab bar
- **THEN** the active tab has a distinct visual style (highlighted border/background)

### Requirement: KPI summary cards
The system SHALL display a row of KPI cards at the top of each skill's analysis, showing TotalDPS, AverageHit, Speed, CritChance, TotalEHP, Life, and Spirit cost.

#### Scenario: KPI card values
- **WHEN** viewing the Spark skill tab
- **THEN** the KPI row shows cards with labels and values from `baseline` data (e.g., TotalDPS: 11,661, TotalEHP: 9,591)

#### Scenario: Large number formatting
- **WHEN** a KPI value exceeds 1,000
- **THEN** the number is displayed with comma separators (e.g., "11,661" not "11661")

### Requirement: DPS multiplier waterfall chart
The system SHALL render a waterfall chart showing how DPS builds up through each multiplier stage: Base → INC → MORE → Speed → CritEffect → LuckyHits → Conversion/Gain → Final DPS.

#### Scenario: Waterfall chart data
- **WHEN** the waterfall chart is rendered
- **THEN** it reads `dps_breakdown.formula_items` to extract multiplier values
- **AND** calculates cumulative DPS at each stage using the DPS formula
- **AND** displays horizontal bars showing incremental and cumulative values

#### Scenario: Hover tooltip
- **WHEN** the user hovers over a bar in the waterfall chart
- **THEN** a tooltip shows the multiplier name, value, and the formula items contributing to that stage

### Requirement: Source category stacked bar chart
The system SHALL render a stacked bar chart showing the breakdown of DPS sources by category (Tree/Item/Skill/Base/Jewel) for each major multiplier.

#### Scenario: Stacked bar data
- **WHEN** the chart is rendered
- **THEN** each bar represents one multiplier (INC, Speed INC, CritChance INC, etc.)
- **AND** each bar is segmented by source category using `category_summary` from each formula item

#### Scenario: Legend
- **WHEN** the chart is displayed
- **THEN** a legend maps colors to source categories (Tree, Item, Skill, Base, Jewel)

### Requirement: Sensitivity ranking horizontal bar chart
The system SHALL render a horizontal bar chart ranking optimization levers by `needed_value` (ascending = highest ROI first).

#### Scenario: Bar chart ordering
- **WHEN** the chart is rendered
- **THEN** bars are sorted by `needed_value` ascending (smallest on top)
- **AND** each bar shows the lever label and needed value

#### Scenario: Hover tooltip
- **WHEN** the user hovers over a bar
- **THEN** a tooltip shows the `formula` string and `dps_per_unit` value

### Requirement: Aura DPS gain interactive chart
The system SHALL render a line chart showing aura DPS gain as a function of configurable parameters (e.g., Resonance Count), with a draggable slider for L1 interaction.

#### Scenario: Line chart with slider
- **WHEN** viewing the aura analysis section for Trinity
- **THEN** the chart displays two lines: bare aura DPS% and real DPS% (with supports)
- **AND** a range slider below the chart allows adjusting the parameter value (e.g., Resonance 0-300)
- **AND** a vertical marker line on the chart moves with the slider position

#### Scenario: Slider interaction updates display
- **WHEN** the user drags the Resonance slider to a new position
- **THEN** the interpolated DPS values at that position update in real-time below the chart
- **AND** the support contribution (difference between lines) at that position is calculated and displayed

#### Scenario: Interpolation from endpoints
- **WHEN** only two endpoint values exist (min=0 and max=300)
- **THEN** the chart renders a straight line between them (linear interpolation)

#### Scenario: Aura without config ranges
- **WHEN** an aura has no `config_ranges` data
- **THEN** the interactive chart is not shown, only the static DPS contribution value

### Requirement: Talent value scatter chart
The system SHALL render a scatter/bubble chart plotting each allocated notable/keystone by DPS% impact (x-axis) and EHP% impact (y-axis).

#### Scenario: Scatter chart data
- **WHEN** the chart is rendered
- **THEN** each point represents one talent from `talent_value` array
- **AND** x-axis = `dps_pct`, y-axis = `ehp_pct`
- **AND** points are colored by `category` (进攻/防御/混合/无效)

#### Scenario: Hover tooltip
- **WHEN** the user hovers over a point
- **THEN** the tooltip shows talent name, type, DPS%, and EHP%

### Requirement: Defence radar chart
The system SHALL render a radar/spider chart showing key defensive stats (Life, ES, Evasion, Armour, TotalEHP, resistances).

#### Scenario: Radar chart data
- **WHEN** the chart is rendered
- **THEN** it reads defensive values from `baseline` (Life, EnergyShield, MeleeEvasion, ArmourDefense, TotalEHP, resistances)
- **AND** normalizes values to a common scale (0-100%) relative to reasonable maximums

### Requirement: Collapsible detail tables
The system SHALL render collapsible sections for: talent value details, sensitivity details, talent exploration, and jewel diagnosis.

#### Scenario: Collapsible sections
- **WHEN** the page displays detail tables
- **THEN** each section is wrapped in a `<details>` element with a clickable header
- **AND** clicking the header toggles visibility of the table content

#### Scenario: Talent value table
- **WHEN** the talent value detail section is expanded
- **THEN** it displays a table with columns: Name, Type, DPS%, EHP%, Category

#### Scenario: Sensitivity detail table
- **WHEN** the sensitivity detail section is expanded
- **THEN** it displays a table with columns: Label, Type, Needed Value, DPS/Unit, Formula

#### Scenario: Jewel diagnosis table
- **WHEN** the jewel diagnosis section is expanded
- **THEN** it displays a table with columns: Name, Slot, DPS%, Status, Granted Passives

### Requirement: Dark theme styling
The system SHALL use a dark theme consistent with Path of Exile visual style (dark gray backgrounds, gold/amber accents).

#### Scenario: Color scheme
- **WHEN** the HTML report is rendered
- **THEN** the background color is dark gray (#1a1a2e or similar)
- **AND** text is light colored (white/light gray)
- **AND** accent colors use gold/amber tones for highlights
- **AND** chart colors use a distinct palette for each data series

### Requirement: Data size optimization
The system SHALL strip unnecessary data from analysis JSON before embedding in HTML to keep file size manageable.

#### Scenario: Strip sample_diff
- **WHEN** embedding analysis data
- **THEN** the `sample_diff` field from each sensitivity entry is removed (this field contains full diff dictionaries and is the largest data component)

#### Scenario: Keep essential fields
- **WHEN** embedding analysis data
- **THEN** all fields needed for chart rendering and table display are preserved (baseline, sensitivity key fields, talent_value, dps_breakdown, aura_spirit)
