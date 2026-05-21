import scrapy


class HackernewsJobsSpider(scrapy.Spider):
    name = "hackernews_jobs"
    allowed_domains = ["news.ycombinator.com"]
    start_urls = ["https://news.ycombinator.com/jobs"]

    def parse(self, response):
        """Extract job listings from the Hacker News /jobs page."""
        for row in response.css("tr.athing"):
            yield {
                "post_id": row.css("::attr(id)").get(),
                "title": row.css(".titleline a::text").get(),
                "url": row.css(".titleline a::attr(href)").get(),
                "domain": row.css(".sitestr::text").get(),
            }