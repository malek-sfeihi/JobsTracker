"""Each case comes from a real email that the rules once got wrong (or must keep getting right)."""
import pytest

from app.filters.job_filter import classify, normalize


@pytest.mark.parametrize("subject, body, expected", [
    # The three original Thales examples
    ("Thank you for applying",
     "We have received your application for the position of Software Engineering Intern "
     "and are currently reviewing your experience.", "confirmation"),
    ("Invitation",
     "Vous êtes invité à participer à notre processus de sélection !", "assessment"),
    ("Thales Careers - Software Engineering Intern",
     "We regret to inform you that on this occasion you have not been selected.", "rejection"),
    # Confirmations that *look* like rejections: same words, opposite meaning
    ("Thank you for your application",
     "We have received your application. If you are not selected for this position, "
     "keep an eye on our jobs page.", "confirmation"),
    ("Thanks for applying!",
     "Unfortunately, due to the high volume of interest we cannot reply to everyone.", "confirmation"),
    # Real rejections phrased differently
    ("Your application", "We have decided not to move forward with your application.", "rejection"),
    ("Votre candidature", "Celle-ci ne correspond malheureusement pas au profil recherché.", "rejection"),
    # AI interviews, offers, programs
    ("Complete your interview to stay in consideration", "", "interview"),
    ("Good news", "We are delighted to offer you the position.", "offer"),
    ("Your Chevening application has been submitted", "", "confirmation"),
    # Noise that must stay out
    ("Aricoma recrute au poste de À distance", "New jobs for you", None),
    ("Partner offers", "Get a free eligibility assessment now!", None),
    ("AI in Hiring", "cv screening, matching, video interviewing and workforce management", None),
    ("Pouvons-nous vous garder dans notre vivier de talents?",
     "Nous aimerions conserver vos informations dans notre vivier de talents.", None),
])
def test_classify(subject, body, expected):
    assert classify(subject, body) == expected


def test_normalize_removes_accents_and_case():
    assert normalize("Candidature bien REÇUE") == "candidature bien recue"
