from __future__ import annotations

import re
from typing import Any

from flask import Blueprint, jsonify, render_template, request, session

from core.auth import login_required
from epic1_facilities.services import (
    ROOM_STATUS_OPTIONS,
    ROOM_TYPE_OPTIONS,
    get_building_options,
    get_rooms,
    insert_room,
    room_exists,
)

try:
    from postgrest.exceptions import APIError as PostgrestAPIError
except Exception:  # pragma: no cover - fallback for older postgrest package layouts.
    try:
        from postgrest import APIError as PostgrestAPIError  # type: ignore
    except Exception:  # pragma: no cover
        PostgrestAPIError = None


facilities_bp = Blueprint("facilities", __name__)

ALLOWED_ROOM_TYPES = set(ROOM_TYPE_OPTIONS)
ALLOWED_ROOM_STATUS = set(ROOM_STATUS_OPTIONS)
FLOOR_MIN = -2
FLOOR_MAX = 20


def _require_admin_api():
    if "user_id" not in session:
        return jsonify({"error": "Authentication required.", "code": "UNAUTHORIZED"}), 401
    if session.get("role") != "admin":
        return jsonify({"error": "Admin privileges required.", "code": "FORBIDDEN"}), 403
    return None


def _parse_integer(value: Any, field_name: str) -> int:
    if isinstance(value, bool):
        raise TypeError(f"{field_name} must be an integer.")
    if isinstance(value, int):
        return value
    if isinstance(value, str) and re.fullmatch(r"-?\d+", value.strip()):
        return int(value.strip())
    raise TypeError(f"{field_name} must be an integer.")


def _is_duplicate_room_error(exc: Exception) -> bool:
    code = str(getattr(exc, "code", "") or "")
    message = str(getattr(exc, "message", "") or "")
    details = str(getattr(exc, "details", "") or "")
    raw = f"{exc} {message} {details}".lower()

    if code == "23505":
        return True

    return (
        "rooms_room_number_building_name_key" in raw
        or ("unique" in raw and "room_number" in raw and "building_name" in raw)
    )


@facilities_bp.route("/rooms", methods=["GET"])
@login_required
def rooms_list():
    role = session.get("role")
    rooms = get_rooms()
    building_options = get_building_options()
    return render_template(
        "facilities/rooms.html",
        role=role,
        can_add_room=role == "admin",
        rooms=rooms,
        building_options=building_options,
        room_type_options=ROOM_TYPE_OPTIONS,
    )


@facilities_bp.route("/api/admin/rooms/add", methods=["POST"])
def api_add_room():
    guard = _require_admin_api()
    if guard:
        return guard

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return (
            jsonify(
                {
                    "error": "Request body must be valid JSON.",
                    "code": "INVALID_DATA_TYPES",
                }
            ),
            400,
        )

    room_number_raw = payload.get("room_number")
    building_name_raw = payload.get("building_name")
    room_type_raw = payload.get("room_type")
    status_raw = payload.get("status", "Available")

    errors: dict[str, str] = {}

    if room_number_raw is None or (isinstance(room_number_raw, str) and not room_number_raw.strip()):
        errors["room_number"] = "Room number is required."
    elif not isinstance(room_number_raw, str):
        return jsonify({"error": "room_number must be a string.", "code": "INVALID_DATA_TYPES"}), 400

    if building_name_raw is None or (isinstance(building_name_raw, str) and not building_name_raw.strip()):
        errors["building_name"] = "Building name is required."
    elif not isinstance(building_name_raw, str):
        return jsonify({"error": "building_name must be a string.", "code": "INVALID_DATA_TYPES"}), 400

    if room_type_raw is None or (isinstance(room_type_raw, str) and not room_type_raw.strip()):
        errors["room_type"] = "Room type is required."
    elif not isinstance(room_type_raw, str):
        return jsonify({"error": "room_type must be a string.", "code": "INVALID_DATA_TYPES"}), 400

    if status_raw is not None and not isinstance(status_raw, str):
        return jsonify({"error": "status must be a string.", "code": "INVALID_DATA_TYPES"}), 400
    if errors:
        return (
            jsonify(
                {
                    "error": "Validation failed.",
                    "code": "VALIDATION_ERROR",
                    "errors": errors,
                }
            ),
            400,
        )

    try:
        floor = _parse_integer(payload.get("floor"), "floor")
        capacity = _parse_integer(payload.get("capacity"), "capacity")
    except TypeError as exc:
        return jsonify({"error": str(exc), "code": "INVALID_DATA_TYPES"}), 400

    room_number = room_number_raw.strip()
    building_name = building_name_raw.strip()
    room_type = room_type_raw.strip()
    status = status_raw.strip() if isinstance(status_raw, str) and status_raw.strip() else "Available"

    if not (FLOOR_MIN <= floor <= FLOOR_MAX):
        errors["floor"] = f"Floor must be between {FLOOR_MIN} and {FLOOR_MAX}."
    if capacity <= 0:
        errors["capacity"] = "Capacity must be a positive integer."
    if room_type not in ALLOWED_ROOM_TYPES:
        errors["room_type"] = "Invalid room type."
    if status not in ALLOWED_ROOM_STATUS:
        errors["status"] = "Invalid room status."

    if errors:
        return (
            jsonify(
                {
                    "error": "Validation failed.",
                    "code": "VALIDATION_ERROR",
                    "errors": errors,
                }
            ),
            400,
        )

    if room_exists(room_number, building_name):
        return jsonify({"error": "Room already exists in this building.", "code": "DUPLICATE_ROOM"}), 409

    insert_payload = {
        "room_number": room_number,
        "building_name": building_name,
        "floor": floor,
        "capacity": capacity,
        "room_type": room_type,
        "status": status,
    }

    try:
        room = insert_room(insert_payload)
    except Exception as exc:
        if _is_duplicate_room_error(exc):
            return jsonify({"error": "Room already exists in this building.", "code": "DUPLICATE_ROOM"}), 409

        if PostgrestAPIError is not None and isinstance(exc, PostgrestAPIError):
            return jsonify({"error": "Failed to insert room.", "code": "DATABASE_ERROR"}), 500

        return jsonify({"error": "Failed to insert room.", "code": "DATABASE_ERROR"}), 500

    if not room:
        return jsonify({"error": "Failed to insert room.", "code": "DATABASE_ERROR"}), 500

    return (
        jsonify(
            {
                "success": True,
                "message": "Room added successfully.",
                "room": room,
            }
        ),
        201,
    )
