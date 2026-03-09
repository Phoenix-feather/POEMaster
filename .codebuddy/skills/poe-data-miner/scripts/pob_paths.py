#!/usr/bin/env python3
"""
POB路径和文件范围管理 — 强制执行 POB数据提取范围规则

所有需要访问POB数据的脚本必须通过本模块获取路径和文件列表。
禁止直接使用 pob_path.rglob('*.lua') 等方式自行扫描。

规则来源: .codebuddy/rules/pob-data-extraction-scope.mdc

强制扫描范围:
    1. POBData/Data/         所有.lua（递归，含子目录）
    2. POBData/Modules/      所有.lua（不递归）
    3. POBData/TreeData/X_Y/ tree.lua（仅最新版本）
    4. POBData/GameVersions.lua

禁止扫描:
    - Classes/    （UI控件）
    - lua/        （第三方库）
    - 根目录工具文件 (Launch.lua, UpdateCheck.lua 等)
    - TreeData/ 旧版本
"""

import re
from pathlib import Path
from typing import List, Optional, Tuple, Dict

# 脚本所在目录
_SCRIPTS_DIR = Path(__file__).parent

# 项目根目录: scripts → poe-data-miner → skills → .codebuddy → POEMaster
_PROJECT_ROOT = _SCRIPTS_DIR.parent.parent.parent.parent


def get_project_root() -> Path:
    """获取项目根目录"""
    return _PROJECT_ROOT


def get_pob_path() -> Path:
    """获取POB数据路径
    
    查找顺序:
    1. 项目根目录 / POBData
    2. g:/POEMaster/POBData（硬编码备用）
    
    Raises:
        FileNotFoundError: POB数据目录不存在
    """
    # 主路径
    pob_path = _PROJECT_ROOT / 'POBData'
    if pob_path.exists():
        return pob_path
    
    # 备用
    fallback = Path('g:/POEMaster/POBData')
    if fallback.exists():
        return fallback
    
    raise FileNotFoundError(
        f"POB数据路径不存在!\n"
        f"  主路径: {pob_path}\n"
        f"  备用: {fallback}\n"
        f"  项目根: {_PROJECT_ROOT}"
    )


def get_knowledge_base_path() -> Path:
    """获取知识库路径"""
    kb = _SCRIPTS_DIR.parent / 'knowledge_base'
    kb.mkdir(parents=True, exist_ok=True)
    return kb


def get_latest_tree_version(pob_path: Optional[Path] = None) -> Optional[str]:
    """获取最新的天赋树版本目录名
    
    Returns:
        版本目录名（如 '0_4'），或 None
    """
    if pob_path is None:
        pob_path = get_pob_path()
    
    tree_data_dir = pob_path / 'TreeData'
    if not tree_data_dir.exists():
        return None
    
    versions = []
    for item in tree_data_dir.iterdir():
        if item.is_dir() and re.match(r'^\d+_\d+$', item.name):
            major, minor = map(int, item.name.split('_'))
            versions.append((major, minor, item.name))
    
    if not versions:
        return None
    
    versions.sort(reverse=True)
    return versions[0][2]


def collect_lua_files(pob_path: Optional[Path] = None, verbose: bool = False) -> List[Path]:
    """按POB数据提取范围规则收集所有Lua文件
    
    这是访问POB Lua文件的唯一正确入口。
    
    范围:
        1. Data/         所有.lua（递归）
        2. Modules/      所有.lua（不递归）
        3. TreeData/X_Y/ tree.lua（仅最新版本）
        4. GameVersions.lua
    
    Args:
        pob_path: POB数据目录，默认自动检测
        verbose: 是否打印详细信息
    
    Returns:
        符合规则的Lua文件路径列表
    """
    if pob_path is None:
        pob_path = get_pob_path()
    
    lua_files = []
    
    # 1. Data/ 目录（递归，含 Bases/, Skills/, StatDescriptions/, Uniques/ 等）
    data_dir = pob_path / 'Data'
    if data_dir.exists():
        data_files = list(data_dir.rglob('*.lua'))
        lua_files.extend(data_files)
        if verbose:
            print(f"  Data/: {len(data_files)} 个文件")
    elif verbose:
        print("  [WARN] Data/ 目录不存在")
    
    # 2. Modules/ 目录（不递归）
    modules_dir = pob_path / 'Modules'
    if modules_dir.exists():
        modules_files = list(modules_dir.glob('*.lua'))
        lua_files.extend(modules_files)
        if verbose:
            print(f"  Modules/: {len(modules_files)} 个文件")
    elif verbose:
        print("  [WARN] Modules/ 目录不存在")
    
    # 3. TreeData/最新版本/ tree.lua
    latest = get_latest_tree_version(pob_path)
    if latest:
        tree_lua = pob_path / 'TreeData' / latest / 'tree.lua'
        if tree_lua.exists():
            lua_files.append(tree_lua)
            if verbose:
                print(f"  TreeData/{latest}/: tree.lua")
        elif verbose:
            print(f"  [WARN] TreeData/{latest}/tree.lua 不存在")
    elif verbose:
        print("  [WARN] TreeData/ 无版本目录")
    
    # 4. GameVersions.lua
    gv = pob_path / 'GameVersions.lua'
    if gv.exists():
        lua_files.append(gv)
        if verbose:
            print(f"  GameVersions.lua: 已包含")
    
    return lua_files


