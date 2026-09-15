# سایا-جادو — ربات تلگرام (MVP فز ۱)

منشی دیجیتال 24/7 برای مغازه — فقط Python استاندارد، بدون هیچ کتابخانه‌ی خارجی.

## چه کار می‌کند (نقشه‌ی سرلوحه)

| مسیر | فیچر | وضعیت MVP |
|---|---|---|
| B | عکس فاکتور ← OCR ← ثبت انبار | ✅ (OCR اختیاری؛ بدون بک‌اند → ثبت دستی «مبلغ: عدد») |
| K-lite | منشی دیجیتال (گوشی/پیام شب) | ✅ greeting + fallback محترمانه |
| F-lite | چت مشتری ↔ مدیر | ✅ پیام مشتری به مدیر و `/reply` برای پاسخ |
| D | یادآور موعد (نسیه/قبض) | ✅ `/remind` دقیقه‌ای یا `YYYY-MM-DD` + حلقه‌ی ارسال |
| D | یادآور **صوتی** (فارسی) | ✅ TTS با `fa-IR-DilaraNeural` (edge-tts)؛ بدون بک‌اند ← متن |
| A-lite | فرمان صوتی | ⚠️ اسکلت آماده (STT اختیاری)؛ بدون بک‌اند → fallback |
| K | نردبان اعتبار (سقف + تأیید مالک + پرداخت) | ✅ `/credit` `/approve` `/pay` `/balance` |
| K | گزارش صبح ساعت ۹ (فاکتور + نسیه‌ی سررسید + عقب‌افتاده) | ✅ خودکار (TZ_HOURS) + catch-up محلی |
| B | تأیید مالک پیش از ثبت انبار (اصل ۲) | ✅ پیش‌نمایش 🟢/ + «بله»/«نه» — **ثبت خودکار نیست** |
| F | تاریخ شمسی دقیق (Borkowski) | ✅ کف‌شکن کبیسه + round-trip ۱۰۰ |
| D | یادآور ضدشکست | ✅ ۳ تلاش؛ شکست → log `reminder-failed` |
| K | آستانه‌ی ۵۰٪ نسیه (سرلوحه) | ✅ بالاتر از نیمه‌ی سقف ← approval مالک |
| C | دروازه‌ی دسترسی: فرمان‌های مالی/انباری فقط از چت مالک (اصل ۲، با AI-B) | ✅ `/stats /reply /credit /approve /pay /balance /remind` + «یادآوری» قفل |

قانون طلایی: **هیچ‌گاه کرش، هیچ‌گاه پاسخ خالی** — هر مسیر شکسته به fallback محترمانه می‌رسد و در جدول `log` ثبت می‌شود.

## نصب (VPS)

```bash
# Python 3.9+ کافی است
# برای OCR فارسی (اختیاری ولی توصیه‌شده):
sudo apt-get install -y tesseract-ocr tesseract-ocr-fa
```

## راه‌اندازی

1. در تلگرام با **@BotFather** : دستور `/newbot` → نام و username بده (مثلاً `saya_jadu_bot`) → **token** را بگیر.
2. با بوت `/start` بفرست تا `chat_id` خودت را ببینی (یا از @userinfobot).
3. اجرا:

```bash
export BOT_TOKEN='...'
export MANAGER_CHAT_ID='...'        # chat_id صاحب مغازه
python3 bot.py
```

متغیرهای اختیاری:

| env | کاربرد |
|---|---|
| `SAYA_DB` | مسیر SQLite (پیش‌فرض: `bot/data/saya.db`) |
| `SAYA_DATA` | پوشه‌ی عکس/صوت ذخیره‌شده |
| `OCR_CLOUD_URL` / `OCR_CLOUD_KEY` | OCR ابری (POST multipart `image` ← JSON `{"text":...}`) |
| `STT_URL` / `STT_KEY` | املا صوتی (POST multipart `image` ← JSON `{"text":...}`) |

## تست بدون توکن

```bash
python3 bot.py --selftest
```

کل پایپ‌لاین آفلاین (اعداد/تقویم، parse فاکتور، انبار، تأیید فاکتور، یادآور، نردبان اعتبار، دروازه‌ی دسترسی، گزارش صبح، مسیرهای گفت‌وگو با Telegram mock) — باید `SELFTEST OK: 59/59` باشد.

## نمونه‌ی دستورات

```
/start                 ← منو
[عکس فاکتور]           ← خواندن + ثبت انبار
مبلغ: 68265000         ← ثبت دستی
/remind علی 30 قبض برق را پرداخت کند
/remind مشتری 2026-10-20 مبلغ نسیه آماده است
/reply 1234567410 سلام، فاکتورت آماده است
/credit علی 500000 2026-10-20 ← نسیه (سقف: ۵۰۰۰۰۰۰۰؛ فراتر ← /approve)
/pay علی 300000         ← کسر از نسیه
/balance علی            ← مانده
/stats                 ← خلاصه‌ی ثبت‌ها
```

## اجرا با Docker (توصیه‌شده)
راهنمای کامل: `vps/SETUP.md`

```bash
cp bot/.env.example .env && nano .env
docker compose -f bot/docker-compose.yml up -d --build
```

## systemd (اجرای دائم روی VPS — بدون Docker)

```ini
# /etc/systemd/system/saya-bot.service
[Unit]
Description=saya-jadu telegram bot
After=network-online.target
[Service]
WorkingDirectory=/opt/saya/bot
Environment=BOT_TOKEN=xxx
Environment=MANAGER_CHAT_ID=xxx
ExecStart=/usr/bin/python3 bot.py
Restart=always
[Install]
WantedBy=multi-user.target
```

## بعدی (فز ۱b)

- STT/TTS واقعی (edge-tts یا API) — اسکلت `stt`/`tts` در `talk.py` آماده است
- نردبان اعتبار و گزارش صبح (K-lite کامل)
- واتساپ (دوکان‌پیام) — همان handler، کانال متفاوت
- وب‌پایگاه به‌جای polling (وقتی بار بالا رفت)
