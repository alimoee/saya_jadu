# -*- coding: utf-8 -*-
"""اقتصاد واحد سایا — مدل محاسباتی مرجع (v2، خودِ repo).

هر عدد خروجی اینفوگرافیک باید از این ماژول قابل بازتولید باشد.
فرض‌ها صریح‌اند؛ هر چیزی که از سایتِ منتشرشده گرفته نشده، ASSUMPTION است.

اجرا/تست:  python3 unit_econ.py            (خروجی کامل)
           python3 unit_econ.py --selftest (assertionها)

منبع نرخ ارز: بازار تهران ۱۴۰۵/۰۶/۱۵ — ۲۲۷٬۸۰۰ تومان/دلار (خبرآنلاین).
"""
import datetime

# ── ثابت‌های بازار ────────────────────────────────────
FX = 228_000            # تومان/دلار (بازار تهران، ۱۴۰/۰۶/۵)
LLM_MARKUP = 1.8        # واسط ایرانی روی تعرفه‌ی جهانی
SMS_COST = 120          # تومان/پیامک (ملی‌پیامک — برآورد)

# تعرفه‌های LLM بر ۱M توکن (دولار: ورودی/خروجی) — فهرست جهانی
LLM = {
    "mini": (0.15, 0.60),    # کلاس GPT-4o-mini
    "mid":  (2.50, 10.0),    # کلاس GPT-4o / Sonnet
    "top":  (5.00, 25.0),    # کلاس GPT-5 / Opus (فقط حساسیت)
}
TOKENS_PER_CHAT = (1500, 400)   # ASSUMPTION: گفتگوی کوتاه مغازه‌ای

# صوت در استک واقعی سایا: edge-tts (رایگان) + Vosk (رایگان)
COST_TTS_PER_CHAR_PAID = 15.0 / 1e6   # فقط سناریوی حساسیت (دولار/کاراکتر)
COST_STT_PER_MIN_PAID  = 0.006        # فقط سناریوی حساسیت (دولار/دقیقه)
CHARS_PER_VOICE_CHAT = 300            # ASSUMPTION: پاسخ صوتی ~۳۰ کاراکتر
MIN_PER_VOICE_CHAT = 0.3              # ASSUMPTION: ~۱۸ ثانیه ورودی صوت

VOICE_SHARE = 0.4       # ASSUMPTION: ۴۰٪ گفتگوها صوتی (همان فرض سند v1)

# ── پلن‌های سایتِ منتشرشده (هر فصل = ۹۰ روز) ────────
# قیمت از سایت زنده (فصلی). «chats» = مصرف مفروض ماهانه (ASSUMPTION برای
# مغازه/مغازه+؛ دفتر از سایت: ۲۰۰ مکالمه/ماه + فراتر ۲۰۰ فاکتور ۵۰ تومان).
PLANS = {
    "maghaze":      dict(label="مغازه",   price=990_000,   chats=1800, sms=30,  extra_invoice_t=0),
    "maghaze_plus": dict(label="مغازه+",  price=1_900_000, chats=4800, sms=60,  extra_invoice_t=0),
    "daftar":       dict(label="دفتر",    price=3_900_000, chats=200,  sms=100, extra_invoice_t=100 * 500),
}
EXTRA_INVOICE_PRICE = 500     # تومان/فاکتور (دفتر، فراتر از ۲۰۰) — از سایت
# ── تناقض دوره‌ی صورتحساب (یافته‌ی کلیدی v2) ──────────
# سایت هم «۹۹۰ هزار به‌ازای هر فصل» و هم «یعنی ۳۳ هزار در روز» نوشته.
# ۳۳k × ۹۰ روز = ۲.۹۷M ≠ ۹۹k  →  پس «۳۳ هزار در روز» فقط با دوره‌ی ۳۰ روزه درست است.
# دو تفسیر ممکن:
CYCLES = {
    "quarter": dict(days=90, note="«فصل» واقعی (۹۰ روز)"),
    "month":   dict(days=30, note="«۳۳ هزار در روز» → دوره‌ی ۳۰ روزه"),
}
SEASONS_PER_MONTH = 1.0 / 3.0  # فقط برای تفسیر quarter

