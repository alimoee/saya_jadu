# -*- coding: utf-8 -*-
"""لایه‌ی ذخیره — SQLite خالص (بدون سرور، بدون کلید)."""
import json
import os
import sqlite3
import time

SCHEMA = """
CREATE TABLE IF NOT EXISTS invoices(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  trade TEXT, no TEXT, total INTEGER, items TEXT,
  photo TEXT, source TEXT, created_at INTEGER);
CREATE TABLE IF NOT EXISTS reminders(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  customer TEXT, chat_id INTEGER, text TEXT,
  remind_at INTEGER, done INTEGER DEFAULT 0, attempts INTEGER DEFAULT 0,
  created_at INTEGER);
CREATE TABLE IF NOT EXISTS customers(
  chat_id INTEGER PRIMARY KEY, name TEXT, phone TEXT, created_at INTEGER);
CREATE TABLE IF NOT EXISTS pending(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  chat_id INTEGER, kind TEXT, payload TEXT, created_at INTEGER, expires INTEGER);
CREATE TABLE IF NOT EXISTS credits(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  customer TEXT, chat_id INTEGER, amount INTEGER, paid INTEGER DEFAULT 0,
  due INTEGER, status TEXT DEFAULT 'open', created_at INTEGER);
CREATE TABLE IF NOT EXISTS accounts(
  chat_id INTEGER PRIMARY KEY,
  name TEXT, shop TEXT, trade TEXT, city TEXT, phone TEXT,
  n_customers INTEGER DEFAULT 0, n_items INTEGER DEFAULT 0,
  status TEXT DEFAULT 'trial',
  plan TEXT DEFAULT 'shorou',
  verification INTEGER DEFAULT 0,
  period_end INTEGER DEFAULT 0,
  units_total REAL DEFAULT 0,
  units_left REAL DEFAULT 0,
  last_warn INTEGER DEFAULT 0,
  receipt_pending INTEGER DEFAULT 0,
  notes TEXT DEFAULT '',
  created_at INTEGER, updated_at INTEGER);
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS log(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts INTEGER, kind TEXT, detail TEXT);
"""


