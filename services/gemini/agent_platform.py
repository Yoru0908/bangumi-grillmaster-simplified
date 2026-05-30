from __future__ import annotations

import base64
import json
from typing import Any
from urllib import error, request
from urllib.parse import urlencode

from google import genai

from settings import settings


class AgentPlatformGeminiClient:
    """Compatibility wrapper exposing the google-genai async client shape."""

    def __init__(self):
        self.aio = _AgentPlatformAio()


class _AgentPlatformAio:
    def __init__(self):
        self.models = _AgentPlatformModels()


class _AgentPlatformModels:
    async def generate_content(self, *, model: str, contents: list, config) -> object:
        body = _build_generate_content_body(contents, config)
        if settings.gemini_agent_platform_proxy_url:
            response = await _post_json(_proxy_url(model), body)
            if response.status_code >= 400:
                raise RuntimeError(response.text)
            payload = _response_payload(response)
            _raise_payload_error(payload)
            return _GenerateContentResponse(payload)

        api_key = _api_key()
        url = _model_url(settings.gemini_agent_platform_base_url, model, api_key)
        response = await _post_json(url, body)
        if response.status_code == 404 and "us-central1-aiplatform" in url:
            response = await _post_json(
                _model_url(
                    "https://aiplatform.googleapis.com/v1beta1/publishers/google/models",
                    model,
                    api_key,
                ),
                body,
            )
        if response.status_code >= 400:
            raise RuntimeError(response.text)
        payload = _response_payload(response)
        _raise_payload_error(payload)
        return _GenerateContentResponse(payload)


class _GenerateContentResponse:
    def __init__(self, payload: dict):
        self.text = _extract_text(payload)
        self.usage_metadata = _UsageMetadata(payload.get("usageMetadata") or {})
        finish_reason = _extract_finish_reason(payload)
        self.candidates = [_Candidate(finish_reason)] if finish_reason else []


class _UsageMetadata:
    def __init__(self, payload: dict):
        self.prompt_token_count = payload.get("promptTokenCount", 0)
        self.cached_content_token_count = payload.get("cachedContentTokenCount", 0)
        self.candidates_token_count = payload.get("candidatesTokenCount", 0)
        self.thoughts_token_count = payload.get("thoughtsTokenCount", 0)
        self.total_token_count = payload.get("totalTokenCount", 0)


class _Candidate:
    def __init__(self, finish_reason: str):
        self.finish_reason = getattr(genai.types.FinishReason, finish_reason, finish_reason)


def gemini_client():
    if settings.gemini_backend == "agent_platform":
        return AgentPlatformGeminiClient()
    return genai.Client(api_key=settings.gemini_api_key)


def _api_key() -> str:
    api_key = (
        settings.gemini_agent_platform_api_key
        or settings.agent_platform_api_key
    )
    if not api_key:
        raise RuntimeError(
            "GEMINI_AGENT_PLATFORM_API_KEY or AGENT_PLATFORM_API_KEY is required "
            "for direct GEMINI_BACKEND=agent_platform"
        )
    return api_key


async def _post_json(url: str, body: dict):
    async with httpx.AsyncClient(timeout=None) as client:
        return await client.post(url, json=body)


def _model_url(base_url: str, model: str, api_key: str) -> str:
    return f"{base_url.rstrip('/')}/{model}:generateContent?key={api_key}"


def _proxy_url(model: str) -> str:
    separator = "&" if "?" in settings.gemini_agent_platform_proxy_url else "?"
    return (
        f"{settings.gemini_agent_platform_proxy_url.rstrip('/')}"
        f"{separator}{urlencode({'model': model})}"
    )


