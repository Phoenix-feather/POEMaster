# 知识演化策略

## 问题背景

### POB版本更新带来的挑战

```
┌─────────────────────────────────────────────────────┐
│              POB版本更新的影响                      │
├─────────────────────────────────────────────────────┤
│                                                     │
│  版本 0.3 → 版本 0.4                               │
│                                                     │
│  变化类型：                                         │
│    1. 新增技能                                      │
│       └─ 知识库需要扩展                            │
│                                                     │
│    2. 技能调整                                      │
│       └─ 知识库需要更新                            │
│                                                     │
│    3. 技能删除                                      │
│       └─ 知识库需要清理                            │
│                                                     │
│    4. stat定义变化                                  │
│       └─ 映射关系需要重建                          │
│                                                     │
│    5. 计算逻辑调整                                  │
│       └─ 推理规则需要修正                          │
│                                                     │
│  问题：如何自动检测和处理这些变化？                 │
│                                                     │
└─────────────────────────────────────────────────────┘
```

---

## 演化检测机制

### 版本检测

```python
class VersionDetector:
    """版本检测器"""
    
    def __init__(self, pob_data_path: str):
        self.pob_path = Path(pob_data_path)
    
    def get_current_version(self) -> dict:
        """
        获取当前POB版本信息
        
        从 GameVersions.lua 提取
        """
        version_file = self.pob_path / 'GameVersions.lua'
        
        if not version_file.exists():
            return {'version': 'unknown', 'hash': None}
        
        # 解析版本信息
        content = version_file.read_text(encoding='utf-8')
        
        # 提取版本号
        version_match = re.search(r'gameVersion\s*=\s*"([^"]+)"', content)
        pob_match = re.search(r'pobVersion\s*=\s*"([^"]+)"', content)
        
        return {
            'game_version': version_match.group(1) if version_match else 'unknown',
            'pob_version': pob_match.group(1) if pob_match else 'unknown',
            'data_hash': self.calculate_data_hash()
        }
    
    def calculate_data_hash(self) -> str:
        """
        计算POB数据哈希
        
        用于快速检测数据变化
        """
        import hashlib
        
        hasher = hashlib.sha256()
        
        # 关键文件列表
        key_files = [
            'Data/Gems.lua',
            'Data/Global.lua',
            'Data/SkillStatMap.lua',
            'Modules/CalcTriggers.lua',
            'Modules/CalcActiveSkill.lua'
        ]
        
        for file_path in key_files:
            full_path = self.pob_path / file_path
            if full_path.exists():
                content = full_path.read_bytes()
                hasher.update(content)
        
        return hasher.hexdigest()[:16]  # 前16位
    
    def has_version_changed(self) -> bool:
        """检测版本是否变化"""
        current = self.get_current_version()
        
        # 读取上次记录的版本
        last_version = self.load_last_version()
        
        if not last_version:
            return True  # 首次运行
        
        # 比较版本号和哈希
        return (
            current['game_version'] != last_version['game_version'] or
            current['data_hash'] != last_version['data_hash']
        )
```

### 变化检测

```python
class ChangeDetector:
    """变化检测器"""
    
    def __init__(self, graph_db_path: str, pob_data_path: str):
        self.graph = AttributeGraph(graph_db_path)
        self.pob_path = Path(pob_data_path)
    
    def detect_entity_changes(self) -> dict:
        """
        检测实体变化
        
        返回：
        {
            'added': [...],    # 新增实体
            'modified': [...],  # 修改实体
            'deleted': [...]   # 删除实体
        }
        """
        # 扫描当前POB数据
        scanner = POBDataScanner(self.pob_path)
        current_entities = scanner.scan_all_files()
        
        # 获取知识库中的实体
        stored_entities = self.graph.get_all_entities()
        
        # 构建索引
        current_ids = {e['id'] for e in current_entities}
        stored_ids = {e['id'] for e in stored_entities}
        
        # 新增
        added = current_ids - stored_ids
        
        # 删除
        deleted = stored_ids - current_ids
        
        # 修改（比较哈希）
        modified = []
        common_ids = current_ids & stored_ids
        
        for entity_id in common_ids:
            current = next(e for e in current_entities if e['id'] == entity_id)
            stored = next(e for e in stored_entities if e['id'] == entity_id)
            
            current_hash = self.calculate_entity_hash(current)
            stored_hash = stored.get('data_hash')
            
            if current_hash != stored_hash:
                modified.append({
                    'id': entity_id,
                    'old_hash': stored_hash,
                    'new_hash': current_hash
                })
        
        return {
            'added': list(added),
            'modified': modified,
            'deleted': list(deleted)
        }
    
    def detect_edge_changes(self) -> dict:
        """
        检测边变化
        
        返回：
        {
            'invalidated': [...],  # 因源数据变化而失效的边
            'newly_verified': [...], # 新获得证据的边
            'broken': [...]        # 因反例而失效的边
        }
        """
        changes = {
            'invalidated': [],
            'newly_verified': [],
            'broken': []
        }
        
        # 检查每条边
        all_edges = self.graph.get_all_edges()
        
        for edge in all_edges:
            # 检查源实体是否存在
            if not self.graph.get_node(edge['source']):
                changes['invalidated'].append({
                    'edge': edge,
                    'reason': 'source_entity_deleted'
                })
                continue
            
            # 检查目标节点是否存在
            if not self.graph.get_node(edge['target']):
                changes['invalidated'].append({
                    'edge': edge,
                    'reason': 'target_node_deleted'
                })
                continue
            
            # 对pending边，尝试重新验证
            if edge['status'] == 'pending':
                result = self.reverify_edge(edge)
                if result['status'] == 'verified':
                    changes['newly_verified'].append({
                        'edge': edge,
                        'new_evidence': result['evidence']
                    })
                elif result['status'] == 'rejected':
                    changes['broken'].append({
                        'edge': edge,
                        'counter_example': result.get('counter_example')
                    })
        
        return changes
```

