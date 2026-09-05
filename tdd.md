# Phase 1 — Catalog & Foundation · Technical Design

**Ships** Weeks 1–12 · **Status** Production, used by pilot merchants
**Depends on** nothing · **Depended on by** Phases 2, 3 and 4

---

## 1. What this phase is

A product master. The merchant's single source of truth for what they sell — products,
variants, brands, categories, images — with a real team model on top of it, and CSV export in
the shapes the marketplaces accept.

It also lays every piece of foundation the later phases assume: tenancy, authentication,
permissions, the audit posture, the API conventions, and the deployment. Roughly half the work
in this phase is never seen by a user and is the reason Phases 2–4 can be built quickly.

### Why this is a releasable product on its own

Most Indonesian merchants keep product data in a spreadsheet that is copied by hand into each
marketplace's seller centre. That spreadsheet is the thing that goes stale, contradicts itself
between channels, and has no history. Phase 1 replaces it with something that has structure,
roles, an image library and an export that matches what Shopee and Tokopedia actually accept
for bulk upload.

That is genuinely useful the day it ships, and it seeds the catalog that every later phase
operates on. A merchant who has spent two weeks getting their 3,000 SKUs clean in Phase 1 is a
merchant who is still there when Phase 3 connects their channels.

### What it deliberately cannot do

- **No stock.** No quantities, no locations, no reservations. Inventory is unlimited.
- **No orders.** Nothing is sold through it yet.
- **No marketplace connection.** Export is a CSV the merchant uploads themselves.
- **No bulk edit or CSV import.** Those arrive in Phase 2 — Phase 1 is create-and-edit only.

Say all four to a pilot merchant before onboarding them. A merchant who expects stock control
in Phase 1 will conclude the product is broken rather than early.

---

## 2. Architecture

### 2.1 Shape

One Go module, one deployable image, three entrypoints. A modular monolith — not
microservices. The domain packages are separated by import rules rather than by network calls,
so extracting a service later is mechanical rather than archaeological.

```
cmd/api       HTTP API. Serves the Next.js front end and third-party integrators.
cmd/worker    Queue consumer. In Phase 1: image derivative generation and CSV export only.
cmd/migrate   Schema migrations. Runs to completion and exits.
```

### 2.2 Deployment — single VPS

Front end and back end on one box. Suggested size to start: **8 vCPU / 16 GB / NVMe**, Ubuntu
LTS, Docker Compose.

```
Cloudflare (DNS, WAF, edge rate limiting)  ──►  VPS
                                                 ├── Caddy         :443   TLS + reverse proxy
                                                 ├── Next.js       :3000
                                                 ├── cmd/api  ×2   :8080  (rolling restarts)
                                                 ├── cmd/worker ×1        (no ingress)
                                                 ├── PostgreSQL 18        local NVMe volume
                                                 └── Redis 8              local volume, AOF on

Cloudflare R2  ◄── product images, exports
```

Two API replicas is not for throughput — it is so a deploy drains one container at a time.

**What one box makes your responsibility.** Each of these would otherwise be a managed
service's job, and each is a way to lose a merchant's data:

- **Backups.** `pgBackRest` or `wal-g` to R2: nightly base backup plus continuous WAL
  archiving. **Restore-test it before the first pilot merchant**, not after. This is Phase 1's
  single largest risk and it is an exit criterion, not a nice-to-have.
- **Resource limits.** Set `cpus` and `mem_limit` per service in Compose, or an image-processing
  burst in the worker starves PostgreSQL and stalls the whole box.
- **PostgreSQL tuning for a shared box.** `shared_buffers` ≈ 25% of RAM,
  `effective_cache_size` ≈ 50%, `max_connections` = 100 with hard pool caps in pgx.
- **Disk headroom.** Alert at 70%.

**When to move off.** PostgreSQL first — it is the component whose failure loses data. Then the
worker. Neither needs a code change, only connection strings.

### 2.3 Component choices

