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


def admin_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in first.", "warning")
            return redirect(url_for("auth.login"))
        if session.get("role") != "admin":
            flash("Access denied. Admin privileges required.", "danger")
            return redirect(url_for("staff.profile"))
        return f(*args, **kwargs)

    return wrapped


def course_coordinator_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in first.", "warning")
            return redirect(url_for("auth.login"))
        if session.get("role") != "course_coordinator":
            flash(
                "Access denied. Course Coordinator privileges required.",
                "danger",
            )
            return redirect(url_for("staff.profile"))
        return f(*args, **kwargs)

    return wrapped


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("staff.profile"))

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
            session.update(
                {
                    "user_id": user["id"],
                    "username": user["username"],
                    "role": user["role"],
                }
            )
            flash(f"Welcome back, {user['full_name']}!", "success")

            return redirect(url_for("staff.profile"))

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

            # 1. Create the Auth User
            user_resp = (
                supabase.table("users")
                .insert(
                    {
                        "username": username,
                        "password_hash": hashed,
                        "full_name": full_name,
                        "role": role,
                    }
                )
                .execute()
            )

            new_user_id = user_resp.data[0]["id"]

            # 2. Automatically generate the public directory profile
            if role in ["staff", "admin", "course_coordinator"]:
                supabase.table("staff").insert(
                    {
                        "user_id": new_user_id,
                        "staff_id": f"STAFF-{new_user_id}",  # Generate a placeholder ID
                        "name": full_name,
                        "role_type": "course_coordinator" if role == "course_coordinator" else "professor",
                        "department": "Pending Assignment",
                        "email": f"{username}@university.edu",
                    }
                ).execute()
            elif role == "student":
                supabase.table("students").insert(
                    {
                        "user_id": new_user_id,
                        "student_id": f"STU-{new_user_id}",
                        "name": full_name,
                        "email": f"{username}@university.edu",
                        "department": "Undeclared",
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
