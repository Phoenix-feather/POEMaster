"""Markdown 报告格式化模块。

职责：
- format_report: 将 full_analysis 数据格式化为 Markdown
- _format_section7: 光环/精魄部分
- _format_section_defence: 防御部分
"""
import logging
from .data_bridge import POEDataBridge
from .sensitivity import GEM_QUALITY_CAP

logger = logging.getLogger(__name__)

# =============================================================================
# 报告格式化（Markdown 表格）
# =============================================================================


def _format_section7(lines: list, aura_data: dict, skill_flags: dict,
                    baseline: dict, build_modifiers: dict = None):
    """格式化 Section 7: 光环与精魄分析。"""
    existing_auras = aura_data.get("existing_auras", [])
    candidate_auras = aura_data.get("candidate_auras", [])
    spirit_tests = aura_data.get("spirit_support_tests", [])
    budget = aura_data.get("spirit_budget", {})

    # 从 build_modifiers 提取构筑已有 modifier 总量
    bm = build_modifiers or {}
    speed_inc = bm.get("Speed_INC", {}).get("total", 0)
    # Damage_MORE 是所有 MORE 修饰符的汇总乘数（如 ×1.20 表示 20% MORE）
    total_more = bm.get("Damage_MORE", {}).get("total", 1)

    lines.append("## 9. 光环与精魄分析")
    lines.append("")

    # 7A: 现有光环
    lines.append("### 9A. 现有光环 DPS 贡献")
    lines.append("")

    if existing_auras:
        # 主表只显示关键指标
        lines.append("| # | 光环 | 裸光环 DPS | 真实 DPS | EHP | 精魄 |")
        lines.append("|---|------|------------|----------|-----|------|")
        
        for i, a in enumerate(existing_auras, 1):
            name = a.get("name", "?")
            bare_dp = a.get("bare_dps_pct", 0)
            real_dp = a.get("dps_pct", 0)
            ep = a.get("ehp_pct", 0)
            sp = a.get("spirit_cost", 0)

            # 触发攻击标注
            triggered_note = ""
            if a.get("has_triggered_dps"):
                trig_name = a.get("triggered_skill_name", "")
                if trig_name:
                    triggered_note = f" ⚔️{trig_name}(POB未算)"

            # 裸光环 DPS（无辅助，用于和推荐光环对比）
            bare_str = f"{bare_dp:+.1f}%"
            # 真实 DPS（含辅助）
            real_str = f"{real_dp:+.1f}%"
            if a.get("simulated"):
                real_str += " ⚠️模拟"

            # 辅助额外贡献（真实 - 裸光环的额外增益）
            supports_extra = a.get("supports_extra_pct", 0)
            if abs(supports_extra) >= 0.1:
                sup_names = a.get("support_names", [])
                if sup_names:
                    real_str += f" (辅助+{supports_extra:.1f}%)"
                else:
                    real_str += f" (辅助+{supports_extra:.1f}%)"

            # 条件标注（仅用于主表显示）
            ranges = a.get("config_ranges", [])
            label = ""
            mid = 0
            if ranges:
                for cr in ranges:
                    label = cr.get("label", cr["config_var"])
                    label = label.rstrip(":")
                    mid = cr.get("mid", 0)
                    real_str += f" (条件: {label}={mid})"

            lines.append(f"| {i} | {name}{triggered_note} | {bare_str} | {real_str} | {ep:+.1f}% | {sp:.0f} |")
            
            # 可折叠详情区块
            has_details = (
                ranges or 
                abs(supports_extra) >= 0.1 or 
                a.get("gem_level", 0) > 0
            )
            
            if has_details:
                lines.append("")
                lines.append(f"<details>")
                lines.append(f"<summary><b>{name} 详细数据</b></summary>")
                lines.append("")
                
                # 条件参数范围
                if ranges:
                    lines.append("### 条件参数范围")
                    lines.append("")
                    lines.append("| 端点 | 裸光环 | 真实 | 辅助增益 | Speed INC |")
                    lines.append("|------|--------|------|----------|-----------|")
                    
                    for cr in ranges:
                        label = cr.get("label", cr["config_var"])
                        label = label.rstrip(":")
                        actual_max = int(cr["actual_max"])
                        pct_min = cr.get("dps_pct_min", 0)
                        pct_max = cr.get("dps_pct_max", 0)
                        bare_pct_min = cr.get("bare_pct_min", pct_min)
                        bare_pct_max = cr.get("bare_pct_max", pct_max)
                        
                        # Speed INC 变化
                        speed_inc_min = cr.get("speed_inc_min", 0)
                        speed_inc_bare = cr.get("speed_inc_min_bare", 0)
                        speed_inc_real = cr.get("speed_inc_max", 0)
                        
                        # min 端点
                        speed_min_str = f"{speed_inc_min:.0f}%" if speed_inc_min else "—"
                        sup_min = pct_min - bare_pct_min
                        sup_min_str = f"{sup_min:+.1f}%" if abs(sup_min) >= 0.1 else "—"
                        lines.append(f"| {label}=0 | {bare_pct_min:+.1f}% | {pct_min:+.1f}% | {sup_min_str} | {speed_min_str} |")
                        
                        # max 端点
                        speed_max_str = f"{speed_inc_min:.0f}%→{speed_inc_real:.0f}%" if speed_inc_real > speed_inc_min else f"{speed_inc_real:.0f}%"
                        sup_max = pct_max - bare_pct_max
                        sup_max_str = f"{sup_max:+.1f}%" if abs(sup_max) >= 0.1 else "—"
                        lines.append(f"| {label}={actual_max} | {bare_pct_max:+.1f}% | {pct_max:+.1f}% | {sup_max_str} | {speed_max_str} |")
                    lines.append("")
                
                # 辅助贡献
                if abs(supports_extra) >= 0.1:
                    lines.append("### 辅助贡献")
                    lines.append("")
                    sup_names = a.get("support_names", [])
                    
                    # 使用 POEDataBridge 查询辅助效果
                    try:
                        bridge = POEDataBridge()
                        for sup_name in sup_names:
                            # 查找辅助宝石 ID
                            sup_id = bridge.get_support_by_name(sup_name)
                            if sup_id:
                                # 查询效果和条件
                                effects = bridge.get_support_effects(sup_id)
                                if effects:
                                    # 格式化显示
                                    effect_strs = []
                                    for e in effects:
                                        if e['condition']:
                                            effect_strs.append(f"{e['effect']} (条件: {e['condition']})")
                                        else:
                                            effect_strs.append(e['effect'])
                                    lines.append(f"- **{sup_name}**: {', '.join(effect_strs)}")
                                else:
                                    lines.append(f"- **{sup_name}**")
                            else:
                                # 查询失败，只显示名称
                                lines.append(f"- **{sup_name}**")
                        bridge.close()
                    except Exception as e:
                        # 降级方案：只显示名称
                        logger.warning(f"Failed to query support effects: {e}")
                        for sup_name in sup_names:
                            lines.append(f"- **{sup_name}**")
                    
                    cond_str = f"（{label}={mid}时）" if label else ""
                    lines.append(f"- 总辅助贡献: **+{supports_extra:.1f}%** DPS{cond_str}")
                    # 显示各端点的辅助贡献
                    if ranges:
                        endpoint_parts = []
                        for cr in ranges:
                            cr_label = cr.get("label", cr["config_var"]).rstrip(":")
                            cr_max = int(cr["actual_max"])
                            cr_pct_min = cr.get("dps_pct_min", 0)
                            cr_bare_pct_min = cr.get("bare_pct_min", cr_pct_min)
                            cr_pct_max = cr.get("dps_pct_max", 0)
                            cr_bare_pct_max = cr.get("bare_pct_max", cr_pct_max)
                            sup_min = cr_pct_min - cr_bare_pct_min
                            sup_max = cr_pct_max - cr_bare_pct_max
                            endpoint_parts.append(f"{cr_label}=0时{sup_min:+.1f}%，{cr_label}={cr_max}时{sup_max:+.1f}%")
                        lines.append(f"- 端点差异: {', '.join(endpoint_parts)}")
                    lines.append("")
                
                # 基础数值
                gem_lv = a.get("gem_level", 0)
                eff_lv = a.get("effective_level", gem_lv)
                more_val = a.get("more_per_30", 0)
                spd_per_q = a.get("quality_speed_inc", 0)
                level_bonus = a.get("level_bonus", 0)
                
                if gem_lv > 0:
                    lines.append("### 基础数值")
                    lines.append("")
                    if eff_lv != gem_lv:
                        lines.append(f"- 有效等级: **Lv{eff_lv}** (基础 Lv{gem_lv} + 辅助 +{level_bonus})")
                    else:
                        lines.append(f"- 有效等级: **Lv{eff_lv}**")
                    if more_val > 0:
                        lines.append(f"- MORE per 30 Resonance: **{more_val:.0f}%**")
                    if spd_per_q > 0:
                        gem_q = a.get("gem_quality", 0)
                        if gem_q > 0:
                            lines.append(f"- Speed INC per quality: **{spd_per_q:.2f}%** (q{gem_q} = {gem_q * spd_per_q:.1f}% INC)")
                    lines.append("")
                
                lines.append("</details>")
                lines.append("")
        
        lines.append("")

        # 模拟值说明
        simulated_auras = [a for a in existing_auras if a.get("simulated")]
        if simulated_auras:
            lines.append("**⚠️模拟值说明：**")
            lines.append("")
            for a in simulated_auras:
                name = a.get("name", "?")
                gem_level = a.get("gem_level", "?")
                # 数据驱动：根据 aura 数据中的字段动态生成说明
                desc_parts = [f"- **{name}** (Lv{gem_level}):"]
                # EC: 三元素分别注入
                if a.get("damage_breakdown") and a.get("ec_detail"):
                    raw_val = a.get("raw_value", 0)
                    bd = a["damage_breakdown"]
                    ec = a["ec_detail"]
                    fire_pct = bd.get("fire", 0)
                    cold_pct = bd.get("cold", 0)
                    lightning_pct = bd.get("lightning", 0)
                    dps_f = ec.get("fire_more_dps", 0)
                    dps_c = ec.get("cold_more_dps", 0)
                    dps_l = ec.get("lightning_more_dps", 0)
                    desc_parts[0] += f" 分别注入 {raw_val:.0f}% MORE 到火/冰/电取平均。伤害构成：火 {fire_pct:.1f}% / 冰 {cold_pct:.1f}% / 电 {lightning_pct:.1f}%"
                    lines.append(desc_parts[0])
                    lines.append(f"  三次模拟 DPS：火 {dps_f:.0f} / 冰 {dps_c:.0f} / 电 {dps_l:.0f}")
                # Charge Infusion 或其他有 charge_counts 的光环
                elif a.get("charge_counts"):
                    charges = a["charge_counts"]
                    charge_strs = [f"{k[:1].upper()}={v}" for k, v in charges.items()]
                    desc_parts[0] += f" 需启用 Charge 配置才能生效，已模拟 {'/'.join(charge_strs)}"
                    lines.append(desc_parts[0])
                else:
                    desc_parts[0] += " 已模拟条件配置"
                    lines.append(desc_parts[0])
            lines.append("")

            # 通用说明
            lines.append("**模拟方法说明：**")
            lines.append("")
            lines.append("- **等级前提**：光环模拟基于构筑实际宝石等级数据（非固定 Level 20）")
            lines.append("- **裸光环 DPS**：仅光环宝石效果（禁用所有辅助宝石），用于和「潜在光环推荐」对比。真实 DPS 含辅助宝石额外增益，标注在括号中")
            lines.append("- **DPS 贡献计算**：移除光环后 DPS 下降百分比（正值=正向贡献）。条件光环需注入参数才能生效，默认注入参数最大值的 50%，标注在真实 DPS 括号中")
            speed_label = "攻击速度" if skill_flags.get("is_attack", False) else "施法速度"
            lines.append(f"- **构筑已有 modifier**：{speed_label} INC {speed_inc:.0f}%（来自 POB skillModList），总 MORE ×{total_more:.2f}。INC 叠加为加法（新增边际递减），MORE 叠加为乘法")
            lines.append(f"- **品质上限**：所有宝石品质按 {GEM_QUALITY_CAP}% 上限计算（游戏实际上限）。构筑中超品质宝石已自动降级")
            lines.append("- **条件范围计算**：设置参数绝对值（0 和 max），对比「无光环」DPS。Speed 门槛效果从 POB skillModList 读取端点 INC 差值，边际 = 新增INC / (1+已有INC)")
            lines.append("- **期望收益计算**：对于 EC 等随机效果光环，期望 = 效果值 × 受影响技能元素占比之和 ÷ 3（因为随机选择火/冰/电之一）")
            lines.append("")

        # 纯防御光环（移除后 DPS 影响小但 EHP 有影响）
        def_auras = [a for a in existing_auras
                     if abs(a.get("dps_pct", 0)) < 0.1
                     and abs(a.get("ehp_pct", 0)) >= 0.1]
        if def_auras:
            lines.append("**纯防御光环**（移除后 EHP 下降）：")
            lines.append("")
            for a in def_auras:
                lines.append(f"- **{a['name']}**: EHP {a['ehp_pct']:+.1f}%, 精魄 {a['spirit_cost']:.0f}")
            lines.append("")

        dps_auras = [a for a in existing_auras if abs(a.get("dps_pct", 0)) >= 0.1]
        zero_auras = [a for a in existing_auras
                      if abs(a.get("dps_pct", 0)) < 0.1
                      and abs(a.get("ehp_pct", 0)) < 0.1]

        if zero_auras:
            lines.append(f"**DPS/EHP 影响未检测到** ({len(zero_auras)} 个)：")
            lines.append("")
            lines.append("这些光环可能提供非DPS收益（如生存/功能性），或其效果依赖动态条件（如Frenzy Charge）而POB未完全计算。")
            lines.append("")
            for a in zero_auras:
                trig_note = ""
                if a.get("has_triggered_dps"):
                    trig_name = a.get("triggered_skill_name", "")
                    trig_note = f" — ⚔️有触发攻击「{trig_name}」但POB未实现DPS计算" if trig_name else " — ⚔️有触发攻击但POB未实现DPS计算"
                lines.append(f"- **{a['name']}**: 精魄 {a['spirit_cost']:.0f}{trig_note}")
            lines.append("")
    else:
        lines.append("构筑中无活跃光环。")
        lines.append("")

    # 7B: 潜在光环推荐
    lines.append("### 9B. 潜在光环推荐")
    lines.append("")

    effective_candidates = [c for c in candidate_auras
                            if c.get("dps_pct", 0) > 0.1]
    failed_candidates = [c for c in candidate_auras
                          if c.get("dps_pct", 0) <= 0.1]

    if effective_candidates:
        lines.append("| # | 光环 | 精魄 | DPS% | EHP% | 说明 |")
        lines.append("|---|------|------|------|------|------|")
        for i, c in enumerate(effective_candidates, 1):
            name = c.get("name", "?")
            name_cn = c.get("name_cn", "")
            sp = c.get("spirit", 0)
            dp = c.get("dps_pct", 0)
            ep = c.get("ehp_pct", 0)
            desc = c.get("description", "")
            # 精魄不足时在说明中标注
            if c.get("spirit_note"):
                desc = f"{c['spirit_note']}; {desc}" if desc else c["spirit_note"]
            display = f"{name}" + (f"（{name_cn}）" if name_cn else "")
            lines.append(f"| {i} | {display} | {sp:.0f} | {dp:+.1f}% | {ep:+.1f}% | {desc} |")
        lines.append("")

    if failed_candidates:
        lines.append("**无 DPS 影响：**")
        lines.append("")
        for c in failed_candidates:
            name = c.get("name", "?")
            name_cn = c.get("name_cn", "")
            display = f"{name}" + (f"（{name_cn}）" if name_cn else "")
            lines.append(f"- {display}")
        lines.append("")

    # 9C: 精魄辅助推荐
    lines.append("### 9C. 精魄辅助推荐")
    lines.append("")
    
    # 分离有效和无效结果（类似光环推荐）
    effective_spirit = [s for s in spirit_tests if s.get("dps_pct", 0) > 0.1]
    failed_spirit = [s for s in spirit_tests if s.get("dps_pct", 0) <= 0.1]
    
    if effective_spirit:
        # 按辅助名称去重：同一辅助只保留 DPS% 最高的结果
        best_by_name = {}
        for s in effective_spirit:
            name = s.get("name", "")
            existing = best_by_name.get(name)
            if not existing or abs(s.get("dps_pct", 0)) > abs(existing.get("dps_pct", 0)):
                best_by_name[name] = s
        unique_spirit = list(best_by_name.values())
        unique_spirit.sort(key=lambda x: -abs(x.get("dps_pct", 0)))
        top_results = unique_spirit[:5]
        
        lines.append("| # | 精魄辅助 | 精魄 | DPS% | 条件 | 来源 |")
        lines.append("|---|----------|------|------|------|------|")
        for i, s in enumerate(top_results, 1):
            name = s.get("name", "?")
            name_cn = s.get("name_cn", "")
            sp = s.get("spirit", 0)
            dp = s.get("dps_pct", 0)
            cond = s.get("condition", "")
            # 精魄不足时在条件中标注
            if s.get("spirit_note"):
                cond = f"{s['spirit_note']}; {cond}" if cond else s["spirit_note"]
            estimated = " ⚠️估算" if s.get("estimated") else ""
            
            # 来源标注
            source = s.get("source", "unknown")
            source_display = "硬编码" if source == "hardcoded" else "动态扫描" if source == "dynamic" else "未知"
            
            display = f"{name}" + (f"（{name_cn}）" if name_cn else "")
            lines.append(f"| {i} | {display} | {sp:.0f} | {dp:+.1f}% | {cond}{estimated} | {source_display} |")
        lines.append("")
    
    if failed_spirit:
        lines.append(f"其余 {len(set(s.get('skill_id','') for s in failed_spirit))} 个辅助无可模拟的 DPS 效果。")
        lines.append("")
    
    if not effective_spirit and not failed_spirit:
        lines.append("构筑中无活跃光环，无法添加精魄辅助。")
        lines.append("")

    # 7D: Spirit Budget
    lines.append("### 9D. 精魄预算")
    lines.append("")

    total = budget.get("total", 0)
    reserved = budget.get("reserved", 0)
    available = budget.get("available", 0)
    rec_total = budget.get("recommended_total", 0)
    rec_remain = budget.get("recommended_remaining", 0)

    lines.append("| 项目 | 精魄 |")
    lines.append("|------|------|")
    lines.append(f"| 总精魄 | {total:.0f} |")
    lines.append(f"| 已用精魄 | {reserved:.0f} |")
    lines.append(f"| 可用精魄 | {available:.0f} |")

    if rec_total > 0:
        lines.append(f"| 推荐光环消耗 | {rec_total:.0f} |")
        lines.append(f"| 推荐后剩余 | {rec_remain:.0f} |")

    if rec_remain < 0:
        lines.append("")
        lines.append("**注意**: 推荐光环的精魄总消耗超过可用精魄，需要根据优先级取舍。")

    lines.append("")

    # 7E: 数据一致性校验
    warnings = aura_data.get("warnings", [])
    if warnings:
        lines.append("### 9E. 数据一致性检查")
        lines.append("")
        lines.append("**⚠️ 以下项目需要人工确认：**")
        lines.append("")
        for w in warnings:
            lines.append(f"- {w}")
        lines.append("")

    # 9F: POB 未实现效果预估
    unimpl_effects = aura_data.get("unimplemented_effects", [])
    if unimpl_effects:
        lines.append("### 9F. POB 未实现效果预估")
        lines.append("")
        lines.append("**⚠️ 以下技能效果在 POB 中未实现，已通过配置模拟：**")
        lines.append("")
        lines.append("| 技能 | 效果描述 | DPS 预估 |")
        lines.append("|------|----------|----------|")
        for ue in unimpl_effects:
            lines.append(f"| **{ue['skill_name']}** | {ue['description']} | **+{ue['delta_pct']:.1f}%** |")
        lines.append("")
        lines.append("**注**: 这些效果由 `config/pob_unimplemented_effects.yaml` 配置，")
        lines.append("实际游戏效果可能因条件触发方式不同而有差异。")
        lines.append("")


