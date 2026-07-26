"""LLM response parsing utilities — safe extraction from OpenAI-compatible API responses."""
from typing import Optional


def extract_content(data: dict) -> str:
    """Safely extract text content from an OpenAI-compatible API response.
    Returns empty string if structure is unexpected."""
    if not data or not isinstance(data, dict):
        return ""
    choices = data.get("choices") or []
    if not choices or not isinstance(choices, list):
        return ""
    message = choices[0].get("message") or {} if isinstance(choices[0], dict) else {}
    content = message.get("content")
    if content is None:
        return ""
    return content.strip() if isinstance(content, str) else str(content).strip()
