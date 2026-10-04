# Backlog Fase 1 — Catalog & Foundation

**Berurutan.** Item ditulis dalam urutan pengerjaannya. Dependensi mengalir ke bawah; tidak ada yang
bergantung pada sesuatu di bawahnya. Id mencatat kapan item ditambahkan, bukan posisinya: ambil
item `todo` **teratas** yang dependensinya sudah `done`.

Acceptance merujuk aturan yang dibuktikannya (`BR-xxx`, `02-business-rules.md`); teks aturannya ada
di sana.

**Status** `todo` · `wip` · `review` · `done` · `blocked` · `dropped`
**Repo** `BE` backend · `FE` frontend · `CT` kontrak · `OPS` infrastruktur

---

## Aturan

- **Satu item, satu PR, satu branch** bernama `p1-<id>-<slug>` (mis. `p1-014-variant-matrix`).
- **Klaim dengan menyetel `wip` dan menulis namamu di Owner**, lewat commit ke file ini, sebelum
  menulis kode. Dua agent di satu item adalah kegagalan yang membuat file ini ada.
- **Item `done` hanya kalau kolom Acceptance-nya terbukti benar** — bukan saat kodenya di-merge.
  Kalau acceptance butuh test, test itu bagian dari item.
- **Item `BE` dan padanan `FE`-nya adalah item terpisah.** Keduanya rilis mandiri; frontend bekerja
  dengan client hasil generate dan bisa dibangun sebelum backend kalau kontraknya sudah ada.
- **`blocked` wajib punya alasan** di Notes. Item blocked tanpa alasan sama dengan `todo`.
- Jangan mengurutkan ulang item demi kenyamanan. Kalau urutannya salah, jelaskan kenapa di PR.

---

## M0 · Fondasi (minggu 1–3)

Tidak ada yang terlihat oleh user di sini. Semua yang sesudahnya bergantung pada seluruh isinya.

Infrastruktur produksi — VPS, Caddy, TLS, backup, dan CI — ada di `M4` di akhir fase, bukan di sini.
Belum ada mesin dan belum ada domain; setiap dokumen masih menulis `{domain}`. Satu-satunya bagian
yang benar-benar dibutuhkan backend adalah PostgreSQL 18 yang bisa dihubungi, dan `P1-000`
menyediakannya dari mesin developer sendiri — sebuah connection string dan target `make`, tanpa
container. Ini pengurutan ulang yang disengaja, bukan demi kenyamanan — alasannya ada di `M4`.

**Layanan di host, bukan container.** Mesin dev yang sudah menjalankan PostgreSQL dan Redis tidak
mendapat apa-apa dari salinan kedua di Docker; container hanya menambah satu runtime lagi yang harus
dijaga tetap hidup. Konsekuensinya, versi dev adalah apa pun yang ada di mesin, dan itulah sebabnya
pin-nya PostgreSQL 18 dan Redis 8 selagi belum ada mesin dan belum ada data untuk dimigrasi.
Menyamakan dev dengan prod menghapus satu jenis bug (fitur khusus 18 yang sampai ke server 16) yang
tidak bisa ditangkap secara andal oleh review sebanyak apa pun. Tinjau ulang pin ini hanya setelah
mesinnya ada.

