# 测试策略设计

## 测试目标

1. **正确性**：验证逻辑、证据评估、冲突解决等核心功能正确
2. **完整性**：覆盖所有关键路径和边界情况
3. **可靠性**：系统在各种异常情况下保持稳定
4. **性能**：满足性能指标要求

## 测试层次架构

```
┌─────────────────────────────────────────────────┐
│              E2E 集成测试 (端到端)               │
├─────────────────────────────────────────────────┤
│           系统测试 (API + 工作流)                │
├─────────────────────────────────────────────────┤
│         集成测试 (模块间交互)                    │
├─────────────────────────────────────────────────┤
│           单元测试 (函数级别)                    │
└─────────────────────────────────────────────────┘
```

## 单元测试

### 1. 证据搜索测试

```python
import pytest
from unittest.mock import Mock, patch
from verification.pob_searcher import POBCodeSearcher

class TestPOBCodeSearcher:
    """POB代码搜索器测试"""
    
    @pytest.fixture
    def searcher(self):
        """创建搜索器实例"""
        return POBCodeSearcher(pob_data_path='test_data/POBData')
    
    # ========== Layer 1: 显式stat测试 ==========
    
    def test_search_explicit_stat_found(self, searcher):
        """测试找到显式stat定义"""
        result = searcher.search_stat_definition('FireDamage')
        
        assert result['found'] == True
        assert result['layer'] == 1
        assert 'StatDescriptions/Fire.lua' in result['source']
        assert result['strength'] == 1.0
    
    def test_search_explicit_stat_not_found(self, searcher):
        """测试未找到显式stat定义"""
        result = searcher.search_stat_definition('NonExistentStat')
        
        assert result['found'] == False
        assert result['layer'] == 0
    
    def test_search_explicit_stat_with_modifiers(self, searcher):
        """测试带修饰符的stat搜索"""
        result = searcher.search_stat_definition('FireDamage', modifiers=['more', 'inc'])
        
        assert result['found'] == True
        assert len(result['variants']) >= 2  # Should find FireDamageMore, FireDamageInc
    
    # ========== Layer 2: 代码逻辑测试 ==========
    
    def test_search_skilltype_constraint_explicit(self, searcher):
        """测试找到显式类型约束"""
        result = searcher.search_skilltype_constraint('FireSpell')
        
        assert result['found'] == True
        assert 'CalcOffence.lua' in result['source']
        assert result['strength'] == 0.8
    
    def test_search_skilltype_constraint_inferred(self, searcher):
        """测试推断的类型约束"""
        result = searcher.search_skilltype_constraint('CustomType')
        
        # 应该通过模式匹配找到相关代码
        assert result['found'] == True
        assert result['strength'] == 0.6  # 推断的强度较低
    
    def test_search_calc_logic(self, searcher):
        """测试计算逻辑搜索"""
        result = searcher.search_calc_logic('energy_generation', 'CoC')
        
        assert result['found'] == True
        assert 'CalcTriggers.lua' in result['source']
        assert 'function' in result['code_snippet']
    
    # ========== Layer 3: 语义推断测试 ==========
    
    def test_semantic_inference_naming_convention(self, searcher):
        """测试命名约定推断"""
        result = searcher.semantic_inference('FireSpell', 'damage_type:fire')
        
        assert result['inferred'] == True
        assert result['reason'] == 'naming_convention'
        assert result['strength'] == 0.5
    
    def test_semantic_inference_co_occurrence(self, searcher):
        """测试共现关系推断"""
        result = searcher.semantic_inference('ColdSpell', 'damage_type:cold')
        
        assert result['inferred'] == True
        assert result['reason'] == 'co_occurrence'
    
    def test_semantic_inference_no_match(self, searcher):
        """测试无法推断的情况"""
        result = searcher.semantic_inference('RandomEntity', 'random_property')
        
        assert result['inferred'] == False
        assert result['strength'] == 0.0
```

### 2. 证据评估测试

