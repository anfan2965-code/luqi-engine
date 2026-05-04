"""
引擎核心接口协议 - 定义五大模块的标准接口
所有模块实现必须遵循这些协议，确保可替换性和可测试性
"""

from __future__ import annotations

_MEMORY_RETRIEVAL_DEFAULT_LIMIT: int = 10
_DIALOGUE_MAX_ROUNDS_DEFAULT: int = 20

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any, Dict, List, Optional, Tuple

from luqi_engine.core.types import (
    ActionResult,
    BoundingBox,
    ConflictReport,
    DesireVector,
    EntityId,
    LLMRequest,
    LLMResponse,
    LLMStreamChunk,
    LocalModelOutput,
    SDKType,
    Vector3,
    WorldState,
)


class IWorldViewRenderer(ABC):
    """
    世界观渲染引导接口
    职责：为LLM提供结构化引导，解析用户自定义世界观
    """

    @abstractmethod
    async def extract_elements(self, raw_content: str, content_type: str) -> Dict[str, Any]:
        """
        从原始内容中提取世界观要素
        content_type: "text", "markdown", "json", "image_desc"
        返回分类后的要素字典
        """

    @abstractmethod
    async def classify_elements(self, elements: Dict[str, Any]) -> Dict[str, List[Dict]]:
        """
        将提取的要素分类到标准维度
        维度：geography, society, culture, history, magic_system, technology, etc.
        """

    @abstractmethod
    async def build_relations(self, classified: Dict[str, List[Dict]]) -> Dict[str, Any]:
        """
        建立要素间的关联关系图
        返回邻接表形式的关联图
        """

    @abstractmethod
    async def render_guidance(self, world_model: Dict[str, Any]) -> str:
        """
        生成给LLM的结构化渲染引导文本
        """

    @abstractmethod
    async def detect_conflicts(self, world_model: Dict[str, Any]) -> List[ConflictReport]:
        """
        检测世界观内部的逻辑矛盾
        准确率目标: >=95%
        """


class ISceneBuilder(ABC):
    """
    场景构建支持接口
    职责：场景描述框架、空间关系、动态更新
    """

    @abstractmethod
    async def create_scene(self, scene_config: Dict[str, Any]) -> EntityId:
        """创建新场景并返回场景ID"""

    @abstractmethod
    async def add_element(self, scene_id: EntityId, element: Dict[str, Any]) -> EntityId:
        """向场景添加元素"""

    @abstractmethod
    async def query_elements(
        self,
        scene_id: EntityId,
        element_type: Optional[str] = None,
        bounds: Optional[BoundingBox] = None,
    ) -> List[Dict[str, Any]]:
        """查询场景中的元素"""

    @abstractmethod
    async def update_environment(self, scene_id: EntityId, delta_time: float) -> None:
        """更新场景环境状态（时间、天气等）"""

    @abstractmethod
    async def check_spatial_conflicts(self, scene_id: EntityId) -> List[ConflictReport]:
        """检测场景元素的空间冲突，准确率>=95%"""


