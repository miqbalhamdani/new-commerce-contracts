# Phase 1 — Catalog & Foundation · Product

**Ships** Weeks 1–12 · **Status** Production, used by pilot merchants
**Depends on** nothing · **Depended on by** Phases 2, 3 and 4

What this phase is, who uses it, what they do with it, and how we know each part is done. Rules are
cited as `BR-xxx` and live in `02-business-rules.md`. The schema is `03-erd.md`, the HTTP contract
is `04-api-spec.md`, and build order and status are in `05-backlog.md`.

---

## 1. What this phase is

A product master: the merchant's single source of truth for what they sell (products, variants,
brands, categories, images). It has a real team model on top and exports CSV in the formats the
marketplaces accept.

It also lays every piece of foundation the later phases assume: tenancy, authentication,
permissions, the audit posture, the API conventions and the deployment. Roughly half the work in
this phase is never seen by a user, and it is the reason Phases 2–4 can be built quickly.

### Why it is worth releasing on its own

Most Indonesian merchants keep product data in a spreadsheet that is copied by hand into each
marketplace's seller centre. That spreadsheet goes stale, contradicts itself between channels and
has no history. Phase 1 replaces it with something that has structure, roles, an image library and
an export that matches what Shopee and Tokopedia actually accept for bulk upload.

That is useful the day it ships, and it seeds the catalog every later phase works on. A merchant
who spent two weeks getting 3,000 SKUs clean in Phase 1 is still there when Phase 3 connects their
channels.

---

## 2. Scope

### In this phase

Products, variants and the variant matrix · brands with marketplace brand ids · categories in
independent trees · product imagery · team, roles and API keys · marketplace CSV export · the
onboarding wizard.

### Deliberately not in this phase

- **No stock.** No quantities, locations or reservations; stock is unlimited (BR-015).
- **No orders.** Nothing is sold through it yet.
- **No marketplace connection.** Export is a CSV the merchant uploads themselves.
- **No bulk edit or CSV import.** Phase 1 is create-and-edit only.

Tell a pilot merchant all four before onboarding them. Users will ask for these in week one; have
the answer ready:

| Request | Answer | Arrives |
|---|---|---|
| "Where do I set stock?" | There is no stock yet. Manage quantity on the marketplace as you do today. | Phase 4 |
| "Can I import my spreadsheet?" | Not yet: create products here, or wait a phase. | Phase 2 |
| "Can I edit 200 products at once?" | Not yet. | Phase 2 |
| "Does it sync to Shopee?" | Not yet. Export a CSV and upload it yourself. | Phase 3 |
| "Where are my orders?" | Not yet. | Phase 2 |

**The stock question is the one that matters.** A merchant who believes Phase 1 manages inventory
will conclude the product is broken rather than early. Say it in the sales conversation, say it
again in onboarding, and put it in the empty state of the product list.

---

## 3. Users

A merchant's owner or admin sets the system up, and one or two merchandising or operations staff
work in it daily. Warehouse staff have no reason to open it until Phase 4. Roles and what each may
do: BR-023.

---

## 4. Screens

| Screen | Primary user | Purpose |
|---|---|---|
| Sign in / accept invitation | All | Entry |
| Onboarding wizard | Owner | Tenant setup, first brand, first category tree |
| Product list | Ops | The daily workspace. Search, filter, bulk select |
| Product editor | Ops | Title, description, brand, attributes, categories, media |
| **Variant matrix editor** | Ops | The screen that sets this product apart. A grid of options × values |
| Category manager | Admin | One tree per `kind`; drag to move, rename |
| Brand manager | Admin | Brands and their marketplace brand ids |
| Media library | Ops | Per-product imagery: reorder, assign to a variant |
| Team & roles | Owner/Admin | Invite, assign role, disable |
| API keys | Owner/Admin | Issue, view prefix, revoke |
| Export | Ops | Pick a marketplace template, download the CSV |

A screen the user lacks permission for is not in their navigation at all (BR-025).

---

## 5. Journeys

### 5.1 First-run onboarding

**Actor** Owner, first login after signup. **Goal:** get from empty to a real catalog.

```
1. Accept invitation → set password → land on an empty product list
2. Onboarding wizard (skippable, resumable):
     a. Confirm business name, timezone (Asia/Jakarta), currency (IDR)
     b. Create the first brand, with an optional "I sell on Shopee/Tokopedia" step
        that captures channel_brand_ids while the context is fresh
     c. Create a starter category tree, or accept a suggested one for their vertical
     d. Invite one teammate
3. Land on "Create your first product" with a visible next action
```

**Acceptance criteria**
- The wizard can be skipped at any step and resumed from a banner on the product list.
- A merchant who skips it entirely can still create a product; brand and category are optional
  (BR-030).
