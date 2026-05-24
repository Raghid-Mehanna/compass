import scrapy
from datetime import datetime, timezone

from compass_scraper.items import JobItem


class HackernewsJobsSpider(scrapy.Spider):
    name = "hackernews_jobs"
    # No allowed_domains: HN's /jobs list links out to each employer's own
    # site (varied domains), and the OffsiteMiddleware would block them.
    start_urls = ["https://news.ycombinator.com/jobs"]

    def parse(self, response):
        """Scrape the HN /jobs index for one row per listing, then follow the
        external link to fetch and store the detail page HTML."""
        scraped_at = datetime.now(timezone.utc).isoformat()
        partition_date = datetime.now(timezone.utc).date().isoformat()

        for row in response.css("tr.athing"):
            post_id = row.css("::attr(id)").get()
            title = row.css(".titleline a::text").get()
            url = row.css(".titleline a::attr(href)").get()
            domain = row.css(".sitestr::text").get()

            if not post_id or not url:
                continue

            # Some HN listings have relative URLs (e.g. "item?id=48225852"
            # pointing back to an HN thread). urljoin makes them absolute.
            absolute_url = response.urljoin(url)

            yield scrapy.Request(
                absolute_url,
                callback=self.parse_detail,
                # Pass the metadata extracted from the index page into the
                # detail-page callback via request meta. This decouples the
                # two parses cleanly.
                cb_kwargs={
                    "metadata": {
                        "post_id": post_id,
                        "source": "hn_whoshiring",
                        "title": title,
                        "url": absolute_url,
                        "domain": domain,
                        "company": None,
                        "scraped_at": scraped_at,
                        "partition_date": partition_date,
                    }
                },
                # If the external URL 404s or times out, log and move on
                # rather than crashing the whole crawl.
                errback=self.detail_failed,
            )

    def parse_detail(self, response, metadata):
        item = JobItem(**metadata)
        item["_html_body"] = response.body
        yield item

    def detail_failed(self, failure):
        self.logger.warning(
            "Detail-page fetch failed: %s — %s",
            failure.request.url, failure.value,
        )
