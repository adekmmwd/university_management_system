-- Course Coordinator: Course Catalog (CREATE-only)
-- Creates a UUID-based course catalog table and locks INSERT behind RLS.

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- The existing schema created a legacy `public.courses` and `public.staff_courses`.
-- For this story, we rebuild them to match the required catalog schema.

DROP TABLE IF EXISTS public.staff_courses;
DROP TABLE IF EXISTS public.courses;

-- Add a stable UUID identifier to staff records so course creation can reference
-- a UUID creator without changing the existing int primary key.
ALTER TABLE public.staff
ADD COLUMN IF NOT EXISTS uuid uuid;

UPDATE public.staff
SET uuid = uuid_generate_v4()
WHERE uuid IS NULL;

ALTER TABLE public.staff
ALTER COLUMN uuid SET NOT NULL;

ALTER TABLE public.staff
ALTER COLUMN uuid SET DEFAULT uuid_generate_v4();

CREATE UNIQUE INDEX IF NOT EXISTS staff_uuid_unique_idx ON public.staff(uuid);

-- Course Catalog
CREATE TABLE public.courses (
	id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
	course_code varchar NOT NULL UNIQUE,
	title varchar NOT NULL,
	description text,
	course_type varchar NOT NULL,
	capacity integer NOT NULL DEFAULT 50,
	department varchar NOT NULL,
	created_by uuid NOT NULL,
	created_at timestamp with time zone NOT NULL DEFAULT now(),
	CONSTRAINT courses_course_type_check CHECK (course_type IN ('Core', 'Elective')),
	CONSTRAINT courses_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.staff(uuid)
);

-- Recreate staff course assignments to reference the UUID course IDs.
CREATE TABLE public.staff_courses (
	id SERIAL PRIMARY KEY,
	staff_id INTEGER REFERENCES public.staff(id) ON DELETE CASCADE,
	course_id uuid REFERENCES public.courses(id) ON DELETE CASCADE,
	role TEXT NOT NULL DEFAULT 'Professor',
	academic_year TEXT,
	created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
	UNIQUE(staff_id, course_id)
);

-- RLS
ALTER TABLE public.courses ENABLE ROW LEVEL SECURITY;

-- Insert Policy: Only authenticated users with a Course Coordinator claim.
-- Note: This policy is evaluated when using Supabase Auth / JWTs.
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
	) = 'course coordinator'
);
