from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from core.database import supabase
from core.auth import login_required, admin_required

community_bp = Blueprint("community", __name__)


# UMS-9: List Students
@community_bp.route("/students")
@admin_required
def students_list():
    # Get filter parameters
    search = request.args.get('search', '').strip()
    department = request.args.get('department', '')
    year = request.args.get('year', '')
    
    # Build query
    query = supabase.table("students").select("*")
    
    if search:
        # Search in name or student_id
        query = query.or_(f"name.ilike.%{search}%,student_id.ilike.%{search}%")
    
    if department:
        query = query.eq("department", department)
    
    if year:
        query = query.eq("year", year)
    
    students = query.order("name").execute().data
    
    # Get unique departments and years for filter dropdowns
    all_students = supabase.table("students").select("department,year").execute().data
    departments = sorted(set(s['department'] for s in all_students if s['department']))
    years = sorted(set(s['year'] for s in all_students if s['year']))
    
    return render_template("community/students.html", 
                         students=students, 
                         search=search, 
                         department=department, 
                         year=year,
                         departments=departments,
                         years=years)


# API endpoint for real-time search
@community_bp.route("/api/students/search")
@admin_required
def students_search():
    search = request.args.get('q', '').strip()
    department = request.args.get('department', '')
    year = request.args.get('year', '')
    
    query = supabase.table("students").select("*")
    
    if search:
        query = query.or_(f"name.ilike.%{search}%,student_id.ilike.%{search}%")
    
    if department:
        query = query.eq("department", department)
    
    if year:
        query = query.eq("year", year)
    
    students = query.order("name").limit(50).execute().data  # Limit for performance
    
    return jsonify(students)


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