def _build_generate_content_body(contents: list, config) -> dict:
    body: dict[str, Any] = {
        "contents": [
            {
                "role": "user",
                "parts": [_content_part(item) for item in contents],
            }
        ]
    }
    if config is None:
        return body

    config_payload = config.model_dump(
        mode="json", by_alias=True, exclude_none=True
    )
    system_instruction = config_payload.pop("systemInstruction", None)
    if system_instruction:
        body["systemInstruction"] = _system_instruction(system_instruction)
    _normalize_thinking_config(config_payload)
    safety_settings = config_payload.pop("safetySettings", None)
    if safety_settings:
        body["safetySettings"] = safety_settings
    if config_payload:
        body["generationConfig"] = config_payload
    return body


def _system_instruction(system_instruction) -> dict:
    if isinstance(system_instruction, str):
        return {"parts": [{"text": system_instruction}]}
    if isinstance(system_instruction, dict) and "parts" in system_instruction:
        return system_instruction
    return {"parts": [_content_part(system_instruction)]}


def _content_part(item) -> dict:
    if isinstance(item, str):
        return {"text": item}

    inline_data = getattr(item, "inline_data", None)
    if inline_data is not None:
        data = inline_data.data
        encoded = data if isinstance(data, str) else base64.b64encode(data).decode("ascii")
        return {
            "inlineData": {
                "mimeType": inline_data.mime_type,
                "data": encoded,
            }
        }

    text = getattr(item, "text", None)
    if text is not None:
        return {"text": text}

    raise TypeError(f"Unsupported Gemini content part: {type(item)!r}")


def _normalize_thinking_config(config_payload: dict) -> None:
    thinking_budget = settings.gemini_agent_platform_thinking_budget
    if thinking_budget is None:
        return
    thinking_config = config_payload.get("thinkingConfig")
    if thinking_config is None:
        config_payload["thinkingConfig"] = {"thinkingBudget": thinking_budget}
        return
    thinking_config.pop("thinkingLevel", None)
    thinking_config["thinkingBudget"] = thinking_budget


def _extract_text(payload: dict) -> str:
    parts = (payload.get("candidates") or [{}])[0].get("content", {}).get("parts", [])
    return "".join(part.get("text", "") for part in parts)


def _extract_finish_reason(payload: dict) -> str | None:
    return (payload.get("candidates") or [{}])[0].get("finishReason")


def _response_payload(response) -> dict:
    try:
        return response.json()
    except (json.JSONDecodeError, ValueError):
        pass
    text = response.text or ""
    for line in text.splitlines():
        if line.startswith("data: "):
            return json.loads(line[6:])
    return {}


def _raise_payload_error(payload: dict) -> None:
    error_payload = payload.get("error")
    if not error_payload:
        return
    if isinstance(error_payload, dict):
        message = error_payload.get("message") or json.dumps(error_payload, ensure_ascii=False)
    else:
        message = str(error_payload)
    raise RuntimeError(message)


class _HttpModule:
    AsyncClient = None


class _AsyncUrlLibClient:
    def __init__(self, *, timeout=None):
        self.timeout = timeout

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url: str, json: dict):
        import asyncio

        return await asyncio.to_thread(_post_json_sync, url, json)


class _UrlLibResponse:
    def __init__(self, *, status_code: int, payload: dict | None, text: str):
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self):
        if self._payload is None:
            raise json.JSONDecodeError("response is not JSON", self.text, 0)
        return self._payload


def _post_json_sync(url: str, body: dict) -> _UrlLibResponse:
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=None) as resp:
            text = resp.read().decode("utf-8")
            payload = None
            try:
                payload = json.loads(text) if text else {}
            except json.JSONDecodeError:
                payload = None
            return _UrlLibResponse(
                status_code=resp.status,
                payload=payload,
                text=text,
            )
    except error.HTTPError as exc:
        text = exc.read().decode("utf-8")
        payload = None
        try:
            payload = json.loads(text) if text else {}
        except json.JSONDecodeError:
            payload = None
        return _UrlLibResponse(status_code=exc.code, payload=payload, text=text)


httpx = _HttpModule()
httpx.AsyncClient = _AsyncUrlLibClient
