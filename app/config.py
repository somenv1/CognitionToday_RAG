import os

from dotenv import load_dotenv


load_dotenv()


class BaseConfig:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///rag.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENAI_CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-4.1-mini")
    OPENAI_EMBEDDING_MODEL = os.getenv(
        "OPENAI_EMBEDDING_MODEL",
        "text-embedding-3-large",
    )

    RAG_VECTOR_TOP_K = int(os.getenv("RAG_VECTOR_TOP_K", "30"))
    RAG_LEXICAL_TOP_K = int(os.getenv("RAG_LEXICAL_TOP_K", "20"))
    RAG_RERANK_TOP_K = int(os.getenv("RAG_RERANK_TOP_K", "8"))
    RAG_FINAL_CONTEXT_K = int(os.getenv("RAG_FINAL_CONTEXT_K", "5"))
    RAG_SCORE_THRESHOLD = float(os.getenv("RAG_SCORE_THRESHOLD", "0.015"))

    BLOG_SITEMAP_URL = os.getenv("BLOG_SITEMAP_URL")
    BLOG_ALLOWED_HOSTS = [
        host.strip()
        for host in os.getenv("BLOG_ALLOWED_HOSTS", "").split(",")
        if host.strip()
    ]


class DevelopmentConfig(BaseConfig):
    DEBUG = True


class ProductionConfig(BaseConfig):
    DEBUG = False


config_by_name = {
    "default": DevelopmentConfig,
    "development": DevelopmentConfig,
    "production": ProductionConfig,
}