class Store:
    def __init__(self, path):
        self.path = path
        d = os.path.dirname(path)
        if d:
            os.makedirs(d, exist_ok=True)
        with self._conn() as c:
            c.executescript(SCHEMA)

    def _conn(self):
        c = sqlite3.connect(self.path)
        c.row_factory = sqlite3.Row
        return c

    # ── invoices / انبار ──────────────────────────────
    def add_invoice(self, trade, no, total, items, photo="", source="chat"):
        with self._conn() as c:
            cur = c.execute(
                "INSERT INTO invoices(trade,no,total,items,photo,source,created_at)"
                " VALUES(?,?,?,?,?,?,?)",
                (trade, no, total,
                 json.dumps(items, ensure_ascii=False), photo, source,
                 int(time.time())),
            )
            return cur.lastrowid

    def last_invoice(self):
        with self._conn() as c:
            r = c.execute("SELECT * FROM invoices ORDER BY id DESC LIMIT 1").fetchone()
            if r is None:
                return None
            d = dict(r)
            d["items"] = json.loads(d.get("items") or "[]")
            return d

    def invoice_count(self):
        with self._conn() as c:
            return c.execute("SELECT COUNT(*) FROM invoices").fetchone()[0]

    # ── reminders / یادآورها ─────────────────────────
    def add_reminder(self, customer, chat_id, text, remind_at):
        with self._conn() as c:
            cur = c.execute(
                "INSERT INTO reminders(customer,chat_id,text,remind_at,created_at)"
                " VALUES(?,?,?,?,?)",
                (customer, chat_id, text, int(remind_at), int(time.time())),
            )
            return cur.lastrowid

    def due_reminders(self, now=None):
        now = int(now if now is not None else time.time())
        with self._conn() as c:
            rows = c.execute(
                "SELECT * FROM reminders WHERE done=0 AND remind_at<=? ORDER BY remind_at",
                (now,),
            ).fetchall()
            return [dict(r) for r in rows]

    def mark_reminder(self, rid):
        with self._conn() as c:
            c.execute("UPDATE reminders SET done=1 WHERE id=?", (rid,))

    def bump_reminder(self, rid):
        """یک تلاش ناموفق ثبت می‌کند؛ تعداد تلاش‌ها برمی‌گردد."""
        with self._conn() as c:
            c.execute("UPDATE reminders SET attempts=attempts+1 WHERE id=?", (rid,))
            r = c.execute("SELECT attempts FROM reminders WHERE id=?", (rid,)).fetchone()
            return r["attempts"] if r else 0

    # ── customers / مشتریان ──────────────────────────
    def upsert_customer(self, chat_id, name="", phone=""):
        with self._conn() as c:
            row = c.execute("SELECT * FROM customers WHERE chat_id=?", (chat_id,)).fetchone()
            if row is None:
                c.execute(
                    "INSERT INTO customers(chat_id,name,phone,created_at) VALUES(?,?,?,?)",
                    (chat_id, name, phone, int(time.time())),
                )
            else:
                c.execute(
                    "UPDATE customers SET name=?, phone=? WHERE chat_id=?",
                    (name or row["name"], phone or row["phone"], chat_id),
                )

    # ── accounts (سابک/اعتبار — باتری نمادی) ────────────
    def upsert_account(self, chat_id, **kw):
        cols = ("name", "shop", "trade", "city", "phone", "n_customers",
                "n_items", "status", "plan", "verification", "period_end",
                "units_total", "units_left", "last_warn", "receipt_pending",
                "notes")
        now = int(time.time())
        with self._conn() as c:
            c.execute("INSERT OR IGNORE INTO accounts(chat_id, created_at, updated_at)"
                      " VALUES(?,?,?)", (chat_id, now, now))
            sets = [k for k in kw if k in cols]
            if sets:
                sql = "UPDATE accounts SET updated_at=?,%s WHERE chat_id=?" % (
                    ",".join('"%s"=?' % s for s in sets))
                c.execute(sql, [now] + [kw[s] for s in sets] + [chat_id])
        return self.get_account(chat_id)

    def get_account(self, chat_id):
        with self._conn() as c:
            r = c.execute("SELECT * FROM accounts WHERE chat_id=?",
                          (chat_id,)).fetchone()
            return dict(r) if r is not None else None

    def account_by_name(self, name):
        name = (name or "").strip()
        if not name:
            return None
        with self._conn() as c:
            r = c.execute("SELECT * FROM accounts WHERE name=? COLLATE NOCASE"
                          " OR shop=? COLLATE NOCASE LIMIT 1", (name, name)).fetchone()
            return dict(r) if r is not None else None

    def list_accounts(self):
        with self._conn() as c:
            rows = c.execute("SELECT * FROM accounts ORDER BY updated_at DESC").fetchall()
            return [dict(r) for r in rows]

    def charge_units(self, chat_id, delta):
        """کسری/اضافه‌کردن واحدِ باتری. برگردان: واحدهای باقی‌مانده (>=0)."""
        with self._conn() as c:
            r = c.execute("SELECT units_left FROM accounts WHERE chat_id=?",
                          (chat_id,)).fetchone()
            if r is None:
                return 0.0
            new_left = max(0.0, (r["units_left"] or 0) - delta)
            c.execute("UPDATE accounts SET units_left=?, updated_at=? WHERE chat_id=?",
                      (new_left, int(time.time()), chat_id))
            return new_left

    def add_units(self, chat_id, units):
        with self._conn() as c:
            c.execute("UPDATE accounts SET units_left=units_left+?, updated_at=?"
                      " WHERE chat_id=?", (units, int(time.time()), chat_id))
        a = self.get_account(chat_id)
        return (a or {}).get("units_left", 0.0)

    def get_customer(self, chat_id):
        with self._conn() as c:
            r = c.execute("SELECT * FROM customers WHERE chat_id=?", (chat_id,)).fetchone()
            return dict(r) if r else None

    # ── credits / نسیه و نردبان اعتبار ────────────────
    def get_setting(self, key, default=None):
        with self._conn() as c:
            r = c.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
            return r["value"] if r else default

    def set_setting(self, key, value):
        with self._conn() as c:
            c.execute("INSERT INTO settings(key,value) VALUES(?,?) "
                      "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, str(value)))

    def credit_cap(self):
        v = self.get_setting("credit_cap")
        try:
            return int(v) if v else 50000000
        except ValueError:
            return 50000000

    def add_credit(self, customer, chat_id, amount, due, approved=False):
        with self._conn() as c:
            cur = c.execute(
                "INSERT INTO credits(customer,chat_id,amount,paid,due,status,created_at)"
                " VALUES(?,?,?,0,?,?,?)",
                (customer, chat_id, amount, due,
                 "approved" if approved else "open", int(time.time())))
            return cur.lastrowid

    def credit_balance(self, customer):
        with self._conn() as c:
            r = c.execute(
                "SELECT COALESCE(SUM(amount-paid),0) AS b FROM credits "
                "WHERE customer=? AND status IN ('open','approved')", (customer,)).fetchone()
            return r["b"] if r else 0

    def pay_credit(self, customer, amount):
        """amount را از قدیمی‌ترین نسیه‌ها کم می‌کند؛ برگردان: مجموع کسرشده"""
        done = 0
        with self._conn() as c:
            rows = c.execute(
                "SELECT id, amount-paid AS rest FROM credits WHERE customer=?"
                " AND status IN ('open','approved') AND paid<amount ORDER BY id",
                (customer,)).fetchall()
            for row in rows:
                take = min(row["rest"], amount - done)
                c.execute("UPDATE credits SET paid=paid+? WHERE id=?", (take, row["id"]))
                done += take
                if done >= amount:
                    break
        return done

    def due_credits(self, start, end=None):
        end = end if end is not None else start + 86400
        with self._conn() as c:
            rows = c.execute(
                "SELECT * FROM credits WHERE status IN ('open','approved') "
                "AND paid<amount AND due BETWEEN ? AND ? ORDER BY due", (start, end)).fetchall()
            return [dict(r) for r in rows]

    def overdue_credits(self, now=None):
        now = int(now if now is not None else time.time())
        with self._conn() as c:
            rows = c.execute(
                "SELECT * FROM credits WHERE status IN ('open','approved') "
                "AND paid<amount AND due<? ORDER BY due", (now,)).fetchall()
            return [dict(r) for r in rows]

    def invoices_since(self, ts):
        with self._conn() as c:
            rows = c.execute(
                "SELECT * FROM invoices WHERE created_at>=? ORDER BY id", (int(ts),)).fetchall()
            out = []
            for r in rows:
                d = dict(r)
                d["items"] = json.loads(d.get("items") or "[]")
                out.append(d)
            return out

    # ── pending / تأیید مالک (اصل ۲ سرلوحه) ───────────
    def add_pending(self, chat_id, kind, payload, ttl=600):
        with self._conn() as c:
            now = int(time.time())
            c.execute("DELETE FROM pending WHERE chat_id=? OR expires<=?", (chat_id, now))
            cur = c.execute(
                "INSERT INTO pending(chat_id,kind,payload,created_at,expires)"
                " VALUES(?,?,?,?,?)",
                (chat_id, kind, json.dumps(payload, ensure_ascii=False), now, now + ttl))
            return cur.lastrowid

    def pop_pending(self, chat_id):
        with self._conn() as c:
            now = int(time.time())
            c.execute("DELETE FROM pending WHERE expires<=?", (now,))
            r = c.execute(
                "SELECT * FROM pending WHERE chat_id=? ORDER BY id DESC LIMIT 1",
                (chat_id,)).fetchone()
            if r is None:
                return None
            d = dict(r)
            c.execute("DELETE FROM pending WHERE id=?", (r["id"],))
            d["payload"] = json.loads(d.get("payload") or "{}")
            return d

    # ── log / رویدادها (برای «مشکلی احدا نکند») ───────
    def prune_log(self, days=30):
        """مسیر رشد بی‌پایانِ log (issue #7): قدیمی‌تر از N روز حذف می‌شود."""
        try:
            with self._conn() as c:
                c.execute("DELETE FROM log WHERE ts < ?",
                          (int(time.time()) - days * 86400,))
        except Exception:
            pass

    def log(self, kind, detail):
        try:
            with self._conn() as c:
                c.execute("INSERT INTO log(ts,kind,detail) VALUES(?,?,?)",
                          (int(time.time()), kind, str(detail)[:500]))
        except Exception:
            pass
