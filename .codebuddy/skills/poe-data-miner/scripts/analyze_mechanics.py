#!/usr/bin/env python3
"""
Analyze POE skill mechanics and formulas.
Usage: python analyze_mechanics.py <skill_name> --data <data_dir>
"""

import argparse
import json
from pathlib import Path
from typing import Dict, Any, Optional


# Known mechanics formulas
MECHANICS = {
    "energy_generation": {
        "formula": "(HitDamage / AilmentThreshold) × BaseEnergy × (1 + IncBonus) × MoreMods",
        "description": "Energy generation for Meta Skills",
        "factors": {
            "base_energy": "Base energy per trigger event",
            "inc_bonus": "Sum of all increased modifiers (linear)",
            "more_mods": "Product of more/less modifiers (multiplicative)"
        }
    },
    "cast_on_critical": {
        "base_energy": 100,
        "unit": "centienergy per monster power",
        "level_scaling": "+3% energy_generated_+% per level"
    },
    "cast_on_block": {
        "base_energy": 2500,
        "unit": "centienergy per block",
        "note": "Fixed 25 energy per block"
    },
    "boundless_energy": {
        "tier1": "+35% energy generated",
        "tier2": "+45% energy generated"
    },
    "doedres_undoing": {
        "mechanism": "Curse creates Hazard zone, explosion damage attributed to player",
        "effect": "Bypasses SkillType.Triggered energy restriction",
        "applicable_to": ["Cast on Critical", "Cast on Elemental Ailment"]
    }
}


def analyze_skill(skill_data: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze a skill's mechanics based on its data."""
    analysis = {
        "skill_name": skill_data.get("name", "Unknown"),
        "skill_types": skill_data.get("skillTypes", []),
        "mechanics": {},
        "stats_analysis": {}
    }
    
    # Check if Meta skill
    if "Meta" in analysis["skill_types"]:
        analysis["mechanics"]["type"] = "Meta Skill"
        
        if "GeneratesEnergy" in analysis["skill_types"]:
            analysis["mechanics"]["energy"] = MECHANICS["energy_generation"]
    
    # Analyze statSets
    for i, statset in enumerate(skill_data.get("statSets", [])):
        stats = statset.get("stats", [])
        const_stats = statset.get("constantStats", [])
        
        analysis["stats_analysis"][f"statSet_{i+1}"] = {
            "stats": stats,
            "constantStats": const_stats
        }
        
        # Check for known stats
        for stat_name, stat_value in const_stats:
            if "centienergy" in stat_name:
                analysis["mechanics"]["energy_base"] = {
                    "value": stat_value,
                    "stat": stat_name
                }
    
    return analysis


def format_analysis(analysis: Dict[str, Any]) -> str:
    """Format analysis for display."""
    lines = []
    lines.append(f"## Skill: {analysis['skill_name']}")
    lines.append(f"Types: {', '.join(analysis['skill_types'])}")
    lines.append("")
    
    if analysis["mechanics"]:
        lines.append("### Mechanics")
        for key, value in analysis["mechanics"].items():
            if isinstance(value, dict):
                lines.append(f"- **{key}**:")
                for k, v in value.items():
                    lines.append(f"  - {k}: {v}")
            else:
                lines.append(f"- **{key}**: {value}")
        lines.append("")
    
    if analysis["stats_analysis"]:
        lines.append("### Stats Analysis")
        for statset_name, statset_data in analysis["stats_analysis"].items():
            lines.append(f"- **{statset_name}**:")
            for stat in statset_data.get("constantStats", []):
                lines.append(f"  - {stat[0]}: {stat[1]}")
            for stat in statset_data.get("stats", []):
                lines.append(f"  - {stat}")
    
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description='Analyze skill mechanics')
    parser.add_argument('skill_name', help='Skill name to analyze')
    parser.add_argument('--data', '-d', help='Data directory containing skill files')
    parser.add_argument('--skill-file', '-s', help='Direct path to skill JSON file')
    
    args = parser.parse_args()
    
    skill_data = None
    
    if args.skill_file:
        skill_data = json.loads(Path(args.skill_file).read_text(encoding='utf-8'))
        if args.skill_name in skill_data:
            skill_data = skill_data[args.skill_name]
    elif args.data:
        # Try to find skill in data directory
        data_dir = Path(args.data)
        for json_file in data_dir.glob("**/*.json"):
            try:
                data = json.loads(json_file.read_text(encoding='utf-8'))
                if args.skill_name in data:
                    skill_data = data[args.skill_name]
                    break
                for skill_id, skill in (data.items() if isinstance(data, dict) else []):
                    if skill.get("name", "").lower() == args.skill_name.lower():
                        skill_data = skill
                        break
            except (json.JSONDecodeError, AttributeError):
                continue
    
    if not skill_data:
        print(f"Skill '{args.skill_name}' not found")
        return 1
    
    analysis = analyze_skill(skill_data)
    print(format_analysis(analysis))
    
    return 0


if __name__ == '__main__':
    exit(main())
