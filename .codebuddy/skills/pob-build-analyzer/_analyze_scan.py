"""分析扫描结果并生成配置条目。"""
import json

# 加载扫描结果
with open('_scan_results.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print(f"总共 {data['summary']['player_beneficial']} 个玩家受益 stats\n")

# 分类
categories = {
    'active_skills': [],
    'support_gems': [],
    'trigger_skills': [],
    'other': []
}

for item in data['stats']:
    stat = item['stat']
    skills = item['skills']
    
    # 主动技能
    if any(kw in stat for kw in ['demon_form', 'charged_blast', 'arc_damage', 'cascadeable_offering']):
        categories['active_skills'].append(item)
    # 辅助宝石
    elif stat.startswith('support_'):
        categories['support_gems'].append(item)
    # 触发类
    elif 'trigger' in stat:
        categories['trigger_skills'].append(item)
    # 其他
    else:
        categories['other'].append(item)

print("=== 主动技能未实现效果 ===")
for item in categories['active_skills']:
    print(f"\n{item['stat']}")
    print(f"  Skills: {', '.join(item['skills'])}")
    
    # 生成配置模板
    skill_name = item['skills'][0] if item['skills'] else 'Unknown'
    if 'demon_form' in item['stat']:
        print(f"""
  配置建议:
    "{skill_name}":
      detect:
        type: "gem_name"
        name: "{skill_name}"
      skill_type: "active"
      effects:
        - type: "mod"
          mod_name: "SpellDamage"
          mod_type: "MORE"
          value: null  # 动态读取层数
          source: "DemonForm_stacks"
          description: "每层 +MORE 法术伤害（需动态读取层数）"
""")
    elif 'charged_blast' in item['stat']:
        print(f"""
  配置建议:
    "{skill_name}":
      detect:
        type: "gem_name"
        name: "{skill_name}"
      skill_type: "active"
      effects:
        - type: "mod"
          mod_name: "SpellDamage"
          mod_type: "MORE"
          value: null  # 动态读取层数
          source: "ChargedBlast_stacks"
          description: "每层 +MORE 法术伤害（需动态读取层数）"
""")

print("\n\n=== 辅助宝石未实现效果 (前20个) ===")
for item in categories['support_gems'][:20]:
    stat = item['stat']
    # 提取辅助宝石名称
    support_name = stat.replace('support_', '').split('_')[0].replace('_', ' ').title()
    
    print(f"\n{stat}")
    print(f"  辅助: {support_name}")
    print(f"  效果: {stat.split('_final')[0].replace('_', ' ')}")

print(f"\n... 还有 {len(categories['support_gems']) - 20} 个辅助宝石效果")

print("\n\n=== 触发类未实现效果 ===")
for item in categories['trigger_skills']:
    print(f"\n{item['stat']}")
    print(f"  Skills: {', '.join(item['skills'])}")

print("\n\n=== 其他重要未实现效果 (前30个) ===")
important_keywords = ['damage_+%_final', 'more', 'elemental', 'penetrate', 'crit']
important = [item for item in categories['other'] 
             if any(kw in item['stat'].lower() for kw in important_keywords)]

for item in important[:30]:
    print(f"\n{item['stat']}")
    print(f"  Skills: {', '.join(item['skills'][:3])}")

print(f"\n\n统计:")
print(f"  主动技能: {len(categories['active_skills'])} 个")
print(f"  辅助宝石: {len(categories['support_gems'])} 个")
print(f"  触发类: {len(categories['trigger_skills'])} 个")
print(f"  其他: {len(categories['other'])} 个")
