"""Data-access layer: plain functions over SQLite (see db.py) returning
lightweight Record objects that support both dict-style and dot-style
attribute access, so templates can write `employee.name` the same way they
would against an ORM model."""

from datetime import datetime, date, time, timedelta
from werkzeug.security import generate_password_hash, check_password_hash

import db as dbmod

MEAL_TYPES = ["Breakfast", "Lunch", "Snacks", "Dinner"]
MEAL_TYPE_FOOD_TYPES = {
    "Breakfast": ["Veg", "Non-Veg"],
    "Lunch": ["Veg", "Non-Veg"],
    "Snacks": ["Snacks"],
    "Dinner": ["Veg", "Non-Veg"],
}

PLANTS = ["1250 TPD Plant", "2000 TPD Plant"]

# Per-meal booking cutoffs — all five values are admin-configurable from
# Admin > Settings (see routes_admin.settings_page). Breakfast is booked the
# evening before, so it's expressed as "N hours before a same-date reference
# time" (default: 12 hours before 6:00 AM -> cutoff is 6:00 PM the previous
# day). Lunch, Snacks and Dinner cut off at a fixed clock time on the
# booking date itself.
CUTOFF_SETTING_KEYS = (
    "breakfast_cutoff_hours_before",
    "breakfast_reference_time",
    "lunch_cutoff_time",
    "snacks_cutoff_time",
    "dinner_cutoff_time",
)

_MEAL_CUTOFF_TIME_KEY = {
    "Lunch": "lunch_cutoff_time",
    "Snacks": "snacks_cutoff_time",
    "Dinner": "dinner_cutoff_time",
}

DEFAULT_SETTINGS = {
    "report_admin_email": "",
    "company_name": "Our Plant",
    "breakfast_cutoff_hours_before": "12",
    "breakfast_reference_time": "06:00",
    "lunch_cutoff_time": "08:00",
    "snacks_cutoff_time": "16:00",
    "dinner_cutoff_time": "18:00",
    # One "already sent today" marker per automated meal report — see
    # scheduler.py. Each fires 5 minutes after its meal's booking cutoff.
    "report_last_sent_lunch_date": "",
    "report_last_sent_snacks_date": "",
    "report_last_sent_dinner_breakfast_date": "",
}


def _iso_to_date(s):
    return datetime.strptime(s, "%Y-%m-%d").date() if s else None


def _iso_to_datetime(s):
    return datetime.strptime(s, "%Y-%m-%d %H:%M:%S") if s else None


class Record:
    """Generic attribute-accessible wrapper around a dict of column values."""
    def __init__(self, **fields):
        self.__dict__["_fields"] = fields

    def __getattr__(self, name):
        try:
            return self._fields[name]
        except KeyError:
            raise AttributeError(name)

    def __setattr__(self, name, value):
        self._fields[name] = value

    def get(self, name, default=None):
        return self._fields.get(name, default)


# ------------------------------------------------------------------ Employee

def _row_to_employee(row):
    if row is None:
        return None
    return Record(
        id=row["id"], employee_code=row["employee_code"], name=row["name"],
        age=row["age"], sex=row["sex"], department=row["department"],
        food_preference=row["food_preference"], plant=row["plant"], is_active=bool(row["is_active"]),
    )


def create_employee(employee_code, name, department, age=None, sex=None, food_preference="Veg", plant=None):
    now = datetime.utcnow().isoformat(timespec="seconds")
    plant = plant or PLANTS[0]
    emp_id = dbmod.execute(
        "INSERT INTO employees (employee_code, name, age, sex, department, food_preference, plant, is_active, created_at) "
        "VALUES (?,?,?,?,?,?,?,1,?)",
        (employee_code, name, age, sex, department, food_preference, plant, now),
    )
    return emp_id


def get_employee(emp_id):
    return _row_to_employee(dbmod.query("SELECT * FROM employees WHERE id=?", (emp_id,), one=True))


