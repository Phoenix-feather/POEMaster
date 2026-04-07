## Why

当前构筑分析报告以 Markdown 格式输出，纯文本表格可读性有限，无法直观展示数据关系（如 DPS 乘区累积、光环参数连续变化）。需要将报告转化为交互式网页版本，支持多技能页签切换、图表可视化和简单的参数交互（如 Trinity Resonance 滑块）。

## What Changes

- 新增 Python 脚本，读取多个技能的 `analysis_{skill}.json` 缓存数据，生成单个自包含 HTML 文件（数据内嵌 JSON）
- HTML 页面使用 React + Recharts + Tailwind CSS（CDN 引入，无需构建工具），实现：
  - 多技能页签切换（Spark、Comet、Frost Bomb 等主动技能）
  - 6 个图表：DPS 乘区瀑布图、来源类别堆叠柱、灵敏度排名条形图、光环增益折线+滑块、天赋价值气泡图、防御雷达图
  - 4 个折叠明细表格：天赋价值、灵敏度、天赋探索、珠宝诊断
- L0 交互：页签切换、折叠/展开
- L1 交互：Trinity Resonance 滑块 → 折线图实时插值更新

## Capabilities

### New Capabilities

- `build-report-html`: 将 pob-build-analyzer 的 analysis JSON 数据渲染为自包含交互式 HTML 报告

### Modified Capabilities

## Impact

- **新增文件**：`pob-build-analyzer/report_generator.py`（HTML 生成脚本）
- **输出文件**：`cache/builds/{build_id}/report_{build_id}.html`（自包含 HTML）
- **依赖**：无新 Python 依赖；HTML 通过 CDN 引入 React、Recharts、Tailwind
- **现有代码**：不修改现有 `what_if.py`、`calculator.py` 等模块，纯新增
