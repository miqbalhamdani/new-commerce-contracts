# Fase 1 — Catalog & Foundation · Spesifikasi API

**Konvensi di §1 berlaku untuk semua fase.** Fase berikutnya merujuk bagian ini, tidak menulisnya
ulang. Setiap endpoint mencantumkan izin yang dibutuhkan (matriks di §3) dan aturan yang
ditegakkannya (`BR-xxx`, lihat `02-business-rules.md`). `openapi.yaml` adalah salinan yang terbaca
mesin; sebuah path muncul di sana saat item backlog yang membangunnya selesai. Untuk apa pun yang
dijelaskan keduanya, kedua file harus selaras: ubah salah satu, ubah juga yang lain, dalam commit
yang sama.

---

## 1. Konvensi

| Aspek | Aturan |
|---|---|
| Base | `https://api.{domain}/v1`: versi ada di path; perubahan yang merusak kompatibilitas mendapat `/v2` |
| Auth (UI) | `Authorization: Bearer <JWT>`, access token 15 menit, refresh berotasi di cookie httpOnly (BR-022) |
| Auth (integrator) | `Authorization: Bearer <api_key>`, terbatas pada izin key tersebut (BR-028) |
| Tenant | Diturunkan dari token, **tidak pernah** diterima dari header, query, atau body (BR-003) |
| Content type | `application/json; charset=utf-8` |
| Penulisan nama | `snake_case` di JSON, sama dengan database, jadi tidak ada lapisan penerjemah yang bisa melenceng |
| Id | String UUID v7 (BR-005) |
| Uang | `{"amount": 2000000, "currency": "IDR"}`: integer dalam satuan terkecil (BR-006) |
| Waktu | RFC 3339 dengan offset, selalu UTC (BR-007) |
| Field yang dikelola server | `id`, `tenant_id`, `version`, `created_at`, `updated_at`, `path`, `slug`: mengirim salah satunya menghasilkan `422`, saat create maupun update (BR-008) |
| Dihilangkan vs `null` | Create: field yang dihilangkan memakai default, `null` menghasilkan `422`. `PATCH`: field yang dihilangkan tidak berubah, `null` mengosongkan field yang nullable (BR-009) |
| Konkurensi | `If-Match: <version>` pada setiap `PATCH` ke produk, varian, brand, atau kategori, dan pada `PUT` matriks varian; versi basi → `409` (BR-010) |
| Respons | Setiap field selalu ada; field opsional yang kosong bernilai `null`. Referensi diperluas menjadi `{id, name}` |
| Koleksi | `{ "data": [...], "next_cursor": "…" }`. `next_cursor` bernilai `null` di halaman terakhir. Koleksi tanpa paginasi tidak menyertakannya. `GET /v1/roles` satu-satunya array polos |
| Paginasi | Hanya cursor: `?limit=50&cursor=<opaque>`, `limit` 1–200. Tidak ada `offset`: offset yang dalam berarti sequential scan |
| Pengurutan | `?sort=-created_at` (awalan `-` untuk menurun), daftar yang diizinkan ditentukan per endpoint |
| Penyaringan | Parameter query eksplisit, bukan query DSL |
| Hapus | `DELETE` katalog mengarsipkan dan mengembalikan `204` (BR-012) |

### 1.1 Error

Setiap error berbentuk RFC 9457 `application/problem+json` (BR-011):

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

Kodenya adalah segmen terakhir `type`. Entri `errors[]` selalu membawa `field`
dan boleh membawa apa pun yang dibutuhkan kegagalan tersebut.

