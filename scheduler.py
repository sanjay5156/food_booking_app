"""Background scheduler that emails meal-specific booking ledgers shortly
after each meal's booking cutoff closes, so the kitchen gets each final
head-count as soon as it's locked in — rather than one combined report at a
single fixed time:

  - Lunch report                  -> 5 minutes after Lunch's cutoff, same day
  - Snacks report                 -> 5 minutes after Snacks' cutoff, same day
  - Dinner + next-day Breakfast   -> 5 minutes after Dinner's cutoff, same day
    report                           (Breakfast for the next calendar day is
                                      booked the evening before, so by the
                                      time Dinner's cutoff has passed,
                                      next-day Breakfast bookings have
                                      normally closed too, by default)

All three trigger times move automatically if the cutoffs are changed in
Admin > Settings > Booking Cutoff Times — there's nothing else to configure.

Built on a plain Python thread (stdlib `threading`) rather than APScheduler,
so the app has zero third-party dependencies beyond Flask + openpyxl. It
checks once a minute whether "now" is at or past each report's trigger
moment and whether that report has already gone out today; a report fires
the first time it's noticed as due, so a brief restart around the trigger
time doesn't cause it to be skipped for the day (it just goes out a little
late once the app is back up).

NOTE ON RELIABILITY: this only fires while the Flask process is running.
For a production deployment where the server might be restarted or asleep
around a trigger time, see README.md for the equivalent system-cron / Task
Scheduler alternative that calls the same logic via `python send_report.py`.
"""

import logging
import threading
import time
from datetime import datetime, date, timedelta

import models
from utils.excel_export import build_ledger_workbook, build_meal_slice_workbook, workbook_to_bytes
from utils.email_utils import send_excel_report

logger = logging.getLogger("scheduler")

CHECK_INTERVAL_SECONDS = 60
POST_CUTOFF_DELAY_MINUTES = 5

REPORT_KEYS = ("lunch", "snacks", "dinner_breakfast")

REPORT_LABELS = {
    "lunch": "Lunch",
    "snacks": "Snacks",
    "dinner_breakfast": "Dinner + Next-Day Breakfast",
}


def _last_sent_key(report_key):
    return f"report_last_sent_{report_key}_date"


def _cutoff_meal_for_report(report_key):
    return {"lunch": "Lunch", "snacks": "Snacks", "dinner_breakfast": "Dinner"}.get(report_key)


def trigger_datetime(report_key, today=None, cutoffs=None):
    """The exact moment this report should fire: 5 minutes after the
    relevant meal's cutoff on `today`. Returns None for an unknown key."""
    today = today or date.today()
    cutoffs = cutoffs or models.get_cutoff_settings()
    meal_type = _cutoff_meal_for_report(report_key)
    if not meal_type:
        return None
    cutoff_dt = models.get_meal_cutoff_datetime(meal_type, today, cutoffs=cutoffs)
    if cutoff_dt is None:
        return None
    return cutoff_dt + timedelta(minutes=POST_CUTOFF_DELAY_MINUTES)


def trigger_time_display(report_key, cutoffs=None):
    """Human-readable clock time (e.g. '8:05 AM') this report fires at,
    independent of which calendar day — used on the settings page."""
    dt = trigger_datetime(report_key, today=date(2000, 1, 2), cutoffs=cutoffs)
    return dt.strftime("%I:%M %p").lstrip("0") if dt else ""


def _segments_and_label(report_key, today):
    tomorrow = today + timedelta(days=1)
    if report_key == "lunch":
        return [(today, "Lunch")], f"Lunch — {today.isoformat()}"
    if report_key == "snacks":
        return [(today, "Snacks")], f"Snacks — {today.isoformat()}"
    if report_key == "dinner_breakfast":
        return (
            [(today, "Dinner"), (tomorrow, "Breakfast")],
            f"Dinner {today.isoformat()} + Breakfast {tomorrow.isoformat()}",
        )
    return [], ""


