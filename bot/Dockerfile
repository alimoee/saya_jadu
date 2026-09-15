FROM python:3.12-slim

# OCR فارسی (اختیاری ولی توصیه‌شده) + ffmpeg برای تبدیل صدای تلگرام (مسیر STT/Vosk)
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr tesseract-ocr-fa ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# TTS یادآورها (رایگان)
RUN pip install --no-cache-dir edge-tts

# STT محلی/آفلاین (اختیاری): docker build --build-arg INSTALL_VOSK=1 ...
# مدل فارسی را جداگانه دانلود کن (راهنما: vps/SETUP.md) و VOSK_MODEL_PATH را ست کن.
ARG INSTALL_VOSK=0
RUN if [ "$INSTALL_VOSK" = "1" ]; then pip install --no-cache-dir vosk; fi

WORKDIR /app
COPY bot/ ./
CMD ["python3", "bot.py"]
