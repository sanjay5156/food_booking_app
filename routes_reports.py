from datetime import date, timedelta
from io import BytesIO

from flask import Blueprint, render_template, request, jsonify, send_file, flash, redirect, url_for

import models
from auth import login_required, admin_required
from models import PLANTS
from utils.excel_export import build_ledger_workbook, workbook_to_bytes
from scheduler import (
    generate_and_send_full_day_report, generate_and_send_meal_report,
    REPORT_KEYS, REPORT_LABELS, trigger_time_display,
)

reports_bp = Blueprint("reports", __name__)


def _period_range(period, anchor: date):
    if period == "daily":
        return anchor, anchor
    if period == "weekly":
        start = anchor - timedelta(days=anchor.weekday())  # Monday
        return start, start + timedelta(days=6)
    if period == "monthly":
        start = anchor.replace(day=1)
        if start.month == 12:
            end = start.replace(year=start.year + 1, month=1) - timedelta(days=1)
        else:
            end = start.replace(month=start.month + 1) - timedelta(days=1)
        return start, end
    return anchor, anchor


@reports_bp.route("/admin/reports")
@login_required
@admin_required
def reports_page():
    departments = models.list_departments()
    return render_template("admin_reports.html", departments=departments, plants=PLANTS)


@reports_bp.route("/api/reports/summary")
@login_required
@admin_required
def reports_summary():
    period = request.args.get("period", "daily")
    anchor_str = request.args.get("date")
    department = request.args.get("department") or None
    target = request.args.get("target") or None
    plant = request.args.get("plant") or None

    try:
        anchor = date.fromisoformat(anchor_str) if anchor_str else date.today()
    except ValueError:
        anchor = date.today()

    start, end = _period_range(period, anchor)

    bookings = models.list_bookings(
        start_date=start, end_date=end, department=department, target=target, plant=plant, status="active",
    )

    def bucket(keyfn):
        out = {}
        for b in bookings:
            k = keyfn(b)
            out[k] = out.get(k, 0) + b.quantity
        return out

    by_department = bucket(lambda b: b.department)
    by_plant = bucket(lambda b: b.plant)
    by_meal_type = bucket(lambda b: b.meal_type)
    by_food_type = bucket(lambda b: b.food_type)
    by_target = bucket(lambda b: b.target)
    by_date = bucket(lambda b: b.booking_date.isoformat())

    total = sum(b.quantity for b in bookings)

    return jsonify({
        "period": period,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "total_meals": total,
        "total_records": len(bookings),
        "by_department": by_department,
        "by_plant": by_plant,
        "by_meal_type": by_meal_type,
        "by_food_type": by_food_type,
        "by_target": by_target,  # Self vs Guest
        "by_date": by_date,
    })


@reports_bp.route("/admin/ledger")
@login_required
@admin_required
def ledger_view():
    """Manual view/print catering sheet, login-gated for authorized personnel."""
    start_str = request.args.get("start")
    end_str = request.args.get("end")
    department = request.args.get("department") or None
    target = request.args.get("target") or None
    plant = request.args.get("plant") or None

    today = date.today()
    start = date.fromisoformat(start_str) if start_str else today
    end = date.fromisoformat(end_str) if end_str else today

    bookings = models.list_bookings(
        start_date=start, end_date=end, department=department, target=target, plant=plant, status=None,
    )
    departments = models.list_departments()

    return render_template(
        "print_ledger.html", bookings=bookings, start=start, end=end,
        department=department, target=target, plant=plant, departments=departments, plants=PLANTS,
    )


@reports_bp.route("/admin/export/excel")
@login_required
@admin_required
def export_excel():
    start_str = request.args.get("start")
    end_str = request.args.get("end")
    department = request.args.get("department") or None
    target = request.args.get("target") or None
    plant = request.args.get("plant") or None

    today = date.today()
    start = date.fromisoformat(start_str) if start_str else today
    end = date.fromisoformat(end_str) if end_str else today

    wb = build_ledger_workbook(start, end, department=department, target=target, plant=plant)
    data = workbook_to_bytes(wb)
    filename = f"food_booking_ledger_{start.isoformat()}_to_{end.isoformat()}.xlsx"

    return send_file(
        BytesIO(data), as_attachment=True, download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@reports_bp.route("/admin/reports/send-now", methods=["POST"])
@login_required
@admin_required
def send_now():
    """Manual, on-demand send of the full day's ledger (all four meal
    types in one attachment) — not on the automatic schedule."""
    ok, message = generate_and_send_full_day_report()
    flash(message, "success" if ok else "error")
    return redirect(url_for("admin.settings_page"))


@reports_bp.route("/admin/reports/send-meal-now/<report_key>", methods=["POST"])
@login_required
@admin_required
def send_meal_now(report_key):
    """Manual trigger for one of the three automatic meal-cutoff reports —
    handy for testing without waiting for the actual cutoff to pass."""
    if report_key not in REPORT_KEYS:
        flash("Unknown report.", "error")
        return redirect(url_for("admin.settings_page"))
    ok, message = generate_and_send_meal_report(report_key)
    flash(message, "success" if ok else "error")
    return redirect(url_for("admin.settings_page"))
