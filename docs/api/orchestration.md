# 编排系统 (Orchestration)

引擎初始化、对话编排和角色状态提取。

## 模块概览

```
luqi_engine/orchestration/
├── engine_initializer.py   — EngineInitializer 7阶段初始化编排
├── chat_orchestrator.py    — ChatOrchestrator 对话流程编排
└── character_extractor.py  — CharacterExtractor 角色状态提取
```

## EngineInitializer — 引擎初始化编排器 ⭐ 核心

```python
class EngineInitializer:
    """7阶段引擎初始化编排器

    初始化阶段顺序:
      1. config     — 加载配置
      2. core       — RNG/EventBus/PluginManager
      3. modules    — WorldView/Scene/Character/Narrative/Interaction
      4. llm        — LLMBridge/DialogueModes/Fallback/StateRenderer/IntentClassifier
      5. local_model — LocalModelPipeline
      6. local_llm  — LocalLLMAdapter
      7. performance — PoolManager/ResourceManager/SampleCollector

    快照恢复路径:
      - 尝试从snapshot_path恢复
      - 失败时自动降级到常规完整初始化
      - 不抛出异常，记录warning日志
    """

    def __init__(self, logger: Optional[logging.Logger] = None) -> None: ...

    @property
    def init_phases(self) -> List[str]:
        """返回已完成的初始化阶段列表"""

    async def initialize(
        self,
        engine: Any,
        snapshot_path: Optional[str] = None,
    ) -> None:
        """执行完整初始化流程

        Args:
            engine: LuqiEngine实例 (需有_config属性)
            snapshot_path: 可选快照路径，优先尝试快照恢复
        """
```

## ChatOrchestrator — 对话编排器

```python
class ChatOrchestrator:
    """对话流程编排器

    编排五层Agent流水线:
      Layer1 DialogueAgent → 意图识别 + CanonicalIR生成
      Layer2 NovelistAgent → 叙事增量预测
      Layer3 CriticAgent   → 质量审核 + 修正建议
      Layer4 AtmosphereAgent → 环境渲染
      Layer5 OutputAssembler → 最终输出组装

    校验链:
      IR → SupremeCourt.validate_dialogue_ir() → ValidatedIR
      Delta → SupremeCourt.validate_novel_delta() → ValidatedDelta
    """

    def __init__(self, engine: Any) -> None: ...

    async def orchestrate(
        self,
        user_input: str,
        character_id: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """执行完整对话编排流水线

        Returns:
          {
            "response": str,           # 最终回复文本
            "canonical_ir": CanonicalIR, # 规范IR
            "validated_ir": ValidatedIR,# 校验后IR
            "narrative_delta": NarrativeDelta,
            "emotion_delta": EmotionDelta,
            "violations": List[Violation],
            "agent_outputs": AgentOutputs,
            "corrections": AlgorithmCorrections,
            "metadata": Dict[str, Any],
          }
        """
```

## CharacterExtractor — 角色状态提取器

```python
class CharacterExtractor:
    """从CharacterEntity提取各子系统状态的工具类"""

    def __init__(self) -> None: ...

    def extract_personality(self, character: Any) -> Dict[str, float]:
        """提取OCEAN人格分数 {openness, conscientiousness, ...}"""

    def extract_emotion_pad(self, character: Any) -> Dict[str, float]:
        """提取PAD情感状态 {pleasure, arousal, dominance}"""

    def extract_character_state(self, character: Any) -> Dict[str, Any]:
        """提取完整角色状态快照 (用于Prompt构建)

        包含:
        - personality: OCEAN分数
        - emotion_pad: PAD状态
        - desires: 当前欲望向量
        - motives: 动机优先级列表
        - memory_summary: 近期记忆摘要
        - social_relations: 社交关系概要
        """
```
