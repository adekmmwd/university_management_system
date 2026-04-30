from flask import Blueprint, render_template, session, jsonify, request, redirect, url_for, flash
from core.database import supabase
from core.auth import login_required, course_coordinator_required
from epic3_staff.services import get_staff_courses, get_staff_by_user_id, get_departments
from epic2_curriculum.services import list_courses_for_student

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
    elif role in ["staff", "professor", "ta", "admin", "course_coordinator"]:
        resp = supabase.table("staff").select("*").eq("user_id", uid).execute()
        extra_info = resp.data[0] if resp.data else None

    departments = []
    if role == "course_coordinator":
        departments = get_departments(preferred=(extra_info or {}).get("department"))

    available_courses = []
    if role == "student" and extra_info and extra_info.get("uuid"):
        try:
            available_courses = list_courses_for_student(extra_info["uuid"]) or []
        except Exception:
            available_courses = []

    return render_template(
        "staff/dashboard.html",
        user=user,
        extra=extra_info,
        role=role,
        departments=departments,
        available_courses=available_courses,
    )


@staff_bp.route("/courses", methods=["POST"])
@login_required
@course_coordinator_required
def create_course():
    """Create a new course catalog record (CREATE only)."""
    uid = session.get("user_id")

    course_code = request.form.get("course_code", "").strip().upper()
    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip() or None
    course_type = request.form.get("course_type", "").strip()
    department = request.form.get("department", "").strip()
    capacity_raw = request.form.get("capacity", "").strip()

    if not course_code:
        flash("Course code is required.", "danger")
        return redirect(url_for("staff.profile"))
    if not title:
        flash("Course title is required.", "danger")
        return redirect(url_for("staff.profile"))
    if course_type not in ["Core", "Elective"]:
        flash("Course type must be Core or Elective.", "danger")
        return redirect(url_for("staff.profile"))
    if not department:
        flash("Department is required.", "danger")
        return redirect(url_for("staff.profile"))

    try:
        capacity = int(capacity_raw) if capacity_raw else 50
        if capacity <= 0:
            raise ValueError()
    except ValueError:
        flash("Capacity must be a positive number.", "danger")
        return redirect(url_for("staff.profile"))

    staff_member = get_staff_by_user_id(uid)
    if not staff_member or not staff_member.get("uuid"):
        flash("Staff profile not found for this user.", "danger")
        return redirect(url_for("staff.profile"))

    created_by = staff_member["uuid"]

    existing = (
        supabase.table("courses")
        .select("id")
        .eq("course_code", course_code)
        .limit(1)
        .execute()
    )
    if getattr(existing, "data", None):
        flash(
            f"Course code {course_code} already exists. Please choose a different code.",
            "danger",
        )
        return redirect(url_for("staff.profile"))

    try:
        resp = (
            supabase.table("courses")
            .insert(
                {
                    "course_code": course_code,
                    "title": title,
                    "description": description,
                    "course_type": course_type,
                    "capacity": capacity,
                    "department": department,
                    "created_by": created_by,
                }
            )
            .execute()
        )

        if getattr(resp, "data", None):
            flash("Course created successfully.", "success")
            return redirect(url_for("staff.profile"))

        error = getattr(resp, "error", None)
        if error:
            msg = str(error)
            if "duplicate" in msg.lower() or "unique" in msg.lower():
                flash(
                    f"Course code {course_code} already exists. Please choose a different code.",
                    "danger",
                )
            else:
                flash("Failed to create course. Please try again.", "danger")
            return redirect(url_for("staff.profile"))

        flash("Failed to create course. Please try again.", "danger")
        return redirect(url_for("staff.profile"))

    except Exception as e:
        msg = str(e)
        if "duplicate" in msg.lower() or "unique" in msg.lower():
            flash(
                f"Course code {course_code} already exists. Please choose a different code.",
                "danger",
            )
        else:
            flash("Failed to create course. Please try again.", "danger")
        return redirect(url_for("staff.profile"))


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
