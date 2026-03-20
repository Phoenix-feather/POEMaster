#!/usr/bin/env python3
"""
POE数据扫描模块
扫描POB所有Lua文件，识别数据类型，提取实体数据、映射数据、计算逻辑
"""

import os
import re
import json
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum

# 尝试导入yaml，如果失败则使用简单的解析
try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


class DataType(Enum):
    """数据类型枚举"""
    SKILL_DEFINITION = "skill_definition"
    GEM_DEFINITION = "gem_definition"
    UNIQUE_ITEM = "unique_item"
    STAT_MAPPING = "stat_mapping"
    CALCULATION_MODULE = "calculation_module"
    DATA_TABLE = "data_table"
    CONFIG_SETTINGS = "config_settings"
    PASSIVE_NODE = "passive_node"  # 天赋节点（包括升华）
    ITEM_BASE = "item_base"  # 装备基础
    MINION_DEFINITION = "minion_definition"  # 召唤物/幽灵
    MOD_AFFIX = "mod_affix"  # 词缀定义（普通/腐化/珠宝/独占）
    MOD_DEFINITION = "mod_definition"  # ModCache.lua 中的游戏机制映射
    UNKNOWN = "unknown"


@dataclass
class ScanResult:
    """扫描结果"""
    file_path: str
    data_type: DataType
    content: str
    entities: List[Dict[str, Any]]
    version: Optional[str] = None


@dataclass
class ScanCache:
    """扫描缓存"""
    pob_path: str
    version: Optional[str] = None
    files_scanned: int = 0
    entities_found: int = 0
    last_scan_time: Optional[str] = None


@dataclass
class ScanLogEntry:
    """单个文件的扫描日志条目"""
    file_path: str
    file_size: int
    decision: str  # 'parsed', 'skipped', 'error'
    data_type: Optional[str] = None
    entities_found: int = 0
    reason: Optional[str] = None  # 跳过原因
    error_message: Optional[str] = None
    parse_time_ms: Optional[int] = None


class ScanLog:
    """扫描日志收集器"""
    
    # 已知的游戏无关数据类别
    GAME_IRRELEVANT_CATEGORIES = {
        'ui_data': ['FlavourText.lua', 'QueryMods.lua'],
        'config': ['Global.lua', 'Misc.lua'],
        'update': ['Update'],  # 目录名
    }
    
    def __init__(self):
        self.entries: List[ScanLogEntry] = []
        self.summary = {
            'total_files': 0,
            'parsed_files': 0,
            'skipped_files': 0,
            'error_files': 0,
            'skipped_reasons': {},
            'parsed_by_type': {},
        }
    
    def add_entry(self, entry: ScanLogEntry):
        """添加日志条目"""
        self.entries.append(entry)
        self.summary['total_files'] += 1
        
        if entry.decision == 'parsed':
            self.summary['parsed_files'] += 1
            type_key = entry.data_type or 'unknown'
            self.summary['parsed_by_type'][type_key] = self.summary['parsed_by_type'].get(type_key, 0) + 1
        elif entry.decision == 'skipped':
            self.summary['skipped_files'] += 1
            reason = entry.reason or 'unknown'
            self.summary['skipped_reasons'][reason] = self.summary['skipped_reasons'].get(reason, 0) + 1
        elif entry.decision == 'error':
            self.summary['error_files'] += 1
    
    def get_category(self, file_path: str) -> Optional[str]:
        """判断文件是否属于游戏无关数据类别"""
        for category, patterns in self.GAME_IRRELEVANT_CATEGORIES.items():
            for pattern in patterns:
                if pattern in file_path:
                    return category
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'summary': self.summary,
            'skipped_details': [
                {
                    'file': e.file_path,
                    'reason': e.reason,
                    'category': self.get_category(e.file_path),
                }
                for e in self.entries 
                if e.decision == 'skipped'
            ][:20],  # 只保留前20个跳过记录
            'error_details': [
                {
                    'file': e.file_path,
                    'error': e.error_message,
                }
                for e in self.entries 
                if e.decision == 'error'
            ][:10],  # 只保留前10个错误记录
        }
    
    def save_yaml(self, path: str):
        """保存为 YAML 文件"""
        import yaml
        with open(path, 'w', encoding='utf-8') as f:
            yaml.dump(self.to_dict(), f, default_flow_style=False, allow_unicode=True)
    
    def print_summary(self):
        """打印摘要"""
        print("\n=== 扫描日志摘要 ===")
        print(f"总文件数: {self.summary['total_files']}")
        print(f"已解析: {self.summary['parsed_files']}")
        print(f"已跳过: {self.summary['skipped_files']}")
        print(f"错误: {self.summary['error_files']}")
        
        if self.summary['parsed_by_type']:
            print("\n按类型解析:")
            for t, c in sorted(self.summary['parsed_by_type'].items(), key=lambda x: -x[1]):
                print(f"  {t}: {c}")
        
        if self.summary['skipped_reasons']:
            print("\n跳过原因:")
            for r, c in sorted(self.summary['skipped_reasons'].items(), key=lambda x: -x[1])[:5]:
                print(f"  {r}: {c}")


