from openai import OpenAI


class EmbeddingService:
    def __init__(self, config) -> None:
        self.model = config["OPENAI_EMBEDDING_MODEL"]
        self.api_key = config.get("OPENAI_API_KEY")

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is required to create embeddings")

        client = OpenAI(api_key=self.api_key)
        response = client.embeddings.create(model=self.model, input=texts)
        return [item.embedding for item in response.data]
