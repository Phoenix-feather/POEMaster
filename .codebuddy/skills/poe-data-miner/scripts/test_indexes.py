"""
索引系统测试脚本

测试四级索引功能
"""

import sys
import time
from pathlib import Path

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from indexes import IndexManager
from indexes.stat_index import StatIndex
from indexes.skilltype_index import SkillTypeIndex
from indexes.function_index import FunctionCallIndex
from indexes.semantic_index import SemanticFeatureIndex


def test_stat_index(pob_data_path: str):
    """测试Stat索引"""
    print("\n" + "="*60)
    print("测试 StatIndex")
    print("="*60)
    
    index = StatIndex('test_stat_index.db')
    
    # 构建索引
    start_time = time.time()
    index.build_index(pob_data_path)
    duration = time.time() - start_time
    
    print(f"构建时间: {duration:.2f} 秒")
    
    # 查询测试
    print("\n查询测试:")
    
    # 测试1: 查询某个stat
    result = index.search({'stat_id': 'FireDamage'})
    print(f"  FireDamage: {result['usage_count']} 次使用")
    
    # 测试2: 模糊搜索
    result = index.search({'fuzzy': 'fire'})
    print(f"  模糊搜索 'fire': {result['count']} 个结果")
    
    # 测试3: Top stats
    top_stats = index.get_top_stats(5)
    print(f"\n  Top 5 高频stats:")
    for stat in top_stats:
        print(f"    {stat['stat_id']}: {stat['usage_count']} 次")
    
    # 统计信息
    stats = index.get_stats()
    print(f"\n索引统计:")
    print(f"  记录数: {stats['record_count']}")
    print(f"  数据库大小: {stats['db_size'] / 1024:.2f} KB")
    
    # 清理
    index.clear()
    print("\n✅ StatIndex 测试通过")


def test_skilltype_index(pob_data_path: str):
    """测试SkillType索引"""
    print("\n" + "="*60)
    print("测试 SkillTypeIndex")
    print("="*60)
    
    index = SkillTypeIndex('test_skilltype_index.db')
    
    # 构建索引
    start_time = time.time()
    index.build_index(pob_data_path)
    duration = time.time() - start_time
    
    print(f"构建时间: {duration:.2f} 秒")
    
    # 查询测试
    print("\n查询测试:")
    
    # 测试1: 查询Triggered类型的约束
    result = index.search({'skill_type': 'Triggered'})
    print(f"  Triggered类型:")
    print(f"    required by: {len(result['required_by'])} 个技能")
    print(f"    excluded by: {len(result['excluded_by'])} 个技能")
    print(f"    added by: {len(result['added_by'])} 个技能")
    
    # 测试2: 获取所有skillTypes
    all_types = index.get_all_skilltypes()
    print(f"\n  总共有 {len(all_types)} 个skillTypes")
    print(f"  前10个: {all_types[:10]}")
    
    # 统计信息
    stats = index.get_stats()
    print(f"\n索引统计:")
    print(f"  记录数: {stats['record_count']}")
    print(f"  数据库大小: {stats['db_size'] / 1024:.2f} KB")
    
    # 清理
    index.clear()
    print("\n✅ SkillTypeIndex 测试通过")


def test_function_index(pob_data_path: str):
    """测试函数调用索引"""
    print("\n" + "="*60)
    print("测试 FunctionCallIndex")
    print("="*60)
    
    index = FunctionCallIndex('test_function_index.db')
    
    # 构建索引
    start_time = time.time()
    index.build_index(pob_data_path)
    duration = time.time() - start_time
    
    print(f"构建时间: {duration:.2f} 秒")
    
    # 查询测试
    print("\n查询测试:")
    
    # 测试1: 查询某个函数
    result = index.search({'function_name': 'isTriggered'})
    if result['found']:
        print(f"  isTriggered函数:")
        print(f"    定义位置: {result['definition']['file_path']}")
        print(f"    调用次数: {result['call_count']}")
        print(f"    被调用者: {len(result['called_by'])} 个")
    
    # 测试2: 查询Top被调用函数
    top_funcs = index.get_top_called_functions(5)
    print(f"\n  Top 5 被调用函数:")
    for func in top_funcs:
        print(f"    {func['function_name']}: {func['call_count']} 次")
    
    # 统计信息
    stats = index.get_stats()
    print(f"\n索引统计:")
    print(f"  记录数: {stats['record_count']}")
    print(f"  数据库大小: {stats['db_size'] / 1024:.2f} KB")
    
    # 清理
    index.clear()
    print("\n✅ FunctionCallIndex 测试通过")


