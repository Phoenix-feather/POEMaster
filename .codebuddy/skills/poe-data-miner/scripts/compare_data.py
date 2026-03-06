#!/usr/bin/env python3
"""
Compare two skills or items side-by-side.
Usage: python compare_data.py <entity1> <entity2> --data <data_dir>
"""

import argparse
import json
from pathlib import Path
from typing import Dict, Any, List, Tuple
from collections import defaultdict


def load_entity(file_path: str, name: str) -> Dict[str, Any]:
    """Load entity data from file."""
    data = json.loads(Path(file_path).read_text(encoding='utf-8'))
    if name in data:
        return data[name]
    for key, value in data.items():
        if isinstance(value, dict) and value.get("name", "").lower() == name.lower():
            return value
    return data


def compare_values(v1: Any, v2: Any) -> Tuple[bool, str]:
    """Compare two values and return (is_different, description)."""
    if v1 == v2:
        return False, "Same"
    return True, f"{v1} → {v2}"


def compare_skills(skill1: Dict[str, Any], skill2: Dict[str, Any]) -> Dict[str, Any]:
    """Compare two skills."""
    comparison = {
        "names": (skill1.get("name"), skill2.get("name")),
        "differences": {},
        "common": {}
    }
    
    # Compare skillTypes
    types1 = set(skill1.get("skillTypes", []))
    types2 = set(skill2.get("skillTypes", []))
    
    if types1 != types2:
        comparison["differences"]["skillTypes"] = {
            "only_in_1": list(types1 - types2),
            "only_in_2": list(types2 - types1),
            "common": list(types1 & types2)
        }
    else:
        comparison["common"]["skillTypes"] = list(types1)
    
    # Compare descriptions
    desc1 = skill1.get("description", "")
    desc2 = skill2.get("description", "")
    if desc1 != desc2:
        comparison["differences"]["description"] = {
            "entity1": desc1[:100] + "..." if len(desc1) > 100 else desc1,
            "entity2": desc2[:100] + "..." if len(desc2) > 100 else desc2
        }
    
    # Compare stats
    stats1 = {}
    stats2 = {}
    
    for statset in skill1.get("statSets", []):
        for stat in statset.get("constantStats", []):
            stats1[stat[0]] = stat[1]
    
    for statset in skill2.get("statSets", []):
        for stat in statset.get("constantStats", []):
            stats2[stat[0]] = stat[1]
    
    all_stats = set(stats1.keys()) | set(stats2.keys())
    stat_diff = {}
    for stat in all_stats:
        v1, v2 = stats1.get(stat), stats2.get(stat)
        if v1 != v2:
            stat_diff[stat] = {"entity1": v1, "entity2": v2}
    
    if stat_diff:
        comparison["differences"]["stats"] = stat_diff
    
    return comparison


def format_comparison(comparison: Dict[str, Any]) -> str:
    """Format comparison for display."""
    lines = []
    name1, name2 = comparison["names"]
    
    lines.append(f"## Comparison: {name1} vs {name2}")
    lines.append("")
    
    if comparison["differences"]:
        lines.append("### Differences")
        for key, diff in comparison["differences"].items():
            lines.append(f"\n**{key}:**")
            if isinstance(diff, dict):
                for k, v in diff.items():
                    lines.append(f"  - {k}: {v}")
            else:
                lines.append(f"  {diff}")
    
    if comparison["common"]:
        lines.append("\n### Common")
        for key, value in comparison["common"].items():
            lines.append(f"- **{key}**: {value}")
    
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description='Compare two skills/items')
    parser.add_argument('entity1', help='First entity name')
    parser.add_argument('entity2', help='Second entity name')
    parser.add_argument('--file1', '-f1', help='First entity file')
    parser.add_argument('--file2', '-f2', help='Second entity file')
    
    args = parser.parse_args()
    
    if not args.file1 or not args.file2:
        print("Both --file1 and --file2 are required")
        return 1
    
    entity1 = load_entity(args.file1, args.entity1)
    entity2 = load_entity(args.file2, args.entity2)
    
    comparison = compare_skills(entity1, entity2)
    print(format_comparison(comparison))
    
    return 0


if __name__ == '__main__':
    exit(main())
