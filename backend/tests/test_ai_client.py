import json

import httpx
import pytest

from app.ai.groq_client import AINotConfigured, AIRequestError, GroqClient


def _client(handler, key="k", retries=2):
    return GroqClient(api_key=key, model="openai/gpt-oss-120b", fast_model="other/fast-model", base_url="https://api.test/v1",
                      timeout=5, max_retries=retries, transport=httpx.MockTransport(handler), sleep=lambda _s: None)


def _ok(text):
    return httpx.Response(200, json={"choices": [{"message": {"content": text}}], "usage": {"prompt_tokens": 3, "completion_tokens": 4}})


def test_missing_key_raises_a_helpful_error():
    with pytest.raises(AINotConfigured):
        _client(lambda r: _ok("x"), key="").chat([{"role": "user", "content": "hi"}])


def test_rate_limits_are_retried_then_succeed():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(429, headers={"retry-after": "1"}, json={"error": {"message": "slow down"}}) if len(calls) < 3 else _ok("done")

    assert _client(handler).chat([{"role": "user", "content": "hi"}]).text == "done" and len(calls) == 3


def test_persistent_failures_raise_after_the_retry_budget():
    with pytest.raises(AIRequestError):
        _client(lambda r: httpx.Response(503, json={"error": {"message": "down"}}), retries=1).chat([{"role": "user", "content": "hi"}])


def test_bad_key_is_not_retried():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(401, json={"error": {"message": "invalid"}})

    with pytest.raises(AIRequestError, match="API key"):
        _client(handler).chat([{"role": "user", "content": "hi"}])
    assert len(calls) == 1


def test_request_shape_for_json_mode_on_gpt_oss():
    seen = {}

    def handler(request):
        seen.update(json.loads(request.content), auth=request.headers["authorization"])
        return _ok('{"a": 1}')

    assert _client(handler).chat_json([{"role": "user", "content": "return JSON"}]) == {"a": 1}
    assert seen["response_format"] == {"type": "json_object"} and seen["reasoning_effort"] == "medium" and seen["auth"] == "Bearer k"
    assert "max_completion_tokens" in seen


def test_fast_model_does_not_send_gpt_oss_only_parameters():
    seen = {}

    def handler(request):
        seen.update(json.loads(request.content))
        return _ok("hello")

    _client(handler).chat([{"role": "user", "content": "hi"}], fast=True)
    assert seen["model"] == "other/fast-model" and "reasoning_effort" not in seen


def test_invalid_json_is_repaired_with_one_retry():
    replies = iter(["not json at all", '{"ok": true}'])
    assert _client(lambda r: _ok(next(replies))).chat_json([{"role": "user", "content": "JSON please"}]) == {"ok": True}


def test_invalid_json_twice_raises():
    with pytest.raises(AIRequestError):
        _client(lambda r: _ok("still not json")).chat_json([{"role": "user", "content": "JSON please"}])


def test_unknown_model_gives_an_actionable_message():
    handler = lambda r: httpx.Response(404, json={"error": {"message": "The model `old-model` does not exist or you do not have access to it."}})
    with pytest.raises(AIRequestError, match="GROQ_FAST_MODEL"):
        _client(handler).chat([{"role": "user", "content": "hi"}], fast=True)
