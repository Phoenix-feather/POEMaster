"""
基础索引类

提供所有索引类的通用接口和基础功能
"""

import sqlite3
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Any

logger = logging.getLogger(__name__)


class BaseIndex:
    """基础索引类"""
    
    def __init__(self, db_path: str, index_name: str):
        """
        初始化基础索引
        
        Args:
            db_path: 索引数据库路径
            index_name: 索引名称
        """
        self.db_path = Path(db_path)
        self.index_name = index_name
        self.conn: Optional[sqlite3.Connection] = None
        
        # 确保目录存在
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 初始化数据库连接
        self._init_connection()
        
        logger.info(f"初始化索引: {index_name} at {db_path}")
    
    def _init_connection(self):
        """初始化数据库连接"""
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self._create_tables()
    
    def _create_tables(self):
        """创建索引表（子类实现）"""
        raise NotImplementedError("子类必须实现 _create_tables 方法")
    
    def build_index(self, pob_data_path: str):
        """
        构建索引（子类实现）
        
        Args:
            pob_data_path: POB数据路径
        """
        raise NotImplementedError("子类必须实现 build_index 方法")
    
    def update_index(self, changed_file: str):
        """
        增量更新索引（子类实现）
        
        Args:
            changed_file: 变更的文件路径
        """
        raise NotImplementedError("子类必须实现 update_index 方法")
    
    def search(self, query: Dict[str, Any]) -> Dict[str, Any]:
        """
        搜索索引（子类实现）
        
        Args:
            query: 查询参数
            
        Returns:
            查询结果
        """
        raise NotImplementedError("子类必须实现 search 方法")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取索引统计信息
        
        Returns:
            统计信息字典
        """
        stats = {
            'index_name': self.index_name,
            'db_path': str(self.db_path),
            'db_size': self._get_db_size(),
            'last_updated': self._get_last_updated(),
            'record_count': self._get_record_count()
        }
        
        return stats
    
    def _get_db_size(self) -> int:
        """获取数据库文件大小（字节）"""
        if self.db_path.exists():
            return self.db_path.stat().st_size
        return 0
    
    def _get_last_updated(self) -> Optional[str]:
        """获取最后更新时间"""
        if not self.db_path.exists():
            return None
        
        mtime = self.db_path.stat().st_mtime
        return datetime.fromtimestamp(mtime).isoformat()
    
    def _get_record_count(self) -> int:
        """获取记录数量（子类实现）"""
        return 0
    
    def clear(self):
        """清空索引"""
        if self.conn:
            self.conn.close()
        
        if self.db_path.exists():
            self.db_path.unlink()
        
        self._init_connection()
        logger.info(f"索引已清空: {self.index_name}")
    
    def optimize(self):
        """优化索引（VACUUM）"""
        if self.conn:
            self.conn.execute('VACUUM')
            self.conn.commit()
            logger.info(f"索引已优化: {self.index_name}")
    
    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()
            self.conn = None
            logger.info(f"索引连接已关闭: {self.index_name}")
    
    def __enter__(self):
        """上下文管理器入口"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.close()
    
    def __del__(self):
        """析构函数"""
        self.close()
