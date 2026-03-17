# 隐含知识验证机制 - 实现规划

## 设计文档索引

```
openspec/changes/knowledge-verification-design/
├── design.md           # 核心设计原则和架构
├── design-detailed.md  # 详细设计（搜索算法、证据评估、边界处理）
└── implementation.md   # 本文档：实现路线图
```

---

## 核心设计总结

### 核心洞察

```
隐含知识 = 关联图模式发现 + POB代码验证
```

### 三大原则

1. **验证优先**：从POB代码自动验证，不依赖人工总结
2. **状态透明**：四级状态（verified/pending/hypothesis/rejected）
3. **流畅交互**：推理时不中断，用户后续再确认

---

## 实现阶段规划

### Phase 0: 数据结构准备

**目标**：扩展数据库支持验证状态

**任务**：
- [ ] 扩展 `graph_edges` 表结构
  ```sql
  ALTER TABLE graph_edges ADD COLUMN status TEXT DEFAULT 'pending';
  ALTER TABLE graph_edges ADD COLUMN confidence REAL DEFAULT 0.5;
  ALTER TABLE graph_edges ADD COLUMN evidence_type TEXT;
  ALTER TABLE graph_edges ADD COLUMN evidence_source TEXT;
  ALTER TABLE graph_edges ADD COLUMN evidence_content TEXT;
  ALTER TABLE graph_edges ADD COLUMN discovery_method TEXT;
  ```
- [ ] 创建 `verification_cache` 表
- [ ] 创建 `pending_knowledge` 视图

**验收标准**：
- 数据库迁移成功
- 现有边默认状态为 'verified'（向后兼容）

---

### Phase 1: POB代码搜索器

**目标**：实现POB代码搜索能力

**任务**：
- [ ] 创建 `POBCodeSearcher` 类
  - [ ] `search_stat_definition(stat_name)` - 搜索stat定义
  - [ ] `search_skilltype_constraint(skill_type)` - 搜索类型约束
  - [ ] `search_calc_logic(keyword)` - 搜索计算逻辑
  - [ ] `verify_implication(source, target)` - 验证隐含关系
- [ ] 实现搜索缓存机制
- [ ] 实现搜索结果结构化

**关键代码位置**：
```
scripts/knowledge_verifier.py
```

**验收标准**：
- 可以搜索 `generic_ongoing_trigger_does_not_use_energy`
- 返回明确的位置信息（文件:行号）
- 搜索耗时 < 1秒（缓存命中）

---

### Phase 2: 模式发现器

**目标**：从关联图发现潜在模式

**任务**：
- [ ] 创建 `PatternDiscoverer` 类
  - [ ] `discover_type_property_patterns()` - 发现类型-属性模式
  - [ ] `discover_causal_patterns()` - 发现因果模式
  - [ ] `discover_bypass_patterns()` - 发现绕过模式
- [ ] 实现特征提取和共同特征识别
- [ ] 实现支持度计算

**关键代码位置**：
```
scripts/pattern_discoverer.py
```

**验收标准**：
- 能发现 "TrailOfCaltropsPlayer → DoesNotUseEnergy" 模式
- 能识别出 "generic_ongoing_trigger_does_not_use_energy" 作为共同特征

---

### Phase 3: 证据评估器

**目标**：评估证据强度，确定知识状态

**任务**：
- [ ] 创建 `EvidenceEvaluator` 类
  - [ ] 定义证据强度标准
  - [ ] `evaluate_evidence_set(evidence_list)` - 综合评估
  - [ ] 处理冲突证据
  - [ ] 处理反例
- [ ] 实现置信度计算逻辑

**关键代码位置**：
```
scripts/knowledge_verifier.py (EvidenceEvaluator 类)
```

**验收标准**：
- stat定义证据 → 强度 1.0
- 代码逻辑证据 → 强度 0.8
- 多数模式证据 → 强度 0.7

---

### Phase 4: 集成到初始化流程

**目标**：在 `init_knowledge_base.py` 中使用自动验证

**任务**：
- [ ] 修改 `build_property_layer()`
  - 移除硬编码的 `type_property_mappings`
  - 使用模式发现和自动验证
