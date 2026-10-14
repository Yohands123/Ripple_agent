from pathlib import Path
from types import SimpleNamespace

import pytest

from pipeline.supplier_lists import (
    ParseError, address_row, fetch_pdf, fiscal_year, parse_page, parse_pdf, region_rows,
)


def word(text, x, y):
    return {"text": text, "x0": x, "x1": x + 20, "top": y, "bottom": y + 8}


class Page:
    height = 400

    def __init__(self, words, edges):
        self.words = words
        self.horizontal_edges = [{"x0": x0, "x1": x1, "top": y} for x0, x1, y in edges]

    def dedupe_chars(self):
        return self

    def extract_words(self, **kwargs):
        return self.words


def test_fiscal_year_uses_reporting_year_not_publication_year():
    assert fiscal_year("Apple Supplier Responsibility 2019\nfor fiscal year 2018.") == 2018
    with pytest.raises(ParseError):
        fiscal_year("Supplier List published 2019")
    with pytest.raises(ParseError):
        fiscal_year("fiscal year 2020 and fiscal year 2021")
    assert fiscal_year("February 2017: procurement for our products worldwide in 2016.") == 2016


def test_legacy_address_table_retains_first_last_rows_and_skips_footer():
    page = Page([
        word("Supplier", 10, 80), word("Name", 50, 80), word("Address", 200, 80),
        word("First", 10, 100), word("Shanghai,", 200, 100), word("China", 280, 100),
        word("Last", 10, 140), word("Tokyo,", 200, 140), word("Japan", 280, 140),
        word("For More Information", 10, 250), word("not a supplier address", 200, 270),
    ], [(10, 180, 90), (200, 400, 90), (10, 400, 120)])
    rows, _ = parse_page(page)
    assert [(r["supplier"], r["country"]) for r in rows] == [("First", "China"), ("Last", "Japan")]


def test_regions_expand_without_splitting_parenthesized_names():
    rows = region_rows("Supplier (continued)", "Kedah; Malacca (Melaka), Perak", "Malaysia")
    assert [r["location"] for r in rows] == ["Kedah", "Malacca (Melaka)", "Perak"]
    assert all(r["supplier"] == "Supplier" for r in rows)
    assert region_rows("Supplier", "", "Singapore")[0]["location"] == "Singapore"
    with pytest.raises(ParseError):
        region_rows("", "Kedah", "Malaysia")


def test_street_address_is_preserved_and_country_is_normalized():
    row = address_row("Supplier", "No. 8, Industrial Park, Suzhou, Jiangsu, China")
    assert row["location"] == "No. 8, Industrial Park, Suzhou, Jiangsu, China"
    assert row["country"] == "China"
    assert address_row("Supplier", "Incheon, Korea")["country"] == "South Korea"
    with pytest.raises(ParseError):
        address_row("Supplier", "Address without a country")


def test_vertically_centered_name_applies_to_every_country_row():
    page = Page([
        word("Supplier", 10, 80), word("Name", 50, 80), word("Primary", 200, 80),
        word("Example", 10, 140), word("Corporation", 70, 140),
        word("Guangdong;", 200, 105), word("Jiangsu", 200, 115),
        word("China", 320, 110), word("mainland", 355, 110),
        word("Yamagata", 200, 150), word("Japan", 320, 150),
    ], [(10, 400, 100), (200, 400, 130), (10, 400, 180)])
    rows, previous = parse_page(page)
    assert previous == "Example Corporation"
    assert [(r["supplier"], r["location"], r["country"]) for r in rows] == [
        ("Example Corporation", "Guangdong", "China"),
        ("Example Corporation", "Jiangsu", "China"),
        ("Example Corporation", "Yamagata", "Japan"),
    ]


def test_final_supplier_without_bottom_border_is_not_lost():
    page = Page([
        word("Supplier", 10, 80), word("Name", 50, 80), word("Primary", 200, 80),
        word("First", 10, 110), word("Guangdong", 200, 110), word("China", 320, 110),
        word("Last", 10, 170), word("Oregon", 200, 170), word("United", 320, 170), word("States", 355, 170),
    ], [(10, 400, 100), (10, 400, 160)])
    rows, _ = parse_page(page)
    assert [r["supplier"] for r in rows] == ["First", "Last"]
    assert rows[-1]["location"] == "Oregon"


def test_continued_supplier_across_pages():
    page = Page([
        word("Supplier", 10, 80), word("Name", 50, 80), word("Primary", 200, 80),
        word("Shanghai", 200, 110), word("China", 320, 110),
    ], [(10, 400, 100), (10, 400, 150)])
    assert parse_page(page, "Previous Company")[0][0]["supplier"] == "Previous Company"
    with pytest.raises(ParseError):
        parse_page(page)


def test_headquarters_section_is_separate_and_notes_are_not_rows():
    page = Page([
        word("Supplier", 10, 80), word("Name", 50, 80), word("Primary", 200, 80),
        word("Factory", 10, 110), word("Shanghai", 200, 110), word("China", 320, 110),
        word("The suppliers below do not have internal manufacturing sites", 10, 180),
        word("Supplier", 10, 210), word("Name", 50, 210), word("Location", 200, 210),
        word("Fabless", 10, 240), word("California", 200, 240), word("United", 320, 240), word("States", 355, 240),
    ], [(10, 400, 100), (10, 400, 150), (10, 400, 230), (10, 400, 260)])
    rows, _ = parse_page(page)
    assert [(r["supplier"], r["locationRole"]) for r in rows] == [("Factory", "manufacturing"), ("Fabless", "headquarters")]


def test_html_is_not_accepted_as_a_pdf():
    response = SimpleNamespace(content=b"<html>Not a PDF</html>", text="No attachment", url="https://example.org", raise_for_status=lambda: None)
    session = SimpleNamespace(get=lambda *args, **kwargs: response)
    with pytest.raises(ParseError, match="HTML"):
        fetch_pdf("https://example.org/renamed.pdf", session)


def test_cached_pdf_cannot_be_relabelled_with_a_different_year():
    path = Path("data/raw/supplier_lists/suppliers_2020.pdf")
    if not path.exists():
        pytest.skip("Raw PDFs are intentionally not committed")
    with pytest.raises(ParseError, match="Expected FY2021, document covers FY2020"):
        parse_pdf(path, 2021)