| ID | Item | Repo | Depends | Acceptance | Status | Owner |
|---|---|---|---|---|---|---|
| P1-000 | Layanan dev lokal: PostgreSQL 18 + Redis 8 di host | OPS | — | `make dev` terhubung ke PostgreSQL 18 di host pada `:5432` dan Redis 8 pada `:6379`; `GET /healthz` melaporkan keduanya | done | Iqbal Hamdani |
| P1-005 | Kerangka `openapi.yaml` + generator terpasang di dua repo | CT/BE/FE | 000 | `make generate` tidak mengubah apa pun pada tree bersih di dua repo | done | Iqbal Hamdani |
| P1-006 | Runner migrasi, peran `app_user` non-owner, helper RLS | BE | 000 | `app_user` tidak memiliki apa pun; `FORCE RLS` di setiap tabel tenant (BR-001) | done | Iqbal Hamdani |
| P1-007 | `InTenantTx`, konteks tenant, gagal tertutup saat tenant tidak ada | BE | 006 | Tanpa tenant mengembalikan `ErrNoTenantContext`, tidak pernah hasil kosong (BR-002) | done | Iqbal Hamdani |
| P1-008 | **Suite test isolasi tenant atas setiap route terdaftar** | BE | 007 | Dua tenant di-seed; token A mengembalikan nol baris milik B di setiap route (BR-001, BR-003) | done | Iqbal Hamdani |
| P1-009 | Penjaga policy RLS | BE | 006 | `make lint-rls` keluar non-zero untuk tabel ber-`tenant_id` tanpa policy (BR-001) | done | Iqbal Hamdani |
| P1-010 | Skema `tenants`, `users`, `refresh_tokens`, `api_keys` | BE | 006 | Persis sesuai `03-erd.md` §3.2 | done | Iqbal Hamdani |
| P1-011 | Auth: login, rotasi refresh, logout, argon2id | BE | 010 | Refresh token yang dipakai ulang mencabut seluruh rantai (BR-020–022) | done | Iqbal Hamdani |
| P1-012 | RBAC: 5 peran di-seed, pengecekan `resource:action` di batas handler | BE | 011 | `403` menyebut izin yang dibutuhkan di `detail` (BR-023, BR-024) | done | Iqbal Hamdani |
| P1-013 | Envelope error (RFC 9457), `trace_id`, wiring OpenTelemetry | BE | 007 | Setiap error membawa `trace_id` yang bisa ditelusuri ke span (BR-011) | done | Iqbal Hamdani |
| P1-014 | App shell, routing, layar auth, penanganan sesi | FE | 005, 011 | Access token di memori, refresh di cookie httpOnly (BR-022) | done | Iqbal Hamdani |
| P1-015 | Batas laju per user dan per API key, header `RateLimit-*` | BE | 012 | Melewati batas menghasilkan `429 rate_limited`; header ada di setiap respons (BR-014) | todo | |
| P1-016 | Allow-list field log | BE | 013 | Field yang tidak ada di allow-list diredaksi di setiap baris log (BR-013) | todo | |

---

## M1 · Inti katalog (minggu 5–8)

| ID | Item | Repo | Depends | Acceptance | Status | Owner |
|---|---|---|---|---|---|---|
| P1-020 | Skema `brands` + composite FK ke tenant | BE | 010 | Sesuai `03-erd.md` §3.3; `products_same_tenant_as_brand` menolak brand lintas tenant (BR-004) | todo | |
| P1-021 | API CRUD brand termasuk `channel_brand_ids` | BE | 020 | Sesuai `04-api-spec.md` §5 (BR-010, BR-012, BR-030) | todo | |
| P1-022 | Skema `categories`, ltree, slugify, trigger path | BE | 010 | Pemindahan menulis ulang path setiap keturunan dalam satu statement (BR-032) | todo | |
| P1-023 | Penjaga siklus kategori + penanganan bentrok slug antar-saudara | BE | 022 | Memindahkan node ke bawah keturunannya sendiri memicu error (BR-034, BR-035) | todo | |
| P1-024 | API kategori, filter `kind`, fetch dengan batas kedalaman | BE | 022 | Sesuai `04-api-spec.md` §6; `path` dikirim → `422`; menghapus kategori yang dipakai → `409 category_in_use` beserta jumlahnya (BR-008, BR-036) | todo | |
| P1-025 | Skema `products` termasuk `attributes`, `option_names` | BE | 020 | Sesuai `03-erd.md` §3.3 | todo | |
| P1-026 | Skema `variants`, partial unique index SKU, composite FK | BE | 025 | Banyak SKU null diizinkan; yang non-null unik per tenant; satu varian hidup per kombinasi opsi (BR-039, BR-040) | todo | |
| P1-027 | Join `product_categories`, keanggotaan multi-`kind` | BE | 022, 025 | Satu produk di 3 pohon dengan kind berbeda sekaligus; tautan lintas tenant ditolak (BR-004, BR-031) | todo | |
| P1-028 | CRUD produk, `If-Match`, penolakan field yang dikelola server | BE | 025 | Sesuai `04-api-spec.md` §7.1 (BR-008, BR-009, BR-010, BR-012) | todo | |
| P1-029 | CRUD varian | BE | 026 | Sesuai `04-api-spec.md` §7.2; SKU duplikat → `409 duplicate_sku` (BR-039) | todo | |
| P1-030 | Daftar produk: pencarian (trigram), filter, pagination cursor | BE | 028 | p95 < 600ms dengan 10k produk; `category_id` mencakup keturunannya | todo | |
| P1-031 | Layar brand manager | FE | 021 | Kriteria penerimaan `01-product-requirements.md` §5.1 | todo | |
| P1-032 | Category manager: pohon, drag-to-move, dialog konfirmasi | FE | 024 | Kriteria penerimaan `01-product-requirements.md` §5.3 (BR-033) | todo | |
| P1-033 | Layar daftar produk: pencarian, filter, state tersimpan | FE | 030 | Pilihan tetap bertahan melewati pagination dan filter | todo | |
| P1-034 | Editor produk: field, pilihan brand, multi-select kategori | FE | 028 | Ada prompt perubahan belum tersimpan saat berpindah halaman | todo | |

