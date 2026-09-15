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



# ── استک هزینه‌ی واقع‌بینانه (v2.1) ────────────────────
WAGE_H = 150_000                # تومان/ساعت نیروی مؤثر (ASSUMPTION)
ONBOARD_HOURS = 2.0             # آنبردینگ تلفنی برای دو نفر (قول سایت)
ONBOARD_COST = int(ONBOARD_HOURS * WAGE_H)   # یک‌باره/مغازه

HYBRID_LLM_SHARE = 0.20         # مغز هیبرید: ۲۰٪ گفتگوها به LLM (بقیه الگویی)

VPS_MONTHLY = 8_000_000         # VPS + درگاه + دامنه + متفرقه (ASSUMPTION)
DUNNING_LOSS = 0.05             # از دست‌رفتن تمدید (بی‌پرداختی/فراموشی)

TRIAL_DAYS = 14
TRIALS_PER_PAID = 1.0 / 0.35    # قیف: تریال→پرداخت ۳۵٪
TRIAL_COST_PER = 25_000         # هزینه‌ی LLM/SMS یک تریال ۱۴ روزه (ASSUMPTION)

# باتری (اعتبار مصرفی) — مصرف خرد ماهانه هر مغازه (ASSUMPTION)
BATTERY = {
    "maghaze":      dict(extra_invoices=150, extra_llm_chats=100),
    "maghaze_plus": dict(extra_invoices=400, extra_llm_chats=300),
    "daftar":       dict(extra_invoices=300, extra_llm_chats=150),
}
BATTERY_PRICE_PER_INVOICE = 500      # تومان (سایت، پلن دفتر)
BATTERY_PRICE_PER_LLM_CHAT = 1_000   # تومان — پیشنهاد ما (≈۵× هزینه‌ی mini) (ASSUMPTION)

def battery_monthly(plan, age, fx=FX):
    """(درآمد، هزینه) باتری ماهِ age هر مغازه. مصرف ۳ ماه اول ramp-up دارد."""
    b = BATTERY[plan]
    ramp = 0.5 if age == 1 else (0.75 if age == 2 else 1.0)
    rev = (b["extra_invoices"] * BATTERY_PRICE_PER_INVOICE +
           b["extra_llm_chats"] * BATTERY_PRICE_PER_LLM_CHAT) * ramp
    cost = b["extra_llm_chats"] * llm_cost_per_chat("mini", fx) * ramp
    return rev, cost

def hybrid_llm_per_chat(fx=FX):
    """مغز هیبرید: ۸۰٪ الگویی (≈۰) + ۲۰٪ LLM اقتصادی."""
    return HYBRID_LLM_SHARE * llm_cost_per_chat("mini", fx)

def team_breakdown():
    """تفکیک هزینه‌ی ثابت ۹۵۰M (ASSUMPTION — تهران ۱۴۰۵)."""
    return [
        ("مالک/مدیر (هزینه‌ی فرصت)", 250_000_000),
        ("۲ توسعه‌دهنده‌ی تمام‌وقت", 360_000_000),
        ("پشتیبانی/آنبردینگ (پاره)", 150_000_000),
        ("VPS + زیرساخت + درگاه", 40_000_000),
        ("بازاریابی (بودجه‌ی کم)", 100_000_000),
        ("متفرقه/پراکندگی", 50_000_000),
    ]

