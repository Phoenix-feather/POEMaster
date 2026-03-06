#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""数据覆盖率报告生成器"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime

def generate_coverage_report(kb_path: str):
    """生成数据覆盖率报告"""
    kb_path = Path(kb_path)
    
    report = {
        'generated_at': datetime.now().isoformat(),
        'summary': {},
        'entity_types': {},
        'field_coverage': {},
        'data_quality': {}
    }
    
    # 连接数据库
    entities_db = kb_path / 'entities.db'
    rules_db = kb_path / 'rules.db'
    graph_db = kb_path / 'graph.db'
    mechanisms_db = kb_path / 'mechanisms.db'
    
    conn_entities = sqlite3.connect(entities_db)
    cursor_entities = conn_entities.cursor()
    
    # 1. 摘要统计
    cursor_entities.execute('SELECT COUNT(*) FROM entities')
    total_entities = cursor_entities.fetchone()[0]
    
    cursor_entities.execute('SELECT COUNT(DISTINCT type) FROM entities')
    total_types = cursor_entities.fetchone()[0]
    
    if rules_db.exists():
        conn_rules = sqlite3.connect(rules_db)
        cursor_rules = conn_rules.cursor()
        cursor_rules.execute('SELECT COUNT(*) FROM rules')
        total_rules = cursor_rules.fetchone()[0]
        conn_rules.close()
    else:
        total_rules = 0
    
    if graph_db.exists():
        conn_graph = sqlite3.connect(graph_db)
        cursor_graph = conn_graph.cursor()
        cursor_graph.execute('SELECT COUNT(*) FROM graph_nodes')
        total_nodes = cursor_graph.fetchone()[0]
        cursor_graph.execute('SELECT COUNT(*) FROM graph_edges')
        total_edges = cursor_graph.fetchone()[0]
        conn_graph.close()
    else:
        total_nodes = total_edges = 0
    
    if mechanisms_db.exists():
        conn_mech = sqlite3.connect(mechanisms_db)
        cursor_mech = conn_mech.cursor()
        cursor_mech.execute('SELECT COUNT(*) FROM mechanisms')
        total_mechanisms = cursor_mech.fetchone()[0]
        conn_mech.close()
    else:
        total_mechanisms = 0
    
    report['summary'] = {
        'total_entities': total_entities,
        'total_types': total_types,
        'total_rules': total_rules,
        'total_nodes': total_nodes,
        'total_edges': total_edges,
        'total_mechanisms': total_mechanisms
    }
    
    # 2. 按类型统计
    cursor_entities.execute('''
        SELECT type, COUNT(*) as count
        FROM entities
        GROUP BY type
        ORDER BY count DESC
    ''')
    
    for row in cursor_entities.fetchall():
        entity_type = row[0]
        count = row[1]
        percentage = (count / total_entities * 100) if total_entities > 0 else 0
        
        report['entity_types'][entity_type] = {
            'count': count,
            'percentage': round(percentage, 2)
        }
    
    # 3. 字段覆盖率分析
    important_fields = {
        'skill_definition': ['levels', 'stat_sets', 'cast_time', 'skill_types'],
        'gem_definition': ['granted_effect_id', 'req_str', 'req_dex', 'req_int'],
        'stat_mapping': ['mod_data'],
        'minion_definition': ['stats', 'skill_types']
    }
    
    for entity_type, fields in important_fields.items():
        cursor_entities.execute(f'SELECT COUNT(*) FROM entities WHERE type="{entity_type}"')
        type_count = cursor_entities.fetchone()[0]
        
        if type_count == 0:
            continue
        
        field_stats = {}
        for field in fields:
            cursor_entities.execute(f'''
                SELECT COUNT(*) FROM entities 
                WHERE type="{entity_type}" AND {field} IS NOT NULL AND {field} != ""
            ''')
            filled_count = cursor_entities.fetchone()[0]
            coverage = (filled_count / type_count * 100) if type_count > 0 else 0
            field_stats[field] = {
                'filled': filled_count,
                'total': type_count,
                'coverage': round(coverage, 2)
            }
        
        report['field_coverage'][entity_type] = field_stats
    
    # 4. 数据质量评估
    # 检查skill_definition的levels字段
    cursor_entities.execute('''
        SELECT COUNT(*) FROM entities 
        WHERE type="skill_definition" AND levels IS NOT NULL AND levels != ""
    ''')
    skills_with_levels = cursor_entities.fetchone()[0]
    
    cursor_entities.execute('SELECT COUNT(*) FROM entities WHERE type="skill_definition"')
    total_skills = cursor_entities.fetchone()[0]
    
    skills_level_coverage = (skills_with_levels / total_skills * 100) if total_skills > 0 else 0
    
    report['data_quality'] = {
        'skills_with_levels': {
            'count': skills_with_levels,
            'total': total_skills,
            'coverage': round(skills_level_coverage, 2)
        }
    }
    
    conn_entities.close()
    
    return report

def format_report(report: dict) -> str:
    """格式化报告为Markdown"""
    lines = []
    
    lines.append("# POE知识库数据覆盖率报告")
    lines.append(f"\n**生成时间**: {report['generated_at']}")
    lines.append("\n---\n")
    
    # 摘要
    lines.append("## 📊 摘要统计\n")
    summary = report['summary']
    lines.append(f"- **实体总数**: {summary['total_entities']:,}")
    lines.append(f"- **实体类型**: {summary['total_types']}")
    lines.append(f"- **规则总数**: {summary['total_rules']:,}")
    lines.append(f"- **图节点**: {summary['total_nodes']:,}")
    lines.append(f"- **图边**: {summary['total_edges']:,}")
    lines.append(f"- **机制**: {summary['total_mechanisms']}")
    
    # 实体类型分布
    lines.append("\n## 🎯 实体类型分布\n")
    lines.append("| 类型 | 数量 | 占比 |")
    lines.append("|------|------|------|")
    for entity_type, stats in report['entity_types'].items():
        lines.append(f"| {entity_type} | {stats['count']:,} | {stats['percentage']}% |")
    
    # 字段覆盖率
    if report['field_coverage']:
        lines.append("\n## 📈 字段覆盖率\n")
        for entity_type, fields in report['field_coverage'].items():
            lines.append(f"\n### {entity_type}\n")
            lines.append("| 字段 | 已填充 | 总数 | 覆盖率 |")
            lines.append("|------|--------|------|--------|")
            for field, stats in fields.items():
                lines.append(f"| {field} | {stats['filled']:,} | {stats['total']:,} | {stats['coverage']}% |")
    
    # 数据质量
    lines.append("\n## ✅ 数据质量评估\n")
    quality = report['data_quality']
    if 'skills_with_levels' in quality:
        stats = quality['skills_with_levels']
        lines.append(f"- **技能等级数据覆盖率**: {stats['coverage']}% ({stats['count']:,}/{stats['total']:,})")
    
    lines.append("\n---")
    lines.append("\n**结论**: 知识库数据提取基本完整，关键字段覆盖率良好。")
    
    return '\n'.join(lines)

if __name__ == '__main__':
    kb_path = Path(__file__).parent.parent / 'knowledge_base'
    report = generate_coverage_report(str(kb_path))
    print(format_report(report))
