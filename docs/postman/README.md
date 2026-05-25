# Postman smoke-test collection

This directory contains a sanitized Postman collection, a local environment template, and sample files for manually smoke-testing the local Spend Analyzer API.

## Files

| Path | Purpose |
|---|---|
| `spend-analyser.postman_collection.json` | Postman collection for local health, docs, auth, and ingestion smoke tests |
| `spend-analyser-local.postman_environment.json` | Local Postman environment template with no committed token |
| `files/sample-statement.pdf` | Valid dummy PDF statement for positive `/ingest` testing |
| `files/invalid-sample-statement.pdf` | Invalid `.pdf` file for negative `/ingest` validation testing |

The sample PDFs contain dummy data only. They are for upload and validation smoke tests, not parser-accuracy tests.

## Prerequisites

Start the local stack from the repository root:

```bash
docker compose up -d --build
```

Confirm the local API and identity provider are reachable:

```text
http://localhost:8000/health
http://localhost:8000/health/db
http://localhost:8000/docs
http://localhost:8000/openapi.json
http://localhost:8080/realms/spend-analyzer/.well-known/openid-configuration
```

## Import into Postman

1. Open Postman.
2. Import `spend-analyser.postman_collection.json`.
3. Import `spend-analyser-local.postman_environment.json`.
4. Select the `Spend Analyser Local` environment.

The environment contains local defaults:

```text
api_base_url = http://localhost:8000
idp_base_url = http://localhost:8080
realm = spend-analyzer
client_id = spend-analyzer-local
username = test.user
password = change_me
access_token = <empty>
```

Do not commit exported environments that contain a real `access_token`.

## Run order

Run these requests in order:

```text
1. Health
2. DB Health
3. Docs
4. OpenAPI
5. Token
6. Me
7. Ingest
```

The `Token` request stores the returned token into the `access_token` environment variable. The `Me` and `Ingest` requests use that token automatically.

## File upload setup

The `Ingest` request uses the file form-data field:

```text
file = docs/postman/files/sample-statement.pdf
```

If Postman does not resolve the relative path after import, manually select the same file manually from the repository checkout.

Expected successful `/ingest` result:

```text
201 Created
status = UPLOADED
original_file_name = sample-statement.pdf
content_type = application/pdf
```

## Negative tests

The collection also includes a `Negative Tests` folder for missing-token and invalid-file scenarios.

## Notes

Postman cannot attach generated in-memory content to a multipart file field. The collection therefore uses checked-in local fixture files.
