from __future__ import annotations

import logging
import os
from typing import Any, AsyncIterator, Dict, List, Optional
from pathlib import Path

from luqi_engine.core.interfaces import ILLMBridge
from luqi_engine.core.types import LLMRequest, LLMResponse, LLMStreamChunk, SDKType


class LocalLLMAdapter(ILLMBridge):
    def __init__(self, model_path: str = "", n_gpu_layers: int = 0, n_ctx: int = 2048,
                 max_tokens: int = 512, temperature: float = 0.7, top_p: float = 0.9) -> None:
        self._model_path = model_path
        self._n_gpu_layers = n_gpu_layers
        self._n_ctx = n_ctx
        self._max_tokens = max_tokens
        self._temperature = temperature
        self._top_p = top_p
        self._model: Optional[Any] = None
        self._tokenizer: Optional[Any] = None
        self._hf_mode: bool = False
        self._loaded = False
        self._logger = logging.getLogger(__name__)

    def _ensure_loaded(self) -> None:
        if self._loaded and self._model is not None:
            return
        if not self._model_path or not os.path.exists(self._model_path):
            raise FileNotFoundError("Model file not found: {}".format(self._model_path))
        model_file = Path(self._model_path)
        if model_file.is_dir() or model_file.suffix in [".safetensors", ".bin"]:
            self._load_huggingface_model()
        elif model_file.suffix == ".gguf":
            self._load_gguf_model()
        else:
            raise ValueError("Unsupported model format: {}".format(model_file.suffix))

    def _load_gguf_model(self) -> None:
        try:
            from llama_cpp import Llama
            self._model = Llama(
                model_path=self._model_path,
                n_gpu_layers=self._n_gpu_layers,
                n_ctx=self._n_ctx,
                verbose=False,
            )
            self._hf_mode = False
            self._loaded = True
        except ImportError:
            raise ImportError(
                "llama-cpp-python is required for GGUF mode. "
                "Install with: pip install llama-cpp-python"
            )

    def _load_huggingface_model(self) -> None:
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer
            import torch
            print("[LocalLLMAdapter] Loading HuggingFace model from: {}".format(self._model_path))
            self._tokenizer = AutoTokenizer.from_pretrained(
                self._model_path, trust_remote_code=True
            )
            if self._tokenizer.pad_token is None:
                self._tokenizer.pad_token = self._tokenizer.eos_token
            self._model = AutoModelForCausalLM.from_pretrained(
                self._model_path,
                trust_remote_code=True,
                torch_dtype=torch.float16,
                device_map="cpu",
            )
            self._model.eval()
            self._hf_mode = True
            self._loaded = True
            print("[LocalLLMAdapter] HuggingFace model loaded successfully")
        except ImportError as e:
            raise ImportError(
                "transformers and torch are required for HuggingFace mode. "
                "Install with: pip install transformers torch"
            ) from e

    async def chat(self, request: LLMRequest) -> LLMResponse:
        self._ensure_loaded()
        if self._hf_mode:
            return await self._chat_hf(request)
        return await self._chat_gguf(request)

    async def _chat_gguf(self, request: LLMRequest) -> LLMResponse:
        messages = []
        for msg in request.messages:
            messages.append({
                "role": msg.get("role", "user"),
                "content": msg.get("content", ""),
            })
        try:
            response = self._model.create_chat_completion(
                messages=messages,
                max_tokens=self._max_tokens,
                temperature=self._temperature,
                top_p=self._top_p,
            )
            content = ""
            finish_reason = "stop"
            if response.get("choices") and len(response["choices"]) > 0:
                choice = response["choices"][0]
                content = choice.get("message", {}).get("content", "")
                finish_reason = choice.get("finish_reason", "stop")
            usage = response.get("usage", {})
            return LLMResponse(
                content=content,
                role="assistant",
                finish_reason=finish_reason,
                usage={
                    "prompt_tokens": usage.get("prompt_tokens", 0),
                    "completion_tokens": usage.get("completion_tokens", 0),
                    "total_tokens": usage.get("total_tokens", 0),
                },
                tokens=usage.get("total_tokens", 0),
            )
        except Exception as e:
            self._logger.error("GGUF推理失败: %s", e, exc_info=True)
            return LLMResponse(
                content="",
                role="assistant",
                finish_reason="error",
                usage={},
                tokens=0,
            )

    async def _chat_hf(self, request: LLMRequest) -> LLMResponse:
        try:
            text = self._tokenizer.apply_chat_template(
                request.messages, tokenize=False, add_generation_prompt=True
            )
            inputs = self._tokenizer(text, return_tensors="pt").to(self._model.device)
            import torch
            with torch.no_grad():
                outputs = self._model.generate(
                    **inputs,
                    max_new_tokens=self._max_tokens,
                    temperature=self._temperature,
                    top_p=self._top_p,
                    do_sample=self._temperature > 0,
                    pad_token_id=self._tokenizer.pad_token_id,
                )
            response_text = self._tokenizer.decode(
                outputs[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True
            )
            prompt_len = inputs["input_ids"].shape[1]
            completion_len = outputs.shape[1] - prompt_len
            return LLMResponse(
                content=response_text,
                role="assistant",
                finish_reason="stop" if completion_len < self._max_tokens else "length",
                usage={
                    "prompt_tokens": prompt_len,
                    "completion_tokens": completion_len,
                    "total_tokens": outputs.shape[1],
                },
                tokens=outputs.shape[1],
            )
        except Exception as e:
            self._logger.error("HuggingFace推理失败: %s", e, exc_info=True)
            return LLMResponse(
                content="",
                role="assistant",
                finish_reason="error",
                usage={},
                tokens=0,
            )

    async def chat_stream(self, request: LLMRequest) -> AsyncIterator[LLMStreamChunk]:
        self._ensure_loaded()
        if self._hf_mode:
            async for chunk in self._chat_stream_hf(request):
                yield chunk
            return
        messages = []
        for msg in request.messages:
            messages.append({
                "role": msg.get("role", "user"),
                "content": msg.get("content", ""),
            })

        try:
            for chunk in self._model.create_chat_completion(
                messages=messages,
                max_tokens=self._max_tokens,
                temperature=self._temperature,
                top_p=self._top_p,
                stream=True,
            ):
                choices = chunk.get("choices", [])
                if not choices:
                    continue
                delta = choices[0].get("delta", {})
                content = delta.get("content", "")
                finish_reason = choices[0].get("finish_reason")
                if content:
                    yield LLMStreamChunk(delta=content, finish_reason=finish_reason)
        except Exception as e:
            self._logger.error("GGUF流式推理失败: %s", e, exc_info=True)
            yield LLMStreamChunk(
                delta="",
                finish_reason="error",
            )

    async def _chat_stream_hf(self, request: LLMRequest) -> AsyncIterator[LLMStreamChunk]:
        try:
            text = self._tokenizer.apply_chat_template(
                request.messages, tokenize=False, add_generation_prompt=True
            )
            inputs = self._tokenizer(text, return_tensors="pt").to(self._model.device)
            import torch
            from transformers import StreamerGeneratorConfig, TextIteratorStreamer
            import threading
            streamer = TextIteratorStreamer(
                self._tokenizer, skip_prompt=True, skip_special_tokens=True
            )
            generation_kwargs = dict(
                **inputs,
                streamer=streamer,
                max_new_tokens=self._max_tokens,
                temperature=self._temperature,
                top_p=self._top_p,
                do_sample=self._temperature > 0,
                pad_token_id=self._tokenizer.pad_token_id,
            )
            thread = threading.Thread(target=self._model.generate, kwargs=generation_kwargs)
            thread.start()
            try:
                for new_text in streamer:
                    yield LLMStreamChunk(delta=new_text, finish_reason=None)
            finally:
                thread.join(timeout=30)
            yield LLMStreamChunk(delta="", finish_reason="stop")
        except Exception as e:
            self._logger.error("HuggingFace流式推理失败: %s", e, exc_info=True)
            yield LLMStreamChunk(
                delta="",
                finish_reason="error",
            )

    async def embed(self, text: str) -> List[float]:
        raise NotImplementedError(
            "LocalLLMAdapter does not support embedding. "
            "Use a dedicated embedding model."
        )

    async def validate(self) -> bool:
        if not self._model_path:
            return False
        if not os.path.exists(self._model_path):
            return False
        try:
            self._ensure_loaded()
            return self._loaded
        except Exception as e:
            self._logger.debug("模型验证失败: %s", e)
            return False

    def get_sdk_type(self) -> SDKType:
        return SDKType.LOCAL_LLM

    def unload(self) -> None:
        if self._model is not None:
            del self._model
            self._model = None
        if self._tokenizer is not None:
            del self._tokenizer
            self._tokenizer = None
        self._loaded = False
        self._hf_mode = False

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    @property
    def model_path(self) -> str:
        return self._model_path
