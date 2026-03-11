#!/usr/bin/env python3
"""
Lua 解析器适配器
使用 lupa 解析标准 Lua 表，替代正则解析

优势：
- 正确处理嵌套结构
- 自动处理字符串边界
- 更健壮的语法解析
"""

import re
from typing import Dict, List, Any, Optional
from pathlib import Path

try:
    import lupa
    from lupa import LuaRuntime
    HAS_LUPA = True
except ImportError:
    HAS_LUPA = False


class LuaParser:
    """Lua 解析器适配器"""
    
    def __init__(self):
        if not HAS_LUPA:
            raise ImportError("lupa not installed. Run: pip install lupa")
        self.lua = LuaRuntime()
    
    # ========== 文件类型判断 ==========
    
    def should_use_lua_parser(self, file_type: str) -> bool:
        """判断是否应该使用 Lua 解析器"""
        # 使用 Lua 解析器的类型
        lua_types = {
            'skill_definition',
            'gem_definition', 
            'passive_node',
            'stat_mapping'
        }
        # 装备使用正则（非标准 Lua 格式）
        return file_type in lua_types
    
    # ========== 技能定义解析 ==========
    
    def parse_skills_file(self, content: str) -> List[Dict[str, Any]]:
        """
        解析技能定义文件
        
        格式:
        skills["SkillID"] = {
            name = "...",
            skillTypes = {...},
            levels = {...},
        }
        """
        skills = []
        
        # 预处理：注入必要的全局变量
        preprocessed = self._preprocess_skill_file(content)
        
        try:
            result = self.lua.execute(preprocessed)
            
            for skill_id, skill_data in result.items():
                # 跳过非技能数据
                if not skill_data or 'name' not in skill_data:
                    continue
                
                skill = {
                    'id': skill_id,
                    'name': str(skill_data['name']) if 'name' in skill_data else skill_id,
                    'type': 'skill_definition',
                    'description': str(skill_data['description']) if 'description' in skill_data else '',
                    'skill_types': self._extract_skill_types(skill_data),
                    'stats': self._extract_skill_stats(skill_data),
                    'base_stats': self._extract_base_stats(skill_data),
                    'quality_stats': self._extract_quality_stats(skill_data),
                    'levels': self._extract_levels(skill_data),
                }
                skills.append(skill)
                
        except Exception as e:
            print(f"  [WARN] Lua 解析失败: {e}")
            import traceback
            traceback.print_exc()
        
        return skills
    
    def _preprocess_skill_file(self, content: str) -> str:
        """预处理技能文件"""
        # 注入必要的全局变量
        # 使用 setmetatable 让枚举表能接受任何索引，并支持调用
        setup = '''
-- Inject necessary globals
SkillType = setmetatable({}, {__index = function(t, k) return k end})
KeywordFlag = setmetatable({}, {__index = function(t, k) return k end})
ModFlag = setmetatable({}, {__index = function(t, k) return k end})
mod = function() end
flag = setmetatable({}, {__call = function() end})
skill = setmetatable({}, {__call = function() end})

'''
        # 确保返回 skills 表
        if 'return skills' not in content:
            content = content + '\nreturn skills'
        
        # 替换参数接收方式
        content = content.replace('local skills, mod, flag, skill = ...', 
                                  'local skills = {}')
        
        return setup + content
    
    # ========== ModCache 解析 ==========
    
    def parse_modcache(self, content: str) -> Dict[str, Dict]:
        """
        解析 ModCache.lua
        
        格式:
        c["description"]={
            [1] = {
                [1] = {name="Stat1", value=15, type="BASE"},
                [2] = {name="Stat2", value=15, type="BASE"},
            },
            [2] = "suffix string"
        }
        """
        mappings = {}
        
        # 预处理
        preprocessed = self._preprocess_modcache(content)
        
        try:
            result = self.lua.execute(preprocessed)
            
            # lupa 的 Lua 表需要用 .items() 遍历
            for desc, data in result.items():
                stats = []
                
                if data:
                    # 遍历 data
                    for idx, item in data.items():
                        # item 可能是:
                        # 1. 嵌套表 (包含多个 stat 定义)
                        # 2. 字符串 (后缀描述)
                        
                        if item and not isinstance(item, str):
                            # 检查是否是嵌套的 stat 表
                            # 遍历 item 获取每个 stat
                            for sub_idx, stat_data in item.items():
                                if stat_data and 'name' in stat_data:
                                    stat = {
                                        'name': str(stat_data['name']),
                                        'type': str(stat_data['type']) if 'type' in stat_data else '',
                                        'value': str(stat_data['value']) if 'value' in stat_data else '',
                                    }
                                    # 提取额外字段
                                    if 'keywordFlags' in stat_data:
                                        stat['keywordFlags'] = int(stat_data['keywordFlags'])
                                    if 'flags' in stat_data:
                                        stat['flags'] = int(stat_data['flags'])
                                    stats.append(stat)
                
                if stats:
                    mappings[desc] = {
                        'description': desc,
                        'stats': stats
                    }
                            
        except Exception as e:
            print(f"  [WARN] ModCache Lua parse failed: {e}")
            import traceback
            traceback.print_exc()
        
        return mappings
    
    def _preprocess_modcache(self, content: str) -> str:
        """预处理 ModCache.lua"""
        # 替换参数接收（注意：第一行可能是 local c=...c["..."] 连在一起的）
        content = content.replace('local c=...', 'local c={}\n')
        # 添加 return
        if 'return c' not in content:
            content = content + '\nreturn c'
        return content
    
    # ========== 天赋节点解析 ==========
    
    def parse_passive_tree(self, content: str) -> List[Dict[str, Any]]:
        """
        解析天赋树文件
        
        格式:
        return {
            nodes={
                [id]={
                    name="...",
                    ascendancyName="...",
                    stats={[1]="...", ...},
                },
            },
        }
        """
        nodes = []
        
        try:
            result = self.lua.execute(content)
            
            # result 是整个返回对象，需要提取 nodes 表
            if 'nodes' in result:
                tree_nodes = result['nodes']
            else:
                tree_nodes = result
            
            for node_id, node_data in tree_nodes.items():
                # 跳过非数字 ID（可能是元数据）
                try:
                    int(node_id)
                except (ValueError, TypeError):
                    continue
                
                # 检查是否有 name 字段
                if 'name' not in node_data:
                    continue
                
                node = {
                    'id': f"passive_{node_id}",
                    'skill_id': int(node_id),
                    'name': str(node_data['name']),
                    'type': 'ascendancy_node' if 'ascendancyName' in node_data and node_data['ascendancyName'] else 'passive_node',
                    'ascendancy': str(node_data['ascendancyName']) if 'ascendancyName' in node_data else '',
                    'is_notable': 'isNotable' in node_data and node_data['isNotable'],
                    'is_keystone': 'isKeystone' in node_data and node_data['isKeystone'],
                    'stats': self._extract_node_stats(node_data),
                }
                
                if node['name']:
                    nodes.append(node)
                    
        except Exception as e:
            print(f"  [WARN] Passive tree Lua parse failed: {e}")
            import traceback
            traceback.print_exc()
        
        return nodes
    
    # ========== 辅助方法 ==========
    
    def _extract_skill_types(self, skill_data) -> List[str]:
        """提取技能类型"""
        types = []
        try:
            if 'skillTypes' not in skill_data:
                return types
            st = skill_data['skillTypes']
            if st:
                for type_key, value in st.items():
                    # skillTypes 格式: {[SkillType.Buff] = true, ...}
                    # 我们只取 key
                    type_str = str(type_key)
                    # 过滤掉 SkillType. 前缀
                    if type_str.startswith('SkillType.'):
                        type_str = type_str[10:]
                    types.append(type_str)
        except (KeyError, TypeError, AttributeError) as e:
            # Lua 表结构异常，返回已解析的内容
            pass
        return types
    
    def _extract_skill_stats(self, skill_data) -> List[str]:
        """提取技能属性"""
        stats = []
        try:
            if 'stats' not in skill_data:
                return stats
            s = skill_data['stats']
            if s:
                for idx, stat_text in s.items():
                    if stat_text and isinstance(stat_text, str):
                        stats.append(stat_text)
        except (KeyError, TypeError, AttributeError):
            pass
        return stats
    
    def _extract_base_stats(self, skill_data) -> List[str]:
        """提取基础属性"""
        stats = []
        try:
            if 'baseStats' not in skill_data:
                return stats
            s = skill_data['baseStats']
            if s:
                for idx, stat_text in s.items():
                    if stat_text and isinstance(stat_text, str):
                        stats.append(stat_text)
        except (KeyError, TypeError, AttributeError):
            pass
        return stats
    
    def _extract_quality_stats(self, skill_data) -> List[tuple]:
        """提取品质属性"""
        stats = []
        try:
            if 'qualityStats' not in skill_data:
                return stats
            qs = skill_data['qualityStats']
            if qs:
                for idx, pair in qs.items():
                    if '1' in pair and '2' in pair:
                        stats.append((str(pair['1']), str(pair['2'])))
        except (KeyError, TypeError, AttributeError):
            pass
        return stats
    
    def _extract_levels(self, skill_data) -> List[Dict]:
        """提取等级数据"""
        levels = []
        try:
            if 'levels' not in skill_data:
                return levels
            lvls = skill_data['levels']
            if lvls:
                for lvl_num, lvl_data in lvls.items():
                    level = {
                        'level': int(lvl_num),
                        'requirement': int(lvl_data['levelRequirement']) if 'levelRequirement' in lvl_data else 0,
                        'cost': self._extract_cost(lvl_data),
                    }
                    levels.append(level)
        except (KeyError, TypeError, AttributeError, ValueError):
            pass
        return levels
    
    def _extract_cost(self, lvl_data) -> Dict[str, int]:
        """提取消耗"""
        cost = {}
        try:
            if 'cost' not in lvl_data:
                return cost
            c = lvl_data['cost']
            if c:
                for key, value in c.items():
                    cost[str(key)] = int(value)
        except (KeyError, TypeError, AttributeError, ValueError):
            pass
        return cost
    
    def _extract_node_stats(self, node_data) -> List[str]:
        """提取天赋节点属性"""
        stats = []
        try:
            if 'stats' not in node_data:
                return stats
            s = node_data['stats']
            if s:
                for idx, stat_text in s.items():
                    if stat_text and isinstance(stat_text, str):
                        stats.append(stat_text)
        except (KeyError, TypeError, AttributeError):
            pass
        return stats
