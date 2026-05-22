import scrapy
from datetime import datetime, timezone

from compass_scraper.items import JobItem


class HackernewsJobsSpider(scrapy.Spider):
    name = "hackernews_jobs"
    allowed_domains = ["news.ycombinator.com"]
    start_urls = ["https://news.ycombinator.com/jobs"]

    def parse(self, response):
        """Extract job listings from the Hacker News /jobs page."""
        scraped_at = datetime.now(timezone.utc).isoformat()

        for row in response.css("tr.athing"):
            item = JobItem()
            item["post_id"] = row.css("::attr(id)").get()
            item["title"] = row.css(".titleline a::text").get()
            item["url"] = row.css(".titleline a::attr(href)").get()
            item["domain"] = row.css(".sitestr::text").get()
            item["source"] = "hn_whoshiring"
            item["scraped_at"] = scraped_at
            yield item