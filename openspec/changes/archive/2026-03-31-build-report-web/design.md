## Context

pob-build-analyzer 已有完整的分析数据管线：`full_analysis()` → `analysis_{skill}.json`（结构化 JSON）→ `format_report()` → `report_{skill}.md`（Markdown 报告）。当前 Monk Invoker 构筑缓存中已有 Spark 技能的完整分析数据（~7000行 JSON），包含 baseline、sensitivity、talent_value、talent_exploration、jewel_diagnosis、dps_breakdown、aura_spirit 等 7 个分析模块。

构筑的 `meta.json` 包含 23 个技能组，其中有意义的分析目标约 4-6 个（主动技能 + 伤害光环）。

## Goals / Non-Goals

**Goals:**

- 生成单个自包含 HTML 文件，内嵌所有分析数据（无需 HTTP server）
- 支持多技能页签切换（基于已有 analysis JSON）
- 6 个可视化图表 + 4 个折叠明细表格
- L0+L1 交互：页签、折叠、Trinity Resonance 滑块
- 暗色主题，与 POE 游戏风格一致
- 通过 CDN 引入 React/Recharts/Tailwind（零构建工具）

**Non-Goals:**

- 不做实时 What-If 操作（改天赋/装备重新计算）
- 不做服务端渲染或 API
- 不修改现有 what_if.py / calculator.py 等核心模块
- 不做响应式布局（主要在桌面浏览器查看）

## Decisions

### D1: 技术方案 — 单文件 HTML + CDN 依赖

**选择**: Python 脚本生成单个 `.html` 文件，所有分析数据作为 `<script>` 标签中的 JSON 变量内嵌。React/Recharts/Tailwind 通过 CDN（esm.sh/unpkg）引入。

**替代方案**:
- A) Node.js + Vite 构建项目 → 过度工程化，需要额外的构建流程
- B) 纯原生 HTML/JS/Canvas → 图表库缺失，开发成本高
- C) Python 生成多文件（HTML + JSON）→ 需要启动 server 才能避免 CORS

**理由**: 方案 A 最简单（`preview_url()` 直接打开即可），CDN 引入的库稳定可靠，无需任何构建工具。

### D2: 图表库 — Recharts

**选择**: Recharts（基于 React + D3）

**替代方案**:
- Chart.js → 功能足够但与 React 集成不如 Recharts 流畅
- ECharts → 功能更强大但体积更大（~1MB）
- 纯 SVG 手绘 → 开发成本极高

**理由**: Recharts 声明式 API 适合瀑布图、折线图等复杂图表，与 React 生态一致。通过 esm.sh CDN 引入即可。

### D3: 图表类型映射

| 分析模块 | 图表类型 | Recharts 组件 |
|---------|---------|---------------|
| dps_breakdown.formula_items | 瀑布图 (Waterfall) | 自定义 ComposedChart |
| dps_breakdown.category_summary | 堆叠柱状图 | BarChart (stacked) |
| sensitivity | 横向条形图 | BarChart (layout=vertical) |
| aura_spirit.config_ranges | 折线图 + 滑块 | LineChart + input[range] |
| talent_value | 散点/气泡图 | ScatterChart |
| baseline 防御数据 | 雷达图 | 自定义 SVG |

### D4: 数据准备 — Python 端预处理

**选择**: 在 Python 生成 HTML 前，将 `analysis_spark.json` 的原始数据转换为图表友好的扁平结构。

**理由**: 避免在浏览器端做复杂数据转换。例如：
- 瀑布图需要从 `formula_items` 计算累积值和乘区
- 光环折线图需要从 `config_ranges` 的两个端点生成插值点序列
- 天赋气泡图需要从 `talent_value` 提取 (dps_pct, ehp_pct) 坐标

### D5: 暗色主题

**选择**: 使用 Tailwind CSS dark 类 + 自定义 CSS 变量，配合 POE 风格的深灰/金色配色。

## Risks / Trade-offs

- **[CDN 可用性]** → 如果 esm.sh/unpkg 不可用，页面无法渲染。缓解：这是内部工具，网络环境可控。
- **[单文件体积]** → 多技能数据可能使 HTML 文件达到 500KB-1MB。缓解：JSON 压缩（去除 sample_diff 等大字段），对数据做精简。
- **[Recharts 瀑布图]** → Recharts 没有原生 Waterfall 组件，需要自定义 ComposedChart。缓解：用 stacked bar + invisible bar 模拟。
- **[线性插值精度]** → 光环折线图只有两个端点，中间用线性插值。实际可能非线性。缓解：标注"近似值"。
