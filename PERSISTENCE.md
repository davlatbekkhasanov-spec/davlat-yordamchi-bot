# Deploydan keyin ma'lumot yo'qolmasin

## Railway Volume (MAJBURIY — bir marta)

1. Railway → `davlat-yordamchi-bot` servisi
2. **Volumes** → **Add Volume** → Mount path: **`/data`**
3. Variables:
   ```
   DB_PATH=/data/data.db
   TZ=Asia/Tashkent
   ```

Volume bo'lmasa har deploy yangi bo'sh disk.

## Avtomatik (kod)

- Eski `data.db` → `/data/data.db` migratsiya
- Har start: `/data/backups/startup_*.db` + JSON zaxira
- Seed faqat bo'sh slotga yoziladi
- **Tizim holati**: `Volume: ✅` ko'rinishi kerak

## Tiklash

`/backup` (Telegram) yoki `python tools/restore_backup.py backup_....json`
