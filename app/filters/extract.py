import re
from email.utils import parseaddr

from app.filters.job_filter import normalize

# Recruiting platforms (ATS) send emails for many companies, so their domain says nothing
# about the company. For Workday the company is the part before the @: thales@myworkday.com
ATS_DOMAINS = [
    "myworkday", "lever", "workable", "workablemail", "ashbyhq", "smartrecruiters", "join",
    "bamboohr", "pinpoint", "greenhouse", "teamtailor", "welcomekit", "jobposting", "dayforce",
    "allibo", "recruitee", "jobvite", "icims", "successfactors", "taleo", "hellowork",
    "welcometothejungle",
]
# Domains that don't name the organisation: personal mailboxes, governments, the EU...
GENERIC_DOMAINS = ["gmail", "outlook", "hotmail", "yahoo", "gov", "europa"]
# Workday addresses that aren't a company name (system@myworkday.com...)
WORKDAY_NON_COMPANY = ["system", "workday", "notification", "notifications", "noreply", "no-reply"]

# Patterns are applied to the *normalized* subject (lowercase, no accents)
COMPANY_IN_SUBJECT = [
    r"(?:applying|application) (?:to|at) ([\w&.' -]+?)(?:[!.:|]|$)",
    r"(?:applying|application) at ([\w&.' -]+?)(?:[!.:|]|$)",
    r"candidature (?:chez|a) ([\w&.' -]+?)(?:[!.:|]|$)",
    r"\bat ([\w&.' -]+?)$",
    r"postule (?:chez|d.) ?([\w&.' -]+?)(?:[!.:|]|$)",
    r"bewerbung bei ([\w&.' -]+?)(?:[!.:|]|$)",
]

POSITION_PATTERNS = [
    r"for the (?:position|role) of ([^.\n]+?)(?: \(| and |[.\n])",
    r"for the ([^.\n]+?) (?:position|role|job)\b",
    r"(?:au |pour le )poste (?:de |d.)?([^.\n]+?)(?: \(| et |[.\n]|$)",
    r"in the ([^.\n]+?) role\b",
    r"candidature (?:bien recue )?pour (?:etre )?([^.\n]+?)$",
    r"application well received for ([^.\n]+?)$",
    r"thank you for applying - ([^.\n]+?)$",
    r"thales careers - ([^.\n]+?)$",
    r"application - ([^.\n]+?) at ",
    r"thanks for applying to ([^.\n]+?) - ",
]

TEAM_WORDS = r"\b(recruiting|recruitment|talent|hiring|hr|rh|team|equipe|careers?|workday|notification|no ?reply|de recrutement|de chez|group)\b"


def company_key(name: str) -> str:
    """A comparable key: "Sopra Steria", "soprasteria" and "Sopra Steria Group" -> "soprasteria"."""
    name = normalize(name)
    name = re.sub(r"\b(group|groupe|inc|sa|sas|gmbh|ltd|spa|international|careers?)\b", "", name)
    return re.sub(r"[^a-z0-9]", "", name)


def _company_from_address(address: str) -> str | None:
    local, _, domain = address.lower().partition("@")
    parts = domain.split(".")
    if len(parts) < 2:
        return None
    main = parts[-2]  # mail.amazon.jobs -> amazon, jobalerts.thalesgroup.com -> thalesgroup
    if main == "myworkday":
        # Workday is the one platform that puts the company before the @: thales@myworkday.com
        return None if local in WORKDAY_NON_COMPANY else local
    if any(main.startswith(ats) for ats in ATS_DOMAINS) or main in GENERIC_DOMAINS:
        # Other platforms use random codes (r-c-6a6f704e...@...) -> use the display name instead
        return None
    return main


def _company_from_display_name(display: str) -> str | None:
    display = normalize(display)
    display = re.sub(r"\[via .*?\]|via linkedin|/.*$", "", display)  # "Ibexa/Internship - ..." -> "ibexa"
    display = re.sub(r"equipe (?:rh |de recrutement )?de |^.* de chez ", "", display)
    display = re.sub(TEAM_WORDS, "", display)
    display = display.strip(" \"'-|")
    return display or None


def extract_company(sender: str, subject: str) -> str | None:
    """Best guess of the company name, from the subject, then the sender address, then its name."""
    clean_subject = normalize(subject)
    for pattern in COMPANY_IN_SUBJECT:
        match = re.search(pattern, clean_subject)
        if match and len(match.group(1).split()) <= 4:  # a company name, not a whole sentence
            return match.group(1).strip()

    display, address = parseaddr(sender)
    return _company_from_address(address) or _company_from_display_name(display)


def extract_position(subject: str, body: str) -> str | None:
    """Best guess of the job title, looked for in the subject first, then the body."""
    for text in (normalize(subject), normalize(body)[:3000]):
        for pattern in POSITION_PATTERNS:
            match = re.search(pattern, text, re.MULTILINE)
            position = match.group(1).strip(" -:") if match else ""
            if _looks_like_position(position):
                return position
    return None


def _looks_like_position(text: str) -> bool:
    # Rejects sentence fragments like "meantime, you can already check..." or "un poste chez x"
    return (
        5 <= len(text) <= 120
        and not re.search(r"\b(you|your|vous|votre|un poste|a position)\b", text)
    )


def same_company(key_a: str, key_b: str) -> bool:
    """"thales" and "thalesgroup", "lucca" and "ilucca" are the same company."""
    if not key_a or not key_b:
        return False
    if key_a == key_b:
        return True
    shorter, longer = sorted((key_a, key_b), key=len)
    return len(shorter) >= 4 and shorter in longer
