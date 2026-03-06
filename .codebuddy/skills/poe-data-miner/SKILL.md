---
name: poe-data-miner
description: Extract and analyze Path of Exile game data from Lua and JSON files. Use when working with POB data, extracting skill/item information, analyzing skill mechanics, or calculating formulas from game data files.
---

# POE Data Miner

Extract and analyze Path of Exile game data from POB (Path of Building) files. Features intelligent Q&A, incremental learning, and knowledge persistence.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                      User Question                               │
└─────────────────────────┬───────────────────────────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Query Engine                                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ 1. Question Analyzer (intent, entities, constraints)        ││
│  │ 2. Query Mode Selection (entity/rule/graph)                 ││
│  │ 3. Result Integrator                                        ││
│  └─────────────────────────────────────────────────────────────┘│
└────────────┬─────────────────────────────────────┬──────────────┘
             │                                     │
    ┌────────▼────────┐                   ┌────────▼────────┐
    │  Entity Index   │                   │  Rules Library  │
    │  (SQLite)       │                   │  (SQLite)       │
    └────────┬────────┘                   └────────┬────────┘
             │                                     │
             └──────────────────┬──────────────────┘
                                ▼
             ┌─────────────────────────────────────┐
             │      Attribute Graph (SQLite)       │
             │  Nodes: Entity, Mechanism, Stat     │
             │  Edges: has_type, modifies, bypasses│
             └─────────────────────────────────────┘
                                │
             ┌──────────────────┼──────────────────┐
             ▼                  ▼                  ▼
      ┌────────────┐     ┌────────────┐     ┌────────────┐
      │ Predefined │     │ Knowledge  │     │ Extraction │
      │   Edges    │     │   Base     │     │ Patterns   │
      │  (config)  │     │ (learning) │     │  (config)  │
      └────────────┘     └────────────┘     └────────────┘
```

## Quick Start

### Query Knowledge Base (Recommended)
```bash
# 统计信息
python scripts/kb_query.py stats

# 实体查询
python scripts/kb_query.py entity --meta           # 所有元技能
python scripts/kb_query.py entity --search "Cast"  # 搜索
python scripts/kb_query.py entity MetaCastOnCritPlayer  # 详情

# 规则查询
python scripts/kb_query.py rule --formula      # 公式规则
python scripts/kb_query.py rule --constraint   # 约束规则
python scripts/kb_query.py rule --bypass       # 绕过规则

