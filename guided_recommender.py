"""
脚手架算法儿童短视频推荐系统 - 核心推荐器实现

核心哲学：不是递给孩子他最爱吃的糖果（这会导致蛀牙和偏食），
而是悄悄在他伸手可及的地方放上关于蚂蚁工坊、纸飞机折叠、非洲鼓点的书籍。
"""

import math
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum
from datetime import datetime, timedelta


class ComplexityLevel(Enum):
    """认知复杂度等级"""
    L1_INTUITIVE = 1   # 直观体验（6-9岁）
    L2_SIMPLE_CAUSE = 2  # 简单因果（6-9岁）
    L3_PRIMARY_REASONING = 3  # 初级推理（6-9岁）
    L4_COMPLEX_CAUSE = 4  # 复杂因果（10-12岁）
    L5_ABSTRACT_CONCEPT = 5  # 抽象概念（10-12岁）
    L6_CRITICAL_THINKING = 6  # 批判思维（10-12岁）


class AgeGroup(Enum):
    """年龄段"""
    AGE_6_9 = "6-9岁"
    AGE_10_12 = "10-12岁"


class WatchResult(Enum):
    """观看结果类型"""
    AUTO_NEXT = "auto_next"      # 被算法自动跳转
    USER_CLOSE = "user_close"    # 主动关闭/返回
    WATCH_FULLY = "watch_fully"  # 完整看完


class ValueDimension(Enum):
    """价值观维度"""
    CURIOSITY = "好奇心"
    EMPATHY = "同理心"
    RESPONSIBILITY = "责任感"
    DIVERSITY = "多元尊重"
    ENVIRONMENT = "环保意识"


@dataclass
class VideoContent:
    """视频内容数据结构"""
    video_id: str
    title: str
    description: str
    category: str
    sub_category: str
    complexity: ComplexityLevel
    age_group: AgeGroup
    
    # 价值观标签 (0-1 连续得分)
    value_tags: Dict[ValueDimension, float] = field(default_factory=dict)
    
    # 质量与互动分
    quality_score: float = 0.5
    engagement_score: float = 0.5
    
    # 引导链路关系
    scaffolding_next: List[str] = field(default_factory=list)  # 可引导至的视频ID
    scaffolding_prev: List[str] = field(default_factory=list)  # 从哪些内容引导而来
    
    # 元数据
    duration_seconds: int = 180
    risk_score: float = 0.0  # 0=安全, 1=高风险
    
    def __post_init__(self):
        """初始化默认值"""
        if not self.value_tags:
            # 默认价值观标签
            self.value_tags = {
                ValueDimension.CURIOSITY: 0.5,
                ValueDimension.EMPATHY: 0.5,
                ValueDimension.RESPONSIBILITY: 0.5,
                ValueDimension.DIVERSITY: 0.5,
                ValueDimension.ENVIRONMENT: 0.5,
            }
    
    def get_value_vector(self) -> List[float]:
        """获取价值观向量"""
        return [self.value_tags.get(dim, 0.5) for dim in ValueDimension]
    
    def compute_short_term_pleasure(self) -> float:
        """计算短期愉悦度 A"""
        return self.sigmoid((self.quality_score + self.engagement_score) / 2)
    
    @staticmethod
    def sigmoid(x: float) -> float:
        """Sigmoid函数"""
        return 1 / (1 + math.exp(-5 * (x - 0.5)))


@dataclass
class UserState:
    """用户状态数据结构"""
    user_id: str
    age_group: AgeGroup
    watch_history: List[Tuple[str, WatchResult]] = field(default_factory=list)
    # 各主题/类别的观看时间分布
    topic_distribution: Dict[str, float] = field(default_factory=dict)
    # 各价值观维度的接触概率 (贝叶斯估计)
    value_exposure: Dict[ValueDimension, float] = field(default_factory=dict)
    
    # 累积的自然结束奖励
    natural_end_bonus: float = 0.0
    pending_encouragement: Optional[str] = None
    
    # 茧房风险指标
    bubble_risk: float = 0.0
    value_deviation: float = 0.0
    
    # 家长培育意向权重
    parent_value_weights: Dict[ValueDimension, float] = field(default_factory=lambda: {
        dim: 1.0 for dim in ValueDimension
    })
    
    # 当前引导链路状态
    current_scaffolding_path: List[str] = field(default_factory=list)
    last_recommended_video_id: Optional[str] = None
    
    def __post_init__(self):
        """初始化默认值"""
        if not self.value_exposure:
            self.value_exposure = {dim: 0.5 for dim in ValueDimension}
    
    def compute_diversity_entropy(self) -> float:
        """计算认知多样性熵 H(p)"""
        if not self.topic_distribution:
            return 0.0
        
        total = sum(self.topic_distribution.values())
        if total == 0:
            return 0.0
        
        probabilities = [p / total for p in self.topic_distribution.values()]
        entropy = 0.0
        for p in probabilities:
            if p > 0:
                entropy -= p * math.log2(p)
        
        return entropy
    
    def compute_max_entropy(self) -> float:
        """计算最大可能熵"""
        n = len(self.topic_distribution) if self.topic_distribution else 1
        return math.log2(max(n, 1))
    
    def compute_bubble_penalty(self) -> float:
        """计算信息茧房惩罚项"""
        H_max = self.compute_max_entropy()
        H_current = self.compute_diversity_entropy()
        return max(0, H_max - H_current)
    
    def compute_natural_end_rate(self) -> float:
        """计算自然结束率"""
        if not self.watch_history:
            return 0.5
        
        natural_ends = sum(
            1 for _, result in self.watch_history 
            if result == WatchResult.USER_CLOSE
        )
        return natural_ends / len(self.watch_history)
    
    def update_topic_distribution(self, video: VideoContent, watch_time_ratio: float):
        """更新主题分布"""
        category = video.category
        current = self.topic_distribution.get(category, 0)
        self.topic_distribution[category] = current + watch_time_ratio


