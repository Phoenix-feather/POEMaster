"""
验证系统命令行接口

提供验证操作的CLI工具
"""

import sys
import argparse
import json
import logging
from pathlib import Path
from datetime import datetime

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from verification import (
    VerificationEngine,
    VerificationAwareQueryEngine,
    VerificationStatus
)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='知识验证系统CLI工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 列出待确认知识
  python verification_cli.py list-pending --pob-data POBData --graph-db knowledge_base/graph.db
  
  # 验证单条知识
  python verification_cli.py verify --edge-id 123 --pob-data POBData --graph-db knowledge_base/graph.db
  
  # 批量验证
  python verification_cli.py batch-verify --pob-data POBData --graph-db knowledge_base/graph.db --limit 10
  
  # 用户确认
  python verification_cli.py user-confirm --edge-id 123 --decision accept --reason "POB代码明确验证" --pob-data POBData --graph-db knowledge_base/graph.db
  
  # 查看统计
  python verification_cli.py stats --pob-data POBData --graph-db knowledge_base/graph.db
        """
    )
    
    parser.add_argument('--pob-data', type=str, required=True, help='POB数据路径')
    parser.add_argument('--graph-db', type=str, required=True, help='关联图数据库路径')
    
    subparsers = parser.add_subparsers(dest='command', help='子命令')
    
    # list-pending子命令
    list_parser = subparsers.add_parser('list-pending', help='列出待确认知识')
    list_parser.add_argument('--limit', type=int, default=20, help='返回数量限制')
    list_parser.add_argument('--format', choices=['json', 'table'], default='table', help='输出格式')
    
    # verify子命令
    verify_parser = subparsers.add_parser('verify', help='验证单条知识')
    verify_parser.add_argument('--edge-id', type=int, required=True, help='边ID')
    verify_parser.add_argument('--auto', action='store_true', help='自动验证（强度≥0.8时）')
    
    # batch-verify子命令
    batch_parser = subparsers.add_parser('batch-verify', help='批量验证')
    batch_parser.add_argument('--limit', type=int, default=10, help='批量验证数量')
    batch_parser.add_argument('--auto', action='store_true', help='自动验证')
    
    # user-confirm子命令
    user_parser = subparsers.add_parser('user-confirm', help='用户确认')
    user_parser.add_argument('--edge-id', type=int, required=True, help='边ID')
    user_parser.add_argument('--decision', choices=['accept', 'reject'], required=True, help='决策')
    user_parser.add_argument('--reason', type=str, help='原因')
    
    # stats子命令
    stats_parser = subparsers.add_parser('stats', help='查看统计')
    stats_parser.add_argument('--detailed', action='store_true', help='详细统计')
    
    # query子命令
    query_parser = subparsers.add_parser('query', help='验证感知查询')
    query_parser.add_argument('--type', type=str, help='按类型查询')
    query_parser.add_argument('--tag', type=str, help='按标签查询')
    query_parser.add_argument('--no-auto-verify', action='store_true', help='禁用自动验证')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # 执行命令
    try:
        with VerificationEngine(args.pob_data, args.graph_db) as engine:
            
            if args.command == 'list-pending':
                cmd_list_pending(engine, args)
            
            elif args.command == 'verify':
                cmd_verify(engine, args)
            
            elif args.command == 'batch-verify':
                cmd_batch_verify(engine, args)
            
            elif args.command == 'user-confirm':
                cmd_user_confirm(engine, args)
            
            elif args.command == 'stats':
                cmd_stats(engine, args)
            
            elif args.command == 'query':
                cmd_query(args)
    
    except Exception as e:
        logger.error(f"执行失败: {e}")
        sys.exit(1)


def cmd_list_pending(engine: VerificationEngine, args):
    """列出待确认知识"""
    import sqlite3
    
    conn = sqlite3.connect(args.graph_db)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    rows = cursor.execute('''
        SELECT e.*, n.name as source_name, n2.name as target_name
        FROM graph_edges e
        JOIN graph_nodes n ON e.source_node = n.id
        JOIN graph_nodes n2 ON e.target_node = n2.id
        WHERE e.status = ?
        LIMIT ?
    ''', (VerificationStatus.PENDING.value, args.limit)).fetchall()
    
    if args.format == 'json':
        results = [dict(row) for row in rows]
        print(json.dumps(results, indent=2, ensure_ascii=False))
    
    else:  # table
        print("\n" + "="*80)
        print("待确认知识列表")
        print("="*80)
        print(f"{'ID':<6} {'源节点':<25} {'目标节点':<25} {'边类型':<15} {'置信度':<10}")
        print("-"*80)
        
        for row in rows:
            print(f"{row['id']:<6} {row['source_name']:<25} {row['target_name']:<25} {row['edge_type']:<15} {row['confidence']:<10.2f}")
        
        print("="*80)
        print(f"总计: {len(rows)} 条")
    
    conn.close()


def cmd_verify(engine: VerificationEngine, args):
    """验证单条知识"""
    print(f"\n验证知识: edge_id={args.edge_id}")
    
    result = engine.verify_knowledge(args.edge_id, auto_verify=args.auto)
    
    if result['success']:
        print(f"\n✅ 验证成功")
        print(f"状态: {result['evaluation']['status']}")
        print(f"置信度: {result['evaluation']['confidence']:.2f}")
        print(f"证据强度: {result['evaluation']['overall_strength']:.2f}")
        print(f"证据数量: {result['evaluation']['evidence_count']}")
        
        if result.get('auto_verified'):
            print("✨ 已自动验证")
    else:
        print(f"\n❌ 验证失败: {result.get('error')}")


def cmd_batch_verify(engine: VerificationEngine, args):
    """批量验证"""
    import sqlite3
    
    conn = sqlite3.connect(args.graph_db)
    cursor = conn.cursor()
    
    # 获取pending边ID
    rows = cursor.execute('''
        SELECT id FROM graph_edges 
        WHERE status = ? 
        LIMIT ?
    ''', (VerificationStatus.PENDING.value, args.limit)).fetchall()
    
    edge_ids = [row[0] for row in rows]
    conn.close()
    
    if not edge_ids:
        print("无待验证知识")
        return
    
    print(f"\n批量验证 {len(edge_ids)} 条知识...")
    
    result = engine.batch_verify(edge_ids, auto_verify_threshold=0.8)
    
    print(f"\n验证结果:")
    print(f"  已验证: {result['verified']}")
    print(f"  待确认: {result['pending']}")
    print(f"  假设: {result['hypothesis']}")
    print(f"  已拒绝: {result['rejected']}")
    print(f"  错误: {result['errors']}")


def cmd_user_confirm(engine: VerificationEngine, args):
    """用户确认"""
    print(f"\n用户确认: edge_id={args.edge_id}, decision={args.decision}")
    
    result = engine.user_verify(
        edge_id=args.edge_id,
        decision=args.decision,
        reason=args.reason
    )
    
    if result['success']:
        print(f"\n✅ 确认成功")
        print(f"旧状态: {result['old_status']}")
        print(f"新状态: {result['new_status']}")
        print(f"决策: {result['decision']}")
        if result['reason']:
            print(f"原因: {result['reason']}")
    else:
        print(f"\n❌ 确认失败: {result.get('error')}")


def cmd_stats(engine: VerificationEngine, args):
    """查看统计"""
    stats = engine.get_verification_stats()
    
    print("\n" + "="*60)
    print("知识验证统计")
    print("="*60)
    print(f"总知识数: {stats['total_knowledge']}")
    print(f"验证率: {stats['verified_rate']:.1%}")
    print(f"平均置信度: {stats['average_confidence']:.2f}")
    print(f"验证历史记录数: {stats['verification_history_count']}")
    
    print("\n按状态分布:")
    for status, count in stats['by_status'].items():
        percentage = count / stats['total_knowledge'] * 100 if stats['total_knowledge'] > 0 else 0
        print(f"  {status}: {count} ({percentage:.1f}%)")
    
    print("="*60)


def cmd_query(args):
    """验证感知查询"""
    with VerificationAwareQueryEngine(args.pob_data, args.graph_db) as query_engine:
        
        auto_verify = not args.no_auto_verify
        
        if args.type:
            print(f"\n查询类型: {args.type}")
            result = query_engine.query_by_type(args.type, auto_verify=auto_verify)
        
        elif args.tag:
            print(f"\n查询标签: {args.tag}")
            result = query_engine.query_by_tag(args.tag, auto_verify=auto_verify)
        
        else:
            print("请指定查询条件 (--type 或 --tag)")
            return
        
        print(f"\n查询结果:")
        print(f"  已验证: {len(result['verified'])}")
        print(f"  待确认: {len(result['pending'])}")
        print(f"  升级数: {result['summary']['upgraded_count']}")
        print(f"  执行验证: {result['summary']['verification_performed']}")
        print(f"  查询耗时: {result['summary']['query_duration']:.2f}s")


if __name__ == '__main__':
    main()
