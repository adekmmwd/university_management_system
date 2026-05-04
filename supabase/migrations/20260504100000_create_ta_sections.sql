-- Create sections table for course sections with TA assignments
-- Allows TAs to update their responsibilities for assigned sections

CREATE TABLE IF NOT EXISTS public.sections (
    id uuid PRIMARY KEY DEFAULT extensions.uuid_generate_v4(),
    course_id uuid NOT NULL,
    section_number INTEGER NOT NULL,
    ta_id uuid,
    responsibility TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT sections_course_id_fkey FOREIGN KEY (course_id) REFERENCES public.courses(id) ON DELETE CASCADE,
    CONSTRAINT sections_ta_id_fkey FOREIGN KEY (ta_id) REFERENCES public.staff(uuid) ON DELETE SET NULL,
    CONSTRAINT sections_unique_course_number UNIQUE(course_id, section_number),
    CONSTRAINT sections_responsibility_length CHECK (responsibility IS NULL OR LENGTH(responsibility) <= 500)
);

-- Add indexes for performance
CREATE INDEX IF NOT EXISTS idx_sections_course_id ON public.sections(course_id);
CREATE INDEX IF NOT EXISTS idx_sections_ta_id ON public.sections(ta_id);

-- Enable RLS
ALTER TABLE public.sections ENABLE ROW LEVEL SECURITY;

-- RLS Policy: TAs can view their own sections
CREATE POLICY sections_select_ta
ON public.sections
FOR SELECT
USING (
    auth.uid()::TEXT = (SELECT uuid::TEXT FROM public.staff WHERE id = (SELECT id FROM public.staff WHERE uuid = ta_id LIMIT 1))
    OR
    (SELECT role FROM public.staff WHERE uuid = ta_id) = 'ta'
);

-- RLS Policy: TAs can update responsibility for their own sections
CREATE POLICY sections_update_ta_responsibility
ON public.sections
FOR UPDATE
WITH CHECK (
    (SELECT staff.uuid FROM public.staff WHERE staff.uuid = sections.ta_id AND staff.id = (
        SELECT staff_id FROM (
            SELECT id as staff_id FROM public.staff WHERE role = 'ta'
        ) AS ta_check
    ))::TEXT = auth.uid()::TEXT
)
USING (
    (SELECT staff.uuid FROM public.staff WHERE staff.uuid = sections.ta_id AND staff.id = (
        SELECT staff_id FROM (
            SELECT id as staff_id FROM public.staff WHERE role = 'ta'
        ) AS ta_check
    ))::TEXT = auth.uid()::TEXT
);

-- Function to get TA's assigned sections
CREATE OR REPLACE FUNCTION public.get_ta_sections(p_ta_uuid uuid)
RETURNS TABLE (
    id uuid,
    course_id uuid,
    course_code varchar,
    course_title varchar,
    section_number INTEGER,
    responsibility TEXT,
    created_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE
)
LANGUAGE sql
STABLE
AS $$
    SELECT
        s.id,
        s.course_id,
        c.course_code,
        c.title,
        s.section_number,
        s.responsibility,
        s.created_at,
        s.updated_at
    FROM public.sections s
    INNER JOIN public.courses c ON c.id = s.course_id
    WHERE s.ta_id = p_ta_uuid
    ORDER BY c.course_code, s.section_number;
$$;
