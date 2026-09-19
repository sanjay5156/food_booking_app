#!/usr/bin/env python
"""Standalone script to email a booking ledger — the same logic the in-app
scheduler uses. Intended to be triggered by the OS's own scheduler (cron on
Linux/Mac, Task Scheduler on Windows) for a more reliable production setup
than relying on the Flask process staying up at each report's trigger
moment. See README.md for setup instructions.

The app now sends three automatic meal-scoped reports a day, each 5 minutes
after that meal's booking cutoff (Admin > Settings > Booking Cutoff Times):
Lunch, Snacks, and Dinner + next-day Breakfast. If you're setting these up
as OS-level cron jobs instead of relying on the in-app scheduler, you need
one job per report, timed 5 minutes after the matching cutoff — and you'll
need to update the cron times yourself if you change a cutoff later, since
cron doesn't read the app's settings.

Usage:
    python send_report.py lunch                    # today's Lunch report
    python send_report.py snacks                    # today's Snacks report
    python send_report.py dinner_breakfast           # today's Dinner + tomorrow's Breakfast report
    python send_report.py full 2026-09-02            # full day's ledger (all meals) for a given date
    python send_report.py full                       # full day's ledger for today
"""
import sys
from datetime import date

from app import create_app
from scheduler import generate_and_send_meal_report, generate_and_send_full_day_report, REPORT_KEYS

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in (*REPORT_KEYS, "full"):
        print(__doc__)
        sys.exit(2)

    which = sys.argv[1]
    app = create_app()
    with app.app_context():
        if which == "full":
            target = date.fromisoformat(sys.argv[2]) if len(sys.argv) > 2 else None
            ok, message = generate_and_send_full_day_report(for_date=target)
        else:
            ok, message = generate_and_send_meal_report(which)
        print(message)
        sys.exit(0 if ok else 1)
