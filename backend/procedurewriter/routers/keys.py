"""API key management router."""

import os

from fastapi import APIRouter

from procedurewriter.db import delete_secret, get_secret, mask_secret, set_secret
from procedurewriter.ncbi_status import check_ncbi_status
from procedurewriter.schemas import ApiKeyInfo, ApiKeySetRequest, ApiKeyStatus
from procedurewriter.settings import settings

router = APIRouter(prefix="/api/keys", tags=["keys"])

# Secret names
_OPENAI_SECRET_NAME = "openai_api_key"
_ANTHROPIC_SECRET_NAME = "anthropic_api_key"
_NCBI_SECRET_NAME = "ncbi_api_key"


def _effective_openai_api_key() -> str | None:
    """Get effective OpenAI API key from DB or environment."""
    return get_secret(settings.db_path, name=_OPENAI_SECRET_NAME) or os.getenv("OPENAI_API_KEY")


def _effective_ncbi_api_key() -> str | None:
    """Get effective NCBI API key from DB or settings."""
    return get_secret(settings.db_path, name=_NCBI_SECRET_NAME) or settings.ncbi_api_key


def _effective_anthropic_api_key() -> str | None:
    """Get effective Anthropic API key from DB or environment."""
    return get_secret(settings.db_path, name=_ANTHROPIC_SECRET_NAME) or os.getenv("ANTHROPIC_API_KEY")


# OpenAI key endpoints
@router.get("/openai", response_model=ApiKeyInfo)
def api_get_openai_key() -> ApiKeyInfo:
    """Get masked OpenAI API key."""
    key = _effective_openai_api_key()
    if not key:
        return ApiKeyInfo(present=False, masked=None)
    return ApiKeyInfo(present=True, masked=mask_secret(key))


@router.put("/openai", response_model=ApiKeyInfo)
def api_set_openai_key(req: ApiKeySetRequest) -> ApiKeyInfo:
    """Set OpenAI API key."""
    set_secret(settings.db_path, name=_OPENAI_SECRET_NAME, value=req.api_key.strip())
    return api_get_openai_key()


@router.delete("/openai", response_model=ApiKeyInfo)
def api_delete_openai_key() -> ApiKeyInfo:
    """Delete OpenAI API key."""
    delete_secret(settings.db_path, name=_OPENAI_SECRET_NAME)
    return api_get_openai_key()


@router.get("/openai/status", response_model=ApiKeyStatus)
def api_openai_status() -> ApiKeyStatus:
    """Check if OpenAI key is set and valid."""
    key = _effective_openai_api_key()
    if not key:
        return ApiKeyStatus(present=False, ok=False, message="No OpenAI API key configured.")
    try:
        from openai import OpenAI

        client = OpenAI(api_key=key, timeout=10.0, max_retries=0)
        _ = client.models.list()
        return ApiKeyStatus(present=True, ok=True, message="OK")
    except Exception as e:  # noqa: BLE001
        return ApiKeyStatus(present=True, ok=False, message=str(e))


# NCBI key endpoints
@router.get("/ncbi", response_model=ApiKeyInfo)
def api_get_ncbi_key() -> ApiKeyInfo:
    """Get masked NCBI API key."""
    key = _effective_ncbi_api_key()
    if not key:
        return ApiKeyInfo(present=False, masked=None)
    return ApiKeyInfo(present=True, masked=mask_secret(key))


@router.put("/ncbi", response_model=ApiKeyInfo)
def api_set_ncbi_key(req: ApiKeySetRequest) -> ApiKeyInfo:
    """Set NCBI API key."""
    set_secret(settings.db_path, name=_NCBI_SECRET_NAME, value=req.api_key.strip())
    return api_get_ncbi_key()


@router.delete("/ncbi", response_model=ApiKeyInfo)
def api_delete_ncbi_key() -> ApiKeyInfo:
    """Delete NCBI API key."""
    delete_secret(settings.db_path, name=_NCBI_SECRET_NAME)
    return api_get_ncbi_key()


@router.get("/ncbi/status", response_model=ApiKeyStatus)
def api_ncbi_status() -> ApiKeyStatus:
    """Check if NCBI key is set."""
    key = _effective_ncbi_api_key()
    present = bool(key)
    from procedurewriter.pipeline.fetcher import CachedHttpClient

    http = CachedHttpClient(cache_dir=settings.cache_dir, timeout_s=10.0, max_retries=1, backoff_s=0.6)
    try:
        ok, message = check_ncbi_status(http=http, tool=settings.ncbi_tool, email=settings.ncbi_email, api_key=key)
        return ApiKeyStatus(present=present, ok=ok, message=message)
    except Exception as e:  # noqa: BLE001
        return ApiKeyStatus(present=present, ok=False, message=str(e))
    finally:
        http.close()


# Anthropic key endpoints
@router.get("/anthropic", response_model=ApiKeyInfo)
def api_get_anthropic_key() -> ApiKeyInfo:
    """Get masked Anthropic API key."""
    key = _effective_anthropic_api_key()
    if not key:
        return ApiKeyInfo(present=False, masked=None)
    return ApiKeyInfo(present=True, masked=mask_secret(key))


@router.put("/anthropic", response_model=ApiKeyInfo)
def api_set_anthropic_key(req: ApiKeySetRequest) -> ApiKeyInfo:
    """Set Anthropic API key."""
    set_secret(settings.db_path, name=_ANTHROPIC_SECRET_NAME, value=req.api_key.strip())
    return api_get_anthropic_key()


@router.delete("/anthropic", response_model=ApiKeyInfo)
def api_delete_anthropic_key() -> ApiKeyInfo:
    """Delete Anthropic API key."""
    delete_secret(settings.db_path, name=_ANTHROPIC_SECRET_NAME)
    return api_get_anthropic_key()


@router.get("/anthropic/status", response_model=ApiKeyStatus)
def api_anthropic_status() -> ApiKeyStatus:
    """Check if Anthropic key is set."""
    key = _effective_anthropic_api_key()
    if not key:
        return ApiKeyStatus(present=False, ok=False, message="No Anthropic API key configured.")
    try:
        from anthropic import Anthropic
        Anthropic(api_key=key)  # Validate key format by instantiating
        return ApiKeyStatus(present=True, ok=True, message="OK (key format valid)")
    except ImportError:
        return ApiKeyStatus(present=True, ok=False, message="anthropic package not installed")
    except Exception as e:  # noqa: BLE001
        return ApiKeyStatus(present=True, ok=False, message=str(e))
