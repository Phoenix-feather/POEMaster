# 知识冲突解决机制

## 问题定义

### 冲突类型

```
┌─────────────────────────────────────────────────────┐
│                知识冲突类型                          │
├─────────────────────────────────────────────────────┤
│                                                     │
│  类型1: 直接矛盾                                    │
│    知识A: Hazard → DoesNotUseEnergy                 │
│    知识B: SpearfieldPlayer (Hazard) → UsesEnergy    │
│                                                     │
│  类型2: 推理链冲突                                  │
│    路径1: A → B → C → D (结论: D为真)              │
│    路径2: A → X → Y → D (结论: D为假)              │
│                                                     │
│  类型3: 证据强度冲突                                │
│    证据1: POB代码显示 X (强度0.8)                   │
│    证据2: POB代码显示 not X (强度0.7)               │
│                                                     │
│  类型4: 时间版本冲突                                │
│    旧版本POB: 技能A有属性X                          │
│    新版本POB: 技能A没有属性X                        │
│                                                     │
└─────────────────────────────────────────────────────┘
```

---

## 冲突检测机制

### 检测策略

```python
class ConflictDetector:
    """冲突检测器"""
    
    def detect_direct_contradiction(self) -> List[dict]:
        """
        检测直接矛盾
        
        逻辑：
        1. 找到所有 "type → property" 关系
        2. 检查是否存在相反的property
        """
        conflicts = []
        
        # 获取所有类型-属性关系
        type_property_edges = self.graph.query_edges(edge_type='implies')
        
        # 按source分组
        by_source = defaultdict(list)
        for edge in type_property_edges:
            by_source[edge['source']].append(edge)
        
        # 检查矛盾
        for source, edges in by_source.items():
            properties = [e['target'] for e in edges]
            
            # 检查相反属性
            for prop in properties:
                opposite = self.get_opposite_property(prop)
                if opposite and opposite in properties:
                    conflicts.append({
                        'type': 'direct_contradiction',
                        'source': source,
                        'property1': prop,
                        'property2': opposite,
                        'edges': [
                            e for e in edges 
                            if e['target'] in [prop, opposite]
                        ]
                    })
        
        return conflicts
    
    def detect_inference_conflict(self) -> List[dict]:
        """
        检测推理链冲突
        
        逻辑：
        1. 对每个实体，找所有推理路径
        2. 检查不同路径是否得出相反结论
        """
        conflicts = []
        
        # 获取所有实体
        entities = self.graph.get_nodes_by_type(NodeType.ENTITY)
        
        for entity in entities:
            # 获取所有可达的属性
            properties = self.graph.get_neighbors(entity, edge_type='implies')
            
            # 检查矛盾属性对
            for i, prop1 in enumerate(properties):
                for prop2 in properties[i+1:]:
                    if self.are_contradictory(prop1, prop2):
                        # 找到矛盾，追溯路径
                        path1 = self.graph.find_path(entity['id'], prop1['id'])
                        path2 = self.graph.find_path(entity['id'], prop2['id'])
                        
                        conflicts.append({
                            'type': 'inference_conflict',
                            'entity': entity['id'],
                            'property1': prop1,
                            'property2': prop2,
                            'path1': path1,
                            'path2': path2
                        })
        
        return conflicts
    
    def detect_evidence_conflict(self, edge_id: str) -> Optional[dict]:
        """
        检测证据强度冲突
        
        逻辑：
        1. 收集边的所有证据
        2. 检查是否有矛盾证据
        """
        edge = self.graph.get_edge(edge_id)
        if not edge:
            return None
        
        evidence_list = edge.get('evidence', [])
        if not evidence_list:
            return None
        
        # 分离支持和反对证据
        supporting = []
        opposing = []
        
        for evidence in evidence_list:
            if evidence.get('supports'):
                supporting.append(evidence)
            else:
                opposing.append(evidence)
        
        if supporting and opposing:
            return {
                'type': 'evidence_conflict',
                'edge_id': edge_id,
                'supporting': supporting,
                'opposing': opposing,
                'net_strength': sum(e['strength'] for e in supporting) - 
                               sum(e['strength'] for e in opposing)
            }
        
        return None
    
    def get_opposite_property(self, property: str) -> Optional[str]:
        """获取相反属性"""
        opposites = {
            'DoesNotUseEnergy': 'UsesEnergy',
            'UsesEnergy': 'DoesNotUseEnergy',
            'CannotGenerateEnergyForMeta': 'CanGenerateEnergyForMeta',
            'CanGenerateEnergyForMeta': 'CannotGenerateEnergyForMeta',
            # ... 更多对
        }
        return opposites.get(property)
```

