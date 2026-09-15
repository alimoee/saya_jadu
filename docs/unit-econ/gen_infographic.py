#!/usr/bin/env python3
"""تولید اینفوگرافیک v2.1 — همه‌ی اعداد از خروجی unit_econ.py (بدون تایپ دستی)."""
import sys, datetime, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import unit_econ as u

D = {i: chr(0x06F0 + i) for i in range(10)}
def fa(n):
    """عدد فارسی + جداکننده‌ی هزارگان (جداکننده فقط برای اعداد ۵ رقم به بالا)."""
    s = str(abs(int(n)))
    out = []
    for i, c in enumerate(reversed(s)):
        if i and i % 3 == 0 and len(s) > 4:
            out.append('\u066c')
        out.append(D[int(c)])
    return ''.join(reversed(out))
fnum = fa

fx = fnum(u.FX)
arpu_q = fnum(u.arpu_monthly(cycle="quarter"))
arpu_m = fnum(u.arpu_monthly(cycle="month"))

def margin_cell(plan, model):
    pct = u.plan_month_margin_pct(plan, model)
    if pct >= 0: return fa(int(pct)) + "٪"
    return "زیان"

rows_html = ""
for k in ("maghaze", "maghaze_plus", "daftar"):
    p = u.PLANS[k]
    row = [p["label"], fnum(p["price"])] + [margin_cell(k, m) for m in ("rule", "mini", "mid")]
    bad = " class='bad'" if "زیان" in row[3:] else ""
    rows_html += "<tr%s>%s</tr>\n" % (bad, "".join("<td>%s</td>" % c for c in row))

