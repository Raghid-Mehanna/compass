import scrapy
from datetime import datetime, timezone

from compass_scraper.items import JobItem


class YcWorkatastartupJobsSpider(scrapy.Spider):
    name = "yc_workatastartup_jobs"
    allowed_domains = ["workatastartup.com"]
    start_urls = ["https://www.workatastartup.com/jobs/l/software-engineer"]

    # Playwright meta used for BOTH the index page (Algolia loads listings
    # async) and the per-job detail pages (also React-rendered).
    _PLAYWRIGHT_META = {
        "playwright": True,
        "playwright_page_goto_kwargs": {"wait_until": "networkidle"},
    }

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url, meta=self._PLAYWRIGHT_META)

    def parse(self, response):
        scraped_at = datetime.now(timezone.utc).isoformat()
        partition_date = datetime.now(timezone.utc).date().isoformat()

        for container in response.css("div.cursor-pointer.flex-col"):
            href = container.css('a[target="job"]::attr(href)').get()
            if not href:
                continue

            post_id = href.rsplit("/", 1)[-1]
            company_raw = container.css('a[target="company"] span.font-bold::text').get()
            company = company_raw.replace("\xa0", " ").strip() if company_raw else None
            title = container.css('a[target="job"]::text').get()
            absolute_url = response.urljoin(href)

            yield scrapy.Request(
                absolute_url,
                callback=self.parse_detail,
                meta=self._PLAYWRIGHT_META,
                cb_kwargs={
                    "metadata": {
                        "post_id": post_id,
                        "source": "yc_workatastartup",
                        "title": title,
                        "url": absolute_url,
                        "domain": "workatastartup.com",
                        "company": company,
                        "scraped_at": scraped_at,
                        "partition_date": partition_date,
                    }
                },
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
