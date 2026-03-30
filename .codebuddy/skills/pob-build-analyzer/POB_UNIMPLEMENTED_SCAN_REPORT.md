# POB 未实现效果扫描报告

**扫描时间**: 2026-03-30  
**POB 数据路径**: `G:/POEMaster/POBData`

## 扫描统计

| 类别 | 数量 | 说明 |
|------|------|------|
| **SkillStatMap 已映射** | 880 | POB 已支持的 stats |
| **未映射 stats** | 449 | SkillStatMap.lua 中未定义映射 |
| **玩家受益相关** | 226 | 影响玩家数值的未映射 stats |

### 玩家受益 stats 分类

| 类型 | 数量 | 示例 |
|------|------|------|
| **辅助宝石** | 115 | `support_*_damage_+%_final` |
| **其他** | 90 | 特殊机制、增益等 |
| **触发类** | 17 | `trigger_meta_gem_damage_+%_final` |
| **主动技能** | 4 | Demon Form, Charged Blast |

## 已添加到配置的重要效果

### 1. 主动技能（4个）

#### ✅ Unbound Avatar
- **效果**: 40% MORE 元素伤害（Unbound 状态）
- **实现状态**: 已验证，已添加到配置
- **来源**: `ailment_bearer_elemental_damage_+%_final = 40`

#### 🆕 Demon Form
- **效果**: 每层 +MORE 法术伤害（动态层数）
- **stat**: `demon_form_spell_damage_+%_final_per_stack`
- **实现状态**: 已添加配置模板，需动态读取层数

#### 🆕 Charged Blast
- **效果**: 每层 +MORE 法术伤害（动态层数）
- **stat**: `charged_blast_spell_damage_+%_final_per_stack`
- **实现状态**: 已添加配置模板，需动态读取层数

#### ⚠️ Arc Infusion
- **效果**: ?% MORE 伤害（消耗充能时）
- **stat**: `arc_damage_+%_final_from_infusion_consumption`
- **实现状态**: 未添加，需确认技能名称

### 2. 元技能/触发类（1个）

#### 🆕 Meta Gem Trigger
- **效果**: 元技能触发时 MORE 伤害
- **stat**: `trigger_meta_gem_damage_+%_final`
- **适用**: SupportMetaCastOnCritPlayer, SupportMetaCastOnBlockPlayer 等
- **实现状态**: 已添加配置模板

### 3. 辅助宝石（115个，已添加3个示例）

#### 🆕 Brutality Support
- **效果**: MORE 物理伤害
- **stat**: `support_brutality_physical_damage_+%_final`

#### 🆕 Controlled Destruction Support
- **效果**: MORE 法术伤害
- **stat**: `support_controlled_destruction_spell_damage_+%_final`

#### 🆕 Elemental Damage Support
- **效果**: MORE 元素伤害（攻击技能）
- **stat**: `support_attack_skills_elemental_damage_+%_final`

**注意**: 大部分辅助宝石效果 POB 已通过 ModCache.lua 实现，需逐个验证。

### 4. 光环/被动效果（1个）

#### ⚠️ Elemental Conflux
- **效果**: 每8秒随机元素 MORE 伤害
- **实现状态**: 已添加，但需特殊处理（期望值计算）

## 未添加但重要的效果

以下 stat 在扫描中发现，但需要进一步确认：

### 主动技能类
- `cascadeable_offering_support_offering_casted_spell_damage_+%_final` (Kulemak's Dominion)
- `archmage_all_damage_%_to_gain_as_lightning_to_grant_to_non_channelling_spells_per_100_max_mana`
- `skill_attrition_hit_damage_+%_final_vs_rare_or_unique_enemy_per_second_ever_in_presence_up_to_max`

### 触发类
- `trigger_meta_gem_damage_+%_final` (已添加模板)
- `generic_ongoing_trigger_maximum_energy` (元技能能量上限)
- `trigger_skills_refund_half_energy_spent_chance_%` (能量返还)

### 辅助宝石类（重要的 MORE 伤害）
- `support_ablation_offering_skill_damage_+%_final`
- `support_advancing_assault_melee_damage_+%_final_if_*`
- `support_bloodlust_melee_physical_damage_+%_final_vs_bleeding_enemies`
- `support_chanelling_damage_+%_final_per_second_channelling`
- `support_chaos_damage_+%_final_if_corpse_consumed_on_use`
- `support_close_combat_attack_damage_+%_final_from_distance`
- `support_deadly_poison_hit_damage_+%_final`
- `support_debilitate_hit_damage_+%_final_per_poison_stack`
- `support_elemental_armament_attack_damage_+%_final_per_elemental_ailment_on_target`
- `support_executioner_damage_vs_enemies_on_low_life_+%_final`
- `support_inhibitor_damage_+%_final_per_charge_type_or_infusion_type`
- `support_mobility_damage_+%_final`
- `support_pierce_damage_+%_final_per_pierced_target`
- `support_spell_damage_+%_final_while_above_90%_maximum_mana`

## 配置文件位置

```
.codebuddy/skills/pob-build-analyzer/config/pob_unimplemented_effects.yaml
```

## 扫描工具

### 1. 完整扫描
```bash
cd /g/POEMaster/.codebuddy/skills/pob-build-analyzer
python -B _scan_to_file.py
```
输出: `_scan_results.json`

### 2. 分析扫描结果
```bash
python -B _analyze_scan.py
```
分类显示: 主动技能/辅助宝石/触发类/其他

### 3. 快速查看
```bash
python -B _scan_all.py
```
直接输出到控制台（前 50 个）

## 下一步建议

1. **验证辅助宝石效果**: 检查 POB 的 ModCache.lua 是否已实现这些 support_* stats
2. **动态值读取**: 为 Demon Form/Charged Blast 添加层数读取逻辑
3. **测试新效果**: 对比添加注入前后的 DPS 差异
4. **扩展配置**: 根据实际构筑需求，逐步添加其他重要效果

## 扫描方法论

### 筛选标准
- ✅ 包含关键词: damage/more/elemental/fire/cold/lightning/chaos/physical/attack/spell/cast/speed/crit
- ✅ 排除: display_ 开头（仅显示）、monster/minion 相关、纯机制参数（_ms/_angle/_range 等）

### 数据来源
- **SkillStatMap.lua**: POB 的 stat 映射核心文件
- **扫描逻辑**: 遍历 Data/Skills/ 下所有技能定义，提取 constantStats 和 statInteractions

---

**维护者**: POEMaster Project  
**最后更新**: 2026-03-30
