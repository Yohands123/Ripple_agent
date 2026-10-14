import csv
import json
from pathlib import Path

import pytest

from pipeline.extract_profiles import apple_revenue_share, product_category


def test_named_revenue_percentages_follow_ordered_years():
    text = "In fiscal 2023, 2022, and 2021, Apple, through sales to multiple distributors, accounted for 66%, 58%, and 59% of net revenue, respectively."
    assert apple_revenue_share(text, 2023)[0] == pytest.approx(0.66)
    assert apple_revenue_share(text, 2022)[0] == pytest.approx(0.58)
    assert apple_revenue_share(text, 2021)[0] == pytest.approx(0.59)
    assert apple_revenue_share(text, 2020) == (None, None)


def test_percentages_before_years_and_decimal_values():
    text = "Sales to Apple Inc. accounted for approximately 17.5%, 19%, and 22% of our net sales for fiscal years 2023, 2022, and 2021, respectively."
    assert apple_revenue_share(text, 2023)[0] == pytest.approx(0.175)


def test_spelled_percent_and_pdf_line_breaks():
    text = "For fiscal years 2023, 2022, and 2021, Apple Inc., who purchased through manufacturers, represented approximately 83 percent, 79 percent, and 83 percent of total sales, respectively."
    assert apple_revenue_share(text.replace(" ", "\n"), 2022)[0] == pytest.approx(0.79)


def test_earlier_year_mentions_do_not_hide_overlapping_disclosure():
    text = "For fiscal year 2023 and each of fiscal years 2022 and 2021, our ten largest customers represented 92 percent and 93 percent of sales, respectively. For fiscal years 2023, 2022, and 2021, Apple, Inc. represented approximately 83 percent, 79 percent, and 83 percent of total sales, respectively."
    assert apple_revenue_share(text, 2023)[0] == pytest.approx(0.83)


def test_named_customer_table_maps_each_percentage_to_its_column():
    text = "Concentration of net revenue during the periods indicated: Fiscal Year Ended August 31, 2023 2022 2021 Apple, Inc. 17 % 19 % 22 % Competition"
    assert apple_revenue_share(text, 2023)[0] == pytest.approx(0.17)
    assert apple_revenue_share(text, 2021)[0] == pytest.approx(0.22)


def test_explicit_same_share_for_each_year_and_single_year():
    text = "Aggregate sales to Apple Inc., through all channels, accounted for approximately 20% of net revenue for each of fiscal years 2023 and 2022."
    assert apple_revenue_share(text, 2023)[0] == pytest.approx(0.2)
    assert apple_revenue_share(text, 2022)[0] == pytest.approx(0.2)
    assert apple_revenue_share("Apple represented 18% of total sales for fiscal year 2018.", 2018)[0] == pytest.approx(0.18)


@pytest.mark.parametrize("text", [
    "In fiscal 2023, 2022, and 2021, customer A represented 50%, 40%, and 30% of net revenue, respectively.",
    "In fiscal 2023, 2022, and 2021, Apple represented 50%, 40%, and 30% of accounts receivable, respectively.",
    "In fiscal 2023, 2022, and 2021, Apple represented more than 10%, 10%, and 10% of net revenue, respectively.",
    "In fiscal 2023, 2022, and 2021, Apple and Samsung represented 50%, 40%, and 30% of net revenue, respectively.",
    "In fiscal 2023, 2022, and 2021, Apple represented 50% and 40% of net revenue, respectively.",
])
def test_other_measures_and_ambiguous_attributions_stay_unknown(text):
    assert apple_revenue_share(text, 2023) == (None, None)


def test_conflicting_disclosures_are_not_resolved_by_guessing():
    text = "In fiscal 2023, 2022, and 2021, Apple represented 50%, 40%, and 30% of net revenue, respectively. In fiscal 2023, 2022, and 2021, Apple represented 60%, 40%, and 30% of net revenue, respectively."
    assert apple_revenue_share(text, 2023) == (None, None)


def test_product_rule_requires_a_business_or_product_passage():
    issuer = {"evidence": "foundry", "partType": "semiconductor foundry"}
    assert product_category(["A foundry litigation risk."], issuer) == (None, None)
    assert product_category(["Business overview: our semiconductor foundry services."], issuer) == ("semiconductor foundry", 1)


def test_processed_values_have_sources_and_review_has_thirty_rows():
    path = Path("data/processed/supplier_profiles.json")
    if not path.exists():
        pytest.skip("Run M3 extraction to verify processed outputs")
    result = json.loads(path.read_text(encoding="utf-8"))
    for profile in result["profiles"]:
        for field in ["partType", "appleRevenueShare"]:
            if profile[field] is not None:
                assert profile[field + "Source"]["title"]
                assert profile[field + "Source"]["url"].startswith("https://")
        if profile["appleRevenueShare"] is not None:
            assert 0 <= profile["appleRevenueShare"] <= 1
    with Path("data/review/hand_check.csv").open(encoding="utf-8") as handle:
        assert len(list(csv.DictReader(handle))) == 30
