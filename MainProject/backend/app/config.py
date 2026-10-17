"""Application settings, loaded from environment variables / .env.

Secrets (LLM API keys, JWT secret) only ever live here on the server.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "AI Interview Simulator"
    # PostgreSQL in production, e.g. postgresql+psycopg2://user:pass@localhost:5432/interviews
    # SQLite is the zero-setup default for local development and tests.
    database_url: str = "sqlite:///./interview_sim.db"

    jwt_secret: str = "change-me-in-production-please-use-a-long-random-string"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24

    # LLM provider: "anthropic", "openai" (any OpenAI-compatible endpoint) or "demo".
    # If the chosen provider has no API key, the app runs in clearly-labelled demo mode.
    llm_provider: str = "anthropic"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-5-5"
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"
    llm_timeout_seconds: float = 45.0

    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Interview guard rails
    max_followups_per_topic: int = 2
    max_questions_hard_cap: int = 30
    grace_seconds: int = 60  # small allowance after the timer before the server closes a session

    @property
    def demo_mode(self) -> bool:
        p = self.llm_provider.lower()
        if p == "anthropic":
            return not self.anthropic_api_key
        if p == "openai":
            return not self.openai_api_key
        return True


@lru_cache
def get_settings() -> Settings:
    return Settings()
