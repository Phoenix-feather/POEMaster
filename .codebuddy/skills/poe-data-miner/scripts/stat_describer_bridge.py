#!/usr/bin/env python3
"""
StatDescriber 适配层 — 通过 lupa 运行 POB 原生 StatDescriber.lua

功能:
    - 100%精确复现POB的stat描述逻辑（数值变换、限制匹配、继承链等）
    - 注入最小必要的适配函数: LoadModule, copyTable, round, floor, ConPrintf
    - 批量处理优化: 预加载公共scope，避免重复加载3.9MB的stat_descriptions.lua
    - 优雅降级: lupa不可用时返回None + 警告日志

依赖:
    - lupa (pip install lupa) — Lua/Python双向桥接
    - POBData/ 目录下的 Modules/StatDescriber.lua 和 Data/StatDescriptions/

用法:
    bridge = StatDescriberBridge('/path/to/POBData')
    lines, line_map = bridge.describe_stats(
        stats={'arc_damage_+%_final_for_each_remaining_chain': 15},
        scope_name='skill_stat_descriptions'
    )
    # lines: ['15% more Damage for each remaining Chain']
    # line_map: {'15% more Damage for each remaining Chain': 'arc_damage_+%_final_for_each_remaining_chain'}
"""

import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Union

logger = logging.getLogger(__name__)

# 尝试导入 lupa
try:
    from lupa import LuaRuntime
    LUPA_AVAILABLE = True
except ImportError:
    LUPA_AVAILABLE = False
    logger.warning("lupa 未安装, StatDescriber 桥接不可用. 安装: pip install lupa")


