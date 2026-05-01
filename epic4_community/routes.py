from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from core.database import supabase
from core.auth import login_required, admin_required
import re

community_bp = Blueprint("community", __name__)


def _valid_student_id(s: str) -> bool:
    return bool(re.match(r"^\d{7}$", (s or "").strip()))


def _valid_email(e: str) -> bool:
    return bool(re.match(r"^[^@]+@[^@]+\.[^@]+$", (e or "").strip()))


# UMS-9: List Students
@community_bp.route("/students")
@admin_required
def students_list():
    # Get filter parameters
    search = request.args.get('search', '').strip()
    department = request.args.get('department', '')
    year = request.args.get('year', '')

    # Build query (exclude archived)
    query = supabase.table("students").select("*").eq("archived", False)

    if search:
        # Search in name or student_id
        query = query.or_(f"name.ilike.%{search}%,student_id.ilike.%{search}%")

    if department:
        query = query.eq("department", department)

    if year:
        query = query.eq("year", year)

    students = query.order("name").execute().data or []

    # Get unique departments and years for filter dropdowns (active only)
    all_students = (
        supabase.table("students").select("department,year").eq("archived", False).execute().data or []
    )
    departments = sorted(set(s['department'] for s in all_students if s.get('department')))
    years = sorted(set(s['year'] for s in all_students if s.get('year')))

    return render_template(
        "community/students.html",
        students=students,
        search=search,
        department=department,
        year=year,
        departments=departments,
        years=years,
    )


# API endpoint for real-time search
@community_bp.route("/api/students/search")
@admin_required
def students_search():
    search = request.args.get('q', '').strip()
    department = request.args.get('department', '')
    year = request.args.get('year', '')

    query = supabase.table("students").select("*").eq("archived", False)

    if search:
        query = query.or_(f"name.ilike.%{search}%,student_id.ilike.%{search}%")

    if department:
        query = query.eq("department", department)

    if year:
        query = query.eq("year", year)

    students = query.order("name").limit(50).execute().data or []  # Limit for performance

    return jsonify(students)


# API: uniqueness/check endpoint
@community_bp.route("/api/students/check")
@admin_required
def api_check_student():
    student_id = (request.args.get("student_id") or "").strip()
    email = (request.args.get("email") or "").strip()
    result: dict = {}
    if student_id:
        resp = supabase.table("students").select("id").eq("student_id", student_id).execute()
        result["student_id_exists"] = bool(getattr(resp, "data", None))
    if email:
        resp = supabase.table("students").select("id").eq("email", email).execute()
        result["email_exists"] = bool(getattr(resp, "data", None))
    return jsonify(result)


# UMS-9: Create Student (form)
@community_bp.route("/students/new", methods=["GET", "POST"])
@admin_required
def student_new():
    if request.method == "POST":
        student_id = (request.form.get("student_id") or "").strip()
        name = (request.form.get("name") or "").strip()
        email = (request.form.get("email") or "").strip()
        department = (request.form.get("department") or "").strip()
        year = (request.form.get("year") or "").strip()

        errors: list[str] = []
        if not student_id or not _valid_student_id(student_id):
            errors.append("Student ID must be a 7-digit number.")
        else:
            resp = supabase.table("students").select("id").eq("student_id", student_id).execute()
            if getattr(resp, "data", None):
                errors.append("Student ID already exists.")

        if not name:
            errors.append("Name is required.")

        if not email or not _valid_email(email):
            errors.append("A valid email address is required.")
        else:
            resp = supabase.table("students").select("id").eq("email", email).execute()
            if getattr(resp, "data", None):
                errors.append("Email already exists.")

        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template("community/student_form.html", student=None)

        data = {
            "student_id": student_id,
            "name": name,
            "email": email,
            "department": department,
            "year": year,
            "status": "active",
            "archived": False,
        }
        supabase.table("students").insert(data).execute()
        flash(f"Student {name} added.", "success")
        return redirect(url_for("community.students_list"))

    return render_template("community/student_form.html", student=None)


