# 隐含知识验证机制设计

## 核心洞察

**隐含知识不是凭空产生的，而是对关联图模式分析的提炼。**

验证流程：
```
关联图模式发现 → POB代码验证 → 分类处理
```

---

## 设计原则

### 原则1: 验证优先，不依赖人工输入

```
❌ 错误流程：
人工总结 → 写入配置 → 系统使用

✅ 正确流程：
关联图发现模式 → POB代码验证 → 自动分类
```

### 原则2: 知识分层，状态透明

```
知识状态分类：

verified    (已验证)
├─ 找到POB代码明确证据
├─ 置信度: 100%
└─ 作为推理依据

pending     (待确认)
├─ 缺少明确代码证据
├─ 置信度: 50%
├─ 作为探索线索
└─ 用户后续可确认

hypothesis  (假设)
├─ 基于类比推理
├─ 置信度: 30%
├─ 仅作提示
└─ 需要验证才能使用

rejected    (已拒绝)
├─ 发现反例
├─ 置信度: 0%
└─ 不参与推理
```

### 原则3: 流畅交互，延迟确认

```
推理过程中：
├─ 自动处理所有状态的数据
├─ 不中断用户询问用户确认
└─ 返回分层结果

后续交互：
├─ 用户查看待确认列表
├─ 逐一确认或拒绝
└─ 系统更新状态
```

---

## 架构设计

### 数据结构扩展

```sql
-- graph_edges 表扩展
ALTER TABLE graph_edges ADD COLUMN status TEXT DEFAULT 'pending';
ALTER TABLE graph_edges ADD COLUMN confidence REAL DEFAULT 0.5;
ALTER TABLE graph_edges ADD COLUMN evidence_type TEXT;
ALTER TABLE graph_edges ADD COLUMN evidence_source TEXT;
ALTER TABLE graph_edges ADD COLUMN evidence_content TEXT;
ALTER TABLE graph_edges ADD COLUMN discovery_method TEXT;
ALTER TABLE graph_edges ADD COLUMN parent_edge_id INTEGER;

-- 状态定义
-- status: 'verified' | 'pending' | 'hypothesis' | 'rejected'
-- evidence_type: 'stat' | 'code' | 'rule' | 'analogy' | 'user_input'
-- discovery_method: 'pattern' | 'analogy' | 'diffusion' | 'user_input'
```

### 验证机制

```python
class KnowledgeVerifier:
    """知识验证器"""
    
    def verify_implication(self, source_type: str, target_property: str) -> dict:
        """
        验证类型是否隐含属性
        
        Returns:
            {
                'status': 'verified' | 'pending' | 'rejected',
                'confidence': float,
                'evidence': {...}
            }
        """
        
        # Step 1: 搜索POB代码
        evidence = self.search_pob_evidence(source_type, target_property)
        
        # Step 2: 分类处理
        if evidence['type'] == 'explicit_stat':
            return {
                'status': 'verified',
                'confidence': 1.0,
                'evidence': evidence
            }
        elif evidence['type'] == 'pattern_match':
            return {
                'status': 'pending',
                'confidence': 0.5,
                'evidence': evidence,
                'note': '找到模式但缺少明确证据'
            }
        elif evidence['type'] == 'counter_example':
            return {
                'status': 'rejected',
                'confidence': 0.0,
                'evidence': evidence,
                'note': '发现反例'
            }
        else:
            return {
                'status': 'hypothesis',
                'confidence': 0.3,
                'evidence': None,
                'note': '缺少证据'
            }
    
    def search_pob_evidence(self, source_type: str, target_property: str) -> dict:
        """在POB代码中搜索证据"""
        # 搜索策略：
        # 1. 搜索stat定义
        # 2. 搜索skillTypes约束
        # 3. 搜索CalcModules逻辑
        
        # 返回证据类型和内容
        pass
```

---

## 工作流程

### 流程1: 知识发现

```
用户问题
    ↓
查询已验证知识 → 返回verified结果
    ↓
发现新模式
    ↓
POB代码验证
    ├─ 找到证据 → verified
    ├─ 缺少证据 → pending
    └─ 发现反例 → rejected
    ↓
返回分层结果
```

### 流程2: 启发式推理

```
query_bypass(constraint)
    ↓
Step 1: 收集候选
    ├─ verified边 → 高权重
    ├─ pending边 → 低权重（作为线索）
    └─ hypothesis边 → 不使用
    ↓
Step 2: 验证pending候选
    └─ 对pending边进行POB代码搜索
    ↓
Step 3: 扩散发现
    └─ 只从verified边扩散
    ↓
Step 4: 返回结果
    ├─ verified: [...]
    ├─ pending: [...]
    └─ hypothesis: [...]
```

### 流程3: 用户反馈

```
用户查看待确认列表
    ↓
GET /pending-knowledge
    ↓
返回所有status='pending'的边
    ↓
用户逐个确认
    ├─ 确认 → POST /confirm {edge_id}
    │   └─ 更新status='verified'
    └─ 拒绝 → POST /reject {edge_id}
        └─ 更新status='rejected'
```

