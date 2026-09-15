# -*- coding: utf-8 -*-
"""دست‌یار گفت‌وگو — همه دستورات و مسیرهای پیام.
قانون طلایی: هیچ‌گاه کرش، هیچ‌گاه پاسخ خالی؛ هر مسیر نامطمئن -> fallback محترمانه."""
import datetime
import os
import re
import time

from persian import fa_num, jalali, to_int
import ocr as ocrmod

DATA = os.environ.get("SAYA_DATA", os.path.join(os.path.dirname(os.path.abspath(__file__)), "data"))

# ── متن‌ها ─────────────────────────────────────────────
MANAGER_GREET = (
    "سلام! 🌙\n"
    "من منشی دیجیتال «سایا-جادو» هستم — شب‌ها و روزها بیدارم و خط را نمی‌گذارم زمین.\n\n"
    "چه کارهایی از من برمی‌آید:\n"
    "• عکس فاکتور بفرست ← می‌خوانم، جمع را می‌گویم و به انبار ثبت می‌کنم\n"
    "• اگر مطمئن نبودم: «مبلغ: عدد» بفرست تا دستی ثبت کنم\n"
    "• /remind مشتری <دقیقه یا YYYY-MM-DD> <متن> ← یادآوری در موعد\n"
    "• /reply <chat_id> <متن> ← پاسخ من را به مشتری برسانم\n"
    "• /stats ← خلاصه ثبت‌ها\n"
    "• /menu ← همین فهرست\n\n"
    "همین حالا یک عکس فاکتور بفرست تا امتحانم کنی.")

CUSTOMER_GREET = (
    "سلام! 👋\n"
    "این منشی دیجیتال است. پیامت را به صاحب مغازه می‌رسانم و به‌زودی جواب می‌گیری.\n"
    "اگر رسید یا فاکتوری داری، همین‌جا بفرست.")

INVOICE_OK_HEAD = "✅ فاکتور شماره {no} ثبت شد\n\nجمع کل: {total}\n"
INVOICE_ITEM = "• {name}: {qty} × {price} = {line}\n"
INVOICE_OK_TAIL = "\nبه انبار اضافه شد 📦 (ثبت #{id})"
INVOICE_NO_ITEMS = "\n(قلم‌ها را جدا نمی‌خواندم؛ اگر خواستی جداگانه بگو)\n"

INVOICE_OCR_MISSING = (
    "📷 عکس رسید.\n"
    "املا خودکار فعلاً روی این سرور نصب نیست — مبلغ را بفرست تا ثبت کنم:\n"
    "«مبلغ: عدد»")

INVOICE_NO_TOTAL = (
    "📷 عکس را دیدم، ولی «جمع کل» را مطمئن نمی‌خوانم.\n"
    "دقیق بگو: «مبلغ: عدد»")

MANUAL_OK = "✅ ثبت دستی شد\nمبلغ: {total}\nثبت #{id} در انبار"

REMINDER_OK = ("⏰ یادآوری ثبت شد\nبرای: {name}\nزمان: {when}\n«{text}»")
REMINDER_TO_CUSTOMER = "🌙 یادآوری «سایا-جادو»:\n{text}"
REMINDER_TO_MANAGER = "✅ یادآوری برای {name} رفت ({when})"

VOICE_GRACEFUL = (
    "🎙 صدایت را گرفتم، ولی املا صوتی فعلاً در حالت آزمایشی است.\n"
    "متن بفرست تا اجرا کنم — یا عکس فاکتور بفرست.")

FALLBACK = (
    "متوجه نشدم 😅\n"
    "ساده‌ترین کارها:\n"
    "• عکس فاکتور بفرست\n"
    "• «مبلغ: عدد» برای ثبت دستی\n"
    "• /menu برای فهرست")

STATS = ("📊 ثبت‌های انبار: {n}\n"
         "آخرین فاکتور: شماره {no} — جمع {total}")


def _manager_id():
    return os.environ.get("MANAGER_CHAT_ID")


# ── ورودی اصلی (هرگز exception به بیرون نمی‌دهد) ──────
def handle(msg, store, tg):
    chat = msg.get("chat") or {}
    chat_id = chat.get("id")
    sender = (msg.get("from") or {})
    name = sender.get("first_name") or ""
    is_manager = bool(_manager_id()) and str(chat_id) == str(_manager_id())
    try:
        _handle_inner(msg, store, tg, chat_id, name, is_manager)
    except Exception as e:
        store.log("handler-error", repr(e)[:300])
        tg.safe_send(chat_id, "متأسفم، یک ایراد گذرا پیش آمد. /menu", store, "error-retry")