| Kode | Status | Kapan | BR |
|---|---|---|---|
| `validation_failed` | 422 | Body rusak, validasi gagal, field yang dikelola server dikirim, `null` di tempat yang tidak boleh, `If-Match` tidak ada | 008, 009 |
| `publish_check_failed` | 422 | `draft → active` gagal publish check; satu entri `errors[]` per kegagalan | 038 |
| `unauthenticated` | 401 | Kredensial tidak ada, kedaluwarsa, atau tidak sah; setiap login yang gagal | 021 |
| `permission_denied` | 403 | `detail` menyebut izin yang dibutuhkan | 024 |
| `not_found` | 404 | Resource tidak ada di tenant ini, termasuk baris milik tenant lain | 011 |
| `version_conflict` | 409 | `If-Match` basi | 010 |
| `duplicate_sku` | 409 | SKU sudah dipakai di tenant ini; `detail` menyebut produk yang memakainya | 039 |
| `category_in_use` | 409 | Menghapus kategori yang punya anak atau produk | 036 |
| `rate_limited` | 429 | Melewati batas; lihat header `RateLimit-*` | 014 |
| `internal` | 500 | Apa pun yang tak terduga. `detail` sengaja generik; `trace_id` adalah petunjuknya | 011 |

### 1.2 Batas laju

| Pemanggil | Batas |
|---|---|
| Sesi UI (JWT) | 600 req/menit/pengguna |
| API key | 300 req/menit/key, burst 60 |

Header di setiap respons: `RateLimit-Limit`, `RateLimit-Remaining`, `RateLimit-Reset` (BR-014).

---

## 2. Auth dan identitas

| Method | Path | Izin | BR |
|---|---|---|---|
| `POST` | `/v1/auth/login` | tidak ada | 020, 021, 022 |
| `POST` | `/v1/auth/refresh` | cookie refresh | 022 |
| `POST` | `/v1/auth/logout` | sudah login | 022 |
| `POST` | `/v1/auth/accept-invite` | tidak ada (token undangan) | 026 |
| `GET` | `/v1/me` | sudah login | — |
| `PATCH` | `/v1/me` | sudah login | 009 |

Tenant dibuat oleh tim platform, bukan lewat API ini. Owner lalu menerima undangan seperti
pengguna lain.

### Login

```json
POST /v1/auth/login
{ "email": "ops@erigo.co.id", "password": "…" }

200 OK   ← refresh token dipasang sebagai cookie httpOnly, Secure, SameSite=Lax
{ "access_token": "eyJ…", "expires_in": 900,
  "user":   { "id": "0192…", "name": "Budi", "role": "ops",
              "permissions": ["products:read", "products:write", "…"] },
  "tenant": { "id": "0192…", "name": "Erigo", "timezone": "Asia/Jakarta", "currency": "IDR" } }
```

Body ini adalah **Session**. `refresh` dan `accept-invite` juga mengembalikannya. Tenant ditentukan
dari baris pengguna (BR-020): tidak ada parameter tenant, workspace, atau subdomain, dan
menambahkannya akan merusak kompatibilitas. Pencarian ini satu-satunya pembacaan yang melintasi
tenant dan berjalan lewat satu fungsi `SECURITY DEFINER` (BR-003). Password salah, email tak
dikenal, dan akun nonaktif semuanya menghasilkan `401` yang sama (BR-021).

### Refresh dan logout

```
POST /v1/auth/refresh      (tanpa body; membaca cookie)  → 200 Session, cookie baru
POST /v1/auth/logout       (tanpa body; membaca cookie)  → 204, cookie dihapus
```

Setiap `refresh` merotasi token; memakai ulang token yang sudah dirotasi mencabut seluruh rantainya
(BR-022). `refresh` tidak butuh autentikasi karena dipanggil *setelah* access token kedaluwarsa.
`logout` idempoten: panggilan kedua, atau panggilan tanpa cookie, tetap menghasilkan `204`.

### Menerima undangan

```json
POST /v1/auth/accept-invite
{ "token": "inv_9c2e…", "password": "at-least-8-chars" }

200 OK   ← Session + cookie refresh: pengguna langsung masuk dalam keadaan login
```

Token yang kedaluwarsa atau sudah dipakai menghasilkan `422` pada `token` (BR-026).

### Me

