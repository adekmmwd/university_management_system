-- Course Registration: enrollments + atomic registration helpers

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Ensure students have a stable UUID identifier (matches the UUID-based course catalog)
ALTER TABLE public.students
ADD COLUMN IF NOT EXISTS uuid uuid;

UPDATE public.students
SET uuid = extensions.uuid_generate_v4()
WHERE uuid IS NULL;

ALTER TABLE public.students
ALTER COLUMN uuid SET NOT NULL;

ALTER TABLE public.students
ALTER COLUMN uuid SET DEFAULT extensions.uuid_generate_v4();

CREATE UNIQUE INDEX IF NOT EXISTS students_uuid_unique_idx ON public.students(uuid);

-- Enrollment table (many-to-many)
CREATE TABLE IF NOT EXISTS public.enrollments (
	id uuid PRIMARY KEY DEFAULT extensions.uuid_generate_v4(),
	student_id uuid NOT NULL,
	course_id uuid NOT NULL,
	enrolled_at timestamp with time zone NOT NULL DEFAULT now(),
	CONSTRAINT enrollments_student_id_fkey FOREIGN KEY (student_id) REFERENCES public.students(uuid) ON DELETE CASCADE,
	CONSTRAINT enrollments_course_id_fkey FOREIGN KEY (course_id) REFERENCES public.courses(id) ON DELETE CASCADE,
	CONSTRAINT enrollments_unique_student_course UNIQUE(student_id, course_id)
);

CREATE INDEX IF NOT EXISTS enrollments_course_id_idx ON public.enrollments(course_id);
CREATE INDEX IF NOT EXISTS enrollments_student_id_idx ON public.enrollments(student_id);

-- Optional: enable RLS (service_role bypasses RLS; app enforcement is via the RPC below)
ALTER TABLE public.enrollments ENABLE ROW LEVEL SECURITY;

-- List courses for a student with department/capacity/enrollment status.
-- Used by the student dashboard to render disabled/enabled Register buttons.
CREATE OR REPLACE FUNCTION public.list_courses_for_student(p_student_uuid uuid)
RETURNS TABLE (
	id uuid,
	course_code varchar,
	title varchar,
	description text,
	course_type varchar,
	capacity integer,
	department varchar,
	enrolled_count bigint,
	already_enrolled boolean,
	department_match boolean,
	is_full boolean
)
LANGUAGE sql
STABLE
AS $$
	WITH student AS (
		SELECT uuid, department
		FROM public.students
		WHERE uuid = p_student_uuid
		LIMIT 1
	), counts AS (
		SELECT course_id, count(*)::bigint AS enrolled_count
		FROM public.enrollments
		GROUP BY course_id
	)
	SELECT
		c.id,
		c.course_code,
		c.title,
		c.description,
		c.course_type,
		c.capacity,
		c.department,
		COALESCE(cnt.enrolled_count, 0) AS enrolled_count,
		EXISTS (
			SELECT 1
			FROM public.enrollments e
			WHERE e.course_id = c.id
				AND e.student_id = p_student_uuid
		) AS already_enrolled,
		(lower(COALESCE(s.department, '')) = lower(COALESCE(c.department, ''))) AS department_match,
		(COALESCE(cnt.enrolled_count, 0) >= c.capacity) AS is_full
	FROM public.courses c
	CROSS JOIN student s
	LEFT JOIN counts cnt ON cnt.course_id = c.id
	ORDER BY c.department, c.course_code;
$$;

-- Atomic registration: enforces department match + capacity limit inside a single transaction.
CREATE OR REPLACE FUNCTION public.register_for_course(
	p_student_uuid uuid,
	p_course_id uuid
)
RETURNS uuid
LANGUAGE plpgsql
AS $$
DECLARE
	student_department text;
	course_department text;
	course_capacity integer;
	current_count bigint;
	new_enrollment_id uuid;
BEGIN
	SELECT s.department
	INTO student_department
	FROM public.students s
	WHERE s.uuid = p_student_uuid
	LIMIT 1;

	IF NOT FOUND THEN
		RAISE EXCEPTION 'student_not_found';
	END IF;

	-- Lock the course row so concurrent registrations for the same course serialize.
	SELECT c.department, c.capacity
	INTO course_department, course_capacity
	FROM public.courses c
	WHERE c.id = p_course_id
	FOR UPDATE;

	IF course_department IS NULL THEN
		RAISE EXCEPTION 'course_not_found';
	END IF;

	IF lower(COALESCE(student_department, '')) <> lower(COALESCE(course_department, '')) THEN
		RAISE EXCEPTION 'department_mismatch';
	END IF;

	SELECT count(*)
	INTO current_count
	FROM public.enrollments e
	WHERE e.course_id = p_course_id;

	IF current_count >= course_capacity THEN
		RAISE EXCEPTION 'course_full';
	END IF;

	BEGIN
		INSERT INTO public.enrollments (student_id, course_id)
		VALUES (p_student_uuid, p_course_id)
		RETURNING id INTO new_enrollment_id;
	EXCEPTION
		WHEN unique_violation THEN
			RAISE EXCEPTION 'already_enrolled';
	END;

	RETURN new_enrollment_id;
END;
$$;
