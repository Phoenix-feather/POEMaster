# 隐含知识验证机制 - 详细设计

## POB代码搜索算法

### 搜索策略分层

```
┌─────────────────────────────────────────────────────┐
│              POB代码搜索策略                         │
├─────────────────────────────────────────────────────┤
│                                                     │
│  Layer 1: 精确匹配（优先级最高）                     │
│    ├─ stat定义搜索                                  │
│    │   └─ "generic_ongoing_trigger_does_not_use_energy" │
│    ├─ skillTypes约束                                │
│    │   └─ requireSkillTypes, excludeSkillTypes      │
│    └─ 明确的规则代码                                │
│        └─ addSkillTypes, triggered 标签赋值         │
│                                                     │
│  Layer 2: 模式匹配（中等优先级）                     │
│    ├─ 条件语句                                      │
│    │   └─ if skillTypes[SkillType.XXX] then ...     │
│    ├─ 函数调用模式                                  │
│    │   └─ isTriggered(skill), hasEnergy(skill)      │
│    └─ 计算逻辑                                      │
│        └─ CalcModules 中的计算公式                  │
│                                                     │
│  Layer 3: 语义推断（低优先级）                       │
│    ├─ 注释和描述                                    │
│    ├─ 命名约定                                      │
│    └─ 上下文关联                                    │
│                                                     │
└─────────────────────────────────────────────────────┘
```

### 具体搜索实现

```python
class POBCodeSearcher:
    """POB代码搜索器"""
    
    def __init__(self, pob_data_path: str):
        self.pob_path = Path(pob_data_path)
        self.cache = {}  # 搜索缓存
        
    def search_stat_definition(self, stat_name: str) -> dict:
        """
        搜索stat定义
        
        返回：
        {
            'found': True,
            'locations': [
                {
                    'file': 'act_dex.lua',
                    'line': 9596,
                    'context': 'stats = { "generic_ongoing_trigger_does_not_use_energy" }',
                    'skill': 'TrailOfCaltropsPlayer'
                }
            ]
        }
        """
        results = []
        
        # 搜索 Data/Skills/*.lua
        skills_dir = self.pob_path / 'Data' / 'Skills'
        for lua_file in skills_dir.glob('*.lua'):
            matches = self._search_in_file(
                lua_file, 
                f'"{stat_name}"',
                context_lines=5
            )
            results.extend(matches)
        
        return {
            'found': len(results) > 0,
            'locations': results
        }
    
    def search_skilltype_constraint(self, skill_type: str) -> dict:
        """
        搜索skillTypes约束
        
        返回：
        {
            'found': True,
            'required_by': [...],  # requireSkillTypes
            'excluded_by': [...],  # excludeSkillTypes
            'added_by': [...]      # addSkillTypes
        }
        """
        result = {
            'found': False,
            'required_by': [],
            'excluded_by': [],
            'added_by': []
        }
        
        skills_dir = self.pob_path / 'Data' / 'Skills'
        for lua_file in skills_dir.glob('*.lua'):
            # 搜索 requireSkillTypes
            required = self._search_skilltype_usage(
                lua_file, 'requireSkillTypes', skill_type
            )
            result['required_by'].extend(required)
            
            # 搜索 excludeSkillTypes
            excluded = self._search_skilltype_usage(
                lua_file, 'excludeSkillTypes', skill_type
            )
            result['excluded_by'].extend(excluded)
            
            # 搜索 addSkillTypes
            added = self._search_skilltype_usage(
                lua_file, 'addSkillTypes', skill_type
            )
            result['added_by'].extend(added)
        
        result['found'] = (
            len(result['required_by']) > 0 or
            len(result['excluded_by']) > 0 or
            len(result['added_by']) > 0
        )
        
        return result
    
    def search_calc_logic(self, keyword: str) -> dict:
        """
        搜索CalcModules中的计算逻辑
        
        返回：
        {
            'found': True,
            'locations': [
                {
                    'file': 'CalcTriggers.lua',
                    'line': 41,
                    'function': 'isTriggered',
                    'context': 'return skill.skillTypes[SkillType.Triggered]'
                }
            ]
        }
        """
        results = []
        
        modules_dir = self.pob_path / 'Modules'
        for lua_file in modules_dir.glob('Calc*.lua'):
            matches = self._search_in_file(
                lua_file,
                keyword,
                context_lines=10,
                extract_function=True
            )
            results.extend(matches)
        
        return {
            'found': len(results) > 0,
            'locations': results
        }
    
    def verify_implication(self, source: str, target: str) -> dict:
        """
        验证隐含关系
        
        返回：
        {
            'status': 'verified' | 'pending' | 'rejected',
            'confidence': float,
            'evidence': {...},
            'counter_examples': [...]
        }
        """
        evidence_list = []
        counter_examples = []
        
        # 策略1: 搜索stat定义
        stat_result = self.search_stat_definition(target)
        if stat_result['found']:
            # 检查stat是否在source类型的技能中
            for loc in stat_result['locations']:
                if self._has_skilltype(loc['skill'], source):
                    evidence_list.append({
                        'type': 'stat_definition',
                        'strength': 1.0,
                        'source': loc
                    })
        
        # 策略2: 搜索约束关系
        constraint_result = self.search_skilltype_constraint(source)
        if constraint_result['found']:
            # 检查是否排除了某些能力
            if 'Triggered' in str(constraint_result['excluded_by']):
                evidence_list.append({
                    'type': 'constraint',
                    'strength': 0.8,
                    'source': constraint_result
                })
        
        # 策略3: 搜索计算逻辑
        calc_result = self.search_calc_logic(source)
        if calc_result['found']:
            evidence_list.append({
                'type': 'calc_logic',
                'strength': 0.7,
                'source': calc_result
            })
        
        # 策略4: 检查反例
        counter_examples = self._find_counter_examples(source, target)
        
        # 计算置信度
        if counter_examples:
            return {
                'status': 'rejected',
                'confidence': 0.0,
                'evidence': evidence_list,
                'counter_examples': counter_examples
            }
        elif evidence_list:
            max_strength = max(e['strength'] for e in evidence_list)
            return {
                'status': 'verified' if max_strength >= 0.8 else 'pending',
                'confidence': max_strength,
                'evidence': evidence_list
            }
        else:
            return {
                'status': 'pending',
                'confidence': 0.3,
                'evidence': None
            }
```

