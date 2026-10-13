# Sentimen Forex

Aplikasi desktop Windows (.exe) yang menampilkan widget **Community Outlook Myfxbook** (sentimen trader retail) dalam satu jendela. Tidak perlu akun atau login.

## Fitur
- Widget Outlook resmi Myfxbook untuk 29 simbol (pair mayor, minor, emas, dan lainnya)
- Muat ulang otomatis tiap 5 menit
- Jendela ringan berbasis Microsoft Edge WebView2 (sudah tersedia di Windows 10/11)
- Cadangan: jika WebView2 tidak ada, halaman dibuka di browser bawaan

## Cara build .exe lewat GitHub
1. Buat repository baru di GitHub, lalu upload `app.py`, `requirements.txt`, `README.md`, dan folder `.github/workflows/build.yml`.
2. Buka tab **Actions** dan jalankan workflow **Build SentimenForex.exe** (atau otomatis berjalan saat push ke `main`).
3. Setelah selesai, unduh `SentimenForex.exe` dari bagian **Artifacts**.
4. Untuk rilis resmi: buat tag, misalnya `git tag v1.0.0 && git push origin v1.0.0`. File .exe otomatis muncul di halaman **Releases**.

## Menjalankan dari source
```
pip install -r requirements.txt
python app.py
```

## Mengubah daftar simbol
Edit parameter `symbols=` pada URL script widget di `app.py` (kode simbol sesuai generator widget di Myfxbook).

## Catatan
- Butuh koneksi internet karena widget dimuat dari server Myfxbook.
- Data sentimen adalah posisi trader retail, bukan saran trading.
