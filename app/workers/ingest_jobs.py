from __future__ import annotations

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

# URL patterns to skip during sitemap discovery.
# These are typical WordPress taxonomy / structural pages that aren't articles.
NON_ARTICLE_PATTERNS = (
    "/category/",
    "/tag/",
    "/author/",
    "/feed/",
    "/wp-content/",
    "/wp-admin/",
    "/wp-json/",
    "/page/",
    "/comments/",
    "/web-stories/",
    "/web-story/",
    "?web-story",
    "web-story-page=",
)

def _ingest_document(url: str) -> str:
    """RQ job: ingest a single article URL. Returns the document id."""
    from app import create_app
    app = create_app()
    with app.app_context():
        service = IngestService(app.config)
        document = service.ingest_url(url)
        return document.id


def _fetch_sitemap_urls(sitemap_url: str, visited: set[str] | None = None) -> list[str]:
    """
    Recursively fetch sitemap(s) and return article URLs.

    Handles both sitemap index files (<sitemapindex> with child <sitemap> entries)
    and regular sitemap files (<urlset> with <url> entries).
    """
    if visited is None:
        visited = set()
    if sitemap_url in visited:
        return []
    visited.add(sitemap_url)

    response = requests.get(sitemap_url, headers=REQUEST_HEADERS, timeout=20)
    response.raise_for_status()

    root = ElementTree.fromstring(response.content)
    tag = root.tag.lower()

    # Is this a sitemap index (points to other sitemaps)?
    if tag.endswith("sitemapindex"):
        child_sitemap_urls = [
            node.text.strip()
            for node in root.findall(".//{*}sitemap/{*}loc")
            if node.text
        ]
        collected: list[str] = []
        for child_url in child_sitemap_urls:
            collected.extend(_fetch_sitemap_urls(child_url, visited))
        return collected

    # Otherwise, it's a regular sitemap with article URLs.
    return [
        node.text.strip()
        for node in root.findall(".//{*}url/{*}loc")
        if node.text
    ]


def _is_article_url(url: str) -> bool:
    """Heuristic filter — skip obvious non-article URLs."""
    lowered = url.lower().rstrip("/")
    if lowered.endswith(".xml"):
        return False
    # Filter out bare domains (homepage like https://cognitiontoday.com)
    # An article URL always has a path beyond the domain.
    parts = lowered.split("/")
    # After .split("/"), a bare URL like "https://cognitiontoday.com" has 3 parts:
    # ["https:", "", "cognitiontoday.com"] — no path segment.
    # A real article URL has 4+ parts.
    if len(parts) < 4:
        return False
    for pattern in NON_ARTICLE_PATTERNS:
        if pattern in lowered:
            return False
    return True

def _sync_sitemap(sitemap_url: str) -> dict:
    """
    RQ job: walk the sitemap tree, filter non-article URLs,
    and enqueue a separate ingestion job per article.

    Runs fast (seconds) and returns a summary dict.
    Actual article processing happens in parallel by other worker jobs.
    """
    from app import create_app
    app = create_app()
    with app.app_context():
        all_urls = _fetch_sitemap_urls(sitemap_url)
        article_urls = [url for url in all_urls if _is_article_url(url)]

        if extensions.rq_queue is None:
            raise RuntimeError("RQ queue is not initialized")

        enqueued = 0
        skipped = len(all_urls) - len(article_urls)
        for url in article_urls:
            extensions.rq_queue.enqueue(_ingest_document, url)
            enqueued += 1

        app.logger.info(
            "Sitemap sync complete: enqueued=%d skipped=%d total_discovered=%d",
            enqueued, skipped, len(all_urls),
        )
        return {
            "enqueued": enqueued,
            "skipped": skipped,
            "total_discovered": len(all_urls),
        }


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
