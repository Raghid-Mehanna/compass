"""
Item pipelines for Compass.

Pipeline order matters. Each item flows through:

  StoragePipeline (priority 200)
    - Reads raw HTML bytes from item["_html_body"]
    - Computes SHA256
    - Skips upload if a Mongo doc already exists with the same hash
      (the "do not re-upload unchanged files" idempotency requirement)
    - Otherwise uploads to MinIO at <bucket>/<source>/<post_id>.html
    - Annotates item with file_path + file_hash

  MongoPipeline (priority 300)
    - Strips the internal _html_body field (it doesn't belong in Mongo)
    - Upserts the rest by post_id
"""

import logging

from itemadapter import ItemAdapter
from pymongo import MongoClient
from pymongo.errors import PyMongoError

from compass_scraper.storage import MinioStorage, sha256_hex


logger = logging.getLogger(__name__)


class StoragePipeline:
    """Uploads each item's raw HTML body to MinIO and records path + hash.

    Sits before MongoPipeline so that by the time Mongo writes the doc,
    `file_path` and `file_hash` fields are already populated.
    """

    def __init__(
        self,
        mongo_uri: str,
        mongo_db: str,
        mongo_collection: str,
        minio_endpoint: str,
        minio_access_key: str,
        minio_secret_key: str,
        minio_secure: bool,
        minio_bucket_landing: str,
    ) -> None:
        self.mongo_uri = mongo_uri
        self.mongo_db = mongo_db
        self.mongo_collection = mongo_collection
        self.minio_endpoint = minio_endpoint
        self.minio_access_key = minio_access_key
        self.minio_secret_key = minio_secret_key
        self.minio_secure = minio_secure
        self.minio_bucket_landing = minio_bucket_landing

        self._mongo_client: MongoClient | None = None
        self._storage: MinioStorage | None = None

    @classmethod
    def from_crawler(cls, crawler):
        s = crawler.settings
        return cls(
            mongo_uri=s.get("MONGO_URI"),
            mongo_db=s.get("MONGO_DB"),
            mongo_collection=s.get("MONGO_COLLECTION"),
            minio_endpoint=s.get("MINIO_ENDPOINT"),
            minio_access_key=s.get("MINIO_ACCESS_KEY"),
            minio_secret_key=s.get("MINIO_SECRET_KEY"),
            minio_secure=s.getbool("MINIO_SECURE"),
            minio_bucket_landing=s.get("MINIO_BUCKET_LANDING"),
        )

    def open_spider(self, spider):
        self._mongo_client = MongoClient(self.mongo_uri)
        self._storage = MinioStorage(
            endpoint=self.minio_endpoint,
            access_key=self.minio_access_key,
            secret_key=self.minio_secret_key,
            secure=self.minio_secure,
        )
        self._storage.ensure_bucket(self.minio_bucket_landing)
        logger.info(
            "StoragePipeline ready: minio=%s bucket=%s",
            self.minio_endpoint, self.minio_bucket_landing,
        )

    def close_spider(self, spider):
        if self._mongo_client is not None:
            self._mongo_client.close()

    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        body: bytes | None = adapter.get("_html_body")
        post_id = adapter.get("post_id")
        source = adapter.get("source")

        if not body or not post_id or not source:
            # Either the spider didn't fetch a detail page or the item is
            # malformed; skip storage and let MongoPipeline handle it.
            return item

        new_hash = sha256_hex(body)
        object_name = f"{source}/{post_id}.html"

        # Idempotency: if Mongo already has this post_id with this hash,
        # the file is unchanged — skip the MinIO upload (saves bytes + API
        # calls when re-running on the same day).
        existing = self._mongo_client[self.mongo_db][self.mongo_collection].find_one(
            {"post_id": post_id}, projection={"file_hash": 1}
        )
        if existing and existing.get("file_hash") == new_hash:
            logger.debug("Unchanged file, skipping upload: %s", object_name)
        else:
            self._storage.put_bytes(
                bucket=self.minio_bucket_landing,
                object_name=object_name,
                data=body,
                content_type="text/html",
            )
            logger.info(
                "Uploaded to MinIO: bucket=%s object=%s bytes=%d",
                self.minio_bucket_landing, object_name, len(body),
            )

        adapter["file_path"] = object_name
        adapter["file_hash"] = new_hash
        return item


class MongoPipeline:
    """Writes scraped items to MongoDB, upserting by post_id.

    Runs after StoragePipeline so the items already carry file_path + file_hash.
    """

    def __init__(self, mongo_uri: str, mongo_db: str, mongo_collection: str) -> None:
        self.mongo_uri = mongo_uri
        self.mongo_db = mongo_db
        self.mongo_collection = mongo_collection
        self.client: MongoClient | None = None

    @classmethod
    def from_crawler(cls, crawler):
        s = crawler.settings
        return cls(
            mongo_uri=s.get("MONGO_URI"),
            mongo_db=s.get("MONGO_DB"),
            mongo_collection=s.get("MONGO_COLLECTION"),
        )

    def open_spider(self, spider):
        self.client = MongoClient(self.mongo_uri)
        logger.info(
            "MongoPipeline connected to %s, db=%s, collection=%s",
            self.mongo_uri, self.mongo_db, self.mongo_collection,
        )

    def close_spider(self, spider):
        if self.client is not None:
            self.client.close()
            logger.info("MongoPipeline connection closed")

    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        data = adapter.asdict()

        # Strip the internal raw-bytes field — it has served its purpose in
        # the storage step and has no business in Mongo.
        data.pop("_html_body", None)

        post_id = data.get("post_id")
        if not post_id:
            logger.warning("Skipping item without post_id: %s", data.get("title"))
            return item

        try:
            result = self.client[self.mongo_db][self.mongo_collection].update_one(
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
