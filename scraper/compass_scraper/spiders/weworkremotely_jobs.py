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
        scraped_at = datetime.now(timezone.utc).isoformat()
        partition_date = datetime.now(timezone.utc).date().isoformat()

        for li in response.css("li.new-listing-container:not(.listing-ad)"):
            href = li.css("a.listing-link--unlocked::attr(href)").get()
            if not href:
                continue

            post_id = href.rsplit("/", 1)[-1]
            company_raw = li.css("p.new-listing__company-name::text").get()
            company = company_raw.strip() if company_raw else None
            title = li.css("span.new-listing__header__title__text::text").get()
            absolute_url = response.urljoin(href)

            yield scrapy.Request(
                absolute_url,
                callback=self.parse_detail,
                # WWR is behind Cloudflare with TLS fingerprinting that 403s
                # any standard HTTP client (Scrapy/curl-without-impersonation).
                # A real browser passes through, so route detail requests via
                # Playwright. The index page itself loads fine without it.
                meta={"playwright": True},
                cb_kwargs={
                    "metadata": {
                        "post_id": post_id,
                        "source": "weworkremotely",
                        "title": title,
                        "url": absolute_url,
                        "domain": "weworkremotely.com",
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
