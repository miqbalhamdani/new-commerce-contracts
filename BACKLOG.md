# Phase 1 Backlog — Catalog & Foundation

**Ordered.** Items are listed in the order they should be built. Dependencies flow downward;
nothing depends on something below it.

**Status** `todo` · `wip` · `review` · `done` · `blocked` · `dropped`
**Repo** `BE` backend · `FE` frontend · `CT` contracts · `OPS` infrastructure

---

## Rules

- **One item, one PR, one branch** named `p1-<id>-<slug>` (e.g. `p1-014-variant-matrix`).
- **Claim by setting `wip` and putting your name in Owner**, in a commit to this file, before
  writing code. Two agents on one item is the failure this file exists to prevent.
- **An item is `done` only when its Acceptance column is demonstrably true** — not when the code
  merges. If acceptance needs a test, the test is part of the item.
- **A `BE` item and its `FE` counterpart are separate items.** They ship independently; the
  frontend works against the generated client and can be built before the backend if the contract
  exists.
- **`blocked` requires a reason** in Notes. A blocked item with no reason is `todo`.
- Do not reorder items to suit convenience. If the order is wrong, say why in the PR.

---

## M0 · Foundation (weeks 1–3)

Nothing user-visible ships here. Everything after it depends on all of it.

Production infrastructure — the VPS, Caddy, TLS, backups and CI — sits in `M4` at the end of the
phase, not here. There is no box and no domain yet; every document still says `{domain}`. The
only piece of it the backend genuinely needs is a reachable PostgreSQL 18, and `P1-000` provides
that from the developer's own machine — a connection string and a `make` target, no container.
This is a deliberate reorder, not a convenient one — the reasoning is in `M4`.

| ID | Item | Repo | Depends | Acceptance | Status | Owner |
|---|---|---|---|---|---|---|
| P1-000 | Local dev services: host PostgreSQL 18 + Redis 8 | OPS | — | `make dev` connects to host PostgreSQL 18 on `:5432` and Redis 8 on `:6379`; `GET /healthz` reports both | done | Iqbal Hamdani |
| P1-005 | `openapi.yaml` skeleton + generators wired both repos | CT/BE/FE | 000 | `make generate` is a no-op on a clean tree in both repos | done | Iqbal Hamdani |
| P1-006 | Migration runner, `app_user` non-owning role, RLS helper | BE | 000 | `app_user` owns nothing; `FORCE RLS` on every tenant table | done | Iqbal Hamdani |
| P1-007 | `InTenantTx`, tenant context, fail-closed on missing tenant | BE | 006 | Missing tenant returns `ErrNoTenantContext`, never an empty result | wip | Iqbal Hamdani |
| P1-008 | **Tenant isolation test suite over every registered route** | BE | 007 | Two seeded tenants; A's token returns zero of B's rows on every route | todo | |
| P1-009 | RLS-policy guard | BE | 006 | `make lint-rls` exits non-zero on a `tenant_id` table with no policy | todo | |
| P1-010 | `tenants`, `users`, `refresh_tokens`, `api_keys` schema | BE | 006 | Matches `erd.md` §3.2 exactly | todo | |
| P1-011 | Auth: login, refresh rotation, logout, argon2id | BE | 010 | A reused refresh token revokes the whole chain | todo | |
| P1-012 | RBAC: 5 seeded roles, `resource:action` checks at handler boundary | BE | 011 | `403` names the required permission in `detail` | todo | |
| P1-013 | Error envelope (RFC 9457), `trace_id`, OpenTelemetry wiring | BE | 007 | Every error carries a `trace_id` resolvable to a span | todo | |
| P1-014 | App shell, routing, auth screens, session handling | FE | 005, 011 | Access token in memory, refresh in httpOnly cookie | todo | |

---

## M1 · Catalog core (weeks 5–8)

