# pending数据的角色机制详解

## 核心洞察

pending数据在不同推理阶段扮演**不同角色**，其权重和作用方式需要**动态调整**。

---

## 角色定义矩阵

```
┌─────────────────────────────────────────────────────────────────────┐
│                    pending数据角色矩阵                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  推理阶段      │ 角色        │ 权重  │ 作用机制      │ 输出影响    │
│  ─────────────────────────────────────────────────────────────────  │
│  查询阶段      │ 候选结果    │ 0.5   │ 降级返回      │ 分层显示    │
│  发现阶段      │ 探索线索    │ 0.3   │ 引导搜索      │ 生成假设    │
│  验证阶段      │ 待验证项    │ N/A   │ 主动验证      │ 状态转换    │
│  扩散阶段      │ 不参与      │ 0.0   │ 阻断扩散      │ 无         │
│  因果推理      │ 弱证据      │ 0.2   │ 支持弱推理链  │ 降低置信度  │
│  组合推理      │ 不参与      │ 0.0   │ 阻断组合      │ 无         │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 详细角色解析

### 角色1: 查询阶段的"候选结果"

```python
def query_bypass(constraint: str) -> dict:
    """
    查询绕过路径
    
    pending数据角色：作为候选结果返回，但标记状态
    """
    
    # Step 1: 收集所有候选
    verified_edges = query_edges(
        target=constraint,
        edge_type='bypasses',
        status='verified'
    )
    
    pending_edges = query_edges(
        target=constraint,
        edge_type='bypasses',
        status='pending'
    )
    
    # Step 2: 对pending边进行验证尝试
    upgraded = []
    still_pending = []
    
    for edge in pending_edges:
        # 尝试在POB代码中找证据
        evidence = search_pob_evidence(edge['source'], constraint)
        
        if evidence and evidence['strength'] >= 0.8:
            # 升级为verified
            update_edge_status(edge['id'], 'verified', evidence)
            upgraded.append({
                **edge,
                'status': 'verified',
                'confidence': 1.0,
                'evidence': evidence
            })
        else:
            # 保持pending
            still_pending.append({
                **edge,
                'status': 'pending',
                'confidence': edge['confidence'] * 0.5,  # 降低置信度
                'upgrade_attempted': True
            })
    
    # Step 3: 组合结果
    all_verified = verified_edges + upgraded
    
    return {
        'verified': all_verified,
        'pending': still_pending,
        'hypothesis': [],  # 查询阶段不返回假设
        'summary': {
            'verified_count': len(all_verified),
            'pending_count': len(still_pending),
            'upgraded_count': len(upgraded)
        }
    }
```

**关键点**：
- pending边作为**候选结果**返回
- 用户可以看到，但知道这是**待确认**的
- 系统会**主动尝试验证**
- 验证成功则**自动升级**

---

### 角色2: 发现阶段的"探索线索"

```python
def discover_bypass_paths(constraint: str) -> dict:
    """
    发现绕过路径
    
    pending数据角色：作为探索线索，引导搜索方向
    """
    
    # Step 1: 从verified边收集关键特征
    verified_edges = query_edges(
        target=constraint,
        edge_type='bypasses',
        status='verified'
    )
    
    key_features = []
    for edge in verified_edges:
        features = extract_features(edge['source'])
        key_features.append(features)
    
    # Step 2: 从pending边收集潜在特征
    pending_edges = query_edges(
        target=constraint,
        edge_type='bypasses',
        status='pending'
    )
    
    potential_features = []
    for edge in pending_edges:
        # 提取特征，但标记为"待验证"
        features = extract_features(edge['source'])
        features['from_pending'] = True
        features['confidence'] = edge['confidence'] * 0.3  # 降低权重
        potential_features.append(features)
    
    # Step 3: 合并特征，但区分优先级
    all_features = {
        'high_confidence': key_features,      # 来自verified
        'exploratory': potential_features     # 来自pending
    }
    
    # Step 4: 引导搜索
    candidates = []
    
    # 优先：基于verified特征搜索
    for features in all_features['high_confidence']:
        similar = find_similar_entities(features, threshold=0.7)
        for entity in similar:
            # 验证新发现的实体
            result = verify_bypass_in_pob(entity, constraint)
            candidates.append({
                'entity': entity,
                'status': result['status'],
                'confidence': result['confidence'],
                'source': 'verified_feature'
            })
    
    # 次优：基于pending特征探索（降低权重）
    for features in all_features['exploratory']:
        # 只有在没有verified特征时才使用
        if not candidates:
            similar = find_similar_entities(features, threshold=0.7)
            for entity in similar:
                result = verify_bypass_in_pob(entity, constraint)
                if result['status'] == 'verified':
                    candidates.append({
                        'entity': entity,
                        'status': 'verified',
                        'confidence': result['confidence'] * 0.7,  # 降低
                        'source': 'pending_feature'
                    })
                else:
                    # 生成假设，而非pending边
                    candidates.append({
                        'entity': entity,
                        'status': 'hypothesis',
                        'confidence': 0.2,
                        'source': 'pending_feature',
                        'note': '基于待确认知识的推断'
                    })
    
    return {
        'candidates': candidates,
        'sources': {
            'verified_based': len([c for c in candidates if c['source'] == 'verified_feature']),
            'pending_based': len([c for c in candidates if c['source'] == 'pending_feature'])
        }
    }
