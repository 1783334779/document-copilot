# Data

Local data artifacts for development live here.

- `downloads/` holds raw source files fetched from SEC EDGAR, grouped by year.
- `markdown/` holds Docling-converted Markdown exports with the same year layout and manifest.
- Downloaded and converted payloads are gitignored because the corpus can get large.
- Fetch a sample corpus with `uv run data/download.py`
- Downloads retry temporary network failures up to four attempts. Rerunning reuses completed files, and `downloads/manifest.json` is saved after each filing. Set `CLEAR_OUTPUT_DIR = True` in the script only when you intend to delete and replace the downloaded corpus.
- Convert HTML filings to Markdown with `uv run data/convert_to_markdown.py`
