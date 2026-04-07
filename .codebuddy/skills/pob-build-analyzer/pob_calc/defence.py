"""防御、资源、恢复分析模块。

所有函数均为纯 baseline output 数据读取，零 Lua 交互。
"""


def defence_overview(baseline: dict) -> dict:
    """Section 2A: 防御概览 — 从 baseline output 读取防御数据。

    零 Lua 交互，纯 output 数据读取。

    Args:
        baseline: 基线 output dict

    Returns:
        {
            "pools": {Life, LifeUnreserved, LifeRecoverable, EnergyShield,
                      EnergyShieldRecoveryCap, Mana, ManaUnreserved,
                      Ward, sharedMindOverMatter},
            "armour": Armour,
            "evasion": Evasion,
            "block": {BlockChance, SpellBlockChance, EffectiveAverageBlockChance,
                      BlockEffect},
            "suppression": EffectiveSpellSuppressionChance,
            "deflect": DeflectChance,
            "resistances": {Fire, Cold, Lightning, Chaos} × {Resist, ResistMax, ResistOverCap},
            "max_hit_taken": {Physical, Fire, Cold, Lightning, Chaos} MaximumHitTaken,
            "dot_ehp": {Physical, Fire, Cold, Lightning, Chaos} DotEHP,
            "total_ehp": TotalEHP,
            "total_number_of_hits": TotalNumberOfHits,
        }
    """
    bl = baseline

    # Pool 构成
    pools = {
        "Life": bl.get("Life", 0),
        "LifeUnreserved": bl.get("LifeUnreserved", 0),
        "LifeRecoverable": bl.get("LifeRecoverable", 0),
        "EnergyShield": bl.get("EnergyShield", 0),
        "ESRecoveryCap": bl.get("EnergyShieldRecoveryCap", 0),
        "Mana": bl.get("Mana", 0),
        "ManaUnreserved": bl.get("ManaUnreserved", 0),
        "Ward": bl.get("Ward", 0),
        "MoMPct": bl.get("sharedMindOverMatter", 0),
    }

    # 减伤层
    armour = bl.get("Armour", 0)
    evasion = bl.get("Evasion", 0)
    block = {
        "BlockChance": bl.get("BlockChance", 0),
        "SpellBlockChance": bl.get("SpellBlockChance", 0),
        "EffectiveAvgBlock": bl.get("EffectiveAverageBlockChance", 0),
        "BlockEffect": bl.get("BlockEffect", 0),
    }
    suppression = bl.get("EffectiveSpellSuppressionChance", 0)
    deflect = bl.get("DeflectChance", 0)

    # 抗性面板
    resist_types = ["Fire", "Cold", "Lightning", "Chaos"]
    resistances = {}
    for elem in resist_types:
        resistances[elem] = {
            "Resist": bl.get(f"{elem}Resist", 0),
            "ResistMax": bl.get(f"{elem}ResistMax", 75),
            "ResistOverCap": bl.get(f"{elem}ResistOverCap", 0),
        }

    # MaxHitTaken（5 种伤害类型，含 Physical）
    hit_types = ["Physical", "Fire", "Cold", "Lightning", "Chaos"]
    max_hit = {}
    for dtype in hit_types:
        max_hit[dtype] = bl.get(f"{dtype}MaximumHitTaken", 0)

    # DotEHP
    dot_ehp = {}
    for dtype in hit_types:
        dot_ehp[dtype] = bl.get(f"{dtype}DotEHP", 0)

    # 承伤乘数（每种伤害类型最终承受比例，越小越好）
    taken_hit_mult = {}
    for dtype in hit_types:
        taken_hit_mult[dtype] = bl.get(f"{dtype}TakenHitMult", 0)

    # 找最短板
    weakest = min(max_hit, key=max_hit.get) if any(max_hit.values()) else None
    # 找最短板对应的承伤占比（vs 最大值）
    if weakest and max( max_hit.values(), default=0) > 0:
        weakest_pct = max_hit[weakest] / max( max_hit.values(), default=1) * 100
    else:
        weakest_pct = 0

    return {
        "pools": pools,
        "armour": armour,
        "evasion": evasion,
        "block": block,
        "suppression": suppression,
        "deflect": deflect,
        "resistances": resistances,
        "max_hit_taken": max_hit,
        "dot_ehp": dot_ehp,
        "taken_hit_mult": taken_hit_mult,
        "total_ehp": bl.get("TotalEHP", 0),
        "total_number_of_hits": bl.get("TotalNumberOfHits", 0),
        "weakest_type": weakest,
        "weakest_pct": weakest_pct,
    }


# =============================================================================
# 资源面分析
# =============================================================================


