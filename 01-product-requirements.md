# Fase 1 — Catalog & Foundation · Kebutuhan Produk

**Rilis** Minggu 1–12 · **Status** Produksi, dipakai merchant pilot
**Bergantung pada** tidak ada · **Dibutuhkan oleh** Fase 2, 3 dan 4

Apa fase ini, siapa yang memakainya, apa yang mereka lakukan dengannya, dan bagaimana kita tahu
setiap bagiannya selesai. Aturan dirujuk sebagai `BR-xxx` dan tinggal di `02-business-rules.md`.
Skemanya ada di `03-erd.md`, kontrak HTTP di `04-api-spec.md`, serta urutan bangun dan status di
`05-backlog.md`.

---

## 1. Apa fase ini

Sebuah product master: satu sumber kebenaran bagi merchant untuk apa yang mereka jual (produk,
varian, brand, kategori, gambar). Di atasnya ada model tim yang sungguhan, dan ia mengekspor CSV
dalam format yang diterima marketplace.

Fase ini juga meletakkan semua fondasi yang diandalkan fase-fase berikutnya: tenancy, autentikasi,
izin, postur audit, konvensi API, dan deployment. Kira-kira separuh pekerjaan di fase ini tidak
pernah terlihat oleh pengguna, dan itulah alasan Fase 2–4 bisa dibangun dengan cepat.

### Kenapa layak dirilis sendiri

Sebagian besar merchant Indonesia menyimpan data produk di spreadsheet yang disalin manual ke seller
centre tiap marketplace. Spreadsheet itu cepat basi, saling bertentangan antar-channel, dan tidak
punya riwayat. Fase 1 menggantinya dengan sesuatu yang punya struktur, peran, galeri gambar, dan
ekspor yang cocok dengan yang benar-benar diterima Shopee dan Tokopedia untuk bulk upload.

Itu berguna sejak hari rilis, dan ia mengisi katalog yang dipakai setiap fase berikutnya. Merchant
yang sudah dua minggu merapikan 3.000 SKU di Fase 1 masih akan ada ketika Fase 3 menghubungkan
channel mereka.

---

## 2. Ruang lingkup

### Di fase ini

Produk, varian, dan matriks varian · brand dengan brand id marketplace · kategori dalam pohon-pohon
yang independen · gambar produk · tim, peran, dan API key · ekspor CSV marketplace · onboarding
wizard.

**Bahasa aplikasi: Inggris** (BR-016). Semua yang tampil di web app (teks UI, email, pesan error
API) berbahasa Inggris. Dokumen kontrak ini berbahasa Indonesia.

### Sengaja tidak ada di fase ini

- **Tanpa stok.** Tidak ada kuantitas, lokasi, atau reservasi; stok tidak terbatas (BR-015).
- **Tanpa order.** Belum ada yang dijual lewat sistem ini.
- **Tanpa koneksi marketplace.** Ekspor berupa CSV yang diunggah merchant sendiri.
- **Tanpa bulk edit atau impor CSV.** Fase 1 hanya buat-dan-ubah.

Sampaikan keempatnya ke merchant pilot sebelum onboarding. Pengguna akan menanyakan ini di minggu
pertama; siapkan jawabannya:

| Permintaan | Jawaban | Datang di |
|---|---|---|
| "Di mana saya mengatur stok?" | Belum ada stok. Kelola kuantitas di marketplace seperti sekarang. | Fase 4 |
| "Bisakah saya mengimpor spreadsheet saya?" | Belum: buat produk di sini, atau tunggu satu fase. | Fase 2 |
| "Bisakah saya mengubah 200 produk sekaligus?" | Belum. | Fase 2 |
| "Apakah tersinkron ke Shopee?" | Belum. Ekspor CSV lalu unggah sendiri. | Fase 3 |
| "Di mana order saya?" | Belum ada. | Fase 2 |

