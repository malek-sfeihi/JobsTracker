from datetime import datetime, timedelta, timezone

import pytest

from app.services.applications import _same_position, compute_status

TODAY = datetime(2026, 10, 5, tzinfo=timezone.utc)


def email(category: str, days_ago: int, subject: str = "") -> dict:
    return {"category": category, "date": TODAY - timedelta(days=days_ago), "subject": subject}


@pytest.mark.parametrize("emails, expected", [
    ([email("confirmation", 3)], "in_progress"),
    ([email("confirmation", 20)], "ghosted"),                        # 15+ days of silence
    ([email("confirmation", 9), email("rejection", 8)], "rejected"),
    ([email("confirmation", 6), email("assessment", 2)], "action_needed"),
    ([email("confirmation", 29), email("assessment", 25)], "expired"),  # invitation never done
    ([email("assessment", 3, "Assessment Completed")], "in_progress"),  # done: their turn now
    ([email("interview", 9), email("offer", 1)], "offer"),
])
def test_compute_status(emails, expected):
    assert compute_status(emails, TODAY) == expected


def test_same_position_uses_job_ids_first():
    assert _same_position("Software Engineering Intern (R0339364)", "software engineering intern (r0339364)")
    assert not _same_position("SDE Intern (id: 3074226)", "SDE Intern (id: 10555863)")


def test_one_word_difference_means_different_positions():
    # 85% similar text, but Germany and France were two separate Amazon applications
    assert not _same_position("2026 software dev engineer intern - germany",
                              "2027 software dev engineer intern - france")
