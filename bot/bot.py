#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""سایا-جادو — ربات تلگرام (MVP فز ۱)
اجرا:  BOT_TOKEN=... MANAGER_CHAT_ID=... python3 bot.py
تست آفلاین:  python3 bot.py --selftest     (بدون توکن، بدون شبکه)
فقط stdlib؛ بک‌اند OCR/STT اختیاری (env) با fallback محترمانه."""
import os
import sys
import signal
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import store as storemod
import talk
from persian import fa_num  # noqa: E402


def selftest():
    """کل پایپ‌لاین آفلاین: amla -> parse -> anbar -> reminder -> dialogue."""
    import tempfile
    import datetime
    from persian import jalali, to_int
    import ocr as ocrmod

    def _fa(s):
        return "".join(chr(0x06F0 + int(c)) if c.isdigit() else c for c in s).replace(",", "\u066C")

    ok = 0
    def check(name, cond):
        nonlocal ok
        print(("  PASS " if cond else "  FAIL ") + name)
        assert cond, name
        ok += 1

    print("— persian —")
    check("fa_num thousands", fa_num(68265000) == _fa("68,265,000"))
    check("fa_num small", fa_num(10457, sep=False) == _fa("10457"))
    check("to_int fa", to_int(_fa("68,265,000")) == 68265000)
    check("to_int ascii", to_int("68,265,000") == 68265000)
    check("jalali 2026-10-14", jalali(datetime.date(2026, 10, 14)) == _fa("22") + " " + "مهر" + " " + _fa("1405"))
    from persian import j2g, g2j, parse_jalali
    check("j2g 1395/1/23", j2g(1395, 1, 23) == (2016, 4, 11))
    check("g2j 2026-03-21", g2j(2026, 3, 21) == (1405, 1, 1))
    check("j2g 1399/12/30 leap", j2g(1399, 12, 30) == (2021, 3, 20))
    check("parse 22/7 (1405)", parse_jalali("22/7", datetime.date(2026, 9, 15)) == datetime.date(2026, 10, 14))
    check("parse 30/12/1399", parse_jalali("30/12/1399") == datetime.date(2021, 3, 20))
    check("parse 30/12/1405 rejected", parse_jalali("30/12/1405") is None)

    print("— ocr parse —")
    sample = (
        "فاکتور فروش\n"
        "شماره: 10457\n"
        "گوشت بره ۱۰ کیلویی   40 x 1\u066C600\u066C000\n"
        "سبزیجات   1 x 4\u066C265\u066C000\n"
        "مجموع: " + _fa("68,265,000") + "\n"
    )
    p = ocrmod.parse_invoice(sample)
    check("parse no", p is not None and p["no"] == "10457")
    check("parse total", p is not None and p["total"] == 68265000)
    check("parse items", p is not None and len(p["items"]) == 2)
    check("items sum", ocrmod.items_sum(p["items"]) == 68265000)
    check("parse fails without total", ocrmod.parse_invoice("چیزی بدون جمع") is None)

    print("— store —")
    with tempfile.TemporaryDirectory() as td:
        st = storemod.Store(os.path.join(td, "t.db"))
        iid = st.add_invoice("restoran", "10457", 68265000,
                             [["گوشت بره ۱۰ کیلویی", 40, 1600000],
                              ["سبزیجات", 1, 4265000]], "", "ocr")
        check("invoice saved", st.last_invoice()["total"] == 68265000)
        check("items json", st.last_invoice()["items"][0][0] == "گوشت بره ۱۰ کیلویی")
        rid = st.add_reminder("علی", 12345, "وقت پرداخت است", time.time() - 60)
        due = st.due_reminders()
        check("reminder due", len(due) == 1 and due[0]["id"] == rid)
        st.mark_reminder(rid)
        check("reminder marked", st.due_reminders() == [])
        # prune_log (issue #7): قدیمی حذف، تازه می‌ماند
        st.log("fresh", "keep me")
        with st._conn() as c:
            c.execute("INSERT INTO log(ts,kind,detail) VALUES(?,?,?)",
                      (int(time.time()) - 90 * 86400, "old", "drop me"))
        st.prune_log(30)
        rows = [r["kind"] for r in st._conn().execute("SELECT kind FROM log").fetchall()]
        check("prune keeps fresh", "fresh" in rows)
        check("prune drops old", "old" not in rows)

    print("— talk (mock tg) —")
    sent = []
    class MockTG:
        def download_file(self, fid):
            return b"\xff\xd8fakejpg"
        def send_message(self, chat_id, text):
            sent.append((chat_id, text))
            return {"ok": True}
        def send_photo(self, chat_id, blob, caption=""):
            sent.append((chat_id, "PHOTO:" + caption))
            return {"ok": True}
        def safe_send(self, cid, text, stx=None, kind="s"):
            sent.append((cid, text))
            return True
    talk.ocr_image_stub = None

    with tempfile.TemporaryDirectory() as td:
        st = storemod.Store(os.path.join(td, "t2.db"))
        os.environ["SAYA_DATA"] = os.path.join(td, "data")
        os.environ["MANAGER_CHAT_ID"] = "999"

        # فاکتور با بک‌اند mock -> پیش‌نمایش مالک + تأیید
        import talk as talkmod
        # ساعت کل selftest روی قبل از ۹ قفل می‌شود تا گزارش صبح زودتر از تستِ خودش فراموی‌نشود
        real_tdh0 = talkmod._local_day_hour
        talkmod._local_day_hour = lambda _now=None: (datetime.date.today(), 8)
        real_ocr = talkmod.ocrmod.ocr_image
        talkmod.ocrmod.ocr_image = lambda b: sample
        msg = {"chat": {"id": 999, "type": "private"},
               "from": {"first_name": "مدیر"},
               "photo": [{"file_id": "F1"}],
               "message_id": 1}
        talkmod.handle(msg, st, MockTG())
        talkmod.ocrmod.ocr_image = real_ocr

        check("preview sent, not auto-stored", st.invoice_count() == 0)
        check("preview asks بله", any("بله" in x and _fa("68,265,000") in x for (_c, x) in sent if isinstance(x, str)))
        sent.clear()
        talkmod.handle({"chat": {"id": 999}, "from": {"first_name": "مدیر"},
                        "text": "بله", "message_id": 2}, st, MockTG())
        check("confirmed stored", st.invoice_count() == 1)
        check("confirm reply has total", any(_fa("68,265,000") in x for (_c, x) in sent if isinstance(x, str)))
        # فاکتور دوم -> لغو
        talkmod.ocrmod.ocr_image = lambda b: sample
        sent.clear()
        talkmod.handle(msg, st, MockTG())
        talkmod.ocrmod.ocr_image = real_ocr
        talkmod.handle({"chat": {"id": 999}, "from": {"first_name": "مدیر"},
                        "text": "نه", "message_id": 3}, st, MockTG())
        check("cancelled not stored", st.invoice_count() == 1)

        # بدون بک‌اند OCR -> fallback
        talkmod.ocrmod.ocr_image = lambda b: None
        sent.clear()
        talkmod.handle(msg, st, MockTG())
        talkmod.ocrmod.ocr_image = real_ocr
        check("ocr-missing fallback", any("مبلغ: عدد" in t for (_c, t) in sent if isinstance(t, str)))

        # ثبت دستی مالک
        sent.clear()
        talkmod.handle({"chat": {"id": 999}, "from": {"first_name": "م"},
                        "text": "مبلغ: " + _fa("5,000,000"), "message_id": 40}, st, MockTG())
        check("manual total parsed", st.last_invoice()["total"] == 5000000)
        # مشتری: فقط درخواست، بدون ثبت خودکار
        # (طرح جدید: مشتری باید حساب/انبارداری داشته — قبلاً این کار را onboarding می‌کرد)
        st.upsert_account(555, name="علی", status="active", plan="harsheh",
                          period_end=int(time.time()) + 30 * 86400,
                          units_total=1000.0, units_left=500.0)
        n_before = st.invoice_count()
        sent.clear()
        talkmod.handle({"chat": {"id": 555}, "from": {"first_name": "علی"},
                        "text": "مبلغ: " + _fa("1,000,000"), "message_id": 41}, st, MockTG())
        check("customer manual not auto-stored", st.invoice_count() == n_before)
        check("customer manual relayed", any(c == "999" and "درخواست ثبت" in x for (c, x) in sent if isinstance(x, str)))

        # منو
        sent.clear()
        talkmod.handle({"chat": {"id": 111}, "from": {"first_name": "م"},
                        "text": "/start", "message_id": 3}, st, MockTG())
        # طرح جدید: چتِ ناشناس -> onboarding (یا گرامت مدیر اگر مالک باشد)
        check("start greets", any("منشی" in t for (_c, t) in sent if isinstance(t, str)))

        # پیام مشتری -> مدیر
        sent.clear()
        talkmod.handle({"chat": {"id": 555}, "from": {"first_name": "علی"},
                        "text": "سلام، فاکتورم کی آماده؟", "message_id": 4}, st, MockTG())
        check("customer relayed", any(c in (999, "999") and "علی" in t for (c, t) in sent if isinstance(t, str)))
        check("customer acked", any(c == 555 and "پیامت رفت" in t for (c, t) in sent if isinstance(t, str)))

        # یادآور -> موعد (گذشته) -> ارسال متن (TTS خاموش)
        sent.clear()
        real_syn = None
        try:
            import tts as ttsmod
            real_syn = ttsmod.synthesize
            ttsmod.synthesize = lambda s: None
        except ImportError:
            pass
        st.add_reminder("علی", 111, "پرداخت قبض را یادت نرود", time.time() - 10)
        talkmod.poll_reminders(st, MockTG())
        check("reminder delivered", any(c == 111 and "یادآوری" in x for (c, x) in sent if isinstance(x, str)))
        # یادآور با صدا (TTS mock) -> send_voice
        sent.clear()
        voices = []
        class MockTGV(MockTG):
            def send_voice(self, cid, blob):
                voices.append((cid, len(blob)))
                return {"ok": True}
        st.add_reminder("علی", 111, "قبض برق", time.time() - 5)
        if real_syn is not None:
            ttsmod.synthesize = lambda s: b"FAKE_MP3_BYTES"
        talkmod.poll_reminders(st, MockTGV())
        if real_syn is not None:
            ttsmod.synthesize = real_syn
        check("reminder voice sent", len(voices) == 1 and voices[0][0] == 111)

        # متن ناشناخته -> fallback (هرگز خالی)
        sent.clear()
        talkmod.handle({"chat": {"id": 999}, "from": {"first_name": "م"},
                        "text": "xxxx", "message_id": 6}, st, MockTG())
        check("unknown fallback", any("متوجه نشدم" in t for (_c, t) in sent if isinstance(t, str)))

        print("— credit / نردبان اعتبار —")
        st.set_setting("credit_cap", "2000000")
        # ثبت عادی
        sent.clear()
        talkmod.handle({"chat": {"id": 999}, "from": {"first_name": "م"},
                        "text": "/credit علی 600000", "message_id": 8}, st, MockTG())
        check("credit added", st.credit_balance("علی") == 600000)
        # شکستن سقف -> تأیید لازم
        sent.clear()
        talkmod.handle({"chat": {"id": 999}, "from": {"first_name": "م"},
                        "text": "/credit علی 500000", "message_id": 9}, st, MockTG())
        check("cap blocks", st.credit_balance("علی") == 600000)
        check("cap asks approval", any("/approve" in x for (_c, x) in sent if isinstance(x, str)))
        # تأیید مالک
        sent.clear()
        talkmod.handle({"chat": {"id": 999}, "from": {"first_name": "م"},
                        "text": "/approve علی 500000", "message_id": 10}, st, MockTG())
        check("approved", st.credit_balance("علی") == 1100000)
        # پرداخت
        sent.clear()
        talkmod.handle({"chat": {"id": 999}, "from": {"first_name": "م"},
                        "text": "/pay علی 300000", "message_id": 11}, st, MockTG())
        check("paid", st.credit_balance("علی") == 800000)
        # دروازه‌ی دسترسی (issue #2، با AI-B): فرمان‌های مالی فقط از چت مالک
        print("— دروازه‌ی دسترسی —")
        sent.clear()
        talkmod.handle({"chat": {"id": 555}, "from": {"first_name": "علی"},
                        "text": "/pay علی " + _fa("100,000"), "message_id": 50}, st, MockTG())
        check("customer /pay blocked",
              any(c == 555 and "صاحب مغازه" in x for (c, x) in sent if isinstance(x, str)))
        check("balance unchanged", st.credit_balance("علی") == 800000)
        # چتِ بی‌حساب: هیچ فرمان مالی نمی‌خورد — هدایت می‌شود به onboarding
        sent.clear()
        talkmod.handle({"chat": {"id": 777}, "from": {"first_name": "بی‌حساب"},
                        "text": "/credit علی 100000", "message_id": 51}, st, MockTG())
        check("stranger /credit not executed",
              st.credit_balance("علی") == 800000
              and any(c == 777 and "نام مغازه" in x for (c, x) in sent if isinstance(x, str)))
        for cmd in ("/balance علی", "/stats", "/remind علی 30 سلام"):
            sent.clear()
            talkmod.handle({"chat": {"id": 555}, "from": {"first_name": "علی"},
                            "text": cmd, "message_id": 51}, st, MockTG())
            check("customer blocked: " + cmd.split()[0],
                  any(c == 555 and "صاحب مغازه" in x for (c, x) in sent if isinstance(x, str)))
        sent.clear()
        talkmod.handle({"chat": {"id": 999}, "from": {"first_name": "م"},
                        "text": "/stats", "message_id": 52}, st, MockTG())
        check("manager /stats ok", any("ثبت‌های انبار" in x for (_c, x) in sent if isinstance(x, str)))
        # آستانه ۵۰٪: رضا 400k OK، سپس 800k می‌شکند
        sent.clear()
        talkmod.handle({"chat": {"id": 999}, "from": {"first_name": "م"},
                        "text": "/credit رضا 400000", "message_id": 12}, st, MockTG())
        check("credit under half ok", st.credit_balance("رضا") == 400000)
        sent.clear()
        talkmod.handle({"chat": {"id": 999}, "from": {"first_name": "م"},
                        "text": "/credit رضا 800000", "message_id": 13}, st, MockTG())
        check("credit over half blocked", st.credit_balance("رضا") == 400000)

        # تاریخ شمسی/میلادی در /credit و /remind (issue #5 — پچ بازبینی AI-B)
        print("— تاریخ شمسی/میلادی —")
        sent.clear()
        talkmod.handle({"chat": {"id": 999}, "from": {"first_name": "م"},
                        "text": "/credit مریم 300000 1405-07-25", "message_id": 60}, st, MockTG())
        check("jalali ISO credit", st.credit_balance("مریم") == 300000)
        check("jalali ISO label", any("۲۵ مهر ۱۴۰۵" in x for (_c, x) in sent if isinstance(x, str)))
        sent.clear()
        talkmod.handle({"chat": {"id": 999}, "from": {"first_name": "م"},
                        "text": "/credit سارا 200000 25/7", "message_id": 61}, st, MockTG())
        check("jalali slash credit", st.credit_balance("سارا") == 200000)
        check("jalali slash label", any("۲۵ مهر" in x for (_c, x) in sent if isinstance(x, str)))
        sent.clear()
        talkmod.handle({"chat": {"id": 999}, "from": {"first_name": "م"},
                        "text": "/credit حسین 100000 1405-13-40", "message_id": 62}, st, MockTG())
        check("invalid date rejected", any("نمی‌فهمم" in x for (_c, x) in sent if isinstance(x, str)))
        check("invalid credit not stored", st.credit_balance("حسین") == 0)
        sent.clear()
        talkmod.handle({"chat": {"id": 999}, "from": {"first_name": "م"},
                        "text": "/credit نگار 150000 2026-12-01", "message_id": 63}, st, MockTG())
        check("gregorian still ok", st.credit_balance("نگار") == 150000)
        sent.clear()
        talkmod.handle({"chat": {"id": 999}, "from": {"first_name": "م"},
                        "text": "/remind مریم 1405-07-25 نسیه‌ات یادت نره", "message_id": 64}, st, MockTG())
        check("jalali reminder label", any("۲۵ مهر ۱۴۰۵" in x for (_c, x) in sent if isinstance(x, str)))
        future = st.due_reminders(time.time() + 300 * 86400)
        check("jalali reminder stored", any(r["text"] == "نسیه‌ات یادت نره" for r in future))
        sent.clear()
        talkmod.handle({"chat": {"id": 999}, "from": {"first_name": "م"},
                        "text": "/remind مریم 22/7 چک بانکی", "message_id": 65}, st, MockTG())
        check("slash date is not minutes", any("مهر" in x for (_c, x) in sent if isinstance(x, str)))
        future2 = st.due_reminders(time.time() + 300 * 86400)
        check("slash reminder stored", any(r["text"] == "چک بانکی" for r in future2))

        # سررسید و عقب‌افتاده
        now = time.time()
        st.add_credit("رضا", 666, 200000, now + 3600)          # امروز سررسید
        st.add_credit("حسین", 777, 400000, now - 86400)         # دیر شده
        due = st.due_credits(now - 3600, now + 86400)
        check("due credit", any(c["customer"] == "رضا" for c in due))
        check("overdue credit", [c["customer"] for c in st.overdue_credits(now)] == ["حسین"])
        # گزارش صبح
        sent.clear()
        os.environ["TZ_HOURS"] = "0"
        fake_now = now
        real_tdh = talkmod._local_day_hour
        talkmod._local_day_hour = lambda _now=None: (datetime.date.fromtimestamp(fake_now), 9)
        talkmod._maybe_morning_report(st, MockTG())
        talkmod._local_day_hour = real_tdh
        rep = [x for (_c, x) in sent if isinstance(x, str) and "گزارش صبح" in x]
        check("morning sent to manager", any(c == "999" for (c, _x) in sent if "گزارش صبح" in _x))
        check("morning has total", bool(rep) and _fa("73,265,000") in rep[0])
        # بار دوم همان روز تکرار نمی‌شود
        n_before = len(sent)
        talkmod._local_day_hour = lambda _now=None: (datetime.date.fromtimestamp(fake_now), 9)
        talkmod._maybe_morning_report(st, MockTG())
        talkmod._local_day_hour = real_tdh
        check("morning once/day", len(sent) == n_before)

        # retry یادآور: ۳ تلاش ناموفق -> mark + log
        class MockTGF(MockTG):
            def send_message(self, chat_id, text):
                sent.append((chat_id, text))
                return {"ok": False}
            def send_voice(self, cid, blob):
                return {"ok": False}
            def safe_send(self, cid, text, stx=None, kind="s"):
                sent.append((cid, text))
                return False
        st.add_reminder("تست", 111, "رسید", time.time() - 5)
        talkmod.poll_reminders(st, MockTGF())
        check("retry1 still open", len(st.due_reminders()) == 1)
        talkmod.poll_reminders(st, MockTGF())
        talkmod.poll_reminders(st, MockTGF())
        check("retry3 closed", len(st.due_reminders()) == 0)
        # catch-up گزارش صبح (ساعت ۱۰، بوت از ۹ به بعد بالا آمده)
        st3 = storemod.Store(os.path.join(td, "t3.db"))
        sent.clear()
        talkmod._local_day_hour = lambda _now=None: (datetime.date.today(), 10)
        talkmod._maybe_morning_report(st3, MockTG())
        talkmod._local_day_hour = real_tdh
        check("morning catch-up sent", any(c == "999" for (c, _x) in sent if isinstance(_x, str) and "گزارش صبح" in _x))
        # تاریخ شمسی در /remind
        sent.clear()
        talkmod.handle({"chat": {"id": 999}, "from": {"first_name": "م"},
                        "text": "/remind علی 22/7 قبض", "message_id": 60}, st, MockTG())
        durs = st.due_reminders(time.time() + 90 * 86400)
        check("jalali remind stored", any(r["customer"] == "علی" and "قبض" in r["text"] for r in durs))

        # مسیر صوت (ماژول A): STT -> فرمان / رله
        import stt as sttmod
        real_stt = sttmod.transcribe
        class VoiceTG(MockTG):
            def __init__(self):
                self.voices = []
            def send_voice(self, cid, blob):
                self.voices.append(cid)
                return {"ok": True}
        sent.clear()
        sttmod.transcribe = lambda b: "مبلغ: " + _fa("5,000,000")
        vtg = VoiceTG()
        talkmod.handle({"chat": {"id": 999}, "from": {"first_name": "م"},
                        "voice": {"file_id": "V1"}, "message_id": 70}, st, vtg)
        check("voice manager cmd executed", st.last_invoice()["total"] == 5000000)
        sent.clear()
        sttmod.transcribe = lambda b: "سلام، قبض برمی‌دارم"
        vtg2 = VoiceTG()
        talkmod.handle({"chat": {"id": 555}, "from": {"first_name": "علی"},
                        "voice": {"file_id": "V2"}, "message_id": 71}, st, vtg2)
        check("voice customer relayed", any(c == "999" for (c, _x) in sent if isinstance(_x, str)))
        sttmod.transcribe = lambda b: None
        sent.clear()
        vtg3 = VoiceTG()
        talkmod.handle({"chat": {"id": 555}, "from": {"first_name": "علی"},
                        "voice": {"file_id": "V3"}, "message_id": 72}, st, vtg3)
        check("stt-down: customer voice relayed", "999" in vtg3.voices)
        check("stt-down: customer graceful",
              any(isinstance(x, str) and "صاحب مغازه فرستادم" in x for (_c, x) in sent))
        sent.clear()
        vtg4 = VoiceTG()
        talkmod.handle({"chat": {"id": 999}, "from": {"first_name": "م"},
                        "voice": {"file_id": "V4"}, "message_id": 73}, st, vtg4)
        check("stt-down: manager graceful no self-relay",
              len(vtg4.voices) == 0 and any(isinstance(x, str) and "حالت آزمایشی" in x for (_c, x) in sent))
        sttmod.transcribe = real_stt

        # exception داخلی -> crash نمی‌کند
        def boom(*a, **k):
            raise RuntimeError("test-boom")
        real_h = talkmod._handle_inner
        talkmod._handle_inner = boom
        talkmod.handle({"chat": {"id": 111}, "text": "y", "message_id": 7}, st, MockTG())
        talkmod._handle_inner = real_h
        check("no crash on error", any("ایراد گذرا" in t for (_c, t) in sent if isinstance(t, str)))

    # ── حساب‌ها: تریال ۱۰ روزه + باتری + اخطار + یخ + رسید + مالک ──
    print("\u2014 accounts / battery —")
    tdA = tempfile.mkdtemp()
    st = storemod.Store(os.path.join(tdA, "acc.db"))
    CUST = 666
    def cm(*text, photo=False, voice=False):
        m = {"chat": {"id": CUST, "type": "private"},
             "from": {"first_name": "علی"}, "message_id": 900 + len(sent)}
        if photo:
            m["photo"] = [{"file_id": "R1"}]
        if voice:
            m["voice"] = {"file_id": "V1", "duration": 30}
        if text:
            m["text"] = text[0]
        return m
    def mm(text):
        return {"chat": {"id": 999, "type": "private"},
                "from": {"first_name": "م"}, "text": text, "message_id": 1000 + len(sent)}
    sent.clear()
    talkmod.handle(cm("/start"), st, MockTG())
    check("onboard q1 name", any("نامت" in x for (_c, x) in sent if isinstance(x, str)))
    talkmod.handle(cm("علی"), st, MockTG())
    talkmod.handle(cm("سوپرمارکت خونه"), st, MockTG())
    talkmod.handle(cm("خرده‌فروشی"), st, MockTG())
    talkmod.handle(cm("کرج"), st, MockTG())
    talkmod.handle(cm("09123456789"), st, MockTG())
    talkmod.handle(cm("40"), st, MockTG())
    sent.clear()
    talkmod.handle(cm("120"), st, MockTG())
    acc = st.get_account(CUST)
    check("account created", acc is not None and acc["status"] == "trial")
    import pricing as pricingmod
    check("trial units", acc["units_total"] == pricingmod.units_included(pricingmod.TRIAL_PLAN))
    check("trial 10 days", abs((acc["period_end"] - time.time()) / 86400 - 10) < 0.01)
    check("onboard done msg", any("۱۰ روز آزمایش" in x for (_c, x) in sent if isinstance(x, str)))
    check("verification 100%", acc["verification"] == 100)
    check("manager notified", any("مشتریِ جدید" in x for (_c, x) in sent if isinstance(x, str)))

    # شارژ باتری: هر گفتگو = ۱ واحد
    before = acc["units_left"]
    sent.clear()
    talkmod.handle(cm("سلام"), st, MockTG())
    check("battery charged 1 unit", st.get_account(CUST)["units_left"] == before - 1.0)
    check("customer relayed to mgr", any("مشتری (علی)" in x for (_c, x) in sent if isinstance(x, str)))

    # هشدار کم‌باتری در عبور از آستانه
    st.upsert_account(CUST, units_total=100.0, units_left=21.0)
    sent.clear()
    talkmod.handle(cm("سلام"), st, MockTG())
    check("battery low warn at 20%", any("باتری: ۲۰٪" in x for (_c, x) in sent if isinstance(x, str)))

    # باتری خالی
    st.upsert_account(CUST, units_left=0.0)
    sent.clear()
    talkmod.handle(cm("سلام"), st, MockTG())
    check("battery empty blocks", any("باتری خالی" in x for (_c, x) in sent if isinstance(x, str)))

    # اخطار عقب‌افتادگی (روز ۲) -> وضعیت overdue + پیام قرمز
    st.upsert_account(CUST, period_end=int(time.time()) - 2 * 86400, status="trial")
    sent.clear()
    talkmod._scan_accounts(st, MockTG())
    acc = st.get_account(CUST)
    check("overdue status", acc["status"] == "overdue")
    check("overdue red warn", any("اطلاعاتِ شما حذف خواهد شد" in x for (_c, x) in sent if isinstance(x, str)))

    # روز هشتم -> یخ + خبر مالک
    st.upsert_account(CUST, period_end=int(time.time()) - 8 * 86400, last_warn=0)
    sent.clear()
    talkmod._scan_accounts(st, MockTG())
    acc = st.get_account(CUST)
    check("frozen after 8 days", acc["status"] == "frozen")
    check("frozen notice", any("یخ‌زده" in x for (_c, x) in sent if isinstance(x, str)))
    check("frozen mgr told", any("یخ‌زد" in x for (_c, x) in sent if isinstance(x, str)))

    # رسید: مشتریِ یخ‌زده عکس می‌فرستد -> مالک
    sent.clear()
    talkmod.handle(cm(photo=True), st, MockTG())
    acc = st.get_account(CUST)
    check("receipt pending", acc["receipt_pending"] == 1)
    check("receipt to manager", any(isinstance(x, str) and x.startswith("PHOTO:🧾") for (_c, x) in sent))

    # مالک: /charge -> فعال + شارژ
    sent.clear()
    talkmod.handle(mm("/charge علی"), st, MockTG())
    acc = st.get_account(CUST)
    check("charge reactivates", acc["status"] == "active" and acc["units_left"] == pricingmod.units_included(pricingmod.TRIAL_PLAN))
    check("charge period +30d", abs((acc["period_end"] - time.time()) / 86400 - 30) < 0.05)

    # مالک: /manage + /note + /plan + /battery
    sent.clear()
    talkmod.handle(mm("/manage"), st, MockTG())
    check("manage list", any("📇" in x for (_c, x) in sent if isinstance(x, str)))
    talkmod.handle(mm("/note علی مشتری خوب است"), st, MockTG())
    check("note saved", (st.get_account(CUST).get("notes") or "") == "مشتری خوب است")
    talkmod.handle(mm("/plan علی حرفه‌ای"), st, MockTG())
    check("plan changed", st.get_account(CUST)["plan"] == "harsheh")

    # ضدِ حسابِ کاسب: شارژِ اضافه هرگز ارزانی‌تر از نسخه‌ی بالاتر نیست
    check("anti-arbitrage", pricingmod.anti_arbitrage())

    # دروازه‌ی امکانات: حرفه‌ای -> OCR می‌رود (اینجا بدون بک‌اند: fallback)
    sent.clear()
    talkmod.handle(cm(photo=True), st, MockTG())
    check("pro photo -> ocr path", any("مبلغ را بفرست" in x or "جمع کل" in x for (_c, x) in sent if isinstance(x, str)))
    # پایه -> upsell
    talkmod.handle(mm("/plan علی پایه"), st, MockTG())
    sent.clear()
    talkmod.handle(cm(photo=True), st, MockTG())
    check("base photo upsell", any("نسخه‌ی حرفه‌ای/عمده‌فروش" in x for (_c, x) in sent if isinstance(x, str)))
    sent.clear()
    talkmod.handle(cm(voice=True), st, MockTG())
    check("base voice upsell", any("نسخه‌ی حرفه‌ای/عمده‌فروش" in x for (_c, x) in sent if isinstance(x, str)))
    sent.clear()
    talkmod.handle(cm("/credit تست 100000 2026-12-01"), st, MockTG())
    check("base credit upsell", any("نسخه‌ی حرفه‌ای/عمده‌فروش" in x for (_c, x) in sent if isinstance(x, str)))
    # «ارتقا» -> مالک
    sent.clear()
    talkmod.handle(cm("ارتقا"), st, MockTG())
    check("upgrade relayed", any("درخواست **ارتقا**" in x for (_c, x) in sent if isinstance(x, str)))
    # گزارش صبحِ حسابِ حرفه‌ای
    talkmod.handle(mm("/plan علی حرفه‌ای"), st, MockTG())
    talkmod._local_day_hour = lambda _now=None: (datetime.date.today(), 9)
    sent.clear()
    talkmod._scan_accounts(st, MockTG())
    talkmod._local_day_hour = real_tdh
    check("account morning sent", any("گزارش صبحِ" in x and "باتری" in x for (_c, x) in sent if isinstance(x, str)))
    sent.clear()
    talkmod._scan_accounts(st, MockTG())
    check("account morning once/day", sum(1 for _c, x in sent if isinstance(x, str) and "گزارش صبحِ" in x) == 0)
    sent.clear()
    talkmod.handle(cm("/battery"), st, MockTG())
    check("customer battery info", any("باتری" in x for (_c, x) in sent if isinstance(x, str)))

    # حق‌البازگشت: ۱۰ روز عقب -> ۴ روز × ۳٬۰۰ = ۱٬۰۰
    st.upsert_account(CUST, period_end=int(time.time()) - 10 * 86400, status="active")
    fee = pricingmod.recovery_fee(st.get_account(CUST), int(time.time()))
    check("recovery fee 4 days", fee == 12000)
    sent.clear()
    talkmod.handle(mm("/recover علی"), st, MockTG())
    check("recover asks confirm", any("۱۲٬۰۰۰" in x for (_c, x) in sent if isinstance(x, str)))
    sent.clear()
    talkmod.handle(mm("/recover علی yes"), st, MockTG())
    check("recover reactivates", st.get_account(CUST)["status"] == "active")
    check("recover fee msg", any("بازگردانی" in x for (_c, x) in sent if isinstance(x, str)))

    # ممنوعیت: مشتری نمی‌تواند /manage بزند
    sent.clear()
    talkmod.handle(cm("/manage"), st, MockTG())
    check("customer forbidden manage", any("مخصوص صاحب مغازه" in x for (_c, x) in sent if isinstance(x, str)))

    talkmod._local_day_hour = real_tdh0
    print("\nSELFTEST OK: %d/%d" % (ok, ok))
    return 0


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--selftest":
        return selftest()

    token = os.environ.get("BOT_TOKEN")
    if not token:
        print("BOT_TOKEN لازم است (از @BotFather بگیرید). README.md را ببینید.")
        return 1

    import tg as tgmod
    b = tgmod.TGBot(token)
    me = b.get_me()
    if not me.get("ok"):
        print("خطا در اتصال به Telegram:", me.get("description"))
        return 1
    db = os.environ.get("SAYA_DB",
                        os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "saya.db"))
    st = storemod.Store(db)
    st.log("boot", "bot online @" + str(me.get("result", {}).get("username")))
    print("🌙 سایا-جادو آنلاین: @%s" % me["result"].get("username"))
    print("   OCR:", (os.environ.get("OCR_CLOUD_URL") and "cloud")
          or (os.path.exists("/usr/bin/tesseract") and "tesseract") or "none (manual fallback)")

    stop = {"run": True}

    def _sig(_s, _f):
        stop["run"] = False

    signal.signal(signal.SIGTERM, _sig)
    signal.signal(signal.SIGINT, _sig)

    def reminder_loop():
        while stop["run"]:
            try:
                talk.poll_reminders(st, b)
            except Exception as e:
                st.log("reminder-loop", repr(e)[:200])
            time.sleep(30)

    threading.Thread(target=reminder_loop, daemon=True).start()

    offset = None
    last_err_log = 0.0
    last_prune = 0.0
    while stop["run"]:
        if time.time() - last_prune > 3600:
            st.prune_log(30)
            last_prune = time.time()
        r = b.get_updates(offset=offset, timeout=30)
        if not r.get("ok"):
            # 429 را خودِ _call با retry_after رعایت می‌کند؛ اینجا فقط: لاگ خفیف + مکث امن (issue #7)
            if time.time() - last_err_log > 300:
                st.log("get-updates", r.get("description", "")[:200])
                last_err_log = time.time()
            time.sleep(3)
            continue
        for up in r.get("result", []):
            offset = up["update_id"] + 1
            msg = up.get("message")
            if msg:
                talk.handle(msg, st, b)
    print("خاموش شدم. 🌙")
    return 0


if __name__ == "__main__":
    sys.exit(main())
