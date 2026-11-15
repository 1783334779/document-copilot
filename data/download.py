# /// script
# requires-python = ">=3.12"
# ///
from __future__ import annotations

import json
import shutil
import time
from datetime import UTC, datetime
from http.client import IncompleteRead
from pathlib import Path
from urllib import error, request


# Params: edit these, then run `uv run data/download.py`
USER_AGENT = "Document Copilot your.email@example.com"
TICKERS = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL"]
FILINGS_PER_COMPANY = 5
OUTPUT_DIR = Path(__file__).resolve().parent / "downloads"
CLEAR_OUTPUT_DIR = False
REQUEST_TIMEOUT = 60
REQUEST_ATTEMPTS = 4

COMPANY_CIKS = {
    "AAPL": "0000320193",
    "MSFT": "0000789019",
    "NVDA": "0001045810",
    "AMZN": "0001018724",
    "GOOGL": "0001652044",
}


def get_json(url: str) -> dict:
    return json.loads(get_bytes(url, accept="application/json"))


def get_bytes(
    url: str, accept: str = "text/html,application/xhtml+xml,application/xml"
) -> bytes:
    req = request.Request(
        url,
        headers={
            "Accept": accept,
            "User-Agent": USER_AGENT,
        },
    )
    for attempt in range(1, REQUEST_ATTEMPTS + 1):
        time.sleep(0.2)
        try:
            with request.urlopen(req, timeout=REQUEST_TIMEOUT) as response:
                return response.read()
        except (error.URLError, TimeoutError, ConnectionError, IncompleteRead) as exc:
            if isinstance(exc, error.HTTPError) and exc.code not in (
                408, 429, 500, 502, 503, 504
            ):
                raise
            if attempt == REQUEST_ATTEMPTS:
                raise RuntimeError(
                    f"Download failed after {attempt} attempts: {url}. "
                    "Completed files are preserved; rerun to resume."
                ) from exc
            delay = 2 ** attempt
            if isinstance(exc, error.HTTPError):
                retry_after = exc.headers.get("Retry-After", "")
                if retry_after.isdigit():
                    delay = max(delay, int(retry_after))
            print(
                f"Request failed ({exc}); retry {attempt}/{REQUEST_ATTEMPTS - 1} "
                f"in {delay}s: {url}",
                flush=True,
            )
            time.sleep(delay)

    raise AssertionError("REQUEST_ATTEMPTS must be positive")


def save_manifest(manifest: dict) -> None:
    manifest_path = OUTPUT_DIR / "manifest.json"
    temporary_path = manifest_path.with_suffix(".json.part")
    temporary_path.write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    temporary_path.replace(manifest_path)


def download_filings() -> dict:
    if CLEAR_OUTPUT_DIR and OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    target_years = {
        str(year)
        for year in range(
            datetime.now(UTC).year - FILINGS_PER_COMPANY, datetime.now(UTC).year
        )
    }
    manifest = {
        "source": "SEC EDGAR",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "form": "10-K",
        "downloaded_count": 0,
        "filings": [],
    }

    for ticker in TICKERS:
        print(f"Downloading {ticker} filings...", flush=True)
        cik = COMPANY_CIKS[ticker]
        submission = get_json(f"https://data.sec.gov/submissions/CIK{cik}.json")
        filings = extract_10k_filings(submission, target_years)
        for item in submission.get("filings", {}).get("files", []):
            if len(filings) >= FILINGS_PER_COMPANY:
                break
            sec_submission = get_json(
                f"https://data.sec.gov/submissions/{item['name']}"
            )
            filings.extend(extract_10k_filings(sec_submission, target_years))

        for filing in filings[:FILINGS_PER_COMPANY]:
            accession_path = filing["accession_number"].replace("-", "")
            source_url = (
                "https://www.sec.gov/Archives/edgar/data/"
                f"{int(cik)}/{accession_path}/{filing['primary_document']}"
            )
            year_dir = OUTPUT_DIR / filing["year"]
            year_dir.mkdir(parents=True, exist_ok=True)
            local_path = year_dir / (
                f"{ticker.lower()}_{filing['form'].lower()}_"
                f"{filing['filing_date']}_{filing['accession_number']}"
                f"{Path(filing['primary_document']).suffix or '.html'}"
            )
            if local_path.is_file() and local_path.stat().st_size:
                print(f"  Already downloaded: {local_path.name}", flush=True)
            else:
                print(f"  Downloading: {local_path.name}", flush=True)
                content = get_bytes(source_url)
                temporary_path = local_path.with_suffix(local_path.suffix + ".part")
                temporary_path.write_bytes(content)
                temporary_path.replace(local_path)

            manifest["filings"].append(
                {
                    "ticker": ticker,
                    "cik": cik,
                    "form": filing["form"],
                    "filing_date": filing["filing_date"],
                    "report_date": filing["report_date"],
                    "accession_number": filing["accession_number"],
                    "primary_document": filing["primary_document"],
                    "source_url": source_url,
                    "local_path": str(local_path.relative_to(OUTPUT_DIR)),
                }
            )
            manifest["downloaded_count"] += 1

            save_manifest(manifest)

    save_manifest(manifest)
    return manifest


def extract_10k_filings(
    submission: dict, target_years: set[str]
) -> list[dict[str, str]]:
    recent = submission["filings"]["recent"] if "filings" in submission else submission
    filings = []

    for form, accession, document, filing_date, report_date in zip(
        recent["form"],
        recent["accessionNumber"],
        recent["primaryDocument"],
        recent["filingDate"],
        recent["reportDate"],
        strict=True,
    ):
        year = (report_date or filing_date)[:4]
        if form == "10-K" and year in target_years:
            filings.append(
                {
                    "year": year,
                    "form": form,
                    "accession_number": accession,
                    "primary_document": document,
                    "filing_date": filing_date,
                    "report_date": report_date,
                }
            )

    return filings


if __name__ == "__main__":
    result = download_filings()
    print(f"Downloaded {result['downloaded_count']} filing(s) to {OUTPUT_DIR}")
    print(f"Manifest: {OUTPUT_DIR / 'manifest.json'}")
