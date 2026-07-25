"""
Model Adapter Layer for Cambium.

This is the abstraction that makes "any model pluggable" real rather than
just a README claim. Every LLM call in Cambium goes through a ModelAdapter.

Design:
- Protocol-based: any class implementing the protocol is a valid adapter
- Capability detection: max_context, supports_streaming, supports_thinking, supports_tools
- Fallback: if the primary model fails, automatically try the backup
- Parameter normalization: strips unsupported params before sending

Built-in adapters:
- OpenAICompatibleAdapter: works with OpenAI, Azure, ModelScope, OpenRouter,
  SiliconFlow, vLLM, llama.cpp, Ollama (all OpenAI-compatible APIs)

Future adapters can be added (Anthropic native, Google Gemini native, etc.)
without touching any calling code.
"""
from __future__ import annotations
import json
import re
import asyncio
from typing import Dict, List, Optional, Any, Protocol
from dataclasses import dataclass, field
import httpx


# ============================================================
# Capability descriptor
# ============================================================

@dataclass
class ModelCapabilities:
    """Describes what a model can do. Used to normalize requests."""
    max_context: int = 32768
    max_output: int = 8192
    supports_streaming: bool = True
    supports_thinking: bool = False
    supports_tools: bool = True
    supports_json_mode: bool = False
    # Some models use different param names
    thinking_param_name: str = "enable_thinking"  # Qwen uses this
    # Models that don't support certain OpenAI params
    unsupported_params: set = field(default_factory=set)


# Known model capability profiles (by model name substring)
_KNOWN_PROFILES = {
    "qwen": ModelCapabilities(
        max_context=32768, supports_thinking=True, supports_tools=True,
        thinking_param_name="enable_thinking",
    ),
    "deepseek": ModelCapabilities(
        max_context=65536, supports_thinking=False, supports_tools=False,
        unsupported_params={"enable_thinking", "thinking_budget"},
    ),
    "llama": ModelCapabilities(
        max_context=8192, supports_thinking=False, supports_tools=False,
        unsupported_params={"enable_thinking", "thinking_budget", "top_k"},
    ),
    "gpt-4": ModelCapabilities(
        max_context=8192, supports_thinking=False, supports_tools=True,
        unsupported_params={"enable_thinking", "thinking_budget"},
    ),
    "gpt-4o": ModelCapabilities(
        max_context=128000, supports_thinking=False, supports_tools=True,
        unsupported_params={"enable_thinking", "thinking_budget"},
    ),
    "gpt-5": ModelCapabilities(
        max_context=128000, supports_thinking=False, supports_tools=True,
        unsupported_params={"enable_thinking", "thinking_budget"},
    ),
    "claude": ModelCapabilities(
        max_context=200000, supports_thinking=True, supports_tools=True,
        thinking_param_name="thinking",
        unsupported_params={"enable_thinking", "frequency_penalty"},
    ),
    "mistral": ModelCapabilities(
        max_context=32768, supports_thinking=False, supports_tools=True,
        unsupported_params={"enable_thinking", "thinking_budget"},
    ),
    "gemini": ModelCapabilities(
        max_context=128000, supports_thinking=False, supports_tools=True,
        unsupported_params={"enable_thinking", "thinking_budget", "frequency_penalty"},
    ),
}


def detect_capabilities(model_name: str) -> ModelCapabilities:
    """Auto-detect model capabilities from model name."""
    name_lower = model_name.lower()
    for key, caps in _KNOWN_PROFILES.items():
        if key in name_lower:
            return caps
    # Default: assume OpenAI-compatible with standard capabilities
    return ModelCapabilities()


# ============================================================
# ModelAdapter Protocol
# ============================================================

class ModelAdapter(Protocol):
    """Protocol that all model adapters must implement."""

    async def chat(
        self,
        messages: List[Dict],
        *,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stream: bool = False,
        tools: Optional[List[Dict]] = None,
        enable_thinking: bool = False,
        thinking_budget: int = 0,
        **kwargs,
    ) -> Dict:
        """Send a chat completion request. Returns the full response dict.
        If stream=True, returns an async iterator of chunks instead."""
        ...

    async def chat_stream(
        self,
        messages: List[Dict],
        *,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        tools: Optional[List[Dict]] = None,
        enable_thinking: bool = False,
        thinking_budget: int = 0,
        **kwargs,
    ):
        """Async generator yielding stream chunks."""
        ...

    def capabilities(self) -> ModelCapabilities:
        """Return the capability descriptor for this model."""
        ...


# ============================================================
# OpenAICompatibleAdapter
# ============================================================