---

## 模式发现机制

### 从关联图发现潜在模式

```python
class PatternDiscoverer:
    """模式发现器"""
    
    def __init__(self, graph_db_path: str):
        self.graph = AttributeGraph(graph_db_path)
    
    def discover_type_property_patterns(self) -> List[dict]:
        """
        发现类型-属性模式
        
        返回：
        [
            {
                'pattern': 'Hazard -> DoesNotUseEnergy',
                'support': 0.7,  # 70%的Hazard类型有此属性
                'examples': [...],
                'counter_examples': [...]
            }
        ]
        """
        patterns = []
        
        # 获取所有类型节点
        type_nodes = self.graph.get_nodes_by_type(NodeType.TYPE_NODE)
        
        for type_node in type_nodes:
            # 获取所有拥有此类型的实体
            entities = self.graph.get_reverse_neighbors(
                type_node['id'], 
                edge_type='has_type'
            )
            
            # 统计这些实体的共同属性
            property_counts = Counter()
            for entity in entities:
                # 获取实体的stats
                stats = self.graph.get_neighbors(
                    entity['id'],
                    edge_type='has_stat'
                )
                for stat in stats:
                    property_counts[stat['id']] += 1
            
            # 发现高频属性（超过阈值的）
            total_entities = len(entities)
            for prop_id, count in property_counts.items():
                support = count / total_entities
                
                if support >= 0.7:  # 70%支持度
                    patterns.append({
                        'source_type': type_node['id'],
                        'target_property': prop_id,
                        'support': support,
                        'positive_examples': count,
                        'negative_examples': total_entities - count
                    })
        
        return patterns
    
    def discover_causal_patterns(self) -> List[dict]:
        """
        发现因果模式
        
        返回：
        [
            {
                'pattern': 'MetaTrigger -> produces -> Triggered',
                'confidence': 1.0,
                'evidence': [...]
            }
        ]
        """
        patterns = []
        
        # 查找 produces 边
        produces_edges = self.graph.get_edges_by_type('produces')
        
        for edge in produces_edges:
            # 分析触发机制和标签的关系
            trigger_mech = edge['source']
            label = edge['target']
            
            # 查找使用此触发机制的实体
            entities = self.graph.get_reverse_neighbors(
                trigger_mech,
                edge_type='triggers_via'
            )
            
            # 验证这些实体是否都有目标标签
            verified_count = 0
            for entity in entities:
                types = self.graph.get_neighbors(
                    entity['id'],
                    edge_type='has_type'
                )
                if any(t['id'] == label for t in types):
                    verified_count += 1
            
            confidence = verified_count / len(entities) if entities else 0
            
            patterns.append({
                'trigger_mechanism': trigger_mech,
                'label': label,
                'confidence': confidence,
                'verified_count': verified_count,
                'total_count': len(entities)
            })
        
        return patterns
    
    def discover_bypass_patterns(self) -> List[dict]:
        """
        发现绕过模式
        
        返回：
        [
            {
                'constraint': 'EnergyCycleLimit',
                'bypass_entities': [...],
                'common_features': {...}
            }
        ]
        """
        patterns = []
        
        # 查找所有约束节点
        constraints = self.graph.get_nodes_by_type(NodeType.CONSTRAINT)
        
        for constraint in constraints:
            # 查找绕过此约束的实体
            bypass_entities = self.graph.get_reverse_neighbors(
                constraint['id'],
                edge_type='bypasses'
            )
            
            if len(bypass_entities) < 2:
                continue  # 至少需要2个例子才能发现模式
            
            # 分析共同特征
            all_features = []
            for entity in bypass_entities:
                features = self._extract_features(entity['id'])
                all_features.append(features)
            
            # 找到共同特征
            common_features = self._find_common_features(all_features)
            
            if common_features:
                patterns.append({
                    'constraint': constraint['id'],
                    'bypass_count': len(bypass_entities),
                    'common_features': common_features,
                    'bypass_entities': [e['id'] for e in bypass_entities]
                })
        
        return patterns
```

