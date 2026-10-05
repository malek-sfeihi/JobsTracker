import re
from html import unescape

from app.filters.job_filter import RULES, normalize

# Why a company said no, most specific first: the first category with a matching
# sentence wins. Patterns run on normalized text (lowercase, no accents).
REASONS = {
    "eligibility": [
        r"graduation date", r"eligibility requirement", r"not eligible", r"date de (fin d.etudes|diplome)",
    ],
    "location": [
        r"not currently hiring in your", r"work (authorization|permit)", r"\bvisa\b", r"sponsorship",
        r"autorisation de travail", r"permis de travail",
    ],
    "position_closed": [
        r"no longer (available|open)", r"position has been filled", r"plus disponible",
        r"poste (a ete )?pourvu", r"role has been filled",
    ],
    "format": [
        r"modalites de formation", r"duree (du|de) stage", r"convention de stage",
        r"internship (duration|dates|period)", r"periode de stage",
    ],
    "profile_mismatch": [
        r"ne correspond (malheureusement )?pas", r"does not (match|fit)", r"not (the right|a good) (fit|match)",
    ],
    "competition": [
        r"other candidates", r"autres candidatures", r"candidates whose", r"other applicants",
        r"large number of applications", r"high volume", r"nombre important de candidatures",
    ],
}

REASON_LABELS = {
    "eligibility": "Eligibility (e.g. graduation date)",
    "location": "Location or work permit",
    "position_closed": "Position closed",
    "format": "Internship format or timing",
    "profile_mismatch": "Profile didn't match the role",
    "competition": "Other candidates chosen",
    "no_reason": "No reason given",
}


def _sentences(body: str) -> list[str]:
    text = unescape(body)
    text = re.sub(r"<[^>]+>|https?://\S+", " ", text)  # HTML tags and links
    text = " ".join(text.split())
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if len(s.strip()) > 15]


def extract_reason(body: str) -> tuple[str, str]:
    """Return (reason category, the sentence of the email that says it)."""
    sentences = _sentences(body)
    for reason, patterns in REASONS.items():
        for sentence in sentences:
            if any(re.search(p, normalize(sentence)) for p in patterns):
                return reason, sentence

    # No specific reason: quote the sentence that announces the rejection instead
    for sentence in sentences:
        if any(re.search(p, normalize(sentence)) for p in RULES["rejection"]):
            return "no_reason", sentence
    return "no_reason", ""
