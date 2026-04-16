from xml.etree import ElementTree

import requests

from app import extensions
from app.services.ingest_service import IngestService


REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/javascript, */*; q=0.01",
}


def _ingest_document(url: str) -> str:
    from app import create_app

    app = create_app()
    with app.app_context():
        service = IngestService(app.config)
        document = service.ingest_url(url)
        return document.id


def _sync_sitemap(sitemap_url: str) -> int:
    from app import create_app

    app = create_app()
    with app.app_context():
        response = requests.get(sitemap_url, headers=REQUEST_HEADERS, timeout=20)
        response.raise_for_status()
        root = ElementTree.fromstring(response.content)

        urls = [
            node.text
            for node in root.findall(".//{*}loc")
            if node.text
        ]

        service = IngestService(app.config)
        ingested = 0
        for url in urls:
            try:
                service.ingest_url(url)
                ingested += 1
            except Exception:
                app.logger.exception("Failed to ingest %s", url)

        return ingested


def enqueue_document_ingestion(config, url: str):
    if extensions.rq_queue is None:
        raise RuntimeError("RQ queue is not initialized")

    return extensions.rq_queue.enqueue(_ingest_document, url)


def enqueue_sitemap_sync(config):
    sitemap_url = config.get("BLOG_SITEMAP_URL")
    if not sitemap_url:
        raise RuntimeError("BLOG_SITEMAP_URL is required for sitemap sync")
    if extensions.rq_queue is None:
        raise RuntimeError("RQ queue is not initialized")

    return extensions.rq_queue.enqueue(_sync_sitemap, sitemap_url)