```

**关键点**：
- pending数据**不直接参与推理**
- 而是作为**探索方向提示**
- 优先级**低于verified数据**
- 可能生成**hypothesis而非pending**

---

### 角色3: 验证阶段的"待验证项"

```python
class PendingValidator:
    """pending边验证器"""
    
    def __init__(self, graph_db_path: str, pob_path: str):
        self.graph = AttributeGraph(graph_db_path)
        self.searcher = POBCodeSearcher(pob_path)
    
    def validate_all_pending(self) -> dict:
        """
        验证所有pending边
        
        返回：
        {
            'upgraded': [...],    # 升级为verified
            'rejected': [...],    # 发现反例，拒绝
            'still_pending': [...] # 无法验证，保持pending
        }
        """
        results = {
            'upgraded': [],
            'rejected': [],
            'still_pending': []
        }
        
        # 获取所有pending边
        pending_edges = self.graph.query_edges(status='pending')
        
        for edge in pending_edges:
            # 验证
            result = self.searcher.verify_implication(
                edge['source'],
                edge['target']
            )
            
            if result['status'] == 'verified':
                # 升级
                self.graph.update_edge(
                    edge['id'],
                    status='verified',
                    confidence=result['confidence'],
                    evidence=result['evidence']
                )
                results['upgraded'].append({
                    'edge': edge,
                    'evidence': result['evidence']
                })
            
            elif result['status'] == 'rejected':
                # 拒绝
                self.graph.update_edge(
                    edge['id'],
                    status='rejected',
                    evidence=result.get('counter_examples')
                )
                results['rejected'].append({
                    'edge': edge,
                    'counter_examples': result.get('counter_examples')
                })
            
            else:
                # 保持pending
                results['still_pending'].append(edge)
        
        return results
    
    def validate_by_priority(self, priority: str = 'auto') -> dict:
        """
        按优先级验证pending边
        
        优先级策略：
        1. 被多次引用的边优先
        2. 近期创建的边优先
        3. 用户标记为重要的边优先
        """
        pending_edges = self.graph.query_edges(status='pending')
        
        # 计算优先级分数
        scored_edges = []
        for edge in pending_edges:
            score = 0
            
            # 被引用次数
            ref_count = count_edge_references(edge['id'])
            score += ref_count * 10
            
            # 创建时间（越近越高）
            age_days = (datetime.now() - edge['created_at']).days
            score += max(0, 30 - age_days)
            
            # 用户标记
            if edge.get('user_marked_important'):
                score += 50
            
            scored_edges.append({
                'edge': edge,
                'priority_score': score
            })
        
        # 按分数排序
        scored_edges.sort(key=lambda x: x['priority_score'], reverse=True)
        
        # 验证高优先级边
        if priority == 'auto':
            # 验证前10个或分数>50的
            to_validate = [
                e['edge'] for e in scored_edges 
                if e['priority_score'] > 50 or scored_edges.index(e) < 10
            ]
        else:
            to_validate = [e['edge'] for e in scored_edges]
        
        # 批量验证
        results = {
            'upgraded': [],
            'rejected': [],
            'still_pending': []
        }
        
        for edge in to_validate:
            result = self.searcher.verify_implication(edge['source'], edge['target'])
            # ... (同上)
        
        return results
