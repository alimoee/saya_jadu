# -*- coding: utf-8 -*-
"""دست‌یار گفت‌وگو — همه دستورات و مسیرهای پیام.
قانون طلایی: هیچ‌گاه کرش، هیچ‌گاه پاسخ خالی؛ هر مسیر نامطمئن -> fallback محترمانه."""
import datetime
import os
import re
import time

from persian import fa_num, jalali, to_int, parse_jalali
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

# اصل ۲ سرلوحه: تصمیم مالی/انباری فقط با مالک — این فرمان‌ها هرگز از چت مشتری اجرا نمی‌شود (issue #2، با AI-B)
MANAGER_ONLY_CMDS = ("/stats", "/reply", "/credit", "/approve", "/pay", "/balance", "/remind", "یادآوری")

CUSTOMER_FORBIDDEN = (
    "🔒 این فرمان مخصوص صاحب مغازه است.\n"
    "اگر سؤال یا درخواستی داری، همین‌جا بنویس — به صاحب مغازه می‌رسانم.")

CREDIT_OK = ("✅ نسیه ثبت شد\nمشتری: {name}\nمبلغ: {amount}\nسررسید: {due}")
CREDIT_CAP = ("⚠️ مانده + این مبلغ از نیمی از سقف اعتبار ({cap}) بیشتر می‌شود.\n"
              "به‌عنوان مالک با این فرمان تأیید کن:\n"
              "/approve {name} {amount} [{due}]")
CREDIT_BAL = "💳 مانده‌ی نسیه‌ی {name}: {balance}"
CREDIT_PAID = ("✅ پرداخت ثبت شد\n{amount} از نسیه‌ی {name} کسر شد\nمانده: {rest}")
MORNING_HEAD = "☀️ گزارش صبح ({today})\n\n"

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


def _invoice_ok_text(no, total, items, iid):
    body = INVOICE_OK_HEAD.format(
        no=fa_num(to_int(str(no)) or 0) if no not in (None, "?") else "?",
        total=fa_num(total))
    if items:
        for (nm, q, p) in items:
            body += INVOICE_ITEM.format(name=nm, qty=fa_num(q, sep=False),
                                        price=fa_num(p), line=fa_num(q * p))
    else:
        body += INVOICE_NO_ITEMS
    return body + INVOICE_OK_TAIL.format(id=fa_num(iid, sep=False))


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

    # مشتری: هرگز ورود خودکار (اصل ۲ سرلوحه) — پیش‌نمایش برای صاحب مغازه
    if not is_manager:
        preview = "• شماره: %s\n• جمع: %s" % (
            fa_num(to_int(str(parsed["no"])) or 0) if parsed["no"] not in (None, "?") else "?",
            fa_num(total))
        if _manager_id():
            tg.send_photo(_manager_id(), blob,
                          "📷 مشتری (%s) — پیش‌نمایش خواندن:\n%s" % (name or chat_id, preview))
        tg.safe_send(chat_id, "✅ فاکتورت همراه با پیش‌نمایش خواندن برای صاحب مغازه رفت.", store)
        store.log("invoice-customer", "total=%s" % total)
        return

    # مالک: پیش‌نمایش با اطمینان per-field -> تأیید -> انبار (issue #5)
    items = [list(x) for x in parsed["items"]]
    store.add_pending(chat_id, "invoice",
                      {"no": parsed["no"], "total": total, "items": items,
                       "photo": os.path.basename(photo_path) if photo_path else ""})
    body = "📄 فاکتور خوانده شد:\n"
    body += "• شماره: %s %s\n" % (
        fa_num(to_int(str(parsed["no"])) or 0) if parsed["no"] not in (None, "?") else "؟",
        "🟢" if parsed["no"] not in (None, "?") else "🟡 (خواندم)")
    body += "• جمع کل: %s 🟢\n" % fa_num(total)
    if items:
        s = ocrmod.items_sum(items)
        body += "• قلم‌ها: %s %s\n" % (
            fa_num(len(items), sep=False),
            "🟢" if s == total else "🟡 (جمع قلم‌ها با جمع کل %s اختلاف دارد)" % fa_num(abs(s - total)))
    else:
        body += "• قلم‌ها: 🟡 (جدا خواندم؛ فقط جمع ثبت می‌شود)\n"
    body += "\nبرای ثبت در انبار «بله» بنویس، برای لغو «نه»."
    tg.safe_send(chat_id, body, store)
    store.log("invoice-pending", "total=%s items=%s" % (total, len(items)))