class POBDataScanner:
    """POB数据扫描器"""
    
    def __init__(self, pob_path: str, config_path: Optional[str] = None, enable_log: bool = True):
        """
        初始化扫描器
        
        Args:
            pob_path: POB数据目录路径
            config_path: 配置文件路径
            enable_log: 是否启用扫描日志
        """
        self.pob_path = Path(pob_path)
        self.config = self._load_config(config_path) if config_path else self._default_config()
        self.cache = ScanCache(pob_path=str(self.pob_path))
        self.results: List[ScanResult] = []
        self.scan_log = ScanLog() if enable_log else None
    
    # ========== 括号平衡解析器 ==========
    
    def extract_lua_table(self, content: str, start_pos: int) -> Optional[str]:
        """
        使用括号平衡算法提取完整的Lua表
        
        Args:
            content: 文件内容
            start_pos: 表开始位置（'{'的位置）
            
        Returns:
            完整的表内容（包括外层{}）
        """
        depth = 0
        i = start_pos
        in_string = False
        string_char = None
        escape_next = False
        
        while i < len(content):
            char = content[i]
            
            # 处理转义字符
            if escape_next:
                escape_next = False
                i += 1
                continue
            
            if char == '\\':
                escape_next = True
                i += 1
                continue
            
            # 处理字符串
            if in_string:
                if char == string_char:
                    in_string = False
                    string_char = None
            else:
                if char in '"\'':
                    in_string = True
                    string_char = char
                elif char == '{':
                    depth += 1
                elif char == '}':
                    depth -= 1
                    if depth == 0:
                        return content[start_pos:i+1]
            
            i += 1
        
        return None
    
    def _extract_skill_types(self, table_content: str) -> List[str]:
        """
        从skillTypes表中提取技能类型
        
        Args:
            table_content: skillTypes表内容
            
        Returns:
            技能类型列表
        """
        types = []
        # 匹配 [SkillType.XXX] = true 格式
        pattern = r'\[SkillType\.(\w+)\]\s*=\s*true'
        matches = re.findall(pattern, table_content)
        types.extend(matches)
        
        # 也匹配直接字符串列表
        str_matches = re.findall(r'"(\w+)"', table_content)
        for m in str_matches:
            if m not in types and not m.startswith('_'):
                types.append(m)
        
        return types
    
    def _extract_stat_sets(self, table_content: str) -> Dict[str, Any]:
        """
        从statSets表中提取属性（完整版）
        
        Args:
            table_content: 完整的技能表内容
            
        Returns:
            包含所有statSets数据的字典
        """
        result = {
            'constant_stats': [],
            'stats': [],
            'stat_sets': {}  # 新增：完整statSets数据
        }
        
        # 找到statSets部分
        statsets_match = re.search(r'statSets\s*=\s*\{', table_content)
        if not statsets_match:
            return result
        
        # 提取statSets表
        statsets_start = statsets_match.end() - 1
        statsets_content = self.extract_lua_table(table_content, statsets_start)
        if not statsets_content:
            return result
        
        # 在statSets中找[1]或第一个表
        first_set_match = re.search(r'\[\s*1\s*\]\s*=\s*\{', statsets_content)
        if not first_set_match:
            # 尝试找第一个嵌套表
            first_set_match = re.search(r'=\s*\{[^{]*\{', statsets_content)
        
        if not first_set_match:
            return result
        
        # 提取第一个statSet
        set_start = first_set_match.end() - 1
        set_content = self.extract_lua_table(statsets_content, set_start)
        if not set_content:
            return result
        
        # 提取完整的statSets数据
        stat_sets_data = {}
        
        # 提取 label
        label_match = re.search(r'label\s*=\s*"([^"]+)"', set_content)
        if label_match:
            stat_sets_data['label'] = label_match.group(1)
        
        # 提取 baseEffectiveness
        base_eff_match = re.search(r'baseEffectiveness\s*=\s*([\d.]+)', set_content)
        if base_eff_match:
            stat_sets_data['baseEffectiveness'] = float(base_eff_match.group(1))
        
        # 提取 incrementalEffectiveness
        inc_eff_match = re.search(r'incrementalEffectiveness\s*=\s*([\d.]+)', set_content)
        if inc_eff_match:
            stat_sets_data['incrementalEffectiveness'] = float(inc_eff_match.group(1))
        
        # 提取 damageIncrementalEffectiveness
        dmg_inc_eff_match = re.search(r'damageIncrementalEffectiveness\s*=\s*([\d.]+)', set_content)
        if dmg_inc_eff_match:
            stat_sets_data['damageIncrementalEffectiveness'] = float(dmg_inc_eff_match.group(1))
        
        # 提取 statDescriptionScope
        scope_match = re.search(r'statDescriptionScope\s*=\s*"([^"]+)"', set_content)
        if scope_match:
            stat_sets_data['statDescriptionScope'] = scope_match.group(1)
        
        # 提取 baseFlags
        base_flags = []
        flags_match = re.search(r'baseFlags\s*=\s*\{([^}]+)\}', set_content)
        if flags_match:
            flags_content = flags_match.group(1)
            # 匹配 flag_name = true
            flag_pattern = r'(\w+)\s*=\s*true'
            base_flags = re.findall(flag_pattern, flags_content)
        if base_flags:
            stat_sets_data['baseFlags'] = base_flags
        
        # 提取 notMinionStat
        not_minion_stats = []
        not_minion_match = re.search(r'notMinionStat\s*=\s*\{([^}]+)\}', set_content)
        if not_minion_match:
            stats_content = not_minion_match.group(1)
            not_minion_stats = re.findall(r'"([^"]+)"', stats_content)
        if not_minion_stats:
            stat_sets_data['notMinionStat'] = not_minion_stats
        
        # 提取 statMap（简化版，只提取stat名称）
        stat_map = {}
        statmap_match = re.search(r'statMap\s*=\s*\{', set_content)
        if statmap_match:
            statmap_start = statmap_match.end() - 1
            statmap_table = self.extract_lua_table(set_content, statmap_start)
            if statmap_table:
                # 提取所有stat名称
                stat_pattern = r'\["([^"]+)"\]\s*='
                stat_names = re.findall(stat_pattern, statmap_table)
                for stat_name in stat_names:
                    stat_map[stat_name] = {}  # 简化处理
        if stat_map:
            stat_sets_data['statMap'] = stat_map
        
        # 提取 statSets.levels（每级stat值）
        levels_data = {}
        levels_match = re.search(r'levels\s*=\s*\{', set_content)
        if levels_match:
            levels_start = levels_match.end() - 1
            levels_table = self.extract_lua_table(set_content, levels_start)
            if levels_table:
                # 匹配每个等级 [n] = { ... }
                level_pattern = r'\[\s*(\d+)\s*\]\s*=\s*\{([^}]+)\}'
                level_matches = re.finditer(level_pattern, levels_table)
                
                for level_match in level_matches:
                    level_num = level_match.group(1)
                    level_content = level_match.group(2)
                    
                    level_data = {}
                    
                    # 提取stat值（数字列表）
                    values = []
                    value_pattern = r'([\d.]+)'
                    value_matches = re.findall(value_pattern, level_content.split('statInterpolation')[0])
                    values = [float(v) if '.' in v else int(v) for v in value_matches]
                    if values:
                        level_data['values'] = values
                    
                    # 提取 statInterpolation
                    interp_match = re.search(r'statInterpolation\s*=\s*\{([^}]+)\}', level_content)
                    if interp_match:
                        interp_content = interp_match.group(1)
                        interp_values = re.findall(r'(\d+)', interp_content)
                        level_data['statInterpolation'] = [int(v) for v in interp_values]
                    
                    # 提取 actorLevel
                    actor_match = re.search(r'actorLevel\s*=\s*([\d.]+)', level_content)
                    if actor_match:
                        level_data['actorLevel'] = float(actor_match.group(1))
                    
                    if level_data:
                        levels_data[level_num] = level_data
        
        if levels_data:
            stat_sets_data['levels'] = levels_data
        
        # 保存完整的statSets数据
        if stat_sets_data:
            result['stat_sets'] = stat_sets_data
        
        # 从set_content中提取constantStats
        const_match = re.search(r'constantStats\s*=\s*\{', set_content)
        if const_match:
            const_start = const_match.end() - 1
            const_table = self.extract_lua_table(set_content, const_start)
            if const_table:
                # 提取 { "name", value } 格式（支持负数值，如 -30）
                pattern = r'\{\s*"([^"]+)"\s*,\s*(-?[\d.]+)\s*\}'
                matches = re.findall(pattern, const_table)
                for name, value in matches:
                    result['constant_stats'].append([name, float(value) if '.' in value else int(value)])
        
        # 从set_content中提取stats
        stats_match = re.search(r'stats\s*=\s*\{', set_content)
        if stats_match:
            stats_start = stats_match.end() - 1
            stats_table = self.extract_lua_table(set_content, stats_start)
            if stats_table:
                # 提取字符串列表
                stats = re.findall(r'"([^"]+)"', stats_table)
                result['stats'] = stats
        
        return result
        
    def _default_config(self) -> Dict:
        """默认配置 - 使用特征指纹识别"""
        return {
            # 特征指纹配置：每种类型由多个特征组合识别
            # score_threshold: 需要匹配的最少特征数
            # features: 特征模式列表，每个匹配得1分
            'type_fingerprints': {
                'skill_definition': {
                    'score_threshold': 2,
                    'features': [
                        r'skills\s*\[\s*"[^"]+"\s*\]\s*=\s*\{',
                        r'skillTypes\s*=',
                        r'constantStats\s*=',
                        r'levels\s*=\s*\{',
                    ],
                    'data_type': 'skill_definition'
                },
                'passive_node': {
                    'score_threshold': 2,
                    'features': [
                        r'\tnodes\s*=\s*\{',  # tree.lua 格式（前面有tab）
                        r'orbit\s*=\s*\d+',
                        r'ascendancyName\s*=',
                        r'isNotable\s*=',
                    ],
                    'data_type': 'passive_node'
                },
                'stat_mapping': {
                    'score_threshold': 2,
                    'features': [
                        r'c\s*\[\s*"[^"]+"\s*\]\s*=\s*\{',  # ModCache 格式
                        r'local\s+c\s*=',
                    ],
                    'data_type': 'stat_mapping'
                },
                'gem_definition': {
                    'score_threshold': 2,
                    'features': [
                        r'\[\s*"Metadata/Items/Gems/[^"]+"\s*\]',
                        r'gem_data\s*=',
                        r'requires_level\s*=',
                        r'gem_tags\s*=',
                    ],
                    'data_type': 'gem_definition'
                },
                'unique_item': {
                    'score_threshold': 2,
                    'features': [
                        r'\[\[',  # 多行字符串
                        r'\]\]',
                        r'addItemMod',
                        r'Variant:',
                    ],
                    'data_type': 'unique_item'
                },
                'item_base': {
                    'score_threshold': 2,
                    'features': [
                        r'itemBases\s*\[\s*"[^"]+"\s*\]\s*=',
                        r'type\s*=\s*"[^"]+"\s*,',  # 装备类型
                        r'tags\s*=\s*\{',
                        r'armour\s*=',
                        r'evasion\s*=',
                        r'energyShield\s*=',
                    ],
                    'data_type': 'item_base'
                },
                'minion_definition': {
                    'score_threshold': 2,
                    'features': [
                        r'minions\s*\[\s*"[^"]+"\s*\]\s*=\s*\{',
                        r'monsterTags\s*=',
                        r'spectreReservation\s*=',
                        r'companionReservation\s*=',
                        r'monsterCategory\s*=',
                    ],
                    'data_type': 'minion_definition'
                },
                'mod_affix': {
                    'score_threshold': 3,
                    'features': [
                        r'\[\s*"[A-Z][a-zA-Z0-9_]+"\s*\]\s*=\s*\{\s*type\s*=',  # 词缀ID格式
                        r'type\s*=\s*"(Prefix|Suffix|Corrupted)"\s*,',
                        r'affix\s*=\s*"[^"]*"',
                        r'statOrder\s*=\s*\{',
                        r'weightKey\s*=\s*\{',
                        r'modTags\s*=\s*\{',
                        r'tradeHash\s*=',
                    ],
                    'data_type': 'mod_affix'
                },
                'calculation_module': {
                    'score_threshold': 2,
                    'features': [
                        r'function\s+\w+\.\w+\s*\(',  # function xxx.yyy() 格式
                        r'function\s+calcs\.',         # function calcs.xxx
                        r'local\s+calcs\s*=',          # local calcs = ...
                        r'calcs\.\w+\s*=',             # calcs.xxx = function
                    ],
                    'data_type': 'calculation_module'
                },
            },
            # 保留旧的 patterns 配置作为回退（兼容性）
            'file_type_patterns': {
                'skill_definition': {
                    'patterns': [r'skills\s*\[\s*"[^"]+"\s*\]\s*=\s*\{'],
                    'data_type': 'skill_definition',
                    'priority': 1
                },
                'passive_node': {
                    'patterns': [r'\tnodes\s*=\s*\{'],
                    'data_type': 'passive_node',
                    'priority': 1
                },
                'stat_mapping': {
                    'patterns': [r'c\s*\[\s*"[^"]+"\s*\]'],
                    'data_type': 'stat_mapping',
                    'priority': 1
                },
                'gem_definition': {
                    'patterns': [r'\[\s*"Metadata/Items/Gems/'],
                    'data_type': 'gem_definition',
                    'priority': 2
                },
                'unique_item': {
                    'patterns': [r'\[\[.*\]\]'],
                    'data_type': 'unique_item',
                    'priority': 3
                },
                'item_base': {
                    'patterns': [r'itemBases\s*\[\s*"'],
                    'data_type': 'item_base',
                    'priority': 1
                },
                'minion_definition': {
                    'patterns': [r'minions\s*\[\s*"'],
                    'data_type': 'minion_definition',
                    'priority': 0
                },
                'mod_affix': {
                    'patterns': [r'type\s*=\s*"(Prefix|Suffix|Corrupted)"'],
                    'data_type': 'mod_affix',
                    'priority': 0
                }
            },
            'extraction_patterns': {
                'skill_id_name': {
                    'pattern': r'skills\s*\[\s*"([^"]+)"\s*\]'
                },
                'skill_types': {
                    'pattern': r'skillTypes\s*=\s*\{([^}]+)\}'
                },
                'constant_stats': {
                    'pattern': r'constantStats\s*=\s*\{([^}]+)\}'
                },
                'variable_stats': {
                    'pattern': r'stats\s*=\s*\{([^}]+)\}'
                }
            },
            'version_patterns': {
                'game_version': {
                    'patterns': [
                        r'game_version\s*=\s*"([^"]+)"',
                        r'GAME_VERSION\s*=\s*"([^"]+)"'
                    ]
                }
            }
        }
    
    def _load_config(self, config_path: str) -> Dict:
        """加载配置文件"""
        with open(config_path, 'r', encoding='utf-8') as f:
            if HAS_YAML:
                return yaml.safe_load(f)
            else:
                # 简单的YAML解析
                content = f.read()
                return self._parse_simple_yaml(content)
    
    def _parse_simple_yaml(self, content: str) -> Dict:
        """简单的YAML解析（当PyYAML不可用时）"""
        # 这是一个简化的解析器，只处理基本的键值对
        config = {}
        lines = content.split('\n')
        current_key = None
        current_indent = 0
        
        for line in lines:
            if line.strip().startswith('#') or not line.strip():
                continue
            
            indent = len(line) - len(line.lstrip())
            if ':' in line and indent <= current_indent:
                key, _, value = line.partition(':')
                current_key = key.strip()
                if value.strip():
                    config[current_key] = value.strip().strip('"\'')
        
        return config
    
    def scan_all_files(self) -> List[ScanResult]:
        """
        扫描所有Lua文件（通过pob_paths模块遵循POB数据提取范围规则）
        
        Returns:
            扫描结果列表
        """
        import time
        from pob_paths import collect_lua_files
        
        self.results = []
        
        # 通过统一入口收集Lua文件（强制执行POB数据提取范围规则）
        lua_files = collect_lua_files(self.pob_path, verbose=True)
        print(f"\n符合POB数据提取范围规则的Lua文件: {len(lua_files)} 个")
        
        for file_path in lua_files:
            start_time = time.time()
            result = self.scan_file(file_path)
            parse_time_ms = int((time.time() - start_time) * 1000) if result else None
            
            if result:
                self.results.append(result)
                self.cache.files_scanned += 1
                
                # 记录解析成功
                if self.scan_log:
                    self.scan_log.add_entry(ScanLogEntry(
                        file_path=result.file_path,
                        file_size=len(result.content),
                        decision='parsed',
                        data_type=result.data_type.value,
                        entities_found=len(result.entities),
                        parse_time_ms=parse_time_ms
                    ))
        
        # 提取版本信息
        self.cache.version = self._extract_version()
        
        # 打印日志摘要
        if self.scan_log:
            self.scan_log.print_summary()
        
        return self.results
    
    def scan_file(self, file_path: Path) -> Optional[ScanResult]:
        """
        扫描单个文件
        
        Args:
            file_path: 文件路径
            
        Returns:
            扫描结果或None
        """
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            file_size = len(content)
        except Exception as e:
            # 记录读取错误
            if self.scan_log:
                self.scan_log.add_entry(ScanLogEntry(
                    file_path=str(file_path.relative_to(self.pob_path)) if file_path.is_relative_to(self.pob_path) else str(file_path),
                    file_size=0,
                    decision='error',
                    error_message=str(e)
                ))
            return None
        
        # 识别数据类型
        data_type = self._identify_data_type(content)
        if data_type == DataType.UNKNOWN:
            # 记录跳过（无匹配类型）
            if self.scan_log:
                # 判断是否是游戏无关数据
                category = self.scan_log.get_category(str(file_path))
                reason = f'game_irrelevant_{category}' if category else 'no_matching_patterns'
                
                self.scan_log.add_entry(ScanLogEntry(
                    file_path=str(file_path.relative_to(self.pob_path)),
                    file_size=file_size,
                    decision='skipped',
                    reason=reason
                ))
            return None
        
        # 提取实体
        entities = self._extract_entities(content, data_type)
        
        return ScanResult(
            file_path=str(file_path.relative_to(self.pob_path)),
            data_type=data_type,
            content=content,
            entities=entities
        )
    
    def _identify_data_type(self, content: str) -> DataType:
        """
        使用特征指纹识别数据类型
        
        原理：基于多个特征的组合评分，而非单一模式匹配
        每个特征匹配得1分，达到阈值则识别为该类型
        得分最高的类型胜出
        
        Args:
            content: 文件内容
            
        Returns:
            数据类型
        """
        fingerprints = self.config.get('type_fingerprints', {})
        
        # 计算每种类型的得分
        type_scores = {}
        
        for type_name, fingerprint in fingerprints.items():
            score = 0
            threshold = fingerprint.get('score_threshold', 1)
            features = fingerprint.get('features', [])
            matched_features = []
            
            for feature in features:
                if re.search(feature, content):
                    score += 1
                    matched_features.append(feature[:30])  # 记录匹配的特征
            
            # 达到阈值才记录得分
            if score >= threshold:
                type_scores[type_name] = {
                    'score': score,
                    'threshold': threshold,
                    'matched': matched_features,
                    'data_type': fingerprint.get('data_type', type_name)
                }
        
        # 选择得分最高的类型
        if type_scores:
            best_type = max(type_scores.keys(), key=lambda x: type_scores[x]['score'])
            return DataType(type_scores[best_type]['data_type'])
        
        # 回退到旧的模式匹配
        patterns = self.config.get('file_type_patterns', {})
        best_match = DataType.UNKNOWN
        best_priority = float('inf')
        
        for type_name, type_config in patterns.items():
            for pattern in type_config.get('patterns', []):
                if re.search(pattern, content):
                    priority = type_config.get('priority', 999)
                    if priority < best_priority:
                        best_priority = priority
                        best_match = DataType(type_config.get('data_type', type_name))
        
        return best_match
    
    def _extract_entities(self, content: str, data_type: DataType) -> List[Dict[str, Any]]:
        """
        提取实体数据
        
        Args:
            content: 文件内容
            data_type: 数据类型
            
        Returns:
            实体列表
        """
        entities = []
        
        if data_type == DataType.SKILL_DEFINITION:
            entities = self._extract_skills(content)
        elif data_type == DataType.STAT_MAPPING:
            entities = self._extract_stat_mappings(content)
        elif data_type == DataType.CALCULATION_MODULE:
            entities = self._extract_calculation_functions(content)
        elif data_type == DataType.GEM_DEFINITION:
            entities = self._extract_gems(content)
        elif data_type == DataType.UNIQUE_ITEM:
            entities = self._extract_uniques(content)
        elif data_type == DataType.ITEM_BASE:
            entities = self._extract_item_bases(content)
        elif data_type == DataType.MINION_DEFINITION:
            entities = self._extract_minions(content)
        elif data_type == DataType.MOD_AFFIX:
            entities = self._extract_mod_affix(content)
        elif data_type == DataType.PASSIVE_NODE:
            entities = self._extract_passive_nodes(content)
        
        self.cache.entities_found += len(entities)
        return entities
    
    def _extract_skills(self, content: str) -> List[Dict[str, Any]]:
        """提取技能定义 - 使用括号平衡算法"""
        skills = []
        
        # 匹配 skills["xxx"] = { 的开始位置
        pattern = r'skills\s*\[\s*"([^"]+)"\s*\]\s*=\s*\{'
        matches = list(re.finditer(pattern, content))
        
        for match in matches:
            skill_id = match.group(1)
            table_start = match.end() - 1  # '{' 的位置
            
            # 使用括号平衡提取完整表
            table_content = self.extract_lua_table(content, table_start)
            if not table_content:
                continue
            
            # 从表内容中提取字段
            skill = {
                'id': skill_id,
                'name': self._extract_field(table_content, 'name'),
                'base_type_name': self._extract_field(table_content, 'baseTypeName'),
                'cast_time': self._extract_cast_time(table_content),
                'quality_stats': self._extract_quality_stats(table_content),
                'skill_types': self._extract_skill_types_from_table(table_content),
                'constant_stats': [],
                'stats': [],
                'description': self._extract_field(table_content, 'description'),
                'reservation': self._extract_reservation(table_content),
                'levels': self._extract_levels(table_content),
                'stat_sets': {},
                'support': self._extract_support_flag(table_content),
                'require_skill_types': self._extract_require_skill_types(table_content),
                'add_skill_types': self._extract_add_skill_types(table_content),
                'exclude_skill_types': self._extract_exclude_skill_types(table_content),
                'is_trigger': self._extract_is_trigger(table_content),
                'hidden': self._extract_hidden(table_content)
            }
            
            # 从statSets提取属性
            stat_sets = self._extract_stat_sets(table_content)
            skill['constant_stats'] = stat_sets['constant_stats']
            skill['stats'] = stat_sets['stats']
            skill['stat_sets'] = stat_sets.get('stat_sets', {})
            
            # 检查hidden字段
            # 注意：不再跳过隐藏技能！隐藏技能对绕过检测至关重要
            # （如 TriggeredCurseZoneHazardExplosionPlayer 自带 InbuiltTrigger 标签，
            #   被 SupportMeta* 的 excludeSkillTypes 排除 → 绕过 Triggered 约束）
            # hidden=true 的技能仍然入库，通过 hidden=1 字段标记
            
            # 验证必要字段
            if not skill['id']:
                continue
            
            # 使用ID作为默认名称
            if not skill['name']:
                skill['name'] = skill_id
            
            skills.append(skill)
        
        return skills
    
    def _extract_skill_types_from_table(self, table_content: str) -> List[str]:
        """从技能表中提取skillTypes"""
        # 找到skillTypes部分
        types_match = re.search(r'skillTypes\s*=\s*\{', table_content)
        if not types_match:
            return []
        
        # 提取skillTypes表
        types_start = types_match.end() - 1
        types_table = self.extract_lua_table(table_content, types_start)
        if not types_table:
            return []
        
        return self._extract_skill_types(types_table)
    
    def _extract_stat_mappings(self, content: str) -> List[Dict[str, Any]]:
        """
        提取属性映射（ModCache.lua 格式）
        
        ModCache.lua 格式:
        c["描述文本"] = {
            {[1]={type="MORE", name="Damage", value=100, ...}, ...},
            "描述文本"
        }
        """
        mappings = []
        
        # 匹配 c["..."] = { 格式
        pattern = r'c\s*\[\s*"([^"]+)"\s*\]\s*=\s*\{'
        matches = re.finditer(pattern, content)
        
        for match in matches:
            stat_name = match.group(1)
            start_pos = match.end() - 1  # { 的位置
            
            # 使用括号平衡提取完整内容
            table_content = self.extract_lua_table(content, start_pos)
            if not table_content:
                continue
            
            # 解析 mod 数据
            mod_data = self._parse_mod_cache_entry(table_content)
            
            if mod_data:
                mapping = {
                    'id': stat_name[:100],  # 限制ID长度
                    'name': stat_name,
                    'type': 'mod_definition',
                    'description': stat_name,
                    'mod_data': mod_data
                }
                mappings.append(mapping)
        
        return mappings
    
    def _parse_mod_cache_entry(self, table_content: str) -> List[Dict[str, Any]]:
        """
        解析 ModCache 条目中的 mod 数据
        
        格式: {[1]={type="MORE", name="Damage", value=100, ...}, [2]={...}}
        """
        mods = []
        
        # 匹配 {type="...", name="...", value=...} 格式
        # 使用非贪婪匹配，但需要处理嵌套
        mod_pattern = r'\{\s*(type\s*=\s*"[^"]+"[^}]+)\}'
        
        # 由于嵌套复杂，使用简化的字段提取
        # 找所有 type="..." 的位置
        type_matches = list(re.finditer(r'type\s*=\s*"([^"]+)"', table_content))
        
        for type_match in type_matches:
            # 从这个位置向前找最近的 { 开始，向后找对应的 } 结束
            start = table_content.rfind('{', 0, type_match.start())
            if start < 0:
                continue
            
            # 使用括号平衡找结束位置
            depth = 0
            end = start
            for i in range(start, len(table_content)):
                if table_content[i] == '{':
                    depth += 1
                elif table_content[i] == '}':
                    depth -= 1
                    if depth == 0:
                        end = i + 1
                        break
            
            mod_body = table_content[start:end]
            
            # 提取字段
            mod = {}
            
            # type
            m = re.search(r'type\s*=\s*"([^"]+)"', mod_body)
            if m:
                mod['type'] = m.group(1)
            
            # name
            m = re.search(r'name\s*=\s*"([^"]+)"', mod_body)
            if m:
                mod['name'] = m.group(1)
            
            # value
            m = re.search(r'value\s*=\s*(-?[\d.]+)', mod_body)
            if m:
                mod['value'] = float(m.group(1))
            
            # flags
            flags_match = re.search(r'flags\s*=\s*(\d+)', mod_body)
            if flags_match:
                mod['flags'] = int(flags_match.group(1))
            
            # keywordFlags
            kw_flags_match = re.search(r'keywordFlags\s*=\s*(\d+)', mod_body)
            if kw_flags_match:
                mod['keywordFlags'] = int(kw_flags_match.group(1))
            
            # globalLimit
            limit_match = re.search(r'globalLimit\s*=\s*(-?[\d.]+)', mod_body)
            if limit_match:
                mod['globalLimit'] = float(limit_match.group(1))
            
            # globalLimitKey
            limit_key_match = re.search(r'globalLimitKey\s*=\s*"([^"]+)"', mod_body)
            if limit_key_match:
                mod['globalLimitKey'] = limit_key_match.group(1)
            
            if mod:
                mods.append(mod)
        
        return mods
    
    def _extract_calculation_functions(self, content: str) -> List[Dict[str, Any]]:
        """
        提取计算函数
        
        Modules/Calc*.lua 格式:
        function calcs.hitChance(evasion, accuracy, uncapped)
            local rawChance = (accuracy * 1.25) / (accuracy + evasion * 0.3) * 100
            return m_max(m_min(round(rawChance), 100), 5)
        end
        """
        functions = []
        
        # 匹配 function xxx.yyy(...) ... end 格式
        pattern = r'function\s+(\w+)\.(\w+)\s*\(([^)]*)\)(.*?)end'
        matches = re.finditer(pattern, content, re.DOTALL)
        
        for match in matches:
            namespace = match.group(1)
            func_name = match.group(2)
            full_name = f"{namespace}.{func_name}"
            params = match.group(3).split(',')
            body = match.group(4)
            
            # 提取条件判断
            conditions = self._extract_conditions(body)
            
            # 提取公式相关内容
            formulas = self._extract_formulas(body)
            
            func = {
                'id': full_name,
                'name': full_name,
                'type': 'calculation_module',
                'namespace': namespace,
                'function_name': func_name,
                'parameters': [p.strip() for p in params if p.strip()],
                'conditions': conditions,
                'formulas': formulas,
                'body': body.strip()[:500]  # 保存部分代码
            }
            functions.append(func)
        
        # 也匹配简单函数 function xxx(...) ... end
        pattern2 = r'function\s+(\w+)\s*\(([^)]*)\)(.*?)end'
        matches2 = re.finditer(pattern2, content, re.DOTALL)
        
        for match in matches2:
            func_name = match.group(1)
            # 跳过已经匹配的 xxx.yyy 格式
            if '.' in func_name:
                continue
            params = match.group(2).split(',')
            body = match.group(3)
            
            # 只保留可能是计算相关的函数
            calc_keywords = ['calc', 'compute', 'get', 'sum', 'merge', 'process']
            if not any(kw in func_name.lower() for kw in calc_keywords):
                continue
            
            conditions = self._extract_conditions(body)
            formulas = self._extract_formulas(body)
            
            func = {
                'id': func_name,
                'name': func_name,
                'type': 'calculation_module',
                'parameters': [p.strip() for p in params if p.strip()],
                'conditions': conditions,
                'formulas': formulas,
                'body': body.strip()[:500]
            }
            functions.append(func)
        
        return functions
    
    def _extract_gems(self, content: str) -> List[Dict[str, Any]]:
        """
        提取宝石定义
        
        Gems.lua 格式:
        ["Metadata/Items/Gems/SkillGemIceNova"] = {
            name = "Ice Nova",
            baseTypeName = "Ice Nova",
            grantedEffectId = "IceNovaPlayer",
            tags = { intelligence = true, spell = true, ... },
            gemType = "Spell",
            reqStr = 0, reqDex = 0, reqInt = 100,
            Tier = 1,
            naturalMaxLevel = 20,
        }
        """
        gems = []
        
        # 匹配 ["Metadata/Items/Gems/..."] = {
        pattern = r'\[\s*"Metadata/Items/Gems/([^"]+)"\s*\]\s*=\s*\{'
        matches = re.finditer(pattern, content)
        
        for match in matches:
            gem_id = match.group(1)
            start_pos = match.end() - 1  # { 的位置
            
            # 使用括号平衡提取完整内容
            table_content = self.extract_lua_table(content, start_pos)
            if not table_content:
                continue
            
            # 提取字段
            gem = {
                'id': f"Metadata/Items/Gems/{gem_id}",
                'name': self._extract_field(table_content, 'name') or gem_id,
                'type': 'gem_definition',
                'game_id': f"Metadata/Items/Gems/{gem_id}",
                'variant_id': gem_id,
            }
            
            # 基础类型名称
            base_type = self._extract_field(table_content, 'baseTypeName')
            if base_type:
                gem['base_type_name'] = base_type
            
            # 关联的技能ID
            granted_effect = self._extract_field(table_content, 'grantedEffectId')
            if granted_effect:
                gem['granted_effect_id'] = granted_effect
            
            # 宝石类型
            gem_type = self._extract_field(table_content, 'gemType')
            if gem_type:
                gem['gem_type'] = gem_type
                gem['skill_types'] = [gem_type]  # 用于规则关联
            
            # 标签字符串
            tag_string = self._extract_field(table_content, 'tagString')
            if tag_string:
                gem['tag_string'] = tag_string
            
            # 从 tags = {...} 字典提取标签
            tags_dict = self._extract_tags_dict(table_content)
            if tags_dict:
                gem['tags'] = tags_dict  # 存储为字典格式
            
            # 需求属性（修改字段名）
            req_str = self._extract_number(table_content, 'reqStr')
            req_dex = self._extract_number(table_content, 'reqDex')
            req_int = self._extract_number(table_content, 'reqInt')
            gem['req_str'] = req_str or 0
            gem['req_dex'] = req_dex or 0
            gem['req_int'] = req_int or 0
            
            # Tier 和最大等级（修改字段名）
            tier = self._extract_number(table_content, 'Tier')
            if tier is not None:
                gem['tier'] = tier
            
            max_level = self._extract_number(table_content, 'naturalMaxLevel')
            if max_level is not None:
                gem['natural_max_level'] = max_level
            
            # 武器需求
            weapon_req = self._extract_field(table_content, 'weaponRequirements')
            if weapon_req:
                gem['weapon_requirements'] = weapon_req
            
            # 宝石家族
            gem_family = self._extract_field(table_content, 'gemFamily')
            if gem_family:
                gem['gem_family'] = gem_family
            
            # 额外stat集合
            additional_set1 = self._extract_field(table_content, 'additionalStatSet1')
            if additional_set1:
                gem['additional_stat_set1'] = additional_set1
            
            additional_set2 = self._extract_field(table_content, 'additionalStatSet2')
            if additional_set2:
                gem['additional_stat_set2'] = additional_set2
            
            # additionalGrantedEffectId — Support→隐藏技能链的关键数据
            additional_effects = []
            for i in range(1, 4):  # 最多3个
                effect_id = self._extract_field(table_content, f'additionalGrantedEffectId{i}')
                if effect_id:
                    additional_effects.append(effect_id)
            if additional_effects:
                gem['additional_granted_effect_ids'] = additional_effects
            
            gems.append(gem)
        
        return gems
    
    def _extract_tags_dict(self, content: str) -> Dict[str, bool]:
        """提取 tags = { key = true, ... } 格式的标签字典"""
        tags = {}
        
        # 匹配 tags = { ... }
        tags_match = re.search(r'tags\s*=\s*\{([^}]+)\}', content)
        if tags_match:
            tags_body = tags_match.group(1)
            # 匹配 key = true 格式
            for tag_match in re.finditer(r'(\w+)\s*=\s*true', tags_body):
                tags[tag_match.group(1)] = True
        
        return tags
    
    def _extract_number(self, content: str, field: str) -> Optional[int]:
        """提取数字字段"""
        match = re.search(rf'{field}\s*=\s*(-?\d+)', content)
        return int(match.group(1)) if match else None
    
    def _extract_uniques(self, content: str) -> List[Dict[str, Any]]:
        """
        提取暗金物品
        
        格式:
        [[
        Item Name
        Base Type
        Variant: Pre 0.1.1
        Variant: Current
        {variant:1}stat line 1
        {variant:2}stat line 2
        stat line 3 (所有变体)
        ]]
        
        {variant:N} 表示 stat 属于特定变体版本
        {variant:N,M} 表示 stat 属于多个变体版本
        """
        uniques = []
        
        # 匹配 [[...]] 块
        pattern = r'\[\[([^\]]*(?:\][^\]])*?)\]\]'
        matches = re.findall(pattern, content, re.DOTALL)
        
        for block in matches:
            lines = [l.strip() for l in block.strip().split('\n') if l.strip()]
            if not lines:
                continue
            
            # 第一行是装备名称
            name = lines[0]
            
            # 提取变体信息
            variants = []
            base_type = None
            stats = []
            skip_prefixes = ('Variant:', 'League:', 'Source:', 'Requires')
            
            for i, line in enumerate(lines[1:], start=1):
                # 提取变体定义
                if line.startswith('Variant:'):
                    variant_name = line[8:].strip()
                    variants.append(variant_name)
                    continue
                
                # 跳过其他元数据行
                if any(line.startswith(prefix) for prefix in skip_prefixes):
                    continue
                
                # 第二行通常是基础类型（不含特殊字符）
                if i == 1 and not any(c in line for c in '()%+{'):
                    base_type = line
                    continue
                
                # 处理 {variant:N} 前缀的 stat 行
                # 格式: {variant:1}stat 或 {variant:1,2}stat
                variant_match = re.match(r'\{variant:([\d,]+)\}(.+)', line)
                if variant_match:
                    # 提取 stat 内容（去掉 variant 前缀）
                    stat_content = variant_match.group(2).strip()
                    if stat_content:
                        stats.append(stat_content)
                    continue
                
                # 普通 stat 行
                if line:
                    stats.append(line)
            
            if name:
                unique = {
                    'id': name,
                    'name': name,
                    'type': 'unique_item',
                    'stats': stats,
                }
                if base_type:
                    unique['base_type'] = base_type
                if variants:
                    unique['variants'] = variants
                
                uniques.append(unique)
        
        return uniques
    
    def _extract_passive_nodes(self, content: str) -> List[Dict[str, Any]]:
        """
        提取天赋节点数据（包括普通天赋和升华天赋）
        
        tree.lua 格式：
        nodes={
            [skill_id]={
                ascendancyName="Blood Mage",
                name="Vitality Siphon",
                isNotable=true,
                stats={[1]="10% of Spell Damage Leeched as Life"},
                ...
            },
            ...
        }
        """
        nodes = []
        
        # 找到 nodes={ 的位置 - 需要找到独立的 nodes 表，不是嵌套的
        # 顶层 nodes 表的特征：前面只有一个 tab，后面跟着节点定义 [数字]={
        # 使用 findall 找到所有匹配，然后选择正确的一个
        pattern = r'\tnodes\s*=\s*\{'
        all_matches = list(re.finditer(pattern, content))
        
        match = None
        for m in all_matches:
            # 检查后面是否跟着节点定义
            next_chars = content[m.end():m.end()+50]
            if re.search(r'\[\s*\d+\s*\]\s*=\s*\{', next_chars):
                match = m
                break
        
        if not match:
            return nodes
        
        # 提取整个 nodes 表
        nodes_start = match.end() - 1
        nodes_table = self.extract_lua_table(content, nodes_start)
        if not nodes_table:
            return nodes
        
        # 匹配每个节点 [skill_id]={...}
        # 使用括号平衡算法提取每个节点
        pattern = r'\[\s*(\d+)\s*\]\s*=\s*\{'
        matches = list(re.finditer(pattern, nodes_table))
        
        for i, match in enumerate(matches):
            skill_id = match.group(1)
            table_start = match.end() - 1
            
            # 提取节点表
            node_table = self.extract_lua_table(nodes_table, table_start)
            if not node_table:
                continue
            
            # 提取节点属性
            name = self._extract_field(node_table, 'name')
            ascendancy = self._extract_field(node_table, 'ascendancyName')
            is_notable = 'isNotable=true' in node_table or re.search(r'isNotable\s*=\s*true', node_table) is not None
            is_keystone = 'isKeystone=true' in node_table or re.search(r'isKeystone\s*=\s*true', node_table) is not None
            
            # 提取 stats
            stats = self._extract_passive_stats(node_table)
            
            # 只保留有名字和属性的节点
            if not name or not stats:
                continue
            
            node = {
                'id': f"passive_{skill_id}",
                'skill_id': int(skill_id),
                'name': name,
                'type': 'ascendancy_node' if ascendancy else 'passive_node',
                'ascendancy_name': ascendancy,  # 修复：使用正确的字段名
                'is_notable': is_notable,
                'is_keystone': is_keystone,
                'stats_node': stats,  # 修复：使用正确的字段名
                'stat_descriptions': stats  # [v2新增] 统一描述文本字段
            }
            
            nodes.append(node)
        
        return nodes
    
    def _extract_passive_stats(self, table_content: str) -> List[str]:
        """从天赋节点表中提取 stats 数组"""
        stats = []
        
        # 找到 stats={ 的位置
        stats_match = re.search(r'stats\s*=\s*\{', table_content)
        if not stats_match:
            return stats
        
        # 提取 stats 表
        stats_start = stats_match.end() - 1
        stats_table = self.extract_lua_table(table_content, stats_start)
        if not stats_table:
            return stats
        
        # 提取 [n]="stat text" 格式
        pattern = r'\[\s*\d+\s*\]\s*=\s*"([^"]+)"'
        matches = re.findall(pattern, stats_table)
        stats.extend(matches)
        
        return stats
    
    def _extract_conditions(self, body: str) -> List[Dict[str, str]]:
        """提取条件判断"""
        conditions = []
        
        # 匹配 if ... then ... end
        pattern = r'if\s+(.+?)\s+then\s+(.+?)(?:elseif|else|end)'
        matches = re.finditer(pattern, body, re.DOTALL)
        
        for match in matches:
            condition = {
                'condition': match.group(1).strip(),
                'action': match.group(2).strip()
            }
            conditions.append(condition)
        
        return conditions
    
    def _extract_formulas(self, body: str) -> List[Dict[str, str]]:
        """提取公式"""
        formulas = []
        
        # 查找包含计算关键字的行
        calc_keywords = ['return', '=', '*=', '+=', '-=', 'calcSum', 'calcProduct']
        
        for line in body.split('\n'):
            line = line.strip()
            if any(kw in line for kw in calc_keywords) and len(line) > 10:
                formula = {
                    'expression': line
                }
                formulas.append(formula)
        
        return formulas
    
    def _extract_field(self, text: str, field_name: str) -> Optional[str]:
        """提取字段值"""
        pattern = rf'{field_name}\s*=\s*"([^"]+)"'
        match = re.search(pattern, text)
        return match.group(1) if match else None
    
    def _extract_array(self, text: str, field_name: str) -> List[str]:
        """提取数组字段"""
        result = []
        
        # 匹配 field = { ... }
        pattern = rf'{field_name}\s*=\s*\{{([^}}]+)\}}'
        match = re.search(pattern, text)
        
        if match:
            array_content = match.group(1)
            # 提取字符串值
            values = re.findall(r'"([^"]+)"', array_content)
            # 也提取 [Type.XXX] = true 格式
            type_values = re.findall(r'\[SkillType\.(\w+)\]', array_content)
            result = values + type_values
        
        return result
    
    def _extract_stats_array(self, text: str, field_name: str) -> List[List]:
        """提取stats数组（可能是嵌套数组）"""
        result = []
        
        # 匹配 field = { { ... }, { ... } }
        pattern = rf'{field_name}\s*=\s*\{{([^}}]+(?:\{{[^}}]*\}}[^}}]*)*)\}}'
        match = re.search(pattern, text)
        
        if match:
            array_content = match.group(1)
            # 匹配嵌套数组 { "name", value }
            nested_pattern = r'\{\s*"([^"]+)"\s*,\s*(\d+\.?\d*)\s*\}'
            nested_matches = re.findall(nested_pattern, array_content)
            
            for name, value in nested_matches:
                result.append([name, float(value) if '.' in value else int(value)])
        
        return result
    
    def _extract_reservation(self, text: str) -> Optional[Dict[str, int]]:
        """提取预留信息"""
        reservation = {}
        
        # 查找 spirit_reservation_flat
        spirit_match = re.search(r'spirit_reservation_flat\s*=\s*(\d+)', text)
        if spirit_match:
            reservation['spirit'] = int(spirit_match.group(1))
        
        # 查找 mana_reservation_flat
        mana_match = re.search(r'mana_reservation_flat\s*=\s*(\d+)', text)
        if mana_match:
            reservation['mana'] = int(mana_match.group(1))
        
        return reservation if reservation else None
    
    def _extract_cast_time(self, table_content: str) -> Optional[float]:
        """提取施法时间"""
        match = re.search(r'castTime\s*=\s*([\d.]+)', table_content)
        return float(match.group(1)) if match else None
    
    def _extract_quality_stats(self, table_content: str) -> List[List[Any]]:
        """提取品质加成"""
        result = []
        
        # 查找 qualityStats = { ... }
        quality_match = re.search(r'qualityStats\s*=\s*\{', table_content)
        if not quality_match:
            return result
        
        # 提取qualityStats表
        quality_start = quality_match.end() - 1
        quality_table = self.extract_lua_table(table_content, quality_start)
        if not quality_table:
            return result
        
        # 匹配 { "stat_name", value } 格式
        pattern = r'\{\s*"([^"]+)"\s*,\s*([\d.]+)\s*\}'
        matches = re.findall(pattern, quality_table)
        
        for name, value in matches:
            result.append([name, float(value) if '.' in value else int(value)])
        
        return result
    
    def _extract_levels(self, table_content: str) -> Dict[str, Any]:
        """提取技能等级数据（完整）"""
        levels = {}
        
        # 查找 levels = { ... }
        levels_match = re.search(r'levels\s*=\s*\{', table_content)
        if not levels_match:
            return levels
        
        # 提取levels表
        levels_start = levels_match.end() - 1
        levels_table = self.extract_lua_table(table_content, levels_start)
        if not levels_table:
            return levels
        
        # 匹配每个等级 [n] = { ... }
        level_pattern = r'\[\s*(\d+)\s*\]\s*=\s*\{([^}]+)\}'
        level_matches = re.finditer(level_pattern, levels_table)
        
        for level_match in level_matches:
            level_num = level_match.group(1)
            level_content = level_match.group(2)
            
            level_data = {}
            
            # 提取 levelRequirement
            req_match = re.search(r'levelRequirement\s*=\s*(\d+)', level_content)
            if req_match:
                level_data['levelRequirement'] = int(req_match.group(1))
            
            # 提取 cost = { Mana = X, Spirit = Y }
            cost = {}
            mana_match = re.search(r'cost\s*=\s*\{\s*Mana\s*=\s*(\d+)', level_content)
            if mana_match:
                cost['Mana'] = int(mana_match.group(1))
            
            spirit_match = re.search(r'spiritReservationFlat\s*=\s*(\d+)', level_content)
            if spirit_match:
                cost['Spirit'] = int(spirit_match.group(1))
            
            if cost:
                level_data['cost'] = cost
            
            # 提取 cooldown
            cooldown_match = re.search(r'cooldown\s*=\s*([\d.]+)', level_content)
            if cooldown_match:
                level_data['cooldown'] = float(cooldown_match.group(1))
            
            # 提取 critChance
            crit_match = re.search(r'critChance\s*=\s*(\d+)', level_content)
            if crit_match:
                level_data['critChance'] = int(crit_match.group(1))
            
            # 提取 damageEffectiveness
            dmg_eff_match = re.search(r'damageEffectiveness\s*=\s*([\d.]+)', level_content)
            if dmg_eff_match:
                level_data['damageEffectiveness'] = float(dmg_eff_match.group(1))
            
            # 提取 spiritReservationFlat
            spirit_match = re.search(r'spiritReservationFlat\s*=\s*(\d+)', level_content)
            if spirit_match:
                level_data['spiritReservationFlat'] = int(spirit_match.group(1))
            
            if level_data:
                levels[level_num] = level_data
        
        return levels
    
    def _extract_support_flag(self, table_content: str) -> bool:
        """提取是否辅助宝石标志"""
        match = re.search(r'support\s*=\s*true', table_content)
        return bool(match)
    
    def _extract_require_skill_types(self, table_content: str) -> List[str]:
        """提取需求技能类型"""
        types = []
        
        # 查找 requireSkillTypes = { ... }
        match = re.search(r'requireSkillTypes\s*=\s*\{([^}]+)\}', table_content)
        if match:
            content = match.group(1)
            # 匹配 SkillType.XXX 或 "XXX"
            type_pattern = r'SkillType\.(\w+)|"(\w+)"'
            type_matches = re.findall(type_pattern, content)
            
            for type_tuple in type_matches:
                # type_tuple可能是 (xxx, '') 或 ('', xxx)
                type_name = type_tuple[0] if type_tuple[0] else type_tuple[1]
                if type_name:
                    types.append(type_name)
        
        return types
    
    def _extract_add_skill_types(self, table_content: str) -> List[str]:
        """提取添加技能类型"""
        types = []
        
        match = re.search(r'addSkillTypes\s*=\s*\{([^}]+)\}', table_content)
        if match:
            content = match.group(1)
            type_pattern = r'SkillType\.(\w+)|"(\w+)"'
            type_matches = re.findall(type_pattern, content)
            
            for type_tuple in type_matches:
                type_name = type_tuple[0] if type_tuple[0] else type_tuple[1]
                if type_name:
                    types.append(type_name)
        
        return types
    
    def _extract_exclude_skill_types(self, table_content: str) -> List[str]:
        """提取排除技能类型"""
        types = []
        
        match = re.search(r'excludeSkillTypes\s*=\s*\{([^}]+)\}', table_content)
        if match:
            content = match.group(1)
            type_pattern = r'SkillType\.(\w+)|"(\w+)"'
            type_matches = re.findall(type_pattern, content)
            
            for type_tuple in type_matches:
                type_name = type_tuple[0] if type_tuple[0] else type_tuple[1]
                if type_name:
                    types.append(type_name)
        
        return types
    
    def _extract_is_trigger(self, table_content: str) -> bool:
        """提取是否触发器标志"""
        match = re.search(r'isTrigger\s*=\s*true', table_content)
        return bool(match)
    
    def _extract_hidden(self, table_content: str) -> bool:
        """提取是否隐藏标志"""
        match = re.search(r'hidden\s*=\s*true', table_content)
        return bool(match)
    
    def _extract_item_bases(self, content: str) -> List[Dict[str, Any]]:
        """
        提取装备基础数据
        
        格式:
        itemBases["Crimson Amulet"] = {
            type = "Amulet",
            tags = { "amulet" },
            armour = 0,
            evasion = 0,
            energyShield = 0,
            ...
        }
        """
        bases = []
        
        # 匹配 itemBases["name"] = { ... }
        pattern = r'itemBases\s*\[\s*"([^"]+)"\s*\]\s*=\s*\{'
        matches = list(re.finditer(pattern, content))
        
        for match in matches:
            name = match.group(1)
            table_start = match.end() - 1
            
            # 提取表内容
            table_content = self.extract_lua_table(content, table_start)
            if not table_content:
                continue
            
            # 提取属性
            item_type = self._extract_field(table_content, 'type')
            tags = self._extract_array(table_content, 'tags')
            
            # 提取基础属性
            base = {
                'id': name,
                'name': name,
                'type': 'item_base',
                'item_type': item_type,
                'tags': tags,
            }
            
            # 提取防御属性
            armour_match = re.search(r'armour\s*=\s*(\d+)', table_content)
            if armour_match:
                base['armour'] = int(armour_match.group(1))
            
            evasion_match = re.search(r'evasion\s*=\s*(\d+)', table_content)
            if evasion_match:
                base['evasion'] = int(evasion_match.group(1))
            
            es_match = re.search(r'energyShield\s*=\s*(\d+)', table_content)
            if es_match:
                base['energy_shield'] = int(es_match.group(1))
            
            # 提取武器属性
            damage_match = re.search(r'weaponDamage\s*=\s*\{\s*(\d+)\s*,\s*(\d+)\s*\}', table_content)
            if damage_match:
                base['weapon_damage_min'] = int(damage_match.group(1))
                base['weapon_damage_max'] = int(damage_match.group(2))
            
            # 提取要求
            req_str_match = re.search(r'reqStr\s*=\s*(\d+)', table_content)
            if req_str_match:
                base['req_str'] = int(req_str_match.group(1))
            
            req_dex_match = re.search(r'reqDex\s*=\s*(\d+)', table_content)
            if req_dex_match:
                base['req_dex'] = int(req_dex_match.group(1))
            
            req_int_match = re.search(r'reqInt\s*=\s*(\d+)', table_content)
            if req_int_match:
                base['req_int'] = int(req_int_match.group(1))
            
            bases.append(base)
        
        return bases
    
    def _extract_minions(self, content: str) -> List[Dict[str, Any]]:
        """
        提取召唤物/幽灵数据
        
        Minions.lua 格式:
        minions["RaisedZombie"] = {
            name = "Raised Zombie",
            monsterTags = { "animal_claw_weapon", "melee", ... },
            life = 0.7,
            damage = 0.75,
            fireResist = 0,
            coldResist = 0,
            lightningResist = 0,
            chaosResist = 0,
            attackTime = 1.25,
            attackRange = 9,
            accuracy = 1,
            weaponType1 = "One Handed Axe",
            limit = "ActiveZombieLimit",
            baseMovementSpeed = 16,
            spectreReservation = 50,
            companionReservation = 30,
            monsterCategory = "Undead",
            skillList = { "MinionMeleeStep", },
            modList = { ... },
        }
        """
        minions = []
        
        # 匹配 minions["id"] = { ... }
        pattern = r'minions\s*\[\s*"([^"]+)"\s*\]\s*=\s*\{'
        matches = list(re.finditer(pattern, content))
        
        for match in matches:
            minion_id = match.group(1)
            table_start = match.end() - 1
            
            # 提取表内容
            table_content = self.extract_lua_table(content, table_start)
            if not table_content:
                continue
            
            # 提取属性
            name = self._extract_field(table_content, 'name')
            if not name:
                # 尝试从 ID 提取名称
                name = minion_id.split('/')[-1].replace('_', ' ')
            
            minion = {
                'id': minion_id,
                'name': name,
                'type': 'minion_definition',
            }
            
            # 提取基础属性（可能是浮点数）
            life = self._extract_float(table_content, 'life')
            if life is not None:
                minion['life'] = life
            
            damage = self._extract_float(table_content, 'damage')
            if damage is not None:
                minion['damage'] = damage
            
            armour = self._extract_float(table_content, 'armour')
            if armour is not None:
                minion['armour'] = armour
            
            # 攻击属性
            attack_time = self._extract_float(table_content, 'attackTime')
            if attack_time is not None:
                minion['attack_time'] = attack_time
            
            attack_range = self._extract_float(table_content, 'attackRange')
            if attack_range is not None:
                minion['attack_range'] = attack_range
            
            accuracy = self._extract_float(table_content, 'accuracy')
            if accuracy is not None:
                minion['accuracy'] = accuracy
            
            # 抗性
            stats = {}
            for resist in ['fireResist', 'coldResist', 'lightningResist', 'chaosResist']:
                val = self._extract_number(table_content, resist)
                if val is not None:
                    stats[resist] = val
            
            # 伤害扩展
            damage_spread = self._extract_float(table_content, 'damageSpread')
            if damage_spread is not None:
                stats['damageSpread'] = damage_spread
            
            if stats:
                minion['stats'] = stats
            
            # 移动速度
            move_speed = self._extract_float(table_content, 'baseMovementSpeed')
            if move_speed is not None:
                minion['movement_speed'] = move_speed
            
            # 预留资源
            spectre_res = self._extract_number(table_content, 'spectreReservation')
            companion_res = self._extract_number(table_content, 'companionReservation')
            if spectre_res is not None or companion_res is not None:
                minion['reservation'] = {
                    'spectre': spectre_res,
                    'companion': companion_res
                }
            
            # 类型信息
            monster_category = self._extract_field(table_content, 'monsterCategory')
            if monster_category:
                minion['monster_category'] = monster_category
            
            # 提取技能列表
            skill_list = self._extract_array(table_content, 'skillList')
            if skill_list:
                minion['skill_list'] = skill_list
                minion['skills'] = skill_list  # 用于规则关联
            
            # 提取怪物标签
            monster_tags = self._extract_array(table_content, 'monsterTags')
            if monster_tags:
                minion['monster_tags'] = monster_tags
            
            # 武器类型
            weapon_type = self._extract_field(table_content, 'weaponType1')
            if weapon_type:
                minion['weapon_type'] = weapon_type
            
            # 限制
            limit = self._extract_field(table_content, 'limit')
            if limit:
                minion['limit'] = limit
            
            minions.append(minion)
        
        return minions
    
    def _extract_float(self, content: str, field: str) -> Optional[float]:
        """提取浮点数字段"""
        match = re.search(rf'{field}\s*=\s*(-?[\d.]+)', content)
        return float(match.group(1)) if match else None
    
    def _extract_mod_affix(self, content: str) -> List[Dict[str, Any]]:
        """
        提取词缀定义数据
        
        格式:
        ["AffixID"] = {
            type = "Prefix"/"Suffix"/"Corrupted",
            affix = "of the Brute",
            "+(5-8) to Strength",
            statOrder = { 947 },
            level = 1,
            group = "Strength",
            weightKey = { ... },
            weightVal = { ... },
            modTags = { "attribute" },
            tradeHash = 4080418644,
        }
        
        来源文件: ModItem.lua, ModJewel.lua, ModCorrupted.lua, ModItemExclusive.lua
        """
        affixes = []
        
        # 匹配 ["AffixID"] = { 格式
        pattern = r'\[\s*"([A-Z][a-zA-Z0-9_]*)"\s*\]\s*=\s*\{'
        matches = list(re.finditer(pattern, content))
        
        for match in matches:
            affix_id = match.group(1)
            table_start = match.end() - 1
            
            # 提取表内容
            table_content = self.extract_lua_table(content, table_start)
            if not table_content:
                continue
            
            # 检查是否有 type = "Prefix"/"Suffix"/"Corrupted"
            type_match = re.search(r'type\s*=\s*"([^"]+)"', table_content)
            if not type_match:
                continue
            
            affix_type = type_match.group(1)
            
            # 提取 affix 名称
            affix_name = self._extract_field(table_content, 'affix') or ''
            
            # 提取描述文本（通常是表中的字符串字段）
            # 格式: "+(5-8) to Strength" 或 "(5-15)% increased Damage"
            desc_patterns = [
                r'"([^"]*\d[^"]*)"',  # 包含数字的字符串
            ]
            descriptions = []
            for dp in desc_patterns:
                desc_matches = re.findall(dp, table_content)
                for d in desc_matches:
                    # 过滤掉非描述性文本
                    if any(c in d for c in ['%', '+', '-', 'to', 'with', 'when', 'on']):
                        if len(d) > 5 and len(d) < 200:
                            descriptions.append(d)
            
            # 提取 statOrder
            stat_order = []
            stat_order_match = re.search(r'statOrder\s*=\s*\{([^}]+)\}', table_content)
            if stat_order_match:
                stat_order = [int(x.strip()) for x in stat_order_match.group(1).split(',') if x.strip().isdigit()]
            
            # 提取 level
            level_match = re.search(r'level\s*=\s*(\d+)', table_content)
            level = int(level_match.group(1)) if level_match else 1
            
            # 提取 group
            group = self._extract_field(table_content, 'group') or ''
            
            # 提取 modTags
            mod_tags = []
            tags_match = re.search(r'modTags\s*=\s*\{([^}]+)\}', table_content)
            if tags_match:
                mod_tags = [t.strip().strip('"') for t in tags_match.group(1).split(',') if t.strip()]
            
            # 提取 weightKey（哪些装备类型可以出现这个词缀）
            weight_keys = []
            weight_match = re.search(r'weightKey\s*=\s*\{([^}]+)\}', table_content)
            if weight_match:
                weight_keys = [w.strip().strip('"') for w in weight_match.group(1).split(',') if w.strip()]
            
            # 提取 tradeHash
            trade_hash = None
            trade_match = re.search(r'tradeHash\s*=\s*(\d+)', table_content)
            if trade_match:
                trade_hash = int(trade_match.group(1))
            
            affix = {
                'id': affix_id,
                'name': affix_name,
                'type': 'mod_affix',
                'affix_type': affix_type,  # Prefix/Suffix/Corrupted
                'descriptions': descriptions[:3] if descriptions else [],  # 最多保留3个
                'stat_descriptions': descriptions[:3] if descriptions else [],  # [v2新增] 统一描述文本字段
                'stat_order': stat_order,
                'level': level,
                'group': group,
                'mod_tags': mod_tags,
                'weight_keys': weight_keys,
                'trade_hash': trade_hash,
            }
            
            affixes.append(affix)
        
        return affixes
    
    def _extract_version(self) -> Optional[str]:
        """提取版本信息"""
        # GameVersions.lua 在 POB 根目录下（固定位置）
        version_file = self.pob_path / 'GameVersions.lua'
        if not version_file.exists():
            return None
        
        try:
            with open(version_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 尝试匹配版本号
            patterns = self.config.get('version_patterns', {}).get('game_version', {}).get('patterns', [])
            for pattern in patterns:
                match = re.search(pattern, content)
                if match:
                    return match.group(1)
        except Exception:
            pass
        
        return None
    
    def get_scan_summary(self) -> Dict[str, Any]:
        """获取扫描摘要"""
        type_counts = {}
        for result in self.results:
            type_name = result.data_type.value
            type_counts[type_name] = type_counts.get(type_name, 0) + 1
        
        return {
            'pob_path': str(self.pob_path),
            'version': self.cache.version,
            'files_scanned': self.cache.files_scanned,
            'entities_found': self.cache.entities_found,
            'data_types': type_counts
        }


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='POE数据扫描器')
    parser.add_argument('pob_path', help='POB数据目录路径')
    parser.add_argument('--config', help='配置文件路径')
    parser.add_argument('--output', '-o', help='输出文件路径')
    parser.add_argument('--summary', action='store_true', help='只输出摘要')
    
    args = parser.parse_args()
    
    # 创建扫描器
    scanner = POBDataScanner(args.pob_path, args.config)
    
    # 执行扫描
    print(f"扫描POB数据目录: {args.pob_path}")
    results = scanner.scan_all_files()
    
    # 输出结果
    if args.summary:
        summary = scanner.get_scan_summary()
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    else:
        output = {
            'summary': scanner.get_scan_summary(),
            'results': [asdict(r) for r in results]
        }
        
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(output, f, indent=2, ensure_ascii=False)
            print(f"结果已保存到: {args.output}")
        else:
            print(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
