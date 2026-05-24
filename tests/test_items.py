"""Tests for the JobItem schema.

These are intentionally tight — JobItem is the contract every spider
fulfills, so a typo'd field name there would silently break the
landing-zone schema.
"""

import pytest
from compass_scraper.items import JobItem


REQUIRED_FIELDS = {
    "post_id", "source", "title", "url",
    "domain", "company", "scraped_at", "partition_date",
    "file_path", "file_hash", "_html_body",
}


def test_jobitem_exposes_all_required_fields():
    assert set(JobItem.fields.keys()) == REQUIRED_FIELDS


def test_jobitem_accepts_valid_payload():
    item = JobItem(
        post_id="x-123",
        source="weworkremotely",
        title="Engineer",
        url="https://example.com/jobs/123",
        domain="example.com",
        company="Acme",
        scraped_at="2026-05-24T00:00:00+00:00",
        partition_date="2026-05-24",
        file_path="weworkremotely/x-123.html",
        file_hash="deadbeef" * 8,
    )
    assert item["post_id"] == "x-123"
    assert item["source"] == "weworkremotely"


def test_jobitem_rejects_unknown_field():
    with pytest.raises(KeyError):
        item = JobItem()
        item["totally_not_a_real_field"] = "boom"
