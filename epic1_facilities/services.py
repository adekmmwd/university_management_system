from __future__ import annotations

from typing import Any

from core.database import supabase

ROOM_TYPE_OPTIONS = ("Lecture Hall", "Lab", "Office", "Meeting Room")
ROOM_STATUS_OPTIONS = ("Available", "Maintenance", "Occupied")

# Fallback values so the building dropdown is still usable before rooms exist.
DEFAULT_BUILDINGS = (
    "Main Building",
    "Engineering Building A",
    "Engineering Building B",
    "Labs Complex",
)


def get_rooms() -> list[dict[str, Any]]:
    response = (
        supabase.table("rooms")
        .select("id, room_number, building_name, floor, capacity, room_type, status")
        .order("building_name")
        .order("floor")
        .order("room_number")
        .execute()
    )
    return response.data or []


def get_building_options() -> list[str]:
    options: list[str] = []

    rooms_response = (
        supabase.table("rooms")
        .select("building_name")
        .order("building_name")
        .execute()
    )
    for row in rooms_response.data or []:
        name = (row.get("building_name") or "").strip()
        if name and name not in options:
            options.append(name)

    for name in DEFAULT_BUILDINGS:
        if name not in options:
            options.append(name)

    return options


def room_exists(room_number: str, building_name: str) -> bool:
    response = (
        supabase.table("rooms")
        .select("id")
        .eq("room_number", room_number)
        .eq("building_name", building_name)
        .limit(1)
        .execute()
    )
    return bool(response.data)


def get_room_by_id(room_id: str) -> dict[str, Any] | None:
    response = (
        supabase.table("rooms")
        .select("id, room_number, building_name, floor, capacity, room_type, status")
        .eq("id", room_id)
        .limit(1)
        .execute()
    )
    return response.data[0] if getattr(response, "data", None) else None


def insert_room(room_data: dict[str, Any]) -> dict[str, Any] | None:
    response = supabase.table("rooms").insert(room_data).execute()
    return response.data[0] if getattr(response, "data", None) else None


def _parse_time(value: str):
    from datetime import datetime, time as dtime

    if isinstance(value, dtime):
        return value
    if isinstance(value, str):
        for fmt in ("%H:%M", "%H:%M:%S"):
            try:
                return datetime.strptime(value, fmt).time()
            except ValueError:
                continue
    raise ValueError("Invalid time format")


def _normalize_booking(booking: dict[str, Any]) -> dict[str, Any]:
    room = booking.get("rooms") or {}
    staff = booking.get("staff") or {}
    return {
        "id": booking.get("id"),
        "room_id": booking.get("room_id"),
        "staff_id": booking.get("staff_id"),
        "title": booking.get("title"),
        "date": booking.get("date"),
        "start_time": booking.get("start_time"),
        "end_time": booking.get("end_time"),
        "created_at": booking.get("created_at"),
        "updated_at": booking.get("updated_at"),
        "room_number": room.get("room_number"),
        "building_name": room.get("building_name"),
        "staff_name": staff.get("name"),
        "staff_code": staff.get("staff_id"),
    }


def get_all_bookings() -> list[dict[str, Any]]:
    response = (
        supabase.table("bookings")
        .select(
            "id, room_id, staff_id, title, date, start_time, end_time, created_at, updated_at, rooms(room_number, building_name), staff(name, staff_id)"
        )
        .order("date", ascending=False)
        .order("start_time", ascending=True)
        .execute()
    )
    return [_normalize_booking(row) for row in (response.data or [])]


def get_bookings_for_staff(staff_id: int) -> list[dict[str, Any]]:
    response = (
        supabase.table("bookings")
        .select(
            "id, room_id, staff_id, title, date, start_time, end_time, created_at, updated_at, rooms(room_number, building_name), staff(name, staff_id)"
        )
        .eq("staff_id", staff_id)
        .order("date", ascending=False)
        .order("start_time", ascending=True)
        .execute()
    )
    return [_normalize_booking(row) for row in (response.data or [])]


def get_booking_by_id(booking_id: int) -> dict[str, Any] | None:
    response = (
        supabase.table("bookings")
        .select(
            "id, room_id, staff_id, title, date, start_time, end_time, created_at, updated_at, rooms(room_number, building_name), staff(name, staff_id)"
        )
        .eq("id", booking_id)
        .limit(1)
        .execute()
    )
    row = response.data[0] if getattr(response, "data", None) else None
    return _normalize_booking(row) if row else None


def booking_conflicts(room_id: str, date: str, start_time: str, end_time: str, exclude_booking_id: int | None = None) -> bool:
    try:
        start = _parse_time(start_time)
        end = _parse_time(end_time)
    except ValueError:
        return True

    response = (
        supabase.table("bookings")
        .select("id, start_time, end_time")
        .eq("room_id", room_id)
        .eq("date", date)
        .execute()
    )

    for row in (response.data or []):
        if exclude_booking_id is not None and row.get("id") == exclude_booking_id:
            continue
        try:
            existing_start = _parse_time(row.get("start_time"))
            existing_end = _parse_time(row.get("end_time"))
        except ValueError:
            continue
        if not (existing_end <= start or existing_start >= end):
            return True
    return False


def create_booking(booking_data: dict[str, Any]) -> dict[str, Any] | None:
    response = supabase.table("bookings").insert(booking_data).execute()
    return response.data[0] if getattr(response, "data", None) else None


def delete_booking(booking_id: int) -> None:
    supabase.table("bookings").delete().eq("id", booking_id).execute()

