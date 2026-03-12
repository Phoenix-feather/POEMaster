# 监控和日志系统设计

## 设计目标

1. **可观测性**：全面跟踪验证过程的每个环节
2. **可追溯性**：所有决策都有完整的证据链记录
3. **可调试性**：快速定位验证失败的原因
4. **性能监控**：识别性能瓶颈，优化验证流程

## 日志系统架构

### 日志层次结构

```
logs/
├── verification/
│   ├── verification.log           # 验证过程日志
│   ├── pob_search.log            # POB代码搜索日志
│   ├── evidence_eval.log         # 证据评估日志
│   └── conflict_resolution.log   # 冲突解决日志
├── system/
│   ├── knowledge_update.log      # 知识库更新日志
│   ├── graph_changes.log         # 图结构变更日志
│   └── performance.log           # 性能监控日志
└── user/
    ├── user_decisions.log        # 用户决策日志
    └── batch_operations.log      # 批量操作日志
```

### 日志格式标准

```python
import logging
import json
from datetime import datetime

class StructuredLogger:
    """结构化日志记录器"""
    
    def __init__(self, name, log_file):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        
        # JSON格式处理器
        handler = logging.FileHandler(log_file)
        handler.setFormatter(JSONFormatter())
        self.logger.addHandler(handler)
    
    def log_verification(self, knowledge_id, event, details):
        """记录验证事件"""
        self.logger.info('', extra={
            'timestamp': datetime.now().isoformat(),
            'knowledge_id': knowledge_id,
            'event': event,
            'details': details
        })

# 示例日志条目
{
    "timestamp": "2026-03-11T10:30:45.123456",
    "level": "INFO",
    "knowledge_id": "k001",
    "event": "verification_started",
    "details": {
        "subject": "FireSpell",
        "predicate": "implies",
        "object": "damage_type:fire",
        "verification_type": "auto",
        "min_evidence_strength": 0.8
    }
}
```

### 日志级别规范

| 级别 | 使用场景 | 示例 |
|------|----------|------|
| DEBUG | 详细调试信息 | POB代码搜索的每一步 |
| INFO | 正常操作记录 | 验证开始、完成、状态变更 |
| WARNING | 需要注意但不影响运行 | 证据强度低于预期、冲突检测 |
| ERROR | 操作失败但可恢复 | POB文件解析失败、数据库写入失败 |
| CRITICAL | 严重错误影响系统运行 | 知识库损坏、配置丢失 |

## 监控指标

### 1. 验证性能指标

```python
class VerificationMetrics:
    """验证性能指标收集器"""
    
    def __init__(self):
        self.metrics = {
            'verification_time': [],          # 验证耗时
            'evidence_search_time': [],        # 证据搜索耗时
            'auto_verification_rate': 0,       # 自动验证成功率
            'pending_knowledge_count': 0,      # 待确认知识数量
            'conflict_count': 0,               # 冲突数量
        }
    
    def record_verification(self, knowledge_id, duration, result):
        """记录单次验证"""
        self.metrics['verification_time'].append({
            'knowledge_id': knowledge_id,
            'duration': duration,
            'result': result,
            'timestamp': datetime.now()
        })
        
        # 更新统计
        self.update_statistics()
    
    def get_performance_report(self):
        """生成性能报告"""
        times = [v['duration'] for v in self.metrics['verification_time']]
        
        return {
            'total_verifications': len(times),
            'avg_duration': sum(times) / len(times) if times else 0,
            'max_duration': max(times) if times else 0,
            'min_duration': min(times) if times else 0,
            'p95_duration': self.percentile(times, 95),
            'auto_verification_rate': self.metrics['auto_verification_rate'],
            'pending_count': self.metrics['pending_knowledge_count']
        }
```

### 2. 知识质量指标

```python
class KnowledgeQualityMetrics:
    """知识质量指标"""
    
    def calculate_metrics(self, knowledge_base):
        """计算知识库质量指标"""
        
        total = knowledge_base.count_all()
        verified = knowledge_base.count_by_status('verified')
        pending = knowledge_base.count_by_status('pending')
        hypothesis = knowledge_base.count_by_status('hypothesis')
        rejected = knowledge_base.count_by_status('rejected')
        
        return {
            'total_knowledge': total,
            'status_distribution': {
                'verified': verified / total,
                'pending': pending / total,
                'hypothesis': hypothesis / total,
                'rejected': rejected / total
            },
            'average_confidence': self.calculate_average_confidence(knowledge_base),
            'average_evidence_strength': self.calculate_avg_evidence(knowledge_base),
            'coverage_score': self.calculate_coverage(knowledge_base),
            'freshness_score': self.calculate_freshness(knowledge_base)
        }
    
    def calculate_coverage(self, knowledge_base):
        """计算知识覆盖度"""
        # 基于POB数据覆盖范围
        expected_entities = self.get_expected_entity_count()
        covered_entities = knowledge_base.get_covered_entities()
        
        return len(covered_entities) / expected_entities
    
    def calculate_freshness(self, knowledge_base):
        """计算知识新鲜度"""
        # 基于最后验证时间
        all_knowledge = knowledge_base.get_all()
        
        freshness_scores = []
        for k in all_knowledge:
            age_days = (datetime.now() - k.last_verified).days
            # 指数衰减：30天半衰期
            freshness = 2 ** (-age_days / 30)
            freshness_scores.append(freshness)
        
        return sum(freshness_scores) / len(freshness_scores)
```

