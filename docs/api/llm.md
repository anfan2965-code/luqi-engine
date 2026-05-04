# LLM 模块

LLM模块负责与大语言模型的交互，包括适配器注册、意图分类、状态渲染和降级容错。

## 核心组件

::: luqi_engine.llm.bridge
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: luqi_engine.llm.intent_classifier
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: luqi_engine.llm.state_renderer
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: luqi_engine.llm.fallback
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: luqi_engine.llm.adapter_registry
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: luqi_engine.llm.dialogue_modes
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: luqi_engine.llm.prompt_builder
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: luqi_engine.llm.response_parser
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: luqi_engine.llm.local_llm_adapter
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: luqi_engine.llm.deepseek_optimizer
    options:
      show_root_heading: true
      show_root_toc_entry: true

## 意图分类 (IntentClassifier)

IntentClassifier 负责判断用户输入的复杂度级别：

```python
from luqi_engine.llm.intent_classifier import IntentClassifier, IntentLevel

classifier = IntentClassifier()

# 分类示例
level = classifier.classify("你好")
# 返回: IntentLevel.SIMPLE

level = classifier.classify("我很难过，你能安慰我吗")
# 返回: IntentLevel.MODERATE

level = classifier.classify("给我讲一个关于这个世界的完整故事背景")
# 返回: IntentLevel.COMPLEX
```

### 分级标准

| 级别 | 长度范围 | 处理方式 | 典型场景 |
|------|----------|----------|----------|
| `SIMPLE` | ≤20字符 | 本地LLM | 问候、简单问答 |
| `MODERATE` | 21-100字符 | 本地LLM | 日常对话、情感表达 |
| `COMPLEX` | >100字符 | 云端LLM | 复杂推理、长文本生成 |

## 状态渲染 (StateRenderer)

StateRenderer 将角色状态转换为系统提示词：

```python
from luqi_engine.llm.state_renderer import StateRenderer

renderer = StateRenderer()

prompt = renderer.render_system_prompt(
    character_name="小雪",
    personality={
        "openness": 85,
        "conscientiousness": 70,
        "extraversion": 35,
        "agreeableness": 75,
        "neuroticism": 55,
    },
    pad_emotion={
        "pleasure": -0.3,
        "arousal": 0.2,
        "dominance": -0.1,
    },
    scene="教室",
    behavior_instruction="温柔地回应",
    memories=[{"content": "昨天聊过天气"}],
    background="转学生",
)
print(prompt)
```

## 降级容错 (LLMFallback)

四级降级机制确保离线/故障时的可用性：

```python
from luqi_engine.llm.fallback import LLMFallback, DegradationLevel

fallback = LLMFallback()

# 查询当前降级级别
level = fallback.current_level
# DegradationLevel.NORMAL / DEGRADED / SEVERELY_DEGRADED / OFFLINE

# 手动设置降级
fallback.set_degradation_level(DegradationLevel.OFFLINE)
```

### 降级策略

| 级别 | 连续失败次数 | 行为 |
|------|-------------|------|
| `NORMAL` | 0-2次 | 正常使用云端LLM |
| `DEGRADED` | 3-5次 | 降低请求频率，启用缓存 |
| `SEVERELY_DEGRADED` | 6-9次 | 主要使用本地模型 |
| `OFFLINE` | ≥10次 | 完全切换到本地模型 |

## 对话模式 (DialogueModes)

支持多种对话模式：

```python
from luqi_engine.llm.dialogue_modes import DialogueMode

mode = DialogueMode.SINGLE_CHARACTER    # 单角色对话
mode = DialogueMode.MULTI_CHARACTER     # 多角色对话（默认）
```

## LLM适配器

支持多种LLM后端：

::: luqi_engine.llm.openai_adapter
    options:
      show_root_heading: true

::: luqi_engine.llm.anthropic_adapter
    options:
      show_root_heading: true
