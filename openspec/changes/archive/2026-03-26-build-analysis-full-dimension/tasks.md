# Tasks: build-analysis-full-dimension

## Phase 1: 防御面基础 ✅
- [x] 1.1 添加 14 个防御灵敏度 profile 到 SENSITIVITY_PROFILES
- [x] 1.2 新增 defence_overview() 函数（Pool/减伤层/抗性/MaxHitTaken/DotEHP/TakenHitMult）
- [x] 1.3 集成防御灵敏度到 full_analysis()（复用 sensitivity_analysis, target=TotalEHP）
- [x] 1.4 新增 _format_section_defence() 报告格式化（2A-2G 共7个子表）
- [x] 1.5 更新基线概览补充最短板承伤

## Phase 2: 双维度升级 ✅
- [x] 2.1 diagnose_jewels() 添加 ehp_stat 参数（3个 Lua 调用点全部升级）
- [x] 2.2 珠宝诊断报告双维度展示（Section 6 + Section 8e）
- [x] 2.3 passive_node_analysis() EHP 维度确认（已有）
- [x] 2.4 defence_weakness_diagnosis（承伤乘数 TakenHitMult）
- [x] 2.5 抗性平衡检测（未满/溢出分析总结）

## Phase 3: 资源面 ✅
- [x] 3.1 resource_overview() 函数（Life/Mana/Spirit/ES/Ward 预算）
- [x] 3.2 life_recovery_analysis() 函数（Regen+Leech+Recoup+OnHit 聚合）
- [x] 3.3 mana_recovery_analysis() 函数
- [x] 3.4 恢复增强灵敏度（8 个恢复 profile + per-profile target_stat + 3D 报告）
- [x] 3.5 资源面报告格式化（3A/3B/3C/3D 四个子表）

## Phase 4: 构筑审计 ✅
- 已在 Section 4/6/7/8 中分散实现（无效天赋、零贡献珠宝、零影响光环）

## Phase 5: 执行摘要 + 报告重构 ✅
- [x] 5.1 Part 0 执行摘要（维度概览 + 关键发现 + 优化方向 Top 3）
- [x] 5.2 报告标题更新为"构筑全面分析报告"

## 代码统计
- 起始: 5,727 行
- 最终: ~6,740 行
- 新增: ~1,013 行
- 新增函数: defence_overview(), resource_overview(), life_recovery_analysis(), mana_recovery_analysis(), _format_section_defence()
- 新增数据: _DEFENCE_PROFILES (14个), _RECOVERY_PROFILES (8个), full_analysis 返回值增加 resource_overview/life_recovery/mana_recovery/recovery_sensitivity
- 灵敏度框架增强: sensitivity_analysis 支持 per-profile target_stat 覆盖
- Linter: 0 错误
