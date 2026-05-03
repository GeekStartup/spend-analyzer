from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Application
    app_name: str
    app_env: str
    app_version: str
    app_port: int

    # Database
    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str

    # Identity Provider / Keycloak Admin
    keycloak_admin: str
    keycloak_admin_password: str

    # Identity Provider / OIDC
    oidc_issuer_url: str
    oidc_jwks_url: str
    oidc_audience: str
    oidc_client_id: str

    # AI
    openai_api_key: str = ""
    openai_model: str = "gpt-4.1-mini"

    # Storage
    upload_dir: str
    storage_type: str

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


settings = Settings()
