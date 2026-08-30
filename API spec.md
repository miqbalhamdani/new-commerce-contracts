# Phase 1 — Catalog & Foundation · API Specification

**The conventions in §1 apply to every phase.** Later phases reference this section rather than
restating it.

---

## 1. Conventions

| Concern | Rule |
|---|---|
| Base | `https://api.{domain}/v1` — version in the path; breaking changes get `/v2` |
| Auth (UI) | `Authorization: Bearer <JWT>`, 15-minute access token, rotating refresh in an httpOnly cookie |
| Auth (integrators) | `Authorization: Bearer <api_key>`, scoped to permissions, per-key rate limit |
| Tenant | Derived from the token. **Never** accepted from a header or body — that would be a trivial cross-tenant escalation |
| Content type | `application/json; charset=utf-8` |
| Casing | `snake_case` in JSON, matching the database, so no translation layer can drift |
| Pagination | Cursor only: `?limit=50&cursor=<opaque>`. No `offset` — deep offsets are a sequential scan |
| Sorting | `?sort=-created_at` (leading `-` for descending), allow-listed per endpoint |
| Filtering | Explicit params, not a query DSL |
| Concurrency | `If-Match: <version>` on every `PATCH`; `409` on mismatch |
| Errors | RFC 9457 `application/problem+json` |
| Time | RFC 3339 with offset, always UTC |
| Money | `{"amount": 2000000, "currency": "IDR"}` — integer minor units, never a decimal string |
| **Server-managed fields** | The client never sends `id`, `tenant_id`, `version`, `created_at`, `updated_at`, or `path`. Ignored if present on create; `422` if present on update |
| **Defaultable fields** | Omit `currency` (defaults to the tenant's) and `status` (defaults to `draft`). **Sending `null` is not the same as omitting** — `null` fails validation, an absent key takes the default |

### 1.1 Error shape

```json
{
  "type": "https://docs.{domain}/errors/version-conflict",
  "title": "Version conflict",
  "status": 409,
  "detail": "Product was modified by another user. Reload and retry.",
  "instance": "/v1/products/01926f3a-…",
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "errors": [{ "field": "version", "expected": 4, "supplied": 3 }]
}
```

`trace_id` is the OpenTelemetry trace id — a support ticket quoting it goes straight to the span.

Canonical codes in this phase: `validation_failed` 422 · `version_conflict` 409 ·
`duplicate_sku` 409 · `permission_denied` 403 · `not_found` 404 · `rate_limited` 429.

### 1.2 Rate limits

| Caller | Limit |
|---|---|
| UI session (JWT) | 600 req/min/user |
| API key | 300 req/min/key, burst 60 |

Headers on every response: `RateLimit-Limit`, `RateLimit-Remaining`, `RateLimit-Reset`.

---

## 2. Auth and identity

```
POST   /v1/auth/login
POST   /v1/auth/refresh
POST   /v1/auth/logout
POST   /v1/auth/accept-invite
GET    /v1/me
PATCH  /v1/me
```

```json
POST /v1/auth/login
{ "email": "ops@erigo.co.id", "password": "…" }

200 OK   ← refresh token is set as an httpOnly, Secure, SameSite=Lax cookie
{ "access_token": "eyJ…", "expires_in": 900,
  "user": { "id": "0192…", "name": "Budi", "role": "ops",
            "permissions": ["products:read","products:write","categories:write"] },
  "tenant": { "id": "0192…", "name": "Erigo", "timezone": "Asia/Jakarta",
              "currency": "IDR" } }
```

Refresh rotates: each call issues a new refresh token and revokes the old one. **A reused
refresh token means theft** — the whole rotation chain is revoked and the user is signed out
everywhere.

---

## 3. Users and API keys

```
GET    /v1/users?status=&role=
POST   /v1/users/invite
PATCH  /v1/users/{id}                      role, status
DELETE /v1/users/{id}                      disable, never hard delete
GET    /v1/roles                           the five seeded roles and their permissions

GET    /v1/api-keys
POST   /v1/api-keys
DELETE /v1/api-keys/{id}
```

```json
POST /v1/api-keys
{ "name": "Warehouse scanner app",
  "permissions": ["products:read","categories:read"] }

201 Created
{ "id": "0192…", "name": "Warehouse scanner app", "key_prefix": "bk_live_",
  "secret": "bk_live_7f3a91c2e8…",     ← shown exactly once, never retrievable again
  "permissions": [...] }
```

---

## 4. Brands

```
GET    /v1/brands?q=&archived=false
POST   /v1/brands
GET    /v1/brands/{id}
PATCH  /v1/brands/{id}                     If-Match required
DELETE /v1/brands/{id}                     archive
```

```json
POST /v1/brands
{ "name": "Erigo",
  "channel_brand_ids": { "shopee": "12345", "tokopedia": "998" } }
```

`slug` is derived from `name` server-side. `channel_brand_ids` is consumed by the CSV export in
this phase and by the listing publisher from Phase 3 — filling it in early saves rework later.

---

## 5. Categories

```
GET    /v1/categories?kind=category&parent_id=&depth=
POST   /v1/categories
PATCH  /v1/categories/{id}                 name and/or parent_id — triggers a subtree rebase
DELETE /v1/categories/{id}                 refused if it has children or products
```

```json
POST /v1/categories
{ "name": "Jackets", "parent_id": "0192-outerwear", "kind": "category" }

201 Created
{ "id": "0192…", "name": "Jackets", "parent_id": "0192-outerwear",
  "kind": "category", "path": "apparel.outerwear.jackets" }
```

**`path` is read-only.** It is derived by a trigger from `name` + `parent_id`; sending it
returns `422`.

`GET /v1/categories?kind=activity` returns one tree. Omit `kind` to get all trees, grouped.
`?depth=1` returns only direct children of `parent_id`, for lazy-loading a large tree.

Moving a category rebases every descendant's `path` in one statement. Products are unaffected —
`product_categories` references `category_id`, never `path`.

---

## 6. Products and variants

```
GET    /v1/products?status=&brand_id=&category_id=&q=&limit=&cursor=
POST   /v1/products
GET    /v1/products/{id}
PATCH  /v1/products/{id}                   If-Match required
DELETE /v1/products/{id}                   archive, not hard delete

GET    /v1/products/{id}/variants
POST   /v1/products/{id}/variants
PATCH  /v1/variants/{id}                   If-Match required
DELETE /v1/variants/{id}                   archive

PUT    /v1/products/{id}/variant-matrix
GET    /v1/products/export?template=&format=
```

### 6.1 Create — what the client actually sends

Only what the user supplied. `version` and `currency` are **absent**, not `null`:

```json
POST /v1/products
{
  "title": "Erigo Basic Tee",
  "brand_id": "0192a1c4-…",
  "option_names": ["Colour", "Size"],
  "attributes": { "material": "Cotton Combed 30s" }
}
```

```json
201 Created
{
  "id": "0192b7f0-…",
  "version": 1,                              ← server-assigned
  "title": "Erigo Basic Tee",
  "brand": { "id": "0192a1c4-…", "name": "Erigo" },   ← expanded on read
  "status": "draft",                         ← default applied
  "option_names": ["Colour", "Size"],
  "variant_count": 0,
  "created_at": "2026-08-27T09:15:00Z"
}
```

Updates send the version in the **header**, never the body: `If-Match: 1`. The server increments
it and returns the new value; a stale value gets `409 version_conflict`.

### 6.2 The variant matrix

`PUT /v1/products/{id}/variant-matrix` saves the whole option grid in **one transaction**.

The problem it solves: a merchandiser opens the grid, pastes prices from Excel, removes a
colourway and adds a size. Without this endpoint the front end must diff the grid itself and
fire 25 separate requests — no transaction, no ordering guarantee, and a partial failure leaves
the grid in a state neither the user nor the system understands.

It is **declarative** — "here is what the grid should be" — and the server computes the diff.

```json
PUT /v1/products/{id}/variant-matrix
{
  "option_names": ["Colour", "Size"],
  "rows": [
    { "option_values": ["Black","S"], "sku": "TS-BLK-S",
      "price": { "amount": 19900000, "currency": "IDR" } },
    { "option_values": ["Black","M"], "sku": "TS-BLK-M",
      "price": { "amount": 19900000, "currency": "IDR" } },
    { "option_values": ["Black","XXL"], "sku": "TS-BLK-XXL",
      "price": { "amount": 21900000, "currency": "IDR" } }
  ],
  "archive_missing": true
}
```

```json
200 OK
{
  "created": 1, "updated": 2, "archived": 4,
  "results": [
    { "option_values": ["Black","S"],   "status": "updated", "variant_id": "0192…" },
    { "option_values": ["Black","XXL"], "status": "created", "variant_id": "0193…" },
    { "option_values": ["White","S"],   "status": "error",
      "code": "duplicate_sku", "detail": "SKU TS-WHT-S already exists on another product" }
  ]
}
```

`archive_missing: false` patches part of a grid without archiving the combinations that were
not sent — used when the editor is showing a filtered view.

### 6.3 Matrix versus `PATCH /v1/variants/{id}`

Different jobs. Do not use one for the other.

| | `variant-matrix` | `PATCH /variants/{id}` |
|---|---|---|
| Scope | Every variant of the product | Exactly one |
| Can create | Yes | No |
| Can archive | Yes | No |
| Changes grid shape | Yes | No |
| Typical caller | Matrix editor's Save | Variant detail drawer |
| Concurrency | Product-level | `If-Match` on that variant |

A warehouse manager fixing one barcode uses `PATCH`. Sending a whole-grid `PUT` for that would
clobber a merchandiser's concurrent edit.

---

## 7. Media

```
POST   /v1/media/presign
POST   /v1/media/confirm
DELETE /v1/media/{id}
PATCH  /v1/products/{id}/media/order
```

Uploads go **direct from browser to R2**. Image bytes never transit the Go API.

```
1. FE  → POST /v1/media/presign  { product_id, mime_type, bytes }
        ← { upload_url, r2_key, expires_in: 600 }
2. FE  → PUT  <upload_url>   (raw file, progress bar)
3. FE  → POST /v1/media/confirm  { r2_key, product_id, variant_id? }
        ← 201 { id, r2_key, derivatives: {} }     derivatives arrive async
```

`/media/confirm` validates content type and size against R2's `HEAD` before persisting the row —
a presigned URL binds the size at signature time, but the confirm step is what stops a key being
registered for an object that was never uploaded.

Derivatives (1600 / 800 / 200px WebP) are generated by the worker and appear on the record
within ~15s. Serve them through a Cloudflare Worker on a custom domain for edge caching.

---

## 8. Catalog export

The feature that makes this phase standalone-useful.

```
GET /v1/products/export?template=shopee&format=csv&status=active
→ 202 { "job_id": "0192…" }

GET /v1/jobs/{job_id}
→ { "state": "done", "download_url": "https://…", "expires_in": 900 }
```

`template` renders the catalog into the column layout that marketplace's bulk-upload sheet
expects, using `brands.channel_brand_ids` for brand mapping and
`products.attributes.channel.{kind}` for category and required attributes.

Supported: `shopee`, `tokopedia`, `tiktok`, `lazada`, `blibli`, `generic`.

No `channels` table is involved — this is pure CSV generation and the merchant uploads the file
themselves. It is also a rehearsal for Phase 3: if the attribute mapping is wrong here it would
have been wrong in the API integration, and this is a far cheaper place to discover that.

---

## 9. Not in this phase

Requested often enough during pilot that they are worth naming explicitly:

| Endpoint | Phase |
|---|---|
| `POST /v1/products/bulk` | 2 |
| `POST /v1/products/import` | 2 |
| Anything under `/v1/orders` | 2 |
| Anything under `/v1/channels` or `/v1/hooks` | 3 |
| Anything under `/v1/inventory` or `/v1/locations` | 4 |

`GET /v1/jobs/{id}` exists from Phase 1 because the export needs it, and every later phase's
async work reuses it unchanged.
