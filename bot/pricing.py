#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""سایا-جادو — قیمت‌بندی v3.0 (اعداد مالک، ۲۶ شهریور ۱۴)

دستور مالک:
  • پایه: ۲٬۱۰۰٬۰۰۰ + ارزش‌افزوده — ۳۰ مشتری / ۵۰ قلم / ۶۰ مکالمه
  • حرفه‌ای/عمده‌فروش: ۵٬۳۰۰٬۰۰۰/ماه — ۷۵ قلم / ۲۵۰ تماس
  • حرفه‌ای/تولیدکننده: ۱۵٬۰۰۰٬۰۰۰/ماه — ۱۰۰ مشتری / ۱۵۰ تماس
  • سرور حداقلی: ۳٬۰۰۰٬۰۰۰ تومان (۴ هسته + ۱۰۰ گیگ) + تورم ۵٪ ماهانه
  • قیمتِ شارژِ اضافه **گران** باشد: حسابگر نباید «پایه + شارژ» را ارزانی‌تر از
    نسخه‌ی بالاتر ببیند (با assertِ anti_arbitrage قفل شده).
  • هر نسخه **امکانات** متفاوت دارد؛ دمو/تریال = **فول امکانات** تا مشتری
    بفهمد با پایه چه چیزهایی را از دست می‌دهد.
