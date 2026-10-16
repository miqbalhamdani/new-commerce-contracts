# Runbook: ACL Cosmetics legacy catalog → new-commerce (production)

One-time move of the old Laravel shop's catalog into one existing production shop, through the
admin `/v1` API. Script: `import_acl.py` (this folder). Source: `~/Downloads/acl-cosm-backup/`.

| | |
|---|---|
| Moves | 3 brands, 42 categories (tree kept), 116 products, 418 variants, 364 images |
| Skips | deleted rows, old admin users/oauth, contact messages, `customs` top-product lists, banners/logos/icons, 164 unreferenced image files |
| Prices | every variant **Rp 1** (`regular_price: 100`): no prices in the legacy data |
| Weights | from the size text (`600 ml`→600 g, `2 kg`→2000 g, else 100 g). Fix in admin |
| Status | products published (`active`) at the end; one that fails BR-038 stays `draft` and is reported |
| Duration | ~15 min (admin rate limit is 100 req/min per user; the script waits on `429`) |
| Re-runnable | yes: `state.json` records each finished step; a re-run continues where it stopped |

Known data fixes the script makes (both printed in its report):
- `body-peeling-honey` is the slug of two live products → the second becomes `body-peeling-honey-2`.
- SKU `77251` is on two products → the one on `conditioner-aromatic` becomes `77251-dup`. **Fix by hand.**

---

## 0. Before the day

- [ ] Python 3.9+ on the machine that runs it (stdlib only, nothing to install).
- [ ] The backup folder is complete: `acl_cosm_16102026.sql`, `product/`, `temp/`.
- [ ] Production: the target shop exists, and you have an **owner or admin** login for it
      (needs `brands:write`, `categories:write`, `products:write`, `variants:write`).
- [ ] The shop's catalog is empty, or at least holds none of the legacy SKUs.
- [ ] Production API base URL is known: `https://api.<domain>/v1`.

## 1. Dry run (no API calls)

```bash
cd ~/escape/new-commerce/new-commerce-contracts/acl-migration
python3 -I import_acl.py --backup ~/Downloads/acl-cosm-backup --dry-run
```

Expect exactly:
```
brands 3, categories 42, products 116, variants 418, images 364
note: slug body-peeling-honey -> body-peeling-honey-2 (product 25)
note: sku 77251 -> 77251-dup (product conditioner-aromatic, fix in admin)
```
Any `missing image …` exit → the backup folder is incomplete; stop.

## 2. Rehearsal on a local stack (recommended)

Host services, from `new-commerce-api/`:
```bash
brew services start postgresql@18 redis minio
make db-create migrate storage-init
make dev-seed            # owner@example.com / development-password (DEV_SEED_EMAIL, DEV_SEED_PASSWORD)
make dev                 # terminal 1: API on :8080
make worker              # terminal 2: image derivatives
```
Then, from this folder, with a **separate state file** (a state file is tied to one API URL):
```bash
ACL_EMAIL=owner@example.com ACL_PASSWORD=development-password python3 -I import_acl.py \
  --backup ~/Downloads/acl-cosm-backup --api http://localhost:8080/v1 --state state.local.json
```
Pass: ends with `published 116/116` and exit code 0. Look at a few products in the admin
(variants, images, categories), then try a re-run: it should finish at once with nothing new.

## 3. Production run

### 3.1 Backup first (on the VPS, in `deploy/`)
Archiving does **not** undo an import (slugs and SKUs stay reserved), so the database dump is
the only real rollback.
```bash
docker compose exec -T postgres pg_dump -U postgres -Fc new_commerce > ~/pre-acl-import-$(date +%F).dump
ls -lh ~/pre-acl-import-*.dump        # non-zero size
```

### 3.2 Check the worker is up
```bash
docker compose ps worker              # running / healthy
docker compose logs -f --since 1m worker   # leave open during the run
```

### 3.3 Run (from your machine)
```bash
cd ~/escape/new-commerce/new-commerce-contracts/acl-migration
export ACL_EMAIL='<owner email>'
read -s ACL_PASSWORD && export ACL_PASSWORD     # keeps it out of shell history
python3 -I import_acl.py --backup ~/Downloads/acl-cosm-backup --api https://api.<domain>/v1
```
- Progress prints one line per product: `[n/116] <slug>`; `!` lines are per-product errors,
  and the run carries on.
- Avoid heavy admin use with the same account meanwhile: it shares the 100 req/min budget.
- Interrupted (Ctrl-C, network, laptop sleep)? Run the same command again.

### 3.4 Read the report
```
published N/116
product <legacy id>: <error or slug note>
```
Exit code 0 = all published. Non-zero = see §5, fix, re-run (finished steps are skipped).

## 4. Verify

- [ ] Admin → Products: 116 products, status Active (minus any listed in the report).
- [ ] Admin → Brands: ACL, Herbaulia, Refani. Categories: Hair Care / Body Care / Skin Care /
      Cosmetic / Body Spa with their children.
- [ ] Spot-check 3 products, e.g. `moisturizer-hand-gel` (6 variants, each with its image),
      `creambath-coklat` (images taken from `temp/`), `acl-two-way-cake` (`Variant` option).
- [ ] Images have derivatives: worker log shows `image_derivatives` jobs finishing; the product
      page in admin shows thumbnails. Allow a few minutes for 364 images.
- [ ] Storefront `/products/<legacy-slug>` opens for a couple of old URLs.
- [ ] Keep `state.json` and the run output: they map legacy ids → new ids.

## 5. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `401` at start | Wrong email/password, or `--api` missing `/v1`. |
| `403 … <permission>` | The account's role lacks that permission; use an owner. |
| `422 … sku` / matrix row `error` | SKU already exists in the shop. Remove/rename the clashing variant in admin, re-run. |
| Product left draft, `422` on publish | BR-038 not met (no image, category, SKU, price or weight). Fix in admin and publish there, or fix and re-run. |
| `kept <slug>` slug note | The legacy slug was already taken; product keeps the generated one. Change it in admin if the old URL matters. |
| `… belongs to <url>; use another --state` | You pointed a state file at a different API. Use `--state` with a new file name. |
| Images never get thumbnails | Worker down or failing: `docker compose logs worker`. Uploads are already recorded; derivatives run when it is back. |
| Script killed mid-image | Re-run. An image confirmed twice is the same image (no duplicates). |

## 6. Rollback

Only if the import must be undone entirely (on the VPS, in `deploy/`):
```bash
docker compose stop api-1 api-2 worker
docker compose exec -T postgres pg_restore -U postgres -d new_commerce --clean --if-exists \
  < ~/pre-acl-import-<date>.dump
docker compose start api-1 api-2 worker
```
Any orders, edits or sign-ups made after the backup are lost too, so roll back promptly or not
at all. Uploaded image objects stay in R2 (`<tenant>/products/…`); harmless, delete if you care.
Then delete `state.json` before any new attempt.

## 7. After the migration

- [ ] Set real prices on all 418 variants (all are Rp 1 now).
- [ ] Correct shipping weights where the size-based guess is wrong (`ml`≈`g`, colour/scent variants = 100 g).
- [ ] Fix SKU `77251-dup` on `conditioner-aromatic`.
- [ ] Banners, logo, certification and "keunggulan kami" images belong to the storefront web app.
- [ ] Recreate the 4 "top product" lists (Hair Care, Body Care, Skin Care, Hair Styling) if the
      storefront needs them, e.g. as `collection` categories.
