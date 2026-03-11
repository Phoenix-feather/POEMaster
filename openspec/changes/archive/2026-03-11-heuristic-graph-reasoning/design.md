# Design: 启发式关联图推理系统

## 架构设计

### 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                      启发式关联图架构                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │                  统一查询接口                               │ │
│  │  heuristic_reason.py                                       │ │
│  │  - query_bypass(constraint, mode='auto')                  │ │
│  │  - query_constraint_causes(constraint)                    │ │
│  │  - query_similar_entities(entity)                         │ │
│  └───────────────────────────────────────────────────────────┘ │
│                              │                                  │
│                              ▼                                  │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │                  三层推理能力                               │ │
│  │                                                             │ │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐         │ │
│  │  │ 查询能力    │ │ 发现能力    │ │ 扩散能力    │         │ │
│  │  │             │ │             │ │             │         │ │
│  │  │ 查询已知边  │ │ 从零推理    │ │ 类比发现    │         │ │
│  │  └─────────────┘ └─────────────┘ └─────────────┘         │ │
│  │                                                             │ │
│  │  heuristic_query.py   heuristic_discovery.py   heuristic_diffuse.py
│  └───────────────────────────────────────────────────────────┘ │
│                              │                                  │
│                              ▼                                  │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │                  关联图核心                                 │ │
│  │  graph.db + attribute_graph.py                            │ │
│  │                                                             │ │
│  │  节点类型：                                                 │ │
│  │  - entity, mechanism, attribute（现有）                     │ │
│  │  - type_node, property_node, trigger_mechanism（新增）     │ │
│  │                                                             │ │
│  │  边类型：                                                   │ │
│  │  - has_type, has_stat, requires, excludes, provides（现有）│ │
│  │  - implies, produces, prevents, bypasses, triggers_via（新增）│ │
│  └───────────────────────────────────────────────────────────┘ │
│                              │                                  │
│                              ▼                                  │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │                  配置层                                     │ │
│  │  config/edge_semantics.yaml                                │ │
│  │  - 定义边语义                                               │ │
│  │  - 定义推理规则                                             │ │
│  │  - 定义传递性                                               │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## 数据结构设计

### 节点类型扩展

```python
# attribute_graph.py

class NodeType(Enum):
    """节点类型"""
    
    # === 现有类型 ===
    ENTITY = "entity"              # 实体节点（技能、物品等）
    MECHANISM = "mechanism"        # 机制节点（skillTypes、效果等）
    ATTRIBUTE = "attribute"        # 属性节点（stats）
    CONSTRAINT = "constraint"      # 约束节点
    HEURISTIC = "heuristic"        # 启发节点
    
    # === 新增类型 ===
    TYPE_NODE = "type_node"        # 类型节点（如 Meta, Hazard, Triggered）
    PROPERTY_NODE = "property_node" # 属性节点（如 UsesEnergy, DoesNotUseEnergy）
    TRIGGER_MECHANISM = "trigger_mechanism"  # 触发机制节点（如 MetaTrigger, HazardTrigger）
```

### 边类型扩展

```python
# attribute_graph.py

class EdgeType(Enum):
    """边类型"""
    
    # === 现有类型 ===
    # 实例层
    HAS_TYPE = "has_type"          # 拥有类型
    HAS_STAT = "has_stat"          # 拥有属性
    REQUIRES = "requires"          # 需要
    EXCLUDES = "excludes"          # 排除
    PROVIDES = "provides"          # 提供
    
    # 预置边
    USES_FORMULA = "uses_formula"
    APPLIES = "applies"
    RESERVES = "reserves"
    
    # === 新增类型 ===
    # 类型层
    IMPLIES = "implies"            # 隐含关系（A 隐含 B）
    INCOMPATIBLE_WITH = "incompatible_with"  # 互斥关系
    
    # 触发层
    TRIGGERS_VIA = "triggers_via"  # 通过...触发
    PRODUCES = "produces"          # 产生（触发机制产生标签）
    CREATES = "creates"            # 创建（创建效果而非触发）
    
    # 功能层
    PREVENTS = "prevents"          # 阻止
    BYPASSES = "bypasses"          # 绕过
    CONSTRAINED_BY = "constrained_by"  # 受...约束
    ENABLES = "enables"            # 启用
```

### 图结构示例

