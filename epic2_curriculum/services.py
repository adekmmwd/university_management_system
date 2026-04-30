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
