import sys, logging
logging.basicConfig(level=logging.WARNING)
sys.path.insert(0, '.codebuddy/skills/pob-build-analyzer')
from pob_calc import POBCalculator
calc = POBCalculator.from_current()
r = calc.full_analysis(skill_name='spark')
bl = r['baseline']['TotalDPS']
auras = r['aura_spirit']['existing_auras']
print(f'Baseline TotalDPS: {bl:.0f}')
for a in auras:
    print(f"  {a['name']:25s} bare={a.get('bare_dps_pct',0):+.1f}% real={a['dps_pct']:+.1f}% spirit={a['spirit_cost']:.0f}")
print(calc.get_html_report_path())
