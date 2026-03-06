## Why

当前 POB 数据扫描器存在严重的数据提取问题，导致大量游戏核心数据未被导入知识库。特别是 ModCache.lua（6254个条目）完全未被提取，这包含了游戏机制的核心映射数据。此外，gem_definition 和 minion_definition 的数据字段全部为空，导致规则库和关联图的构建基础不完整。

## What Changes

### P0 - 关键修复
- **修复 ModCache.lua 提取**：新增正确的提取方法 `_extract_mod_cache`，解析 `c["描述"] = {{mod数据}, "描述"}` 格式
- **修复 stat_mapping 类型识别**：更新特征指纹配置，正确识别 ModCache.lua
- **新增 mod_definition 实体类型**：存储 ModCache 中的 mod 数据（type, name, value, flags 等）

### P1 - 数据完整性修复
- **修复 gem_definition 提取**：解析 Gems.lua 的正确格式，提取 skill_types, constant_stats, stats 字段
- **修复 minion_definition 提取**：解析 Minions.lua 和 Spectres.lua 的完整数据

### P2 - 数据范围优化
- **更新黑名单配置**：过滤 lua/, Classes/, Update/ 目录
- **动态版本检测**：TreeData 版本检测改为动态获取，支持未来版本更新

## Capabilities

### New Capabilities
- `mod-cache-extraction`: ModCache.lua 数据提取能力，解析游戏机制映射数据
- `blacklist-filter`: 数据范围过滤能力，排除非游戏数据目录

### Modified Capabilities
- `entity-extraction`: 修复现有实体提取逻辑（gem_definition, minion_definition）

## Impact

### 直接影响
- `data_scanner.py`: 核心扫描逻辑修改
- `entity_index.py`: 新增 mod_definition 实体类型的存储支持
- 知识库实体数量预计增加 6000+

### 间接影响
- 规则库：基于 mod 数据生成更多规则
- 关联图：建立 "描述" ↔ "游戏参数" 的边
- 机制库：更完整的机制识别和来源追踪
