#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""سایا-جادو — قیمت‌بندی و اعتبار (باتری)

قاعده‌ی مالک (۱۶ سپتامبر ۱۴۵):
  ۱) تبلیغ: ۱۰ روز استفاده‌ی رایگان — اول جمع‌آوری اطلاعات + بررسی صحت.
  ۲) نرخ‌ها در چند بسته؛ شامل تعداد مشتری، اقلام و تماس/گفتگو.
  ۳) نرخ اضافه‌ها: هر ۵۰ کالا، هر ۱۰ مشتری، هر ساعت تماس/جواب‌گویی.
  ۴) حاشیه‌ی سود: حداقل ۳۰٪ روی هزینه‌های واقعی (سرور و غیره).
  ۵) باتری نمادی مثل موبایل: مالک بفهمد چقدر اعتبار مانده.
  ۶) پس از موعد: تا ۱ هفته باتری چشمک‌زن + اخطار قرمز؛ بعد یخ‌زدگی.
  ۷) داده در سرور می‌ماند؛ ریکاوری = حق‌البازگشت به ازای هر روز گذشته.
  ۸) مدیریت مالی و رفتاری: خودِ مالک (دستورات /manage ...).

واحد باتری: «واحد خدمت» — ۱ واحد ≈ ۱٬۰۰۰ تومان خدمت.
  گفتگوی متنی با مشتری = ۱ واحد
  فاکتور (عکس/ثبت)      = ۰.۵ واحد
  هر دقیقه صدا          = ۰.۱۵ واحد
