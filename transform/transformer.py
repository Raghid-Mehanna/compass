"""
Compass transformation script.

Reads metadata from the landing collection in Mongo, fetches each raw HTML
from the MinIO landing bucket, strips the boilerplate (nav, header, footer,
scripts, styles), and writes:

  - the cleaned HTML to the processed bucket as <source>/<post_id>.html
  - a new metadata record (with the new file_path and recomputed file_hash)
    to the processed collection in Mongo

The landing zone is treated as immutable per the spec: this script never
deletes or updates anything in the landing bucket/collection.

Usage:

    python -m transform.transformer
    python -m transform.transformer --start-date 2026-05-01 --end-date 2026-05-31
    python -m transform.transformer --source weworkremotely

Idempotency: re-running with the same input produces the same output. The
new metadata record is upserted by post_id; if the cleaned hash matches an
existing processed doc, no MinIO write happens.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Iterable

from bs4 import BeautifulSoup
from dotenv import load_dotenv
from pymongo import MongoClient


# Make compass_scraper importable so we reuse MinioStorage + sha256_hex.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scraper"))

from compass_scraper.storage import MinioStorage, sha256_hex  # noqa: E402
from compass_scraper.logging_setup import configure_json_logging  # noqa: E402


logger = logging.getLogger(__name__)


# Tags that are boilerplate across virtually every job listing page — they
# carry no relevant content for the actual job description. Stripping them
# is the "get only the relevant content" part of the Kedra spec.
BOILERPLATE_TAGS = (
    "script", "style", "nav", "header", "footer", "aside",
    "form", "noscript", "svg", "iframe",
)


def clean_html(raw_html: bytes) -> bytes:
    """Strip boilerplate from raw HTML; return cleaned HTML bytes.

    Strategy:
      1. Drop the boilerplate tags listed above outright.
      2. Prefer the <main> or <article> region if present (most modern sites
         use one of these for the primary content).
      3. Fall back to <body> if neither exists.
    """
    soup = BeautifulSoup(raw_html, "lxml")

    for tag_name in BOILERPLATE_TAGS:
        for element in soup.find_all(tag_name):
            element.decompose()

    main = soup.find("main") or soup.find("article") or soup.find("body")
    if main is None:
        # Pathological page (no body) — return whatever is left after the
        # boilerplate pass.
        cleaned = soup
    else:
        cleaned = main

    return cleaned.encode("utf-8")


def iter_landing_docs(
    collection,
    start_date: str | None,
    end_date: str | None,
    source: str | None,
) -> Iterable[dict]:
    """Yield landing-zone Mongo docs matching the filters."""
    query: dict = {"file_path": {"$exists": True, "$ne": None}}
    if source:
        query["source"] = source
    if start_date or end_date:
        date_filter: dict = {}
        if start_date:
            date_filter["$gte"] = start_date
        if end_date:
            date_filter["$lte"] = end_date
        query["partition_date"] = date_filter

    return collection.find(query)


def transform_one(
    doc: dict,
    storage: MinioStorage,
    landing_bucket: str,
    processed_bucket: str,
    processed_collection,
) -> dict:
    """Transform a single landing-zone doc.

    Returns a stats dict: {"action": "uploaded"|"skipped_unchanged"|"error", ...}.
    """
    post_id = doc["post_id"]
    source = doc["source"]
    landing_path = doc["file_path"]
    processed_path = f"{source}/{post_id}.html"

    try:
        raw_html = storage.get_bytes(landing_bucket, landing_path)
    except Exception as exc:
        logger.error(
            "Failed to read landing file: source=%s post_id=%s path=%s err=%s",
            source, post_id, landing_path, exc,
        )
        return {"action": "error", "reason": "landing_read"}

    cleaned = clean_html(raw_html)
    new_hash = sha256_hex(cleaned)

    existing = processed_collection.find_one(
        {"post_id": post_id}, projection={"file_hash": 1}
    )
    if existing and existing.get("file_hash") == new_hash:
        logger.debug("Unchanged after cleaning, skipping: %s/%s", source, post_id)
        return {"action": "skipped_unchanged"}

    storage.put_bytes(
        bucket=processed_bucket,
        object_name=processed_path,
        data=cleaned,
        content_type="text/html",
    )

    # Build the processed metadata: same fields as landing, but file_path /
    # file_hash now refer to the cleaned object in the processed bucket.
    processed_doc = {
        k: v for k, v in doc.items()
        if k not in {"_id", "file_path", "file_hash"}
    }
    processed_doc["file_path"] = processed_path
    processed_doc["file_hash"] = new_hash
    processed_doc["landing_path"] = landing_path  # crumb back to raw source

    processed_collection.update_one(
        {"post_id": post_id},
        {"$set": processed_doc},
        upsert=True,
    )
    logger.info(
        "Transformed: source=%s post_id=%s bytes_in=%d bytes_out=%d",
        source, post_id, len(raw_html), len(cleaned),
    )
    return {"action": "uploaded"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compass transformer")
    parser.add_argument("--start-date", help="Inclusive lower bound, YYYY-MM-DD")
    parser.add_argument("--end-date", help="Inclusive upper bound, YYYY-MM-DD")
    parser.add_argument("--source", help="Limit to a single source (e.g. weworkremotely)")
    args = parser.parse_args(argv)

    load_dotenv(PROJECT_ROOT / ".env")
    configure_json_logging(level=os.getenv("LOG_LEVEL", "INFO"))

    mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    mongo_db = os.getenv("MONGO_DB", "compass")
    landing_collection_name = os.getenv("MONGO_COLLECTION", "jobs")
    processed_collection_name = os.getenv("MONGO_COLLECTION_PROCESSED", "jobs_processed")
    landing_bucket = os.getenv("MINIO_BUCKET_LANDING", "compass-landing")
    processed_bucket = os.getenv("MINIO_BUCKET_PROCESSED", "compass-processed")

    storage = MinioStorage(
        endpoint=os.getenv("MINIO_ENDPOINT", "localhost:9000"),
        access_key=os.getenv("MINIO_ACCESS_KEY", "minio"),
        secret_key=os.getenv("MINIO_SECRET_KEY", "minio12345"),
        secure=os.getenv("MINIO_SECURE", "false").lower() == "true",
    )
    storage.ensure_bucket(processed_bucket)

    client = MongoClient(mongo_uri)
    db = client[mongo_db]
    landing = db[landing_collection_name]
    processed = db[processed_collection_name]

    counts = {"uploaded": 0, "skipped_unchanged": 0, "error": 0}
    docs = list(iter_landing_docs(landing, args.start_date, args.end_date, args.source))
    logger.info(
        "Transformer starting: docs_to_process=%d source=%s start=%s end=%s",
        len(docs), args.source or "*", args.start_date or "*", args.end_date or "*",
    )

    for doc in docs:
        result = transform_one(
            doc=doc,
            storage=storage,
            landing_bucket=landing_bucket,
            processed_bucket=processed_bucket,
            processed_collection=processed,
        )
        counts[result["action"]] = counts.get(result["action"], 0) + 1

    logger.info(
        "Transformer finished: uploaded=%d skipped_unchanged=%d errors=%d",
        counts["uploaded"], counts["skipped_unchanged"], counts["error"],
    )
    client.close()
    return 0 if counts["error"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
