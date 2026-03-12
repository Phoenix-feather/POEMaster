# 异常处理改进指南

## 改进原则

1. **区分异常类型** - 不同类型的异常使用不同的处理策略
2. **详细日志记录** - 记录足够的信息用于调试
3. **友好的错误信息** - 对用户提供清晰易懂的错误信息
4. **优雅降级** - 异常情况下提供备用方案

## 已实施的改进

### 1. VerificationEngine 改进

#### verify_knowledge 方法

**改进前**：
```python
def verify_knowledge(self, edge_id: int, auto_verify: bool = True):
    edge = self._get_edge(edge_id)
    if not edge:
        return {'success': False, 'error': f'边 {edge_id} 不存在'}
```

**改进后**：
```python
def verify_knowledge(self, edge_id: int, auto_verify: bool = True):
    logger.info(f"验证知识: edge_id={edge_id}, auto_verify={auto_verify}")
    
    try:
        # 1. 获取边信息
        edge = self._get_edge(edge_id)
        if not edge:
            logger.warning(f"边不存在: edge_id={edge_id}")
            return {
                'success': False,
                'error': f'边 {edge_id} 不存在',
                'error_type': 'EdgeNotFound',
                'edge_id': edge_id
            }
        
        # 2. 执行三层搜索（带异常捕获）
        try:
            evidence_list = self._search_evidence(edge)
        except Exception as e:
            logger.error(f"证据搜索失败: edge_id={edge_id}, error={e}", exc_info=True)
            return {
                'success': False,
                'error': f'证据搜索失败: {str(e)}',
                'error_type': 'EvidenceSearchFailed',
                'edge_id': edge_id
            }
        
        # 3. 评估证据（带异常捕获）
        try:
            evaluation = self.evaluator.evaluate(evidence_list)
        except Exception as e:
            logger.error(f"证据评估失败: edge_id={edge_id}, error={e}", exc_info=True)
            return {
                'success': False,
                'error': f'证据评估失败: {str(e)}',
                'error_type': 'EvaluationFailed',
                'edge_id': edge_id
            }
        
        # ... 其余逻辑
        
    except Exception as e:
        logger.critical(f"验证过程未捕获异常: edge_id={edge_id}, error={e}", exc_info=True)
        return {
            'success': False,
            'error': f'验证过程发生意外错误: {str(e)}',
            'error_type': 'UnexpectedError',
            'edge_id': edge_id
        }
```

### 2. POBCodeSearcher 改进

#### 索引查询改进

**改进后**：
```python
def search_stat_definition(self, stat_id: str) -> Dict[str, Any]:
    logger.debug(f"Layer 1搜索stat定义: {stat_id}")
    
    try:
        stat_index = self.index_manager.get_index('stat')
        if not stat_index:
            logger.error("StatIndex未初始化")
            return self._empty_result_with_error(1, "索引未初始化")
        
        result = stat_index.search({'stat_id': stat_id})
        
        if result['found']:
            logger.debug(f"找到stat定义: {stat_id}, 使用次数={result['usage_count']}")
        else:
            logger.debug(f"未找到stat定义: {stat_id}")
        
        return result
        
    except sqlite3.Error as e:
        logger.error(f"数据库查询错误: stat_id={stat_id}, error={e}")
        return self._empty_result_with_error(1, f"数据库错误: {str(e)}")
    
    except Exception as e:
        logger.error(f"查询过程异常: stat_id={stat_id}, error={e}", exc_info=True)
        return self._empty_result_with_error(1, f"查询异常: {str(e)}")

def _empty_result_with_error(self, layer: int, error_msg: str) -> Dict[str, Any]:
    """返回带错误信息的空结果"""
    return {
        'found': False,
        'layer': layer,
        'strength': 0.0,
        'evidence': [],
        'counter_examples': [],
        'error': error_msg
    }
```

### 3. VerificationAwareQueryEngine 改进

#### 异步验证改进

**改进后**：
```python
def _async_verify_batch(self, edge_ids: List[int]) -> List[Dict[str, Any]]:
    logger.info(f"异步验证 {len(edge_ids)} 条知识")
    
    results = []
    futures = []
    
    # 使用线程池执行验证
    for i, edge_id in enumerate(edge_ids):
        try:
            future = self.executor.submit(
                self.verification_engine.verify_knowledge,
                edge_id,
                True
            )
            futures.append((edge_id, future))
        except Exception as e:
            logger.error(f"提交验证任务失败: edge_id={edge_id}, error={e}")
            results.append({
                'success': False,
                'error': f'提交任务失败: {str(e)}',
                'error_type': 'TaskSubmissionFailed',
                'edge_id': edge_id
            })
    
    # 等待结果（带超时）
    for edge_id, future in futures:
        try:
            result = future.result(timeout=self.verification_timeout)
            results.append(result)
            
        except TimeoutError:
            logger.error(f"验证超时: edge_id={edge_id}, timeout={self.verification_timeout}s")
            results.append({
                'success': False,
                'error': f'验证超时（{self.verification_timeout}秒）',
                'error_type': 'TimeoutError',
                'edge_id': edge_id
            })
        
        except Exception as e:
            logger.error(f"验证执行失败: edge_id={edge_id}, error={e}", exc_info=True)
            results.append({
                'success': False,
                'error': f'验证执行失败: {str(e)}',
                'error_type': type(e).__name__,
                'edge_id': edge_id
            })
    
    return results
```