def _handle_inner(msg, store, tg, chat_id, name, is_manager):
    # ۱) صوت
    if "voice" in msg:
        text = _stt(_voice_bytes(msg, store, tg))
        if text:
            store.log("voice", "stt ok: %s" % text[:120])
            text = text.strip()
        else:
            tg.safe_send(chat_id, VOICE_GRACEFUL, store)
            return
        # ادامه با متن (فرمان)
        _handle_text(text, store, tg, chat_id, name, is_manager)
        return

    # ۲) عکس -> فاکتور
    if "photo" in msg:
        _handle_photo(msg, store, tg, chat_id, name, is_manager)
        return

    # ۳) متن
    text = (msg.get("text") or "").strip()
    if text:
        _handle_text(text, store, tg, chat_id, name, is_manager)
        return

    tg.safe_send(chat_id, FALLBACK, store)


# ── صوت ───────────────────────────────────────────────
def _voice_bytes(msg, store, tg):
    v = msg["voice"]
    fid = v.get("file_id")
    if not fid:
        return None
    blob = tg.download_file(fid)
    if blob:
        try:
            os.makedirs(DATA, exist_ok=True)
            with open(os.path.join(DATA, "voice-%d.ogg" % int(time.time())), "wb") as f:
                f.write(blob)
        except Exception:
            pass
    return blob


def _stt(ogg_bytes):
    """بک‌اند STT اختیاری (STT_URL) — قرارداد: POST image=ogg -> {"text": ...}"""
    url = os.environ.get("STT_URL")
    if not url or not ogg_bytes:
        return None
    import json as _json
    import urllib.request
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
            return _json.loads(r.read().decode("utf-8")).get("text")
    except Exception:
        return None


# ── فاکتور (مسیر B) ───────────────────────────────────
def _handle_photo(msg, store, tg, chat_id, name, is_manager):
    sizes = msg.get("photo") or []
    if not sizes:
        tg.safe_send(chat_id, INVOICE_OCR_MISSING, store)
        return
    fid = sizes[-1].get("file_id")
    blob = tg.download_file(fid) if fid else None
    if not blob:
        tg.safe_send(chat_id, "📷 عکس را دریافت نکردم؛ دوباره بفرست.", store)
        store.log("photo", "download failed")
        return

    # ذخیره محلی (برای بازبینی)
    photo_path = ""
    try:
        os.makedirs(os.path.join(DATA, "photos"), exist_ok=True)
        photo_path = os.path.join(DATA, "photos", "inv-%d.jpg" % int(time.time()))
        with open(photo_path, "wb") as f:
            f.write(blob)
    except Exception:
        photo_path = ""

    text = ocrmod.ocr_image(blob)
    parsed = ocrmod.parse_invoice(text) if text else None

    if not parsed:
        if not text:
            tg.safe_send(chat_id, INVOICE_OCR_MISSING, store)
            store.log("ocr", "no backend or failed")
        else:
            tg.safe_send(chat_id, INVOICE_NO_TOTAL, store)
            store.log("ocr", "text but no total: %s" % text[:120])
        if not is_manager and _manager_id():
            tg.send_photo(_manager_id(), blob, "📷 مشتری (%s) — فاکتور" % (name or chat_id))
        return

    total = parsed["total"]
    iid = store.add_invoice("", str(parsed["no"]) or "?", total,
                            [list(x) for x in parsed["items"]],
                            os.path.basename(photo_path) if photo_path else "",
                            "ocr" if text else "manual")
    store.log("invoice", "id=%s no=%s total=%s items=%s" % (iid, parsed["no"], total, len(parsed["items"])))

    body = INVOICE_OK_HEAD.format(
        no=fa_num(to_int(str(parsed["no"])) or 0) if parsed["no"] not in (None, "?") else "?",
        total=fa_num(total))
    if parsed["items"]:
        for (nm, q, p) in parsed["items"]:
            body += INVOICE_ITEM.format(name=nm, qty=fa_num(q, sep=False),
                                        price=fa_num(p), line=fa_num(q * p))
    else:
        body += INVOICE_NO_ITEMS
    body += INVOICE_OK_TAIL.format(id=fa_num(iid, sep=False))
    tg.safe_send(chat_id, body, store)

    if not is_manager and _manager_id():
        tg.send_photo(_manager_id(), blob,
                      "📷 مشتری (%s) — فاکتور ثبت شد: %s" % (name or chat_id, fa_num(total)))


