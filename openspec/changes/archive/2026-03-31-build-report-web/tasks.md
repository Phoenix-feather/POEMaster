## 1. HTML Template & Infrastructure

- [x] 1.1 Create `report_generator.py` with `generate_html_report(build_id, skills)` function signature and basic CLI entry point
- [x] 1.2 Build HTML template skeleton: dark theme CSS variables, CDN imports (React, Recharts, Tailwind via esm.sh), dark background (#1a1a2e), light text, gold accent colors
- [x] 1.3 Implement JSON data embedding: read analysis JSON files, strip `sample_diff` fields, embed as `<script id="data">` block with all skills' data
- [x] 1.4 Implement meta.json reading for build info header (class, ascendancy, level, build_id)

## 2. Tab Navigation & Layout

- [x] 2.1 Build React tab component: tab bar with skill names, active tab state, click handler to switch
- [x] 2.2 Build KPI summary cards row: TotalDPS, AverageHit, Speed, CritChance, TotalEHP, Life (with comma formatting for >1000)
- [x] 2.3 Build responsive grid layout: 2-column chart grid, full-width collapsible tables below

## 3. Charts — DPS Analysis

- [x] 3.1 Implement DPS waterfall chart: parse `dps_breakdown.formula_items` into cumulative stages (Base → INC → MORE → Speed → CritEffect → LuckyHits → ConvGain → Final), render as custom ComposedChart with stacked/invisible bars
- [x] 3.2 Implement source category stacked bar chart: extract `category_summary` from each formula item, render BarChart with stacked segments colored by category (Tree/Item/Skill/Base/Jewel), add legend
- [x] 3.3 Implement sensitivity ranking horizontal bar chart: sort `sensitivity` by `needed_value` ascending, render BarChart (layout=vertical), add hover tooltip with `formula` and `dps_per_unit`

## 4. Charts — Aura Analysis

- [x] 4.1 Implement aura DPS gain line chart: for each aura with `config_ranges`, render two lines (bare_dps_pct and dps_pct) across parameter range (0 to actual_max), with linear interpolation between endpoints
- [x] 4.2 Implement Resonance slider: add `<input type="range">` below the line chart, sync with vertical marker line, display interpolated values and support contribution at slider position
- [x] 4.3 Handle aura without config_ranges: show static DPS contribution value without interactive chart

## 5. Charts — Talent & Defence

- [x] 5.1 Implement talent value scatter chart: plot `talent_value` entries as points (x=dps_pct, y=ehp_pct), color by category (进攻=red, 防御=blue, 混合=purple, 无效=gray), add hover tooltip with name/type
- [x] 5.2 Implement defence radar chart: extract Life, EnergyShield, MeleeEvasion, ArmourDefense, TotalEHP from baseline, normalize to 0-100% scale, render as custom SVG radar with labeled axes

## 6. Collapsible Detail Tables

- [x] 6.1 Implement talent value detail table: columns (Name, Type, DPS%, EHP%, Category), wrapped in `<details>` element
- [x] 6.2 Implement sensitivity detail table: columns (Label, Type, Needed Value, DPS/Unit, Formula), wrapped in `<details>` element
- [x] 6.3 Implement talent exploration table: columns (Name, Type, DPS%, EHP%), wrapped in `<details>` element
- [x] 6.4 Implement jewel diagnosis table: columns (Name, Slot, DPS%, Status), wrapped in `<details>` element

## 7. Integration & Testing

- [x] 7.1 Run `generate_html_report()` for Monk_Invoker build with Spark skill, verify HTML output
- [x] 7.2 Open HTML in CodeBuddy `preview_url()`, verify all 6 charts render correctly
- [x] 7.3 Verify tab switching, collapsible sections, and Resonance slider interaction
- [x] 7.4 Verify dark theme styling and number formatting
- [x] 7.5 Run multi-skill generation (Spark + Comet), verify tab navigation between skills
