from __future__ import annotations

import os
from typing import Any, Dict, Optional

import httpx


class LLMError(RuntimeError):
    """Raised when an LLM call cannot be completed."""


class LLMClient:
    """Provider-agnostic LLM client (Anthropic / Gemini).

    Reads configuration from constructor args first, then environment:
    LLM_PROVIDER, LLM_MODEL, ANTHROPIC_API_KEY, GEMINI_API_KEY.
    The 'ollama' provider needs no key and talks to a local Ollama server
    (OLLAMA_BASE_URL, default http://localhost:11434).
    Missing credentials raise a clear error only when a call is attempted,
    never at import or startup time.
    """

    def __init__(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 4096,
    ):
        self.provider = (provider or os.getenv("LLM_PROVIDER", "anthropic")).lower()
        # Provider-aware default: an unset LLM_MODEL must not leak a Claude ID
        # into Gemini calls (or vice versa).
        _defaults = {
            "anthropic": "claude-sonnet-4-5",
            "gemini": "gemini-3.8-flash",
            "ollama": os.getenv("OLLAMA_MODEL", "llama3.1:8b"),
        }
        raw_model = model or os.getenv("LLM_MODEL") or _defaults[self.provider]
        self.model = self._clean_model_name(raw_model)
        self.temperature = temperature
        self.max_tokens = max_tokens
        # Local CPU inference is slow (minutes for long prompts); give it room.
        _timeout = 600.0 if self.provider == "ollama" else 120.0
        self._http = httpx.AsyncClient(timeout=_timeout)

        if self.provider == "anthropic":
            self._api_key = os.getenv("ANTHROPIC_API_KEY", "")
            self._endpoint = "https://api.anthropic.com/v1/messages"
        elif self.provider == "gemini":
            self._api_key = os.getenv("GEMINI_API_KEY", "")
            self._endpoint = (
                f"https://generativelanguage.googleapis.com/v1beta/models/"
                f"{self.model}:generateContent"
            )
        elif self.provider == "ollama":
            self._api_key = ""
            base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
            self._endpoint = f"{base}/api/generate"
        else:
            raise ValueError(
                f"Unsupported LLM provider: {provider!r}. Use 'anthropic', 'gemini' or 'ollama'."
            )

    @staticmethod
    def _clean_model_name(raw: str) -> str:
        """Normalize a model ID from env/config.

        Strips whitespace/CR characters (common with Windows-edited .env
        files) and a leading `models/` resource prefix, which the Gemini
        endpoint rejects as an unexpected name format.
        """
        name = (raw or "").strip().strip("'\"")
        if name.startswith("models/"):
            name = name[len("models/"):]
        return name.strip().rstrip("/")

    def _require_key(self):
        if self.provider == "ollama":
            return  # local server, no key needed
        if not self._api_key:
            name = "ANTHROPIC_API_KEY" if self.provider == "anthropic" else "GEMINI_API_KEY"
            raise LLMError(
                f"{name} is not set. Copy .env.example to .env and add your key, "
                f"or set LLM_PROVIDER to the other provider."
            )

    async def call(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Make an LLM call and return the raw text response."""
        self._require_key()
        temp = temperature if temperature is not None else self.temperature
        max_tok = max_tokens if max_tokens is not None else self.max_tokens

        try:
            if self.provider == "anthropic":
                return await self._call_anthropic(system_prompt, user_prompt, temp, max_tok)
            if self.provider == "gemini":
                return await self._call_gemini(system_prompt, user_prompt, temp, max_tok)
            return await self._call_ollama(system_prompt, user_prompt, temp, max_tok)
        except LLMError:
            raise
        except Exception as exc:
            raise LLMError(f"{self.provider} request failed: {exc}") from exc

    async def _call_anthropic(self, system_prompt: str, user_prompt: str, temp: float, max_tok: int) -> str:
        try:
            resp = await self._http.post(
                self._endpoint,
                headers={
                    "x-api-key": self._api_key,
                    "Content-Type": "application/json",
                    "Anthropic-Version": "2023-06-01",
                },
                json={
                    "model": self.model,
                    "temperature": temp,
                    "max_tokens": max_tok,
                    "system": system_prompt,
                    "messages": [{"role": "user", "content": user_prompt}],
                },
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            # Surface the provider's own error body (it names the bad field,
            # e.g. an unknown model id) instead of a bare status code.
            body = (exc.response.text or "")[:500]
            raise LLMError(
                f"anthropic request failed (HTTP {exc.response.status_code}): {body}"
            ) from exc
        data = resp.json()
        content = data.get("content", [])
        if isinstance(content, list):
            texts = [b.get("text", "") for b in content if isinstance(b, dict) and b.get("type", "text") == "text"]
            if texts:
                return "".join(texts)
        return str(data)

    async def _call_gemini(self, system_prompt: str, user_prompt: str, temp: float, max_tok: int) -> str:
        try:
            resp = await self._http.post(
                f"{self._endpoint}?key={self._api_key}",
                json={
                    "system_instruction": {"parts": [{"text": system_prompt}]},
                    "contents": [{"parts": [{"text": user_prompt}]}],
                    "generationConfig": {
                        "temperature": temp,
                        "maxOutputTokens": max_tok,
                    },
                },
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            body = (exc.response.text or "")[:500]
            raise LLMError(
                f"gemini request failed (HTTP {exc.response.status_code}): {body}"
            ) from exc
        data = resp.json()
        try:
            parts = data["candidates"][0]["content"]["parts"]
            texts = [p.get("text", "") for p in parts if isinstance(p, dict)]
            if texts:
                return "".join(texts)
        except (KeyError, IndexError, TypeError):
            pass
        return str(data)

    async def _call_ollama(self, system_prompt: str, user_prompt: str, temp: float, max_tok: int) -> str:
        prompt = f"{system_prompt}\n\n{user_prompt}" if system_prompt else user_prompt
        try:
            resp = await self._http.post(
                self._endpoint,
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": temp, "num_predict": max_tok},
                },
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            body = (exc.response.text or "")[:500]
            raise LLMError(
                f"ollama request failed (HTTP {exc.response.status_code}): {body}. "
                f"Is Ollama running with model '{self.model}' pulled? (ollama pull {self.model})"
            ) from exc
        except httpx.ConnectError as exc:
            raise LLMError(
                f"Cannot reach Ollama at {self._endpoint}. Start it with `ollama serve` "
                f"(Docker: point OLLAMA_BASE_URL at http://host.docker.internal:11434)."
            ) from exc
        data = resp.json()
        text = data.get("response", "")
        if not text:
            raise LLMError(f"Ollama returned no text: {str(data)[:300]}")
        return text

    async def close(self):
        """Close the HTTP client."""
        await self._http.aclose()
