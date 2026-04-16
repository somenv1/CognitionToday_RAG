from __future__ import annotations

import re
from dataclasses import dataclass


HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.*)$")
SENTENCE_BOUNDARY_PATTERN = re.compile(r"(?<=[.!?])\s+")


@dataclass
class ChunkDraft:
    chunk_index: int
    heading_path: list[str]
    text: str
    embedding_text: str
    token_count: int
    word_count: int
    paragraph_count: int
    prev_chunk_index: int | None
    next_chunk_index: int | None


@dataclass
class Section:
    heading_path: list[str]
    paragraphs: list[str]


class ChunkService:
    def __init__(
        self,
        target_tokens: int = 420,
        max_tokens: int = 600,
        overlap_tokens: int = 60,
    ) -> None:
        self.target_tokens = target_tokens
        self.max_tokens = max_tokens
        self.overlap_tokens = overlap_tokens

    def chunk_markdown(self, markdown_text: str) -> list[ChunkDraft]:
        sections = self._extract_sections(markdown_text)
        chunk_buffer: list[dict] = []

        for section in sections:
            section_paragraphs = self._normalize_paragraphs(section.paragraphs)
            if not section_paragraphs:
                continue

            current_parts: list[str] = []
            current_tokens = 0

            for paragraph in section_paragraphs:
                paragraph_tokens = self._estimate_tokens(paragraph)

                if paragraph_tokens > self.max_tokens:
                    oversized_parts = self._split_oversized_paragraph(paragraph)
                else:
                    oversized_parts = [paragraph]

                for part in oversized_parts:
                    part_tokens = self._estimate_tokens(part)

                    if current_parts and current_tokens + part_tokens > self.target_tokens:
                        chunk_buffer.append(
                            self._build_chunk_buffer_item(
                                heading_path=section.heading_path,
                                paragraphs=current_parts,
                            )
                        )
                        current_parts = self._build_overlap_window(current_parts)
                        current_tokens = self._estimate_tokens("\n\n".join(current_parts))

                    while current_parts and current_tokens + part_tokens > self.max_tokens:
                        current_parts.pop(0)
                        current_tokens = self._estimate_tokens("\n\n".join(current_parts))

                    current_parts.append(part)
                    current_tokens += part_tokens

            if current_parts:
                chunk_buffer.append(
                    self._build_chunk_buffer_item(
                        heading_path=section.heading_path,
                        paragraphs=current_parts,
                    )
                )

        return self._finalize_chunks(chunk_buffer)

    def _extract_sections(self, markdown_text: str) -> list[Section]:
        sections: list[Section] = []
        active_headings: list[str] = []
        current_body: list[str] = []

        for raw_line in markdown_text.splitlines():
            line = raw_line.rstrip()
            heading_match = HEADING_PATTERN.match(line.strip())

            if heading_match:
                self._flush_section(
                    sections=sections,
                    active_headings=active_headings,
                    current_body=current_body,
                )
                current_body = []

                hashes, heading_text = heading_match.groups()
                level = len(hashes)
                heading_text = self._clean_heading(heading_text)
                active_headings = active_headings[: max(level - 1, 0)]
                active_headings.append(heading_text)
                continue

            current_body.append(line)

        self._flush_section(
            sections=sections,
            active_headings=active_headings,
            current_body=current_body,
        )

        return sections

    def _flush_section(
        self,
        *,
        sections: list[Section],
        active_headings: list[str],
        current_body: list[str],
    ) -> None:
        body = "\n".join(current_body).strip()
        if not body:
            return

        heading_path = active_headings[:] or ["Introduction"]
        paragraphs = [paragraph for paragraph in body.split("\n\n") if paragraph.strip()]
        sections.append(Section(heading_path=heading_path, paragraphs=paragraphs))

    def _build_chunk_buffer_item(
        self,
        *,
        heading_path: list[str],
        paragraphs: list[str],
    ) -> dict:
        text = "\n\n".join(paragraphs).strip()
        return {
            "heading_path": heading_path,
            "text": text,
            "token_count": self._estimate_tokens(text),
            "word_count": len(text.split()),
            "paragraph_count": len(paragraphs),
        }

    def _finalize_chunks(self, chunk_buffer: list[dict]) -> list[ChunkDraft]:
        finalized: list[ChunkDraft] = []

        for index, item in enumerate(chunk_buffer):
            finalized.append(
                ChunkDraft(
                    chunk_index=index,
                    heading_path=item["heading_path"],
                    text=item["text"],
                    embedding_text=self._build_embedding_text(
                        heading_path=item["heading_path"],
                        text=item["text"],
                    ),
                    token_count=item["token_count"],
                    word_count=item["word_count"],
                    paragraph_count=item["paragraph_count"],
                    prev_chunk_index=index - 1 if index > 0 else None,
                    next_chunk_index=index + 1 if index + 1 < len(chunk_buffer) else None,
                )
            )

        return finalized

    def _build_overlap_window(self, paragraphs: list[str]) -> list[str]:
        overlap: list[str] = []
        total_tokens = 0

        for paragraph in reversed(paragraphs):
            paragraph_tokens = self._estimate_tokens(paragraph)
            if overlap and total_tokens + paragraph_tokens > self.overlap_tokens:
                break
            overlap.insert(0, paragraph)
            total_tokens += paragraph_tokens
            if total_tokens >= self.overlap_tokens:
                break

        return overlap

    def _split_oversized_paragraph(self, paragraph: str) -> list[str]:
        sentences = [
            sentence.strip()
            for sentence in SENTENCE_BOUNDARY_PATTERN.split(paragraph.strip())
            if sentence.strip()
        ]

        if len(sentences) <= 1:
            return self._split_by_word_windows(paragraph)

        parts: list[str] = []
        current_sentences: list[str] = []
        current_tokens = 0

        for sentence in sentences:
            sentence_tokens = self._estimate_tokens(sentence)
            if current_sentences and current_tokens + sentence_tokens > self.max_tokens:
                parts.append(" ".join(current_sentences).strip())
                current_sentences = []
                current_tokens = 0

            current_sentences.append(sentence)
            current_tokens += sentence_tokens

        if current_sentences:
            parts.append(" ".join(current_sentences).strip())

        return parts or self._split_by_word_windows(paragraph)

    def _split_by_word_windows(self, text: str) -> list[str]:
        words = text.split()
        if not words:
            return []

        estimated_words_per_chunk = max(1, self.target_tokens * 3 // 4)
        estimated_overlap_words = max(1, self.overlap_tokens * 3 // 4)
        step = max(1, estimated_words_per_chunk - estimated_overlap_words)
        parts: list[str] = []

        for start in range(0, len(words), step):
            window = words[start : start + estimated_words_per_chunk]
            if not window:
                break
            parts.append(" ".join(window))
            if start + estimated_words_per_chunk >= len(words):
                break

        return parts

    def _normalize_paragraphs(self, paragraphs: list[str]) -> list[str]:
        normalized: list[str] = []

        for paragraph in paragraphs:
            cleaned = re.sub(r"\n{2,}", "\n", paragraph).strip()
            if not cleaned:
                continue
            normalized.append(cleaned)

        return normalized

    @staticmethod
    def _build_embedding_text(*, heading_path: list[str], text: str) -> str:
        heading_context = " > ".join(heading_path)
        return "\n".join(
            [
                f"Section: {heading_context}",
                "",
                text,
            ]
        ).strip()

    @staticmethod
    def _clean_heading(heading_text: str) -> str:
        cleaned = heading_text.strip().strip("#").strip()
        return cleaned or "Untitled Section"

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        return max(1, len(text.split()) * 4 // 3)
