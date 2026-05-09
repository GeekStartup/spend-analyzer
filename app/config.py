from functools import lru_cache
from typing import Literal
from urllib.parse import quote_plus

from pydantic import Field, computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Central application configuration

    All values are loaded from environment variables or the local .env file.
    Other modules should import settings from this file instead of reading
    environment variables directly.
    """

    # Application
    app_name: str = Field(..., description="Application display name")
    app_env: Literal["local", "dev", "test", "stage", "prod"] = Field(
        default="local", description="Application environment"
    )
    app_version: str = Field(default="0.1.0", description="Application version")
    app_port: int = Field(default=8000, description="Application port")

    # Database
    db_host: str = Field(..., description="Database host")
    db_port: int = Field(default=5432, description="Database port")
    db_name: str = Field(..., description="Database name")
    db_user: str = Field(..., description="Database user")
    db_password: str = Field(..., description="Database password")

    # Identity Provider / Keycloak Admin
    keycloak_admin: str = Field(..., description="Keycloak admin username")
    keycloak_admin_password: str = Field(..., description="Keycloak admin password")

    # Identity Provider / OIDC
    oidc_issuer_url: str = Field(..., description="OIDC issuer URL")
    oidc_jwks_url: str = Field(..., description="OIDC JWKS endpoint URL")
    oidc_audience: str = Field(..., description="Expected JWT audience")
    oidc_client_id: str = Field(..., description="OIDC client id")

    # AI
    openai_api_key: str = Field(default="", description="OpenAI API key")
    openai_model: str = Field(default="gpt-4.1-mini", description="OpenAI model name")

    # Storage
    upload_dir: str = Field(
        default="/app/uploads", description="Statement upload directory"
    )
    storage_type: Literal["local", "s3"] = Field(
        default="local",
        description="Storage backend type",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator(
        "app_name",
        "db_host",
        "db_name",
        "db_user",
        "db_password",
        "keycloak_admin",
        "keycloak_admin_password",
        "oidc_issuer_url",
        "oidc_jwks_url",
        "oidc_audience",
        "oidc_client_id",
    )
    @classmethod
    def must_not_be_blank(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("Value must not be blank")
        return value.strip()

    @field_validator("oidc_issuer_url", "oidc_jwks_url")
    @classmethod
    def must_be_url_like(cls, value: str) -> str:
        if not value.startswith(("http://", "https://")):
            raise ValueError("Value must start with http:// or https://")
        return value.strip()

    @computed_field
    @property
    def database_url(self) -> str:
        """
        Canonical PostgreSQL connection URL.

        Later, database modules can use this instead of manually rebuilding
        the URL in multiple places.
        """
        db_user = quote_plus(self.db_user)
        db_password = quote_plus(self.db_password)

        return (
            f"postgresql://{db_user}:{db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @computed_field
    @property
    def is_ai_enabled(self) -> bool:
        """
        AI fallback is available only when an OpenAI API key is configured.
        """
        return bool(self.openai_api_key.strip())


@lru_cache
def get_settings() -> Settings:
    """
    Load and cache application settings.

    This avoids recreating and revalidating the Settings object every time
    some module needs configuration.
    """
    return Settings()


settings = get_settings()
