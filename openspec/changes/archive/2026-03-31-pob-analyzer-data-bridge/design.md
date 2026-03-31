## Context

### 当前状态
- `pob-build-analyzer` 通过 Lua 代码直接读取 POB 数据文件
- `poe-data-miner` 已将 POB 数据提取到 SQLite 数据库（entities.db, formulas.db）
- 两个技能独立运行，无代码级联动

### 约束
- 不修改 `poe-data-miner`（保持独立）
- 不引入子进程调用（避免开销和输出解析）
- 数据库路径需跨技能定位（相对路径）
- 报告格式需同时支持 Markdown 和未来的 HTML 输出

## Goals / Non-Goals

**Goals:**
1. 创建 `data_bridge.py` 模块，封装 entities.db 查询
2. 替换 `what_if.py` 中 4 个手写 Lua 查询函数
3. 优化报告格式，使用可折叠区块提升可读性
4. 为后续网页版扩展预留 HTML 友好结构

**Non-Goals:**
- 不创建公式查询、机制查询等完整知识库查询能力（那是 poe-data-miner 的职责）
- 不修改 poe-data-miner 的数据结构
- 不实现 HTML 输出生成器（只优化 Markdown 格式，使其可转换为 HTML）

## Decisions

### D1: 数据访问方式 — 直接读 SQLite

**选择**: 直接导入 sqlite3，读取 `poe-data-miner/knowledge_base/entities.db`

**替代方案**:
1. ❌ 调用 `kb_query.py` CLI — 子进程开销，输出解析复杂
2. ❌ 从 `poe_data_miner` 包导入 — 需要添加 `__init__.py`，修改 poe-data-miner
3. ✅ 直接读 SQLite — 无依赖修改，性能最佳，路径可控

**路径解析**:
```python
# pob_calc/data_bridge.py
from pathlib import Path

class POEDataBridge:
    def __init__(self):
        # 相对于 pob_calc/ 目录
        # pob_calc/ → pob-build-analyzer/ → .codebuddy/skills/ → poe-data-miner/
        self.db_path = (
            Path(__file__).parent.parent.parent  # pob-build-analyzer
            / "poe-data-miner"
            / "knowledge_base"
            / "entities.db"
        )
```

### D2: 数据查询 API 设计

**选择**: 提供专用的窄接口，而非通用查询

```python
class POEDataBridge:
    def get_skill_stat_at_level(self, skill_id: str, level: int, stat_index: int = 0) -> float
    def get_support_level_bonus(self, support_id: str) -> int
    def get_quality_speed_per_q(self, skill_id: str) -> float
    def get_entity(self, entity_id: str) -> dict | None
```

**理由**:
- `what_if.py` 只需要这 4 种查询
- 避免暴露 SQLite 连接，防止误用
- 查询逻辑封装在 data_bridge，便于测试和缓存

### D3: 报告格式 — 可折叠区块 + 主表分离

**选择**: 主表只显示关键指标，详细信息放入 `<details>` 折叠区块

**格式设计**:
```markdown
| # | 光环 | 裸光环 | 真实 | EHP | 精魄 |
|---|------|--------|------|-----|------|
| 1 | Trinity | +30% | +35% | +0% | 100 |

<details>
<summary><b>Trinity 详细数据</b></summary>

### 条件参数范围
| 端点 | 裸光环 | 真实 | Speed INC |
|------|--------|------|-----------|
| Res=0 | +0.0% | +0.0% | 75% |
| Res=300 | +73.7% | +91.3% | 75%→97% |

### 辅助贡献
- **Dialla's Desire**: +1 等级, +10% 品质
- **Uhtred's Omen**: +3 等级

### 基础数值
- 有效等级: **Lv24** (基础 Lv20 + 辅助 +4)
- MORE per 30 Resonance: **7%**
</details>
```

**网页扩展性**:
- `<details>` 原生支持，无需转换
- 可添加 CSS 样式
- 可添加 JS 交互（全部展开/折叠）
- 未来生成 HTML 时可直接嵌入

### D4: 灵敏度分析表格优化

**选择**: 同样使用可折叠区块

主表只显示 Top 5 或 Top 10，完整列表放入折叠区块。

## Risks / Trade-offs

### R1: 路径硬编码
- **风险**: 如果项目结构改变，路径失效
- **缓解**: 路径计算使用相对路径，基于 `__file__`，适应项目根目录变化
- **影响**: 低 — 项目结构稳定

### R2: entities.db 数据缺失
- **风险**: 某些技能或辅助在 entities.db 中不存在
- **缓解**: `POEDataBridge` 方法返回默认值（0 或 None），调用方处理 fallback
- **影响**: 低 — 已验证 Trinity/Dialla's/Uhtred's 数据存在

### R3: 报告格式兼容性
- **风险**: CodeBuddy 内置浏览器可能不支持 `<details>` 折叠
- **缓解**: `<details>` 是标准 HTML，主流 Markdown 渲染器支持
- **影响**: 低 — 最坏情况显示为普通区块

### R4: 折叠区块过多影响扫描
- **风险**: 用户需要逐个展开，无法快速扫描
- **缓解**: 主表显示关键指标，折叠区块只放详细信息；默认展开第一个区块
- **影响**: 中 — 需要用户反馈调整

## Migration Plan

### Phase 1: 创建 data_bridge.py
1. 实现 `POEDataBridge` 类
2. 编写单元测试验证数据查询

### Phase 2: 替换 Lua 查询
1. 删除 `what_if.py` 中的 4 个 Lua 查询函数
2. 在 `aura_spirit_analysis()` 中使用 `POEDataBridge`
3. 验证输出不变

### Phase 3: 报告格式优化
1. 修改 `format_report()` 中的光环表格格式
2. 添加可折叠区块
3. 生成测试报告验证

### 回滚策略
- Git 分支保护，可随时回滚
- data_bridge.py 独立模块，可删除
- 报告格式修改可单独回滚

## Open Questions

1. **是否需要缓存**: entities.db 查询是否需要内存缓存？
   - 当前查询量小（每个光环 3-4 次查询）
   - SQLite 自带页缓存
   - **结论**: 暂不需要，如有性能问题再添加

2. **HTML 输出生成器**: 是否在本次变更中实现？
   - **结论**: 不在本次范围，只优化 Markdown 格式
