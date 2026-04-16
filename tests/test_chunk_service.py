import importlib.util
from pathlib import Path
import sys
import unittest


MODULE_PATH = Path(__file__).resolve().parents[1] / "app" / "services" / "chunk_service.py"
SPEC = importlib.util.spec_from_file_location("chunk_service", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

ChunkService = MODULE.ChunkService


class ChunkServiceTestCase(unittest.TestCase):
    def test_preserves_heading_paths_for_sections(self):
        markdown = """
# What Is Confirmation Bias?

## Definition
Confirmation bias is the tendency to favor evidence that supports existing beliefs.

## Examples in Daily Life
People may notice stories that confirm their political views while ignoring contradictory evidence.
""".strip()

        service = ChunkService(target_tokens=80, max_tokens=120, overlap_tokens=20)
        chunks = service.chunk_markdown(markdown)

        self.assertEqual(len(chunks), 2)
        self.assertEqual(
            chunks[0].heading_path,
            ["What Is Confirmation Bias?", "Definition"],
        )
        self.assertEqual(
            chunks[1].heading_path,
            ["What Is Confirmation Bias?", "Examples in Daily Life"],
        )

    def test_splits_oversized_paragraph_by_sentence_groups(self):
        large_paragraph = " ".join(
            [
                "Sentence one explains the concept clearly.",
                "Sentence two adds more context for retrieval quality.",
                "Sentence three expands the example with extra detail.",
                "Sentence four introduces the tradeoff in chunk size.",
                "Sentence five keeps the paragraph intentionally long.",
                "Sentence six ensures the paragraph exceeds the token limit.",
            ]
        )
        markdown = f"""
# Retrieval Quality

## Long Section
{large_paragraph}
""".strip()

        service = ChunkService(target_tokens=20, max_tokens=24, overlap_tokens=8)
        chunks = service.chunk_markdown(markdown)

        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(chunk.token_count <= 24 for chunk in chunks))
        self.assertTrue(all("Section: Retrieval Quality > Long Section" in chunk.embedding_text for chunk in chunks))


if __name__ == "__main__":
    unittest.main()