---

## 证据强度评估

### 证据类型与强度

```
┌─────────────────────────────────────────────────────┐
│              证据强度评估标准                        │
├─────────────────────────────────────────────────────┤
│                                                     │
│  证据类型              │ 强度 │ 说明                │
│  ─────────────────────────────────────────────────  │
│  explicit_stat         │ 1.0  │ 明确的stat定义      │
│  explicit_code         │ 1.0  │ 明确的代码逻辑      │
│  skilltype_constraint  │ 0.9  │ skillTypes约束      │
│  calc_logic            │ 0.8  │ 计算逻辑推断        │
│  pattern_majority      │ 0.7  │ 大多数案例符合      │
│  pattern_minority      │ 0.5  │ 少数案例符合        │
│  analogy               │ 0.3  │ 类比推理            │
│  user_input            │ 0.5  │ 用户输入（待验证）  │
│                                                     │
└─────────────────────────────────────────────────────┘
```

### 综合评估逻辑

```python
class EvidenceEvaluator:
    """证据评估器"""
    
    def evaluate_evidence_set(self, evidence_list: List[dict]) -> dict:
        """
        评估证据集合
        
        返回：
        {
            'status': 'verified' | 'pending' | 'rejected',
            'confidence': float,
            'reasoning': str
        }
        """
        if not evidence_list:
            return {
                'status': 'pending',
                'confidence': 0.0,
                'reasoning': '无证据'
            }
        
        # 分离支持和反对证据
        supporting = [e for e in evidence_list if e.get('strength', 0) > 0]
        opposing = [e for e in evidence_list if e.get('strength', 0) < 0]
        
        # 计算综合置信度
        if opposing:
            # 有反对证据
            return {
                'status': 'rejected',
                'confidence': 0.0,
                'reasoning': f'发现 {len(opposing)} 个反例'
            }
        
        # 计算支持证据的综合强度
        if not supporting:
            return {
                'status': 'pending',
                'confidence': 0.0,
                'reasoning': '无支持证据'
            }
        
        # 加权平均
        total_weight = sum(e['strength'] for e in supporting)
        weighted_confidence = total_weight / len(supporting)
        
        # 确定状态
        if weighted_confidence >= 0.8:
            status = 'verified'
        elif weighted_confidence >= 0.5:
            status = 'pending'
        else:
            status = 'hypothesis'
        
        return {
            'status': status,
            'confidence': weighted_confidence,
            'reasoning': self._generate_reasoning(supporting)
        }
```

