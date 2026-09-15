# -*- coding: utf-8 -*-
"""عکس فاکتور -> متن -> فیلدها.
بک‌اند OCR قابل تعویض است: tesseract (lokal) -> ابری (OCR_CLOUD_URL) -> None.
اگر هیچ بک‌اندی نباشد، None برمی‌گرداند و handler مسیر «ثبت دستی» را باز می‌کند
(قانون: هیچ‌گاه کرش، همیشه fallback)."""
import json
import os
import re
import shutil
import subprocess
import tempfile
import urllib.request

from persian import to_int


def backend_name():
    if shutil.which("tesseract"):
        return "tesseract"
    if os.environ.get("OCR_CLOUD_URL"):
        return "cloud"
    return None


def ocr_image(img_bytes):
    """bytes عکس -> متن فارسی/انگلیسی یا None."""
    # ۱) tesseract محلی
    if shutil.which("tesseract"):
        try:
            with tempfile.TemporaryDirectory() as td:
                p = os.path.join(td, "inv.jpg")
                with open(p, "wb") as f:
                    f.write(img_bytes)
                out = subprocess.run(
                    ["tesseract", p, "stdout", "-l", "fa+eng", "--psm", "6"],
                    capture_output=True, timeout=120)
                text = out.stdout.decode("utf-8", errors="replace").strip()
                return text or None
        except Exception:
            return None
    # ۲) ابری — قرارداد ساده: POST multipart(name=image) <- JSON {"text": "..."}
    url = os.environ.get("OCR_CLOUD_URL")
    if url:
        try:
            boundary = "----sayaocr"
            body = (("--%s\r\nContent-Disposition: form-data; name=\"image\";"
                     " filename=\"inv.jpg\"\r\nContent-Type: image/jpeg\r\n\r\n" % boundary)
                    .encode() + img_bytes +
                    ("\r\n--%s--\r\n" % boundary).encode())
            req = urllib.request.Request(
                url, data=body,
                headers={"Content-Type": "multipart/form-data; boundary=" + boundary,
                         "Authorization": "Bearer " + os.environ.get("OCR_CLOUD_KEY", "")})
            with urllib.request.urlopen(req, timeout=60) as r:
                data = json.loads(r.read().decode("utf-8"))
            return data.get("text") or None
        except Exception:
            return None
    return None


_NUM = r"[\d\u06F0-\u06F9]"


def parse_invoice(text):
    """متن خام -> {no, total, items:[(name,qty,price)]} یا None (اگر total پیدا نشد).
    همه ارقام فارسی/انگلیسی و جداکننده‌ها تحمل می‌شوند."""
    if not text:
        return None
    t = text.replace("\u200f", " ").replace("\u200e", " ")
    res = {"no": None, "total": None, "items": []}

    m = re.search(r"شماره[\s:：\-]*" + _NUM + r"[\d\u06F0-\u06F9\u066C,]{0,12}", t)
    if m:
        res["no"] = str(to_int(m.group(0)))

    for pat in (r"قابل پرداخت[\s:：]*", r"مبلغ کل[\s:：]*", r"جمع کل[\s:：]*",
                r"مجموع[\s:：]*", r"جمع[\s:：]*", r"مبلغ[\s:：]*"):
        m = re.search(pat + r"([\d\u06F0-\u06F9][\d\u06F0-\u06F9\u066C,]{2,18})", t)
        if m:
            res["total"] = to_int(m.group(1))
            if res["total"]:
                break

    # قلم‌ها: خط‌های «نام  qty x price»
    for line in t.splitlines():
        m = re.match(r"^\s*(.{2,40}?)\s+(" + _NUM + r"+)\s*[,،x×*\-]\s*"
                     r"([\d\u06F0-\u06F9][\d\u06F0-\u06F9\u066C,]{1,15})\s*$", line)
        if m:
            name = m.group(1).strip()
            qty = to_int(m.group(2))
            price = to_int(m.group(3))
            if name and qty and price and not any(w in name for w in ("شماره", "مجموع", "جمع", "مبلغ")):
                res["items"].append((name, qty, price))
    res["items"] = res["items"][:10]

    if not res["total"]:
        return None
    return res


def items_sum(items):
    return sum(q * p for (_n, q, p) in items)