class OpenAICompatibleAdapter:
    """Adapter for any OpenAI-compatible API (OpenAI, ModelScope, vLLM, llama.cpp, etc.)"""

    def __init__(self, *, api_key: str, base_url: str, model: str,
                 capabilities: Optional[ModelCapabilities] = None):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._caps = capabilities or detect_capabilities(model)

    def capabilities(self) -> ModelCapabilities:
        return self._caps

    def _build_payload(
        self,
        messages: List[Dict],
        *,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stream: bool = False,
        tools: Optional[List[Dict]] = None,
        enable_thinking: bool = False,
        thinking_budget: int = 0,
        **kwargs,
    ) -> Dict:
        """Build the request payload, stripping unsupported params."""
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": min(max_tokens, self._caps.max_output),
            "stream": stream,
        }
        # Thinking support
        if enable_thinking and self._caps.supports_thinking:
            payload[self._caps.thinking_param_name] = True
            if thinking_budget > 0:
                payload["thinking_budget"] = thinking_budget
        # Tools support
        if tools and self._caps.supports_tools:
            payload["tools"] = tools
            payload["tool_choice"] = kwargs.get("tool_choice", "auto")
        # Extra kwargs (top_p, top_k, etc.) — filter unsupported
        for k, v in kwargs.items():
            if k not in self._caps.unsupported_params and v is not None:
                payload[k] = v
        # Truncate messages if they exceed context
        payload["messages"] = self._truncate_messages(payload["messages"])
        return payload

    def _truncate_messages(self, messages: List[Dict]) -> List[Dict]:
        """If messages exceed context window, keep system + last N messages."""
        # Rough estimate: 1 token ≈ 3.5 chars for mixed CJK+English
        total_chars = sum(len(m.get("content", "")) for m in messages)
        estimated_tokens = total_chars // 3
        if estimated_tokens <= self._caps.max_context * 0.8:
            return messages
        # Need to truncate: keep system messages + last N
        system_msgs = [m for m in messages if m.get("role") == "system"]
        non_system = [m for m in messages if m.get("role") != "system"]
        # Keep last N non-system messages that fit
        budget = int(self._caps.max_context * 0.7)
        kept = []
        chars = sum(len(m.get("content", "")) for m in system_msgs)
        for m in reversed(non_system):
            chars += len(m.get("content", ""))
            if chars > budget:
                break
            kept.insert(0, m)
        # Add a truncation notice
        if len(kept) < len(non_system):
            notice = {"role": "system", "content": f"[注意] 由于上下文长度限制，已省略 {len(non_system) - len(kept)} 条较早的消息。"}
            return system_msgs + [notice] + kept
        return system_msgs + kept

    async def chat(
        self,
        messages: List[Dict],
        *,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stream: bool = False,
        tools: Optional[List[Dict]] = None,
        enable_thinking: bool = False,
        thinking_budget: int = 0,
        timeout: float = 300.0,
        **kwargs,
    ) -> Dict:
        """Send a non-streaming chat completion request."""
        payload = self._build_payload(
            messages, temperature=temperature, max_tokens=max_tokens,
            stream=False, tools=tools, enable_thinking=enable_thinking,
            thinking_budget=thinking_budget, **kwargs,
        )
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                json=payload, headers=headers,
            )
            if resp.status_code != 200:
                raise ModelError(
                    f"HTTP {resp.status_code}: {resp.text[:300]}",
                    status_code=resp.status_code,
                )
            return resp.json()

    async def chat_stream(
        self,
        messages: List[Dict],
        *,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        tools: Optional[List[Dict]] = None,
        enable_thinking: bool = False,
        thinking_budget: int = 0,
        timeout: float = 300.0,
        **kwargs,
    ):
        """Async generator yielding SSE stream chunks."""
        payload = self._build_payload(
            messages, temperature=temperature, max_tokens=max_tokens,
            stream=True, tools=tools, enable_thinking=enable_thinking,
            thinking_budget=thinking_budget, **kwargs,
        )
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout, connect=30.0)) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                json=payload, headers=headers,
            ) as resp:
                if resp.status_code != 200:
                    body = await resp.aread()
                    raise ModelError(
                        f"HTTP {resp.status_code}: {body.decode(errors='ignore')[:300]}",
                        status_code=resp.status_code,
                    )
                async for line in resp.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    data_str = line[5:].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        yield json.loads(data_str)
                    except json.JSONDecodeError:
                        continue


# ============================================================
# Fallback Adapter — tries primary, falls back to backup on failure
# ============================================================

