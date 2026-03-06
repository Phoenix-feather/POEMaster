# 查询经验教训记录

## 记录目的
每次查询失败后总结原因，避免重复犯错。

---

## 经验 #1: Windows命令行引号问题

### 失败现象
```python
# 这行命令在Windows下可能返回空结果
python -c "import sqlite3; c.execute('SELECT * FROM rules WHERE category = \"formula\"')"
```

### 根本原因
- Windows PowerShell对嵌套引号处理与Unix不同
- `python -c "..."` 中的双引号会被Shell解析
- 即使使用转义 `\"` 也不可靠

### 解决方案
```python
# 方案1: 使用独立脚本 + 参数
python kb_query.py rule --formula

# 方案2: 使用参数化查询（在脚本内）
cursor.execute('SELECT * FROM rules WHERE category = ?', (category,))
```

### 避免规则
> **永远不要在 `python -c "..."` 中嵌套引号进行数据库查询**

---

## 经验 #2: Unicode字符输出失败

### 失败现象
```
UnicodeEncodeError: 'gbk' codec can't encode character '\u2713'
```

### 根本原因
- Windows默认编码是GBK
- Unicode字符（✓、✗等）无法编码

### 解决方案
```python
# 方案1: 使用ASCII替代
print("[OK]")  # 而不是 "✓"

# 方案2: 设置UTF-8编码（在脚本开头）
import sys
sys.stdout.reconfigure(encoding='utf-8')
```

### 避免规则
> **在Windows环境下，脚本输出避免Unicode特殊字符**

---

## 经验 #3: 多行输出被截断

### 失败现象
- 命令执行成功但输出为空
- 部分输出丢失

### 根本原因
- 命令行缓冲区限制
- Python print与Shell缓冲不同步

### 解决方案
```python
# 方案1: 使用json.dumps格式化
print(json.dumps(result, indent=2, ensure_ascii=False))

# 方案2: 分批输出
for item in results:
    print(item)
```

### 避免规则
> **大量数据输出时使用格式化工具，避免原始打印**

---

## 经验 #4: 复杂命令构造容易出错

### 失败现象
- 每次查询都需要重新构造命令
- 容易出现语法错误

### 解决方案
使用 kb_query.py 封装常用查询：

```bash
# 简单明了的命令
python kb_query.py stats
python kb_query.py entity --meta
python kb_query.py rule --formula
```

### 避免规则
> **优先使用封装好的查询工具，避免临时构造复杂命令**

---

## 最佳实践总结

### 查询优先级
1. **第一选择**: `kb_query.py` 封装命令
2. **第二选择**: 独立脚本文件
3. **最后选择**: `python -c "..."` （仅用于简单无引号查询）

### 命令构造规则
```python
# ✓ 正确：简单无引号
python -c "import os; print(os.getcwd())"

# ✗ 错误：嵌套引号查询
python -c "import sqlite3; c.execute('SELECT * FROM x WHERE y = \"val\"')"

# ✓ 正确：使用脚本
python query_script.py --filter "val"
```

### 输出处理规则
```python
# ✓ 正确：ASCII + JSON
print("[OK] Found", len(results), "items")
print(json.dumps(results, indent=2, ensure_ascii=False))

# ✗ 错误：Unicode + 长文本
print("✓ 成功找到项目...")
```

---

## 更新日志

| 日期 | 问题 | 解决方案 |
|------|------|----------|
| 2026-03-04 | Windows引号问题 | 创建kb_query.py |
| 2026-03-04 | Unicode输出失败 | 使用ASCII替代 |
| 2026-03-04 | 多行输出截断 | JSON格式化输出 |
