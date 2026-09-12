# FileMorph API

All authenticated mutations require cookies plus `X-CSRF-Token` matching `filemorph_csrf`. Access/refresh tokens are HTTP-only cookies. Account IDs come from the session, never a client-supplied owner.

## Errors

```json
{"error":{"code":"INVALID_FILE","message":"Choose a valid PDF file.","request_id":"..."}}
```

Responses also include `X-Request-ID`. Authentication failures are `401`, CSRF rejection `403`, inaccessible jobs `404`, unavailable jobs `409`, expiration `410`, oversized inputs `413`, unsupported conversion/content `422`, and rate limits `429`.

## Authentication

| Method | Route | Body/behavior |
| --- | --- | --- |
| POST | `/api/auth/signup` | JSON `email`, `password`, `display_name`; creates cookies; `201` |
| POST | `/api/auth/login` | JSON `email`, `password`; creates cookies |
| POST | `/api/auth/logout` | Revokes current refresh session and clears cookies; `204` |
| POST | `/api/auth/refresh` | Consumes refresh session once and rotates cookies |
| GET | `/api/auth/me` | Current public user |

User responses contain `id`, `email`, `display_name`, `created_at`, not password hashes or tokens. Passwords are 8+ characters and at most 72 UTF-8 bytes for bcrypt.

## Conversions

| Method | Route | Behavior |
| --- | --- | --- |
| GET | `/api/formats` | Public registered formats, limits, MIME, fidelity, batch/execution metadata |
| POST | `/api/conversions` | Multipart `conversion_type`, single `file` or repeated `files`; optional `page_range`; returns `{job}` with `201` |
| GET | `/api/conversions/{id}` | Owned job detail |
| GET | `/api/conversions/{id}/download` | Owned completed file; attachment filename |
| GET | `/api/conversions/{id}/preview` | Owned completed Markdown/asset JSON |
| POST | `/api/conversions/{id}/retry` | Reprocess retained source; returns `{job}` |
| PATCH | `/api/conversions/{id}` | Multipart `output_filename`; keeps the actual output suffix |
| DELETE | `/api/conversions/{id}` | Removes files and hides job; `204` |

Batch upload order is output page order. Maximum 20 files and configured combined byte/page limits apply. `split-pdf` accepts ranges such as `1-3,5`; invalid ranges produce an honest failed job. Current small conversions complete within the request; a `failed` job is not a successful output.

Job fields: `id`, source filename/format/size, target format, output filename/size, `status`, `progress`, page count, fidelity, safe failure reason, created/completed/expiration timestamps. Internal storage keys are omitted.

## History and Account

| Method | Route | Behavior |
| --- | --- | --- |
| GET | `/api/history` | `page`, `page_size` (1-100), `search`, `source_format`, `target_format`, `status`, `sort=newest|oldest` |
| DELETE | `/api/history` | Deletes all owned files/history entries; `204` |
| DELETE | `/api/history/{id}` | Alias of owned-job deletion |
| GET | `/api/users/me` | Public profile |
| PATCH | `/api/users/me` | JSON `display_name` |
| PATCH | `/api/users/me/password` | JSON `current_password`, `new_password`; invalidates old sessions; `204` |
| DELETE | `/api/users/me` | Deletes account, sessions, jobs, source/output files; `204` |
| GET | `/api/health` | Liveness |
| GET | `/api/ready` | Runtime persistence mode; MongoDB indexes initialize at startup |

History returns `{items,total,page,page_size}`. Every query is scoped to the authenticated account.

## Compatibility

`POST /api/convert` and `/api/convert/to-markdown` retain Markdown JSON/bundle responses. `/api/convert/{id}` retains binary outputs for individual files. They remain public and do not persist history. Batch workspace and range options should use `/api/conversions`; calling a split without a range is rejected.