"""
import math

TRIAL_DAYS = 10          # تبلیغ: ۱۰ روز رایگان (دستور مالک)
TRIAL_PLAN = "shorou"    # اعتبار تریال = شاملاتِ بسته‌ی «شروع»
PERIOD_DAYS = 30         # دوره‌ی پرداخت (ماه) — هم‌خوانی «۳۳ هزار در روز»×۳۰

# ── نرخ‌های واحد (تومان) — تأیید مالک ─────────────────
UNIT_PRICE = {
    "chat":   1_000,   # هر گفتگو (تأیید مالک ۲۵ شهریور)
    "invoice": 500,    # هر فاکتور (سایت، پلن دفتر)
    "voice_min": 150,  # هر دقیقه تماس/صدا (≈ ۹٬۰۰۰ / ساعت)
}
VOICE_HOUR_PRICE = 9_000   # تومان/ساعت تماس و جواب‌گویی (حاشیه ۳۶٪ حتی در بدترین فرض)
EXTRA_PER_10_CUSTOMERS = 75_000   # ماهانه، هر ۱۰ مشتریِ فراتر
EXTRA_PER_50_ITEMS = 50_000       # ماهانه، هر ۵۰ قلمِ فراتر
EXTRA_PER_100_CHATS = 100_000     # = ۱۰۰ × ۱٬۰۰ (هم‌نرخ باتری)
EXTRA_PER_30_INVOICES = 15_000    # = ۳۰ × ۰۰ (هم‌نرخ باتری)

# ── بسته‌ها (ماهانه، تومان) ─────────────────────────────
# شمول‌ها: customers=مشتری، items=قلم، chats=گفتگو، invoices=فاکتور، voice_min=دقیقه تماس
PACKAGES = {
    "shorou":  dict(label="شروع",  price=330_000,
                    customers=10,  items=50,   chats=300,  invoices=30,  voice_min=60),
    "maghaze": dict(label="مغازه", price=990_000,
                    customers=30,  items=200,  chats=1800, invoices=100, voice_min=120),
    "bazaar":  dict(label="بازار",  price=1_900_000,
                    customers=100, items=1000, chats=4800, invoices=250, voice_min=300),
}

# ── باتری و عقب‌ماندگی ─────────────────────────────────
LOW_BATTERY_PCT = 20       # کمتر از ۲۰٪: هشدار
WARN_GRACE_DAYS = 7        # پس از موعد: ۷ روز اخطار قرمز (چشمک‌زن)
RECOVERY_PER_DAY = 3_000   # تومان/روز حق‌البازگشت، از روز هشتمِ عقب‌ماندگی

STATUS_TRIAL = "trial"
STATUS_ACTIVE = "active"
STATUS_OVERDUE = "overdue"
STATUS_FROZEN = "frozen"


def units_included(plan):
    """کل واحدهای داخلِ یک بسته (گفتگو + فاکتور + صدا همه به واحد)."""
    p = PACKAGES[plan]
    return (p["chats"] * UNIT_PRICE["chat"] / 1000.0
            + p["invoices"] * UNIT_PRICE["invoice"] / 1000.0
            + p["voice_min"] * UNIT_PRICE["voice_min"] / 1000.0)


def battery_pct(acct):
    t = acct.get("units_total") or 0
    if t <= 0:
        return 0
    return max(0, int(round((acct.get("units_left") or 0) / t * 100)))


def days_overdue(acct, now):
    pe = acct.get("period_end") or 0
    if not pe or now <= pe:
        return 0
    return int((now - pe) // 86400)


def recovery_days(acct, now):
    """روزهای حق‌البازگشت: از روز هشتمِ عقب‌ماندگی شروع می‌شود."""
    return max(0, days_overdue(acct, now) - WARN_GRACE_DAYS + 1)


def recovery_fee(acct, now):
    return recovery_days(acct, now) * RECOVERY_PER_DAY


def extra_charges(acct):
    """بهره‌ی ماهانه‌ی اضافه‌ها فراتر از شمولِ بسته (تومان)."""
    p = PACKAGES.get(acct.get("plan") or "shorou")
    nc = max(0, (acct.get("n_customers") or 0) - p["customers"])
    ni = max(0, (acct.get("n_items") or 0) - p["items"])
    return (math.ceil(nc / 10.0) * EXTRA_PER_10_CUSTOMERS
            + math.ceil(ni / 50.0) * EXTRA_PER_50_ITEMS)


# ── حاشیه‌ی سود (بررسی ۳۰٪) ─────────────────────────────
# هزینه‌ی هر گفتگو: LLM mini خام ≈ ۱۹۰.۸ تومان (۲۲۸k×۱.۸)؛ هیبرید (۲۰٪ LLM) ≈ ۳۸.۲.
COST_CHAT_FULL = 190.8
COST_INVOICE = 50.0
COST_SMS = 120.0


def plan_margin_pct(plan, full_llm=True):
    """حاشیه‌ی سود ماهانه‌ی بسته (بدترین فرض مصرف: سقف شمول + LLM کامل)."""
    p = PACKAGES[plan]
    cost = (p["chats"] * (COST_CHAT_FULL if full_llm else COST_CHAT_FULL * 0.2)
            + p["invoices"] * COST_INVOICE
            + 60 * COST_SMS)
    return round((p["price"] - cost) / p["price"] * 100, 1)


if __name__ == "__main__":
    print("بسته‌ها (ماهانه):")
    for k, p in PACKAGES.items():
        print("  %-8s %12s تومان | مشتری %4d | قلم %5d | گفتگو %5d | فاکتور %3d | صدا %3d دقیقه | واحدها %.0f | حاشیه (بدترین) %s%%"
              % (p["label"], format(p["price"], ","), p["customers"], p["items"],
                 p["chats"], p["invoices"], p["voice_min"], units_included(k),
                 plan_margin_pct(k)))
    print("اضافه‌ها: هر ۱۰ مشتری %s | هر ۵۰ قلم %s | هر ۱۰۰ گفتگو %s | هر ۳۰ فاکتور %s | هر ساعت تماس %s"
          % (format(EXTRA_PER_10_CUSTOMERS, ","), format(EXTRA_PER_50_ITEMS, ","),
             format(EXTRA_PER_100_CHATS, ","), format(EXTRA_PER_30_INVOICES, ","),
             format(VOICE_HOUR_PRICE, ",")))
    print("تریال: %d روز | اخطار: %d روز | ریکاوری: %s تومان/روز"
          % (TRIAL_DAYS, WARN_GRACE_DAYS, format(RECOVERY_PER_DAY, ",")))
