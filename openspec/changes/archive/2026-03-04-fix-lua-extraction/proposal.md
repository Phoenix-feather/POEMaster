## Why

当前Lua扫描器使用简单正则表达式提取技能定义，无法正确处理嵌套的Lua表结构，导致实体数据提取不完整、Layer 1规则几乎无法生成。这严重影响了知识库的数据质量和问答能力。

## What Changes

- 使用括号平衡算法替代简单正则，正确提取嵌套Lua表
- 改进字段提取逻辑，支持 `[SkillType.XXX] = true` 格式
- 改进stats提取，支持 `statSets` 嵌套结构
- 添加提取结果验证，确保关键字段非空

## Capabilities

### New Capabilities

- `lua-table-parser`: Lua嵌套表解析能力，使用括号平衡算法正确提取多层嵌套结构

### Modified Capabilities

- `data-scanner`: 修改实体提取逻辑，使用新的解析器替代正则表达式

## Impact

- **data_scanner.py**: 核心提取逻辑重写
- **init_knowledge_base.py**: 可能需要调整调用方式
- **知识库数据质量**: 预期实体识别从~14提升到~200-300，Layer 1规则从~5提升到~500+
