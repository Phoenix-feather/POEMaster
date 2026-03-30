## Context

**背景**:
- 当前 `aura_spirit_analysis()` 中的精魄辅助推荐使用硬编码列表 `_SPIRIT_SUPPORT_CANDIDATES`（5 个候选）
- 这些候选主要针对攻击构筑（Precision 仅攻击构筑有效，Direstrike 需要 Low Life）
- 法术构筑分析时出现"所有精魄辅助测试均无 DPS 影响"的情况

**当前状态**:
```python
# 硬编码候选列表
_SPIRIT_SUPPORT_CANDIDATES = [
    Direstrike I/II,    # 攻击伤害 INC，需要 Low Life
    Precision I/II,     # 命中 INC，仅攻击构筑
    Refraction III,     # 元素暴露，需要 Banner
]
```

**约束**:
- 必须在每次 analysis 时实时扫描（不使用缓存）
- 只显示对当前构筑有效的候选（DPS 收益 > 0.1%）
- 只显示 Top 5（按 DPS 收益排序）
- 保留硬编码候选（高价值、精确标注）

## Goals / Non-Goals

**Goals:**
- 动态扫描 POB 数据库中所有精魄辅助宝石
- 智能过滤无效候选（根据构筑类型、技能标签、条件状态）
- 合并硬编码和动态候选，避免重复
- 只显示 Top 5 有效候选，减少噪音

**Non-Goals:**
- 不实现缓存机制（每次实时扫描）
- 不修改现有光环分析逻辑
- 不处理精魄辅助的复杂条件检测（如 Low Life 状态检测）
- 不修改报告格式（保持现有 Section 7C 结构）

## Decisions

### 决策 1: 混合候选源架构

**选择**: 硬编码核心 + 动态扫描补充

**理由**:
- 硬编码候选可以有详细的中文名称、描述、条件标注（用户友好）
- 动态扫描可以自动发现新宝石，无需手动维护
- 两者合并去重，保留硬编码的优先级（更详细）

**替代方案**:
- ❌ 纯动态扫描：失去精确标注，用户体验下降
- ❌ 纯硬编码：需要手动维护，容易遗漏新宝石

### 决策 2: 实时扫描策略

**选择**: 每次 `aura_spirit_analysis()` 调用时实时扫描 `data.gems`

**理由**:
- POB 数据库不大（~1000 个宝石），扫描速度快（<100ms）
- 实时扫描确保数据最新（POB 更新后无需手动同步）
- 实现简单，无需缓存管理

**替代方案**:
- ❌ 缓存到文件：增加复杂度，需要版本管理
- ❌ 启动时扫描：POB 更新后需要重启

### 决策 3: 过滤策略

**选择**: 多级过滤机制

**过滤逻辑**:
1. **构筑类型过滤**: 根据主技能的 `is_attack` / `is_spell` 标签
2. **技能标签过滤**: 检查辅助宝石的 `supportType` 或 `modTags`
3. **条件过滤**: 跳过明显不适用的条件（如 Precision 对法术构筑）

**实现**:
```python
def filter_spirit_supports(candidates, is_attack, is_spell, skill_tags):
    filtered = []
    for candidate in candidates:
        # 精确过滤（硬编码候选的已知条件）
        if candidate.get("condition") == "仅攻击构筑" and not is_attack:
            continue
        
        # 标签过滤（动态候选）
        if not is_compatible(candidate, skill_tags):
            continue
        
        filtered.append(candidate)
    return filtered
```

**替代方案**:
- ❌ 不过滤：显示所有候选，噪音太大
- ❌ 测试后过滤：浪费时间测试无效候选

### 决策 4: Top N 选择策略

**选择**: 按 DPS 收益排序，只显示 Top 5

**理由**:
- 减少报告噪音，只展示最有价值的推荐
- Top 5 足够覆盖主要优化方向
- 避免用户决策疲劳

**实现**:
```python
# 先按精魄消耗排序（优先测试小消耗的）
candidates_to_test = sorted(candidates, key=lambda x: x["spirit"])

# 测试所有候选
results = [test_support(s) for s in candidates_to_test]

# 过滤有效结果（DPS > 0.1%）
effective = [r for r in results if r["dps_pct"] > 0.1]

# 排序并取 Top 5
top_5 = sorted(effective, key=lambda x: -x["dps_pct"])[:5]
```

**替代方案**:
- ❌ 显示所有有效候选：可能过多（10-20 个）
- ❌ Top 3：可能遗漏有价值的选择

## Risks / Trade-offs

### 风险 1: 扫描性能

**风险**: 实时扫描可能增加分析时间

**缓解**:
- 扫描逻辑优化：只扫描 `spiritReservationFlat > 0` 的宝石
- 预期性能：<100ms（POB 数据库较小）
- 监控：添加性能日志，如果超过 200ms 则考虑缓存

### 风险 2: 过滤准确性

**风险**: 过滤逻辑可能误删有效候选

**缓解**:
- 保守过滤：只过滤明确不适用的候选
- 日志记录：记录被过滤的候选，便于调试
- 用户反馈：如果遗漏重要候选，可以快速调整

### 风险 3: 动态候选描述质量

**风险**: 动态扫描的候选可能缺少详细描述

**缓解**:
- 从 POB 的 `grantedEffect.description` 提取描述
- 自动生成简短描述（如 "SupportName: 效果描述"）
- 硬编码候选保持详细标注

### 风险 4: Top 5 遗漏

**风险**: Top 5 可能遗漏某些有价值的选择

**缓解**:
- 日志输出完整结果（便于高级用户查看）
- 可配置的 Top N（未来扩展）

## Open Questions

无。所有关键技术决策已确定。
