# Fase 1 — Catalog & Foundation · Aturan Bisnis

**Semua aturan di fase ini, bernomor.** Setiap aturan ditulis sekali di sini. `01-product-requirements.md`,
`03-erd.md`, `04-api-spec.md`, dan `05-backlog.md` merujuk aturan lewat id-nya (`BR-038`) dan tidak
menulis ulang isinya. Test juga sebaiknya merujuk id ini.

Sebuah aturan menyatakan apa yang harus benar, lalu diikuti catatan singkat soal alasannya.
Mekanisme yang menegakkannya ada di ERD atau API spec.

Id dikelompokkan per area dan tidak pernah dipakai ulang: `001–019` platform · `020–029` auth & tim ·
`030–049` katalog · `050–059` media · `060–069` ekspor.

---

## 1. Platform

Aturan ini berlaku di setiap fase. Mengubah salah satunya adalah perubahan yang merusak kedua repo
kode.

### BR-001 Database yang menegakkan isolasi tenant
Setiap tabel milik tenant punya `tenant_id`, `ENABLE` **dan** `FORCE ROW LEVEL SECURITY`, serta
policy `tenant_isolation`. Aplikasi terhubung sebagai `app_user`, yang tidak memiliki apa pun,
sehingga RLS selalu berlaku padanya. CI gagal kalau ada tabel ber-`tenant_id` tanpa policy aktif.

*Kenapa:* satu `WHERE tenant_id = $1` yang terlupa adalah kebocoran lintas tenant, dan code review
tidak bisa diandalkan untuk menangkap bug semacam itu. `FORCE` penting karena tanpanya pemilik
tabel, yaitu peran yang menjalankan migrasi, melewati policy-nya sendiri.

### BR-002 Konteks tenant disetel per transaksi dan gagal tertutup
Tenant disetel dengan `set_config('app.tenant_id', …, true)` di dalam setiap transaksi, tidak
pernah per koneksi. Query tanpa konteks tenant mengembalikan `ErrNoTenantContext`, tidak pernah
hasil kosong.

*Kenapa:* pgx memakai pool koneksi, jadi `SET` di level koneksi akan terbawa ke tenant request
berikutnya. Tanpa error itu, konteks yang hilang terlihat seperti "tidak ada baris". Itu aman,
tetapi sangat membingungkan saat debugging.

### BR-003 Tenant berasal dari token, tidak pernah dari request
Tidak ada header, query parameter, atau field body yang bisa memilih tenant. Satu-satunya
pembacaan lintas tenant di jalur request adalah lookup saat login. Lookup itu lewat satu fungsi
`SECURITY DEFINER` yang hanya mengembalikan `id`, `tenant_id`, `password_hash`, `status`, dan
`role`. Pekerjaan admin lintas tenant memakai peran dan pool `BYPASSRLS` terpisah, dicatat di audit
log, dan tidak pernah bisa dijangkau dari request.

*Kenapa:* tenant yang dibaca dari request membuka eskalasi lintas tenant yang sepele.

### BR-004 `tenant_id` salinan di tabel anak dijaga composite foreign key
Kalau tabel anak membawa `tenant_id` yang sebenarnya bisa diturunkan dari induknya (`variants` →
`products`), foreign key pada `(parent_id, tenant_id)` membuat keduanya mustahil berbeda.

*Kenapa:* tanpa salinan itu, policy RLS harus berupa correlated subquery di setiap baris, dan
keunikan per tenant (`UNIQUE (tenant_id, sku)`) tidak bisa dinyatakan. Pengecekan foreign key
melewati RLS, jadi FK biasa akan menerima induk milik tenant lain.

### BR-005 Key berupa UUID v7, dibuat oleh aplikasi
Tidak ada id integer berurutan di API mana pun.

*Kenapa:* UUID yang terurut waktu menjaga insert B-tree tetap di ujung index; id berurutan
membocorkan volume bisnis.

### BR-006 Uang adalah jumlah integer ditambah mata uang
`{"amount": <bigint minor units>, "currency": "IDR"}`, tidak pernah float atau string desimal.
Kalau `currency` tidak dikirim, dipakai mata uang tenant (BR-029).