class StatDescriberBridge:
    """
    POB StatDescriber.lua 的 Python 桥接
    
    通过 lupa LuaRuntime 直接运行 POB 原生 Lua 代码，
    实现 100% 精确的 stat 描述生成。
    """
    
    # 预加载的公共 scope 名称（避免重复加载大文件）
    PRELOAD_SCOPES = [
        'stat_descriptions',
        'gem_stat_descriptions',
        'active_skill_gem_stat_descriptions',
        'skill_stat_descriptions',
        'passive_skill_stat_descriptions',
    ]
    
    def __init__(self, pob_path: Union[str, Path]):
        """
        初始化 StatDescriber 桥接
        
        Args:
            pob_path: POBData 目录路径
        
        Raises:
            RuntimeError: lupa 不可用或 StatDescriber.lua 加载失败
        """
        self.pob_path = Path(pob_path)
        self.lua: Optional[Any] = None
        self._describer_func = None
        self._initialized = False
        self._init_error: Optional[str] = None
        
        # 验证 POB 路径
        self._validate_paths()
        
        # 初始化 Lua 运行时
        if LUPA_AVAILABLE:
            try:
                self._init_lua_runtime()
                self._initialized = True
            except Exception as e:
                self._init_error = str(e)
                logger.error(f"StatDescriber 初始化失败: {e}")
        else:
            self._init_error = "lupa 未安装"
    
    def _validate_paths(self):
        """验证所需文件是否存在"""
        required_files = [
            'Modules/StatDescriber.lua',
            'Modules/Common.lua',
            'Data/StatDescriptions/stat_descriptions.lua',
        ]
        
        missing = []
        for f in required_files:
            if not (self.pob_path / f).exists():
                missing.append(f)
        
        if missing:
            logger.warning(f"缺少文件: {missing}")
    
    def _init_lua_runtime(self):
        """
        初始化 lupa LuaRuntime 并注入适配层
        
        注入内容:
        1. LoadModule(path) — 从文件系统加载并执行 .lua 文件
        2. copyTable(tbl, noRecurse) — 从 Common.lua 复制
        3. round(val, dec) — 从 Common.lua 复制
        4. floor(val, dec) — 从 Common.lua 复制
        5. ConPrintf(fmt, ...) — 空函数（仅用于警告输出）
        6. ItemClasses — 空表（mod_value_to_item_class 极少用到）
        7. io.open — 需要设置正确的工作目录
        """
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        
        # 保存 POB 路径到 Lua 全局变量（供 LoadModule 使用）
        pob_path_str = str(self.pob_path).replace('\\', '/')
        self.lua.execute(f'_POB_ROOT = "{pob_path_str}"')
        
        # 注入 ConPrintf (空函数，仅抑制警告)
        self.lua.execute('function ConPrintf(...) end')
        
        # 注入 ItemClasses (空表 + metatable 防止 nil 索引错误)
        self.lua.execute('''
            ItemClasses = setmetatable({}, {
                __index = function(t, k)
                    return { Name = "Unknown" }
                end
            })
        ''')
        
        # 注入 copyTable — 直接复制 Common.lua 的实现
        self.lua.execute('''
            function copyTable(tbl, noRecurse)
                local out = {}
                for k, v in pairs(tbl) do
                    if not noRecurse and type(v) == "table" then
                        out[k] = copyTable(v)
                    else
                        out[k] = v
                    end
                end
                return out
            end
        ''')
        
        # 注入 round — 直接复制 Common.lua 的实现
        self.lua.execute('''
            local m_floor = math.floor
            function round(val, dec)
                if dec then
                    return m_floor(val * 10 ^ dec + 0.5) / 10 ^ dec
                else
                    return m_floor(val + 0.5)
                end
            end
        ''')
        
        # 注入 floor — 直接复制 Common.lua 的实现（含浮点误差补偿）
        self.lua.execute('''
            function floor(val, dec)
                if dec then
                    local mult = 10 ^ dec
                    return math.floor(val * mult + 0.0001) / mult
                else
                    return math.floor(val)
                end
            end
        ''')
        
        # 注入 LoadModule — 核心适配函数
        # POB 的 LoadModule 等同于 dofile + 返回值，加载 .lua 文件并返回其 return 值
        self.lua.execute('''
            local _module_cache = {}
            
            function LoadModule(path)
                -- 检查缓存
                if _module_cache[path] then
                    return _module_cache[path]
                end
                
                -- 构建完整文件路径
                local full_path = _POB_ROOT .. "/" .. path .. ".lua"
                
                -- 加载并执行文件
                local func, err = loadfile(full_path)
                if not func then
                    -- 尝试不加 .lua 后缀（某些路径可能已包含）
                    func, err = loadfile(_POB_ROOT .. "/" .. path)
                    if not func then
                        error("LoadModule failed: " .. tostring(err))
                    end
                end
                
                local result = func()
                _module_cache[path] = result
                return result
            end
        ''')
        
        # 修补 io.open 以使用 POB 根目录作为基准
        # StatDescriber.lua 中 io.open 用于探测 Specific_Skill_Stat_Descriptions/ 文件是否存在
        self.lua.execute('''
            local _original_io_open = io.open
            local _old_io_open = io.open
            io.open = function(path, mode)
                -- 如果是相对路径，加上 POB 根目录前缀
                if not path:match("^[A-Za-z]:") and not path:match("^/") then
                    path = _POB_ROOT .. "/" .. path
                end
                return _old_io_open(path, mode)
            end
        ''')
        
        # 加载 StatDescriber.lua
        describer_path = self.pob_path / 'Modules' / 'StatDescriber.lua'
        if not describer_path.exists():
            raise FileNotFoundError(f"StatDescriber.lua 不存在: {describer_path}")
        
        # StatDescriber.lua return 一个函数，我们需要获取这个函数
        describer_lua_path = str(describer_path).replace('\\', '/')
        self._describer_func = self.lua.eval(f'dofile("{describer_lua_path}")')
        
        if self._describer_func is None:
            raise RuntimeError("StatDescriber.lua 未返回有效函数")
        
        logger.info("StatDescriber 桥接初始化成功")
        
        # 预加载公共 scope（Task 2.5: 批量处理优化）
        self._preload_scopes()
    
    def _preload_scopes(self):
        """
        预加载公共 StatDescription scope
        
        stat_descriptions.lua 约 3.9MB/22万行，预加载避免重复解析。
        预加载通过调用 describer_func 一次以触发 getScope 的缓存机制。
        """
        for scope_name in self.PRELOAD_SCOPES:
            try:
                # 用一个虚拟 stat 调用来触发 scope 的加载和缓存
                # StatDescriber 内部会在首次调用时自动缓存 scope
                self._describer_func(
                    self.lua.table_from({'_dummy_preload_stat_': 1}),
                    scope_name,
                    False
                )
            except Exception as e:
                logger.warning(f"预加载 scope '{scope_name}' 失败: {e}")
        
        logger.info(f"预加载完成: {len(self.PRELOAD_SCOPES)} 个 scope")
    
    @property
    def available(self) -> bool:
        """桥接是否可用"""
        return self._initialized and self._describer_func is not None
    
    @property
    def error(self) -> Optional[str]:
        """初始化错误信息"""
        return self._init_error
    
    def describe_stats(
        self,
        stats: Dict[str, Union[int, float, Dict[str, float]]],
        scope_name: str = 'stat_descriptions',
        quality: bool = False
    ) -> Tuple[Optional[List[str]], Optional[Dict[str, str]]]:
        """
        调用 POB StatDescriber 生成 stat 描述文本
        
        Args:
            stats: stat 名称→数值 的映射
                - 简单值: {'stat_name': 15}
                - 范围值: {'stat_name': {'min': 10, 'max': 20}}
            scope_name: StatDescription 作用域名
                - 'stat_descriptions' (通用/根节点)
                - 'skill_stat_descriptions' (技能stat)
                - 'passive_skill_stat_descriptions' (天赋stat)
                - 'gem_stat_descriptions' (宝石stat)
                - 'advanced_mod_stat_descriptions' (高级mod)
            quality: 是否包含 gem_quality 描述行
        
        Returns:
            (lines, line_map) 元组:
                - lines: 描述文本行列表，如 ['15% more Damage for each remaining Chain']
                - line_map: {文本行: stat名称} 映射
                - 失败时返回 (None, None)
        """
        # Task 2.6: 优雅降级
        if not self.available:
            logger.warning(f"StatDescriber 不可用: {self._init_error}")
            return None, None
        
        if not stats:
            return [], {}
        
        try:
            # 构建 Lua stats 表
            lua_stats = self._build_lua_stats(stats)
            
            # 调用 StatDescriber 函数
            result = self._describer_func(lua_stats, scope_name, quality)
            
            # 解析返回值
            return self._parse_result(result)
            
        except Exception as e:
            logger.error(f"describe_stats 失败 (scope={scope_name}): {e}")
            return None, None
    
    def _build_lua_stats(self, stats: Dict[str, Union[int, float, Dict[str, float]]]) -> Any:
        """将 Python stats 字典转换为 Lua table"""
        lua_table = {}
        for stat_name, value in stats.items():
            if isinstance(value, dict):
                # 范围值: {min: N, max: N}
                lua_table[stat_name] = self.lua.table_from({
                    'min': value.get('min', 0),
                    'max': value.get('max', 0)
                })
            else:
                # 简单数值
                lua_table[stat_name] = value
        
        return self.lua.table_from(lua_table)
    
    def _parse_result(self, result) -> Tuple[List[str], Dict[str, str]]:
        """解析 StatDescriber 返回值（Lua table → Python）"""
        # StatDescriber 返回 (out, lineMap)
        # 由于 unpack_returned_tuples=True，result 是一个 tuple
        if result is None:
            return [], {}
        
        if isinstance(result, tuple):
            lua_out, lua_line_map = result
        else:
            # 单一返回值的情况
            lua_out = result
            lua_line_map = None
        
        # 转换 out (Lua array → Python list)
        lines = []
        if lua_out is not None:
            # Lua table 的数字索引从 1 开始
            try:
                for line in lua_out.values():
                    if line is not None:
                        lines.append(str(line))
            except (AttributeError, TypeError):
                # 可能是空表或非表类型
                pass
        
        # 转换 lineMap (Lua table → Python dict)
        line_map = {}
        if lua_line_map is not None:
            try:
                for k, v in lua_line_map.items():
                    line_map[str(k)] = str(v)
            except (AttributeError, TypeError):
                pass
        
        return lines, line_map
    
    def describe_entity_stats(
        self,
        entity: Dict[str, Any],
        entity_type: str = None
    ) -> Optional[List[str]]:
        """
        为实体生成 stat 描述（便捷方法）
        
        根据实体类型自动选择合适的 scope:
        - skill_definition → skill_stat_descriptions
        - gem_definition → gem_stat_descriptions
        - passive_node → passive_skill_stat_descriptions
        - mod_affix → stat_descriptions
        - unique_item → stat_descriptions
        
        Args:
            entity: 实体数据字典
            entity_type: 实体类型（如果不在entity中指定）
        
        Returns:
            描述文本行列表，或 None
        """
        if not self.available:
            return None
        
        etype = entity_type or entity.get('type', 'unknown')
        
        # 选择 scope
        scope_map = {
            'skill_definition': 'skill_stat_descriptions',
            'gem_definition': 'gem_stat_descriptions',
            'passive_node': 'passive_skill_stat_descriptions',
            'mod_affix': 'stat_descriptions',
            'unique_item': 'stat_descriptions',
        }
        scope_name = scope_map.get(etype, 'stat_descriptions')
        
        # 提取 stats
        stats = self._extract_stats_from_entity(entity)
        if not stats:
            return None
        
        # 是否是 gem quality 相关
        quality = entity.get('gem_type') is not None
        
        lines, _ = self.describe_stats(stats, scope_name, quality)
        return lines
    
    def _extract_stats_from_entity(self, entity: Dict[str, Any]) -> Dict[str, Union[int, float]]:
        """
        从实体数据中提取 stats 字典
        
        支持多种来源:
        1. constant_stats: 固定stat列表 [{stat: name, value: N}, ...]
        2. stats: 动态stat列表（同格式）
        3. stats_node: 天赋节点stat列表 ["stat_name"]
        """
        stats = {}
        
        # 从 constant_stats 提取
        constant_stats = entity.get('constant_stats', [])
        if isinstance(constant_stats, list):
            for cs in constant_stats:
                if isinstance(cs, dict):
                    stat_name = cs.get('stat') or cs.get('name') or cs.get('k')
                    value = cs.get('value') or cs.get('v', 0)
                    if stat_name:
                        stats[stat_name] = value
                elif isinstance(cs, (list, tuple)) and len(cs) >= 2:
                    stats[cs[0]] = cs[1]
        
        # 从 stats 提取（通常是动态stat，取等级1的值作为代表）
        entity_stats = entity.get('stats', [])
        if isinstance(entity_stats, list):
            for s in entity_stats:
                if isinstance(s, dict):
                    stat_name = s.get('stat') or s.get('name') or s.get('k')
                    if stat_name and stat_name not in stats:
                        # 优先取 baseValue，否则取 value
                        value = s.get('baseValue') or s.get('value') or s.get('v', 0)
                        stats[stat_name] = value
                elif isinstance(s, str):
                    # 某些格式只是 stat 名称列表，用 1 作为默认值
                    stats[s] = 1
        
        # 从 levels 提取（取等级1的stats）
        levels = entity.get('levels', {})
        if isinstance(levels, dict):
            # levels 格式: {level_num: {stats: [val1, val2, ...]}}
            level_1 = levels.get(1) or levels.get('1') or levels.get(0) or levels.get('0')
            if isinstance(level_1, dict):
                level_stats = level_1.get('stats', [])
                # level_stats 是一个数值数组，需要配合 stats 定义来关联
                # 这里只处理显式的 stat 名→值映射
                if isinstance(level_stats, dict):
                    stats.update(level_stats)
        
        # 从 stats_node 提取（天赋节点）
        stats_node = entity.get('stats_node', [])
        if isinstance(stats_node, list):
            for sn in stats_node:
                if isinstance(sn, str) and sn not in stats:
                    stats[sn] = 1  # 天赋节点stat通常是布尔标志
                elif isinstance(sn, dict):
                    stat_name = sn.get('stat') or sn.get('name')
                    value = sn.get('value', 1)
                    if stat_name:
                        stats[stat_name] = value
        
        return stats
    
    def batch_describe(
        self,
        entities: List[Dict[str, Any]],
        scope_name: str = None
    ) -> Dict[str, Optional[List[str]]]:
        """
        批量描述多个实体的 stats（Task 2.5: 批量处理优化）
        
        Scope 已预加载，此方法仅负责逐个调用 describer_func。
        
        Args:
            entities: 实体数据列表
            scope_name: 强制使用的 scope（None 则自动选择）
        
        Returns:
            {entity_id: [描述行列表]} 映射
        """
        results = {}
        
        for entity in entities:
            eid = entity.get('id', 'unknown')
            if scope_name:
                stats = self._extract_stats_from_entity(entity)
                if stats:
                    lines, _ = self.describe_stats(stats, scope_name)
                    results[eid] = lines
                else:
                    results[eid] = None
            else:
                results[eid] = self.describe_entity_stats(entity)
        
        return results
    
    def clear_cache(self):
        """清除 Lua 模块缓存（如果需要重新加载 StatDescription 文件）"""
        if self.lua:
            self.lua.execute('_module_cache = {}')
            # 也需要清除 scopes 缓存（StatDescriber.lua 内部的 local scopes）
            # 重新加载 StatDescriber.lua
            try:
                describer_path = str(self.pob_path / 'Modules' / 'StatDescriber.lua').replace('\\', '/')
                self._describer_func = self.lua.eval(f'dofile("{describer_path}")')
                self._preload_scopes()
            except Exception as e:
                logger.error(f"重新加载 StatDescriber 失败: {e}")
    
    def close(self):
        """释放 Lua 运行时资源"""
        self.lua = None
        self._describer_func = None
        self._initialized = False
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
    
    def __del__(self):
        self.close()


