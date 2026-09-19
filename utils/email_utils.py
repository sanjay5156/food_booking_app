"""SMTP email sending for the automated daily Excel report."""

import smtplib
from email.message import EmailMessage

from flask import current_app


def send_excel_report(to_address: str, subject: str, body: str, filename: str, file_bytes: bytes):
    """Sends an email with the ledger .xlsx attached. Reads SMTP settings
    from the Flask app config (populated from environment variables / .env).
    Raises on failure so callers/schedulers can log and alert."""
    host = current_app.config.get("SMTP_HOST")
    port = current_app.config.get("SMTP_PORT")
    username = current_app.config.get("SMTP_USERNAME")
    password = current_app.config.get("SMTP_PASSWORD")
    use_tls = current_app.config.get("SMTP_USE_TLS", True)
    mail_from = current_app.config.get("MAIL_FROM") or username

    if not host or not to_address:
        raise RuntimeError(
            "Email is not configured. Set SMTP_HOST/SMTP_USERNAME/SMTP_PASSWORD in .env "
            "and set the report recipient address in Admin > Settings."
        )

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = mail_from
    msg["To"] = to_address
    msg.set_content(body)
    msg.add_attachment(
        file_bytes,
        maintype="application",
        subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=filename,
    )

    with smtplib.SMTP(host, port, timeout=30) as server:
        if use_tls:
            server.starttls()
        if username and password:
            server.login(username, password)
        server.send_message(msg)
