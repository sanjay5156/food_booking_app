import os
import secrets
from dotenv import load_dotenv

from paths import app_data_dir

BASE_DIR = app_data_dir()
ENV_PATH = os.path.join(BASE_DIR, ".env")

_ENV_TEMPLATE = """\
# Food Booking System — local configuration.
# Edit the values below, then restart the app for changes to take effect.

# Flask secret key (auto-generated on first run — do not share it)
SECRET_KEY={secret_key}

# SMTP settings used to email the daily Excel booking report.
# Leave SMTP_HOST blank to disable the automated email until you set this up.
SMTP_HOST=
SMTP_PORT=587
SMTP_USE_TLS=true
SMTP_USERNAME=
SMTP_PASSWORD=
MAIL_FROM=

# Default admin account created on first run (change the password after
# your first login — Change Password in the top menu).
DEFAULT_ADMIN_USERNAME=admin
DEFAULT_ADMIN_PASSWORD=admin123
"""


def _ensure_env_file():
    """Creates a .env with a freshly generated secret key on first run,
    so there's nothing to configure before the app works out of the box."""
    if os.path.exists(ENV_PATH):
        return
    os.makedirs(BASE_DIR, exist_ok=True)
    with open(ENV_PATH, "w", encoding="utf-8") as f:
        f.write(_ENV_TEMPLATE.format(secret_key=secrets.token_hex(32)))


_ensure_env_file()
load_dotenv(ENV_PATH)


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")
    DATABASE_PATH = os.environ.get(
        "DATABASE_PATH", os.path.join(BASE_DIR, "instance", "food_booking.db")
    )

    SMTP_HOST = os.environ.get("SMTP_HOST", "")
    SMTP_PORT = int(os.environ.get("SMTP_PORT", 587))
    SMTP_USE_TLS = os.environ.get("SMTP_USE_TLS", "true").lower() == "true"
    SMTP_USERNAME = os.environ.get("SMTP_USERNAME", "")
    SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
    MAIL_FROM = os.environ.get("MAIL_FROM", "")

    DEFAULT_ADMIN_USERNAME = os.environ.get("DEFAULT_ADMIN_USERNAME", "admin")
    DEFAULT_ADMIN_PASSWORD = os.environ.get("DEFAULT_ADMIN_PASSWORD", "admin123")
