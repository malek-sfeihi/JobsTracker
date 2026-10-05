import re
from datetime import datetime, timezone
from difflib import SequenceMatcher

from app.core.config import settings
from app.db.database import get_connection
from app.filters.extract import company_key, extract_company, extract_position, same_company
from app.filters.reasons import extract_reason
from app.filters.job_filter import normalize


def _position_key(position: str) -> str:
    """"Software Engineering Intern (R0339364)" -> "software engineering intern"."""
    position = normalize(position)
    position = re.sub(r"\(.*?\)|\b(h/f|f/h|m/f|h/f/x)\b", " ", position)
    return " ".join(re.sub(r"[^a-z0-9]+", " ", position).split())


def _job_id(position: str) -> str | None:
    """Job reference number if there is one: "(id: 3074226)" or "(R0339364)"."""
    match = re.search(r"\((?:id:\s*)?r?(\d{5,})\)", position.lower())
    return match.group(1) if match else None


def _same_position(a: str, b: str) -> bool:
    id_a, id_b = _job_id(a), _job_id(b)
    if id_a and id_b:
        return id_a == id_b
    a, b = _position_key(a), _position_key(b)
    # 0.9 and not lower: "... intern - germany" vs "... intern - france" are 85% similar
    return a in b or b in a or SequenceMatcher(None, a, b).ratio() >= 0.9


def compute_status(emails: list[dict], today: datetime) -> str:
    """Status of an application from its emails (sorted oldest -> newest)."""
    last = emails[-1]
    days_since = (today - last["date"]).days

    if any(e["category"] == "offer" for e in emails):
        return "offer"
    if last["category"] == "rejection":
        return "rejected"
    # An invitation to a test/interview = your turn... unless the email says it's done
    is_done = re.search(r"completed|termine|submitted|soumis", normalize(last["subject"]))
    if last["category"] in ("interview", "assessment") and not is_done:
        return "action_needed" if days_since <= settings.ghost_days else "expired"
    # Otherwise you did your part and it's their turn
    return "in_progress" if days_since <= settings.ghost_days else "ghosted"


def build_applications() -> None:
    """Group the job emails into applications. Rebuilt from scratch every time: like the
    categories, applications are *derived* from the stored emails, so they're cheap to redo."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM emails WHERE category IS NOT NULL ORDER BY received_at"
    ).fetchall()

    emails = []
    for row in rows:
        company = extract_company(row["sender"], row["subject"]) or "unknown"
        emails.append({
            "id": row["id"],
            "kind": row["kind"],
            "category": row["category"],
            "subject": row["subject"],
            "body": row["body"],
            "company": company,
            "key": company_key(company),
            "position": extract_position(row["subject"], row["body"]),
            "date": datetime.fromisoformat(row["received_at"]),
        })

    # Each application: {"company", "key", "position", "kind", "emails": [...]}
    applications = []

    # Pass 1: emails that mention a position -> same company AND same position = same application
    for email in [e for e in emails if e["position"]]:
        match = next(
            (a for a in applications
             if same_company(a["key"], email["key"]) and _same_position(a["position"], email["position"])),
            None,
        )
        if match:
            match["emails"].append(email)
        else:
            applications.append({**email, "emails": [email]})

    # Pass 2: emails without a position ("Thank you for applying") -> attach to the application
    # of the same company that is closest in time, or start a new one
    for email in [e for e in emails if not e["position"]]:
        candidates = [a for a in applications if same_company(a["key"], email["key"])]
        if candidates:
            closest = min(
                candidates,
                key=lambda a: min(abs(e["date"] - email["date"]) for e in a["emails"]),
            )
            closest["emails"].append(email)
        else:
            applications.append({**email, "emails": [email]})

    today = datetime.now(timezone.utc)
    overrides = {row["anchor_email_id"]: row for row in conn.execute("SELECT * FROM overrides")}
    conn.execute("UPDATE emails SET application_id = NULL")
    conn.execute("DELETE FROM applications")
    for app in applications:
        app["emails"].sort(key=lambda e: e["date"])
        anchor = app["emails"][0]["id"]
        company, position = app["company"], app["position"]
        status = compute_status(app["emails"], today)
        # Your corrections win over the automatic guesses
        override = overrides.get(anchor)
        if override:
            company = override["company"] or company
            position = override["position"] or position
            status = override["status"] or status
        # Why they said no: read from the most recent rejection email
        rejections = [e for e in app["emails"] if e["category"] == "rejection"]
        reason, quote = extract_reason(rejections[-1]["body"]) if rejections else (None, None)
        cursor = conn.execute(
            """INSERT INTO applications
               (company, position, kind, status, last_activity, first_activity, anchor_email_id,
                rejection_reason, rejection_quote)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (company, position, app["kind"], status, app["emails"][-1]["date"].isoformat(),
             app["emails"][0]["date"].isoformat(), anchor, reason, quote),
        )
        conn.executemany(
            "UPDATE emails SET application_id = ? WHERE id = ?",
            [(cursor.lastrowid, e["id"]) for e in app["emails"]],
        )
    conn.commit()
    conn.close()


# Display order of the morning summary: what needs you first
STATUS_LABELS = {
    "action_needed": "🟡 ACTION NEEDED - your turn",
    "offer": "🎉 OFFERS",
    "in_progress": "🔵 IN PROGRESS - waiting for them",
    "ghosted": f"👻 GHOSTED - no news for {settings.ghost_days}+ days",
    "rejected": "❌ REJECTED",
    "expired": "⚫ EXPIRED - invitations you didn't do",
}


def print_summary() -> None:
    conn = get_connection()
    today = datetime.now(timezone.utc)
    total = conn.execute("SELECT COUNT(*) FROM applications").fetchone()[0]
    print(f"\n===== {total} applications - {today:%A %d %B %Y} =====")
    for status, label in STATUS_LABELS.items():
        apps = conn.execute(
            "SELECT * FROM applications WHERE status = ? ORDER BY last_activity DESC", (status,)
        ).fetchall()
        if not apps:
            continue
        print(f"\n{label} ({len(apps)})")
        for app in apps:
            days = (today - datetime.fromisoformat(app["last_activity"])).days
            kind = " [program]" if app["kind"] == "program" else ""
            print(f"   {app['company']:28.28} {(app['position'] or '-'):55.55} {days:>3}d ago{kind}")
    conn.close()


if __name__ == "__main__":
    build_applications()
    print_summary()