```

**关键点**：
- pending边可以**批量验证**
- 按优先级处理，**高影响边优先**
- 可能**自动升级或拒绝**
- 减少**人工确认负担**

---

### 角色4: 扩散阶段的"阻断器"

```python
def diffuse_from_bypass(known_bypass: dict) -> List[dict]:
    """
    从已知绕过边扩散
    
    pending数据角色：不参与扩散（阻断）
    """
    
    # 只有verified边才能作为扩散源
    if known_bypass['status'] != 'verified':
        return []  # 直接返回空，不扩散
    
    # 提取特征
    features = extract_features(known_bypass['source'])
    
    # 找相似实体
    similar_entities = find_similar_entities(features, threshold=0.7)
    
    results = []
    for entity, similarity in similar_entities:
        # 验证
        evidence = verify_bypass_in_pob(entity, known_bypass['constraint'])
        
        if evidence['status'] == 'verified':
            # 创建verified边
            create_edge(
                source=entity,
                target=known_bypass['constraint'],
                edge_type='bypasses',
                status='verified',
                confidence=similarity,
                evidence=evidence,
                discovery_method='diffusion',
                parent_edge=known_bypass['id']
            )
            results.append({
                'entity': entity,
                'status': 'verified',
                'similarity': similarity
            })
        elif evidence['status'] == 'pending':
            # 创建pending边？NO！创建hypothesis
            # 为什么？因为扩散本身是弱推理
            # 加上pending源，置信度太低
            create_edge(
                source=entity,
                target=known_bypass['constraint'],
                edge_type='bypasses',
                status='hypothesis',  # 注意：是hypothesis，不是pending
                confidence=similarity * 0.2,  # 大幅降低
                discovery_method='diffusion_from_verified',
                parent_edge=known_bypass['id'],
                note='扩散发现，需要验证'
            )
            results.append({
                'entity': entity,
                'status': 'hypothesis',
                'similarity': similarity
            })
    
    return results
```

**关键点**：
- pending边**不能作为扩散源**
- 扩散发现的新边可能是**hypothesis而非pending**
- 避免**错误传播**

---

### 角色5: 因果推理的"弱证据"

```python
def infer_causal_chain(start_entity: str, end_property: str) -> dict:
    """
    因果推理链
    
    pending数据角色：作为弱证据，支持弱推理链
    """
    
    # 寻找推理路径
    paths = find_all_paths(start_entity, end_property)
    
    results = []
    for path in paths:
        # 评估路径中每个边的强度
        edge_strengths = []
        for edge in path:
            if edge['status'] == 'verified':
                edge_strengths.append(1.0)
            elif edge['status'] == 'pending':
                edge_strengths.append(0.2)  # 弱证据
            else:
                edge_strengths.append(0.0)  # hypothesis不参与
        
        # 计算路径总强度
        # 使用乘法：任一边为0则路径为0
        path_strength = 1.0
        for strength in edge_strengths:
            path_strength *= strength
        
        # 或者使用最小值：最弱边决定路径强度
        # path_strength = min(edge_strengths)
        
        # 判断路径有效性
        if path_strength > 0:
            # 至少有一条完整路径
            results.append({
                'path': path,
                'strength': path_strength,
                'status': 'verified' if path_strength >= 0.8 else 'weak'
            })
        else:
            # 路径中有断点
            # 找到断点位置
            breakpoint = find_breakpoint(path)
            results.append({
                'path': path,
                'strength': 0.0,
                'status': 'broken',
                'breakpoint': breakpoint,
                'suggestion': f'需要验证 {breakpoint["source"]} → {breakpoint["target"]}'
            })
    
    return {
        'valid_paths': [r for r in results if r['strength'] > 0],
        'broken_paths': [r for r in results if r['strength'] == 0],
        'weak_paths': [r for r in results if 0 < r['strength'] < 0.8]
    }
