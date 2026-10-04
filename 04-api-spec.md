# Phase 1 — Catalog & Foundation · API Specification

**The conventions in §1 apply to every phase.** Later phases reference this section rather than
restating it. Each endpoint lists the permission it requires (matrix in §3) and the rules it
enforces (`BR-xxx`, see `02-business-rules.md`). `openapi.yaml` is the machine-readable copy; a
path appears there when the backlog item that builds it lands.

---

## 1. Conventions

| Concern | Rule |
|---|---|
| Base | `https://api.{domain}/v1`: the version is in the path; breaking changes get `/v2` |
| Auth (UI) | `Authorization: Bearer <JWT>`, 15-minute access token, rotating refresh in an httpOnly cookie (BR-022) |
| Auth (integrators) | `Authorization: Bearer <api_key>`, limited to the key's permissions (BR-028) |
| Tenant | Derived from the token, **never** accepted from a header, query or body (BR-003) |
| Content type | `application/json; charset=utf-8` |
| Casing | `snake_case` in JSON, matching the database, so there is no translation layer to drift |
| Ids | UUID v7 strings (BR-005) |
| Money | `{"amount": 2000000, "currency": "IDR"}`: integer minor units (BR-006) |
| Time | RFC 3339 with offset, always UTC (BR-007) |
| Server-managed fields | `id`, `tenant_id`, `version`, `created_at`, `updated_at`, `path`, `slug`: sending one is `422`, on create and update (BR-008) |
| Omitted vs `null` | Create: omitted takes the default, `null` is `422`. `PATCH`: omitted is unchanged, `null` clears a nullable field (BR-009) |
| Concurrency | `If-Match: <version>` on every `PATCH` to a product, variant, brand or category, and on the variant matrix `PUT`; stale → `409` (BR-010) |
| Responses | Every field is always present; an empty optional field is `null`. References are expanded to `{id, name}` |
| Collections | `{ "data": [...], "next_cursor": "…" }`. `next_cursor` is `null` on the last page. Unpaginated collections omit it. `GET /v1/roles` is the one bare array |
| Pagination | Cursor only: `?limit=50&cursor=<opaque>`, `limit` 1–200. No `offset`: a deep offset is a sequential scan |
| Sorting | `?sort=-created_at` (leading `-` for descending), allow-listed per endpoint |
| Filtering | Explicit query parameters, not a query DSL |
| Deletes | Catalog `DELETE` archives and returns `204` (BR-012) |

### 1.1 Errors

Every error is RFC 9457 `application/problem+json` (BR-011):

```json
{
  "type": "https://docs.{domain}/errors/version_conflict",
  "title": "Version conflict",
  "status": 409,
  "detail": "Product was modified by another user. Reload and retry.",
  "instance": "/v1/products/01926f3a-…",
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "errors": [{ "field": "version", "expected": 4, "supplied": 3 }]
}
```

The code is the last segment of `type`. `errors[]` entries always carry `field`
and may carry anything the failure needs.

| Code | Status | When | BR |
|---|---|---|---|
| `validation_failed` | 422 | Malformed body, failed validation, a server-managed field sent, `null` where it isn't allowed, missing `If-Match` | 008, 009 |
| `publish_check_failed` | 422 | `draft → active` fails the publish check; one `errors[]` entry per failure | 038 |
| `unauthenticated` | 401 | Missing, expired or invalid credentials; every failed login | 021 |
| `permission_denied` | 403 | `detail` names the required permission | 024 |
| `not_found` | 404 | No such resource in this tenant, including another tenant's rows | 011 |
| `version_conflict` | 409 | Stale `If-Match` | 010 |
| `duplicate_sku` | 409 | SKU already used in this tenant; `detail` names the product holding it | 039 |
| `category_in_use` | 409 | Deleting a category that has children or products | 036 |
| `rate_limited` | 429 | Over the limit; see the `RateLimit-*` headers | 014 |
| `internal` | 500 | Anything unexpected. `detail` is generic on purpose; `trace_id` is the lead | 011 |

### 1.2 Rate limits

| Caller | Limit |
|---|---|
| UI session (JWT) | 600 req/min/user |
| API key | 300 req/min/key, burst 60 |

Headers on every response: `RateLimit-Limit`, `RateLimit-Remaining`, `RateLimit-Reset` (BR-014).

