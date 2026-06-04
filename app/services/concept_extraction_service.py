from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

# NOTE: the `kind` field has a definition-bias — the LLM tends to tag any
# named concept as "definition" even when its content is procedural or
# claim-shaped. No retrieval logic currently reads `kind`, so this is
# documented rather than fixed. Revisit if Phase 3+ adds kind-based
# filtering or weighting.

logger = logging.getLogger(__name__)

MAX_CONCEPTS = 15

# minLength / maxLength are documentation hints only — OpenAI's structured-output
# strict mode does not support them, so strict=False is used below.
_SCHEMA = {
    "type": "object",
    "properties": {
        "concepts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "term":         {"type": "string", "minLength": 3,  "maxLength": 100},
                    "definition":   {"type": "string", "minLength": 20, "maxLength": 500},
                    "context_hint": {"type": ["string", "null"],        "maxLength": 200},
                    "kind": {
                        "type": "string",
                        "enum": ["definition", "framework", "technique", "claim", "distinction"],
                    },
                },
                "required": ["term", "definition", "context_hint", "kind"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["concepts"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = """\
You are a concept extractor for a psychology and cognitive science blog.

Read the article below and extract 8 to 12 key concepts that the article \
explicitly defines, explains, or introduces. Do not exceed 15 concepts.

Rules you must follow without exception:

1. SOURCE FIDELITY — Only extract concepts the article itself defines or \
explains. Do not draw on general psychology, neuroscience, or any external \
knowledge. If the article does not explain a term, do not extract it.

2. ORIGINAL FRAMING — Write definitions using the article's own language, \
phrasing, examples, and emphasis. Do not paraphrase into textbook language \
or outside frameworks.

3. SELF-CONTAINED DEFINITIONS — Each definition must be 1–3 sentences, \
fully understandable without reading the article. No pronouns with ambiguous \
referents ("it", "this", "they"). No forward or backward references \
("as described above", "see the next section").

4. NO INVENTION — Do not extract or imply any concept not clearly grounded \
in the source text. When in doubt, omit it.

5. KIND — Assign exactly one kind per concept:
   • definition  — the article defines or names a term
   • framework   — the article presents a model, system, or structured set of ideas
   • technique   — the article describes a practical method or procedure
   • claim       — the article makes a specific empirical or causal assertion
   • distinction — the article explicitly contrasts two or more things

6. context_hint — Optional. A 1–2 sentence pointer to where in the article \
this concept appears (e.g., the section name, a key example, or a brief \
location marker). Set to null if the concept runs throughout the article.

Return a JSON object matching the schema you have been given.\
"""


def _user_message(title: str, markdown: str) -> str:
    return f"Article title: {title}\n\n---\n\n{markdown}"


@dataclass
class ConceptDraft:
    term: str
    definition: str
    context_hint: str | None
    kind: str
    extraction_order: int
    metadata: dict = field(default_factory=dict)


class ConceptExtractionService:
    def __init__(self, config) -> None:
        self.api_key = config.get("OPENAI_API_KEY")
        self.model = config.get("OPENAI_CONCEPT_EXTRACTION_MODEL", "gpt-4.1")

    def extract(self, *, title: str, markdown: str) -> list[ConceptDraft]:
        if not self.api_key:
            logger.info("OPENAI_API_KEY not set — skipping concept extraction")
            return []

        from openai import OpenAI
        client = OpenAI(api_key=self.api_key)

        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": _user_message(title, markdown)},
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "concept_extraction",
                        "schema": _SCHEMA,
                        "strict": False,
                    },
                },
                temperature=0.1,
            )
        except Exception as exc:
            logger.warning("OpenAI call failed during concept extraction: %s", exc)
            return []

        raw = (response.choices[0].message.content or "").strip()

        try:
            parsed = json.loads(raw)
            raw_concepts = parsed.get("concepts", [])
        except (json.JSONDecodeError, AttributeError) as exc:
            logger.warning("Concept extraction: failed to parse LLM response: %s", exc)
            return []

        drafts: list[ConceptDraft] = []
        for order, item in enumerate(raw_concepts[:MAX_CONCEPTS]):
            try:
                drafts.append(ConceptDraft(
                    term=item["term"],
                    definition=item["definition"],
                    context_hint=item.get("context_hint"),
                    kind=item["kind"],
                    extraction_order=order,
                    metadata={
                        "model": self.model,
                        "response_id": response.id,
                    },
                ))
            except (KeyError, TypeError) as exc:
                logger.warning("Skipping malformed concept at index %d: %s", order, exc)

        return drafts