def _format_section_defence(lines: list, defence_ov: dict, baseline: dict):
    """格式化 Part 4: 防御面（概览）。灵敏度已移至 Section 3B。"""
    if not defence_ov:
        return

    total_ehp = defence_ov.get("total_ehp", 0)
    if total_ehp <= 0:
        return

    pools = defence_ov.get("pools", {})
    resistances = defence_ov.get("resistances", {})
    max_hit = defence_ov.get("max_hit_taken", {})
    dot_ehp = defence_ov.get("dot_ehp", {})
    taken_hit_mult = defence_ov.get("taken_hit_mult", {})
    weakest = defence_ov.get("weakest_type", "")
    weakest_pct = defence_ov.get("weakest_pct", 0)
    num_hits = defence_ov.get("total_number_of_hits", 0)

    # === Part 4.1: 防御概览 ===
    lines.append("## 4. 防御面")
    lines.append("")

    # 4A 生命池构成
    lines.append("### 4A. 生命池构成")
    lines.append("")
    lines.append("| 资源 | 数值 | 备注 |")
    lines.append("|------|------|------|")

    life = pools.get("Life", 0)
    es = pools.get("EnergyShield", 0)
    mana = pools.get("Mana", 0)
    ward = pools.get("Ward", 0)
    mom_pct = pools.get("MoMPct", 0)

    lines.append(f"| Life | {life:,.0f} | — |")
    if es > 0:
        lines.append(f"| Energy Shield | {es:,.0f} | — |")
    lines.append(f"| Mana | {mana:,.0f} | 可用 {pools.get('ManaUnreserved', 0):,.0f} |")
    if ward > 0:
        lines.append(f"| Ward | {ward:,.0f} | 每次受击刷新 |")
    if mom_pct > 0:
        lines.append(f"| MoM | {mom_pct:.0f}% | 魔力优先承受伤害 |")
    lines.append("")

    # 4B 减伤层
    lines.append("### 4B. 减伤层")
    lines.append("")

    block = defence_ov.get("block", {})
    suppression = defence_ov.get("suppression", 0)
    deflect = defence_ov.get("deflect", 0)

    lines.append("| 层 | 数值 |")
    lines.append("|------|------|")
    lines.append(f"| 护甲 | {defence_ov.get('armour', 0):,.0f} |")
    lines.append(f"| 闪避 | {defence_ov.get('evasion', 0):,.0f} |")
    lines.append(f"| 攻击格挡 | {block.get('BlockChance', 0):.0f}% |")
    lines.append(f"| 法术格挡 | {block.get('SpellBlockChance', 0):.0f}% |")
    if suppression > 0:
        lines.append(f"| 法术压制 | {suppression:.0f}% |")
    if deflect > 0:
        lines.append(f"| 偏转 | {deflect:.0f}% |")
    lines.append("")

    # 4C 抗性面板
    lines.append("### 4C. 抗性面板")
    lines.append("")
    lines.append("| 元素 | 当前 | 上限 | 状态 |")
    lines.append("|------|------|------|------|")

    elem_cn = {"Fire": "火焰", "Cold": "冰霜", "Lightning": "闪电", "Chaos": "混沌"}
    for elem, res_data in resistances.items():
        cur = res_data["Resist"]
        mx = res_data["ResistMax"]
        over = res_data["ResistOverCap"]
        gap = mx - cur
        if gap <= 0:
            status = f"满 ({over:+.0f}%溢出)" if over > 0 else "满"
        elif gap <= 5:
            status = f"接近 (差 {gap:.0f}%)"
        else:
            status = f"未满 (差 {gap:.0f}%)"
        cn = elem_cn.get(elem, elem)
        lines.append(f"| {cn} | {cur:.0f}% | {mx:.0f}% | {status} |")
    lines.append("")

    # 抗性分析总结
    unfilled = [elem_cn.get(e, e) for e, r in resistances.items() if r["Resist"] < r["ResistMax"]]
    overcapped = [elem_cn.get(e, e) for e, r in resistances.items() if r["ResistOverCap"] > 20]
    if unfilled:
        lines.append(f"未满抗性: {', '.join(unfilled)} — 优先补满可显著提升对应元素 EHP。")
        lines.append("")
    if overcapped:
        lines.append(f"过度堆叠: {', '.join(overcapped)} — 超出上限 20%+，可考虑将属性分配到其他维度。")
        lines.append("")

    # 4D MaxHitTaken
    lines.append("### 4D. 最大承伤 (MaxHitTaken)")
    lines.append("")
    lines.append(f"**TotalEHP = {total_ehp:,.0f}**（平均承受 {num_hits:.1f} 次攻击）")
    lines.append("")
    lines.append("| 伤害类型 | MaxHitTaken | 占最强% |")
    lines.append("|----------|-------------|--------|")

    max_val = max(max_hit.values(), default=1)
    for dtype, val in max_hit.items():
        pct = val / max_val * 100 if max_val > 0 else 0
        marker = " ← 最短板" if dtype == weakest else ""
        cn = elem_cn.get(dtype, dtype)
        lines.append(f"| {cn} | {val:,.0f} | {pct:.0f}%{marker} |")

    if weakest:
        lines.append("")
        lines.append(f"**最短板**: {elem_cn.get(weakest, weakest)}"
                     f"（仅承受 {max_hit.get(weakest, 0):,.0f} 伤害"
                     f"，为最强的 {weakest_pct:.0f}%）")
    lines.append("")

    # 2.1e 承伤乘数（弱点诊断）
    has_thm = any(v > 0 for v in taken_hit_mult.values())
    if has_thm:
        lines.append("### 4E. 承伤乘数 (TakenHitMult)")
        lines.append("")
        lines.append("数值越小越好，表示实际承受伤害占原始伤害的比例。")
        lines.append("")
        lines.append("| 伤害类型 | 承伤乘数 | 含义 |")
        lines.append("|----------|---------|------|")
        for dtype, mult in taken_hit_mult.items():
            if mult > 0:
                cn = elem_cn.get(dtype, dtype)
                pct = mult * 100
                marker = " ← 最短板" if dtype == weakest else ""
                lines.append(f"| {cn} | {mult:.3f} ({pct:.1f}%) | 每承受 100 伤害实际受 {pct:.0f}{marker} |")
        lines.append("")

    # 2.1f DotEHP
    has_dot = any(v > 0 for v in dot_ehp.values())
    if has_dot:
        lines.append("### 4F. DOT 有效生命")
        lines.append("")
        lines.append("| 伤害类型 | DotEHP |")
        lines.append("|----------|--------|")
        for dtype, val in dot_ehp.items():
            if val > 0:
                cn = elem_cn.get(dtype, dtype)
                lines.append(f"| {cn} | {val:,.0f} |")
        lines.append("")

    lines.append("")