"""
import math

TRIAL_DAYS = 10          # تبلیغ: ۱۰ روز رایگان
TRIAL_FEATURES_ALL = True  # دمو/تریال فول امکانات (تحرّک برای خرید)
PERIOD_DAYS = 30
VAT = 0.10               # ارزش‌افزوده: عبوری است (درآمد ما نیست؛ روی قیمت می‌نشیند)

# ── بسته‌ها (ماهانه، تومان — بدون VAT) ─────────────────
# customers/items/chats = شمول. features = تفاوت نسخه‌ها.
PACKAGES = {
    "payeh": dict(
        label="پایه", price=2_100_000,
        customers=30, items=50, chats=60,
        features=("text", "manual-invoice", "remind", "catalog")),
    "harsheh": dict(
        label="حرفه‌ای/عمده‌فروش", price=5_300_000,
        customers=75, items=75, chats=250,
        features=("text", "manual-invoice", "remind", "catalog",
                  "ocr-invoice", "credit", "voice", "morning")),
    "tolid": dict(
        label="حرفه‌ای/تولیدکننده", price=15_000_000,
        customers=100, items=300, chats=150,   # ۱۵۰ تماس دقیقاً به‌قول مالک
        features=("text", "manual-invoice", "remind", "catalog",
                  "ocr-invoice", "credit", "voice", "morning", "quote")),
}
TRIAL_PLAN = "payeh"     # اعتبار تریال = شمولِ پایه (ولی امکاناتش = همه)

# ── نرخ‌های شارژِ اضافه (تومان) — عمداً گران: ضدِ «حسابِ کاسب» ─
# قیمت ضمنیِ مکالمه در پایه = ۲٬۱۰۰٬۰۰۰/۶۰ = ۳۵٬۰۰۰ ← شارژ بالاتر از آن.
UPSELL = {
    "chat": 40_000,        # هر مکالمه/تماسِ فراتر (قیمت ضمنی پایه ۳۵k → ۴۰k)
    "invoice": 20_000,     # هر فاکتورِ فراتر (= ۰.۵ مکالمه)
    "per_10_customers": 1_000_000,   # هر ۱۰ مشتری (۱۰۰k/تک ← ضمنی ۷۰k)
    "per_50_items": 4_000_000,       # هر ۵۰ قلم (۸۰k/تک ← ضمنی ۴۲-۷۱k)
}

# واحد باتری: ۱ واحد = ۱ مکالمه/تماس (شارژش ۴۰k تومان)
UNITS = dict(chat=1.0, invoice=0.5)

# ── باتری و عقب‌ماندگی ─────────────────────────────────
LOW_BATTERY_PCT = 20
WARN_GRACE_DAYS = 7
RECOVERY_PER_DAY = 3_000

STATUS_TRIAL = "trial"
STATUS_ACTIVE = "active"
STATUS_OVERDUE = "overdue"
STATUS_FROZEN = "frozen"

# ── زیرساخت (مالک: سرور حداقلی ۳ میلیون، ۴ هسته + ۱۰۰ گیگ) ──
VPS_MONTHLY = 3_000_000     # واقعی مالک
GATEWAY_MISC = 500_000      # درگاه/دامنه/متفرقه (ASSUMPTION)
INFLATION_M = 0.05          # تورم: ۵٪ ماهانه روی قیمت و هزینه


def inflate(value, month):
    """ارزش در ماهِ month با تورم ۵٪ ماهانه (ماه ۱ = قیمت پایه)."""
    return value * ((1 + INFLATION_M) ** max(0, month - 1))


def units_included(plan):
    return float(PACKAGES[plan]["chats"])


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
    return max(0, days_overdue(acct, now) - WARN_GRACE_DAYS + 1)


def recovery_fee(acct, now):
    return recovery_days(acct, now) * RECOVERY_PER_DAY


def plan_features(plan):
    if plan is None or plan == STATUS_TRIAL or plan == "trial":
        return set(PACKAGES["tolid"]["features"])   # تریال/دمو: همه
    return set(PACKAGES.get(plan, PACKAGES["payeh"])["features"])


def allows(acct, feature):
    """تریال/دمو = همه‌چیز؛ بعد از آن فقط امکاناتِ نسخه‌ی خودش."""
    if acct.get("status") == STATUS_TRIAL and TRIAL_FEATURES_ALL:
        return True
    return feature in plan_features(acct.get("plan"))


def upsell_cost_to_reach(from_plan, to_plan):
    """هزینه‌ی «بسط دادنِ from تا شمولِ to با نرخِ شارژ» — برای ضد-حساب."""
    a, b = PACKAGES[from_plan], PACKAGES[to_plan]
    c = math.ceil(max(0, b["customers"] - a["customers"]) / 10.0)
    i = math.ceil(max(0, b["items"] - a["items"]) / 50.0)
    ch = max(0, b["chats"] - a["chats"])
    return (c * UPSELL["per_10_customers"]
            + i * UPSELL["per_50_items"]
            + ch * UPSELL["chat"])


def anti_arbitrage():
    """assert: هیچ‌وقت «نسخه‌ی پایین + شارژ» ارزانی‌تر از نسخه‌ی بالاتر نمی‌شود."""
    order = ["payeh", "harsheh", "tolid"]
    ok = True
    for lo, hi in zip(order, order[1:]):
        cost = upsell_cost_to_reach(lo, hi)
        ok = ok and cost > PACKAGES[hi]["price"] - PACKAGES[lo]["price"]
    return ok


# ── حاشیه (بررسی در selftest) ──────────────────────────
COST_CHAT_FULL = 190.8    # LLM mini خام تومان/گفتگو
COST_INVOICE = 50.0
COST_SMS = 120.0


def plan_margin_pct(plan, full_llm=True):
    p = PACKAGES[plan]
    chats = p["chats"]
    cost = (chats * (COST_CHAT_FULL if full_llm else COST_CHAT_FULL * 0.2)
            + 30 * COST_INVOICE + 60 * COST_SMS)
    return round((p["price"] - cost) / p["price"] * 100, 1)


if __name__ == "__main__":
    print("بسته‌ها (ماهانه، بدون VAT %d٪):" % int(VAT * 100))
    for k, p in PACKAGES.items():
        print("  %-22s %14s تومان | مشتری %3d | قلم %4d | مکالمه/تماس %4d | حاشیه(بدترین) %s%%"
              % (p["label"], format(p["price"], ","), p["customers"], p["items"],
                 p["chats"], plan_margin_pct(k)))
    print("شارژِ اضافه: مکالمه %s | فاکتور %s | هر ۱۰ مشتری %s | هر ۵۰ قلم %s"
          % (format(UPSELL["chat"], ","), format(UPSELL["invoice"], ","),
             format(UPSELL["per_10_customers"], ","), format(UPSELL["per_50_items"], ",")))
    print("ضدِ حسابِ کاسب (شارژ تا نسخه‌ی بالاتر > اختلاف قیمت):",
          "سبز ✓" if anti_arbitrage() else "سرخ ✗")
    print("سرور: %s/ماه (۴ هسته+۱۰۰G) + تورم ۵٪/ماه" % format(VPS_MONTHLY, ","))