def get_employee_by_code(code):
    return _row_to_employee(dbmod.query("SELECT * FROM employees WHERE employee_code=?", (code,), one=True))


def list_employees():
    rows = dbmod.query("SELECT * FROM employees ORDER BY department, name")
    return [_row_to_employee(r) for r in rows]


def list_departments():
    rows = dbmod.query("SELECT DISTINCT department FROM employees ORDER BY department")
    return [r["department"] for r in rows]


def update_employee(emp_id, name, age, sex, department, food_preference, plant):
    dbmod.execute(
        "UPDATE employees SET name=?, age=?, sex=?, department=?, food_preference=?, plant=? WHERE id=?",
        (name, age, sex, department, food_preference, plant, emp_id),
    )


def set_employee_preference(emp_id, food_preference):
    dbmod.execute("UPDATE employees SET food_preference=? WHERE id=?", (food_preference, emp_id))


def toggle_employee_active(emp_id):
    emp = get_employee(emp_id)
    new_val = 0 if emp.is_active else 1
    dbmod.execute("UPDATE employees SET is_active=? WHERE id=?", (new_val, emp_id))
    dbmod.execute("UPDATE users SET is_active=? WHERE employee_id=?", (new_val, emp_id))
    return bool(new_val)


# ----------------------------------------------------------------------- User

def _row_to_user(row):
    if row is None:
        return None
    return Record(
        id=row["id"], username=row["username"], password_hash=row["password_hash"],
        role=row["role"], employee_id=row["employee_id"], is_active=bool(row["is_active"]),
        last_login=row["last_login"],
    )


def create_user(username, password, role="employee", employee_id=None):
    now = datetime.utcnow().isoformat(timespec="seconds")
    return dbmod.execute(
        "INSERT INTO users (username, password_hash, role, employee_id, is_active, created_at) VALUES (?,?,?,?,1,?)",
        (username, generate_password_hash(password), role, employee_id, now),
    )


def get_user(user_id):
    return _row_to_user(dbmod.query("SELECT * FROM users WHERE id=?", (user_id,), one=True))


def get_user_by_username(username):
    return _row_to_user(dbmod.query("SELECT * FROM users WHERE username=?", (username,), one=True))


def check_user_password(user, raw_password):
    return check_password_hash(user.password_hash, raw_password)


def set_user_password(user_id, raw_password):
    dbmod.execute("UPDATE users SET password_hash=? WHERE id=?", (generate_password_hash(raw_password), user_id))


def touch_last_login(user_id):
    dbmod.execute("UPDATE users SET last_login=? WHERE id=?", (datetime.utcnow().isoformat(timespec="seconds"), user_id))


# ------------------------------------------------------------------ FoodItem

def _row_to_fooditem(row):
    if row is None:
        return None
    return Record(
        id=row["id"], meal_type=row["meal_type"], food_type=row["food_type"],
        item_name=row["item_name"], is_active=bool(row["is_active"]),
    )


def add_or_reactivate_food_item(meal_type, food_type, item_name):
    existing = dbmod.query(
        "SELECT * FROM food_items WHERE meal_type=? AND food_type=? AND item_name=?",
        (meal_type, food_type, item_name), one=True,
    )
    if existing:
        dbmod.execute("UPDATE food_items SET is_active=1 WHERE id=?", (existing["id"],))
        return False  # was a re-activation, not a new item
    now = datetime.utcnow().isoformat(timespec="seconds")
    dbmod.execute(
        "INSERT INTO food_items (meal_type, food_type, item_name, is_active, created_at) VALUES (?,?,?,1,?)",
        (meal_type, food_type, item_name, now),
    )
    return True


def list_food_items(meal_type=None, food_type=None, active_only=True):
    sql = "SELECT * FROM food_items WHERE 1=1"
    args = []
    if meal_type:
        sql += " AND meal_type=?"
        args.append(meal_type)
    if food_type:
        sql += " AND food_type=?"
        args.append(food_type)
    if active_only:
        sql += " AND is_active=1"
    sql += " ORDER BY meal_type, food_type, item_name"
    return [_row_to_fooditem(r) for r in dbmod.query(sql, args)]


