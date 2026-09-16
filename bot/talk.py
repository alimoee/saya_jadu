# -*- coding: utf-8 -*-
"""دست‌یار گفت‌وگو — همه دستورات و مسیرهای پیام.
قانون طلایی: هیچ‌گاه کرش، هیچ‌گاه پاسخ خالی؛ هر مسیر نامطمئن -> fallback محترمانه."""
import datetime
import os
import re
import time

from persian import fa_num, jalali, to_int, parse_jalali
import ocr as ocrmod
import stt as sttmod
import pricing

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

VOICE_GRACEFUL_C = (
    "🎙 صدایت را گرفتم، ولی الان نمی‌توانم آن را به متن تبدیل کنم — برای صاحب مغازه فرستادم.\n"
    "اگر مهم است، لطفاً همین را به‌صورت متن هم بفرست.")

FALLBACK = (
    "متوجه نشدم 😅\n"
    "ساده‌ترین کارها:\n"
    "• عکس فاکتور بفرست\n"
    "• «مبلغ: عدد» برای ثبت دستی\n"
    "• /menu برای فهرست")

# اصل ۲ سرلوحه: تصمیم مالی/انباری فقط با مالک — این فرمان‌ها هرگز از چت مشتری اجرا نمی‌شود (issue #2، با AI-B)
MANAGER_ONLY_CMDS = ("/stats", "/reply", "/credit", "/approve", "/pay", "/balance",
                     "/remind", "یادآوری", "/manage", "/charge", "/recover",
                     "/freeze", "/thaw", "/note", "/plan")

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

# ── متن‌های تریال/باتری/ریکاوری ────────────────────────
TRADE_LIST = ("ابزار", "عطار", "رستوران", "تولیدی", "کارخانه", "عمده‌فروشی",
              "خرده‌فروشی", "موبایل", "پوشاک", "یدکی خودرو", "طلا", "خدمات (کفاش)",
              "لوازم‌آلات", "قنادی", "داروخانه", "بوکسری", "عمارت", "سرایخیتی",
              "آرایشگاه", "گاراژ", "پت‌شاپ", "کتاب", "سوپرمارکت")
CITY_LIST = ("تهران", "مشهد", "اصفهان", "تبریز", "شیراز", "کرج", "کرمان", "اهواز",
             "قم", "همدان", "ارومیه", "اراک", "یزد", "زنجان", "رشت", "کرمانشاه",
             "سنندج", "زاهدان", "بندرعباس", "اردبیل", "سبزوار", "نجف‌آباد", "گرگان",
             "شهرکرد", "ساری", "کازرون", "نایین", "داورزن", "بجنورد", "دماوند",
             "نیشابور", "انزلی", "احر", "بابلسر", "خرم‌آباد", "ماهشهر", "مرودشت",
             "شبستر", "سیرجان", "فردیس", "اسلامشهر", "گرمسار", "گنبدکاووس", "دلیجان",
             "فولادشهر", "کاشان", "بروجرد", "آستارا", "لیک‌ک")

ONBOARD_Q = [
    "خوش آمدی! 🌙\nمن منشیِ دیجیتالِ این مغازه‌ام.\nبرای شروع، فقط چند سؤال کوتاه — اول: **نامت** چیست؟ ✍️",
    "چه خوب! حالا **نام مغازه**؟ 🏪",
    "**صنف** چیست؟ (مثلاً: ابزار، عطار، رستوران، موبایل، پوشاک، طلای …)",
    "**شهر**؟",
    "**شماره‌ی موبایل**؟ (شکل: 09xxxxxxxxx) 📱",
    "در ماه تقریباً **چند مشتری** داری؟ (فقط عدد)",
    "تقریباً **چند قلم کالا** داری؟ (فقط عدد)",
]
ONBOARD_VERIFY = ("🔍 در حالِ بررسیِ اطلاعاتت…\n(شماره، شهر، صنف و هماهنگیِ اعداد را چک می‌کنم تا مطمئن شوم با یک مغازه‌ی واقعی طرفم) ⏳")
ONBOARD_DONE = ("✅ {pct}٪ اطلاعاتِ واردشده بررسی و صحیح است.\n{detail}\n\n🎁 حالا **۱۰ روز آزمایشِ رایگان** شروع شد!\n"
                "🔋 باتری: ۱۰۰٪ — هر گفتگو، فاکتور و تماس از این اعتبار کم می‌شود.\n"
                "هر وقت خواستی شروع کنی: /menu")
