#!/usr/bin/env python3
"""
假设管理器 (Hypothesis Manager)

功能:
1. 添加假设边到关联图
2. 验证假设后同步更新规则库和关联图
3. 拒绝假设后清理关联图

工作流程:
探索 → 新假设 → 启发记录 (YAML) + 假设边 (graph.db)
验证 → 规则库 (rules.db) + 更新边状态 (hypothesis → verified)
拒绝 → 清理假设边
"""

import sqlite3
import json
import yaml
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List
from dataclasses import dataclass


@dataclass
class Hypothesis:
    """假设数据结构"""
    id: str
    question: str
    source_entity: str
    target_entity: str
    relation_type: str
    condition: Optional[str]
    effect: Optional[str]
    reasoning: str
    status: str  # hypothesis/verified/rejected
    evidence: Optional[str] = None
    verified_at: Optional[str] = None


class HypothesisManager:
    """假设管理器"""
    
    def __init__(self, knowledge_base_path: str):
        self.kb_path = Path(knowledge_base_path)
        self.graph_db = self.kb_path / 'graph.db'
        self.rules_db = self.kb_path / 'rules.db'
        self.heuristic_file = self.kb_path.parent / 'config' / 'heuristic_records.yaml'
    
    def add_hypothesis(self, hypothesis: Hypothesis) -> bool:
        """
        添加假设边到关联图
        
        步骤:
        1. 添加启发记录到 YAML 文件
        2. 添加假设边到关联图 (status='hypothesis')
        """
        print(f"\n[添加假设] {hypothesis.id}")
        
        # Step 1: 添加启发记录
        if not self._save_heuristic_record(hypothesis):
            return False
        
        # Step 2: 添加假设边到关联图
        if not self._add_hypothesis_edge(hypothesis):
            return False
        
        print(f"  ✓ 假设已添加: {hypothesis.source_entity} --{hypothesis.relation_type}--> {hypothesis.target_entity}")
        return True
    
    def verify_hypothesis(self, hypothesis_id: str, evidence: str) -> bool:
        """
        验证假设并同步更新
        
        步骤:
        1. 更新启发记录 (status: hypothesis → verified)
        2. 添加规则到规则库
        3. 更新关联图边状态 (status: hypothesis → verified)
        """
        print(f"\n[验证假设] {hypothesis_id}")
        
        # Step 1: 读取启发记录
        hypothesis = self._load_heuristic_record(hypothesis_id)
        if not hypothesis:
            print(f"  ✗ 启发记录不存在: {hypothesis_id}")
            return False
        
        if hypothesis.status != 'hypothesis':
            print(f"  ✗ 假设状态不正确: {hypothesis.status}")
            return False
        
        # Step 2: 更新启发记录
        hypothesis.status = 'verified'
        hypothesis.evidence = evidence
        hypothesis.verified_at = datetime.now().isoformat()
        self._update_heuristic_record(hypothesis)
        print(f"  ✓ 更新启发记录状态: verified")
        
        # Step 3: 添加规则到规则库
        rule_id = self._add_rule_from_hypothesis(hypothesis)
        print(f"  ✓ 添加规则: {rule_id}")
        
        # Step 4: 更新关联图边状态
        self._update_edge_status(hypothesis_id, 'verified', evidence, rule_id)
        print(f"  ✓ 更新边状态: hypothesis → verified")
        
        return True
    
    def reject_hypothesis(self, hypothesis_id: str, reason: str) -> bool:
        """
        拒绝假设并清理
        
        步骤:
        1. 更新启发记录 (status: hypothesis → rejected)
        2. 删除关联图的假设边
        """
        print(f"\n[拒绝假设] {hypothesis_id}")
        
        # Step 1: 读取启发记录
        hypothesis = self._load_heuristic_record(hypothesis_id)
        if not hypothesis:
            print(f"  ✗ 启发记录不存在: {hypothesis_id}")
            return False
        
        # Step 2: 更新启发记录
        hypothesis.status = 'rejected'
        hypothesis.evidence = f"Rejected: {reason}"
        self._update_heuristic_record(hypothesis)
        print(f"  ✓ 更新启发记录状态: rejected")
        
        # Step 3: 删除关联图的假设边
        self._delete_hypothesis_edge(hypothesis_id)
        print(f"  ✓ 删除假设边")
        
        return True
    
    def list_hypotheses(self, status: Optional[str] = None) -> List[Dict]:
        """列出假设"""
        conn = sqlite3.connect(str(self.graph_db))
        cursor = conn.cursor()
        
        if status:
            cursor.execute('''
                SELECT heuristic_record_id, source_node, target_node, edge_type, status
                FROM graph_edges
                WHERE status = ? AND heuristic_record_id IS NOT NULL
            ''', (status,))
        else:
            cursor.execute('''
                SELECT heuristic_record_id, source_node, target_node, edge_type, status
                FROM graph_edges
                WHERE heuristic_record_id IS NOT NULL
            ''')
        
        results = []
        for row in cursor.fetchall():
            results.append({
                'id': row[0],
                'source': row[1],
                'target': row[2],
                'relation_type': row[3],
                'status': row[4]
            })
        
        conn.close()
        return results
    
    # ===== 内部方法 =====
    
    def _save_heuristic_record(self, hypothesis: Hypothesis) -> bool:
        """保存启发记录到 YAML 文件"""
        try:
            # 确保 config 目录存在
            self.heuristic_file.parent.mkdir(parents=True, exist_ok=True)
            
            # 读取现有记录
            records = {}
            if self.heuristic_file.exists():
                with open(self.heuristic_file, 'r', encoding='utf-8') as f:
                    records = yaml.safe_load(f) or {}
            
            # 添加新记录
            records[hypothesis.id] = {
                'question': hypothesis.question,
                'hypothesis': {
                    'source_entity': hypothesis.source_entity,
                    'target_entity': hypothesis.target_entity,
                    'relation_type': hypothesis.relation_type,
                    'condition': hypothesis.condition,
                    'effect': hypothesis.effect,
                    'reasoning': hypothesis.reasoning
                },
                'status': hypothesis.status,
                'evidence': hypothesis.evidence,
                'verified_at': hypothesis.verified_at,
                'created_at': datetime.now().isoformat()
            }
            
            # 保存
            with open(self.heuristic_file, 'w', encoding='utf-8') as f:
                yaml.dump(records, f, allow_unicode=True, default_flow_style=False)
            
            return True
        except Exception as e:
            print(f"  ✗ 保存启发记录失败: {e}")
            return False
    
    def _load_heuristic_record(self, hypothesis_id: str) -> Optional[Hypothesis]:
        """加载启发记录"""
        if not self.heuristic_file.exists():
            return None
        
        with open(self.heuristic_file, 'r', encoding='utf-8') as f:
            records = yaml.safe_load(f) or {}
        
        if hypothesis_id not in records:
            return None
        
        record = records[hypothesis_id]
        hyp_data = record.get('hypothesis', {})
        
        return Hypothesis(
            id=hypothesis_id,
            question=record.get('question', ''),
            source_entity=hyp_data.get('source_entity', ''),
            target_entity=hyp_data.get('target_entity', ''),
            relation_type=hyp_data.get('relation_type', ''),
            condition=hyp_data.get('condition'),
            effect=hyp_data.get('effect'),
            reasoning=hyp_data.get('reasoning', ''),
            status=record.get('status', 'hypothesis'),
            evidence=record.get('evidence'),
            verified_at=record.get('verified_at')
        )
    
    def _update_heuristic_record(self, hypothesis: Hypothesis) -> bool:
        """更新启发记录"""
        return self._save_heuristic_record(hypothesis)
    
    def _add_hypothesis_edge(self, hypothesis: Hypothesis) -> bool:
        """添加假设边到关联图"""
        try:
            conn = sqlite3.connect(str(self.graph_db))
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO graph_edges (
                    source_node, target_node, edge_type, weight, attributes,
                    status, heuristic_record_id, condition, effect, evidence, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                hypothesis.source_entity,
                hypothesis.target_entity,
                hypothesis.relation_type,
                0.8,  # 假设边权重较低
                json.dumps({'category': 'hypothesis'}, ensure_ascii=False),
                'hypothesis',
                hypothesis.id,
                hypothesis.condition,
                hypothesis.effect,
                hypothesis.reasoning,
                datetime.now().isoformat()
            ))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"  ✗ 添加假设边失败: {e}")
            return False
    
    def _add_rule_from_hypothesis(self, hypothesis: Hypothesis) -> str:
        """从假设创建规则"""
        rule_id = f"rule_{hypothesis.id}"
        
        conn = sqlite3.connect(str(self.rules_db))
        cursor = conn.cursor()
        
        # 确定规则类别
        if hypothesis.relation_type == 'bypasses':
            category = 'bypass'
        else:
            category = 'relation'
        
        cursor.execute('''
            INSERT INTO rules (
                id, category, source_entity, target_entity, relation_type,
                condition, effect, evidence, source_layer, heuristic_record_id,
                created_at, verified_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            rule_id,
            category,
            hypothesis.source_entity,
            hypothesis.target_entity,
            hypothesis.relation_type,
            hypothesis.condition,
            hypothesis.effect,
            hypothesis.evidence,
            3,  # 假设验证来自代码层
            hypothesis.id,
            datetime.now().isoformat(),
            hypothesis.verified_at
        ))
        
        conn.commit()
        conn.close()
        
        return rule_id
    
    def _update_edge_status(self, hypothesis_id: str, status: str, 
                            evidence: str, source_rule: str) -> bool:
        """更新边的状态"""
        try:
            conn = sqlite3.connect(str(self.graph_db))
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE graph_edges
                SET status = ?, evidence = ?, source_rule = ?, 
                    verified_at = ?, weight = 1.0
                WHERE heuristic_record_id = ?
            ''', (
                status,
                evidence,
                source_rule,
                datetime.now().isoformat(),
                hypothesis_id
            ))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"  ✗ 更新边状态失败: {e}")
            return False
    
    def _delete_hypothesis_edge(self, hypothesis_id: str) -> bool:
        """删除假设边"""
        try:
            conn = sqlite3.connect(str(self.graph_db))
            cursor = conn.cursor()
            
            cursor.execute('''
                DELETE FROM graph_edges
                WHERE heuristic_record_id = ? AND status = 'hypothesis'
            ''', (hypothesis_id,))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"  ✗ 删除假设边失败: {e}")
            return False


