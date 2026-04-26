from flask import Blueprint, render_template, request, redirect, url_for, flash
from core.database import supabase
from core.auth import login_required

community_bp = Blueprint("community", __name__)


# UMS-9: List Students
@community_bp.route("/students")
@login_required
def students_list():
    students = supabase.table("students").select("*").order("name").execute().data
    return render_template("community/students.html", students=students)


# UMS-9: Create Student
@community_bp.route("/students/new", methods=["GET", "POST"])
@login_required
def student_new():
    if request.method == "POST":
        data = {
            "student_id": request.form.get("student_id"),
            "name": request.form.get("name"),
            "email": request.form.get("email"),
            "department": request.form.get("department"),
            "year": request.form.get("year"),
        }
        supabase.table("students").insert(data).execute()
        flash(f"Student {data['name']} added.", "success")
        return redirect(url_for("community.students_list"))

    return render_template("community/student_form.html", student=None)


# UMS-9: Edit Student
@community_bp.route("/students/<int:sid>/edit", methods=["GET", "POST"])
@login_required
def student_edit(sid):
    if request.method == "POST":
        data = {
            "name": request.form.get("name"),
            "email": request.form.get("email"),
            "department": request.form.get("department"),
            "year": request.form.get("year"),
        }
        supabase.table("students").update(data).eq("id", sid).execute()
        flash("Student updated successfully.", "success")
        return redirect(url_for("community.students_list"))

    resp = supabase.table("students").select("*").eq("id", sid).execute()
    student = resp.data[0] if resp.data else None
    return render_template("community/student_form.html", student=student)
