# استقرار روی VPS — فز ۲

## گزینه‌ی A: Docker (توصیه‌شده)

روی سرور (Ubuntu 22.04+):

```bash
# Docker
curl -fsSL https://get.docker.com | sh

# کد (کلید Contents R/W همان کافی است)
git clone https://github.com/alimoee/saya_jadu.git
cd saya_jadu
cp bot/.env.example .env
nano .env          # BOT_TOKEN + MANAGER_CHAT_ID

# اجرا
docker compose -f bot/docker-compose.yml up -d --build
docker compose -f bot/docker-compose.yml logs -f
```

به‌روزرسانی بعدی:
```bash
git pull && docker compose -f bot/docker-compose.yml up -d --build
```

داده‌ها (SQLite + عکس‌ها) در `./data` می‌مانند — پیش از ری‌بیلد بکاپ بگیر:
```bash
tar czf saya-data-$(date +%F).tar.gz data/
```

## گزینه‌ی B: سیستم خالی (بدون Docker)

```bash
sudo apt-get update
sudo apt-get install -y tesseract-ocr tesseract-ocr-fa python3
pip3 install edge-tts
# systemd unit: در bot/README.md
```

## نکات

- **پورت باز لازم نیست** — ربات با long polling با Telegram حرف می‌زند (outbound فقط).
- اکران ۵۱۲ MB + ۱ vCPU برای شروع کافی است (TTS در ابر مایکروسافت است، نه روی سرور).
- هر ۳۰ روز کلید را تازه کن (fine-grained 30-روزه) و `docker compose ... restart`.
- لوگ رویدادها در SQLite: `sqlite3 data/saya.db "SELECT * FROM log ORDER BY id DESC LIMIT 20"`
