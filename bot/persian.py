# -*- coding: utf-8 -*-
"""اعداد و تقویم فارسی — ارقام همیشه از کد‌پوینت ساخته می‌شوند (قانون پروژه).

تقویم: جدول نوروز (jal_cal) پورت jalaali-js است و در برابر تقویم رسمی ایران
(jdatetime) روزبه‌روز برای ۱۹۹۶..۲۰۴۰ اعتبارسنجی شده — بقیه‌ی محاسبات با
ordinal خودِ پایتون انجام می‌شود (بی‌خطا). نسخه‌ی قبلی _g2j در مرز نوروزیِ
سال‌های ۱۳۹۹/۱۴۰۳ و روز اسفند ۳۰ یک‌روز/یک‌سال خطا داشت (issue #5).
"""
import datetime
import re

# U+06F0..U+06F9
FA = {i: chr(0x06F0 + i) for i in range(10)}
FA_SEP = "\u066C"  # ٬

JAL = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
       "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"]
JAL_DAY = ["شنبه", "یکشنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه"]

# ── تقویم جدول نوروز (پورت jalCal از jalaali-js — div از نوع truncate مثل JS) ──
_BREAKS = [-61, 9, 38, 199, 426, 686, 756, 818, 1111, 1181, 1210,
           1635, 2060, 2097, 2192, 2262, 2324, 2394, 2456, 3178]


def _div(a, b):
    """تقسیم truncate — دقیقاً مثل ~~(a/b) در JS."""
    q = a // b
    if q < 0 and q * b != a:
        q += 1
    return q


def _jal_cal(jy):
    """(leap, gy, march) — leap==0 یعنی کبیسه؛ march = روز مارسِ ۱ فروردین."""
    jp = _BREAKS[0]
    leap_j = -14
    jump = 0
    for i in range(1, len(_BREAKS)):
        jm = _BREAKS[i]
        jump = jm - jp
        if jy < jm:
            break
        leap_j += _div(jump, 33) * 8 + _div(jump % 33, 4)
        jp = jm
    n = jy - jp
    leap_j += _div(n, 33) * 8 + _div(n % 33 + 3, 4)
    if jump % 33 == 4 and jump - n == 4:
        leap_j += 1
    gy = jy + 621
    leap_g = _div(gy, 4) - _div((_div(gy, 100) + 1) * 3, 4) - 150
    march = 20 + leap_j - leap_g
    if jump - n < 6:
        n = n - jump + _div(jump + 4, 33) * 33
    leap = ((n + 1) % 33 - 1) % 4
    return leap, gy, march


def _farvardin1_ordinal(jy):
    """ordinal میلادیِ ۱ فروردین سال شمسی + پرچم کبیسه."""
    leap, gy, march = _jal_cal(jy)
    return datetime.date(gy, 3, march).toordinal(), leap


def is_leap_jalali(jy):
    """سال کبیسه شمسی؟ (اسفند ۳۰ روزه)"""
    return _farvardin1_ordinal(jy)[1] == 0


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
    for ch in (FA_SEP, ",", "٬", " "):
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


def _g2j(gy, gm, gd):
    """میلادی -> شمسی — مطابق تقویم رسمی ایران (اعتبارسنجی‌شده با jdatetime)."""
    o = datetime.date(gy, gm, gd).toordinal()
    jy = gy - 621
    o0, _leap = _farvardin1_ordinal(jy)
    if o < o0:
        jy -= 1
        o0, _leap = _farvardin1_ordinal(jy)
    k = o - o0  # روزِ سال، مبتنی بر صفر
    if k <= 185:
        return (jy, 1 + k // 31, (k % 31) + 1)
    k -= 186
    return (jy, 7 + k // 30, (k % 30) + 1)


def jalali_to_gregorian(jy, jm, jd):
    """شمسی -> میلادی (تاریخ datetime.date).
    تاریخ نامعتبر (مثل ۱۴۰۵-۱۲-۳۰ در سال غیرکبیسه یا ماه ۱۳) -> ValueError."""
    if not (1 <= jm <= 12):
        raise ValueError("bad jalali month %s" % jm)
    if jm <= 6:
        last = 31
    elif jm <= 11:
        last = 30
    else:
        last = 30 if is_leap_jalali(jy) else 29
    if not (1 <= jd <= last):
        raise ValueError("bad jalali day %s-%s-%s" % (jy, jm, jd))
    o0, _leap = _farvardin1_ordinal(jy)
    doy = (jm - 1) * 31 + (jd - 1) if jm <= 6 else 186 + (jm - 7) * 30 + (jd - 1)
    d = datetime.date.fromordinal(o0 + doy)
    return (d.year, d.month, d.day)


def jalali(d):
    """datetime.date -> 'روز + ماه + سال' با ارقام فارسی"""
    jy, jm, jd = _g2j(d.year, d.month, d.day)
    return "%s %s %s" % (fa_num(jd, sep=False), JAL[jm - 1], fa_num(jy, sep=False))


def jalali_now():
    import datetime
    return jalali(datetime.date.today())