# ──────────────────────────────────────────────────────────────
# CLI 自检和测试
# ──────────────────────────────────────────────────────────────

def main():
    """命令行测试入口"""
    import argparse
    import sys
    
    SCRIPTS_DIR = Path(__file__).parent
    sys.path.insert(0, str(SCRIPTS_DIR))
    from pob_paths import get_pob_path
    
    parser = argparse.ArgumentParser(description='StatDescriber 桥接测试')
    parser.add_argument('--pob-path', help='POB数据路径')
    parser.add_argument('--test-arc', action='store_true', help='用Arc的stats测试')
    parser.add_argument('--test-stat', help='测试单个stat（格式: stat_name=value）')
    parser.add_argument('--scope', default='skill_stat_descriptions', help='StatDescription scope名')
    
    args = parser.parse_args()
    
    pob_path = args.pob_path or str(get_pob_path())
    
    print(f"POB路径: {pob_path}")
    print(f"lupa 可用: {LUPA_AVAILABLE}")
    
    if not LUPA_AVAILABLE:
        print("\n[ERROR] lupa 未安装，请运行: pip install lupa")
        return
    
    bridge = StatDescriberBridge(pob_path)
    
    print(f"桥接可用: {bridge.available}")
    if bridge.error:
        print(f"错误: {bridge.error}")
        return
    
    if args.test_arc:
        # Arc 技能的典型 stats（等级20）
        arc_stats = {
            'spell_minimum_base_lightning_damage': 96,
            'spell_maximum_base_lightning_damage': 478,
            'number_of_chains': 7,
            'arc_damage_+%_final_for_each_remaining_chain': 15,
            'base_cast_speed': 800,
            'base_critical_strike_multiplier_+': 0,
            'base_skill_effect_duration': 0,
        }
        
        print(f"\n--- Arc 测试 (scope={args.scope}) ---")
        lines, line_map = bridge.describe_stats(arc_stats, args.scope)
        
        if lines:
            print(f"描述行数: {len(lines)}")
            for line in lines:
                stat = line_map.get(line, '?')
                print(f"  [{stat}] {line}")
        else:
            print("  无描述输出")
    
    if args.test_stat:
        # 解析 stat_name=value 格式
        parts = args.test_stat.split('=')
        if len(parts) == 2:
            stat_name = parts[0].strip()
            stat_value = float(parts[1].strip())
            
            print(f"\n--- 单stat测试: {stat_name}={stat_value} ---")
            lines, line_map = bridge.describe_stats(
                {stat_name: stat_value},
                args.scope
            )
            
            if lines:
                for line in lines:
                    print(f"  {line}")
            else:
                print("  无描述输出")
        else:
            print(f"格式错误: 应为 stat_name=value, 实际: {args.test_stat}")
    
    if not args.test_arc and not args.test_stat:
        # 默认：用一个简单stat测试
        print("\n--- 基础测试 ---")
        lines, line_map = bridge.describe_stats(
            {'base_maximum_life': 50},
            'stat_descriptions'
        )
        
        if lines:
            print(f"描述: {lines}")
        else:
            print("  无描述输出（可能stat名不在该scope中）")
        
        print("\n使用 --test-arc 测试Arc技能, 或 --test-stat stat_name=value 测试单个stat")


if __name__ == '__main__':
    main()
