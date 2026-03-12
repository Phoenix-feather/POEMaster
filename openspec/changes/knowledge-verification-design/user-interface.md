# 用户交互界面设计

## 设计目标

1. **透明度**：用户清楚知道哪些知识已验证、哪些待确认
2. **可控性**：用户可以干预验证过程，修改知识状态
3. **高效性**：批量处理待确认知识，减少重复操作
4. **可追溯**：所有决策都有证据链和决策记录

## 界面组件

### 1. 待确认知识仪表板

```
┌─────────────────────────────────────────────────────────────┐
│  待确认知识仪表板 (Pending Knowledge Dashboard)              │
├─────────────────────────────────────────────────────────────┤
│  概览                                                        │
│  ┌─────────────┬─────────────┬─────────────┬──────────────┐ │
│  │ 待确认(50%)  │ 假设(30%)   │ 已验证(100%) │ 已拒绝(0%)   │ │
│  │    23个      │    8个      │    142个     │    5个       │ │
│  └─────────────┴─────────────┴─────────────┴──────────────┘ │
│                                                              │
│  优先队列 (按影响力排序)                                      │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ #1 [HIGH] FireSpell → 伤害类型:火焰                      ││
│  │     影响: 12个技能计算  验证进度: 自动验证中...           ││
│  │     [查看证据] [立即处理]                                 ││
│  ├─────────────────────────────────────────────────────────┤│
│  │ #2 [MED] CoC → 触发条件:暴击                              ││
│  │     影响: 5个触发链  验证进度: 等待人工确认               ││
│  │     [查看证据] [立即处理]                                 ││
│  └─────────────────────────────────────────────────────────┘│
│                                                              │
│  [批量处理] [导出报告] [设置优先级规则]                       │
└─────────────────────────────────────────────────────────────┘
```

### 2. 知识详情卡片

```
┌─────────────────────────────────────────────────────────────┐
│  知识详情: FireSpell → 伤害类型:火焰                        │
├─────────────────────────────────────────────────────────────┤
│  状态: PENDING (置信度: 50%)                                 │
│  来源: 启发式发现 (2026-03-10)                               │
│                                                              │
│  ━━━ 证据链 ━━━                                              │
│  ✅ Layer 1: POB数据                                         │
│     • Fireball技能标签: ['spell', 'fire', 'area']           │
│     • 火焰技能列表包含Fireball                               │
│                                                              │
│  ✅ Layer 2: 代码逻辑                                        │
│     • CalcOffence.lua:892 "if skill.FireSpell then..."      │
│     • FireDamageMultiplier计算使用FireSpell标志             │
│                                                              │
│  ⚠️  Layer 3: 语义推断 (缺失)                                │
│     • 未找到 "FireSpell = damage type fire" 的显式定义      │
│                                                              │
│  ━━━ 自动验证结果 ━━━                                        │
│  综合证据强度: 0.85 (推荐: 验证)                             │
│  • 显式stat: 0.0                                             │
│  • 代码逻辑: 0.8                                             │
│  • 模式匹配: 0.7                                             │
│                                                              │
│  ━━━ 用户决策 ━━━                                            │
│  [✓ 验证此知识] [✗ 拒绝此知识] [⏸ 稍后处理]                │
│                                                              │
│  备注 (可选): ________________________________________       │
└─────────────────────────────────────────────────────────────┘
```

### 3. 批量处理界面

```
┌─────────────────────────────────────────────────────────────┐
│  批量处理向导                                                │
├─────────────────────────────────────────────────────────────┤
│  筛选条件                                                    │
│  □ 按类型: [ ] 因果规则  [ ] 标签属性  [ ] 绕过机制          │
│  □ 按影响: [ ] HIGH  [×] MEDIUM  [ ] LOW                     │
│  □ 按证据强度: 最低 [0.7] ────────── 最高 [1.0]              │
│  □ 按等待时间: 超过 [7] 天                                    │
│                                                              │
│  已选择: 15条知识                                            │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ [×] #1 FireSpell → 伤害类型:火焰 (强度:0.85)             ││
│  │ [×] #2 ColdSpell → 伤害类型:冰霜 (强度:0.85)             ││
│  │ [×] #3 LightningSpell → 伤害类型:闪电 (强度:0.85)        ││
│  │ ...                                                      ││
│  └─────────────────────────────────────────────────────────┘│
│                                                              │
│  批量操作                                                    │
│  ○ 全部验证 (证据强度≥0.7的自动验证)                        │
│  ○ 全部拒绝 (无可靠证据的标记为拒绝)                         │
│  ○ 智能处理 (根据证据强度自动决策)                           │
│  ○ 逐条审核 (手动逐条确认)                                   │
│                                                              │
│  [执行批量操作] [取消]                                       │
└─────────────────────────────────────────────────────────────┘
```

### 4. 验证历史记录