def generate_and_send_meal_report(report_key, today=None, to_override=None):
    """Builds and emails one meal-scoped ledger (Lunch, Snacks, or
    Dinner+next-day-Breakfast). Returns (True, message) on success,
    (False, message) on failure. Used by both the automatic scheduler and
    the admin 'Send now' buttons."""
    if report_key not in REPORT_KEYS:
        return False, f"Unknown report: {report_key}"

    today = today or date.today()
    recipient = to_override or models.get_setting("report_admin_email")
    company = models.get_setting("company_name", "Our Plant")

    if not recipient:
        return False, "No report recipient email is configured (Admin > Settings)."

    segments, label = _segments_and_label(report_key, today)
    wb = build_meal_slice_workbook(segments, title=f"{company} — {label}")
    file_bytes = workbook_to_bytes(wb)
    filename = f"food_booking_{report_key}_{today.isoformat()}.xlsx"

    try:
        send_excel_report(
            to_address=recipient,
            subject=f"{company}: {label} — Booking Ledger",
            body=(
                f"Attached is the booking ledger for {label}.\n\n"
                "This is an automated message from the Food Booking System, "
                "sent automatically once booking for these meals closed."
            ),
            filename=filename,
            file_bytes=file_bytes,
        )
    except Exception as exc:  # noqa: BLE001 — surface any SMTP error to the caller/log
        logger.exception("Failed to send %s report email", report_key)
        return False, f"Failed to send email: {exc}"

    return True, f"{label} report emailed to {recipient}."


def generate_and_send_full_day_report(for_date: date = None, to_override: str = None):
    """Builds and emails the full day's ledger across all four meal types in
    one attachment. Not on the automatic schedule (that's the three
    meal-scoped reports above) — kept for the admin's on-demand 'Send Full
    Day Ledger Now' button and the equivalent standalone cron script."""
    target_date = for_date or date.today()
    recipient = to_override or models.get_setting("report_admin_email")
    company = models.get_setting("company_name", "Our Plant")

    if not recipient:
        return False, "No report recipient email is configured (Admin > Settings)."

    wb = build_ledger_workbook(
        target_date, target_date,
        title=f"{company} — Food Booking Ledger — {target_date.isoformat()}",
    )
    file_bytes = workbook_to_bytes(wb)
    filename = f"food_booking_ledger_{target_date.isoformat()}.xlsx"

    try:
        send_excel_report(
            to_address=recipient,
            subject=f"{company}: Food Booking Ledger for {target_date.isoformat()}",
            body=(
                f"Attached is the full food booking ledger for {target_date.isoformat()}.\n\n"
                "This is an automated message from the Food Booking System."
            ),
            filename=filename,
            file_bytes=file_bytes,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to send full-day booking report email")
        return False, f"Failed to send email: {exc}"

    return True, f"Full-day report for {target_date.isoformat()} emailed to {recipient}."


def _minute_check(app):
    with app.app_context():
        try:
            now = datetime.now()
            today = date.today()
            today_str = today.isoformat()
            cutoffs = models.get_cutoff_settings()

            for report_key in REPORT_KEYS:
                if models.get_setting(_last_sent_key(report_key)) == today_str:
                    continue  # already sent today

                trigger_dt = trigger_datetime(report_key, today=today, cutoffs=cutoffs)
                if trigger_dt is None or now < trigger_dt:
                    continue  # not due yet

                ok, message = generate_and_send_meal_report(report_key, today=today)
                if ok:
                    models.set_setting(_last_sent_key(report_key), today_str)
                    logger.info(message)
                else:
                    logger.warning("Scheduled %s report not sent: %s", report_key, message)
        except Exception:  # noqa: BLE001 — never let the scheduler thread die
            logger.exception("Error in scheduled report check")


def _run_loop(app):
    while True:
        _minute_check(app)
        time.sleep(CHECK_INTERVAL_SECONDS)


def init_scheduler(app):
    thread = threading.Thread(target=_run_loop, args=(app,), daemon=True, name="meal-report-scheduler")
    thread.start()
    app.scheduler_thread = thread
    return thread