# UMS-9: Edit Student (form)
@community_bp.route("/students/<int:sid>/edit", methods=["GET", "POST"])
@admin_required
def student_edit(sid):
    resp = supabase.table("students").select("*").eq("id", sid).limit(1).execute()
    student = resp.data[0] if getattr(resp, "data", None) else None
    if not student:
        flash("Student not found.", "danger")
        return redirect(url_for("community.students_list"))

    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        email = (request.form.get("email") or "").strip()
        department = (request.form.get("department") or "").strip()
        year = (request.form.get("year") or "").strip()

        errors: list[str] = []
        if not name:
            errors.append("Name is required.")

        if not email or not _valid_email(email):
            errors.append("A valid email is required.")
        else:
            resp = supabase.table("students").select("id").eq("email", email).execute()
            if getattr(resp, "data", None) and resp.data[0]["id"] != sid:
                errors.append("Email already in use by another student.")

        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template("community/student_form.html", student=student)

        update_data = {"name": name, "email": email, "department": department, "year": year}
        supabase.table("students").update(update_data).eq("id", sid).execute()
        flash("Student updated successfully.", "success")
        return redirect(url_for("community.students_list"))

    return render_template("community/student_form.html", student=student)


# API: Create student (JSON)
@community_bp.route("/api/students", methods=["POST"])
@admin_required
def api_create_student():
    payload = request.get_json(silent=True) or {}
    student_id = (payload.get("student_id") or "").strip()
    name = (payload.get("name") or "").strip()
    email = (payload.get("email") or "").strip()
    department = (payload.get("department") or "").strip()
    year = payload.get("year")

    errors: list[str] = []
    if not student_id or not _valid_student_id(student_id):
        errors.append("Student ID must be a 7-digit number.")
    else:
        resp = supabase.table("students").select("id").eq("student_id", student_id).execute()
        if getattr(resp, "data", None):
            errors.append("Student ID already exists.")

    if not name:
        errors.append("Name is required.")

    if not email or not _valid_email(email):
        errors.append("A valid email address is required.")
    else:
        resp = supabase.table("students").select("id").eq("email", email).execute()
        if getattr(resp, "data", None):
            errors.append("Email already exists.")

    if errors:
        return jsonify({"errors": errors}), 400

    data = {
        "student_id": student_id,
        "name": name,
        "email": email,
        "department": department,
        "year": year,
        "status": "active",
        "archived": False,
    }
    resp = supabase.table("students").insert(data).execute()
    new = resp.data[0] if getattr(resp, "data", None) else None
    return jsonify(new or {"message": "created"}), 201


# API: Update student (JSON)
@community_bp.route("/api/students/<int:sid>", methods=["PUT"])
@admin_required
def api_update_student(sid):
    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()
    email = (payload.get("email") or "").strip()
    department = (payload.get("department") or "").strip()
    year = payload.get("year")

    resp = supabase.table("students").select("*").eq("id", sid).limit(1).execute()
    student = resp.data[0] if getattr(resp, "data", None) else None
    if not student:
        return jsonify({"error": "Student not found"}), 404

    errors: list[str] = []
    if not name:
        errors.append("Name is required.")
    if not email or not _valid_email(email):
        errors.append("A valid email is required.")
    else:
        resp = supabase.table("students").select("id").eq("email", email).execute()
        if getattr(resp, "data", None) and resp.data[0]["id"] != sid:
            errors.append("Email already in use by another student.")

    if errors:
        return jsonify({"errors": errors}), 400

    update_data = {"name": name, "email": email, "department": department, "year": year}
    resp = supabase.table("students").update(update_data).eq("id", sid).execute()
    updated = resp.data[0] if getattr(resp, "data", None) else None
    return jsonify(updated or {"message": "updated"}), 200


# API: Delete or archive student
@community_bp.route("/api/students/<int:sid>", methods=["DELETE"])
@admin_required
def api_delete_student(sid):
    resp = supabase.table("students").select("id,status,archived").eq("id", sid).limit(1).execute()
    student = resp.data[0] if getattr(resp, "data", None) else None
    if not student:
        return jsonify({"error": "Student not found"}), 404

    if student.get("archived"):
        return jsonify({"message": "Student already archived", "id": sid}), 200

    status = (student.get("status") or "").strip().lower()
    if status == "graduate":
        supabase.table("students").update({"archived": True}).eq("id", sid).execute()
        return jsonify({"archived": True, "id": sid}), 200
    else:
        supabase.table("students").delete().eq("id", sid).execute()
        return jsonify({"deleted": True, "id": sid}), 200
