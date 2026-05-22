import scrapy
from datetime import datetime, timezone

from compass_scraper.items import JobItem


class WeWorkRemotelyJobsSpider(scrapy.Spider):
    name = "weworkremotely_jobs"
    allowed_domains = ["weworkremotely.com"]
    start_urls = [
        "https://weworkremotely.com/categories/remote-full-stack-programming-jobs",
    ]

    def parse(self, response):
        """Extract listings from a WeWorkRemotely category page.

        Real listings are `li.new-listing-container` without the `listing-ad`
        class. Sponsored ad rows share most of the markup, so the negative
        class selector is what keeps junk out of Mongo.
        """
        scraped_at = datetime.now(timezone.utc).isoformat()

        for li in response.css("li.new-listing-container:not(.listing-ad)"):
            href = li.css("a.listing-link--unlocked::attr(href)").get()
            if not href:
                continue

            # The slug uniquely identifies a posting, e.g.
            # "/remote-jobs/nomad-senior-software-engineer-ii" -> "nomad-senior-software-engineer-ii"
            post_id = href.rsplit("/", 1)[-1]

            item = JobItem()
            item["post_id"] = post_id
            item["source"] = "weworkremotely"
            item["title"] = li.css("span.new-listing__header__title__text::text").get()
            item["url"] = response.urljoin(href)
            item["domain"] = "weworkremotely.com"
            item["company"] = (li.css("p.new-listing__company-name::text").get() or "").strip() or None
            item["scraped_at"] = scraped_at
            yield item
