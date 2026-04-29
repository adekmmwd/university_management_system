from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from core.auth import login_required
from epic2_curriculum.services import (
    get_course,
    get_all_courses,
    get_student_department,
    get_subjects_by_department,
    update_course,
)

curriculum_bp = Blueprint("curriculum", __name__)


def staff_required(f):
    """Decorator to require staff or admin role"""
    from functools import wraps
    @wraps(f)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in first.", "warning")
            return redirect(url_for("auth.login"))
        role = session.get("role")
        if role not in ["staff", "professor", "ta", "admin"]:
            flash("Access denied. Staff privileges required.", "danger")
            return redirect(url_for("staff.profile"))
        return f(*args, **kwargs)
    return wrapped


def student_required(f):
    """Decorator to require student role"""
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


# UMS-Epic2: Edit Course Information
@curriculum_bp.route("/courses")
@login_required
def courses_list():
    """Display all courses (for coordinators)"""
    role = session.get("role")
    courses = get_all_courses()
    return render_template("curriculum/courses.html", courses=courses, role=role)


# GET: Show edit form for a course
@curriculum_bp.route("/edit-course/<int:course_id>")
@login_required
@staff_required
def edit_course(course_id):
    """Display the edit form for a specific course"""
    course = get_course(course_id)
    
    if not course:
        flash("Course not found.", "danger")
        return redirect(url_for("curriculum.courses_list"))
    
    return render_template("curriculum/edit_course.html", course=course)


# POST: Update a course
@curriculum_bp.route("/update-course/<int:course_id>", methods=["POST"])
@login_required
@staff_required
def update_course_route(course_id):
    """Handle the course update form submission"""
    # Get form data
    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    capacity_str = request.form.get("capacity", "").strip()
    
    # Validation
    errors = []
    
    if not title:
        errors.append("Title is required.")
    
    if not description:
        errors.append("Description is required.")
    
    capacity = None
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
    
    # Update the course
    result = update_course(
        course_id=course_id,
        title=title,
        description=description,
        capacity=capacity
    )
    
    if result:
        flash("Course updated successfully!", "success")
        return redirect(url_for("curriculum.courses_list"))
    else:
        flash("Failed to update course. Please try again.", "danger")
        return redirect(url_for("curriculum.edit_course", course_id=course_id))


# UMS-Epic2: Student Subject List
@curriculum_bp.route("/my-curriculum")
@login_required
@student_required
def my_curriculum():
    """Display the student's department curriculum list"""
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