*Kenapa:* float kehilangan sen. Menyimpan dua digit minor unit untuk IDR juga berarti menambah
mata uang lain tidak butuh migrasi.

### BR-007 Waktu dalam UTC di wire dan di database
`timestamptz` dalam UTC; RFC 3339 dengan offset di wire. Zona waktu tenant hanya diterapkan saat
render.

### BR-008 Field yang dikelola server tidak pernah diterima
`id`, `tenant_id`, `version`, `created_at`, `updated_at`, `path`, dan `slug` diisi oleh server.
Klien yang mengirim salah satunya mendapat `422`, **baik saat create maupun update**.

*Kenapa:* mengabaikan field diam-diam mengajari klien bahwa mengirimnya berhasil. Satu aturan untuk
kedua verb berarti tidak ada yang perlu diingat.

### BR-009 Tidak mengirim field berbeda dengan mengirim `null`
- **Create:** field yang tidak dikirim memakai default-nya; `null` adalah `422`.
- **Update (`PATCH`):** field yang tidak dikirim tidak berubah. `null` mengosongkan field yang
  ditandai nullable di ERD, dan `422` untuk field lain.

*Kenapa:* tanpa aturan ini, "pakai default" dan "saya mau kosong" berarti hal yang sama, dan server
harus menebak maksud klien.

### BR-010 Edit bersamaan ditangkap, tidak ditimpa
Produk, varian, brand, dan kategori membawa `version`. Setiap `PATCH` ke sana wajib memakai
`If-Match: <version>`, dan version yang usang mengembalikan `409 version_conflict`. `version` hanya
dikirim di header, tidak pernah di body. Settings, user, dan media tidak punya `version`, jadi
`PATCH`-nya tidak memakai `If-Match`: edit di sana jarang dan hanya satu field, sehingga
last-write-wins tidak merugikan.

### BR-011 Error memakai satu bentuk dan bisa ditelusuri
Setiap error berbentuk RFC 9457 `application/problem+json` dan membawa `trace_id`, yaitu trace id
OpenTelemetry. Baris milik tenant lain mengembalikan `404`, persis seperti baris yang tidak ada.

*Kenapa:* tiket support yang mengutip `trace_id` langsung menuju span-nya. Jawaban yang berbeda
untuk baris tenant lain akan menunjukkan id mana yang ada.

### BR-012 Penghapusan katalog berarti arsip
`DELETE` pada brand, kategori, produk, atau varian mengisi `archived_at`; barisnya tetap ada. User
dinonaktifkan (BR-027), API key dicabut (BR-028). Media satu-satunya yang benar-benar dihapus.

*Kenapa:* fase berikutnya merujuk baris katalog dari order dan listing; penghapusan permanen akan
meninggalkan rujukan yang menggantung.

### BR-013 Log meredaksi secara default
Logging terstruktur memakai **allow-list** field: field baru diredaksi sampai ada yang
mengizinkannya.

*Kenapa:* Fase 1 tidak punya PII pelanggan; Fase 2 membawanya bersama order. Bangun kebiasaannya
selagi risikonya masih kecil.

### BR-014 Batas laju
Sesi UI: 600 request/menit per user. API key: 300 request/menit per key, burst 60. Setiap respons
membawa `RateLimit-Limit`, `RateLimit-Remaining`, `RateLimit-Reset`; melewati batas menghasilkan
`429 rate_limited`.

### BR-015 Tanpa stok, tanpa order, tanpa channel di Fase 1
Stok tidak terbatas. **Tidak ada kolom kuantitas di `variants`, di fase mana pun**: stok milik
(varian, lokasi) dan datang di Fase 4 sebagai ledger append-only. Apa pun yang menyiratkan stok,
order, atau koneksi marketplace berada di luar ruang lingkup (`01-product-requirements.md` §2).

*Kenapa:* `qty` di varian menutup kemungkinan multi-gudang, menghilangkan jejak audit, membuat
setiap order berebut satu baris, dan menghapus beda antara stok di tangan dan stok yang
dipesan, padahal beda itulah yang mencegah oversell.

### BR-016 Bahasa aplikasi: Inggris
Semua yang ditampilkan web app berbahasa Inggris: teks UI, email (termasuk email undangan), serta
`title`/`detail` error API. Kode, identifier, dan `openapi.yaml` juga berbahasa Inggris. Dokumen
kontrak ditulis dalam Bahasa Indonesia.

