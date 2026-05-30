import base64
import importlib
import json
import unittest
from unittest.mock import patch

from google import genai


class _FakeHttpResponse:
    def __init__(self, status_code: int, payload: dict | None = None, text: str = ""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self):
        if self.text:
            raise json.JSONDecodeError("not json", self.text, 0)
        return self._payload


class _FakeAsyncClient:
    posts: list[tuple[str, dict]] = []
    responses: list[_FakeHttpResponse] = []

    def __init__(self, *, timeout=None):
        self.timeout = timeout

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url: str, json: dict):
        self.__class__.posts.append((url, json))
        return self.__class__.responses.pop(0)


class AgentPlatformGeminiTests(unittest.IsolatedAsyncioTestCase):
    def _agent_platform_module(self):
        try:
            return importlib.import_module("services.gemini.agent_platform")
        except ImportError as exc:
            self.fail(f"services.gemini.agent_platform is missing: {exc}")

    def setUp(self):
        _FakeAsyncClient.posts = []
        _FakeAsyncClient.responses = []

    def test_agent_platform_uses_original_thinking_level_by_default(self):
        module = self._agent_platform_module()

        self.assertIsNone(
            module.settings.__class__.model_fields[
                "gemini_agent_platform_thinking_budget"
            ].default
        )

    async def test_generate_content_posts_gemini_rest_payload_and_parses_response(self):
        module = self._agent_platform_module()
        _FakeAsyncClient.responses = [
            _FakeHttpResponse(
                200,
                {
                    "candidates": [
                        {
                            "content": {"parts": [{"text": "translated"}]},
                            "finishReason": "STOP",
                        }
                    ],
                    "usageMetadata": {
                        "promptTokenCount": 10,
                        "cachedContentTokenCount": 3,
                        "candidatesTokenCount": 5,
                        "thoughtsTokenCount": 2,
                    },
                },
            )
        ]
        config = genai.types.GenerateContentConfig(
            system_instruction="system prompt",
            response_mime_type="application/json",
            thinking_config=genai.types.ThinkingConfig(
                thinking_level=genai.types.ThinkingLevel.HIGH
            ),
        )
        media_part = genai.types.Part.from_bytes(
            data=b"audio-bytes",
            mime_type="audio/ogg",
        )

        with (
            patch.object(module.httpx, "AsyncClient", _FakeAsyncClient),
            patch.object(module.settings, "gemini_agent_platform_proxy_url", None),
            patch.object(module.settings, "gemini_agent_platform_api_key", "agent-key"),
            patch.object(module.settings, "agent_platform_api_key", None),
            patch.object(
                module.settings,
                "gemini_agent_platform_base_url",
                "https://us-central1-aiplatform.googleapis.com/v1beta1/publishers/google/models",
            ),
            patch.object(module.settings, "gemini_agent_platform_thinking_budget", None),
        ):
            client = module.AgentPlatformGeminiClient()
            response = await client.aio.models.generate_content(
                model="gemini-2.5-pro",
                contents=[media_part, "hello"],
                config=config,
            )

        url, body = _FakeAsyncClient.posts[0]
        self.assertEqual(
            url,
            "https://us-central1-aiplatform.googleapis.com/v1beta1/publishers/google/models/"
            "gemini-2.5-pro:generateContent?key=agent-key",
        )
        self.assertEqual(body["contents"][0]["role"], "user")
        self.assertEqual(
            body["contents"][0]["parts"][0],
            {
                "inlineData": {
                    "mimeType": "audio/ogg",
                    "data": base64.b64encode(b"audio-bytes").decode("ascii"),
                }
            },
        )
        self.assertEqual(body["contents"][0]["parts"][1], {"text": "hello"})
        self.assertEqual(
            body["systemInstruction"], {"parts": [{"text": "system prompt"}]}
        )
        self.assertEqual(
            body["generationConfig"]["responseMimeType"], "application/json"
        )
        self.assertEqual(
            body["generationConfig"]["thinkingConfig"]["thinkingLevel"], "HIGH"
        )
        self.assertNotIn("thinkingBudget", body["generationConfig"]["thinkingConfig"])
        self.assertEqual(response.text, "translated")
        self.assertEqual(response.usage_metadata.prompt_token_count, 10)
        self.assertEqual(response.usage_metadata.cached_content_token_count, 3)
        self.assertEqual(response.usage_metadata.candidates_token_count, 5)
        self.assertEqual(response.usage_metadata.thoughts_token_count, 2)
        self.assertEqual(
            response.candidates[0].finish_reason,
            genai.types.FinishReason.STOP,
        )

    async def test_generate_content_uses_thinking_budget_when_configured(self):
        module = self._agent_platform_module()
        _FakeAsyncClient.responses = [
            _FakeHttpResponse(
                200,
                {
                    "candidates": [
                        {
                            "content": {"parts": [{"text": "translated"}]},
                            "finishReason": "STOP",
                        }
                    ],
                    "usageMetadata": {
                        "promptTokenCount": 10,
                        "cachedContentTokenCount": 3,
                        "candidatesTokenCount": 5,
                        "thoughtsTokenCount": 2,
                    },
                },
            )
        ]
        config = genai.types.GenerateContentConfig(
            system_instruction="system prompt",
            response_mime_type="application/json",
            thinking_config=genai.types.ThinkingConfig(
                thinking_level=genai.types.ThinkingLevel.HIGH
            ),
        )
        media_part = genai.types.Part.from_bytes(
            data=b"audio-bytes",
            mime_type="audio/ogg",
        )

        with (
            patch.object(module.httpx, "AsyncClient", _FakeAsyncClient),
            patch.object(module.settings, "gemini_agent_platform_proxy_url", None),
            patch.object(module.settings, "gemini_agent_platform_api_key", "agent-key"),
            patch.object(module.settings, "agent_platform_api_key", None),
            patch.object(
                module.settings,
                "gemini_agent_platform_base_url",
                "https://us-central1-aiplatform.googleapis.com/v1beta1/publishers/google/models",
            ),
            patch.object(module.settings, "gemini_agent_platform_thinking_budget", 32768),
        ):
            client = module.AgentPlatformGeminiClient()
            response = await client.aio.models.generate_content(
                model="gemini-2.5-pro",
                contents=[media_part, "hello"],
                config=config,
            )

        url, body = _FakeAsyncClient.posts[0]
        self.assertEqual(
            url,
            "https://us-central1-aiplatform.googleapis.com/v1beta1/publishers/google/models/"
            "gemini-2.5-pro:generateContent?key=agent-key",
        )
        self.assertEqual(
            body["generationConfig"]["thinkingConfig"]["thinkingBudget"], 32768
        )
        self.assertNotIn("thinkingLevel", body["generationConfig"]["thinkingConfig"])
        self.assertEqual(response.text, "translated")

    async def test_generate_content_falls_back_to_global_endpoint_on_regional_404(self):
        module = self._agent_platform_module()
        _FakeAsyncClient.responses = [
            _FakeHttpResponse(404, text="not found"),
            _FakeHttpResponse(
                200,
                {
                    "candidates": [
                        {
                            "content": {"parts": [{"text": "ok"}]},
                            "finishReason": "STOP",
                        }
                    ]
                },
            ),
        ]

        with (
            patch.object(module.httpx, "AsyncClient", _FakeAsyncClient),
            patch.object(module.settings, "gemini_agent_platform_proxy_url", None),
            patch.object(module.settings, "gemini_agent_platform_api_key", None),
            patch.object(module.settings, "agent_platform_api_key", "shared-key"),
            patch.object(
                module.settings,
                "gemini_agent_platform_base_url",
                "https://us-central1-aiplatform.googleapis.com/v1beta1/publishers/google/models",
            ),
        ):
            client = module.AgentPlatformGeminiClient()
            response = await client.aio.models.generate_content(
                model="gemini-2.5-pro",
                contents=["hello"],
                config=genai.types.GenerateContentConfig(),
            )

        self.assertEqual(response.text, "ok")
        self.assertEqual(len(_FakeAsyncClient.posts), 2)
        self.assertTrue(_FakeAsyncClient.posts[0][0].startswith("https://us-central1-"))
        self.assertEqual(
            _FakeAsyncClient.posts[1][0],
            "https://aiplatform.googleapis.com/v1beta1/publishers/google/models/"
            "gemini-2.5-pro:generateContent?key=shared-key",
        )

    async def test_generate_content_requires_agent_platform_key_for_direct_endpoint(self):
        module = self._agent_platform_module()
        with (
            patch.object(module.httpx, "AsyncClient", _FakeAsyncClient),
            patch.object(module.settings, "gemini_agent_platform_proxy_url", None),
            patch.object(module.settings, "gemini_agent_platform_api_key", None),
            patch.object(module.settings, "agent_platform_api_key", None),
            patch.object(module.settings, "gemini_api_key", "existing-gemini-key"),
        ):
            client = module.AgentPlatformGeminiClient()
            with self.assertRaises(RuntimeError) as raised:
                await client.aio.models.generate_content(
                    model="gemini-2.5-pro",
                    contents=["hello"],
                    config=genai.types.GenerateContentConfig(),
                )

        self.assertIn("AGENT_PLATFORM_API_KEY", str(raised.exception))
        self.assertEqual(_FakeAsyncClient.posts, [])

    async def test_generate_content_uses_configured_proxy_url_and_parses_sse(self):
        module = self._agent_platform_module()
        _FakeAsyncClient.responses = [
            _FakeHttpResponse(
                200,
                text=(
                    ": heartbeat\n\n"
                    'data: {"candidates":[{"content":{"parts":[{"text":"proxied"}]},'
                    '"finishReason":"STOP"}],"usageMetadata":{"promptTokenCount":4}}\n\n'
                ),
            )
        ]

        with (
            patch.object(module.httpx, "AsyncClient", _FakeAsyncClient),
            patch.object(
                module.settings,
                "gemini_agent_platform_proxy_url",
                "https://gemini-proxy.46log.com",
            ),
        ):
            client = module.AgentPlatformGeminiClient()
            response = await client.aio.models.generate_content(
                model="gemini-2.5-pro",
                contents=["hello"],
                config=genai.types.GenerateContentConfig(),
            )

        self.assertEqual(response.text, "proxied")
        self.assertEqual(response.usage_metadata.prompt_token_count, 4)
        self.assertEqual(
            _FakeAsyncClient.posts[0][0],
            "https://gemini-proxy.46log.com?model=gemini-2.5-pro",
        )
        self.assertNotIn("key=", _FakeAsyncClient.posts[0][0])

    async def test_generate_content_raises_proxy_sse_error_payload(self):
        module = self._agent_platform_module()
        _FakeAsyncClient.responses = [
            _FakeHttpResponse(
                200,
                text='data: {"error":{"code":401,"message":"proxy auth failed"}}\n\n',
            )
        ]

        with (
            patch.object(module.httpx, "AsyncClient", _FakeAsyncClient),
            patch.object(
                module.settings,
                "gemini_agent_platform_proxy_url",
                "https://gemini-proxy.46log.com",
            ),
        ):
            client = module.AgentPlatformGeminiClient()
            with self.assertRaises(RuntimeError) as raised:
                await client.aio.models.generate_content(
                    model="gemini-2.5-pro",
                    contents=["hello"],
                    config=genai.types.GenerateContentConfig(),
                )

        self.assertIn("proxy auth failed", str(raised.exception))

    def test_urllib_response_payload_parses_proxy_sse_text(self):
        module = self._agent_platform_module()
        response = module._UrlLibResponse(
            status_code=200,
            payload=None,
            text=': heartbeat\n\ndata: {"candidates":[{"content":{"parts":[{"text":"ok"}]}}]}\n\n',
        )

        payload = module._response_payload(response)

        self.assertEqual(
            payload["candidates"][0]["content"]["parts"][0]["text"],
            "ok",
        )

    def test_gemini_client_factory_uses_agent_platform_backend(self):
        module = self._agent_platform_module()
        sentinel_sdk_client = object()

        with patch.object(module.settings, "gemini_backend", "agent_platform"):
            self.assertIsInstance(
                module.gemini_client(), module.AgentPlatformGeminiClient
            )

        with (
            patch.object(module.settings, "gemini_backend", "google_genai"),
            patch.object(module.settings, "gemini_api_key", "sdk-key"),
            patch.object(module.genai, "Client", return_value=sentinel_sdk_client),
        ):
            self.assertIs(module.gemini_client(), sentinel_sdk_client)


if __name__ == "__main__":
    unittest.main()