```
完整的图结构（能量循环问题）：

节点：
  # === 实例层（entity） ===
  MetaCastOnCritPlayer
  SupportDoedresUndoingPlayer
  SpearfieldPlayer
  TrailOfCaltropsPlayer
  
  # === 类型层（type_node） ===
  Meta
  Triggers
  GeneratesEnergy
  Hazard
  Duration
  Triggered
  
  # === 属性层（property_node） ===
  UsesEnergySystem
  DoesNotUseEnergy
  CanGenerateEnergyForMeta
  
  # === 触发机制层（trigger_mechanism） ===
  MetaTrigger
  HazardTrigger
  CreationTrigger
  
  # === 约束层（constraint） ===
  EnergyCycleLimit

边：

  # === 实例层 ===
  MetaCastOnCritPlayer --[has_type]--> Meta
  MetaCastOnCritPlayer --[has_type]--> Triggers
  MetaCastOnCritPlayer --[has_type]--> GeneratesEnergy
  MetaCastOnCritPlayer --[triggers_via]--> MetaTrigger
  
  SupportDoedresUndoingPlayer --[creates]--> Hazard
  SupportDoedresUndoingPlayer --[triggers_via]--> CreationTrigger
  
  SpearfieldPlayer --[has_type]--> Hazard
  SpearfieldPlayer --[triggers_via]--> HazardTrigger
  
  TrailOfCaltropsPlayer --[has_type]--> Triggers
  TrailOfCaltropsPlayer --[has_stat]--> does_not_use_energy
  
  # === 类型层（隐含属性） ===
  Meta --[implies]--> UsesTriggerMechanism
  Meta + GeneratesEnergy --[implies]--> UsesEnergySystem
  Hazard --[implies]--> DoesNotUseEnergy
  Triggered --[implies]--> CannotGenerateEnergyForMeta
  
  # === 触发机制层 ===
  MetaTrigger --[produces]--> Triggered
  HazardTrigger --[does_not_produce]--> Triggered
  CreationTrigger --[does_not_produce]--> Triggered
  
  # === 约束层 ===
  UsesEnergySystem --[constrained_by]--> EnergyCycleLimit
  DoesNotUseEnergy --[bypasses]--> EnergyCycleLimit
```

## 边语义配置设计

```yaml
# config/edge_semantics.yaml

edge_types:
  # === 实例层边 ===
  has_type:
    direction: forward
    description: "实体拥有某个类型"
    transitive: false
    
  has_stat:
    direction: forward
    description: "实体拥有某个属性"
    transitive: false
    
  requires:
    direction: forward
    description: "需要某个类型"
    transitive: false
    
  excludes:
    direction: forward
    description: "排除某个类型"
    transitive: false
    
  provides:
    direction: forward
    description: "提供某个类型"
    transitive: false
    
  # === 类型层边（新增）===
  implies:
    direction: forward
    description: "隐含关系"
    transitive: true  # 可传递：A implies B, B implies C => A implies C
    inference: true   # 可用于推理
    
  incompatible_with:
    direction: bidirectional
    description: "互斥关系"
    transitive: false
    
  # === 触发层边（新增）===
  triggers_via:
    direction: forward
    description: "通过...触发"
    transitive: false
    
  produces:
    direction: forward
    description: "产生"
    transitive: false
    inference: true
    
  creates:
    direction: forward
    description: "创建"
    transitive: false
    
  # === 功能层边（新增）===
  prevents:
    direction: forward
    description: "阻止"
    transitive: false
    inference: true
    
  bypasses:
    direction: forward
    description: "绕过"
    transitive: false
    inference: true
    
  constrained_by:
    direction: forward
    description: "受...约束"
    transitive: false

# 推理规则（边组合产生新知识）
inference_rules:
  - name: "implies chain"
    description: "隐含关系可传递"
    pattern:
      - A --[implies]--> B
      - B --[implies]--> C
    conclusion:
      - A --[implies]--> C
      
  - name: "produces prevents"
    description: "产生阻止关系"
    pattern:
      - A --[produces]--> B
      - B --[prevents]--> C
    conclusion:
      - A --[blocks]--> C
      
  - name: "bypasses constrained"
    description: "绕过约束链"
    pattern:
      - A --[bypasses]--> B
      - C --[constrained_by]--> B
    conclusion:
      - A --[bypasses_constraint_of]--> C
```

## 核心算法设计

### 1. 发现算法

