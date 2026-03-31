## Context

**Current State**:
- Lua 代码只收集辅助宝石名称，不收集效果和条件（注释："无法准确测量单辅助贡献，只收集名称"）
- `data_bridge.py` 的 `get_support_level_bonus()` 只返回数值，不返回条件
- 格式化代码只遍历名称列表，显示空白效果

**Data Source**:
- `entities.db` 的 `constant_stats` 字段包含完整信息：
  - `["supported_active_skill_gem_level_+", 1]` → 无条件 +1 level
  - `["supported_active_skill_gem_level_+_if_one_other_support", 3]` → 条件性 +3 level

**Challenge**:
- Lua 返回的是宝石名称（如 "Dialla's Desire"）
- 查询需要的是 entity ID（如 "SupportDiallasDesirePlayer"）
- 需要名称到 ID 的映射

## Goals / Non-Goals

**Goals**:
- 从 `constant_stats` 解析效果和条件
- 实现名称到 ID 的映射（支持模糊匹配）
- 在报告中显示完整信息：效果 + 条件

**Non-Goals**:
- 不修改 Lua 代码（保持现有架构）
- 不测量单个辅助的贡献（POB 限制）
- 不处理复杂的多条件逻辑

## Decisions

### 1. 效果解析策略

**Decision**: 使用模式匹配解析 stat 名称

**Rationale**:
- stat 名称有固定格式：`supported_active_skill_gem_level_+` 或 `..._if_<condition>`
- 可以用正则表达式提取关键信息

**Implementation**:
```python
def _parse_stat_name(stat_name: str, value: int) -> tuple[str, str]:
    """解析 stat 名称，返回 (效果描述, 条件描述)"""
    
    # 效果类型
    if 'level_+' in stat_name:
        effect = f"+{value} level"
    elif 'quality_' in stat_name:
        effect = f"+{value}% quality"
    else:
        effect = f"{stat_name}: {value}"
    
    # 条件提取
    condition = None
    if '_if_' in stat_name:
        match = re.search(r'_if_(.+)$', stat_name)
        if match:
            cond_str = match.group(1)
            # 条件映射表
            CONDITION_MAP = {
                'one_other_support': '1个其他辅助',
                'no_other_supports': '无其他辅助',
                # 可扩展...
            }
            condition = CONDITION_MAP.get(cond_str, cond_str.replace('_', ' '))
    
    return effect, condition
```

**Alternatives**:
- ❌ 查询 `stat_descriptions` 表：数据不完整（Uhtred's Omen 的 stat_descriptions 为空）
- ❌ 使用外部配置：维护成本高，entities.db 已有数据

### 2. 名称到 ID 映射

**Decision**: 实现 `get_support_by_name()` 方法，使用模糊匹配

**Rationale**:
- Lua 返回名称可能带空格/特殊字符（如 "Dialla's Desire"）
- Entity ID 格式固定：`Support<Name>Player`
- 需要容错处理

**Implementation**:
```python
def get_support_by_name(self, name: str) -> Optional[str]:
    """根据辅助宝石名称查找 entity ID"""
    
    # 1. 尝试精确匹配
    row = self.conn.execute(
        "SELECT id FROM entities WHERE name = ?",
        (name,)
    ).fetchone()
    if row:
        return row['id']
    
    # 2. 尝试模糊匹配（去除空格、特殊字符）
    normalized = name.replace("'", "").replace(" ", "")
    pattern = f"%Support%{normalized}%Player"
    row = self.conn.execute(
        "SELECT id FROM entities WHERE id LIKE ?",
        (pattern,)
    ).fetchone()
    
    return row['id'] if row else None
```

**Alternatives**:
- ❌ 建立静态映射表：需要手动维护，容易过时
- ❌ 要求 Lua 返回 skillId：需要修改 Lua 代码

### 3. 报告格式

**Decision**: 折叠区块显示详细效果

**Format**:
```markdown
### 辅助贡献

- **Dialla's Desire**: +1 level, +10% quality
- **Uhtred's Omen**: +3 level (条件: 1个其他辅助)
- 总辅助贡献: **+3.9%** DPS
```

**Rationale**:
- 保持主表简洁（只显示总贡献）
- 折叠区块显示详细信息
- 条件用括号标注，清晰明了

## Risks / Trade-offs

**Risk**: 名称映射可能失败 → **Mitigation**: 提供降级方案，失败时只显示名称

**Risk**: 条件解析不完整 → **Mitigation**: 使用映射表 + 默认处理，逐步完善

**Trade-off**: 不测量单个辅助贡献 → **Accept**: POB 限制，无法绕过

## Migration Plan

1. **Phase 1**: 添加 `get_support_effects()` 和 `get_support_by_name()` 方法
2. **Phase 2**: 修改 `what_if.py` 格式化代码
3. **Phase 3**: 测试并生成报告

**Rollback**: 移除新增方法，恢复原格式化代码