---

## 冲突解决策略

### 策略1: 证据强度仲裁

```python
class EvidenceArbiter:
    """证据仲裁器"""
    
    def resolve_conflict(self, conflict: dict) -> dict:
        """
        根据证据强度解决冲突
        
        优先级：
        1. explicit_stat > code_logic > pattern
        2. 新证据 > 旧证据
        3. 多证据 > 单证据
        """
        # 收集所有证据
        all_evidence = []
        
        for edge in conflict.get('edges', []):
            evidence_list = edge.get('evidence', [])
            for evidence in evidence_list:
                all_evidence.append({
                    'edge_id': edge['id'],
                    'conclusion': edge['target'],  # 属性
                    'evidence': evidence,
                    'strength': self.calculate_evidence_strength(evidence)
                })
        
        # 按结论分组
        by_conclusion = defaultdict(list)
        for ev in all_evidence:
            by_conclusion[ev['conclusion']].append(ev)
        
        # 计算每个结论的总强度
        conclusion_strengths = {}
        for conclusion, evidences in by_conclusion.items():
            # 使用加权平均
            total_weight = sum(e['strength'] for e in evidences)
            weighted_sum = sum(e['strength'] * e['strength'] for e in evidences)
            conclusion_strengths[conclusion] = weighted_sum / total_weight if total_weight > 0 else 0
        
        # 选择最强结论
        strongest_conclusion = max(conclusion_strengths.items(), key=lambda x: x[1])
        
        # 决策
        return {
            'resolution': 'accept',
            'accepted_conclusion': strongest_conclusion[0],
            'strength': strongest_conclusion[1],
            'rejected_conclusions': [
                c for c in conclusion_strengths.keys() 
                if c != strongest_conclusion[0]
            ],
            'reasoning': f"基于证据强度，'{strongest_conclusion[0]}' 获得最高置信度 {strongest_conclusion[1]:.2f}"
        }
```

### 策略2: 条件限定

```python
class ConditionQualifier:
    """条件限定器"""
    
    def resolve_conflict(self, conflict: dict) -> dict:
        """
        通过添加条件限定解决冲突
        
        适用于：
        - 两个结论在不同条件下都成立
        - 无法简单判断哪个正确
        """
        # 找到差异条件
        edge1, edge2 = conflict['edges']
        
        # 提取各自的条件
        conditions1 = self.extract_conditions(edge1)
        conditions2 = self.extract_conditions(edge2)
        
        # 找到不同条件
        diff_conditions = self.find_different_conditions(conditions1, conditions2)
        
        if diff_conditions:
            # 可以通过条件限定解决
            return {
                'resolution': 'qualify',
                'new_rules': [
                    {
                        'rule': f"{conflict['source']} → {edge1['target']} when {diff_conditions['for_edge1']}",
                        'status': 'pending',
                        'note': '添加条件限定'
                    },
                    {
                        'rule': f"{conflict['source']} → {edge2['target']} when {diff_conditions['for_edge2']}",
                        'status': 'pending',
                        'note': '添加条件限定'
                    }
                ],
                'reasoning': '通过条件限定解决矛盾，两条规则在不同条件下都成立'
            }
        else:
            # 无法通过条件限定
            return {
                'resolution': 'escalate',
                'reason': '无法找到有效的条件限定，需要人工判断',
                'suggested_actions': [
                    '手动验证游戏机制',
                    '检查POB代码上下文',
                    '查看技能的实际表现'
                ]
            }
    
    def extract_conditions(self, edge: dict) -> List[str]:
        """提取边的条件"""
        conditions = []
        
        # 从证据中提取
        if edge.get('evidence'):
            for evidence in edge['evidence']:
                if evidence.get('type') == 'stat':
                    # stat本身就是条件
                    conditions.append(f"has_stat_{evidence['content']}")
        
        # 从属性中提取
        if edge.get('attributes'):
            attrs = edge['attributes']
            if attrs.get('condition'):
                conditions.append(attrs['condition'])
        
        return conditions
```

