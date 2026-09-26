"""Small chat boundary for the Phase 0 OpenAI-compatible llama.cpp server."""

import requests


class IntelligenceError(RuntimeError):
    """The model endpoint is unavailable or returned an unusable response."""


class IntelligenceClient:
    def __init__(self, base_url: str, model: str | None = None, timeout: int = 300):
        self.base_url = base_url.rstrip("/")
        self.configured_model = model or None
        self.timeout = timeout
        if not self.base_url.startswith(("http://", "https://")):
            raise ValueError("INTELLIGENCE_BASE_URL must be an HTTP(S) URL")

    def _request(self, method: str, path: str, **kwargs):
        try:
            response = requests.request(
                method,
                f"{self.base_url}{path}",
                timeout=10 if method == "GET" else self.timeout,
                **kwargs,
            )
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as exc:
            raise IntelligenceError(f"Model endpoint request failed: {exc}") from exc

    def resolve_model(self) -> str:
        payload = self._request("GET", "/v1/models")
        try:
            models = [item["id"] for item in payload["data"]]
            if not models or any(not isinstance(model, str) or not model for model in models):
                raise ValueError("empty or invalid model list")
        except (KeyError, TypeError, ValueError) as exc:
            raise IntelligenceError("Invalid response from /v1/models") from exc

        if self.configured_model:
            if self.configured_model not in models:
                raise IntelligenceError(
                    f"Configured model {self.configured_model!r} is absent from /v1/models"
                )
            return self.configured_model
        if len(models) != 1:
            raise IntelligenceError("Set INTELLIGENCE_MODEL when /v1/models lists multiple models")
        return models[0]

    def chat(self, model: str, messages: list[dict]) -> str:
        payload = self._request(
            "POST",
            "/v1/chat/completions",
            json={"model": model, "messages": messages, "stream": False},
        )
        try:
            content = payload["choices"][0]["message"]["content"]
            if not isinstance(content, str) or not content.strip():
                raise ValueError("empty assistant content")
            return content
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise IntelligenceError("Invalid chat completion response") from exc
