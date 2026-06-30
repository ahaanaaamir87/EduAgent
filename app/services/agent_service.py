"""
Agent layer for EduAgent.

This module defines a small Agent/Tool abstraction modeled after Google's
Agent Development Kit (ADK) concepts -- an Agent has a name, instructions,
and a model, and is invoked with a prompt to produce a response. Two
backends implement this interface:

  - LocalOllamaAgent  (default, AGENT_BACKEND=local): runs entirely on your
    local machine using the `ollama` Python client against a model you've
    pulled (e.g. `ollama pull llama3`). No internet / API key required.

  - GoogleADKAgent (AGENT_BACKEND=adk): a thin wrapper around the real
    `google-adk` package + Gemini, for when you want to swap to Google's
    cloud-hosted models. Requires GOOGLE_API_KEY. Only imported if selected,
    so the app runs fine without google-adk installed/configured.

Everything else in the app (routers) talks to `get_agent()` and never
needs to know which backend is active.
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
    """Common interface every backend implements."""

    name: str = "EduAgent"

    def run(self, system_prompt: str, user_prompt: str, history: Optional[List[dict]] = None,
            max_tokens: Optional[int] = None) -> str:
        raise NotImplementedError


class LocalOllamaAgent(BaseAgent):
    """
    Default agent backend: a local LLM served by Ollama.
    Mirrors the ADK "Agent.run()" call signature so it's a drop-in
    replacement for the Google ADK backend below.
    """

    name = "EduAgent (Ollama local)"

    def __init__(self, model: str = None):
    if ollama is None:
        raise RuntimeError(
            "Ollama is not installed. Install the ollama package or use AGENT_BACKEND=adk."
        )

    self.model = model or settings.OLLAMA_CHAT_MODEL

    def run(self, system_prompt: str, user_prompt: str, history: Optional[List[dict]] = None,
            max_tokens: Optional[int] = None) -> str:
        messages = [{"role": "system", "content": system_prompt}]
        for turn in (history or []):
            messages.append({"role": turn["role"], "content": turn["content"]})
        messages.append({"role": "user", "content": user_prompt})

        response = _ollama_client.chat(
            model=self.model,
            messages=messages,
            options={
                # Caps how many tokens the model will generate. This is the
                # single biggest lever for response time on CPU-only machines
                # -- an uncapped model can ramble on for a very long time.
                "num_predict": max_tokens or settings.OLLAMA_MAX_TOKENS,
                # Smaller context window = less to process per token on CPU.
                "num_ctx": settings.OLLAMA_NUM_CTX,
            },
        )
        return response["message"]["content"]


class GoogleADKAgent(BaseAgent):
    """
    Optional backend using the real Google Agent Development Kit + Gemini.
    Only constructed if AGENT_BACKEND=adk and google-adk is installed with
    a valid GOOGLE_API_KEY. See README for setup.
    """

    name = "EduAgent (Google ADK / Gemini)"

    def __init__(self, model: str = "gemini-1.5-flash"):
        try:
            from google.adk.agents import Agent
            from google.adk.runners import InMemoryRunner
        except ImportError as e:
            raise RuntimeError(
                "google-adk is not installed. Run `pip install google-adk` "
                "and set GOOGLE_API_KEY, or set AGENT_BACKEND=local to use Ollama instead."
            ) from e

        self._Agent = Agent
        self._Runner = InMemoryRunner
        self.model = model

    def run(self, system_prompt: str, user_prompt: str, history: Optional[List[dict]] = None,
            max_tokens: Optional[int] = None) -> str:
        agent = self._Agent(
            name="eduagent",
            model=self.model,
            instruction=system_prompt,
        )
        runner = self._Runner(agent=agent)
        # NOTE: Real ADK session/run wiring depends on the installed SDK version.
        # This is intentionally a minimal example -- see Google ADK docs for
        # full streaming/session APIs: https://google.github.io/adk-docs/
        result = runner.run(user_prompt)
        return str(result)


_agent_instance: Optional[BaseAgent] = None


def get_agent() -> BaseAgent:
    """Returns the singleton agent for the configured backend."""
    global _agent_instance
    if _agent_instance is not None:
        return _agent_instance

    if settings.AGENT_BACKEND == "adk":
        _agent_instance = GoogleADKAgent()
    else:
        _agent_instance = LocalOllamaAgent()
    return _agent_instance