def get_food_items_grouped():
    items = list_food_items(active_only=False)
    grouped = {}
    for it in items:
        grouped.setdefault(it.meal_type, {}).setdefault(it.food_type, []).append(it)
    return grouped


def toggle_food_item(item_id):
    row = dbmod.query("SELECT * FROM food_items WHERE id=?", (item_id,), one=True)
    new_val = 0 if row["is_active"] else 1
    dbmod.execute("UPDATE food_items SET is_active=? WHERE id=?", (new_val, item_id))
    return _row_to_fooditem(dbmod.query("SELECT * FROM food_items WHERE id=?", (item_id,), one=True))


def delete_food_item(item_id):
    dbmod.execute("DELETE FROM food_items WHERE id=?", (item_id,))


# ------------------------------------------------------------------- Booking

def _row_to_booking(row):
    if row is None:
        return None
    r = Record(
        id=row["id"],
        booked_at=_iso_to_datetime(row["booked_at"]) if " " in (row["booked_at"] or "") else row["booked_at"],
        booker_user_id=row["booker_user_id"],
        employee_id=row["employee_id"],
        target=row["target"],
        booking_date=_iso_to_date(row["booking_date"]),
        meal_type=row["meal_type"],
        food_type=row["food_type"],
        item_name=row["item_name"],
        quantity=row["quantity"],
        department=row["department"],
        plant=row["plant"],
        guest_classification=row["guest_classification"],
        guest_note=row["guest_note"],
        status=row["status"],
    )
    # attach related employee / booker lazily as plain attributes
    r.employee = get_employee(row["employee_id"]) if row["employee_id"] else None
    booker = get_user(row["booker_user_id"])
    r.booker = booker
    return r


def create_self_booking(booker_user_id, employee_id, department, plant, booking_date, meal_type, food_type, item_name):
    """One active Self booking per employee/date/meal — re-booking updates it in place."""
    existing = dbmod.query(
        "SELECT * FROM bookings WHERE employee_id=? AND booking_date=? AND meal_type=? AND target='Self' AND status='active'",
        (employee_id, booking_date, meal_type), one=True,
    )
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    if existing:
        dbmod.execute(
            "UPDATE bookings SET food_type=?, item_name=?, plant=?, booked_at=? WHERE id=?",
            (food_type, item_name, plant, now, existing["id"]),
        )
        return existing["id"]
    return dbmod.execute(
        "INSERT INTO bookings (booked_at, booker_user_id, employee_id, target, booking_date, meal_type, "
        "food_type, item_name, quantity, department, plant, status) VALUES (?,?,?,?,?,?,?,?,1,?,?,?)",
        (now, booker_user_id, employee_id, "Self", booking_date, meal_type, food_type, item_name, department, plant, "active"),
    )


def create_guest_booking(booker_user_id, employee_id, department, plant, booking_date, meal_type, food_type,
                          item_name, quantity, guest_classification, guest_note):
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    return dbmod.execute(
        "INSERT INTO bookings (booked_at, booker_user_id, employee_id, target, booking_date, meal_type, "
        "food_type, item_name, quantity, department, plant, guest_classification, guest_note, status) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (now, booker_user_id, employee_id, "Guest", booking_date, meal_type, food_type, item_name,
         quantity, department, plant, guest_classification, guest_note, "active"),
    )


def get_booking(booking_id):
    return _row_to_booking(dbmod.query("SELECT * FROM bookings WHERE id=?", (booking_id,), one=True))


def cancel_booking(booking_id):
    dbmod.execute("UPDATE bookings SET status='cancelled' WHERE id=?", (booking_id,))


