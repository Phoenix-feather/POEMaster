# 公式库快速参考卡片

## 🎯 核心原则

**轻量级 + 利用POB现有系统**

- ❌ 不创建pob_sources.db
- ✅ 只存储函数定义 + source_file
- ✅ 利用555个官方stat ID
- ✅ 混合特征匹配

---

## 📊 POB三层Stat架构

```
公式代码 (CalcModules)
  ↓ 简化名称："Speed", "CooldownRecovery"
  
映射层 (SkillStatMap.lua) ⚠️ 未提取
  ↓ 简化名称 → stat ID
  
官方stat层 (ModCache.lua) ✅ 已提取
  → 555个官方stat ID
```

---

## 🗄️ 数据库Schema

| 表名 | 功能 |
|------|------|
| formulas | 主表（函数定义+特征） |
| formula_features | 特征索引（快速查询） |
| formula_stats | 公式-Stat关联 |
| formula_calls | 调用关系图 |

---

## 🚀 快速开始

### 初始化

```bash
python init_formula_library.py <pob_path> \
    --db formulas.db \
    --entities-db entities.db
```

### 查询

```bash
# 查询实体相关的公式
python formula_matcher.py --entity "MetaCastOnCritPlayer"

# 查询使用指定stat的公式
python formula_matcher.py --stat "CooldownRecovery"

# 查看公式的调用链
python formula_matcher.py --formula "CalcTriggers_calcTriggerEnergy"
```

---

## 🔢 匹配算法

```
匹配分数 = 精确匹配 × 0.5 + 模糊匹配 × 0.3 + 标签匹配 × 0.2

精确匹配：官方stat ID
模糊匹配：简化名称
标签匹配：规范化标签（skill_types）
```

---

## 📁 核心文件

| 文件 | 功能 |
|------|------|
| formula_extractor.py | 公式提取器 |
| call_chain_analyzer.py | 调用链分析器 |
| formula_matcher.py | 公式匹配器 |
| init_formula_library.py | 初始化脚本 |

---

## ✅ 关键发现

1. **data_json 100%填充** → 最完整数据源
2. **stat_sets 100%填充** → 最可靠字段
3. **stats字段填充率低** → 正常（POB原始数据如此）
4. **官方stat ID: 555个** → 可直接用于精确匹配

---

## ⚠️ 常见问题

| 问题 | 原因 | 解决 |
|------|------|------|
| 找不到trigger_energy stat ID | 不在ModCache.lua中 | 用模糊特征匹配 |
| stats字段为空 | POB原始数据如此 | 用data_json字段 |
| 匹配精确度不够 | 缺少映射层 | 提取SkillStatMap.lua |

---

## 📖 相关文档

- `docs/memory_migration_summary.md` - 迁移记忆总结
- `docs/implementation_plan_summary.md` - 实施方案总结
- `.codebuddy/rules/pob-stat-system-architecture.mdc` - POB Stat架构规则
- `.codebuddy/rules/formula-library-implementation.mdc` - 公式库实施规则

---

## 🎓 记忆ID

- 公式库实施完成：51284777
- POB三层Stat架构：46176056
- 公式库轻量级设计原则：31569926

---

## 🔗 快速链接

**测试命令**：
```bash
# 测试特征提取
python test_formula_extractor.py

# 提取官方stat ID
python extract_stat_ids.py

# 检查字段存在率
python check_pob_field_presence.py
```

**预期结果**：
- 公式提取：< 5分钟
- 查询响应：< 1秒
- 匹配准确率：> 80%
