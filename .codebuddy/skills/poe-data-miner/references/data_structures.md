# POB Data Structures Reference

## Directory Structure

```
POBData/
├── Data/
│   ├── Skills/
│   │   ├── act_str.lua    # Strength active skills
│   │   ├── act_dex.lua    # Dexterity active skills
│   │   ├── act_int.lua    # Intelligence active skills
│   │   ├── sup_str.lua    # Strength supports
│   │   ├── sup_dex.lua    # Dexterity supports
│   │   └── sup_int.lua    # Intelligence supports
│   ├── Uniques/
│   │   ├── weapon.lua     # Unique weapons
│   │   ├── armour.lua     # Unique armour
│   │   ├── shield.lua     # Unique shields
│   │   └── jewel.lua      # Unique jewels
│   ├── Gems.lua           # Gem definitions
│   ├── SkillStatMap.lua   # Stat to modifier mappings
│   ├── ModCache.lua       # Modifier cache
│   └── GameVersions.lua   # Version information
├── Modules/
│   ├── CalcActiveSkill.lua
│   ├── CalcDefence.lua
│   └── CalcOffence.lua
└── Classes/
    └── SkillsTab.lua
```

---

## Skill Definition Structure

```lua
skills["SkillId"] = {
    name = "Skill Name",
    baseTypeName = "Base Type",
    color = 3,  -- 1=Str, 2=Dex, 3=Int
    description = "Description text",
    skillTypes = {
        [SkillType.Meta] = true,
        [SkillType.GeneratesEnergy] = true,
        -- ...
    },
    castTime = 0,
    qualityStats = {
        { "stat_name", value },
    },
    levels = {
        [1] = { levelRequirement = 0, ... },
        [20] = { levelRequirement = 90, ... },
    },
    statSets = {
        [1] = {
            label = "StatSet Name",
            incrementalEffectiveness = 0.055,
            statDescriptionScope = "skill_stat_descriptions",
            baseFlags = {},
            constantStats = {
                { "stat_name", value },
            },
            stats = {
                "energy_generated_+%",
                -- ...
            },
            levels = {
                [1] = { 0, statInterpolation = { 1 }, actorLevel = 1 },
                [20] = { 57, statInterpolation = { 1 }, actorLevel = 97.7 },
            },
        },
    },
}
```

### Key Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Display name |
| `baseTypeName` | string | Gem base type |
| `color` | number | 1=Str, 2=Dex, 3=Int |
| `description` | string | Skill description text |
| `skillTypes` | table | Set of SkillType enums |
| `castTime` | number | Cast time in seconds |
| `qualityStats` | table | Quality bonus stats |
| `levels` | table | Level requirements |
| `statSets` | table | Stat configurations |

---

## Gem Definition Structure

```lua
["Metadata/Items/Gems/SkillGemName"] = {
    name = "Gem Name",
    baseTypeName = "Base Type",
    gameId = "Metadata/Items/Gems/SkillGemName",
    variantId = "VariantName",
    grantedEffectId = "SkillId",
    additionalGrantedEffectId1 = "SupportSkillId",
    tags = {
        support = true,
    },
    gemType = "Active",  -- or "Support"
    gemFamily = "Family Name",
    tagString = "",
    reqStr = 0,
    reqDex = 0,
    reqInt = 100,
    Tier = 2,
}
```

### Gem Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Gem display name |
| `grantedEffectId` | string | Links to skill definition |
| `gemType` | string | "Active" or "Support" |
| `reqStr/Dex/Int` | number | Attribute requirements |
| `Tier` | number | Gem tier (1-3 typically) |

---

## SkillStatMap Structure

Maps game stats to internal modifiers:

```lua
["stat_name"] = {
    skill("property", value, { conditions }),
    div = 1000,  -- divisor
},
```

### Common Mappings

```lua
-- Duration
["base_skill_effect_duration"] = {
    skill("duration", nil),
    div = 1000,
},

-- Damage
["spell_minimum_base_fire_damage"] = {
    skill("FireMin", nil),
},
["spell_maximum_base_fire_damage"] = {
    skill("FireMax", nil),
},

-- Modifiers
["energy_generated_+%"] = {
    skill("EnergyGeneration", "INC", { mod = true }),
},

-- Reservation
["spirit_reservation_flat"] = {
    skill("SpiritReservation", nil),
},
```

### Modifier Types

| Type | Description | Calculation |
|------|-------------|-------------|
| `INC` | Increased modifier | Additive (sum) |
| `MORE` | More modifier | Multiplicative (product) |
| `BASE` | Base value | Direct addition |
| `FLAG` | Boolean flag | Set to true |

---

## SkillType Enum

### Category Types

| Type | Description |
|------|-------------|
| `Attack` | Attack skill |
| `Spell` | Spell skill |
| `Projectile` | Projectile-based |
| `Area` | Area of effect |
| `Duration` | Has duration |
| `Melee` | Melee attack |
| `RangedAttack` | Ranged attack |

### Behavior Types

| Type | Description |
|------|-------------|
| `Triggerable` | Can be triggered |
| `Triggered` | **Triggered by another skill** |
| `Trappable` | Can be trapped |
| `Mineable` | Can be mined |
| `Totem` | Totem skill |
| `Vaal` | Vaal skill |
| `Cooldown` | Has cooldown |
| `Multistrikeable` | Can multistrike |

