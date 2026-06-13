from app.auth.dependencies import oauth2_scheme


def test_oauth2_scheme_uses_configured_token_url():
    assert oauth2_scheme.model.flows.password.tokenUrl == "token"
