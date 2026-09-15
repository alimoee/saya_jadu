FROM python:3.12-slim

# OCR فارسی (اختیاری ولی توصیه‌شده)
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr tesseract-ocr-fa \
    && rm -rf /var/lib/apt/lists/*

# TTS یادآورها (رایگان)
RUN pip install --no-cache-dir edge-tts

WORKDIR /app
COPY bot/ ./
CMD ["python3", "bot.py"]