**Pertanyaan soal stok adalah yang paling penting.** Merchant yang mengira Fase 1 mengelola inventori
akan menyimpulkan produknya rusak, bukan masih awal. Katakan di percakapan penjualan, katakan lagi
saat onboarding, dan taruh di empty state daftar produk.

---

## 3. Pengguna

Owner atau admin merchant menyiapkan sistem, dan satu atau dua staf merchandising atau operasional
bekerja di dalamnya setiap hari. Staf gudang tidak punya alasan membukanya sampai Fase 4. Peran dan
apa yang boleh dilakukan masing-masing: BR-023.

---

## 4. Layar

| Screen | Pengguna utama | Tujuan |
|---|---|---|
| Sign in / accept invitation | Semua | Pintu masuk |
| Onboarding wizard | Owner | Setup tenant, brand pertama, pohon kategori pertama |
| Product list | Ops | Ruang kerja harian. Cari, filter, pilih massal |
| Product editor | Ops | Judul, deskripsi, brand, atribut, kategori, media |
| **Variant matrix editor** | Ops | Layar yang membedakan produk ini. Grid opsi × nilai |
| Category manager | Admin | Satu pohon per `kind`; seret untuk memindah, ganti nama |
| Brand manager | Admin | Brand beserta brand id marketplace-nya |
| Media library | Ops | Gambar per produk: urutkan ulang, tetapkan ke varian |
| Team & roles | Owner/Admin | Undang, tetapkan peran, nonaktifkan |
| API keys | Owner/Admin | Terbitkan, lihat prefix, cabut |
| Export | Ops | Pilih template marketplace, unduh CSV |

Layar yang tidak diizinkan untuk pengguna sama sekali tidak muncul di navigasinya (BR-025).

---

## 5. Alur

### 5.1 Onboarding pertama kali

**Aktor** Owner, login pertama setelah signup. **Tujuan:** dari kosong menjadi katalog sungguhan.

```
1. Accept invitation → atur password → mendarat di product list yang kosong
2. Onboarding wizard (bisa dilewati, bisa dilanjutkan):
     a. Konfirmasi nama usaha, zona waktu (Asia/Jakarta), mata uang (IDR)
     b. Buat brand pertama, dengan langkah opsional "I sell on Shopee/Tokopedia"
        yang menangkap channel_brand_ids selagi konteksnya masih segar
     c. Buat pohon kategori awal, atau terima usulan untuk vertikal mereka
     d. Undang satu rekan tim
3. Mendarat di "Create your first product" dengan langkah berikutnya yang terlihat
```

**Kriteria penerimaan**
- Wizard bisa dilewati di langkah mana pun dan dilanjutkan dari banner di produk list.
- Merchant yang melewatinya sepenuhnya tetap bisa membuat produk; brand dan kategori opsional
  (BR-030).
- Zona waktu dan mata uang terisi otomatis tanpa pengguna memilih (BR-029).
- Langkah brand menangkap `channel_brand_ids` (BR-030).

### 5.2 Membuat produk dengan varian

**Aktor** Ops. **Tujuan:** produk yang siap dijual dengan grid ukuran/warna lengkap. **Target:**
di bawah 3 menit untuk produk 15 varian.

```
Product list → "New product"
  ↓
Product editor
  · Judul, deskripsi
  · Brand (select yang bisa dicari, "＋ create" inline)
  · Kategori (satu picker per kind)
  · Atribut (key/value; key usulan per kategori)
  · Media (drag-drop, unggah langsung ke R2 dengan progress per file)
  ↓
"Add options" → definisikan option_names, mis. Colour dan Size
  ↓
Variant matrix editor
  · Isi nilai per opsi: Black, White / S, M, L, XL, XXL
  · Grid merender 2 × 5 = 10 sel
  · Isi SKU, harga, berat per sel
  · Tempel kolom dari Excel · Fill-down · Harga massal ±%
  ↓
Save  →  satu PUT /variant-matrix  →  10 varian dibuat
  ↓
Set status Active  →  publish check berjalan
```

