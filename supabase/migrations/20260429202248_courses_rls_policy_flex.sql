-- Relax role string matching for the courses insert policy.
-- Accepts both 'course coordinator' and 'course_coordinator'.

DROP POLICY IF EXISTS courses_insert_course_coordinator ON public.courses;

CREATE POLICY courses_insert_course_coordinator
ON public.courses
FOR INSERT
TO authenticated
WITH CHECK (
	lower(
		coalesce(
			auth.jwt() -> 'app_metadata' ->> 'role',
			auth.jwt() -> 'user_metadata' ->> 'role',
			''
		)
	) IN ('course coordinator', 'course_coordinator')
);
