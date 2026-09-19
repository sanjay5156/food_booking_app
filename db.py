"""Thin SQLite data layer. No ORM — the app is deliberately built on nothing
but Python's standard library (sqlite3) plus Flask, so it installs and runs
on a locked-down office PC or intranet server with no extra dependencies."""

import sqlite3
import os
from flask import g, current_app

SCHEMA = """
CREATE TABLE IF NOT EXISTS employees (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  employee_code TEXT UNIQUE NOT NULL,
  name TEXT NOT NULL,
  age INTEGER,
  sex TEXT,
  department TEXT NOT NULL,
  food_preference TEXT NOT NULL DEFAULT 'Veg',
  plant TEXT NOT NULL DEFAULT '1250 TPD Plant',
  is_active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'employee',
  employee_id INTEGER REFERENCES employees(id),
  is_active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL,
  last_login TEXT
);

CREATE TABLE IF NOT EXISTS food_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  meal_type TEXT NOT NULL,
  food_type TEXT NOT NULL,
  item_name TEXT NOT NULL,
  is_active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL,
  UNIQUE(meal_type, food_type, item_name)
);

CREATE TABLE IF NOT EXISTS bookings (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  booked_at TEXT NOT NULL,
  booker_user_id INTEGER NOT NULL REFERENCES users(id),
  employee_id INTEGER REFERENCES employees(id),
  target TEXT NOT NULL,
  booking_date TEXT NOT NULL,
  meal_type TEXT NOT NULL,
  food_type TEXT NOT NULL,
  item_name TEXT,
  quantity INTEGER NOT NULL DEFAULT 1,
  department TEXT NOT NULL,
  plant TEXT NOT NULL DEFAULT '1250 TPD Plant',
  guest_classification TEXT,
  guest_note TEXT,
  status TEXT NOT NULL DEFAULT 'active'
);
CREATE INDEX IF NOT EXISTS idx_bookings_date ON bookings(booking_date);

CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY,
  value TEXT
);
"""


def get_db():
    if "db" not in g:
        db_path = current_app.config["DATABASE_PATH"]
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        g.db = sqlite3.connect(db_path)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def _column_exists(db, table, column):
    cols = [row["name"] for row in db.execute(f"PRAGMA table_info({table})")]
    return column in cols


def _migrate(db):
    """Lightweight, additive-only migrations for installs that already have
    a data file from before a column existed — so upgrading never loses
    existing employees or bookings."""
    if not _column_exists(db, "employees", "plant"):
        db.execute("ALTER TABLE employees ADD COLUMN plant TEXT NOT NULL DEFAULT '1250 TPD Plant'")
    if not _column_exists(db, "bookings", "plant"):
        db.execute("ALTER TABLE bookings ADD COLUMN plant TEXT NOT NULL DEFAULT '1250 TPD Plant'")
    db.commit()


def init_db(app):
    app.teardown_appcontext(close_db)
    with app.app_context():
        db = get_db()
        db.executescript(SCHEMA)
        db.commit()
        _migrate(db)


def query(sql, args=(), one=False):
    cur = get_db().execute(sql, args)
    rows = cur.fetchall()
    cur.close()
    return (rows[0] if rows else None) if one else rows


def execute(sql, args=()):
    db = get_db()
    cur = db.execute(sql, args)
    db.commit()
    last_id = cur.lastrowid
    cur.close()
    return last_id
