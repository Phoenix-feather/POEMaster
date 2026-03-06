# 公式库实施方案总结

## 探索历程回顾

### 第一阶段：架构争议（用户批评）

**我最初的过度设计方案**：
- ❌ 创建pob_sources.db存储原始Lua代码（冗余）
- ❌ 双轨数据层（过度设计）
- ❌ 重复存储POB数据

**用户的关键批评**：
> "POB数据已经有了，只需要提取一个公式库就可以识别适配了，最多公式库的每条数据带一个LUA文件信息，对于规范化数据处理不了的信息再去POB原始数据找"

**修正后的轻量级方案**：
- ✅ 公式库只存储函数定义，带source_file字段
- ✅ 只有规范化数据处理不了时才读原始Lua
- ✅ 启发思考完成后再精确定位

---

### 第二阶段：特征提取方法讨论

**用户的核心思路**：
> "先从公式提取分析过程中提取他的特征或者准确的标签/状态来构建这个公式的特征数据；然后我们机制库/实体库/规则库里面如果有规范化的标签/状态或者可信度低一些的描述性都能提取出特征这样来匹配公式。不过这个是我的想法，如果POB原始数据中就有准确定位匹配的方法就更好"

**关键决策**：
1. ✅ 提取**所有函数**（而非只提取Calc开头的）
2. ✅ 提取时就建立**完整调用图**
3. ✅ 特征匹配：精确（官方stat ID）+ 模糊（简化名称）+ 标签

---

### 第三阶段：POB数据探索（重大发现）

**发现POB三层Stat架构**：

```
Layer 1: 公式代码 (CalcModules)
         ↓ 使用简化名称："Speed", "CooldownRecovery"
         
Layer 2: SkillStatMap.lua (映射层，未提取)
         ↓ 提供简化名称 → stat ID映射
         
Layer 3: ModCache.lua (官方stat层，已提取)
         → 555个官方stat ID
         → 类型：BASE, FLAG, INC, MORE等
```

**关键发现**：
1. ✅ ModCache.lua已提取：555个官方stat ID
2. ❌ SkillStatMap.lua未提取（映射层缺失）
3. ✅ 计算模块已提取：59个CalcModule
4. ✅ 规范化数据完整：data_json 100%填充

---

### 第四阶段：规范化数据端验证

**用户的问题**：
> "规范化数据端之前也有提取状态/标签数据能直接用吗，还是需要补充"
> "技能实体的stats没有数据需要检查一下原因"

**检查结果**：
- ✅ data_json 100%填充，包含所有数据
- ⚠️ 独立字段填充率低是正常的（POB原始数据如此）
- ✅ 字段识别正确，无需修复

**实际数据分布**：
| 字段 | 填充率 | 可直接用？ |
|------|--------|-----------|
| stat_sets | 100% | ✅ 是 |
| constant_stats | 89.1% | ✅ 是 |
| stats | 54.4% | ✅ 是 |
| skill_types | 38.2% | ✅ 是 |
| quality_stats | 32.0% | ✅ 是 |
| **data_json** | **100%** | ✅ **最完整** |

---

## 最终方案架构

### 核心原则

```
┌─────────────────────────────────────────────────────────────┐
│                  轻量级 + 利用POB现有系统                     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. 轻量级设计                                               │
│     - 不复制POB原始数据                                       │
│     - 公式库只存储函数定义 + source_file                      │
│     - 需要原始代码时去文件系统读                              │
│                                                             │
│  2. 利用POB现有系统                                           │
│     - 555个官方stat ID（ModCache.lua）                       │
│     - 规范化标签（skill_types, tags）                        │
│     - 保证计算一致性                                          │
│                                                             │
│  3. 混合特征匹配                                              │
│     - 精确特征：官方stat ID                                   │
│     - 模糊特征：简化名称                                      │
│     - 标签特征：规范化的skill_types                           │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 数据库Schema

```sql
-- 公式表
CREATE TABLE formulas (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    code TEXT NOT NULL,            -- 函数代码
    
    -- 源文件定位
    source_file TEXT NOT NULL,     -- 相对路径
    line_start INTEGER,
    line_end INTEGER,
    
    -- 特征（JSON数组）
    exact_stats TEXT,              -- ["CooldownRecovery"] 官方stat ID
    fuzzy_stats TEXT,              -- ["Speed"] 简化名称
    inferred_tags TEXT,            -- ["triggered"] 推断标签
    
    -- 调用关系
    calls TEXT,                    -- 调用的函数
    called_by TEXT,                -- 被调用的函数
    
    -- 约束和文档
    constraints TEXT,
    description TEXT
);