```

**关键点**：
- pending边可以**参与因果链**
- 但强度**大幅降低**（0.2）
- 导致整体推理链**置信度降低**
- 可能**断开推理链**（如果有多个pending边）

---

### 角色6: 组合推理的"阻断器"

```python
def discover_combination_rules(entity: str) -> List[dict]:
    """
    发现组合规则
    
    pending数据角色：不参与组合推理（阻断）
    """
    
    # 获取实体的所有关系
    relations = get_entity_relations(entity)
    
    # 只使用verified关系
    verified_relations = [
        r for r in relations
        if r['status'] == 'verified'
    ]
    
    # 发现组合效果
    combinations = []
    for i, rel1 in enumerate(verified_relations):
        for rel2 in verified_relations[i+1:]:
            # 检查是否产生新的效果
            combined_effect = check_combination_effect(rel1, rel2)
            
            if combined_effect:
                # 验证组合效果
                evidence = verify_combination_in_pob(rel1, rel2)
                
                if evidence['status'] == 'verified':
                    combinations.append({
                        'relations': [rel1, rel2],
                        'effect': combined_effect,
                        'status': 'verified',
                        'evidence': evidence
                    })
    
    # 不使用pending关系，避免错误组合
    # pending关系可能本身就不可靠，组合后更不可靠
    
    return combinations
```

**关键点**：
- pending边**不参与组合**
- 组合推理**敏感性高**，错误会放大
- 宁可**漏掉**也不要**错误**

---

## 权重动态调整机制

### 置信度计算

```python
def calculate_effective_confidence(edge: dict) -> float:
    """
    计算边的有效置信度
    
    考虑因素：
    1. 基础置信度（根据状态）
    2. 引用次数（多次验证）
    3. 存续时间（时间检验）
    4. 证据强度
    """
    base_confidence = {
        'verified': 1.0,
        'pending': 0.5,
        'hypothesis': 0.3,
        'rejected': 0.0
    }
    
    confidence = base_confidence[edge['status']]
    
    # 引用次数加成
    ref_count = count_edge_references(edge['id'])
    if ref_count > 5:
        confidence = min(1.0, confidence + 0.1)
    
    # 存续时间加成
    age_days = (datetime.now() - edge['created_at']).days
    if age_days > 30 and edge['status'] == 'pending':
        # 长期pending的知识，降低置信度
        confidence *= 0.8
    
    # 证据强度修正
    if edge.get('evidence'):
        evidence_strength = edge['evidence'].get('strength', 0)
        confidence = (confidence + evidence_strength) / 2
    
    return confidence
```

### 状态转换触发器

```python
class StatusTransitionTrigger:
    """状态转换触发器"""
    
    def check_upgrade_conditions(self, edge: dict) -> bool:
        """
        检查是否满足升级条件
        
        pending → verified 条件：
        1. 找到明确POB代码证据
        2. 被多次成功引用
        3. 用户明确确认
        """
        # 条件1：找到证据
        if edge.get('evidence') and edge['evidence']['strength'] >= 0.8:
            return True
        
        # 条件2：多次成功引用
        ref_count = count_edge_references(edge['id'])
        success_rate = calculate_reference_success_rate(edge['id'])
        if ref_count > 5 and success_rate > 0.8:
            return True
        
        # 条件3：用户确认
        if edge.get('user_confirmed'):
            return True
        
        return False
    
    def check_reject_conditions(self, edge: dict) -> bool:
        """
        检查是否满足拒绝条件
        
        pending → rejected 条件：
        1. 发现明确反例
        2. 用户明确拒绝
        3. 长期无验证且无引用
        """
        # 条件1：发现反例
        if edge.get('counter_examples'):
            return True
        
        # 条件2：用户拒绝
        if edge.get('user_rejected'):
            return True
        
        # 条件3：长期无验证
        age_days = (datetime.now() - edge['created_at']).days
        ref_count = count_edge_references(edge['id'])
        if age_days > 90 and ref_count == 0:
            return True
        
        return False
