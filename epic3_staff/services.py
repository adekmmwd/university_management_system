from core.database import supabase
from flask import jsonify


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
            "id, role, academic_year, courses(id, course_code, course_name, department)"
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
                    "course_name": course_data.get("course_name"),
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
        response = supabase.table("staff").select("id, staff_id, name").eq("user_id", user_id).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        print(f"Error retrieving staff record for user {user_id}: {str(e)}")
        return None