def test_semantic_index(pob_data_path: str):
    """测试语义特征索引"""
    print("\n" + "="*60)
    print("测试 SemanticFeatureIndex")
    print("="*60)
    
    index = SemanticFeatureIndex('test_semantic_index.db')
    
    # 构建索引
    start_time = time.time()
    index.build_index(pob_data_path)
    duration = time.time() - start_time
    
    print(f"构建时间: {duration:.2f} 秒")
    
    # 查询测试
    print("\n查询测试:")
    
    # 测试1: 查找相似实体
    result = index.search({'entity': 'Fireball', 'top_k': 5})
    if result['found']:
        print(f"  Fireball的相似实体:")
        for sim in result['similar_entities'][:3]:
            print(f"    {sim['entity']}: {sim['similarity']:.3f}")
    
    # 测试2: 按标签查询
    entities = index.get_entities_by_tag('fire')
    print(f"\n  带'fire'标签的实体: {len(entities)} 个")
    
    # 统计信息
    stats = index.get_stats()
    print(f"\n索引统计:")
    print(f"  记录数: {stats['record_count']}")
    print(f"  数据库大小: {stats['db_size'] / 1024:.2f} KB")
    
    # 清理
    index.clear()
    print("\n✅ SemanticFeatureIndex 测试通过")


def test_index_manager(pob_data_path: str):
    """测试索引管理器"""
    print("\n" + "="*60)
    print("测试 IndexManager")
    print("="*60)
    
    # 创建索引管理器
    manager = IndexManager(pob_data_path)
    
    # 构建所有索引
    start_time = time.time()
    manager.build_all_indexes(parallel=True)
    duration = time.time() - start_time
    
    print(f"\n总构建时间: {duration:.2f} 秒")
    
    # 检查健康状态
    health = manager.check_health()
    print(f"\n健康状态: {health['overall_status'].upper()}")
    
    # 获取统计信息
    stats = manager.get_stats()
    print(f"\n索引统计:")
    print(f"  总大小: {stats['total_size'] / 1024 / 1024:.2f} MB")
    print(f"  总记录数: {stats['total_records']}")
    
    for name, index_stats in stats['indexes'].items():
        print(f"\n  {name}:")
        print(f"    记录数: {index_stats['record_count']}")
        print(f"    大小: {index_stats['db_size'] / 1024:.2f} KB")
    
    # 清理
    manager.clear_all()
    print("\n✅ IndexManager 测试通过")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='索引系统测试')
    parser.add_argument('--pob-data', type=str, required=True, help='POB数据路径')
    parser.add_argument('--test', type=str, choices=['stat', 'skilltype', 'function', 'semantic', 'manager', 'all'],
                       default='all', help='测试类型')
    
    args = parser.parse_args()
    
    pob_data_path = Path(args.pob_data)
    if not pob_data_path.exists():
        print(f"错误: POB数据路径不存在: {pob_data_path}")
        sys.exit(1)
    
    print(f"POB数据路径: {pob_data_path}")
    
    try:
        if args.test in ['stat', 'all']:
            test_stat_index(str(pob_data_path))
        
        if args.test in ['skilltype', 'all']:
            test_skilltype_index(str(pob_data_path))
        
        if args.test in ['function', 'all']:
            test_function_index(str(pob_data_path))
        
        if args.test in ['semantic', 'all']:
            test_semantic_index(str(pob_data_path))
        
        if args.test in ['manager', 'all']:
            test_index_manager(str(pob_data_path))
        
        print("\n" + "="*60)
        print("✅ 所有测试通过")
        print("="*60)
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
