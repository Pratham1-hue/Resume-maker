"""Shared dependency factories.

All heavy third-party imports happen inside the factory functions so that
importing this module (and therefore starting the app) never fails when an
optional dependency is missing. Errors surface only when the corresponding
feature is actually used, with a clear message.
"""

from app.core.logging import get_logger

logger = get_logger(__name__)


def get_chroma_client(persist_dir: str = "./chroma_db"):
    """Get or create a ChromaDB client instance."""
    try:
        import chromadb
    except ImportError as exc:
        raise ImportError(
            "chromadb is not installed. Run `pip install chromadb` "
            "or reinstall the project with `pip install -e .`."
        ) from exc
    # NOTE: chromadb>=1.x PersistentClient takes only `path`.
    # Older `Settings(allow_reset=..., is_persistent=...)` kwargs were removed.
    client = chromadb.PersistentClient(path=persist_dir)
    logger.info(f"ChromaDB client initialized at {persist_dir}")
    return client


def get_llm_client(provider: str = "anthropic"):
    """Get an LLM client instance based on the provider.

    Returns the project's own provider-agnostic client (see app.llm.client)
    so callers get a uniform `.call(system_prompt, user_prompt)` interface.
    """
    from app.llm.client import LLMClient

    return LLMClient(provider=provider)


def get_http_client():
    """Get an async HTTP client for scraping."""
    import httpx
    return httpx.AsyncClient(timeout=60.0)