ONBOARD_PHONE_BAD = "⚠️ این شماره شبیه موبایل نیست (باید ۰۹ + ۱۰ رقم باشد). دوباره بفرست، لطفاً."
ONBOARD_NUM_BAD = "⚠️ فقط عدد بفرست (مثلاً: ۴۰ یا 40)."
ONBOARD_FIRST_PHOTO = "سلام! 👋 من منشیِ این مغازه‌ام. اول /start بزن تا چند سؤال کوتاه بپرسم و حسابِ رایگانت را باز کنم."
ONBOARD_FIRST_VOICE = "سلام! 👋 اول /start بزن تا حسابِ آزمایشی‌ات باز شود؛ بعد صدایت را هم می‌فهمم. 🌙"
BATTERY_EMPTY = ("🔋 باتری خالی شد.\nبرای ادامه: **رسیدِ پرداخت را به‌صورت عکس بفرست** — "
                 "یا با صاحبِ مغازه تماس بگیر. (اطلاعاتت امن است)")
BATTERY_LOW = "🔋 باتری: {pct}٪ — لطفاً زودتر شارژ کن تا منشی در خدمتت بماند."
OVERDUE_WARN = ("{blink}🔋 دوره‌ی حساب به‌تمام ({date}).\n⚠️ **اطلاعاتِ شما حذف خواهد شد** — "
                "حالا شارژ کن: رسیدِ پرداخت را **به‌صورت عکس** همین‌جا بفرست. "
                "(تا {grace} روز فرصت داری)")
FROZEN_NOTICE = ("❄️ حساب موقتاً **یخ‌زده** شد — ولی **داده‌هایت در سرور ما محفوظ است**.\n"
                 "هر روزِ انتظار: {fee} تومان حق‌البازگشت.\n"
                 "برای فعال‌شدن: رسیدِ پرداخت را عکس بفرست، یا با صاحبِ مغازه تماس بگیر.")
FROZEN_SHORT = "❄️ حساب یخ‌زده است. رسیدِ پرداخت را **عکس** بفرست تا بررسی شود."
RECEIPT_GOT = "📷 رسید دریافت شد — همین حالا بررسی می‌شود. به‌محضِ تأیید، حسابت شارژ می‌شود و من بهت خبر می‌دهم. ✅"
RECEIPT_TO_MGR = ("🧾 رسیدِ پرداخت از: {name} ({shop})\nچت: {chat_id}\n"
                  "برای فعال‌کردن حساب: /charge {name}")
APPROVE_OK = ("✅ پرداخت تأیید شد — حسابِ {name} فعال شد:\n"
              "+۳۰ روز خدمت و باتری پر شد 🔋\nبه مشتری خبر دادم.")
APPROVE_NOACCT = "❌ حسابی با این نام/چت پیدا نشد: {target}\n/manage برای فهرست"
FEE_APPLIED = "✅ حق‌البازگشت ({fee}) محاسبه و حسابِ {name} بازگردانی شد. 🔓"
FREEZE_OK = "❄️ حسابِ {name} یخ‌زد."
THAW_OK = "🔓 حسابِ {name} فعال شد (+۳۰ روز، باتری پر)."
NOTE_OK = "📝 یادداشت رفت روی حسابِ {name}."
PLAN_OK = "📦 بسته‌ی {name} → {label} شد (باتری بر اساسِ شمولِ بسته پر شد)."
MANAGE_EMPTY = "هنوز حسابی نیست."
BATTERY_INFO = "🔋 باتری: {pct}٪ — {left} از {total} واحد خدمت\nبسته: {label}\nانقضای دوره: {date}"
NEW_CUST = ("🆕 مشتریِ جدید: {name} — {shop} ({trade}، {city})\n"
            "تأیید اطلاعات: {pct}٪ | چت: {chat_id}\n"
            "تریال ۱۰ روزه شروع شد. مدیریت: /manage")


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


