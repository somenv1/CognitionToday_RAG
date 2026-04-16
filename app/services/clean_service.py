from dataclasses import dataclass
from hashlib import sha256

from bs4 import BeautifulSoup
import trafilatura


@dataclass
class CleanedDocument:
    canonical_url: str
    title: str
    cleaned_markdown: str
    metadata: dict
    content_hash: str
    raw_html: str


class CleanService:
    def clean(self, *, url: str, html: str) -> CleanedDocument:
        soup = BeautifulSoup(html, "html.parser")
        title_tag = soup.find("title")
        page_title = title_tag.get_text(strip=True) if title_tag else url

        extracted = trafilatura.extract(
            html,
            url=url,
            include_comments=False,
            include_images=False,
            include_tables=True,
            output_format="markdown",
            with_metadata=False,
        )

        if not extracted:
            raise ValueError(f"Unable to extract main article content from {url}")

        cleaned_markdown = f"# {page_title}\n\n{extracted.strip()}".strip()
        content_hash = sha256(cleaned_markdown.encode("utf-8")).hexdigest()

        title_line = page_title
        metadata = {
            "source_url": url,
            "content_length": len(cleaned_markdown),
        }

        return CleanedDocument(
            canonical_url=url,
            title=title_line,
            cleaned_markdown=cleaned_markdown,
            metadata=metadata,
            content_hash=content_hash,
            raw_html=html,
        )