```python
class TestEvidenceEvaluator:
    """证据评估器测试"""
    
    @pytest.fixture
    def evaluator(self):
        return EvidenceEvaluator()
    
    def test_evaluate_single_strong_evidence(self, evaluator):
        """测试单个强证据"""
        evidence = [
            {'type': 'explicit_stat', 'strength': 1.0, 'source': 'StatDescriptions/Fire.lua'}
        ]
        
        result = evaluator.evaluate(evidence)
        
        assert result['overall_strength'] == 1.0
        assert result['recommendation'] == 'accept'
    
    def test_evaluate_multiple_evidence(self, evaluator):
        """测试多个证据组合"""
        evidence = [
            {'type': 'explicit_stat', 'strength': 1.0, 'source': 'StatDescriptions/Fire.lua'},
            {'type': 'code_logic', 'strength': 0.8, 'source': 'CalcOffence.lua'},
            {'type': 'pattern', 'strength': 0.7, 'source': 'naming_convention'}
        ]
        
        result = evaluator.evaluate(evidence)
        
        # 综合强度应该是加权平均
        expected = (1.0 * 0.4 + 0.8 * 0.3 + 0.7 * 0.2) / (0.4 + 0.3 + 0.2)
        assert abs(result['overall_strength'] - expected) < 0.01
        assert result['recommendation'] == 'accept'
    
    def test_evaluate_weak_evidence(self, evaluator):
        """测试弱证据情况"""
        evidence = [
            {'type': 'semantic_inference', 'strength': 0.3, 'source': 'guess'}
        ]
        
        result = evaluator.evaluate(evidence)
        
        assert result['overall_strength'] < 0.5
        assert result['recommendation'] == 'reject'
    
    def test_evaluate_conflicting_evidence(self, evaluator):
        """测试冲突证据"""
        evidence = [
            {'type': 'explicit_stat', 'strength': 1.0, 'source': 'Calc.lua:100', 'value': 'true'},
            {'type': 'explicit_stat', 'strength': 1.0, 'source': 'Calc.lua:200', 'value': 'false'}
        ]
        
        result = evaluator.evaluate(evidence)
        
        assert result['has_conflict'] == True
        assert result['recommendation'] == 'review'
```

### 3. 冲突检测测试

```python
class TestConflictDetector:
    """冲突检测器测试"""
    
    @pytest.fixture
    def detector(self):
        return ConflictDetector()
    
    def test_detect_direct_contradiction(self, detector):
        """测试直接矛盾检测"""
        k1 = Knowledge(
            id='k1',
            subject='CoC',
            predicate='consumes_energy',
            object='true',
            status='verified'
        )
        
        k2 = Knowledge(
            id='k2',
            subject='CoC',
            predicate='consumes_energy',
            object='false',
            status='pending'
        )
        
        conflict = detector.detect_conflict(k1, k2)
        
        assert conflict is not None
        assert conflict['type'] == 'direct_contradiction'
        assert conflict['severity'] == 'high'
    
    def test_detect_inference_conflict(self, detector):
        """测试推断冲突检测"""
        k1 = Knowledge(
            id='k1',
            subject='Fireball',
            predicate='has_tag',
            object='melee',
            status='verified'
        )
        
        k2 = Knowledge(
            id='k2',
            subject='Fireball',
            predicate='has_tag',
            object='spell',
            status='verified'
        )
        
        # 如果系统知道 melee 和 spell 互斥
        conflict = detector.detect_conflict(k1, k2, knowledge_base=mock_kb)
        
        assert conflict is not None
        assert conflict['type'] == 'inference_conflict'
    
    def test_no_conflict_compatible(self, detector):
        """测试兼容知识不产生冲突"""
        k1 = Knowledge(
            id='k1',
            subject='Fireball',
            predicate='damage_type',
            object='fire'
        )
        
        k2 = Knowledge(
            id='k2',
            subject='Fireball',
            predicate='cast_time',
            object='0.75'
        )
        
        conflict = detector.detect_conflict(k1, k2)
        
        assert conflict is None
```

### 4. 模式发现测试