| Concern | Choice | Why |
|---|---|---|
| Router | `chi` | Stdlib-compatible `http.Handler`, no framework lock-in |
| DB access | `pgx/v5` + `sqlc` | Typed queries generated from real SQL. RLS and row locking need SQL you control |
| Migrations | `golang-migrate` | Plain up/down SQL, reviewable in a PR |
| Queue | Redis Streams | Barely needed in Phase 1, but establishing it now avoids a retrofit in Phase 3 |
| Object storage | Cloudflare R2 | Zero egress, S3-compatible. Product imagery is the bulk of stored bytes |
| Front end | Next.js 15 App Router | Server Components for dense list views; client components only for the grid editors |
| Auth | JWT access (15 min) + rotating refresh, `argon2id` | Short access token keeps the RLS context fresh |
| Observability | OpenTelemetry | Established in Phase 1 so Phase 3's webhook path is traceable from day one |

---

## 3. Multi-tenancy

Shared schema, `tenant_id` on every tenant-owned table, enforced by PostgreSQL Row-Level
Security. Application code cannot be the only guard — one forgotten `WHERE tenant_id = $1` in a
reporting query is a cross-tenant leak, and that class of bug is invisible in review.

### 3.1 The pattern

```sql
ALTER TABLE products ENABLE ROW LEVEL SECURITY;
ALTER TABLE products FORCE  ROW LEVEL SECURITY;   -- applies to the table owner too

CREATE POLICY tenant_isolation ON products
    USING      (tenant_id = current_setting('app.tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);
```

`FORCE` matters. Without it the role that owns the table bypasses its own policy — and that is
the role your migrations run as. The application connects as a **non-owning** role:

```sql
CREATE ROLE app_user LOGIN PASSWORD :'pw';
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO app_user;
-- app_user owns nothing, so RLS always applies
```

### 3.2 Setting the context

Per **transaction**, never per connection — pgx pools connections, and a leaked `SET` would
follow the connection into the next request's tenant.

```go
// internal/db/tx.go
func (s *Store) InTenantTx(ctx context.Context, fn func(pgx.Tx) error) error {
    tenantID, ok := tenant.FromContext(ctx)
    if !ok {
        return ErrNoTenantContext // fail closed, never fall through to "all tenants"
    }
    tx, err := s.pool.BeginTx(ctx, pgx.TxOptions{})
    if err != nil {
        return err
    }
    defer tx.Rollback(ctx) //nolint:errcheck // no-op after commit

    // is_local = true scopes the setting to this transaction only
    if _, err := tx.Exec(ctx,
        `SELECT set_config('app.tenant_id', $1::text, true)`, tenantID); err != nil {
        return err
    }
    if err := fn(tx); err != nil {
        return err
    }
    return tx.Commit(ctx)
}
```

`ErrNoTenantContext` is the important line. With no tenant set, `current_setting(…, true)`
returns `NULL`, the policy evaluates to `NULL`, and every row is filtered out — RLS fails
*closed*, which is safe but produces a baffling empty result. Returning an error makes the bug
loud instead of mysterious.

### 3.3 Guard rails

- **Migration test.** CI enumerates `information_schema.tables` and fails if any table with a
  `tenant_id` column lacks an enabled RLS policy. A new table without one cannot merge.
- **Isolation test.** Every registered route is exercised with two seeded tenants; tenant A's
  token must return zero of tenant B's rows.
- **No `pool.Query` outside `internal/db`,** enforced by an import-boundary lint rule.
- **Composite indexes lead with `tenant_id`.** RLS adds the predicate to every query; an index
  that cannot serve it is dead weight.
- **Cross-tenant admin work** uses a separate `BYPASSRLS` role, a separate pool, and audit
  logging. Never reachable from a request-scoped code path.

### 3.4 Denormalised `tenant_id` on child tables

`variants.tenant_id` is derivable through `products`. It is denormalised on purpose: without
it, the RLS policy has to be a correlated subquery that runs on every row touched by every
query on `variants`, cannot be served by an index on `variants` alone, and makes
`UNIQUE (tenant_id, sku)` inexpressible — SKU uniqueness is per tenant, not per product.

