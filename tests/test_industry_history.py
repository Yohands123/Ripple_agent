import pytest

from pipeline.industry_history import parse_evidence


def document(exchange="NASDAQ Global Select Market"):
    return ("<SEC-HEADER>\nCENTRAL INDEX KEY: 123\nSTANDARD INDUSTRIAL CLASSIFICATION: SEMICONDUCTORS [3674]\n</SEC-HEADER>"
            "<html>Securities registered pursuant to Section 12(b): Common stock Name of exchange " + exchange +
            " Securities registered pursuant to Section 12(g): None. Later discussion: New York Stock Exchange</html>").encode()


def test_classification_and_exchange_come_from_archived_header_and_cover():
    result = parse_evidence(document(), 123)
    assert result["sic"] == "3674"
    assert result["exchange"] == "NASDAQ"
    assert "Later discussion" not in result["exchangeEvidence"]
    assert parse_evidence(document("New York Stock Exchange"), 123)["exchange"] == "NYSE"


def test_unverified_or_ambiguous_exchange_is_not_guessed():
    assert parse_evidence(document("Unidentified exchange"), 123)["exchange"] is None
    assert parse_evidence(document("NASDAQ and NYSE"), 123)["exchange"] is None
    with pytest.raises(ValueError):
        parse_evidence(document(), 456)
