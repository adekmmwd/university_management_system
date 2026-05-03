-- Add updated_at column to announcements
ALTER TABLE public.announcements
ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
