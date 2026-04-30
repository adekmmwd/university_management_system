import uuid

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from core.auth import login_required
from epic2_curriculum.services import (
    get_all_courses,
    get_course,
    get_student_by_user_id,
    get_student_department,
    get_subjects_by_department,
    register_student_for_course,
    update_course,
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