-- 公式特征索引表
CREATE TABLE formula_features (
    formula_id TEXT,
    feature_type TEXT,             -- "exact", "fuzzy", "tag"
    feature_value TEXT,
    confidence REAL,
    PRIMARY KEY (formula_id, feature_type, feature_value)
);

-- 公式-Stat关联表
CREATE TABLE formula_stats (
    formula_id TEXT,
    stat_id TEXT,
    relation TEXT,                 -- "uses" 或 "produces"
    PRIMARY KEY (formula_id, stat_id, relation)
);

-- 公式调用关系表
CREATE TABLE formula_calls (
    caller_id TEXT,
    callee_id TEXT,
    call_count INTEGER DEFAULT 1,
    PRIMARY KEY (caller_id, callee_id)
);
```

### 特征提取流程

```
┌──────────────────────┐     ┌──────────────────────┐
│   公式端特征提取      │     │  规范化数据端特征提取  │
├──────────────────────┤     ├──────────────────────┤
│ 从CalcModules提取：   │     │ 从实体库提取：        │
│ • 函数代码（body）    │     │ • data_json (100%)   │
│ • 提取stat名称        │     │ • stat_sets (100%)   │
│ • 尝试映射到官方ID    │     │ • skill_types (38%)  │
│ • 推断标签            │     │ • stats (54%)        │
│                      │     │ • tags (宝石)        │
│ 示例：               │     │                      │
│ exact: ["CooldownRecovery"] │ exact: ["skill_combat_frenzy_x_ms_cooldown"]│
│ fuzzy: ["Speed"]     │     │ tags: ["Spell", "Duration"]│
│ tags: ["triggered"]  │     │                      │
└──────────┬───────────┘     └──────────┬───────────┘
           │                            │
           └────────特征匹配────────────┘
                        │
                        ▼
              ┌─────────────────┐
              │   匹配分数计算   │
              │  精确 × 0.5     │
              │  模糊 × 0.3     │
              │  标签 × 0.2     │
              └─────────────────┘
```

### 实施步骤

#### Phase 1：公式提取（核心）

```python
# 创建 formula_extractor.py

class FormulaExtractor:
    def extract_all_functions(self, pob_path: str):
        """提取所有Lua函数"""
        for lua_file in pob_path.rglob('*.lua'):
            functions = self._parse_lua_functions(lua_file)
            for func in functions:
                self._extract_formula(func, lua_file)
    
    def _extract_formula(self, func: Function, source_file: Path):
        """提取公式并分析特征"""
        formula = {
            'id': f"{source_file.relative_name}_{func.name}",
            'name': func.name,
            'code': func.body,
            'source_file': str(source_file.relative_to(pob_path)),
            'line_start': func.start_line,
            'line_end': func.end_line,
            
            # 特征提取
            'exact_stats': [],  # 能映射到官方stat ID的
            'fuzzy_stats': [],  # 简化名称
            'inferred_tags': [],  # 从代码推断
        }
        
        # 从代码提取stat名称
        stat_names = self._extract_stat_names(func.body)
        for stat_name in stat_names:
            # 尝试映射到官方stat ID
            if stat_name in self.official_stat_ids:
                formula['exact_stats'].append(stat_name)
            else:
                formula['fuzzy_stats'].append(stat_name)
        
        # 推断标签
        formula['inferred_tags'] = self._infer_tags(func.body)
        
        return formula
```

#### Phase 2：调用链分析

```python
class CallChainAnalyzer:
    def build_call_graph(self, formulas: List[Formula]):
        """构建完整调用图"""
        name_to_id = {f['name']: f['id'] for f in formulas}
        
        for formula in formulas:
            for called_func in formula['calls']:
                if called_func in name_to_id:
                    self._add_call_edge(
                        formula['id'], 
                        name_to_id[called_func]
                    )
    
    def calculate_call_depth(self):
        """计算调用深度（BFS从叶子节点开始）"""
        pass
    
    def compute_total_stats(self, formula_id: str):
        """计算综合stats（包括间接调用）"""
        pass