# ── متن / دستورات ────────────────────────────────────
def _handle_text(text, store, tg, chat_id, name, is_manager):
    t = text.strip()

    if t.startswith("/start") or t.startswith("/help") or t == "/menu" or t == "منو":
        tg.safe_send(chat_id, MANAGER_GREET if is_manager else CUSTOMER_GREET, store)
        return

    # دروازه‌ی دسترسی (issue #2، با AI-B): فرمان‌های مالی/انباری/یادآور فقط از چت مالک
    if not is_manager and t.startswith(MANAGER_ONLY_CMDS):
        store.log("forbidden-cmd", "chat=%s text=%s" % (chat_id, t[:80]))
        tg.safe_send(chat_id, CUSTOMER_FORBIDDEN, store)
        return

    if t in ("بله", "تأیید", "درست"):
        p = store.pop_pending(chat_id)
        if p and p.get("kind") == "invoice":
            d = p["payload"]
            iid = store.add_invoice("", str(d.get("no") or "?"), d["total"],
                                    d.get("items", []), d.get("photo", ""), "ocr-confirmed")
            store.log("invoice-confirmed", "id=%s total=%s" % (iid, d["total"]))
            tg.safe_send(chat_id, _invoice_ok_text(d.get("no"), d["total"], d.get("items", []), iid), store)
        else:
            tg.safe_send(chat_id, FALLBACK, store)
        return

    if t in ("نه", "لغو", "انصراف"):
        if store.pop_pending(chat_id):
            tg.safe_send(chat_id, "لغو شد ✅ (چیزی در انبار ثبت نشد)", store)
        else:
            tg.safe_send(chat_id, FALLBACK, store)
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
        if not total:
            tg.safe_send(chat_id, "مبلغ درست نیست.", store)
            return
        if is_manager:
            iid = store.add_invoice("", "?", total, [], "", "manual")
            store.log("invoice-manual", "id=%s total=%s" % (iid, total))
            tg.safe_send(chat_id, MANUAL_OK.format(total=fa_num(total), id=fa_num(iid, sep=False)), store)
        else:
            if _manager_id():
                store.upsert_customer(chat_id, name)
                tg.safe_send(_manager_id(),
                             "📥 مشتری (%s) درخواست ثبت دستی دارد: %s — ثبت فقط از حساب خودت ممکن است." % (name or chat_id, fa_num(total)), store)
            tg.safe_send(chat_id, "✅ مبلغت برای صاحب مغازه رفت؛ پس از تأیید او ثبت می‌شود.", store)
        return

    if t.startswith("/credit") or t.startswith("/approve"):
        if t.startswith("/approve") and not is_manager:
            tg.safe_send(chat_id, FALLBACK, store)
            return
        _cmd_credit(t, store, tg, chat_id, approved=t.startswith("/approve"))
        return

    if t.startswith("/balance"):
        parts = t.split(None, 1)
        if len(parts) < 2:
            tg.safe_send(chat_id, "فرمت: /balance <مشتری>", store)
            return
        tg.safe_send(chat_id, CREDIT_BAL.format(name=parts[1], balance=fa_num(store.credit_balance(parts[1]))), store)
        return

    if t.startswith("/pay"):
        parts = t.split(None, 2)
        if len(parts) < 3:
            tg.safe_send(chat_id, "فرمت: /pay <مشتری> <مبلغ>", store)
            return
        amt = to_int(parts[2])
        if not amt or amt <= 0:
            tg.safe_send(chat_id, "مبلغ درست نیست.", store)
            return
        done = store.pay_credit(parts[1], amt)
        store.log("credit-pay", "%s %s" % (parts[1], done))
        tg.safe_send(chat_id, CREDIT_PAID.format(
            name=parts[1], amount=fa_num(done),
            rest=fa_num(store.credit_balance(parts[1]))), store)
        return

    # پیام عادی مشتری -> مدیر
    if not is_manager and _manager_id():
        store.upsert_customer(chat_id, name)
        tg.safe_send(_manager_id(), "👤 مشتری (%s):\n%s" % (name or chat_id, t[:800]), store)
        tg.safe_send(chat_id, "✅ پیامت رفت؛ منتظر بمان.", store)
        return

    tg.safe_send(chat_id, FALLBACK, store)


