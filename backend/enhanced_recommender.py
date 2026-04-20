"""
脚手架算法 - 增强版推荐器
整合：内容标签体系 + 学习者画像成长指标 + 家长教养旋钮 + Contextual Bandit
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.storage import (
    LearnerProfile, StorageManager, ContextualBandit, 
    ContentModerator, MetricsCollector
)
from guided_recommender import ValueDimension, ComplexityLevel, AgeGroup, WatchResult
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
import math
import json


# ========== 增强内容标签体系 ==========

class CognitiveChallengeType:
    """认知挑战类型"""
    CAUSAL_REASONING = "因果推理"      # 理解因果关系
    ROLE_TAKING = "角色代入"            # 代入他人视角
    MULTI_PERSPECTIVE = "多视角比较"    # 比较不同观点
    VALUE_DILEMMA = "价值两难判断"       # 处理价值冲突


class EmotionalTone:
    """情感基调"""
    CURIOSITY = "好奇"
    WARMTH = "温暖"
    COURAGE = "勇气"
    CALM = "平静"
    MODERATE_FRUSTRATION = "适度挫败"


class SocialGoal:
    """社会目标"""
    COOPERATION = "合作"
    FAIRNESS = "公平"
    PERSISTENCE = "坚韧"
    RESPECT_DIFFERENCE = "尊重差异"


@dataclass
class EnhancedVideoContent:
    """增强版视频内容"""
    video_id: str
    title: str
    description: str
    category: str
    sub_category: str
    complexity: ComplexityLevel
    age_group: AgeGroup
    
    # 原价值观标签 (保留)
    value_tags: Dict[ValueDimension, float] = field(default_factory=dict)
    
    # 新增：认知挑战类型 (可多选)
    cognitive_challenges: List[str] = field(default_factory=list)
    
    # 新增：情感基调
    emotional_tone: str = "好奇"
    
    # 新增：社会目标 (可多选)
    social_goals: List[str] = field(default_factory=list)
    
    # 质量与互动分
    quality_score: float = 0.5
    engagement_score: float = 0.5
    
    # 引导链路
    scaffolding_next: List[str] = field(default_factory=list)
    scaffolding_prev: List[str] = field(default_factory=list)
    
    # 风险分
    risk_score: float = 0.0
    
    def get_enhanced_tags(self) -> Dict:
        """获取完整标签"""
        return {
            'values': {k.value: v for k, v in self.value_tags.items()},
            'cognitive': self.cognitive_challenges,
            'emotional': self.emotional_tone,
            'social': self.social_goals
        }


# ========== 增强学习者画像 ==========

class EnhancedLearnerProfile(LearnerProfile):
    """增强版学习者画像"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # 成长性指标（新增）
        self.zpd_velocity = 0.0           # 挑战更高难度内容的频率变化
        self.tool_appropriation = 0.0     # 使用脚手架后独立解决比例
        self.curiosity_spark = 0.0         # 自发探索次数
        
        # 能力状态（新增）
        self.current_zpd_low = 1
        self.current_zpd_high = 3
        self.dominant_interests = []
        
        # 历史交互详情（新增）
        self.interaction_details = []  # [{video_id, action, timestamp, duration, scaffolding_used}]
        
        # 探索行为追踪（新增）
        self.spontaneous_explorations = 0  # 自发跳转到非推荐内容的次数
        self.scaffolding_uses = 0          # 使用系统提示的次数
        self.scaffolding_after_success = 0 # 使用后独立解决次数
        
    def update_growth_metrics(self, event: Dict, recommended_content: List[EnhancedVideoContent]):
        """更新成长性指标"""
        video_id = event.get('video_id')
        action = event.get('action')
        
        # 找到对应的内容
        content = next((c for c in recommended_content if c.video_id == video_id), None)
        if not content:
            return
        
        # 更新 ZPD Velocity
        complexity = int(content.complexity.name.replace('L', ''))
        if complexity >= self.current_zpd_high and action == 'natural_end':
            # 成功挑战高难度内容
            self.zpd_velocity = min(1.0, self.zpd_velocity + 0.05)
            # 可能需要上调ZPD上限
            if complexity > self.current_zpd_high:
                self.current_zpd_high = min(6, complexity + 1)
        elif complexity < self.current_zpd_low and action == 'skip':
            # 跳过低于ZPD的内容
            self.zpd_velocity = max(0, self.zpd_velocity - 0.02)
        
        # 更新 Tool Appropriation
        if event.get('scaffolding_used'):
            self.scaffolding_uses += 1
            if event.get('independently_solved'):
                self.scaffolding_after_success += 1
        
        if self.scaffolding_uses > 0:
            self.tool_appropriation = self.scaffolding_after_success / self.scaffolding_uses
        
        # 更新 Curiosity Spark
        # 如果用户跳转到的内容不在推荐列表中，视为自发探索
        if not any(c.video_id == video_id for c in recommended_content):
            if action in ['watch', 'natural_end']:
                self.curiosity_spark += 1
                self.spontaneous_explorations += 1
    
    def get_zpd_status(self) -> Dict:
        """获取ZPD状态"""
        return {
            'zpd_low': self.current_zpd_low,
            'zpd_high': self.current_zpd_high,
            'zpd_velocity': self.zpd_velocity,
            'in_zpd_challenges': sum(1 for e in self.interaction_details 
                                     if self.current_zpd_low <= int(e.get('complexity', 0).replace('L','')) <= self.current_zpd_high)
        }


