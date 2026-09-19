from datetime import date, time as time_cls

from flask import Blueprint, render_template, request, flash, redirect, url_for

import models
from auth import login_required, admin_required
from models import MEAL_TYPES, MEAL_TYPE_FOOD_TYPES, PLANTS
from scheduler import REPORT_KEYS, REPORT_LABELS, trigger_time_display

admin_bp = Blueprint("admin", __name__)


@admin_bp.route("/admin/dashboard")
@login_required
@admin_required
def dashboard():
    today = date.today()
    today_bookings = models.list_bookings(start_date=today, end_date=today, status="active")
    total_today = sum(b.quantity for b in today_bookings)
    self_today = sum(b.quantity for b in today_bookings if b.target == "Self")
    guest_today = sum(b.quantity for b in today_bookings if b.target == "Guest")
    employee_count = len([e for e in models.list_employees() if e.is_active])
    food_item_count = len(models.list_food_items(active_only=True))

    return render_template(
        "admin_dashboard.html",
        today=today, total_today=total_today, self_today=self_today,
        guest_today=guest_today, employee_count=employee_count,
        food_item_count=food_item_count,
    )


# ---------------------------------------------------------------- Employees

@admin_bp.route("/admin/employees")
@login_required
@admin_required
def employees_list():
    employees = models.list_employees()
    return render_template("admin_employees.html", employees=employees, plants=PLANTS)


@admin_bp.route("/admin/employees/add", methods=["POST"])
@login_required
@admin_required
def employees_add():
    code = request.form.get("employee_code", "").strip().upper()
    name = request.form.get("name", "").strip()
    age = request.form.get("age") or None
    sex = request.form.get("sex", "").strip()
    department = request.form.get("department", "").strip()
    food_preference = request.form.get("food_preference", "Veg")
    plant = request.form.get("plant", PLANTS[0])

    if not code or not name or not department:
        flash("Employee ID, Name and Department are required.", "error")
        return redirect(url_for("admin.employees_list"))

    if models.get_employee_by_code(code):
        flash(f"Employee ID {code} already exists.", "error")
        return redirect(url_for("admin.employees_list"))

    emp_id = models.create_employee(
        employee_code=code, name=name, department=department,
        age=int(age) if age else None, sex=sex, food_preference=food_preference, plant=plant,
    )

    # Auto-create a login account (username = employee code, default password = employee code)
    if not models.get_user_by_username(code):
        models.create_user(username=code, password=code, role="employee", employee_id=emp_id)

    flash(f"Employee {name} ({code}) added. Default login password is their Employee ID.", "success")
    return redirect(url_for("admin.employees_list"))


@admin_bp.route("/admin/employees/<int:emp_id>/edit", methods=["POST"])
@login_required
@admin_required
def employees_edit(emp_id):
    emp = models.get_employee(emp_id)
    if not emp:
        flash("Employee not found.", "error")
        return redirect(url_for("admin.employees_list"))

    name = request.form.get("name", emp.name).strip()
    age_raw = request.form.get("age")
    age = int(age_raw) if age_raw else emp.age
    sex = request.form.get("sex", emp.sex).strip()
    department = request.form.get("department", emp.department).strip()
    food_preference = request.form.get("food_preference", emp.food_preference)
    plant = request.form.get("plant", emp.plant)

    models.update_employee(emp_id, name, age, sex, department, food_preference, plant)
    flash(f"Employee {emp.employee_code} updated.", "success")
    return redirect(url_for("admin.employees_list"))


@admin_bp.route("/admin/employees/<int:emp_id>/toggle", methods=["POST"])
@login_required
@admin_required
def employees_toggle(emp_id):
    emp = models.get_employee(emp_id)
    if not emp:
        flash("Employee not found.", "error")
        return redirect(url_for("admin.employees_list"))
    now_active = models.toggle_employee_active(emp_id)
    flash(f"Employee {emp.employee_code} is now {'active' if now_active else 'inactive'}.", "success")
    return redirect(url_for("admin.employees_list"))


# --------------------------------------------------------------- Food items

@admin_bp.route("/admin/food-items")
@login_required
@admin_required
def food_items_list():
    grouped = models.get_food_items_grouped()
    return render_template(
        "admin_food_items.html", grouped=grouped,
        meal_types=MEAL_TYPES, meal_type_food_types=MEAL_TYPE_FOOD_TYPES,
    )


