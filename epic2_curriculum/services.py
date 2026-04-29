from core.database import supabase


def get_course(course_id):
    """
    Retrieve a course by its ID.
    
    Args:
        course_id: The ID of the course to retrieve
    
    Returns:
        The course record or None if not found
    """
    try:
        response = supabase.table("courses").select("*").eq("id", course_id).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        print(f"Error retrieving course {course_id}: {str(e)}")
        return None


def get_all_courses():
    """
    Retrieve all courses from the database.
    
    Returns:
        A list of all courses
    """
    try:
        response = supabase.table("courses").select("*").order("course_name").execute()
        return response.data if response.data else []
    except Exception as e:
        print(f"Error retrieving courses: {str(e)}")
        return []


def update_course(course_id, title=None, description=None, capacity=None):
    """
    Update a course's information.
    
    Args:
        course_id: The ID of the course to update
        title: New title (optional)
        description: New description (optional)
        capacity: New capacity (optional)
    
    Returns:
        The updated course record or None if error
    """
    try:
        # Build update payload with only provided fields
        update_data = {}
        if title is not None:
            update_data["course_name"] = title
        if description is not None:
            update_data["description"] = description
        if capacity is not None:
            update_data["capacity"] = capacity
        
        if not update_data:
            return None
            
        response = (
            supabase.table("courses")
            .update(update_data)
            .eq("id", course_id)
            .execute()
        )
        
        return response.data[0] if response.data else None
    except Exception as e:
        print(f"Error updating course {course_id}: {str(e)}")
        return None