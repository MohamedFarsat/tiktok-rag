# TikTok Community Guidelines Crawler

This project provides an ethical, robots-aware crawler that downloads TikTok Community Guidelines pages
and exports a Graph-RAG-ready JSONL dataset.

## Ethical Scraping Notes

- Uses a truthful User-Agent and conservative request rates.
- Honors explicit robots rules defined in the project.
- Uses retries with exponential backoff and conditional requests.
- Caches HTML responses and headers in `.cache/`.

## How to Run

```bash
python -m scraper.cli --start https://www.tiktok.com/community-guidelines/en --out data --max-pages 300
```

## Limitations

- Pages that require JavaScript rendering may not be fully captured.
