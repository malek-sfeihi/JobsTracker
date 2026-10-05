"""Fictional demo data, so the dashboard can be shown without anyone's real emails.

    DEMO=true python -m app.demo          (PowerShell: $env:DEMO="true"; python -m app.demo)

The fake emails go through the *real* pipeline (classifier -> grouping -> statuses ->
rejection reasons), so the demo also shows that the code works end to end.
"""
import random
from datetime import datetime, timedelta, timezone

from app.core.config import settings
from app.db.database import get_connection, record_sync_run, save_email
from app.filters.job_filter import classify, detect_kind
from app.services.applications import build_applications

# Email templates. {c} = company, {p} = position
TEMPLATES = {
    "confirmation": (
        "Thank you for applying to {c}",
        "Hi Alex, We have received your application for the position of {p}. "
        "Our team is currently reviewing your experience and will get back to you.",
    ),
    "confirmation_fr": (
        "Votre candidature chez {c}",
        "Bonjour Alex, Nous avons bien reçu votre candidature pour le poste de {p}. "
        "Notre équipe l'étudie avec attention.",
    ),
    "assessment": (
        "Your application to {c}: next step",
        "Hi Alex, Thanks again for applying for the position of {p}. "
        "As a next step, please complete the online assessment within 5 days.",
    ),
    "interview": (
        "Your application to {c}: interview invitation",
        "Hi Alex, We enjoyed reading your application for the position of {p} "
        "and would like to invite you to an interview with the team next week.",
    ),
    "offer": (
        "Your application to {c}: good news!",
        "Hi Alex, Congratulations! We are delighted to offer you the position of {p}. "
        "Your offer letter is attached.",
    ),
}
# Rejections, one per reason the dashboard knows about
REJECTIONS = {
    "competition": "After careful consideration, we have decided to move forward with other "
                   "candidates whose experience more closely matches the role.",
    "no_reason": "After careful consideration, we regret to inform you that you have not been "
                 "selected for this position.",
    "eligibility": "We reviewed your application and, unfortunately, your graduation date does not "
                   "meet the eligibility requirements for this role.",
    "location": "As we are not currently hiring in your country, we are unable to consider your "
                "application at this time.",
    "position_closed": "We regret to inform you that the position has been filled.",
    "profile_mismatch": "Votre candidature ne correspond malheureusement pas au profil recherché "
                        "pour ce poste.",
}

# (company, position, [(days ago, email type), ...])
STORIES = [
    ("Kestrel Labs", "Backend Engineer Intern",
     [(31, "confirmation"), (19, "interview"), (9, "interview"), (1, "offer")]),
    ("Orbital Forge", "Data Engineering Intern", [(6, "confirmation"), (2, "assessment")]),
    ("Contoso", "Software Engineer Intern", [(10, "confirmation"), (3, "interview")]),
    ("Nimbus Works", "Full Stack Developer Intern", [(2, "confirmation")]),
    ("Brightloop", "Python Developer Intern", [(4, "confirmation")]),
    ("Fabrikam", "Développeur Java", [(5, "confirmation_fr")]),
    ("Pixelgrove", "Frontend Engineer Intern", [(8, "confirmation")]),
    ("Tailspin", "Machine Learning Intern", [(11, "confirmation")]),
    ("Quillhaven", "Software Engineer Intern", [(13, "confirmation")]),
    ("Woodgrove", "Data Analyst Intern", [(1, "confirmation")]),
    ("Litware", "Backend Developer Intern", [(0, "confirmation")]),
    ("Northwind", "Cloud Engineer Intern", [(18, "confirmation")]),
    ("Adatum", "DevOps Intern", [(23, "confirmation")]),
    ("Wingtip", "Software Developer Intern", [(27, "confirmation")]),
    ("Lamna", "AI Engineer Intern", [(34, "confirmation")]),
    ("Driftwood AI", "NLP Research Intern", [(41, "confirmation")]),
    ("Relecloud", "Platform Engineer Intern", [(48, "confirmation")]),
    ("Ironleaf", "Software Engineer Intern", [(29, "confirmation"), (25, "assessment")]),
    ("Cobalt Harbor", "Backend Engineer Intern", [(26, "confirmation"), (22, "rejection:competition")]),
    ("Proseware", "Java Developer Intern", [(30, "confirmation"), (27, "rejection:no_reason")]),
    ("Vellora", "Quant Developer Intern", [(20, "confirmation"), (19, "rejection:eligibility")]),
    ("Lumen Atelier", "Software Developer Co-op", [(15, "confirmation"), (14, "rejection:location")]),
    ("Fourth Coffee", "Data Engineer Intern", [(37, "confirmation"), (32, "rejection:position_closed")]),
    ("Alpenglow", "Développeur Full Stack", [(16, "confirmation_fr"), (12, "rejection:profile_mismatch")]),
    ("Sablewood", "Software Engineer Intern", [(52, "confirmation"), (47, "rejection:competition")]),
    ("Driftmark", "Backend Developer Intern", [(9, "confirmation"), (8, "rejection:competition")]),
    ("Hollowpine", "Python Engineer Intern", [(12, "confirmation"), (11, "rejection:no_reason")]),
]


def _email(n: int, company: str, position: str, days_ago: int, kind: str, now: datetime) -> dict:
    if kind.startswith("rejection:"):
        subject = f"Your application at {company}"
        body = (f"Hi Alex, Thank you for applying for the position of {position}. "
                f"{REJECTIONS[kind.split(':')[1]]} We wish you all the best in your search.")
    else:
        subject, body = (part.format(c=company, p=position) for part in TEMPLATES[kind])
    domain = company.lower().replace(" ", "") + ".example"  # .example: reserved, never a real domain
    received = now - timedelta(days=days_ago, hours=random.randint(0, 9), minutes=random.randint(0, 59))
    return {
        "id": f"demo-{n:03d}", "thread_id": f"demo-{n:03d}",
        "sender": f"{company} Recruiting <no-reply@{domain}>", "subject": subject,
        "date": "", "received_at": received.isoformat(), "body": body,
    }


def seed_demo() -> None:
    if not settings.demo:
        raise SystemExit("Refusing to write demo data into your real database: set DEMO=true first.")
    settings.db_path.unlink(missing_ok=True)  # start fresh: demo.db only, never jobtracker.db
    random.seed(7)  # same "random" times on every run
    now = datetime.now(timezone.utc)

    conn = get_connection()
    n = 0
    for company, position, events in STORIES:
        for days_ago, kind in events:
            n += 1
            email = _email(n, company, position, days_ago, kind, now)
            save_email(conn, email, classify(email["subject"], email["body"]), detect_kind(email["sender"]))
    conn.commit()
    record_sync_run(conn, new_emails=3, ok=True)
    conn.close()
    build_applications()
    print(f"Demo database ready: {settings.db_path} ({n} emails, {len(STORIES)} applications)")


if __name__ == "__main__":
    seed_demo()
