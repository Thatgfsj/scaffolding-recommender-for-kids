"""
脚手架算法 - 数据存储与状态管理
支持 SQLite 持久化 + Redis 会话缓存
"""

import sqlite3
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import pickle

# ========== Learner Profile ==========

@dataclass
class LearnerProfile:
    """学习者画像"""
    user_id: str
    name: str
    age_group: str
    created_at: str
    last_active: str
    
    # 交互历史
    watch_history: List[Dict]  # [{video_id, action, timestamp, duration}]
    
    # 成长性指标
    zpd_velocity: float = 0.0           # 挑战更高难度频率变化
    tool_appropriation: float = 0.0      # 使用脚手架后独立解决比例
    curiosity_spark: float = 0.0         # 自发探索次数
    
    # 能力状态
    current_zpd_low: int = 1             # 当前ZPD下限
    current_zpd_high: int = 3            # 当前ZPD上限
    dominant_interests: List[str] = None  # 主要兴趣标签
    
    # 累积指标
    total_watches: int = 0
    natural_end_count: int = 0
    total_watch_time: int = 0
    
    def __post_init__(self):
        if self.dominant_interests is None:
            self.dominant_interests = []
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, d: Dict) -> 'LearnerProfile':
        return cls(**d)


class StorageManager:
    """存储管理器 - SQLite + Redis"""
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = os.path.join(os.path.dirname(__file__), 'scaffolding.db')
        
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """初始化数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 用户画像表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS learner_profiles (
                user_id TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        ''')
        
        # 事件日志表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                event_data TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                session_id TEXT
            )
        ''')
        
        # 推荐日志表（用于A/B测试和分析）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS recommendations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                rec_list TEXT NOT NULL,
                model_version TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
        ''')
        
        # 家长设置表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS parent_settings (
                user_id TEXT PRIMARY KEY,
                risk_tolerance REAL DEFAULT 0.5,
                diversity_preference REAL DEFAULT 0.5,
                value_focus TEXT DEFAULT '{}',
                strategy_params TEXT DEFAULT '{}',
                updated_at TEXT NOT NULL
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def save_learner_profile(self, profile: LearnerProfile):
        """保存学习者画像"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO learner_profiles (user_id, data, updated_at)
            VALUES (?, ?, ?)
        ''', (profile.user_id, json.dumps(profile.to_dict()), datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
    
    def load_learner_profile(self, user_id: str) -> Optional[LearnerProfile]:
        """加载学习者画像"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT data FROM learner_profiles WHERE user_id = ?', (user_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return LearnerProfile.from_dict(json.loads(row[0]))
        return None
    
    def log_event(self, user_id: str, event_type: str, event_data: Dict, session_id: str = None):
        """记录事件到日志"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO events (user_id, event_type, event_data, timestamp, session_id)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, event_type, json.dumps(event_data), datetime.now().isoformat(), session_id))
        
        conn.commit()
        conn.close()
    
    def get_events(self, user_id: str, event_type: str = None, limit: int = 100) -> List[Dict]:
        """获取事件日志"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if event_type:
            cursor.execute('''
                SELECT event_type, event_data, timestamp 
                FROM events 
                WHERE user_id = ? AND event_type = ?
                ORDER BY timestamp DESC
                LIMIT ?
            ''', (user_id, event_type, limit))
        else:
            cursor.execute('''
                SELECT event_type, event_data, timestamp 
                FROM events 
                WHERE user_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
            ''', (user_id, limit))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [{'event_type': r[0], 'event_data': json.loads(r[1]), 'timestamp': r[2]} for r in rows]
    
    def save_parent_settings(self, user_id: str, settings: Dict):
        """保存家长设置"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO parent_settings 
            (user_id, risk_tolerance, diversity_preference, value_focus, strategy_params, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            user_id,
            settings.get('risk_tolerance', 0.5),
            settings.get('diversity_preference', 0.5),
            json.dumps(settings.get('value_focus', {})),
            json.dumps(settings.get('strategy_params', {})),
            datetime.now().isoformat()
        ))
        
        conn.commit()
        conn.close()
    
    def load_parent_settings(self, user_id: str) -> Dict:
        """加载家长设置"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM parent_settings WHERE user_id = ?', (user_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'risk_tolerance': row[1],
                'diversity_preference': row[2],
                'value_focus': json.loads(row[3]),
                'strategy_params': json.loads(row[4])
            }
        
        return {
            'risk_tolerance': 0.5,
            'diversity_preference': 0.5,
            'value_focus': {},
            'strategy_params': {}
        }
    
    def log_recommendation(self, user_id: str, rec_list: List[str], model_version: str = 'v1.0'):
        """记录推荐结果（用于A/B测试）"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO recommendations (user_id, rec_list, model_version, timestamp)
            VALUES (?, ?, ?, ?)
        ''', (user_id, json.dumps(rec_list), model_version, datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
    
    def get_analytics(self, user_id: str, days: int = 7) -> Dict:
        """获取分析数据"""
        since = (datetime.now() - timedelta(days=days)).isoformat()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 统计各类事件
        cursor.execute('''
            SELECT event_type, COUNT(*) 
            FROM events 
            WHERE user_id = ? AND timestamp > ?
            GROUP BY event_type
        ''', (user_id, since))
        
        event_counts = {row[0]: row[1] for row in cursor.fetchall()}
        
        # 统计推荐
        cursor.execute('''
            SELECT COUNT(*) FROM recommendations 
            WHERE user_id = ? AND timestamp > ?
        ''', (user_id, since))
        
        rec_count = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            'period_days': days,
            'event_counts': event_counts,
            'recommendation_count': rec_count
        }


