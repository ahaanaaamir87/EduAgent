"""
Agent layer for EduAgent.
Supports both Ollama (local) and Google ADK (Gemini).
"""

from __future__ import annotations

from typing import List, Optional

try:
    import ollama
except ImportError:
    ollama = None

from app.config import settings

_ollama_client = (
    ollama.Client(host=settings.OLLAMA_HOST)
    if ollama is not None
    else None
)


class BaseAgent:
    """Common interface."""

    name = "EduAgent"

    def run(
        self,
        system_prompt: str,
        user_prompt: str,
        history: Optional[List[dict]] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        raise NotImplementedError


class LocalOllamaAgent(BaseAgent):
    """Runs using a local Ollama model."""

    name = "EduAgent (Ollama)"

    def __init__(self, model: str | None = None):
        if ollama is None:
            raise RuntimeError(
                "Ollama package is not installed."
            )

        self.model = model or settings.OLLAMA_CHAT_MODEL

    def run(
        self,
        system_prompt: str,
        user_prompt: str,
        history: Optional[List[dict]] = None,
        max_tokens: Optional[int] = None,
    ) -> str:

        messages = [
            {
                "role": "system",
                "content": system_prompt,
            }
        ]

        for turn in history or []:
            messages.append(
                {
                    "role": turn["role"],
                    "content": turn["content"],
                }
            )

        messages.append(
            {
                "role": "user",
                "content": user_prompt,
            }
        )

        response = _ollama_client.chat(
            model=self.model,
            messages=messages,
            options={
                "num_predict": max_tokens
                or settings.OLLAMA_MAX_TOKENS,
                "num_ctx": settings.OLLAMA_NUM_CTX,
            },
        )

        return response["message"]["content"]


class GeminiAgent(BaseAgent):
    """Runs using Gemini directly via google-generativeai (no google-adk dependency)."""

    name = "EduAgent (Gemini)"

    def __init__(self, model: str = "gemini-1.5-flash"):
        try:
            import google.generativeai as genai
        except ImportError as e:
            raise RuntimeError(
                "google-generativeai is not installed."
            ) from e

        import os
        api_key = os.getenv("GOOGLE_API_KEY", "")
        if not api_key:
            raise RuntimeError("GOOGLE_API_KEY is not set in environment variables.")

        genai.configure(api_key=api_key)
        self._genai = genai
        self.model = model

    def run(
        self,
        system_prompt: str,
        user_prompt: str,
        history: Optional[List[dict]] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        model = self._genai.GenerativeModel(
            model_name=self.model,
            system_instruction=system_prompt,
        )

        chat_history = []
        for turn in history or []:
            role = "user" if turn["role"] == "user" else "model"
            chat_history.append({"role": role, "parts": [turn["content"]]})

        chat = model.start_chat(history=chat_history)
        response = chat.send_message(
            user_prompt,
            generation_config={"max_output_tokens": max_tokens or 1024},
        )
        return response.text


_agent_instance: Optional[BaseAgent] = None


def get_agent() -> BaseAgent:
    global _agent_instance

    if _agent_instance is not None:
        return _agent_instance

    if settings.AGENT_BACKEND.lower() == "adk":
        _agent_instance = GeminiAgent()
    else:
        _agent_instance = LocalOllamaAgent()

    return _agent_instance