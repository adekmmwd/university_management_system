-- Add uuid, status and archived columns to students table
-- Ensures pgcrypto is available for gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

ALTER TABLE public.students
    ADD COLUMN IF NOT EXISTS uuid uuid DEFAULT gen_random_uuid();

-- Populate uuid for existing rows
UPDATE public.students SET uuid = gen_random_uuid() WHERE uuid IS NULL;

ALTER TABLE public.students
    ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'active';

ALTER TABLE public.students
    ADD COLUMN IF NOT EXISTS archived BOOLEAN DEFAULT FALSE;

-- Ensure indexes for performance and uniqueness
CREATE INDEX IF NOT EXISTS idx_students_student_id ON public.students(student_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_students_email_unique ON public.students (lower(email));