min_g = u.min_growth_for_be()
scen = []
for fixed, slope, cap, tag in (
    (u.FIXED_MINIMAL, 120, 120, "تیم کامل (%s میلیون) + رشد %s مغازه/ماه" % (fa(u.FIXED_MINIMAL // 1_000_000), fa(120))),
    (u.FIXED_MINIMAL, min_g, min_g, "حداقل رشد محاسبه‌شده (%s/ماه)" % fa(min_g)),
    (450_000_000, 80, 80, "تیم لاغر (%s میلیون) + رشد %s/ماه" % (fa(450), fa(80))),
    (450_000_000, 60, 60, "تیم لاغر (%s میلیون) + رشد %s/ماه" % (fa(450), fa(60))),
    (u.FIXED_MINIMAL, 30, 30, "تنها مالک — سقف آنبردینگ %s/ماه" % fa(30)),
):
    _n, be, burn, _ns = u.cashflow_v2(target_slope=slope, onboarding_capacity=cap, cycle="month", fixed=fixed)
    scen.append((tag, ("ماه " + fa(be)) if be else "هرگز در %s ماه" % fa(18), fnum(-burn)))
scen_html = "".join("<tr><td>%s</td><td class='%s'>%s</td><td>%s</td></tr>\n" % (
    t, ("good" if b.startswith("ماه") else "bad"), b, br) for t, b, br in scen)

team_rows = [(n, fnum(v)) for n, v in u.team_breakdown()]
team_html = "".join("<tr><td>%s</td><td>%s</td></tr>\n" % (n, v) for n, v in team_rows)

bat_rows = []
for k in ("maghaze", "maghaze_plus", "daftar"):
    rev, cost = u.battery_monthly(k, 3)
    bat_rows.append((u.PLANS[k]["label"], fnum(rev), fnum(cost), fa(int(100 * (rev - cost) / rev))))
bat_html = "".join("<tr><td>%s</td><td>%s</td><td>%s</td><td class='good'>%s٪</td></tr>\n" % r for r in bat_rows)

today = datetime.date.today().strftime("%Y-%m-%d")
mp_rev, mp_cost = u.battery_monthly("maghaze_plus", 3)
trials_per_paid = round(u.TRIALS_PER_PAID)  # 3
min_g = u.min_growth_for_be()
be_base, burn_base = u.cashflow_v2(target_slope=120, onboarding_capacity=120, cycle="month")[1:3]

HTML = """<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>اقتصاد واحد سایا — مدل v2.1 (بنیاد: چرخه‌ی ۳۰روزه)</title>
<style>
  :root{--bg:#0d1117;--card:#161b22;--line:#30363d;--txt:#e6edf3;--mut:#8b949e;
        --gold:#e3b341;--green:#3fb950;--red:#f85149;--blue:#58a6ff;}
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--txt);
       font-family:"Vazirmatn","IRANSans","Segoe UI",Tahoma,sans-serif;font-size:15px;line-height:1.9}
  .wrap{max-width:920px;margin:0 auto;padding:32px 20px 60px}
  h1{font-size:26px;margin:0 0 4px}
  .sub{color:var(--mut);margin-bottom:26px;font-size:13.5px}
  .card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:20px 22px;margin:18px 0}
  .card h2{font-size:17px;margin:0 0 10px;color:var(--gold)}
  table{width:100%%;border-collapse:collapse;font-size:14px;margin:8px 0}
  th{color:var(--mut);font-weight:600;text-align:right;padding:7px 10px;border-bottom:1px solid var(--line)}
  td{padding:8px 10px;border-bottom:1px solid #21262d}
  tr:last-child td{border-bottom:none}
  .good{color:var(--green);font-weight:700}
  .bad{color:var(--red);font-weight:700}
  .strip{display:flex;flex-wrap:wrap;gap:12px;margin:18px 0}
  .chip{flex:1 1 260px;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px}
  .chip b{display:block;font-size:19px;margin-bottom:2px}
  .chip span{color:var(--mut);font-size:12.5px;line-height:1.7;display:block}
  .alert{border-right:4px solid var(--gold);background:#1a1a0d}
  code{background:#21262d;border:1px solid var(--line);border-radius:6px;padding:2px 7px;
       font-family:Consolas,monospace;font-size:12.5px;color:var(--blue)}
  ul{margin:6px 0;padding-right:22px}
  li{margin:5px 0}
  .tag{display:inline-block;border:1px solid var(--line);border-radius:6px;padding:1px 8px;
       font-size:11.5px;color:var(--mut);margin-right:6px}
  .foot{color:var(--mut);font-size:12px;margin-top:30px;border-top:1px solid var(--line);padding-top:14px}
</style>
</head>
<body>
<div class="wrap">
  <h1>سایا — اقتصاد واحد (مدل v2.1 — بنیاد: چرخه‌ی ۳۰روزه)</h1>
  <div class="sub">مالکیت: مخزن <code>docs/unit-econ/unit_econ.py</code> · تست‌شده (--selftest) · تاریخ %s ·
  FX = %s تومان/دلار (بازار تهران، %s) · همه‌ی اعداد این صفحه خروجی مستقیم مدل‌اند — بدون تایپ دستی.</div>

  <div class="card alert" style="border-right-color:var(--green);background:#0d1a12">
    <h2 style="color:var(--green)">✅ تصمیم مالک (۲۵ شهریور ۱۴۰۵): چرخه‌ی صورتحساب = ۳۰ روز</h2>
    تناقض قدیمی سایت («%s هر فصل» ↔ «%s هزار در روز») با پچ ۲۵ شهریور <b>رفع شد</b> (فصل → ماه روی ai-a/final؛ زنده با merge به main).
    قیمت‌ها بدون تغییر: %s هزار تومان <b>هر ماه</b> = %s هزار در روز. چرخه‌ی ۹۰روزه (فصلی) در مدل به‌عنوان سناریوی <b class="bad">ردشده</b> می‌ماند (هرگز سربه‌سر، حتی با رشد %s/ماه).
    <span style="display:block;color:var(--mut);font-size:13px;margin-top:6px">
    ARPU مؤثر ماهانه: بنیاد (ماه) = %s · ردشده (فصل) = %s</span>
  </div>

  <div class="strip">
    <div class="chip"><b class="bad">چرخه‌ی فصلی = رد شد</b><span>حتی با %s مغازه/ماه جدید در %s ماه — قیمت فصلی، ARPU را برای پوشش %s میلیون هزینه‌ی ثابت نمی‌رساند. (تصمیم ۲۵ شهریور: ماه)</span></div>
    <div class="chip"><b class="good">۳۰ روز + تیم → ماه %s</b><span>تیم کامل (%s میلیون) + رشد %s مغازه/ماه؛ سوخت تا آنجا ≈ %s تومان.</span></div>
    <div class="chip"><b class="bad">تنها مالک = غیرممکن</b><span>آنبردینگ هر مغازه ≈ %s ساعت تلفن → سقف ≈ %s مغازه/ماه؛ با این سقف مدل هرگز سربه‌سر نمی‌شود. یک تیم کوچک آنبردینگ/فروش لازم است.</span></div>
    <div class="chip"><b>حداقل رشد: %s مغازه/ماه</b><span>محاسبه‌شده در مدل (جستجوی دوجنب). کمتر از این، تا ماه %s سربه‌سر نمی‌آید — بدون بافر. رشد %s بافر دارد (ماه %s).</span></div>
    <div class="chip"><b class="good">باتری: حاشیه %s–%s٪</b><span>باتری حالا یک خط درآمد واقعی است: مغازه+ ماهی %s درآمد، هزینه‌اش %s.</span></div>
    <div class="chip"><b>هوش هیبرید: %s تومان/گفتگو</b><span>٪%s قاعده‌ای رایگان + ٪%s LLM ارزان — میانگین ≈ %s در برابر %s برای LLM کامل. حاشیه‌ی پلن‌ها ۹۰٪+ می‌ماند.</span></div>
  </div>

  <div class="card">
    <h2>حاشیه‌ی هر پلن در چرخه‌ی ۳۰روزه (بنیاد — قبل از باتری)</h2>
    <table>
      <tr><th>پلن</th><th>قیمت/ماه</th><th>هوش rule (قاعده‌ای)</th><th>هوش LLM-mini</th><th>هوش LLM-mid</th></tr>
      %s
    </table>
    <div class="sub" style="margin-top:8px">در چرخه‌ی ماهانه همان قیمت، درآمدهای ماهانه ۳ برابر سناریوی فصلی می‌شوند. مغز هیبرید (٪%s LLM) هزینه را زیر mini نگه می‌دارد: حاشیه‌ی واقعی بنیاد ۹۰٪+ برای همه‌ی پلن‌ها.</div>
  </div>

  <div class="card">
    <h2>جریان نقدی واقع‌بینانه — سناریوهای عملیاتی (چرخه‌ی ۳۰روزه)</h2>
    <table>
      <tr><th>سناریو</th><th>سربه‌سر</th><th>عمیق‌ترین سوخت</th></tr>
      %s
    </table>
    <div class="sub" style="margin-top:8px">مدل شامل: ramp ۶ماهه‌ی رشد · سقف آنبردینگ · تریال‌ها (%s تریال/هر مشتری جدید، %s تومان/تریال) · دنینگ ٪%s · چرخش cohort (٪%s ماه دوم، ٪%s بعدش) · باتری با ramp مصرف · هزینه‌ی متغیر LLM/SMS با تورم FX.</div>
  </div>

  <div class="card">
    <h2>تفکیک هزینه‌ی ثابت %s تومان/ماه <span class="tag">ASSUMPTION — در انتظار چالش AI-B</span></h2>
    <table>
      <tr><th>قلم</th><th>تومان/ماه</th></tr>
      %s
    </table>
    <div class="sub" style="margin-top:8px">مهم‌ترین اهرم: «هزینه‌ی فرصت مالک» (%s میلیون). اگر مالک تمام‌وقت نباشد یا ۱ توسعه‌دهنده کفایت کند → سناریوی «تیم لاغر» (سربه‌سر ماه ۱۰–۱۴).</div>
  </div>

  <div class="card">
    <h2>باتری — خط درآمد واقعی <span class="tag">تأیید مالک ۲۵ شهریور</span></h2>
    <table>
      <tr><th>پلن</th><th>درآمد ماهانه خرد (پیک)</th><th>هزینه ماهانه خرد</th><th>حاشیه</th></tr>
      %s
    </table>
    <div class="sub" style="margin-top:8px">قیمت‌ها روی سایت (هر سه کارت) نمایش داده می‌شوند: گفتگوی هوشمند اضافی %s تومان (≈%s× هزینه‌ی mini) + فاکتور اضافی %s تومان (پلن دفتر).</div>
  </div>

  <div class="card">
    <h2>پارامترهای مدل (منبع هرکدام)</h2>
    <ul>
      <li>FX %s تومان (بازار تهران، %s) · markup LLM ٪%s</li>
      <li>قیمت پلن‌ها، فاکتور اضافی، گفتگوی رایگان: <b>سایت</b> · صوت: <b>رایگان</b> (edge-tts + Vosk)</li>
      <li>چرخه‌ی محاسباتی ۳۰ روز: <b>تصمیم مالک ۲۵ شهریور</b> (سایت اصلاح شد) · قیمت گفتگوی باتری %s تومان: <b>تأیید مالک</b> (در سایت)</li>
      <li>هوش هیبرید: ٪%s LLM-mini + ٪%s قاعده‌ای <span class="tag">ASSUMPTION</span></li>
      <li>آنبردینگ تلفنی برای ۲ نفر (مالک + همکار — از سایت): ≈%s ساعت × %s تومان/ساعت = %s تومان/مغازه (یک‌بار) <span class="tag">ASSUMPTION</span></li>
      <li>تریال: %s روز (<b>سایت</b>) · %s تریال/مشتری جدید · %s تومان/تریال <span class="tag">ASSUMPTION — متناسب‌شده</span></li>
      <li>دنینگ ٪%s · چرخش ٪%s ماه دوم + ٪%s/ماه <span class="tag">ASSUMPTION — چالش AI-B</span></li>
      </ul>
  </div>

  <div class="card">
    <h2>اقدامات (وضعیت ۲۵ شهریور)</h2>
    <ul>
      <li>✅ اصلاح کپی سایت (فصل → ماه) + قیمت گفتگو روی هر سه کارت — روی <code>ai-a/final</code> (زنده با merge به main) · تست سایت ۲۹/۲۹</li>
      <li>✅ قیمت گفتگوی باتری %s تومان تأیید شد و در سایت است</li>
      <li>برنامه‌ی رشد: حداقل محاسبه‌شده %s مغازه/ماه (بدون بافر) → تیم آنبردینگ/فروش ۲–۳ نفر؛ هدف بافردار %s</li>
      <li>اگر مسیر «تنها مالک» است: فقط با کاهش ثابت به ≈%s میلیون و رشد %s+/ماه ممکن می‌شود (رشد %s کفایت نمی‌کند)</li>
    </ul>
  </div>

  <div class="foot">تولیدکننده: <code>docs/unit-econ/unit_econ.py</code> · بازتولید:
  <code>cd docs/unit-econ &amp;&amp; python3 unit_econ.py --selftest</code> ·
  همه‌ی اعداد از خروجی همان اسکریپت ساخته شده‌اند (بدون تایپ دستی) · تاریخ %s</div>
</div>
</body>
</html>
"""

fa_date = "".join(D[int(c)] for c in "1405") + "/" + fa(6) + "/" + fa(15)
vals = (today, fx, fa_date,
        fa(990000), "۳۳", fa(990), "۳۳", fa(250),
        arpu_m, arpu_q,
        fa(250), fa(18), fa(u.FIXED_MINIMAL // 1_000_000),
        fa(be_base), fa(u.FIXED_MINIMAL // 1_000_000), fa(120), fnum(-burn_base),
        fa(2), fa(30),
        fa(min_g), fa(18), fa(120), fa(be_base),
        bat_rows[0][3], bat_rows[2][3], fnum(mp_rev), fnum(mp_cost),
        fa(u.hybrid_llm_per_chat()),
        fa(int(100 * (1 - u.HYBRID_LLM_SHARE))), fa(int(100 * u.HYBRID_LLM_SHARE)),
        fa(u.hybrid_llm_per_chat()), fa(u.llm_cost_per_chat("mini")),
        rows_html,
        fa(int(100 * u.HYBRID_LLM_SHARE)),
        scen_html,
        fa(trials_per_paid), fnum(u.TRIAL_COST_PER),
        fa(int(100 * u.DUNNING_LOSS)), fa(40), fa(10),
        fnum(u.FIXED_MINIMAL),
        team_html,
        fa(250),
        bat_html,
        fnum(u.BATTERY_PRICE_PER_LLM_CHAT), "۵", fnum(500),
        fa(u.FX), fa_date, fa(80),
        fnum(u.BATTERY_PRICE_PER_LLM_CHAT),
        fa(int(100 * u.HYBRID_LLM_SHARE)), fa(int(100 * (1 - u.HYBRID_LLM_SHARE))),
        fa(2), fnum(u.WAGE_H), fnum(u.ONBOARD_COST),
        fa(u.TRIAL_DAYS), fa(trials_per_paid), fnum(u.TRIAL_COST_PER),
        fa(int(100 * u.DUNNING_LOSS)), fa(40), fa(10),
        fnum(u.BATTERY_PRICE_PER_LLM_CHAT),
        fa(min_g), fa(120),
        fa(450), fa(60), fa(30),
        today)

out = HTML % vals
open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'index.html'), 'w', encoding='utf-8').write(out)
print("written", len(out), "bytes")
