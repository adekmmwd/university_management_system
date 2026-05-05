-- Facilities: Rooms management schema + policies.
-- Adds table constraints for data integrity and admin-only inserts via RLS.

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS public.rooms (
    id uuid PRIMARY KEY DEFAULT extensions.uuid_generate_v4(),
    room_number varchar NOT NULL,
    building_name varchar NOT NULL,
    floor integer NOT NULL,
    capacity integer NOT NULL,
    room_type varchar NOT NULL,
    status varchar NOT NULL DEFAULT 'Available',
    created_at timestamp with time zone NOT NULL DEFAULT now(),
    updated_at timestamp with time zone NOT NULL DEFAULT now(),
    CONSTRAINT rooms_capacity_positive CHECK (capacity > 0),
    CONSTRAINT rooms_floor_range CHECK (floor BETWEEN -2 AND 20),
    CONSTRAINT rooms_room_type_check CHECK (room_type IN ('Lecture Hall', 'Lab', 'Office', 'Meeting Room')),
    CONSTRAINT rooms_status_check CHECK (status IN ('Available', 'Maintenance', 'Occupied'))
);

ALTER TABLE public.rooms
    ADD COLUMN IF NOT EXISTS room_number varchar,
    ADD COLUMN IF NOT EXISTS building_name varchar,
    ADD COLUMN IF NOT EXISTS floor integer,
    ADD COLUMN IF NOT EXISTS capacity integer,
    ADD COLUMN IF NOT EXISTS room_type varchar,
    ADD COLUMN IF NOT EXISTS status varchar DEFAULT 'Available',
    ADD COLUMN IF NOT EXISTS created_at timestamp with time zone DEFAULT now(),
    ADD COLUMN IF NOT EXISTS updated_at timestamp with time zone DEFAULT now();

UPDATE public.rooms SET status = 'Available' WHERE status IS NULL;

ALTER TABLE public.rooms
    ALTER COLUMN room_number SET NOT NULL,
    ALTER COLUMN building_name SET NOT NULL,
    ALTER COLUMN floor SET NOT NULL,
    ALTER COLUMN capacity SET NOT NULL,
    ALTER COLUMN room_type SET NOT NULL,
    ALTER COLUMN status SET NOT NULL,
    ALTER COLUMN status SET DEFAULT 'Available';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'rooms_capacity_positive'
          AND conrelid = 'public.rooms'::regclass
    ) THEN
        ALTER TABLE public.rooms
            ADD CONSTRAINT rooms_capacity_positive CHECK (capacity > 0);
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'rooms_floor_range'
          AND conrelid = 'public.rooms'::regclass
    ) THEN
        ALTER TABLE public.rooms
            ADD CONSTRAINT rooms_floor_range CHECK (floor BETWEEN -2 AND 20);
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'rooms_room_type_check'
          AND conrelid = 'public.rooms'::regclass
    ) THEN
        ALTER TABLE public.rooms
            ADD CONSTRAINT rooms_room_type_check CHECK (room_type IN ('Lecture Hall', 'Lab', 'Office', 'Meeting Room'));
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'rooms_status_check'
          AND conrelid = 'public.rooms'::regclass
    ) THEN
        ALTER TABLE public.rooms
            ADD CONSTRAINT rooms_status_check CHECK (status IN ('Available', 'Maintenance', 'Occupied'));
    END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS rooms_room_number_building_name_key
    ON public.rooms (room_number, building_name);

CREATE INDEX IF NOT EXISTS idx_rooms_building_name ON public.rooms (building_name);
CREATE INDEX IF NOT EXISTS idx_rooms_status ON public.rooms (status);

ALTER TABLE public.rooms ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS rooms_select_authenticated ON public.rooms;
DROP POLICY IF EXISTS rooms_insert_admin ON public.rooms;

CREATE POLICY rooms_select_authenticated
ON public.rooms
FOR SELECT
TO authenticated
USING (true);

CREATE POLICY rooms_insert_admin
ON public.rooms
FOR INSERT
TO authenticated
WITH CHECK (
    lower(
        coalesce(
            auth.jwt() -> 'app_metadata' ->> 'role',
            auth.jwt() -> 'user_metadata' ->> 'role',
            ''
        )
    ) = 'admin'
);