# ========== 家长教养旋钮 ==========

@dataclass
class ParentingKnobs:
    """家长控制参数"""
    
    # 冒险系数：允许系统推荐超出ZPD上限的频率 (0.0 ~ 1.0)
    # 0 = 完全保守，1 = 允许超出
    risk_tolerance: float = 0.5
    
    # 多样性倾向：偏好深度纵向 vs 广度横向 (0.0 ~ 1.0)
    # 0 = 深度纵向（专注单一主题深挖）
    # 1 = 广度横向（跨领域广泛探索）
    diversity_preference: float = 0.5
    
    # 价值观权重：当前阶段侧重
    value_focus: Dict[str, float] = field(default_factory=lambda: {
        '好奇心': 1.0,
        '同理心': 1.0,
        '责任感': 1.0,
        '多元尊重': 1.0,
        '环保意识': 1.0
    })
    
    # 每周允许观看时长（分钟）
    weekly_time_limit: int = 300
    
    # 是否启用自动茧房干预
    auto_bubble_intervention: bool = True
    
    def to_strategy_params(self) -> Dict:
        """转换为策略参数"""
        return {
            'risk_tolerance': self.risk_tolerance,
            'diversity_preference': self.diversity_preference,
            'value_focus': self.value_focus,
            'weekly_time_limit': self.weekly_time_limit,
            'auto_bubble_intervention': self.auto_bubble_intervention
        }
    
    @classmethod
    def from_dict(cls, d: Dict) -> 'ParentingKnobs':
        return cls(**d)


# ========== 增强推荐器 ==========

