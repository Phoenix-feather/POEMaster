## Context

当前 `data_scanner.py` 使用简单正则表达式提取Lua技能定义：

```python
pattern = r'skills\s*\[\s*"([^"]+)"\s*\]\s*=\s*\{([^}]+(?:\{[^}]*\}[^}]*)*)\}'
```

这个正则在遇到嵌套 `{}` 时无法正确匹配边界，导致提取的 `skill_body` 不完整。

### Lua实际结构

```lua
skills["CastOnCritical"] = {
    name = "Cast on Critical",
    skillTypes = { [SkillType.Meta] = true, [SkillType.Triggers] = true },
    statSets = {
        [1] = {
            constantStats = { { "spirit_reservation_flat", 100 } },
            stats = { "energy_generated_+%" }
        }
    }
}
```

## Goals / Non-Goals

**Goals:**
- 正确提取完整嵌套Lua表结构
- 支持任意层级的嵌套
- 保持向后兼容的API

**Non-Goals:**
- 不实现完整的Lua解析器
- 不处理Lua代码执行
- 不支持复杂的Lua语法（如函数定义、控制流）

## Decisions

### 1. 使用括号平衡算法

**选择**: 括号平衡算法  
**替代方案**:
- 完整Lua解析器 - 过于复杂，引入外部依赖
- 状态机解析 - 与括号平衡本质相同

**理由**: 简单有效，无外部依赖，足以处理表结构提取

### 2. 分两阶段解析

**选择**: 先提取完整表，再解析字段  
**替代方案**: 一次性解析

**理由**: 分离关注点，便于调试和测试

### 3. 保留正则提取简单字段

**选择**: 对非嵌套字段仍使用正则  
**替代方案**: 全部使用状态机

**理由**: 简单字段用正则更快，且已验证可用

## Risks / Trade-offs

| 风险 | 缓解措施 |
|------|----------|
| 边界情况处理（字符串中的花括号） | 忽略引号内的花括号 |
| 大文件性能 | 逐块处理，避免全量加载 |
| 新格式不兼容 | 添加格式检测和回退机制 |
