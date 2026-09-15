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
  remind_at INTEGER, done INTEGER DEFAULT 0, created_at INTEGER);
CREATE TABLE IF NOT EXISTS customers(
  chat_id INTEGER PRIMARY KEY, name TEXT, phone TEXT, created_at INTEGER);
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

    def get_customer(self, chat_id):
        with self._conn() as c:
            r = c.execute("SELECT * FROM customers WHERE chat_id=?", (chat_id,)).fetchone()
            return dict(r) if r else None

    # ── log / رویدادها (برای «مشکلی احدا نکند») ───────
    def log(self, kind, detail):
        try:
            with self._conn() as c:
                c.execute("INSERT INTO log(ts,kind,detail) VALUES(?,?,?)",
                          (int(time.time()), kind, str(detail)[:500]))
        except Exception:
            pass
