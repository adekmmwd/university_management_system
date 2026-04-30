-- Add subject_type to courses for core/elective classification
ALTER TABLE public.courses
ADD COLUMN IF NOT EXISTS subject_type TEXT NOT NULL DEFAULT 'Elective';

ALTER TABLE public.courses
ADD CONSTRAINT IF NOT EXISTS courses_subject_type_check
CHECK (subject_type IN ('Core', 'Elective'));

-- Seed sample type values for existing subjects
UPDATE public.courses
SET subject_type = 'Core'
WHERE course_code IN ('CSE301', 'CSE354', 'ENG302');