def resource_overview(baseline: dict) -> dict:
    """Part 3.1: 资源预算概览 — 从 baseline output 读取资源数据。

    零 Lua 交互，纯 output 数据读取。

    Returns:
        {
            "life": {total, unreserved, recoverable},
            "mana": {total, unreserved, reserved_pct},
            "spirit": {total, unreserved, reserved_pct},
            "es": {total, recovery_cap},
            "ward": Ward,
            "life_sustainability": "可续航"/"不可续航"/"未知",
            "mana_sustainability": ...,
        }
    """
    bl = baseline

    life_total = bl.get("Life", 0)
    life_unreserved = bl.get("LifeUnreserved", 0)
    life_recoverable = bl.get("LifeRecoverable", life_total)

    mana_total = bl.get("Mana", 0)
    mana_unreserved = bl.get("ManaUnreserved", mana_total)
    mana_reserved_pct = ((mana_total - mana_unreserved) / mana_total * 100
                         if mana_total > 0 else 0)

    spirit_total = bl.get("Spirit", 0)
    spirit_unreserved = bl.get("SpiritUnreserved", spirit_total)
    spirit_reserved_pct = ((spirit_total - spirit_unreserved) / spirit_total * 100
                           if spirit_total > 0 else 0)

    es_total = bl.get("EnergyShield", 0)
    es_recovery_cap = bl.get("EnergyShieldRecoveryCap", es_total)

    ward = bl.get("Ward", 0)

    return {
        "life": {
            "total": life_total,
            "unreserved": life_unreserved,
            "recoverable": life_recoverable,
        },
        "mana": {
            "total": mana_total,
            "unreserved": mana_unreserved,
            "reserved_pct": mana_reserved_pct,
        },
        "spirit": {
            "total": spirit_total,
            "unreserved": spirit_unreserved,
            "reserved_pct": spirit_reserved_pct,
        },
        "es": {
            "total": es_total,
            "recovery_cap": es_recovery_cap,
        },
        "ward": ward,
    }


def life_recovery_analysis(baseline: dict) -> dict:
    """Part 3.2: 生命恢复能力分析 — 聚合所有恢复来源。

    Returns:
        {
            "sources": [
                {"name": "偷取", "rate": 120.0, "details": {...}},
                {"name": "再生", "rate": 45.0, "details": {...}},
                ...
            ],
            "total_rate": 173.3,
            "time_to_full": 18.8,
            "leech_rate_pct": 37.0,
        }
    """
    bl = baseline
    sources = []

    # 再生
    regen = bl.get("LifeRegenRecovery", 0)
    if regen != 0:
        sources.append({
            "name": "再生",
            "rate": regen,
            "details": {"LifeRegenRecovery": regen},
        })

    # 偷取 (Leech)
    leech = bl.get("LifeLeech", 0)
    leech_instant = bl.get("LifeLeechInstant", 0)
    leech_rate = leech + leech_instant
    if leech_rate != 0:
        max_leech_rate = bl.get("MaxLifeLeechRate", 0)
        leech_util = (leech_rate / max_leech_rate * 100) if max_leech_rate > 0 else 0
        sources.append({
            "name": "偷取",
            "rate": leech_rate,
            "details": {
                "LifeLeech": leech,
                "LifeLeechInstant": leech_instant,
                "MaxLifeLeechRate": max_leech_rate,
                "利用率": round(leech_util, 1),
            },
        })

    # 回收 (Recoup)
    recoup = bl.get("LifeRecoup", 0)
    if recoup != 0:
        sources.append({
            "name": "回收",
            "rate": recoup,
            "details": {"LifeRecoup": recoup},
        })

    # 击中恢复
    on_hit = bl.get("LifeOnHitRate", 0)
    if on_hit != 0:
        sources.append({
            "name": "击中恢复",
            "rate": on_hit,
            "details": {"LifeOnHitRate": on_hit},
        })

    # 按贡献排序
    sources.sort(key=lambda x: abs(x["rate"]), reverse=True)

    total_rate = sum(s["rate"] for s in sources)
    life = bl.get("LifeRecoverable", bl.get("Life", 1))
    time_to_full = life / total_rate if total_rate > 0 else float("inf")

    max_leech = bl.get("MaxLifeLeechRate", 0)
    leech_rate_pct = ((leech_rate / max_leech * 100) if max_leech > 0 and leech_rate > 0
                      else 0)

    return {
        "sources": sources,
        "total_rate": round(total_rate, 1),
        "time_to_full": round(time_to_full, 1),
        "leech_rate_pct": round(leech_rate_pct, 1),
        "max_leech_rate": max_leech,
    }


def mana_recovery_analysis(baseline: dict) -> dict:
    """Part 3.3: 魔力恢复能力分析 — 结构同 life_recovery_analysis。

    Returns:
        {
            "sources": [...],
            "total_rate": ...,
            "time_to_full": ...,
        }
    """
    bl = baseline
    sources = []

    # 魔力再生
    regen = bl.get("ManaRegenRecovery", 0)
    if regen != 0:
        sources.append({
            "name": "再生",
            "rate": regen,
            "details": {"ManaRegenRecovery": regen},
        })

    # 魔力偷取
    leech = bl.get("ManaLeech", 0)
    leech_instant = bl.get("ManaLeechInstant", 0)
    leech_rate = leech + leech_instant
    if leech_rate != 0:
        max_leech_rate = bl.get("MaxManaLeechRate", 0)
        leech_util = (leech_rate / max_leech_rate * 100) if max_leech_rate > 0 else 0
        sources.append({
            "name": "偷取",
            "rate": leech_rate,
            "details": {
                "ManaLeech": leech,
                "ManaLeechInstant": leech_instant,
                "MaxManaLeechRate": max_leech_rate,
                "利用率": round(leech_util, 1),
            },
        })

    # 魔力回收
    recoup = bl.get("ManaRecoup", 0)
    if recoup != 0:
        sources.append({
            "name": "回收",
            "rate": recoup,
            "details": {"ManaRecoup": recoup},
        })

    sources.sort(key=lambda x: abs(x["rate"]), reverse=True)

    total_rate = sum(s["rate"] for s in sources)
    mana = bl.get("ManaUnreserved", 1)
    time_to_full = mana / total_rate if total_rate > 0 else float("inf")

    return {
        "sources": sources,
        "total_rate": round(total_rate, 1),
        "time_to_full": round(time_to_full, 1),
    }

