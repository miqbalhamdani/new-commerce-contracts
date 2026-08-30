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
| `tdd.md` | Why this phase exists, architecture, tenancy, domain rules, non-functionals | Architecture and invariants |
| `erd.md` | Tables, columns, indexes, constraints, triggers | The database shape |
| `API spec.md` | Conventions, endpoints, payloads, error codes | The HTTP contract, in prose |
| `openapi.yaml` | The same contract, machine-readable | Code generation in both repos |
| `flows.md` | Screens, journeys, acceptance criteria | What "done" means for a feature |
| `BACKLOG.md` | Every feature, ordered, with status | What to build next |

`openapi.yaml` is **hand-authored here**, not generated from backend code. That inversion is the
whole point of this repo: the backend conforms to the contract rather than the contract
documenting whatever the backend happens to do.

`API spec.md` and `openapi.yaml` must agree. If you change one, change the other in the same
commit. CI fails the PR otherwise.

---

## What does NOT belong here

- Migrations. `erd.md` describes the schema; `backend/db/migrations/` implements it.
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
speculative, or someone forgot. `BACKLOG.md` is where that is tracked.

---

## Invariants

These hold across every phase. Changing one is a breaking change to both repos and needs an
explicit decision, not a PR comment.

- **Tenancy.** Every tenant-owned table carries `tenant_id` with `ENABLE` + `FORCE ROW LEVEL
  SECURITY`. A denormalised `tenant_id` on a child table is protected by a composite foreign key.
- **Keys** are UUID v7, generated application-side. Never a sequential integer in an API.
- **Money** is `{"amount": <bigint minor units>, "currency": "IDR"}`. Never a float, never a
  decimal string.
- **Time** is `timestamptz` in UTC, RFC 3339 with offset on the wire. Tenant timezone is applied
  at render time only.
- **Server-managed fields** — `id`, `tenant_id`, `version`, `created_at`, `updated_at`, `path` —
  are never accepted from a client.
- **Omitting a field takes its default. Sending `null` is a validation error.** These are not
  the same thing.
- **Concurrency** is `version` + the `If-Match` header on every `PATCH`.
- **There is no quantity column on `variants`, in any phase.** Stock is a property of
  (variant, location) and arrives in Phase 4 as an append-only ledger. See `erd.md` §4.2.

---

## Phase 1 scope guard

Phase 1 has **no stock, no orders, no marketplace channels**. If a backlog item, an endpoint or
a screen implies any of them, it is out of scope and belongs to a later phase.

The catalog CSV export (`GET /v1/products/export`) is the deliberate exception that gives Phase 1
standalone value without needing channels. It generates a file the merchant uploads themselves.

---

## Working in this repo

- **Read before writing.** `tdd.md` §3 (tenancy) and `erd.md` §2 (conventions) explain most
  "why is it like this" questions.
- **Prose is part of the contract.** The paragraphs explaining *why* a decision was made are
  what stop the next person undoing it. Do not strip them to make a doc shorter.
- **One concern per PR.** A schema change and an endpoint change in one PR cannot be reviewed
  properly and cannot be reverted separately.
- **Update `BACKLOG.md` in the same PR** that changes scope. A backlog that lags the contracts is
  worse than no backlog.
