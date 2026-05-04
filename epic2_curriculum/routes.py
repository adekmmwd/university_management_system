import uuid

from flask import Blueprint, flash, jsonify, redirect, render_template, request, session, url_for

from core.auth import login_required
from epic2_curriculum.services import (
    can_delete_course,
    deactivate_course,
    delete_course,
    get_all_courses,
    get_course,
    get_student_by_user_id,
    get_student_department,
    get_subjects_by_department,
    get_ta_sections,
    register_student_for_course,
    update_course,
    update_section_responsibility,
)

curriculum_bp = Blueprint("curriculum", __name__)


def staff_required(f):
    """Decorator to require staff-like privileges."""

    from functools import wraps

    @wraps(f)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in first.", "warning")
            return redirect(url_for("auth.login"))

        role = session.get("role")
        if role not in ["staff", "professor", "ta", "admin", "course_coordinator"]:
            flash("Access denied. Staff privileges required.", "danger")
            return redirect(url_for("staff.profile"))

        return f(*args, **kwargs)

    return wrapped


def student_required(f):
    """Decorator to require student role."""

    from functools import wraps

    @wraps(f)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in first.", "warning")
            return redirect(url_for("auth.login"))
        if session.get("role") != "student":
            flash("Access denied. Student privileges required.", "danger")
            return redirect(url_for("staff.profile"))
        return f(*args, **kwargs)

    return wrapped


def ta_required(f):
    """Decorator to require TA role."""

    from functools import wraps

    @wraps(f)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in first.", "warning")
            return redirect(url_for("auth.login"))
        if session.get("role") != "ta":
            flash("Access denied. TA privileges required.", "danger")
            return redirect(url_for("staff.profile"))
        return f(*args, **kwargs)

    return wrapped


def coordinator_required(f):
    """Decorator to require Course Coordinator role."""

    from functools import wraps

    @wraps(f)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in first.", "warning")
            return redirect(url_for("auth.login"))
        if session.get("role") != "course_coordinator":
            flash("Access denied. Course Coordinator privileges required.", "danger")
            return redirect(url_for("staff.profile"))
        return f(*args, **kwargs)

    return wrapped


@curriculum_bp.route("/courses/<course_id>/register", methods=["POST"])
@login_required
def register_course(course_id: str):
    if session.get("role") != "student":
        flash("Only students can register for courses.", "danger")
        return redirect(url_for("staff.profile"))

    uid = session.get("user_id")
    student = get_student_by_user_id(uid)
    if not student or not student.get("uuid"):
        flash("Student profile not found.", "danger")
        return redirect(url_for("staff.profile"))

    try:
        uuid.UUID(course_id)
    except ValueError:
        flash("Invalid course id.", "danger")
        return redirect(url_for("staff.profile"))

    try:
        register_student_for_course(student["uuid"], course_id)
        flash("Registered successfully.", "success")
        return redirect(url_for("staff.profile"))
    except Exception as e:
        msg = str(e).lower()

        if "department_mismatch" in msg:
            flash("You can only register for courses in your department.", "danger")
        elif "course_full" in msg:
            flash("Registration failed: course capacity is full.", "danger")
        elif "already_enrolled" in msg:
            flash("You are already registered for this course.", "warning")
        elif "student_not_found" in msg:
            flash("Student profile not found.", "danger")
        elif "course_not_found" in msg:
            flash("Course not found.", "danger")
        else:
            flash("Registration failed. Please try again.", "danger")

        return redirect(url_for("staff.profile"))


@curriculum_bp.route("/courses")
@login_required
def courses_list():
    role = session.get("role")
    courses = get_all_courses()
    return render_template("curriculum/courses.html", courses=courses, role=role)


@curriculum_bp.route("/edit-course/<course_id>")
@login_required
@staff_required
def edit_course(course_id: str):
    course = get_course(course_id)
    if not course:
        flash("Course not found.", "danger")
        return redirect(url_for("curriculum.courses_list"))
    return render_template("curriculum/edit_course.html", course=course)


@curriculum_bp.route("/update-course/<course_id>", methods=["POST"])
@login_required
@staff_required
def update_course_route(course_id: str):
    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    capacity_str = request.form.get("capacity", "").strip()

    errors: list[str] = []
    if not title:
        errors.append("Title is required.")
    if not description:
        errors.append("Description is required.")

    capacity: int | None = None
    if capacity_str:
        try:
            capacity = int(capacity_str)
            if capacity <= 0:
                errors.append("Capacity must be a positive integer.")
        except ValueError:
            errors.append("Capacity must be a valid number.")
    else:
        errors.append("Capacity is required.")

    if errors:
        for error in errors:
            flash(error, "danger")
        return redirect(url_for("curriculum.edit_course", course_id=course_id))

    result = update_course(course_id=course_id, title=title, description=description, capacity=capacity)
    if result:
        flash("Course updated successfully!", "success")
        return redirect(url_for("curriculum.courses_list"))

    flash("Failed to update course. Please try again.", "danger")
    return redirect(url_for("curriculum.edit_course", course_id=course_id))


