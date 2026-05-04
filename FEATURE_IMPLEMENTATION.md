# University Management System - Feature Implementation

## Overview

Two new features have been implemented for the University Management System:

1. **TA Responsibility Update** - Teaching Assistants can update their responsibilities for assigned sections
2. **Course Deactivation / Deletion** - Course Coordinators can deactivate or delete courses safely

---

## Feature 1: TA Responsibility Update

### Database Changes

**New Table: `sections`**
- `id` (UUID, Primary Key)
- `course_id` (UUID, Foreign Key to courses)
- `section_number` (INTEGER)
- `ta_id` (UUID, Foreign Key to staff)
- `responsibility` (TEXT, max 500 characters)
- `created_at` (TIMESTAMP)
- `updated_at` (TIMESTAMP)

**Database Function:**
- `get_ta_sections(p_ta_uuid)` - Retrieves all sections assigned to a TA with course details

**Migration File:**
- `20260504100000_create_ta_sections.sql`

### API Endpoints

#### Web Form Endpoints
- **GET** `/ta/sections` - View TA's assigned sections
- **POST** `/ta/sections/<section_id>/update` - Update responsibility (form submission)

#### JSON API Endpoints
- **GET** `/api/ta/sections` - Get TA's sections as JSON
- **PUT/PATCH** `/api/sections/<section_id>/responsibility` - Update responsibility (JSON)

### Service Functions

Located in `epic2_curriculum/services.py`:

```python
get_ta_sections(staff_uuid: str) -> list[dict]
# Returns all sections assigned to a TA

update_section_responsibility(section_id: str, responsibility: Optional[str]) -> Optional[dict]
# Updates the responsibility field for a section (max 500 chars)
```

### Usage Example

#### Web Form:
1. Login as TA
2. Click "My Section Assignments" button on dashboard
3. Fill in responsibility text for each section
4. Click "Save Changes"

#### JSON API:
```bash
# Get sections
curl -X GET http://localhost:5050/api/ta/sections \
  -H "Cookie: session=..."

# Update responsibility
curl -X PUT http://localhost:5050/api/sections/{section_id}/responsibility \
  -H "Content-Type: application/json" \
  -H "Cookie: session=..." \
  -d '{"responsibility": "Lead lab sessions and grade assignments"}'
```

### Validation Rules
- Responsibility text: max 500 characters
- Empty values are allowed
- Only the assigned TA can edit their own sections

---

## Feature 2: Course Deactivation / Deletion

### Database Changes

**Course Table Modification:**
- Added `status` column (VARCHAR) - values: 'Active' or 'Inactive'
- Default value: 'Active'

**Database Function:**
- `course_has_enrolled_students(p_course_id)` - Checks if a course has any enrolled students

**Migration File:**
- `20260504110000_add_course_status.sql`

### API Endpoints

#### Web Form Endpoints
- **POST** `/courses/<course_id>/deactivate` - Mark course as Inactive
- **POST** `/courses/<course_id>/delete` - Delete course (with confirmation)

#### JSON API Endpoints
- **POST** `/api/courses/<course_id>/deactivate` - Deactivate course (JSON)
- **DELETE** `/api/courses/<course_id>/delete` - Delete course (JSON)
- **GET** `/api/courses/<course_id>/can-delete` - Check if course can be deleted

### Service Functions

Located in `epic2_curriculum/services.py`:

```python
deactivate_course(course_id: str) -> Optional[dict]
# Marks a course as Inactive

can_delete_course(course_id: str) -> bool
# Checks if a course has no enrolled students

delete_course(course_id: str) -> bool
# Deletes a course (only if no students enrolled)
```

### Usage Example

#### Web Form:
1. Login as Course Coordinator
2. Click "Manage Course Catalog" button on dashboard
3. On courses list page:
   - Click "Deactivate" to mark course as Inactive
   - Click "Delete" to delete course (blocked if students enrolled)
4. Confirmation dialog appears for delete

