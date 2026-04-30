-- Add capacity column to courses table for Epic 2: Update Course Information
ALTER TABLE public.courses ADD COLUMN IF NOT EXISTS capacity INTEGER DEFAULT 30;