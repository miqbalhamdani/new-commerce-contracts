# contracts — source of truth

**Phase 1 · Catalog & Foundation.** This repo defines *what* the system is. `backend/` and
`frontend/` define *how* it is built. Information flows one way: contracts → code. Never the
reverse.

If a contract and an implementation disagree, **the contract is right and the code is a bug** —
unless the contract is wrong, in which case you change the contract first, in its own PR, and
then fix the code.

---

## Files

| File | Answers | Authoritative for |
|---|---|---|
| `01-product.md` | Why this phase exists, scope, screens, journeys + acceptance criteria, architecture, non-functionals | What "done" means for a feature |
| `02-business-rules.md` | Every rule, numbered `BR-xxx`, with its why | What must always be true |
| `03-erd.md` | Tables, columns, indexes, constraints, triggers | The database shape |
| `04-api-spec.md` | Conventions, endpoints, request and response bodies, error codes | The HTTP contract, in prose |
| `openapi.yaml` | The same contract, machine-readable | Code generation in both repos |
| `05-backlog.md` | Every feature, ordered, with status | What to build next |

`03-erd.md` and `04-api-spec.md` are written to be read on their own, without the other docs.

`openapi.yaml` is **hand-authored here**, not generated from backend code. That inversion is the
whole point of this repo: the backend conforms to the contract rather than the contract
documenting whatever the backend happens to do.

`04-api-spec.md` and `openapi.yaml` must agree. If you change one, change the other in the same
commit. CI fails the PR otherwise.

---

## What does NOT belong here

- Migrations. `03-erd.md` describes the schema; `backend/db/migrations/` implements it.
- Go or TypeScript source of any kind.
- Component designs, CSS, copy decks.
- Deployment scripts, secrets, environment config.
- Anything Phase 2, 3 or 4. Those phases have their own contracts, added when their phase starts.

If you are tempted to put implementation detail here to "keep it together", put it in the code
repo and link to it from here instead.

---

## How the code repos consume this

Both `backend/` and `frontend/` vendor this repo as a **git submodule at `contracts/`**, pinned
to a tag.

```
contracts/  v1.4.0  ← backend pins this
contracts/  v1.4.0  ← frontend pins this
```

Pinning to a tag rather than tracking `main` is deliberate. During a contract change the two
repos are briefly on different versions, and you need to know which — a floating submodule turns
that into a mystery.

### Changing a contract

```
1. PR here.        Change the doc(s) AND openapi.yaml together.
                   Add or update the BACKLOG row. Bump the version in VERSION.
2. Tag.            v1.4.0 → v1.5.0. Breaking changes bump the minor in Phase 1
                   (there is no v1 public API yet); after launch they bump the major.
3. Backend PR.     Bump the submodule, regenerate, implement, tests green.
4. Frontend PR.    Bump the submodule, regenerate the client, implement.
```

A contract change with no consuming PR within a week is a smell — either the change was
speculative, or someone forgot. `05-backlog.md` is where that is tracked.

---

## Invariants

These hold across every phase. Changing one is a breaking change to both repos and needs an
explicit decision, not a PR comment. Full text in `02-business-rules.md` §1.

- **Tenancy** (BR-001–004). Every tenant-owned table carries `tenant_id` with `ENABLE` + `FORCE ROW
  LEVEL SECURITY`. A denormalised `tenant_id` on a child table is protected by a composite foreign
  key.
- **Keys** are UUID v7, generated application-side (BR-005).
- **Money** is `{"amount": <bigint minor units>, "currency": "IDR"}` (BR-006).
- **Time** is `timestamptz` in UTC, RFC 3339 with offset on the wire (BR-007).
- **Server-managed fields** (`id`, `tenant_id`, `version`, `created_at`, `updated_at`, `path`,
  `slug`) sent by a client are `422`, on create and update (BR-008).
- **Omitted vs `null`** (BR-009). Create: omitted takes the default, `null` is `422`. `PATCH`:
  omitted is unchanged, `null` clears a nullable field.
- **Concurrency** is `version` + `If-Match` on every `PATCH` to a versioned resource: products,
  variants, brands, categories (BR-010).
- **There is no quantity column on `variants`, in any phase** (BR-015).

---

## Phase 1 scope guard

Phase 1 has **no stock, no orders, no marketplace channels**. If a backlog item, an endpoint or
a screen implies any of them, it is out of scope and belongs to a later phase.

The catalog CSV export (`GET /v1/products/export`) is the deliberate exception that gives Phase 1
standalone value without needing channels. It generates a file the merchant uploads themselves.

---

## Working in this repo

- **Read before writing.** `02-business-rules.md` §1 (platform) and `03-erd.md` §2 (conventions)
  explain most "why is it like this" questions.
- **A rule's text lives once, in `02-business-rules.md`.** Every other doc cites `BR-xxx` and does
  not restate it. A new rule gets the next free id in its area; ids are never reused.
- **No edit history in the prose** ("an older version said…"). Git has the history.
- **Prose is part of the contract.** The paragraphs explaining *why* a decision was made are
  what stop the next person undoing it. Do not strip them to make a doc shorter.
- **One concern per PR.** A schema change and an endpoint change in one PR cannot be reviewed
  properly and cannot be reverted separately.
- **Update `05-backlog.md` in the same PR** that changes scope. A backlog that lags the contracts is
  worse than no backlog.
