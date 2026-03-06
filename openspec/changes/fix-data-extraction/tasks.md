## 1. Blacklist Filter

- [ ] 1.1 Update `_should_skip_old_tree_data` to filter lua/, Classes/, Update/ directories
- [ ] 1.2 Fix TreeData version detection to be dynamic (remove hardcoded version list)
- [ ] 1.3 Test blacklist filtering with sample paths

## 2. ModCache Extraction

- [ ] 2.1 Add `mod_definition` to DataType enum
- [ ] 2.2 Create `_extract_mod_cache` method with correct regex pattern `c\s*\[\s*"([^"]+)"\s*\]\s*=\s*\{`
- [ ] 2.3 Implement brace-balancing for nested mod data extraction
- [ ] 2.4 Parse mod fields: type, name, value, flags, keywordFlags, globalLimit, globalLimitKey
- [ ] 2.5 Add `mod_definition` type fingerprint configuration
- [ ] 2.6 Update `_extract_entities` to handle `mod_definition` type

## 3. Entity Index Updates

- [ ] 3.1 Add `mod_data` column to entities table
- [ ] 3.2 Update `insert_entity` to store mod_definition data
- [ ] 3.3 Update `kb_query.py` to parse mod_data JSON field

## 4. Fix Existing Extraction

- [ ] 4.1 Fix `_extract_gems` to parse Gems.lua format correctly
- [ ] 4.2 Fix `_extract_minions` to extract stats, skills fields
- [ ] 4.3 Test gem_definition extraction with sample data
- [ ] 4.4 Test minion_definition extraction with sample data

## 5. Validation

- [ ] 5.1 Re-run init_knowledge_base.py with new extraction logic
- [ ] 5.2 Verify ModCache.lua extraction count (expected ~6254 entries)
- [ ] 5.3 Verify gem_definition has non-empty fields
- [ ] 5.4 Verify minion_definition has non-empty fields
- [ ] 5.5 Generate data coverage report
