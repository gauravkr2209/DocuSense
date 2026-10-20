"""Model providers for DocuSense.

Gemini (default) runs on Google's servers with a free-tier API key.
Ollama runs on this computer. The rest of the code only calls the functions
in this file, so switching provider or model is a configuration change.
"""
import os
import re
from typing import Callable, List, Optional, Tuple

import config

KEY_ENV = "GOOGLE_API_KEY"
_QUOTA = re.compile(r"\b429\b|RESOURCE_EXHAUSTED|quota", re.IGNORECASE)

# Gemini 3 models spend hidden "thinking" tokens from the same output budget
# as the answer. A small budget cuts long answers short, so Gemini gets a
# generous floor.
GEMINI_MIN_OUTPUT_TOKENS = 8192


class ProviderError(Exception):
    """Raised when the chosen model provider cannot be used."""


def is_local() -> bool:
    return config.PROVIDER == "ollama"


def provider_label() -> str:
    return "Ollama (local)" if is_local() else "Gemini (cloud)"


def gemini_key() -> Optional[str]:
    """The key from the environment, or None. It is never printed."""
    return os.environ.get(KEY_ENV, "").strip() or None


def provider_ready() -> bool:
    """True when the active provider has what it needs to start."""
    return is_local() or gemini_key() is not None


def missing_key_message() -> str:
    return (
        f"No Gemini API key is set. Add {KEY_ENV} to .streamlit/secrets.toml "
        "or to your environment variables."
    )


def _require_key() -> str:
    key = gemini_key()
    if key is None:
        raise ProviderError(missing_key_message())
    return key


def explain_error(exc: Exception, action: str) -> str:
    """A readable message for a failed model call. Never shows a key."""
    text = str(exc)
    if _QUOTA.search(text):
        return (
            "The free Gemini usage limit has been reached for now. "
            "Wait a minute and try again, or check the rate-limit page."
        )
    if "UNAVAILABLE" in text or "503" in text or "high demand" in text.lower():
        return (
            "Google's servers are busy right now. Please try again in a minute."
        )
    if is_local():
        return f"{action} Is Ollama running and is the model pulled? Details: {text}"
    return f"{action} Details: {text}"


def get_embeddings():
    """Embedding model for the active provider."""
    if is_local():
        from langchain_ollama import OllamaEmbeddings

        return OllamaEmbeddings(
            model=config.OLLAMA_EMBEDDING_MODEL,
            base_url=config.OLLAMA_BASE_URL,
        )
    from langchain_google_genai import GoogleGenerativeAIEmbeddings

    return GoogleGenerativeAIEmbeddings(
        model=f"models/{config.GEMINI_EMBEDDING_MODEL}",
        google_api_key=_require_key(),
    )


class ModelChain:
    """Tries chat models in order. If one fails (busy, over quota, not
    available), the next one answers. last_model holds the name of the
    model that gave the most recent answer, so the interface can show it."""

    def __init__(self, candidates: List[Tuple[str, Callable[[], object]]]):
        self._candidates = candidates
        self.last_model = ""

    def invoke(self, messages):
        errors: List[str] = []
        for name, build in self._candidates:
            try:
                reply = build().invoke(messages)
            except ProviderError:
                raise
            except Exception as exc:
                errors.append(f"{name}: {exc}")
                continue
            self.last_model = name
            return reply
        last = errors[-1] if errors else "no chat models are configured"
        raise ProviderError(explain_error(RuntimeError(last), "The chat model failed."))


def get_chat_model(max_output_tokens=None, num_ctx=None):
    """Chat model for the active provider. For Gemini this is a ModelChain
    over the configured models. Models are only built when they are needed."""
    if is_local():
        from langchain_ollama import ChatOllama

        def build_local():
            return ChatOllama(
                model=config.OLLAMA_CHAT_MODEL,
                base_url=config.OLLAMA_BASE_URL,
                temperature=0,
                num_ctx=num_ctx,
                num_predict=max_output_tokens,
            )

        return ModelChain([(config.OLLAMA_CHAT_MODEL, build_local)])

    from langchain_google_genai import ChatGoogleGenerativeAI

    key = _require_key()
    budget = max(max_output_tokens or 0, GEMINI_MIN_OUTPUT_TOKENS)

    def make(name: str) -> Callable[[], object]:
        def build():
            return ChatGoogleGenerativeAI(
                model=name,
                google_api_key=key,
                temperature=0,
                max_output_tokens=budget,
                max_retries=2,
            )

        return build

    return ModelChain([(name, make(name)) for name in config.GEMINI_CHAT_MODELS])


def text_of(reply) -> str:
    """The plain text of a model reply, whatever its shape."""
    content = getattr(reply, "content", reply)
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                parts.append(part.get("text", ""))
            elif isinstance(part, str):
                parts.append(part)
        return "".join(parts).strip()
    return str(content).strip()