*Kenapa:* satu bahasa di produk dan codebase berarti teks, error, dan tipe hasil generate tidak
pernah perlu diterjemahkan antar lapisan; dokumen berbahasa Indonesia untuk orang-orang yang
mendefinisikan sistemnya.

---

## 2. Auth & tim

### BR-020 Email unik di seluruh sistem dan menentukan tenant
Satu baris user milik tepat satu tenant, dan email-nya unik di semua tenant. Login hanya menerima
email dan password; tenant dibaca dari baris user.

*Kenapa:* dengan email yang sama di dua tenant, tidak ada apa pun di request login yang bisa
membedakan keduanya. Konsekuensinya diterima: agensi yang mengelola dua merchant butuh dua alamat
email.

### BR-021 Semua login gagal terlihat sama
Password salah, email tidak dikenal, dan akun nonaktif semuanya mengembalikan `401` yang sama.

*Kenapa:* perbedaan apa pun memberi tahu penyerang email mana yang ada.

### BR-022 Sesi berumur pendek dan refresh berotasi
- Access token adalah JWT 15 menit, disimpan hanya di memori, tidak pernah di `localStorage`.
- Refresh token tinggal di cookie `httpOnly`, `Secure`, `SameSite=Lax` dan tidak pernah ada di body
  respons.
- Setiap refresh menerbitkan refresh token baru dan mencabut yang lama. **Refresh token yang
  dipakai ulang berarti pencurian:** seluruh rantai rotasinya dicabut dan user dikeluarkan dari
  semua sesi.
- Password di-hash dengan `argon2id` (memori 64 MB, 3 iterasi).

*Kenapa:* access token yang pendek menjaga konteks tenant tetap segar, dan cookie yang tidak bisa
dibaca script menjauhkan token berumur panjang dari jangkauan.

### BR-023 Lima peran tetap; izin hanya berasal dari peran
Perannya adalah `owner`, `admin`, `ops`, `warehouse`, dan `viewer`. Semuanya di-seed, sama untuk
setiap tenant, dan Fase 1 tidak punya peran kustom atau override per user. Sebuah izin berbentuk
`resource:action`, dengan hanya dua aksi, `read` dan `write`, karena menghapus berarti mengarsipkan
(BR-012) sehingga termasuk menulis. Hanya owner yang bisa memberi peran `owner` kepada orang lain.
Matriks lengkapnya ada di `04-api-spec.md` §3. Ringkasnya:

| Peran | Maksud |
|---|---|
| `owner` | `admin` ditambah `settings:write`, tidak lebih. |
| `admin` | Semua hal operasional. |
| `ops` | Produk, varian, media, ekspor. Membaca kategori dan brand, tidak menulisnya. Tidak mengelola user. |
| `warehouse` | Membaca katalog. Peran ini di-seed sekarang supaya himpunan izinnya tidak berubah bentuk saat Fase 4 memberinya stok. |
| `viewer` | Membaca, tidak pernah menulis. |

### BR-024 `403` menyebut izin yang kurang
`403 permission_denied` menaruh izin yang dibutuhkan di `detail` (`requires users:write`).

*Kenapa:* pemanggil bisa membedakan "kamu tidak bisa melakukan ini" dari "minta X ke owner-mu".

### BR-025 Yang tidak bisa dilakukan tidak ditampilkan
Layar atau aksi yang tidak diizinkan untuk user **tidak ada**, bukan dinonaktifkan. User `ops` tidak
melihat navigasi Team, API keys, atau billing; `viewer` tidak melihat tombol simpan di mana pun.

*Kenapa:* kontrol yang dinonaktifkan mengiklankan kemampuan dan memicu tiket support.

### BR-026 Undangan
Owner atau admin mengundang dengan email, nama, dan peran. User berstatus `invited` tanpa password
sampai ia menerima undangan, menyetel password, dan menjadi `active`. Tautan undangan kedaluwarsa
setelah **7 hari** dan bisa dikirim ulang selama user masih `invited`. Begitu user `active`, semua
tautan yang pernah dikirim kepadanya berhenti bekerja.

