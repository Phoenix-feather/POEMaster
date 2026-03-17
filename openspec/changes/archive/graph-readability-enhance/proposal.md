# Proposal: 图数据可读性增强

## 问题陈述

当前 `predefined_edges.yaml` 和图查询输出的可读性极差：

1. **约束ID是哈希值** - `con_desc_321bfe` 完全不知道是什么
2. **modifier只存ID** - `passive_4681` 不知道是哪个天赋
3. **mechanism描述机械化** - 自动生成的模板文本缺少上下文

示例：
```yaml
# 当前 - 不可读
- constraint: con_desc_321bfe
  modifier: passive_4681
  mechanism: 行为替换(2% chance...)语义重叠(charges,frenzy)
```

## 目标

1. **存储层**: 在 graph_edges 表冗余名称字段
2. **查询层**: 查询方法自动解析并返回可读名称
3. **YAML增强**: predefined_edges.yaml 包含完整的名称和详细机制描述

## 预期效果

```yaml
# 增强后 - 可读
- constraint:
    id: con_desc_321bfe
    name: "球数转换: Power→Frenzy"
  modifier:
    id: passive_4681
    name: "Gain Maximum Frenzy Charges..."
    type: "🔮 天赋"
  mechanism:
    summary: "球数获取方式与转换规则冲突"
    detail: |
      详细的冲突分析...
```

## 范围

- 修改 `attribute_graph.py`
- 重建 graph.db
- 重新生成 predefined_edges.yaml

## 不包含

- entities.db 结构不变
- rules.db 结构不变
