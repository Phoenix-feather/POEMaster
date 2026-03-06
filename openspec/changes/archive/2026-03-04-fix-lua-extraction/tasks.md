## 1. 核心解析器实现

- [x] 1.1 实现括号平衡算法 `extract_lua_table()`
- [x] 1.2 添加字符串内花括号忽略逻辑
- [x] 1.3 实现技能类型提取 `_extract_skill_types()`
- [x] 1.4 实现statSets嵌套结构提取 `_extract_stat_sets()`

## 2. data_scanner.py 修改

- [x] 2.1 重写 `_extract_skills()` 使用新解析器
- [x] 2.2 更新 `_extract_field()` 支持更复杂的字段格式
- [x] 2.3 更新 `_extract_array()` 支持 `[Type.XXX] = true` 格式
- [x] 2.4 更新 `_extract_stats_array()` 支持statSets嵌套

## 3. 验证与测试

- [x] 3.1 添加提取结果验证函数
- [x] 3.2 创建单元测试验证解析器
- [x] 3.3 测试act_str.lua、sup_str.lua等文件
- [x] 3.4 验证提取数量（预期200-300技能）→ 实际1253技能

## 4. 知识库重建

- [x] 4.1 运行优化后的扫描
- [x] 4.2 重新初始化实体索引
- [x] 4.3 重新生成Layer 1规则
- [x] 4.4 验证规则数量（预期500+）→ 实际8961规则
