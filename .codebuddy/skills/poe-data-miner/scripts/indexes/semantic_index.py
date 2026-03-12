"""
语义特征索引

四级索引：支持语义级别的快速搜索和相似度计算
"""

import re
import json
import logging
import pickle
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
from collections import defaultdict, Counter
import sqlite3

from .base_index import BaseIndex

logger = logging.getLogger(__name__)


class SemanticFeatureIndex(BaseIndex):
    """语义特征四级索引"""
    
    def __init__(self, db_path: str):
        """
        初始化语义特征索引
        
        Args:
            db_path: 索引数据库路径
        """
        super().__init__(db_path, 'semantic_index')
        self.feature_dim = 128  # 特征向量维度
    
    def _create_tables(self):
        """创建索引表"""
        cursor = self.conn.cursor()
        
        # 实体特征表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS entity_features (
                entity_name TEXT PRIMARY KEY,
                entity_type TEXT,
                feature_vector BLOB,
                keywords TEXT,
                tags TEXT,
                description TEXT,
                skill_types TEXT,
                stats TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 特征相似度缓存表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS similarity_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entity1 TEXT NOT NULL,
                entity2 TEXT NOT NULL,
                similarity_score REAL NOT NULL,
                common_features TEXT,
                last_computed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(entity1, entity2)
            )
        ''')
        
        # 关键词索引表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS keyword_index (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                keyword TEXT NOT NULL,
                entity_name TEXT NOT NULL,
                weight REAL DEFAULT 1.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 标签索引表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tag_index (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tag TEXT NOT NULL,
                entity_name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 创建索引
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_entity_name ON entity_features(entity_name)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_entity_type ON entity_features(entity_type)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_keyword ON keyword_index(keyword)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_tag ON tag_index(tag)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_similarity ON similarity_cache(entity1, entity2)')
        
        self.conn.commit()
    
    def build_index(self, pob_data_path: str):
        """
        构建语义特征索引
        
        Args:
            pob_data_path: POB数据路径
        """
        logger.info(f"开始构建语义特征索引: {pob_data_path}")
        
        # 1. 从实体库加载实体数据
        entities = self._load_entities_from_db(pob_data_path)
        
        # 2. 提取特征
        for entity_name, entity_data in entities.items():
            features = self._extract_features(entity_data)
            self._insert_entity_features(entity_name, entity_data, features)
        
        # 3. 构建关键词和标签索引
        self._build_keyword_index(entities)
        self._build_tag_index(entities)
        
        # 4. 预计算高频实体的相似度
        self._precompute_similarity()
        
        logger.info(f"语义特征索引构建完成: {self._get_record_count()} 个实体")
    
    def _load_entities_from_db(self, pob_data_path: str) -> Dict[str, Any]:
        """从实体库加载实体数据"""
        entities = {}
        
        # 查找entities.db
        pob_path = Path(pob_data_path)
        entities_db = pob_path.parent / 'knowledge_base' / 'entities.db'
        
        if not entities_db.exists():
            logger.warning(f"实体库不存在: {entities_db}")
            return entities
        
        try:
            conn = sqlite3.connect(str(entities_db))
            conn.row_factory = sqlite3.Row
            
            cursor = conn.cursor()
            
            # 加载所有实体
            rows = cursor.execute('''
                SELECT name, type, tags, skill_types, stats, description 
                FROM entities
            ''').fetchall()
            
            for row in rows:
                entity_name = row['name']
                entities[entity_name] = {
                    'name': entity_name,
                    'type': row['type'],
                    'tags': json.loads(row['tags']) if row['tags'] else [],
                    'skill_types': json.loads(row['skill_types']) if row['skill_types'] else [],
                    'stats': json.loads(row['stats']) if row['stats'] else [],
                    'description': row['description'] or ''
                }
            
            conn.close()
            
        except Exception as e:
            logger.error(f"加载实体库失败: {e}")
        
        return entities
    
    def _extract_features(self, entity_data: Dict) -> Dict[str, Any]:
        """
        提取实体特征
        
        特征类型：
        1. 类型特征
        2. 标签特征（tags）
        3. 关键词特征（从描述中提取）
        4. 统计特征（stats）
        5. SkillType特征
        """
        features = {
            'type_features': {},
            'tag_features': {},
            'keyword_features': {},
            'stat_features': {},
            'skilltype_features': {}
        }
        
        # 1. 类型特征
        entity_type = entity_data.get('type', '')
        if entity_type:
            features['type_features'][f'type_{entity_type}'] = 1.0
        
        # 2. 标签特征
        tags = entity_data.get('tags', [])
        for tag in tags:
            features['tag_features'][f'tag_{tag}'] = 1.0
        
        # 3. 关键词特征（从描述中提取）
        description = entity_data.get('description', '')
        keywords = self._extract_keywords(description)
        for keyword, weight in keywords.items():
            features['keyword_features'][f'kw_{keyword}'] = weight
        
        # 4. Stat特征
        stats = entity_data.get('stats', [])
        for stat in stats:
            stat_id = stat if isinstance(stat, str) else stat.get('id', '')
            features['stat_features'][f'stat_{stat_id}'] = 1.0
        
        # 5. SkillType特征
        skill_types = entity_data.get('skill_types', [])
        for skill_type in skill_types:
            features['skilltype_features'][f'st_{skill_type}'] = 1.0
        
        return features
    
    def _extract_keywords(self, text: str) -> Dict[str, float]:
        """
        从文本中提取关键词
        
        使用简单的TF-IDF思想：
        1. 分词
        2. 过滤停用词
        3. 计算词频
        """
        # 停用词列表
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'be',
            'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
            'would', 'should', 'could', 'may', 'might', 'must', 'shall', 'can',
            'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they'
        }
        
        # 简单分词（按空格和标点）
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
        
        # 过滤停用词并统计词频
        word_freq = Counter(word for word in words if word not in stop_words)
        
        # 归一化权重
        max_freq = max(word_freq.values()) if word_freq else 1
        
        keywords = {word: freq / max_freq for word, freq in word_freq.items()}
        
        return keywords
    
    def _insert_entity_features(self, entity_name: str, entity_data: Dict, features: Dict):
        """插入实体特征"""
        cursor = self.conn.cursor()
        
        # 将特征转换为特征向量（简化版：使用哈希）
        feature_vector = self._features_to_vector(features)
        
        # 序列化特征向量
        vector_blob = pickle.dumps(feature_vector)
        
        # 提取关键词
        keywords = list(features['keyword_features'].keys())
        
        # 提取标签
        tags = entity_data.get('tags', [])
        
        cursor.execute('''
            INSERT OR REPLACE INTO entity_features 
            (entity_name, entity_type, feature_vector, keywords, tags, 
             description, skill_types, stats)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            entity_name,
            entity_data.get('type', ''),
            vector_blob,
            json.dumps(keywords),
            json.dumps(tags),
            entity_data.get('description', ''),
            json.dumps(entity_data.get('skill_types', [])),
            json.dumps(entity_data.get('stats', []))
        ))
        
        self.conn.commit()
    
    def _features_to_vector(self, features: Dict) -> List[float]:
        """
        将特征转换为特征向量
        
        使用哈希技巧（hashing trick）：
        将特征名称哈希到固定维度的向量空间
        """
        vector = [0.0] * self.feature_dim
        
        # 合并所有特征
        all_features = {}
        for feature_type, feature_dict in features.items():
            all_features.update(feature_dict)
        
        # 哈希特征到向量
        for feature_name, value in all_features.items():
            # 使用特征名称的哈希值确定位置
            index = hash(feature_name) % self.feature_dim
            vector[index] += value
        
        # L2归一化
        norm = sum(v ** 2 for v in vector) ** 0.5
        if norm > 0:
            vector = [v / norm for v in vector]
        
        return vector
    
    def _build_keyword_index(self, entities: Dict[str, Any]):
        """构建关键词索引"""
        cursor = self.conn.cursor()
        
        for entity_name, entity_data in entities.items():
            description = entity_data.get('description', '')
            keywords = self._extract_keywords(description)
            
            for keyword, weight in keywords.items():
                cursor.execute('''
                    INSERT INTO keyword_index (keyword, entity_name, weight)
                    VALUES (?, ?, ?)
                ''', (keyword, entity_name, weight))
        
        self.conn.commit()
    
    def _build_tag_index(self, entities: Dict[str, Any]):
        """构建标签索引"""
        cursor = self.conn.cursor()
        
        for entity_name, entity_data in entities.items():
            tags = entity_data.get('tags', [])
            
            for tag in tags:
                cursor.execute('''
                    INSERT INTO tag_index (tag, entity_name)
                    VALUES (?, ?)
                ''', (tag, entity_name))
        
        self.conn.commit()
    
    def _precompute_similarity(self, top_k: int = 100):
        """预计算高频实体的相似度"""
        logger.info("预计算实体相似度...")
        
        cursor = self.conn.cursor()
        
        # 获取高频实体（根据标签数量）
        entities = cursor.execute('''
            SELECT entity_name FROM entity_features 
            ORDER BY length(tags) DESC 
            LIMIT ?
        ''', (top_k,)).fetchall()
        
        entity_names = [e['entity_name'] for e in entities]
        
        # 计算两两相似度
        count = 0
        for i, entity1 in enumerate(entity_names):
            for j, entity2 in enumerate(entity_names[i+1:], i+1):
                similarity, common_features = self._calculate_similarity(entity1, entity2)
                
                if similarity > 0.5:  # 只缓存高相似度
                    cursor.execute('''
                        INSERT OR REPLACE INTO similarity_cache 
                        (entity1, entity2, similarity_score, common_features)
                        VALUES (?, ?, ?, ?)
                    ''', (entity1, entity2, similarity, json.dumps(common_features)))
                    
                    count += 1
        
        self.conn.commit()
        logger.info(f"预计算相似度完成: {count} 对")
    
    def _calculate_similarity(self, entity1: str, entity2: str) -> Tuple[float, List[str]]:
        """
        计算两个实体的相似度
        
        使用余弦相似度
        """
        cursor = self.conn.cursor()
        
        # 获取特征向量
        vec1_row = cursor.execute(
            'SELECT feature_vector FROM entity_features WHERE entity_name = ?',
            (entity1,)
        ).fetchone()
        
        vec2_row = cursor.execute(
            'SELECT feature_vector FROM entity_features WHERE entity_name = ?',
            (entity2,)
        ).fetchone()
        
        if not vec1_row or not vec2_row:
            return 0.0, []
        
        vec1 = pickle.loads(vec1_row['feature_vector'])
        vec2 = pickle.loads(vec2_row['feature_vector'])
        
        # 计算余弦相似度
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = sum(a ** 2 for a in vec1) ** 0.5
        norm2 = sum(b ** 2 for b in vec2) ** 0.5
        
        if norm1 == 0 or norm2 == 0:
            return 0.0, []
        
        similarity = dot_product / (norm1 * norm2)
        
        # 提取共同特征
        common_features = self._find_common_features(entity1, entity2)
        
        return similarity, common_features
    
    def _find_common_features(self, entity1: str, entity2: str) -> List[str]:
        """查找两个实体的共同特征"""
        cursor = self.conn.cursor()
        
        # 获取标签
        tags1 = set(cursor.execute(
            'SELECT tag FROM tag_index WHERE entity_name = ?',
            (entity1,)
        ).fetchall())
        
        tags2 = set(cursor.execute(
            'SELECT tag FROM tag_index WHERE entity_name = ?',
            (entity2,)
        ).fetchall())
        
        # 获取关键词
        kw1 = set(cursor.execute(
            'SELECT keyword FROM keyword_index WHERE entity_name = ?',
            (entity1,)
        ).fetchall())
        
        kw2 = set(cursor.execute(
            'SELECT keyword FROM keyword_index WHERE entity_name = ?',
            (entity2,)
        ).fetchall())
        
        # 合并共同特征
        common_tags = [t['tag'] for t in tags1 & tags2]
        common_kw = [k['keyword'] for k in kw1 & kw2]
        
        return common_tags + common_kw
    
    def update_index(self, changed_file: str):
        """
        增量更新索引
        
        Args:
            changed_file: 变更的文件路径
        """
        # 语义索引通常需要完全重建，因为实体特征相互关联
        # 这里简化处理：只更新单个实体
        pass
    
    def search(self, query: Dict[str, Any]) -> Dict[str, Any]:
        """
        搜索语义索引
        
        Args:
            query: 查询参数，支持:
                - entity: 实体名称（查找相似实体）
                - keywords: 关键词列表
                - tags: 标签列表
                - features: 特征字典
                
        Returns:
            查询结果
        """
        cursor = self.conn.cursor()
        
        # 查找相似实体
        if 'entity' in query:
            entity_name = query['entity']
            top_k = query.get('top_k', 10)
            
            # 尝试从缓存读取
            cached = cursor.execute('''
                SELECT entity2, similarity_score, common_features 
                FROM similarity_cache 
                WHERE entity1 = ? 
                ORDER BY similarity_score DESC 
                LIMIT ?
            ''', (entity_name, top_k)).fetchall()
            
            if cached:
                return {
                    'found': True,
                    'similar_entities': [
                        {
                            'entity': row['entity2'],
                            'similarity': row['similarity_score'],
                            'common_features': json.loads(row['common_features'])
                        }
                        for row in cached
                    ]
                }
            
            # 缓存未命中，实时计算
            return self._find_similar_entities_realtime(entity_name, top_k)
        
        # 按关键词搜索
        elif 'keywords' in query:
            keywords = query['keywords']
            
            results = cursor.execute('''
                SELECT entity_name, SUM(weight) as total_weight
                FROM keyword_index
                WHERE keyword IN ({})
                GROUP BY entity_name
                ORDER BY total_weight DESC
                LIMIT ?
            '''.format(','.join('?' * len(keywords))), keywords + [100]).fetchall()
            
            return {
                'found': len(results) > 0,
                'entities': [dict(r) for r in results]
            }
        
        # 按标签搜索
        elif 'tags' in query:
            tags = query['tags']
            
            results = cursor.execute('''
                SELECT entity_name, COUNT(*) as tag_count
                FROM tag_index
                WHERE tag IN ({})
                GROUP BY entity_name
                ORDER BY tag_count DESC
                LIMIT ?
            '''.format(','.join('?' * len(tags))), tags + [100]).fetchall()
            
            return {
                'found': len(results) > 0,
                'entities': [dict(r) for r in results]
            }
        
        return {'found': False}
    
    def _find_similar_entities_realtime(self, entity_name: str, top_k: int) -> Dict[str, Any]:
        """实时查找相似实体"""
        cursor = self.conn.cursor()
        
        # 获取目标实体特征
        target = cursor.execute(
            'SELECT feature_vector FROM entity_features WHERE entity_name = ?',
            (entity_name,)
        ).fetchone()
        
        if not target:
            return {'found': False}
        
        target_vec = pickle.loads(target['feature_vector'])
        
        # 获取所有其他实体
        all_entities = cursor.execute(
            'SELECT entity_name, feature_vector FROM entity_features WHERE entity_name != ?',
            (entity_name,)
        ).fetchall()
        
        # 计算相似度
        similarities = []
        
        for row in all_entities:
            other_vec = pickle.loads(row['feature_vector'])
            
            # 余弦相似度
            dot_product = sum(a * b for a, b in zip(target_vec, other_vec))
            norm1 = sum(a ** 2 for a in target_vec) ** 0.5
            norm2 = sum(b ** 2 for b in other_vec) ** 0.5
            
            if norm1 > 0 and norm2 > 0:
                similarity = dot_product / (norm1 * norm2)
                
                if similarity > 0.3:  # 过滤低相似度
                    similarities.append({
                        'entity': row['entity_name'],
                        'similarity': similarity
                    })
        
        # 排序并返回TopK
        similarities.sort(key=lambda x: x['similarity'], reverse=True)
        top_results = similarities[:top_k]
        
        return {
            'found': len(top_results) > 0,
            'similar_entities': top_results
        }
    
    def _get_record_count(self) -> int:
        """获取记录数量"""
        cursor = self.conn.cursor()
        count = cursor.execute('SELECT COUNT(*) FROM entity_features').fetchone()[0]
        return count
    
    def get_entities_by_tag(self, tag: str) -> List[str]:
        """
        根据标签获取实体列表
        
        Args:
            tag: 标签名称
            
        Returns:
            实体名称列表
        """
        cursor = self.conn.cursor()
        
        results = cursor.execute(
            'SELECT entity_name FROM tag_index WHERE tag = ?',
            (tag,)
        ).fetchall()
        
        return [r['entity_name'] for r in results]
    
    def get_entities_by_keyword(self, keyword: str) -> List[Dict[str, Any]]:
        """
        根据关键词获取实体列表
        
        Args:
            keyword: 关键词
            
        Returns:
            实体列表（带权重）
        """
        cursor = self.conn.cursor()
        
        results = cursor.execute('''
            SELECT entity_name, weight 
            FROM keyword_index 
            WHERE keyword = ? 
            ORDER BY weight DESC
        ''', (keyword,)).fetchall()
        
        return [dict(r) for r in results]
    
    def get_entity_features(self, entity_name: str) -> Optional[Dict[str, Any]]:
        """
        获取实体特征
        
        Args:
            entity_name: 实体名称
            
        Returns:
            实体特征字典
        """
        cursor = self.conn.cursor()
        
        row = cursor.execute(
            'SELECT * FROM entity_features WHERE entity_name = ?',
            (entity_name,)
        ).fetchone()
        
        if row:
            return dict(row)
        
        return None
