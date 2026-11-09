"""Thin client for Groq's OpenAI-compatible chat completions API.

Design notes:
- Stateless per call: results and errors are returned or raised, never stored on the client, so concurrent
  requests cannot overwrite each other's status.
- Transient failures (429, 5xx, timeouts) are retried with exponential backoff and honour Retry-After.
- JSON mode is requested for structured tasks and the reply is still validated by callers, because a model
  can return valid JSON that does not match the schema we asked for.
"""
import json
import logging
import re
import time
from dataclasses import dataclass

import httpx

log = logging.getLogger(__name__)
_RETRYABLE = {429, 500, 502, 503, 504}


class AIError(Exception):
    """Base class; `status_code` is the HTTP status the API layer should answer with."""
    status_code = 502


class AINotConfigured(AIError):
    status_code = 503


class AIRequestError(AIError):
    status_code = 502


@dataclass(frozen=True)
class ChatResult:
    text: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    finish_reason: str = "stop"


def extract_json(text: str):
    """Parse a JSON object or array from model output, tolerating code fences and surrounding prose."""
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.IGNORECASE)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    for opener, closer in (("{", "}"), ("[", "]")):
        start, end = cleaned.find(opener), cleaned.rfind(closer)
        if start != -1 and end > start:
            try:
                return json.loads(cleaned[start : end + 1])
            except json.JSONDecodeError:
                continue
    raise ValueError("No valid JSON found in model output")


class GroqClient:
    def __init__(self, *, api_key: str, model: str, fast_model: str, base_url: str, timeout: float,
                 max_retries: int = 2, transport: httpx.BaseTransport | None = None, sleep=time.sleep):
        self._api_key = api_key
        self.model = model
        self.fast_model = fast_model
        self._url = base_url.rstrip("/") + "/chat/completions"
        self._timeout = timeout
        self._max_retries = max_retries
        self._transport = transport
        self._sleep = sleep

    @property
    def configured(self) -> bool:
        return bool(self._api_key)

    def chat(self, messages: list[dict], *, fast: bool = False, max_tokens: int = 1024, temperature: float = 0.4,
             json_mode: bool = False, reasoning_effort: str = "low", timeout: float | None = None) -> ChatResult:
        if not self.configured:
            raise AINotConfigured("The AI service is not configured. Add GROQ_API_KEY to backend/.env and restart.")
        model = self.fast_model if fast else self.model
        payload: dict = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_completion_tokens": max_tokens,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        if model.startswith("openai/gpt-oss"):
            payload["reasoning_effort"] = reasoning_effort
        data = self._post(payload, timeout)
        try:
            choice = data["choices"][0]
            text = choice["message"]["content"] or ""
        except (KeyError, IndexError, TypeError):
            raise AIRequestError("Groq returned an unexpected response format.")
        if not text.strip():
            raise AIRequestError("Groq returned an empty response. Try again.")
        usage = data.get("usage") or {}
        return ChatResult(text.strip(), model, usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0),
                          choice.get("finish_reason") or "stop")

    def chat_json(self, messages: list[dict], *, fast: bool = False, max_tokens: int = 2048,
                  temperature: float = 0.2, reasoning_effort: str = "medium"):
        """Request a JSON reply. One repair attempt is made if the first reply cannot be parsed."""
        result = self.chat(messages, fast=fast, max_tokens=max_tokens, temperature=temperature,
                           json_mode=True, reasoning_effort=reasoning_effort)
        try:
            return extract_json(result.text)
        except ValueError:
            log.warning("Model returned unparseable JSON; retrying once")
        retry = self.chat(
            messages + [{"role": "assistant", "content": result.text[:1500]},
                        {"role": "user", "content": "That was not valid JSON. Reply again with only the JSON object."}],
            fast=fast, max_tokens=max_tokens, temperature=0.0, json_mode=True, reasoning_effort=reasoning_effort)
        try:
            return extract_json(retry.text)
        except ValueError:
            raise AIRequestError("The model did not return valid JSON. Please try again.")

    def _post(self, payload: dict, timeout: float | None = None) -> dict:
        headers = {"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"}
        last_error = "unknown error"
        for attempt in range(self._max_retries + 1):
            try:
                with httpx.Client(timeout=timeout or self._timeout, transport=self._transport) as client:
                    response = client.post(self._url, headers=headers, json=payload)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_error = f"network error ({type(exc).__name__})"
                response = None
            if response is not None:
                if response.status_code == 200:
                    return response.json()
                if response.status_code == 401:
                    raise AIRequestError("Groq rejected the API key. Check GROQ_API_KEY.")
                detail = _error_detail(response)
                if response.status_code == 404 and "model" in detail.lower():
                    raise AIRequestError(
                        f"Groq model '{payload['model']}' is not available to your account. Set GROQ_MODEL / GROQ_FAST_MODEL "
                        "in backend/.env to a current model (https://console.groq.com/docs/models) and restart.")
                last_error = f"HTTP {response.status_code}: {detail}"
                if response.status_code not in _RETRYABLE:
                    raise AIRequestError(f"Groq request failed ({last_error})")
            if attempt < self._max_retries:
                delay = min(2 ** attempt, 8)
                if response is not None and response.headers.get("retry-after", "").replace(".", "", 1).isdigit():
                    delay = min(float(response.headers["retry-after"]), 10)
                log.warning("Groq call failed (%s); retrying in %.1fs", last_error, delay)
                self._sleep(delay)
        raise AIRequestError(f"Groq is unavailable right now ({last_error}). Please try again shortly.")


def _error_detail(response: httpx.Response) -> str:
    try:
        return str(response.json().get("error", {}).get("message", ""))[:200]
    except Exception:
        return response.text[:200]