# ── تاریخ (شمسی/میلادی — issue #5، بازبینی AI-B روی کار AI-A) ──
_FA_TRANS = str.maketrans("".join(chr(0x06F0 + i) for i in range(10)), "0123456789")


def _parse_when_date(s, hour):
    """تاریخ پذیرش: شمسی ISO (۱۴۰۵-۰۷-۲۵ یا ۱۴۰۵/۷/۲۵)، میلادی ISO (2026-10-17)،
    و فرمت‌های بازِ parse_jalali (۲۲/۷، ۲۲ مهر). ارقام فارسی هم.
    خروجی: datetime (ساعت مشخص) یا None — تاریخ نامعتبر (مثل ۱۴۰۵-۱۳-۴۰) None می‌دهد."""
    s = str(s).strip().translate(_FA_TRANS)
    m = re.match(r"^(\d{4})[-/](\d{1,2})[-/](\d{1,2})$", s)
    if m:
        y, a, b = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            if y < 1700:  # کاربر ایرانی: سال شمسی — اعتبارسنجی کبیسه‌آگاه از parse_jalali
                d = parse_jalali("%d/%d/%d" % (b, a, y))
            else:
                d = datetime.date(y, a, b)
        except ValueError:
            return None
        if d is None:
            return None
        return datetime.datetime(d.year, d.month, d.day, hour)
    d = parse_jalali(s)
    if d is not None:
        return datetime.datetime(d.year, d.month, d.day, hour)
    return None


# ── یادآور (مسیر D) ───────────────────────────────────
def _cmd_remind(t, store, tg, chat_id, is_manager):
    parts = t.split(None, 3)
    if len(parts) < 4:
        tg.safe_send(chat_id, "فرمت: /remind <مشتری> <دقیقه یا YYYY-MM-DD> <متن>", store)
        return
    cust, when, rtext = parts[1], parts[2], parts[3].strip()

    remind_at = None
    when_label = ""
    dt = _parse_when_date(when, 9)  # اول تاریخ (شمسی/میلادی)، بعد دقیقه — ترتیب مهم است: «22/7» دقیقه نیست
    if dt is not None:
        remind_at = dt.timestamp()
        when_label = jalali(dt.date()) + " ساعت ۹ صبح"
    else:
        mins = to_int(when)
        if mins is not None and 0 < mins < 100000:
            remind_at = time.time() + mins * 60
            when_label = fa_num(mins) + " دقیقه دیگر"
    if remind_at is None:
        tg.safe_send(chat_id, "زمان را نمی‌فهمم — دقیقه (مثلاً ۳۰)، شمسی (۱۴۰۵-۰۷-۲۵ یا ۲۲/۷) یا میلادی (2026-10-17) بده.", store)
        return

    rid = store.add_reminder(cust, chat_id, rtext, remind_at)
    store.log("reminder", "id=%s cust=%s at=%s" % (rid, cust, remind_at))
    tg.safe_send(chat_id, REMINDER_OK.format(name=cust, when=when_label, text=rtext[:200]), store)


# ── نسیه / نردبان اعتبار (K-lite کامل) ─────────────────
def _cmd_credit(t, store, tg, chat_id, approved):
    parts = t.split(None, 3)
    if len(parts) < 3:
        tg.safe_send(chat_id, "فرمت: /credit <مشتری> <مبلغ> [YYYY-MM-DD]", store)
        return
    cust = parts[1]
    amt = to_int(parts[2])
    if not amt or amt <= 0:
        tg.safe_send(chat_id, "مبلغ درست نیست.", store)
        return
    if len(parts) == 4:  # سررسید شمسی/میلادی — تاریخ نامعتبر هرگز بی‌صدا +۳۰ روز نمی‌شود (issue #5، بازبینی AI-B)
        dt = _parse_when_date(parts[3], 23)
        if dt is None:
            tg.safe_send(chat_id, "تاریخ سررسید را نمی‌فهمم — شمسی مثل ۱۴۰۵-۰۷-۲۵ یا ۲۲/۷، یا میلادی مثل 2026-10-17.", store)
            return
        due = dt.timestamp()
    else:
        due = time.time() + 30 * 86400
    half = store.credit_cap() // 2
    if not approved and store.credit_balance(cust) + amt > half:
        store.log("credit-cap", "%s %s > %s" % (cust, amt, store.credit_cap()))
        tg.safe_send(chat_id, CREDIT_CAP.format(
            cap=fa_num(store.credit_cap()), name=cust,
            amount=amt, due=parts[3] if len(parts) == 4 else ""), store)
        return
    rid = store.add_credit(cust, chat_id, amt, due, approved=approved)
    store.log("credit", "id=%s %s %s approved=%s" % (rid, cust, amt, approved))
    tg.safe_send(chat_id, CREDIT_OK.format(
        name=cust, amount=fa_num(amt),
        due=jalali(datetime.date.fromtimestamp(due))), store)