class ICharacterManager(ABC):
    """
    角色系统管理接口
    职责：角色创建、性格量化、记忆系统
    """

    @abstractmethod
    async def create_character(self, character_config: Dict[str, Any]) -> EntityId:
        """创建角色并返回角色ID"""

    @abstractmethod
    async def get_personality(self, character_id: EntityId) -> Dict[str, float]:
        """获取角色性格量化值（OCEAN模型，0-100分）"""

    @abstractmethod
    async def update_personality(self, character_id: EntityId, deltas: Dict[str, float]) -> None:
        """根据经历微调角色性格"""

    @abstractmethod
    async def store_memory(
        self,
        character_id: EntityId,
        memory_type: str,
        content: Dict[str, Any],
    ) -> None:
        """
        存储记忆
        memory_type: "short_term", "long_term", "emotional"
        """

    @abstractmethod
    async def retrieve_memories(
        self,
        character_id: EntityId,
        query: str,
        memory_type: Optional[str] = None,
        limit: int = _MEMORY_RETRIEVAL_DEFAULT_LIMIT,
    ) -> List[Dict[str, Any]]:
        """检索相关记忆"""

    @abstractmethod
    async def validate_behavior_consistency(
        self,
        character_id: EntityId,
        proposed_action: Dict[str, Any],
    ) -> Tuple[bool, float]:
        """
        验证行为是否符合性格设定
        返回: (是否一致, 一致性分数0-1)
        目标: 一致性概率>=95%
        """

    @abstractmethod
    async def store_shared_memory(
        self,
        event_id: str,
        content: Dict[str, Any],
        participant_ids: List[str],
        emotional_valence: float = 0.0,
    ) -> None:
        """存储跨角色共享记忆"""

    @abstractmethod
    async def retrieve_temporal(
        self,
        character_id: EntityId,
        time_start: float,
        time_end: float,
        query: str = "",
        limit: int = _MEMORY_RETRIEVAL_DEFAULT_LIMIT,
    ) -> List[Dict[str, Any]]:
        """时序范围查询记忆"""

    @abstractmethod
    async def memory_tool_call(
        self,
        character_id: EntityId,
        tool_name: str,
        params: Dict[str, Any],
    ) -> Any:
        """LLM自主记忆管理工具调用"""

    @abstractmethod
    async def load_memory_module(self, character_id: EntityId) -> None:
        """加载角色记忆模块到内存"""

    @abstractmethod
    async def unload_memory_module(self, character_id: EntityId) -> None:
        """卸载角色记忆模块，序列化到磁盘"""


