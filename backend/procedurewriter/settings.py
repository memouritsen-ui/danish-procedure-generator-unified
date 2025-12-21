from __future__ import annotations

from enum import Enum
from pathlib import Path

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

    # Evidence verification (uses Anthropic Haiku)
    enable_evidence_verification: bool = True

    # Evidence source requirements
    require_international_sources: bool = True
    require_danish_guidelines: bool = True
    missing_tier_policy: str = "allow_with_ack"

    # Job queue settings (SQLite-backed)
    queue_poll_interval_s: float = 0.5
    queue_heartbeat_interval_s: float = 30.0
    queue_stale_timeout_s: int = 1800
    queue_max_attempts: int = 3
    queue_max_concurrency: int = 2
    queue_start_worker_on_startup: bool = True

    # LLM Provider Configuration
    llm_provider: LLMProviderEnum = LLMProviderEnum.OPENAI
    use_llm: bool = True
    llm_model: str = "gpt-5.2"  # Upgraded from gpt-4o-mini for better style processing

    # Quality loop configuration
    quality_loop_max_iterations: int = 3
    quality_loop_quality_threshold: int = 8
    quality_loop_policy: str = "auto"
    quality_loop_max_cost_usd: float = 2.0

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

    # NICE/Cochrane API settings (institutional access)
    nice_api_key: str | None = None
    cochrane_api_key: str | None = None
    nice_api_base_url: str = "https://api.nice.org.uk"
    cochrane_api_base_url: str = "https://api.onlinelibrary.wiley.com"
    allow_html_fallback_international: bool = False

    # Wiley TDM (full-text PDF) settings
    enable_wiley_tdm: bool = False
    wiley_tdm_token: str | None = None
    wiley_tdm_base_url: str = "https://api.wiley.com/onlinelibrary/tdm/v1"
    wiley_tdm_max_downloads: int = 5
    wiley_tdm_allow_non_wiley_doi: bool = False
    wiley_tdm_use_client: bool = True

    def get_default_model_for_provider(self) -> str:
        """Get the default model name for the configured provider."""
        defaults = {
            LLMProviderEnum.OPENAI: "gpt-5.2",
            LLMProviderEnum.ANTHROPIC: "claude-opus-4-5-20251101",
            LLMProviderEnum.OLLAMA: "llama3.1",
        }
        return defaults.get(self.llm_provider, "gpt-5.2")

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

    @property
    def docx_template_path(self) -> Path:
        return self.resolved_config_dir / "docx_template.yaml"

    # Danish Guideline Library settings
    guideline_library_path: Path | None = None

    @property
    def resolved_guideline_library_path(self) -> Path:
        """Path to the guideline_harvester library root."""
        if self.guideline_library_path:
            return self.guideline_library_path
        return Path.home() / "guideline_harvester" / "library"


# Singleton instance - import this instead of creating Settings()
settings = Settings()