Kalau publish check (BR-038) gagal, setiap kegagalan didaftar dengan tautan ke sel yang salah, dan
produk tetap `draft`.

**Kriteria penerimaan**
- Grid 2 × 5 merender 10 sel dan tersimpan dalam satu request di bawah 2 detik (BR-041).
- Menempel kolom 10 baris dari Excel mengisi 10 sel tanpa memuat ulang halaman.
- SKU duplikat hanya menggagalkan **baris itu**; sembilan lainnya tetap tersimpan, dan sel yang gagal
  disorot dengan nama produk yang bentrok (BR-039, BR-041).
- Penyesuaian harga massal (± nominal atau %) menampilkan pratinjau sebelum diterapkan.
- Mengunggah gambar 5 MB menampilkan progress dan tidak pernah memblokir form (BR-051, BR-052).
- Meninggalkan editor dengan perubahan yang belum disimpan meminta konfirmasi sebelum berpindah.
- Mengaktifkan produk yang gagal publish check mendaftar setiap kegagalan dan membiarkannya `draft`
  (BR-038).
- Satu produk bisa berada di kategori dari beberapa kind sekaligus (BR-031).

### 5.3 Menata ulang pohon kategori

**Aktor** Admin. **Tujuan:** memindah "Jackets" dari Outerwear ke induk baru Technical Outerwear.

```
Category manager → pilih kind: Category
  ↓
Seret "Jackets" ke "Technical Outerwear"
  ↓
Confirm dialog: "Move Jackets and its 4 subcategories? 128 products will keep
                 their assignments."
  ↓
Save → satu PATCH → path setiap turunan ditulis ulang dalam satu statement
```

**Kriteria penerimaan**
- Confirm dialog menyatakan bahwa penetapan produk tidak terpengaruh, beserta jumlahnya (BR-033).
- Memindah node dengan 200 turunan selesai di bawah 1 detik (BR-032).
- Menyeret induk ke turunannya sendiri ditolak oleh klien dan, kalau dipaksa, oleh database dengan
  pesan yang jelas (BR-034).
- Dua kategori bernama "Jackets" di bawah induk berbeda sama-sama berfungsi (BR-035).
- Mengganti nama "Outerwear" membiarkan semua penetapan produk utuh (BR-033).
- Menghapus kategori yang punya anak atau produk ditolak dengan jumlah apa yang menghalanginya
  (BR-036).

### 5.4 Ekspor untuk marketplace

**Aktor** Ops. **Tujuan:** mengunggah 400 produk ke Shopee tanpa mengetik ulang.

```
Export → pilih template: Shopee
       → filter: status = Active, category = Apparel
       → Generate
  ↓
Job async, progress ditampilkan
  ↓
"412 products ready" → Download CSV
  ↓
Merchant mengunggahnya sendiri ke Shopee Seller Centre
```

**Kriteria penerimaan**
- 10.000 varian terekspor di bawah 60 detik (BR-060).
- Produk dengan mapping yang hilang tidak memblokir ekspor; mereka didaftar, dikelompokkan menurut apa
  yang hilang (BR-062).
- Tautan unduhan kedaluwarsa setelah 15 menit dan bisa dibuat ulang (BR-063).
- CSV terbuka di Excel dengan pengaturan locale Indonesia tanpa merusak harga (BR-064).

### 5.5 Mengundang rekan tim

**Aktor** Owner. **Tujuan:** memberi akses ke merchandiser tanpa menyerahkan billing.

```
Team & roles → Invite → email + peran (ops)
  ↓
Email undangan → Accept → atur password → mendarat di product list
  ↓
Pengguna ops melihat Products, Categories, Brands, Media, Export.
Mereka TIDAK melihat Team, API keys, atau billing.
```

