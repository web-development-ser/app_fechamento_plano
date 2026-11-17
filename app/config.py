import os

from dotenv import load_dotenv

load_dotenv()


def normalizar_dsn(url):
    """Aceita o formato SQLAlchemy (postgresql+psycopg://, postgresql+psycopg2://) e devolve o do libpq."""
    if not url:
        return url
    for prefixo in ("postgresql+psycopg2://", "postgresql+psycopg://", "postgres://"):
        if url.startswith(prefixo):
            return "postgresql://" + url[len(prefixo):]
    return url


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY")
    DATABASE_URL = normalizar_dsn(os.environ.get("DATABASE_URL"))
    MAX_CONTENT_LENGTH = int(os.environ.get("MAX_UPLOAD_MB", "10")) * 1024 * 1024
    DEBUG = os.environ.get("FLASK_DEBUG", "0") == "1"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PAGE_SIZE = 50