The cost is that two rows could disagree, which a composite foreign key makes impossible:

```sql
ALTER TABLE products ADD CONSTRAINT products_id_tenant_uq UNIQUE (id, tenant_id);
ALTER TABLE variants ADD CONSTRAINT variants_same_tenant_as_product
    FOREIGN KEY (product_id, tenant_id) REFERENCES products (id, tenant_id);
```

**Apply this pattern to every child table carrying a denormalised `tenant_id`,** in every phase.

---

## 4. Roles and permissions

Five seeded roles. Permissions are a flat set of `resource:action` strings, so a custom role is
a data change rather than a deploy.

| Role | Intent in Phase 1 |
|---|---|
| `owner` | Everything, including billing and tenant deletion |
| `admin` | Everything except billing |
| `ops` | Products and categories. No user management |
| `warehouse` | Read-only in Phase 1; becomes meaningful in Phase 4 |
| `viewer` | Read-only |

Checked at the handler boundary: `products:write`, `categories:write`, `users:manage`. The
`warehouse` role's location scoping does not exist yet — there are no locations until Phase 4 —
but the role is seeded now so the permission surface does not change shape later.

---

## 5. Domain notes

### 5.1 The variant matrix

A product carries `option_names` (`['Colour','Size']`); each variant carries `option_values`
positionally against it (`['Black','S']`). Position 0 is always Colour.

That positional guarantee is what makes the matrix editor cheap: one query returns every
variant with its option tuple, and the front end pivots the array into a grid. A
`variant_option_values` join table is more normalised and makes every grid render a three-way
join plus a pivot.

The trade-off: "all Black variants" needs `option_values @> ARRAY['Black']` and a GIN index.
Add it when the query actually appears, not before.

### 5.2 Category paths

`categories.path` is an `ltree` derived by a database trigger from `name` + `parent_id`. The
client never sends it.

A trigger rather than Go code because the hard case is a **move**: renaming a mid-tree category
must rewrite `path` on every descendant atomically. In application code, every write path has
to remember to do that, and the one that forgets leaves a silently broken tree.

The payoff is subtree queries — `WHERE path <@ 'apparel'` is one indexed operator instead of a
recursive CTE walking `parent_id` one level at a time.

`product_categories` references `category_id`, never `path`, so a move touches zero product
links. That is why `parent_id` is the truth and `path` is only a derived index.

### 5.3 Multi-hierarchy classification

`categories.kind` (`category`, `series`, `collection`, `activity`, `custom`) gives a product
membership in several independent trees at once. An outdoor brand's jacket sits in
`apparel.outerwear.jackets`, in `hiking`, and in `ss26` — three rows in `product_categories`,
three trees, no conflict.

This exists in Phase 1 rather than later because retrofitting it means re-tagging the whole
catalog by hand.

### 5.4 Cloudflare R2

Two object classes in this phase, one bucket, prefixed by tenant. The database stores **object
keys, never URLs** — URLs expire, keys do not.

| Prefix | Contents | Access |
|---|---|---|
| `{tenant}/products/{variant}/{hash}.webp` | Imagery: original plus 1600/800/200px derivatives | Presigned GET, 1h |
| `{tenant}/exports/{job}.csv` | Catalog exports | Presigned GET, 15m |

Uploads go **direct from browser to R2** via a presigned PUT — image bytes never transit the Go
API. The client requests a URL, uploads, then calls back with the key; the API validates
content type and size from R2's `HEAD` before persisting it. Derivatives are generated by the
worker (`libvips` via `bimg`).

### 5.5 Marketplace CSV export

The feature that makes Phase 1 standalone-useful. `GET /v1/products/export?template=shopee`
renders the catalog into the column layout that marketplace's bulk-upload sheet expects, using
`brands.channel_brand_ids` for the brand mapping and `products.attributes.channel.{kind}` for
the category and required attributes.