def cashflow_v2(months=18, target_slope=120, onboarding_capacity=30,
                cycle="month", fixed=FIXED_MINIMAL,
                churn2=0.40, churn_later=0.10, fx_drift=0.0,
                include_battery=True, mix=None):
    """مدل واقع‌بینانه (v2.1):
    - رشد با ramp ۶ ماهه و سقف آنبردینگ (هر مغازه ~۲ ساعت آنبردینگ تلفنی)
    - تریال‌های لازم برای هر مشتری جدید + هزینه‌یشان
    - چرخش cohort (ماه دوم ۴۰٪، بعدش ۱۰٪)
    - اشتراک: month = ماهانه / quarter = پرداخت پله‌ای (ماه ۱،۴،۷ هر cohort)
    - دنینگ ۵٪ · باتری با ramp-up مصرف · تورم FX هر ۶ ماه (اختیاری)
    خروجی: (جریان خالص ماهانه، ماه سربه‌سر، عمیق‌ترین سوخت، جدید/ماه)"""
    mix = mix or MIX
    arpu_mix = sum(w * PLANS[k]["price"] * 30.0 / CYCLES[cycle]["days"] for k, w in mix.items())
    price_mix = sum(w * PLANS[k]["price"] for k, w in mix.items())
    var_unit = {k: (PLANS[k]["chats"] * (HYBRID_LLM_SHARE * llm_cost_per_chat("mini")) +
                    PLANS[k]["sms"] * SMS_COST) for k in mix}
    var_mix = sum(w * var_unit[k] for k, w in mix.items())
    bat_rev_mix_age = {}
    for a in range(1, months + 1):
        bat_rev_mix_age[a] = sum(w * battery_monthly(k, a)[0] for k, w in mix.items())
    bat_cost_mix = {a: sum(w * battery_monthly(k, a)[1] for k, w in mix.items())
                    for a in range(1, months + 1)}
    net, cum, burn, be, new_series = [], 0.0, 0.0, None, []
    cohorts = []
    for m in range(1, months + 1):
        fx_m = FX * (1.0 + fx_drift) ** (m / 6.0)
        new_m = min(int(round(target_slope * min(1.0, m / 6.0))), onboarding_capacity)
        new_series.append(new_m)
        cohorts.append(new_m)
        active = []   # (count, age)
        for idx, cnt in enumerate(cohorts):
            age = m - idx
            if cnt:
                surv = 1.0 if age == 1 else _retention(age, churn2, churn_later)
                active.append((cnt * surv, age))
        # درآمد اشتراک
        if cycle == "month":
            sub_in = sum(c * arpu_mix for c, a in active) * (1 - DUNNING_LOSS)
        else:
            sub_in = 0.0
            for c, a in active:
                if a % 3 == 1:  # ماه پرداخت: ۱،۴،۷،...
                    sub_in += c * price_mix
            sub_in *= (1 - DUNNING_LOSS)
        # باتری
        bat_in = bat_cost = 0.0
        if include_battery:
            for c, a in active:
                bat_in += c * bat_rev_mix_age[min(a, months)]
                bat_cost += c * bat_cost_mix[min(a, months)]
        # هزینه‌ها
        var_out = sum(c * var_mix for c, a in active)
        # تورم FX فقط روی بخش دلاری هزینه (LLM) اثر دارد — تقریب:
        var_out *= (1 + (fx_m / FX - 1.0) * 0.5)
        out = (fixed + new_m * (ONBOARD_COST + TRIALS_PER_PAID * TRIAL_COST_PER) + var_out)
        net_m = (sub_in + bat_in) - (out + bat_cost)
        net.append(net_m)
        cum += net_m
        burn = min(burn, cum)
        if be is None and net_m > 0:
            be = m
    return net, be, burn, new_series

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
    print("\n— مدل واقع‌بینانه v2.1 (ramp + سقف آنبردینگ + تریال + دنینگ + باتری) —")
    for cycle in ("quarter", "month"):
        for cap in (30, 120):
            _n, be, burn, _ns = cashflow_v2(target_slope=120, onboarding_capacity=cap, cycle=cycle)
            print("  %-8s سقف آنبردینگ %-4d → سربه‌سر: %s | سوخت: %s ت" % (
                cycle, cap, ("ماه %d" % be) if be else "هرگز در ۱۸ ماه", format(int(-burn), ",")))
    _n, be, burn, ns = cashflow_v2(target_slope=120, onboarding_capacity=120, cycle="month", fx_drift=0.25)
    print("  month + تورم FX ۲۵٪/ماه → سربه‌سر: %s" % (("ماه %d" % be) if be else "هرگز"))
    print("\n— تفکیک هزینه‌ی ثابت (ASSUMPTION) —")
    tot = 0
    for name, v in team_breakdown():
        tot += v
        print("  %-34s %s ت" % (name, format(v, ",")))
    print("  %-34s %s ت" % ("جمع", format(tot, ",")))
    print("\n— باتری (درآمد/هزینه‌ی ماهانه خرد، پیک مصرف) —")
    for k in PLANS:
        rev, cost = battery_monthly(k, 3)
        print("  %-14s درآمد %s | هزینه %s | حاشیه %s%%" % (
            PLANS[k]["label"], format(int(rev), ","), format(int(cost), ","),
            int(100 * (rev - cost) / rev) if rev else 0))
    print("\n— سناریوهای عملیاتی (ماهانه) —")
    for fixed, slope, cap, tag in (
        (FIXED_MINIMAL, 120, 120, "تیم کامل (۹۵۰M) + رشد ۱۲/ماه"),
        (FIXED_MINIMAL, 110, 110, "حداقل رشد برای سربه‌سر ۱۸ماهه (۱۱۰/ماه)"),
        (450_000_000, 80, 80, "تیم لاغر (۴۵۰M) + رشد ۸۰/ماه"),
        (450_000_000, 60, 60, "تیم لاغر (۴۵M) + رشد ۶۰/ماه"),
        (FIXED_MINIMAL, 30, 30, "تنها مالک (سقف ۳۰/ماه) — عدم امکان"),
    ):
        _n, be, burn, _ns = cashflow_v2(target_slope=slope, onboarding_capacity=cap,
                                        cycle="month", fixed=fixed)
        print("  %-44s → %s | سوخت %s" % (
            tag, ("ماه %d" % be) if be else "هرگز", format(int(-burn), ",")))


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
    # v2.1: باتری حاشیه‌دار
    for k in PLANS:
        rev, cost = battery_monthly(k, 3)
        assert rev > cost > 0, k
    # هیبرید < LLM کامل
    assert hybrid_llm_per_chat() < llm_cost_per_chat("mini")
    # ramp: هیچ ماهی از سقف آنبردینگ بیشتر نمی‌شود
    _n, _be, _b, ns = cashflow_v2(target_slope=120, onboarding_capacity=30)
    assert all(x <= 30 for x in ns)
    assert ns[-1] == 30 and ns[0] < 30
    # سقف بالاتر → سربه‌سر زودتر
    _n, be120, _b, _ns = cashflow_v2(target_slope=120, onboarding_capacity=120, cycle="month")
    assert be120 is not None
    _n, be30, _b, _ns = cashflow_v2(target_slope=120, onboarding_capacity=30, cycle="month")
    if be30 is not None:
        assert be120 < be30
    # quarter: ماه‌های ۲ و ۳ جریان خالص بدتر (پرداخت پله‌ای)
    nq, _beq, _bq, _nq = cashflow_v2(target_slope=60, onboarding_capacity=60, cycle="quarter")
    nm, _bem, _bm, _nm = cashflow_v2(target_slope=60, onboarding_capacity=60, cycle="month")
    assert nq[1] < nm[1]
    # تورم FX → سربه‌سر بیشتر
    be_fresh = cashflow_v2(target_slope=120, onboarding_capacity=120, cycle="month")[1]
    be_drift = cashflow_v2(target_slope=120, onboarding_capacity=120, cycle="month", fx_drift=0.5)[1]
    assert be_drift is None or be_drift >= (be_fresh or 1)
    # team_breakdown جمع می‌شود
    assert abs(sum(v for _n, v in team_breakdown()) - FIXED_MINIMAL) < 1
    print("UNIT-ECON SELFTEST OK")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--selftest":
        selftest()
    else:
        report()
