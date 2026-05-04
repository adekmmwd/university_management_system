from datetime import datetime, timezone

from core.database import supabase


def _parse_event_date(value):
    if not value:
        return None

    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                return None

    return value


def get_upcoming_events():
    try:
        # Use date-only string for comparison since event_date may store dates
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        response = (
            supabase.table("events")
            .select("*")
            .gte("event_date", today)
            .order("event_date", ascending=True)
            .execute()
        )
        rows = response.data or []
    except Exception as e:
        print(f"Error fetching events: {e}")
        rows = []

    events = []
    for row in rows:
        try:
            event_date = _parse_event_date(row.get("event_date"))
            formatted_date = event_date.strftime("%b %d, %Y") if event_date else "TBA"
            events.append(
                {
                    "title": row.get("title", "Untitled"),
                    "description": (row.get("description") or "").strip(),
                    "event_date": event_date,
                    "formatted_date": formatted_date,
                    "type": (row.get("type") or "Event").title(),
                }
            )
        except Exception as e:
            print(f"Error processing event row: {e}")
            continue

    return events