```json
GET /v1/me
200 OK
{ "user":   { "id": "0192…", "email": "ops@erigo.co.id", "name": "Budi", "role": "ops",
              "permissions": ["products:read", "…"] },
  "tenant": { "id": "0192…", "name": "Erigo", "timezone": "Asia/Jakarta", "currency": "IDR" } }

PATCH /v1/me
{ "name": "Budi Santoso" }
200 OK   ← body sama dengan GET /v1/me
```

`name` satu-satunya field yang bisa diubah di sini. Ganti dan reset password tidak ada di fase ini.

---

## 3. Peran dan izin

Lima peran, di-seed dan tetap (BR-023). Izin berbentuk `resource:action`, dengan action berupa
`read` atau `write`.

| Izin | `owner` | `admin` | `ops` | `warehouse` | `viewer` |
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

**`owner` adalah `admin` ditambah `settings:write`, tidak lebih.** Owner memberi akses kepada
merchandiser "tanpa menyerahkan urusan tagihan" (`01-product-requirements.md` §5.5), jadi batas antara kedua
peran adalah pengaturan tenant itu sendiri.

**`ops` membaca kategori dan brand tetapi tidak menulisnya.** Editor produk perlu membacanya untuk
memasang produk; menata ulang pohon kategori adalah tugas pengelola kategori, yang menjadi milik
Admin.

**`warehouse` membaca katalog dan tidak mengubah apa pun.** Peran ini ada supaya sudah tersedia
sebelum Fase 4 memberinya stok.

`403` menyebut izin yang dibutuhkan di `detail` (BR-024). Klien tidak merender apa yang tidak bisa
dilakukan pengguna (BR-025).

---

## 4. Pengaturan, pengguna, dan API key

| Method | Path | Izin | BR |
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

### Pengaturan

```json
GET /v1/settings
200 OK
{ "id": "0192…", "name": "Erigo", "slug": "erigo",
  "timezone": "Asia/Jakarta", "currency": "IDR", "status": "active" }

PATCH /v1/settings
{ "name": "Erigo Apparel", "timezone": "Asia/Makassar" }
200 OK   ← body sama dengan GET
```

Hanya `name` dan `timezone` yang bisa diubah. `currency` tetap di Fase 1.

### Peran

```json
GET /v1/roles
200 OK
[ { "name": "owner", "description": "Everything, including the tenant's own settings",
    "permissions": ["products:read", "…", "settings:write"] },
  … ]
```

Respons ini konstan: klien merender pemilih peran dari respons ini, bukan meng-hardcode §3.

### Pengguna

```json
GET /v1/users?status=invited
200 OK
{ "data": [
    { "id": "0192…", "email": "rina@erigo.co.id", "name": "Rina", "role": "ops",
      "status": "invited", "last_login_at": null, "created_at": "2026-08-27T09:15:00Z" } ],
  "next_cursor": null }

POST /v1/users/invite
{ "email": "rina@erigo.co.id", "name": "Rina", "role": "ops" }
201 Created   ← User seperti di atas; email undangan dikirim

POST /v1/users/{id}/resend-invite
204 No Content   ← hanya selama status invited; selain itu 422

PATCH /v1/users/{id}
{ "role": "admin" }                 atau   { "status": "active" }
200 OK   ← User

DELETE /v1/users/{id}
204 No Content   ← menyetel status disabled; barisnya tidak pernah dihapus
```

- Email yang sudah dipakai di tenant mana pun menghasilkan `422` pada `email` (BR-020).
- Hanya owner yang bisa memberikan peran `owner` (BR-023).
- Owner aktif terakhir milik tenant tidak bisa diturunkan perannya atau dinonaktifkan (BR-027).
- `PATCH` menerima `role` dan `status` (`active` mengaktifkan lagi pengguna yang nonaktif) dan tidak
  butuh `If-Match` (BR-010).

### API key