```
┌─────────────────────────────────────────────────────────────┐
│  验证历史                                                    │
├─────────────────────────────────────────────────────────────┤
│  筛选: [全部▼] 搜索: __________________ [🔍]               │
│                                                              │
│  时间         知识                        决策    操作者     │
│  ──────────────────────────────────────────────────────────│
│  2026-03-11  CoC → 能量生成规则       ✓验证   自动验证     │
│  2026-03-10  Triggered → 标签        ✓验证   用户确认     │
│  2026-03-10  Spell → 速度影响施法     ✗拒绝   用户确认     │
│  2026-03-09  Melee → 攻击速度        ✓验证   自动验证     │
│                                                              │
│  [导出CSV] [生成报告]                                        │
└─────────────────────────────────────────────────────────────┘
```

## 命令行接口 (CLI)

### 查看待确认知识

```bash
# 列出所有待确认知识
python -m poe_data_miner verify list --status pending

# 按优先级排序
python -m poe_data_miner verify list --sort-by impact --top 10

# 过滤特定类型
python -m poe_data_miner verify list --type causal_rule
```

### 处理单条知识

```bash
# 查看详情
python -m poe_data_miner verify show <knowledge_id>

# 验证知识
python -m poe_data_miner verify accept <knowledge_id> \
    --reason "POB代码中明确验证" \
    --evidence "CalcTriggers.lua:123"

# 拒绝知识
python -m poe_data_miner verify reject <knowledge_id> \
    --reason "与实际机制不符"

# 推迟处理
python -m poe_data_miner verify defer <knowledge_id> \
    --until "2026-03-20"
```

### 批量处理

```bash
# 批量验证 (证据强度≥0.8)
python -m poe_data_miner verify batch-accept \
    --min-evidence-strength 0.8 \
    --type type_property

# 智能批量处理
python -m poe_data_miner verify batch-auto \
    --strategy smart

# 导出待处理报告
python -m poe_data_miner verify export \
    --format markdown \
    --output pending_report.md
```

### 查询统计

```bash
# 验证统计
python -m poe_data_miner verify stats

# 输出:
# ━━━━━━━━━━━━━━━━━━━━━━━━━━
# 知识验证统计 (2026-03-11)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━
# 总计: 178条
# ├─ 已验证: 142 (79.8%)
# ├─ 待确认: 23 (12.9%)
# ├─ 假设: 8 (4.5%)
# └─ 已拒绝: 5 (2.8%)
#
# 自动验证成功率: 89.2%
# 平均证据强度: 0.82
```

## API接口

### RESTful API

```python
# 查询待确认知识
GET /api/v1/knowledge?status=pending&sort=impact

# 响应
{
    "total": 23,
    "items": [
        {
            "id": "k001",
            "subject": "FireSpell",
            "predicate": "implies",
            "object": "damage_type:fire",
            "status": "pending",
            "confidence": 0.5,
            "evidence_strength": 0.85,
            "impact_score": 12,
            "created_at": "2026-03-10T10:30:00Z"
        }
    ]
}

# 验证知识
POST /api/v1/knowledge/{id}/verify
{
    "decision": "accept",  # 或 "reject"
    "reason": "POB代码中明确验证",
    "evidence_reference": "CalcTriggers.lua:123"
}

# 批量处理
POST /api/v1/knowledge/batch-verify
{
    "knowledge_ids": ["k001", "k002", "k003"],
    "decision": "accept",
    "strategy": "auto"  # 或 "manual"
}
```

### Python SDK

```python
from poe_data_miner import KnowledgeManager

# 初始化
manager = KnowledgeManager()

# 查询待确认知识
pending = manager.query_knowledge(status='pending', sort_by='impact')
for k in pending[:10]:
    print(f"{k.id}: {k.subject} → {k.object}")
    print(f"  证据强度: {k.evidence_strength}")

# 验证单条
manager.verify_knowledge(
    knowledge_id='k001',
    decision='accept',
    reason='POB代码明确验证',
    evidence='CalcTriggers.lua:123'
)

# 批量验证
results = manager.batch_verify(
    knowledge_ids=['k001', 'k002', 'k003'],
    strategy='auto',
    min_evidence_strength=0.8
)
print(f"成功: {results['accepted']}, 失败: {results['rejected']}")
```

## 通知机制

### 自动验证完成通知

```
┌─────────────────────────────────────────────────────────────┐
│  📋 自动验证完成通知                                        │
├─────────────────────────────────────────────────────────────┤
│  本次自动验证完成，共处理 15 条知识：                        │
│                                                              │
│  ✅ 已验证: 13 条 (证据强度≥0.8)                            │
│  ⚠️  需人工确认: 2 条 (证据强度<0.7)                         │
│                                                              │
│  需人工确认的知识：                                          │
│  1. TrailOfCaltropsPlayer → 无能量消耗                      │
│     证据强度: 0.65 (低于自动验证阈值)                        │
│     [查看详情] [立即处理]                                    │
│                                                              │
│  2. AwakenedSpellCascade → 触发次数+1                       │
│     证据强度: 0.62                                           │
│     [查看详情] [立即处理]                                    │
│                                                              │
│  [查看全部报告] [忽略]                                       │
└─────────────────────────────────────────────────────────────┘
```

