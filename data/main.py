import logging
import os

import aggregate
import scrape
import upload

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s:%(message)s")


def run():
    try:
        scrape.scrape()
        aggregate.aggregate()
    except:
        logging.exception("failed to update data")
        raise

    # uploading to S3 is only for the hosted ffdraft.app. Skip it when no bucket is configured.
    if os.environ.get("S3_BUCKET") and os.environ.get("AWS_ACCESS_KEY_ID"):
        upload.upload()
    else:
        logging.info("S3_BUCKET not set, skipping upload")


if __name__ == "__main__":
    run()
