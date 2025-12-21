"""Configuration management router."""

from fastapi import APIRouter

from procedurewriter import config_store
from procedurewriter.schemas import ConfigText
from procedurewriter.settings import settings

router = APIRouter(prefix="/api/config", tags=["config"])


@router.get("/author_guide", response_model=ConfigText)
def api_get_author_guide() -> ConfigText:
    """Get author guide configuration."""
    return ConfigText(text=config_store.read_text(settings.author_guide_path))


@router.put("/author_guide", response_model=ConfigText)
def api_set_author_guide(cfg: ConfigText) -> ConfigText:
    """Update author guide configuration."""
    config_store.write_text_validated_yaml(settings.author_guide_path, cfg.text)
    return cfg


@router.get("/source_allowlist", response_model=ConfigText)
def api_get_allowlist() -> ConfigText:
    """Get source allowlist configuration."""
    return ConfigText(text=config_store.read_text(settings.allowlist_path))


@router.put("/source_allowlist", response_model=ConfigText)
def api_set_allowlist(cfg: ConfigText) -> ConfigText:
    """Update source allowlist configuration."""
    config_store.write_text_validated_yaml(settings.allowlist_path, cfg.text)
    return cfg


@router.get("/docx_template", response_model=ConfigText)
def api_get_docx_template() -> ConfigText:
    """Get the DOCX template configuration."""
    return ConfigText(text=config_store.read_text(settings.docx_template_path))


@router.put("/docx_template", response_model=ConfigText)
def api_set_docx_template(cfg: ConfigText) -> ConfigText:
    """Update the DOCX template configuration."""
    config_store.write_text_validated_yaml(settings.docx_template_path, cfg.text)
    return cfg
