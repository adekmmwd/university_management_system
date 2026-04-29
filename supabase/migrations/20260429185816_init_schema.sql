-- University Management System
-- Initial schema migration

-- Users Table (Auth)
CREATE TABLE public.users (
	id SERIAL PRIMARY KEY,
	username TEXT UNIQUE NOT NULL,
	password_hash TEXT NOT NULL,
	role TEXT NOT NULL DEFAULT 'student',
	full_name TEXT
);

-- Students Table (UMS-9)
CREATE TABLE public.students (
	id SERIAL PRIMARY KEY,
	user_id INTEGER REFERENCES public.users(id) ON DELETE CASCADE,
	student_id TEXT UNIQUE NOT NULL,
	name TEXT NOT NULL,
	email TEXT NOT NULL,
	department TEXT,
	year TEXT
);

-- Staff Table (UMS-11)
CREATE TABLE public.staff (
	id SERIAL PRIMARY KEY,
	user_id INTEGER REFERENCES public.users(id) ON DELETE CASCADE,
	staff_id TEXT UNIQUE NOT NULL,
	name TEXT NOT NULL,
	role_type TEXT NOT NULL DEFAULT 'professor',
	email TEXT,
	department TEXT,
	office_hours TEXT
);

-- Courses Table (UMS-Staff Courses Feature)
CREATE TABLE public.courses (
	id SERIAL PRIMARY KEY,
	course_code TEXT UNIQUE NOT NULL,
	course_name TEXT NOT NULL,
	department TEXT,
	credit_hours INTEGER,
	semester TEXT,
	description TEXT,
	created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Staff Courses Mapping Table (Many-to-Many)
CREATE TABLE public.staff_courses (
	id SERIAL PRIMARY KEY,
	staff_id INTEGER REFERENCES public.staff(id) ON DELETE CASCADE,
	course_id INTEGER REFERENCES public.courses(id) ON DELETE CASCADE,
	role TEXT NOT NULL DEFAULT 'Professor',
	academic_year TEXT,
	created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
	UNIQUE(staff_id, course_id)
);

-- Indexes for performance optimization
CREATE INDEX IF NOT EXISTS idx_students_student_id ON public.students(student_id);
CREATE INDEX IF NOT EXISTS idx_students_name ON public.students(name);
CREATE INDEX IF NOT EXISTS idx_students_department ON public.students(department);
CREATE INDEX IF NOT EXISTS idx_students_year ON public.students(year);

-- Indexes for courses and staff_courses
CREATE INDEX IF NOT EXISTS idx_courses_course_code ON public.courses(course_code);
CREATE INDEX IF NOT EXISTS idx_courses_department ON public.courses(department);
CREATE INDEX IF NOT EXISTS idx_staff_courses_staff_id ON public.staff_courses(staff_id);
CREATE INDEX IF NOT EXISTS idx_staff_courses_course_id ON public.staff_courses(course_id);
CREATE INDEX IF NOT EXISTS idx_staff_courses_role ON public.staff_courses(role);
