from __future__ import annotations

from typing import Any, Optional

from core.database import supabase


def get_student_by_user_id(user_id: int) -> Optional[dict[str, Any]]:
    resp = (
        supabase.table("students")
        .select("id, user_id, uuid, student_id, name, email, department, year")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    return resp.data[0] if getattr(resp, "data", None) else None


def get_student_department(user_id: int) -> Optional[str]:
    try:
        resp = (
            supabase.table("students")
            .select("department")
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        return resp.data[0]["department"] if getattr(resp, "data", None) else None
    except Exception:
        return None


def list_courses_for_student(student_uuid: str) -> list[dict[str, Any]]:
    resp = supabase.rpc("list_courses_for_student", {"p_student_uuid": student_uuid}).execute()
    return resp.data or []


def register_student_for_course(student_uuid: str, course_id: str) -> str:
    resp = supabase.rpc(
        "register_for_course",
        {"p_student_uuid": student_uuid, "p_course_id": course_id},
    ).execute()

    # PostgREST returns scalar results as a single-element list in some cases;
    # but may also return the raw scalar depending on configuration.
    data = getattr(resp, "data", None)
    if isinstance(data, list) and data:
        return str(data[0])
    if data is None:
        raise RuntimeError("Registration failed.")
    return str(data)


def _normalize_course_record(course: dict[str, Any]) -> dict[str, Any]:
    # The live schema uses `title` + `course_type`. Some templates still refer
    # to `course_name` + `subject_type`, so provide compatibility fields.
    if "course_name" not in course and "title" in course:
        course["course_name"] = course.get("title")
    if "subject_type" not in course and "course_type" in course:
        course["subject_type"] = course.get("course_type")
    return course


def get_course(course_id: str) -> Optional[dict[str, Any]]:
    try:
        resp = supabase.table("courses").select("*").eq("id", course_id).limit(1).execute()
        course = resp.data[0] if getattr(resp, "data", None) else None
        return _normalize_course_record(course) if course else None
    except Exception:
        return None


def get_all_courses() -> list[dict[str, Any]]:
    try:
        resp = supabase.table("courses").select("*").order("course_code").execute()
        courses = resp.data if getattr(resp, "data", None) else []
        return [_normalize_course_record(c) for c in courses]
    except Exception:
        return []


def get_subjects_by_department(department: str) -> list[dict[str, Any]]:
    try:
        resp = (
            supabase.table("courses")
            .select("id, course_code, title, description, course_type, capacity, department")
            .eq("department", department)
            .order("course_code")
            .execute()
        )
        subjects = resp.data if getattr(resp, "data", None) else []
        normalized: list[dict[str, Any]] = []
        for subject in subjects:
            subject = _normalize_course_record(subject)
            subject["subject_type"] = subject.get("subject_type") or "Elective"
            normalized.append(subject)
        return normalized
    except Exception:
        return []


def get_enrolled_courses_for_student(student_uuid: str) -> list[dict[str, Any]]:
    """Return the courses a student is currently enrolled in.

    Used by the Schedule Widget on the student dashboard.

    Args:
        student_uuid: The student's UUID from the students table.

    Returns:
        A list of course dicts with keys: id, course_code, title, course_type, department.
    """
    try:
        resp = (
            supabase.table("enrollments")
            .select("course_id, courses(id, course_code, title, course_type, department)")
            .eq("student_id", student_uuid)
            .execute()
        )
        rows = resp.data if getattr(resp, "data", None) else []
        courses: list[dict[str, Any]] = []
        for row in rows:
            course = row.get("courses")
            if course:
                courses.append(
                    {
                        "id": course.get("id"),
                        "course_code": course.get("course_code"),
                        "title": course.get("title"),
                        "course_type": course.get("course_type"),
                        "department": course.get("department"),
                    }
                )
        # Sort by course_code for consistent display
        courses.sort(key=lambda c: c.get("course_code", ""))
        return courses
    except Exception as e:
        print(f"Error retrieving enrolled courses for student {student_uuid}: {e}")
        return []


def get_coordinated_courses_for_staff(staff_uuid: str) -> list[dict[str, Any]]:
    """Return the courses a staff member created / coordinates.

    Used by the Schedule Widget on the staff dashboard.

    Args:
        staff_uuid: The staff member's UUID from the staff table.

    Returns:
        A list of course dicts with keys: id, course_code, title, course_type,
        capacity, department.
    """
    try:
        resp = (
            supabase.table("courses")
            .select("id, course_code, title, course_type, capacity, department")
            .eq("created_by", staff_uuid)
            .order("course_code")
            .execute()
        )
        return resp.data if getattr(resp, "data", None) else []
    except Exception as e:
        print(f"Error retrieving coordinated courses for staff {staff_uuid}: {e}")
        return []


def update_course(
    course_id: str,
    title: Optional[str] = None,
    description: Optional[str] = None,
    capacity: Optional[int] = None,
) -> Optional[dict[str, Any]]:
    try:
        update_data: dict[str, Any] = {}
        if title is not None:
            update_data["title"] = title
        if description is not None:
            update_data["description"] = description
        if capacity is not None:
            update_data["capacity"] = capacity

        if not update_data:
            return None

        resp = supabase.table("courses").update(update_data).eq("id", course_id).execute()
        course = resp.data[0] if getattr(resp, "data", None) else None
        return _normalize_course_record(course) if course else None
    except Exception:
        return None
