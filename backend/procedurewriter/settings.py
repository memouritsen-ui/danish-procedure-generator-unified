from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


class LLMProviderEnum(str, Enum):
    """Supported LLM providers."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OLLAMA = "ollama"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PROCEDUREWRITER_", extra="ignore")

    repo_root: Path = Field(default_factory=_default_repo_root)
    data_dir: Path | None = None
    config_dir: Path | None = None

    dummy_mode: bool = False

    # LLM Provider Configuration
    llm_provider: LLMProviderEnum = LLMProviderEnum.OPENAI
    use_llm: bool = True
    llm_model: str = "gpt-4o-mini"

    # Provider-specific settings (read from env without prefix)
    # These are typically set as OPENAI_API_KEY, ANTHROPIC_API_KEY, etc.

    # OpenAI settings
    openai_embeddings_model: str = "text-embedding-3-small"

    # Ollama settings
    ollama_base_url: str = "http://localhost:11434"

    # NCBI/PubMed settings
    ncbi_email: str | None = None
    ncbi_tool: str = "danish-procedure-generator"
    ncbi_api_key: str | None = None

    def get_default_model_for_provider(self) -> str:
        """Get the default model name for the configured provider."""
        defaults = {
            LLMProviderEnum.OPENAI: "gpt-4o-mini",
            LLMProviderEnum.ANTHROPIC: "claude-3-5-sonnet-20241022",
            LLMProviderEnum.OLLAMA: "llama3.1",
        }
        return defaults.get(self.llm_provider, "gpt-4o-mini")

    @property
    def resolved_data_dir(self) -> Path:
        return self.data_dir or (self.repo_root / "data")

    @property
    def resolved_config_dir(self) -> Path:
        return self.config_dir or (self.repo_root / "config")

    @property
    def db_path(self) -> Path:
        return self.resolved_data_dir / "index" / "runs.sqlite3"

    @property
    def runs_dir(self) -> Path:
        return self.resolved_data_dir / "runs"

    @property
    def cache_dir(self) -> Path:
        return self.resolved_data_dir / "cache"

    @property
    def uploads_dir(self) -> Path:
        return self.resolved_data_dir / "uploads"

    @property
    def author_guide_path(self) -> Path:
        return self.resolved_config_dir / "author_guide.yaml"

    @property
    def allowlist_path(self) -> Path:
        return self.resolved_config_dir / "source_allowlist.yaml"

    @property
    def evidence_hierarchy_path(self) -> Path:
        return self.resolved_config_dir / "evidence_hierarchy.yaml"
