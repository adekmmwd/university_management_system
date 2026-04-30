-- Invitations Table (Admin onboarding)
-- Tracks one-time, expiring invitation tokens for staff/students.

CREATE TABLE IF NOT EXISTS public.invitations (
	email VARCHAR NOT NULL,
	token UUID PRIMARY KEY,
	expires_at TIMESTAMPTZ NOT NULL,
	status VARCHAR NOT NULL DEFAULT 'Pending',
	created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_invitations_email ON public.invitations(email);
CREATE INDEX IF NOT EXISTS idx_invitations_status ON public.invitations(status);
CREATE INDEX IF NOT EXISTS idx_invitations_expires_at ON public.invitations(expires_at);
