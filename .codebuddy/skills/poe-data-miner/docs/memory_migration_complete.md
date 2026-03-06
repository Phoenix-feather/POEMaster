# POEMaster 记忆导出（用于项目迁移恢复）

## 📋 项目背景

**工作区**：g:/POEMaster  
**专注领域**：POE2 元技能能量生成系统的数据挖掘和知识图谱构建  
**核心技能**：poe-data-miner  
**注意**：区分 g:/POEMaster（数据挖掘）和 g:/POEMasterHome（构筑分析）两个项目

---

## 📊 数据统计（2026-03-06）

**实体**：16,113个
- skill_definition: 900
- gem_definition: 900
- passive_node: 4,313
- item_base: 1,171
- unique_item: 474
- minion_definition: 496
- mod_affix: 2,570
- stat_mapping: 5,230
- calculation_module: 59

**规则**：19,128条
- modifier: 18,724
- formula: 400
- 其他: 4

**知识图谱**：19,774节点，13,878边

**新增**：公式库（formulas.db，待初始化）

---

## 🏗️ 核心实现

**数据库位置**：`.codebuddy/skills/poe-data-miner/knowledge_base/`
- entities.db（实体库）
- rules.db（规则库）
- graph.db（知识图谱）
- mechanisms.db（机制库）
- formulas.db（公式库，新增）

**查询工具**：kb_query.py（推荐）

**公式库核心文件**（新增）：
- formula_extractor.py（提取器）
- call_chain_analyzer.py（调用链分析）
- formula_matcher.py（匹配器）
- init_formula_library.py（初始化脚本）

**Schema管理系统**：schema_manager.py
- 解决硬编码失效问题
- 队列机制、循环检测、迭代次数动态计算

---

## 🎯 POB三层Stat架构

**Layer 1: 公式代码**（CalcModules）
- 使用简化名称："Speed", "CooldownRecovery"

**Layer 2: 映射层**（SkillStatMap.lua）
- 状态：⚠️ 未提取
- 提供简化名称 → stat ID映射

**Layer 3: 官方stat层**（ModCache.lua）
- 状态：✅ 已提取
- 数量：555个官方stat ID
- 类型：BASE(233), FLAG(138), INC(137), 等

**关键发现**：
- data_json 100%填充 → 最完整数据源
- stat_sets 100%填充 → 最可靠字段
- stats字段填充率低是正常的（POB原始数据如此）

---

## 🔄 分析流程

**Phase 1**: 规则识别阶段（标签互斥、约束条件、机制规则）

**Phase 2**: 关联图构建阶段（辅助、组合、修改关系）

**Phase 3**: 组合规则发现阶段（组合效果、绕过机制、例外情况）

**新增 Phase 0**: 公式库特征匹配
- 匹配算法：精确×0.5 + 模糊×0.3 + 标签×0.2

---

## 💡 设计原则

**公式库轻量级设计**：
1. ❌ 不创建pob_sources.db（避免冗余）
2. ✅ 公式库只存储函数定义 + source_file字段
3. ✅ 需要原始代码时去文件系统读（启发思考完成后）
4. ✅ 利用POB现有系统（555个官方stat ID、规范化标签）
5. ✅ 混合特征匹配（精确+模糊+标签）

**数据流程**：
扫描POB Lua → 实体数据库 → 规则库 → 知识图谱
提取Lua函数 → 公式库 → 特征匹配 → 规范化数据

---

## 🔧 启发记录系统

**实际案例**：hr_0001 - 尸体爆炸绕过Triggered能量限制

**核心思想**：用"问题+启发"替代"硬编码答案"

**存储位置**：heuristic_records.yaml

**版本更新验证**：用原问题重新探索，通过特征匹配定位公式

---

## 📚 方法论

**三源启发的双向验证**：
1. 数据模式（统计规律、标签关系）
2. 计算公式代码（CalcTriggers.lua等，核心环节）
3. 已有可信规则（已验证的高置信度规则）

**代码验证是最核心的环节**，只有代码验证才能建立因果关系。

---

## 🚀 快速使用

### 初始化公式库

```bash
cd g:/POEMaster/.codebuddy/skills/poe-data-miner/scripts
python init_formula_library.py <pob_path> --db formulas.db --entities-db entities.db
```

### 查询示例

```bash
# 实体查询
python kb_query.py entity MetaCastOnCritPlayer

# 规则查询
python kb_query.py rule --search "energy"

# 公式查询
python formula_matcher.py --entity "MetaCastOnCritPlayer"
```

---

## 📁 规则文件

已创建的规则文件（`.codebuddy/rules/`）：
1. schema-management-mandatory.mdc - Schema管理系统强制调用规则
2. pob-data-extraction-scope.mdc - POB数据提取范围规则
3. pob-stat-system-architecture.mdc - POB Stat系统架构规则
4. formula-library-implementation.mdc - 公式库实施规则
5. poemaster-data-statistics.mdc - POEMaster数据统计规则

---

## 🎓 记忆ID映射

| 记忆标题 | ID |
|---------|-----|
| 当前工作区 - POEMaster | 16664716 |
| POEMaster数据统计 | 17257634 |
| POEMaster核心实现细节 | 25648731 |
| POEMaster分析流程设计 | 40795863 |
| 启发记录系统实际运行案例 | 42525527 |
| POEMaster数据流程 | 50770388 |
| POEMaster项目规则已创建 | 67155369 |
| POEMaster分析方法论 | 73532808 |
| 硬编码失效问题解决方案 | 97683303 |
| 公式库实施完成 | 51284777 |
| POB三层Stat架构及数据现状 | 46176056 |
| 公式库轻量级设计原则 | 31569926 |

---

## 📝 还原步骤

在新项目中：

1. **查看此文档**：`docs/memory_migration_complete.md`
2. **查看规则文件**：`.codebuddy/rules/*.mdc`（如需详细规则）
3. **查看快速参考**：`docs/quick_reference.md`
4. **查看实施总结**：`docs/implementation_plan_summary.md`

**核心命令**：
```bash
# 初始化
python init_formula_library.py <pob_path> --db formulas.db --entities-db entities.db

# 测试
python test_formula_extractor.py

# 查询
python formula_matcher.py --entity "MetaCastOnCritPlayer"
```

---

## ✅ 完成清单

- [x] 所有记忆已更新（12个）
- [x] 规则文件已创建（5个）
- [x] 核心代码已实现（6个脚本）
- [x] 数据库Schema已定义
- [x] 查询接口已扩展
- [x] 文档已完善
- [x] 迁移导出文件已创建

**准备就绪**：等待POB数据路径，即可运行初始化！
