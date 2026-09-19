"""Lightweight session-based authentication — no Flask-Login dependency.
Provides a `current_user` proxy (mirroring the handful of attributes the
templates and routes use), plus `login_required` / `admin_required`
decorators."""

from functools import wraps

from flask import Blueprint, render_template, request, redirect, url_for, flash, session, g

import models

auth_bp = Blueprint("auth", __name__)


class AnonymousUser:
    is_authenticated = False
    is_admin = False
    employee_id = None
    username = None
    id = None
    employee = None


class LoggedInUser:
    is_authenticated = True

    def __init__(self, user_record):
        self._user = user_record

    @property
    def id(self):
        return self._user.id

    @property
    def username(self):
        return self._user.username

    @property
    def role(self):
        return self._user.role

    @property
    def is_admin(self):
        return self._user.role == "admin"

    @property
    def employee_id(self):
        return self._user.employee_id

    @property
    def employee(self):
        if self._user.employee_id:
            return models.get_employee(self._user.employee_id)
        return None

    @property
    def welcome_message(self):
        """'Welcome Mr./Ms. <Name> (<Employee ID>)' for an employee login,
        shown in the top toolbar for the whole session — or a plain
        username greeting for an admin/non-employee account."""
        emp = self.employee
        if emp:
            honorific = {"male": "Mr.", "female": "Ms."}.get((emp.sex or "").strip().lower(), "")
            name_part = f"{honorific} {emp.name}".strip()
            return f"Welcome {name_part} ({emp.employee_code})"
        return f"Welcome, {self.username}"

    def check_password(self, raw_password):
        return models.check_user_password(self._user, raw_password)


def get_current_user():
    if "current_user" in g:
        return g.current_user

    user_id = session.get("user_id")
    if not user_id:
        g.current_user = AnonymousUser()
        return g.current_user

    user_record = models.get_user(user_id)
    if not user_record or not user_record.is_active:
        session.pop("user_id", None)
        g.current_user = AnonymousUser()
    else:
        g.current_user = LoggedInUser(user_record)
    return g.current_user


def login_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not get_current_user().is_authenticated:
            return redirect(url_for("auth.login", next=request.path))
        return view_func(*args, **kwargs)
    return wrapped


def admin_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        user = get_current_user()
        if not user.is_authenticated or not user.is_admin:
            flash("You need admin access for that page.", "error")
            return redirect(url_for("auth.login"))
        return view_func(*args, **kwargs)
    return wrapped


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    user = get_current_user()
    if user.is_authenticated:
        return redirect(url_for("admin.dashboard" if user.is_admin else "booking.dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user_record = models.get_user_by_username(username)

        if user_record and user_record.is_active and models.check_user_password(user_record, password):
            session.clear()
            session["user_id"] = user_record.id
            models.touch_last_login(user_record.id)
            next_page = request.args.get("next")
            if next_page:
                return redirect(next_page)
            return redirect(url_for("admin.dashboard" if user_record.role == "admin" else "booking.dashboard"))

        flash("Invalid username or password.", "error")

    return render_template("login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    user = get_current_user()
    if request.method == "POST":
        current_pw = request.form.get("current_password", "")
        new_pw = request.form.get("new_password", "")
        confirm_pw = request.form.get("confirm_password", "")

        if not user.check_password(current_pw):
            flash("Current password is incorrect.", "error")
        elif len(new_pw) < 4:
            flash("New password must be at least 4 characters.", "error")
        elif new_pw != confirm_pw:
            flash("New password and confirmation do not match.", "error")
        else:
            models.set_user_password(user.id, new_pw)
            flash("Password updated successfully.", "success")
            return redirect(url_for("admin.dashboard" if user.is_admin else "booking.dashboard"))

    return render_template("change_password.html")
