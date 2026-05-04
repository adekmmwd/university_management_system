-- Add status field to courses table for deactivation/deletion management
-- Status: Active | Inactive

ALTER TABLE public.courses
ADD COLUMN IF NOT EXISTS status VARCHAR DEFAULT 'Active' CHECK (status IN ('Active', 'Inactive'));

-- Add indexes for filtering by status
CREATE INDEX IF NOT EXISTS idx_courses_status ON public.courses(status);

-- Create function to check if a course has enrolled students
CREATE OR REPLACE FUNCTION public.course_has_enrolled_students(p_course_id uuid)
RETURNS BOOLEAN
LANGUAGE sql
STABLE
AS $$
    SELECT EXISTS (
        SELECT 1 FROM public.enrollments
        WHERE course_id = p_course_id
    );
$$;

-- Add RLS policy for coordinators to update course status
-- This is in addition to any existing policies
DROP POLICY IF EXISTS courses_update_coordinator ON public.courses;

CREATE POLICY courses_update_coordinator
ON public.courses
FOR UPDATE
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

-- Add RLS policy for coordinators to delete courses
DROP POLICY IF EXISTS courses_delete_coordinator ON public.courses;

CREATE POLICY courses_delete_coordinator
ON public.courses
FOR DELETE
TO authenticated
USING (
    lower(
        coalesce(
            auth.jwt() -> 'app_metadata' ->> 'role',
            auth.jwt() -> 'user_metadata' ->> 'role',
            ''
        )
    ) = 'course coordinator'
);
