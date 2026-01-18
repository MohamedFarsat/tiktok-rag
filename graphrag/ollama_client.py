from __future__ import annotations

import json
import socket
from typing import Dict, List, Optional
from urllib import error, request

DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"
DEFAULT_LLM_MODEL = "llama3.2:3b-instruct"
FALLBACK_LLM_MODEL = "qwen2.5:3b-instruct"


class OllamaError(RuntimeError):
    pass


class ModelNotFoundError(OllamaError):
    pass


class OllamaClient:
    def __init__(self, base_url: str = DEFAULT_OLLAMA_URL, timeout: float = 20.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def generate(
        self,
        model: str,
        prompt: str,
        temperature: float = 0.2,
        short_prompt: Optional[str] = None,
    ) -> str:
        try:
            return self._post_generate(model, prompt, temperature)
        except TimeoutError:
            if short_prompt:
                return self._post_generate(model, short_prompt, temperature)
            raise

    def list_models(self, timeout: float = 2.0) -> List[str]:
        req = request.Request(f"{self.base_url}/api/tags", method="GET")
        try:
            with request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:  # pragma: no cover - transport errors
            raise OllamaError(f"Failed to reach Ollama: {exc}") from exc
        models = data.get("models") or []
        names: List[str] = []
        for item in models:
            name = item.get("name")
            if name:
                names.append(str(name))
        return names

    def _post_generate(self, model: str, prompt: str, temperature: float) -> str:
        body = json.dumps(
            {
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": temperature},
            }
        ).encode("utf-8")
        req = request.Request(
            f"{self.base_url}/api/generate",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=self.timeout) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except error.HTTPError as exc:
            raw = exc.read().decode("utf-8") if exc.fp else ""
            message = raw or str(exc)
            lowered = message.lower()
            if "model" in lowered and "not found" in lowered:
                raise ModelNotFoundError(message) from exc
            raise OllamaError(message) from exc
        except error.URLError as exc:
            if _is_timeout(exc):
                raise TimeoutError("Ollama request timed out.") from exc
            raise OllamaError(f"Failed to reach Ollama: {exc}") from exc
        except socket.timeout as exc:
            raise TimeoutError("Ollama request timed out.") from exc
        except json.JSONDecodeError as exc:
            raise OllamaError("Invalid response from Ollama.") from exc
        response_text = payload.get("response")
        if not isinstance(response_text, str):
            raise OllamaError("Missing response text from Ollama.")
        return response_text.strip()


def _is_timeout(exc: error.URLError) -> bool:
    reason = getattr(exc, "reason", None)
    if isinstance(reason, socket.timeout):
        return True
    if isinstance(exc, TimeoutError):
        return True
    message = str(reason or exc).lower()
    return "timed out" in message or "timeout" in message