### BR-027 Menonaktifkan user
User dinonaktifkan, tidak pernah dihapus: rujukan `created_by` di tempat lain harus tetap bisa
dijelaskan. Menonaktifkan user mencabut refresh token-nya, sehingga ia keluar paling lambat dalam
15 menit, saat access token kedaluwarsa. Owner aktif terakhir di sebuah tenant tidak bisa
dinonaktifkan atau diturunkan perannya.

*Kenapa:* tanpa penjaga owner ini, tenant bisa mengunci dirinya sendiri dari pengaturannya.

### BR-028 API key
- Key disimpan sebagai hash SHA-256, dan plaintext-nya ditampilkan **tepat sekali**, saat dibuat.
- Daftar hanya menampilkan prefix key (`bk_live_7f3a`), cukup untuk membedakan satu key dari yang
  lain.
- Key membawa himpunan izin eksplisit, yang harus merupakan subset dari izin pembuatnya. Key
  dicabut, tidak pernah diedit.

*Kenapa:* tanpa pengecekan subset, admin bisa membuat key dengan `settings:write` dan mendapat
akses lebih besar daripada yang diizinkan perannya sendiri.

### BR-029 Default tenant
Tenant baru memakai zona waktu `Asia/Jakarta` dan mata uang `IDR` secara default, tanpa ada yang
memilihnya. Field uang baru memakai mata uang tenant secara default.

---

## 3. Katalog

### BR-030 Brand
`slug` brand berasal dari namanya dan unik per tenant, termasuk brand yang diarsipkan, jadi dua
brand yang namanya menghasilkan slug sama ditolak. `channel_brand_ids` memetakan brand ke id brand
milik masing-masing marketplace (`{"shopee": "12345"}`) dan diisi sekali per brand, bukan per
produk. Brand pada produk bersifat opsional.

*Kenapa:* marketplace menolak listing yang id brand-nya tidak mereka kenal. Mengumpulkan id itu saat
onboarding butuh dua menit; mencarinya lagi enam bulan kemudian, saat Fase 3 membutuhkannya, butuh
berjam-jam.

### BR-031 Setiap kind kategori adalah pohon yang independen
`kind` adalah salah satu dari `category`, `series`, `collection`, `activity`, atau `custom`, dan
setiap kind adalah pohonnya sendiri. Produk bisa masuk ke kategori di beberapa pohon sekaligus:
sebuah jaket bisa berada di `apparel.outerwear.jackets`, `hiking`, dan `ss26`.

*Kenapa:* ini dikirim di Fase 1 karena menambahkannya belakangan berarti men-tag ulang seluruh
katalog secara manual.

### BR-032 Database yang menurunkan path kategori
`path` (sebuah `ltree`) dihitung oleh trigger dari `name` dan `parent_id`. Klien tidak pernah
mengirimnya (BR-008). Mengganti nama atau memindahkan kategori menulis ulang `path` setiap
keturunannya dalam statement yang sama.

*Kenapa:* kasus sulitnya adalah pemindahan. Kalau kode aplikasi harus ingat menulis ulang
keturunan, satu jalur tulis yang lupa akan meninggalkan pohon yang rusak tanpa suara.

### BR-033 Memindahkan atau mengganti nama kategori tidak pernah menyentuh produk
Penugasan produk merujuk id kategori, tidak pernah path-nya. Konfirmasi pemindahan menyatakannya,
lengkap dengan jumlahnya: "Move Jackets and its 4 subcategories? 128 produk will keep their
assignments."

*Kenapa:* user mengira pemindahan akan men-tag ulang produk, lalu menghindari fiturnya. Menyatakannya
secara eksplisit membuat fitur itu dipakai.

### BR-034 Tidak ada siklus kategori
Kategori tidak bisa dipindahkan ke bawah keturunannya sendiri. Klien memblokirnya, dan database
menolaknya kalau dipaksa.

### BR-035 Nama kategori boleh berulang
Dua kategori bernama "Jackets" di bawah induk berbeda tidak masalah. Saudara dengan nama sama juga
diizinkan; database membedakan label path mereka (`jackets`, `jackets_1`).

### BR-036 Kategori yang sedang dipakai tidak bisa dihapus
Menghapus kategori yang punya anak atau produk yang ditugaskan ditolak dengan
`409 category_in_use`, dan responsnya menyebut berapa anak dan berapa produk yang menghalanginya.