```json
POST /v1/api-keys
{ "name": "Warehouse scanner app",
  "permissions": ["products:read", "categories:read"] }

201 Created
{ "id": "0192…", "name": "Warehouse scanner app", "key_prefix": "bk_live_7f3a",
  "secret": "bk_live_7f3a91c2e8…",          ← ditampilkan tepat sekali, tidak bisa diambil lagi
  "permissions": ["products:read", "categories:read"],
  "created_by": { "id": "0192…", "name": "Budi" },
  "last_used_at": null, "created_at": "2026-08-27T09:15:00Z" }

GET /v1/api-keys
200 OK
{ "data": [ …bentuk sama tanpa "secret"… ] }    ← tanpa paginasi; key yang dicabut tidak ditampilkan

DELETE /v1/api-keys/{id}
204 No Content   ← mencabut; berlaku pada request berikutnya dari key itu
```

Izin sebuah key harus merupakan bagian dari izin pembuatnya; selain itu menghasilkan `422` pada
`permissions` (BR-028).

---

## 5. Brand

| Method | Path | Izin | BR |
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
200 OK   ← Brand, versi 2
```

- `slug` diturunkan dari `name`, termasuk saat ganti nama.
- Nama yang slug-nya sama dengan slug brand lain, termasuk brand yang diarsipkan, menghasilkan `422`
  pada `name` (BR-030).
- `channel_brand_ids` diganti sebagai satu objek utuh.
- Daftar `GET` diurutkan menurut `name`; `q` mencocokkan nama.

---

## 6. Kategori

| Method | Path | Izin | BR |
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
200 OK   ← Category ditambah jumlah yang dibutuhkan dialog pindah:
{ …, "descendant_count": 4, "product_count": 128 }      ← product_count mencakup seluruh subtree

PATCH /v1/categories/{id}      If-Match: 1
{ "parent_id": "0192-technical-outerwear" }      atau   { "name": "Jackets & Coats" }
200 OK   ← Category dengan path barunya

DELETE /v1/categories/{id}
204 No Content
409 category_in_use
{ …, "errors": [ { "field": "children", "count": 4 }, { "field": "products", "count": 128 } ] }
```

- **`path` hanya-baca.** Database yang menurunkannya; mengirimnya menghasilkan `422` (BR-008,
  BR-032).
- Ganti nama atau pindah menulis ulang `path` setiap turunannya dalam satu statement dan tidak
  menyentuh penempatan produk (BR-033).
- Memindahkan kategori ke bawah turunannya sendiri menghasilkan `422` pada `parent_id` (BR-034).
- `parent_id: null` pada `PATCH` menjadikan kategori itu root.
- **Daftar.** Tanpa paginasi, datar, diurutkan menurut `kind` lalu `path`; klien menyusun pohon dari
  `parent_id`.
  - `kind` membatasi daftar ke satu pohon.
  - `parent_id` mulai dari anak-anak node itu; bila dihilangkan, mulai dari root.
  - `depth=1` hanya mengembalikan satu tingkat, untuk lazy-loading pohon yang besar.

---

## 7. Produk dan varian

| Method | Path | Izin | BR |
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

### 7.1 Produk

```json
POST /v1/products
{ "title": "Erigo Basic Tee",
  "brand_id": "0192a1c4-…",
  "category_ids": ["0192-jackets", "0192-hiking"],
  "attributes": { "material": "Cotton Combed 30s" } }
```

Hanya yang diisi pengguna: `status` dan `version` **tidak ada**, bukan `null`.

```json
201 Created
{ "id": "0192b7f0-…",
  "version": 1,                                       ← diisi server
  "title": "Erigo Basic Tee",
  "description": null,
  "status": "draft",                                  ← default diterapkan
  "brand": { "id": "0192a1c4-…", "name": "Erigo" },   ← diperluas saat dibaca
  "categories": [ { "id": "0192-jackets", "kind": "category", "name": "Jackets",
                    "path": "apparel.outerwear.jackets" }, … ],
  "attributes": { "material": "Cotton Combed 30s" },
  "option_names": [],
  "variant_count": 0,
  "media": [],                                        ← objek Media, urut position (§8)
  "archived_at": null,
  "created_at": "2026-08-27T09:15:00Z", "updated_at": "2026-08-27T09:15:00Z" }
```

