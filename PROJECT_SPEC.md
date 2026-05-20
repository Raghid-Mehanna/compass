# Compass — Personal Job Intelligence Pipeline

**Owner:** Raghid Mehanna
**Status:** v1 in active development
**Started:** 2026-05-20
**Visibility:** Public

---

## Motivation

I'm a recent MSc Mechatronics graduate running a disciplined multi-track job
search across the Gulf region and European tech startups. Within week one I
hit the patterns every serious job seeker hits:

- 10+ relevant job boards, each updated unpredictably
- The same role posted on 3–4 sites under different titles
- Roles closing within 48–72 hours that I'd miss if I checked manually
- Nationals-only roles ("UAE Nat / Saudi Nat / Emirati only") scattered
  through results, hard to filter cleanly
- No way to track changes over time

Manual aggregation was costing me ~90 minutes/day in check + triage — time
better spent on quality applications and interview prep.

So I built Compass.

---

## What Compass Does (v1)

A nightly data pipeline that:

1. Scrapes job postings from 5+ targeted boards
2. Normalizes them into a single consistent schema
3. Stores metadata in MongoDB and raw HTML in MinIO object storage
4. Deduplicates roles posted across multiple sources
5. Generates a structured daily digest of new and relevant opportunities

Runs in Docker, orchestrated by Dagster, idempotent, structured logging
throughout — built to the same engineering standards I'd apply to a
production client deliverable.

---

## Target Sources (v1)

| Source | Region | Priority |
|---|---|---|
| Bayt | Gulf (regional) | P0 |
| GulfTalent | Gulf (regional) | P0 |
| Wellfound (formerly AngelList) | Global startups | P0 |
| Y Combinator Work at a Startup | Global startups | P1 |
| Hacker News "Who's Hiring" monthly | Global tech | P1 |

LinkedIn is intentionally excluded due to ToS restrictions on automated
scraping.

---

## Functional Requirements (v1 — 5 features)

### F1 — Multi-source Ingestion
- Scrapy spider per source, with shared base class
- Playwright fallback for JS-rendered boards
- Per-source config (regions, categories, keyword filters)
- Raw HTML stored to MinIO for re-processing
- Configurable run schedules

### F2 — Metadata Extraction + Normalization
Per role, extract and normalize:
- Source platform + canonical listing ID
- Title (raw + normalized)
- Company name
- Location (country, city, remote/onsite/hybrid)
- Posting date + last updated
- Salary range + currency (where present)
- Seniority signal (entry/mid/senior/lead — rule-based)
- Skills mentioned in JD (keyword extraction)
- Nationals-only flag (Saudization / Emiratization signal detection)
- Application URL
- Full JD text (cleaned)
- Detected language (en / ar / mixed)

All output flows into one unified schema across all sources.

### F3 — Storage
- **MongoDB:** structured metadata, queryable
- **MinIO:** raw HTML + cleaned JD text, S3-compatible blob storage
- Each metadata record links to its raw artifact via path + file hash

### F4 — Deduplication
- Cross-source duplicate detection via fuzzy matching on:
  (company + title + location + posting_date)
- Confidence-scored matches: exact / high / medium
- Both raw view and deduplicated view remain queryable
- Idempotent: re-running over same date range produces zero duplicates

### F5 — Daily Digest
- Structured JSON + human-readable Markdown report
- Sections:
  - New roles since last run
  - Roles closing soon (where deadline detectable)
  - Per-source health (scraped / failed / skipped counts)
  - Filtered views: Gulf consulting · EU tech startups
- Optional email delivery (v1.5)

---

## Technical Stack

| Layer | Technology | Rationale |
|---|---|---|
| Language | Python 3.10 | Industry standard for data pipelines |
| Scraping (HTML) | Scrapy | Async-first, production-grade, scales |
| Scraping (JS) | Playwright | For JS-rendered boards |
| HTML parsing | BeautifulSoup4 + lxml | JD content extraction |
| Metadata store | MongoDB | Flexible schema across heterogeneous sources |
| Object storage | MinIO | S3-compatible, runs in Docker locally |
| Orchestration | Dagster | Modern, Python-native, asset-based |
| Infrastructure | Docker + docker-compose | Reproducible local stack |
| Config | YAML + env vars | No hardcoded values |
| Logging | structlog (JSON) | Machine-parseable structured logs |

---

## Architecture (High Level)
┌──────────────────────┐
              │  Dagster (scheduled)  │
              └──────────┬───────────┘
                         │
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
     ┌─────────┐    ┌─────────┐    ┌─────────┐
     │ Spider1 │    │ Spider2 │... │ SpiderN │
     │  Bayt   │    │  GTalent│    │ Wellfnd │
     └────┬────┘    └────┬────┘    └────┬────┘
          │              │              │
          └──────────────┼──────────────┘
                         ▼
              ┌──────────────────────┐
              │  Normalizer + Hasher  │
              └──────────┬───────────┘
                         │
          ┌──────────────┼──────────────┐
          ▼                             ▼
     ┌─────────────┐             ┌─────────────┐
     │   MongoDB   │             │    MinIO    │
     │  metadata   │             │  raw + JD   │
     └──────┬──────┘             └─────────────┘
            ▼
     ┌─────────────┐
     │ Deduplicator│
     └──────┬──────┘
            ▼
     ┌─────────────┐
     │Daily Digest │  →  JSON + Markdown
     └─────────────┘
     ---

## Deliverables

1. Git repository with full source, modular, documented
2. `docker-compose up` brings the entire stack online locally
3. CLI: `compass ingest --since YYYY-MM-DD --sources bayt,gulftalent`
4. CLI: `compass dedupe`
5. CLI: `compass digest --today`
6. ARCHITECTURE.md (1 page) explaining all design decisions
7. README.md with setup, usage, examples
8. Sample dataset: 500+ roles end-to-end across all sources

---

## Acceptance Criteria — v1 Complete When

- [ ] Minimum 5 sources integrated and producing data
- [ ] Full nightly run completes in under 30 minutes
- [ ] Idempotency verified: 2 consecutive runs → 0 duplicates
- [ ] Daily digest delivers in clean Markdown + JSON
- [ ] Compass has surfaced at least one role I actually applied to,
      that I'd have missed manually
- [ ] Documentation enables fresh clone + setup in under 30 minutes

---

## Out of Scope (v1)

- Semantic search / vector embeddings (v1.5)
- LLM-assisted classification (v1.5)
- Frontend / dashboard (v2)
- Cloud deployment (v2)
- Multi-user / SaaS features (never)
- LinkedIn scraping (excluded by policy)
- Application automation (excluded by design — applications stay human)

---

## Project Log

| Date | Milestone |
|---|---|
| 2026-05-20 | Project initialized · Spec committed |
| | |