```python
class TestPatternDiscoverer:
    """模式发现器测试"""
    
    @pytest.fixture
    def discoverer(self):
        return PatternDiscoverer()
    
    def test_discover_type_property_pattern(self, discoverer):
        """测试类型-属性模式发现"""
        entities = [
            {'name': 'Fireball', 'tags': ['spell', 'fire']},
            {'name': 'Firestorm', 'tags': ['spell', 'fire']},
            {'name': 'MagmaOrb', 'tags': ['spell', 'fire']},
        ]
        
        patterns = discoverer.discover_type_property_patterns(entities)
        
        # 应该发现 "spell + fire => fire damage" 模式
        assert any(
            p['pattern'] == 'spell+fire=>fire_damage' 
            for p in patterns
        )
    
    def test_discover_causal_pattern(self, discoverer):
        """测试因果模式发现"""
        rules = [
            {'trigger': 'CoC', 'action': 'cast', 'result': 'energy_cost'},
            {'trigger': 'Mjolner', 'action': 'cast', 'result': 'energy_cost'},
        ]
        
        patterns = discoverer.discover_causal_patterns(rules)
        
        # 应该发现 "trigger_cast => energy_cost" 模式
        assert len(patterns) > 0
        assert any('trigger' in p['pattern'] for p in patterns)
    
    def test_discover_bypass_pattern(self, discoverer):
        """测试绕过模式发现"""
        entities = [
            {
                'name': 'TrailOfCaltropsPlayer',
                'trigger_type': 'generic_ongoing',
                'energy_cost': 0,
                'special_stat': 'generic_ongoing_trigger_does_not_use_energy'
            }
        ]
        
        patterns = discoverer.discover_bypass_patterns(entities)
        
        # 应该发现 "generic_ongoing_trigger_does_not_use_energy => no_energy" 模式
        assert any(
            'no_energy' in p['pattern'] 
            for p in patterns
        )
```

## 集成测试

### 1. 验证流程集成测试

```python
class TestVerificationWorkflow:
    """验证工作流集成测试"""
    
    @pytest.fixture
    def verification_system(self):
        """创建完整验证系统"""
        return VerificationSystem(
            pob_data_path='test_data/POBData',
            knowledge_base_path='test_data/knowledge_base'
        )
    
    def test_auto_verification_flow(self, verification_system):
        """测试自动验证流程"""
        # 创建待验证知识
        knowledge = Knowledge(
            id='test_001',
            subject='FireSpell',
            predicate='implies',
            object='damage_type:fire',
            status='pending'
        )
        
        # 执行验证
        result = verification_system.verify(knowledge)
        
        # 验证结果
        assert result['status'] == 'verified'
        assert result['evidence_strength'] >= 0.8
        assert len(result['evidence_chain']) > 0
        
        # 验证知识库更新
        stored = verification_system.knowledge_base.get('test_001')
        assert stored['status'] == 'verified'
        assert stored['last_verified'] is not None
    
    def test_manual_verification_flow(self, verification_system):
        """测试人工验证流程"""
        knowledge = Knowledge(
            id='test_002',
            subject='CustomEntity',
            predicate='has_property',
            object='custom_value',
            status='pending'
        )
        
        result = verification_system.verify(knowledge)
        
        # 证据不足，需要人工确认
        assert result['status'] == 'pending'
        assert result['needs_user_confirmation'] == True
        
        # 模拟用户确认
        verification_system.user_confirm(
            knowledge_id='test_002',
            decision='accept',
            reason='User verified through gameplay'
        )
        
        stored = verification_system.knowledge_base.get('test_002')
        assert stored['status'] == 'verified'
        assert stored['verified_by'] == 'user'
    
    def test_conflict_resolution_flow(self, verification_system):
        """测试冲突解决流程"""
        # 已有验证知识
        existing = Knowledge(
            id='existing_001',
            subject='CoC',
            predicate='energy_cost',
            object='10',
            status='verified'
        )
        verification_system.knowledge_base.add(existing)
        
        # 新知识产生冲突
        new_knowledge = Knowledge(
            id='new_001',
            subject='CoC',
            predicate='energy_cost',
            object='0',
            status='pending'
        )
        
        result = verification_system.verify(new_knowledge)
        
        # 应该检测到冲突
        assert result['has_conflict'] == True
        assert result['conflict_with'] == 'existing_001'
        
        # 冲突解决
        verification_system.resolve_conflict(
            conflict_id=result['conflict_id'],
            resolution='update_existing',
            reason='Game mechanic changed in new patch'
        )
        
        # 验证解决结果
        old = verification_system.knowledge_base.get('existing_001')
        new = verification_system.knowledge_base.get('new_001')
        
        assert old['status'] == 'rejected'
        assert new['status'] == 'verified'
```

### 2. 知识演化集成测试