---

## 边界情况处理

### 情况1: 反例处理

```python
def handle_counter_example(pattern: dict, counter_example: dict):
    """
    处理反例
    
    策略：
    1. 记录反例
    2. 降低模式置信度
    3. 标记为需要条件限定
    """
    # 检查是否可以添加条件限定
    conditions = find_differentiating_conditions(
        pattern['positive_examples'],
        [counter_example]
    )
    
    if conditions:
        # 可以通过条件限定来保留模式
        return {
            'action': 'add_condition',
            'condition': conditions,
            'new_pattern': f"{pattern['source']} (when {conditions}) -> {pattern['target']}"
        }
    else:
        # 无法限定，拒绝模式
        return {
            'action': 'reject',
            'reason': '无法找到有效的条件限定'
        }
```

### 情况2: 冲突证据处理

```python
def handle_conflicting_evidence(evidence_list: List[dict]):
    """
    处理冲突证据
    
    策略：
    1. 按证据强度排序
    2. 强证据优先
    3. 记录冲突情况
    """
    # 按强度排序
    sorted_evidence = sorted(
        evidence_list,
        key=lambda e: abs(e['strength']),
        reverse=True
    )
    
    # 取最强证据
    strongest = sorted_evidence[0]
    
    # 检查是否有冲突
    conflicts = [
        e for e in sorted_evidence[1:]
        if e['conclusion'] != strongest['conclusion']
    ]
    
    if conflicts:
        return {
            'status': 'pending',
            'confidence': strongest['strength'] * 0.8,  # 降低置信度
            'reasoning': f'存在冲突证据，采用最强证据（强度{strongest["strength"]}）',
            'conflicts': conflicts
        }
    else:
        return {
            'status': 'verified' if strongest['strength'] >= 0.8 else 'pending',
            'confidence': strongest['strength'],
            'reasoning': '证据一致'
        }
```

### 情况3: 缺失证据处理

```python
def handle_missing_evidence(pattern: dict):
    """
    处理缺失证据
    
    策略：
    1. 标记为待确认
    2. 记录搜索路径
    3. 提供用户提示
    """
    return {
        'status': 'pending',
        'confidence': 0.3,
        'search_performed': True,
        'search_paths': [
            'Data/Skills/*.lua',
            'Modules/Calc*.lua'
        ],
        'user_hint': f'未找到 "{pattern["source"]} -> {pattern["target"]}" 的明确证据',
        'suggest_actions': [
            '手动验证游戏机制',
            '查看社区讨论',
            '咨询有经验的玩家'
        ]
    }
```

---

## 性能优化策略

### 缓存机制

```python
class VerificationCache:
    """验证结果缓存"""
    
    def __init__(self, cache_db_path: str):
        self.conn = sqlite3.connect(cache_db_path)
        self._init_cache_table()
    
    def get_cached_verification(self, source: str, target: str) -> Optional[dict]:
        """获取缓存的验证结果"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT status, confidence, evidence, verified_at
            FROM verification_cache
            WHERE source = ? AND target = ?
        ''', (source, target))
        
        row = cursor.fetchone()
        if row:
            return {
                'status': row[0],
                'confidence': row[1],
                'evidence': json.loads(row[2]) if row[2] else None,
                'verified_at': row[3]
            }
        return None
    
    def cache_verification(self, source: str, target: str, result: dict):
        """缓存验证结果"""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO verification_cache
            (source, target, status, confidence, evidence, verified_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            source,
            target,
            result['status'],
            result['confidence'],
            json.dumps(result.get('evidence'), ensure_ascii=False),
            datetime.now().isoformat()
        ))
        self.conn.commit()
```

### 批量验证