---

## 2. Auth and identity

| Method | Path | Permission | BR |
|---|---|---|---|
| `POST` | `/v1/auth/login` | none | 020, 021, 022 |
| `POST` | `/v1/auth/refresh` | refresh cookie | 022 |
| `POST` | `/v1/auth/logout` | signed in | 022 |
| `POST` | `/v1/auth/accept-invite` | none (invitation token) | 026 |
| `GET` | `/v1/me` | signed in | — |
| `PATCH` | `/v1/me` | signed in | 009 |

Tenants are created by the platform team, not through this API. The owner then receives an
invitation like any other user.

### Login

```json
POST /v1/auth/login
{ "email": "ops@erigo.co.id", "password": "…" }

200 OK   ← refresh token set as an httpOnly, Secure, SameSite=Lax cookie
{ "access_token": "eyJ…", "expires_in": 900,
  "user":   { "id": "0192…", "name": "Budi", "role": "ops",
              "permissions": ["products:read", "products:write", "…"] },
  "tenant": { "id": "0192…", "name": "Erigo", "timezone": "Asia/Jakarta", "currency": "IDR" } }
```

This body is the **Session**. `refresh` and `accept-invite` return it too. The tenant is resolved
from the user row (BR-020): there is no tenant, workspace or subdomain parameter, and adding one
would be a breaking change. The lookup is the one read that crosses tenants and runs through a
single `SECURITY DEFINER` function (BR-003). A wrong password, an unknown email and a disabled
account are all the same `401` (BR-021).

### Refresh and logout

```
POST /v1/auth/refresh      (no body; reads the cookie)  → 200 Session, new cookie
POST /v1/auth/logout       (no body; reads the cookie)  → 204, cookie cleared
```

Each `refresh` rotates the token; reusing a rotated token revokes the whole chain (BR-022).
`refresh` is unauthenticated because you call it *after* the access token has expired. `logout`
is idempotent: a second call, or a call with no cookie, is still `204`.

### Accept an invitation

```json
POST /v1/auth/accept-invite
{ "token": "inv_9c2e…", "password": "at-least-8-chars" }

200 OK   ← Session + refresh cookie: the user lands signed in
```

An expired or already-used token is `422` on `token` (BR-026).

### Me

```json
GET /v1/me
200 OK
{ "user":   { "id": "0192…", "email": "ops@erigo.co.id", "name": "Budi", "role": "ops",
              "permissions": ["products:read", "…"] },
  "tenant": { "id": "0192…", "name": "Erigo", "timezone": "Asia/Jakarta", "currency": "IDR" } }

PATCH /v1/me
{ "name": "Budi Santoso" }
200 OK   ← same body as GET /v1/me
```

`name` is the only field you can change here. Password change and reset are not in this phase.

---

## 3. Roles and permissions

Five roles, seeded and fixed (BR-023). A permission is `resource:action`, where the action is
`read` or `write`.

| Permission | `owner` | `admin` | `ops` | `warehouse` | `viewer` |
|---|:--:|:--:|:--:|:--:|:--:|
| `products:read` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `products:write` | ✓ | ✓ | ✓ | | |
| `variants:read` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `variants:write` | ✓ | ✓ | ✓ | | |
| `categories:read` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `categories:write` | ✓ | ✓ | | | |
| `brands:read` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `brands:write` | ✓ | ✓ | | | |
| `media:read` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `media:write` | ✓ | ✓ | ✓ | | |
| `exports:read` | ✓ | ✓ | ✓ | | ✓ |
| `users:read` | ✓ | ✓ | | | |
| `users:write` | ✓ | ✓ | | | |
| `api_keys:read` | ✓ | ✓ | | | |
| `api_keys:write` | ✓ | ✓ | | | |
| `settings:read` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `settings:write` | ✓ | | | | |

**`owner` is `admin` plus `settings:write`, and nothing else.** An owner hands a merchandiser access
"without giving away billing" (`01-product.md` §5.5), so the line between the two roles is the
tenant's own settings.

**`ops` reads categories and brands but doesn't write them.** The product editor needs to read them
to attach a product; restructuring the tree is the category manager's job, which belongs to Admin.

**`warehouse` reads the catalog and changes nothing.** It exists so the role is available before
Phase 4 gives it stock.