# ── گزارش صبح (K-lite) ─────────────────────────────────
def _tz_hours():
    try:
        return float(os.environ.get("TZ_HOURS", "3.5"))
    except ValueError:
        return 3.5


def _local_day_hour(now=None):
    now = now or time.time()
    dt = datetime.datetime.fromtimestamp(now + _tz_hours() * 3600,
                                         tz=datetime.timezone.utc)
    return dt.date(), dt.hour


def morning_report_text(store, today):
    y0 = datetime.datetime(today.year, today.month, today.day).timestamp()
    invs = store.invoices_since(y0 - 86400)
    total = sum(i["total"] for i in invs)
    due = store.due_credits(y0)
    ov = store.overdue_credits(y0)
    body = MORNING_HEAD.format(today=jalali(today))
    body += "فاکتور (24 ساعت اخیر): %s — جمع %s\n" % (
        fa_num(len(invs), sep=False), fa_num(total))
    if due:
        body += "نسیه‌ی سررسید امروز: %s\n" % fa_num(len(due), sep=False)
        for c in due:
            body += "• %s: %s\n" % (c["customer"], fa_num(c["amount"] - c["paid"]))
    else:
        body += "نسیه‌ی سررسید امروز: نیست\n"
    if ov:
        body += "نسیه‌ی عقب‌افتاده: %s\n" % fa_num(len(ov), sep=False)
        for c in ov:
            body += "• %s: %s (سررسید %s)\n" % (
                c["customer"], fa_num(c["amount"] - c["paid"]),
                jalali(datetime.date.fromtimestamp(c["due"])))
    else:
        body += "نسیه‌ی عقب‌افتاده: نیست \U0001F389"
    return body


def _maybe_morning_report(store, tg):
    """ساعت ۹ به بعد (به‌وقت محلی)؛ اگر در لحظه‌ی ۹ نبود (مثلاً بوت آفلاین بود) جبران می‌شود."""
    d, h = _local_day_hour()
    if h < 9 or not _manager_id():
        return
    key = "last_report_%d%02d%02d" % (d.year, d.month, d.day)
    if store.get_setting(key):
        return
    store.set_setting(key, "1")
    tg.safe_send(_manager_id(), morning_report_text(store, d), store, "morning")


# ── حلقه‌ی یادآورها (از bot.py صدا می‌شود) ──────────────
def _send_reminder(recipient, text, store, tg):
    """اول صدا (اگر TTS باشد)، اگر نه متن؛ اگر صدا شکست، متن. برگردان: موفق/ناموفق."""
    try:
        import tts
        blob = tts.synthesize("یادآوری: " + text)
    except Exception:
        blob = None
    if blob:
        try:
            ok = tg.send_voice(recipient, blob).get("ok", False)
            if ok:
                if store is not None:
                    store.log("reminder-voice", "sent")
                return True
        except Exception:
            pass
    return tg.safe_send(recipient, REMINDER_TO_CUSTOMER.format(text=text), store, "reminder")


def poll_reminders(store, tg):
    for r in store.due_reminders():
        ok = _send_reminder(r["chat_id"], r["text"], store, tg) if r.get("chat_id") else False
        if ok:
            store.mark_reminder(r["id"])
            if _manager_id():
                tg.safe_send(_manager_id(),
                             REMINDER_TO_MANAGER.format(name=r["customer"], when=jalali(datetime.date.today())),
                             store, "reminder-log")
        else:
            n = store.bump_reminder(r["id"])
            if n >= 3:
                store.mark_reminder(r["id"])
                store.log("reminder-failed", "id=%s بعد از %s تلاش" % (r["id"], n))
    _maybe_morning_report(store, tg)
