from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Load .env files into os.environ so direct os.getenv() users (LLMClient)
# see the same values under `uvicorn` as under docker-compose (which injects
# them itself). Backend-local .env wins over project-root .env.
try:
    from dotenv import load_dotenv

    _APP = Path(__file__).resolve().parent
    load_dotenv(_APP.parent / ".env")  # backend/.env
    load_dotenv(_APP.parent.parent / ".env")  # project-root .env
except ImportError:
    pass


class Settings(BaseSettings):
    """Application configuration. Values come from environment variables
    (or a local `.env` file). All fields have safe defaults so the app can
    start without any keys configured; LLM calls fail later with a clear
    message telling the user which key to set."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_debug: bool = True

    # LLM
    llm_provider: str = "anthropic"
    llm_model: str = "claude-sonnet-4-5"
    llm_temperature: float = 0.2
    llm_max_tokens: int = 4096
    anthropic_api_key: str = ""
    gemini_api_key: str = ""

    # Embeddings
    embedding_provider: str = "local"
    local_embedding_model: str = "all-MiniLM-L6-v2"

    # Vector store
    chroma_persist_dir: str = "./chroma_db"

    # CORS
    cors_origins: str = (
        "http://localhost:3000,http://127.0.0.1:3000,"
        "http://localhost:5173,http://127.0.0.1:5173"
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