def list_bookings(start_date=None, end_date=None, department=None, target=None,
                   status="active", employee_id=None, booker_user_id=None, for_user_or_employee=None, plant=None,
                   meal_type=None):
    sql = "SELECT * FROM bookings WHERE 1=1"
    args = []
    if start_date:
        sql += " AND booking_date >= ?"
        args.append(start_date.isoformat() if hasattr(start_date, "isoformat") else start_date)
    if end_date:
        sql += " AND booking_date <= ?"
        args.append(end_date.isoformat() if hasattr(end_date, "isoformat") else end_date)
    if department:
        sql += " AND department = ?"
        args.append(department)
    if plant:
        sql += " AND plant = ?"
        args.append(plant)
    if target:
        sql += " AND target = ?"
        args.append(target)
    if meal_type:
        sql += " AND meal_type = ?"
        args.append(meal_type)
    if status:
        sql += " AND status = ?"
        args.append(status)
    if employee_id:
        sql += " AND employee_id = ?"
        args.append(employee_id)
    if booker_user_id:
        sql += " AND booker_user_id = ?"
        args.append(booker_user_id)
    if for_user_or_employee:
        user_id, emp_id = for_user_or_employee
        if emp_id:
            sql += " AND (booker_user_id = ? OR (employee_id = ? AND target = 'Self'))"
            args.extend([user_id, emp_id])
        else:
            sql += " AND booker_user_id = ?"
            args.append(user_id)
    sql += " ORDER BY booking_date DESC, meal_type, department"
    return [_row_to_booking(r) for r in dbmod.query(sql, args)]


def booking_to_dict(b):
    return {
        "id": b.id,
        "booked_at": b.booked_at.strftime("%Y-%m-%d %H:%M") if hasattr(b.booked_at, "strftime") else b.booked_at,
        "booker": b.booker.username if b.booker else None,
        "employee_code": b.employee.employee_code if b.employee else None,
        "employee_name": b.employee.name if b.employee else None,
        "target": b.target,
        "booking_date": b.booking_date.isoformat(),
        "meal_type": b.meal_type,
        "food_type": b.food_type,
        "item_name": b.item_name,
        "quantity": b.quantity,
        "department": b.department,
        "plant": b.plant,
        "guest_classification": b.guest_classification,
        "guest_note": b.guest_note,
        "status": b.status,
    }


# ------------------------------------------------------------------ Settings

def get_setting(key, default=""):
    row = dbmod.query("SELECT value FROM settings WHERE key=?", (key,), one=True)
    return row["value"] if row and row["value"] is not None else default


def set_setting(key, value):
    dbmod.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value),
    )


def get_all_settings():
    rows = dbmod.query("SELECT key, value FROM settings")
    return {r["key"]: r["value"] for r in rows}


# ------------------------------------------------------------ Booking cutoffs

def _parse_hhmm(raw, fallback_key):
    """Parses an 'HH:MM' string into a time object, falling back to the
    matching DEFAULT_SETTINGS value if raw is missing or malformed (e.g. an
    old/blank setting) rather than letting a bad value break booking."""
    for candidate in (raw, DEFAULT_SETTINGS.get(fallback_key)):
        if not candidate:
            continue
        try:
            h, m = candidate.split(":")
            return time(int(h), int(m))
        except (ValueError, AttributeError):
            continue
    return time(0, 0)


def get_cutoff_settings():
    """The five admin-configurable cutoff values, as native types, with
    DEFAULT_SETTINGS as the fallback for anything unset or invalid."""
    settings = get_all_settings()

    hours_before_raw = settings.get("breakfast_cutoff_hours_before")
    try:
        hours_before = int(hours_before_raw)
    except (TypeError, ValueError):
        hours_before = int(DEFAULT_SETTINGS["breakfast_cutoff_hours_before"])

    return {
        "breakfast_cutoff_hours_before": hours_before,
        "breakfast_reference_time": settings.get("breakfast_reference_time") or DEFAULT_SETTINGS["breakfast_reference_time"],
        "lunch_cutoff_time": settings.get("lunch_cutoff_time") or DEFAULT_SETTINGS["lunch_cutoff_time"],
        "snacks_cutoff_time": settings.get("snacks_cutoff_time") or DEFAULT_SETTINGS["snacks_cutoff_time"],
        "dinner_cutoff_time": settings.get("dinner_cutoff_time") or DEFAULT_SETTINGS["dinner_cutoff_time"],
    }


