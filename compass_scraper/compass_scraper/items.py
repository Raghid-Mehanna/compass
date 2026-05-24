"""
Item definitions for Compass.

Each scraped record from any source (HN, YC, Wellfound, etc.) MUST conform
to JobItem. This gives us one schema across sources, which makes the
MongoPipeline's upsert-by-post_id logic safe and the analytics trivial.
"""

import scrapy


class JobItem(scrapy.Item):
    """A single scraped job posting.

    Required fields: post_id, title, url, source, scraped_at.
    Optional: domain (not all sources expose it cleanly), company.
    Storage-pipeline fills: file_path, file_hash.
    Internal (stripped before Mongo write): _html_body.
    """

    # Identity
    post_id = scrapy.Field()        # source-specific unique id
    source = scrapy.Field()         # e.g. "hn_whoshiring", "yc_workatastartup"

    # Content
    title = scrapy.Field()
    url = scrapy.Field()
    domain = scrapy.Field()         # parsed from URL; may be None
    company = scrapy.Field()        # populated where the source exposes it

    # Metadata
    scraped_at = scrapy.Field()     # ISO 8601 UTC timestamp
    partition_date = scrapy.Field() # YYYY-MM-DD date the crawl ran (job sites
                                    # don't expose date filters; we partition
                                    # by scrape date — see ARCHITECTURE.md)

    # File reference (set by StoragePipeline after upload to MinIO)
    file_path = scrapy.Field()      # e.g. "weworkremotely/nomad-...html"
    file_hash = scrapy.Field()      # SHA256 hex of the raw HTML

    # Internal: raw HTML bytes of the detail page. Spiders set this; the
    # StoragePipeline reads and uploads, then MongoPipeline strips it before
    # writing the doc to Mongo. Never persisted.
    _html_body = scrapy.Field()
