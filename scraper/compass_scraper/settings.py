"""
Scrapy settings for compass_scraper.

All tunables — Mongo connection, user-agent, throttle, log level — are loaded
from environment variables (see .env.example). Hardcoded values are avoided
so the same code is portable between local dev and CI/prod.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env if present (project root is two levels up from this file).
PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")


# --- Structured (JSON) logging ---
# Install the JSON handler immediately, before any Scrapy/Twisted/library code
# has a chance to log. LOG_ENABLED=False (below) tells Scrapy not to install
# its own plain-text handler that would otherwise compete with ours.
from compass_scraper.logging_setup import configure_json_logging  # noqa: E402

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_ENABLED = False  # we install our own handler in logging_setup
configure_json_logging(level=LOG_LEVEL)


BOT_NAME = "compass_scraper"

SPIDER_MODULES = ["compass_scraper.spiders"]
NEWSPIDER_MODULE = "compass_scraper.spiders"

ADDONS = {}


# --- Scraping behavior (env-driven, with defensible defaults) ---
USER_AGENT = os.getenv(
    "USER_AGENT",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
)
ROBOTSTXT_OBEY = True
CONCURRENT_REQUESTS_PER_DOMAIN = int(os.getenv("CONCURRENT_REQUESTS_PER_DOMAIN", "1"))
DOWNLOAD_DELAY = float(os.getenv("DOWNLOAD_DELAY", "1"))

# Browser-realistic headers. WWR (Cloudflare-protected) 403s Scrapy's default
# Accept-* headers because their compact form (e.g. Accept: */*) doesn't match
# what real Chrome sends. These values are taken straight from a live Chrome
# request to match the bot-detection fingerprint.
DEFAULT_REQUEST_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",  # no brotli — Scrapy decodes gzip/deflate natively
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-User": "?1",
    "Sec-Fetch-Dest": "document",
}

# Retry on 403/429/5xx so a single transient block doesn't kill the crawl.
RETRY_ENABLED = True
RETRY_TIMES = 2
RETRY_HTTP_CODES = [403, 429, 500, 502, 503, 504]


# --- Pipelines ---
# StoragePipeline runs first (uploads HTML + computes hash), then MongoPipeline
# upserts the metadata. Lower number = earlier in the chain.
ITEM_PIPELINES = {
    "compass_scraper.pipelines.StoragePipeline": 200,
    "compass_scraper.pipelines.MongoPipeline": 300,
}


# --- MongoDB (env-driven) ---
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB", "compass")
MONGO_COLLECTION = os.getenv("MONGO_COLLECTION", "jobs")
MONGO_COLLECTION_PROCESSED = os.getenv("MONGO_COLLECTION_PROCESSED", "jobs_processed")


# --- MinIO (env-driven) ---
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minio")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minio12345")
MINIO_SECURE = os.getenv("MINIO_SECURE", "false").lower() == "true"
MINIO_BUCKET_LANDING = os.getenv("MINIO_BUCKET_LANDING", "compass-landing")
MINIO_BUCKET_PROCESSED = os.getenv("MINIO_BUCKET_PROCESSED", "compass-processed")


# --- Encoding ---
FEED_EXPORT_ENCODING = "utf-8"


# --- Playwright (for JS-rendered sources, e.g. YC Work at a Startup) ---
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"
DOWNLOAD_HANDLERS = {
    "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
    "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
}
PLAYWRIGHT_BROWSER_TYPE = "chromium"