def get_meal_cutoff_datetime(meal_type, booking_date, cutoffs=None):
    """The exact moment booking closes for `meal_type` on `booking_date` (a
    date object). Returns None for an unrecognized meal_type."""
    cutoffs = cutoffs or get_cutoff_settings()

    if meal_type == "Breakfast":
        ref_time = _parse_hhmm(cutoffs["breakfast_reference_time"], "breakfast_reference_time")
        reference = datetime.combine(booking_date, ref_time)
        return reference - timedelta(hours=cutoffs["breakfast_cutoff_hours_before"])

    key = _MEAL_CUTOFF_TIME_KEY.get(meal_type)
    if not key:
        return None
    cutoff_time = _parse_hhmm(cutoffs[key], key)
    return datetime.combine(booking_date, cutoff_time)


def is_booking_open(meal_type, booking_date, now=None, cutoffs=None):
    """True if `meal_type` can still be booked for `booking_date` right now
    (or at `now`, if given — pass one shared timestamp when checking several
    dates in the same request so they're all judged consistently)."""
    cutoff_dt = get_meal_cutoff_datetime(meal_type, booking_date, cutoffs=cutoffs)
    if cutoff_dt is None:
        return True
    return (now or datetime.now()) < cutoff_dt


def _format_12h(t):
    return t.strftime("%I:%M %p").lstrip("0")


def meal_cutoff_description(meal_type, cutoffs=None):
    """Human-readable explanation of when `meal_type` bookings close, shown
    to employees in the booking UI and to admins on the settings page."""
    cutoffs = cutoffs or get_cutoff_settings()

    if meal_type == "Breakfast":
        ref_time = _parse_hhmm(cutoffs["breakfast_reference_time"], "breakfast_reference_time")
        cutoff_time = (datetime.combine(date(2000, 1, 2), ref_time) - timedelta(hours=cutoffs["breakfast_cutoff_hours_before"])).time()
        return (
            f"Closes {cutoffs['breakfast_cutoff_hours_before']} hour(s) before {_format_12h(ref_time)} — "
            f"i.e. by {_format_12h(cutoff_time)} the day before."
        )

    key = _MEAL_CUTOFF_TIME_KEY.get(meal_type)
    if not key:
        return ""
    t = _parse_hhmm(cutoffs[key], key)
    return f"Closes {_format_12h(t)} on the same day."


def meal_cutoff_config_for_js(cutoffs=None):
    """Shape consumed by booking.js so the browser can compute, for any
    candidate date, whether a meal's cutoff has passed — without a server
    round trip per date."""
    cutoffs = cutoffs or get_cutoff_settings()
    return {
        "Breakfast": {
            "type": "before_reference",
            "hours_before": cutoffs["breakfast_cutoff_hours_before"],
            "reference_time": cutoffs["breakfast_reference_time"],
            "description": meal_cutoff_description("Breakfast", cutoffs),
        },
        "Lunch": {
            "type": "same_day",
            "cutoff_time": cutoffs["lunch_cutoff_time"],
            "description": meal_cutoff_description("Lunch", cutoffs),
        },
        "Snacks": {
            "type": "same_day",
            "cutoff_time": cutoffs["snacks_cutoff_time"],
            "description": meal_cutoff_description("Snacks", cutoffs),
        },
        "Dinner": {
            "type": "same_day",
            "cutoff_time": cutoffs["dinner_cutoff_time"],
            "description": meal_cutoff_description("Dinner", cutoffs),
        },
    }
