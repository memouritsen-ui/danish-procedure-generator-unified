from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PROCEDUREWRITER_", extra="ignore")

    repo_root: Path = Field(default_factory=_default_repo_root)
    data_dir: Path | None = None
    config_dir: Path | None = None

    dummy_mode: bool = False

    use_llm: bool = True
    llm_model: str = "gpt-4o-mini"

    openai_embeddings_model: str = "text-embedding-3-small"

    ncbi_email: str | None = None
    ncbi_tool: str = "danish-procedure-generator"
    ncbi_api_key: str | None = None

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