def _msg_units(msg):
    """هزینه‌ی یک پیام به واحد خدمت (صدا بر اساسِ طول، عکس=فاکتور، متن=گفتگو)."""
    if "voice" in msg:
        sec = (msg.get("voice") or {}).get("duration") or 30
        return max(0.05, sec / 60.0 * pricing.UNIT_PRICE["voice_min"] / 1000.0)
    if "photo" in msg:
        return 0.5
    if msg.get("text"):
        return 1.0
    return 0.0


def _handle_inner(msg, store, tg, chat_id, name, is_manager):
    acct = None
    if not is_manager:
        acct = store.get_account(chat_id)
        # بدون حساب -> شروعِ جمع‌آوری اطلاعات (تریال ۱۰ روزه)
        if acct is None:
            if "photo" in msg or "voice" in msg:
                tg.safe_send(chat_id,
                             ONBOARD_FIRST_PHOTO if "photo" in msg else ONBOARD_FIRST_VOICE, store)
                return
            p = store.pop_pending(chat_id)
            state = p["payload"] if (p and p.get("kind") == "onboard") else None
            txt = (msg.get("text") or "").strip()
            if txt in ("نه", "لغو", "انصراف") and state:
                tg.safe_send(chat_id, "انصراف شد ✅ (حسابی باز نشد)", store)
                return
            _onboard(txt, store, tg, chat_id, name, state)
            return
        # حسابِ یخ‌زده: فقط مسیرِ رسید
        if acct.get("status") == pricing.STATUS_FROZEN:
            if "photo" in msg:
                _receipt_photo(msg, store, tg, chat_id, acct)
                return
            tg.safe_send(chat_id, FROZEN_SHORT, store)
            return
        # حسابِ عقب‌افتاده با عکس -> رسید
        if (acct.get("status") == pricing.STATUS_OVERDUE and "photo" in msg
                and (acct.get("receipt_pending") or 0) == 0):
            _receipt_photo(msg, store, tg, chat_id, acct)
            return
        # دروازه‌ی باتری
        cost = _msg_units(msg)
        if cost and (acct.get("units_left") or 0) < cost:
            tg.safe_send(chat_id, BATTERY_EMPTY, store)
            return
    prev_pct = pricing.battery_pct(acct) if acct else None

    # ۱) صوت (ماژول A)
    _processed = {"done": False}
    if "voice" in msg:
        blob = _voice_bytes(msg, store, tg)
        text = _stt(blob)
        if text:
            store.log("voice", "stt ok: %s" % text[:120])
            _handle_text(text.strip(), store, tg, chat_id, name, is_manager)
            _processed["done"] = True
        else:
            # بدون STT صدای مشتری گم نمی‌شود (ماژول F): برای صاحب مغازه می‌رود
            if not is_manager and _manager_id() and blob:
                tg.send_voice(_manager_id(), blob)
            tg.safe_send(chat_id, VOICE_GRACEFUL_C if not is_manager else VOICE_GRACEFUL, store)
            store.log("voice", "stt unavailable -> " + ("relay to manager" if not is_manager else "graceful"))
        return

    # ۲) عکس -> فاکتور
    if "photo" in msg:
        _handle_photo(msg, store, tg, chat_id, name, is_manager)
        _maybe_charge(store, tg, chat_id, acct, prev_pct, _msg_units(msg), is_manager)
        return

    # ۳) متن
    text = (msg.get("text") or "").strip()
    if text:
        _handle_text(text, store, tg, chat_id, name, is_manager)
        _maybe_charge(store, tg, chat_id, acct, prev_pct, _msg_units(msg), is_manager)
        return

    tg.safe_send(chat_id, FALLBACK, store)


