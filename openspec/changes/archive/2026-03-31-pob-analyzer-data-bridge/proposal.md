## Why

`pob-build-analyzer` 当前所有数据查询都通过手写 Lua 代码直接读取 POB 原始数据，没有利用 `poe-data-miner` 已经整理好的结构化数据（entities.db）。这导致：
1. 每次查询等级数值、辅助效果都需要重复编写 Lua 代码
2. `poe-data-miner` 的 16,461 个实体数据未被复用
3. 两个技能的设计意图（联动）未实现

同时，报告格式存在可读性问题：
1. 光环表格的"条件参数范围"列塞入过多嵌套信息，横向滚动
2. 灵敏度分析、珠宝诊断等表格也有类似问题
3. 后续扩展网页版时需要更好的结构

## What Changes

### 1. 数据联动
- 创建 `pob_calc/data_bridge.py` 模块，直接读取 `poe-data-miner/knowledge_base/entities.db`
- 替换 `what_if.py` 中手写 Lua 查询为 `POEDataBridge` API 调用
- 支持查询：技能等级数值、辅助宝石等级加成、品质效果等

### 2. 报告格式优化
- 光环表格的详细信息改为可折叠 `<details>` 区块
- 每个光环一个可展开卡片，包含条件参数范围、辅助贡献、基础数值
- 灵敏度分析、珠宝诊断等表格同样优化
- 为后续网页版扩展预留 HTML 友好结构

## Capabilities

### New Capabilities

- `data-bridge`: 数据桥接能力 — 从 poe-data-miner 的 entities.db 读取结构化游戏数据，供 pob-build-analyzer 使用
- `report-collapsible`: 可折叠报告格式 — 报告表格支持可折叠区块，提升可读性并支持网页扩展

### Modified Capabilities

无（这是新增功能，不改变现有 spec 级别的需求）

## Impact

### 代码影响
- **新增**: `pob_calc/data_bridge.py` (~50 行)
- **修改**: `pob_calc/what_if.py`
  - 删除 4 个 Lua 查询函数（`_get_skill_stat_at_level`, `_get_support_level_bonus`, `_get_quality_speed_per_q`）
  - 新增 `POEDataBridge` 集成调用
  - 修改 `format_report()` 中的表格格式化逻辑（~100 行）
- **修改**: `pob_calc/__init__.py` — 导出 `POEDataBridge`

### 依赖影响
- 新增依赖路径：`pob-build-analyzer` → `poe-data-miner/knowledge_base/entities.db`
- 路径硬编码：`../poe-data-miner/knowledge_base/`（相对路径）
- 无需修改 `poe-data-miner`

### 数据影响
- entities.db 已包含所有需要的数据：
  - `stat_sets.levels` — 技能等级数值
  - `constant_stats` — 辅助宝石效果
  - `quality_stats` — 品质效果