```python
# heuristic_discovery.py

class HeuristicDiscovery:
    """启发式发现能力"""
    
    def discover_bypass_paths(self, constraint: str) -> List[Dict]:
        """
        从零开始发现绕过某个约束的路径
        
        算法：
        1. 反向推理：分析约束的成因
        2. 反常检测：寻找不满足约束关键因素的实体
        3. 类比推理：分析反常实体的特征
        4. 假设验证：验证反常实体能否绕过
        5. 生成新边：如果验证通过，创建 bypasses 边
        """
        
        # Step 1: 反向推理
        causes = self.analyze_constraint_causes(constraint)
        
        # Step 2: 反常检测
        anomalies = self.find_anomalies(causes)
        
        # Step 3: 类比推理
        for anomaly in anomalies:
            features = self.extract_features(anomaly)
            
            # Step 4: 假设验证
            if self.verify_bypass(anomaly, constraint):
                # Step 5: 生成新边
                self.create_bypass_edge(anomaly, constraint)
        
        return self.get_discovered_bypasses()
    
    def analyze_constraint_causes(self, constraint: str) -> List[Dict]:
        """分析约束的成因（反向图遍历）"""
        
        # 找到所有指向约束的边
        incoming = self.graph.get_incoming_edges(constraint)
        
        causes = []
        for edge in incoming:
            # 追溯因果链
            causal_chain = self.trace_causal_chain(edge.source)
            causes.append({
                'source': edge.source,
                'chain': causal_chain,
                'key_factor': causal_chain[-1]
            })
        
        return causes
    
    def find_anomalies(self, causes: List[Dict]) -> List[str]:
        """寻找反常点（不满足关键因素的实体）"""
        
        anomalies = []
        
        for cause in causes:
            key_factor = cause['key_factor']
            
            # 统计大多数实体的模式
            normal_pattern = self.get_normal_pattern(key_factor)
            
            # 找到不符合模式的实体
            all_entities = self.graph.get_nodes_by_type(NodeType.ENTITY)
            
            for entity in all_entities:
                if not self.matches_pattern(entity, normal_pattern):
                    anomalies.append(entity)
        
        return anomalies
    
    def verify_bypass(self, entity: str, constraint: str) -> bool:
        """验证假设：entity 能否绕过 constraint"""
        
        # 获取约束的关键因素
        key_factors = self.get_constraint_key_factors(constraint)
        
        # 检查 entity 是否不满足关键因素
        for factor in key_factors:
            if self.has_factor(entity, factor):
                return False  # 满足关键因素，不能绕过
        
        # 收集证据
        evidence = self.gather_evidence(entity, constraint)
        
        return len(evidence) > 0
```

### 2. 扩散算法

```python
# heuristic_diffuse.py

class HeuristicDiffuse:
    """启发式扩散能力"""
    
    def diffuse_from_bypass(self, known_bypass_edge: Dict) -> List[Dict]:
        """
        从一条已知的绕过边，发现类似的绕过边
        
        算法：
        1. 提取已知绕过边的关键特征
        2. 寻找具有相似特征的实体
        3. 验证这些实体是否也能绕过
        4. 生成新的绕过边
        """
        
        source = known_bypass_edge['source']
        target = known_bypass_edge['target']
        
        # Step 1: 提取关键特征
        features = self.extract_key_features(source)
        
        # Step 2: 寻找相似实体
        similar_entities = self.find_similar_entities(features, exclude=[source])
        
        # Step 3 & 4: 验证并生成新边
        new_bypasses = []
        for entity in similar_entities:
            if self.verify_bypass(entity, target):
                edge = self.create_bypass_edge(entity, target)
                new_bypasses.append(edge)
        
        return new_bypasses
    
    def extract_key_features(self, entity: str) -> Dict:
        """提取实体的关键特征"""
        
        features = {
            'types': [],
            'properties': [],
            'trigger_mechanisms': [],
            'stats': []
        }
        
        # 获取所有出边
        edges = self.graph.get_outgoing_edges(entity)
        
        for edge in edges:
            if edge['edge_type'] == 'has_type':
                features['types'].append(edge['target'])
            elif edge['edge_type'] == 'has_stat':
                features['stats'].append(edge['target'])
            elif edge['edge_type'] == 'triggers_via':
                features['trigger_mechanisms'].append(edge['target'])
        
        # 获取隐含属性
        implied = self.get_implied_properties(entity)
        features['properties'] = implied
        
        return features
    
    def find_similar_entities(self, features: Dict, exclude: List[str] = None) -> List[Tuple[str, float]]:
        """寻找相似实体"""
        
        similar = []
        
        all_entities = self.graph.get_nodes_by_type(NodeType.ENTITY)
        
        for entity in all_entities:
            if exclude and entity in exclude:
                continue
            
            entity_features = self.extract_key_features(entity)
            
            # 计算相似度
            similarity = self.calculate_similarity(features, entity_features)
            
            if similarity > 0.7:  # 阈值
                similar.append((entity, similarity))
        
        # 按相似度排序
        similar.sort(key=lambda x: x[1], reverse=True)
        
        return similar
    
    def calculate_similarity(self, features1: Dict, features2: Dict) -> float:
        """计算特征相似度"""
        
        # Jaccard 相似度
        def jaccard(set1, set2):
            if not set1 and not set2:
                return 1.0
            intersection = len(set(set1) & set(set2))
            union = len(set(set1) | set(set2))
            return intersection / union if union > 0 else 0.0
        
        # 加权平均
        weights = {
            'types': 0.3,
            'properties': 0.4,
            'trigger_mechanisms': 0.2,
            'stats': 0.1
        }
        
        total_similarity = 0.0
        for key, weight in weights.items():
            total_similarity += weight * jaccard(features1[key], features2[key])
        
        return total_similarity
```