### 策略3: 状态降级

```python
class StatusDowngrader:
    """状态降级器"""
    
    def resolve_conflict(self, conflict: dict) -> dict:
        """
        通过降级状态解决冲突
        
        适用于：
        - 无法确定哪个正确
        - 证据强度相近
        """
        # 将所有冲突边的状态降级为hypothesis
        for edge in conflict['edges']:
            self.graph.update_edge(
                edge['id'],
                status='hypothesis',
                confidence=edge['confidence'] * 0.5,
                conflict_detected=True,
                conflict_reason=str(conflict)
            )
        
        return {
            'resolution': 'downgrade',
            'affected_edges': [e['id'] for e in conflict['edges']],
            'new_status': 'hypothesis',
            'reasoning': '检测到冲突，无法确定正确性，降级为假设状态'
        }
```

---

## 冲突解决决策树

```
发现冲突
    ↓
┌───┴────────────────────────────┐
│                                │
证据强度差异大？                 NO
│                                │
YES                              │
↓                                │
证据强度仲裁                     是否可条件限定？
↓                                │
解决                            ┌─┴─┐
                                │   │
                               YES  NO
                                │   │
                            条件  用户
                            限定  决策
                                │   │
                             ┌─┴───┴─┐
                             │        │
                          pending  手动确认
                             │
                         等待验证
```

---

## 用户决策支持

### 冲突报告格式

```
┌─────────────────────────────────────────────────────────────┐
│                    检测到知识冲突                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  冲突类型：直接矛盾                                          │
│  涉及实体：Hazard                                            │
│                                                             │
│  ─────────────────────────────────────────────────────────  │
│                                                             │
│  矛盾属性：                                                  │
│    ✓ DoesNotUseEnergy (置信度: 50%)                         │
│      证据: TrailOfCaltropsPlayer有相关stat                  │
│      来源: 模式发现                                          │
│                                                             │
│    ✗ UsesEnergy (置信度: 0%)                                │
│      证据: 无                                                │
│      来源: 推断                                              │
│                                                             │
│  ─────────────────────────────────────────────────────────  │
│                                                             │
│  系统建议：                                                  │
│    基于"证据强度"，建议接受: DoesNotUseEnergy               │
│    但发现反例: SpearfieldPlayer                             │
│                                                             │
│  更精确的规则可能是：                                        │
│    "有 generic_ongoing_trigger_does_not_use_energy stat     │
│     的 Hazard 技能不使用能量系统"                           │
│                                                             │
│  ─────────────────────────────────────────────────────────  │
│                                                             │
│  请选择：                                                    │
│    [1] 接受建议                                              │
│    [2] 拒绝建议，保持原样                                    │
│    [3] 使用条件限定                                          │
│    [4] 标记为待验证                                          │
│    [5] 查看详细证据                                          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 冲突监控仪表板

```python
class ConflictDashboard:
    """冲突监控仪表板"""
    
    def generate_report(self) -> dict:
        """生成冲突报告"""
        detector = ConflictDetector(self.graph_db)
        
        # 检测各类冲突
        direct = detector.detect_direct_contradiction()
        inference = detector.detect_inference_conflict()
        
        # 统计
        stats = {
            'total_conflicts': len(direct) + len(inference),
            'direct_contradictions': len(direct),
            'inference_conflicts': len(inference),
            'by_status': {
                'resolved': self.count_resolved(),
                'pending': self.count_pending(),
                'escalated': self.count_escalated()
            }
        }
        
        return {
            'statistics': stats,
            'details': {
                'direct_contradictions': direct[:10],  # 前10个
                'inference_conflicts': inference[:10]
            },
            'recommendations': self.generate_recommendations(direct + inference)
        }
    
    def generate_recommendations(self, conflicts: List[dict]) -> List[str]:
        """生成处理建议"""
        recommendations = []
        
        for conflict in conflicts:
            if conflict['type'] == 'direct_contradiction':
                rec = f"建议验证 '{conflict['source']}' 的属性定义，可能需要条件限定"
            else:
                rec = f"建议检查 '{conflict['entity']}' 的推理链，存在路径冲突"
            
            recommendations.append(rec)
        
        return recommendations
