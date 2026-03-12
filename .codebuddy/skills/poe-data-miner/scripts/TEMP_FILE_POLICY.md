# 临时文件管理策略

## 分类标准

### 长期保留的脚本
- **核心工具**：query_router.py, kb_query.py
- **知识库管理**：init_knowledge_base.py, data_scanner.py等
- **长期使用**：heuristic_query.py等

### 临时脚本（执行后删除）
- **一次性探索**：explore_*.py, diagnose_*.py
- **临时验证**：verify_*.py（除非是长期验证工具）
- **中间过程**：analyze_*.py, query_*_detail.py

### 结果数据（保存到知识库）
- **验证结果** → knowledge_base/verification_records.yaml
- **分析结果** → knowledge_base/analysis_records.yaml
- **探索发现** → knowledge_base/discoveries.yaml

## 工作流程

### 正确流程：
```
1. 需要执行一次性操作
   ↓
2. 使用execute_command直接执行
   或创建临时脚本+立即删除
   ↓
3. 保存结果到知识库（不是脚本）
   ↓
4. 清理临时文件
```

### 错误流程：
```
1. 需要执行一次性操作
   ↓
2. 创建脚本文件
   ↓
3. 执行脚本
   ↓
4. 保留脚本（冗余！）❌
```

## 清理清单

当前需要清理的临时脚本：
- scripts/explore_bypass_via_graph.py → 应该直接执行
- scripts/verify_hazard_bypass.py → 应该保存结果而非脚本
- scripts/diagnose_missed_mechanism.py → 已删除 ✓
- scripts/query_doedre_detail.py → 已删除 ✓
- scripts/analyze_doedre_mechanism.py → 已删除 ✓