# ترکیب مصرف‌کننده (ASSUMPTION)
MIX = {"maghaze": 0.60, "maghaze_plus": 0.30, "daftar": 0.10}

# هزینه ثابت تیم مینیمال (ASSUMPTION — عدد سند v1؛ ورودی مالک)
FIXED_MINIMAL = 950_000_000    # تومان/ماه
FIXED_WITH_GROWTH = 1_800_000_000

# ── قیف (اعداد سند v1 — ASSUMPTION، بدون منبع رسمی) ──
FUNNEL = [
    ("بازار کل اصناف خرد", 3_200_000, 0.10),
    ("دیجیتال‌پذیر + گوشی", None, 0.05),
    ("لید کیفی", None, 0.15),
    ("تریال فعال ۱۴ روزه", None, 0.35),
    ("مشتری پرداخت‌کننده", None, 0.60),
]


# ── توابع ─────────────────────────────────────────────
def llm_cost_per_chat(model="mini", fx=FX, markup=LLM_MARKUP):
    """هزینه‌ی LLM یک گفتگو، تومان (بدون صوت)."""
    cin, cout = LLM[model]
    tin, tout = TOKENS_PER_CHAT
    return (tin * cin + tout * cout) / 1e6 * fx * markup


def voice_cost_per_chat(paid, fx=FX):
    """هزینه‌ی صوت یک گفتگوی صوتی، تومان. استک واقعی = ۰ (edge-tts/Vosk رایگان)."""
    if not paid:
        return 0.0
    return (COST_TTS_PER_CHAR_PAID * CHARS_PER_VOICE_CHAT +
            COST_STT_PER_MIN_PAID * MIN_PER_VOICE_CHAT) * fx


def plan_monthly_cost(plan, model="mini", paid_voice=False, fx=FX):
    """هزینه‌ی ماهانه‌ی سرویس‌کردن یک مغازه‌ی پلنِ plan، تومان."""
    p = PLANS[plan]
    llm = 0.0 if model == "rule" else llm_cost_per_chat(model, fx)
    voice = voice_cost_per_chat(paid_voice, fx) * VOICE_SHARE
    return p["chats"] * (llm + voice) + p["sms"] * SMS_COST


def plan_quarter_margin(plan, model="mini", paid_voice=False, fx=FX):
    """حاشیه‌ی سه‌ماهه = درآمد فصلی − ۳ ماه هزینه. (تومان)"""
    p = PLANS[plan]
    return p["price"] - 3 * plan_monthly_cost(plan, model, paid_voice, fx)


def plan_quarter_margin_pct(plan, model="mini", paid_voice=False, fx=FX):
    p = PLANS[plan]
    return 100.0 * plan_quarter_margin(plan, model, paid_voice, fx) / p["price"]


def arpu_monthly(model="mini", paid_voice=False, fx=FX, mix=None, cycle="quarter"):
    """درآمد-مؤثر ماهانه میانگین (ترکیب پلن‌ها)، تومان. cycle: 'quarter' یا 'month'."""
    mix = mix or MIX
    days = CYCLES[cycle]["days"]
    arpu = 0.0
    for k, w in mix.items():
        arpu += w * (PLANS[k]["price"] * 30.0 / days +
                     PLANS[k]["extra_invoice_t"] * 30.0 / days)
    return arpu


def contribution_monthly(model="mini", paid_voice=False, fx=FX, mix=None, cycle="quarter"):
    """سهم مشارکت ماهانه میانگین = ARPU − هزینه‌ی ماهانه میانگین."""
    mix = mix or MIX
    cost = sum(w * plan_monthly_cost(k, model, paid_voice, fx) for k, w in mix.items())
    return arpu_monthly(fx=fx, mix=mix, cycle=cycle) - cost