class FallbackAdapter:
    """Wraps a primary adapter and a backup adapter. If primary fails
    (network error, 429, 500, etc.), automatically retries with backup."""

    def __init__(self, primary: ModelAdapter, backup: Optional[ModelAdapter] = None,
                 max_retries: int = 2):
        self.primary = primary
        self.backup = backup
        self.max_retries = max_retries

    def capabilities(self) -> ModelCapabilities:
        return self.primary.capabilities()

    async def chat(self, messages: List[Dict], **kwargs) -> Dict:
        last_error = None
        for attempt in range(self.max_retries):
            try:
                return await self.primary.chat(messages, **kwargs)
            except ModelError as e:
                last_error = e
                # Retry on 429 (rate limit) or 5xx
                if e.status_code in (429, 500, 502, 503, 504):
                    await asyncio.sleep(1 * (attempt + 1))
                    continue
                # Other errors: try backup
                break
            except (httpx.ConnectError, httpx.ReadTimeout, httpx.ConnectTimeout) as e:
                last_error = e
                await asyncio.sleep(1 * (attempt + 1))
                continue
        # All retries failed — try backup
        if self.backup:
            try:
                return await self.backup.chat(messages, **kwargs)
            except Exception as e:
                last_error = e
        raise last_error or ModelError("All adapters failed")

    async def chat_stream(self, messages: List[Dict], **kwargs):
        """Stream from primary; if it fails before first chunk, switch to backup."""
        try:
            async for chunk in self.primary.chat_stream(messages, **kwargs):
                yield chunk
            return
        except (ModelError, httpx.ConnectError, httpx.ReadTimeout) as e:
            if not self.backup:
                raise
            # Fall through to backup
        async for chunk in self.backup.chat_stream(messages, **kwargs):
            yield chunk


# ============================================================
# Exceptions
# ============================================================

class ModelError(Exception):
    """Raised when a model API call fails."""
    def __init__(self, message: str, status_code: int = 0):
        super().__init__(message)
        self.status_code = status_code


class JSONExtractionError(Exception):
    """Raised when LLM returns malformed JSON."""
    pass


# ============================================================
# Helper: extract JSON from LLM response (with retry)
# ============================================================

def extract_json_from_text(text: str) -> Optional[Dict]:
    """Extract a JSON object from LLM response text.
    Handles: ```json blocks, raw JSON, JSON embedded in prose.
    Returns None if no valid JSON found."""
    if not text:
        return None
    # Try ```json ... ``` block first
    m = re.search(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    # Try raw JSON object
    m = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    # Try JSON array
    m = re.search(r"\[[^\[\]]*(?:\[[^\[\]]*\][^\[\]]*)*\]", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    return None


async def chat_and_extract_json(
    adapter: ModelAdapter,
    prompt: str,
    *,
    temperature: float = 0.2,
    max_tokens: int = 800,
    timeout: float = 30.0,
    max_retries: int = 2,
) -> Optional[Dict]:
    """Send a prompt to the model and extract JSON from the response.
    Retries on JSON parse failure with a corrective prompt."""
    messages = [{"role": "user", "content": prompt}]
    for attempt in range(max_retries):
        try:
            result = await adapter.chat(
                messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=False,
                enable_thinking=False,
                timeout=timeout,
            )
            text = result["choices"][0]["message"]["content"].strip()
            parsed = extract_json_from_text(text)
            if parsed is not None:
                return parsed
            # Retry with a corrective prompt
            if attempt < max_retries - 1:
                messages = [
                    {"role": "user", "content": prompt},
                    {"role": "assistant", "content": text},
                    {"role": "user", "content": "你的回复不包含有效的 JSON。请只输出纯 JSON，不要其他文字。"},
                ]
        except Exception as e:
            if attempt < max_retries - 1:
                await asyncio.sleep(1)
                continue
            raise
    return None


# ============================================================
# Factory: create adapter from config
# ============================================================

def create_adapter(api_key: str, base_url: str, model: str,
                   backup_config: Optional[Dict] = None) -> ModelAdapter:
    """Create a ModelAdapter from config. If backup_config is provided,
    wraps in a FallbackAdapter."""
    primary = OpenAICompatibleAdapter(
        api_key=api_key, base_url=base_url, model=model,
    )
    if backup_config and backup_config.get("api_base_url"):
        backup = OpenAICompatibleAdapter(
            api_key=backup_config.get("api_key", ""),
            base_url=backup_config["api_base_url"],
            model=backup_config.get("api_model", model),
        )
        return FallbackAdapter(primary, backup)
    return primary