class ScaffoldingRecommender:
    """
    脚手架算法儿童短视频推荐系统 - 核心推荐器
    
    设计哲学：
    - 不优化点击率，不最大化时长，不迎合既有兴趣
    - 而是主动引导、拓展视野、传递价值观
    - 像一位住在屏幕里的、既博学又幽默的图书馆导师
    """
    
    # 熵阈值，低于此值触发强制多样性干预
    ENTROPY_MIN_THRESHOLD = 1.5
    
    # 探索奖励系数
    EXPLORATION_BONUS = 0.15
    
    # 默认权重配置（稳态）
    DEFAULT_WEIGHTS = {
        'w_A': 0.3,  # 短期愉悦度
        'w_B': 0.3,  # 信息茧房惩罚
        'w_C': 0.25,  # 价值观势能
        'w_D': 0.15,  # 自然结束奖励
    }
    
    def __init__(self, age_group: AgeGroup):
        """
        初始化推荐器
        
        Args:
            age_group: 用户年龄段
        """
        self.age_group = age_group
        self.content_library: Dict[str, VideoContent] = {}
        self.user_state: Optional[UserState] = None
        
        # 初始化内容库
        self._init_content_library()
    
    def _init_content_library(self):
        """初始化模拟内容库（至少20个视频）"""
        
        contents = [
            # ========== 玩具开箱类 (L1) ==========
            VideoContent(
                video_id="v001",
                title="超级飞侠乐迪豪华玩具拆箱",
                description="超级飞侠系列玩具开箱，展示各种飞机玩具",
                category="玩具开箱",
                sub_category="动画玩具",
                complexity=ComplexityLevel.L1_INTUITIVE,
                age_group=AgeGroup.AGE_6_9,
                quality_score=0.7,
                engagement_score=0.8,
                value_tags={
                    ValueDimension.CURIOSITY: 0.4,
                    ValueDimension.EMPATHY: 0.3,
                    ValueDimension.RESPONSIBILITY: 0.6,
                    ValueDimension.DIVERSITY: 0.2,
                    ValueDimension.ENVIRONMENT: 0.1,
                },
                scaffolding_next=["v002", "v003"],
            ),
            VideoContent(
                video_id="v002",
                title="汪汪队阿奇警车拆解",
                description="汪汪队立大功玩具警车拆解展示",
                category="玩具开箱",
                sub_category="动画玩具",
                complexity=ComplexityLevel.L1_INTUITIVE,
                age_group=AgeGroup.AGE_6_9,
                quality_score=0.7,
                engagement_score=0.75,
                scaffolding_next=["v003"],
            ),
            VideoContent(
                video_id="v003",
                title="乐迪玩具里面有什么？拆开看看！",
                description="深入拆解遥控玩具，看看内部构造",
                category="玩具拆解",
                sub_category="玩具探索",
                complexity=ComplexityLevel.L2_SIMPLE_CAUSE,
                age_group=AgeGroup.AGE_6_9,
                quality_score=0.75,
                engagement_score=0.7,
                value_tags={
                    ValueDimension.CURIOSITY: 0.7,
                    ValueDimension.EMPATHY: 0.3,
                    ValueDimension.RESPONSIBILITY: 0.3,
                    ValueDimension.DIVERSITY: 0.2,
                    ValueDimension.ENVIRONMENT: 0.1,
                },
                scaffolding_next=["v004", "v005"],
                scaffolding_prev=["v001", "v002"],
            ),
            
            # ========== 简单机械类 (L2-L3) ==========
            VideoContent(
                video_id="v004",
                title="玩具车是怎么跑起来的？轮子里的秘密",
                description="探索玩具车内部电机和轮子传动原理",
                category="简单机械",
                sub_category="动力机械",
                complexity=ComplexityLevel.L2_SIMPLE_CAUSE,
                age_group=AgeGroup.AGE_6_9,
                quality_score=0.8,
                engagement_score=0.7,
                value_tags={
                    ValueDimension.CURIOSITY: 0.8,
                    ValueDimension.EMPATHY: 0.3,
                    ValueDimension.RESPONSIBILITY: 0.3,
                    ValueDimension.DIVERSITY: 0.2,
                    ValueDimension.ENVIRONMENT: 0.1,
                },
                scaffolding_next=["v006", "v007"],
                scaffolding_prev=["v003"],
            ),
            VideoContent(
                video_id="v005",
                title="滑滑梯为什么这么快？认识滑动摩擦",
                description="通过滑滑梯和冰壶游戏认识摩擦力",
                category="简单机械",
                sub_category="物理原理",
                complexity=ComplexityLevel.L2_SIMPLE_CAUSE,
                age_group=AgeGroup.AGE_6_9,
                quality_score=0.75,
                engagement_score=0.7,
                value_tags={
                    ValueDimension.CURIOSITY: 0.75,
                    ValueDimension.EMPATHY: 0.4,
                    ValueDimension.RESPONSIBILITY: 0.2,
                    ValueDimension.DIVERSITY: 0.3,
                    ValueDimension.ENVIRONMENT: 0.2,
                },
                scaffolding_next=["v006"],
                scaffolding_prev=["v003"],
            ),
            VideoContent(
                video_id="v006",
                title="跷跷板为什么一边高一边低？认识杠杆原理",
                description="通过跷跷板理解杠杆原理和平衡",
                category="简单机械",
                sub_category="物理原理",
                complexity=ComplexityLevel.L3_PRIMARY_REASONING,
                age_group=AgeGroup.AGE_6_9,
                quality_score=0.8,
                engagement_score=0.7,
                value_tags={
                    ValueDimension.CURIOSITY: 0.8,
                    ValueDimension.EMPATHY: 0.5,
                    ValueDimension.RESPONSIBILITY: 0.3,
                    ValueDimension.DIVERSITY: 0.3,
                    ValueDimension.ENVIRONMENT: 0.2,
                },
                scaffolding_next=["v007", "v008"],
                scaffolding_prev=["v004", "v005"],
            ),
            
            # ========== 液压机械类 (L4) ==========
            VideoContent(
                video_id="v007",
                title="挖掘机的大铲子是怎么动的？液压力量",
                description="展示液压系统如何驱动挖掘机工作",
                category="液压机械",
                sub_category="工程原理",
                complexity=ComplexityLevel.L4_COMPLEX_CAUSE,
                age_group=AgeGroup.AGE_10_12,
                quality_score=0.85,
                engagement_score=0.75,
                value_tags={
                    ValueDimension.CURIOSITY: 0.9,
                    ValueDimension.EMPATHY: 0.3,
                    ValueDimension.RESPONSIBILITY: 0.4,
                    ValueDimension.DIVERSITY: 0.3,
                    ValueDimension.ENVIRONMENT: 0.3,
                },
                scaffolding_next=["v008"],
                scaffolding_prev=["v006"],
            ),
            VideoContent(
                video_id="v008",
                title="小哥白尼教你用纸杯和吸管做液压机械臂",
                description="用简单材料制作液压驱动的机械手臂",
                category="液压机械",
                sub_category="手工制作",
                complexity=ComplexityLevel.L4_COMPLEX_CAUSE,
                age_group=AgeGroup.AGE_6_9,
                quality_score=0.9,
                engagement_score=0.85,
                value_tags={
                    ValueDimension.CURIOSITY: 0.95,
                    ValueDimension.EMPATHY: 0.4,
                    ValueDimension.RESPONSIBILITY: 0.7,
                    ValueDimension.DIVERSITY: 0.3,
                    ValueDimension.ENVIRONMENT: 0.2,
                },
                scaffolding_next=["v009", "v010"],
                scaffolding_prev=["v007"],
            ),
            VideoContent(
                video_id="v009",
                title="液压机械臂还能做什么？真实世界应用",
                description="展示工业机械臂和液压设备的应用",
                category="液压机械",
                sub_category="科普拓展",
                complexity=ComplexityLevel.L4_COMPLEX_CAUSE,
                age_group=AgeGroup.AGE_10_12,
                quality_score=0.85,
                engagement_score=0.7,
                value_tags={
                    ValueDimension.CURIOSITY: 0.85,
                    ValueDimension.EMPATHY: 0.3,
                    ValueDimension.RESPONSIBILITY: 0.5,
                    ValueDimension.DIVERSITY: 0.4,
                    ValueDimension.ENVIRONMENT: 0.4,
                },
                scaffolding_next=["v010"],
                scaffolding_prev=["v008"],
            ),
            VideoContent(
                video_id="v010",
                title="仿生机器人：模仿自然的发明",
                description="介绍仿生机器人如何从自然界获取灵感",
                category="液压机械",
                sub_category="进阶科技",
                complexity=ComplexityLevel.L5_ABSTRACT_CONCEPT,
                age_group=AgeGroup.AGE_10_12,
                quality_score=0.9,
                engagement_score=0.8,
                value_tags={
                    ValueDimension.CURIOSITY: 0.95,
                    ValueDimension.EMPATHY: 0.4,
                    ValueDimension.RESPONSIBILITY: 0.5,
                    ValueDimension.DIVERSITY: 0.6,
                    ValueDimension.ENVIRONMENT: 0.6,
                },
                scaffolding_prev=["v008", "v009"],
            ),
            
            # ========== 搞笑宠物类 (L1) ==========
            VideoContent(
                video_id="v011",
                title="猫咪搞笑合集第45弹",
                description="可爱猫咪的搞笑瞬间集锦",
                category="搞笑宠物",
                sub_category="猫咪",
                complexity=ComplexityLevel.L1_INTUITIVE,
                age_group=AgeGroup.AGE_6_9,
                quality_score=0.6,
                engagement_score=0.9,
                value_tags={
                    ValueDimension.CURIOSITY: 0.3,
                    ValueDimension.EMPATHY: 0.5,
                    ValueDimension.RESPONSIBILITY: 0.1,
                    ValueDimension.DIVERSITY: 0.1,
                    ValueDimension.ENVIRONMENT: 0.1,
                },
            ),
            VideoContent(
                video_id="v012",
                title="狗狗趣事：二哈又拆家了",
                description="哈士奇的搞笑日常",
                category="搞笑宠物",
                sub_category="狗狗",
                complexity=ComplexityLevel.L1_INTUITIVE,
                age_group=AgeGroup.AGE_6_9,
                quality_score=0.6,
                engagement_score=0.85,
            ),
            
            # ========== 科学实验类 (L2-L3) ==========
            VideoContent(
                video_id="v013",
                title="彩虹牛奶：颜色是怎么跳舞的",
                description="用牛奶和色素展示表面张力的科学实验",
                category="科学实验",
                sub_category="化学启蒙",
                complexity=ComplexityLevel.L2_SIMPLE_CAUSE,
                age_group=AgeGroup.AGE_6_9,
                quality_score=0.85,
                engagement_score=0.85,
                value_tags={
                    ValueDimension.CURIOSITY: 0.95,
                    ValueDimension.EMPATHY: 0.3,
                    ValueDimension.RESPONSIBILITY: 0.3,
                    ValueDimension.DIVERSITY: 0.3,
                    ValueDimension.ENVIRONMENT: 0.2,
                },
                scaffolding_next=["v014"],
            ),
            VideoContent(
                video_id="v014",
                title="火山喷发大冒险：认识化学反应",
                description="模拟火山喷发的化学小实验",
                category="科学实验",
                sub_category="化学启蒙",
                complexity=ComplexityLevel.L3_PRIMARY_REASONING,
                age_group=AgeGroup.AGE_6_9,
                quality_score=0.9,
                engagement_score=0.9,
                value_tags={
                    ValueDimension.CURIOSITY: 0.95,
                    ValueDimension.EMPATHY: 0.3,
                    ValueDimension.RESPONSIBILITY: 0.3,
                    ValueDimension.DIVERSITY: 0.3,
                    ValueDimension.ENVIRONMENT: 0.3,
                },
            ),
            
            # ========== 自然动物类 (L2-L3) ==========
            VideoContent(
                video_id="v015",
                title="非洲草原的大象家族",
                description="跟随镜头认识非洲象群的生活",
                category="自然动物",
                sub_category="野生动物",
                complexity=ComplexityLevel.L2_SIMPLE_CAUSE,
                age_group=AgeGroup.AGE_6_9,
                quality_score=0.9,
                engagement_score=0.8,
                value_tags={
                    ValueDimension.CURIOSITY: 0.8,
                    ValueDimension.EMPATHY: 0.7,
                    ValueDimension.RESPONSIBILITY: 0.5,
                    ValueDimension.DIVERSITY: 0.7,
                    ValueDimension.ENVIRONMENT: 0.9,
                },
            ),
            VideoContent(
                video_id="v016",
                title="蚂蚁工坊：观察蚂蚁如何建造城堡",
                description="延时摄影展示蚂蚁的社会结构",
                category="自然动物",
                sub_category="昆虫世界",
                complexity=ComplexityLevel.L2_SIMPLE_CAUSE,
                age_group=AgeGroup.AGE_6_9,
                quality_score=0.85,
                engagement_score=0.75,
                value_tags={
                    ValueDimension.CURIOSITY: 0.9,
                    ValueDimension.EMPATHY: 0.5,
                    ValueDimension.RESPONSIBILITY: 0.4,
                    ValueDimension.DIVERSITY: 0.4,
                    ValueDimension.ENVIRONMENT: 0.8,
                },
            ),
            
            # ========== 手工艺术类 (L2-L3) ==========
            VideoContent(
                video_id="v017",
                title="超简单纸飞机折叠大全",
                description="多种纸飞机的折法及飞行原理",
                category="手工艺术",
                sub_category="折纸",
                complexity=ComplexityLevel.L2_SIMPLE_CAUSE,
                age_group=AgeGroup.AGE_6_9,
                quality_score=0.8,
                engagement_score=0.8,
                value_tags={
                    ValueDimension.CURIOSITY: 0.7,
                    ValueDimension.EMPATHY: 0.3,
                    ValueDimension.RESPONSIBILITY: 0.4,
                    ValueDimension.DIVERSITY: 0.3,
                    ValueDimension.ENVIRONMENT: 0.3,
                },
            ),
            VideoContent(
                video_id="v018",
                title="非洲鼓点节奏入门",
                description="简单易学的非洲鼓节奏教程",
                category="手工艺术",
                sub_category="音乐节奏",
                complexity=ComplexityLevel.L2_SIMPLE_CAUSE,
                age_group=AgeGroup.AGE_6_9,
                quality_score=0.8,
                engagement_score=0.8,
                value_tags={
                    ValueDimension.CURIOSITY: 0.6,
                    ValueDimension.EMPATHY: 0.7,
                    ValueDimension.RESPONSIBILITY: 0.3,
                    ValueDimension.DIVERSITY: 0.9,
                    ValueDimension.ENVIRONMENT: 0.2,
                },
            ),
            
            # ========== 友谊情感类 (L2-L3) ==========
            VideoContent(
                video_id="v019",
                title="小猪佩奇：友情大考验",
                description="佩奇和朋友们的友情故事",
                category="友谊情感",
                sub_category="动画故事",
                complexity=ComplexityLevel.L2_SIMPLE_CAUSE,
                age_group=AgeGroup.AGE_6_9,
                quality_score=0.75,
                engagement_score=0.75,
                value_tags={
                    ValueDimension.CURIOSITY: 0.4,
                    ValueDimension.EMPATHY: 0.9,
                    ValueDimension.RESPONSIBILITY: 0.6,
                    ValueDimension.DIVERSITY: 0.5,
                    ValueDimension.ENVIRONMENT: 0.2,
                },
            ),
            VideoContent(
                video_id="v020",
                title="如何成为更好的朋友？",
                description="关于友谊和社交的情感教育",
                category="友谊情感",
                sub_category="情感教育",
                complexity=ComplexityLevel.L3_PRIMARY_REASONING,
                age_group=AgeGroup.AGE_6_9,
                quality_score=0.8,
                engagement_score=0.7,
                value_tags={
                    ValueDimension.CURIOSITY: 0.4,
                    ValueDimension.EMPATHY: 0.95,
                    ValueDimension.RESPONSIBILITY: 0.7,
                    ValueDimension.DIVERSITY: 0.6,
                    ValueDimension.ENVIRONMENT: 0.2,
                },
            ),
            
            # ========== 环保意识类 (L3-L4) ==========
            VideoContent(
                video_id="v021",
                title="海洋塑料污染：我们可以做什么？",
                description="认识海洋污染并学习环保行动",
                category="环保意识",
                sub_category="环境保护",
                complexity=ComplexityLevel.L3_PRIMARY_REASONING,
                age_group=AgeGroup.AGE_10_12,
                quality_score=0.85,
                engagement_score=0.7,
                value_tags={
                    ValueDimension.CURIOSITY: 0.7,
                    ValueDimension.EMPATHY: 0.8,
                    ValueDimension.RESPONSIBILITY: 0.9,
                    ValueDimension.DIVERSITY: 0.5,
                    ValueDimension.ENVIRONMENT: 0.95,
                },
            ),
            VideoContent(
                video_id="v022",
                title="身边的可回收物：垃圾分类小知识",
                description="学习如何正确进行垃圾分类",
                category="环保意识",
                sub_category="环境保护",
                complexity=ComplexityLevel.L2_SIMPLE_CAUSE,
                age_group=AgeGroup.AGE_6_9,
                quality_score=0.8,
                engagement_score=0.7,
                value_tags={
                    ValueDimension.CURIOSITY: 0.6,
                    ValueDimension.EMPATHY: 0.5,
                    ValueDimension.RESPONSIBILITY: 0.9,
                    ValueDimension.DIVERSITY: 0.4,
                    ValueDimension.ENVIRONMENT: 0.9,
                },
            ),
            
            # ========== 品格教育类 (L3-L4) ==========
            VideoContent(
                video_id="v023",
                title="勇气魔法：克服恐惧的小技巧",
                description="用故事和动画帮助孩子理解勇气",
                category="品格教育",
                sub_category="勇气培养",
                complexity=ComplexityLevel.L3_PRIMARY_REASONING,
                age_group=AgeGroup.AGE_6_9,
                quality_score=0.85,
                engagement_score=0.75,
                value_tags={
                    ValueDimension.CURIOSITY: 0.5,
                    ValueDimension.EMPATHY: 0.6,
                    ValueDimension.RESPONSIBILITY: 0.8,
                    ValueDimension.DIVERSITY: 0.4,
                    ValueDimension.ENVIRONMENT: 0.2,
                },
            ),
            VideoContent(
                video_id="v024",
                title="责任感的魔法：承担是成长的开始",
                description="通过故事理解责任感和担当",
                category="品格教育",
                sub_category="责任感培养",
                complexity=ComplexityLevel.L3_PRIMARY_REASONING,
                age_group=AgeGroup.AGE_6_9,
                quality_score=0.85,
                engagement_score=0.75,
                value_tags={
                    ValueDimension.CURIOSITY: 0.4,
                    ValueDimension.EMPATHY: 0.6,
                    ValueDimension.RESPONSIBILITY: 0.95,
                    ValueDimension.DIVERSITY: 0.4,
                    ValueDimension.ENVIRONMENT: 0.2,
                },
            ),
        ]
        
        # 添加到内容库
        for content in contents:
            self.content_library[content.video_id] = content
        
        print(f"[脚手架系统] 内容库初始化完成，共 {len(self.content_library)} 个视频")
    
    def set_user(self, user_id: str):
        """设置当前用户"""
        self.user_state = UserState(
            user_id=user_id,
            age_group=self.age_group
        )
        print(f"[脚手架系统] 用户 {user_id} 已初始化")
    
    def update_profile(self, video_id: str, action: str) -> Dict[str, Any]:
        """
        更新用户状态
        
        Args:
            video_id: 视频ID
            action: 用户行为
                - "watch": 观看（配合 watch_result 区分具体行为）
                - "skip": 跳过
                - "like": 点赞
                - "favorite": 收藏
                - "click_why": 点击"为什么推荐这个"
                - "natural_end": 主动结束观看
                - "auto_next": 被算法自动跳转
        
        Returns:
            更新后的状态摘要
        """
        if self.user_state is None:
            raise ValueError("用户未设置，请先调用 set_user()")
        
        if video_id not in self.content_library:
            raise ValueError(f"视频 {video_id} 不存在于内容库")
        
        video = self.content_library[video_id]
        
        # 解析行为
        watch_result = None
        if action == "natural_end":
            watch_result = WatchResult.USER_CLOSE
        elif action == "auto_next":
            watch_result = WatchResult.AUTO_NEXT
        elif action == "watch":
            watch_result = WatchResult.WATCH_FULLY
        
        # 更新历史记录
        if watch_result:
            self.user_state.watch_history.append((video_id, watch_result))
        
        # 更新自然结束奖励
        if action == "natural_end":
            self.user_state.natural_end_bonus += 0.1
            self.user_state.pending_encouragement = "看完了就去做点别的吧！"
        elif action == "auto_next":
            self.user_state.natural_end_bonus = max(0, self.user_state.natural_end_bonus - 0.05)
        
        # 更新主题分布
        self.user_state.update_topic_distribution(video, watch_time_ratio=1.0)
        
        # 更新价值观接触（贝叶斯更新）
        self._update_value_exposure(video)
        
        # 更新茧房风险
        self._update_bubble_risk()
        
        # 更新引导链路
        if video_id in self.user_state.current_scaffolding_path:
            # 已在引导路径上，继续下一步
            pass
        else:
            # 开始新的引导路径
            self.user_state.current_scaffolding_path = [video_id]
        
        self.user_state.last_recommended_video_id = video_id
        
        return {
            "video_id": video_id,
            "action": action,
            "natural_end_bonus": self.user_state.natural_end_bonus,
            "encouragement": self.user_state.pending_encouragement,
            "bubble_risk": self.user_state.bubble_risk,
            "diversity_entropy": self.user_state.compute_diversity_entropy(),
        }
    
    def _update_value_exposure(self, video: VideoContent):
        """更新价值观接触概率（贝叶斯更新）"""
        for dim in ValueDimension:
            content_value = video.value_tags.get(dim, 0.5)
            prior = self.user_state.value_exposure.get(dim, 0.5)
            # 简化的贝叶斯更新
            posterior = 0.7 * prior + 0.3 * content_value
            self.user_state.value_exposure[dim] = posterior
    
    def _update_bubble_risk(self):
        """更新茧房风险指标"""
        entropy = self.user_state.compute_diversity_entropy()
        if entropy < self.ENTROPY_MIN_THRESHOLD:
            self.user_state.bubble_risk = (self.ENTROPY_MIN_THRESHOLD - entropy) / self.ENTROPY_MIN_THRESHOLD
        else:
            self.user_state.bubble_risk = 0.0
    
    def _compute_dynamic_weights(self) -> Dict[str, float]:
        """计算动态权重"""
        if self.user_state is None:
            return self.DEFAULT_WEIGHTS.copy()
        
        # 检查各维度风险
        entropy = self.user_state.compute_diversity_entropy()
        bubble_risk = self.user_state.bubble_risk
        natural_end_rate = self.user_state.compute_natural_end_rate()
        
        # 新用户冷启动
        if len(self.user_state.watch_history) < 3:
            return {'w_A': 0.7, 'w_B': 0.1, 'w_C': 0.1, 'w_D': 0.1}
        
        # 重度茧房
        if bubble_risk > 0.5:
            return {'w_A': 0.2, 'w_B': 0.5, 'w_C': 0.2, 'w_D': 0.1}
        
        # 无限刷屏检测（自然结束率过低）
        if natural_end_rate < 0.3:
            return {'w_A': 0.2, 'w_B': 0.2, 'w_C': 0.2, 'w_D': 0.4}
        
        # 轻度茧房
        if bubble_risk > 0.2:
            return {'w_A': 0.4, 'w_B': 0.3, 'w_C': 0.2, 'w_D': 0.1}
        
        # 均衡发展
        return self.DEFAULT_WEIGHTS.copy()
    
    def _compute_value_potential(self, video: VideoContent) -> float:
        """
        计算价值观势能 ΔV
        
        衡量推荐对价值观培育的贡献
        """
        if self.user_state is None:
            return 0.0
        
        delta_v = 0.0
        for dim in ValueDimension:
            prior = self.user_state.value_exposure.get(dim, 0.5)
            content_value = video.value_tags.get(dim, 0.5)
            weight = self.user_state.parent_value_weights.get(dim, 1.0)
            
            # 预测观看后价值观接受概率的提升
            # 价值观越低的内容，提升空间越大
            potential = (content_value - prior) * weight * 0.2
            delta_v += max(0, potential)
        
        return delta_v
    
    def _compute_education_relevance(self, video: VideoContent) -> float:
        """
        计算教育相关性 EduRel
        
        与主流算法的"相关性"不同，这是专为本系统设计的指标
        """
        if self.user_state is None:
            return 0.5
        
        # 认知复杂度匹配度
        if video.age_group == self.age_group or video.age_group == AgeGroup.AGE_6_9:
            cog_fit = 0.8
        else:
            cog_fit = 0.4
        
        # 价值观匹配度（基于家长权重）
        value_align = 0.0
        for dim in ValueDimension:
            content_value = video.value_tags.get(dim, 0.5)
            weight = self.user_state.parent_value_weights.get(dim, 1.0)
            value_align += content_value * weight
        value_align = value_align / sum(self.user_state.parent_value_weights.values())
        
        # 引导链路 proximity
        scaffolding_proximity = 0.0
        if self.user_state.last_recommended_video_id:
            last_video = self.content_library.get(self.user_state.last_recommended_video_id)
            if last_video and video.video_id in last_video.scaffolding_next:
                scaffolding_proximity = 0.9
            elif video.video_id in last_video.scaffolding_prev:
                scaffolding_proximity = 0.5
        
        # 综合得分
        edu_rel = 0.4 * cog_fit + 0.35 * value_align + 0.25 * scaffolding_proximity
        return edu_rel
    
    def _check_exploration_bonus(self, video: VideoContent) -> float:
        """检查是否应该给予探索奖励"""
        if self.user_state is None:
            return 0.0
        
        is_cross_domain = True
        for category in self.user_state.topic_distribution.keys():
            if video.category == category or video.sub_category == category:
                is_cross_domain = False
                break
        
        if is_cross_domain and self.user_state.bubble_risk > 0.1:
            return self.EXPLORATION_BONUS
        
        return 0.0
    
    def _check_ai_garbage_content(self, video: VideoContent) -> bool:
        """检测AI泔水内容（简化版）"""
        # 实际应有多模态检测，此处为简化演示
        # 高风险分（>0.7）的内容视为可疑
        return video.risk_score > 0.7
    
    def get_recommendation(self, count: int = 10) -> List[Dict[str, Any]]:
        """
        获取推荐列表
        
        Args:
            count: 推荐数量
        
        Returns:
            推荐列表，每项包含视频信息和决策日志
        """
        if self.user_state is None:
            raise ValueError("用户未设置，请先调用 set_user()")
        
        weights = self._compute_dynamic_weights()
        recommendations = []
        
        # 分类获取候选
        education_candidates = []  # 教育相关性候选
        cross_domain_candidates = []  # 跨域候选
        scaffolding_candidates = []  # 引导链路候选
        exploration_candidates = []  # 探索候选
        
        entropy = self.user_state.compute_diversity_entropy()
        bubble_risk = self.user_state.bubble_risk
        
        for video_id, video in self.content_library.items():
            # 跳过已观看的
            watched = any(vid == video_id for vid, _ in self.user_state.watch_history)
            if watched:
                continue
            
            # 跳过AI泔水内容
            if self._check_ai_garbage_content(video):
                continue
            
            # 计算各项得分
            A = video.compute_short_term_pleasure()
            bubble_penalty = self.user_state.compute_bubble_penalty()
            C = self._compute_value_potential(video)
            D = self.user_state.compute_natural_end_rate()
            
            # 计算探索奖励
            exploration_bonus = self._check_exploration_bonus(video)
            
            # 计算教育相关性
            edu_rel = self._compute_education_relevance(video)
            
            # 综合得分
            J = (
                weights['w_A'] * A +
                weights['w_B'] * bubble_penalty +
                weights['w_C'] * C +
                weights['w_D'] * D +
                exploration_bonus +
                0.2 * edu_rel  # 教育相关性加成
            )
            
            candidate_info = {
                'video': video,
                'score': J,
                'A': A,
                'bubble_penalty': bubble_penalty,
                'C': C,
                'D': D,
                'exploration_bonus': exploration_bonus,
                'edu_rel': edu_rel,
            }
            
            # 分类
            if video.category in self.user_state.topic_distribution:
                education_candidates.append(candidate_info)
            else:
                cross_domain_candidates.append(candidate_info)
            
            # 检查是否在引导链路上
            if self.user_state.last_recommended_video_id:
                last_video = self.content_library.get(self.user_state.last_recommended_video_id)
                if last_video and video.video_id in last_video.scaffolding_next:
                    scaffolding_candidates.append(candidate_info)
            
            exploration_candidates.append(candidate_info)
        
        # 按比例组成推荐列表
        # 60% 教育相关性排序, 20% 跨域, 10% 引导链路, 10% 随机探索
        education_count = int(count * 0.6)
        cross_domain_count = int(count * 0.2)
        scaffolding_count = int(count * 0.1)
        exploration_count = count - education_count - cross_domain_count - scaffolding_count
        
        # 排序并选取
        education_candidates.sort(key=lambda x: x['score'], reverse=True)
        cross_domain_candidates.sort(key=lambda x: x['score'], reverse=True)
        scaffolding_candidates.sort(key=lambda x: x['score'], reverse=True)
        exploration_candidates.sort(key=lambda x: x['score'], reverse=True)
        
        selected = []
        selected_ids = set()
        
        # 按顺序选取
        for c in scaffolding_candidates[:scaffolding_count]:
            if c['video'].video_id not in selected_ids:
                selected.append(c)
                selected_ids.add(c['video'].video_id)
        
        for c in cross_domain_candidates[:cross_domain_count]:
            if c['video'].video_id not in selected_ids:
                selected.append(c)
                selected_ids.add(c['video'].video_id)
        
        for c in education_candidates[:education_count]:
            if c['video'].video_id not in selected_ids:
                selected.append(c)
                selected_ids.add(c['video'].video_id)
        
        for c in exploration_candidates[:exploration_count]:
            if c['video'].video_id not in selected_ids:
                selected.append(c)
                selected_ids.add(c['video'].video_id)
        
        # 构建返回结果
        for c in selected:
            video = c['video']
            
            # 生成推荐理由
            reason = self._generate_recommendation_reason(video)
            
            recommendations.append({
                'video_id': video.video_id,
                'title': video.title,
                'description': video.description,
                'category': video.category,
                'sub_category': video.sub_category,
                'complexity': video.complexity.name,
                'score': round(c['score'], 3),
                'decision_log': {
                    'A (愉悦度)': round(c['A'], 3),
                    'B (茧房惩罚)': round(c['bubble_penalty'], 3),
                    'C (价值观势能)': round(c['C'], 3),
                    'D (自然结束)': round(c['D'], 3),
                    '探索奖励': round(c['exploration_bonus'], 3),
                    '教育相关性': round(c['edu_rel'], 3),
                },
                'reason': reason,
                'weights_used': weights,
            })
        
        return recommendations
    
    def _generate_recommendation_reason(self, video: VideoContent) -> str:
        """生成推荐理由"""
        if self.user_state is None:
            return "发现有趣的内容！"
        
        last_video = None
        if self.user_state.last_recommended_video_id:
            last_video = self.content_library.get(self.user_state.last_recommended_video_id)
        
        if last_video and video.video_id in last_video.scaffolding_next:
            # 引导链路关系
            return f"你之前看了「{last_video.title}」→ 这个可以让你更深入了解「{video.sub_category}」！"
        elif self.user_state.bubble_risk > 0.2:
            # 茧房干预
            return f"发现新领域！你可能对「{video.category}」感兴趣～"
        elif video.value_tags.get(ValueDimension.CURIOSITY, 0) > 0.8:
            # 好奇心导向
            return f"好奇心警报！这个视频会回答「为什么会这样」的问题🔍"
        else:
            return f"脚手架系统觉得这个视频很有意思，推荐给你！"
    
    def get_parent_report(self) -> Dict[str, Any]:
        """
        获取家长透明度报告
        
        Returns:
            周报数据
        """
        if self.user_state is None:
            raise ValueError("用户未设置，请先调用 set_user()")
        
        # 计算各项统计
        total_watches = len(self.user_state.watch_history)
        natural_ends = sum(1 for _, r in self.user_state.watch_history if r == WatchResult.USER_CLOSE)
        natural_end_rate = natural_ends / total_watches if total_watches > 0 else 0
        
        entropy = self.user_state.compute_diversity_entropy()
        H_max = self.user_state.compute_max_entropy()
        
        # 价值观分布
        value_distribution = {}
        for dim in ValueDimension:
            exposure = self.user_state.value_exposure.get(dim, 0.5)
            value_distribution[dim.value] = round(exposure * 100, 1)
        
        # 兴趣拓展
        historical_categories = set()
        for video_id, _ in self.user_state.watch_history:
            if video_id in self.content_library:
                historical_categories.add(self.content_library[video_id].category)
        
        all_categories = set(v.category for v in self.content_library.values())
        new_categories = all_categories - historical_categories
        
        # 计算系统评语
        comments = []
        if natural_end_rate > 0.5:
            comments.append("小明越来越懂得控制观看节奏了！")
        if entropy > 2.0:
            comments.append("兴趣越来越多元化了！")
        if ValueDimension.CURIOSITY in self.user_state.value_exposure:
            if self.user_state.value_exposure[ValueDimension.CURIOSITY] > 0.7:
                comments.append("小明开始对「东西是怎么工作的」感兴趣了！")
        
        return {
            'report_date': datetime.now().strftime('%Y年%m月%d日'),
            'user_id': self.user_state.user_id,
            'watch_summary': {
                'total_watches': total_watches,
                'natural_end_rate': round(natural_end_rate * 100, 1),
                'comment': comments[0] if comments else "观看习惯良好",
            },
            'value_distribution': value_distribution,
            'interest_expansion': {
                'historical_count': len(historical_categories),
                'new_areas': [cat for cat in new_categories][:3],
            },
            'diversity_entropy': {
                'current': round(entropy, 2),
                'max': round(H_max, 2),
                'status': '健康' if entropy > 2.0 else '需关注',
            },
            'safety': {
                'ai_garbage_blocked': 0,  # 本周期无检测到
                'value_drift_flagged': 0,
            },
            'fuguang_comment': " ".join(comments) if comments else "本周小明表现不错！"
        }
    
    def set_parent_intent(self, semantic_input: str) -> Dict[str, Any]:
        """
        接收家长语义输入并调整权重
        
        Args:
            semantic_input: 家长的自然语言描述
                例如："孩子最近有点霸道，想让他看看关于分享和友谊的内容"
        
        Returns:
            调整结果确认
        """
        if self.user_state is None:
            raise ValueError("用户未设置，请先调用 set_user()")
        
        # 简化的语义解析（实际应使用LLM）
        semantic_lower = semantic_input.lower()
        
        adjustments = {}
        
        # 意图关键词映射
        intent_keywords = {
            ValueDimension.CURIOSITY: ['好奇心', '好奇', '探索', '想知道', '为什么'],
            ValueDimension.EMPATHY: ['同理心', '分享', '友谊', '朋友', '关爱', '体贴', '霸道'],
            ValueDimension.RESPONSIBILITY: ['责任感', '责任', '承担', '担当', '义务'],
            ValueDimension.DIVERSITY: ['多元', '不同', '包容', '尊重', '各种'],
            ValueDimension.ENVIRONMENT: ['环保', '自然', '环境', '地球', '动物'],
        }
        
        for dim, keywords in intent_keywords.items():
            for keyword in keywords:
                if keyword in semantic_lower:
                    adjustments[dim.value] = 1.5  # 增强该维度权重
                    break
        
        # 如果没有匹配到任何意图，给予默认提升好奇心
        if not adjustments:
            adjustments[ValueDimension.CURIOSITY.value] = 1.3
        
        # 应用权重调整
        for dim_name, weight in adjustments.items():
            for dim in ValueDimension:
                if dim.value == dim_name:
                    self.user_state.parent_value_weights[dim] = weight
        
        return {
            'semantic_input': semantic_input,
            'adjustments_applied': adjustments,
            'current_weights': {dim.value: w for dim, w in self.user_state.parent_value_weights.items()},
            'confirmation': f"已收到您的培育意向，系统权重已调整。脚手架系统会重点关注：{', '.join(adjustments.keys())}"
        }
    
    def get_scaffolding_path(self) -> List[str]:
        """获取当前引导链路"""
        if self.user_state is None:
            return []
        return self.user_state.current_scaffolding_path.copy()
    
    def explain_recommendation(self, video_id: str) -> str:
        """
        解释为什么推荐这个视频
        
        Args:
            video_id: 视频ID
        
        Returns:
            知识图谱路径说明
        """
        if self.user_state is None or video_id not in self.content_library:
            return ""
        
        video = self.content_library[video_id]
        last_video = None
        if self.user_state.last_recommended_video_id:
            last_video = self.content_library.get(self.user_state.last_recommended_video_id)
        
        path_parts = []
        
        # 最近观看
        if last_video:
            path_parts.append(f"你最近看了：「{last_video.title}」")
        
        # 发现的好奇点
        curiosity = video.value_tags.get(ValueDimension.CURIOSITY, 0.5)
        if curiosity > 0.7:
            path_parts.append(f"脚手架发现你可能对「{video.sub_category}」很好奇？")
        
        # 推荐内容
        path_parts.append(f"推荐：「{video.title}」")
        
        # 连接逻辑
        if last_video and video.video_id in last_video.scaffolding_next:
            path_parts.append(f"连接逻辑：{last_video.sub_category} → 好奇{video.sub_category}的更多知识")
        
        return "\n".join(path_parts)


# ============================================================================
# 辅助函数
# ============================================================================

def create_recommender(age_group: str = "6-9岁") -> ScaffoldingRecommender:
    """创建推荐器的工厂函数"""
    if age_group == "6-9岁":
        return ScaffoldingRecommender(AgeGroup.AGE_6_9)
    else:
        return ScaffoldingRecommender(AgeGroup.AGE_10_12)


if __name__ == "__main__":
    # 简单测试
    recommender = create_recommender("6-9岁")
    recommender.set_user("test_user")
    
    print("\n=== 初始推荐 ===")
    recs = recommender.get_recommendation(5)
    for rec in recs:
        print(f"- {rec['title']} (分数: {rec['score']})")
    
    print("\n=== 更新用户状态 ===")
    result = recommender.update_profile("v001", "natural_end")
    print(f"更新结果: {result}")
    
    print("\n=== 再次推荐 ===")
    recs = recommender.get_recommendation(5)
    for rec in recs:
        print(f"- {rec['title']} (分数: {rec['score']})")
