"""Central configuration, loaded once from environment variables."""

from functools import lru_cache
import os

from pydantic import BaseModel, Field
from dotenv import load_dotenv


# Makes values edited in VS Code's .env file available to Uvicorn and Streamlit.
load_dotenv()


class Settings(BaseModel):
    database_url: str = Field(
        default_factory=lambda: os.getenv("DATABASE_URL", "duckdb:///data/text2sql.duckdb")
    )
    seed_demo_data: bool | None = Field(
        default_factory=lambda: (
            None
            if "SEED_DEMO_DATA" not in os.environ
            else os.environ["SEED_DEMO_DATA"].strip().lower() in {"1", "true", "yes"}
        )
    )
    openai_api_key: str | None = Field(default_factory=lambda: os.getenv("OPENAI_API_KEY") or None)
    openai_model: str = Field(default_factory=lambda: os.getenv("OPENAI_MODEL", "gpt-4o-mini"))
    llm_provider: str = Field(default_factory=lambda: os.getenv("LLM_PROVIDER", "offline").lower())
    ollama_base_url: str = Field(
        default_factory=lambda: os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
    )
    ollama_model: str = Field(default_factory=lambda: os.getenv("OLLAMA_MODEL", "llama3.2:3b"))
    max_rows: int = Field(default_factory=lambda: int(os.getenv("MAX_ROWS", "1000")))
    max_estimated_rows: int = Field(
        default_factory=lambda: int(os.getenv("MAX_ESTIMATED_ROWS", "100000"))
    )
    max_subquery_depth: int = Field(
        default_factory=lambda: int(os.getenv("MAX_SUBQUERY_DEPTH", "3"))
    )

    @property
    def should_seed_demo_data(self) -> bool:
        """Seed only local DuckDB by default; PostgreSQL is never seeded implicitly."""
        if self.seed_demo_data is not None:
            return self.seed_demo_data
        return self.database_url.startswith("duckdb")


@lru_cache
def get_settings() -> Settings:
    return Settings()
