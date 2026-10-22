# Lightweight OSINT Target Profiler Tracker — MVP 8 Layer

Dashboard Streamlit untuk mengamati metadata situs publik dan aset yang Anda miliki atau diizinkan untuk dianalisis.

## Layer MVP
1. Validasi URL HTTPS dan pemeriksaan bahwa DNS mengarah ke IP publik.
2. Status HTTP, content-type, dan server headers.
3. HTML metadata: title, description, canonical, robots, Open Graph.
4. Crawl tautan internal pada host yang sama, maksimal 15 halaman.
5. Pencarian subdomain pasif dari Certificate Transparency (`crt.sh`); subdomain tidak dipindai.
6. Petunjuk teknologi dari header/marker HTML; indikatif saja.
7. Snapshot SQLite dan perbandingan perubahan.
8. Ringkasan AI opsional melalui OpenAI API; tanpa key menggunakan fallback lokal.

## Jalankan lokal
Python 3.11+ disarankan.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Centang kotak otorisasi dan gunakan hanya target yang Anda miliki/berwenang untuk diuji.

## Aktifkan AI (opsional)
Set environment variable `OPENAI_API_KEY` sebelum menjalankan aplikasi. Jangan masukkan key ke Git atau ke source code. Opsional: `OPENAI_MODEL` untuk memilih model yang tersedia pada akun Anda.

Linux/macOS:
```bash
export OPENAI_API_KEY="..."
streamlit run app.py
```
PowerShell:
```powershell
$env:OPENAI_API_KEY="..."
streamlit run app.py
```

## Deploy
Push repository ke GitHub, lalu deploy di Streamlit Community Cloud. Tambahkan `OPENAI_API_KEY` pada pengaturan Secrets jika AI diperlukan. SQLite pada filesystem hosting mungkin tidak persisten; untuk penggunaan berkelanjutan, pindahkan database ke layanan terkelola/persistent volume. Jangan publikasikan dashboard tanpa autentikasi dan kebijakan akses.

## Batasan keamanan dan akurasi
- HTTPS/port 443 saja; redirect tidak diikuti; respons HTML maksimum 1 MB.
- Crawl hanya host awal dan maksimum 15 halaman. Tidak menjalankan exploit, brute force, login attempts, atau pemindaian port.
- Subdomain berasal dari data sertifikat publik; bisa tidak aktif, salah cakupan, atau tidak dimiliki oleh organisasi yang diasumsikan.
- Petunjuk teknologi dapat keliru atau sengaja disembunyikan.
- Pemeriksaan DNS di aplikasi tidak menghilangkan semua risiko DNS rebinding. Untuk layanan publik, terapkan egress firewall/proxy, autentikasi, rate limit, dan pemantauan.
- AI mengirim ringkasan metadata terpilih ke penyedia API saat key diatur. Hindari memasukkan data privat/rahasia.
