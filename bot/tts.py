# -*- coding: utf-8 -*-
"""TTS اختیاری برای یادآورها (مسیر D — «یادآور موعدها با صدا»).
بک‌اند: edge-tts (رایگان) — صدا: fa-IR-DilaraNeural (منشی دیجیتال).
اگر بک‌اند نبود یا خطا داد -> None -> handler به متن برمی‌گردد (fallback محترمانه)."""
import asyncio
import os
import time

DATA = os.environ.get("SAYA_DATA",
                      os.path.join(os.path.dirname(os.path.abspath(__file__)), "data"))
DEFAULT_VOICE = os.environ.get("TTS_VOICE", "fa-IR-DilaraNeural")


def available():
    if os.environ.get("TTS_ENABLE", "1") == "0":
        return False
    try:
        import edge_tts  # noqa: F401
        return True
    except ImportError:
        return False


def synthesize(text, out_path=None):
    """text -> bytes فایل صوتی (mp3) یا None. هرگز exception نمی‌دهد."""
    if not available():
        return None
    try:
        import edge_tts
        os.makedirs(DATA, exist_ok=True)
        out = out_path or os.path.join(DATA, "tts-%d.mp3" % int(time.time() * 1000))

        async def _run():
            c = edge_tts.Communicate(text, DEFAULT_VOICE)
            await c.save(out)

        asyncio.run(_run())
        if not os.path.exists(out) or os.path.getsize(out) < 500:
            return None
        with open(out, "rb") as f:
            return f.read()
    except Exception:
        return None
