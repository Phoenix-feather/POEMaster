"""
索引构建脚本

用于构建和管理POB代码索引
"""

import sys
import argparse
import logging
from pathlib import Path

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from indexes import IndexManager

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='POB代码索引构建工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 构建所有索引
  python build_indexes.py --build --pob-data ../POBData
  
  # 查看索引状态
  python build_indexes.py --stats --pob-data ../POBData
  
  # 优化索引
  python build_indexes.py --optimize --pob-data ../POBData
  
  # 清空索引
  python build_indexes.py --clear --pob-data ../POBData
        """
    )
    
    parser.add_argument(
        '--pob-data',
        type=str,
        required=True,
        help='POB数据目录路径'
    )
    
    parser.add_argument(
        '--build',
        action='store_true',
        help='构建所有索引'
    )
    
    parser.add_argument(
        '--stats',
        action='store_true',
        help='查看索引统计信息'
    )
    
    parser.add_argument(
        '--health',
        action='store_true',
        help='检查索引健康状态'
    )
    
    parser.add_argument(
        '--optimize',
        action='store_true',
        help='优化所有索引'
    )
    
    parser.add_argument(
        '--clear',
        action='store_true',
        help='清空所有索引'
    )
    
    parser.add_argument(
        '--report',
        type=str,
        help='导出索引报告到指定文件'
    )
    
    parser.add_argument(
        '--sequential',
        action='store_true',
        help='顺序构建索引（不使用并行）'
    )
    
    parser.add_argument(
        '--config',
        type=str,
        help='配置文件路径'
    )
    
    args = parser.parse_args()
    
    # 检查POB数据路径
    pob_data_path = Path(args.pob_data)
    if not pob_data_path.exists():
        logger.error(f"POB数据路径不存在: {pob_data_path}")
        sys.exit(1)
    
    # 创建索引管理器
    with IndexManager(str(pob_data_path), args.config) as manager:
        
        # 构建索引
        if args.build:
            logger.info("开始构建索引...")
            manager.build_all_indexes(parallel=not args.sequential)
            logger.info("索引构建完成")
        
        # 查看统计信息
        if args.stats:
            stats = manager.get_stats()
            print("\n" + "="*60)
            print("索引统计信息")
            print("="*60)
            print(f"POB数据路径: {stats['pob_data_path']}")
            print(f"总大小: {stats['total_size'] / 1024 / 1024:.2f} MB")
            print(f"总记录数: {stats['total_records']}")
            print("\n各索引详情:")
            for name, index_stats in stats['indexes'].items():
                print(f"\n  {name}:")
                print(f"    数据库路径: {index_stats['db_path']}")
                print(f"    数据库大小: {index_stats['db_size'] / 1024:.2f} KB")
                print(f"    记录数量: {index_stats['record_count']}")
                print(f"    最后更新: {index_stats['last_updated'] or 'N/A'}")
        
        # 检查健康状态
        if args.health:
            health = manager.check_health()
            print("\n" + "="*60)
            print("索引健康状态")
            print("="*60)
            print(f"总体状态: {health['overall_status'].upper()}")
            
            if health['issues']:
                print("\n问题列表:")
                for issue in health['issues']:
                    print(f"  - {issue}")
            
            print("\n各索引状态:")
            for name, status in health['indexes'].items():
                print(f"\n  {name}:")
                print(f"    状态: {status['status'].upper()}")
                if 'message' in status:
                    print(f"    消息: {status['message']}")
                if 'size' in status:
                    print(f"    大小: {status['size'] / 1024:.2f} KB")
                if 'records' in status:
                    print(f"    记录数: {status['records']}")
        
        # 优化索引
        if args.optimize:
            logger.info("开始优化索引...")
            manager.optimize_all()
            logger.info("索引优化完成")
        
        # 清空索引
        if args.clear:
            confirm = input("确认要清空所有索引吗？(yes/no): ")
            if confirm.lower() == 'yes':
                manager.clear_all()
                logger.info("索引已清空")
            else:
                logger.info("操作已取消")
        
        # 导出报告
        if args.report:
            manager.export_report(args.report)
            logger.info(f"索引报告已导出: {args.report}")


if __name__ == '__main__':
    main()