`GET /v1/products/{id}` mengembalikan body yang sama.

```json
PATCH /v1/products/{id}        If-Match: 1
{ "description": "Kaos basic 30s", "brand_id": null, "status": "active" }
200 OK   ← Product, versi 2
```

- **Versi.** Dibawa di `If-Match`, tidak pernah di body; server yang menaikkannya.
- **Mengosongkan.** `null` mengosongkan `description` atau `brand_id` (BR-009).
- **Diganti utuh.** `category_ids` mengganti semua penempatan; `attributes` mengganti seluruh
  objek.
- **`option_names`** hanya berubah lewat matriks varian (§7.3); mengirimnya di sini menghasilkan
  `422`.
- **Status.** `"status": "active"` menjalankan publish check (BR-038) dan `"draft"` membatalkan
  publikasi. `DELETE` mengarsipkan.

```json
422 publish_check_failed
{ …, "errors": [
    { "field": "sku",        "variant_id": "0192…", "detail": "Variant Black / XL has no SKU" },
    { "field": "price",      "variant_id": "0192…", "detail": "Price must be greater than zero" },
    { "field": "media",      "detail": "At least one image is required" },
    { "field": "categories", "detail": "At least one category of kind category is required" } ] }
```

**Daftar.**

```json
GET /v1/products?status=active&category_id=0192-apparel&q=tee&sort=-updated_at
200 OK
{ "data": [
    { "id": "0192…", "version": 3, "title": "Erigo Basic Tee", "status": "active",
      "brand": { "id": "0192…", "name": "Erigo" },
      "variant_count": 10,
      "price_min": { "amount": 19900000, "currency": "IDR" },
      "price_max": { "amount": 21900000, "currency": "IDR" },
      "cover_url": "https://…/200.webp",              ← turunan 200px dari gambar pertama, atau null
      "updated_at": "2026-08-27T09:15:00Z" } ],
  "next_cursor": "eyJ…" }
```

- `category_id` mencocokkan kategori itu **beserta turunannya**.
- `q` adalah pencocokan trigram pada `title`.
- `sort` menerima `-created_at` (default), `-updated_at`, atau `title`.
- Produk yang diarsipkan hanya muncul dengan `status=archived`.

### 7.2 Varian

```json
POST /v1/products/{id}/variants
{ "option_values": ["Black", "S"], "sku": "TS-BLK-S",
  "price": { "amount": 19900000 }, "weight_grams": 200 }

201 Created
{ "id": "0192…", "product_id": "0192b7f0-…", "version": 1,
  "option_values": ["Black", "S"], "sku": "TS-BLK-S", "barcode": null,
  "price": { "amount": 19900000, "currency": "IDR" },   ← currency default dari tenant
  "compare_at_price": null, "weight_grams": 200,
  "archived_at": null,
  "created_at": "2026-08-27T09:15:00Z", "updated_at": "2026-08-27T09:15:00Z" }

PATCH /v1/variants/{id}        If-Match: 1
{ "barcode": "8991234567890", "compare_at_price": null }
200 OK   ← Variant, versi 2

GET /v1/products/{id}/variants
200 OK
{ "data": [ …Variant… ] }      ← tanpa paginasi, urut option_values
```

- `option_values` harus punya satu entri untuk setiap entri `option_names` dan unik di antara varian
  hidup milik produk itu (BR-040). Nilainya hanya berubah lewat matriks.
- SKU yang bentrok menghasilkan `409 duplicate_sku` (BR-039).

### 7.3 Matriks varian

`PUT /v1/products/{id}/variant-matrix` menyimpan seluruh grid opsi dalam **satu request** (BR-041).

