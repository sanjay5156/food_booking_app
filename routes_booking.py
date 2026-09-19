from datetime import datetime, date

from flask import Blueprint, render_template, request, jsonify

import models
from auth import login_required, get_current_user
from models import MEAL_TYPES, MEAL_TYPE_FOOD_TYPES, PLANTS

booking_bp = Blueprint("booking", __name__)


def _parse_date(s):
    return datetime.strptime(s, "%Y-%m-%d").date()


@booking_bp.route("/dashboard")
@login_required
def dashboard():
    departments = models.list_departments()
    return render_template(
        "employee_dashboard.html",
        meal_types=MEAL_TYPES,
        meal_type_food_types=MEAL_TYPE_FOOD_TYPES,
        departments=departments,
        plants=PLANTS,
        meal_cutoffs=models.meal_cutoff_config_for_js(),
    )


@booking_bp.route("/api/food-catalog")
@login_required
def food_catalog():
    """Returns the food-type options and menu items for a given meal type,
    driving the conditional dropdown in the UI."""
    meal_type = request.args.get("meal_type", "")
    if meal_type not in MEAL_TYPE_FOOD_TYPES:
        return jsonify({"error": "Unknown meal type"}), 400

    food_types = MEAL_TYPE_FOOD_TYPES[meal_type]
    items_by_type = {}
    for ft in food_types:
        items = models.list_food_items(meal_type=meal_type, food_type=ft, active_only=True)
        items_by_type[ft] = [i.item_name for i in items]

    return jsonify({"meal_type": meal_type, "food_types": food_types, "items": items_by_type})


@booking_bp.route("/api/my-preference", methods=["POST"])
@login_required
def update_preference():
    user = get_current_user()
    if not user.employee_id:
        return jsonify({"error": "Only employee accounts have a food preference."}), 400

    pref = (request.json or {}).get("food_preference")
    if pref not in ("Veg", "Non-Veg"):
        return jsonify({"error": "food_preference must be Veg or Non-Veg"}), 400

    models.set_employee_preference(user.employee_id, pref)
    return jsonify({"ok": True, "food_preference": pref})


@booking_bp.route("/api/book/self", methods=["POST"])
@login_required
def book_self():
    """Employee booking food for himself across one or more calendar dates
    (single date, a continuous range, or non-consecutive dates with gaps).
    One food type/item selection applies to every date in the submission."""
    user = get_current_user()
    if not user.employee_id:
        return jsonify({"error": "Only employee accounts can book for themselves."}), 400

    data = request.json or {}
    dates = data.get("dates", [])
    meal_type = data.get("meal_type")
    food_type = data.get("food_type")
    item_name = data.get("item_name") or None

    if not dates:
        return jsonify({"error": "Select at least one date."}), 400
    if meal_type not in MEAL_TYPE_FOOD_TYPES:
        return jsonify({"error": "Invalid meal type."}), 400
    if food_type not in MEAL_TYPE_FOOD_TYPES[meal_type]:
        return jsonify({"error": "Invalid food type for that meal."}), 400

    parsed_dates = []
    for d in dates:
        try:
            parsed_dates.append(_parse_date(d))
        except ValueError:
            return jsonify({"error": f"Invalid date: {d}"}), 400

    # Booking cutoffs apply to everyone except admin accounts, who may need
    # to fix a booking after the deadline. Every date in one submission is
    # checked against the same "now" so a request that straddles a cutoff
    # moment mid-save isn't judged inconsistently.
    if not user.is_admin:
        now = datetime.now()
        cutoffs = models.get_cutoff_settings()
        closed = sorted(d for d in parsed_dates if not models.is_booking_open(meal_type, d, now=now, cutoffs=cutoffs))
        if closed:
            desc = models.meal_cutoff_description(meal_type, cutoffs)
            closed_str = ", ".join(d.isoformat() for d in closed)
            return jsonify({
                "error": f"Booking for {meal_type} has closed for: {closed_str}. {desc} No dates were booked."
            }), 400

    emp = models.get_employee(user.employee_id)
    count = 0
    for booking_date in parsed_dates:
        models.create_self_booking(
            booker_user_id=user.id, employee_id=emp.id, department=emp.department, plant=emp.plant,
            booking_date=booking_date.isoformat(), meal_type=meal_type,
            food_type=food_type, item_name=item_name,
        )
        count += 1

    return jsonify({"ok": True, "count": count})


