"""
Dagster assets for the Compass pipeline.

Two layers:

  Landing assets (one per source)
      hn_landing, wwr_landing, waas_landing
      Each runs `scrapy crawl <spider>` as a subprocess. The spider writes
      metadata to Mongo `jobs` and raw HTML to MinIO `compass-landing`.

  Processed asset (depends on all three landing assets)
      processed_jobs
      Runs transform.transformer to clean HTML and write to MinIO
      `compass-processed` plus Mongo `jobs_processed`.

The dependency graph is `(hn|wwr|waas)_landing -> processed_jobs`, so a
single `dagster asset materialize --select '*'` invocation does the full
end-to-end run with proper ordering and parallelism on the landing layer.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from dagster import MaterializeResult, asset


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRAPER_DIR = PROJECT_ROOT / "scraper"


def _run_spider(spider_name: str, context) -> MaterializeResult:
    """Run `scrapy crawl <spider_name>` as a subprocess.

    Using a subprocess (rather than embedding Scrapy's CrawlerProcess) keeps
    Twisted's reactor + Playwright's asyncio loop isolated from Dagster's
    event loop. Trade-off: separate process means we log Scrapy's stdout via
    `context.log` rather than getting structured asset materialization metadata.
    """
    context.log.info("Starting spider: %s", spider_name)
    result = subprocess.run(
        ["scrapy", "crawl", spider_name],
        cwd=str(SCRAPER_DIR),
        capture_output=True,
        text=True,
        check=False,
    )

    # Bubble spider stdout/stderr up to Dagster's run logs.
    if result.stdout:
        context.log.debug("scrapy stdout:\n%s", result.stdout[-2000:])
    if result.stderr:
        context.log.debug("scrapy stderr:\n%s", result.stderr[-2000:])

    if result.returncode != 0:
        raise RuntimeError(f"Spider {spider_name} exited {result.returncode}")

    context.log.info("Spider finished: %s", spider_name)
    return MaterializeResult(metadata={"spider": spider_name})


@asset(group_name="landing", description="Hacker News /jobs metadata + raw detail HTML.")
def hn_landing(context) -> MaterializeResult:
    return _run_spider("hackernews_jobs", context)


@asset(group_name="landing", description="WeWorkRemotely listings metadata + raw detail HTML (via Playwright).")
def wwr_landing(context) -> MaterializeResult:
    return _run_spider("weworkremotely_jobs", context)


@asset(group_name="landing", description="YC Work at a Startup metadata + raw detail HTML (via Playwright).")
def waas_landing(context) -> MaterializeResult:
    return _run_spider("yc_workatastartup_jobs", context)


@asset(
    group_name="processed",
    description="Clean HTML stripped of nav/header/footer; metadata in jobs_processed.",
    # Use deps= (not ins=) because the landing assets produce side effects
    # (writes to Mongo + MinIO), not return values. ins= would make Dagster's
    # I/O manager try to load a non-existent output file and crash with
    # FileNotFoundError.
    deps=[hn_landing, wwr_landing, waas_landing],
)
def processed_jobs(context) -> MaterializeResult:
    """Run the transformer over all landing docs.

    Invoked in-process (no subprocess) because transformer is a plain Python
    function with no Twisted/asyncio reactor of its own.
    """
    sys.path.insert(0, str(PROJECT_ROOT))
    from transform.transformer import main as run_transformer

    context.log.info("Running transformer")
    exit_code = run_transformer([])
    if exit_code != 0:
        raise RuntimeError(f"Transformer exited {exit_code}")
    return MaterializeResult()
