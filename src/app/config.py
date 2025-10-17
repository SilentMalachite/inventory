"""
Configuration management for the inventory system.
"""

from pydantic import Field, validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings with validation."""

    # Application
    app_name: str = "Inventory System"
    version: str = "0.1.1"
    debug: bool = False

    # Development mode
    dev_mode: bool = Field(default=True, env="INVENTORY_DEV_MODE")

    # Security
    # Provide a safe default for development/tests; enforce in production via validator
    secret_key: str | None = Field(
        default="DEV_SECRET_KEY_0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ",
        env="INVENTORY_SECRET_KEY",
        min_length=32,
    )
    api_key: str | None = Field(None, env="INVENTORY_API_KEY")
    basic_user: str | None = Field(None, env="INVENTORY_BASIC_USER")
    basic_pass: str | None = Field(None, env="INVENTORY_BASIC_PASS")

    # Database and storage
    app_dir: str | None = Field(None, env="INVENTORY_APP_DIR")

    # Audit logging
    audit_disabled: bool = Field(default=False, env="INVENTORY_AUDIT_DISABLED")
    audit_stdout: bool = Field(default=False, env="INVENTORY_AUDIT_STDOUT")

    # Migration
    migrate: bool = Field(default=False, env="INVENTORY_MIGRATE")

    # Database performance
    db_pool_size: int = Field(default=10, env="INVENTORY_DB_POOL_SIZE")
    db_max_overflow: int = Field(default=20, env="INVENTORY_DB_MAX_OVERFLOW")
    db_pool_recycle: int = Field(default=3600, env="INVENTORY_DB_POOL_RECYCLE")

    @validator("secret_key")
    def validate_secret_key(cls, v, values):
        """Validate secret key in production."""
        dev = values.get("dev_mode", True)
        if not dev and (not v or len(v) < 32):
            raise ValueError(
                "INVENTORY_SECRET_KEY must be at least 32 characters in production"
            )
        return v

    @validator("basic_pass")
    def validate_basic_auth(cls, v, values):
        """Validate basic auth configuration."""
        dev = values.get("dev_mode", True)
        if not dev:
            has_user = values.get("basic_user") is not None
            has_pass = v is not None

            if has_user != has_pass:
                raise ValueError(
                    "Both INVENTORY_BASIC_USER and INVENTORY_BASIC_PASS must be set or both must be empty"
                )

        return v

    @validator("api_key")
    def validate_api_key(cls, v, values):
        """Validate API key in production."""
        dev = values.get("dev_mode", True)
        if not dev and not v:
            raise ValueError("INVENTORY_API_KEY must be set in production")
        return v

    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return not self.dev_mode

    @property
    def security_enabled(self) -> bool:
        """Check if security is enabled."""
        return self.is_production

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Global settings instance
_settings: Settings | None = None


def get_settings() -> Settings:
    """Get settings from current environment (no caching) to reflect runtime changes in tests."""
    return Settings()


def override_settings(settings: Settings) -> None:
    """Override the global settings for testing."""
    global _settings
    _settings = settings