```python
class BatchVerifier:
    """批量验证器"""
    
    def verify_patterns_batch(self, patterns: List[dict]) -> List[dict]:
        """
        批量验证模式
        
        优化：
        1. 合并相同的搜索
        2. 复用中间结果
        3. 并行处理
        """
        results = []
        
        # 按source分组
        by_source = defaultdict(list)
        for pattern in patterns:
            by_source[pattern['source']].append(pattern)
        
        # 对每个source进行批量搜索
        for source, pattern_list in by_source.items():
            # 一次性搜索source相关的所有代码
            source_code_cache = self.searcher.preload_source_code(source)
            
            for pattern in pattern_list:
                # 在缓存的代码中搜索target
                result = self.searcher.verify_in_cache(
                    source_code_cache,
                    pattern['target']
                )
                results.append(result)
        
        return results
```

---

## 用户交互设计

### 命令行接口

```bash
# 查看待确认知识列表
python knowledge_manager.py --list-pending

# 输出：
# ╭────────────────────────────────────────────────╮
# │            待确认知识列表                       │
# ├────────────────────────────────────────────────┤
# │                                                │
# │ [1] Hazard → DoesNotUseEnergy                  │
# │     置信度: 0.5                                │
# │     发现时间: 2026-03-11 10:30                 │
# │     证据: 基于TrailOfCaltropsPlayer推断        │
# │                                                │
# │ [2] SpearfieldPlayer → BypassesEnergyCycle     │
# │     置信度: 0.5                                │
# │     发现时间: 2026-03-11 10:35                 │
# │     证据: 基于相似性推断                        │
# │                                                │
# ╰────────────────────────────────────────────────╯

# 确认某个知识
python knowledge_manager.py --confirm 1

# 拒绝某个知识
python knowledge_manager.py --reject 2

# 提供证据
python knowledge_manager.py --confirm 1 --evidence "act_dex.lua:9596"
```

### 交互式确认流程

```python
def interactive_confirmation(pending_list: List[dict]):
    """
    交互式确认流程
    
    用户可以：
    1. 查看详细信息
    2. 查看POB代码证据
    3. 确认/拒绝/跳过
    4. 提供额外证据
    """
    for item in pending_list:
        print(f"\n{'='*60}")
        print(f"知识: {item['source']} → {item['target']}")
        print(f"置信度: {item['confidence']}")
        print(f"发现方式: {item['discovery_method']}")
        
        # 显示已有证据
        if item.get('evidence'):
            print("\n已发现的证据:")
            for e in item['evidence']:
                print(f"  - {e['type']}: {e.get('source', 'N/A')}")
        
        # 用户选择
        choice = input("\n选择: [c]确认 [r]拒绝 [s]跳过 [e]提供证据 [d]详情: ")
        
        if choice == 'c':
            confirm_knowledge(item['id'])
            print("✓ 已确认")
        elif choice == 'r':
            reject_knowledge(item['id'])
            print("✗ 已拒绝")
        elif choice == 'e':
            evidence = input("请输入证据（文件:行号 或 描述）: ")
            confirm_knowledge(item['id'], evidence)
            print("✓ 已确认（附带证据）")
        elif choice == 'd':
            show_detailed_info(item)
            # 重新询问
            continue
        else:
            print("→ 已跳过")
```

---

## 状态转换图

