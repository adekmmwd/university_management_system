import re
from flask import Blueprint, render_template, session, jsonify, request, redirect, url_for, flash
from core.database import supabase
from core.auth import login_required, admin_required, course_coordinator_required, admin_or_head_staff_required
from epic3_staff.services import (
    get_staff_courses,
    get_staff_by_user_id,
    get_departments,
    create_announcement,
    get_pinned_announcements,
    get_announcements,
    get_announcement_by_id,
    update_announcement,
    set_announcement_archive_status,
    delete_announcement,
)
from epic2_curriculum.services import (
    list_courses_for_student,
    get_enrolled_courses_for_student,
    get_coordinated_courses_for_staff,
    get_student_by_user_id,
)

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
    if role in ["course_coordinator", "admin"]:
        departments = get_departments(preferred=(extra_info or {}).get("department"))

    available_courses = []
    if role == "student" and extra_info and extra_info.get("uuid"):
        try:
            available_courses = list_courses_for_student(extra_info["uuid"]) or []
        except Exception:
            available_courses = []

    # --- Schedule Widget data ------------------------------------------------
    schedule_courses = []
    if role == "student" and extra_info and extra_info.get("uuid"):
        try:
            schedule_courses = get_enrolled_courses_for_student(extra_info["uuid"]) or []
        except Exception:
            schedule_courses = []
    elif role in ["staff", "professor", "ta", "admin", "course_coordinator"] and extra_info:
        staff_uuid = extra_info.get("uuid")
        if staff_uuid:
            try:
                schedule_courses = get_coordinated_courses_for_staff(staff_uuid) or []
            except Exception:
                schedule_courses = []

    pinned_announcements = get_pinned_announcements()

    return render_template(
        "staff/dashboard.html",
        user=user,
        extra=extra_info,
        role=role,
        departments=departments,
        available_courses=available_courses,
        pinned_announcements=pinned_announcements,
        schedule_courses=schedule_courses,
    )


@staff_bp.route("/courses", methods=["POST"])
@login_required
def create_course():
    """Create a new course catalog record (admin or course_coordinator)."""
    uid = session.get("user_id")
    role = session.get("role")

    if role not in ["admin", "course_coordinator"]:
        flash("Access denied. Admin or Course Coordinator privileges required.", "danger")
        return redirect(url_for("staff.profile"))

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

    # For admin, created_by is optional; for coordinator it must be their staff UUID
    created_by = None
    staff_member = get_staff_by_user_id(uid)
    if staff_member and staff_member.get("uuid"):
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
        insert_data = {
            "course_code": course_code,
            "title": title,
            "description": description,
            "course_type": course_type,
            "capacity": capacity,
            "department": department,
        }
        if created_by:
            insert_data["created_by"] = created_by

        resp = (
            supabase.table("courses")
            .insert(insert_data)
            .execute()
        )

        if getattr(resp, "data", None):
            flash(f"Course {course_code} created successfully.", "success")
            return redirect(url_for("curriculum.courses_list"))

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


@staff_bp.route("/admin/announcements/new")
@login_required
@admin_or_head_staff_required
def new_announcement():
    return render_template("staff/announcement_form.html")


@staff_bp.route("/admin/announcements/create", methods=["POST"])
@login_required
@admin_or_head_staff_required
def create_announcement_route():
    title = (request.form.get("title") or "").strip()
    content = (request.form.get("content") or "").strip()
    is_pinned = bool(request.form.get("is_pinned"))
    expiry_date = (request.form.get("expiry_date") or "").strip() or None

    if not title:
        flash("Announcement title is required.", "danger")
        return redirect(url_for("staff.new_announcement"))
    if not content:
        flash("Announcement content is required.", "danger")
        return redirect(url_for("staff.new_announcement"))

    staff_member = get_staff_by_user_id(session.get("user_id"))
    if not staff_member or not staff_member.get("uuid"):
        flash("Staff profile not found for announcement creation.", "danger")
        return redirect(url_for("staff.profile"))

    created_by = staff_member["uuid"]
    success, message = create_announcement(title, content, is_pinned, created_by, expiry_date)
    if success:
        flash("Announcement posted successfully.", "success")
        return redirect(url_for("staff.manage_announcements"))

    flash(message or "Failed to post announcement. Please try again.", "danger")
    return redirect(url_for("staff.new_announcement"))


@staff_bp.route("/admin/announcements")
@login_required
@admin_or_head_staff_required
def manage_announcements():
    status = request.args.get("status", "active")
    if status not in {"active", "archived"}:
        status = "active"
    announcements = get_announcements(status)
    return render_template("staff/manage_announcements.html", announcements=announcements, status=status)


@staff_bp.route("/admin/announcements/edit/<announcement_id>")
@login_required
@admin_or_head_staff_required
def edit_announcement(announcement_id):
    announcement = get_announcement_by_id(announcement_id)
    if not announcement:
        flash("Announcement not found.", "danger")
        return redirect(url_for("staff.manage_announcements"))
    return render_template("staff/announcement_form.html", announcement=announcement)


