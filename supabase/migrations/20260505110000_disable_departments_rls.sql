-- Disable RLS for departments table since the python backend uses custom Flask sessions
-- and enforces role checks (like @admin_required) at the application level.
-- If the app is using the anon key, RLS blocks inserts.

ALTER TABLE public.departments DISABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS departments_admin_all ON public.departments;
DROP POLICY IF EXISTS departments_view_all ON public.departments;
