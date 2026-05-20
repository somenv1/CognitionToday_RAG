import sys
from openai import OpenAI


class EmbeddingService:
    def __init__(self, config) -> None:
        self.model = config["OPENAI_EMBEDDING_MODEL"]
        self.api_key = config.get("OPENAI_API_KEY")
        print(f"[EmbeddingService] init: model={self.model!r} api_key_present={self.api_key is not None}", flush=True)

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        print(f"[EmbeddingService] embed_texts called with {len(texts)} texts", flush=True)
        if not self.api_key:
            print(f"[EmbeddingService] NO API KEY!", flush=True)
            raise RuntimeError("OPENAI_API_KEY is required to create embeddings")

        try:
            client = OpenAI(api_key=self.api_key)
            response = client.embeddings.create(model=self.model, input=texts)
            embeddings = [item.embedding for item in response.data]
            first_dim = len(embeddings[0]) if embeddings else "N/A"
            print(f"[EmbeddingService] SUCCESS: got {len(embeddings)} embeddings, first has {first_dim} dimensions", flush=True)
            return embeddings
        except Exception as e:
            print(f"[EmbeddingService] FAILED with {type(e).__name__}: {e}", flush=True)
            raise
