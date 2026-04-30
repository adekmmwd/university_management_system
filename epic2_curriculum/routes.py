import uuid

from flask import Blueprint, flash, redirect, request, session, url_for

from core.auth import login_required
from epic2_curriculum.services import get_student_by_user_id, register_student_for_course


curriculum_bp = Blueprint("curriculum", __name__)


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