### BR-037 Siklus hidup produk
`draft` → `active` → `archived`. Produk baru dimulai sebagai `draft`. Hanya `draft → active` yang
punya gerbang (BR-038).

### BR-038 Publish check
Memindahkan produk dari `draft` ke `active` mensyaratkan:
1. setiap varian yang tidak diarsipkan punya SKU;
2. setiap varian yang tidak diarsipkan punya harga lebih dari nol;
3. minimal satu gambar;
4. minimal satu kategori dengan kind `category`.

Kalau gagal, produk tetap `draft` dan responsnya mencantumkan setiap kegagalan, supaya klien bisa
menautkan ke sel yang bermasalah (`422 publish_check_failed`). Ini pengecekan di jalur publish,
**bukan** constraint tabel.

*Kenapa:* draft harus cepat dibuat. Tetapi varian tanpa SKU tidak bisa di-bulk-update di Fase 2
atau dicocokkan ke listing marketplace di Fase 3, jadi pengecekan inilah tempat masalah itu
ditangkap.

### BR-039 SKU opsional selama draft dan unik begitu diisi
Berapa pun varian boleh tanpa SKU. SKU yang diisi unik di dalam tenant, lintas semua produk.
Bentrokan menghasilkan `409 duplicate_sku` dan menyebut produk yang sudah memegangnya.

### BR-040 Sumbu opsi bersifat posisional
`option_names` sebuah produk adalah daftar terurut (`["Colour","Size"]`), dan `option_values`
setiap varian mengikuti posisi yang sama (`["Black","S"]`). **Kalau produk punya sumbu Colour,
sumbu itu di posisi 0.** Produk tanpa sumbu Colour tidak masalah. Tidak ada dua varian hidup dalam
satu produk yang punya `option_values` sama.

*Kenapa:* posisi membuat editor matriks murah: satu query mengembalikan setiap varian beserta
nilainya, dan klien mengubahnya menjadi grid. Tabel join akan membuat setiap render grid menjadi
join tiga arah.

### BR-041 Matriks varian disimpan dalam satu request; satu baris buruk gagal sendirian
Editor matriks mengirim seluruh grid yang dimaksud dalam satu request, dan server menghitung apa
yang harus dibuat, diubah, dan diarsipkan. Baris yang gagal (misalnya SKU duplikat) gagal
**sendirian**: baris lain tetap tersimpan, dan respons melaporkan hasil untuk setiap baris. Baris
yang cocok dengan varian yang diarsipkan memulihkannya, jadi colourway yang dihapus lalu
ditambahkan kembali tetap memegang SKU-nya.

*Kenapa:* tanpa ini, klien akan menembakkan puluhan request terpisah tanpa transaksi, dan kegagalan
sebagian akan meninggalkan grid yang tidak dipahami user maupun sistem.

---

## 4. Media

### BR-050 Simpan object key, tidak pernah URL
Database menyimpan object key R2. URL diterbitkan saat seseorang membaca media (BR-053).

*Kenapa:* URL kedaluwarsa; key tidak.

### BR-051 Unggahan langsung ke R2, lalu dikonfirmasi
Browser mengunggah langsung ke R2 dengan `PUT` presigned; byte gambar tidak pernah melewati API.
Tipe yang diterima adalah JPEG, PNG, dan WebP, masing-masing sampai 20 MB. Unggahan baru dianggap
ada setelah klien mengonfirmasinya, dan konfirmasi mengecek content type serta ukuran objek dengan
`HEAD` R2. Key tidak bisa didaftarkan untuk objek yang tidak pernah diunggah.

### BR-052 Turunan gambar dibuat secara asinkron
Worker membuat turunan WebP 1600, 800, dan 200 px (libvips). Turunan siap dalam 15 detik p95.
Mengunggah tidak pernah memblokir form produk.

### BR-053 Tata letak bucket dan umur tautan
Satu bucket, dengan setiap objek di bawah prefix tenant-nya.

| Prefix | Isi | Umur `GET` presigned |
|---|---|---|
| `{tenant}/products/{product}/{media}/…` | Original beserta turunannya | 1 jam |
| `{tenant}/exports/{job}.csv` | Ekspor katalog | 15 menit |