@curriculum_bp.route("/my-curriculum")
@login_required
@student_required
def my_curriculum():
    user_id = session.get("user_id")
    department = get_student_department(user_id)

    if not department:
        flash("Unable to determine your department. Please update your profile.", "warning")
        return render_template(
            "curriculum/subject_list.html",
            department=None,
            core_subjects=[],
            elective_subjects=[],
        )

    subjects = get_subjects_by_department(department)
    core_subjects = [s for s in subjects if s.get("subject_type", "Elective").lower() == "core"]
    elective_subjects = [s for s in subjects if s.get("subject_type", "Elective").lower() != "core"]

    return render_template(
        "curriculum/subject_list.html",
        department=department,
        core_subjects=core_subjects,
        elective_subjects=elective_subjects,
    )


# ============================================================================
# Feature 1: TA Responsibility Update - Routes
# ============================================================================


@curriculum_bp.route("/ta/sections", methods=["GET"])
@login_required
@ta_required
def view_ta_sections():
    """TA views their assigned sections with responsibility field."""
    user_id = session.get("user_id")
    
    # Get TA's UUID from staff table
    try:
        from core.database import supabase
        staff_resp = (
            supabase.table("staff")
            .select("uuid")
            .eq("id", user_id)
            .limit(1)
            .execute()
        )
        if not getattr(staff_resp, "data", None):
            flash("Staff profile not found.", "danger")
            return redirect(url_for("staff.profile"))
        
        ta_uuid = staff_resp.data[0]["uuid"]
        sections = get_ta_sections(ta_uuid)
        
        return render_template("curriculum/ta_sections.html", sections=sections)
    except Exception as e:
        print(f"Error retrieving TA sections: {e}")
        flash("Error retrieving your sections.", "danger")
        return redirect(url_for("staff.profile"))


@curriculum_bp.route("/ta/sections/<section_id>/update", methods=["POST"])
@login_required
@ta_required
def update_ta_responsibility(section_id: str):
    """TA updates their responsibility for a section."""
    try:
        uuid.UUID(section_id)
    except ValueError:
        flash("Invalid section id.", "danger")
        return redirect(url_for("curriculum.view_ta_sections"))

    responsibility = request.form.get("responsibility", "").strip()

    # Validate responsibility
    if len(responsibility) > 500:
        flash("Responsibility must be max 500 characters.", "danger")
        return redirect(url_for("curriculum.view_ta_sections"))

    result = update_section_responsibility(section_id, responsibility)
    
    if result:
        flash("Responsibility updated successfully!", "success")
        return redirect(url_for("curriculum.view_ta_sections"))

    flash("Failed to update responsibility. Please try again.", "danger")
    return redirect(url_for("curriculum.view_ta_sections"))


# ============================================================================
# Feature 2: Course Deactivation / Deletion - Routes
# ============================================================================


@curriculum_bp.route("/courses/<course_id>/deactivate", methods=["POST"])
@login_required
@coordinator_required
def deactivate_course_route(course_id: str):
    """Course Coordinator marks a course as Inactive."""
    try:
        uuid.UUID(course_id)
    except ValueError:
        flash("Invalid course id.", "danger")
        return redirect(url_for("curriculum.courses_list"))

    result = deactivate_course(course_id)
    
    if result:
        flash(f"Course '{result.get('title', 'Unknown')}' marked as Inactive.", "success")
        return redirect(url_for("curriculum.courses_list"))

    flash("Failed to deactivate course. Please try again.", "danger")
    return redirect(url_for("curriculum.courses_list"))


@curriculum_bp.route("/courses/<course_id>/delete", methods=["POST"])
@login_required
@coordinator_required
def delete_course_route(course_id: str):
    """Course Coordinator deletes a course (only if no students enrolled)."""
    try:
        uuid.UUID(course_id)
    except ValueError:
        flash("Invalid course id.", "danger")
        return redirect(url_for("curriculum.courses_list"))

    # Get course info before deletion
    course = get_course(course_id)
    
    if not course:
        flash("Course not found.", "danger")
        return redirect(url_for("curriculum.courses_list"))

    # Check if course can be deleted
    if not can_delete_course(course_id):
        flash(
            f"Cannot delete '{course.get('title', 'Unknown')}' because students are enrolled.",
            "danger",
        )
        return redirect(url_for("curriculum.courses_list"))

    # Delete the course
    success = delete_course(course_id)
    
    if success:
        flash(f"Course '{course.get('title', 'Unknown')}' deleted successfully.", "success")
        return redirect(url_for("curriculum.courses_list"))

    flash("Failed to delete course. Please try again.", "danger")
    return redirect(url_for("curriculum.courses_list"))


