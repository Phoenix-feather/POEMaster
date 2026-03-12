"""
索引管理器

统一管理所有索引的构建、更新和查询
"""

import os
import time
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import yaml

from .stat_index import StatIndex
from .skilltype_index import SkillTypeIndex
from .function_index import FunctionCallIndex
from .semantic_index import SemanticFeatureIndex

logger = logging.getLogger(__name__)


class IndexManager:
    """索引管理器"""
    
    def __init__(self, pob_data_path: str, config_path: Optional[str] = None):
        """
        初始化索引管理器
        
        Args:
            pob_data_path: POB数据路径
            config_path: 配置文件路径
        """
        self.pob_data_path = Path(pob_data_path)
        
        # 加载配置
        self.config = self._load_config(config_path)
        
        # 索引数据库路径
        index_dir = self.pob_data_path.parent / 'indexes'
        index_dir.mkdir(parents=True, exist_ok=True)
        
        # 初始化各索引
        self.indexes = {
            'stat': StatIndex(str(index_dir / 'stat_index.db')),
            'skilltype': SkillTypeIndex(str(index_dir / 'skilltype_index.db')),
            'function': FunctionCallIndex(str(index_dir / 'function_index.db')),
            'semantic': SemanticFeatureIndex(str(index_dir / 'semantic_index.db'))
        }
        
        logger.info(f"索引管理器初始化完成，索引目录: {index_dir}")
    
    def _load_config(self, config_path: Optional[str]) -> Dict[str, Any]:
        """加载配置文件"""
        if config_path and os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        else:
            # 默认配置
            return {
                'build_config': {
                    'max_workers': 4,
                    'batch_size': 1000
                },
                'performance': {
                    'query_timeout': 5.0,
                    'max_results': 1000
                }
            }
    
    def build_all_indexes(self, parallel: bool = True):
        """
        构建所有索引
        
        Args:
            parallel: 是否并行构建
        """
        logger.info("开始构建所有索引...")
        start_time = time.time()
        
        if parallel:
            # 并行构建
            max_workers = self.config.get('build_config', {}).get('max_workers', 4)
            
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {
                    executor.submit(
                        self.indexes['stat'].build_index, 
                        str(self.pob_data_path)
                    ): 'stat',
                    
                    executor.submit(
                        self.indexes['skilltype'].build_index,
                        str(self.pob_data_path)
                    ): 'skilltype',
                    
                    executor.submit(
                        self.indexes['function'].build_index,
                        str(self.pob_data_path)
                    ): 'function',
                    
                    executor.submit(
                        self.indexes['semantic'].build_index,
                        str(self.pob_data_path)
                    ): 'semantic'
                }
                
                for future in as_completed(futures):
                    index_name = futures[future]
                    try:
                        future.result()
                        logger.info(f"{index_name} 索引构建完成")
                    except Exception as e:
                        logger.error(f"{index_name} 索引构建失败: {e}")
        
        else:
            # 顺序构建
            for name, index in self.indexes.items():
                try:
                    logger.info(f"构建 {name} 索引...")
                    index.build_index(str(self.pob_data_path))
                    logger.info(f"{name} 索引构建完成")
                except Exception as e:
                    logger.error(f"{name} 索引构建失败: {e}")
        
        duration = time.time() - start_time
        logger.info(f"所有索引构建完成，耗时 {duration:.2f} 秒")
    
    def incremental_update(self, changed_files: List[str]):
        """
        增量更新索引
        
        Args:
            changed_files: 变更的文件列表
        """
        logger.info(f"增量更新索引，变更文件数: {len(changed_files)}")
        
        for file_path in changed_files:
            # 根据文件类型更新对应索引
            if 'StatDescriptions' in file_path:
                self.indexes['stat'].update_index(file_path)
            
            elif 'Skills' in file_path:
                self.indexes['stat'].update_index(file_path)
                self.indexes['skilltype'].update_index(file_path)
            
            elif 'Modules' in file_path:
                self.indexes['function'].update_index(file_path)
        
        # 语义索引需要重建（简化处理）
        # 实际可以只更新相关实体
        
        logger.info("增量更新完成")
    
    def search_all(self, query: Dict[str, Any]) -> Dict[str, Any]:
        """
        跨索引搜索
        
        Args:
            query: 查询参数
            
        Returns:
            综合搜索结果
        """
        results = {
            'stat': None,
            'skilltype': None,
            'function': None,
            'semantic': None
        }
        
        # 并行搜索
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {
                executor.submit(self.indexes['stat'].search, query): 'stat',
                executor.submit(self.indexes['skilltype'].search, query): 'skilltype',
                executor.submit(self.indexes['function'].search, query): 'function',
                executor.submit(self.indexes['semantic'].search, query): 'semantic'
            }
            
            for future in as_completed(futures):
                index_name = futures[future]
                try:
                    results[index_name] = future.result()
                except Exception as e:
                    logger.error(f"{index_name} 搜索失败: {e}")
                    results[index_name] = {'error': str(e)}
        
        return results
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取所有索引的统计信息
        
        Returns:
            统计信息字典
        """
        stats = {
            'pob_data_path': str(self.pob_data_path),
            'indexes': {},
            'total_size': 0,
            'total_records': 0
        }
        
        for name, index in self.indexes.items():
            index_stats = index.get_stats()
            stats['indexes'][name] = index_stats
            stats['total_size'] += index_stats['db_size']
            stats['total_records'] += index_stats['record_count']
        
        return stats
    
    def check_health(self) -> Dict[str, Any]:
        """
        检查索引健康状态
        
        Returns:
            健康状态字典
        """
        health = {
            'overall_status': 'healthy',
            'indexes': {},
            'issues': []
        }
        
        for name, index in self.indexes.items():
            index_stats = index.get_stats()
            
            # 检查索引是否存在
            if index_stats['db_size'] == 0:
                health['indexes'][name] = {
                    'status': 'empty',
                    'message': '索引为空，需要构建'
                }
                health['issues'].append(f"{name} 索引为空")
                health['overall_status'] = 'degraded'
            
            # 检查记录数
            elif index_stats['record_count'] == 0:
                health['indexes'][name] = {
                    'status': 'empty',
                    'message': '索引无记录'
                }
                health['issues'].append(f"{name} 索引无记录")
                health['overall_status'] = 'degraded'
            
            else:
                health['indexes'][name] = {
                    'status': 'healthy',
                    'size': index_stats['db_size'],
                    'records': index_stats['record_count']
                }
        
        return health
    
    def optimize_all(self):
        """优化所有索引"""
        logger.info("开始优化所有索引...")
        
        for name, index in self.indexes.items():
            try:
                logger.info(f"优化 {name} 索引...")
                index.optimize()
                logger.info(f"{name} 索引优化完成")
            except Exception as e:
                logger.error(f"{name} 索引优化失败: {e}")
        
        logger.info("所有索引优化完成")
    
    def clear_all(self):
        """清空所有索引"""
        logger.warning("清空所有索引...")
        
        for name, index in self.indexes.items():
            try:
                index.clear()
                logger.info(f"{name} 索引已清空")
            except Exception as e:
                logger.error(f"{name} 索引清空失败: {e}")
        
        logger.info("所有索引已清空")
    
    def close_all(self):
        """关闭所有索引连接"""
        for name, index in self.indexes.items():
            try:
                index.close()
            except Exception as e:
                logger.error(f"{name} 索引关闭失败: {e}")
        
        logger.info("所有索引连接已关闭")
    
    def get_index(self, index_name: str):
        """
        获取指定索引
        
        Args:
            index_name: 索引名称（stat/skilltype/function/semantic）
            
        Returns:
            索引实例
        """
        return self.indexes.get(index_name)
    
    def export_report(self, output_path: str):
        """
        导出索引报告
        
        Args:
            output_path: 输出文件路径
        """
        stats = self.get_stats()
        health = self.check_health()
        
        report = {
            'generated_at': datetime.now().isoformat(),
            'statistics': stats,
            'health': health
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            yaml.dump(report, f, default_flow_style=False, allow_unicode=True)
        
        logger.info(f"索引报告已导出: {output_path}")
    
    def __enter__(self):
        """上下文管理器入口"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.close_all()
    
    def __del__(self):
        """析构函数"""
        self.close_all()