Masalah yang diselesaikannya: seorang merchandiser membuka grid, menempelkan harga dari Excel,
menghapus satu varian warna, dan menambah satu ukuran. Tanpa endpoint ini, front end harus menghitung
selisih grid sendiri dan mengirim 25 request terpisah, tanpa transaksi dan tanpa jaminan urutan.
Kegagalan sebagian akan meninggalkan grid dalam keadaan yang tidak dipahami pengguna maupun sistem.

Endpoint ini **deklaratif** ("beginilah seharusnya grid ini") dan server yang menghitung selisihnya.

```json
PUT /v1/products/{id}/variant-matrix      If-Match: 3      ← versi PRODUK
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

- **Pencocokan.** Baris dicocokkan dengan varian hidup milik produk menurut `option_values`. Baris
  yang cocok dengan varian yang diarsipkan akan memulihkannya, jadi varian warna yang ditambahkan
  lagi tetap memakai SKU-nya.
- **Satu baris buruk gagal sendirian.** Baris lain tetap tersimpan, dan setiap baris mendapat hasil
  (BR-041). Responsnya tetap `200` meski ada baris yang gagal.
- **`archive_missing`.**
  - `true` mengarsipkan varian hidup yang tidak dikirim.
  - `false` menambal sebagian grid tanpa mengarsipkan apa pun; editor memakainya untuk tampilan
    yang difilter.
  - Mengubah `option_names` dengan `archive_missing: false` menghasilkan `422`: varian berbentuk
    lama tidak bisa bertahan.
- **Error tingkat request.** Baris yang `option_values`-nya tidak cocok dengan `option_names`
  membuat seluruh request `422` sebelum apa pun ditulis. Begitu juga baris duplikat dan sumbu Colour
  yang tidak berada di posisi 0 (BR-040).
- **Konkurensi.** `version` produk menjaga matriks, dan penyimpanan yang berhasil menaikkannya.

### 7.4 Matriks versus `PATCH /v1/variants/{id}`

Tugasnya berbeda. Jangan pakai yang satu untuk yang lain.

| | `variant-matrix` | `PATCH /variants/{id}` |
|---|---|---|
| Cakupan | Semua varian produk | Tepat satu |
| Bisa membuat | Ya | Tidak |
| Bisa mengarsipkan | Ya | Tidak |
| Mengubah bentuk grid | Ya | Tidak |
| Pemanggil biasa | Tombol Save di editor matriks | Drawer detail varian |
| Konkurensi | `If-Match` pada produk | `If-Match` pada varian itu |

Orang yang memperbaiki satu barcode memakai `PATCH`. Mengirim `PUT` seluruh grid untuk itu akan
menimpa suntingan merchandiser yang berjalan bersamaan.

---

## 8. Media

| Method | Path | Izin | BR |
|---|---|---|---|
| `POST` | `/v1/media/presign` | `media:write` | 051, 053 |
| `POST` | `/v1/media/confirm` | `media:write` | 050, 051 |
| `PATCH` | `/v1/media/{id}` | `media:write` | 009 |
| `DELETE` | `/v1/media/{id}` | `media:write` | 012 |
| `PATCH` | `/v1/products/{id}/media/order` | `media:write` | — |

Unggahan berjalan **langsung dari browser ke R2**; byte gambar tidak pernah melewati API (BR-051).

```json
1. POST /v1/media/presign
   { "product_id": "0192…", "mime_type": "image/jpeg", "bytes": 5242880 }
   200 OK
   { "upload_url": "https://…r2…", "r2_key": "0192-tenant/products/0192…/0193…",
     "expires_in": 600 }

2. PUT <upload_url>            byte file mentah, langsung ke R2, dengan progress bar