**Kriteria penerimaan**
- Pengguna `ops` mendapat `403` yang menyebut izin yang dibutuhkan di endpoint manajemen pengguna mana
  pun (BR-024), dan navigasi sama sekali tidak menampilkan layarnya (BR-025).
- Menonaktifkan pengguna mengeluarkannya paling lambat dalam 15 menit (BR-027).
- Tautan undangan kedaluwarsa setelah 7 hari dan bisa dikirim ulang (BR-026).
- `viewer` tidak bisa menyimpan apa pun di mana pun; tombol simpan tidak ada, bukan sekadar nonaktif
  (BR-025).

---

## 6. Arsitektur

### 6.1 Bentuk

Satu modul Go, satu image yang bisa di-deploy, tiga entrypoint. Ini modular monolith, bukan
microservices: paket domain dipisahkan oleh aturan import, bukan panggilan jaringan, sehingga
memisahkan sebuah service nanti adalah pekerjaan mekanis, bukan arkeologi.

```
cmd/api       HTTP API. Melayani front end Next.js dan integrator pihak ketiga.
cmd/worker    Konsumen queue. Di Fase 1: hanya pembuatan turunan gambar dan ekspor CSV.
cmd/migrate   Migrasi skema. Berjalan sampai selesai lalu keluar.
```

### 6.2 Deployment: satu VPS

Front end dan back end di satu mesin. Ukuran awal: **8 vCPU / 16 GB / NVMe**, Ubuntu LTS, Docker
Compose.

```
Cloudflare (DNS, WAF, batas laju di edge)  ──►  VPS
                                                 ├── Caddy         :443   TLS + reverse proxy
                                                 ├── Next.js       :3000
                                                 ├── cmd/api  ×2   :8080  (rolling restart)
                                                 ├── cmd/worker ×1        (tanpa ingress)
                                                 ├── PostgreSQL 18        volume NVMe lokal
                                                 └── Redis 8              volume lokal, AOF aktif

Cloudflare R2  ◄── gambar produk, ekspor
```

Dua replika API bukan untuk throughput: keduanya memungkinkan deploy mengosongkan satu container
pada satu waktu.

**Apa yang jadi tanggung jawabmu karena satu mesin.** Masing-masing ini biasanya tugas managed
service, dan masing-masing adalah cara kehilangan data merchant:

- **Backup.** `pgBackRest` atau `wal-g` ke R2: base backup tiap malam plus pengarsipan WAL terus-
  menerus. **Uji restore sebelum merchant pilot pertama**, bukan sesudahnya. Ini risiko terbesar
  Fase 1 dan sebuah kriteria keluar, bukan sekadar bagus kalau ada.
- **Batas sumber daya.** Atur `cpus` dan `mem_limit` per service di Compose, atau lonjakan
  pemrosesan gambar di worker akan melaparkan PostgreSQL dan membuat seluruh mesin macet.
- **Tuning PostgreSQL untuk mesin bersama.** `shared_buffers` ≈ 25% RAM,
  `effective_cache_size` ≈ 50%, `max_connections` = 100 dengan batas pool keras di pgx.
- **Sisa ruang disk.** Peringatan di 70%.

**Satu origin, dua proses.** Caddy menyajikan aplikasi Next.js di `/` dan mem-proxy `/v1/*` ke
`cmd/api` di domain yang sama, sehingga browser hanya pernah berbicara dengan satu origin. Itulah
yang membuat refresh token cukup berupa cookie `SameSite=Lax` biasa tanpa CORS di mana pun dalam
sistem. Pengembangan lokal meniru ini dengan rewrite Next.js, bukan dengan melonggarkan apa pun di
API: API yang harus tahu soal origin browser bisa salah menilainya.

**Kapan pindah dari mesin ini.** PostgreSQL dulu, karena kegagalannya menghilangkan data. Lalu
worker. Keduanya tidak butuh perubahan kode, hanya connection string baru.