A `403` names the required permission in `detail` (BR-024). A client doesn't render what the user
can't do (BR-025).

---

## 4. Settings, users and API keys

| Method | Path | Permission | BR |
|---|---|---|---|
| `GET` | `/v1/settings` | `settings:read` | 029 |
| `PATCH` | `/v1/settings` | `settings:write` | 009, 029 |
| `GET` | `/v1/roles` | `users:read` | 023 |
| `GET` | `/v1/users?status=&role=&limit=&cursor=` | `users:read` | — |
| `POST` | `/v1/users/invite` | `users:write` | 020, 023, 026 |
| `POST` | `/v1/users/{id}/resend-invite` | `users:write` | 026 |
| `PATCH` | `/v1/users/{id}` | `users:write` | 023, 027 |
| `DELETE` | `/v1/users/{id}` | `users:write` | 027 |
| `GET` | `/v1/api-keys` | `api_keys:read` | 028 |
| `POST` | `/v1/api-keys` | `api_keys:write` | 028 |
| `DELETE` | `/v1/api-keys/{id}` | `api_keys:write` | 028 |

### Settings

```json
GET /v1/settings
200 OK
{ "id": "0192…", "name": "Erigo", "slug": "erigo",
  "timezone": "Asia/Jakarta", "currency": "IDR", "status": "active" }

PATCH /v1/settings
{ "name": "Erigo Apparel", "timezone": "Asia/Makassar" }
200 OK   ← same body as GET
```

Only `name` and `timezone` can be changed. `currency` is fixed in Phase 1.

### Roles

```json
GET /v1/roles
200 OK
[ { "name": "owner", "description": "Everything, including the tenant's own settings",
    "permissions": ["products:read", "…", "settings:write"] },
  … ]
```

The response is a constant: clients render the role picker from it instead of hardcoding §3.

### Users

```json
GET /v1/users?status=invited
200 OK
{ "data": [
    { "id": "0192…", "email": "rina@erigo.co.id", "name": "Rina", "role": "ops",
      "status": "invited", "last_login_at": null, "created_at": "2026-08-27T09:15:00Z" } ],
  "next_cursor": null }

POST /v1/users/invite
{ "email": "rina@erigo.co.id", "name": "Rina", "role": "ops" }
201 Created   ← the User above; an invitation email is sent

POST /v1/users/{id}/resend-invite
204 No Content   ← only while status is invited; otherwise 422

PATCH /v1/users/{id}
{ "role": "admin" }                 or   { "status": "active" }
200 OK   ← the User

DELETE /v1/users/{id}
204 No Content   ← sets status disabled; never deletes the row
```

- An email already used at any tenant is `422` on `email` (BR-020).
- Only an owner can assign `owner` (BR-023).
- The tenant's last active owner can't be demoted or disabled (BR-027).
- `PATCH` takes `role` and `status` (`active` re-enables a disabled user) and needs no `If-Match`
  (BR-010).

### API keys

```json
POST /v1/api-keys
{ "name": "Warehouse scanner app",
  "permissions": ["products:read", "categories:read"] }

201 Created
{ "id": "0192…", "name": "Warehouse scanner app", "key_prefix": "bk_live_7f3a",
  "secret": "bk_live_7f3a91c2e8…",          ← shown exactly once, never retrievable again
  "permissions": ["products:read", "categories:read"],
  "created_by": { "id": "0192…", "name": "Budi" },
  "last_used_at": null, "created_at": "2026-08-27T09:15:00Z" }

GET /v1/api-keys
200 OK
{ "data": [ …same shape without "secret"… ] }    ← unpaginated; revoked keys are not listed

DELETE /v1/api-keys/{id}
204 No Content   ← revokes; takes effect on the key's next request
```

A key's permissions must be a subset of its creator's; anything else is `422` on `permissions`
(BR-028).

---

## 5. Brands

| Method | Path | Permission | BR |
|---|---|---|---|
| `GET` | `/v1/brands?q=&archived=false&limit=&cursor=` | `brands:read` | — |
| `POST` | `/v1/brands` | `brands:write` | 030 |
| `GET` | `/v1/brands/{id}` | `brands:read` | — |
| `PATCH` | `/v1/brands/{id}` | `brands:write` | 010, 030 |
| `DELETE` | `/v1/brands/{id}` | `brands:write` | 012 |