```

#### Phase 3：特征匹配

```python
class FormulaMatcher:
    def find_matching_formulas(self, entity_id: str):
        """查找匹配的公式"""
        # 1. 从实体提取特征
        entity_features = self._extract_entity_features(entity_id)
        
        # 2. 匹配公式
        matches = []
        for formula_id, formula_features in self.formulas.items():
            score = self._calculate_match_score(
                formula_features, entity_features
            )
            if score > 0.5:
                matches.append((formula_id, score))
        
        return sorted(matches, key=lambda x: x[1], reverse=True)
    
    def _calculate_match_score(self, formula_features, entity_features):
        """计算匹配分数"""
        # 精确匹配
        exact_score = len(
            formula_features['exact_stats'] & entity_features['exact_stats']
        ) / max(len(formula_features['exact_stats']), 1)
        
        # 模糊匹配
        fuzzy_score = len(
            formula_features['fuzzy_stats'] & entity_features['fuzzy_stats']
        ) / max(len(formula_features['fuzzy_stats']), 1)
        
        # 标签匹配
        tag_score = len(
            formula_features['inferred_tags'] & entity_features['tags']
        ) / max(len(formula_features['inferred_tags']), 1)
        
        return exact_score * 0.5 + fuzzy_score * 0.3 + tag_score * 0.2
```

#### Phase 4：集成到知识库

```python
# 更新 init_knowledge_base.py

def init_formula_library(pob_path: str, db_path: str):
    """初始化公式库"""
    print("提取公式...")
    extractor = FormulaExtractor(pob_path)
    formulas = extractor.extract_all_functions()
    
    print("分析调用链...")
    analyzer = CallChainAnalyzer()
    analyzer.build_call_graph(formulas)
    analyzer.calculate_call_depth()
    
    print("建立特征索引...")
    matcher = FormulaMatcher()
    matcher.build_feature_index(formulas)
    
    print(f"完成：{len(formulas)} 个公式")
```

---

## 关键决策总结

| 问题 | 决策 | 理由 |
|------|------|------|
| 是否需要pob_sources.db？ | ❌ 不需要 | POB原始文件已在文件系统，只需source_file字段 |
| 提取哪些函数？ | ✅ 所有函数 | 更全面，支持启发式发现 |
| 何时建立调用图？ | ✅ 提取时就建立 | 保证完整性，避免后续重复分析 |
| 如何匹配公式和实体？ | ✅ 混合特征匹配 | 精确（官方ID）+ 模糊（简化名称）+ 标签 |
| 数据来源？ | ✅ 直接用data_json | 100%填充，无需修复独立字段 |
| 是否需要SkillStatMap.lua？ | ⏸️ 可选 | 先用现有数据，后续可补充提升精确度 |

---

## 数据现状确认

### 已有数据（可直接用）

- ✅ **实体库**：16,113个实体，data_json 100%填充
- ✅ **规则库**：19,128条规则
- ✅ **CalcModules**：59个计算模块
- ✅ **官方Stat ID**：555个（ModCache.lua）
- ✅ **规范化标签**：skill_types, tags

### 待提取数据（可选）

- ⏸️ **SkillStatMap.lua**：简化名称 → stat ID映射（可提升精确度）
- ⏸️ **公式库**：本次实施的核心任务

---

## 成功标准

### 短期目标

1. ✅ 提取所有CalcModule函数到公式库
2. ✅ 建立完整的调用关系图
3. ✅ 实现特征提取和匹配
4. ✅ 验证匹配准确性（MetaCastOnCritPlayer → calcTriggerEnergy）

### 长期目标

1. ✅ 支持启发记录验证（版本更新后重新探索）
2. ✅ 支持复杂查询（如"哪些公式影响了trigger_energy？"）
3. ✅ 与POB保持一致性（利用官方系统）
4. ✅ 可扩展性（支持新增计算逻辑）

---

## 风险与对策

| 风险 | 对策 |
|------|------|
| Stat名称映射不准确 | 使用混合特征匹配，精确+模糊 |
| 调用关系复杂 | 提取时就建立完整调用图 |
| 数据结构变化 | 用启发记录（存问题而非答案）|
| POB更新导致失效 | 利用官方系统，保持一致性 |

---

## 总结

**核心优势**：
1. ✅ 轻量级（不冗余存储）
2. ✅ 利用POB现有系统（保证一致性）
3. ✅ 混合特征匹配（精确+模糊）
4. ✅ 支持启发式推理（问题驱动）

**实施优先级**：
1. 🔴 **Phase 1**：公式提取（核心，必须）
2. 🔴 **Phase 2**：调用链分析（必要）
3. 🟡 **Phase 3**：特征匹配（提高准确性）
4. 🟢 **Phase 4**：SkillStatMap提取（可选，提升精确度）

**准备就绪**：
- ✅ 数据完整（data_json 100%）
- ✅ 架构清晰（轻量级 + POB系统）
- ✅ 方法明确（混合特征匹配）
- ✅ 可直接实施（无需补充数据）
