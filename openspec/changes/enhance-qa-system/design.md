## Context

POE Data Miner v2（2026-03-18 重构完成）是一个基于 POB 数据的问答服务。当前架构：

- **数据层**：3 个 SQLite DB（entities.db 20MB/16461 实体、formulas.db 4.5MB/1486 公式、mechanisms.db 40KB/44 机制）
- **查询层**：`kb_query.py` 提供 4 个 CLI 子命令（entity/stats/mechanism/formula），返回 raw JSON
- **AI 调用方式**：文档驱动——AI 读 skill.md 后在终端执行 bash 命令
- **Lua 环境**：lupa>=2.0 已有，当前裸初始化，仅能加载纯数据表文件

核心约束：
- 所有脚本迭代必须在原文件上更新（禁止新增替代旧文件）
- 数据结构变更必须触发 Schema 管理系统
- POB 原始数据不能遗漏（data_json 兜底完整性）

## Goals / Non-Goals

**Goals:**
- 预计算入库所有解读字段（summary/key_mechanics/display_stats/behavior_description），查不到说明设计有漏洞
- 用户自然语言提问，AI 自动分类为 8 种问题类型并选择合适的子命令组合
- 44 个机制全部有行为描述（能分析出来就写）
- 辅助宝石推荐用抽象公式量化差异，不可量化但机制适配的给潜力推荐
- 系统定位从"静态数据查询"升级为"数据分析汇总服务"

**Non-Goals:**
- 不做实时 DPS 数值计算器（不代入具体装备/天赋数值算绝对 DPS）
- 不做 Build 推荐系统（不提供"最佳 Build"这种主观推荐）
- 不做游戏版本追踪（不自动检测 POB 更新并重建知识库）
- 不重写 POB 的完整计算引擎

## Decisions

### D1: 解读层预计算入库（而非查询时动态生成）

**选择**：初始化时预计算 summary/key_mechanics/display_stats 并写入 DB

**理由**：如果查询不到说明设计有漏洞——动态拼接掩盖了数据缺失问题。预计算结果稳定、查询快、可在初始化时做完整性校验。

**替代方案**：
- 查询时动态生成：❌ 每次查询都要做提取逻辑，结果可能不稳定
- 预计算 + 动态兜底：❌ 兜底逻辑掩盖漏洞，不如强制暴露问题

### D2: 使用 lupa 运行 POB 原始 StatDescriber.lua（而非 Python 重写）

**选择**：搭建 ~50 行适配层，注入 LoadModule/copyTable/round/floor 等，直接在 lupa 中运行 StatDescriber.lua

**理由**：
- 结果 100% 精确（跑的是 POB 原始代码）
- 维护成本最低（POB 更新 StatDescriber 时无需改适配层）
- 适配工作量小（StatDescriber 外部依赖只有 5 个函数）

**替代方案**：
- Python 重写 320 行 Lua 逻辑：❌ 工作量大、精度 95%、需同步维护
- 静态模板匹配：❌ 精度 80%、无法处理 20+ 种特殊处理指令

**适配层需注入**：

| 函数 | 来源 | 实现方式 |
|------|------|---------|
| `LoadModule(path, ...)` | POB C++ 宿主 | Python 模拟: `loadfile(pob_root..path..".lua")(...)` |
| `copyTable(tbl, noRecurse)` | Common.lua:419 | 提取原始 Lua 代码注入 |
| `round(val, dec)` | Common.lua:646 | 提取原始 Lua 代码注入 |
| `floor(val, dec)` | Common.lua:658 | 提取原始 Lua 代码注入 |
| `ConPrintf(...)` | POB C++ 宿主 | 空函数 `function() end` |
| `ItemClasses` | POB 数据 | 空表 `{}` |

### D3: 问题分类由 AI 通过 skill.md 指引完成（而非 Python 侧 NLP）

**选择**：在 skill.md 中定义 8 种问题类型的识别规则 + 调用策略 + 输出模板，AI 读指引后自动分类

**理由**：
- AI 天然擅长自然语言理解，不需要在 Python 侧做简陋的关键词分类
- skill.md 是 AI 的行为指南，修改灵活（无需改代码）
- CLI 子命令语义明确，AI 容易选择

**替代方案**：
- Python 侧 `ask` 命令做 NLP 分类：❌ 关键词匹配太简陋，比不上 AI
- 保持 4 个子命令不变：❌ AI 需要多次调用自行拼装，容易出错

**CLI 子命令设计**：面向场景扩展，每个子命令返回针对该场景优化的数据

### D4: 辅助推荐基于抽象公式量化 + 潜力列表

**选择**：可量化的辅助（MORE/INC/BASE 类 stat 增益）用抽象公式表达差异；不可量化但机制适配的辅助给潜力推荐列表

**理由**：不需要算具体数值——知道一个辅助提供 39% MORE Damage 和另一个提供 +100 Added Lightning，用 DPS 公式结构就能看出它们的影响位置和相对权重。连锁翻倍但伤害减少这种可以量化其净收益公式。

**可量化示例**：
```
Chain Support: ChainMax += 2, Damage × (1 - 20%) per chain
  对 Arc: 初始 ChainRemaining 增加 → 初始 MORE 加成增加
  净效果公式: damage_change = MORE_per_chain × additional_chains - less_per_chain_penalty
```

