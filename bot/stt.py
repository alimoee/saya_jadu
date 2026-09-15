# -*- coding: utf-8 -*-
"""STT اختیاری برای فرمان صوتی (ماژول A — «فرمان با صدا»).

بک‌اند به این ترتیب:
1) **Vosk محلی (آفلاین):** `VOSK_MODEL_PATH` تنظیم باشد + پکیج `vosk` نصب + `ffmpeg`
   (مدل فارسی: vosk-model-fa-0.7 — حدود 40MB؛ راهنما در vps/SETUP.md).
2) **بک‌اند HTTP (STT_URL):** قرارداد: POST فایل ogg (field: `image`) -> {"text": "..."}.
   برای هر سرور whisper/ASR سازگاری می‌کند.

اگر هیچ‌کدام نبود یا خطا داد -> None -> handler به fallback می‌رود
(صدای مشتری برای صاحب مغارس ارسال می‌شود + متن محترمانه). هرگز exception نمی‌دهد."""
import io
import json
import os
import subprocess
import urllib.request

# کش مدل Vosk (لود 40MB فقط یک‌بار در هر پروس)
_model = {"obj": None, "failed": False}


def _vosk_model_path():
    p = os.environ.get("VOSK_MODEL_PATH", "").strip()
    return p if p and os.path.isdir(p) else None


def _ffmpeg_to_wav16k(ogg_bytes):
    """ogg/opus -> WAV 16kHz mono (bytes) — الزامِ Vosk."""
    try:
        r = subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", "pipe:0",
             "-ar", "16000", "-ac", "1", "-f", "wav", "pipe:1"],
            input=ogg_bytes, capture_output=True, timeout=60)
        if r.returncode == 0 and len(r.stdout) > 1000:
            return r.stdout
    except Exception:
        pass
    return None


def _vosk_model():
    if _model["obj"] is None and not _model["failed"]:
        try:
            from vosk import Model, SetLogLevel
            SetLogLevel(-1)
            _model["obj"] = Model(_vosk_model_path())
        except Exception:
            _model["failed"] = True
    return _model["obj"]


def _transcribe_vosk(ogg_bytes):
    if not _vosk_model_path():
        return None
    try:
        import shutil
        if not shutil.which("ffmpeg"):
            return None
        from vosk import KaldiRecognizer
    except ImportError:
        return None
    model = _vosk_model()
    if model is None:
        return None
    wav = _ffmpeg_to_wav16k(ogg_bytes)
    if not wav:
        return None
    try:
        import wave
        wf = wave.open(io.BytesIO(wav), "rb")
        if wf.getnchannels() != 1 or wf.getsampwidth() != 2:
            return None
        rec = KaldiRecognizer(model, wf.getframerate())
        while True:
            frames = wf.readframes(4000)
            if not frames:
                break
            rec.AcceptWaveform(frames)
        result = json.loads(rec.FinalResult())
        return (result.get("text") or "").strip() or None
    except Exception:
        return None


def _transcribe_http(ogg_bytes):
    url = os.environ.get("STT_URL", "").strip()
    if not url:
        return None
    boundary = "----sayastt"
    body = (("--%s\r\nContent-Disposition: form-data; name=\"image\"; filename=\"v.ogg\"\r\n"
             "Content-Type: audio/ogg\r\n\r\n" % boundary).encode() +
            ogg_bytes + ("\r\n--%s--\r\n" % boundary).encode())
    try:
        req = urllib.request.Request(
            url, data=body,
            headers={"Content-Type": "multipart/form-data; boundary=" + boundary,
                     "Authorization": "Bearer " + os.environ.get("STT_KEY", "")})
        with urllib.request.urlopen(req, timeout=90) as r:
            return (json.loads(r.read().decode("utf-8")).get("text") or "").strip() or None
    except Exception:
        return None


def available():
    """آیا حداقل یک بک‌اند STT هست؟"""
    return bool(_vosk_model_path()) or bool(os.environ.get("STT_URL", "").strip())


def transcribe(ogg_bytes):
    """ogg/opus -> متن (یا None). هرگز exception نمی‌دهد."""
    if not ogg_bytes:
        return None
    try:
        t = _transcribe_vosk(ogg_bytes)
        if t:
            return t
        return _transcribe_http(ogg_bytes)
    except Exception:
        return None
