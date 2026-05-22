"""
Item definitions for Compass.

Each scraped record from any source (HN, YC, Wellfound, etc.) MUST conform
to JobItem. This gives us one schema across sources, which makes the
MongoPipeline's upsert-by-post_id logic safe and the Day-6+ analytics
trivial.
"""

import scrapy


class JobItem(scrapy.Item):
    """A single scraped job posting.

    Required fields: post_id, title, url, source, scraped_at.
    Optional: domain (not all sources expose it cleanly).
    """

    # Identity
    post_id = scrapy.Field()        # source-specific unique id
    source = scrapy.Field()         # e.g. "hn_whoshiring", "yc_workatastartup"

    # Content
    title = scrapy.Field()
    url = scrapy.Field()
    domain = scrapy.Field()         # parsed from URL; may be None

    # Metadata
    scraped_at = scrapy.Field()     # ISO 8601 UTC timestamp