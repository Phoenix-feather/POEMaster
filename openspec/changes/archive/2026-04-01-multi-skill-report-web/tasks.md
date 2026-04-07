## 1. 数据层重构（what_if.py）

- [x] 1.1 新增 `_extract_global_data()` 函数：从 full_analysis 结果中提取全局数据（defence_overview, resource_overview, recovery, build_modifiers, build_attributes, jewel_overview）
- [x] 1.2 新增 `_extract_build_modifiers()` 函数：从主技能的 dps_breakdown.formula_items 提取通用修饰符汇总，过滤掉 category=Skill 的 source
- [x] 1.3 修改 `full_analysis()` 返回值：分离为 skill_data（不含全局字段）和 global_data 两个 dict
- [x] 1.4 新增 `_extract_jewel_overview()` 函数：从 jewel_diagnosis 提取不含 dps_pct 的珠宝概览

## 2. 缓存与报告生成（__init__.py + what_if.py）

- [x] 2.1 修改 `__init__.py` 的 `full_analysis()`：接收 global_data，保存为 global.json
- [x] 2.2 修改 `_cache.save_report()`：支持保存 global.json
- [x] 2.3 修改 `format_report()` 签名：接受 global_data 可选参数，合成"全局 + 技能"报告结构
- [x] 2.4 修改报告 Markdown 模板：基线概览改为"构筑基线"（取 global_data），DPS 拆解保持技能专属

## 3. 网页全局区（report_generator.py）

- [x] 3.1 修改 `generate_html_report()`：加载 global.json，嵌入到 HTML 模板的 `/*__GLOBAL_DATA__*/` 占位符
- [x] 3.2 新增 `BuildModifiersSection` 组件：展示构筑修饰符汇总（施法速度/伤害/暴击等按来源分类）
- [x] 3.3 修改 `KPICards` 改为 `GlobalBaselineSection`：展示构筑属性（TotalAttr/Str/Dex/Int/Accuracy）+ 防御面可展开 + 资源可展开 + 珠宝概览可展开
- [x] 3.4 新增 `JewelOverviewSection` 组件：展示珠宝名称/插槽/granted passives（不含 DPS%）

## 4. 网页技能页签区（report_generator.py）

- [x] 4.1 修改 App 组件：布局拆分为全局区（GlobalBaselineSection）+ 页签区（SkillTabContent）
- [x] 4.2 页签区顶部新增技能 KPI：TotalDPS + AverageHit + Speed + 技能名称
- [x] 4.3 页签区内容：DPSFlowTable + FormulaBreakdown + SensitivityChart + AuraChart + TalentValueTable + SensitivityTable + TalentExplorationTable + JewelDiagnosisTable
- [x] 4.4 所有技能专属组件的数据源从 `SKILLS_DATA[activeTab]` 读取（保持现有逻辑）

## 5. 全局区与页签区数据读取

- [x] 5.1 `generate_html_report()` 新增 `/*__GLOBAL_DATA__*/` 模板占位符，替换为 global.json 内容
- [x] 5.2 全局区组件从 `GLOBAL_DATA` 变量读取数据
- [x] 5.3 添加 fallback：GLOBAL_DATA 为 null 时从 SKILLS_DATA 的第一个技能提取全局字段

## 6. 验证与清理

- [x] 6.1 重新分析当前构筑（spark + comet），验证 global.json 正确生成
- [x] 6.2 验证 report_spark.md 和 report_comet.md 均包含全局数据 + 技能分析
- [x] 6.3 生成 report.html，验证全局区固定 + 页签切换正确
- [x] 6.4 运行 JS 验证（_validate_html_js 通过）
- [x] 6.5 preview_url 在浏览器中打开验证视觉效果