@staff_bp.route("/admin/announcements/archive/<announcement_id>", methods=["POST"])
@login_required
@admin_or_head_staff_required
def archive_announcement(announcement_id):
    current_status = request.args.get("status", "active")
    announcement = get_announcement_by_id(announcement_id)
    if not announcement:
        flash("Announcement not found.", "danger")
        return redirect(url_for("staff.manage_announcements", status=current_status))

    archived = not bool(announcement.get("is_archived"))
    success, message = set_announcement_archive_status(announcement_id, archived)
    if success:
        flash(
            "Announcement archived." if archived else "Announcement restored.",
            "success",
        )
    else:
        flash(message or "Failed to update announcement status.", "danger")
    return redirect(url_for("staff.manage_announcements", status=current_status))


@staff_bp.route("/admin/announcements/delete/<announcement_id>", methods=["POST"])
@login_required
@admin_or_head_staff_required
def delete_announcement_route(announcement_id):
    current_status = request.args.get("status", "active")
    success, message = delete_announcement(announcement_id)
    if success:
        flash("Announcement deleted successfully.", "success")
    else:
        flash(message or "Failed to delete announcement.", "danger")
    return redirect(url_for("staff.manage_announcements", status=current_status))


@staff_bp.route("/admin/announcements/update/<announcement_id>", methods=["POST"])
@login_required
@admin_or_head_staff_required
def update_announcement_route(announcement_id):
    title = (request.form.get("title") or "").strip()
    content = (request.form.get("content") or "").strip()
    is_pinned = bool(request.form.get("is_pinned"))
    expiry_date = (request.form.get("expiry_date") or "").strip() or None

    if not title:
        flash("Announcement title is required.", "danger")
        return redirect(url_for("staff.edit_announcement", announcement_id=announcement_id))
    if not content:
        flash("Announcement content is required.", "danger")
        return redirect(url_for("staff.edit_announcement", announcement_id=announcement_id))

    success, message = update_announcement(announcement_id, title, content, is_pinned, expiry_date)
    if success:
        flash("Announcement updated successfully.", "success")
        return redirect(url_for("staff.manage_announcements"))

    flash(message or "Failed to update announcement. Please try again.", "danger")
    return redirect(url_for("staff.edit_announcement", announcement_id=announcement_id))


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


def _valid_email(e: str) -> bool:
    return bool(re.match(r"^[^@]+@[^@]+\.[^@]+$", (e or "").strip()))


def _get_all_departments():
    """Get departments from the departments table, with staff/student counts."""
    try:
        deps = supabase.table("departments").select("*").order("name").execute().data or []
        for d in deps:
            sc = supabase.table("staff").select("id", count="exact").eq("department", d["name"]).execute()
            d["staff_count"] = getattr(sc, "count", 0) or 0
            stc = supabase.table("students").select("id", count="exact").eq("department", d["name"]).execute()
            d["student_count"] = getattr(stc, "count", 0) or 0
        return deps
    except Exception:
        return []


def _get_department_names():
    """Get just department names for dropdowns."""
    try:
        deps = supabase.table("departments").select("name").order("name").execute().data or []
        names = [d["name"] for d in deps if d.get("name")]
        if not names:
            staff = supabase.table("staff").select("department").execute().data or []
            for row in staff:
                dep = (row.get("department") or "").strip()
                if dep and dep not in names:
                    names.append(dep)
        return names
    except Exception:
        return ["Computer Science", "Computer Engineering", "Electrical Engineering"]


# ── Staff Member CRUD ──

@staff_bp.route("/staff/new", methods=["GET", "POST"])
@admin_required
def staff_new():
    if request.method == "POST":
        staff_id = (request.form.get("staff_id") or "").strip()
        name = (request.form.get("name") or "").strip()
        email = (request.form.get("email") or "").strip()
        username = (request.form.get("username") or "").strip()
        role_type = (request.form.get("role_type") or "").strip()
        department = (request.form.get("department") or "").strip()
        office_hours = (request.form.get("office_hours") or "").strip() or None

        errors = []
        if not staff_id:
            errors.append("Staff ID is required.")
        else:
            resp = supabase.table("staff").select("id").eq("staff_id", staff_id).execute()
            if getattr(resp, "data", None):
                errors.append("Staff ID already exists.")

        if not name:
            errors.append("Name is required.")
        if not email or not _valid_email(email):
            errors.append("A valid email address is required.")
        else:
            resp = supabase.table("staff").select("id").eq("email", email).execute()
            if getattr(resp, "data", None):
                errors.append("Email already in use.")

        if not username:
            errors.append("Username is required.")
        else:
            resp = supabase.table("users").select("id").eq("username", username).execute()
            if getattr(resp, "data", None):
                errors.append("Username already exists.")

        if not role_type:
            errors.append("Role is required.")
        if not department:
            errors.append("Department is required.")

        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template("staff/staff_form.html", staff_member=None, departments=_get_department_names())

        # Create user record
        user_data = {
            "username": username,
            "password_hash": "INVITED_NOT_SET",
            "role": role_type,
            "full_name": name,
        }
        user_resp = supabase.table("users").insert(user_data).execute()
        new_user_id = user_resp.data[0]["id"] if getattr(user_resp, "data", None) else None

        data = {
            "staff_id": staff_id,
            "name": name,
            "email": email,
            "role_type": role_type,
            "department": department,
            "office_hours": office_hours,
            "user_id": new_user_id,
        }
        supabase.table("staff").insert(data).execute()
        flash(f"Staff member {name} added successfully.", "success")
        return redirect(url_for("staff.directory"))

    return render_template("staff/staff_form.html", staff_member=None, departments=_get_department_names())