```python
class TestKnowledgeEvolution:
    """知识演化集成测试"""
    
    @pytest.fixture
    def evolution_system(self):
        return KnowledgeEvolutionSystem()
    
    def test_incremental_update(self, evolution_system):
        """测试增量更新"""
        # 模拟POB数据变更
        changes = {
            'type': 'incremental',
            'files_modified': ['Data/Skills/act_int.lua'],
            'entities_changed': ['NewSkill1', 'NewSkill2']
        }
        
        # 执行演化
        result = evolution_system.evolve(changes)
        
        assert result['strategy'] == 'incremental'
        assert result['entities_added'] == 2
        assert result['knowledge_verified'] > 0
    
    def test_selective_update_preserve_user_knowledge(self, evolution_system):
        """测试选择性更新保留用户知识"""
        # 添加用户验证的知识
        user_knowledge = Knowledge(
            id='user_001',
            subject='CustomRule',
            predicate='custom_predicate',
            object='custom_value',
            status='verified',
            verified_by='user'
        )
        evolution_system.knowledge_base.add(user_knowledge)
        
        # 模拟较大变更
        changes = {
            'type': 'major',
            'change_percentage': 0.15
        }
        
        result = evolution_system.evolve(changes)
        
        assert result['strategy'] == 'selective'
        # 用户知识应该被保留
        preserved = result['preserved_knowledge']
        assert 'user_001' in preserved
```

## 系统测试

### 1. API接口测试

```python
class TestVerificationAPI:
    """验证API测试"""
    
    @pytest.fixture
    def client(self):
        app = create_app(testing=True)
        return app.test_client()
    
    def test_list_pending_knowledge(self, client):
        """测试列出待确认知识"""
        response = client.get('/api/v1/knowledge?status=pending')
        
        assert response.status_code == 200
        data = response.get_json()
        
        assert 'total' in data
        assert 'items' in data
        assert all(item['status'] == 'pending' for item in data['items'])
    
    def test_verify_knowledge(self, client):
        """测试验证知识"""
        payload = {
            'decision': 'accept',
            'reason': 'POB code verified',
            'evidence_reference': 'CalcTriggers.lua:123'
        }
        
        response = client.post('/api/v1/knowledge/k001/verify', json=payload)
        
        assert response.status_code == 200
        data = response.get_json()
        
        assert data['status'] == 'verified'
        assert data['verified_at'] is not None
    
    def test_batch_verify(self, client):
        """测试批量验证"""
        payload = {
            'knowledge_ids': ['k001', 'k002', 'k003'],
            'decision': 'accept',
            'strategy': 'auto'
        }
        
        response = client.post('/api/v1/knowledge/batch-verify', json=payload)
        
        assert response.status_code == 200
        data = response.get_json()
        
        assert data['total_processed'] == 3
        assert data['accepted'] + data['rejected'] == 3
```

### 2. 性能测试

```python
class TestPerformance:
    """性能测试"""
    
    def test_single_verification_performance(self, verification_system):
        """测试单次验证性能"""
        knowledge = create_test_knowledge()
        
        start_time = time.time()
        result = verification_system.verify(knowledge)
        duration = time.time() - start_time
        
        assert result['status'] in ['verified', 'pending']
        assert duration < 1.0  # 单次验证应在1秒内完成
    
    def test_batch_verification_performance(self, verification_system):
        """测试批量验证性能"""
        knowledge_list = [create_test_knowledge() for _ in range(10)]
        
        start_time = time.time()
        results = verification_system.batch_verify(knowledge_list)
        duration = time.time() - start_time
        
        assert len(results) == 10
        assert duration < 5.0  # 10条知识批量验证应在5秒内完成
    
    def test_pob_search_cache_effectiveness(self, pob_searcher):
        """测试POB搜索缓存效果"""
        # 第一次搜索
        start1 = time.time()
        result1 = pob_searcher.search_stat_definition('FireDamage')
        time1 = time.time() - start1
        
        # 第二次相同搜索（应该命中缓存）
        start2 = time.time()
        result2 = pob_searcher.search_stat_definition('FireDamage')
        time2 = time.time() - start2
        
        assert result1 == result2
        assert time2 < time1 * 0.1  # 缓存应该快10倍以上
    
    def test_concurrent_verification(self, verification_system):
        """测试并发验证"""
        knowledge_list = [create_test_knowledge() for _ in range(20)]
        
        # 并发执行
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [
                executor.submit(verification_system.verify, k) 
                for k in knowledge_list
            ]
            results = [f.result() for f in futures]
        
        # 验证结果完整性
        assert len(results) == 20
        assert all(r['status'] in ['verified', 'pending', 'error'] for r in results)
```

