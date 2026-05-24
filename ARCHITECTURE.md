# Compass — Architecture

A scraping pipeline that pulls job listings from three sources (Hacker News /jobs, WeWorkRemotely, YC Work at a Startup), stores raw HTML in MinIO and metadata in MongoDB, then runs a BeautifulSoup transformation step that produces cleaned HTML in a second bucket. Dagster orchestrates the whole DAG.

## Partition strategy

We use **scrape-date** as the partition key (`partition_date = YYYY-MM-DD of the crawl run`), not a source-supplied date filter. None of our three sources expose `start_date`/`end_date` query parameters the way the WRC reference site does; their indexes serve "currently active listings" only. Trying to fake monthly date partitions over a live feed would create silently-incorrect data — jobs would shift between partitions as they're posted/removed.

A scrape-date partition gives us the right semantics: every record is stamped with the day it was *observed*, so re-running the pipeline tomorrow produces a fresh partition without polluting yesterday's. If a source later adds real date filters, the field's semantics can be tightened without a schema change.

## Retries and rate limiting

Three coordinated mechanisms in `settings.py`:

1. **`DOWNLOAD_DELAY = 1` and `CONCURRENT_REQUESTS_PER_DOMAIN = 1`** — one in-flight request per domain at a time, with at least a one-second gap. Polite by default.
2. **`RETRY_HTTP_CODES = [403, 429, 500, 502, 503, 504]` with `RETRY_TIMES = 2`** — transient blocks and 5xx errors get up to two retries before the request is given up on.
3. **Per-spider `errback` handlers** — when a detail-page fetch fails terminally (after retries), the spider logs the URL and exception, then keeps going. The crawl is *resilient* rather than fail-fast: one bad employer page can't kill the run.

WeWorkRemotely is the noteworthy case. Their Cloudflare instance TLS-fingerprints standard Python HTTP clients and 403s them at the edge, no matter what headers we send. The fix isn't more polite headers — it's routing WWR detail-page requests through Playwright so the request carries a real Chromium TLS handshake. Slower (10× per-page cost) but reliable.

## Deduplication

Two-layer:

- **Identity** dedup: every record carries a `post_id` unique within its source. Mongo upserts by `(post_id, source)`, so re-running a spider never duplicates rows.
- **Content** dedup: every downloaded HTML body is SHA256-hashed. Before uploading to MinIO, the `StoragePipeline` checks Mongo for an existing record with the same `post_id`. If the existing `file_hash` matches the new hash, the upload is skipped entirely — no MinIO write, no Mongo update. This satisfies the "don't re-upload unchanged files" idempotency requirement at the cost of always re-fetching the source page; HEAD-with-ETag would save the network round trip but adds a per-source cache-header reliability concern.

The transformer (`transform/transformer.py`) re-hashes the cleaned output and applies the same skip-if-unchanged logic against `jobs_processed`, so re-running the transform on an unchanged landing zone is also a no-op.

## What I'd change for 50+ sources

The current design is fine for a handful of sources. At 50+ the pain shows in four places:

1. **Source config in code → source config in YAML.** Each new source today means a hand-written spider file. With 50+, sources should be declarative: a YAML file per source listing URL templates, CSS selectors, whether Playwright is needed, etc. A single generic spider reads that config and produces the same `JobItem`. This also lets non-engineers add sources.

2. **One process per crawl → distributed workers.** A single-machine Scrapy run hits Playwright RAM ceilings around 5-10 concurrent JS-rendered sources. Solution: each source becomes a Kubernetes job, scheduled by Dagster, with its own Playwright instance. Mongo and MinIO move from single-container to sharded.

3. **AutoThrottle per process → centralized rate limiter.** When 50 workers are each polite individually, the *target* sees the sum. Introduce a shared token-bucket service (Redis-backed) keyed by domain, so every worker respects the global budget.

4. **Schema versioning.** With 50 sources evolving independently, `JobItem` will need optional fields and parser versions. Adopt a `schema_version` field on each record and a Dagster asset that flags records produced by old schema versions for re-extraction from the landing-zone HTML — which is why we keep the landing zone immutable.

Encoding detection for non-English sources and jurisdiction-specific compliance (GDPR data subject requests, sitewise robots.txt overrides) round out the must-haves.
