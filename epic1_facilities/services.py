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


def insert_room(room_data: dict[str, Any]) -> dict[str, Any] | None:
    response = supabase.table("rooms").insert(room_data).execute()
    return response.data[0] if getattr(response, "data", None) else None