def _maybe_charge(store, tg, chat_id, acct, prev_pct, cost, is_manager):
    """کسریِ واحد + هشدارِ عبور از آستانه‌ی کم‌باتری (مثل موبایل)."""
    if is_manager or acct is None or not cost:
        return
    left = store.charge_units(chat_id, cost)
    a2 = store.get_account(chat_id) or acct
    pct = pricing.battery_pct(a2)
    if prev_pct is not None and prev_pct > pricing.LOW_BATTERY_PCT >= pct:
        tg.safe_send(chat_id, BATTERY_LOW.format(pct=fa_num(pct, sep=False)), store, "battery-low")


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
    """STT اختیاری (ماژول A) — stt.py: اول Vosk محلی (آفلاین)، بعد STT_URL؛ هرگز نمی‌شکند."""
    return sttmod.transcribe(ogg_bytes)


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


# ── onboarding: جمع‌آوری اطلاعات + بررسی + تریال ۱۰ روزه 
ONBOARD_FIELDS = ("name", "shop", "trade", "city", "phone", "nc", "ni")


def _validate_phone(p):
    d = to_int(str(p or ""))
    s = str(d) if d is not None else ""
    return s.startswith("9") and len(s) == 10 or s.startswith("09") and len(s) == 11


def _in_list(word, lst):
    w = (word or "").strip()
    if not w:
        return False
    return any(w in c or c in w for c in lst)


def _onboard(text, store, tg, chat_id, name, state):
    """ماشینِ حالتِ سؤالات. state = payload از pending (یا None در شروع)."""
    t = (text or "").strip()
    if state is None:
        d, step, tries = {}, 0, 0
        if t.lower() in ("/start", "/help", "/menu", "منو", "سلام", "hi", "hello"):
            pass
        else:
            d["name"] = t
            step = 1
    else:
        d, step, tries = state.get("d", {}), state.get("step", 0), state.get("tries", 0)
        key = ONBOARD_FIELDS[step]
        if not t:
            tg.safe_send(chat_id, ONBOARD_Q[step], store)
            store.add_pending(chat_id, "onboard", {"d": d, "step": step, "tries": tries})
            return
        # اعتبارسنجی‌های مرحله‌ای
        if key == "phone" and not _validate_phone(t):
            if tries < 1:
                tries += 1
                tg.safe_send(chat_id, ONBOARD_PHONE_BAD, store)
                store.add_pending(chat_id, "onboard", {"d": d, "step": step, "tries": tries})
                return
        if key in ("nc", "ni"):
            n = to_int(t)
            if n is None or not (1 <= n <= 99999):
                if tries < 1:
                    tries += 1
                    tg.safe_send(chat_id, ONBOARD_NUM_BAD, store)
                    store.add_pending(chat_id, "onboard", {"d": d, "step": step, "tries": tries})
                    return
                n = 1
            d[key] = n
        else:
            d[key] = t
        step += 1
        if step >= len(ONBOARD_FIELDS):
            _finish_onboarding(store, tg, chat_id, d)
            return
        tg.safe_send(chat_id, ONBOARD_Q[step], store)
        store.add_pending(chat_id, "onboard", {"d": d, "step": step, "tries": 0})
        return
    # شروع: سؤالِ اول
    tg.safe_send(chat_id, ONBOARD_Q[step], store)
    store.add_pending(chat_id, "onboard", {"d": d, "step": step, "tries": 0})