def get_file_scope_summary(pob_path: Optional[Path] = None) -> Dict[str, int]:
    """获取文件范围统计摘要
    
    Returns:
        {'data': N, 'modules': N, 'tree': 0|1, 'game_versions': 0|1, 'total': N}
    """
    if pob_path is None:
        pob_path = get_pob_path()
    
    summary = {
        'data': 0,
        'modules': 0,
        'tree': 0,
        'game_versions': 0,
        'total': 0
    }
    
    data_dir = pob_path / 'Data'
    if data_dir.exists():
        summary['data'] = len(list(data_dir.rglob('*.lua')))
    
    modules_dir = pob_path / 'Modules'
    if modules_dir.exists():
        summary['modules'] = len(list(modules_dir.glob('*.lua')))
    
    latest = get_latest_tree_version(pob_path)
    if latest and (pob_path / 'TreeData' / latest / 'tree.lua').exists():
        summary['tree'] = 1
    
    if (pob_path / 'GameVersions.lua').exists():
        summary['game_versions'] = 1
    
    summary['total'] = sum(summary.values())
    return summary


def validate_pob_path(pob_path: Path) -> Tuple[bool, List[str]]:
    """验证POB路径是否完整
    
    Returns:
        (is_valid, [warning_messages])
    """
    warnings = []
    
    if not pob_path.exists():
        return False, [f"POB路径不存在: {pob_path}"]
    
    # 必须存在的目录/文件
    required = {
        'Data': pob_path / 'Data',
        'Modules': pob_path / 'Modules',
        'GameVersions.lua': pob_path / 'GameVersions.lua',
    }
    
    for name, path in required.items():
        if not path.exists():
            warnings.append(f"缺少: {name}")
    
    # 关键文件检查
    critical_files = [
        'Data/SkillStatMap.lua',
        'Modules/CalcTriggers.lua',
        'Modules/CalcActiveSkill.lua',
        'Modules/CalcOffence.lua',
        'Data/ModCache.lua',
        'Data/Gems.lua',
    ]
    
    for f in critical_files:
        if not (pob_path / f).exists():
            warnings.append(f"缺少关键文件: {f}")
    
    # TreeData检查
    latest = get_latest_tree_version(pob_path)
    if latest is None:
        warnings.append("缺少: TreeData/ 版本目录")
    else:
        tree_lua = pob_path / 'TreeData' / latest / 'tree.lua'
        if not tree_lua.exists():
            warnings.append(f"缺少: TreeData/{latest}/tree.lua")
    
    is_valid = len(warnings) == 0
    return is_valid, warnings


# ──────────────────────────────────────────────────────────────
# 自检：直接运行本模块可打印当前状态
# ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("POB路径和文件范围管理 — 自检")
    print("=" * 60)
    
    try:
        pob = get_pob_path()
        print(f"\nPOB路径: {pob}")
        print(f"项目根: {get_project_root()}")
        print(f"知识库: {get_knowledge_base_path()}")
        
        # 验证
        valid, warns = validate_pob_path(pob)
        if valid:
            print("\n[OK] POB路径验证通过")
        else:
            print(f"\n[WARN] POB路径验证有 {len(warns)} 个警告:")
            for w in warns:
                print(f"  - {w}")
        
        # 文件范围
        print("\n文件范围统计:")
        files = collect_lua_files(pob, verbose=True)
        print(f"\n总计: {len(files)} 个Lua文件")
        
        # 摘要
        summary = get_file_scope_summary(pob)
        print(f"\n摘要: {summary}")
        
        # 天赋树版本
        tree_ver = get_latest_tree_version(pob)
        print(f"\n天赋树最新版本: {tree_ver}")
        
    except FileNotFoundError as e:
        print(f"\n[ERROR] {e}")
