#!/usr/bin/env python3
"""
配置加载器
统一加载和管理启发式推理系统的配置
"""

import yaml
from pathlib import Path
from typing import Dict, Any, Optional

# 默认配置（作为fallback）
DEFAULT_CONFIG = {
    'similarity_weights': {
        'types': 0.3,
        'properties': 0.4,
        'trigger_mechanisms': 0.2,
        'stats': 0.05,
        'constraints': 0.05
    },
    'defaults': {
        'similarity_threshold': 0.7,
        'confidence_threshold': 0.8,
        'max_diffuse_results': 10,
        'max_inference_depth': 5,
        'anomaly_threshold': 0.5,
        'max_path_depth': 5,
        'max_neighbors': 100
    },
    'trigger_detection': {
        'meta_indicators': ['Meta', 'GeneratesEnergy', 'energy'],
        'hazard_indicators': ['Hazard'],
        'creation_indicators': ['undoing', 'creation', 'does_not_use_energy']
    },
    'reasoning': {
        'max_reasoning_depth': 5,
        'confidence_decay': 0.9,
        'min_confidence': 0.5
    },
    'logging': {
        'level': 'INFO',
        'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    }
}


class ConfigLoader:
    """配置加载器类"""
    
    _instance: Optional['ConfigLoader'] = None
    _config: Optional[Dict[str, Any]] = None
    _config_path: Optional[Path] = None
    
    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """初始化配置加载器"""
        if self._config is None:
            self._config = DEFAULT_CONFIG.copy()
    
    def load(self, config_path: str = None) -> Dict[str, Any]:
        """
        加载配置文件
        
        Args:
            config_path: 配置文件路径（可选）
            
        Returns:
            配置字典
        """
        # 如果指定了配置路径
        if config_path:
            self._config_path = Path(config_path)
        # 否则使用默认路径
        elif self._config_path is None:
            # 默认路径：config/heuristic_config.yaml
            self._config_path = Path(__file__).parent.parent / 'config' / 'heuristic_config.yaml'
        
        # 尝试加载配置文件
        if self._config_path.exists():
            try:
                with open(self._config_path, 'r', encoding='utf-8') as f:
                    loaded_config = yaml.safe_load(f)
                    # 合并配置（加载的配置覆盖默认配置）
                    self._config = self._deep_merge(DEFAULT_CONFIG, loaded_config)
            except Exception as e:
                print(f"[WARN] 加载配置文件失败: {e}，使用默认配置")
        else:
            print(f"[WARN] 配置文件不存在: {self._config_path}，使用默认配置")
        
        return self._config
    
    def _deep_merge(self, base: Dict, override: Dict) -> Dict:
        """
        深度合并两个字典
        
        Args:
            base: 基础字典
            override: 覆盖字典
            
        Returns:
            合并后的字典
        """
        result = base.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        
        return result
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置项（支持点号分隔的路径）
        
        Args:
            key: 配置键（如 'similarity_weights.types'）
            default: 默认值
            
        Returns:
            配置值
        """
        keys = key.split('.')
        value = self._config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def get_similarity_weights(self) -> Dict[str, float]:
        """获取相似度权重"""
        return self.get('similarity_weights', DEFAULT_CONFIG['similarity_weights'])
    
    def get_default_threshold(self) -> float:
        """获取默认相似度阈值"""
        return self.get('defaults.similarity_threshold', DEFAULT_CONFIG['defaults']['similarity_threshold'])
    
    def get_max_diffuse_results(self) -> int:
        """获取最大扩散结果数"""
        return self.get('defaults.max_diffuse_results', DEFAULT_CONFIG['defaults']['max_diffuse_results'])
    
    def get_config(self) -> Dict[str, Any]:
        """获取完整配置"""
        return self._config.copy()
    
    def reload(self) -> Dict[str, Any]:
        """重新加载配置"""
        self._config = None
        return self.load()


# 全局配置加载器实例
_config_loader = None


def get_config_loader() -> ConfigLoader:
    """获取全局配置加载器实例"""
    global _config_loader
    if _config_loader is None:
        _config_loader = ConfigLoader()
        _config_loader.load()
    return _config_loader


def get_config(key: str = None, default: Any = None) -> Any:
    """
    获取配置（便捷函数）
    
    Args:
        key: 配置键（可选，不提供则返回完整配置）
        default: 默认值
        
    Returns:
        配置值或完整配置
    """
    loader = get_config_loader()
    if key is None:
        return loader.get_config()
    return loader.get(key, default)


def reload_config() -> Dict[str, Any]:
    """重新加载配置"""
    loader = get_config_loader()
    return loader.reload()


# 使用示例
if __name__ == '__main__':
    # 加载配置
    config = get_config()
    print("完整配置:")
    print(config)
    
    # 获取特定配置项
    print("\n相似度权重:")
    print(get_config('similarity_weights'))
    
    print("\n默认阈值:")
    print(get_config('defaults.similarity_threshold'))