```json
POST /v1/brands
{ "name": "Erigo",
  "channel_brand_ids": { "shopee": "12345", "tokopedia": "998" } }

201 Created
{ "id": "0192…", "version": 1, "name": "Erigo", "slug": "erigo",
  "channel_brand_ids": { "shopee": "12345", "tokopedia": "998" },
  "archived_at": null,
  "created_at": "2026-08-27T09:15:00Z", "updated_at": "2026-08-27T09:15:00Z" }

PATCH /v1/brands/{id}          If-Match: 1
{ "channel_brand_ids": { "shopee": "12345", "tokopedia": "998", "tiktok": "abc" } }
200 OK   ← the Brand, version 2
```

- `slug` comes from `name`, including on rename.
- A name whose slug matches another brand's, archived ones included, is `422` on `name` (BR-030).
- `channel_brand_ids` is replaced as a whole object.
- `GET` lists sort by `name`; `q` matches on name.

---

## 6. Categories

| Method | Path | Permission | BR |
|---|---|---|---|
| `GET` | `/v1/categories?kind=&parent_id=&depth=` | `categories:read` | 031 |
| `GET` | `/v1/categories/{id}` | `categories:read` | 033 |
| `POST` | `/v1/categories` | `categories:write` | 031, 032, 035 |
| `PATCH` | `/v1/categories/{id}` | `categories:write` | 010, 032, 033, 034, 035 |
| `DELETE` | `/v1/categories/{id}` | `categories:write` | 012, 036 |

```json
POST /v1/categories
{ "name": "Jackets", "parent_id": "0192-outerwear", "kind": "category" }

201 Created
{ "id": "0192…", "version": 1, "kind": "category", "name": "Jackets",
  "parent_id": "0192-outerwear", "path": "apparel.outerwear.jackets",
  "archived_at": null,
  "created_at": "2026-08-27T09:15:00Z", "updated_at": "2026-08-27T09:15:00Z" }

GET /v1/categories/{id}
200 OK   ← the Category plus the counts the move dialog needs:
{ …, "descendant_count": 4, "product_count": 128 }      ← product_count covers the whole subtree

PATCH /v1/categories/{id}      If-Match: 1
{ "parent_id": "0192-technical-outerwear" }      or   { "name": "Jackets & Coats" }
200 OK   ← the Category with its new path

DELETE /v1/categories/{id}
204 No Content
409 category_in_use
{ …, "errors": [ { "field": "children", "count": 4 }, { "field": "products", "count": 128 } ] }
```

- **`path` is read-only.** The database derives it; sending it is `422` (BR-008, BR-032).
- A rename or move rewrites every descendant's `path` in one statement and doesn't touch product
  assignments (BR-033).
- A move beneath the category's own descendant is `422` on `parent_id` (BR-034).
- `parent_id: null` on `PATCH` makes the category a root.
- **List.** Unpaginated, flat, ordered by `kind` then `path`; the client builds the tree from
  `parent_id`.
  - `kind` limits the list to one tree.
  - `parent_id` starts from that node's children; omitted, it starts from the roots.
  - `depth=1` returns one level only, for lazy-loading a large tree.

---

## 7. Products and variants

| Method | Path | Permission | BR |
|---|---|---|---|
| `GET` | `/v1/products?status=&brand_id=&category_id=&q=&sort=&limit=&cursor=` | `products:read` | — |
| `POST` | `/v1/products` | `products:write` | 009, 037 |
| `GET` | `/v1/products/{id}` | `products:read` | — |
| `PATCH` | `/v1/products/{id}` | `products:write` | 009, 010, 037, 038 |
| `DELETE` | `/v1/products/{id}` | `products:write` | 012 |
| `GET` | `/v1/products/{id}/variants?archived=false` | `variants:read` | — |
| `POST` | `/v1/products/{id}/variants` | `variants:write` | 039, 040 |
| `PATCH` | `/v1/variants/{id}` | `variants:write` | 009, 010, 039 |
| `DELETE` | `/v1/variants/{id}` | `variants:write` | 012 |
| `PUT` | `/v1/products/{id}/variant-matrix` | `variants:write` | 010, 039, 040, 041 |

### 7.1 Product