def format_report(data: dict, global_data: dict = None) -> str:
    """将 full_analysis() 返回的数据格式化为 Markdown 表格报告。

    Args:
        data: full_analysis() 的返回值
        global_data: extract_global_data() 的返回值（可选，用于合成报告）

    Returns:
        完整的 Markdown 格式报告字符串
    """
    lines = []

    baseline = data.get("baseline", {})
    main_skill = data.get("main_skill", {})
    skill_flags = data.get("skill_flags", {})
    sensitivity = data.get("sensitivity", [])
    talent_value = data.get("talent_value", [])
    talent_exploration = data.get("talent_exploration", [])
    jewel_diag = data.get("jewel_diagnosis", [])
    dps_bd = data.get("dps_breakdown", {})

    # 全局数据优先从 global_data 取，fallback 从 data 取（兼容旧调用）
    g = global_data or data
    defence_ov = g.get("defence_overview", {})
    defence_sens = g.get("defence_sensitivity", [])
    res_ov = g.get("resource_overview", {})
    life_recov = g.get("life_recovery", {})
    mana_recov = g.get("mana_recovery", {})
    recovery_sens = g.get("recovery_sensitivity", [])
    build_modifiers = g.get("build_modifiers", {})
    build_attributes = g.get("build_attributes", {})
    jewel_overview = g.get("jewel_overview", [])

    skill_name = main_skill.get("name", "未知")
    total_dps = baseline.get("TotalDPS", 0)
    avg_hit = baseline.get("AverageHit", 0)
    speed = baseline.get("Speed", 0)
    crit_chance = baseline.get("CritChance", 0)
    crit_multi = baseline.get("CritMultiplier", 0)
    total_ehp = baseline.get("TotalEHP", 0)

    # --- 标题 ---
    lines.append(f"# {skill_name} 构筑全面分析报告")
    lines.append("")

    # 零效天赋（提前计算，用于执行摘要和 Section 4）
    zero_talents = [t for t in talent_value
                    if abs(t.get("dps_pct", 0)) <= 0.1 and abs(t.get("ehp_pct", 0)) <= 0.1]

    # === Part 0: 执行摘要 ===
    lines.append("## 0. 执行摘要")
    lines.append("")

    # 0a. 维度评分
    lines.append("### 维度概览")
    lines.append("")
    lines.append("| 维度 | 关键指标 |")
    lines.append("|------|---------|")
    lines.append(f"| 进攻 | TotalDPS **{total_dps:,.0f}** |")
    lines.append(f"| 防御 | TotalEHP **{defence_ov.get('total_ehp', 0):,.0f}**"
                 f"（最短板: {defence_ov.get('weakest_type', '—')}） |")
    if res_ov:
        spirit_data = res_ov.get("spirit", {})
        spirit_pct = spirit_data.get("reserved_pct", 0)
        lines.append(f"| 资源 | Spirit 占用 **{spirit_pct:.0f}%** |")
    if life_recov and life_recov.get("total_rate", 0) > 0:
        lines.append(f"| 恢复 | 生命恢复 **{life_recov['total_rate']:,.0f}/s** |")
    lines.append("")

    # 0b. 关键发现
    findings = []

    # 防御短板
    if defence_ov and defence_ov.get("weakest_type"):
        weakest_name = defence_ov["weakest_type"]
        elem_cn = {"Physical": "物理", "Fire": "火焰", "Cold": "冰霜",
                   "Lightning": "闪电", "Chaos": "混沌"}
        weakest_cn = elem_cn.get(weakest_name, weakest_name)
        weakest_val = defence_ov["max_hit_taken"].get(weakest_name, 0)
        strongest_val = max(defence_ov["max_hit_taken"].values(), default=1)
        if strongest_val > 0 and weakest_val / strongest_val < 0.7:
            findings.append(f"⚠️ **{weakest_cn}抗性/防御是最短板**"
                            f"（承伤仅 {weakest_val:,.0f}，为最强的"
                            f" {weakest_val/strongest_val*100:.0f}%）")

    # 抗性未满
    if defence_ov:
        for elem, res in defence_ov.get("resistances", {}).items():
            gap = res.get("ResistMax", 75) - res.get("Resist", 0)
            if gap > 10:
                cn = elem_cn.get(elem, elem)
                findings.append(f"⚠️ {cn}抗性差 **{gap:.0f}%** 未满")

    # 精魄紧张
    if res_ov:
        spirit_pct = res_ov.get("spirit", {}).get("reserved_pct", 0)
        if spirit_pct > 80:
            findings.append(f"🔴 精魄预算非常紧张（{spirit_pct:.0f}% 占用）")
        elif spirit_pct > 60:
            findings.append(f"⚠️ 精魄预算紧张（{spirit_pct:.0f}% 占用）")

    # 零效天赋
    if zero_talents:
        findings.append(f"⚠️ {len(zero_talents)} 个已分配天赋对 DPS 和 EHP 均无可测量影响")

    # DPS 灵敏度 Top 1
    effective_sens = [s for s in sensitivity if s.get("needed_value") is not None]
    if effective_sens:
        top = effective_sens[0]
        tl = top.get("target_label", "DPS")
        lines.append("")  # suppress unused warning
        findings.append(f"💡 **{top.get('key', '?')}** 对 {tl} 影响最大"
                        f"（每 1{top.get('unit', '')} 提升 {top.get('dps_per_unit', 0):.2f}% {tl}）")

    if findings:
        lines.append("### 关键发现")
        lines.append("")
        for i, f in enumerate(findings[:5], 1):
            lines.append(f"{i}. {f}")
        lines.append("")

    # 0c. Top 优化建议
    if effective_sens:
        lines.append("### 优化方向 Top 3")
        lines.append("")
        for i, s in enumerate(effective_sens[:3], 1):
            key = s.get("key", "?")
            mod_type = s.get("mod_type", "?")
            needed = s.get("needed_value", 0)
            unit = s.get("unit", "")
            dpu = s.get("dps_per_unit", 0)
            tl = s.get("target_label", "DPS")
            tp = s.get("target_pct", 20)
            lines.append(
                f"{i}. **{key}** ({mod_type}): "
                f"每 1{unit} 提升 {dpu:.2f}% {tl}，"
                f"需要 +{needed:.0f}{unit} 达到 +{tp:.0f}% {tl}"
            )
        lines.append("")

    # === Section 1: 构筑基线 ===
    lines.append("## 1. 构筑基线")
    lines.append("")

    # 1A. 构筑修饰符汇总
    if build_modifiers:
        lines.append("### 构筑修饰符")
        lines.append("")
        lines.append("| 修饰符 | 总量 | 天赋 | 装备 | 珠宝 |")
        lines.append("|--------|------|------|------|------|")
        is_attack = skill_flags.get("is_attack", False)
        speed_label = "攻击速度 INC" if is_attack else "施法速度 INC"
        bm_order = [
            ("Speed_INC", speed_label),
            ("Damage_INC", "伤害 INC"),
            ("ElementalDamage_INC", "元素伤害 INC"),
            ("CritChance_INC", "暴击率 INC"),
            ("CritMultiplier_INC", "暴击伤害 INC"),
            ("Damage_MORE", "伤害 MORE"),
        ]
        for key, label in bm_order:
            m = build_modifiers.get(key)
            if not m:
                continue
            is_more = key.endswith("_MORE")
            if is_more:
                # MORE: total 是乘数，source value 是百分比
                # tree/item/jewel 各自的乘积
                tree_mult = 1.0
                item_mult = 1.0
                jewel_mult = 1.0
                for s in m["sources"]:
                    v = s.get("value", 0)
                    cat = s.get("category", "")
                    if cat == "Tree":
                        tree_mult *= (1 + v / 100)
                    elif cat == "Item":
                        item_mult *= (1 + v / 100)
                    elif cat == "Jewel":
                        jewel_mult *= (1 + v / 100)
                # 转换为百分比：×1.30 → +30%
                tree_pct = (tree_mult - 1) * 100
                item_pct = (item_mult - 1) * 100
                jewel_pct = (jewel_mult - 1) * 100
                tree_fmt = f"+{tree_pct:.0f}%" if tree_mult != 1.0 else "—"
                item_fmt = f"+{item_pct:.0f}%" if item_mult != 1.0 else "—"
                jewel_fmt = f"+{jewel_pct:.0f}%" if jewel_mult != 1.0 else "—"
            else:
                tree_val = sum(s.get("value", 0) for s in m["sources"] if s.get("category") == "Tree")
                item_val = sum(s.get("value", 0) for s in m["sources"] if s.get("category") == "Item")
                jewel_val = sum(s.get("value", 0) for s in m["sources"] if s.get("category") == "Jewel")
                tree_fmt = f"+{tree_val:.0f}%" if tree_val else "—"
                item_fmt = f"+{item_val:.0f}%" if item_val else "—"
                jewel_fmt = f"+{jewel_val:.0f}%" if jewel_val else "—"
            if is_more:
                # total 是乘数，转换为百分比
                total_pct = (m['total'] - 1) * 100
                total_disp = f"{total_pct:+.1f}%"
            else:
                suffix = "%" if "INC" in key else ""
                total_disp = f"{m['total']:.0f}{suffix}"
            lines.append(f"| {label} | {total_disp} | {tree_fmt} | {item_fmt} | {jewel_fmt} |")
        lines.append("")

    # 1B. 构筑属性
    if build_attributes:
        lines.append("### 构筑属性")
        lines.append("")
        lines.append("| 属性 | 数值 |")
        lines.append("|------|------|")
        attr_labels = {
            "TotalAttr": "总属性", "Str": "力量", "Dex": "敏捷", "Int": "智力",
            "Accuracy": "命中",
        }
        for k, label in attr_labels.items():
            v = build_attributes.get(k)
            if v is not None and v != 0:
                lines.append(f"| {label} | {v:,.0f} |")
        lines.append("")

    # 1C. 技能 KPI
    lines.append("### 技能 KPI")
    lines.append("")
    lines.append("| 指标 | 数值 |")
    lines.append("|------|------|")
    lines.append(f"| 主技能 | {skill_name} |")

    flag_tags = []
    if skill_flags.get("is_spell"):
        flag_tags.append("法术")
    if skill_flags.get("is_attack"):
        flag_tags.append("攻击")
    if skill_flags.get("is_projectile"):
        flag_tags.append("投射物")
    if skill_flags.get("is_dot"):
        flag_tags.append("DOT")
    if flag_tags:
        lines.append(f"| 技能类型 | {', '.join(flag_tags)} |")

    lines.append(f"| TotalDPS | **{total_dps:,.0f}** |")
    lines.append(f"| AverageHit | {avg_hit:,.0f} |")
    lines.append(f"| Speed | {speed:.2f}/s |")
    if crit_chance:
        lines.append(f"| CritChance | {crit_chance:.1f}% |")
    if crit_multi:
        lines.append(f"| CritMultiplier | {crit_multi:.2f}x |")
    lines.append(f"| TotalEHP | {total_ehp:,.0f} |")
    if defence_ov and defence_ov.get("weakest_type"):
        weakest_name = defence_ov["weakest_type"]
        weakest_val = defence_ov["max_hit_taken"].get(weakest_name, 0)
        elem_cn = {"Physical": "物理", "Fire": "火焰", "Cold": "冰霜", "Lightning": "闪电", "Chaos": "混沌"}
        lines.append(f"| 最短板承伤 | **{weakest_val:,.0f}** ({elem_cn.get(weakest_name, weakest_name)}) |")
    lines.append("")

    # --- Section 2: DPS 来源拆解 ---
    lines.append("## 2. DPS 来源拆解")
    lines.append("")

    formula_items = dps_bd.get("formula_items", [])
    active_types = dps_bd.get("active_damage_types", [])
    if active_types:
        lines.append(f"活跃伤害类型: {', '.join(active_types)}")
        lines.append("")

    for fi in formula_items:
        fname = fi["formula_name"]
        dval = fi["display_value"]
        lines.append(f"### {fname} = {dval}")
        lines.append("")

        # 公式详情（如 effMult 的计算过程）
        formula_detail = fi.get("formula_detail", "")
        if formula_detail:
            lines.append(f"**公式**: `{formula_detail}`")
            lines.append("")

        # 类别汇总
        cat_sum = fi.get("category_summary", {})
        is_more = fi.get("key", "").endswith("_MORE")
        if cat_sum:
            if is_more:
                lines.append("**类别汇总**: " + " | ".join(
                    f"{cat}: +{(val-1)*100:.0f}%" for cat, val in
                    sorted(cat_sum.items(), key=lambda x: abs(x[1] - 1), reverse=True)
                ))
            else:
                lines.append("**类别汇总**: " + " | ".join(
                    f"{cat}: {val:+.1f}" for cat, val in
                    sorted(cat_sum.items(), key=lambda x: abs(x[1]), reverse=True)
                ))
            lines.append("")

        # 详细来源表格
        sources = fi.get("sources", [])
        if sources:
            lines.append("| 来源 | 类别 | 值 |")
            lines.append("|------|------|-----|")
            for s in sources:
                label = s.get("label", s.get("source", "?"))
                cat = s.get("category", "?")
                val = s.get("value", 0)
                detail = s.get("detail", "")
                if is_more:
                    # MORE source 值是百分比（如 20 = +20% MORE）
                    val_str = f"+{val:.1f}% MORE"
                elif abs(val) >= 1000:
                    val_str = f"{val:+,.0f}"
                else:
                    val_str = f"{val:+.1f}"
                if detail:
                    val_str = f"{val_str} ({detail})"
                lines.append(f"| {label} | {cat} | {val_str} |")
            lines.append("")

    # --- Section 3: 灵敏度分析（分维度） ---
    lines.append("## 3. 灵敏度分析")
    lines.append("")

    # 3A: 进攻灵敏度（DPS）
    lines.append("### 3A. 进攻灵敏度（DPS）")
    lines.append("")

    off_effective = [s for s in sensitivity if s.get("needed_value") is not None]
    off_unreachable = [s for s in sensitivity if s.get("needed_value") is None]

    if off_effective:
        lines.append("| # | 维度 | 类型 | 所需值 | 单位 | 效果/单位 | 当前值 | 公式 |")
        lines.append("|---|------|------|--------|------|----------|--------|------|")
        for i, s in enumerate(off_effective, 1):
            key = s.get("key", "?")
            mod_type = s.get("mod_type", "?")
            needed = s.get("needed_value", 0)
            unit = s.get("unit", "")
            dpu = s.get("dps_per_unit", 0)
            cur = s.get("current_total", 0)
            formula = s.get("formula", "")
            lines.append(
                f"| {i} | {key} | {mod_type} | "
                f"{needed:+.1f}{unit} | {unit} | "
                f"{dpu:.2f}%/{unit if unit else '1'} | "
                f"{cur:.0f} | {formula} |"
            )
        lines.append("")

    if off_unreachable:
        lines.append("**无影响维度**: "
                     + ", ".join(s.get("key", "?") for s in off_unreachable))
        lines.append("")

    # 3B: 防御灵敏度（EHP）
    lines.append("### 3B. 防御灵敏度（EHP）")
    lines.append("")

    if defence_sens:
        def_effective = [s for s in defence_sens if s.get("needed_value") is not None]
        def_unreachable = [s for s in defence_sens if s.get("needed_value") is None]

        if def_effective:
            lines.append("| 维度 | 类型 | 所需值 | 每单位 EHP 提升 | 公式 |")
            lines.append("|------|------|--------|---------------|------|")
            for s in def_effective:
                label = s.get("label", s.get("key", "?"))
                mod_type = s.get("mod_type", "?")
                needed = s.get("needed_value", 0)
                unit = s.get("unit", "")
                dpu = s.get("dps_per_unit", 0) or 0
                formula = s.get("formula", "")
                needed_str = f"{needed:.1f}{unit}" if needed is not None else "—"
                lines.append(f"| {label} | {mod_type} | {needed_str} | +{dpu:.2f}%/单位 | {formula} |")
            lines.append("")

        if def_unreachable:
            lines.append("**无法达到目标**: "
                         + ", ".join(f"{s.get('label', s.get('key', '?'))}" for s in def_unreachable))
            lines.append("")
    else:
        lines.append("无数据")
        lines.append("")

    # 3C: 恢复增强灵敏度
    lines.append("### 3C. 恢复增强灵敏度")
    lines.append("")

    if recovery_sens:
        rec_effective = [s for s in recovery_sens if s.get("needed_value") is not None]
        if rec_effective:
            tp = rec_effective[0].get("target_pct", 20)
            lines.append(f"注入多少恢复属性可使对应恢复指标提升 **{tp:.0f}%**：")
            lines.append("")
            lines.append("| 增强属性 | 所需注入 | 当前总值 | 公式 |")
            lines.append("|---------|---------|---------|------|")
            for s in rec_effective:
                label = s.get("label", s.get("key", "?"))
                needed = s.get("needed_value", 0)
                unit = s.get("unit", "")
                cur = s.get("current_total", 0)
                formula = s.get("formula", "")
                cur_str = f"{cur:,.1f}" if cur > 0 else "—"
                lines.append(f"| {label} | {needed:.1f}{unit} | {cur_str} | {formula} |")
            lines.append("")
    else:
        lines.append("无数据")
        lines.append("")

    # --- Part 4: 防御面 ---
    _format_section_defence(lines, defence_ov, baseline)

    # --- Part 5: 资源面 ---
    if res_ov or life_recov or mana_recov or recovery_sens:
        lines.append("## 5. 资源面")
        lines.append("")

        # 5A 资源预算
        if res_ov:
            lines.append("### 5A. 资源预算")
            lines.append("")
            lines.append("| 资源 | 总量 | 可用 | 占用率 |")
            lines.append("|------|------|------|--------|")

            life_data = res_ov.get("life", {})
            lines.append(f"| Life | {life_data.get('total', 0):,.0f} | "
                         f"{life_data.get('unreserved', 0):,.0f} | — |")

            mana_data = res_ov.get("mana", {})
            mana_pct = mana_data.get("reserved_pct", 0)
            mana_status = f"⚠️ {mana_pct:.0f}%" if mana_pct > 50 else f"{mana_pct:.0f}%"
            lines.append(f"| Mana | {mana_data.get('total', 0):,.0f} | "
                         f"{mana_data.get('unreserved', 0):,.0f} | {mana_status} |")

            spirit_data = res_ov.get("spirit", {})
            spirit_pct = spirit_data.get("reserved_pct", 0)
            spirit_status = f"🔴 {spirit_pct:.0f}%" if spirit_pct > 80 else (
                f"⚠️ {spirit_pct:.0f}%" if spirit_pct > 50 else f"{spirit_pct:.0f}%")
            lines.append(f"| Spirit | {spirit_data.get('total', 0):,.0f} | "
                         f"{spirit_data.get('unreserved', 0):,.0f} | {spirit_status} |")

            es_data = res_ov.get("es", {})
            if es_data.get("total", 0) > 0:
                lines.append(f"| ES | {es_data['total']:,.0f} | "
                             f"{es_data.get('recovery_cap', 0):,.0f} | — |")

            ward = res_ov.get("ward", 0)
            if ward > 0:
                lines.append(f"| Ward | {ward:,.0f} | — | 每次受击刷新 |")

            lines.append("")

        # 5B 生命恢复能力
        if life_recov and life_recov.get("sources"):
            lines.append("### 5B. 生命恢复能力")
            lines.append("")

            total_rate = life_recov.get("total_rate", 0)
            time_to_full = life_recov.get("time_to_full", 0)
            leech_util = life_recov.get("leech_rate_pct", 0)
            life = baseline.get("Life", 1)

            lines.append(f"总恢复速率: **{total_rate:,.1f}/s**"
                         f"（回满约 {time_to_full:.1f}s）")
            if leech_util > 0:
                lines.append(f"偷取上限利用率: {leech_util:.0f}%"
                             f"（上限 {life_recov.get('max_leech_rate', 0):,.0f}/s）")
            lines.append("")

            lines.append("| # | 来源 | 每秒恢复 | 占比 |")
            lines.append("|---|------|---------|------|")
            for i, src in enumerate(life_recov["sources"], 1):
                rate = src.get("rate", 0)
                pct = rate / total_rate * 100 if total_rate > 0 else 0
                lines.append(f"| {i} | {src['name']} | {rate:,.1f}/s | {pct:.0f}% |")
            lines.append("")

        # 5C 魔力恢复能力
        if mana_recov and mana_recov.get("sources"):
            lines.append("### 5C. 魔力恢复能力")
            lines.append("")

            mana_total_rate = mana_recov.get("total_rate", 0)
            mana_time = mana_recov.get("time_to_full", 0)
            mana_avail = baseline.get("ManaUnreserved", 0)

            lines.append(f"总恢复速率: **{mana_total_rate:,.1f}/s**"
                         f"（回满可用 {mana_avail:,.0f} 约需 {mana_time:.1f}s）")
            lines.append("")

            lines.append("| # | 来源 | 每秒恢复 | 占比 |")
            lines.append("|---|------|---------|------|")
            for i, src in enumerate(mana_recov["sources"], 1):
                rate = src.get("rate", 0)
                pct = rate / mana_total_rate * 100 if mana_total_rate > 0 else 0
                lines.append(f"| {i} | {src['name']} | {rate:,.1f}/s | {pct:.0f}% |")
            lines.append("")

    # --- Part 6: 已分配天赋价值 ---
    dps_talents = [t for t in talent_value if abs(t.get("dps_pct", 0)) > 0.1]
    def_talents = [t for t in talent_value
                   if abs(t.get("dps_pct", 0)) <= 0.1 and abs(t.get("ehp_pct", 0)) > 0.1]

    if dps_talents or def_talents or zero_talents:
        lines.append("## 6. 已分配天赋价值")
        lines.append("")

    if dps_talents:
        lines.append("### DPS 影响天赋")
        lines.append("")
        lines.append("| # | 天赋 | 类型 | 移除后 DPS% | 移除后 EHP% | 分类 | 效果 |")
        lines.append("|---|------|------|-------------|-------------|------|------|")
        for i, t in enumerate(dps_talents, 1):
            desc = t.get('description', '') or ''
            lines.append(
                f"| {i} | {t['name']} | {t['type']} | "
                f"{t['dps_pct']:+.1f}% | {t.get('ehp_pct', 0):+.1f}% | "
                f"{t['category']} | {desc} |"
            )
        lines.append("")

    if def_talents:
        lines.append("### 纯防御天赋")
        lines.append("")
        lines.append("| 天赋 | 移除后 EHP% | 效果 |")
        lines.append("|------|-------------|------|")
        for t in def_talents:
            desc = t.get('description', '') or ''
            lines.append(f"| {t['name']} | {t.get('ehp_pct', 0):+.1f}% | {desc} |")
        lines.append("")

    if zero_talents:
        lines.append(f"### 无效天赋 ({len(zero_talents)} 个)")
        lines.append("")
        names = ", ".join(t["name"] for t in zero_talents)
        lines.append(f"{names}")
        lines.append("")

    # --- Part 7: 未分配天赋探索 ---
    if talent_exploration:
        lines.append("## 7. 未分配天赋探索")
        lines.append("")
        top_n = 10
        shown = talent_exploration[:top_n]
        rest = len(talent_exploration) - len(shown)

        lines.append("| # | 天赋 | 类型 | DPS% | EHP% | 分类 |")
        lines.append("|---|------|------|------|------|------|")
        for i, t in enumerate(shown, 1):
            lines.append(
                f"| {i} | {t['name']} | {t['type']} | "
                f"{t['dps_pct']:+.1f}% | {t.get('ehp_pct', 0):+.1f}% | "
                f"{t['category']} |"
            )
        if rest > 0:
            lines.append("")
            lines.append(f"*（另有 {rest} 个候选天赋未显示）*")
        lines.append("")

    # --- Section 8: 珠宝诊断 ---
    lines.append("## 8. 珠宝诊断")
    lines.append("")

    if jewel_diag:
        for j in jewel_diag:
            name = j.get("name", "?")
            base = j.get("base_type", "?")
            rarity = j.get("rarity", "?")
            dp = j.get("dps_pct", 0)
            ep = j.get("ehp_pct", 0)
            status = j.get("status", "?")
            slot = j.get("slot_name", "")

            lines.append(f"### {name} ({base}, {rarity})")
            lines.append("")
            lines.append(f"- **DPS 贡献**: {dp:+.1f}% | **EHP 贡献**: {ep:+.1f}% | **状态**: {status} | **槽位**: {slot}")

            # granted passives
            gp = j.get("granted_passives", [])
            if gp:
                gdp = j.get("granted_dps_pct", 0)
                gep = j.get("granted_ehp_pct", 0)
                lines.append(f"- **分配天赋**: {', '.join(gp)} (DPS {gdp:+.1f}%, EHP {gep:+.1f}%)")

            lines.append("")

            # mods 明细表
            mods = j.get("mods", [])
            if mods:
                lines.append("| Mod | 类型 | 值 | DPS% | EHP% |")
                lines.append("|-----|------|-----|------|------|")
                for m in mods:
                    mname = m.get("name", "?")
                    mtype = m.get("type", "?")
                    mval = m.get("value", "?")
                    mdps = m.get("dps_pct")
                    mehp = m.get("ehp_pct")
                    # 跳过无意义的 Lua table 指针
                    if isinstance(mval, str) and mval.startswith("table:"):
                        mval = "(complex data)"
                    dps_str = f"{mdps:+.1f}%" if mdps is not None else "—"
                    ehp_str = f"{mehp:+.1f}%" if mehp is not None else "—"
                    lines.append(f"| {mname} | {mtype} | {mval} | {dps_str} | {ehp_str} |")
                lines.append("")

    else:
        lines.append("无珠宝。")
        lines.append("")

    # --- Section 7: 光环与精魄分析 ---
    aura_data = data.get("aura_spirit", {})
    bm = aura_data.get("build_modifiers", {})
    _format_section7(lines, aura_data, skill_flags, baseline,
                    build_modifiers=bm)

    # --- Part 10: 总结与建议 ---
    lines.append("## 10. 总结与建议")
    lines.append("")

    # 10a. 核心数据一句话
    lines.append(f"当前 **{skill_name}** TotalDPS = **{total_dps:,.0f}**，"
                 f"AverageHit = {avg_hit:,.0f}，Speed = {speed:.2f}/s，"
                 f"CritChance = {crit_chance:.1f}%，CritMultiplier = {crit_multi:.2f}x。")
    lines.append("")

    # 10b. 进攻面建议
    effective_sens = [s for s in sensitivity if s.get("needed_value") is not None]
    lines.append("### ⚔️ 进攻面")
    lines.append("")
    if effective_sens:
        lines.append("**DPS 灵敏度 Top 5**（所需投入越少 = 性价比越高）：")
        lines.append("")
        lines.append("| # | 维度 | 类型 | 当前值 | 所需值 | 公式 |")
        lines.append("|---|------|------|--------|--------|------|")
        for i, s in enumerate(effective_sens[:5], 1):
            key = s.get("key", "?")
            mod_type = s.get("mod_type", "?")
            cur = s.get("current_total", 0)
            needed = s.get("needed_value", 0)
            unit = s.get("unit", "")
            formula = s.get("formula", "")
            lines.append(
                f"| {i} | {key} | {mod_type} | {cur:.0f} | "
                f"+{needed:.0f}{unit} | {formula} |"
            )
        lines.append("")

    # 穿透提醒
    unreachable_sens = [s for s in sensitivity if s.get("needed_value") is None]
    pen_unreachable = [s for s in unreachable_sens if "pen" in s.get("key", "")]
    if pen_unreachable:
        lines.append("*穿透维度均无影响（敌人抗性已为负值），面对高抗 Boss 时会成为有效优化方向。*")
        lines.append("")

    # 10c. 防御面建议
    lines.append("### 🛡️ 防御面")
    lines.append("")
    if defence_ov:
        weakest = defence_ov.get("weakest_type", "")
        weakest_pct = defence_ov.get("weakest_pct", 0)
        total_ehp = defence_ov.get("total_ehp", 0)
        if weakest:
            lines.append(f"**最短板**: {weakest}（承伤仅为最强的 {weakest_pct:.0f}%）")
            lines.append("")

        # 抗性建议
        resist = defence_ov.get("resistances", {})
        unfilled = [r for r, v in resist.items() if v.get("unfilled", 0) > 0]
        overfilled = [r for r, v in resist.items() if v.get("overflow", 0) >= 20]
        if unfilled:
            lines.append(f"**未满抗性**: {', '.join(unfilled)} — 优先补满可显著提升 EHP")
            lines.append("")
        if overfilled:
            lines.append(f"**过度堆叠**: {', '.join(overfilled)} — 超出上限 20%+，可考虑分配到其他维度")
            lines.append("")

    if defence_sens:
        def_effective = [s for s in defence_sens if s.get("needed_value") is not None]
        if def_effective:
            top_def = def_effective[0]
            label = top_def.get("label", top_def.get("key", "?"))
            needed = top_def.get("needed_value", 0)
            unit = top_def.get("unit", "")
            lines.append(f"**防御性价比最高**: {label}，需要 +{needed:.0f}{unit} 即可提升 EHP +{top_def.get('target_pct', 20):.0f}%")
            lines.append("")

    # 10d. 资源面建议
    lines.append("### 💧 资源与恢复")
    lines.append("")
    if res_ov:
        spirit_data = res_ov.get("spirit", {})
        spirit_pct = spirit_data.get("reserved_pct", 0)
        if spirit_pct > 100:
            lines.append(f"**⚠️ 精魄超载**: 占用 {spirit_pct:.0f}%，需要缩减光环或精魄辅助")
            lines.append("")

    if recovery_sens:
        rec_effective = [s for s in recovery_sens if s.get("needed_value") is not None]
        if rec_effective:
            lines.append("**恢复增强 Top 3**：")
            lines.append("")
            for i, s in enumerate(rec_effective[:3], 1):
                label = s.get("label", s.get("key", "?"))
                needed = s.get("needed_value", 0)
                unit = s.get("unit", "")
                formula = s.get("formula", "")
                lines.append(f"{i}. {label}: {formula}")
            lines.append("")

    # 10e. 天赋建议
    lines.append("### 🌳 天赋")
    lines.append("")
    if talent_exploration:
        lines.append("**推荐点出 Top 5**：")
        lines.append("")
        for i, t in enumerate(talent_exploration[:5], 1):
            ehp_note = f"，EHP {t.get('ehp_pct', 0):+.1f}%" if abs(t.get('ehp_pct', 0)) > 0.1 else ""
            lines.append(f"{i}. **{t['name']}**: DPS {t['dps_pct']:+.1f}%{ehp_note}")
        lines.append("")

    if zero_talents:
        lines.append(f"**⚠️ {len(zero_talents)} 个无效天赋**: "
                     f"{', '.join(t['name'] for t in zero_talents[:8])}"
                     + (f" 等 {len(zero_talents)} 个" if len(zero_talents) > 8 else ""))
        lines.append("")

    # 10f. 珠宝建议
    if jewel_diag:
        low_impact_jewels = [j for j in jewel_diag
                            if abs(j.get("dps_pct", 0)) < 0.1
                            and abs(j.get("ehp_pct", 0)) < 0.1
                            and j.get("status") == "ok"]
        high_impact_jewels = sorted(
            [j for j in jewel_diag
             if abs(j.get("dps_pct", 0)) >= 0.1 or abs(j.get("ehp_pct", 0)) >= 0.1],
            key=lambda j: abs(j.get("dps_pct", 0)) + abs(j.get("ehp_pct", 0)),
            reverse=True,
        )
        if high_impact_jewels or low_impact_jewels:
            lines.append("### 💎 珠宝")
            lines.append("")
            if high_impact_jewels:
                best = high_impact_jewels[0]
                lines.append(f"**最佳**: {best.get('name', '?')} "
                             f"(DPS {best.get('dps_pct', 0):+.1f}%, "
                             f"EHP {best.get('ehp_pct', 0):+.1f}%)")
            if low_impact_jewels:
                names = ", ".join(f"{j.get('name', '?')}" for j in low_impact_jewels)
                lines.append(f"**可替换**: {names}")
            lines.append("")

    return "\n".join(lines)