### 3. 压力测试

```python
class TestStress:
    """压力测试"""
    
    def test_large_knowledge_base(self, verification_system):
        """测试大规模知识库"""
        # 创建10000条待验证知识
        large_knowledge_list = [
            create_test_knowledge(f'test_{i}') 
            for i in range(10000)
        ]
        
        # 批量验证
        results = verification_system.batch_verify(
            large_knowledge_list,
            batch_size=100
        )
        
        # 验证处理完整性
        assert len(results) == 10000
        assert verification_system.knowledge_base.count() >= 10000
    
    def test_memory_usage(self, verification_system):
        """测试内存使用"""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # 执行大规模验证
        for _ in range(1000):
            knowledge = create_test_knowledge()
            verification_system.verify(knowledge)
        
        final_memory = process.memory_info().rss / 1024 / 1024
        memory_increase = final_memory - initial_memory
        
        # 内存增长应控制在合理范围内 (<500MB)
        assert memory_increase < 500
```

## E2E测试

### 1. 完整验证场景

```python
class TestE2EVerification:
    """端到端验证测试"""
    
    @pytest.fixture
    def system(self):
        """创建完整系统"""
        return POEMasterSystem(
            pob_data_path='test_data/POBData',
            knowledge_base_path='test_data/knowledge_base'
        )
    
    def test_complete_verification_scenario(self, system):
        """测试完整验证场景"""
        
        # 1. 系统初始化
        assert system.is_healthy()
        
        # 2. 发现新知识（通过启发式推理）
        discoveries = system.discover_knowledge(limit=10)
        assert len(discoveries) > 0
        
        # 3. 自动验证
        auto_results = system.auto_verify_knowledge(discoveries)
        auto_verified = [r for r in auto_results if r['status'] == 'verified']
        pending = [r for r in auto_results if r['status'] == 'pending']
        
        # 4. 人工处理pending知识
        for p in pending[:3]:
            system.user_verify_knowledge(
                knowledge_id=p['knowledge_id'],
                decision='accept',
                reason='Test verification'
            )
        
        # 5. 验证知识库状态
        stats = system.get_knowledge_stats()
        assert stats['total'] > 0
        assert stats['verified_rate'] > 0.5
        
        # 6. 验证推理使用验证知识
        query_result = system.query('What skills deal fire damage?')
        assert len(query_result['results']) > 0
        assert all(r['confidence'] >= 0.5 for r in query_result['results'])
    
    def test_knowledge_evolution_scenario(self, system):
        """测试知识演化场景"""
        
        # 1. 记录初始状态
        initial_stats = system.get_knowledge_stats()
        
        # 2. 模拟POB数据更新
        system.simulate_pob_update(changes={
            'version': '0.4.1',
            'files_modified': ['Data/Skills/act_int.lua'],
            'entities_added': ['NewSpell1', 'NewSpell2'],
            'entities_removed': ['DeprecatedSkill']
        })
        
        # 3. 触发知识演化
        evolution_result = system.evolve_knowledge()
        
        # 4. 验证演化结果
        assert evolution_result['strategy'] in ['incremental', 'selective', 'full_rebuild']
        assert evolution_result['entities_added'] == 2
        
        # 5. 验证知识库一致性
        final_stats = system.get_knowledge_stats()
        assert final_stats['total'] >= initial_stats['total']
        assert system.check_integrity() == True
```

### 2. 用户交互场景

```python
class TestE2EUserInteraction:
    """端到端用户交互测试"""
    
    def test_user_workflow(self, system):
        """测试用户完整工作流"""
        
        # 1. 用户登录
        user = system.login(user_id='test_user')
        assert user.is_authenticated()
        
        # 2. 查看待确认知识
        pending = system.get_pending_knowledge(user_id='test_user')
        assert len(pending) > 0
        
        # 3. 批量处理
        batch_result = system.user_batch_process(
            user_id='test_user',
            knowledge_ids=[k['id'] for k in pending[:5]],
            action='accept',
            reason='Batch test'
        )
        assert batch_result['processed'] == 5
        
        # 4. 查看验证历史
        history = system.get_user_history(user_id='test_user')
        assert len(history) >= 5
        
        # 5. 导出报告
        report = system.generate_user_report(user_id='test_user')
        assert report['total_decisions'] >= 5
```

