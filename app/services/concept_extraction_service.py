from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

# NOTE: an earlier iteration of this service extracted a `kind` field per concept
# (definition / framework / technique / claim / distinction). It was removed because:
#   - the LLM showed a strong definition-bias, tagging ~85% of concepts "definition"
#     regardless of actual content type (validated across 3 articles on 2026-06-02);
#   - no code path consumed the field, so persisting it added complexity without value;
#   - it was never added to the Concept ORM model or migration, so the dataclass field
#     was effectively unreachable.
# If a future phase needs kind-based filtering or weighting (e.g. preferring `technique`
# concepts for how-to queries), add it back deliberately:
#   1. Add `kind` as a column on Concept in app/models/schema.py
#   2. Generate a migration adding the column
#   3. Restore the field to ConceptDraft, the JSON schema, and the prompt
#   4. Iterate on the prompt to reduce the definition-bias (the previous prompt's
#      examples were too definition-shaped — see commit history around 2026-06-02)
# Don't restore it without a concrete consumer driving the design.

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
                },
                "required": ["term", "definition", "context_hint"],
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

5. context_hint — Optional. A 1–2 sentence pointer to where in the article \
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
                    extraction_order=order,
                    metadata={
                        "model": self.model,
                        "response_id": response.id,
                    },
                ))
            except (KeyError, TypeError) as exc:
                logger.warning("Skipping malformed concept at index %d: %s", order, exc)

        return drafts