```json
POST /v1/products
{ "title": "Erigo Basic Tee",
  "brand_id": "0192a1c4-…",
  "category_ids": ["0192-jackets", "0192-hiking"],
  "attributes": { "material": "Cotton Combed 30s" } }
```

Only what the user supplied: `status` and `version` are **absent**, not `null`.

```json
201 Created
{ "id": "0192b7f0-…",
  "version": 1,                                       ← server-assigned
  "title": "Erigo Basic Tee",
  "description": null,
  "status": "draft",                                  ← default applied
  "brand": { "id": "0192a1c4-…", "name": "Erigo" },   ← expanded on read
  "categories": [ { "id": "0192-jackets", "kind": "category", "name": "Jackets",
                    "path": "apparel.outerwear.jackets" }, … ],
  "attributes": { "material": "Cotton Combed 30s" },
  "option_names": [],
  "variant_count": 0,
  "media": [],                                        ← Media objects, by position (§8)
  "archived_at": null,
  "created_at": "2026-08-27T09:15:00Z", "updated_at": "2026-08-27T09:15:00Z" }
```

`GET /v1/products/{id}` returns the same body.

```json
PATCH /v1/products/{id}        If-Match: 1
{ "description": "Kaos basic 30s", "brand_id": null, "status": "active" }
200 OK   ← the Product, version 2
```

- **Version.** It travels in `If-Match`, never in the body; the server increments it.
- **Clearing.** `null` clears `description` or `brand_id` (BR-009).
- **Replaced as a whole.** `category_ids` replaces all assignments; `attributes` replaces the
  whole object.
- **`option_names`** changes only through the variant matrix (§7.3); sending it here is `422`.
- **Status.** `"status": "active"` runs the publish check (BR-038) and `"draft"` unpublishes.
  `DELETE` archives.

```json
422 publish_check_failed
{ …, "errors": [
    { "field": "sku",        "variant_id": "0192…", "detail": "Variant Black / XL has no SKU" },
    { "field": "price",      "variant_id": "0192…", "detail": "Price must be greater than zero" },
    { "field": "media",      "detail": "At least one image is required" },
    { "field": "categories", "detail": "At least one category of kind category is required" } ] }
```

**List.**

```json
GET /v1/products?status=active&category_id=0192-apparel&q=tee&sort=-updated_at
200 OK
{ "data": [
    { "id": "0192…", "version": 3, "title": "Erigo Basic Tee", "status": "active",
      "brand": { "id": "0192…", "name": "Erigo" },
      "variant_count": 10,
      "price_min": { "amount": 19900000, "currency": "IDR" },
      "price_max": { "amount": 21900000, "currency": "IDR" },
      "cover_url": "https://…/200.webp",              ← 200px derivative of the first image, or null
      "updated_at": "2026-08-27T09:15:00Z" } ],
  "next_cursor": "eyJ…" }
```

- `category_id` matches that category **and its descendants**.
- `q` is a trigram match on `title`.
- `sort` accepts `-created_at` (default), `-updated_at` or `title`.
- Archived products appear only with `status=archived`.

### 7.2 Variant

```json
POST /v1/products/{id}/variants
{ "option_values": ["Black", "S"], "sku": "TS-BLK-S",
  "price": { "amount": 19900000 }, "weight_grams": 200 }

201 Created
{ "id": "0192…", "product_id": "0192b7f0-…", "version": 1,
  "option_values": ["Black", "S"], "sku": "TS-BLK-S", "barcode": null,
  "price": { "amount": 19900000, "currency": "IDR" },   ← currency defaulted from the tenant
  "compare_at_price": null, "weight_grams": 200,
  "archived_at": null,
  "created_at": "2026-08-27T09:15:00Z", "updated_at": "2026-08-27T09:15:00Z" }

PATCH /v1/variants/{id}        If-Match: 1
{ "barcode": "8991234567890", "compare_at_price": null }
200 OK   ← the Variant, version 2

GET /v1/products/{id}/variants
200 OK
{ "data": [ …Variant… ] }      ← unpaginated, ordered by option_values
```

- `option_values` must have one entry per `option_names` entry and be unique among the product's
  live variants (BR-040). It changes only through the matrix.
- A clashing SKU is `409 duplicate_sku` (BR-039).

### 7.3 The variant matrix

