-- Add archive, expiry, and soft-delete fields to announcements
ALTER TABLE public.announcements
ADD COLUMN IF NOT EXISTS is_archived BOOLEAN NOT NULL DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP,
ADD COLUMN IF NOT EXISTS expiry_date TIMESTAMP;

CREATE INDEX IF NOT EXISTS idx_announcements_is_archived ON public.announcements(is_archived);
CREATE INDEX IF NOT EXISTS idx_announcements_expiry_date ON public.announcements(expiry_date);