```

---

## 冲突解决的完整流程

```python
def resolve_conflict_workflow(conflict: dict) -> dict:
    """
    完整的冲突解决流程
    """
    # Step 1: 检测冲突类型
    conflict_type = conflict['type']
    
    # Step 2: 尝试自动解决
    if conflict_type == 'direct_contradiction':
        # 尝试证据仲裁
        arbiter = EvidenceArbiter()
        resolution = arbiter.resolve_conflict(conflict)
        
        if resolution['strength'] >= 0.8:
            # 自动接受
            return apply_resolution(resolution)
        
        elif resolution['strength'] >= 0.5:
            # 条件限定
            qualifier = ConditionQualifier()
            resolution = qualifier.resolve_conflict(conflict)
            
            if resolution['resolution'] == 'qualify':
                return apply_resolution(resolution)
    
    # Step 3: 无法自动解决，降级处理
    downgrader = StatusDowngrader()
    resolution = downgrader.resolve_conflict(conflict)
    
    # Step 4: 记录冲突，等待用户决策
    record_conflict_for_review(conflict, resolution)
    
    return {
        'status': 'escalated',
        'resolution': resolution,
        'next_action': 'user_review'
    }
```

---

## 防止冲突的最佳实践

### 1. 知识添加前的检查

```python
def check_before_adding(source: str, target: str, edge_type: str) -> dict:
    """添加前检查"""
    
    # 检查是否存在矛盾边
    opposite = get_opposite_relation(target)
    if opposite:
        existing = query_edge(source, opposite, edge_type)
        if existing:
            return {
                'can_add': False,
                'reason': f'存在矛盾边: {source} → {opposite}',
                'conflict': existing
            }
    
    # 检查推理链冲突
    inference_conflicts = check_inference_conflicts(source, target)
    if inference_conflicts:
        return {
            'can_add': False,
            'reason': '会引发推理链冲突',
            'conflicts': inference_conflicts
        }
    
    return {
        'can_add': True,
        'warnings': []  # 可能有警告但不阻止
    }
```

### 2. 定期冲突扫描

```python
def scheduled_conflict_scan():
    """定期冲突扫描（每日）"""
    
    detector = ConflictDetector(graph_db)
    dashboard = ConflictDashboard(graph_db)
    
    # 检测所有冲突
    conflicts = []
    conflicts.extend(detector.detect_direct_contradiction())
    conflicts.extend(detector.detect_inference_conflict())
    
    # 尝试自动解决
    auto_resolved = 0
    escalated = 0
    
    for conflict in conflicts:
        result = resolve_conflict_workflow(conflict)
        if result['status'] == 'resolved':
            auto_resolved += 1
        else:
            escalated += 1
    
    # 生成报告
    report = dashboard.generate_report()
    report['auto_resolved'] = auto_resolved
    report['escalated'] = escalated
    
    # 发送通知
    if escalated > 0:
        send_notification(
            level='warning',
            message=f'检测到 {escalated} 个冲突需要人工处理',
            details=report
        )
    
    return report
```

---

## 总结

### 冲突解决策略优先级

```
1. 证据强度仲裁 (优先)
   └─ 当一方明显更强时

2. 条件限定 (次优)
   └─ 当两者在不同条件下成立时

3. 状态降级 (兜底)
   └─ 无法确定时，标记为hypothesis

4. 用户决策 (最后)
   └─ 系统无法自动解决时
```

### 关键原则

```
1. 自动优先：先尝试自动解决
2. 证据为王：基于证据强度决策
3. 精确定义：必要时添加条件限定
4. 透明告知：无法解决时明确告知用户
5. 持续监控：定期扫描和解决冲突
```