@staff_bp.route("/staff/<int:sid>/edit", methods=["GET", "POST"])
@admin_required
def staff_edit(sid):
    resp = supabase.table("staff").select("*").eq("id", sid).limit(1).execute()
    staff_member = resp.data[0] if getattr(resp, "data", None) else None
    if not staff_member:
        flash("Staff member not found.", "danger")
        return redirect(url_for("staff.directory"))

    if staff_member.get("user_id"):
        u_resp = supabase.table("users").select("username").eq("id", staff_member["user_id"]).execute()
        if getattr(u_resp, "data", None):
            staff_member["username"] = u_resp.data[0]["username"]

    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        email = (request.form.get("email") or "").strip()
        username = (request.form.get("username") or "").strip()
        role_type = (request.form.get("role_type") or "").strip()
        department = (request.form.get("department") or "").strip()
        office_hours = (request.form.get("office_hours") or "").strip() or None

        errors = []
        if not name:
            errors.append("Name is required.")
        if not email or not _valid_email(email):
            errors.append("A valid email is required.")
        else:
            resp = supabase.table("staff").select("id").eq("email", email).execute()
            if getattr(resp, "data", None) and resp.data[0]["id"] != sid:
                errors.append("Email already in use by another staff member.")

        if not username:
            errors.append("Username is required.")
        else:
            if staff_member.get("user_id"):
                u_resp = supabase.table("users").select("id").eq("username", username).execute()
                if getattr(u_resp, "data", None) and u_resp.data[0]["id"] != staff_member["user_id"]:
                    errors.append("Username already in use by another user.")
            else:
                u_resp = supabase.table("users").select("id").eq("username", username).execute()
                if getattr(u_resp, "data", None):
                    errors.append("Username already in use by another user.")

        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template("staff/staff_form.html", staff_member=staff_member, departments=_get_department_names())

        if staff_member.get("user_id"):
            supabase.table("users").update({"username": username}).eq("id", staff_member["user_id"]).execute()

        update_data = {
            "name": name,
            "email": email,
            "role_type": role_type,
            "department": department,
            "office_hours": office_hours,
        }
        supabase.table("staff").update(update_data).eq("id", sid).execute()
        flash("Staff member updated successfully.", "success")
        return redirect(url_for("staff.directory"))

    return render_template("staff/staff_form.html", staff_member=staff_member, departments=_get_department_names())


@staff_bp.route("/staff/<int:sid>/delete", methods=["POST"])
@admin_required
def staff_delete(sid):
    resp = supabase.table("staff").select("user_id").eq("id", sid).limit(1).execute()
    staff_member = resp.data[0] if getattr(resp, "data", None) else None
    if not staff_member:
        flash("Staff member not found.", "danger")
        return redirect(url_for("staff.directory"))

    supabase.table("staff").delete().eq("id", sid).execute()
    if staff_member.get("user_id"):
        supabase.table("users").delete().eq("id", staff_member["user_id"]).execute()
        
    flash("Staff member deleted successfully.", "success")
    return redirect(url_for("staff.directory"))


# ── Department Management ──

@staff_bp.route("/admin/departments")
@admin_required
def manage_departments():
    departments = _get_all_departments()
    return render_template("staff/departments.html", departments=departments)


@staff_bp.route("/admin/departments/create", methods=["POST"])
@admin_required
def create_department():
    name = (request.form.get("name") or "").strip()
    code = (request.form.get("code") or "").strip().upper() or None
    head = (request.form.get("head") or "").strip() or None

    if not name:
        flash("Department name is required.", "danger")
        return redirect(url_for("staff.manage_departments"))

    existing = supabase.table("departments").select("id").eq("name", name).execute()
    if getattr(existing, "data", None):
        flash(f"Department '{name}' already exists.", "warning")
        return redirect(url_for("staff.manage_departments"))

    data = {"name": name}
    if code:
        data["code"] = code
    if head:
        data["head"] = head

    supabase.table("departments").insert(data).execute()
    flash(f"Department '{name}' created successfully.", "success")
    return redirect(url_for("staff.manage_departments"))


@staff_bp.route("/admin/departments/delete/<int:dept_id>", methods=["POST"])
@admin_required
def delete_department(dept_id):
    supabase.table("departments").delete().eq("id", dept_id).execute()
    flash("Department deleted.", "success")
    return redirect(url_for("staff.manage_departments"))