- [ ] 修改 `build_trigger_layer()`
  - 使用自动验证的触发机制映射
- [ ] 实现增量更新（避免重复验证）

**关键代码位置**：
```
scripts/init_knowledge_base.py
```

**验收标准**：
- 初始化时自动发现和验证模式
- 生成的边带有正确的状态和置信度
- 无硬编码映射

---

### Phase 5: 集成到启发式推理

**目标**：在推理中使用验证状态

**任务**：
- [ ] 修改 `heuristic_query.py`
  - `query_bypasses()` 分层返回结果
  - 对pending边尝试自动验证
- [ ] 修改 `heuristic_discovery.py`
  - 使用pending边作为线索（降低权重）
  - 发现新边时自动验证
- [ ] 修改 `heuristic_diffuse.py`
  - 只从verified边扩散
  - 扩散结果自动验证

**关键代码位置**：
```
scripts/heuristic_query.py
scripts/heuristic_discovery.py
scripts/heuristic_diffuse.py
```

**验收标准**：
- 查询返回分层结果（verified + pending）
- pending边置信度降低到50%
- 扩散只使用verified边

---

### Phase 6: 用户交互工具

**目标**：提供用户查看和确认待确认知识的工具

**任务**：
- [ ] 创建 `knowledge_manager.py`
  - [ ] `--list-pending` 列出待确认知识
  - [ ] `--confirm <id>` 确认知识
  - [ ] `--reject <id>` 拒绝知识
  - [ ] `--show-evidence <id>` 显示证据详情
- [ ] 实现交互式确认流程
- [ ] 实现证据记录和追溯

**关键代码位置**：
```
scripts/knowledge_manager.py
```

**验收标准**：
- 用户可以查看所有pending知识
- 确认后状态转为verified
- 拒绝后状态转为rejected
- 显示清晰的证据信息

---

### Phase 7: 测试和验证

**目标**：验证整个系统的正确性

**任务**：
- [ ] 单元测试
  - [ ] POB代码搜索器测试
  - [ ] 模式发现器测试
  - [ ] 证据评估器测试
- [ ] 集成测试
  - [ ] 初始化流程测试
  - [ ] 推理流程测试
  - [ ] 用户交互测试
- [ ] 端到端测试
  - [ ] 能量循环绕过案例完整测试

**验收标准**：
- 单元测试覆盖率 > 80%
- 集成测试全部通过
- 端到端测试：发现 TrailOfCaltropsPlayer 绕过能量循环

---

## 测试用例

### 测试用例1: stat定义搜索

```python
def test_search_stat_definition():
    searcher = POBCodeSearcher('POBData')
    result = searcher.search_stat_definition(
        'generic_ongoing_trigger_does_not_use_energy'
    )
    
    assert result['found'] == True
    assert len(result['locations']) > 0
    assert any(
        'TrailOfCaltropsPlayer' in loc['skill']
        for loc in result['locations']
    )
```

### 测试用例2: 模式发现

```python
def test_discover_type_property_pattern():
    discoverer = PatternDiscoverer('knowledge_base/graph.db')
    patterns = discoverer.discover_type_property_patterns()
    
    # 应该发现 Hazard 类型的一些模式
    hazard_patterns = [
        p for p in patterns 
        if p['source_type'] == 'Hazard'
    ]
    
    assert len(hazard_patterns) > 0
    # 每个模式都应该有支持度
    for p in hazard_patterns:
        assert p['support'] >= 0.5
```

### 测试用例3: 验证流程

```python
def test_verify_implication():
    verifier = KnowledgeVerifier('POBData')
    result = verifier.verify_implication(
        'generic_ongoing_trigger_does_not_use_energy',
        'DoesNotUseEnergy'
    )
    
    assert result['status'] == 'verified'
    assert result['confidence'] >= 0.8
    assert result['evidence'] is not None
```

### 测试用例4: 端到端测试