@booking_bp.route("/api/book/guest", methods=["POST"])
@login_required
def book_guest():
    """Any logged-in employee can book bulk meals for visitors/guests on
    behalf of their department (or another department, if selected)."""
    user = get_current_user()
    data = request.json or {}
    try:
        booking_date = _parse_date(data.get("booking_date", ""))
    except ValueError:
        return jsonify({"error": "Invalid or missing booking date."}), 400

    meal_type = data.get("meal_type")
    food_type = data.get("food_type")
    item_name = data.get("item_name") or None
    quantity = data.get("quantity")
    department = (data.get("department") or "").strip()
    plant = (data.get("plant") or "").strip()
    guest_classification = (data.get("guest_classification") or "").strip()
    guest_note = (data.get("guest_note") or "").strip() or None

    if meal_type not in MEAL_TYPE_FOOD_TYPES:
        return jsonify({"error": "Invalid meal type."}), 400
    if food_type not in MEAL_TYPE_FOOD_TYPES[meal_type]:
        return jsonify({"error": "Invalid food type for that meal."}), 400
    if not user.is_admin and not models.is_booking_open(meal_type, booking_date):
        desc = models.meal_cutoff_description(meal_type)
        return jsonify({
            "error": f"Booking for {meal_type} on {booking_date.isoformat()} has closed. {desc}"
        }), 400
    if plant not in PLANTS:
        return jsonify({"error": "Please select which plant this guest booking is for."}), 400
    try:
        quantity = int(quantity)
        if quantity < 1:
            raise ValueError
    except (TypeError, ValueError):
        return jsonify({"error": "Number of meals must be a positive whole number."}), 400
    if not department:
        if user.employee_id:
            department = models.get_employee(user.employee_id).department
        else:
            return jsonify({"error": "Department is required."}), 400
    if not guest_classification:
        return jsonify({"error": "Please specify the guest type (e.g. Client, Vendor, Interview candidate)."}), 400

    booking_id = models.create_guest_booking(
        booker_user_id=user.id, employee_id=user.employee_id, department=department, plant=plant,
        booking_date=booking_date.isoformat(), meal_type=meal_type, food_type=food_type,
        item_name=item_name, quantity=quantity, guest_classification=guest_classification,
        guest_note=guest_note,
    )
    return jsonify({"ok": True, "booking": models.booking_to_dict(models.get_booking(booking_id))})


@booking_bp.route("/api/my-bookings")
@login_required
def my_bookings():
    """Upcoming + recent bookings made by the current user (self bookings
    for their own employee record, plus any guest bookings they created)."""
    user = get_current_user()
    bookings = models.list_bookings(
        status="active", for_user_or_employee=(user.id, user.employee_id),
    )[:100]
    return jsonify([models.booking_to_dict(b) for b in bookings])


@booking_bp.route("/api/book/<int:booking_id>/cancel", methods=["POST"])
@login_required
def cancel_booking_route(booking_id):
    user = get_current_user()
    b = models.get_booking(booking_id)
    if not b:
        return jsonify({"error": "Booking not found."}), 404
    is_owner = b.booker_user_id == user.id or (b.employee_id and b.employee_id == user.employee_id)
    if not (is_owner or user.is_admin):
        return jsonify({"error": "Not authorized to cancel this booking."}), 403
    models.cancel_booking(booking_id)
    return jsonify({"ok": True})