# 图查询
python scripts/kb_query.py graph --neighbors MetaCastOnCritPlayer
python scripts/kb_query.py graph --path source target
```

### Initialize Knowledge Base
```bash
python scripts/data_scanner.py <pob_data_dir> --output <cache_dir>
python scripts/entity_index.py <cache_dir> --db <knowledge_base>/entities.db
python scripts/rules_extractor.py <cache_dir> --db <knowledge_base>/rules.db
python scripts/attribute_graph.py <knowledge_base> --init
```

### Query Skills
```bash
python scripts/query_engine.py "Cast on Critical如何获得能量？" --kb <knowledge_base>
```

### Analyze Mechanics
```bash
python scripts/analyze_mechanics.py "Cast on Critical" --data <pob_data_dir>
```

## Data Sources

### Lua Files (POB Data)
POB stores game data in Lua format under directories like:
- `Data/Skills/act_*.lua` - Active skills by attribute
- `Data/Skills/sup_*.lua` - Support skills
- `Data/Uniques/*.lua` - Unique items
- `Data/Gems.lua` - Gem definitions
- `Data/SkillStatMap.lua` - Stat to modifier mappings
- `TreeData/{version}/tree.lua` - Passive tree data

### JSON Files
For structured data exports or API responses.

### Version-Specific Data
**IMPORTANT**: Only scan the LATEST version for versioned data:
- TreeData: Only scan `TreeData/{latest_version}/tree.lua`, ignore older versions
- The latest version is determined by semantic versioning (e.g., 0_4 > 0_3 > 0_2 > 0_1)
- This prevents duplicate/outdated data in knowledge base

## Core Modules

### 1. Data Scanner (`data_scanner.py`)
Scans and caches POB data files:
- Lua file traversal and content reading
- Data type identification (skills, stats, calculations)
- Version information extraction
- Scan result caching

### 2. Entity Index (`entity_index.py`)
SQLite-based entity storage:
- Entity data extraction and storage
- Query by ID, type, skillTypes
- Full-text search on names/descriptions

### 3. Rules Extractor (`rules_extractor.py`)
Multi-layer rule extraction:
- Layer 1: Entity-stats relationships
- Layer 2: Stat-mechanism mappings (SkillStatMap)
- Layer 3: Condition rules from calculation code

### 4. Attribute Graph (`attribute_graph.py`)
Graph-based knowledge representation:
- Nodes: Entity, Mechanism, Stat, Constraint
- Edges: has_type, has_stat, modifies, causes, blocks, bypasses
- Graph traversal queries (BFS/DFS with recursive CTE)

### 5. Query Engine (`query_engine.py`)
Intelligent question answering:
- Question analysis (intent, entities, constraints)
- Query mode selection (entity/rule/graph)
- Result integration

### 6. Knowledge Manager (`knowledge_manager.py`)
Incremental learning and recovery:
- Heuristic record management
- Pending confirmation workflow
- Version change detection
- Knowledge migration

## Configuration

### Predefined Edges (`config/predefined_edges.yaml`)
Knowledge that cannot be auto-extracted:
```yaml
edges:
  - source: "hazard_zone_explosion"
    target: "triggered_energy_limit"
    edge_type: "bypasses"
    reason: "Hazard damage not attributed to trigger event"
```

### Rule Templates (`config/rule_templates.yaml`)
Patterns for rule extraction:
```yaml
templates:
  - name: "energy_generation"
    conditions:
      - skillTypes.contains("GeneratesEnergy")
    effects:
      - creates_node("mechanism", "EnergyGeneration")
```

### Extraction Patterns (`config/extraction_patterns.yaml`)
Patterns for code analysis:
```yaml
patterns:
  - name: "triggered_check"
    code_pattern: "if skillTypes\\[Triggered\\]"
    extracts: "condition"
```

## Knowledge Base Structure

```
knowledge_base/
├── entities.db         # Entity index (SQLite)
├── rules.db            # Rules library (SQLite)
├── graph.db            # Attribute graph (SQLite)
├── heuristic_records.yaml    # Learned knowledge
├── pending_confirmations.yaml # User confirmations pending
├── unverified_list.yaml      # Needs re-verification
├── learning_log.yaml         # Learning event log
└── version.yaml              # Version tracking
```

## Query Workflow

### Example: "Doedre's Undoing如何绕过能量限制？"

```
1. Question Analysis:
   - Intent: "bypass"
   - Entities: ["Doedre's Undoing", "energy limit"]
   - Constraint: "Triggered skill restriction"

2. Entity Lookup:
   - Find "Doedre's Undoing" in entity index
   - Find related "Cast on Critical" meta skill

3. Rule Lookup:
   - Find rules about "Triggered" restriction
   - Find rules about energy generation limits

4. Graph Traversal:
   - Start from "Doedre's Undoing"
   - Find path: Doedre's Undoing → Hazard → bypasses → Triggered Limit
   - Check: Is path valid for Cast on Critical?

5. Result Integration:
   - Combine entity data + rules + graph path
   - Explain: Hazard explosion not attributed to trigger
   - Cite: Source code locations, stat definitions
```

## Common Patterns

### Find Meta Skills
```lua
-- Pattern in skillTypes
skillTypes = { [SkillType.Meta] = true, [SkillType.GeneratesEnergy] = true }
```

### Extract Stat Modifiers
```lua
-- In statSets
constantStats = {
    { "stat_name", value }
}
stats = { "energy_generated_+%" }
```

### Energy Formula
```
Energy = (HitDamage / AilmentThreshold) × BaseEnergy × (1 + ΣIncBonus) × ΠMoreMods
```

### Triggered Spell Restriction
```lua
-- In CalcActiveSkill.lua
if skillTypes[Triggered] then
    return 0  -- No energy for triggered spells
end

-- Exception: Hazard-based triggers (Doedre's Undoing)
-- Damage attributed to player action, not trigger response
```

## Scripts Reference

| Script | Purpose |
|--------|---------|
| `kb_query.py` | **Query tool (recommended)** - Query entities, rules, graph |
| `init_knowledge_base.py` | Initialize all databases |
| `data_scanner.py` | Scan and cache POB data files |
| `entity_index.py` | Build entity index database |
| `rules_extractor.py` | Extract rules from data |
| `attribute_graph.py` | Build and query attribute graph |
| `query_engine.py` | Answer questions about mechanics |
| `knowledge_manager.py` | Manage learning and recovery |

## References

- `references/mechanics.md` - POE skill mechanics and formulas
- `references/data_structures.md` - POB data structure documentation
- `knowledge_base/query_lessons.md` - **Query lessons learned (avoid failures)**

## Incremental Learning

The system learns from user interactions:

1. **Discovery**: When answering questions, the system may discover new relationships
2. **Confirmation**: Ask user to confirm uncertain discoveries
3. **Persistence**: Confirmed knowledge is saved to heuristic records
4. **Recovery**: On version updates, re-verify learned knowledge

### Learning Trigger Rules

**IMPORTANT**: During Q&A, actively detect learning opportunities and create pending confirmations.

#### When to Create Pending Confirmation

Create a pending confirmation item when ANY of these conditions are met:

1. **Uncertain Bypass Discovery**
   - Found a potential bypass mechanism not in knowledge base
   - Logic suggests it might work but needs validation
   - Example: "Corpse explosion might bypass Triggered limit"

2. **New Mechanism Relationship**
   - Discovered relationship between entities not in graph
   - Inferred from data but not explicitly recorded
   - Example: "Sacrifice allows Minions as Corpses"

3. **Knowledge Gap Detected**
   - User asks about something not in knowledge base
   - AI infers answer from related data
   - Example: "New skill interaction discovered"

4. **Contradiction Found**
   - Data suggests different conclusions
   - Need user to clarify correct interpretation
   - Example: "Stacking behavior unclear"

5. **Inferred New Knowledge** ★ IMPORTANT
   - AI successfully answers question through logical reasoning
   - The conclusion/insight is NOT already in knowledge base
   - Must check if knowledge base has this fact
   - Example: "Instant Leech bypasses Recovery Rate Cap"
   - Trigger: After explaining mechanism, check if conclusion is recorded

6. **Mechanism Abstraction Opportunity** ★ IMPORTANT
   - Multiple entities share similar effects/stats
   - The effect is NOT abstracted as independent mechanism node
   - Should propose creating mechanism node
   - Example: "Instant Leech" should be mechanism, not just Atziri's Acuity stat
   - Pattern: When multiple sources provide same effect → create mechanism node

#### Mechanism Identification Rules ★ CRITICAL

**NEVER use description text to identify mechanisms!**

Mechanisms must be identified by **stat ID** or **internal stat name**:

1. **Find Stat Mapping**
   - Search `ModCache.lua` for description → stat name mapping
   - Example: `"Leech from Critical Hits is instant"` → `InstantLifeLeech`
   - Use stat ID from `statOrder` field

2. **Use Internal Stat Names as Mechanism Identifiers**
   - `InstantLifeLeech` - 立即生命偷取
   - `InstantManaLeech` - 立即魔力偷取
   - `InstantEnergyShieldLeech` - 立即能量护盾偷取
   - `base_leech_is_instant_on_critical` - 暴击时立即偷取

3. **Find All Sources by Stat**
   - After identifying mechanism by stat name
   - Search all entities/mods that grant this stat
   - This gives authoritative list of sources

4. **Example: Instant Leech Discovery**
   ```
   WRONG: 搜索描述 "instant" → 不可靠
   
   RIGHT:
   1. Search ModCache.lua: "Leech from Critical Hits is instant"
   2. Found: name="InstantLifeLeech", statOrder=2208
   3. Mechanism ID: "InstantLifeLeech"
   4. Find sources: search all mods with InstantLifeLeech
   5. Result: Atziri's Acuity, and any other items with this stat
   ```

7. **Data Source Missing** ★ IMPORTANT
   - User mentions data that should exist but doesn't
   - Example: Ascendancy nodes, passive tree data
   - Should acknowledge gap and propose to scan missing data
   - Do NOT just create heuristic record → fix the data source

#### Confirmation Flow

When a learning opportunity is detected:

```
Step 1: Identify Discovery
─────────────────────────
• What was discovered?
• Why is it uncertain?
• What entities/mechanisms are involved?

Step 2: Create Pending Item
───────────────────────────
Call: knowledge_manager.create_pending_confirmation({
    'type': 'bypass' | 'mechanism' | 'relation',
    'question': 'Original user question',
    'answer': 'AI inferred answer',
    'confidence': 'low' | 'medium' | 'high',
    'key_entities': [...],
    'key_mechanisms': [...],
    'reason': 'Why this needs confirmation',
    'data_updates': [
        # What should be added if confirmed
        {'target': 'graph_edges', 'operation': 'insert', 'data': {...}}
    ]
})

Step 3: Ask User Confirmation
─────────────────────────────
Use ask_followup_question tool:
{
    "questions": [{
        "id": "confirm_discovery",
        "question": "Should I record this discovery? [discription]",
        "options": [
            "Yes, this is correct",
            "No, this is wrong",
            "Need more testing"
        ],
        "multiSelect": false
    }]
}

Step 4: Process Confirmation
────────────────────────────
If confirmed:
• Call knowledge_manager.confirm_discovery(item_id, True)
• Apply data_updates to knowledge base
• Log learning event

If rejected:
• Call knowledge_manager.confirm_discovery(item_id, False)
• Record rejection reason if provided
```

#### Example Learning Session

```
User asks: "尸体爆炸能绕过Triggered限制吗？"

AI Analysis:
───────────
1. Knowledge base query: No direct answer
2. Reasoning:
   - Detonate Dead explosion comes from corpse
   - Damage might be attributed to "corpse" not "triggered skill"
   - Similar to Hazard bypass mechanism
3. Confidence: MEDIUM (needs testing)

AI creates pending item:
─────────────────────────
{
    'type': 'bypass',
    'question': '尸体爆炸能绕过Triggered限制吗？',
    'answer': '可能绕过，因为伤害归因为尸体而非触发技能',
    'confidence': 'medium',
    'key_entities': ['DetonateDeadPlayer', 'MetaCastOnCritPlayer'],
    'key_mechanisms': ['Triggered标签', '尸体爆炸', '伤害归因'],
    'reason': '机制类似Hazard绕过，但需要实际测试验证',
    'data_updates': [
        {
            'target': 'graph_edges',
            'operation': 'insert',
            'data': {
                'source': 'corpse_explosion',
                'target': 'triggered_energy_limit',
                'edge_type': 'bypasses',
                'source_type': 'heuristic'
            }
        }
    ]
}

AI asks user:
────────────
"我发现了潜在的绕过机制：尸体爆炸可能因为伤害归因为尸体本身而绕过Triggered限制。
是否将此发现记录到知识库？"

Options:
• 是，确认这个机制
• 否，这个机制不正确
• 需要更多测试验证
```

## Output Formats

### Skill Summary
```
## Skill: Cast on Critical
- Type: Meta, GeneratesEnergy, Triggers
- Description: While active, gains Energy when you Critically Hit...
- Stats: energy_generated_+% (per level)
- Reservation: 100 Spirit (flat)
```

### Mechanism Analysis
```
## Energy Generation (Cast on Critical)
Formula: (HitDamage / AilmentThreshold) × BaseEnergy × (1 + IncBonus) × MoreMods
Base: 100 centienergy per monster power
Scaling: +3% per level, affected by Boundless Energy
Restriction: Triggered spells cannot generate energy
Exception: Doedre's Undoing (Hazard mechanism bypasses restriction)
```

### Graph Path Result
```
## Path Found: Doedre's Undoing → Energy Generation
1. Doedre's Undoing (Support Gem)
   └─ creates → Hazard Zone (Mechanism)
2. Hazard Zone (Mechanism)
   └─ triggers → Curse Explosion (Event)
3. Curse Explosion (Event)
   └─ bypasses → Triggered Restriction (Constraint)
4. Triggered Restriction (Constraint)
   └─ blocks → Energy Generation (Mechanism)
   
Result: Damage from Hazard explosion is NOT attributed to trigger event,
allowing Cast on Critical to generate energy.
```

## Schema Management System

### Overview

The schema management system ensures consistency between data structure definitions and their consumers across the codebase.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    Core Components                                       │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  schemas/schemas.json - Central storage for:                            │
│  • Structure definitions (SQLite tables, dataclasses, enums)           │
│  • Definition-consumer relationships                                   │
│  • Notification queue                                                  │
│  • Change tracking                                                     │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Key Concepts

| Term | Description |
|------|-------------|
| **Structure** | A data definition unit (SQLite table, @dataclass, Enum) |
| **Definition File** | File that defines a structure (e.g., entity_index.py defines entities) |
| **Consumer File** | File that uses a structure (e.g., rules_extractor.py uses entities) |
| **schemas.json** | Central registry of all structures and their relationships |

### Code Modification Workflow

**CRITICAL**: When modifying code files that define or use data structures, follow this workflow:

#### Phase 1: Before Modification

```
When AI receives a request to modify a file:

Step 1: Query schemas.json to determine file role
──────────────────────────────────────────────────
from schema_manager import SchemaManager
manager = SchemaManager('schemas/schemas.json')
role = manager.get_file_role('rules_extractor.py')
# Returns: {'definitions': ['rules', 'Rule'], 'consumptions': ['entities']}

Step 2: Check for pending notifications
───────────────────────────────────────
If file is a consumer, check if referenced structures have changed:
- Compare structure's last_modified with consumer's last_adapted
- Alert user if adaptation needed

Step 3: Proceed with modification
─────────────────────────────────
```

#### Phase 2: After Modification

```
After modifying a file:

Step 1: Remove from queue (if consumer)
───────────────────────────────────────
manager.remove_from_queue('rules_extractor.py')

Step 2: Update schema if definition changed
───────────────────────────────────────────
if is_definition_changed:
    manager.update_schema('rules')
    # This adds consumers to notification queue

Step 3: Update adaptation timestamp
───────────────────────────────────
manager.update_consumer_adapted('entities', 'rules_extractor.py')

Step 4: Save changes
───────────────────
manager.save()
```

#### Phase 3: Queue Processing

```
After all user requests completed:

Step 1: Check if queue is empty
───────────────────────────────
if not manager.is_queue_empty():
    process_queue()

Step 2: Process queue iteratively
─────────────────────────────────
while queue not empty and iteration < max_iterations:
    for record in queue:
        detect_circular()
        if circular:
            handle_circular_flow()
        else:
            modify_consumer_file()
            remove_from_queue()

Step 3: Termination conditions
──────────────────────────────
• Queue empty → Iteration complete
• Max iterations reached → Alert user
```

### Circular Reference Handling

When circular references are detected (File A defines Structure A, references Structure B; File B defines Structure B, references Structure A):

```
Step 1: Detect circular
───────────────────────
is_circular, circular_files = manager.detect_circular()

Step 2: Pre-update phase
────────────────────────
• Collect all required structure changes
• Batch update schemas.json (no notifications triggered)

Step 3: Execution phase
───────────────────────
• Modify circular files sequentially
• Each file adapts to latest schemas.json

Step 4: Clear related queue records
───────────────────────────────────
```

### Iteration Limit Calculation

```
max_iterations = planned_files × max_depth × safety_factor

Where:
• planned_files = Number of files user plans to modify
• max_depth = Maximum depth of single file iteration (default: 3)
• safety_factor = Safety margin (default: 1.5)

Limits:
• Minimum: 5
• Maximum: 100
```

### Initialization

First-time setup or when schemas.json is missing:

```bash
python scripts/init_schemas.py --scripts-dir scripts/ --output schemas/schemas.json
```

This scans all Python files and extracts:
- Structure definitions (CREATE TABLE, @dataclass, Enum)
- Consumer references (imports, SQL queries)

### Schema Manager API

```python
from schema_manager import SchemaManager

manager = SchemaManager('schemas/schemas.json')

# Query file role
role = manager.get_file_role('rules_extractor.py')
# {'definitions': ['rules', 'Rule'], 'consumptions': ['entities']}

# Check if queue is empty
if not manager.is_queue_empty():
    # Process pending notifications
    pass

# Add to queue (definition changed)
manager.add_to_queue('entities', 'rules_extractor.py')

# Remove from queue (consumer modified)
manager.remove_from_queue('rules_extractor.py')

# Detect circular references
is_circular, files = manager.detect_circular()

# Calculate max iterations
max_iter = manager.calculate_max_iterations(planned_files=5)

# Save changes
manager.save()
```

### Validator API

```python
from schema_validator import SchemaValidator

validator = SchemaValidator('schemas/schemas.json')

# Before file modification
result = validator.before_file_modify('rules_extractor.py')
# {'role': {...}, 'warnings': [...], 'pending_schemas': [...]}

# After file modification
validator.after_file_modify('rules_extractor.py', is_definition_changed=True)

# Process queue
result = validator.process_queue(
    modify_callback=lambda file, schemas: True,
    planned_files=3
)
```

### Files Reference

| File | Purpose |
|------|---------|
| `schemas/schemas.json` | Central registry of structures and relationships |
| `scripts/schema_manager.py` | Core management functions |
| `scripts/schema_validator.py` | Validation and queue processing |
| `scripts/init_schemas.py` | Initialize schemas.json from codebase |

### Error Handling

| Error | Handling |
|-------|----------|
| Max iterations reached | Stop, generate report, alert user |
| Single file processing failed | Mark as failed, continue with others |
| Circular handling failed | Log chain, alert user |
| Stale queue records | Alert user for confirmation |
| Consumer file deleted | Remove from queue and schema |
