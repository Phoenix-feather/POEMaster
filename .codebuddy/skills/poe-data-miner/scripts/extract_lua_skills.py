#!/usr/bin/env python3
"""
Extract skill definitions from POB Lua files.
Usage: python extract_lua_skills.py <lua_file> [--skill "<skill_name>"] [--output <output.json>]
"""

import re
import json
import argparse
from pathlib import Path
from typing import Dict, List, Any, Optional


def parse_lua_table(content: str) -> Dict[str, Any]:
    """Parse Lua table structure into Python dict."""
    result = {}
    
    # Match skills["SkillId"] = { ... }
    skill_pattern = r'skills\["([^"]+)"\]\s*=\s*\{([^}]*?(?:\{[^}]*\}[^}]*?)*)\}'
    
    for match in re.finditer(skill_pattern, content, re.DOTALL):
        skill_id = match.group(1)
        skill_body = match.group(2)
        result[skill_id] = parse_skill_body(skill_body)
    
    return result


def parse_skill_body(body: str) -> Dict[str, Any]:
    """Parse individual skill definition body."""
    skill = {}
    
    # Simple string fields
    string_fields = ['name', 'baseTypeName', 'description', 'color']
    for field in string_fields:
        pattern = rf'{field}\s*=\s*"([^"]*)"'
        match = re.search(pattern, body)
        if match:
            skill[field] = match.group(1)
    
    # Boolean fields
    bool_fields = ['support']
    for field in bool_fields:
        pattern = rf'{field}\s*=\s*(true|false)'
        match = re.search(pattern, body)
        if match:
            skill[field] = match.group(1) == 'true'
    
    # skillTypes extraction
    types_match = re.search(r'skillTypes\s*=\s*\{([^}]*)\}', body)
    if types_match:
        types_str = types_match.group(1)
        skill['skillTypes'] = re.findall(r'SkillType\.(\w+)', types_str)
    
    # Extract statSets
    statsets_match = re.search(r'statSets\s*=\s*\{(.+?)\n\s*\}', body, re.DOTALL)
    if statsets_match:
        skill['statSets'] = parse_statsets(statsets_match.group(1))
    
    # Extract levels
    levels_match = re.search(r'levels\s*=\s*\{(.+?)\n\s*\}', body, re.DOTALL)
    if levels_match:
        skill['levels'] = parse_levels(levels_match.group(1))
    
    return skill


def parse_statsets(content: str) -> List[Dict[str, Any]]:
    """Parse statSets section."""
    statsets = []
    
    # Match each statSet entry
    entry_pattern = r'\[\d+\]\s*=\s*\{([^}]+)\}'
    for match in re.finditer(entry_pattern, content, re.DOTALL):
        entry_body = match.group(1)
        statset = {}
        
        # Extract constantStats
        const_match = re.search(r'constantStats\s*=\s*\{([^]]+\])', entry_body, re.DOTALL)
        if const_match:
            statset['constantStats'] = parse_stats_array(const_match.group(1))
        
        # Extract stats
        stats_match = re.search(r'stats\s*=\s*\{([^]]+\])', entry_body, re.DOTALL)
        if stats_match:
            statset['stats'] = parse_string_array(stats_match.group(1))
        
        statsets.append(statset)
    
    return statsets


def parse_stats_array(content: str) -> List[List[Any]]:
    """Parse array of stat tuples."""
    stats = []
    pattern = r'\{\s*"([^"]+)"\s*,\s*([^}]+)\s*\}'
    for match in re.finditer(pattern, content):
        stat_name = match.group(1)
        stat_value = match.group(2).strip()
        # Try to convert to number
        try:
            stat_value = float(stat_value)
            if stat_value.is_integer():
                stat_value = int(stat_value)
        except ValueError:
            pass
        stats.append([stat_name, stat_value])
    return stats


def parse_string_array(content: str) -> List[str]:
    """Parse array of strings."""
    return re.findall(r'"([^"]+)"', content)


def parse_levels(content: str) -> Dict[int, Dict[str, Any]]:
    """Parse level definitions."""
    levels = {}
    pattern = r'\[(\d+)\]\s*=\s*\{([^}]+)\}'
    for match in re.finditer(pattern, content):
        level_num = int(match.group(1))
        level_body = match.group(2)
        
        level_data = {}
        # Extract key-value pairs
        kv_pattern = r'(\w+)\s*=\s*([^,}]+)'
        for kv_match in re.finditer(kv_pattern, level_body):
            key = kv_match.group(1)
            value = kv_match.group(2).strip()
            try:
                value = float(value)
                if value.is_integer():
                    value = int(value)
            except ValueError:
                pass
            level_data[key] = value
        
        levels[level_num] = level_data
    
    return levels


def extract_skill(content: str, skill_name: str) -> Optional[Dict[str, Any]]:
    """Extract a specific skill by name or ID."""
    skills = parse_lua_table(content)
    
    # Try exact ID match first
    if skill_name in skills:
        return {skill_name: skills[skill_name]}
    
    # Try name match
    for skill_id, skill_data in skills.items():
        if skill_data.get('name', '').lower() == skill_name.lower():
            return {skill_id: skill_data}
    
    return None


def main():
    parser = argparse.ArgumentParser(description='Extract skills from POB Lua files')
    parser.add_argument('lua_file', help='Path to Lua file')
    parser.add_argument('--skill', '-s', help='Specific skill name or ID to extract')
    parser.add_argument('--output', '-o', help='Output JSON file path')
    parser.add_argument('--list', '-l', action='store_true', help='List all skill IDs')
    
    args = parser.parse_args()
    
    content = Path(args.lua_file).read_text(encoding='utf-8')
    
    if args.skill:
        result = extract_skill(content, args.skill)
        if result:
            output = json.dumps(result, indent=2, ensure_ascii=False)
        else:
            print(f"Skill '{args.skill}' not found")
            return 1
    else:
        skills = parse_lua_table(content)
        if args.list:
            for skill_id, data in skills.items():
                print(f"{skill_id}: {data.get('name', 'N/A')}")
            return 0
        output = json.dumps(skills, indent=2, ensure_ascii=False)
    
    if args.output:
        Path(args.output).write_text(output, encoding='utf-8')
        print(f"Written to {args.output}")
    else:
        print(output)
    
    return 0


if __name__ == '__main__':
    exit(main())