---

## 5. Ekspor

### BR-060 Pekerjaan panjang berjalan sebagai job
Ekspor berjalan asinkron: request mengembalikan `job_id` dan klien melakukan polling ke
`GET /v1/jobs/{id}`. Endpoint jobs dipakai ulang tanpa perubahan oleh setiap fase berikutnya.

### BR-061 Template mengikuti sheet bulk-upload setiap marketplace
Templatenya adalah `shopee`, `tokopedia`, `tiktok`, `lazada`, `blibli`, dan `generic`. Kolom brand
berasal dari `brands.channel_brand_ids`; kategori marketplace dan atribut wajibnya berasal dari
`products.attributes.channel.{marketplace}`. Tidak ada tabel `channels`: merchant mengunggah file-nya
sendiri.

*Kenapa:* ini gladi resik untuk Fase 3. Pemetaan atribut yang salah di sini juga akan salah di
integrasi API, dan di sinilah tempat yang jauh lebih murah untuk mengetahuinya.

### BR-062 Pemetaan yang hilang tidak pernah memblokir ekspor
Kalau produk tidak punya pemetaan untuk marketplace yang dipilih, ekspor tetap dibuat dengan sel
itu kosong. Job yang selesai mencantumkan produk yang belum lengkap, dikelompokkan menurut apa
yang hilang.

*Kenapa:* merchant memperbaiki semuanya dalam satu kali jalan, alih-alih menemukan masalah baris
demi baris di uploader marketplace.

### BR-063 Tautan unduhan kedaluwarsa dalam 15 menit dan bisa dibuat ulang

### BR-064 CSV terbuka rapi di Excel dengan setelan locale Indonesia
Harga ditulis sedemikian rupa sehingga locale dengan koma desimal tidak merusaknya.

---

## Ketertelusuran

Setiap aturan muncul di tempat yang bisa dilihat user atau pemanggil, dan dibuktikan oleh item
backlog.

| BR | Muncul di | Dibuktikan oleh |
|---|---|---|
| 001 | setiap tabel tenant | P1-006, P1-008, P1-009 |
| 002 | setiap request | P1-007 |
| 003 | `POST /auth/login`, setiap route | P1-008, P1-011 |
| 004 | `variants`, `products → brands` | P1-020, P1-026 |
| 005–007 | setiap payload | P1-028 |
| 008 | setiap create dan `PATCH` | P1-024, P1-028 |
| 009 | setiap create dan `PATCH` | P1-028 |
| 010 | `PATCH` produk, varian, brand, kategori | P1-021, P1-024, P1-028, P1-029 |
| 011 | setiap error | P1-013 |
| 012 | setiap `DELETE` katalog | P1-021, P1-028, P1-029 |
| 013 | logging | P1-016 |
| 014 | setiap route | P1-015 |
| 015 | `01-product-requirements.md` §2, empty state daftar produk | P1-069 |
| 016 | semua layar, email, dan respons error | review |
| 020–022 | Alur: mengundang rekan tim; sign-in | P1-010, P1-011, P1-014 |
| 023–024 | Alur: mengundang rekan tim | P1-012 |
| 025 | Alur: mengundang rekan tim | P1-066 |
| 026–027 | Alur: mengundang rekan tim | P1-064 |
| 028 | Layar API keys | P1-065, P1-067 |
| 029 | Alur: onboarding | P1-071, P1-068 |
| 030 | Alur: onboarding; brand manager | P1-020, P1-021, P1-031 |
| 031 | Alur: membuat produk | P1-027 |
| 032–035 | Alur: menata ulang kategori | P1-022, P1-023, P1-032 |
| 036 | Alur: menata ulang kategori | P1-024 |
| 037–038 | Alur: membuat produk | P1-028, P1-049 |
| 039 | Alur: membuat produk | P1-026, P1-029 |
| 040–041 | Alur: membuat produk | P1-025, P1-040, P1-041, P1-046 |
| 050–053 | Alur: membuat produk (media) | P1-042, P1-043, P1-044, P1-045, P1-048 |
| 060–064 | Alur: ekspor | P1-060, P1-061, P1-062, P1-063 |