### 6.3 Pilihan komponen

| Urusan | Pilihan | Kenapa |
|---|---|---|
| Router | `chi` | Kompatibel dengan `http.Handler` stdlib, tanpa terkunci framework |
| Akses DB | `pgx/v5` + `sqlc` | Query bertipe yang dibangkitkan dari SQL sungguhan. RLS dan row locking butuh SQL yang kamu kendalikan |
| Migrasi | `golang-migrate` | SQL up/down polos, bisa direview di PR |
| Queue | Redis Streams | Hampir tidak dibutuhkan di Fase 1, tapi menyiapkannya sekarang menghindari retrofit di Fase 3 |
| Object storage | Cloudflare R2 | Egress nol, kompatibel S3. Gambar produk adalah sebagian besar byte yang disimpan |
| Front end | Next.js 15 App Router, Tremor | Server Components untuk tampilan daftar yang padat; client component hanya untuk editor grid |
| Auth | JWT access (15 menit) + refresh berotasi, `argon2id` | Access token yang pendek menjaga konteks RLS tetap segar |
| Observability | OpenTelemetry | Disiapkan di Fase 1 agar jalur webhook Fase 3 bisa ditelusuri sejak hari pertama |

### 6.4 Pagar pengaman tenancy

Aturannya BR-001 sampai BR-004. Inilah pengecekan yang menjaganya tetap benar:

- **Tes migrasi.** CI mendaftar `information_schema.tables` dan gagal kalau ada tabel dengan kolom
  `tenant_id` yang tidak punya policy RLS aktif. Tabel baru tanpa policy tidak bisa di-merge.
- **Tes isolasi.** Setiap route terdaftar diuji dengan dua tenant yang di-seed; token tenant A harus
  mengembalikan nol baris milik tenant B.
- **Tidak ada `pool.Query` di luar `internal/db`**, ditegakkan oleh lint rule batas import.
- **Index komposit diawali `tenant_id`.** RLS menambahkan predikat itu ke setiap query; index yang
  tidak bisa melayaninya hanya beban mati.

---

## 7. Kebutuhan non-fungsional

### 7.1 Target

| Jalur | Target |
|---|---|
| Product list, 10k produk | p95 < 600ms first byte |
| Simpan matriks varian, 100 sel | < 2s |
| Unggah gambar → turunan siap | < 15s p95 |
| Ekspor katalog, 10k varian | < 60s, job async |

### 7.2 Asumsi skala, tahun pertama

Per tenant: 100k varian, 20 pengguna bersamaan, 20 GB di R2. Satu PostgreSQL dengan index yang baik
menanganinya dengan nyaman. Jangan sharding dan jangan optimasi sebelum dibutuhkan.

### 7.3 Ketersediaan

**99,5% per bulan** di satu VPS: sekitar 3,6 jam per bulan, yang habis oleh satu reboot kernel plus
satu deploy yang buruk. 99,9% tidak bisa diklaim dengan jujur tanpa host redundan; jangan masukkan ke
kontrak pelanggan sampai PostgreSQL sudah pindah dari mesin ini.

**RPO** 5 menit lewat pengarsipan WAL. **RTO** 1 jam, dan angka itu baru nyata setelah latihan
restore dijalankan.

### 7.4 Keamanan

Hanya TLS 1.3, HSTS, Cloudflare WAF. Password, sesi, dan API key: BR-022, BR-028. Logging:
BR-013.

### 7.5 Pengujian

| Lapisan | Pendekatan |
|---|---|
| Unit | Slugifikasi, diff matriks, pengecekan izin |
| Integrasi | PostgreSQL sungguhan lewat testcontainers. RLS dan trigger tidak bisa di-mock dengan bermakna |
| Isolasi tenant | Suite yang dibangkitkan atas setiap route terdaftar |
| Migrasi | Setiap migrasi diterapkan ke snapshot hasil restore di CI |
