## 1. EC MORE 值动态读取

- [ ] 1.1 验证 POB 数据中 EC 的 grantedEffect.levels 结构，确认 MORE 值的 stat key 名称
- [ ] 1.2 在 `_test_mod_effect` 中添加 Lua 端逻辑：遍历构筑 skillGroups 找到 EC 宝石，读取实际等级和对应 MORE 值
- [ ] 1.3 用动态值替代 `_AURA_INJECT_MODS` 中的硬编码 59，保留原始值作为 fallback
- [ ] 1.4 修改报告格式化 `_format_section7`：EC 说明文本使用实际等级和数值

## 2. Charge 数量动态读取

- [ ] 2.1 在 `_test_remove_skill_group` 的 pre_configs 处理中，添加 Lua 端查询 `env.player.output.Maximum{Frenzy,Power,Endurance}Charges`
- [ ] 2.2 用读取的最大值替代 `_AURA_PRE_CONFIGS` 中的硬编码 3，保留默认值 fallback
- [ ] 2.3 返回实际使用的充能球数量，供报告和校验使用

## 3. 精魄限制解除

- [ ] 3.1 7B 中移除精魄不足时设置 `error` 的逻辑，改为设置 `spirit_note` 字段
- [ ] 3.2 7C 同理，移除精魄不足 error 逻辑
- [ ] 3.3 修改报告格式化 `_format_section7`：精魄不足的候选统一展示在主表格，备注列显示精魄需求
- [ ] 3.4 删除报告中的 "精魄不足但有效" 分区

## 4. 候选光环精魄消耗动态读取

- [ ] 4.1 修改 `_test_add_candidate_aura` 的 Lua 代码：在创建新 gem 后读取 `levels[maxLevel].spiritReservationFlat` 并返回
- [ ] 4.2 修改 `_test_add_spirit_support` 同理
- [ ] 4.3 用动态值替代 result 中从 `_AURA_CANDIDATES` 硬编码的 spirit 字段
- [ ] 4.4 保留硬编码值作为 fallback（当 POB 数据中无 spiritReservationFlat 时）

## 5. 一致性校验框架

- [ ] 5.1 在 `aura_spirit_analysis` 中添加 `_run_consistency_checks` 函数
- [ ] 5.2 实现校验规则：EC 等级差异、Charge 超限、条件不满足归因
- [ ] 5.3 返回结果新增 `warnings` 列表
- [ ] 5.4 修改报告格式化：在 Section 7 末尾追加 "⚠️ 数据一致性检查" 区块

## 6. 报告等级标注修正

- [ ] 6.1 修改 `_format_section7` 中所有硬编码 "Lv20" 文本，改为从结果数据动态读取实际等级
- [ ] 6.2 更新 SKILL.md 光环模拟前提说明

## 7. 验证

- [ ] 7.1 运行 full_analysis 验证所有修改正确（DPS 输出合理、无 lint 错误）
- [ ] 7.2 验证一致性校验产生正确警告
- [ ] 7.3 清理临时文件