class INarrativeController(ABC):
    """
    剧情走向控制接口
    职责：节点识别、分支管理、回归引导
    """

    @abstractmethod
    async def identify_nodes(self, story_state: Dict[str, Any]) -> List[Dict[str, Any]]:
        """识别当前剧情节点（关键事件、转折点、结局条件）"""

    @abstractmethod
    async def compute_branch_weights(
        self,
        current_node: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Dict[str, float]:
        """计算各分支的权重"""

    @abstractmethod
    async def take_branch(self, branch_id: str) -> ActionResult:
        """执行分支选择"""

    @abstractmethod
    async def detect_dead_ends(self, story_graph: Dict[str, Any]) -> List[str]:
        """检测死胡同分支"""

    @abstractmethod
    async def guide_back(
        self,
        current_state: Dict[str, Any],
        method: str = "natural",
    ) -> ActionResult:
        """
        剧情回归引导
        method: "natural"(自然回归), "event_triggered"(事件触发), "forced"(强制回归)
        """

    @abstractmethod
    async def get_elasticity_coefficient(self) -> float:
        """获取当前剧情弹性系数(0-100)"""

    @abstractmethod
    async def set_elasticity_coefficient(self, value: float) -> None:
        """设置剧情弹性系数(0-100)"""


class IInteractionCoordinator(ABC):
    """
    多角色互动协调接口
    职责：关系管理、对话分配、社交规则
    """

    @abstractmethod
    async def get_relationship(
        self,
        char_a: EntityId,
        char_b: EntityId,
    ) -> Dict[str, float]:
        """获取两个角色间的关系指标"""

    @abstractmethod
    async def update_relationship(
        self,
        char_a: EntityId,
        char_b: EntityId,
        deltas: Dict[str, float],
    ) -> None:
        """更新角色间关系"""

    @abstractmethod
    async def compute_speaking_priority(
        self,
        participants: List[EntityId],
        context: Dict[str, Any],
    ) -> List[Tuple[EntityId, float]]:
        """计算对话轮次分配优先级"""

    @abstractmethod
    async def apply_social_rules(
        self,
        character_id: EntityId,
        action: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """应用社交规则引擎，返回修正后的动作"""

    @abstractmethod
    async def coordinate_dialogue(
        self,
        participants: List[EntityId],
        topic: str,
        max_rounds: int = _DIALOGUE_MAX_ROUNDS_DEFAULT,
    ) -> List[Dict[str, Any]]:
        """协调多角色对话流程"""


class ILLMBridge(ABC):
    """
    LLM桥接接口
    职责：统一对接不同LLM SDK，提供同步/流式对话、向量化与连接验证
    """

    @abstractmethod
    async def chat(self, request: LLMRequest) -> LLMResponse:
        """同步对话"""

    @abstractmethod
    async def chat_stream(self, request: LLMRequest) -> AsyncIterator[LLMStreamChunk]:
        """流式对话"""

    @abstractmethod
    async def embed(self, text: str) -> List[float]:
        """文本向量化"""

    @abstractmethod
    async def validate(self) -> bool:
        """验证连接有效性"""

    @abstractmethod
    def get_sdk_type(self) -> SDKType:
        """获取当前SDK类型"""


class ILocalModel(ABC):
    """
    本地模型接口
    职责：预处理、分词、向量化、分类、纠正与训练数据导出
    """

    @abstractmethod
    async def preprocess(self, text: str) -> str:
        """预处理"""

    @abstractmethod
    async def tokenize(self, text: str) -> List[str]:
        """分词"""

    @abstractmethod
    async def vectorize(self, tokens: List[str]) -> Any:
        """TF-IDF向量化"""

    @abstractmethod
    async def classify(self, vector: Any) -> LocalModelOutput:
        """分类"""

    @abstractmethod
    async def correct(self, content: Dict[str, Any]) -> Dict[str, Any]:
        """内容纠正"""

    @abstractmethod
    async def export_training_data(self, since: float) -> List[Dict[str, Any]]:
        """导出训练数据"""


class IDesireEngine(ABC):
    """
    欲望引擎接口
    职责：欲望向量管理、情感驱动更新、驱动链计算
    """

    @abstractmethod
    async def get_desires(self, character_id: EntityId) -> DesireVector:
        """获取欲望向量"""

    @abstractmethod
    async def update_desires(
        self,
        character_id: EntityId,
        emotion_delta: Dict[str, float],
    ) -> DesireVector:
        """根据情感变化更新欲望"""

    @abstractmethod
    async def compute_drive_chain(
        self,
        character_id: EntityId,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """计算驱动链"""


class INarrativeDocument(ABC):
    """
    叙事文档接口
    职责：所有智能体共享的唯一真相源
    """

    @abstractmethod
    def apply_delta(self, delta: Any) -> None:
        """应用差量更新，版本号递增"""

    @abstractmethod
    def to_prompt_context(self, mode: str = "standard") -> str:
        """渲染为可注入 prompt 的文本"""

    @abstractmethod
    def find_conflicting_fact(self, new_fact: Any) -> Optional[Any]:
        """查找与新事实矛盾的已有事实"""


class IAgentRunner(ABC):
    """
    智能体运行器接口
    职责：四智能体的统一抽象
    """

    @abstractmethod
    async def run(self, context: Dict[str, Any], llm_bridge: Any, **kwargs: Any) -> Any:
        """运行智能体，返回结构化输出"""

    @abstractmethod
    def get_name(self) -> str:
        """获取智能体名称"""

    @abstractmethod
    def get_output_type(self) -> str:
        """获取输出类型名称"""


class IAlgorithmSupremeCourt(ABC):
    """
    算法最高法院接口
    职责：所有LLM输出必须经过此门
    """

    @abstractmethod
    def validate_dialogue_ir(self, ir: Any, character: Any, narrative: Any) -> Any:
        """校验 Dialogue Agent 的 CanonicalIR"""

    @abstractmethod
    def validate_novel_delta(self, delta: Any, narrative: Any) -> Any:
        """校验 Novel Agent 的 NarrativeDelta"""


class IVoiceRenderer(ABC):
    """
    确定性语音渲染器接口
    职责：IR→自然语言
    """

    @abstractmethod
    def render(self, ir: Any, voice_profile: Any, seed: int) -> str:
        """基于 seed 确定性生成角色台词文本"""


class IOutputAssembler(ABC):
    """
    输出组装器接口
    职责：将 Atmosphere + Dialogue 合并为沉浸式回复
    """

    @abstractmethod
    def assemble_output(
        self,
        dialogue_text: str,
        atmosphere: Optional[Any],
        assembly_mode: str = "wrap",
    ) -> str:
        """组装最终输出"""


class IPaceSensor(ABC):
    """
    节奏感知器接口
    职责：自适应快/慢用户
    """

    @abstractmethod
    def get_current_pace(self) -> str:
        """获取当前节奏 (frozen/slow/normal/fast/urgent)"""

    @abstractmethod
    def update_pace(self, message_interval_seconds: float) -> None:
        """根据消息间隔更新节奏"""

    @abstractmethod
    def get_auto_mode_config(self) -> Any:
        """获取 AUTO_MODE 配置"""
