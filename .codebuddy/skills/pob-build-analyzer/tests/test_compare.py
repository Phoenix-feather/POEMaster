#!/usr/bin/env python3
"""
精度对比测试：运行 POBCalculator 并与 POB PlayerStats XML 对比。

用法:
    python -m pob_calc.tests.test_compare
    或
    python tests/test_compare.py
"""
import sys
from pathlib import Path

# 确保可以 import pob_calc
sys.path.insert(0, str(Path(__file__).parent.parent))

from pob_calc import POBCalculator


def main():
    # 从 cache 读取分享码
    cache_dir = Path(__file__).parent.parent / "cache"
    share_code_file = cache_dir / "share_code.txt"

    if not share_code_file.exists():
        # 回退到 poe-data-miner 的 cache
        share_code_file = Path(__file__).parent.parent.parent / "poe-data-miner" / "cache" / "share_code.txt"

    if not share_code_file.exists():
        print(f"❌ 找不到分享码文件")
        print(f"  请将 POB 分享码保存到: {cache_dir / 'share_code.txt'}")
        sys.exit(1)

    share_code = share_code_file.read_text(encoding='utf-8').strip()
    print(f"分享码长度: {len(share_code)} 字符")

    # 创建计算器
    print("\n加载构筑...")
    calc = POBCalculator(share_code=share_code)

    info = calc.build_info
    print(f"  等级: {info['level']}")
    print(f"  职业: {info['className']} → {info['ascendClassName']}")
    load = calc.load_result
    print(f"  天赋: {load['tree_nodes']} 节点")
    print(f"  技能: {load['skill_groups']} 组")
    print(f"  装备: {load['items']} 件")
    print(f"  配置: {load['config_inputs']} 项")
    if load['mod_fixes'] > 0:
        print(f"  Mod修复: {load['mod_fixes']} 个")

    # 精度对比
    print("\n运行计算并对比...")
    comparisons = calc.compare_with_pob()

    print(f"\n{'Stat':<30} {'POB':>12} {'Calc':>12} {'Delta':>10} {'Match':>6}")
    print('-' * 72)

    match_count = sum(1 for c in comparisons if c['match'])
    total = len(comparisons)

    for c in comparisons:
        delta_str = f"{c['delta_pct']:+.1f}%" if abs(c['pob_value']) > 0.001 else '0'
        status = "YES" if c['match'] else "NO"
        print(f"{c['stat']:<30} {c['pob_value']:>12.2f} {c['calc_value']:>12.2f} {delta_str:>10} {status:>6}")

    print('-' * 72)
    pct = match_count / total * 100 if total > 0 else 0
    print(f'Match: {match_count}/{total} ({pct:.0f}%)')

    # 主动技能
    skills = calc.get_active_skills()
    main = calc.get_main_skill()
    print(f"\n主技能: {main['name']} (castTime={main['castTime']})")
    print(f"主动技能 ({len(skills)}): {', '.join(skills[:10])}")
    if len(skills) > 10:
        print(f"  ... 共 {len(skills)} 个")

    # 灵敏度测试
    print("\n灵敏度分析:")
    baseline = calc.get_baseline()

    for label, name, typ, val in [
        ("+100 flat Life", "Life", "BASE", 100),
        ("+50% inc Evasion", "Evasion", "INC", 50),
        ("+20% more Life", "Life", "MORE", 20),
    ]:
        diff = calc.what_if_mod(name, typ, val)
        key_changes = {k: v for k, v in diff.items() if k in ('Life', 'Evasion', 'TotalEHP', 'Mana', 'EnergyShield')}
        changes_str = ', '.join(f"{k}: {v[0]:.0f}→{v[1]:.0f} ({v[2]:+.0f})" for k, v in sorted(key_changes.items()))
        print(f"  {label}: {changes_str or '(无关键变化)'}")


if __name__ == '__main__':
    main()