| ID | Item | Repo | Depends | Acceptance | Status | Owner |
|---|---|---|---|---|---|---|
| P1-020 | `brands` schema + composite FK to tenant | BE | 010 | `products_same_tenant_as_brand` rejects a cross-tenant brand | todo | |
| P1-021 | Brands CRUD API incl. `channel_brand_ids` | BE | 020 | Matches `API spec.md` §4 | todo | |
| P1-022 | `categories` schema, ltree, slugify, path triggers | BE | 010 | A move rebases every descendant in one statement | todo | |
| P1-023 | Category cycle guard + sibling slug collision handling | BE | 022 | Moving a node under its own descendant raises | todo | |
| P1-024 | Categories API, `kind` filter, depth-limited fetch | BE | 022 | `path` is rejected with `422` if a client sends it | todo | |
| P1-025 | `products` schema incl. `attributes`, `option_names` | BE | 020 | Matches `erd.md` §3.3 | todo | |
| P1-026 | `variants` schema, partial unique SKU index, composite FK | BE | 025 | Many null SKUs allowed; non-null unique per tenant | todo | |
| P1-027 | `product_categories` join, multi-`kind` membership | BE | 022, 025 | One product in 3 trees of different kind simultaneously | todo | |
| P1-028 | Products CRUD, `If-Match`, server-managed field rejection | BE | 025 | `null` fails validation; omitted takes the default | todo | |
| P1-029 | Variants CRUD | BE | 026 | Duplicate SKU returns `409 duplicate_sku` | todo | |
| P1-030 | Product list: search (trigram), filters, cursor pagination | BE | 028 | p95 < 600ms with 10k products | todo | |
| P1-031 | Brand manager screen | FE | 021 | `flows.md` §2 acceptance | todo | |
| P1-032 | Category manager: tree, drag-to-move, confirm dialog | FE | 024 | Dialog states that product assignments are unaffected | todo | |
| P1-033 | Product list screen: search, filters, saved state | FE | 030 | Selection survives pagination and filtering | todo | |
| P1-034 | Product editor: fields, brand select, category multi-select | FE | 028 | Unsaved-changes prompt on navigate away | todo | |

---

## M2 · Variant matrix & media (weeks 8–10)

The differentiating work of this phase. `flows.md` §3 is the acceptance reference.

| ID | Item | Repo | Depends | Acceptance | Status | Owner |
|---|---|---|---|---|---|---|
| P1-040 | `PUT /variant-matrix`: server-side diff, one transaction | BE | 029 | Create + update + archive in one tx; per-row results | todo | |
| P1-041 | Matrix partial failure semantics | BE | 040 | One duplicate SKU fails that row only; others still save | todo | |
| P1-042 | `product_media` schema | BE | 025 | Stores R2 **keys**, never URLs | todo | |
| P1-043 | `POST /media/presign` + `/media/confirm` with HEAD validation | BE | 042 | A key cannot be registered for an object never uploaded | todo | |
| P1-044 | Worker: image derivatives 1600/800/200 WebP via libvips | BE | 043 | Derivative ready < 15s p95 | todo | |
| P1-045 | R2 bucket, tenant prefixes, presigned GET policy | OPS | 042 | Product images 1h; exports 15m | todo | |
| P1-046 | **Variant matrix editor**: grid, paste from Excel, fill-down | FE | 040 | 2×5 grid renders 10 cells, saves in one request < 2s | todo | |
| P1-047 | Matrix bulk price adjust (± amount / %) | FE | 046 | Preview before apply | todo | |
| P1-048 | Media library: drag-drop, direct-to-R2 upload, reorder | FE | 043 | 5MB image shows progress and never blocks the form | todo | |
| P1-049 | Publish check on `draft → active` | BE/FE | 040, 043 | Every variant has SKU + price; ≥1 image; ≥1 category | todo | |

> **P1-049 is where the nullable SKU is enforced.** It is a publish-path check, not a table
> constraint — drafting must stay frictionless. See `erd.md` §4.1.

---

## M3 · Export & admin (weeks 10–12)

