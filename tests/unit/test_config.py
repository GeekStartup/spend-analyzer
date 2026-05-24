import pytest
from pydantic import ValidationError

from app.config import Settings


def create_settings(**overrides) -> Settings:
    values = {
        "app_name": "Spend Analyzer",
        "app_env": "test",
        "app_version": "0.1.0",
        "app_port": 8000,
        "db_host": "localhost",
        "db_port": 5432,
        "db_name": "spend_analyzer",
        "db_user": "test_user",
        "db_password": "test password",
        "keycloak_admin": "admin",
        "keycloak_admin_password": "admin-password",
        "oidc_issuer_url": "http://identity-provider:8080/realms/spend-analyzer",
        "oidc_jwks_url": (
            "http://identity-provider:8080/realms/spend-analyzer/"
            "protocol/openid-connect/certs"
        ),
        "oidc_audience": "spend-analyzer-api",
        "oidc_client_id": "spend-analyzer-api",
        "openai_api_key": "",
        "openai_model": "gpt-4.1-mini",
        "upload_dir": "/app/uploads",
        "max_upload_size_bytes": 10 * 1024 * 1024,
        "storage_type": "local",
    }
    values.update(overrides)

    return Settings(**values)


def test_settings_trims_required_string_values():
    settings = create_settings(app_name="  Spend Analyzer  ")

    assert settings.app_name == "Spend Analyzer"


def test_settings_rejects_blank_required_string_values():
    with pytest.raises(ValidationError, match="Value must not be blank"):
        create_settings(app_name="   ")


def test_settings_rejects_non_url_oidc_values():
    with pytest.raises(
        ValidationError, match="Value must start with http:// or https://"
    ):
        create_settings(oidc_issuer_url="identity-provider")


def test_database_url_escapes_credentials():
    settings = create_settings(
        db_user="test user",
        db_password="test password",
    )

    assert settings.database_url == (
        "postgresql://test+user:test+password@localhost:5432/spend_analyzer"
    )


def test_is_ai_enabled_returns_false_when_openai_key_is_blank():
    settings = create_settings(openai_api_key="   ")

    assert settings.is_ai_enabled is False


def test_is_ai_enabled_returns_true_when_openai_key_is_configured():
    settings = create_settings(openai_api_key="test-key")

    assert settings.is_ai_enabled is True