3. POST /v1/media/confirm
   { "r2_key": "0192-tenant/products/0192…/0193…", "product_id": "0192…", "variant_id": null }
   201 Created
   { "id": "0193…", "product_id": "0192…", "variant_id": null,
     "r2_key": "0192-tenant/products/0192…/0193…",
     "mime_type": "image/jpeg", "bytes": 5242880, "width": 3000, "height": 4000,
     "position": 0,
     "url": "https://…",                    ← GET presigned untuk file asli, 1 jam (BR-053)
     "derivatives": {},                     ← diisi worker dalam ~15 detik (BR-052)
     "created_at": "2026-08-27T09:15:00Z" }
```

- **Presign.** Menerima `image/jpeg`, `image/png`, dan `image/webp` hingga 20 MB; selain itu
  menghasilkan `422` (BR-051).
- **Confirm.** Memeriksa content type dan ukuran terhadap `HEAD` dari R2 sebelum menyimpan baris.
  Key untuk objek yang tidak pernah diunggah menghasilkan `422`.
- **Turunan (derivative).** Begitu siap, `derivatives` berisi
  `{ "1600": "https://…", "800": "https://…", "200": "https://…" }`, masing-masing URL presigned
  1 jam. Body produk membawa objek Media yang sama.

```json
PATCH /v1/media/{id}
{ "variant_id": "0192…" }          atau   { "variant_id": null }    ← pasang ke varian / tingkat produk
200 OK   ← Media

PATCH /v1/products/{id}/media/order
{ "media_ids": ["0193…", "0194…", "0195…"] }    ← setiap id media milik produk, dalam urutan baru
200 OK
{ "data": [ …Media, urut position… ] }

DELETE /v1/media/{id}
204 No Content   ← menghapus baris; worker menghapus objek R2-nya
```

Media tidak punya `version`, jadi kedua `PATCH` tidak memakai `If-Match`. Daftar urutan yang tidak
berisi tepat media milik produk itu menghasilkan `422`.

---

## 9. Ekspor katalog dan job

| Method | Path | Izin | BR |
|---|---|---|---|
| `GET` | `/v1/products/export?template=&format=csv&status=&brand_id=&category_id=` | `exports:read` | 060, 061, 062 |
| `GET` | `/v1/jobs/{id}` | izin milik job itu (`exports:read` untuk ekspor) | 060, 063 |

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
  "error": null }                          ← sebuah Problem saat state bernilai failed
```

- **Template.** `template` salah satu dari `shopee`, `tokopedia`, `tiktok`, `lazada`, `blibli`,
  atau `generic`. Template merender katalog ke tata letak kolom lembar bulk-upload marketplace itu
  (BR-061). Filternya sama dengan daftar produk di §7.1.
- **Mapping yang kurang.** Tidak pernah menghalangi ekspor. Sel-sel itu dibiarkan kosong dan
  produknya dicantumkan di `incomplete`, dikelompokkan menurut apa yang kurang (BR-062).
- **Tautan unduh.** Setiap `GET` pada job yang sudah selesai menandatangani `download_url` baru yang
  berlaku 15 menit; begitulah tautan dibuat ulang (BR-063). `result` bernilai `null` sampai `state`
  bernilai `done`.

Tidak ada tabel `channels` yang terlibat: ini murni pembuatan CSV, dan merchant mengunggah filenya
sendiri. `GET /v1/jobs/{id}` ada sejak Fase 1 karena ekspor membutuhkannya, dan setiap pekerjaan
async di fase berikutnya memakainya tanpa perubahan.

---

## 10. Tidak ada di fase ini

Cukup sering diminta selama pilot sehingga layak disebut secara eksplisit:

| Endpoint | Fase |
|---|---|
| `POST /v1/products/bulk` | 2 |
| `POST /v1/products/import` | 2 |
| Apa pun di bawah `/v1/orders` | 2 |
| Apa pun di bawah `/v1/channels` atau `/v1/hooks` | 3 |
| Apa pun di bawah `/v1/inventory` atau `/v1/locations` | 4 |
| Ganti dan reset password | belum dijadwalkan |