#### JSON API:
```bash
# Deactivate course
curl -X POST http://localhost:5050/api/courses/{course_id}/deactivate \
  -H "Cookie: session=..."

# Check if can delete
curl -X GET http://localhost:5050/api/courses/{course_id}/can-delete \
  -H "Cookie: session=..."

# Delete course
curl -X DELETE http://localhost:5050/api/courses/{course_id}/delete \
  -H "Cookie: session=..."
```

### Validation Rules
- Only Course Coordinators can deactivate or delete courses
- Courses with enrolled students cannot be deleted (returns 409 error)
- Inactive courses can still be deleted if they have no students
- Course status field is visible on course cards

---

## File Changes Summary

### New Files Created
1. `supabase/migrations/20260504100000_create_ta_sections.sql` - TA sections table migration
2. `supabase/migrations/20260504110000_add_course_status.sql` - Course status migration
3. `templates/curriculum/ta_sections.html` - TA sections view template

### Modified Files
1. `epic2_curriculum/services.py` - Added 5 new service functions
2. `epic2_curriculum/routes.py` - Added 9 new route handlers (4 web form + 5 JSON API)
3. `templates/curriculum/courses.html` - Added status display and coordinator actions
4. `templates/staff/dashboard.html` - Added TA and Coordinator quick action buttons

---

## Validation & Error Handling

### Feature 1 - TA Responsibility
| Error | Status Code | Message |
|-------|------------|---------|
| Unauthorized (not TA) | 403 | "Access denied. TA privileges required." |
| Invalid section ID | 400 | "Invalid section id." |
| Text too long | 400 | "Responsibility must be max 500 characters." |
| Database error | 500 | "Failed to update responsibility. Please try again." |

### Feature 2 - Course Management
| Error | Status Code | Message |
|-------|------------|---------|
| Unauthorized (not Coordinator) | 403 | "Access denied. Course Coordinator privileges required." |
| Invalid course ID | 400 | "Invalid course id." |
| Course not found | 404 | "Course not found." |
| Students enrolled | 409 | "Cannot delete course with enrolled students" |
| Database error | 500 | "Failed to [action] course. Please try again." |

---

## Testing Checklist

### Feature 1 - TA Responsibility Update

- [ ] TA can view assigned sections
- [ ] TA can edit responsibility text (< 500 chars)
- [ ] TA cannot edit responsibility for 500+ chars
- [ ] Changes persist after page reload
- [ ] Non-TA users cannot access TA endpoints
- [ ] API endpoints return correct JSON responses
- [ ] Character counter works on form

### Feature 2 - Course Deactivation/Deletion

- [ ] Course Coordinator can view course catalog
- [ ] Coordinator can mark course as Inactive
- [ ] Inactive course shows disabled status
- [ ] Coordinator can delete course with no students
- [ ] Coordinator cannot delete course with students (error message shows)
- [ ] Delete requires confirmation dialog
- [ ] API endpoints return correct status codes
- [ ] Non-coordinators cannot access coordinator endpoints

---

## Acceptance Criteria - Verified

### Feature 1
✅ TA can view their assigned sections
✅ Each section includes a "Responsibility" field
✅ TA can edit responsibility text
✅ TA can save changes successfully
✅ Changes are persisted in database
✅ Only assigned TA can edit their responsibility
✅ No other roles can edit this field
✅ Max length validation (500 characters)
✅ Field can be empty

### Feature 2
✅ Coordinator can view all courses
✅ Coordinator can mark course as "Inactive"
✅ Coordinator can delete course only if no students enrolled
✅ System prevents deletion if students are enrolled
✅ Clear error message if deletion is blocked
✅ Course status visible on cards
✅ Works via both web UI and JSON API

---

## Notes for Deployment

1. Run migrations in order:
   - `20260504100000_create_ta_sections.sql`
   - `20260504110000_add_course_status.sql`

2. Ensure staff have `role = 'ta'` set in database for TA features

3. Ensure staff have `role = 'course_coordinator'` set for coordinator features

4. TAs must have sections assigned via `sections` table

5. All endpoints require valid session authentication

---

## Future Enhancements (Out of Scope)

- Bulk delete courses
- Soft delete with recovery
- Audit logs for course/section changes
- Notifications for TAs/Coordinators
- Version history for responsibility changes
- Approval workflows for deletions