- Timezone and currency are pre-filled without the user choosing (BR-029).
- The brand step captures `channel_brand_ids` (BR-030).

### 5.2 Create a product with variants

**Actor** Ops. **Goal:** a sellable product with a full size/colour grid. **Target:** under 3
minutes for a 15-variant product.

```
Product list → "New product"
  ↓
Product editor
  · Title, description
  · Brand (searchable select, "＋ create" inline)
  · Categories (one picker per kind)
  · Attributes (key/value; suggested keys by category)
  · Media (drag-drop, uploads direct to R2 with per-file progress)
  ↓
"Add options" → define option_names, e.g. Colour and Size
  ↓
Variant matrix editor
  · Enter values per option: Black, White / S, M, L, XL, XXL
  · Grid renders 2 × 5 = 10 cells
  · Fill SKU, price, weight per cell
  · Paste a column from Excel · Fill-down · Bulk price ±%
  ↓
Save  →  one PUT /variant-matrix  →  10 variants created
  ↓
Set status Active  →  publish check runs
```

If the publish check (BR-038) fails, every failure is listed with a link to the cell at fault and
the product stays `draft`.

**Acceptance criteria**
- A 2 × 5 grid renders 10 cells and saves in one request in under 2 seconds (BR-041).
- Pasting a 10-row column from Excel fills 10 cells without a page reload.
- A duplicate SKU fails **that row only**; the other nine still save, and the failed cell is
  highlighted with the clashing product named (BR-039, BR-041).
- Bulk price adjust (± amount or %) shows a preview before applying.
- Uploading a 5 MB image shows progress and never blocks the form (BR-051, BR-052).
- Leaving the editor with unsaved changes asks for confirmation before navigating away.
- Activating a product that fails the publish check lists every failure and leaves it `draft`
  (BR-038).
- A product can sit in categories of several kinds at once (BR-031).

### 5.3 Reorganise the category tree

**Actor** Admin. **Goal:** move "Jackets" from Outerwear to a new Technical Outerwear parent.

```
Category manager → select kind: Category
  ↓
Drag "Jackets" onto "Technical Outerwear"
  ↓
Confirm dialog: "Move Jackets and its 4 subcategories? 128 products will keep
                 their assignments."
  ↓
Save → one PATCH → every descendant's path rewritten in one statement
```

**Acceptance criteria**
- The confirm dialog states that product assignments are unaffected, with counts (BR-033).
- Moving a node with 200 descendants completes in under 1 second (BR-032).
- Dragging a parent onto its own descendant is rejected by the client and, if forced, by the
  database with a clear message (BR-034).
- Two categories named "Jackets" under different parents both work (BR-035).
- Renaming "Outerwear" leaves all product assignments intact (BR-033).
- Deleting a category with children or products is refused with a count of what blocks it
  (BR-036).

### 5.4 Export for a marketplace

**Actor** Ops. **Goal:** upload 400 products to Shopee without retyping them.

```
Export → choose template: Shopee
       → filter: status = Active, category = Apparel
       → Generate
  ↓
Async job, progress shown
  ↓
"412 products ready" → Download CSV
  ↓
Merchant uploads it to Shopee Seller Centre themselves
```

**Acceptance criteria**
- 10,000 variants export in under 60 seconds (BR-060).
- Products with missing mappings don't block the export; they are listed, grouped by what is
  missing (BR-062).
- The download link expires after 15 minutes and can be regenerated (BR-063).
- The CSV opens in Excel with Indonesian locale settings without mangling prices (BR-064).

### 5.5 Invite a teammate

**Actor** Owner. **Goal:** give a merchandiser access without giving away billing.

```
Team & roles → Invite → email + role (ops)
  ↓
Invitation email → Accept → set password → lands on the product list
  ↓
The ops user sees Products, Categories, Brands, Media, Export.
They do NOT see Team, API keys or billing.
```

**Acceptance criteria**
- An `ops` user gets `403` naming the required permission on any user-management endpoint (BR-024),
  and the navigation doesn't show the screen at all (BR-025).
- Disabling a user signs them out within 15 minutes at worst (BR-027).
- An invitation link expires after 7 days and can be resent (BR-026).
- A `viewer` can't save anything anywhere; save buttons are absent, not merely disabled (BR-025).

---

## 6. Architecture

### 6.1 Shape

One Go module, one deployable image, three entrypoints. It is a modular monolith, not
microservices: the domain packages are separated by import rules rather than network calls, so
pulling a service out later is mechanical work rather than archaeology.

```
cmd/api       HTTP API. Serves the Next.js front end and third-party integrators.
cmd/worker    Queue consumer. In Phase 1: image derivative generation and CSV export only.
cmd/migrate   Schema migrations. Runs to completion and exits.
```

