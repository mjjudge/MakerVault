"""Application settings loaded from environment variables."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All configuration for the MakerVault API.

    Values are loaded from environment variables (case-insensitive).
    Required variables will raise a validation error on startup if missing.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # -------------------------------------------------------------------------
    # Application
    # -------------------------------------------------------------------------
    app_name: str = "MakerVault API"
    app_version: str = "1.0.0"
    debug: bool = False

    # -------------------------------------------------------------------------
    # Database
    # -------------------------------------------------------------------------
    # Full async-compatible connection URL.
    # Example: postgresql+asyncpg://user:password@localhost:5432/makervault
    database_url: str = "postgresql+asyncpg://makervault:makervault@db:5432/makervault"

    # Pool settings
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_echo: bool = False

    # -------------------------------------------------------------------------
    # Document storage
    # -------------------------------------------------------------------------
    document_store_path: str = "/data/makervault/documents"

    # -------------------------------------------------------------------------
    # Backup
    # -------------------------------------------------------------------------
    # Directory where backup archives are written.
    # Override with BACKUP_PATH to use a separate physical disk or mount.
    backup_path: str = "/data/makervault/backups"

    # How many completed backups of each type to keep before pruning.
    # Set to 0 to disable automatic pruning (prune manually via the API).
    backup_retention_count: int = 10

    # -------------------------------------------------------------------------
    # Security
    # -------------------------------------------------------------------------
    secret_key: str = "insecure-default-change-me"


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance.

    Use FastAPI dependency injection to access settings:
        Depends(get_settings)
    """
    return Settings()
