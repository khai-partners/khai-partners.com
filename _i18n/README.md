# Terjemahan bahasa Indonesia (/id/)

Halaman di folder `id/` dibuat otomatis dari halaman bahasa Inggris di root.
Jangan edit `id/*.html` langsung — perubahan akan tertimpa.

Setelah mengubah halaman bahasa Inggris:

    python3 _i18n/i18n.py extract   # cari teks baru
    # tambahkan terjemahan teks baru ke _i18n/id.json
    python3 _i18n/i18n.py build     # bangun ulang id/*.html

`build` melaporkan teks yang belum diterjemahkan di `_i18n/missing.json`.