# ========== Contextual Bandit ==========

class ContextualBandit:
    """
    上下文老虎机 - 在线学习核心
    
    使用 Thompson Sampling 进行探索-利用平衡
    特征：用户状态、内容特征、上下文
    """
    
    def __init__(self, n_arms: int = 4):
        self.n_arms = n_arms
        # 每个臂的 Beta 分布参数
        self.alpha = [1.0] * n_arms  # 成功次数 + 1
        self.beta = [1.0] * n_arms   # 失败次数 + 1
        
        # 特征权重（简化版线性模型）
        self.weights = [0.0] * 10  # 10维特征
        
    def select_arm(self, context: Dict) -> int:
        """
        基于上下文选择臂
        使用 Thompson Sampling
        """
        import random
        
        # 从 Beta 分布采样
        samples = [random.betavariate(self.alpha[i], self.beta[i]) for i in range(self.n_arms)]
        
        # 结合上下文特征调整
        context_bonus = self._compute_context_bonus(context)
        
        # 最终得分 = 采样值 + 上下文调整
        scores = [s + context_bonus[i] * 0.1 for i, s in enumerate(samples)]
        
        return scores.index(max(scores))
    
    def _compute_context_bonus(self, context: Dict) -> List[float]:
        """计算上下文调整"""
        # 简化：基于用户当前状态调整各臂的探索价值
        bubble_risk = context.get('bubble_risk', 0.0)
        zpd_velocity = context.get('zpd_velocity', 0.0)
        
        # 茧房风险高时，多样性臂更有价值
        diversity_bonus = bubble_risk * 0.5
        
        return [
            0.0,           # exploitation arm
            diversity_bonus,  # diversity arm
            zpd_velocity * 0.3,  # scaffolding arm
            0.1            # exploration arm
        ]
    
    def update(self, arm: int, reward: float):
        """
        更新臂的参数
        reward: 0.0 (negative) ~ 1.0 (positive)
        """
        # 简化的奖励更新
        if reward > 0.5:
            self.alpha[arm] += reward
        else:
            self.beta[arm] += (1 - reward)
    
    def get_stats(self) -> Dict:
        """获取各臂的统计"""
        return {
            'arms': [
                {'id': i, 'alpha': self.alpha[i], 'beta': self.beta[i], 
                 'expected': self.alpha[i] / (self.alpha[i] + self.beta[i])}
                for i in range(self.n_arms)
            ]
        }


# ========== Content Moderation Pipeline ==========

