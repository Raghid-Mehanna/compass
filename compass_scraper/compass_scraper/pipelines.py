"""
MongoDB pipeline for Compass.

Each item yielded by a spider passes through here on its way out.
We upsert by post_id, which makes the pipeline idempotent: re-running
a spider updates existing jobs rather than creating duplicates.
"""

import logging
from itemadapter import ItemAdapter
from pymongo import MongoClient, UpdateOne
from pymongo.errors import PyMongoError

logger = logging.getLogger(__name__)


class MongoPipeline:
    """Writes scraped items to MongoDB, upserting by post_id."""

    def __init__(self, mongo_uri, mongo_db, mongo_collection):
        self.mongo_uri = mongo_uri
        self.mongo_db = mongo_db
        self.mongo_collection = mongo_collection
        self.client = None
        self.db = None

    @classmethod
    def from_crawler(cls, crawler):
        """Scrapy calls this to build the pipeline. We pull config from settings."""
        return cls(
            mongo_uri=crawler.settings.get("MONGO_URI", "mongodb://localhost:27017"),
            mongo_db=crawler.settings.get("MONGO_DB", "compass"),
            mongo_collection=crawler.settings.get("MONGO_COLLECTION", "jobs"),
        )

    def open_spider(self, spider):
        """Called once when the spider starts. Open the connection."""
        self.client = MongoClient(self.mongo_uri)
        self.db = self.client[self.mongo_db]
        logger.info(
            "MongoPipeline connected to %s, db=%s, collection=%s",
            self.mongo_uri, self.mongo_db, self.mongo_collection,
        )

    def close_spider(self, spider):
        """Called once when the spider finishes. Close the connection."""
        if self.client is not None:
            self.client.close()
            logger.info("MongoPipeline connection closed")

    def process_item(self, item, spider):
        """Called once per item. Upsert into Mongo by post_id."""
        adapter = ItemAdapter(item)
        data = adapter.asdict()

        post_id = data.get("post_id")
        if not post_id:
            logger.warning("Skipping item without post_id: %s", data.get("title"))
            return item

        try:
            result = self.db[self.mongo_collection].update_one(
                {"post_id": post_id},
                {"$set": data},
                upsert=True,
            )
            if result.upserted_id is not None:
                logger.debug("Inserted new job: %s", data.get("title"))
            elif result.modified_count:
                logger.debug("Updated existing job: %s", data.get("title"))
            else:
                logger.debug("No change for job: %s", data.get("title"))
        except PyMongoError as e:
            logger.error("Mongo error for %s: %s", post_id, e)

        return item