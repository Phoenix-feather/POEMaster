## Why

当前精魄辅助推荐功能只包含 5 个硬编码候选（Direstrike、Precision、Refraction），导致法术构筑分析时出现"所有精魄辅助测试均无 DPS 影响"的情况。这是因为这些硬编码候选主要针对攻击构筑（Precision 仅攻击构筑有效，Direstrike 需要 Low Life），法术构筑缺乏适用的精魄辅助推荐。

## What Changes

- **动态扫描精魄辅助宝石**: 从 POB 的 `data.gems` 中自动发现所有 `spiritReservationFlat > 0` 的辅助宝石
- **混合候选源**: 保留硬编码核心候选（高价值、精确标注），补充动态扫描候选（自动发现）
- **智能过滤**: 根据构筑类型（攻击/法术）、技能标签（Spell/Attack）、条件状态自动过滤无效候选
- **Top 5 显示**: 只显示对当前构筑有效且 DPS 收益 > 0.1% 的前 5 个候选

## Capabilities

### New Capabilities

- `spirit-support-discovery`: 动态发现并推荐精魄辅助宝石的能力
  - 扫描 POB 数据库中所有精魄辅助宝石
  - 根据构筑特征智能筛选
  - 提供实时 DPS 收益预估

### Modified Capabilities

无。这是新功能，不修改现有 spec 级别的能力。

## Impact

**代码影响**:
- `pob_calc/what_if.py`: 新增 `discover_spirit_supports()` 和 `filter_spirit_supports()` 函数
- `pob_calc/what_if.py`: 修改 `aura_spirit_analysis()` 函数，集成动态扫描逻辑
- `pob_calc/what_if.py`: 修改报告格式化逻辑，显示 Top 5 精魄辅助

**数据源**:
- 依赖 POB 的 `data.gems` 数据库
- 实时扫描，无需缓存

**用户体验**:
- 法术构筑不再显示"无 DPS 影响"
- 推荐更精准（只显示有效的）
- 减少噪音（Top 5 而非全部候选）
