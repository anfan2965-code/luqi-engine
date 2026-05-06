# 语音渲染 (Voice)

引擎输出的最终文本组装与格式化渲染模块。

## 模块概览

```
luqi_engine/voice/
├── voice_renderer.py     — 语音/风格渲染器 (语气/口吻/方言)
└── output_assembler.py   — 最终输出组装器 (多源合并)
```

## VoiceRenderer — 语音渲染器

```python
class VoiceRenderer(IVoiceRenderer):
    """确定性IR→自然语言渲染器（基于种子伪随机）

    功能:
    - 根据CanonicalIR的action选择动作模板
    - 根据tone选择语气模板（casual/cautious/formal/angry/sad/neutral）
    - 从key_points中随机选取内容点并渲染为对话
    - 基于种子的确定性输出（相同输入+种子=相同输出）

    模板系统:
    - _TONE_TEMPLATES: 6种语气模板 (casual/cautious/formal/angry/sad/neutral)
    - _ACTION_TEMPLATES: 动作模板 (smile_nod/step_back_draw_weapon/idle)
    - 基于LCG伪随机数生成器的key_points shuffle
    """

    def render(
        self,
        ir: CanonicalIR,
        voice_profile: Optional[Dict[str, Any]] = None,
        seed: int = 0,
    ) -> str:
        """将CanonicalIR渲染为自然语言文本

        Args:
            ir: CanonicalIR 包含 action/key_points/tone/length_hint
            voice_profile: Dict 角色语音配置
                - name: str 角色名 (默认"角色")
            seed: int 随机种子 (默认0，用于确定性输出)
        Returns:
            str: 渲染后的文本（动作描写 + 对话台词）
        """

    def _render_dialogue_from_keypoints(
        self,
        key_points: List[str],
        tone: str,
        length_hint: str,
        rng: Any,
        voice_profile: Optional[Dict[str, Any]] = None,
    ) -> str:
        """从key_points渲染对话内容

        Args:
            key_points: List[str] 关键点列表
            tone: str 语气类型
            length_hint: str 长度提示 (tiny/short/medium/long)
            rng: 伪随机数生成器实例
            voice_profile: 角色语音配置
        Returns:
            str: 渲染后的对话文本
        """
```

## OutputAssembler — 输出组装器

```python
class OutputAssembler:
    """多源输出最终组装

    合并来源:
    1. DialogueAgent 的 CanonicalIR.action_text
    2. NovelistAgent 的 narrative_increment
    3. AtmosphereAgent 的 atmosphere_description
    4. VoiceRenderer 的风格化结果

    组装策略:
    - 结构化模式: 分段组装，带标签
    - 自然流模式: 无缝拼接，模拟自然对话
    - 富文本模式: 含Markdown/表情/排版
    """

    def __init__(self, mode: AssemblyMode = AssemblyMode.NATURAL_FLOW) -> None: ...

    def assemble(
        self,
        components: Dict[str, str],
        format_config: FormatConfig,
    ) -> AssembledOutput:
        """组装各组件为最终输出"""

    def apply_template(self, template: str, variables: Dict[str, str]) -> str: ...
```