---

## M2 · Matriks varian & media (minggu 8–10)

Pekerjaan yang membedakan fase ini. `01-product-requirements.md` §5.2 adalah rujukan kriteria penerimaannya.

| ID | Item | Repo | Depends | Acceptance | Status | Owner |
|---|---|---|---|---|---|---|
| P1-040 | `PUT /variant-matrix`: diff di server, satu transaksi | BE | 029 | Sesuai `04-api-spec.md` §7.3: create + update + restore + arsip; hasil per baris (BR-040, BR-041) | todo | |
| P1-041 | Semantik kegagalan sebagian di matriks | BE | 040 | Satu SKU duplikat hanya menggagalkan baris itu; baris lain tetap tersimpan (BR-041) | todo | |
| P1-042 | Skema `product_media` | BE | 025 | Sesuai `03-erd.md` §3.3 (BR-004, BR-050) | todo | |
| P1-043 | API media: presign, confirm dengan validasi HEAD, assign, urutkan ulang, hapus | BE | 042 | Sesuai `04-api-spec.md` §8; key tidak bisa didaftarkan untuk objek yang tidak pernah diunggah (BR-051) | todo | |
| P1-044 | Worker: turunan gambar WebP 1600/800/200 lewat libvips | BE | 043 | Turunan siap < 15s p95 (BR-052) | todo | |
| P1-045 | Bucket R2, prefix tenant, kebijakan GET presigned | OPS | 042 | Gambar produk 1 jam; ekspor 15 menit (BR-053) | todo | |
| P1-046 | **Editor matriks varian**: grid, paste dari Excel, fill-down | FE | 040 | Grid 2×5 merender 10 sel, tersimpan dalam satu request < 2s (BR-041) | todo | |
| P1-047 | Penyesuaian harga massal di matriks (± nominal / %) | FE | 046 | Ada pratinjau sebelum diterapkan | todo | |
| P1-048 | Media library: drag-drop, unggah langsung ke R2, urutkan ulang, assign ke varian | FE | 043 | Gambar 5MB menampilkan progres dan tidak pernah memblokir form (BR-051, BR-052) | todo | |
| P1-049 | Publish check pada `draft → active` | BE/FE | 040, 043 | `422 publish_check_failed` mencantumkan setiap kegagalan; editor menautkan masing-masing ke selnya (BR-038) | todo | |

> **P1-049 adalah tempat SKU yang nullable ditegakkan.** Ini pengecekan di jalur publish, bukan
> constraint tabel — membuat draft harus tetap mulus. Lihat BR-038 dan `03-erd.md` §4.1.

---

## M3 · Ekspor & admin (minggu 10–12)

| ID | Item | Repo | Depends | Acceptance | Status | Owner |
|---|---|---|---|---|---|---|
| P1-060 | Runner job asinkron + `GET /v1/jobs/{id}` | BE | 007 | Sesuai `04-api-spec.md` §9; dipakai ulang tanpa perubahan oleh setiap fase berikutnya (BR-060) | todo | |
| P1-061 | Ekspor katalog: template untuk 5 marketplace + generic | BE | 060, 030 | 10k varian < 60s; terbuka rapi di Excel dengan locale Indonesia (BR-061, BR-064) | todo | |
| P1-062 | Ekspor melaporkan pemetaan channel yang belum lengkap, dikelompokkan | BE | 061 | Tetap dibuat; menyebut apa yang hilang (BR-062) | todo | |
| P1-063 | Layar ekspor: pemilih template, filter, unduhan | FE | 061 | Tautan kedaluwarsa dalam 15 menit dan bisa dibuat ulang (BR-063) | todo | |
| P1-064 | User: undang, kirim ulang, atur peran, nonaktifkan | BE | 012 | Sesuai `04-api-spec.md` §4 (BR-026, BR-027) | todo | |
| P1-065 | API key: terbitkan, tampilkan prefix, cabut | BE | 012 | Secret ditampilkan tepat sekali; izin dibatasi pada izin pembuatnya (BR-028) | todo | |
| P1-066 | Layar Team & roles | FE | 064 | `ops` sama sekali tidak melihat navigasi pengelolaan user (BR-025) | todo | |
| P1-067 | Layar API keys | FE | 065 | UI salin-sekali dengan peringatan eksplisit (BR-028) | todo | |
| P1-071 | API settings: `GET`/`PATCH /v1/settings` | BE | 012 | Sesuai `04-api-spec.md` §4; hanya `owner` yang bisa `PATCH` (BR-023, BR-029) | todo | |
| P1-068 | Wizard onboarding termasuk pengisian `channel_brand_ids` | FE | 021, 024, 071 | Kriteria penerimaan `01-product-requirements.md` §5.1 (BR-029, BR-030) | todo | |
| P1-069 | Empty state yang membawa pesan "no stock yet" | FE | 033 | Ada di daftar produk dan editor produk (BR-015) | todo | |