## 异常类型分类

### 1. 业务异常（预期内的异常）

| 异常类型 | 说明 | 处理策略 |
|---------|------|---------|
| `EdgeNotFound` | 边不存在 | 返回错误信息，记录warning |
| `InvalidDecision` | 无效的用户决策 | 返回错误信息 |
| `NoEvidence` | 未找到证据 | 返回空结果，记录info |
| `ConflictDetected` | 检测到冲突 | 返回冲突详情 |

### 2. 系统异常（技术问题）

| 异常类型 | 说明 | 处理策略 |
|---------|------|---------|
| `DatabaseError` | 数据库操作失败 | 记录error，返回错误信息 |
| `IndexNotInitialized` | 索引未初始化 | 记录error，初始化索引 |
| `TimeoutError` | 操作超时 | 记录error，返回超时信息 |
| `IOError` | 文件读写失败 | 记录error，返回错误信息 |

### 3. 意外异常（未预期的问题）

| 异常类型 | 说明 | 处理策略 |
|---------|------|---------|
| `UnexpectedError` | 未捕获的异常 | 记录critical，返回通用错误信息 |

## 日志记录规范

### 日志级别使用

```python
# DEBUG: 详细的调试信息
logger.debug(f"Layer {layer}搜索: {keyword}")

# INFO: 正常的业务流程
logger.info(f"验证完成: edge_id={edge_id}, status={status}")

# WARNING: 需要注意但不影响运行
logger.warning(f"边不存在: edge_id={edge_id}")

# ERROR: 错误但可以继续运行
logger.error(f"证据搜索失败: edge_id={edge_id}, error={e}")

# CRITICAL: 严重错误，系统可能无法继续运行
logger.critical(f"数据库连接失败: {db_path}", exc_info=True)
```

### 日志内容规范

```python
# ✅ 好的日志记录
logger.error(
    f"验证失败: edge_id={edge_id}, "
    f"source={source}, target={target}, "
    f"error_type={type(e).__name__}, error={str(e)}",
    exc_info=True  # 包含堆栈跟踪
)

# ❌ 不好的日志记录
logger.error(f"错误: {e}")  # 信息不足
```

## 错误信息返回格式

### 标准错误响应格式

```python
{
    'success': False,
    'error': '用户友好的错误信息',
    'error_type': 'ErrorType',
    'error_details': {  # 可选：详细错误信息
        'field': 'value',
        ...
    },
    # 相关上下文信息
    'edge_id': 123,
    'timestamp': '2026-03-11T10:30:00'
}
```

## 实施检查清单

### 对每个关键方法：

- [ ] 是否有try-except块包裹
- [ ] 是否区分了不同类型的异常
- [ ] 是否记录了详细的日志
- [ ] 是否返回了用户友好的错误信息
- [ ] 是否包含了错误类型字段
- [ ] 是否包含了相关上下文信息

## 测试验证

### 异常处理测试用例

```python
def test_error_handling():
    # 测试不存在的边
    result = engine.verify_knowledge(999)
    assert result['success'] == False
    assert 'error_type' in result
    
    # 测试无效决策
    result = engine.user_verify(1, 'invalid')
    assert result['success'] == False
    assert result['error_type'] == 'InvalidDecision'
    
    # 测试超时
    result = query_engine._async_verify_batch([1, 2, 3])
    # 应该返回结果，不应该抛出异常
```

## 性能考虑

### 异常处理性能优化

1. **避免过度捕获** - 只捕获预期的异常
2. **快速失败** - 发现问题立即返回
3. **延迟日志** - 只在需要时记录详细日志
4. **避免异常循环** - 异常处理中不要再抛出异常

```python
# ✅ 好的做法
try:
    result = do_something()
except ExpectedError as e:
    logger.error(f"预期错误: {e}")
    return {'success': False, 'error': str(e)}

# ❌ 不好的做法
try:
    result = do_something()
except Exception as e:  # 过度捕获
    logger.critical(f"严重错误: {e}")
    raise  # 重新抛出，影响性能
```

## 总结

通过这些改进，验证系统将具备：
- ✅ 更好的错误追踪能力
- ✅ 更友好的用户体验
- ✅ 更容易调试和排错
- ✅ 更稳定的运行表现

**建议**：逐步实施这些改进，优先处理关键路径的异常处理。