### 3. 系统健康指标

```python
class SystemHealthMetrics:
    """系统健康指标"""
    
    def check_health(self):
        """系统健康检查"""
        
        return {
            'database': self.check_database_health(),
            'pob_data': self.check_pob_data_health(),
            'cache': self.check_cache_health(),
            'logs': self.check_logs_health()
        }
    
    def check_database_health(self):
        """数据库健康检查"""
        try:
            # 检查数据库完整性
            entities_ok = self.verify_table_integrity('entities')
            rules_ok = self.verify_table_integrity('rules')
            graph_ok = self.verify_table_integrity('graph')
            
            return {
                'status': 'healthy' if all([entities_ok, rules_ok, graph_ok]) else 'degraded',
                'entities_integrity': entities_ok,
                'rules_integrity': rules_ok,
                'graph_integrity': graph_ok,
                'size_mb': self.get_database_size()
            }
        except Exception as e:
            return {'status': 'unhealthy', 'error': str(e)}
    
    def check_pob_data_health(self):
        """POB数据健康检查"""
        return {
            'status': 'healthy',
            'version': self.get_pob_version(),
            'last_update': self.get_pob_last_update(),
            'file_count': self.count_pob_files(),
            'data_hash': self.calculate_data_hash()
        }
```

## 监控仪表板

### 实时监控仪表板

```
┌─────────────────────────────────────────────────────────────────┐
│  POEMaster 监控仪表板                            2026-03-11 10:30│
├─────────────────────────────────────────────────────────────────┤
│  系统状态: ● HEALTHY                                           │
│                                                                  │
│  ━━━ 验证性能 (最近24小时) ━━━                                 │
│  总验证数: 45        平均耗时: 0.8s        成功率: 89%          │
│  [━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━] P95: 2.3s            │
│                                                                  │
│  ━━━ 知识质量 ━━━                                              │
│  ┌────────────┬────────────┬────────────┬────────────┐         │
│  │  已验证     │  待确认     │  假设       │  已拒绝     │         │
│  │   142      │    23      │    8       │    5        │         │
│  │  (79.8%)   │  (12.9%)   │  (4.5%)    │  (2.8%)     │         │
│  └────────────┴────────────┴────────────┴────────────┘         │
│  平均置信度: 0.85    平均证据强度: 0.82    知识覆盖度: 76%       │
│                                                                  │
│  ━━━ 系统资源 ━━━                                              │
│  CPU: [████░░░░░░] 42%    内存: [██████░░░░] 62%               │
│  磁盘: 1.2GB / 10GB    缓存命中率: 78%                          │
│                                                                  │
│  ━━━ 最近事件 ━━━                                              │
│  10:29:45  ✓ 自动验证完成: FireSpell → damage_type:fire        │
│  10:28:32  ⚠ 冲突检测: CoC能量生成规则                         │
│  10:25:10  ✓ 用户确认: TrailOfCaltropsPlayer → no_energy       │
│                                                                  │
│  [查看详细报告] [导出指标] [配置告警]                            │
└─────────────────────────────────────────────────────────────────┘
```

### 性能趋势图

```
验证耗时趋势 (最近7天)
  3.0s ┤                         ╭─╮
  2.5s ┤                   ╭────╯  ╰──╮
  2.0s ┤             ╭────╯            ╰──╮
  1.5s ┤       ╭────╯                      ╰─╮
  1.0s ┤ ╭───╯                                ╰─
  0.5s ┤─╯
      └──┬──────┬──────┬──────┬──────┬──────┬──────┬──
       03-05  03-06  03-07  03-08  03-09  03-10  03-11

知识质量趋势 (最近30天)
  100% ┤━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 覆盖度
   90% ┤                ╭─────────────────────── 置信度
   80% ┤        ╭──────╯
   70% ┤  ╭────╯
   60% ┤──╯
      └──┬──────────┬──────────┬──────────┬────────
       02-10     02-17     02-24     03-03
```

## 日志分析工具

### 1. 验证失败分析器