`PUT /v1/products/{id}/variant-matrix` saves the whole option grid in **one request** (BR-041).

The problem it solves: a merchandiser opens the grid, pastes prices from Excel, removes a colourway
and adds a size. Without this endpoint the front end would have to diff the grid itself and fire 25
separate requests, with no transaction and no ordering guarantee. A partial failure would leave the
grid in a state neither the user nor the system understands.

It is **declarative** ("here is what the grid should be") and the server computes the diff.

```json
PUT /v1/products/{id}/variant-matrix      If-Match: 3      ← the PRODUCT's version
{ "option_names": ["Colour", "Size"],
  "rows": [
    { "option_values": ["Black","S"], "sku": "TS-BLK-S",
      "price": { "amount": 19900000 }, "weight_grams": 200 },
    { "option_values": ["Black","M"], "sku": "TS-BLK-M",
      "price": { "amount": 19900000 }, "weight_grams": 210 },
    { "option_values": ["Black","XXL"], "sku": "TS-BLK-XXL",
      "price": { "amount": 21900000 }, "weight_grams": 240 },
    { "option_values": ["White","S"], "sku": "TS-WHT-S",
      "price": { "amount": 19900000 }, "weight_grams": 200 } ],
  "archive_missing": true }

200 OK
{ "product_version": 4,
  "created": 1, "updated": 2, "restored": 0, "unchanged": 0, "archived": 4, "failed": 1,
  "archived_variant_ids": ["0192…", "…"],
  "results": [
    { "option_values": ["Black","S"],   "status": "updated", "variant_id": "0192…" },
    { "option_values": ["Black","M"],   "status": "updated", "variant_id": "0192…" },
    { "option_values": ["Black","XXL"], "status": "created", "variant_id": "0193…" },
    { "option_values": ["White","S"],   "status": "error",   "variant_id": null,
      "code": "duplicate_sku", "detail": "SKU TS-WHT-S is used by Erigo Oversize Tee" } ] }
```

- **Matching.** Rows match the product's live variants by `option_values`. A row that matches an
  archived variant restores it, so re-adding a colourway keeps its SKU.
- **One bad row fails alone.** The other rows still save, and every row gets a result (BR-041).
  The response is `200` even when some rows failed.
- **`archive_missing`.**
  - `true` archives the live variants not sent.
  - `false` patches part of a grid without archiving anything; the editor uses it for a filtered
    view.
  - Changing `option_names` with `archive_missing: false` is `422`: variants of the old shape
    can't survive.
- **Request-level errors.** A row whose `option_values` doesn't match `option_names` makes the
  whole request `422` before anything is written. So do duplicate rows and a Colour axis not at
  position 0 (BR-040).
- **Concurrency.** The product's `version` guards the matrix, and a successful save increments it.

### 7.4 Matrix versus `PATCH /v1/variants/{id}`

Different jobs. Don't use one for the other.

| | `variant-matrix` | `PATCH /variants/{id}` |
|---|---|---|
| Scope | Every variant of the product | Exactly one |
| Can create | Yes | No |
| Can archive | Yes | No |
| Changes grid shape | Yes | No |
| Typical caller | Matrix editor's Save | Variant detail drawer |
| Concurrency | `If-Match` on the product | `If-Match` on that variant |

Someone fixing one barcode uses `PATCH`. Sending a whole-grid `PUT` for that would overwrite a
merchandiser's concurrent edit.

---

## 8. Media

| Method | Path | Permission | BR |
|---|---|---|---|
| `POST` | `/v1/media/presign` | `media:write` | 051, 053 |
| `POST` | `/v1/media/confirm` | `media:write` | 050, 051 |
| `PATCH` | `/v1/media/{id}` | `media:write` | 009 |
| `DELETE` | `/v1/media/{id}` | `media:write` | 012 |
| `PATCH` | `/v1/products/{id}/media/order` | `media:write` | — |

Uploads go **directly from the browser to R2**; image bytes never pass through the API (BR-051).

