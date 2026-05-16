# Local Identity Provider Setup

Spend Analyzer uses Keycloak as the local OAuth2/OIDC identity provider.

This setup is intended for local development and integration tests only. Higher environments should configure OIDC through environment-specific infrastructure, identity-provider administration, or infrastructure-as-code.

---

## Local Keycloak Service

The local Docker Compose stack starts Keycloak as:

```text
identity-provider
```

The local browser/admin URL is:

```text
http://localhost:8080
```

---

## Admin Login

Use the credentials from `.env`:

```text
Username: admin
Password: change_me
```

These are local development credentials only.

---

## Imported Realm

The realm is imported automatically from:

```text
infra/keycloak/local/spend-analyzer-realm.json
```

The imported realm name is:

```text
spend-analyzer
```

The import is enabled only in:

```text
docker-compose.yml
docker-compose.test.yml
```

It is not part of the application Docker image and should not be treated as production identity-provider configuration.

---

## Clients

### API Audience Client

```text
spend-analyzer-api
```

This represents the backend API audience.

Future JWT validation should verify that access tokens contain:

```text
aud = spend-analyzer-api
```

### Local Development Client

```text
spend-analyzer-local
```

This is a public local development client used to generate local access tokens.

---

## Local Test User

The imported realm includes this local test user:

```text
Username: test.user
Password: change_me
Email: test.user@example.com
```

This user is for local development and integration tests only.

---

## Start the Local Stack

```bash
docker compose up -d --build
```

Check that Keycloak is reachable:

```text
http://localhost:8080/realms/spend-analyzer/.well-known/openid-configuration
```

---

## Generate an Access Token

### PowerShell

```powershell
$response = Invoke-RestMethod `
  -Method Post `
  -Uri "http://localhost:8080/realms/spend-analyzer/protocol/openid-connect/token" `
  -ContentType "application/x-www-form-urlencoded" `
  -Body @{
    grant_type = "password"
    client_id = "spend-analyzer-local"
    username = "test.user"
    password = "change_me"
  }

$response.access_token
```

### Bash / Git Bash

```bash
curl -X POST "http://localhost:8080/realms/spend-analyzer/protocol/openid-connect/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=password" \
  -d "client_id=spend-analyzer-local" \
  -d "username=test.user" \
  -d "password=change_me"
```

---

## Important Local URLs

| Purpose | URL |
|---|---|
| Realm discovery | `http://localhost:8080/realms/spend-analyzer/.well-known/openid-configuration` |
| Token endpoint | `http://localhost:8080/realms/spend-analyzer/protocol/openid-connect/token` |
| JWKS endpoint for app container | `http://identity-provider:8080/realms/spend-analyzer/protocol/openid-connect/certs` |

---

## Important Test URLs

The integration test stack exposes Keycloak on port `58080`:

| Purpose | URL |
|---|---|
| Realm discovery | `http://localhost:58080/realms/spend-analyzer/.well-known/openid-configuration` |
| Token endpoint | `http://localhost:58080/realms/spend-analyzer/protocol/openid-connect/token` |

---

## Why Realm Import Is Local/Test Only

Local and build environments need repeatable setup.

Realm import gives us:

```text
realm
clients
audience mapper
test user
```

without manual Keycloak UI steps.

Higher environments should not rely on this local realm import file. They should configure identity through one of:

```text
platform-managed identity provider
Keycloak admin process
Terraform/IaC
Keycloak admin API automation
environment-specific security process
```

This keeps production identity configuration controlled and auditable.
