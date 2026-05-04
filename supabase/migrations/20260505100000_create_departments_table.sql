-- Create departments table
CREATE TABLE IF NOT EXISTS public.departments (
    id SERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    code TEXT UNIQUE,
    head TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now())
);

-- Enable RLS
ALTER TABLE public.departments ENABLE ROW LEVEL SECURITY;

-- Admins can do anything
CREATE POLICY departments_admin_all
ON public.departments
FOR ALL
TO authenticated
USING (
    lower(
        coalesce(
            auth.jwt() -> 'app_metadata' ->> 'role',
            auth.jwt() -> 'user_metadata' ->> 'role',
            ''
        )
    ) = 'admin'
)
WITH CHECK (
    lower(
        coalesce(
            auth.jwt() -> 'app_metadata' ->> 'role',
            auth.jwt() -> 'user_metadata' ->> 'role',
            ''
        )
    ) = 'admin'
);

-- Anyone authenticated can view departments
CREATE POLICY departments_view_all
ON public.departments
FOR SELECT
TO authenticated
USING (true);