No `channels` table is involved — this is pure CSV generation, and the merchant uploads the
file themselves. It is also a rehearsal for Phase 3: if the attribute mapping is wrong here, it
would have been wrong in the API integration too, and this is a much cheaper place to find out.

---

## 6. Non-functional requirements

### 6.1 Targets

| Path | Target |
|---|---|
| Product list, 10k products | p95 < 600ms first byte |
| Variant matrix save, 100 cells | < 2s |
| Image upload → derivative ready | < 15s p95 |
| Catalog export, 10k variants | < 60s, async job |

### 6.2 Scale assumption, year one

Per tenant: 100k variants, 20 concurrent users, 20 GB R2. A single well-indexed PostgreSQL
handles this comfortably. Do not shard and do not pre-optimise.

### 6.3 Availability

**99.5% monthly** on a single VPS — about 3.6 hours a year, which one kernel reboot plus one
bad deploy will consume. 99.9% is not honestly claimable without redundant hosts; do not put it
in a customer contract until PostgreSQL has moved off-box.

**RPO** 5 minutes via WAL archiving. **RTO** 1 hour, and that number is only real once the
restore drill has been run.

### 6.4 Security

- TLS 1.3 only, HSTS, Cloudflare WAF.
- Passwords `argon2id`, 64MB memory, 3 iterations.
- API keys stored as SHA-256 hashes; plaintext shown exactly once at creation.
- Structured logging with a field **allow-list**, so a new field is redacted by default rather
  than leaked by default.
- No customer PII exists in Phase 1 — the first PII arrives with orders in Phase 2. Establish
  the redaction discipline now, while the stakes are low.

### 6.5 Testing

| Layer | Approach |
|---|---|
| Unit | Slugification, matrix diffing, permission checks |
| Integration | Real PostgreSQL via testcontainers. RLS and triggers cannot be meaningfully mocked |
| Tenant isolation | Generated suite over every registered route |
| Migration | Every migration applied to a restored snapshot in CI |

---

## 7. Delivery

| Weeks | Deliverable | Exit criterion |
|---|---|---|
| 1–3 | Local dev services, migration runner, tenancy with RLS | `app_user` owns nothing; `FORCE RLS` on every tenant table |
| 3–5 | Auth, RBAC, API conventions, OpenAPI generation, error envelope | Tenant isolation suite green over every route |
| 5–8 | Brands, categories with the ltree trigger, products, variants | A category move rebases every descendant in one statement |
| 8–10 | Variant matrix editor, media upload and derivatives | 100-cell grid saves in under 2s |
| 10–12 | Marketplace CSV export, user management UI | 10k variants exported in under 60s |
| 10–12 | VPS, Caddy, TLS, CI, `pgBackRest` to R2, pilot onboarding | **A successful restore drill from R2 into a clean box**, then one pilot merchant's real catalog in the system |

**The production box is provisioned last, on purpose.** The application develops against
PostgreSQL and Redis installed directly on the developer's machine — no container, no compose
file, nothing else running — and nothing in weeks 1–10 needs a domain, a certificate or a
reverse proxy. Deferring the box avoids paying for an idle server and avoids deciding the TLS
posture twice. `BACKLOG.md` §M4 holds those items.

**Host services rather than containers, and the versions above rather than older ones.** A dev
machine that already runs PostgreSQL and Redis gains nothing from a second copy of each in
Docker — a published port is no less inspectable than a Unix socket, so the container buys only
another runtime to keep alive. The cost of that choice is that the dev version is whatever the
machine has, which is why the pin moved to PostgreSQL 18 and Redis 8 while there is still no box
and no data to migrate: matching dev to prod deletes a class of bug (a 17-or-18-only construct
reaching a 16 server) that no amount of review reliably catches. Revisit the pin only when the
box exists.

**What that deferral does not buy you is a later restore drill.** It stays where it always was:
before any merchant's real data exists. Provisioning late compresses the window between the box
existing and the pilot depending on it, so treat week 10 as a hard start, not a target.

**Do not start Phase 2 until the restore drill has passed.** Everything after this point is
built on the assumption that merchant data is recoverable.
