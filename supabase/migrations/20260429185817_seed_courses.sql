-- University Management System
-- Seed data migration (safe inserts only)

-- ============================================================
-- SAMPLE DATA FOR TESTING (Staff Courses Feature)
-- ============================================================

-- Sample Courses
INSERT INTO public.courses (course_code, course_name, department, credit_hours, semester, description)
VALUES
	('CSE354', 'Distributed Systems', 'Computer Science', 3, 'Spring 2026', 'Advanced topics in distributed computing and systems design'),
	('CSE301', 'Database Management', 'Computer Science', 3, 'Spring 2026', 'Relational databases and SQL optimization'),
	('CSE251', 'Web Development', 'Computer Science', 3, 'Spring 2026', 'Modern web development with frameworks and tools'),
	('CSE401', 'Machine Learning', 'Computer Science', 3, 'Spring 2026', 'Introduction to ML algorithms and neural networks'),
	('ENG201', 'Technical Writing', 'Engineering', 2, 'Spring 2026', 'Professional technical communication'),
	('ENG302', 'Software Engineering', 'Engineering', 3, 'Spring 2026', 'Software design patterns and development methodologies')
ON CONFLICT (course_code) DO NOTHING;

-- NOTE:
-- The original standalone SQL file included sample inserts into public.staff_courses.
-- Those inserts require matching rows in public.staff (and public.users) to exist,
-- otherwise the migration will fail due to foreign key constraints.
