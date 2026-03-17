# Design: 图数据可读性增强

## 架构概览

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          两层增强策略                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Layer 1: 存储层冗余                      Layer 2: 查询层解析               │
│  ┌─────────────────────────┐            ┌─────────────────────────┐        │
│  │ graph_edges 表增加:      │            │ 查询方法自动解析:        │        │
│  │ • source_name           │            │ • 图外实体查 entities.db │        │
│  │ • source_type           │            │ • 返回格式化结果         │        │
│  │ • target_name           │            │                         │        │
│  │ • target_type           │            │                         │        │
│  └─────────────────────────┘            └─────────────────────────┘        │
│            │                                       │                       │
│            ▼                                       ▼                       │
│  ┌─────────────────────────┐            ┌─────────────────────────┐        │
│  │ predefined_edges.yaml   │            │ 用户查询输出             │        │
│  │ 写入时直接带名称         │            │ 自动包含可读名称         │        │
│  └─────────────────────────┘            └─────────────────────────┘        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 1. graph_edges 表结构增强

### 当前结构
```sql
CREATE TABLE graph_edges (
    source_id TEXT,
    target_id TEXT,
    edge_type TEXT,
    properties TEXT,
    confidence REAL,
    source TEXT,
    created_at TIMESTAMP
);
```

### 增强后结构
```sql
CREATE TABLE graph_edges (
    source_id TEXT,
    source_name TEXT,      -- 新增: 人类可读名称
    source_type TEXT,      -- 新增: 实体类型
    target_id TEXT,
    target_name TEXT,      -- 新增: 人类可读名称  
    target_type TEXT,      -- 新增: 节点类型
    edge_type TEXT,
    properties TEXT,
    confidence REAL,
    source TEXT,
    created_at TIMESTAMP
);
```

## 2. predefined_edges.yaml 格式增强

### 当前格式
```yaml
- id: anomaly_con_desc_321bfe_passive_4681
  constraint: con_desc_321bfe
  modifier: passive_4681
  mechanism: 行为替换(2% chance...)语义重叠(charges,frenzy)
  value_score: 2
  status: new_discovery
```

### 增强后格式
```yaml
- id: anomaly_con_desc_321bfe_passive_4681
  constraint:
    id: con_desc_321bfe
    name: "球数转换: Power Charges → Frenzy Charges"
    description: "Gain Power Charges instead of Frenzy Charges"
  modifier:
    id: passive_4681
    name: "Gain Maximum Frenzy Charges on Gaining Frenzy Charge"
    type: "🔮 天赋"
    effect: "2% chance that if you would gain Frenzy Charges, you instead gain up to your maximum number"
  mechanism:
    bypass_type: "行为替换"
    summary: "球数获取方式与转换规则存在语义冲突"
    detail: |
      【修改者】天赋「Gain Maximum Frenzy Charges...」
        效果: 2% 几率在获得 Frenzy Charge 时直接获得最大数量
      
      【约束】「Gain Power Charges instead of Frenzy Charges」
        效果: 将 Frenzy Charge 获取转换为 Power Charge
      
      【冲突分析】
        重叠关键词: charges, frenzy
        两者对 Frenzy Charge 的获取存在不同处理逻辑:
        - 约束: 转换为 Power
        - 天赋: 获得最大数量
        执行顺序将影响最终效果
    overlap_keywords:
      - charges
      - frenzy
  value_score: 2
  status: new_discovery
```

## 3. mechanism 模板系统

### 模板类型

| bypass_type | 描述 | 模板 |
|-------------|------|------|
| 标签替换 | 添加新标签绕过限制 | tag_replacement_template |
| 行为替换 | 效果语义冲突 | behavior_replacement_template |
| 类型替换 | count as 改变类型 | type_replacement_template |
| 标签添加 | 扩展行为范围 | tag_addition_template |

### 模板示例

```python
MECHANISM_TEMPLATES = {
    '标签替换': '''
【修改者】{modifier_type}「{modifier_name}」
  效果: {modifier_effect}
  添加标签: {added_tags}

【约束】「{constraint_name}」
  限制: {constraint_description}
  针对标签: {blocked_tags}

【绕过原理】
  {modifier_name} 为技能添加 {added_tags} 标签后，
  技能被视为不同类型，不再受针对 {blocked_tags} 的限制。
  形成绕过路径: 原技能 → 添加标签 → 新类型 → 绕过约束
''',

    '行为替换': '''
【修改者】{modifier_type}「{modifier_name}」
  效果: {modifier_effect}

【约束】「{constraint_name}」
  效果: {constraint_description}

【冲突分析】
  重叠关键词: {overlap_keywords}
  {conflict_reasoning}
''',
}
```

## 4. 名称解析逻辑

```python
def _resolve_entity_name(self, entity_id: str) -> dict:
    """解析实体的可读名称"""
    
    # 1. 先查图内节点
    node = self._get_node(entity_id)
    if node:
        return {
            'id': entity_id,
            'name': node['name'],
            'type': self._format_type(node['node_type'])
        }
    
    # 2. 查实体库
    if self.entities_db_path:
        entity = self._query_entities_db(entity_id)
        if entity:
            return {
                'id': entity_id,
                'name': entity['name'],
                'type': self._format_entity_type(entity['type']),
                'effect': entity.get('stat_descriptions', '')[:200]
            }
    
    # 3. 从ID推断
    return self._infer_from_id(entity_id)

def _format_entity_type(self, entity_type: str) -> str:
    """格式化实体类型为emoji前缀"""
    TYPE_EMOJI = {
        'passive_node': '🔮 天赋',
        'gem_definition': '💎 宝石',
        'skill_definition': '⚔️ 技能',
        'unique_item': '⭐ 传奇',
        'mod_affix': '📜 词缀',
        'item_base': '📦 基底',
    }
    return TYPE_EMOJI.get(entity_type, f'📋 {entity_type}')
```

## 5. 修改文件清单

| 文件 | 修改内容 |
|------|----------|
| `attribute_graph.py` | 1. `_create_tables()` 增加字段<br>2. `_add_edge()` 填充名称字段<br>3. `_generate_mechanism_detail()` 新增方法<br>4. `_postprocess_archive()` 生成增强 YAML |

## 6. 向后兼容

- 查询方法返回增强字段，但保留原有字段
- 旧代码仍可使用 source_id/target_id
- 新代码可使用 source_name/target_name