### 6.2 Deployment: a single VPS

Front end and back end on one box. Starting size: **8 vCPU / 16 GB / NVMe**, Ubuntu LTS, Docker
Compose.

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

Two API replicas are not for throughput: they let a deploy drain one container at a time.

**What one box makes your responsibility.** Each of these would otherwise be a managed service's
job, and each is a way to lose a merchant's data:

- **Backups.** `pgBackRest` or `wal-g` to R2: nightly base backup plus continuous WAL archiving.
  **Restore-test it before the first pilot merchant**, not after. This is Phase 1's single largest
  risk and an exit criterion, not a nice-to-have.
- **Resource limits.** Set `cpus` and `mem_limit` per service in Compose, or an image-processing
  burst in the worker starves PostgreSQL and stalls the whole box.
- **PostgreSQL tuning for a shared box.** `shared_buffers` ≈ 25% of RAM,
  `effective_cache_size` ≈ 50%, `max_connections` = 100 with hard pool caps in pgx.
- **Disk headroom.** Alert at 70%.

**One origin, two processes.** Caddy serves the Next.js app at `/` and proxies `/v1/*` to
`cmd/api` on the same domain, so the browser only ever talks to one origin. That is what lets the
refresh token be an ordinary `SameSite=Lax` cookie with no CORS anywhere in the system. Local
development reproduces it with a Next.js rewrite rather than by relaxing anything on the API: an API
that has to know about browser origins can get them wrong.

**When to move off the box.** PostgreSQL first, because it is the component whose failure loses
data. Then the worker. Neither needs a code change, only new connection strings.

### 6.3 Component choices

| Concern | Choice | Why |
|---|---|---|
| Router | `chi` | Stdlib-compatible `http.Handler`, no framework lock-in |
| DB access | `pgx/v5` + `sqlc` | Typed queries generated from real SQL. RLS and row locking need SQL you control |
| Migrations | `golang-migrate` | Plain up/down SQL, reviewable in a PR |
| Queue | Redis Streams | Barely needed in Phase 1, but setting it up now avoids a retrofit in Phase 3 |
| Object storage | Cloudflare R2 | Zero egress, S3-compatible. Product imagery is most of the stored bytes |
| Front end | Next.js 15 App Router, Tremor | Server Components for dense list views; client components only for the grid editors |
| Auth | JWT access (15 min) + rotating refresh, `argon2id` | A short access token keeps the RLS context fresh |
| Observability | OpenTelemetry | Set up in Phase 1 so Phase 3's webhook path is traceable from day one |

### 6.4 Tenancy guard rails

The rules are BR-001 to BR-004. These are the checks that keep them true:

- **Migration test.** CI lists `information_schema.tables` and fails if any table with a
  `tenant_id` column lacks an enabled RLS policy. A new table without one can't merge.
- **Isolation test.** Every registered route is exercised with two seeded tenants; tenant A's token
  must return zero of tenant B's rows.
- **No `pool.Query` outside `internal/db`**, enforced by an import-boundary lint rule.
- **Composite indexes lead with `tenant_id`.** RLS adds that predicate to every query; an index
  that can't serve it is dead weight.

---

## 7. Non-functional requirements

### 7.1 Targets

| Path | Target |
|---|---|
| Product list, 10k products | p95 < 600ms first byte |
| Variant matrix save, 100 cells | < 2s |
| Image upload → derivative ready | < 15s p95 |
| Catalog export, 10k variants | < 60s, async job |

### 7.2 Scale assumption, year one

Per tenant: 100k variants, 20 concurrent users, 20 GB in R2. A single well-indexed PostgreSQL
handles this comfortably. Don't shard and don't optimise ahead of need.

### 7.3 Availability

**99.5% monthly** on a single VPS: about 3.6 hours a month, which one kernel reboot plus one bad
deploy will use up. 99.9% can't honestly be claimed without redundant hosts; don't put it in a
customer contract until PostgreSQL has moved off the box.

**RPO** 5 minutes via WAL archiving. **RTO** 1 hour, and that number is only real once the restore
drill has been run.

### 7.4 Security

TLS 1.3 only, HSTS, Cloudflare WAF. Passwords, sessions and API keys: BR-022, BR-028. Logging:
BR-013.

### 7.5 Testing

| Layer | Approach |
|---|---|
| Unit | Slugification, matrix diffing, permission checks |
| Integration | Real PostgreSQL via testcontainers. RLS and triggers can't be meaningfully mocked |
| Tenant isolation | Generated suite over every registered route |
| Migration | Every migration applied to a restored snapshot in CI |
