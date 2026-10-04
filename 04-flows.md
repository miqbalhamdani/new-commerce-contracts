# Phase 1 — Catalog & Foundation · User Flows

**Who uses this phase.** A merchant's owner or admin sets it up; one or two merchandising or
operations staff live in it daily. Warehouse staff have no reason to open it until Phase 4.

---

## 1. Screens

| Screen | Primary user | Purpose |
|---|---|---|
| Sign in / accept invitation | All | Entry |
| Onboarding wizard | Owner | Tenant setup, first brand, first category tree |
| Product list | Ops | The daily workspace. Search, filter, bulk select |
| Product editor | Ops | Title, description, brand, attributes, categories, media |
| **Variant matrix editor** | Ops | The differentiating screen. Grid of options × values |
| Category manager | Admin | Tree per `kind`, drag to reorder, rename, move |
| Brand manager | Admin | Brands and their marketplace brand-id mappings |
| Media library | Ops | Per-product imagery, reorder, assign to variant |
| Team & roles | Owner/Admin | Invite, assign role, disable |
| API keys | Owner/Admin | Issue, view prefix, revoke |
| Export | Ops | Pick a marketplace template, download CSV |

---

## 2. Journey — first-run onboarding

**Actor** Owner, first login after signup. **Goal** get from empty to a real catalog.

```
1. Accept invitation → set password → land on an empty product list
2. Onboarding wizard (skippable, resumable):
     a. Confirm business name, timezone (Asia/Jakarta), currency (IDR)
     b. Create the first brand — with an optional "I sell on Shopee/Tokopedia" step
        that captures channel_brand_ids while the context is fresh
     c. Create a starter category tree, or accept a suggested one for their vertical
     d. Invite one teammate
3. Land on "Create your first product" with a visible next action
```

**Why the wizard captures `channel_brand_ids` at signup.** It is a two-minute task the owner
can do while thinking about their brand, and a two-hour archaeology exercise six months later
when Phase 3 needs it and nobody remembers their Shopee brand id.

**Acceptance criteria**
- The wizard is skippable at every step and resumable from a banner on the product list.
- A merchant who skips it entirely can still create a product; brand and category are optional.
- Timezone defaults to `Asia/Jakarta` and currency to `IDR` without the user choosing.

---

## 3. Journey — create a product with variants

**Actor** Ops. **Goal** a sellable product with a full size/colour grid. **Target** under 3
minutes for a 15-variant product.

```
Product list → "New product"
  ↓
Product editor
  · Title, description
  · Brand (searchable select, "＋ create" inline)
  · Categories (multi-select across trees — one per kind)
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
Save  →  one PUT /variant-matrix  →  10 variants created in one transaction
  ↓
Set status Active  →  publish check runs
```

### The publish check

Moving from `draft` to `active` runs a validation that is deliberately **not** a table
constraint, so drafting stays frictionless:

- Every variant has a SKU. *(A null SKU cannot be bulk-updated in Phase 2 or auto-mapped to a
  marketplace listing in Phase 3 — this is where that is caught.)*
- Every variant has a price greater than zero.
- At least one image.
- At least one category of kind `category`.

Failures are listed with a jump link to the offending cell. The product stays in `draft`.

**Acceptance criteria**
- A 2 × 5 grid renders 10 cells and saves in one request in under 2 seconds.
- Pasting a 10-row column from Excel fills 10 cells without a page reload.
- A duplicate SKU fails **that row only**; the other nine still save, and the failed cell is
  highlighted with the conflicting product named.
- Uploading a 5 MB image shows progress and never blocks the form.
- Leaving the editor with unsaved grid changes prompts before navigating away.

---

## 4. Journey — reorganise the category tree

**Actor** Admin. **Goal** move "Jackets" from Outerwear to a new Technical Outerwear parent.

```
Category manager → select kind: Category
  ↓
Drag "Jackets" onto "Technical Outerwear"
  ↓
Confirm dialog: "Move Jackets and its 4 subcategories? 128 products will keep
                 their assignments."
  ↓
Save → one PATCH → trigger rebases every descendant path in one statement
```

**What the confirm dialog must say, and why.** Users assume a category move re-tags products
and are afraid of it. It does not — `product_categories` references `category_id`, never
`path`. Saying so explicitly is the difference between a feature people use and one they avoid.

**Acceptance criteria**
- Moving a node with 200 descendants completes in under 1 second.
- Dragging a parent onto its own descendant is rejected client-side and, if forced, by the
  database with a clear message.
- Two categories named "Jackets" under different parents both work.
- Renaming "Outerwear" leaves all product assignments intact.
- Deleting a category with children or products is refused with a count of what blocks it.

---

## 5. Journey — export for a marketplace

**Actor** Ops. **Goal** upload 400 products to Shopee without retyping them.

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

If products are missing a required mapping — no `channel_brand_ids.shopee` on the brand, or no
`attributes.channel.shopee.category_id` — the export **still generates**, and the response
names what was left blank so the merchant can fix it in one pass rather than discovering it
row by row inside Shopee's uploader.

**Acceptance criteria**
- 10,000 variants export in under 60 seconds.
- The download link expires after 15 minutes and can be regenerated.
- The response lists products with incomplete channel mapping, grouped by what is missing.
- The CSV opens in Excel with Indonesian locale settings without mangling prices.

---

## 6. Journey — invite a teammate

**Actor** Owner. **Goal** give a merchandiser access without giving away billing.

```
Team & roles → Invite → email + role (ops)
  ↓
Invitation email → Accept → set password → lands on the product list
  ↓
The ops user sees Products, Categories, Brands, Media, Export.
They do NOT see Team, API keys or billing.
```

**Acceptance criteria**
- An `ops` user gets `403` with the required permission named in `detail` on any user-management
  endpoint, and the navigation does not show the screen at all.
- Disabling a user signs them out within 15 minutes at worst, immediately if the revocation
  list is consulted.
- An invitation link expires after 7 days and can be resent.
- A `viewer` cannot save anything anywhere; save buttons are absent, not merely disabled.

---

## 7. What users will ask for that this phase does not do

Have an answer ready before pilot onboarding. Each of these will come up in week one.

| Request | Answer | Arrives |
|---|---|---|
| "Where do I set stock?" | There is no stock yet. Manage quantity on the marketplace as you do today. | Phase 4 |
| "Can I import my spreadsheet?" | Not yet — create products here, or wait a phase. | Phase 2 |
| "Can I edit 200 products at once?" | Not yet. | Phase 2 |
| "Does it sync to Shopee?" | Not yet. Export CSV and upload it yourself. | Phase 3 |
| "Where are my orders?" | Not yet. | Phase 2 |

**The stock question is the one that matters.** A merchant who believes Phase 1 manages
inventory will conclude the product is broken rather than early. Say it in the sales
conversation, say it again in onboarding, and put it in the empty state of the product list.
