## Context

### 当前状态
- ModCache.lua 使用 `c["描述"] = {{mod数据}, "描述"}` 格式存储 6254 个条目
- 现有 `_extract_stat_mappings` 方法使用错误的正则 `r'\[\s*"([^"]+)"\s*\]\s*=\s*\{([^}]+)\}'`
- 正则无法匹配 `c[` 前缀，且 `[^}]+` 无法处理嵌套的 `{...}`
- 导致提取结果为 0 个实体

### 数据格式分析
```
ModCache.lua 格式:
c["描述文本"] = {nil, "描述文本"}                           # 简单映射
c["描述文本"] = {{[1]={type="MORE", name="Damage", ...}}, "描述文本"}  # mod数据

mod数据字段:
- type: "MORE", "INC", "BASE", "OVERRIDE", "FLAG", "MULTIPLIER"
- name: 属性名 (如 "Damage", "Life", "ColdResist")
- value: 数值
- flags, keywordFlags: 条件标识
- globalLimit, globalLimitKey: 全局限制
```

## Goals / Non-Goals

**Goals:**
- 正确提取 ModCache.lua 的 6254 个条目
- 建立 "描述文本" ↔ "游戏参数" 的映射关系
- 支持规则库和关联图的数据需求
- 保持向后兼容，不破坏现有数据结构

**Non-Goals:**
- 不修改 ModCache.lua 文件本身
- 不实现增量更新机制
- 不改变数据库表结构（除非必要）

## Decisions

### 决策1: 新增实体类型 vs 扩展现有类型
**选择**: 新增 `mod_definition` 实体类型

**理由**:
- ModCache 数据与 stat_mapping 性质不同
- stat_mapping 是 POB 内部映射，mod_definition 是游戏机制数据
- 分离存储便于独立查询和扩展

**备选方案**: 扩展 stat_mapping 类型
- 缺点: 混淆两种不同性质的数据

### 决策2: 提取方法设计
**选择**: 使用 `extract_lua_table` + 正则组合

**理由**:
- 已有 `extract_lua_table` 方法处理嵌套 `{...}`
- 正则用于定位条目起始位置
- 组合方案更可靠

**实现要点**:
```python
def _extract_mod_cache(self, content: str) -> List[Dict[str, Any]]:
    # 1. 匹配 c["描述"] = { 格式
    pattern = r'c\s*\[\s*"([^"]+)"\s*\]\s*=\s*\{'
    
    # 2. 对每个匹配，提取完整表内容
    # 3. 解析表内容，提取 mod 数据
```

### 决策3: 数据存储结构
**选择**: 在 entities 表存储，新增字段

**实体结构**:
```python
{
    'id': '描述文本',           # 使用描述作为 ID
    'name': '描述文本',
    'type': 'mod_definition',
    'mod_data': [...],         # mod 数据列表
    'description': '描述文本',
}
```

## Risks / Trade-offs

### 风险1: 描述文本作为 ID 可能重复
**风险**: 不同 mod 可能有相同描述
**缓解**: 使用描述 + 索引作为唯一 ID，如 `描述文本_1`

### 风险2: 数据量增加影响查询性能
**风险**: 6254 个新实体会增加数据库大小
**缓解**: 
- 只存储必要的 mod 字段
- 使用 data_json 存储完整数据，查询时按需解析

### 风险3: 正则解析边界情况
**风险**: 特殊字符或格式可能导致解析失败
**缓解**: 
- 添加错误日志记录
- 统计期望数量 vs 实际数量
- 人工检查异常条目
