#!/usr/bin/env python3
"""
Parse and filter JSON data files.
Usage: python parse_json_data.py <json_file> [--filter <pattern>] [--output <output.json>]
"""

import json
import argparse
import re
from pathlib import Path
from typing import Dict, List, Any, Optional


def load_json(file_path: str) -> Any:
    """Load JSON file."""
    return json.loads(Path(file_path).read_text(encoding='utf-8'))


def filter_by_pattern(data: Any, pattern: str) -> Any:
    """Filter data by regex pattern on keys or values."""
    regex = re.compile(pattern, re.IGNORECASE)
    
    if isinstance(data, dict):
        return {
            k: v for k, v in data.items()
            if regex.search(k) or (isinstance(v, str) and regex.search(v))
        }
    elif isinstance(data, list):
        return [
            item for item in data
            if isinstance(item, dict) and any(
                regex.search(str(k)) or regex.search(str(v))
                for k, v in item.items()
            )
        ]
    return data


def extract_keys(data: Any, keys: List[str]) -> Any:
    """Extract specific keys from data."""
    if isinstance(data, dict):
        return {k: data.get(k) for k in keys if k in data}
    elif isinstance(data, list):
        return [
            {k: item.get(k) for k in keys if k in item}
            for item in data if isinstance(item, dict)
        ]
    return data


def pretty_print(data: Any, indent: int = 2) -> str:
    """Format data for display."""
    return json.dumps(data, indent=indent, ensure_ascii=False)


def main():
    parser = argparse.ArgumentParser(description='Parse and filter JSON data')
    parser.add_argument('json_file', help='Path to JSON file')
    parser.add_argument('--filter', '-f', help='Regex pattern to filter by')
    parser.add_argument('--keys', '-k', help='Comma-separated keys to extract')
    parser.add_argument('--output', '-o', help='Output JSON file path')
    parser.add_argument('--stats', '-s', action='store_true', help='Show data statistics')
    
    args = parser.parse_args()
    
    data = load_json(args.json_file)
    
    if args.filter:
        data = filter_by_pattern(data, args.filter)
    
    if args.keys:
        keys = [k.strip() for k in args.keys.split(',')]
        data = extract_keys(data, keys)
    
    if args.stats:
        if isinstance(data, dict):
            print(f"Type: Object with {len(data)} keys")
            print(f"Keys: {list(data.keys())[:10]}{'...' if len(data) > 10 else ''}")
        elif isinstance(data, list):
            print(f"Type: Array with {len(data)} items")
            if data and isinstance(data[0], dict):
                print(f"Sample keys: {list(data[0].keys())}")
        return 0
    
    output = pretty_print(data)
    
    if args.output:
        Path(args.output).write_text(output, encoding='utf-8')
        print(f"Written to {args.output}")
    else:
        print(output)
    
    return 0


if __name__ == '__main__':
    exit(main())
