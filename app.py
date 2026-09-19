import os
import sys
import logging
import threading
import webbrowser

from flask import Flask, redirect, url_for

from config import Config
from paths import resource_path
import db as dbmod


def create_app():
    app = Flask(
        __name__,
        template_folder=resource_path("templates"),
        static_folder=resource_path("static"),
    )
    app.config.from_object(Config)

    dbmod.init_db(app)

    from auth import auth_bp, get_current_user
    from routes_booking import booking_bp
    from routes_admin import admin_bp
    from routes_reports import reports_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(booking_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(reports_bp)

    @app.context_processor
    def inject_current_user():
        return {"current_user": get_current_user()}

    @app.route("/")
    def index():
        user = get_current_user()
        if user.is_authenticated:
            return redirect(url_for("admin.dashboard" if user.is_admin else "booking.dashboard"))
        return redirect(url_for("auth.login"))

    with app.app_context():
        import seed_data
        seed_data.seed_all()

    return app


def _open_browser_soon(port):
    def _open():
        import time
        time.sleep(1.2)
        try:
            webbrowser.open(f"http://127.0.0.1:{port}/")
        except Exception:
            pass
    threading.Thread(target=_open, daemon=True).start()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    app = create_app()

    from scheduler import init_scheduler
    init_scheduler(app)

    port = int(os.environ.get("PORT", 5000))
    debug_mode = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    is_frozen = getattr(sys, "frozen", False)

    print("=" * 60)
    print("  Food Booking System")
    print("=" * 60)
    print(f"  Opening in your browser at: http://localhost:{port}")
    print(f"  From other devices on this network, use this PC's IP address")
    print(f"  instead of 'localhost', e.g. http://192.168.1.23:{port}")
    print("  Keep this window open while the app is in use.")
    print("  Close this window (or press CTRL+C) to stop the app.")
    print("=" * 60)

    if is_frozen or os.environ.get("OPEN_BROWSER", "true").lower() == "true":
        _open_browser_soon(port)

    # use_reloader is forced off so we don't start two copies of the background scheduler thread
    app.run(host="0.0.0.0", port=port, debug=debug_mode, use_reloader=False)