### Meta Skill Types

| Type | Description |
|------|-------------|
| `Meta` | Meta skill container |
| `GeneratesEnergy` | Can generate energy |
| `Triggers` | Triggers socketed skills |
| `HasReservation` | Reserves spirit/mana |
| `OngoingSkill` | Persistent buff/debuff |
| `Persistent` | Remains active |
| `Buff` | Applies buff |
| `Invocation` | Manual activation |

---

## Unique Item Structure

```lua
[[
Item Name
Base Type
League: League Name
Variant: Pre X.X.X
Variant: Current
Implicits: 1
Grants Skill: Skill Name
(100-150)% increased Armour
+(30-40)% to Fire Resistance
]],
```

### Parsing Rules

1. **Name**: First line
2. **Base Type**: Second line
3. **Properties**: Key-value pairs (e.g., `League: ...`)
4. **Implicits**: Count of implicit modifiers
5. **Modifiers**: Remaining lines

### Variant Handling

```lua
-- Items can have multiple variants
{variant:1}(100-150)% increased Armour
{variant:2}(150-200)% increased Armour
```

---

## Database Schemas

### Entity Index (`entities.db`)

```sql
CREATE TABLE entities (
    id TEXT PRIMARY KEY,
    name TEXT,
    type TEXT,  -- 'active_skill', 'support_gem', 'unique_item'
    description TEXT,
    skill_types TEXT,  -- JSON array
    constant_stats TEXT,  -- JSON array
    stats TEXT,  -- JSON array
    levels TEXT,  -- JSON object
    source_file TEXT,
    created_at TEXT,
    updated_at TEXT
);

CREATE INDEX idx_entities_name ON entities(name);
CREATE INDEX idx_entities_type ON entities(type);
```

### Rules Library (`rules.db`)

```sql
CREATE TABLE rules (
    id TEXT PRIMARY KEY,
    type TEXT,  -- 'entity_stat', 'stat_mechanism', 'condition'
    layer INTEGER,  -- 1, 2, or 3
    source TEXT,  -- 'stats', 'skill_stat_map', 'code'
    pattern TEXT,
    conditions TEXT,  -- JSON object
    effects TEXT,  -- JSON object
    confidence REAL,  -- 0.0 to 1.0
    verified BOOLEAN,
    created_at TEXT
);

CREATE INDEX idx_rules_type ON rules(type);
CREATE INDEX idx_rules_layer ON rules(layer);
```

### Attribute Graph (`graph.db`)

```sql
CREATE TABLE graph_nodes (
    id TEXT PRIMARY KEY,
    type TEXT,  -- 'entity', 'mechanism', 'stat', 'constraint'
    name TEXT,
    properties TEXT,  -- JSON object
    source TEXT,
    created_at TEXT
);

CREATE TABLE graph_edges (
    id TEXT PRIMARY KEY,
    source TEXT,
    target TEXT,
    edge_type TEXT,  -- 'has_type', 'has_stat', 'modifies', 'causes', 'blocks', 'bypasses'
    properties TEXT,  -- JSON object
    source_type TEXT,  -- 'auto', 'rule', 'predefined'
    confidence REAL,
    created_at TEXT
);

CREATE INDEX idx_edges_source ON graph_edges(source);
CREATE INDEX idx_edges_target ON graph_edges(target);
CREATE INDEX idx_edges_type ON graph_edges(edge_type);
```

---

## Parsing Tips

### Extracting Skill Data
1. Match `skills["<id>"] = { ... }`
2. Parse nested tables recursively
3. Handle multi-line string values

### Handling Variants
- Items can have multiple variants
- Use `{variant:N}` markers
- Parse variant definitions at start

### Stat Interpolation
- `statInterpolation = { 1 }` means linear interpolation
- Calculate intermediate values based on actorLevel

### Lua Table Parsing

```lua
-- Simple value
key = value

-- Table
key = {
    nested_key = nested_value
}

-- Array
key = {
    [1] = "value1",
    [2] = "value2"
}

-- Set (boolean table)
key = {
    [EnumValue] = true
}
```

---

## Common Patterns

### Find Meta Skills
```lua
skillTypes = { [SkillType.Meta] = true, ... }
```

### Find Energy Generators
```lua
skillTypes = { [SkillType.GeneratesEnergy] = true, ... }
```

### Extract Base Stats
```lua
constantStats = { { "stat_name", value } }
```

### Level-Based Stats
```lua
stats = { "energy_generated_+%" }
levels = { [N] = { value, statInterpolation = { 1 }, actorLevel = X } }
```

### Triggered Check
```lua
if skillTypes[SkillType.Triggered] then
    -- This skill is triggered, apply restrictions
end
```

---

## Version Information

### GameVersions.lua Structure

```lua
gameVersion = "0.4.0"
pobVersion = "0.4.0"
```

### Version Detection
1. Read `GameVersions.lua` from POB data directory
2. Parse `gameVersion` and `pobVersion`
3. Compare with stored version in knowledge base
4. Trigger recovery if version changed
