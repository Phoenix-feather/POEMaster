## 1. Dynamic Discovery Implementation

- [x] 1.1 Implement `discover_spirit_supports(lua)` function
  - Scan `data.gems` for gems with `spiritReservationFlat > 0`
  - Filter by `grantedEffectId` containing "Support"
  - Extract `{name, skill_id, spirit, description}`
  - Add performance logging (target: <100ms)

- [x] 1.2 Implement `generate_support_description(gem_data)` function
  - Extract from `grantedEffect.description` or `statDescription`
  - Fallback to auto-generated: "SupportName: Effect summary"

## 2. Filtering and Merging

- [x] 2.1 Implement `filter_spirit_supports(candidates, is_attack, is_spell, skill_tags)` function
  - Build type filtering (attack vs spell)
  - Skill tag compatibility check
  - Condition-based filtering (e.g., Precision for attack-only)
  - Log filtered candidates for debugging

- [x] 2.2 Implement `merge_candidates(hardcoded, discovered)` function
  - Combine hardcoded and dynamic candidates
  - Deduplicate by `skill_id`
  - Prioritize hardcoded (better descriptions)
  - Return merged list

## 3. Integration with aura_spirit_analysis

- [x] 3.1 Modify `aura_spirit_analysis()` function
  - Call `discover_spirit_supports(lua)` at start
  - Merge with `_SPIRIT_SUPPORT_CANDIDATES`
  - Apply `filter_spirit_supports()` based on build type
  - Sort by spirit cost (prioritize low-cost for testing)

- [x] 3.2 Update testing loop
  - Test all merged and filtered candidates
  - Filter results by `dps_pct > 0.1%`
  - Sort by DPS impact (descending)
  - Take top 5 results

- [x] 3.3 Update report formatting
  - Display Top 5 in Section 7C
  - Show "无 DPS 影响" if no effective candidates
  - Add source annotation (hardcoded/dynamic)

## 4. Testing and Validation

- [x] 4.1 Test with spell build (e.g., Spark)
  - Verify dynamic discovery finds spell-relevant supports
  - Verify Precision is filtered out
  - Verify Top 5 contains spell-appropriate supports

- [ ] 4.2 Test with attack build (e.g., Ground Slam)
  - Verify Precision is included
  - Verify attack-relevant supports are discovered

- [x] 4.3 Performance testing
  - Measure scan time (target: <100ms)
  - Verify no regression in overall analysis time

- [ ] 4.4 Edge case testing
  - Empty candidate list
  - All candidates filtered out
  - More than 5 effective candidates

## 5. Documentation and Cleanup

- [x] 5.1 Update inline documentation
  - Add docstrings to new functions
  - Document filtering logic
  - Add examples in comments

- [x] 5.2 Update `_SPIRIT_SUPPORT_CANDIDATES` header comment
  - Explain hybrid approach
  - Reference dynamic discovery function

- [x] 5.3 Add debug logging
  - Log discovered candidates count
  - Log filtered candidates count
  - Log top 5 selection
