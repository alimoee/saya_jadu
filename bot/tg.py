# -*- coding: utf-8 -*-
"""لایه‌ی Telegram API — فقط stdlib (urllib). مقاوم: retry روی 429 و خطای شبکه.
هیچ‌گاه از حلقه‌ی اصلی exception پرتاب نمی‌کند؛ خطاها log می‌شوند."""
import json
import time
import urllib.error
import urllib.parse
import urllib.request


class TGBot:
    def __init__(self, token):
        self.base = "https://api.telegram.org/bot%s" % token

    # ── هسته ─────────────────────────────────────────
    def _call(self, method, payload=None, timeout=45, retries=4):
        url = self.base + "/" + method
        data = json.dumps(payload or {}).encode("utf-8")
        last = {"ok": False, "description": "no attempt"}
        for i in range(retries):
            try:
                req = urllib.request.Request(
                    url, data=data, headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    last = json.loads(r.read().decode("utf-8"))
                    if last.get("ok"):
                        return last
                # ok=false از خودِ API (مثلاً chat not found) — retry بی‌فایده
                return last
            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8", errors="replace")
                if e.code == 429:
                    try:
                        ra = json.loads(body).get("parameters", {}).get("retry_after", 3)
                    except Exception:
                        ra = 3
                    time.sleep(ra + 1)
                    continue
                last = {"ok": False, "description": "HTTP %s: %s" % (e.code, body[:200])}
                return last
            except (urllib.error.URLError, TimeoutError, OSError):
                time.sleep(2 * (i + 1))
                continue
        return last

    def _multipart_call(self, method, fields, files, timeout=90, retries=3):
        url = self.base + "/" + method
        boundary = "----saya%d" % int(time.time() * 1000)
        body = b""
        for k, v in fields.items():
            body += ("--%s\r\nContent-Disposition: form-data; name=\"%s\"\r\n\r\n%s\r\n"
                     % (boundary, k, v)).encode("utf-8")
        for k, (fn, blob, ct) in files.items():
            body += ("--%s\r\nContent-Disposition: form-data; name=\"%s\"; filename=\"%s\"\r\n"
                     "Content-Type: %s\r\n\r\n" % (boundary, k, fn, ct)).encode("utf-8")
            body += blob + b"\r\n"
        body += ("--%s--\r\n" % boundary).encode("utf-8")
        last = {"ok": False, "description": "no attempt"}
        for i in range(retries):
            try:
                req = urllib.request.Request(
                    url, data=body,
                    headers={"Content-Type": "multipart/form-data; boundary=" + boundary})
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    last = json.loads(r.read().decode("utf-8"))
                    return last
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    time.sleep(4)
                    continue
                body_txt = e.read().decode("utf-8", errors="replace")
                last = {"ok": False, "description": "HTTP %s: %s" % (e.code, body_txt[:200])}
                return last
            except (urllib.error.URLError, TimeoutError, OSError):
                time.sleep(2 * (i + 1))
                continue
        return last

    # ── روش‌ها ────────────────────────────────────────
    def get_me(self):
        return self._call("getMe")

    def get_updates(self, offset=None, timeout=30):
        p = {"timeout": timeout, "allowed_updates": ["message"]}
        if offset is not None:
            p["offset"] = offset
        return self._call("getUpdates", p, timeout=timeout + 20)

    def send_message(self, chat_id, text):
        return self._call("sendMessage", {"chat_id": chat_id, "text": text[:4000]})

    def send_photo(self, chat_id, photo_bytes, caption=""):
        f = {"photo": ("invoice.jpg", photo_bytes, "image/jpeg")}
        fields = {"chat_id": str(chat_id)}
        if caption:
            fields["caption"] = caption[:1000]
        return self._multipart_call("sendPhoto", fields, f)

    def send_voice(self, chat_id, audio_bytes, duration=0):
        f = {"voice": ("remind.ogg", audio_bytes, "audio/ogg")}
        fields = {"chat_id": str(chat_id)}
        if duration:
            fields["duration"] = str(duration)
        return self._multipart_call("sendVoice", fields, f)

    def download_file(self, file_id):
        r = self._call("getFile", {"file_id": file_id})
        if not r.get("ok"):
            return None
        path = r["result"].get("file_path")
        if not path:
            return None
        try:
            with urllib.request.urlopen(self.base + "/file/" + path, timeout=60) as resp:
                return resp.read()
        except Exception:
            return None

    # ── پاسخ‌دهی ایمن ─────────────────────────────────
    def safe_send(self, chat_id, text, store=None, kind="send"):
        r = self.send_message(chat_id, text)
        if not r.get("ok") and store is not None:
            store.log(kind, "chat=%s err=%s" % (chat_id, r.get("description")))
        return r.get("ok", False)