---

## 待确认数据的角色

### 在查询阶段

```
查询结果分层显示：

✅ 已验证:
  - TrailOfCaltropsPlayer
    证据: stat "generic_ongoing_trigger_does_not_use_energy"
    来源: act_dex.lua:9596

⚠️ 待确认:
  - SupportDoedresUndoingPlayer
    推断: 可能通过Creation机制绕过
    状态: 未找到明确代码证据
```

### 在发现阶段

```
discover_bypass_paths():
    ├─ 使用verified边作为推理依据
    ├─ 使用pending边作为探索线索
    │   └─ 降低置信度 (×0.5)
    └─ 跳过hypothesis边
    
自动验证流程：
    对每个pending候选：
        if 搜索POB代码找到证据:
            转为verified
            更新置信度为1.0
        else:
            保持pending状态
            记录搜索结果
```

### 在扩散阶段

```
diffuse_from_bypass(known_bypass):
    ├─ 只从verified边开始扩散
    ├─ 发现相似实体后：
    │   ├─ 验证是否有POB证据
    │   ├─ 有证据 → verified
    │   └─ 无证据 → pending
    └─ 不使用pending或hypothesis边作为扩散源
```

---

## 实现优先级

### Phase 1: 数据结构扩展
- [ ] 扩展graph_edges表结构
- [ ] 添加status字段
- [ ] 添加验证相关字段

### Phase 2: 验证器实现
- [ ] 实现KnowledgeVerifier类
- [ ] 实现POB代码搜索
- [ ] 实现证据评估逻辑

### Phase 3: 推理系统集成
- [ ] 修改heuristic_query.py使用状态过滤
- [ ] 修改heuristic_discovery.py集成验证
- [ ] 修改heuristic_diffuse.py限制扩散源

### Phase 4: 用户交互
- [ ] 实现待确认列表查询
- [ ] 实现确认/拒绝操作
- [ ] 实现结果分层显示

---

## 示例：能量循环绕过案例

### 初始状态
```
用户问题: "如何绕过能量循环限制？"
```

### 发现流程

```
Step 1: 查询已验证边
  结果: 无（初始为空）

Step 2: 从关联图发现模式
  分析: Triggered技能被很多机制排除
  假设: Triggered → CannotGenerateEnergy?

Step 3: POB代码验证
  搜索: excludeSkillTypes: { Triggered }
  发现: 多个Support技能排除Triggered
  结论: verified, evidence_type='code'

Step 4: 继续发现
  分析: 有技能能绕过吗？
  发现: TrailOfCaltropsPlayer有特殊stat
  验证: generic_ongoing_trigger_does_not_use_energy
  结论: verified, evidence_type='stat'

Step 5: 扩散发现
  相似实体: SpearfieldPlayer
  验证: 无明确stat证据
  结论: pending, confidence=0.5
```

### 返回结果

```
{
  'verified': [
    {
      'entity': 'TrailOfCaltropsPlayer',
      'evidence': {
        'type': 'stat',
        'source': 'act_dex.lua:9596',
        'content': 'generic_ongoing_trigger_does_not_use_energy'
      }
    }
  ],
  'pending': [
    {
      'entity': 'SpearfieldPlayer',
      'reason': '基于相似性推断',
      'confidence': 0.5
    }
  ]
}
```

### 后续用户操作

```
用户查看: GET /pending-knowledge
用户确认: POST /confirm {edge_id: xxx}
系统更新: status='verified', confidence=1.0
```

---

## 与现有系统的集成

### 关联图构建时

```python
def build_property_layer(graph_db_path):
    # 不再硬编码映射
    # 而是从关联图模式发现
    
    # Step 1: 发现模式
    patterns = discover_patterns_from_graph(graph_db_path)
    
    # Step 2: 验证每个模式
    for pattern in patterns:
        verification = verify_implication(pattern.source, pattern.target)
        
        # Step 3: 创建边（带状态）
        create_edge(
            source=pattern.source,
            target=pattern.target,
            status=verification['status'],
            confidence=verification['confidence'],
            evidence=verification['evidence']
        )
```

### 启发式推理时

```python
def query_bypass(constraint):
    # 分层查询
    verified = query_edges(status='verified', target=constraint)
    pending = query_edges(status='pending', target=constraint)
    
    # 对pending进行验证尝试
    for edge in pending:
        new_evidence = search_pob_evidence(edge)
        if new_evidence:
            update_edge_status(edge.id, 'verified')
            verified.append(edge)
    
    return {
        'verified': verified,
        'pending': [e for e in pending if e.status == 'pending']
    }
```

---

## 总结

### 核心改进

1. **验证来源**: 从人工总结 → POB代码验证
2. **状态透明**: 四级状态清晰可见
3. **流程流畅**: 不中断用户交互
4. **知识进化**: pending → verified 的正循环

### 待确认数据的价值

- 作为探索线索，引导发现方向
- 降低盲目搜索成本
- 保持系统透明性
- 支持用户参与知识建设

### 下一步

实现Phase 1: 数据结构扩展