def _finish_onboarding(store, tg, chat_id, d):
    """بررسی صحت (صادقانه) + بازکردن تریال + خبر به مالک."""
    nc, ni = d.get("nc") or 1, d.get("ni") or 1
    checks = [
        ("نام", len((d.get("name") or "").strip()) >= 2),
        ("نام مغازه", len((d.get("shop") or "").strip()) >= 2),
        ("صنف", _in_list(d.get("trade"), TRADE_LIST)),
        ("شهر", _in_list(d.get("city"), CITY_LIST)),
        ("شماره‌ی موبایل", _validate_phone(d.get("phone"))),
        ("اعداد مشتری و کالا", 1 <= nc <= 99999 and 1 <= ni <= 99999),
    ]
    pct = int(round(sum(1 for _l, ok in checks if ok) / len(checks) * 100))
    units = pricing.units_included(pricing.TRIAL_PLAN)
    now = int(time.time())
    store.upsert_account(chat_id,
                         name=(d.get("name") or "").strip(),
                         shop=(d.get("shop") or "").strip(),
                         trade=(d.get("trade") or "").strip(),
                         city=(d.get("city") or "").strip(),
                         phone=str(d.get("phone") or ""),
                         n_customers=nc, n_items=ni,
                         status=pricing.STATUS_TRIAL, plan=pricing.TRIAL_PLAN,
                         verification=pct,
                         period_end=now + pricing.TRIAL_DAYS * 86400,
                         units_total=units, units_left=units)
    detail = "\n".join((("✅ " if ok else "⚠️ ") + lab) for lab, ok in checks)
    tg.safe_send(chat_id, ONBOARD_DONE.format(pct=fa_num(pct, sep=False), detail=detail),
                 store, "onboard-done")
    if _manager_id():
        tg.safe_send(_manager_id(),
                     NEW_CUST.format(name=d.get("name"), shop=d.get("shop"),
                                     trade=d.get("trade"), city=d.get("city"),
                                     pct=fa_num(pct, sep=False), chat_id=chat_id),
                     store, "new-customer")
    store.log("onboard", "chat=%s pct=%s" % (chat_id, pct))


# ── رسیدِ پرداخت (مسیرِ بازگشت از اخطار/یخ) ────────────
def _receipt_photo(msg, store, tg, chat_id, acct):
    ph = (msg.get("photo") or [{}])[-1]
    fid = ph.get("file_id")
    blob = tg.download_file(fid) if fid else None
    if blob and _manager_id():
        try:
            tg.send_photo(_manager_id(), blob,
                          RECEIPT_TO_MGR.format(name=acct.get("name") or "?",
                                                shop=acct.get("shop") or "?",
                                                chat_id=chat_id))
        except Exception:
            pass
    store.upsert_account(chat_id, receipt_pending=1)
    tg.safe_send(chat_id, RECEIPT_GOT, store, "receipt")
    store.log("receipt", "chat=%s bytes=%s" % (chat_id, len(blob) if blob else 0))


def _resolve_account(store, target):
    """نام، shop یا chat_id -> حساب."""
    n = to_int(str(target))
    if n:
        a = store.get_account(n)
        if a:
            return a
    return store.account_by_name(target)