```python
class VerificationFailureAnalyzer:
    """分析验证失败原因"""
    
    def analyze_failures(self, log_file, time_range):
        """分析指定时间范围内的失败"""
        
        failures = self.parse_failures(log_file, time_range)
        
        # 分类失败原因
        failure_types = {
            'no_evidence': [],        # 未找到证据
            'weak_evidence': [],      # 证据强度不足
            'conflict': [],           # 存在冲突
            'parse_error': [],        # POB代码解析错误
            'other': []
        }
        
        for failure in failures:
            category = self.categorize_failure(failure)
            failure_types[category].append(failure)
        
        return {
            'total_failures': len(failures),
            'by_type': failure_types,
            'common_patterns': self.find_common_patterns(failures),
            'recommendations': self.generate_recommendations(failure_types)
        }
    
    def generate_recommendations(self, failure_types):
        """生成改进建议"""
        recommendations = []
        
        if len(failure_types['no_evidence']) > 5:
            recommendations.append({
                'issue': '多条知识缺少证据',
                'suggestion': '检查POB数据覆盖范围或调整证据搜索策略'
            })
        
        if len(failure_types['parse_error']) > 3:
            recommendations.append({
                'issue': '频繁的解析错误',
                'suggestion': '更新POB代码解析器以适配最新语法'
            })
        
        return recommendations
```

### 2. 性能瓶颈分析器

```python
class PerformanceBottleneckAnalyzer:
    """分析性能瓶颈"""
    
    def analyze_bottlenecks(self, metrics):
        """识别性能瓶颈"""
        
        bottlenecks = []
        
        # 分析验证耗时分布
        if metrics['p95_duration'] > 5.0:
            bottlenecks.append({
                'type': 'slow_verification',
                'description': f"P95验证耗时 {metrics['p95_duration']:.1f}s 超过阈值",
                'impact': 'high',
                'suggestion': '优化证据搜索算法或增加缓存'
            })
        
        # 分析自动验证率
        if metrics['auto_verification_rate'] < 0.7:
            bottlenecks.append({
                'type': 'low_auto_rate',
                'description': f"自动验证率 {metrics['auto_verification_rate']:.1%} 低于目标",
                'impact': 'medium',
                'suggestion': '降低证据强度阈值或改进证据评估模型'
            })
        
        return bottlenecks
```

## 告警系统

### 告警规则配置

```yaml
# config/alert_rules.yaml

alerts:
  # 性能告警
  - name: slow_verification
    condition: "p95_verification_time > 5.0s"
    severity: warning
    message: "验证性能下降，P95耗时超过5秒"
    
  - name: low_auto_rate
    condition: "auto_verification_rate < 0.7"
    severity: warning
    message: "自动验证率低于70%"
  
  # 质量告警
  - name: high_pending_rate
    condition: "pending_rate > 0.2"
    severity: warning
    message: "待确认知识比例超过20%"
    
  - name: knowledge_conflict
    condition: "conflict_count > 5"
    severity: error
    message: "检测到{conflict_count}个知识冲突"
  
  # 系统告警
  - name: database_unhealthy
    condition: "database_status != 'healthy'"
    severity: critical
    message: "数据库健康状态异常"
    
  - name: pob_data_outdated
    condition: "pob_data_age_days > 30"
    severity: warning
    message: "POB数据已超过30天未更新"

# 通知渠道
notification_channels:
  - type: log
    path: logs/alerts.log
    
  - type: email
    recipients: ['admin@example.com']
    severity: [critical]
  
  - type: webhook
    url: 'https://hooks.example.com/alert'
    severity: [critical, error]
```

### 告警处理器

```python
class AlertHandler:
    """告警处理器"""
    
    def __init__(self, rules_file, notification_channels):
        self.rules = self.load_rules(rules_file)
        self.channels = notification_channels
        self.alert_history = []
    
    def check_alerts(self, metrics):
        """检查是否触发告警"""
        
        triggered_alerts = []
        
        for rule in self.rules:
            if self.evaluate_condition(rule['condition'], metrics):
                alert = {
                    'name': rule['name'],
                    'severity': rule['severity'],
                    'message': rule['message'].format(**metrics),
                    'timestamp': datetime.now(),
                    'metrics': metrics
                }
                triggered_alerts.append(alert)
                self.send_notification(alert)
        
        self.alert_history.extend(triggered_alerts)
        return triggered_alerts
    
    def send_notification(self, alert):
        """发送告警通知"""
        
        for channel in self.channels:
            if alert['severity'] in channel['severity']:
                if channel['type'] == 'log':
                    self.log_alert(alert, channel['path'])
                elif channel['type'] == 'email':
                    self.send_email(alert, channel['recipients'])
                elif channel['type'] == 'webhook':
                    self.send_webhook(alert, channel['url'])
```

## 审计追踪

### 用户操作审计