# ── متن / دستورات ────────────────────────────────────
def _handle_text(text, store, tg, chat_id, name, is_manager):
    t = text.strip()

    if t.startswith("/start") or t.startswith("/help") or t == "/menu" or t == "منو":
        tg.safe_send(chat_id, MANAGER_GREET if is_manager else CUSTOMER_GREET, store)
        return

    if t.startswith("/stats"):
        n = store.invoice_count()
        last = store.last_invoice()
        if last:
            tg.safe_send(chat_id, STATS.format(
                n=fa_num(n, sep=False),
                no=fa_num(to_int(str(last["no"])) or 0) if str(last["no"]) != "?" else "?",
                total=fa_num(last["total"])), store)
        else:
            tg.safe_send(chat_id, "هنوز فاکتوری ثبت نشده.", store)
        return

    if t.startswith("/remind") or t.startswith("یادآوری"):
        _cmd_remind(t, store, tg, chat_id, is_manager)
        return

    if t.startswith("/reply"):
        if not is_manager:
            tg.safe_send(chat_id, FALLBACK, store)
            return
        parts = t.split(None, 2)
        if len(parts) < 3:
            tg.safe_send(chat_id, "فرمت: /reply <chat_id> <متن>", store)
            return
        cid = to_int(parts[1])
        if not cid:
            tg.safe_send(chat_id, "chat_id نامعتبر است.", store)
            return
        ok = tg.safe_send(cid, parts[2].strip(), store)
        tg.safe_send(chat_id, ("✅ به مشتری فرستاده شد." if ok else "ارسال نشد — chat_id را چک کن."), store)
        return

    if t.startswith("/cust"):
        store.upsert_customer(chat_id, name)
        parts = t.split(None, 2)
        if len(parts) == 3:
            store.upsert_customer(chat_id, parts[1], parts[2])
            tg.safe_send(chat_id, "✅ ثبت شد: %s" % parts[1], store)
        else:
            tg.safe_send(chat_id, "✅ نامت را به‌یاد سپردم. برای شماره: /cust نام <شماره>", store)
        return

    m = re.match(r"^مبلغ\s*[:：]?\s*([\d\u06F0-\u06F9][\d\u06F0-\u06F9\u066C,]*)$", t)
    if m:
        total = to_int(m.group(1))
        if total:
            iid = store.add_invoice("", "?", total, [], "", "manual")
            store.log("invoice-manual", "id=%s total=%s" % (iid, total))
            tg.safe_send(chat_id, MANUAL_OK.format(total=fa_num(total), id=fa_num(iid, sep=False)), store)
            if not is_manager and _manager_id():
                tg.safe_send(_manager_id(),
                             "📥 ثبت دستی از مشتری (%s): %s" % (name or chat_id, fa_num(total)), store)
        return

    # پیام عادی مشتری -> مدیر
    if not is_manager and _manager_id():
        store.upsert_customer(chat_id, name)
        tg.safe_send(_manager_id(), "👤 مشتری (%s):\n%s" % (name or chat_id, t[:800]), store)
        tg.safe_send(chat_id, "✅ پیامت رفت؛ منتظر بمان.", store)
        return

    tg.safe_send(chat_id, FALLBACK, store)


# ── یادآور (مسیر D) ───────────────────────────────────
def _cmd_remind(t, store, tg, chat_id, is_manager):
    parts = t.split(None, 3)
    if len(parts) < 4:
        tg.safe_send(chat_id, "فرمت: /remind <مشتری> <دقیقه یا YYYY-MM-DD> <متن>", store)
        return
    cust, when, rtext = parts[1], parts[2], parts[3].strip()

    remind_at = None
    when_label = ""
    mins = to_int(when)
    if mins is not None and 0 < mins < 100000:
        remind_at = time.time() + mins * 60
        when_label = fa_num(mins) + " دقیقه دیگر"
    elif re.match(r"^\d{4}-\d{2}-\d{2}$", when):
        try:
            d = datetime.datetime.strptime(when, "%Y-%m-%d").replace(hour=9, minute=0)
            remind_at = d.timestamp()
            when_label = jalali(d.date()) + " ساعت ۹ صبح"
        except ValueError:
            pass
    if remind_at is None:
        tg.safe_send(chat_id, "زمان را نمی‌فهمم — دقیقه (مثلاً ۳۰) یا YYYY-MM-DD بده.", store)
        return

    cid = chat_id
    cust_row = store.get_customer(chat_id)
    rid = store.add_reminder(cust, cid, rtext, remind_at)
    store.log("reminder", "id=%s cust=%s at=%s" % (rid, cust, remind_at))
    tg.safe_send(chat_id, REMINDER_OK.format(name=cust, when=when_label, text=rtext[:200]), store)


# ── حلقه‌ی یادآورها (از bot.py صدا می‌شود) ──────────────
def poll_reminders(store, tg):
    for r in store.due_reminders():
        store.mark_reminder(r["id"])
        if r.get("chat_id"):
            tg.safe_send(r["chat_id"], REMINDER_TO_CUSTOMER.format(text=r["text"]), store, "reminder")
        if _manager_id():
            tg.safe_send(_manager_id(),
                         REMINDER_TO_MANAGER.format(name=r["customer"], when=jalali(datetime.date.today())),
                         store, "reminder-log")