### 冲突警告通知

```
┌─────────────────────────────────────────────────────────────┐
│  ⚠️  知识冲突警告                                           │
├─────────────────────────────────────────────────────────────┤
│  检测到潜在冲突：                                            │
│                                                              │
│  知识A (已验证): CoC → 消耗能量                              │
│  证据: CalcTriggers.lua:456                                 │
│                                                              │
│  知识B (待确认): CoC → 无能量消耗                            │
│  证据: 用户观察                                              │
│                                                              │
│  冲突类型: 直接矛盾                                          │
│  建议: 检查知识B的版本兼容性或特殊条件                       │
│                                                              │
│  [查看冲突详情] [解决冲突] [忽略]                            │
└─────────────────────────────────────────────────────────────┘
```

## 用户配置

### 验证偏好设置

```yaml
# config/verification_preferences.yaml

# 自动验证阈值
auto_verification:
  enabled: true
  min_evidence_strength: 0.8  # 证据强度≥0.8自动验证
  types:                      # 允许自动验证的类型
    - type_property           # 类型-属性关系
    - causal_rule             # 因果规则
  exclude_types:              # 禁止自动验证的类型
    - bypass_mechanism        # 绕过机制 (必须人工确认)

# 通知设置
notifications:
  auto_verification_complete: true   # 自动验证完成通知
  conflict_detected: true            # 冲突检测通知
  pending_overdue: true              # 待确认知识过期通知
  overdue_days: 7                    # 超过7天未处理通知

# 优先级规则
priority_rules:
  - condition: "impact_score >= 10"
    priority: HIGH
  - condition: "evidence_strength < 0.5"
    priority: LOW
  - condition: "age_days >= 7"
    priority: HIGH

# 批量处理策略
batch_strategy:
  default: smart                    # 默认策略
  max_batch_size: 50                # 单次批量处理最大数量
  require_confirmation: true        # 批量操作前需确认
```

## 工作流集成

### 与启发式推理的集成

```python
# 在启发式推理过程中，pending知识的处理

class HeuristicReasoner:
    def reason_with_pending_knowledge(self, query):
        """在推理中使用待确认知识"""
        
        # 1. 获取相关pending知识
        pending_edges = self.graph.get_edges(status='pending')
        
        # 2. 根据证据强度调整权重
        weighted_edges = []
        for edge in pending_edges:
            # pending知识权重降低
            weight = self.calculate_weight(
                edge=evidence_strength,
                status_weight=0.5  # pending状态权重
            )
            weighted_edges.append((edge, weight))
        
        # 3. 执行推理
        result = self.execute_reasoning(query, weighted_edges)
        
        # 4. 记录pending知识的使用
        self.log_pending_usage(
            query=query,
            used_edges=[e for e, w in weighted_edges if w > threshold]
        )
        
        return result
```

### 与知识库更新的集成

```python
# 在知识库更新后，触发待确认知识检查

class KnowledgeUpdater:
    def after_update(self, change_type, changed_entities):
        """知识库更新后的钩子"""
        
        if change_type == 'pob_version_upgrade':
            # 版本升级：检查所有verified知识是否需要重新验证
            self.check_verified_knowledge_relevance()
        
        elif change_type == 'entity_added':
            # 新增实体：检查是否有相关pending知识可以自动验证
            self.check_pending_knowledge_validation(changed_entities)
```

## 最佳实践

### 1. 定期审查

- 每周审查一次pending知识队列
- 优先处理高影响、高证据强度的知识
- 及时清理过时或无意义的假设

### 2. 批量处理策略

- 证据强度≥0.8：直接批量验证
- 证据强度0.5-0.8：逐条快速审核
- 证据强度<0.5：谨慎评估或拒绝

### 3. 冲突处理优先级

1. 高影响知识冲突：立即处理
2. 版本兼容性冲突：查阅变更日志
3. 条件限定冲突：细化条件后重新验证

### 4. 用户决策记录

所有用户决策都记录决策原因、证据参考和决策时间，便于：
- 未来审查决策合理性
- 知识溯源和解释
- 训练自动验证模型

## 设计原则总结

1. **最小惊讶原则**：界面清晰，操作结果可预测
2. **渐进式披露**：简单任务简单操作，复杂任务提供详细选项
3. **撤销与修正**：所有决策都可以修改或撤销
4. **批量优先**：支持批量操作，减少重复劳动
5. **透明可追溯**：所有决策都有完整记录
