# -*- coding: utf-8 -*-
"""اعداد و تقویم فارسی — ارقام همیشه از کد‌پوینت ساخته می‌شوند (قانون پروژه)."""
import re

# U+06F0..U+06F9
FA = {i: chr(0x06F0 + i) for i in range(10)}
FA_SEP = "\u066C"  # ٬

JAL = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
       "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"]
JAL_DAY = ["شنبه", "یکشنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه"]


def fa_num(n, sep=True):
    """عدد -> رشته ارقام فارسی؛ با جداکننده هزارگان (sep=True)."""
    if isinstance(n, float):
        n = int(round(n))
    n = int(n)
    neg = n < 0
    s = str(abs(n))
    if sep:
        s = re.sub(r"(\d)(?=(\d{3})+(?!\d))", r"\1" + FA_SEP, s)
    out = []
    for ch in s:
        out.append(FA[int(ch)] if ch.isdigit() else ch)
    return ("-" if neg else "") + "".join(out)


def to_int(s):
    """رشته با ارقام فارسی/انگلیسی و جداکننده‌ها -> int (یا None)."""
    if s is None:
        return None
    if isinstance(s, int):
        return s
    s = str(s)
    for ch in (FA_SEP, ",", " "):
        s = s.replace(ch, "")
    m = ""
    for ch in s:
        if ch in FA.values():
            m += str(list(FA.values()).index(ch))
        elif ch.isdigit():
            m += ch
    try:
        return int(m) if m else None
    except ValueError:
        return None


JAL_MONTH = {m: i + 1 for i, m in enumerate(JAL)}

# ── تقویم دقیق جلالی (الگوریتم Borkowski 1996 — jalaali-js) ──
# دقیق برای سال‌های جلالی 61- تا 3177.
# مرجع: https://www.astro.uni.torun.pl/~kb/Papers/EMP/PersianC-EMP.htm
_BREAKS = (-61, 9, 38, 199, 426, 686, 756, 818, 1111, 1181,
           1210, 1635, 2060, 2097, 2192, 2262, 2324, 2394, 2456, 3178)
MIN_JY, MAX_JY = -61, 3177


def _div(a, b):
    """تقسیم صحیح به‌سراِ صفر (معادل ~~(a/b))"""
    q = abs(a) // abs(b)
    return q if (a < 0) == (b < 0) else -q


def _mod(a, b):
    return a - _div(a, b) * b


def _jal_cal_core(jy):
    gy = jy + 621
    leapJ = -14
    jp = _BREAKS[0]
    jump = 0
    for i in range(1, len(_BREAKS)):
        jm = _BREAKS[i]
        jump = jm - jp
        if jy < jm:
            break
        leapJ = leapJ + _div(jump, 33) * 8 + _div(_mod(jump, 33), 4)
        jp = jm
    n = jy - jp
    leapJ = leapJ + _div(n, 33) * 8 + _div(_mod(n, 33) + 3, 4)
    if _mod(jump, 33) == 4 and jump - n == 4:
        leapJ += 1
    leapG = _div(gy, 4) - _div((_div(gy, 100) + 1) * 3, 4) - 150
    march = 20 + leapJ - leapG
    return gy, march, jump, n


def _leap_from_cycle(jump, n):
    adjusted = n
    if jump - n < 6:
        adjusted = n - jump + _div(jump + 4, 33) * 33
    leap = _mod(_mod(adjusted + 1, 33) - 1, 4)
    if leap == -1:
        leap = 4
    return leap


def is_leap_jy(jy):
    if not (MIN_JY <= jy <= MAX_JY):
        raise ValueError(jy)
    jp = _BREAKS[0]
    jump = 0
    for i in range(1, len(_BREAKS)):
        jm = _BREAKS[i]
        jump = jm - jp
        if jy < jm:
            break
        jp = jm
    return _leap_from_cycle(jump, jy - jp) == 0


def _g2d(gy, gm, gd):
    d = (_div((gy + _div(gm - 8, 6) + 100100) * 1461, 4)
         + _div(153 * _mod(gm + 9, 12) + 2, 5) + gd - 34840408)
    return d - _div(_div(gy + 100100 + _div(gm - 8, 6), 100) * 3, 4) + 752


