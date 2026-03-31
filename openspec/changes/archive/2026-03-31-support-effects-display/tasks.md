## 1. Data Bridge Methods

- [x] 1.1 Add `_parse_stat_name()` helper function to parse effect and condition from stat name
- [x] 1.2 Add `get_support_effects(support_id: str) -> list[dict]` method
- [x] 1.3 Add `get_support_by_name(name: str) -> str | None` method with fuzzy matching
- [x] 1.4 Add condition mapping table for common condition strings

## 2. Report Formatting

- [x] 2.1 Import `POEDataBridge` in `_format_section7()`
- [x] 2.2 Create bridge instance (with error handling)
- [x] 2.3 Loop through `sup_names` and map to IDs using `get_support_by_name()`
- [x] 2.4 Query effects using `get_support_effects()` for each support
- [x] 2.5 Format display: `**{name}**: {effect} (条件: {condition})`
- [x] 2.6 Handle lookup failures gracefully (fallback to name-only display)

## 3. Testing

- [x] 3.1 Test `get_support_effects()` with Dialla's Desire (no conditions)
- [x] 3.2 Test `get_support_effects()` with Uhtred's Omen (with condition)
- [x] 3.3 Test `get_support_by_name()` with exact match
- [x] 3.4 Test `get_support_by_name()` with fuzzy match (missing apostrophe)
- [x] 3.5 Test `get_support_by_name()` with non-existent name
- [x] 3.6 Run full analysis and verify report contains conditions
