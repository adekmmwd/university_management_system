-- Create announcements table for university-wide staff posting

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE public.announcements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    is_pinned BOOLEAN NOT NULL DEFAULT TRUE,
    created_by UUID REFERENCES public.staff(uuid) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_announcements_is_pinned_created_at
ON public.announcements(is_pinned, created_at DESC);
