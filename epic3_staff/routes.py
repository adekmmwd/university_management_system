from flask import Blueprint, render_template, session, jsonify
from core.database import supabase
from core.auth import login_required
from epic3_staff.services import get_staff_courses, get_staff_by_user_id

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


# API: Get assigned courses for staff member (Staff Courses Feature)
@staff_bp.route("/api/staff/<int:staff_id>/courses", methods=["GET"])
@login_required
def get_courses_api(staff_id):
    """
    Get all courses assigned to a staff member.
    Authorization: Only authenticated users can access, and staff can only access their own courses.
    
    Args:
        staff_id: The staff ID from the URL
    
    Returns:
        JSON with list of courses or error message
    """
    uid = session.get("user_id")
    
    # Verify that the staff_id belongs to the current user
    staff_member = get_staff_by_user_id(uid)
    
    if not staff_member or staff_member["id"] != staff_id:
        return jsonify({"error": "Unauthorized"}), 403
    
    # Retrieve the courses
    courses = get_staff_courses(staff_id)
    
    return jsonify({
        "success": True,
        "courses": courses,
        "count": len(courses)
    }), 200