class ContentModerator:
    """
    内容审核管道
    
    第一阶段：基于规则过滤
    第二阶段：ML分类器预过滤
    """
    
    def __init__(self):
        self.rule_filters = [
            self._filter_title_duplication,
            self._filter_grammar_complexity,
            self._filter_emotional_polarization,
        ]
        
        # 模拟ML分类器（实际应使用DistilBERT等）
        self.classifier_loaded = False
    
    def check_content(self, content: Dict) -> Dict:
        """
        检查内容，返回审核结果
        """
        result = {
            'passed': True,
            'risk_score': 0.0,
            'flags': [],
            'filter_stage': 'passed'
        }
        
        # 第一阶段：规则过滤
        for filter_func in self.rule_filters:
            filter_result = filter_func(content)
            if not filter_result['passed']:
                result['passed'] = False
                result['risk_score'] = max(result['risk_score'], filter_result['risk_score'])
                result['flags'].append(filter_result['reason'])
                result['filter_stage'] = 'rule_filtered'
                break
        
        # 第二阶段：ML分类（如果有）
        if result['passed'] and self.classifier_loaded:
            ml_result = self._ml_classify(content)
            if ml_result['risk_score'] > 0.7:
                result['passed'] = False
                result['risk_score'] = ml_result['risk_score']
                result['flags'].append(ml_result['reason'])
                result['filter_stage'] = 'ml_filtered'
        
        return result
    
    def _filter_title_duplication(self, content: Dict) -> Dict:
        """标题去重"""
        # 简化：检查是否包含过多重复词
        title = content.get('title', '')
        words = title.split()
        
        if len(words) > 0:
            word_counts = {}
            for w in words:
                word_counts[w] = word_counts.get(w, 0) + 1
            
            max_repeat = max(word_counts.values()) if word_counts else 0
            if max_repeat / len(words) > 0.5:
                return {'passed': False, 'risk_score': 0.8, 'reason': 'title_duplication'}
        
        return {'passed': True, 'risk_score': 0.0, 'reason': None}
    
    def _filter_grammar_complexity(self, content: Dict) -> Dict:
        """语法复杂度过低检测"""
        title = content.get('title', '')
        desc = content.get('description', '')
        
        text = title + ' ' + desc
        
        # 简化：短句+感叹号过多
        sentences = text.split('！')
        if len(sentences) > 5:
            return {'passed': False, 'risk_score': 0.6, 'reason': 'excessive_exclamation'}
        
        # 检查是否全是大写/符号
        letter_count = sum(1 for c in text if c.isalpha())
        if letter_count > 0:
            upper_ratio = sum(1 for c in text if c.isupper()) / letter_count
            if upper_ratio > 0.5:
                return {'passed': False, 'risk_score': 0.5, 'reason': 'excessive_caps'}
        
        return {'passed': True, 'risk_score': 0.0, 'reason': None}
    
    def _filter_emotional_polarization(self, content: Dict) -> Dict:
        """情感极化检测"""
        # 简化：检测极端情感词
        extreme_words = ['最棒', '最差', '绝对', '必须', '惊人', '恐怖']
        title = content.get('title', '')
        
        for word in extreme_words:
            if word in title:
                return {'passed': False, 'risk_score': 0.4, 'reason': 'emotional_polarization'}
        
        return {'passed': True, 'risk_score': 0.0, 'reason': None}
    
    def _ml_classify(self, content: Dict) -> Dict:
        """ML分类器（模拟）"""
        # 实际应使用微调的DistilBERT分类器
        # 这里简化返回
        return {'risk_score': 0.0, 'reason': None, 'model': 'mock'}
    
    def load_ml_classifier(self, model_path: str = None):
        """加载ML分类器"""
        # TODO: 实际加载DistilBERT模型
        # from transformers import pipeline
        # self.classifier = pipeline("text-classification", model="distilbert-base-uncased")
        self.classifier_loaded = True
        print("[ContentModerator] ML classifier loaded (mock mode)")


# ========== Observability Metrics ==========