| ID | Item | Repo | Depends | Acceptance | Status | Owner |
|---|---|---|---|---|---|---|
| P1-060 | Async job runner + `GET /v1/jobs/{id}` | BE | 007 | Reused unchanged by every later phase | todo | |
| P1-061 | Catalog export: templates for 5 marketplaces + generic | BE | 060, 030 | 10k variants < 60s | todo | |
| P1-062 | Export reports incomplete channel mapping, grouped | BE | 061 | Generates anyway; names what is missing | todo | |
| P1-063 | Export screen: template picker, filters, download | FE | 061 | Link expires in 15m and can be regenerated | todo | |
| P1-064 | Users: invite, role assign, disable | BE | 012 | Disable signs out within 15 min at worst | todo | |
| P1-065 | API keys: issue, prefix display, revoke | BE | 012 | Secret shown exactly once | todo | |
| P1-066 | Team & roles screen | FE | 064 | `ops` sees no user-management nav at all | todo | |
| P1-067 | API keys screen | FE | 065 | Copy-once UI with an explicit warning | todo | |
| P1-068 | Onboarding wizard incl. `channel_brand_ids` capture | FE | 021, 024 | Skippable and resumable at every step | todo | |
| P1-069 | Empty states carrying the "no stock yet" message | FE | 033 | Present on product list and product editor | todo | |

---

## M4 · Production readiness & pilot (weeks 10–12)

Moved down from `M0`, deliberately. None of it can be demonstrated today — there is no VPS and
no domain, so `P1-001`'s acceptance has nothing to point at — and nothing in `M0`–`M3` needs it,
because the backend develops against the host-installed services from `P1-000`.

It cannot move any further than this. `P1-070` puts a real merchant's catalog on the box, and
that must not happen on storage nobody has ever restored from.

| ID | Item | Repo | Depends | Acceptance | Status | Owner |
|---|---|---|---|---|---|---|
| P1-001 | VPS provisioning, Docker Compose, Caddy, TLS | OPS | — | `docker compose up` serves HTTPS on the domain | todo | |
| P1-002 | PostgreSQL 18 + Redis 8 with tuned config and resource limits | OPS | 001 | `shared_buffers` ≈ 25% RAM; per-service `cpus`/`mem_limit` set | todo | |
| P1-003 | **pgBackRest to R2 + restore drill** | OPS | 002 | **A restore from R2 into a clean box succeeds.** Blocks all merchant data | todo | |
| P1-004 | CI: lint, test, migration-on-snapshot, contracts drift check | BE/FE | 001 | A PR that breaks any of the four is red | todo | |
| P1-070 | Pilot merchant onboarding: real catalog loaded | OPS | all | One merchant's real catalog is in the system | todo | |

> **P1-003 gates the pilot.** `P1-070` does not start until the restore drill has passed.
> Everything from that point on assumes merchant data is recoverable.

> **`P1-001` needs a decision before it can start:** the production domain. Every document still
> says `{domain}`. Caddy's default ACME challenge also cannot reach the box through Cloudflare's
> proxy, so the TLS mode — DNS-01 with a Cloudflare token, or a Cloudflare Origin certificate —
> is part of this item, not an implementation detail of it.

---

## Definition of Done

An item is `done` when **all** of these are true. Not four of five.

1. The Acceptance column is demonstrably true, with a test where a test is possible.
2. It matches the contract. If it could not, the contract changed first, in its own PR.
3. Tenant isolation holds — new routes are covered by P1-008's suite.
4. Errors use the RFC 9457 envelope with a `trace_id`.
5. No server-managed field is accepted from a client.
6. `make generate` is a no-op on a clean tree in both repos.
7. Reviewed by someone who did not write it.

---

## Out of scope for Phase 1

Recorded here because they will be proposed, repeatedly, and the answer should be one link.

| Request | Phase |
|---|---|
| Stock, quantities, warehouses | 4 |
| Orders, shipping, labels | 2 |
| `POST /products/bulk`, CSV import | 2 |
| Marketplace API sync (export CSV is the Phase 1 answer) | 3 |
| `Idempotency-Key` on mutations | 4 |
| Per-channel pricing | post-4 |
