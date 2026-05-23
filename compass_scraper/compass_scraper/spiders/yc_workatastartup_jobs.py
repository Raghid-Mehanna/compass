import scrapy
from datetime import datetime, timezone

from compass_scraper.items import JobItem


class YcWorkatastartupJobsSpider(scrapy.Spider):
    name = "yc_workatastartup_jobs"
    allowed_domains = ["workatastartup.com"]

    # Start on the software-engineer category. WAAS exposes many categories
    # (designer, science, product-manager, recruiting, ...). Keep scope tight
    # for now; expand later if needed.
    start_urls = ["https://www.workatastartup.com/jobs/l/software-engineer"]

    def start_requests(self):
        # WAAS is a React SPA whose listings are loaded asynchronously via
        # Algolia. The default Playwright "load" event fires before that data
        # arrives, leaving us with an empty shell. Wait for networkidle so the
        # async XHR has time to populate the DOM before we read it.
        for url in self.start_urls:
            yield scrapy.Request(
                url,
                meta={
                    "playwright": True,
                    "playwright_page_goto_kwargs": {"wait_until": "networkidle"},
                },
            )

    def parse(self, response):
        scraped_at = datetime.now(timezone.utc).isoformat()

        for container in response.css("div.cursor-pointer.flex-col"):
            href = container.css('a[target="job"]::attr(href)').get()
            if not href:
                continue

            # href is like "/jobs/86525" — the numeric ID is unique per posting
            # and stable across crawls, so it's our Mongo upsert key.
            post_id = href.rsplit("/", 1)[-1]

            company_raw = container.css('a[target="company"] span.font-bold::text').get()
            # WAAS renders company names with non-breaking spaces (e.g. "Flick\xa0(F25)").
            # Normalize to a regular space so downstream consumers don't see weird chars.
            company = company_raw.replace("\xa0", " ").strip() if company_raw else None

            item = JobItem()
            item["post_id"] = post_id
            item["source"] = "yc_workatastartup"
            item["title"] = container.css('a[target="job"]::text').get()
            item["url"] = response.urljoin(href)
            item["domain"] = "workatastartup.com"
            item["company"] = company
            item["scraped_at"] = scraped_at
            yield item
