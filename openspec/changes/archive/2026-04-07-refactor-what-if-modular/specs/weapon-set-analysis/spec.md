# weapon-set-analysis

## Overview
支持武器套装切换分析，在两个套装状态间干净切换并对比。

## Requirements

### R1: 套装检测
- `has_weapon_set_2()` 检测构筑是否有第二套武器（检查 Weapon 1 Swap slot 是否有装备）
- `get_weapon_set_skills(ws)` 返回指定套装下可用的技能名称列表

### R2: 套装切换
- 切换 `useSecondWeaponSet` 时同步更新：
  - 装备：Weapon 1/2 ←→ Weapon 1 Swap/2 Swap
  - 天赋：weaponSet=1 的 24 个节点 vs weaponSet=2 的 24 个节点
  - 技能组：slot 绑定 "Weapon 1" 的组在 ws2 下不可用，"Weapon 1 Swap" 的组在 ws1 下不可用
- 切换后需要 `rebuild_modlist()` 使变化生效

### R3: 全局分析对比
- 每个套装独立运行全局分析（defence、resource、recovery、aura_spirit、jewels）
- 生成对比数据：EHP delta、DPS delta、光环差异

### R4: 技能分析对比
- 同一技能在两个套装下分别分析，生成灵敏度/DPS拆解对比
- 某些技能可能只在一个套装下可用（slot 绑定的技能组）

### R5: 缓存格式
- 数据按 `ws1/`、`ws2/` 子目录存储
- `comparison.json` 存储套装间的差异数据
- 只有一个套装时不创建 ws2/ 子目录

### R6: 报告展示
- HTML 报告顶层增加套装选择器（WS1 | WS2 | 对比）
- 全局面板（防御/资源）随套装选择变化
- 技能 tabs 展示当前套装下可用的技能
- 对比面板高亮两套装间的关键差异