```json
1. POST /v1/media/presign
   { "product_id": "0192…", "mime_type": "image/jpeg", "bytes": 5242880 }
   200 OK
   { "upload_url": "https://…r2…", "r2_key": "0192-tenant/products/0192…/0193…",
     "expires_in": 600 }

2. PUT <upload_url>            raw file bytes, straight to R2, with a progress bar

3. POST /v1/media/confirm
   { "r2_key": "0192-tenant/products/0192…/0193…", "product_id": "0192…", "variant_id": null }
   201 Created
   { "id": "0193…", "product_id": "0192…", "variant_id": null,
     "r2_key": "0192-tenant/products/0192…/0193…",
     "mime_type": "image/jpeg", "bytes": 5242880, "width": 3000, "height": 4000,
     "position": 0,
     "url": "https://…",                    ← presigned GET of the original, 1 hour (BR-053)
     "derivatives": {},                     ← filled by the worker within ~15s (BR-052)
     "created_at": "2026-08-27T09:15:00Z" }
```

- **Presign.** It accepts `image/jpeg`, `image/png` and `image/webp` up to 20 MB; anything else
  is `422` (BR-051).
- **Confirm.** It checks content type and size against R2's `HEAD` before saving the row. A key
  for an object that was never uploaded is `422`.
- **Derivatives.** Once ready, `derivatives` is
  `{ "1600": "https://…", "800": "https://…", "200": "https://…" }`, each a presigned 1-hour URL.
  The product body carries the same Media objects.

```json
PATCH /v1/media/{id}
{ "variant_id": "0192…" }          or   { "variant_id": null }    ← assign to a variant / product level
200 OK   ← the Media

PATCH /v1/products/{id}/media/order
{ "media_ids": ["0193…", "0194…", "0195…"] }    ← every media id of the product, in the new order
200 OK
{ "data": [ …Media, by position… ] }

DELETE /v1/media/{id}
204 No Content   ← removes the row; the worker deletes the R2 objects
```

Media has no `version`, so neither `PATCH` takes `If-Match`. An order list that doesn't contain
exactly the product's media is `422`.

---

## 9. Catalog export and jobs

| Method | Path | Permission | BR |
|---|---|---|---|
| `GET` | `/v1/products/export?template=&format=csv&status=&brand_id=&category_id=` | `exports:read` | 060, 061, 062 |
| `GET` | `/v1/jobs/{id}` | the job's own permission (`exports:read` for an export) | 060, 063 |

```json
GET /v1/products/export?template=shopee&format=csv&status=active&category_id=0192-apparel
202 Accepted
{ "job_id": "0192…" }

GET /v1/jobs/{id}
200 OK
{ "id": "0192…", "kind": "catalog_export",
  "state": "done",                         ← queued | running | done | failed
  "progress": 100,                         ← 0–100
  "created_at": "2026-08-27T09:15:00Z", "finished_at": "2026-08-27T09:15:41Z",
  "result": {
    "download_url": "https://…", "expires_in": 900,
    "products": 412, "variants": 2381,
    "incomplete": [
      { "missing": "channel_brand_id",
        "products": [ { "id": "0192…", "title": "Erigo Basic Tee" } ] },
      { "missing": "channel_category_id",
        "products": [ { "id": "0192…", "title": "Erigo Cargo Pants" } ] } ] },
  "error": null }                          ← a Problem when state is failed
```

- **Template.** `template` is one of `shopee`, `tokopedia`, `tiktok`, `lazada`, `blibli` or
  `generic`. It renders the catalog into the column layout of that marketplace's bulk-upload sheet
  (BR-061). The filters match §7.1's product list.
- **Missing mappings.** They never block the export. Those cells are left blank and the products
  are listed in `incomplete`, grouped by what is missing (BR-062).
- **Download link.** Every `GET` of a finished job signs a fresh 15-minute `download_url`, which
  is how a link is regenerated (BR-063). `result` is `null` until `state` is `done`.

No `channels` table is involved: this is pure CSV generation, and the merchant uploads the file
themselves. `GET /v1/jobs/{id}` exists from Phase 1 because the export needs it, and every later
phase's async work reuses it unchanged.

---

## 10. Not in this phase

Requested often enough during the pilot that they are worth naming explicitly:

| Endpoint | Phase |
|---|---|
| `POST /v1/products/bulk` | 2 |
| `POST /v1/products/import` | 2 |
| Anything under `/v1/orders` | 2 |
| Anything under `/v1/channels` or `/v1/hooks` | 3 |
| Anything under `/v1/inventory` or `/v1/locations` | 4 |
| Password change and reset | not yet scheduled |