def _scan_accounts(store, tg):
    """یک‌بار در هر دورِ حلقه: اخطارِ روزانه + یخ‌زدگی پس از ۷ روز."""
    now = int(time.time())
    mgr = _manager_id()
    for a in store.list_accounts():
        if a.get("status") == pricing.STATUS_FROZEN:
            continue
        pe = a.get("period_end") or 0
        if not pe or now <= pe:
            continue
        days = (now - pe) // 86400
        if days < pricing.WARN_GRACE_DAYS:
            store.upsert_account(a["chat_id"], status=pricing.STATUS_OVERDUE)
            if now - (a.get("last_warn") or 0) >= 86400:
                blink = "🔴" if days % 2 == 0 else "⚫"
                tg.safe_send(a["chat_id"], OVERDUE_WARN.format(
                    blink=blink,
                    date=jalali(datetime.date.fromtimestamp(pe)),
                    grace=fa_num(pricing.WARN_GRACE_DAYS, sep=False)),
                    store, "overdue-warn")
                store.upsert_account(a["chat_id"], last_warn=now)
                if mgr:
                    tg.safe_send(mgr, "⚠️ حسابِ %s (%s) عقب‌افتاده شد. /manage"
                                 % (a.get("name") or a["chat_id"], a["chat_id"]),
                                 store, "overdue-mgr")
        else:
            fee = pricing.recovery_fee(a, now)
            store.upsert_account(a["chat_id"], status=pricing.STATUS_FROZEN)
            tg.safe_send(a["chat_id"], FROZEN_NOTICE.format(
                fee=fa_num(pricing.RECOVERY_PER_DAY)), store, "frozen")
            if mgr:
                tg.safe_send(mgr, "❄️ %s یخ‌زد — حق‌البازگشت فعلی: %s. /recover %s"
                             % (a.get("name") or a["chat_id"],
                                fa_num(fee), a["chat_id"]),
                             store, "frozen-mgr")
            store.log("freeze", "chat=%s fee=%s" % (a["chat_id"], fee))


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

    # ── حساب‌ها و باتری (مالک) ───────────────────────────
    if t.startswith("/battery"):
        if is_manager:
            rows = store.list_accounts()
            if not rows:
                tg.safe_send(chat_id, MANAGE_EMPTY, store)
                return
            body = "🔋 حساب‌ها:\n"
            for a in rows[:15]:
                body += ("• %s | %s | 🔋%s٪ | تا %s%s\n" % (
                    a.get("name") or a["chat_id"], a.get("status"),
                    fa_num(pricing.battery_pct(a), sep=False),
                    jalali(datetime.date.fromtimestamp(a["period_end"])) if a.get("period_end") else "—",
                    (" | ⛄ حق‌البازگشت %s" % fa_num(pricing.recovery_fee(a, int(time.time()))))
                    if a.get("status") == pricing.STATUS_FROZEN else ""))
            tg.safe_send(chat_id, body, store)
        else:
            a = store.get_account(chat_id) or {}
            p = pricing.PACKAGES.get(a.get("plan") or pricing.TRIAL_PLAN)
            tg.safe_send(chat_id, BATTERY_INFO.format(
                pct=fa_num(pricing.battery_pct(a), sep=False),
                left=fa_num(int(a.get("units_left") or 0), sep=False),
                total=fa_num(int(a.get("units_total") or 0), sep=False),
                label=p["label"],
                date=jalali(datetime.date.fromtimestamp(a["period_end"])) if a.get("period_end") else "—"),
                store)
        return

    if t.startswith("/manage"):
        rows = store.list_accounts()
        if not rows:
            tg.safe_send(chat_id, MANAGE_EMPTY, store)
            return
        body = "📇 حساب‌ها (%d):\n" % len(rows)
        for a in rows[:20]:
            extra = ""
            if a.get("status") == pricing.STATUS_FROZEN:
                extra = " | ⛄ ریکاوری %s" % fa_num(pricing.recovery_fee(a, int(time.time())))
            if a.get("receipt_pending"):
                extra += " | 🧾 رسید در انتظار"
            if a.get("notes"):
                extra += " | 📝 %s" % a["notes"][:40]
            body += ("• %s | %s | 🔋%s٪ | انبار: %s مشتری / %s قلم%s\n" % (
                a.get("name") or a["chat_id"], a.get("status"),
                fa_num(pricing.battery_pct(a), sep=False),
                fa_num(a.get("n_customers") or 0, sep=False),
                fa_num(a.get("n_items") or 0, sep=False), extra))
        body += ("\nفرمان‌ها: /charge <نام> · /recover <نام> · /freeze <نام> · "
                 "/thaw <نام> · /note <نام> <متن> · /plan <نام> <بسته>")
        tg.safe_send(chat_id, body, store)
        return

    if t.startswith("/charge") or t.startswith("/recover") or t.startswith("/freeze") \
            or t.startswith("/thaw") or t.startswith("/note") or t.startswith("/plan"):
        parts = t.split(None, 2)
        if len(parts) < 2:
            tg.safe_send(chat_id, "فرمت: " + t.split()[0] + " <نام یا chat_id>", store)
            return
        target = parts[1]
        a = _resolve_account(store, target)
        if a is None:
            tg.safe_send(chat_id, APPROVE_NOACCT.format(target=target), store)
            return
        now = int(time.time())
        if t.startswith("/charge"):
            units = pricing.units_included(a.get("plan") or pricing.TRIAL_PLAN)
            store.upsert_account(a["chat_id"], status=pricing.STATUS_ACTIVE,
                                 period_end=now + pricing.PERIOD_DAYS * 86400,
                                 units_total=units, units_left=units, receipt_pending=0)
            tg.safe_send(a["chat_id"], "✅ رسیدت تأیید شد — حسابت **شارژ شد**! 🔋\n"
                         "۳۰ روز دیگر، منشی در خدمتت هست. 🌙",
                         store, "recharge-cust")
            tg.safe_send(chat_id, APPROVE_OK.format(name=a.get("name") or target), store)
            store.log("recharge", "chat=%s" % a["chat_id"])
        elif t.startswith("/recover"):
            fee = pricing.recovery_fee(a, now)
            if len(parts) < 3 or parts[2].lower() not in ("yes", "بله", "تأیید"):
                tg.safe_send(chat_id, "⛄ حق‌البازگشتِ %s: **%s** (%d روز × %s).\n"
                             "برای اعمال و بازکردن: %s" % (
                                 a.get("name") or target, fa_num(fee),
                                 max(0, pricing.days_overdue(a, now) - pricing.WARN_GRACE_DAYS + 1),
                                 fa_num(pricing.RECOVERY_PER_DAY),
                                 "/recover %s yes" % a["chat_id"]), store)
            else:
                units = pricing.units_included(a.get("plan") or pricing.TRIAL_PLAN)
                store.upsert_account(a["chat_id"], status=pricing.STATUS_ACTIVE,
                                     period_end=now + pricing.PERIOD_DAYS * 86400,
                                     units_total=units, units_left=units)
                tg.safe_send(a["chat_id"], "🔓 حسابت بازگردانی شد — ۳۰ روز خدمت فعال شد. 🔋",
                             store, "recovered-cust")
                tg.safe_send(chat_id, FEE_APPLIED.format(fee=fa_num(fee),
                                                         name=a.get("name") or target), store)
                store.log("recover", "chat=%s fee=%s" % (a["chat_id"], fee))
        elif t.startswith("/freeze"):
            store.upsert_account(a["chat_id"], status=pricing.STATUS_FROZEN)
            tg.safe_send(chat_id, FREEZE_OK.format(name=a.get("name") or target), store)
        elif t.startswith("/thaw"):
            units = pricing.units_included(a.get("plan") or pricing.TRIAL_PLAN)
            store.upsert_account(a["chat_id"], status=pricing.STATUS_ACTIVE,
                                 period_end=now + pricing.PERIOD_DAYS * 86400,
                                 units_total=units, units_left=units)
            tg.safe_send(chat_id, THAW_OK.format(name=a.get("name") or target), store)
        elif t.startswith("/note"):
            note = parts[2] if len(parts) > 2 else ""
            store.upsert_account(a["chat_id"], notes=note)
            tg.safe_send(chat_id, NOTE_OK.format(name=a.get("name") or target), store)
        elif t.startswith("/plan"):
            label = parts[2] if len(parts) > 2 else ""
            pk = None
            for k, p in pricing.PACKAGES.items():
                if label and (label in p["label"] or p["label"] in label):
                    pk = k
                    break
            if pk is None:
                tg.safe_send(chat_id, "بسته‌ها: شروع / مغازه / بازار", store)
                return
            units = pricing.units_included(pk)
            store.upsert_account(a["chat_id"], plan=pk,
                                 units_total=units, units_left=units)
            tg.safe_send(chat_id, PLAN_OK.format(name=a.get("name") or target,
                                                 label=pricing.PACKAGES[pk]["label"]), store)
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
    ok = tg.safe_send(_manager_id(), morning_report_text(store, d), store, "morning")
    if ok:
        # فقط بعد از ارسال موفق علامت می‌خورد؛ در غیر این صورت فردا جبران می‌شود
        store.set_setting(key, "1")


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
    try:
        _scan_accounts(store, tg)
    except Exception as e:
        store.log("account-scan", repr(e)[:200])
    _maybe_morning_report(store, tg)