class MetricsCollector:
    """可观测性指标收集器"""
    
    def __init__(self, storage: StorageManager = None):
        self.storage = storage
        self.in_memory_metrics = {
            'recommendations_served': 0,
            'clicks': 0,
            'natural_ends': 0,
            'skips': 0,
            'auto_nexts': 0,
            'diversity_quota_hits': 0,
            'zpd_hits': 0,
            'avg_latency_ms': 0,
            'errors': 0
        }
        
        self.latencies = []
    
    def record_recommendation(self, user_id: str, n_items: int, latency_ms: float):
        """记录推荐请求"""
        self.in_memory_metrics['recommendations_served'] += 1
        self.latencies.append(latency_ms)
        
        # 保持最近1000个延迟记录
        if len(self.latencies) > 1000:
            self.latencies = self.latencies[-1000:]
        
        self.in_memory_metrics['avg_latency_ms'] = sum(self.latencies) / len(self.latencies)
        
        if self.storage:
            self.storage.log_event(user_id, 'rec_served', {
                'n_items': n_items, 'latency_ms': latency_ms
            })
    
    def record_action(self, user_id: str, action: str):
        """记录用户行为"""
        action_map = {
            'watch': 'clicks',
            'natural_end': 'natural_ends',
            'skip': 'skips',
            'auto_next': 'auto_nexts'
        }
        
        metric_key = action_map.get(action)
        if metric_key:
            self.in_memory_metrics[metric_key] += 1
        
        if self.storage:
            self.storage.log_event(user_id, 'user_action', {'action': action})
    
    def record_diversity_quota_hit(self):
        """记录多样性配额命中"""
        self.in_memory_metrics['diversity_quota_hits'] += 1
    
    def record_zpd_hit(self):
        """记录ZPD命中"""
        self.in_memory_metrics['zpd_hits'] += 1
    
    def record_error(self):
        """记录错误"""
        self.in_memory_metrics['errors'] += 1
    
    def get_business_metrics(self) -> Dict:
        """业务指标"""
        total = self.in_memory_metrics['clicks'] + self.in_memory_metrics['skips']
        natural_end_rate = (self.in_memory_metrics['natural_ends'] / total * 100) if total > 0 else 0
        
        return {
            'recommendations_served': self.in_memory_metrics['recommendations_served'],
            'total_interactions': total,
            'natural_end_rate': round(natural_end_rate, 2),
            'skip_rate': round(self.in_memory_metrics['skips'] / total * 100, 2) if total > 0 else 0,
            'diversity_quota_hit_rate': round(
                self.in_memory_metrics['diversity_quota_hits'] / 
                max(1, self.in_memory_metrics['recommendations_served']) * 100, 2
            ),
            'zpd_hit_rate': round(
                self.in_memory_metrics['zpd_hits'] / 
                max(1, self.in_memory_metrics['recommendations_served']) * 100, 2
            )
        }
    
    def get_model_metrics(self) -> Dict:
        """模型指标"""
        return {
            'novelty_score': 0.7,  # TODO: 实际计算
            'zpd命中率': self.in_memory_metrics['zpd_hits'],
            '推荐延迟_p99_ms': sorted(self.latencies)[int(len(self.latencies) * 0.99)] if self.latencies else 0,
            'error_rate': round(
                self.in_memory_metrics['errors'] / 
                max(1, self.in_memory_metrics['recommendations_served']) * 100, 2
            )
        }
    
    def get_system_metrics(self) -> Dict:
        """系统指标"""
        return {
            'recommendations_served': self.in_memory_metrics['recommendations_served'],
            'avg_latency_ms': round(self.in_memory_metrics['avg_latency_ms'], 2),
            'error_count': self.in_memory_metrics['errors'],
            'error_rate': round(
                self.in_memory_metrics['errors'] / 
                max(1, self.in_memory_metrics['recommendations_served']) * 100, 2
            )
        }


if __name__ == '__main__':
    # 测试存储
    storage = StorageManager(':memory:')
    
    # 测试保存/加载
    profile = LearnerProfile(
        user_id='test_user',
        name='小明',
        age_group='6-9岁',
        created_at=datetime.now().isoformat(),
        last_active=datetime.now().isoformat(),
        watch_history=[]
    )
    storage.save_learner_profile(profile)
    loaded = storage.load_learner_profile('test_user')
    print(f"Profile loaded: {loaded.name}")
    
    # 测试上下文老虎机
    bandit = ContextualBandit(n_arms=4)
    context = {'bubble_risk': 0.5, 'zpd_velocity': 0.3}
    arm = bandit.select_arm(context)
    print(f"Selected arm: {arm}")
    
    # 测试内容审核
    moderator = ContentModerator()
    result = moderator.check_content({
        'title': '震惊！！！最棒的！！！',
        'description': 'test'
    })
    print(f"Moderation result: {result}")
    
    # 测试指标收集
    metrics = MetricsCollector()
    metrics.record_recommendation('test_user', 10, 50.0)
    metrics.record_action('test_user', 'watch')
    print(f"Business metrics: {metrics.get_business_metrics()}")
