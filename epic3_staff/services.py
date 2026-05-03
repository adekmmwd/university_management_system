from datetime import datetime, timezone

from core.database import supabase


def get_staff_courses(staff_id):
    """
    Retrieve all courses assigned to a staff member.
    
    Args:
        staff_id: The ID of the staff member (from staff table)
    
    Returns:
        A list of courses with role information, or an empty list if no courses found
    """
    try:
        # Query staff_courses with joined course information
        response = supabase.table("staff_courses").select(
            "id, role, academic_year, courses(id, course_code, title, department)"
        ).eq("staff_id", staff_id).execute()
        
        if not response.data:
            return []
        
        # Transform the response into the required format
        courses = []
        for assignment in response.data:
            if assignment.get("courses"):
                course_data = assignment["courses"]
                courses.append({
                    "course_id": course_data.get("course_code"),
                    "course_name": course_data.get("title"),
                    "department": course_data.get("department"),
                    "role": assignment.get("role", "Professor"),
                    "academic_year": assignment.get("academic_year")
                })
        
        return courses
    
    except Exception as e:
        print(f"Error retrieving courses for staff {staff_id}: {str(e)}")
        return []


def get_staff_by_user_id(user_id):
    """
    Get the staff record for a given user_id.
    
    Args:
        user_id: The user ID
    
    Returns:
        The staff record or None if not found
    """
    try:
        response = supabase.table("staff").select("id, staff_id, name, uuid, department").eq("user_id", user_id).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        print(f"Error retrieving staff record for user {user_id}: {str(e)}")
        return None


def get_departments(preferred=None):
    """Get a stable list of departments for dropdowns."""
    try:
        staff = supabase.table("staff").select("department").execute().data or []
        departments = []
        for row in staff:
            dep = (row.get("department") or "").strip()
            if dep and dep not in departments:
                departments.append(dep)

        if preferred:
            preferred = preferred.strip()
            if preferred and preferred in departments:
                departments = [preferred] + [d for d in departments if d != preferred]
            elif preferred:
                departments = [preferred] + departments

        return sorted(departments) if not preferred else departments
    except Exception as e:
        print(f"Error retrieving departments: {str(e)}")
        return [preferred] if preferred else []


def create_announcement(title, content, is_pinned, created_by, expiry_date=None):
    try:
        payload = {
            "title": title,
            "content": content,
            "is_pinned": is_pinned,
            "is_archived": False,
            "created_by": created_by,
        }
        if expiry_date:
            payload["expiry_date"] = expiry_date

        resp = supabase.table("announcements").insert(payload).execute()
        if getattr(resp, "data", None):
            return True, None
        return False, str(getattr(resp, "error", "Unknown error"))
    except Exception as e:
        return False, str(e)


def get_pinned_announcements():
    try:
        now = datetime.now(timezone.utc).isoformat()
        resp = (
            supabase.table("announcements")
            .select("*")
            .eq("is_pinned", True)
            .eq("is_archived", False)
            .or_(f"expiry_date.is.null,expiry_date.gte.{now}")
            .order("created_at", ascending=False)
            .limit(5)
            .execute()
        )
        return resp.data or []
    except Exception as e:
        print(f"Error retrieving pinned announcements: {str(e)}")
        return []


def get_announcements(status="active"):
    try:
        query = supabase.table("announcements").select("*").order("created_at", ascending=False)
        if status == "active":
            now = datetime.now(timezone.utc).isoformat()
            query = query.eq("is_archived", False).or_(f"expiry_date.is.null,expiry_date.gte.{now}")
        elif status == "archived":
            query = query.eq("is_archived", True)
        resp = query.execute()
        return resp.data or []
    except Exception as e:
        print(f"Error retrieving announcements: {str(e)}")
        return []


def get_announcement_by_id(announcement_id):
    try:
        resp = (
            supabase.table("announcements")
            .select("*")
            .eq("id", announcement_id)
            .limit(1)
            .execute()
        )
        return resp.data[0] if getattr(resp, "data", None) else None
    except Exception as e:
        print(f"Error retrieving announcement {announcement_id}: {str(e)}")
        return None


def update_announcement(announcement_id, title, content, is_pinned, expiry_date=None):
    try:
        payload = {
            "title": title,
            "content": content,
            "is_pinned": is_pinned,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        if expiry_date is not None:
            payload["expiry_date"] = expiry_date

        resp = (
            supabase.table("announcements")
            .update(payload)
            .eq("id", announcement_id)
            .execute()
        )
        if getattr(resp, "data", None):
            return True, None
        return False, str(getattr(resp, "error", "Unknown error"))
    except Exception as e:
        return False, str(e)


def set_announcement_archive_status(announcement_id, archived):
    try:
        resp = (
            supabase.table("announcements")
            .update({"is_archived": archived, "updated_at": datetime.now(timezone.utc).isoformat()})
            .eq("id", announcement_id)
            .execute()
        )
        if getattr(resp, "data", None):
            return True, None
        return False, str(getattr(resp, "error", "Unknown error"))
    except Exception as e:
        return False, str(e)


def delete_announcement(announcement_id):
    try:
        resp = supabase.table("announcements").delete().eq("id", announcement_id).execute()
        if getattr(resp, "data", None):
            return True, None
        return False, str(getattr(resp, "error", "Unknown error"))
    except Exception as e:
        return False, str(e)
