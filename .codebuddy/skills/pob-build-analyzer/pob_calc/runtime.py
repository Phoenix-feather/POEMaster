#!/usr/bin/env python3
"""
POB Lua 运行时工厂。

职责：
  - create_runtime: 创建完整的 POB Lua 运行时
    1. 注入 C 层 stub (LoadModule, Inflate, 渲染/输入等)
    2. 设置 Lua 5.4 兼容层 (bit, unpack, package.path)
    3. 应用兼容补丁 (tostring)
    4. 加载 POB 核心模块 (GameVersions → Common → Data → ModTools → Calcs)
"""
import os
import time
import zlib
import logging
from pathlib import Path

from lupa import LuaRuntime

from .compat import apply_lua54_patches, register_item_fix_functions

logger = logging.getLogger(__name__)

# POB 路径探测顺序：
#   1. 函数参数 pob_path
#   2. 环境变量 POB_DATA_PATH
#   3. 常见安装位置自动探测
_POB_SEARCH_PATHS = [
    Path("G:/POEMaster/POBData"),
    Path("C:/ProgramData/Path of Building/Data"),
    Path.home() / "PathOfBuilding" / "Data",
    Path.home() / "Documents" / "Path of Building" / "Data",
]


def _find_pob_path() -> Path:
    """自动探测 POBData 目录。

    优先级：
    1. 环境变量 POB_DATA_PATH
    2. 常见安装位置
    """
    env_path = os.environ.get('POB_DATA_PATH')
    if env_path:
        p = Path(env_path)
        if p.is_dir():
            return p
        logger.warning("环境变量 POB_DATA_PATH=%s 不是有效目录", env_path)

    for candidate in _POB_SEARCH_PATHS:
        if candidate.is_dir() and (candidate / "Modules" / "Calcs.lua").exists():
            logger.info("自动探测到 POBData: %s", candidate)
            return candidate

    raise FileNotFoundError(
        "未找到 POBData 目录。请通过以下方式之一指定：\n"
        "  1. POBCalculator(pob_path='...')\n"
        "  2. 设置环境变量 POB_DATA_PATH=<path>\n"
        f"  已搜索: {[str(p) for p in _POB_SEARCH_PATHS]}"
    )


