"""
数据库迁移脚本：为graph_edges表添加验证相关字段

运行方式：
    python scripts/migrate_graph_db.py --db-path knowledge_base/graph.db
"""

import sqlite3
import argparse
import logging
from pathlib import Path
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def migrate_graph_edges(db_path: str):
    """
    迁移graph_edges表，添加验证相关字段
    
    Args:
        db_path: graph.db数据库路径
    """
    logger.info(f"开始迁移数据库: {db_path}")
    
    # 备份数据库
    backup_path = backup_database(db_path)
    logger.info(f"数据库已备份到: {backup_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 检查表是否存在
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='graph_edges'
    """)
    
    if not cursor.fetchone():
        logger.error("graph_edges表不存在，请先初始化知识库")
        conn.close()
        return
    
    # 获取当前表结构
    cursor.execute("PRAGMA table_info(graph_edges)")
    current_columns = {row[1]: row[2] for row in cursor.fetchall()}
    
    logger.info(f"当前列: {list(current_columns.keys())}")
    
    # 定义需要添加的新字段
    new_columns = {
        'confidence': 'REAL DEFAULT 0.5',
        'evidence_type': 'TEXT',
        'evidence_source': 'TEXT',
        'evidence_content': 'TEXT',
        'discovery_method': 'TEXT',
        'last_verified': 'TIMESTAMP',
        'verified_by': 'TEXT'
    }
    
    # 添加缺失的列
    added_columns = []
    for column_name, column_type in new_columns.items():
        if column_name not in current_columns:
            try:
                alter_sql = f"ALTER TABLE graph_edges ADD COLUMN {column_name} {column_type}"
                cursor.execute(alter_sql)
                added_columns.append(column_name)
                logger.info(f"添加列: {column_name} ({column_type})")
            except Exception as e:
                logger.error(f"添加列 {column_name} 失败: {e}")
    
    # 更新已有数据
    if added_columns:
        # 为已有的verified边设置默认值
        cursor.execute("""
            UPDATE graph_edges 
            SET confidence = 1.0,
                evidence_type = 'pob_data',
                discovery_method = 'data_extraction',
                last_verified = CURRENT_TIMESTAMP,
                verified_by = 'system'
            WHERE status = 'verified' 
            AND confidence IS NULL
        """)
        
        # 为pending边设置默认值
        cursor.execute("""
            UPDATE graph_edges 
            SET confidence = 0.5,
                discovery_method = 'heuristic'
            WHERE status = 'pending' 
            AND confidence IS NULL
        """)
        
        # 为hypothesis边设置默认值
        cursor.execute("""
            UPDATE graph_edges 
            SET confidence = 0.3,
                discovery_method = 'heuristic'
            WHERE status = 'hypothesis' 
            AND confidence IS NULL
        """)
        
        conn.commit()
        logger.info(f"已更新现有数据")
    
    # 验证迁移结果
    cursor.execute("PRAGMA table_info(graph_edges)")
    final_columns = {row[1]: row[2] for row in cursor.fetchall()}
    
    logger.info(f"迁移后列: {list(final_columns.keys())}")
    
    # 检查是否所有字段都已添加
    missing = [col for col in new_columns.keys() if col not in final_columns]
    if missing:
        logger.warning(f"缺少字段: {missing}")
    else:
        logger.info("✅ 所有字段已成功添加")
    
    conn.close()
    logger.info("数据库迁移完成")


def backup_database(db_path: str) -> str:
    """
    备份数据库
    
    Args:
        db_path: 数据库路径
        
    Returns:
        备份文件路径
    """
    import shutil
    
    db_file = Path(db_path)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = db_file.parent / f"{db_file.stem}_backup_{timestamp}.db"
    
    shutil.copy2(db_file, backup_file)
    
    return str(backup_file)


def create_verification_history_table(db_path: str):
    """
    创建verification_history表
    
    Args:
        db_path: 数据库路径
    """
    logger.info("创建verification_history表...")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 创建验证历史表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS verification_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            edge_id INTEGER NOT NULL,
            old_status TEXT NOT NULL,
            new_status TEXT NOT NULL,
            old_confidence REAL,
            new_confidence REAL,
            evidence_type TEXT,
            evidence_source TEXT,
            evidence_content TEXT,
            reason TEXT,
            verified_by TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (edge_id) REFERENCES graph_edges(id)
        )
    ''')
    
    # 创建索引
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_edge_id ON verification_history(edge_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_verified_by ON verification_history(verified_by)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_created_at ON verification_history(created_at)')
    
    conn.commit()
    conn.close()
    
    logger.info("✅ verification_history表创建完成")


def verify_migration(db_path: str):
    """
    验证迁移结果
    
    Args:
        db_path: 数据库路径
    """
    logger.info("验证迁移结果...")
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # 检查graph_edges表结构
    cursor.execute("PRAGMA table_info(graph_edges)")
    columns = cursor.fetchall()
    
    print("\ngraph_edges表结构:")
    print("-" * 80)
    print(f"{'列名':<25} {'类型':<15} {'非空':<8} {'默认值':<15}")
    print("-" * 80)
    
    for col in columns:
        print(f"{col['name']:<25} {col['type']:<15} {col['notnull']:<8} {col['dflt_value'] or '':<15}")
    
    # 统计数据
    print("\n数据统计:")
    print("-" * 80)
    
    cursor.execute("SELECT COUNT(*) FROM graph_edges")
    total = cursor.fetchone()[0]
    print(f"总边数: {total}")
    
    cursor.execute("""
        SELECT status, COUNT(*) as count 
        FROM graph_edges 
        GROUP BY status
    """)
    
    for row in cursor.fetchall():
        print(f"  {row['status']}: {row['count']}")
    
    # 检查verification_history表
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='verification_history'
    """)
    
    if cursor.fetchone():
        cursor.execute("SELECT COUNT(*) FROM verification_history")
        count = cursor.fetchone()[0]
        print(f"\nverification_history记录数: {count}")
    
    conn.close()
    
    logger.info("验证完成")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='数据库迁移工具')
    parser.add_argument(
        '--db-path',
        type=str,
        required=True,
        help='graph.db数据库路径'
    )
    
    parser.add_argument(
        '--skip-backup',
        action='store_true',
        help='跳过备份（不推荐）'
    )
    
    parser.add_argument(
        '--verify-only',
        action='store_true',
        help='仅验证，不执行迁移'
    )
    
    args = parser.parse_args()
    
    db_path = Path(args.db_path)
    
    if not db_path.exists():
        logger.error(f"数据库文件不存在: {db_path}")
        return
    
    if args.verify_only:
        verify_migration(str(db_path))
    else:
        # 执行迁移
        migrate_graph_edges(str(db_path))
        
        # 创建验证历史表
        create_verification_history_table(str(db_path))
        
        # 验证结果
        verify_migration(str(db_path))
        
        print("\n" + "="*80)
        print("✅ 数据库迁移完成")
        print("="*80)


if __name__ == '__main__':
    main()
