import json

import pytest

from pipeline.sec_filings import SecClient, filing_rows


def test_sec_requires_an_environment_identity():
    with pytest.raises(ValueError, match="SEC_USER_AGENT"):
        SecClient("")


def test_sec_header_and_rate_are_enforced(monkeypatch):
    clock = [10.0]
    request_times, headers = [], []
    monkeypatch.setattr("pipeline.sec_filings.time.monotonic", lambda: clock[0])
    monkeypatch.setattr("pipeline.sec_filings.time.sleep", lambda delay: clock.__setitem__(0, clock[0] + delay))

    class Response:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def read(self):
            return b"{}"

    def open_request(request, **kwargs):
        request_times.append(clock[0])
        headers.append(request.get_header("User-agent"))
        return Response()

    monkeypatch.setattr("pipeline.sec_filings.urlopen", open_request)
    identity = "Ripple test test@example.invalid"
    client = SecClient(identity)
    for _ in range(20):
        client.get("https://data.sec.gov/submissions/example.json")
    assert headers == [identity] * 20
    assert all(b - a >= 0.2 - 1e-9 for a, b in zip(request_times, request_times[1:]))


def test_cached_metadata_makes_no_network_request(tmp_path, monkeypatch):
    path = tmp_path / "cached.json"
    path.write_text(json.dumps({"name": "Public issuer"}), encoding="utf-8")
    client = SecClient("Ripple test test@example.invalid")
    monkeypatch.setattr(client, "get", lambda _: pytest.fail("Cache must not fetch SEC data"))
    assert client.cached_json("https://data.sec.gov/example.json", path)["name"] == "Public issuer"


def test_filing_column_data_preserves_report_and_publication_dates():
    rows = filing_rows({"accessionNumber": ["a", "b"], "reportDate": ["2023-12-31", "2022-12-31"], "filingDate": ["2024-02-01", "2023-02-01"], "form": ["10-K", "10-K"]})
    assert rows[0]["reportDate"] == "2023-12-31"
    assert rows[0]["filingDate"] == "2024-02-01"
    assert filing_rows({}) == []