```

---

## 用户交互层

### pending知识列表视图

```
┌─────────────────────────────────────────────────────────────┐
│                  待确认知识列表                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  筛选：[全部] [高优先级] [近期] [可验证]                    │
│  排序：[优先级] [创建时间] [引用次数]                       │
│                                                             │
│  ─────────────────────────────────────────────────────────  │
│                                                             │
│  [1] Hazard → DoesNotUseEnergy                              │
│      置信度: 50%                                            │
│      发现时间: 2026-03-11                                   │
│      引用次数: 3                                            │
│      证据: 基于TrailOfCaltropsPlayer推断                   │
│                                                             │
│      [查看详情] [验证] [拒绝] [提供证据]                    │
│                                                             │
│  [2] SpearfieldPlayer → BypassesEnergyCycle                 │
│      置信度: 50%                                            │
│      发现时间: 2026-03-11                                   │
│      引用次数: 0                                            │
│      证据: 基于相似性推断                                   │
│                                                             │
│      [查看详情] [验证] [拒绝] [提供证据]                    │
│                                                             │
│  ─────────────────────────────────────────────────────────  │
│                                                             │
│  [批量验证] [批量拒绝] [导出] [刷新]                        │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 验证详情视图

```
┌─────────────────────────────────────────────────────────────┐
│              知识详情：Hazard → DoesNotUseEnergy             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  状态：pending                                              │
│  置信度：50%                                                │
│  发现方式：模式发现                                         │
│                                                             │
│  ─────────────────────────────────────────────────────────  │
│                                                             │
│  支持证据：                                                 │
│    ✗ 未找到POB代码中的直接证据                              │
│    ✓ TrailOfCaltropsPlayer有相关stat                       │
│    ✗ SpearfieldPlayer无相关stat                            │
│                                                             │
│  反例：                                                     │
│    ⚠ SpearfieldPlayer (Hazard类型，但无能量相关stat)       │
│                                                             │
│  推理链：                                                   │
│    Hazard → TrailOfCaltropsPlayer → stat                   │
│                                     ↓                       │
│                    generic_ongoing_trigger_does_not_use_energy │
│                                                             │
│  建议：                                                     │
│    这个推断可能过于宽泛，建议限定条件：                     │
│    "有 generic_ongoing_trigger_does_not_use_energy stat     │
│     的 Hazard 技能不使用能量系统"                           │
│                                                             │
│  ─────────────────────────────────────────────────────────  │
│                                                             │
│  [确认] [拒绝] [修改条件] [跳过]                            │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 性能优化：pending数据索引

```sql
-- 创建pending视图，加速查询
CREATE VIEW pending_knowledge_view AS
SELECT 
    e.id,
    e.source_node,
    e.target_node,
    e.edge_type,
    e.confidence,
    e.created_at,
    e.evidence_type,
    e.discovery_method,
    -- 计算优先级分数
    (
        (SELECT COUNT(*) FROM graph_edges e2 WHERE e2.parent_edge_id = e.id) * 10 +
        MAX(0, 30 - CAST((julianday('now') - julianday(e.created_at)) AS INTEGER)) +
        CASE WHEN e.attributes LIKE '%user_marked_important%' THEN 50 ELSE 0 END
    ) AS priority_score
FROM graph_edges e
WHERE e.status = 'pending'
ORDER BY priority_score DESC;

-- 创建索引加速状态查询
CREATE INDEX idx_edges_status_priority ON graph_edges(status, created_at DESC);
```

---

## 总结

### pending数据的核心角色

```
┌─────────────────────────────────────────────────────┐
│           pending数据的核心价值                     │
├─────────────────────────────────────────────────────┤
│                                                     │
│  1. 探索引导：告诉系统"往哪里看"                    │
│     └─ 降低盲目搜索成本                            │
│                                                     │
│  2. 知识进化：pending → verified 的正循环           │
│     └─ 系统可以持续学习和改进                      │
│                                                     │
│  3. 透明性：用户清楚知道哪些不确定                 │
│     └─ 建立信任关系                                │
│                                                     │
│  4. 灵活性：用户可以选择何时参与验证               │
│     └─ 流畅的交互体验                              │
│                                                     │
│  关键：明确边界，不该用的地方坚决不用              │
│                                                     │
└─────────────────────────────────────────────────────┘
```

### 使用原则

```
可以用的地方：
  ✓ 查询结果（标记状态）
  ✓ 发现线索（降低权重）
  ✓ 验证对象（主动验证）
  ✓ 因果链（弱证据）

不可以用的地方：
  ✗ 扩散源（阻断）
  ✗ 组合推理（阻断）
  ✗ 高置信度决策（阻断）
```
