# Threads Data Scraper (Playwright)

Proyek ini adalah instrumen ekstraksi data otomatis untuk platform Threads (berbasis SPA). Menggunakan Python dan Playwright, skrip ini menavigasi halaman publik, menangani *infinite scroll* yang kompleks, menerapkan autentikasi berbasis sesi (untuk menghindari rate-limit), dan mengekstrak metrik unggahan ke dalam format terstruktur.

## Fitur Utama
- **Autentikasi Sesi:** Menyimpan *cookies* login (`auth.json`) untuk melewati batasan tampilan *Guest* dari Meta.
- **Smart Infinite Scroll:** Menggunakan injeksi JavaScript (*smooth scrolling*) yang dipadukan dengan jeda acak dan mekanisme *jiggle* (PageUp/End) untuk memicu pemuatan asinkron (AJAX) secara natural.
- **Dual Output System:** Menghasilkan dua set data secara bersamaan:
  - `Raw Dataset`: Data mentah yang berisi elemen UI asli (untuk keperluan *debugging*).
  - `Clean Dataset`: Data steril dengan ISO 8601 Timestamp, pemisahan *time-ago*, dan teks bersih tanpa elemen UI yang tidak relevan (siap untuk ML/Data Science).

---

## Persyaratan Teknologi
*   Python 3.8+
*   Playwright (Automation Library)
*   Python-dotenv (Environment Management)

---

## Cara Instalasi & Penggunaan

**1. Clone Repositori & Setup Virtual Environment:**
git clone https://github.com/Lunaruuuuu/threads-scraper.git
cd threads-scraper
python -m venv venv

# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

**2. Instal Dependensi:**
pip install -r requirements.txt
playwright install chromium

**3. Konfigurasi Environment:**
Buat file bernama .env di root direktori dan sesuaikan parameter berikut:
TARGET_URL=[https://www.threads.net/@instagram](https://www.threads.net/@instagram)
MAX_POSTS=30

**4. Inisialisasi Sesi Login:**
Threads membatasi jumlah unggahan yang dapat dilihat pengguna tanpa login. Jalankan skrip ini, login dengan akun dummy (cadangan), lalu tekan ENTER di terminal.
python login.py

**5. Jalankan Scraper:**
python scraper.py

## Analisis Tantangan Anti-Scraping & Solusinya
Mengekstrak data dari platform Single Page Application (SPA) milik Meta menghadirkan beberapa tantangan teknis:

*1. Rate-Limiting & Unauthenticated Block:*
Terlalu banyak memuat data (scroll) tanpa session cookies memicu munculnya overlay login (terkadang tidak kasat mata) yang mengunci DOM dan menghentikan proses scraping.

Solusi: Proyek ini menggunakan pendekatan Two-Step Authentication melalui login.py untuk menyimpan status sesi (local storage & cookies), lalu memuatnya kembali (storage_state) pada saat menjalankan scraper.

*2. Intersection Observer yang Ketat (Stuck Scrolling):*
Threads memuat data baru secara asinkron (Lazy Loading) berdasarkan pemicu posisi scroll pengguna. Jika skrip Playwright melompat langsung ke bawah halaman (PageDown secara agresif), pemicu ini akan terlewat dan proses pemuatan data terhenti (macet di 16 atau 29 post).

Solusi: Mengimplementasikan smooth scroll menggunakan eksekusi JavaScript (menggulir 300px per 150ms) yang dipadukan dengan jeda adaptif untuk menunggu respons jaringan, serta trik jiggle (PageUp lalu End) untuk memicu ulang observer jika deteksi stuck terjadi.

*3. Dynamic CSS & Elemen Teks Menyatu:*
Threads sering menggabungkan teks konten dengan elemen UI secara dinamis (seperti teks 'Terjemahkan' yang menempel di ujung paragraf, atau angka metrik yang tidak memiliki elemen pemisah yang jelas).

Solusi: Menggunakan pendekatan pembersihan bertahap: memfilter array text node, menggunakan Regex sapu jagat re.sub(r'(?i)\b(terjemahkan|translate)\b', '', teks) pada kalimat akhir, dan memformat ulang nilai time_ago (misalnya dari "1hari" menjadi "1 hari").

## Sampel Output
Skrip menyimpan data dalam dua format: JSON (untuk integritas struktur) dan CSV (untuk kemudahan analisis). Output .csv secara spesifik diformat dengan encoding UTF-8 sehingga emoji dan karakter khusus tetap terbaca secara utuh, ideal untuk langsung diimpor ke Pandas DataFrame.

JSON Structure (Contoh Clean Dataset):

JSON
[
    {
        "username": "@zuck",
        "timestamp": "2026-09-25 16:50:21",
        "time_ago": "1 hari",
        "content": "Agrippa said it's time to get back to work 😎",
        "likes": 131,
        "url": "[https://www.threads.net/@zuck/post/Ddt7cL5EfUG](https://www.threads.net/@zuck/post/Ddt7cL5EfUG)"
    }
]
