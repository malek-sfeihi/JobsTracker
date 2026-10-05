from app.db.database import get_connection, known_email_ids, save_email
from app.filters.job_filter import GMAIL_QUERY, IGNORED_SENDERS, classify, detect_kind
from app.services.gmail import fetch_emails, list_message_ids

MAX_EMAILS = 2000


def sync() -> int:
    """Download only the emails we don't have yet, classify and store them. Returns how many."""
    conn = get_connection()
    all_ids = list_message_ids(GMAIL_QUERY, max_results=MAX_EMAILS)
    known = known_email_ids(conn)
    new_ids = [message_id for message_id in all_ids if message_id not in known]
    print(f"{len(all_ids)} emails match the search, {len(new_ids)} are new.")

    for email in fetch_emails(new_ids):
        sender = email["sender"].lower()
        category = None if any(name in sender for name in IGNORED_SENDERS) else classify(
            email["subject"], email["body"]
        )
        save_email(conn, email, category, detect_kind(email["sender"]))
        conn.commit()  # save after each email, so a crash halfway doesn't lose everything

    conn.close()
    return len(new_ids)


def reclassify() -> None:
    """Re-run the rules on every stored email (after editing RULES) - no Gmail calls needed."""
    conn = get_connection()
    for row in conn.execute("SELECT id, sender, subject, body FROM emails").fetchall():
        sender = row["sender"].lower()
        category = None if any(name in sender for name in IGNORED_SENDERS) else classify(
            row["subject"], row["body"]
        )
        conn.execute(
            "UPDATE emails SET category = ?, kind = ? WHERE id = ?",
            (category, detect_kind(row["sender"]), row["id"]),
        )
    conn.commit()
    conn.close()


if __name__ == "__main__":
    import sys

    from app.services.applications import build_applications, print_summary

    if "--reclassify" in sys.argv:
        reclassify()
    else:
        sync()

    # Emails changed -> rebuild the applications and their statuses, then show the summary
    build_applications()
    print_summary()
