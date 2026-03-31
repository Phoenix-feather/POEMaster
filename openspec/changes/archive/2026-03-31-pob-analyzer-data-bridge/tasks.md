## 1. Setup

- [x] 1.1 Create `pob_calc/data_bridge.py` module file
- [x] 1.2 Add database path resolution logic

## 2. Data Bridge Implementation

- [x] 2.1 Implement `POEDataBridge.__init__()` with database connection
- [x] 2.2 Implement `get_skill_stat_at_level()` method
- [x] 2.3 Implement `get_support_level_bonus()` method
- [x] 2.4 Implement `get_quality_speed_per_q()` method
- [x] 2.5 Implement `get_entity()` method
- [x] 2.6 Add error handling for missing database and invalid queries

## 3. what_if.py Integration

- [x] 3.1 Import `POEDataBridge` in `what_if.py`
- [x] 3.2 Create bridge instance in `aura_spirit_analysis()`
- [x] 3.3 Replace `_get_skill_stat_at_level()` Lua implementation with bridge call
- [x] 3.4 Replace `_get_support_level_bonus()` Lua implementation with bridge call
- [x] 3.5 Replace `_get_quality_speed_per_q()` Lua implementation with bridge call
- [x] 3.6 Remove the 3 deprecated Lua query functions
- [x] 3.7 Verify analysis output matches original

## 4. Report Format - Aura Table

- [x] 4.1 Modify `format_report()` to use collapsible format for aura table
- [x] 4.2 Create summary table with reduced columns
- [x] 4.3 Implement `<details>` block generation for each aura
- [x] 4.4 Add "条件参数范围" subsection formatting
- [x] 4.5 Add "辅助贡献" subsection formatting
- [x] 4.6 Add "基础数值" subsection formatting

## 5. Report Format - Other Tables

- [x] 5.1 Apply collapsible format to sensitivity analysis table
- [x] 5.2 Apply collapsible format to jewel diagnosis section

## 6. Testing & Validation

- [x] 6.1 Run full analysis on test build and compare output
- [x] 6.2 Verify all data preserved in new format
- [x] 6.3 Test report rendering in CodeBuddy preview
- [x] 6.4 Test report rendering in GitHub Markdown
- [x] 6.5 Update SKILL.md with new module documentation

## 7. Cleanup

- [x] 7.1 Remove any temporary test files
- [x] 7.2 Verify no lint errors
- [x] 7.3 Run final analysis and save report to cache