---

## 演化处理策略

### 策略1: 增量更新

```python
class IncrementalUpdater:
    """增量更新器"""
    
    def update_from_changes(self, changes: dict) -> dict:
        """
        根据变化进行增量更新
        
        适用于：小规模变化
        """
        results = {
            'added_entities': 0,
            'updated_entities': 0,
            'deleted_entities': 0,
            'updated_edges': 0
        }
        
        # 处理新增实体
        for entity_id in changes['entities']['added']:
            entity_data = self.load_entity_from_pob(entity_id)
            self.add_entity_to_graph(entity_data)
            results['added_entities'] += 1
        
        # 处理修改实体
        for entity in changes['entities']['modified']:
            entity_data = self.load_entity_from_pob(entity['id'])
            self.update_entity_in_graph(entity['id'], entity_data)
            results['updated_entities'] += 1
        
        # 处理删除实体
        for entity_id in changes['entities']['deleted']:
            self.remove_entity_from_graph(entity_id)
            results['deleted_entities'] += 1
        
        # 处理失效边
        for item in changes['edges']['invalidated']:
            self.handle_invalidated_edge(item['edge'], item['reason'])
            results['updated_edges'] += 1
        
        return results
    
    def add_entity_to_graph(self, entity_data: dict):
        """添加新实体到图"""
        # 创建实体节点
        self.graph.create_node(GraphNode(
            id=entity_data['id'],
            type=NodeType.ENTITY,
            name=entity_data['name'],
            attributes=entity_data
        ))
        
        # 创建skillTypes边
        for skill_type in entity_data.get('skill_types', []):
            self.graph.create_edge(GraphEdge(
                source=entity_data['id'],
                target=f"type_{skill_type.lower()}",
                type=EdgeType.HAS_TYPE
            ))
        
        # 创建stats边
        for stat in entity_data.get('stats', []):
            self.graph.create_edge(GraphEdge(
                source=entity_data['id'],
                target=f"attr_{stat.lower()}",
                type=EdgeType.HAS_STAT
            ))
    
    def update_entity_in_graph(self, entity_id: str, new_data: dict):
        """更新实体"""
        # 获取旧数据
        old_data = self.graph.get_node(entity_id)
        
        # 计算差异
        diff = self.calculate_diff(old_data, new_data)
        
        # 更新节点属性
        self.graph.update_node(entity_id, attributes=new_data)
        
        # 更新边
        # 删除不再存在的关系
        for removed_type in diff.get('removed_types', []):
            self.graph.delete_edge(
                source=entity_id,
                target=f"type_{removed_type.lower()}",
                edge_type=EdgeType.HAS_TYPE
            )
        
        # 添加新的关系
        for added_type in diff.get('added_types', []):
            self.graph.create_edge(GraphEdge(
                source=entity_id,
                target=f"type_{added_type.lower()}",
                type=EdgeType.HAS_TYPE
            ))
        
        # 处理stats类似...
```

### 策略2: 完全重建

