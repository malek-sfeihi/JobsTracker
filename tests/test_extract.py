import pytest

from app.filters.extract import company_key, extract_company, extract_position, same_company


@pytest.mark.parametrize("sender, subject, expected", [
    # From the subject
    ("no-reply@datadoghq.com", "Thank you for applying to Datadog", "datadog"),
    ("no-reply@company.example", "Your application at Bigblue", "bigblue"),
    # Workday puts the company before the @
    ("Thales Group <thales@myworkday.com>", "Thales Careers - Software Engineering Intern", "thales"),
    ("FRAMATOME RECRUTEMENT <framatome@talent-soft.com>", "Votre candidature - offre 2026-27758", "framatome"),
    # Company domain
    ("no-reply@optiver.com", "Optiver – Application Update", "optiver"),
    # Recruiting platform with a random code before the @: fall back to the display name
    ('"Équipe RH de Redpill" <redpi-04741de1f838@reply.hellowork.com>', "Candidature bien reçue", "redpill"),
])
def test_extract_company(sender, subject, expected):
    assert extract_company(sender, subject) == expected


def test_same_company_tolerates_suffixes():
    assert same_company(company_key("Thales"), company_key("thalesgroup"))
    assert same_company(company_key("Lucca"), company_key("ilucca"))
    assert same_company(company_key("Sopra Steria"), company_key("soprasteria"))


def test_same_company_ignores_very_short_keys():
    # "ca" is inside "cat", but 2 letters are too short to mean anything
    assert not same_company("ca", "cat")


def test_extract_position_from_body():
    body = "We have reviewed your application for the position of Software Engineering Intern (R0339364)."
    assert extract_position("Update", body) == "software engineering intern"


def test_extract_position_rejects_sentence_fragments():
    assert extract_position("Nous avons reçu votre candidature pour un poste chez TwoWay", "") is None
