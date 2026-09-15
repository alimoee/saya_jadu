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
    for ch in (FA_SEP, ",", "٬", " ", "٬"):
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
    """Gregorian -> Jalali — پورتِ دقیق الگوریتمی که در سایت تست شده (37/37)."""
    gdm = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    jy = 0 if gy <= 1600 else 979
    gy -= 621 if gy <= 1600 else 1600
    gy2 = gy + 1 if gm > 2 else gy
    days = (365 * gy) + (gy2 + 3) // 4 - (gy2 + 99) // 100 + (gy2 + 399) // 400 - 80 + gd + gdm[gm - 1]
    jy += 33 * (days // 12053)
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    jy += (days - 1) // 365
    if days > 365:
        days = (days - 1) % 365
    else:
        days %= 365
    jm = 1 + days // 31 if days < 186 else 7 + (days - 186) // 30
    jd = 1 + (days % 31 if days < 186 else (days - 186) % 30)
    return (jy, jm, jd)


def jalali(d):
    """datetime.date -> 'روز + ماه + سال' با ارقام فارسی"""
    jy, jm, jd = _g2j(d.year, d.month, d.day)
    return "%s %s %s" % (fa_num(jd, sep=False), JAL[jm - 1], fa_num(jy, sep=False))


def jalali_now():
    import datetime
    return jalali(datetime.date.today())