def create_runtime(pob_path: Path = None) -> tuple:
    """创建完整的 POB Lua 运行时。

    Args:
        pob_path: POBData 目录路径。未指定时自动探测（环境变量 → 常见位置）。

    Returns:
        (lua, calcs, load_errors)
        - lua: LuaRuntime 实例
        - calcs: POB calcs 模块（含 initEnv/perform）
        - load_errors: 加载错误列表
    """
    if pob_path is None:
        pob_path = _find_pob_path()
    elif not Path(pob_path).is_dir():
        raise FileNotFoundError(f"POBData 目录不存在: {pob_path}")
    script_path = str(pob_path).replace("\\", "/")

    lua = LuaRuntime(unpack_returned_tuples=True)
    g = lua.globals()

    # === C 层函数 stub ===
    load_count = [0]
    load_errors = []

    def lua_load_module(name, *args):
        load_count[0] += 1
        path = name
        if not path.endswith(".lua"):
            path = path + ".lua"
        full_path = os.path.join(script_path, path)
        if not os.path.exists(full_path):
            load_errors.append(f"文件不存在: {path}")
            return None
        try:
            with open(full_path, 'r', encoding='utf-8', errors='replace') as f:
                code = f.read()
            if code.startswith('\ufeff'):
                code = code[1:]
            if code.startswith('#@'):
                code = code[code.index('\n') + 1:]
            func = lua.eval(f'function(...) {code}\nend')
            return func(*args)
        except Exception as e:
            err_msg = str(e)
            if len(err_msg) > 200:
                err_msg = err_msg[:200] + "..."
            load_errors.append(f"{path}: {err_msg}")
            return None

    g.LoadModule = lua_load_module
    g.PLoadModule = lambda name, *args: (None, lua_load_module(name, *args))
    g.PCall = lambda func, *args: (None, func(*args)) if func else (None, None)

    # 运行时信息
    g.GetTime = lambda: int(time.time() * 1000)
    g.GetScriptPath = lambda: script_path + "/"
    g.GetRuntimePath = lambda: script_path + "/"
    g.GetWorkDir = lambda: script_path + "/"
    g.GetUserPath = lambda: script_path + "/"

    # 控制台
    g.ConPrintf = lambda fmt, *args: None
    g.ConClear = lambda: None
    g.ConExecute = lambda cmd: None
    g.ConPrintTable = lambda tbl: None

    # zlib
    def lua_inflate(data):
        if data is None:
            return None
        raw = bytes(data)
        try:
            return zlib.decompress(raw)
        except Exception:
            try:
                return zlib.decompress(raw, -zlib.MAX_WBITS)
            except Exception as e:
                logger.warning("Inflate 解压失败 (%d bytes): %s", len(raw), e)
                return b""  # 返回空 bytes 而非 None，避免下游 nil 访问崩溃

    g.Inflate = lua_inflate
    g.Deflate = lambda data: zlib.compress(bytes(data)) if data else None

    # 文件系统
    g.MakeDir = lambda path: None
    g.RemoveDir = lambda path: None
    g.NewFileSearch = lambda *args: None

    # StripEscapes
    lua.execute('''
        function StripEscapes(str)
            if not str then return "" end
            return str:gsub("%^x%x%x%x%x%x%x", ""):gsub("%^%d", "")
        end
    ''')

    # 渲染/输入 stub
    for fn in ['SetMainObject', 'RenderInit', 'SetWindowTitle', 'SetDrawLayer',
               'SetViewport', 'SetDrawColor', 'DrawImage', 'DrawImageQuad',
               'DrawString', 'SetCursorPos', 'Copy', 'TakeScreenshot',
               'LaunchSubScript', 'Restart', 'Exit', 'SpawnProcess', 'OpenURL',
               'SetDPIScaleOverridePercent']:
        g[fn] = lambda *args: None
    g.GetScreenSize = lambda: (1920, 1080)
    g.GetScreenScale = lambda: 1
    g.DrawStringWidth = lambda size, font, text: len(str(text or "")) * 7
    g.DrawStringCursorIndex = lambda *args: 0
    g.GetCursorPos = lambda: (0, 0)
    g.IsKeyDown = lambda key: False
    g.GetKeyState = lambda key: False
    g.GetAsyncCount = lambda: 0
    g.Paste = lambda: ""
    g.GetCloudProvider = lambda path: None
    g.GetDPIScaleOverridePercent = lambda: 0

    # === Lua 5.4 兼容层 + 全局变量 ===
    lua.execute(f'''
        -- math.pow 兼容层（Lua 5.4 移除了 math.pow，POB CalcOffence 依赖它）
        if not math.pow then
            math.pow = function(x, y) return x ^ y end
        end

        -- bit 库兼容层
        bit = {{}}
        function bit.band(a, b) return (a or 0) & (b or 0) end
        function bit.bor(a, b) return (a or 0) | (b or 0) end
        function bit.bxor(a, b) return (a or 0) ~ (b or 0) end
        function bit.bnot(a) return ~(a or 0) end
        function bit.lshift(a, n) return ((a or 0) << (n or 0)) end
        function bit.rshift(a, n) return ((a or 0) >> (n or 0)) end
        function bit.tobit(x)
            x = math.floor(x or 0) % 0x100000000
            if x >= 0x80000000 then x = x - 0x100000000 end
            return x
        end

        if not unpack then
            unpack = table.unpack
        end

        launch = {{
            devMode = false,
            versionNumber = "2.45.0",
            versionBranch = "master",
            versionPlatform = "win32",
        }}
        arg = {{}}
        APP_NAME = "Path of Building"

        package.path = "{script_path}/lua/?.lua;{script_path}/?.lua;" .. package.path

        package.preload["lcurl.safe"] = function() return {{}} end
        package.preload["sha1"] = function()
            local sha1_func = function(s) return string.rep("0", 40) end
            return sha1_func
        end
        package.preload["lua-utf8"] = function()
            local u = {{}}
            u.byte = string.byte; u.char = string.char; u.len = function(s) return #s end
            u.sub = string.sub; u.find = string.find; u.gmatch = string.gmatch
            u.gsub = string.gsub; u.match = string.match; u.lower = string.lower
            u.upper = string.upper; u.reverse = string.reverse
            u.format = string.format; u.rep = string.rep
            return u
        end
        package.preload["lua-profiler"] = function() return nil end

        main = {{
            defaultItemAffixQuality = 0.5,
            defaultItemQuality = 20,
        }}
    ''')

    # === 加载 POB 核心模块 ===
    lua.globals().LoadModule("GameVersions")
    lua.globals().LoadModule("Modules/Common")

    # 兼容补丁
    apply_lua54_patches(lua)

    # Data → ModTools → ItemTools → CalcTools → Calcs
    lua.globals().LoadModule("Modules/Data")
    lua.globals().LoadModule("Modules/ModTools")
    lua.globals().LoadModule("Modules/ItemTools")
    lua.globals().LoadModule("Modules/CalcTools")
    calcs = lua.globals().LoadModule("Modules/Calcs")

    # 注册物品修复函数
    register_item_fix_functions(lua)

    return lua, calcs, load_errors
