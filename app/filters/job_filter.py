import re
import unicodedata

# Gmail-side pre-filter: only download emails that mention an application at all.
# {a b c} means "a OR b OR c" in Gmail search syntax.
GMAIL_QUERY = (
    "newer_than:75d -in:sent "
    "{candidature application applying applied postule postulé entretien interview assessment}"
)

# Checked in this order: the first category that matches wins.
# Rejection comes before confirmation because rejections often also say
# "thank you for your application".
RULES = {
    "offer": [
        r"pleased to offer you", r"delighted to offer you", r"offer letter",
        r"heureux de vous proposer", r"promesse d.embauche",
    ],
    # Careful: confirmations often say "IF you are not selected..." or "Unfortunately, due to
    # the high volume we can't reply to everyone" - so we match full phrases, not single words.
    "rejection": [
        r"regret to inform", r"not been selected", r"you were not selected",
        r"not (be )?moving forward", r"not to (move forward|proceed)",
        r"(decided|chosen) to (pursue|move forward with|proceed with) (other )?candidates",
        r"unfortunately,? (we|you|your|the position|at this time|on this occasion)",
        r"position has been filled", r"not currently hiring in your",
        r"malheureusement", r"ne pas donner suite", r"pas (pu )?donner (une )?suite",
        r"pas ete retenue?", r"avons le regret", r"regret de vous informer",
        r"vivier de talents",
    ],
    "interview": [
        r"invite you (to|for) an interview", r"schedule an interview", r"interview invitation",
        # AI / one-way video interviews (micro1, HireVue...) are part of many selection processes
        r"complete your (ai |video )?interview", r"interview is pending",
        r"(one-way|video|recorded) interview\b", r"hirevue", r"entretien video differe",
        r"entretien (telephonique|video|visio|rh|technique)?\s*(avec|le|pour)",
        r"vous rencontrer", r"planifier un (entretien|echange)",
    ],
    # "assessment" alone matched ads ("free assessment"), so we require a job-test context
    "assessment": [
        r"(online|technical|coding) assessment", r"assessment completed",
        r"complete (the|an|your) assessment",
        r"coding (challenge|test)", r"hackerrank", r"codingame", r"codility",
        r"test technique", r"processus de selection", r"invite a participer",
    ],
    "confirmation": [
        r"received your application", r"receipt of your application",
        r"confirmation of your application", r"application received",
        r"thank(s| you) for (applying|your application)", r"application (has been|was) (received|sent|submitted)",
        r"bien recu votre candidature", r"candidature bien recue", r"reception de votre candidature",
        r"candidature a (bien )?ete (recue|envoyee|transmise)", r"merci (pour|de) votre candidature",
        r"merci d.avoir postule",
    ],
}

# Senders whose emails look like applications but aren't (school marketing...)
IGNORED_SENDERS = ["escp"]

# Real applications, but to scholarships/programs rather than jobs: tracked separately
PROGRAM_SENDERS = ["chevening", "european solidarity corps"]


def detect_kind(sender: str) -> str:
    """Return "program" for scholarships/programs, "job" for everything else."""
    sender = sender.lower()
    return "program" if any(name in sender for name in PROGRAM_SENDERS) else "job"


def normalize(text: str) -> str:
    """Lowercase and remove accents, so "Reçu" and "recu" match the same rule."""
    text = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in text if not unicodedata.combining(c))


def explain(subject: str, body: str) -> tuple[str, str, str] | None:
    """Return (category, pattern, matched text) for the first rule that matches, or None."""
    text = normalize(f"{subject}\n{body}")
    for category, patterns in RULES.items():
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                context = text[max(0, match.start() - 60):match.end() + 60]
                return category, pattern, " ".join(context.split())
    return None


def classify(subject: str, body: str) -> str | None:
    """Return the category of a job email, or None if it isn't one."""
    result = explain(subject, body)
    return result[0] if result else None


if __name__ == "__main__":
    from app.services.gmail import search_emails

    emails = search_emails(GMAIL_QUERY, max_results=300)
    matched, unmatched = [], []
    for email in emails:
        if any(name in email["sender"].lower() for name in IGNORED_SENDERS):
            continue
        category = classify(email["subject"], email["body"])
        (matched if category else unmatched).append((category, email))

    print(f"\n=== {len(matched)} job emails out of {len(emails)} searched ===")
    for category, email in matched:
        kind = detect_kind(email["sender"])
        print(f"[{kind:7}] [{category:12}] {email['date'][:16]} | {email['sender'][:35]:35} | {email['subject']}")

    print(f"\n=== {len(unmatched)} not classified (check for misses!) ===")
    for _, email in unmatched:
        print(f"{email['date'][:16]} | {email['sender'][:35]:35} | {email['subject']}")