### 3. 统一接口

```python
# heuristic_reason.py

class HeuristicReason:
    """启发式推理统一接口"""
    
    def __init__(self, graph_db_path: str):
        self.graph = AttributeGraph(graph_db_path)
        self.query = HeuristicQuery(self.graph)
        self.discovery = HeuristicDiscovery(self.graph)
        self.diffuse = HeuristicDiffuse(self.graph)
    
    def query_bypass(self, constraint: str, mode: str = 'auto') -> Dict:
        """
        查询绕过路径（三层能力统一接口）
        
        Args:
            constraint: 约束节点 ID
            mode: 'query' | 'discover' | 'diffuse' | 'auto'
        
        Returns:
            {
                'constraint': constraint,
                'mode': mode,
                'known_bypasses': [...],      # 已知绕过边
                'discovered_bypasses': [...], # 新发现的绕过边
                'diffused_bypasses': [...],   # 扩散发现的绕过边
                'reasoning_chain': [...]      # 推理链
            }
        """
        
        result = {
            'constraint': constraint,
            'mode': mode,
            'known_bypasses': [],
            'discovered_bypasses': [],
            'diffused_bypasses': [],
            'reasoning_chain': []
        }
        
        if mode == 'query':
            # 第一层：只查询已知边
            result['known_bypasses'] = self.query.query_bypasses(constraint)
        
        elif mode == 'discover':
            # 第二层：从零推理
            result['discovered_bypasses'] = self.discovery.discover_bypass_paths(constraint)
            result['reasoning_chain'] = self.discovery.get_reasoning_chain()
        
        elif mode == 'diffuse':
            # 第三层：从已知扩散
            known = self.query.query_bypasses(constraint)
            for bypass in known:
                diffused = self.diffuse.diffuse_from_bypass(bypass)
                result['diffused_bypasses'].extend(diffused)
        
        else:  # auto
            # 自动组合三种能力
            # 1. 查询已知
            known = self.query.query_bypasses(constraint)
            result['known_bypasses'] = known
            
            if known:
                # 2. 从已知扩散
                for bypass in known:
                    diffused = self.diffuse.diffuse_from_bypass(bypass)
                    result['diffused_bypasses'].extend(diffused)
            else:
                # 3. 从零发现
                discovered = self.discovery.discover_bypass_paths(constraint)
                result['discovered_bypasses'] = discovered
                result['reasoning_chain'] = self.discovery.get_reasoning_chain()
        
        return result
```

## 文件结构

```
scripts/
├── attribute_graph.py          # 扩展节点/边类型枚举
├── init_knowledge_base.py      # 添加类型层和属性层构建逻辑
├── heuristic_reason.py         # 统一接口
├── heuristic_query.py          # 查询能力
├── heuristic_discovery.py      # 发现能力
└── heuristic_diffuse.py        # 扩散能力

config/
└── edge_semantics.yaml         # 边语义配置

knowledge_base/
└── graph.db                    # 扩展后的关联图
```
