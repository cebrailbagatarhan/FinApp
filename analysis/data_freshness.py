"""Read-only market price recency checks for the inflation dashboard."""

from datetime import date


def get_market_data_freshness(connection, market_name=None, today=None, stale_after_days=7):
    """Return the latest recorded market price date and its age in days.

    The supplied SQLite connection is not modified or closed. Future/invalid dates
    are explicitly flagged instead of being presented as current observations.
    """
    if stale_after_days < 0:
        raise ValueError("stale_after_days must be nonnegative")
    if market_name:
        row = connection.execute(
            "SELECT MAX(date) FROM products WHERE market_name = ?", (market_name,)
        ).fetchone()
    else:
        row = connection.execute("SELECT MAX(date) FROM products").fetchone()

    latest = row[0] if row else None
    if latest is None:
        return {"status": "missing", "latest_date": None, "age_days": None}
    try:
        observed = date.fromisoformat(str(latest))
    except ValueError:
        return {"status": "invalid", "latest_date": str(latest), "age_days": None}

    age_days = ((today or date.today()) - observed).days
    if age_days < 0:
        status = "future"
    elif age_days > stale_after_days:
        status = "stale"
    else:
        status = "fresh"
    return {"status": status, "latest_date": observed.isoformat(), "age_days": age_days}
