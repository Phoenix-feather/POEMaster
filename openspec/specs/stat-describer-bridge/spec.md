## ADDED Requirements

### Requirement: StatDescriber Lua runtime setup
系统 SHALL 在 lupa LuaRuntime 中搭建 StatDescriber.lua 运行所需的适配层，注入以下全局函数/变量：LoadModule（模拟为 loadfile(pob_root..path..".lua")(...)）、copyTable（从 Common.lua 提取）、round（从 Common.lua 提取）、floor（从 Common.lua 提取）、ConPrintf（空函数）、ItemClasses（空表）。

#### Scenario: LoadModule simulation
- **WHEN** StatDescriber 调用 LoadModule("Data/StatDescriptions/Specific_Skill_Stat_Descriptions/arc")
- **THEN** 适配层 SHALL 成功加载 arc.lua 并返回其 Lua table 内容

#### Scenario: Scope chain resolution
- **WHEN** StatDescriber 加载 arc scope 并发现 parent="skill_stat_descriptions"
- **THEN** 适配层 SHALL 递归加载 skill_stat_descriptions.lua 并建立完整的 scope 继承链

### Requirement: StatDescriber invocation API
系统 SHALL 提供 Python 函数 `describe_stats(stats_dict, scope_name)` 作为调用 StatDescriber.lua 的接口。输入为 Python 字典 {stat_name: value}，输出为字符串列表（人类可读的描述文本）。

#### Scenario: Basic stat description
- **WHEN** `describe_stats({"number_of_chains": 9}, "arc")`
- **THEN** 返回值 SHALL 包含 "Chains 9 Times" 或等效的精确 POB 格式描述

#### Scenario: Multiple stats
- **WHEN** `describe_stats({"number_of_chains": 9, "shock_effect_+%": 50}, "arc")`
- **THEN** 返回值 SHALL 包含对应两个 stat 的描述文本

#### Scenario: Special value handling
- **WHEN** stat 需要特殊处理（negate/divide_by_one_hundred/milliseconds_to_seconds 等）
- **THEN** 描述文本 SHALL 正确应用值变换（由原始 StatDescriber 逻辑保证）

### Requirement: StatDescriber batch processing
系统 SHALL 支持批量处理多个实体的 stat 描述，在初始化阶段一次性加载 scope 数据（避免重复加载 3.9MB 的 stat_descriptions.lua）。

#### Scenario: Batch initialization
- **WHEN** 初始化处理 16000+ 实体的 display_stats
- **THEN** 系统 SHALL 预加载公共 scope（stat_descriptions/skill_stat_descriptions 等），每个实体只额外加载其专属 scope

### Requirement: Graceful degradation
系统 SHALL 在 lupa 不可用或 StatDescriber 加载失败时优雅降级：display_stats 字段置为 null，不中断初始化流程，记录警告日志。

#### Scenario: lupa not installed
- **WHEN** Python 环境未安装 lupa
- **THEN** 初始化 SHALL 跳过 display_stats 预计算，记录 "lupa not available, skipping stat descriptions"

#### Scenario: Large file OOM
- **WHEN** lupa 加载 stat_descriptions.lua (3.9MB) 时内存不足
- **THEN** 系统 SHALL 捕获异常，记录警告，将所有 display_stats 置为 null