class EnhancedScaffoldingRecommender:
    """
    增强版脚手架推荐器
    
    改进点：
    1. 增强内容标签（认知挑战、情感基调、社会目标）
    2. 学习者画像成长性指标
    3. 家长教养旋钮
    4. Contextual Bandit 在线学习
    5. 内容审核管道
    6. 可观测性指标
    """
    
    def __init__(self, storage_path: str = None, use_ml: bool = True):
        self.storage = StorageManager(storage_path)
        self.bandit = ContextualBandit(n_arms=4)
        self.moderator = ContentModerator()
        self.metrics = MetricsCollector(self.storage)
        
        # Contextual Bandit 臂的含义
        self.arm_strategies = {
            0: 'exploitation',      # 利用：推荐最相关的
            1: 'diversity',         # 多样性：跨域探索
            2: 'scaffolding',       # 引导：ZPD内递进
            3: 'exploration'        # 探索：随机发现
        }
        
        self.content_library = {}
        self.current_user = None
        self.parent_knobs = ParentingKnobs()
        self.use_ml = use_ml
        
        self._init_content_library()
    
    def _init_content_library(self):
        """初始化增强版内容库"""
        # 复用原有的内容，添加增强标签
        from guided_recommender import ScaffoldingRecommender
        
        base_recommender = ScaffoldingRecommender(AgeGroup.AGE_6_9)
        
        for video_id, base_content in base_recommender.content_library.items():
            content = EnhancedVideoContent(
                video_id=base_content.video_id,
                title=base_content.title,
                description=base_content.description,
                category=base_content.category,
                sub_category=base_content.sub_category,
                complexity=base_content.complexity,
                age_group=base_content.age_group,
                value_tags=base_content.value_tags,
                quality_score=base_content.quality_score,
                engagement_score=base_content.engagement_score,
                scaffolding_next=base_content.scaffolding_next,
                scaffolding_prev=base_content.scaffolding_prev,
                risk_score=base_content.risk_score
            )
            
            # 自动添加增强标签（基于分类规则）
            self._assign_enhanced_tags(content)
            
            self.content_library[video_id] = content
        
        print(f"[增强推荐器] 内容库初始化完成，共 {len(self.content_library)} 个视频")
    
    def _assign_enhanced_tags(self, content: EnhancedVideoContent):
        """基于规则自动分配增强标签"""
        category = content.category
        
        # 认知挑战类型
        cognitive_map = {
            '科学实验': [CognitiveChallengeType.CAUSAL_REASONING],
            '简单机械': [CognitiveChallengeType.CAUSAL_REASONING, CognitiveChallengeType.MULTI_PERSPECTIVE],
            '液压机械': [CognitiveChallengeType.CAUSAL_REASONING, CognitiveChallengeType.ROLE_TAKING],
            '品格教育': [CognitiveChallengeType.VALUE_DILEMMA, CognitiveChallengeType.ROLE_TAKING],
            '友谊情感': [CognitiveChallengeType.ROLE_TAKING, CognitiveChallengeType.VALUE_DILEMMA],
            '环保意识': [CognitiveChallengeType.MULTI_PERSPECTIVE, CognitiveChallengeType.VALUE_DILEMMA],
        }
        content.cognitive_challenges = cognitive_map.get(category, [CognitiveChallengeType.CAUSAL_REASONING])
        
        # 情感基调
        emotional_map = {
            '玩具开箱': EmotionalTone.CURIOSITY,
            '搞笑宠物': EmotionalTone.WARMTH,
            '科学实验': EmotionalTone.CURIOSITY,
            '手工艺术': EmotionalTone.COURAGE,
            '品格教育': EmotionalTone.WARMTH,
            '友谊情感': EmotionalTone.WARMTH,
            '环保意识': EmotionalTone.CALM,
        }
        content.emotional_tone = emotional_map.get(category, EmotionalTone.CURIOSITY)
        
        # 社会目标
        social_map = {
            '友谊情感': [SocialGoal.COOPERATION, SocialGoal.RESPECT_DIFFERENCE],
            '品格教育': [SocialGoal.PERSISTENCE, SocialGoal.FAIRNESS],
            '环保意识': [SocialGoal.FAIRNESS, SocialGoal.RESPECT_DIFFERENCE],
            '科学实验': [SocialGoal.COOPERATION],
            '手工艺术': [SocialGoal.COOPERATION, SocialGoal.PERSISTENCE],
        }
        content.social_goals = social_map.get(category, [])
    
    def set_user(self, user_id: str):
        """设置用户"""
        self.current_user = self.storage.load_learner_profile(user_id)
        
        if self.current_user is None:
            self.current_user = EnhancedLearnerProfile(
                user_id=user_id,
                name=user_id,
                age_group='6-9岁',
                created_at=datetime.now().isoformat(),
                last_active=datetime.now().isoformat(),
                watch_history=[]
            )
        
        # 加载家长设置
        parent_settings = self.storage.load_parent_settings(user_id)
        self.parent_knobs = ParentingKnobs.from_dict({
            'risk_tolerance': parent_settings.get('risk_tolerance', 0.5),
            'diversity_preference': parent_settings.get('diversity_preference', 0.5),
            'value_focus': parent_settings.get('value_focus', {}),
        })
        
        self.metrics.record_recommendation(user_id, 0, 0)
    
    def set_parent_knobs(self, knobs: Dict) -> Dict:
        """设置家长旋钮"""
        for key, value in knobs.items():
            if hasattr(self.parent_knobs, key):
                setattr(self.parent_knobs, key, value)
        
        # 保存到存储
        self.storage.save_parent_settings(self.current_user.user_id, self.parent_knobs.to_strategy_params())
        
        return {
            'status': 'success',
            'current_knobs': self.parent_knobs.to_strategy_params(),
            'fuguang_comment': self._generate_knob_feedback()
        }
    
    def _generate_knob_feedback(self) -> str:
        """生成旋钮调整反馈"""
        knobs = self.parent_knobs
        
        feedback_parts = []
        
        if knobs.risk_tolerance > 0.7:
            feedback_parts.append("扶光会更有冒险精神，推荐一些有挑战性的内容")
        elif knobs.risk_tolerance < 0.3:
            feedback_parts.append("扶光会保守一些，确保内容在安全区内")
        
        if knobs.diversity_preference > 0.6:
            feedback_parts.append("会带孩子发现更多不同领域")
        elif knobs.diversity_preference < 0.4:
            feedback_parts.append("会专注在一个领域深耕")
        
        return "；".join(feedback_parts) if feedback_parts else "设置已更新，扶光会相应调整推荐策略"
    
    def get_recommendation(self, count: int = 8) -> List[Dict]:
        """
        获取推荐（整合 Contextual Bandit）
        """
        import time
        start_time = time.time()
        
        if self.current_user is None:
            raise ValueError("用户未设置")
        
        # 使用 Contextual Bandit 选择策略
        context = {
            'bubble_risk': self.current_user.bubble_risk if hasattr(self.current_user, 'bubble_risk') else 0.0,
            'zpd_velocity': self.current_user.zpd_velocity if hasattr(self.current_user, 'zpd_velocity') else 0.0,
            'diversity_preference': self.parent_knobs.diversity_preference
        }
        
        selected_arm = self.bandit.select_arm(context)
        strategy = self.arm_strategies[selected_arm]
        
        # 根据策略选择候选
        candidates = self._select_by_strategy(strategy, count)
        
        # 计算推荐得分
        scored = []
        for content in candidates:
            score = self._compute_score(content, strategy)
            
            # 构建推荐理由
            reason = self._generate_reason(content, strategy)
            
            scored.append({
                'video_id': content.video_id,
                'title': content.title,
                'description': content.description,
                'category': content.category,
                'complexity': content.complexity.name,
                'emotional_tone': content.emotional_tone,
                'cognitive_challenges': content.cognitive_challenges,
                'social_goals': content.social_goals,
                'score': score,
                'reason': reason,
                'strategy_used': strategy,
                'tags': content.get_enhanced_tags()
            })
        
        # 排序并返回
        scored.sort(key=lambda x: x['score'], reverse=True)
        results = scored[:count]
        
        # 记录推荐
        latency = (time.time() - start_time) * 1000
        self.metrics.record_recommendation(self.current_user.user_id, len(results), latency)
        
        # 记录带宽臂选择（用于分析）
        self.storage.log_event(self.current_user.user_id, 'arm_selected', {
            'arm': selected_arm,
            'strategy': strategy
        })
        
        return results
    
    def _select_by_strategy(self, strategy: str, count: int) -> List[EnhancedVideoContent]:
        """根据策略选择内容"""
        watched_ids = set()
        if self.current_user and hasattr(self.current_user, 'watch_history'):
            watched_ids = {e[0] for e in self.current_user.watch_history}
        
        candidates = [v for v in self.content_library.values() if v.video_id not in watched_ids]
        
        if strategy == 'exploitation':
            # 利用策略：基于历史相似性
            return candidates[:count]
        
        elif strategy == 'diversity':
            # 多样性策略：选择不同分类
            watched_categories = set()
            if self.current_user and hasattr(self.current_user, 'topic_distribution'):
                watched_categories = set(self.current_user.topic_distribution.keys())
            
            diverse = [v for v in candidates if v.category not in watched_categories]
            return diverse[:count] if diverse else candidates[:count]
        
        elif strategy == 'scaffolding':
            # 引导策略：ZPD 内递进
            if self.current_user and hasattr(self.current_user, 'current_zpd_high'):
                zpd_candidates = [
                    v for v in candidates 
                    if int(v.complexity.name.replace('L', '')) <= self.current_user.current_zpd_high
                ]
                return zpd_candidates[:count] if zpd_candidates else candidates[:count]
            return candidates[:count]
        
        else:  # exploration
            # 探索策略：随机
            import random
            return random.sample(candidates, min(count, len(candidates)))
    
    def _compute_score(self, content: EnhancedVideoContent, strategy: str) -> float:
        """计算推荐得分"""
        score = 0.0
        
        # 基础质量
        quality = (content.quality_score + content.engagement_score) / 2
        score += 0.2 * quality
        
        # 价值观势能（基于家长旋钮）
        value_score = 0.0
        for dim_name, weight in self.parent_knobs.value_focus.items():
            for dim, val in content.value_tags.items():
                if dim.value == dim_name:
                    value_score += val * weight
        if self.parent_knobs.value_focus:
            value_score /= len(self.parent_knobs.value_focus)
        score += 0.3 * value_score
        
        # 冒险系数调整
        complexity = int(content.complexity.name.replace('L', ''))
        if self.current_user and hasattr(self.current_user, 'current_zpd_high'):
            zpd_high = self.current_user.current_zpd_high
            if complexity > zpd_high:
                # 超出ZPD，根据冒险系数决定接受度
                if self.parent_knobs.risk_tolerance < 0.3:
                    score *= 0.5  # 保守策略惩罚
                elif self.parent_knobs.risk_tolerance > 0.7:
                    score *= 1.2  # 冒险策略奖励
        
        # 多样性倾向调整
        if strategy == 'diversity':
            if self.current_user and hasattr(self.current_user, 'topic_distribution'):
                if content.category in self.current_user.topic_distribution:
                    score *= 0.5  # 已看过的分类降权
        
        # ZPD 命中率奖励
        if self.current_user and hasattr(self.current_user, 'current_zpd_low'):
            if self.current_user.current_zpd_low <= complexity <= self.current_user.current_zpd_high:
                score += 0.15
                self.metrics.record_zpd_hit()
        
        # 茧房干预
        if self.current_user and hasattr(self.current_user, 'bubble_risk'):
            if self.current_user.bubble_risk > 0.3 and strategy == 'diversity':
                score += 0.2
                self.metrics.record_diversity_quota_hit()
        
        return min(1.0, max(0.0, score))
    
    def _generate_reason(self, content: EnhancedVideoContent, strategy: str) -> str:
        """生成推荐理由"""
        reasons = {
            'exploitation': f"因为你之前对「{content.category}」感兴趣",
            'diversity': f"发现新领域！你可能对「{content.category}」好奇",
            'scaffolding': f"这个挑战刚刚好，可以让你更进一步",
            'exploration': f"扶光觉得这个很有意思，试试看"
        }
        
        reason = reasons.get(strategy, reasons['exploitation'])
        
        # 添加情感基调
        if content.emotional_tone == EmotionalTone.CURIOSITY:
            reason += " 🔍"
        elif content.emotional_tone == EmotionalTone.COURAGE:
            reason += " 💪"
        elif content.emotional_tone == EmotionalTone.WARMTH:
            reason += " ❤️"
        
        return reason
    
    def update_profile(self, video_id: str, action: str, scaffolding_used: bool = False) -> Dict:
        """更新用户状态"""
        if self.current_user is None:
            raise ValueError("用户未设置")
        
        content = self.content_library.get(video_id)
        if not content:
            raise ValueError(f"视频 {video_id} 不存在")
        
        # 记录行为
        event = {
            'video_id': video_id,
            'action': action,
            'timestamp': datetime.now().isoformat(),
            'scaffolding_used': scaffolding_used
        }
        
        self.current_user.interaction_details.append(event)
        self.current_user.watch_history.append((video_id, WatchResult.USER_CLOSE if action == 'natural_end' else WatchResult.WATCH_FULLY))
        
        # 更新基础指标
        self.current_user.update_topic_distribution(content, 1.0)
        self._update_value_exposure(content)
        
        # 更新茧房风险
        self._update_bubble_risk()
        
        # 更新成长性指标
        self.current_user.update_growth_metrics(
            event, 
            list(self.content_library.values())
        )
        
        # Contextual Bandit 更新
        reward = 1.0 if action == 'natural_end' else 0.5
        # 找到上次选择的臂并更新
        self.bandit.update(0, reward)  # 简化：总是更新利用臂
        
        # 记录行为指标
        self.metrics.record_action(self.current_user.user_id, action)
        
        # 保存状态
        self.storage.save_learner_profile(self.current_user)
        
        return {
            'video_id': video_id,
            'action': action,
            'growth_metrics': {
                'zpd_velocity': self.current_user.zpd_velocity,
                'tool_appropriation': self.current_user.tool_appropriation,
                'curiosity_spark': self.current_user.curiosity_spark
            },
            'zpd_status': self.current_user.get_zpd_status() if hasattr(self.current_user, 'get_zpd_status') else {},
            'bandit_stats': self.bandit.get_stats()
        }
    
    def _update_value_exposure(self, content: EnhancedVideoContent):
        """更新价值观接触"""
        if self.current_user is None:
            return
        
        for dim, value in content.value_tags.items():
            prior = self.current_user.value_exposure.get(dim, 0.5)
            posterior = 0.7 * prior + 0.3 * value
            self.current_user.value_exposure[dim] = posterior
    
    def _update_bubble_risk(self):
        """更新茧房风险"""
        if self.current_user is None:
            return
        
        entropy = self.current_user.compute_diversity_entropy()
        if entropy < 1.5:
            self.current_user.bubble_risk = (1.5 - entropy) / 1.5
        else:
            self.current_user.bubble_risk = 0.0
    
    def get_parent_report(self) -> Dict:
        """获取家长报告（增强版）"""
        if self.current_user is None:
            raise ValueError("用户未设置")
        
        # 基础指标
        total = len(self.current_user.watch_history)
        natural_ends = sum(1 for _, r in self.current_user.watch_history if r == WatchResult.USER_CLOSE)
        
        # 成长性指标
        growth = {}
        if hasattr(self.current_user, 'zpd_velocity'):
            growth = {
                'zpd_velocity': self.current_user.zpd_velocity,
                'tool_appropriation': self.current_user.tool_appropriation,
                'curiosity_spark': self.current_user.curiosity_spark,
                'spontaneous_explorations': self.current_user.spontaneous_explorations
            }
        
        # ZPD 状态
        zpd_status = {}
        if hasattr(self.current_user, 'get_zpd_status'):
            zpd_status = self.current_user.get_zpd_status()
        
        # 价值观分布
        value_dist = {}
        for dim, val in self.current_user.value_exposure.items():
            value_dist[dim.value] = round(val * 100, 1)
        
        # 业务指标
        business_metrics = self.metrics.get_business_metrics()
        
        return {
            'user': self.current_user.name,
            'date': datetime.now().strftime('%Y年%m月%d日'),
            'watch_summary': {
                'total_watches': total,
                'natural_end_rate': round(natural_ends / max(1, total) * 100, 1),
                'total_time_minutes': self.current_user.total_watch_time
            },
            'growth_metrics': growth,
            'zpd_status': zpd_status,
            'value_distribution': value_dist,
            'parent_knobs': self.parent_knobs.to_strategy_params(),
            'business_metrics': business_metrics,
            'fuguang_comment': self._generate_report_comment()
        }
    
    def _generate_report_comment(self) -> str:
        """生成报告评语"""
        comments = []
        
        if self.current_user and hasattr(self.current_user, 'zpd_velocity'):
            if self.current_user.zpd_velocity > 0.6:
                comments.append("小明最近很勇于挑战更高难度！")
            elif self.current_user.curiosity_spark > 5:
                comments.append("小明自发探索了很多新领域！")
        
        if self.metrics.in_memory_metrics.get('natural_end_rate', 0) > 60:
            comments.append("越来越懂得控制观看节奏了")
        
        return " ".join(comments) if comments else "本周表现良好，继续保持！"
    
    def get_observability_dashboard(self) -> Dict:
        """获取可观测性仪表盘"""
        return {
            'business': self.metrics.get_business_metrics(),
            'model': self.metrics.get_model_metrics(),
            'system': self.metrics.get_system_metrics(),
            'bandit': self.bandit.get_stats()
        }