@admin_bp.route("/admin/food-items/add", methods=["POST"])
@login_required
@admin_required
def food_items_add():
    meal_type = request.form.get("meal_type")
    food_type = request.form.get("food_type")
    item_name = request.form.get("item_name", "").strip()

    if meal_type not in MEAL_TYPE_FOOD_TYPES or food_type not in MEAL_TYPE_FOOD_TYPES.get(meal_type, []):
        flash("Invalid meal type / food type combination.", "error")
        return redirect(url_for("admin.food_items_list"))
    if not item_name:
        flash("Item name is required.", "error")
        return redirect(url_for("admin.food_items_list"))

    is_new = models.add_or_reactivate_food_item(meal_type, food_type, item_name)
    flash(
        f"'{item_name}' {'added' if is_new else 're-activated'} under {meal_type} / {food_type}.",
        "success",
    )
    return redirect(url_for("admin.food_items_list"))


@admin_bp.route("/admin/food-items/<int:item_id>/toggle", methods=["POST"])
@login_required
@admin_required
def food_items_toggle(item_id):
    item = models.toggle_food_item(item_id)
    flash(f"'{item.item_name}' is now {'active' if item.is_active else 'inactive'}.", "success")
    return redirect(url_for("admin.food_items_list"))


@admin_bp.route("/admin/food-items/<int:item_id>/delete", methods=["POST"])
@login_required
@admin_required
def food_items_delete(item_id):
    models.delete_food_item(item_id)
    flash("Item deleted.", "success")
    return redirect(url_for("admin.food_items_list"))


# ---------------------------------------------------------------- Settings

_CUTOFF_TIME_FIELDS = {
    "breakfast_reference_time": "Breakfast reference time",
    "lunch_cutoff_time": "Lunch cutoff time",
    "snacks_cutoff_time": "Snacks cutoff time",
    "dinner_cutoff_time": "Dinner cutoff time",
}


@admin_bp.route("/admin/settings", methods=["GET", "POST"])
@login_required
@admin_required
def settings_page():
    if request.method == "POST":
        # Two independent forms share this page (report settings, booking
        # cutoffs) — a hidden "form" field says which one was submitted, so
        # saving one never blanks out the other's fields.
        which = request.form.get("form", "report")

        if which == "cutoffs":
            # Validated up front so a malformed value can never silently
            # break the booking cutoff checks.
            hours_raw = request.form.get("breakfast_cutoff_hours_before", "").strip()
            try:
                hours_before = int(hours_raw)
                if not (0 <= hours_before <= 72):
                    raise ValueError
            except ValueError:
                flash("Breakfast cutoff must be a whole number of hours between 0 and 72.", "error")
                return redirect(url_for("admin.settings_page"))

            time_values = {}
            for key, label in _CUTOFF_TIME_FIELDS.items():
                raw = request.form.get(key, "").strip()
                try:
                    h, m = raw.split(":")
                    time_cls(int(h), int(m))  # validates the range; raises otherwise
                except (ValueError, AttributeError):
                    flash(f"{label} must be a valid time.", "error")
                    return redirect(url_for("admin.settings_page"))
                time_values[key] = raw

            models.set_setting("breakfast_cutoff_hours_before", str(hours_before))
            for key, val in time_values.items():
                models.set_setting(key, val)
            flash("Booking cutoff times updated.", "success")
        else:
            for key in ("report_admin_email", "company_name"):
                models.set_setting(key, request.form.get(key, "").strip())
            flash("Settings updated.", "success")

        return redirect(url_for("admin.settings_page"))

    settings = models.get_all_settings()
    cutoffs = models.get_cutoff_settings()
    cutoff_descriptions = {mt: models.meal_cutoff_description(mt, cutoffs) for mt in MEAL_TYPES}
    report_trigger_times = {key: trigger_time_display(key, cutoffs) for key in REPORT_KEYS}
    return render_template(
        "admin_settings.html", settings=settings, cutoffs=cutoffs, cutoff_descriptions=cutoff_descriptions,
        report_keys=REPORT_KEYS, report_labels=REPORT_LABELS, report_trigger_times=report_trigger_times,
    )
