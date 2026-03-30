"""扫描 POB 未实现效果并生成配置文件。"""
from pob_calc.pob_unimplemented import scan_pob_for_unimplemented_stats
from collections import defaultdict
import yaml

# 扫描
print("扫描 POB 数据...")
unimpl = scan_pob_for_unimplemented_stats('G:/POEMaster/POBData')

# 按 stat 分组
by_stat = defaultdict(list)
for u in unimpl:
    by_stat[u['stat_name']].append(u['skill_name'])

print(f'总共 {len(by_stat)} 个未映射 stats')

# 分类：只关注影响玩家数值的
player_beneficial = []

for stat, skills in by_stat.items():
    stat_lower = stat.lower()
    
    # 跳过 display_ 开头的（仅显示）
    if stat_lower.startswith('display_'):
        continue
    
    # 跳过 monster/minion 相关
    if 'monster' in stat_lower or 'minion_' in stat_lower:
        continue
    
    # 跳过纯机制/行为相关
    if any(kw in stat_lower for kw in ['_ms', '_angle', '_range', '_radius', '_interval', '_duration_ms']):
        continue
    
    # 保留：伤害/元素/攻速/暴击/命中
    if any(kw in stat_lower for kw in [
        'damage', 'more', 'inc', 'elemental', 
        'fire', 'cold', 'lightning', 'chaos', 'physical',
        'attack', 'spell', 'cast', 'speed',
        'crit', 'accuracy', 'penetrate',
        'life', 'mana', 'energy', 'armour', 'evasion',
        'resist', 'taken', 'reduce',
        'ailment', 'shock', 'ignite', 'freeze', 'chill', 'poison', 'bleed',
        'buff', 'aura', 'effect',
        'bearer', 'unbound',  # UA 相关
    ]):
        player_beneficial.append((stat, skills))

print(f'\n玩家受益相关: {len(player_beneficial)} 个')

# 按 stat 名称排序
player_beneficial.sort(key=lambda x: x[0])

# 输出统计
print('\n=== 前 50 个玩家受益 stats ===')
for stat, skills in player_beneficial[:50]:
    skills_unique = sorted(set(skills))
    skills_str = ', '.join(skills_unique[:5])
    if len(skills_unique) > 5:
        skills_str += f' (+{len(skills_unique)-5})'
    print(f'{stat[:55]:55s}')
    print(f'  Skills: {skills_str}')

# 统计涉及的技能
all_skills = set()
for stat, skills in player_beneficial:
    all_skills.update(skills)

print(f'\n涉及的技能: {len(all_skills)} 个')
print('技能列表:')
for s in sorted(all_skills)[:20]:
    print(f'  - {s}')
if len(all_skills) > 20:
    print(f'  ... 还有 {len(all_skills)-20} 个')
