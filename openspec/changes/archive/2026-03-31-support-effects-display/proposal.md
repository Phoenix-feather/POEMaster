## Why

格式优化后辅助宝石信息丢失，只显示名称不显示条件和效果。用户无法了解辅助宝石的具体贡献（如 Uhtred's Omen 需要 1 个其他辅助才生效），降低了报告的可读性和实用性。

## What Changes

- **data_bridge.py**: 添加 `get_support_effects()` 方法，解析 `constant_stats` 中的条件和效果
- **data_bridge.py**: 添加 `get_support_by_name()` 方法，实现名称到 ID 的映射
- **what_if.py**: 修改格式化代码，显示辅助宝石的效果和条件

## Capabilities

### New Capabilities

- `support-effects-query`: 查询辅助宝石的效果和条件，从 entities.db 的 constant_stats 字段解析

### Modified Capabilities

- `data-bridge`: 扩展数据桥接能力，新增辅助宝石效果查询功能

## Impact

**Affected Code**:
- `.codebuddy/skills/pob-build-analyzer/pob_calc/data_bridge.py`
- `.codebuddy/skills/pob-build-analyzer/pob_calc/what_if.py`

**Dependencies**:
- `poe-data-miner/knowledge_base/entities.db` (constant_stats 字段)

**Backward Compatibility**:
- ✅ 新增方法，不影响现有功能
- ✅ 报告格式增强，不破坏现有解析
