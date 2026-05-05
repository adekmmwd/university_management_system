-- Facilities: Bookings schema and conflict protection.

CREATE TABLE IF NOT EXISTS public.bookings (
    id serial PRIMARY KEY,
    room_id uuid NOT NULL REFERENCES public.rooms(id) ON DELETE CASCADE,
    staff_id integer NOT NULL REFERENCES public.staff(id) ON DELETE CASCADE,
    title varchar NOT NULL,
    date date NOT NULL,
    start_time time NOT NULL,
    end_time time NOT NULL,
    created_at timestamp with time zone NOT NULL DEFAULT now(),
    updated_at timestamp with time zone NOT NULL DEFAULT now(),
    CONSTRAINT bookings_time_order CHECK (end_time > start_time)
);

CREATE INDEX IF NOT EXISTS idx_bookings_room_date ON public.bookings (room_id, date);
CREATE INDEX IF NOT EXISTS idx_bookings_staff_id ON public.bookings (staff_id);
CREATE INDEX IF NOT EXISTS idx_bookings_date ON public.bookings (date);

ALTER TABLE public.bookings ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS bookings_select_authenticated ON public.bookings;
DROP POLICY IF EXISTS bookings_insert_authenticated ON public.bookings;

CREATE POLICY bookings_select_authenticated
ON public.bookings
FOR SELECT
TO authenticated
USING (true);

CREATE POLICY bookings_insert_authenticated
ON public.bookings
FOR INSERT
TO authenticated
WITH CHECK (
    EXISTS (
        SELECT 1
        FROM public.staff s
        WHERE s.id = public.bookings.staff_id
    )
);