```python
class AuditLogger:
    """审计日志记录器"""
    
    def log_user_action(self, user_id, action, details):
        """记录用户操作"""
        
        audit_entry = {
            'timestamp': datetime.now().isoformat(),
            'user_id': user_id,
            'action': action,
            'details': details,
            'session_id': self.get_session_id(),
            'ip_address': self.get_client_ip()
        }
        
        self.write_audit_log(audit_entry)
    
    def log_knowledge_change(self, knowledge_id, change_type, before, after, user_id):
        """记录知识变更"""
        
        self.log_user_action(
            user_id=user_id,
            action='knowledge_change',
            details={
                'knowledge_id': knowledge_id,
                'change_type': change_type,
                'before': before,
                'after': after,
                'reason': after.get('reason', 'N/A')
            }
        )
```

### 系统变更审计

```python
class SystemAuditLogger:
    """系统变更审计"""
    
    def log_system_change(self, change_type, details):
        """记录系统级变更"""
        
        entry = {
            'timestamp': datetime.now().isoformat(),
            'change_type': change_type,
            'details': details,
            'initiated_by': 'system',
            'version': self.get_system_version()
        }
        
        self.write_audit_log(entry)
    
    def log_pob_data_update(self, old_version, new_version, changes):
        """记录POB数据更新"""
        
        self.log_system_change(
            change_type='pob_data_update',
            details={
                'old_version': old_version,
                'new_version': new_version,
                'files_changed': len(changes['modified']),
                'files_added': len(changes['added']),
                'files_removed': len(changes['removed'])
            }
        )
```

## 报告生成

### 定期报告

```python
class ReportGenerator:
    """报告生成器"""
    
    def generate_weekly_report(self):
        """生成周报告"""
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)
        
        # 收集数据
        verification_stats = self.get_verification_stats(start_date, end_date)
        quality_stats = self.get_quality_stats(end_date)
        performance_stats = self.get_performance_stats(start_date, end_date)
        
        report = {
            'period': f"{start_date.date()} - {end_date.date()}",
            'verification': {
                'total': verification_stats['total'],
                'auto_verified': verification_stats['auto_verified'],
                'user_verified': verification_stats['user_verified'],
                'rejected': verification_stats['rejected'],
                'success_rate': verification_stats['success_rate']
            },
            'quality': {
                'status_distribution': quality_stats['status_distribution'],
                'avg_confidence': quality_stats['avg_confidence'],
                'avg_evidence_strength': quality_stats['avg_evidence_strength'],
                'coverage': quality_stats['coverage']
            },
            'performance': {
                'avg_verification_time': performance_stats['avg_time'],
                'p95_verification_time': performance_stats['p95_time'],
                'throughput': performance_stats['throughput']
            },
            'highlights': self.generate_highlights(verification_stats, quality_stats),
            'issues': self.identify_issues(performance_stats, quality_stats),
            'recommendations': self.generate_recommendations()
        }
        
        return report
```

### 报告模板

```markdown
# POEMaster 周报告
## 报告周期: 2026-03-04 - 2026-03-11

### 📊 验证统计
- 总验证数: 45
- 自动验证: 38 (84%)
- 用户验证: 5 (11%)
- 已拒绝: 2 (4%)
- 成功率: 89%

### 🎯 知识质量
- 已验证: 142 (79.8%)
- 待确认: 23 (12.9%)
- 假设: 8 (4.5%)
- 已拒绝: 5 (2.8%)
- 平均置信度: 0.85
- 平均证据强度: 0.82
- 知识覆盖度: 76%

### ⚡ 性能表现
- 平均验证耗时: 0.8s
- P95验证耗时: 2.3s
- 吞吐量: 6.4次/小时

### 🌟 亮点
- 自动验证率提升至84%（上周76%）
- 平均证据强度从0.78提升至0.82
- 新增15条类型-属性关系知识

### ⚠️ 问题
- 2条知识因缺少证据被拒绝
- 3个冲突待处理

### 💡 建议
1. 继续优化证据搜索算法，提高自动验证率
2. 处理待确认知识队列中的高优先级项
3. 解决检测到的知识冲突
```

## 最佳实践

### 1. 日志管理

- 按日期轮转日志文件
- 压缩超过7天的日志
- 保留最近30天的日志供查询
- 归档超过90天的日志到冷存储

### 2. 监控配置

- 生产环境：INFO级别日志，启用性能监控
- 开发环境：DEBUG级别日志，关闭性能监控
- 测试环境：DEBUG级别日志，启用完整审计

### 3. 告警响应

- Critical告警：立即响应，30分钟内处理
- Error告警：2小时内响应
- Warning告警：24小时内处理

### 4. 定期维护

- 每日：检查告警日志，处理异常
- 每周：生成报告，分析趋势
- 每月：清理旧日志，优化性能
- 每季度：审查监控策略，更新告警规则