---

## M4 · Kesiapan produksi & pilot (minggu 10–12)

Dipindah turun dari `M0`, dengan sengaja. Tidak satu pun bisa didemonstrasikan hari ini — belum ada
VPS dan domain, jadi acceptance `P1-001` tidak punya apa pun untuk ditunjuk — dan tidak ada yang di
`M0`–`M3` membutuhkannya, karena backend dikembangkan dengan layanan yang terpasang di host dari
`P1-000`.

Item ini tidak bisa dipindah lebih jauh lagi. `P1-070` menaruh katalog merchant sungguhan di mesin,
dan itu tidak boleh terjadi di storage yang belum pernah dipakai untuk restore.

| ID | Item | Repo | Depends | Acceptance | Status | Owner |
|---|---|---|---|---|---|---|
| P1-001 | Provisioning VPS, Docker Compose, Caddy, TLS | OPS | — | `docker compose up` melayani HTTPS di domain | todo | |
| P1-002 | PostgreSQL 18 + Redis 8 dengan config yang di-tune dan batas resource | OPS | 001 | `shared_buffers` ≈ 25% RAM; `cpus`/`mem_limit` per layanan disetel | todo | |
| P1-003 | **pgBackRest ke R2 + latihan restore** | OPS | 002 | **Restore dari R2 ke mesin bersih berhasil.** Memblokir semua data merchant | todo | |
| P1-004 | CI: lint, test, migrasi-di-snapshot, pengecekan drift kontrak | BE/FE | 001 | PR yang merusak salah satu dari keempatnya berstatus merah | todo | |
| P1-070 | Onboarding merchant pilot: katalog sungguhan dimuat | OPS | all | Katalog sungguhan satu merchant ada di sistem | todo | |

> **P1-003 menjadi gerbang pilot.** `P1-070` tidak dimulai sampai latihan restore lulus, begitu
> juga Fase 2. Semua yang terjadi sesudahnya berasumsi data merchant bisa dipulihkan.
> Provisioning yang terlambat menyisakan waktu lebih sedikit antara mesin tersedia dan pilot
> bergantung padanya, jadi perlakukan minggu 10 sebagai tanggal mulai pasti untuk `P1-001`, bukan
> sekadar target.

> **`P1-001` butuh keputusan sebelum bisa dimulai:** domain produksi. Setiap dokumen masih menulis
> `{domain}`. Challenge ACME default milik Caddy juga tidak bisa menjangkau mesin lewat proxy
> Cloudflare, jadi mode TLS — DNS-01 dengan token Cloudflare, atau sertifikat Cloudflare Origin —
> adalah bagian dari item ini, bukan detail implementasinya.

---

## Definisi Selesai

Sebuah item `done` kalau **semua** hal ini benar. Bukan empat dari lima.

1. Kolom Acceptance terbukti benar, dengan test di mana test memungkinkan.
2. Sesuai dengan kontrak. Kalau tidak bisa, kontraknya diubah lebih dulu, di PR-nya sendiri.
3. Isolasi tenant terjaga — route baru tercakup oleh suite P1-008.
4. Error memakai envelope RFC 9457 dengan `trace_id`.
5. Tidak ada field yang dikelola server yang diterima dari klien.
6. `make generate` tidak mengubah apa pun pada tree bersih di dua repo.
7. Di-review oleh orang yang tidak menulisnya.

---

## Di luar ruang lingkup Fase 1

Dicatat di sini karena hal-hal ini akan diusulkan berulang kali, dan jawabannya cukup satu tautan.

| Permintaan | Fase |
|---|---|
| Stok, kuantitas, gudang | 4 |
| Order, pengiriman, label | 2 |
| `POST /products/bulk`, impor CSV | 2 |
| Sinkronisasi API marketplace (ekspor CSV adalah jawaban Fase 1) | 3 |
| `Idempotency-Key` pada mutasi | 4 |
| Harga per channel | setelah 4 |