```python
class FullRebuilder:
    """完全重建器"""
    
    def rebuild_from_scratch(self) -> dict:
        """
        完全重建知识库
        
        适用于：
        - 大规模变化
        - 数据结构改变
        - 长期未更新
        """
        results = {
            'entities': 0,
            'edges': 0,
            'verified': 0,
            'pending': 0
        }
        
        # Step 1: 备份旧数据
        backup_path = self.backup_current_graph()
        
        try:
            # Step 2: 清空图
            self.graph.clear_all()
            
            # Step 3: 重新扫描POB
            scanner = POBDataScanner(self.pob_path)
            entities = scanner.scan_all_files()
            
            # Step 4: 构建实体节点
            for entity in entities:
                self.graph.create_node(GraphNode(
                    id=entity['id'],
                    type=NodeType.ENTITY,
                    name=entity['name'],
                    attributes=entity
                ))
                results['entities'] += 1
            
            # Step 5: 构建类型层
            build_type_layer(self.graph, entities)
            
            # Step 6: 构建属性层（自动验证）
            build_property_layer(self.graph, entities, self.pob_path)
            
            # Step 7: 构建触发层
            build_trigger_layer(self.graph, entities, self.pob_path)
            
            # Step 8: 统计
            stats = self.graph.get_stats()
            results['edges'] = stats['edge_count']
            results['verified'] = stats['status_counts'].get('verified', 0)
            results['pending'] = stats['status_counts'].get('pending', 0)
            
            return results
        
        except Exception as e:
            # 恢复备份
            self.restore_from_backup(backup_path)
            raise
```

### 策略3: 选择性更新

```python
class SelectiveUpdater:
    """选择性更新器"""
    
    def update_affected_areas(self, changes: dict) -> dict:
        """
        选择性更新受影响的区域
        
        适用于：
        - 局部变化
        - 需要保持用户确认的知识
        """
        results = {
            'updated_entities': [],
            'reverified_edges': [],
            'preserved_user_knowledge': []
        }
        
        # Step 1: 分析影响范围
        affected_area = self.analyze_impact_area(changes)
        
        # Step 2: 标记受影响的边为"待重新验证"
        for edge in affected_area['edges']:
            if edge['status'] == 'verified':
                # 用户已确认的知识，标记为需要重新验证
                self.graph.update_edge(
                    edge['id'],
                    status='needs_reverification',
                    previous_status='verified',
                    preserve_user_confirmed=True
                )
                results['preserved_user_knowledge'].append(edge)
        
        # Step 3: 更新实体
        for entity_id in affected_area['entities']:
            self.update_entity(entity_id)
            results['updated_entities'].append(entity_id)
        
        # Step 4: 重新验证边
        for edge in affected_area['edges']:
            result = self.reverify_edge(edge)
            if result['status'] == 'verified':
                # 恢复为verified
                self.graph.update_edge(
                    edge['id'],
                    status='verified',
                    evidence=result['evidence']
                )
                results['reverified_edges'].append(edge)
        
        return results
    
    def analyze_impact_area(self, changes: dict) -> dict:
        """
        分析影响范围
        
        返回受影响的实体和边
        """
        affected_entities = set()
        affected_edges = []
        
        # 直接受影响的实体
        affected_entities.update(changes['entities']['added'])
        affected_entities.update([e['id'] for e in changes['entities']['modified']])
        
        # 间接影响的实体（通过边连接）
        for entity_id in list(affected_entities):
            neighbors = self.graph.get_neighbors(entity_id)
            for neighbor in neighbors:
                affected_entities.add(neighbor['id'])
        
        # 受影响的边
        for entity_id in affected_entities:
            edges = self.graph.get_edges_by_entity(entity_id)
            affected_edges.extend(edges)
        
        return {
            'entities': affected_entities,
            'edges': affected_edges
        }
```

---

## 演化决策树

```
POB版本更新
    ↓
检测变化规模
    ↓
┌───┴────────────────────┐
│                        │
变化<5%                  变化>5%
│                        │
↓                        ↓
增量更新                 是否保留用户知识？
↓                        │
完成                 ┌────┴────┐
                     │         │
                    YES       NO
                     │         │
                     ↓         ↓
                 选择性更新  完全重建
                     │         │
                 保留确认    全新开始
                     │         │
                     └────┬────┘
                          │
                      生成报告
```

---

## 知识衰减机制

### 为什么需要衰减？

```
时间越久，知识越可能过时：

知识创建时间  │  过期风险
───────────────────────────
0-7天        │  低
7-30天       │  中
30-90天      │  高
>90天        │  很高
```

### 衰减策略

