# Tasks: 图数据可读性增强

**状态**: ✅ 已完成 (2026-03-17)

## 实施任务

### Task 1: graph_edges 表结构增强
**文件**: `scripts/attribute_graph.py`
**方法**: `_init_graph_db()`

- [x] 在 graph_edges 表添加 `source_name`, `source_type` 字段
- [x] 在 graph_edges 表添加 `target_name`, `target_type` 字段

### Task 2: 实体名称解析方法
**文件**: `scripts/attribute_graph.py`
**新增方法**: `_resolve_entity_name()`

- [x] 实现三层解析: 图内节点 → entities.db → ID推断
- [x] 实现 `ENTITY_TYPE_EMOJI` emoji 格式化
- [x] 查询实体库获取名称

### Task 3: 边写入时填充名称
**文件**: `scripts/attribute_graph.py`
**方法**: `_insert_edge()`

- [x] 调用 `_resolve_entity_name()` 获取 source 名称
- [x] 调用 `_resolve_entity_name()` 获取 target 名称
- [x] 填充到边记录中

### Task 4: mechanism 模板系统
**文件**: `scripts/attribute_graph.py`
**新增方法**: `_parse_and_enhance_mechanism()`

- [x] 根据 bypass_type 生成详细描述
- [x] 包含修改者、约束、绕过原理三部分
- [x] 支持标签替换、行为替换、类型替换

### Task 5: YAML 序列化增强
**文件**: `scripts/attribute_graph.py`  
**新增方法**: `_enhance_anomaly_for_yaml()`

- [x] 修改 anomaly 结构为嵌套格式
- [x] constraint 字段改为包含 id/name/description 的字典
- [x] modifier 字段改为包含 id/name/type/effect 的字典
- [x] mechanism 字段改为包含 bypass_type/summary/detail 的字典

### Task 6: 重建验证
- [x] 运行图重建
- [x] 验证 graph.db 新字段有值
- [x] 验证 predefined_edges.yaml 格式正确
- [x] 抽查记录确认可读性

## 依赖关系

```
Task 1 (表结构)
    ↓
Task 2 (名称解析) ─→ Task 3 (边写入)
    ↓
Task 4 (模板系统)
    ↓
Task 5 (YAML增强)
    ↓
Task 6 (重建验证)
```

## 预估

- Task 1-3: 小改动，~30行代码
- Task 4: 中等，~80行代码（模板定义）
- Task 5: 中等，~50行代码
- Task 6: 运行验证
