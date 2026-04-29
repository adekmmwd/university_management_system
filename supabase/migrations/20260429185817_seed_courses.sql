-- University Management System
-- Seed data migration (safe inserts only)

-- ============================================================
-- SAMPLE DATA FOR TESTING (Staff Courses Feature)
-- ============================================================

-- NOTE:
-- The `public.courses` table is now a coordinator-managed catalog with required
-- fields like `course_type` and `created_by`. We intentionally do not seed it here.

-- NOTE:
-- The original standalone SQL file included sample inserts into public.staff_courses.
-- Those inserts require matching rows in public.staff (and public.users) to exist,
-- otherwise the migration will fail due to foreign key constraints.