```python
class KnowledgeDecayManager:
    """知识衰减管理器"""
    
    def apply_decay(self) -> dict:
        """
        应用知识衰减
        
        规则：
        1. 长期未验证的pending知识，降低置信度
        2. 长期未引用的verified知识，标记为需要重新验证
        3. 过期的证据，重新评估
        """
        results = {
            'decayed': 0,
            'needs_reverification': 0,
            'evidence_expired': 0
        }
        
        # 获取所有边
        all_edges = self.graph.get_all_edges()
        
        for edge in all_edges:
            age_days = (datetime.now() - edge['created_at']).days
            
            # 策略1: pending知识衰减
            if edge['status'] == 'pending':
                if age_days > 30:
                    # 降低置信度
                    new_confidence = edge['confidence'] * 0.8
                    self.graph.update_edge(
                        edge['id'],
                        confidence=new_confidence
                    )
                    results['decayed'] += 1
            
            # 策略2: verified知识重新验证
            elif edge['status'] == 'verified':
                if age_days > 90:
                    # 检查是否被引用
                    ref_count = self.count_references(edge['id'])
                    if ref_count == 0:
                        # 长期未引用，标记需要重新验证
                        self.graph.update_edge(
                            edge['id'],
                            status='needs_reverification',
                            previous_status='verified'
                        )
                        results['needs_reverification'] += 1
            
            # 策略3: 证据过期
            if edge.get('evidence'):
                evidence_age = (datetime.now() - edge['evidence']['timestamp']).days
                if evidence_age > 60:
                    # 证据过期，需要重新收集
                    self.graph.update_edge(
                        edge['id'],
                        evidence_expired=True
                    )
                    results['evidence_expired'] += 1
        
        return results
```

---

## 演化报告

```python
class EvolutionReporter:
    """演化报告生成器"""
    
    def generate_evolution_report(self, changes: dict, results: dict) -> str:
        """
        生成演化报告
        
        返回Markdown格式的报告
        """
        report = []
        
        report.append("# 知识库演化报告")
        report.append(f"\n生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"\n## 版本信息")
        report.append(f"- POB版本: {changes['version']['pob_version']}")
        report.append(f"- 游戏版本: {changes['version']['game_version']}")
        report.append(f"- 数据哈希: {changes['version']['data_hash']}")
        
        report.append(f"\n## 变化统计")
        report.append(f"- 新增实体: {len(changes['entities']['added'])}")
        report.append(f"- 修改实体: {len(changes['entities']['modified'])}")
        report.append(f"- 删除实体: {len(changes['entities']['deleted'])}")
        
        report.append(f"\n## 更新结果")
        report.append(f"- 新增实体: {results['added_entities']}")
        report.append(f"- 更新实体: {results['updated_entities']}")
        report.append(f"- 删除实体: {results['deleted_entities']}")
        report.append(f"- 更新边: {results['updated_edges']}")
        
        if results.get('preserved_user_knowledge'):
            report.append(f"\n## 保留的用户知识")
            report.append(f"- 保留边数: {len(results['preserved_user_knowledge'])}")
            for edge in results['preserved_user_knowledge'][:5]:
                report.append(f"  - {edge['source']} → {edge['target']}")
        
        report.append(f"\n## 建议")
        if results.get('needs_reverification'):
            report.append(f"- 有 {len(results['needs_reverification'])} 条知识需要重新验证")
        
        return '\n'.join(report)
```

---

## 最佳实践

### 1. 定期更新

```
建议的更新频率：

小更新（日常）：每周
  └─ 检测版本变化
  └─ 增量更新

中更新（月度）：每月
  └─ 知识衰减
  └─ 清理过期知识

大更新（季度）：每季度
  └─ 完整性检查
  └─ 冲突扫描
```

### 2. 版本标签

```python
def add_version_tag(edge_id: str, version: str):
    """为边添加版本标签"""
    edge = graph.get_edge(edge_id)
    
    if not edge.get('version_tags'):
        edge['version_tags'] = []
    
    edge['version_tags'].append({
        'version': version,
        'timestamp': datetime.now().isoformat(),
        'status': edge['status'],
        'confidence': edge['confidence']
    })
    
    graph.update_edge(edge_id, version_tags=edge['version_tags'])
```

### 3. 回滚能力

```python
class KnowledgeRollback:
    """知识回滚"""
    
    def rollback_to_version(self, target_version: str) -> dict:
        """
        回滚到指定版本
        
        用途：
        - POB更新后出现大量错误
        - 需要恢复到稳定版本
        """
        # 加载目标版本备份
        backup = self.load_backup(target_version)
        
        # 保存当前状态
        current_backup = self.backup_current_state()
        
        # 恢复备份
        self.restore_from_backup(backup)
        
        return {
            'rolled_back_to': target_version,
            'backup_saved': current_backup,
            'timestamp': datetime.now().isoformat()
        }
```

---

## 总结

### 演化策略选择

```
变化规模 < 5%   → 增量更新
变化规模 > 5%   → 选择性更新（保留用户知识）
                或 完全重建（全新开始）

定期维护：
  每周  → 版本检测 + 增量更新
  每月  → 知识衰减 + 清理
  每季度 → 完整性检查 + 冲突扫描
```

### 关键原则

```
1. 检测优先：先检测变化，再决定策略
2. 保留价值：用户确认的知识尽量保留
3. 渐进演化：优先增量更新而非重建
4. 可回滚：保持回滚到历史版本的能力
5. 透明报告：每次演化生成详细报告
```