**不可量化→潜力推荐示例**：
```
Spell Echo Support: 重复施法
  对 Arc: 机制适配（清图效率翻倍）
  潜力原因: synergy_type = "mechanic_match"
```

### D5: 机制行为描述从代码逆向提炼，分三类策略

**选择**：

| 机制类型 | 提取策略 | 代码来源 |
|---------|---------|---------|
| Flag 型 | 从 CalcOffence/CalcDefence 找 Flag 检查点 → "当 flag 启用时,{行为}" | `modDB:Flag(nil,"FlagName")` |
| 数值型 | 从 Sum/Mod 使用点 → 完整公式 + 触发条件 | `modDB:Sum("BASE","ModName")` |
| 触发型 | 从 CalcTriggers.configTable → 触发条件 + 冷却 + 技能要求 | `configTable["name"]` |

全部 44 个机制都提取行为描述。

### D6: 新增 supports.db 独立数据库

**选择**：辅助匹配数据存入独立的 supports.db（而非追加到 entities.db 或 formulas.db）

**理由**：辅助匹配是跨实体的关联数据，数据量可能较大（技能数 × 辅助数），与实体/公式的关注点不同，独立存储便于管理和重建。

## Architecture

### 数据流全景

```
POB 数据文件 (Lua)
       │
       ├── act_*.lua / sup_*.lua ──→ data_scanner.py ──→ entity_index.py
       │                                                      │
       │                                                      ├── entities.db
       │                                                      │   + summary (预计算)
       │                                                      │   + key_mechanics (预计算)
       │                                                      │   + display_stats (预计算)
       │                                                      │          ▲
       │                                              stat_describer_bridge.py
       │                                              (lupa + StatDescriber.lua)
       │
       ├── SkillStatMap.lua ──→ stat_map_index.py ──→ formulas.db
       │                                                  + formula_chains
       │
       ├── ModCache.lua ──→ mechanism_extractor.py ──→ mechanisms.db
       │                                                  + behavior_description
       │                                                  + mechanism_relations
       │
       └── CalcTriggers.lua ──→ mechanism_extractor.py
            CalcOffence.lua      (代码分析提取行为)
            CalcDefence.lua

entities.db + support 实体 ──→ support_matcher.py ──→ supports.db
                                                       ├── support_compatibility
                                                       ├── support_effects
                                                       └── support_potential
```

### 查询层架构

```
用户自然语言 → AI(读skill.md指引) → 分类为8种类型之一
                                          │
                   ┌──────────────────────┼────────────────────────┐
                   ▼                      ▼                        ▼
            entity子命令           mechanism子命令            supports子命令
            --detail X             --detail X               --mode X
                   │                      │                        │
                   ▼                      ▼                        ▼
             按类型裁剪字段        附加behavior/          兼容矩阵+效果分类
             附加response_type    relations               +潜力推荐
                   │                      │                        │
                   └──────────────────────┼────────────────────────┘
                                          ▼
                                   JSON + response_type
                                          │
                                          ▼
                                 AI 按 skill.md 模板格式化
                                          │
                                          ▼
                                    用户看到的回答
```

### 初始化流程（7 步）

```
Step 1: Schema 验证
Step 2: 实体索引 → entities.db（含 summary/key_mechanics/display_stats 预计算）
Step 3: 公式索引 → formulas.db（含 formula_chains）
Step 4: 机制提取 → mechanisms.db（含 behavior/relations）
Step 5: 辅助匹配 → supports.db
Step 6: 版本信息更新
Step 7: 完整性校验（summary 覆盖率、behavior 覆盖率、compatibility 完整性）
```

## Risks / Trade-offs

### [Risk] lupa 加载大型 StatDescription 文件可能慢或失败
**Mitigation**: skill_stat_descriptions.lua 710KB、stat_descriptions.lua 3.9MB。在 Step 2 开始前做 lupa 加载测试，如果超时或 OOM，降级到选项 C（静态模板匹配）。初始化阶段一次性加载，不影响查询性能。

### [Risk] 44 个机制的行为描述可能无法全部从代码自动提取
**Mitigation**: 优先自动提取（Flag/数值/触发三类策略），无法自动提取的用 `config/mechanism_descriptions.yaml` 人工补充。初始化时校验覆盖率并报告缺失项。

### [Risk] 辅助匹配预计算结果可能不完整
**Mitigation**: 某些辅助的 require_skill_types 逻辑可能复杂（条件组合）。第一版先处理简单的标签匹配，复杂条件标记为 `needs_review`，后续迭代完善。

### [Risk] Schema 管理系统级联变更
**Mitigation**: 本次涉及 entities/mechanisms/formulas 三个 DB 的 schema 变更 + 新增 supports.db。需要在 Phase 1 开始前更新 schemas.json，确保消费者通知队列正确。

### [Trade-off] 预计算入库 vs 查询灵活性
预计算的 summary/display_stats 在 POB 数据更新后需要重新初始化才能更新。但由于知识库本身就需要手动重新初始化（没有自动更新机制），这不是新增的限制。

## Open Questions

（已在探索阶段全部解决，无遗留问题。）
