"""Minimal synchronous Gemini client for mai_flow.

Two backends, selected by env:
Four backends, tried in order:
  - GEMINI_AGENT_PLATFORM_PROXY_URL set → POST <url>?model=<model>
    (gemini-chat compatible proxy, parses SSE data lines)
  - OPENROUTER_API_KEY set → OpenRouter chat/completions
    (model from LLM_MODEL env, default google/gemini-2.5-flash)
  - GEMINI_API_KEY set → AI Studio endpoint
    generativelanguage.googleapis.com/v1beta/models/{model}:generateContent
  - GEMINI_AGENT_PLATFORM_API_KEY / AGENT_PLATFORM_API_KEY → Vertex
    publisher endpoint {GEMINI_AGENT_PLATFORM_BASE_URL}/{model}:generateContent
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

DEFAULT_BASE_URL = (
    "https://aiplatform.googleapis.com/v1beta1/publishers/google/models"
)
FALLBACK_BASE_URL = (
    "https://us-central1-aiplatform.googleapis.com/v1beta1"
    "/publishers/google/models"
)


@dataclass
class LLMResult:
    text: str
    prompt_tokens: int = 0
    output_tokens: int = 0


def _post(url: str, body: dict, timeout: int = 300) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            # Cloudflare bot-fight blocks urllib's default UA (error 1010).
            "User-Agent": "mai-flow/1.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
    # Proxy may answer with SSE "data: {...}" lines.
    if raw.lstrip().startswith("data:"):
        chunks = []
        for line in raw.splitlines():
            line = line.strip()
            if line.startswith("data:"):
                payload = line[5:].strip()
                if payload and payload != "[DONE]":
                    chunks.append(json.loads(payload))
        if not chunks:
            raise RuntimeError("Empty SSE response from proxy")
        return chunks[-1]
    return json.loads(raw)


def generate(
    prompt: str,
    *,
    system: str | None = None,
    model: str | None = None,
    json_mode: bool = True,
    timeout: int = 300,
) -> LLMResult:
    openrouter_key = os.environ.get("OPENROUTER_API_KEY")
    if openrouter_key and not os.environ.get("GEMINI_AGENT_PLATFORM_PROXY_URL"):
        return _generate_openrouter(
            prompt, system=system, model=model,
            json_mode=json_mode, timeout=timeout, api_key=openrouter_key,
        )

    model = model or os.environ.get("GEMINI_MODEL", "gemini-3-flash-preview")
    body: dict[str, Any] = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {},
    }
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}
    if json_mode:
        body["generationConfig"]["responseMimeType"] = "application/json"

    proxy = os.environ.get("GEMINI_AGENT_PLATFORM_PROXY_URL")
    studio_key = os.environ.get("GEMINI_API_KEY")
    api_key = os.environ.get("GEMINI_AGENT_PLATFORM_API_KEY") or os.environ.get(
        "AGENT_PLATFORM_API_KEY"
    )
    if proxy:
        sep = "&" if "?" in proxy else "?"
        url = f"{proxy.rstrip('/')}{sep}{urlencode({'model': model})}"
    elif studio_key:
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent?key={studio_key}"
        )
    elif api_key:
        base = os.environ.get("GEMINI_AGENT_PLATFORM_BASE_URL", DEFAULT_BASE_URL)
        url = f"{base.rstrip('/')}/{model}:generateContent?key={api_key}"
    else:
        raise RuntimeError(
            "Set GEMINI_API_KEY, GEMINI_AGENT_PLATFORM_PROXY_URL, or "
            "GEMINI_AGENT_PLATFORM_API_KEY"
        )

    try:
        payload = _post(url, body, timeout)
    except urllib.error.HTTPError as e:
        # Vertex publisher endpoint 404 → retry on the global host.
        if e.code == 404 and api_key and not proxy and "us-central1" not in url:
            url = f"{FALLBACK_BASE_URL}/{model}:generateContent?key={api_key}"
            payload = _post(url, body, timeout)
        else:
            raise RuntimeError(f"LLM HTTP {e.code}: {e.read()[:300]!r}") from e

    if "error" in payload:
        raise RuntimeError(f"LLM error: {payload['error']}")

    text_parts = []
    for cand in payload.get("candidates", []):
        for part in (cand.get("content") or {}).get("parts", []):
            if "text" in part:
                text_parts.append(part["text"])
    usage = payload.get("usageMetadata") or {}
    return LLMResult(
        text="".join(text_parts),
        prompt_tokens=usage.get("promptTokenCount", 0),
        output_tokens=usage.get("candidatesTokenCount", 0),
    )

def _generate_openrouter(
    prompt: str,
    *,
    system: str | None,
    model: str | None,
    json_mode: bool,
    timeout: int,
    api_key: str,
) -> LLMResult:
    model = model or os.environ.get("LLM_MODEL", "google/gemini-2.5-flash")
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    body: dict[str, Any] = {"model": model, "messages": messages}
    if json_mode:
        body["response_format"] = {"type": "json_object"}

    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"OpenRouter HTTP {e.code}: {e.read()[:300]!r}") from e

    if "error" in payload:
        raise RuntimeError(f"OpenRouter error: {payload['error']}")
    choice = (payload.get("choices") or [{}])[0]
    usage = payload.get("usage") or {}
    return LLMResult(
        text=(choice.get("message") or {}).get("content", ""),
        prompt_tokens=usage.get("prompt_tokens", 0),
        output_tokens=usage.get("completion_tokens", 0),
    )


def generate_json(prompt: str, **kwargs) -> Any:
    """generate() + tolerant JSON extraction (strips code fences)."""
    result = generate(prompt, **kwargs)
    text = result.text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0]
    return json.loads(text)