# ===== 测试代码 =====

def test_hypothesis_manager():
    """测试假设管理器"""
    
    kb_path = Path('.codebuddy/skills/poe-data-miner/knowledge_base')
    manager = HypothesisManager(str(kb_path))
    
    # 测试添加假设
    hypothesis = Hypothesis(
        id='hr_test_001',
        question='陷阱爆炸能否绕过触发限制？',
        source_entity='TrapExplosion',
        target_entity='TriggeredLimit',
        relation_type='bypasses',
        condition='damage_source = trap',
        effect='绕过 Triggered 能量限制',
        reasoning='类比 DetonateDead 的绕过机制',
        status='hypothesis'
    )
    
    print("\n" + "=" * 70)
    print("测试假设管理器")
    print("=" * 70)
    
    # 添加假设
    manager.add_hypothesis(hypothesis)
    
    # 列出假设
    print("\n当前假设列表:")
    hypotheses = manager.list_hypotheses(status='hypothesis')
    for h in hypotheses:
        print(f"  {h['id']}: {h['source']} --{h['relation_type']}--> {h['target']} ({h['status']})")
    
    # 验证假设
    # manager.verify_hypothesis('hr_test_001', 'CalcTriggers.lua:xxx-xxx')
    
    print("\n测试完成")


if __name__ == "__main__":
    test_hypothesis_manager()
