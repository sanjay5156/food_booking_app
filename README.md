# Food Booking System

A self-contained web application for booking company-provided meals — for
yourself (employees) or for visitors/guests — with an admin dashboard for
menu management, live catering sheets, consumption reports, and automated
Excel reports by email, sent automatically as each meal's booking window
closes.

Built with plain Flask + SQLite + openpyxl only — no database server to
install, no paid services, and no third-party accounts required. It runs
entirely on your own PC or a small server on your local network, and is
used from any phone, tablet or computer's web browser.

## What's included (mapped to your requirements)

- **Book for Self** — Meal Type (Breakfast/Lunch/Snacks/Dinner) drives a
  conditional Food Type dropdown (Veg/Non-Veg, or just Snacks). An
  interactive calendar lets you pick single dates, a continuous range, or
  scattered dates with gaps, all in one go — one food type applies to every
  date you select.
- **Continuous preference** — Each employee's Veg/Non-Veg default lives in
  their profile and is used automatically every day; changing it on the
  dashboard updates it going forward until changed again.
- **Book for Guests** — Any logged-in employee can book N meals for
  visitors, tagging the meal type, food type, guest classification (e.g.
  "Client visit", "Vendor"), and the department to charge it to.
- **Employee database** — Employee ID, Name, Age, Sex, Department, and Food
  Preference, managed from Admin → Employees. Adding an employee also
  creates their login automatically.
- **Menu management** — Admin → Menu Items lets you add/deactivate/delete
  specific dishes under each Meal Type + Food Type (e.g. "Veg Thali" under
  Lunch/Veg, "Cutlet" under Snacks).
- **Per-meal booking cutoffs** — Breakfast, Lunch, Snacks and Dinner each
  close for booking at their own configurable deadline (Admin → Settings →
  Booking Cutoff Times), enforced on the server, not just shown as
  guidance. Breakfast defaults to 12 hours before 6:00 AM (i.e. 6:00 PM the
  evening before); Lunch defaults to 8:00 AM, Snacks to 4:00 PM, and Dinner
  to 6:00 PM, all on the same day as the meal. The employee calendar greys
  out and strikes through any date that's past cutoff for the selected
  meal. Admin accounts are exempt, so a booking can still be corrected
  after the deadline.
- **Automated Excel reports by email** — three .xlsx ledgers a day, each
  emailed to a configurable address automatically 5 minutes after a meal's
  booking cutoff closes: Lunch, Snacks, and Dinner + next-day Breakfast
  combined (Admin → Settings). A "Send now" button is provided per report,
  plus one for an on-demand full-day ledger across all four meal types.
- **Manual view/print** — Admin → View/Print shows a login-gated catering
  sheet for any date range, filterable by department or Self/Guest, with a
  Print button and a one-click Excel download.
- **Reports** — Admin → Reports gives Daily/Weekly/Monthly totals, broken
  down by department, meal type, Veg/Non-Veg/Snacks, and Self vs Guest.

## Requirements

- Python 3.9 or newer, on the computer that will run the app (this can be
  a regular office PC, or a small server — it just needs to be left
  running for others to reach it).
- No internet connection is required to *use* the app once installed —
  everything runs locally. Internet is only needed once, to download the
  three small Python packages during setup, and later if you turn on the
  automated email report (which needs to reach your email provider).

## Don't have Python? Two options

This app is Python-based, so *something* needs Python once — either on
every PC that runs it (Option A), or on just one PC that builds a
standalone `.exe` you then copy anywhere (Option B). There's no way to
skip Python entirely; a browser-based app still needs something to run
its server.

**Option A — install Python once (about 3 minutes, easiest):**
Download Python from python.org (Windows: tick "Add Python to PATH"
during setup), then use `run.bat`/`run.sh` below. After that first
install, every future launch really is just double-click.

**Option B — build a real `FoodBookingSystem.exe` (best for handing this
to PCs that will never have Python):** on any *one* Windows PC that has
Python, double-click `build_exe.bat` in this folder. It installs
PyInstaller temporarily and produces `dist\FoodBookingSystem.exe` — copy
just that one file to as many other Windows PCs as you like and
double-click it there. Those PCs need nothing installed at all. See
"Building a standalone .exe" below for details.

## Setup & running from source

