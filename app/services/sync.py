from app.db.database import get_connection, known_email_ids, record_sync_run, save_email
from app.filters.job_filter import GMAIL_QUERY, IGNORED_SENDERS, classify, detect_kind
from app.services.gmail import fetch_emails, list_message_ids

MAX_EMAILS = 2000


def sync(interactive: bool = True) -> int:
    """Download only the emails we don't have yet, classify and store them. Returns how many.

    Every run (success or failure) is recorded in the sync_runs table for the dashboard.
    """
    conn = get_connection()
    try:
        all_ids = list_message_ids(GMAIL_QUERY, max_results=MAX_EMAILS, interactive=interactive)
        known = known_email_ids(conn)
        new_ids = [message_id for message_id in all_ids if message_id not in known]
        print(f"{len(all_ids)} emails match the search, {len(new_ids)} are new.")

        for email in fetch_emails(new_ids, interactive=interactive):
            sender = email["sender"].lower()
            category = None if any(name in sender for name in IGNORED_SENDERS) else classify(
                email["subject"], email["body"]
            )
            save_email(conn, email, category, detect_kind(email["sender"]))
            conn.commit()  # save after each email, so a crash halfway doesn't lose everything
    except Exception as error:
        record_sync_run(conn, None, ok=False, message=str(error))
        conn.close()
        raise  # re-raise: we recorded the failure, but the caller must still know it happened

    record_sync_run(conn, len(new_ids), ok=True)
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
    import traceback
    from datetime import datetime

    from app.core.config import BASE_DIR
    from app.services.applications import build_applications, print_summary

    scheduled = "--scheduled" in sys.argv
    if scheduled:
        # Scheduled runs have no console (pythonw.exe): send all output to a log file instead.
        # utf-8 because the summary contains emojis, which the default Windows encoding can't write.
        (BASE_DIR / "logs").mkdir(exist_ok=True)
        log = open(BASE_DIR / "logs" / "sync.log", "a", encoding="utf-8")
        sys.stdout = sys.stderr = log
        print(f"\n---------- scheduled sync {datetime.now():%Y-%m-%d %H:%M} ----------")

    try:
        if "--reclassify" in sys.argv:
            reclassify()
        else:
            sync(interactive=not scheduled)
        # Emails changed -> rebuild the applications and their statuses, then show the summary
        build_applications()
        print_summary()
    except Exception:
        traceback.print_exc()
        sys.exit(1)  # a non-zero exit code tells Task Scheduler the run failed
