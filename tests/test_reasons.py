import pytest

from app.filters.reasons import extract_reason


@pytest.mark.parametrize("body, expected", [
    ("We've reviewed your application and, unfortunately, your graduation date does not meet "
     "the eligibility requirements for this role.", "eligibility"),
    ("As we are not currently hiring in your state/country, we are unable to consider your "
     "application.", "location"),
    ("Le poste auquel vous avez postulé n'étant malheureusement plus disponible, nous ne pouvons "
     "pas donner suite.", "position_closed"),
    ("Nous privilégions des candidatures dont le cadre et les modalités de formation correspondent "
     "davantage à nos équipes.", "format"),
    ("A ce jour, celle-ci ne correspond malheureusement pas au profil recherch&eacute; pour le poste.",
     "profile_mismatch"),
    ("We have decided to move forward with other candidates whose experience aligns more closely.",
     "competition"),
    ("We regret to inform you that on this occasion you have not been selected.", "no_reason"),
])
def test_extract_reason(body, expected):
    reason, quote = extract_reason(body)
    assert reason == expected
    assert quote  # always show the user the actual sentence


def test_quote_is_cleaned_of_html_entities():
    _, quote = extract_reason("Votre profil ne correspond pas au profil recherch&eacute;.")
    assert "recherché" in quote
