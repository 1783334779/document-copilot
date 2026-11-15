from __future__ import annotations

import importlib.util
import io
import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import Mock
from urllib.error import HTTPError, URLError

import pytest

spec = importlib.util.spec_from_file_location(
    "download", Path(__file__).resolve().parents[3] / "data" / "download.py"
)
download = importlib.util.module_from_spec(spec)
spec.loader.exec_module(download)


def test_retries_handshake_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    response = io.BytesIO(b"filing")
    urlopen = Mock(side_effect=[URLError(TimeoutError("handshake timed out")), response])
    monkeypatch.setattr(download.request, "urlopen", urlopen)
    monkeypatch.setattr(download.time, "sleep", Mock())

    assert download.get_bytes("https://www.sec.gov/test.htm") == b"filing"
    assert urlopen.call_count == 2


@pytest.mark.parametrize("status, attempts", [(403, 1), (404, 1), (429, 4), (503, 4)])
def test_http_failures_have_bounded_retries(
    monkeypatch: pytest.MonkeyPatch, status: int, attempts: int
) -> None:
    failure = HTTPError("https://www.sec.gov/test.htm", status, "error", {}, None)
    urlopen = Mock(side_effect=failure)
    monkeypatch.setattr(download.request, "urlopen", urlopen)
    monkeypatch.setattr(download.time, "sleep", Mock())

    with pytest.raises(HTTPError if attempts == 1 else RuntimeError):
        download.get_bytes("https://www.sec.gov/test.htm")
    assert urlopen.call_count == attempts


def test_retries_interrupted_response_body(monkeypatch: pytest.MonkeyPatch) -> None:
    response = Mock()
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    response.read.side_effect = download.IncompleteRead(b"partial", 100)
    urlopen = Mock(side_effect=[response, io.BytesIO(b"complete")])
    monkeypatch.setattr(download.request, "urlopen", urlopen)
    monkeypatch.setattr(download.time, "sleep", Mock())

    assert download.get_bytes("https://www.sec.gov/test.htm") == b"complete"


def test_resume_preserves_completed_files_and_manifest(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    year = str(datetime.now(UTC).year - 1)
    submission = {
        "filings": {
            "recent": {
                "form": ["10-K", "10-K"],
                "accessionNumber": ["001", "002"],
                "primaryDocument": ["first.htm", "second.htm"],
                "filingDate": [f"{year}-11-01", f"{year}-10-01"],
                "reportDate": [f"{year}-09-01", f"{year}-08-01"],
            },
            "files": [{"name": "unneeded-history.json"}],
        }
    }
    monkeypatch.setattr(download, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(download, "TICKERS", ["AAPL"])
    monkeypatch.setattr(download, "FILINGS_PER_COMPANY", 2)
    get_json = Mock(return_value=submission)
    monkeypatch.setattr(download, "get_json", get_json)
    get_bytes = Mock(side_effect=[b"first filing", URLError("offline")])
    monkeypatch.setattr(download, "get_bytes", get_bytes)

    with pytest.raises(URLError):
        download.download_filings()

    manifest_path = tmp_path / "manifest.json"
    checkpoint = json.loads(manifest_path.read_text())
    assert checkpoint["downloaded_count"] == 1
    first_file = tmp_path / checkpoint["filings"][0]["local_path"]
    assert first_file.read_bytes() == b"first filing"
    assert get_json.call_count == 1  # No unnecessary historical submissions request.

    get_bytes = Mock(return_value=b"second filing")
    monkeypatch.setattr(download, "get_bytes", get_bytes)
    result = download.download_filings()

    assert result["downloaded_count"] == 2
    assert first_file.read_bytes() == b"first filing"
    assert get_bytes.call_count == 1
    assert json.loads(manifest_path.read_text()) == result
    assert not list(tmp_path.rglob("*.part"))