```python
def test_energy_cycle_bypass_discovery():
    # 初始化知识库
    init_knowledge_base(pob_path, kb_path)
    
    # 查询能量循环绕过
    reason = HeuristicReason(f'{kb_path}/graph.db')
    result = reason.query_bypass('EnergyCycleLimit', mode='discover')
    
    # 验证结果
    assert len(result['verified']) > 0
    assert any(
        'TrailOfCaltropsPlayer' in e['entity']
        for e in result['verified']
    )
    
    # 验证证据
    verified = result['verified'][0]
    assert verified['evidence']['type'] == 'stat'
    assert 'generic_ongoing_trigger_does_not_use_energy' in verified['evidence']['content']
```

---

## 风险与缓解

### 风险1: 搜索性能问题

**风险**：POB代码量大，搜索可能很慢

**缓解措施**：
1. 实现搜索缓存
2. 预索引POB代码
3. 批量验证减少重复搜索
4. 并行处理

### 风险2: 证据解释错误

**风险**：自动解析POB代码可能理解错误

**缓解措施**：
1. 降低自动验证的置信度阈值
2. 重要结论需要用户确认
3. 提供证据追溯，用户可以手动检查
4. 多种证据类型交叉验证

### 风险3: 模式过于笼统

**风险**：发现的模式可能不够精确

**缓解措施**：
1. 使用条件限定细化模式
2. 记录反例
3. 提供置信度让用户判断
4. 支持用户手动调整

### 风险4: 用户交互负担

**风险**：待确认列表太多，用户确认负担重

**缓解措施**：
1. 自动验证尽可能多的知识
2. 只让用户确认关键决策
3. 提供批量操作
4. 智能排序（按重要性）

---

## 向后兼容性

### 现有数据处理

```python
def migrate_existing_edges():
    """迁移现有边到新的状态系统"""
    # 所有现有边默认为verified（向后兼容）
    cursor.execute('''
        UPDATE graph_edges
        SET status = 'verified',
            confidence = 1.0,
            evidence_type = 'legacy'
        WHERE status IS NULL
    ''')
```

### API兼容性

```python
# 旧API（保持兼容）
def query_bypasses(constraint: str) -> List[dict]:
    # 返回格式保持不变，但内部使用新逻辑
    pass

# 新API（推荐使用）
def query_bypasses_v2(constraint: str) -> dict:
    # 返回分层结果
    return {
        'verified': [...],
        'pending': [...],
        'hypothesis': [...]
    }
```

---

## 性能目标

| 指标 | 目标 | 测量方法 |
|------|------|----------|
| 单次验证耗时 | < 1秒 | stat搜索 + 评估 |
| 批量验证（10个模式） | < 5秒 | 并行搜索 + 缓存 |
| 模式发现 | < 3秒 | 关联图遍历 |
| 用户查询响应 | < 2秒 | 包含自动验证尝试 |
| 内存占用 | < 500MB | 缓存 + 索引 |

---

## 实现优先级建议

### P0 (立即实现)

1. **Phase 0**: 数据结构准备 - 无此无法进行后续工作
2. **Phase 1**: POB代码搜索器 - 核心能力

### P1 (高优先级)

3. **Phase 2**: 模式发现器 - 自动发现知识
4. **Phase 3**: 证据评估器 - 确定知识状态

### P2 (中优先级)

5. **Phase 4**: 集成到初始化流程 - 替换硬编码
6. **Phase 5**: 集成到启发式推理 - 使用验证状态

### P3 (低优先级)

7. **Phase 6**: 用户交互工具 - 便捷性改进
8. **Phase 7**: 测试和验证 - 质量保证

---

## 下一步行动

### 如果要开始实现

```
/opsx:new 创建新变更
```

选择优先级：
- **P0** - 数据结构和搜索器
- **P1** - 模式发现和证据评估
- **完整** - 全部7个阶段

### 如果要继续探索

- 搜索算法的具体实现细节？
- 模式发现的具体策略？
- 与现有启发式推理的深度集成？

---

## 总结

本设计实现了一个完整的隐含知识验证机制：

1. **自动验证**：从POB代码搜索证据
2. **状态管理**：四级状态清晰透明
3. **流畅交互**：不中断推理，延迟确认
4. **证据追溯**：每条知识都有来源
5. **持续进化**：用户反馈驱动改进

这将彻底解决当前硬编码映射的问题，使知识库更加可靠和可维护。
