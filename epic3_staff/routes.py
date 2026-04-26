from flask import Blueprint, render_template, session
from core.database import supabase
from core.auth import login_required

staff_bp = Blueprint("staff", __name__)


# UMS-14: User Personal Profile & Dashboard
@staff_bp.route("/profile")
@login_required
def profile():
    uid = session.get("user_id")
    role = session.get("role")

    user_resp = supabase.table("users").select("*").eq("id", uid).execute()
    user = user_resp.data[0] if user_resp.data else None

    extra_info = None
    if role == "student":
        resp = supabase.table("students").select("*").eq("user_id", uid).execute()
        extra_info = resp.data[0] if resp.data else None
    elif role in ["staff", "professor", "ta", "admin"]:
        resp = supabase.table("staff").select("*").eq("user_id", uid).execute()
        extra_info = resp.data[0] if resp.data else None

    return render_template(
        "staff/dashboard.html", user=user, extra=extra_info, role=role
    )


# UMS-11: Academic Staff Directory
@staff_bp.route("/staff")
@login_required
def directory():
    staff_members = supabase.table("staff").select("*").order("name").execute().data
    return render_template("staff/directory.html", staff=staff_members)