def _d2g(jdn):
    j = 4 * jdn + 139361631
    j = j + _div(_div(4 * jdn + 183187720, 146097) * 3, 4) * 4 - 3908
    i = _div(_mod(j, 1461), 4) * 5 + 308
    gd = _div(_mod(i, 153), 5) + 1
    gm = _mod(_div(i, 153), 12) + 1
    gy = _div(j, 1461) - 100100 + _div(8 - gm, 6)
    return (gy, gm, gd)


def _j2d(jy, jm, jd):
    gy, march, _j, _n = _jal_cal_core(jy)
    return _g2d(gy, 3, march) + (jm - 1) * 31 - _div(jm, 7) * (jm - 7) + jd - 1


def _d2j(jdn):
    gy = _d2g(jdn)[0]
    jy = min(gy - 621, MAX_JY)
    gy2, march, jump, n = _jal_cal_core(jy)
    leap = _leap_from_cycle(jump, n)
    jdn1f = _g2d(gy2, 3, march)
    k = jdn - jdn1f
    if k >= 0:
        if k <= 185:
            return (jy, 1 + _div(k, 31), _mod(k, 31) + 1)
        k -= 186
    else:
        jy -= 1
        k += 179
        if leap == 1:
            k += 1
    return (jy, 7 + _div(k, 30), _mod(k, 30) + 1)


def j2g(jy, jm, jd):
    """Jalali (دقيق) -> Gregorian (year, month, day)"""
    if not (MIN_JY <= jy <= MAX_JY and 1 <= jm <= 12):
        raise ValueError((jy, jm, jd))
    return _d2g(_j2d(jy, jm, jd))


def g2j(gy, gm, gd):
    """Gregorian -> Jalali (دقيق) — (year, month, day)"""
    return _d2j(_g2d(gy, gm, gd))


def _to_ascii_digits(s):
    return "".join(str(list(FA.values()).index(c)) if c in FA.values() else c for c in s)


def parse_jalali(s, ref_date=None):
    """تاریخ شمسی -> datetime.date یا None.
    فرمت‌ها: '22/7'، '۲۲/۷/۱۴۰۵'، '22 مهر'، '۲۲ مهر ۴۰۵' (سال خالی = سال شمسیِ ref_date)."""
    import datetime as _dt
    s = _to_ascii_digits(str(s)).strip()
    ref_date = ref_date or _dt.date.today()
    cur_jy = g2j(ref_date.year, ref_date.month, ref_date.day)[0]
    m = re.match(r"^\d{1,4}$", s)
    if m:
        return None
    m = re.match(r"^(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?$", s)
    if m:
        jd, jm = int(m.group(1)), int(m.group(2))
        jy = int(m.group(3)) if m.group(3) else cur_jy
        if m.group(3) and len(m.group(3)) == 2:
            jy += 1400
    else:
        m = re.match(r"^(\d{1,2})\s+([\u0600-\u06FF]+?)(?:\s+(\d{2,4}))?$", s)
        if not m:
            return None
        jd = int(m.group(1))
        jm = JAL_MONTH.get(m.group(2).strip())
        if jm is None:
            return None
        jy = int(m.group(3)) if m.group(3) else cur_jy
        if m.group(3) and len(m.group(3)) == 2:
            jy += 1400
    if not (1 <= jm <= 12 and 1 <= jd <= 31 and MIN_JY <= jy <= MAX_JY):
        return None
    try:
        maxd = 31 if jm <= 6 else (30 if jm <= 11 else (30 if is_leap_jy(jy) else 29))
        if jd > maxd:
            return None
        gy, gm, gd = j2g(jy, jm, jd)
    except Exception:
        return None
    return _dt.date(gy, gm, gd)


def jalali(d):
    """datetime.date -> 'روز + ماه + سال' با ارقام فارسی"""
    jy, jm, jd = g2j(d.year, d.month, d.day)
    return "%s %s %s" % (fa_num(jd, sep=False), JAL[jm - 1], fa_num(jy, sep=False))


def jalali_now():
    import datetime
    return jalali(datetime.date.today())