if __name__ == '__main__':
    # 测试增强推荐器
    recommender = EnhancedScaffoldingRecommender()
    recommender.set_user('test_child')
    
    # 测试家长旋钮
    result = recommender.set_parent_knobs({
        'risk_tolerance': 0.7,
        'diversity_preference': 0.8,
        'value_focus': {'好奇心': 1.5, '同理心': 1.0}
    })
    print("旋钮设置:", result)
    
    # 获取推荐
    recs = recommender.get_recommendation(5)
    print("\n推荐结果:")
    for r in recs:
        print(f"  - {r['title']} ({r['strategy_used']})")
        print(f"    理由: {r['reason']}")
        print(f"    认知挑战: {r['cognitive_challenges']}")
        print(f"    情感基调: {r['emotional_tone']}")
    
    # 更新状态
    if recs:
        recommender.update_profile(recs[0]['video_id'], 'natural_end')
    
    # 获取报告
    report = recommender.get_parent_report()
    print("\n家长报告:")
    print(f"  成长指标: {report['growth_metrics']}")
    print(f"  ZPD状态: {report['zpd_status']}")
    print(f"  扶光评语: {report['fuguang_comment']}")
    
    # 可观测性仪表盘
    dashboard = recommender.get_observability_dashboard()
    print("\n可观测性仪表盘:")
    print(f"  业务指标: {dashboard['business']}")
    print(f"  模型指标: {dashboard['model']}")