**Windows:** double-click `run.bat` (or run it from a command prompt).
**Linux / macOS:** run `./run.sh` from a terminal.

The first run creates a virtual environment and installs dependencies
(a one-time step needing internet access to PyPI). It also generates a
`.env` config file with a random secret key on its very first launch.
Every run after that just starts the app and opens it in your browser.

Then, if it didn't open automatically, go to **http://localhost:5000**
in a browser on that computer, or **http://<that computer's IP
address>:5000** from any other phone, tablet, or PC on the same
office/plant network — no installation needed on those devices, just a
browser.

## Building a standalone .exe (no Python needed on the target PC)

Run `build_exe.bat` once on a Windows PC that has Python. It will:

1. Install PyInstaller into a throwaway build environment (doesn't touch
   your system Python).
2. Bundle the app, its templates/styles, and all dependencies into one
   file: `dist\FoodBookingSystem.exe`.

Copy that single file to any other Windows PC — no install, no Python,
nothing else to copy — and double-click it. It opens a console window
(that's normal; it's the app's server — keep it open while in use) and
launches your browser to the app automatically. The first double-click
on a machine creates its own `.env` and `instance\food_booking.db` right
next to the .exe, so your data stays with wherever you place the file.

A couple of things worth knowing about this route: the .exe only runs on
the same kind of computer it was built on (a Windows build produces a
Windows .exe, usable only on other Windows PCs — not Mac, not
Linux, not phones; those still just use it as a web app in their
browser once it's running somewhere). Building itself needs internet
access on the one build PC (to fetch PyInstaller); running the finished
.exe afterwards does not.

### Manual setup (if you'd rather not use the scripts)

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py                   # creates .env automatically on first run
```

## First login

The app seeds itself with a demo admin account and five sample employees
on first run — replace/remove the sample employees once your real
employee list is entered.

| Role     | Username | Password  |
|----------|----------|-----------|
| Admin    | `admin`  | `admin123`|
| Employee | `EMP001` … `EMP005` | same as the Employee ID (e.g. `EMP001`) |

**Change the admin password immediately** (Change Password, top menu)
before putting this in front of your organization. Employees should do
the same the first time they log in.

New employees added from Admin → Employees automatically get a login:
username = their Employee ID, default password = their Employee ID.

## Configuring the automated email reports

Three Excel ledgers are emailed automatically each day — not at a single
fixed time, but 5 minutes after each meal's booking cutoff closes (Admin →
Settings → Booking Cutoff Times), so the kitchen gets each head-count as
soon as it's final:

| Report | Sends | Covers |
|---|---|---|
| Lunch | 5 min after Lunch's cutoff (default 8:05 AM) | Today's Lunch bookings |
| Snacks | 5 min after Snacks' cutoff (default 4:05 PM) | Today's Snacks bookings |
| Dinner + next-day Breakfast | 5 min after Dinner's cutoff (default 6:05 PM) | Today's Dinner bookings *and* tomorrow's Breakfast bookings, in one attachment |

Change a cutoff time and the matching report's send time moves with it
automatically — there's nothing separate to configure. Admin → Settings
also shows each report's current send time, and has a "Send Now" button
per report (plus one for the full day's ledger across all four meal
types) for testing without waiting for the actual cutoff.

Open Admin → Settings and set:
- **Report Recipient Email** — where the ledgers are sent.
- **Company / Plant Name** — shown in the email subject/title.

Then edit the `.env` file (created automatically next to `app.py`, or
next to `FoodBookingSystem.exe` if you're using the standalone build, the
first time you run it) with your email provider's SMTP details:

```
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USE_TLS=true
SMTP_USERNAME=your_email@example.com
SMTP_PASSWORD=your_app_password
MAIL_FROM=your_email@example.com
```

For Gmail/Outlook/most providers you'll need an **app password**, not
your normal login password (search "[your provider] app password" —
this is a one-time setup step in your email account's security settings).
Restart the app after editing `.env`.

### Making the emails more reliable (recommended for production)

The built-in scheduler only fires while the app is running. That's fine
if the computer stays on, but for a server that might restart, it's more
reliable to let the operating system trigger each email instead, using the
included `send_report.py` script:

```
python send_report.py lunch              # today's Lunch report
python send_report.py snacks             # today's Snacks report
python send_report.py dinner_breakfast   # today's Dinner + tomorrow's Breakfast report
python send_report.py full               # full day's ledger, all meal types
python send_report.py full 2026-09-02    # full day's ledger for a specific date
```

**Linux/macOS (cron)** — run `crontab -e` and add one line per report,
timed 5 minutes after that meal's cutoff (defaults shown — adjust to match
whatever you've set in Admin → Settings → Booking Cutoff Times):
```
5 8  * * * cd /path/to/food_booking_app && venv/bin/python send_report.py lunch
5 16 * * * cd /path/to/food_booking_app && venv/bin/python send_report.py snacks
5 18 * * * cd /path/to/food_booking_app && venv/bin/python send_report.py dinner_breakfast
```

**Windows (Task Scheduler)** — create three daily triggers (one per
report, at the same times as above) that each run:
```
"C:\path\to\food_booking_app\venv\Scripts\python.exe" "C:\path\to\food_booking_app\send_report.py" lunch
```
(swap `lunch` for `snacks` / `dinner_breakfast` on the other two triggers)

If you use the cron/Task Scheduler method, the in-app scheduler won't
double-send — each report checks whether it's already gone out today
before sending. Just remember cron times are fixed at the OS level: if you
change a cutoff in Admin → Settings later, update the matching cron/Task
Scheduler time to match, since only the in-app scheduler follows cutoff
changes automatically.

## Deploying for everyday use

The command `python app.py` starts Flask's built-in development server,
which is fine for trying things out or for a small office network. For a
more robust always-on deployment:

- Run it as a background service (Linux: a `systemd` unit; Windows: Task
  Scheduler "at startup", or NSSM to install it as a Windows service) so
  it survives reboots without anyone needing to keep a terminal open.
- Put a production WSGI server in front of it, e.g. `pip install waitress`
  and run `waitress-serve --port=5000 app:create_app` instead of
  `python app.py`, for better stability under load.
  (A random `SECRET_KEY` is already generated into `.env` automatically
  on first run, so there's nothing to do there.)
- If you ever expose this beyond your local network (rather than just
  your office Wi-Fi/LAN), put it behind HTTPS via a reverse proxy
  (e.g. nginx or Caddy) — do not expose the plain HTTP dev server to the
  public internet.

## Data & backups

All data lives in a single SQLite file: `instance/food_booking.db`. To
back up, just copy that one file (with the app stopped, or using your
OS's file-copy while it's running — SQLite handles that safely for a
single-file backup in almost all cases). To reset the app to a blank
state, stop it and delete that file — it will be recreated with the demo
seed data on next start.

## Project structure

```
app.py                 Flask application factory & entry point
config.py               Configuration (auto-creates & reads .env)
paths.py                 Resolves file paths correctly both from source
                          and when frozen into an .exe
db.py                    SQLite connection handling + schema
models.py                Data-access functions (employees, bookings, food items, settings)
auth.py                  Login/session handling, access control
routes_booking.py        Employee self-booking & guest-booking APIs
routes_admin.py          Admin: employees, menu items, settings
routes_reports.py        Reports, view/print ledger, Excel export
scheduler.py             Background thread for the daily email report
send_report.py           Standalone script for cron / Task Scheduler
seed_data.py              First-run demo data
utils/excel_export.py    Builds the .xlsx ledger
utils/email_utils.py     Sends the ledger by email
templates/, static/       All pages & styling (no external internet
                           dependency — works fully offline once installed)
run.bat / run.sh          Everyday launcher (needs Python installed once)
build_exe.bat             One-time build of a standalone Windows .exe
```

## About "downloadable app"

This is delivered as a downloadable folder you run either with one
script (`run.bat` / `run.sh`, needing Python installed once) or, if you'd
rather skip Python entirely on most machines, by building a real
standalone `FoodBookingSystem.exe` once with `build_exe.bat` and copying
that single file everywhere else — see "Don't have Python?" above. Either
way it's a full web application used from a browser on any device on your
network, not something installed per-device from an app store, which
keeps it easy to update (change one copy of the code) and lets every
employee use it from their own phone or PC. A macOS/Linux equivalent
build, or a true installer with a Start Menu shortcut and auto-start, is
a reasonable follow-up if you need it — just ask.
