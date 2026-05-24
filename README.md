# Compass

A scraping pipeline for job listings. Three sources, two storage zones, idempotent re-runs, Dagster-orchestrated. Built to demonstrate the same patterns used by production legal-doc/news/job-board scrapers.

```
       sources                  landing zone                  processed zone
                       +--------------------------+    +---------------------+
  Hacker News  --+     | MinIO  compass-landing   |    | MinIO  compass-     |
  WeWorkRemotely-+--> | <source>/<post_id>.html  | -> | processed           |
  YC WAAS      --+     | Mongo  compass.jobs      |    | Mongo  compass.     |
                       |   metadata + file_hash   |    | jobs_processed      |
                       +--------------------------+    +---------------------+
                            scrapy + playwright            beautifulsoup
                                  ^                              ^
                                  +-------- Dagster -------------+
```

## Tech stack

- **Python 3.10**
- **Scrapy 2.11** for crawling — fast plain HTTP client for static pages
- **Playwright (Chromium)** wired in via `scrapy-playwright` — used only for JS-rendered or TLS-fingerprinted sources (YC Work at a Startup, WeWorkRemotely detail pages)
- **MongoDB 7** for metadata, **MinIO** for HTML files (the two-bucket pattern)
- **BeautifulSoup 4** for the transformation step
- **Dagster 1.13** for orchestration
- **python-dotenv** + `.env` for config, **python-json-logger** for structured logs
- All infra (Mongo, mongo-express, MinIO) runs via **docker-compose**

## Quick start

```bash
# 1. Clone + create venv
git clone https://github.com/Raghid-Mehanna/compass.git
cd compass
python -m venv venv
source venv/Scripts/activate          # Git Bash on Windows; or venv/bin/activate on Linux/Mac
pip install -r requirements.txt
playwright install chromium

# 2. Configure
cp .env.example .env                  # adjust Mongo/MinIO credentials if needed

# 3. Start infrastructure (Mongo, mongo-express, MinIO)
docker compose up -d

# 4. Run individual spiders (writes to landing zone)
cd scraper
scrapy crawl hackernews_jobs
scrapy crawl weworkremotely_jobs
scrapy crawl yc_workatastartup_jobs
cd ..

# 5. Run the transformation (writes to processed zone)
python -m transform.transformer
# Optional: limit by date or source
python -m transform.transformer --start-date 2026-05-01 --end-date 2026-05-31
python -m transform.transformer --source weworkremotely

# 6. Or use Dagster to orchestrate everything
dagster dev                           # http://localhost:3000
# In the UI, materialize the compass_full_pipeline job.
```

## Project layout

```
compass/
├── scraper/                            # Scrapy project (outer dir)
│   ├── scrapy.cfg
│   └── compass_scraper/                # Python package (the actual code)
│       ├── items.py                    # JobItem schema (the contract)
│       ├── pipelines.py                # StoragePipeline -> MongoPipeline
│       ├── settings.py                 # env-driven config
│       ├── storage.py                  # MinIO wrapper + SHA256 helper
│       ├── logging_setup.py            # JSON structured logging
│       └── spiders/
│           ├── hackernews_jobs.py
│           ├── weworkremotely_jobs.py
│           └── yc_workatastartup_jobs.py
├── transform/
│   └── transformer.py                  # BeautifulSoup cleanup pass
├── orchestration/                      # Dagster
│   ├── assets.py                       # 3 landing assets + 1 processed asset
│   ├── jobs.py
│   └── definitions.py
├── tests/                              # pytest suite
├── docker-compose.yml                  # mongo, mongo-express, minio
├── workspace.yaml                      # Dagster entrypoint
├── .env.example                        # config template
├── ARCHITECTURE.md                     # design decisions (1 page)
├── requirements.txt
└── README.md
```

## Data model

Every record in `compass.jobs` (landing) and `compass.jobs_processed` (processed) conforms to the same shape:

| Field          | Type | Example                                                              |
|----------------|------|----------------------------------------------------------------------|
| `post_id`      | str  | `nomad-senior-software-engineer-ii`                                 |
| `source`       | str  | `weworkremotely`, `yc_workatastartup`, `hn_whoshiring`              |
| `title`        | str  | `Senior Software Engineer II`                                        |
| `url`          | str  | `https://weworkremotely.com/remote-jobs/nomad-...`                  |
| `domain`       | str  | `weworkremotely.com`                                                 |
| `company`      | str  | `Nomad` (where the source exposes it)                                |
| `scraped_at`   | str  | ISO 8601 UTC timestamp, one per crawl run                            |
| `partition_date` | str | `YYYY-MM-DD` of the crawl run                                       |
| `file_path`    | str  | `weworkremotely/nomad-senior-software-engineer-ii.html`             |
| `file_hash`    | str  | SHA256 hex of the raw HTML in the landing bucket                     |

## Running the tests

```bash
pytest
```

## Architecture write-up

See [ARCHITECTURE.md](ARCHITECTURE.md) for partition strategy, retry/rate-limiting mechanisms, deduplication approach, and what would change at 50+ sources.

## Author

Raghid Mehanna · [LinkedIn](https://www.linkedin.com/in/Raghid-Mehanna) · [GitHub](https://github.com/Raghid-Mehanna)
