from functools import wraps
from flask import Blueprint, request, session, redirect, url_for, flash, render_template
from werkzeug.security import generate_password_hash, check_password_hash
from core.database import supabase

auth_bp = Blueprint("auth", __name__)


def login_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in first.", "warning")
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)

    return wrapped


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    # If already logged in, send them to the temporary dashboard
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        pwd = request.form.get("password", "")

        response = (
            supabase.table("users").select("*").eq("username", username).execute()
        )

        if response.data and check_password_hash(
            response.data[0]["password_hash"], pwd
        ):
            user = response.data[0]
            # Create the secure session cookie
            session.update(
                {
                    "user_id": user["id"],
                    "username": user["username"],
                    "role": user["role"],
                }
            )
            flash(f"Welcome back, {user['full_name']}!", "success")
            return redirect(url_for("dashboard"))

        flash("Invalid username or password.", "danger")

    return render_template("auth/login.html")


@auth_bp.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        pwd = request.form.get("password", "")
        full_name = request.form.get("full_name", "").strip()
        role = request.form.get("role", "student")

        existing = (
            supabase.table("users").select("id").eq("username", username).execute()
        )
        if existing.data:
            flash("Username already exists.", "danger")
        else:
            hashed = generate_password_hash(pwd)
            supabase.table("users").insert(
                {
                    "username": username,
                    "password_hash": hashed,
                    "full_name": full_name,
                    "role": role,
                }
            ).execute()
            flash("Account created! Please log in.", "success")
            return redirect(url_for("auth.login"))

    return render_template("auth/signup.html")


@auth_bp.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("auth.login"))