```
┌─────────────────────────────────────────────────────────────┐
│                    知识状态转换图                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│                     ┌──────────────┐                        │
│                     │   发现新模式  │                        │
│                     └──────┬───────┘                        │
│                            │                                │
│              ┌─────────────┼─────────────┐                  │
│              │             │             │                  │
│              ▼             ▼             ▼                  │
│        ┌─────────┐   ┌─────────┐   ┌──────────┐             │
│        │verified │   │ pending │   │hypothesis│             │
│        └────┬────┘   └────┬────┘   └────┬─────┘             │
│             │             │             │                   │
│             │      ┌──────┴──────┐      │                   │
│             │      │             │      │                   │
│             │      ▼             ▼      │                   │
│             │  用户确认      用户拒绝   │                   │
│             │      │             │      │                   │
│             │      │             ▼      │                   │
│             │      │      ┌──────────┐  │                   │
│             │      │      │ rejected │  │                   │
│             │      │      └──────────┘  │                   │
│             │      │                    │                   │
│             │      └────────────────────┘                   │
│             │                  │                            │
│             └──────────────────┘                            │
│                        │                                    │
│                        ▼                                    │
│                  ┌──────────┐                               │
│                  │ 最终状态  │                               │
│                  └──────────┘                               │
│                                                             │
│  转换条件：                                                  │
│  pending → verified: 用户确认 或 发现新证据（强度>=0.8）     │
│  pending → rejected: 用户拒绝 或 发现反例                   │
│  hypothesis → pending: 发现支持证据                         │
│  hypothesis → rejected: 发现反例 或 用户拒绝                │
│  verified → rejected: 发现反例（需要用户确认）              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 与现有系统的集成点

### 集成点1: init_knowledge_base.py

```python
# 修改前
def build_property_layer(graph_db_path: str):
    type_property_mappings = {
        'Hazard': ['DoesNotUseEnergy'],  # 硬编码
    }
    # ...

# 修改后
def build_property_layer(graph_db_path: str, pob_path: str):
    # 发现模式
    discoverer = PatternDiscoverer(graph_db_path)
    patterns = discoverer.discover_type_property_patterns()
    
    # 验证模式
    verifier = KnowledgeVerifier(pob_path)
    for pattern in patterns:
        result = verifier.verify_implication(
            pattern['source_type'],
            pattern['target_property']
        )
        
        # 创建边（带验证状态）
        create_edge_with_verification(
            source=pattern['source_type'],
            target=pattern['target_property'],
            status=result['status'],
            confidence=result['confidence'],
            evidence=result.get('evidence')
        )
```

### 集成点2: heuristic_discovery.py

```python
# 修改前
def discover_bypass_paths(constraint: str):
    # 直接创建边
    create_bypass_edge(entity, constraint)
    return

# 修改后
def discover_bypass_paths(constraint: str):
    # 发现候选
    candidates = find_bypass_candidates(constraint)
    
    results = {
        'verified': [],
        'pending': [],
        'rejected': []
    }
    
    for candidate in candidates:
        # 验证
        result = verify_bypass_in_pob(candidate, constraint)
        
        if result['status'] == 'verified':
            create_bypass_edge(
                candidate, 
                constraint,
                status='verified',
                evidence=result['evidence']
            )
            results['verified'].append(candidate)
        elif result['status'] == 'pending':
            create_bypass_edge(
                candidate,
                constraint,
                status='pending',
                confidence=result['confidence']
            )
            results['pending'].append(candidate)
        else:
            results['rejected'].append(candidate)
    
    return results
```

### 集成点3: heuristic_query.py

```python
# 修改前
def query_bypasses(constraint: str):
    return query_edges(target=constraint, edge_type='bypasses')

# 修改后
def query_bypasses(constraint: str, include_pending: bool = True):
    verified = query_edges(
        target=constraint,
        edge_type='bypasses',
        status='verified'
    )
    
    pending = []
    if include_pending:
        pending = query_edges(
            target=constraint,
            edge_type='bypasses',
            status='pending'
        )
        
        # 尝试验证pending边
        for edge in pending:
            result = verify_bypass_in_pob(edge['source'], constraint)
            if result['status'] == 'verified':
                update_edge_status(edge['id'], 'verified')
                verified.append(edge)
                pending.remove(edge)
    
    return {
        'verified': verified,
        'pending': pending
    }
```

---

## 总结

### 完整的知识生命周期

```
发现 → 验证 → 分类 → 使用 → 反馈 → 更新

1. 发现：从关联图模式或用户输入发现潜在知识
2. 验证：在POB代码中搜索证据
3. 分类：根据证据强度分为 verified/pending/hypothesis/rejected
4. 使用：在推理中使用（根据状态调整权重）
5. 反馈：用户确认或拒绝
6. 更新：根据反馈更新状态和置信度
```

### 关键设计决策

1. **自动验证优先**：减少人工维护负担
2. **状态透明**：用户清楚知道每条知识的可靠性
3. **延迟确认**：不中断交互，后续再处理
4. **证据追溯**：每条知识都有证据链
5. **持续进化**：pending → verified 的正循环