# ============================================================================
# JSON API Endpoints for both features
# ============================================================================


@curriculum_bp.route("/api/ta/sections", methods=["GET"])
@login_required
def api_get_ta_sections():
    """API: Get TA's assigned sections."""
    if session.get("role") != "ta":
        return jsonify({"error": "Unauthorized"}), 403

    user_id = session.get("user_id")

    try:
        from core.database import supabase

        staff_resp = (
            supabase.table("staff")
            .select("uuid")
            .eq("id", user_id)
            .limit(1)
            .execute()
        )
        if not getattr(staff_resp, "data", None):
            return jsonify({"error": "Staff profile not found"}), 404

        ta_uuid = staff_resp.data[0]["uuid"]
        sections = get_ta_sections(ta_uuid)

        return jsonify({"success": True, "sections": sections}), 200
    except Exception as e:
        print(f"Error retrieving TA sections: {e}")
        return jsonify({"error": str(e)}), 500


@curriculum_bp.route("/api/sections/<section_id>/responsibility", methods=["PUT", "PATCH"])
@login_required
def api_update_section_responsibility(section_id: str):
    """API: Update section responsibility."""
    if session.get("role") != "ta":
        return jsonify({"error": "Unauthorized"}), 403

    try:
        uuid.UUID(section_id)
    except ValueError:
        return jsonify({"error": "Invalid section id"}), 400

    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400

    responsibility = data.get("responsibility", "").strip()

    # Validate responsibility
    if len(responsibility) > 500:
        return jsonify({"error": "Responsibility must be max 500 characters"}), 400

    result = update_section_responsibility(section_id, responsibility)

    if result:
        return jsonify({"success": True, "section": result}), 200

    return jsonify({"error": "Failed to update responsibility"}), 500


@curriculum_bp.route("/api/courses/<course_id>/deactivate", methods=["POST"])
@login_required
def api_deactivate_course(course_id: str):
    """API: Deactivate a course."""
    if session.get("role") != "course_coordinator":
        return jsonify({"error": "Unauthorized"}), 403

    try:
        uuid.UUID(course_id)
    except ValueError:
        return jsonify({"error": "Invalid course id"}), 400

    result = deactivate_course(course_id)

    if result:
        return jsonify({"success": True, "course": result}), 200

    return jsonify({"error": "Failed to deactivate course"}), 500


@curriculum_bp.route("/api/courses/<course_id>/delete", methods=["DELETE"])
@login_required
def api_delete_course(course_id: str):
    """API: Delete a course (only if no students enrolled)."""
    if session.get("role") != "course_coordinator":
        return jsonify({"error": "Unauthorized"}), 403

    try:
        uuid.UUID(course_id)
    except ValueError:
        return jsonify({"error": "Invalid course id"}), 400

    course = get_course(course_id)

    if not course:
        return jsonify({"error": "Course not found"}), 404

    # Check if course can be deleted
    if not can_delete_course(course_id):
        return (
            jsonify(
                {
                    "error": "Cannot delete course with enrolled students",
                    "enrolled": True,
                }
            ),
            409,
        )

    # Delete the course
    success = delete_course(course_id)

    if success:
        return jsonify({"success": True, "message": "Course deleted successfully"}), 200

    return jsonify({"error": "Failed to delete course"}), 500


@curriculum_bp.route("/api/courses/<course_id>/can-delete", methods=["GET"])
@login_required
def api_check_delete_course(course_id: str):
    """API: Check if a course can be deleted."""
    if session.get("role") != "course_coordinator":
        return jsonify({"error": "Unauthorized"}), 403

    try:
        uuid.UUID(course_id)
    except ValueError:
        return jsonify({"error": "Invalid course id"}), 400

    course = get_course(course_id)

    if not course:
        return jsonify({"error": "Course not found"}), 404

    can_delete = can_delete_course(course_id)

    return (
        jsonify(
            {
                "success": True,
                "can_delete": can_delete,
                "course_id": course_id,
                "course_title": course.get("title", "Unknown"),
            }
        ),
        200,
    )
