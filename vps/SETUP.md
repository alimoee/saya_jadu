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

## STT — فرمان صوتی (اختیاری، ماژول A)

ربات هر دو گزینه را به‌صورت خودکار می‌فهمد؛ اگر هیچ‌کدام نباشد، صدای مشتری **برای صاحب‌مغازه ارسال می‌شود** + متن محترمانه (چیزی گم نمی‌شود).

### گزینه ۱: Vosk محلی (آفلاین — توصیه‌شده برای VPS کوچک)
```bash
# داخل کانتینر (یا روی سیستم):
pip install vosk
mkdir -p /opt/models && cd /opt/models
wget https://alphacephei.com/vosk/models/vosk-model-fa-0.7.zip
unzip vosk-model-fa-0.7.zip
```
در `docker-compose.yml`:
```yaml
environment:
  - VOSK_MODEL_PATH=/opt/models/vosk-model-fa-0.7
volumes:
  - ./models:/opt/models   # مدل را در ./models نگه‌دار
```
و با `docker build --build-arg INSTALL_VOSK=1` بساز. مدل ~40MB است؛ بارگذاری فقط یک‌بار در هر پروس.

### گزینه ۲: بک‌اند HTTP
هر سرور ASR که POST فایل ogg بپذیرد و `{"text": "..."}` برگرداند:
```yaml
environment:
  - STT_URL=http://asr-server:8000/transcribe
  - STT_KEY=...
```

## نکات

- **پورت باز لازم نیست** — ربات با long polling با Telegram حرف می‌زند (outbound فقط).
- اکران ۵۱۲ MB + ۱ vCPU برای شروع کافی است (TTS در ابر مایکروسافت است، نه روی سرور).
- هر ۳۰ روز کلید را تازه کن (fine-grained 30-روزه) و `docker compose ... restart`.
- لوگ رویدادها در SQLite: `sqlite3 data/saya.db "SELECT * FROM log ORDER BY id DESC LIMIT 20"`
