# Postman smoke-test collection

This directory contains a sanitized Postman collection, a local environment template, and sample files for manually smoke-testing the local Spend Analyzer API.

## Files

| Path | Purpose |
|---|---|
| `spend-analyser.postman_collection.json` | Postman collection for local health, auth, and ingestion smoke tests |
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

Run the requests in this order:

```text
1. Health
2. DB Health
3. Token
4. Me
5. Ingest
```

The `Token` request stores the returned token into the `access_token` environment variable. The `Me` and `Ingest` requests use that token automatically.

## File upload setup

The `Ingest` request uses the file form-data field:

```text
file = docs/postman/files/sample-statement.pdf
```

If Postman does not resolve the relative path after import, manually select:

```text
docs/postman/files/sample-statement.pdf
```

Expected successful `/ingest` result:

```text
201 Created
status = UPLOADED
original_file_name = sample-statement.pdf
content_type = application/pdf
```

## Negative tests

The collection also includes negative tests:

| Request | Expected result |
|---|---|
| `Me - Missing Token` | `401 Unauthorized` |
| `Ingest - Missing Token` | `401 Unauthorized` |
| `Ingest - Invalid PDF Content` | `400 Bad Request` |

For `Ingest - Invalid PDF Content`, attach:

```text
docs/postman/files/invalid-sample-statement.pdf
```

Expected response:

```json
{
  "detail": "Uploaded file content is not a valid PDF"
}
```

## Notes

Postman pre-request scripts cannot attach an in-memory generated file to a multipart `file` field. The collection therefore uses checked-in local fixture files.