def breakeven_shops(fixed=FIXED_MINIMAL, model="mini", paid_voice=False, fx=FX, cycle="quarter"):
    """تعداد مغازه‌ی پایدار برای پوشش هزینه‌ی ثابت."""
    c = contribution_monthly(model, paid_voice, fx, cycle=cycle)
    if c <= 0:
        return None  # هرگز (با این پیکربندی)
    return -(-fixed // c)  # ceil


def funnel_stages():
    """مرحله‌به‌مرحله‌ی قیف: (نام، حجم)."""
    out, n = [], FUNNEL[0][1]
    out.append((FUNNEL[0][0], n))
    for name, _x, rate in FUNNEL[1:]:
        n = int(n * rate)
        out.append((name, n))
    return out


def _retention(age, churn2, churn_later):
    """survival یک cohort در ماهِ age (age=1 یعنی ماه اول)."""
    if age <= 1:
        return 1.0
    return (1 - churn2) * (1 - churn_later) ** (age - 2)


def cashflow(months=18, shops_per_month=120, arpu=750_000,
             fixed=FIXED_MINIMAL, churn2=0.40, churn_later=0.10, no_churn=False):
    """رشد خطی با چرخش: ماه دوم cohort ۴۰٪ می‌ریزد، بعدش ۱۰٪ ماهانه.
    no_churn=True -> همان مدل ساده‌ی سند v1 (بدون چرخش — خوش‌بین‌ترین).
    خروجی: (جریان خالص ماهانه، ماه سربه‌سر یا None، عمیق‌ترین سوخت)."""
    net, cumulative, burn, be = [], 0.0, 0.0, None
    for m in range(1, months + 1):
        shops = 0.0
        for k in range(0, m):
            age = m - k
            shops += shops_per_month * (1.0 if no_churn else _retention(age, churn2, churn_later))
        net_m = shops * arpu - fixed
        net.append(net_m)
        cumulative += net_m
        burn = min(burn, cumulative)
        if be is None and net_m > 0:
            be = m
    return net, be, burn


# ── خروجی / تست ───────────────────────────────────────
def report():
    today = datetime.date(2026, 9, 15)
    print("اقتصاد واحد سایا — مدل v2 (repo) — %s" % today)
    print("FX=%s ت/دلار | markup LLM ×%.1f | صوت: رایگان (edge-tts+Vosk)\n" % (format(FX, ","), LLM_MARKUP))
    print("— تناقض دوره‌ی صورتحساب (یافته‌ی کلیدی) —")
    print("  سایت: «۹۹۰ هر فصل» و «۳۳ هزار در روز» — ۳۳k×۹۰روز=۲.۹۷M ≠ ۹۹k")
    for c in ("quarter", "month"):
        print("  تفسیر %-8s → ARPU ماهانه %s ت" % (c, format(int(arpu_monthly(cycle=c)), ",")))
    print("\n— اقتصاد واحد (حاشیه‌ی هر پلن، دوره‌ی quarter=۹۰روز) —")
    hdr = "%-10s %14s" % ("پلن", "قیمت/فصل")
    for m in ("rule", "mini", "mid"):
        hdr += " %14s" % ("LLM " + m)
    print(hdr)
    for k in ("maghaze", "maghaze_plus", "daftar"):
        p = PLANS[k]
        row = "%-10s %14s" % (p["label"], format(p["price"], ","))
        for m in ("rule", "mini", "mid"):
            mg = plan_quarter_margin(k, m)
            row += " %13s%%" % format(int(100 * mg / p["price"]), ",").rjust(13)
        print(row)
    print("\n— هزینه‌ی LLM بر هر گفتگو (تومان) —")
    for m in ("mini", "mid", "top"):
        print("  %-5s %s" % (m, format(int(llm_cost_per_chat(m)), ",")))
    print("\n— سربه‌سر (تیم مینیمال %s ت/ماه) —" % format(FIXED_MINIMAL, ","))
    for m in ("rule", "mini"):
        b = breakeven_shops(model=m)
        print("  مدل %-4s → %s مغازه‌ی پایدار" % (m, format(b, ",") if b else "هرگز"))
    print("\n— قیف (فرض‌های v1) —")
    for name, n in funnel_stages():
        print("  %-28s %s" % (name, format(n, ",")))
    a_q = arpu_monthly(cycle="quarter")
    a_m = arpu_monthly(cycle="month")
    print("\n— جریان نقدی ۱۸ ماهه (ثابت %s ت/ماه، چرخش ۴۰٪/ماه‌۲ بعدش ۱۰٪) —" % format(FIXED_MINIMAL, ","))
    for bill, arpu in (("quarter ۹۰روز", a_q), ("month ۳۰روز", a_m)):
        print("  ARPU %s: %s ت/ماه" % (bill, format(int(arpu), ",")))
        for label, slope in (("bear", 40), ("base", 120), ("bull", 250)):
            net, be, burn = cashflow(shops_per_month=slope, arpu=arpu)
            print("    %-5s +%-4d/ماه → سربه‌سر: %s | سوخت: %s ت" % (
                label, slope, ("ماه %d" % be) if be else "هرگز در ۱۸ ماه", format(int(-burn), ",")))
    print("  (بدون چرخش — مدل v1) base: " +
          "ماه %d" % cashflow(shops_per_month=120, arpu=a_m, no_churn=True)[1])


def selftest():
    # LLM
    c = llm_cost_per_chat("mini")
    assert 150 < c < 250, c                      # ~۱۹۱ تومان
    assert llm_cost_per_chat("mini", fx=FX * 1.15) > c   # خطی با FX
    # صوت رایگان در استک واقعی
    assert voice_cost_per_chat(paid=False) == 0.0
    assert voice_cost_per_chat(paid=True) > 0
    # حاشیه: rule-based همه مثبت (هزینه ≈ فقط SMS)
    for k in PLANS:
        assert plan_quarter_margin(k, "rule") > 0, k
    # LLM mid برای مغازه ضررده است
    assert plan_quarter_margin("maghaze", "mid") < 0
    # دفتر با ۲۰۰ گفتگو حتی با mini سالم می‌ماند
    assert plan_quarter_margin("daftar", "mini") > 0
    # ARPU مثبت و کمتر از max پلن
    a = arpu_monthly()
    assert 0 < a < 3_900_000 * SEASONS_PER_MONTH + 100 * 500 * 3
    # تناقض دوره: تفسیر month حتماً ARPU بالاتر از quarter (۳ برابر)
    assert abs(arpu_monthly(cycle="month") - 3 * arpu_monthly(cycle="quarter")) < 1.0
    # سربه‌سر: quarter (درآمد کمتر) → تعداد مغازه بیشتر
    assert breakeven_shops(cycle="quarter", model="rule") > breakeven_shops(cycle="month", model="rule")
    # سربه‌سر
    b_rule = breakeven_shops(model="rule")
    assert b_rule is not None and 500 < b_rule < 4000, b_rule
    # قیف
    st = funnel_stages()
    assert st[0][1] == 3_200_000
    assert st[-1][1] < st[0][1]
    assert all(st[i][1] >= st[i + 1][1] for i in range(len(st) - 1))
    # جریان نقدی
    a_q = arpu_monthly()
    a_m = a_q * 3.0
    # فصلی + چرخش واقعی: حتی bull در ۱۸ ماه به سربه‌سر نمی‌رسد (یافته‌ی کلیدی)
    _n, be_q_bull, _b = cashflow(shops_per_month=250, arpu=a_q)
    assert be_q_bull is None
    # ماهانه + چرخش: base سربه‌سر می‌شود، bull زودتر
    _n, be_b, _b = cashflow(shops_per_month=120, arpu=a_m)
    be_bull = cashflow(shops_per_month=250, arpu=a_m)[1]
    assert be_b is not None and 6 <= be_b <= 14, be_b
    assert be_bull is not None and be_bull < be_b
    # مدل v1 (بدون چرخش) زودتر سربه‌سر می‌شود
    be_nochurn = cashflow(shops_per_month=120, arpu=a_m, no_churn=True)[1]
    assert be_nochurn is not None and be_nochurn < be_b
    # bear هرگز
    assert cashflow(shops_per_month=40, arpu=a_m)[1] is None
    # منطقی‌سازی: افزایش fixed → سربه‌سر بیشتر
    assert breakeven_shops(fixed=FIXED_WITH_GROWTH, model="rule") > b_rule
    print("UNIT-ECON SELFTEST OK")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--selftest":
        selftest()
    else:
        report()