## 测试数据管理

### 测试数据生成器

```python
class TestDataGenerator:
    """测试数据生成器"""
    
    @staticmethod
    def generate_knowledge(count=100):
        """生成测试知识"""
        knowledge_list = []
        
        subjects = ['FireSpell', 'ColdSpell', 'LightningSpell', 'Attack', 'Melee']
        predicates = ['implies', 'has_property', 'causes', 'triggers']
        objects = ['fire_damage', 'cold_damage', 'cast_time', 'cooldown']
        
        for i in range(count):
            knowledge = Knowledge(
                id=f'test_{i}',
                subject=random.choice(subjects),
                predicate=random.choice(predicates),
                object=random.choice(objects),
                status=random.choice(['pending', 'verified', 'rejected']),
                evidence_strength=random.uniform(0.3, 1.0)
            )
            knowledge_list.append(knowledge)
        
        return knowledge_list
    
    @staticmethod
    def generate_pob_test_data(output_path):
        """生成测试用POB数据"""
        os.makedirs(output_path, exist_ok=True)
        
        # 生成简化版POB数据结构
        # Data/Skills/test_skill.lua
        # Data/StatDescriptions/test_stat.lua
        # Modules/CalcTest.lua
        ...
```

### 测试数据清理

```python
@pytest.fixture(autouse=True)
def cleanup_test_data():
    """自动清理测试数据"""
    yield
    
    # 清理测试数据库
    if os.path.exists('test_data/knowledge_base/test.db'):
        os.remove('test_data/knowledge_base/test.db')
    
    # 清理测试日志
    for log_file in glob.glob('test_logs/*.log'):
        os.remove(log_file)
```

## 测试覆盖率目标

| 测试类型 | 目标覆盖率 | 优先级 |
|---------|-----------|--------|
| 核心逻辑单元测试 | 90% | P0 |
| 集成测试 | 80% | P0 |
| API接口测试 | 100% | P1 |
| 性能测试 | 关键路径100% | P1 |
| E2E测试 | 核心场景100% | P1 |

## 持续集成配置

```yaml
# .github/workflows/test.yml

name: Test

on: [push, pull_request]

jobs:
  unit-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: 3.9
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-cov
      
      - name: Run unit tests
        run: |
          pytest tests/unit -v --cov=src --cov-report=xml
      
      - name: Upload coverage
        uses: codecov/codecov-action@v2
        with:
          file: ./coverage.xml
  
  integration-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: 3.9
      
      - name: Install dependencies
        run: pip install -r requirements.txt
      
      - name: Run integration tests
        run: pytest tests/integration -v
  
  performance-test:
    runs-on: ubuntu-latest
    if: github.event_name == 'pull_request'
    steps:
      - uses: actions/checkout@v2
      
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: 3.9
      
      - name: Run performance tests
        run: pytest tests/performance -v
      
      - name: Check performance thresholds
        run: python scripts/check_performance.py
```

## 测试最佳实践

### 1. 测试命名规范

```python
# 格式: test_<method>_<scenario>_<expected_result>

def test_verify_knowledge_with_strong_evidence_returns_verified():
    """测试有强证据的知识返回已验证状态"""
    pass

def test_verify_knowledge_with_weak_evidence_returns_pending():
    """测试弱证据的知识返回待确认状态"""
    pass

def test_verify_knowledge_with_conflict_returns_error():
    """测试有冲突的知识返回错误"""
    pass
```

### 2. 测试隔离

- 每个测试独立的fixture
- 不依赖外部服务
- 使用内存数据库
- 自动清理测试数据

### 3. 测试可读性

- 清晰的Given-When-Then结构
- 有意义的测试数据
- 充分的注释和文档

### 4. 测试维护

- 定期更新测试数据
- 重构时同步更新测试
- 监控测试覆盖率变化
- 定期审查测试有效性
