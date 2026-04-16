from __future__ import annotations

import argparse
import importlib.util
import sys
from html.parser import HTMLParser
from pathlib import Path

import requests


DEFAULT_POSTS_URL = "https://cognitiontoday.com/wp-json/wp/v2/posts"
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/javascript, */*; q=0.01",
}


def load_chunk_service():
    module_path = Path(__file__).resolve().parents[1] / "app" / "services" / "chunk_service.py"
    spec = importlib.util.spec_from_file_location("chunk_service", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.ChunkService


class FragmentToMarkdownParser(HTMLParser):
    BLOCK_TAGS = {"p", "li", "blockquote", "pre"}
    HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[str] = []
        self.current_text: list[str] = []
        self.current_tag: str | None = None

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in self.HEADING_TAGS or tag in self.BLOCK_TAGS:
            self._flush_current()
            self.current_tag = tag
        elif tag == "br":
            self.current_text.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag == self.current_tag:
            self._flush_current()
            self.current_tag = None

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if text:
            self.current_text.append(text)

    def to_markdown(self) -> str:
        self._flush_current()
        return "\n\n".join(block for block in self.blocks if block.strip())

    def _flush_current(self) -> None:
        if not self.current_text:
            return

        text = " ".join(part.strip() for part in self.current_text if part.strip()).strip()
        self.current_text = []
        if not text:
            return

        if self.current_tag in self.HEADING_TAGS:
            level = int(self.current_tag[1])
            self.blocks.append(f"{'#' * level} {text}")
        elif self.current_tag == "li":
            self.blocks.append(f"- {text}")
        elif self.current_tag == "blockquote":
            self.blocks.append(f"> {text}")
        else:
            self.blocks.append(text)


def html_fragment_to_markdown(title: str, rendered_html: str) -> str:
    parser = FragmentToMarkdownParser()
    parser.feed(rendered_html)
    body = parser.to_markdown().strip()
    if body:
        return f"# {title}\n\n{body}"
    return f"# {title}"


def fetch_posts(posts_url: str, limit: int) -> list[dict]:
    session = requests.Session()
    session.headers.update(REQUEST_HEADERS)

    remaining = limit
    page = 1
    posts: list[dict] = []

    while remaining > 0:
        per_page = min(100, remaining)
        response = session.get(
            posts_url,
            params={"per_page": per_page, "page": page},
            timeout=30,
        )
        response.raise_for_status()
        page_posts = response.json()
        if not isinstance(page_posts, list) or not page_posts:
            break

        posts.extend(page_posts)
        remaining -= len(page_posts)
        page += 1

        if len(page_posts) < per_page:
            break

    return posts[:limit]


def build_report(posts: list[dict], chunk_service) -> list[dict]:
    report: list[dict] = []

    for post in posts:
        title = post.get("title", {}).get("rendered", "Untitled").strip() or "Untitled"
        rendered_html = post.get("content", {}).get("rendered", "")
        markdown = html_fragment_to_markdown(title, rendered_html)
        chunks = chunk_service.chunk_markdown(markdown)

        report.append(
            {
                "title": title,
                "slug": post.get("slug"),
                "url": post.get("link"),
                "chunk_count": len(chunks),
                "avg_tokens": round(
                    sum(chunk.token_count for chunk in chunks) / len(chunks),
                    1,
                )
                if chunks
                else 0,
                "max_tokens": max((chunk.token_count for chunk in chunks), default=0),
                "headings": [" > ".join(chunk.heading_path) for chunk in chunks[:5]],
            }
        )

    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Test chunking against WordPress posts API.")
    parser.add_argument("--posts-url", default=DEFAULT_POSTS_URL)
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--target-tokens", type=int, default=420)
    parser.add_argument("--max-tokens", type=int, default=600)
    parser.add_argument("--overlap-tokens", type=int, default=60)
    args = parser.parse_args()

    ChunkService = load_chunk_service()
    chunk_service = ChunkService(
        target_tokens=args.target_tokens,
        max_tokens=args.max_tokens,
        overlap_tokens=args.overlap_tokens,
    )

    posts = fetch_posts(args.posts_url, args.limit)
    report = build_report(posts, chunk_service)

    print(f"Fetched posts: {len(posts)}")
    print(
        "Chunking config: "
        f"target={args.target_tokens}, max={args.max_tokens}, overlap={args.overlap_tokens}"
    )
    print()

    for item in report:
        print(f"Title: {item['title']}")
        print(f"Slug: {item['slug']}")
        print(f"URL: {item['url']}")
        print(
            "Chunks: "
            f"{item['chunk_count']} | avg tokens: {item['avg_tokens']} | max tokens: {item['max_tokens']}"
        )
        print("Sample heading paths:")
        for heading in item["headings"]:
            print(f"  - {heading}")
        print()


if __name__ == "__main__":
    main()
