"""Aplica as migrations pendentes no DATABASE_URL do .env. Uso: python -m scripts.init_db"""
from app.config import Config
from app.db import apply_migrations, connect


def main():
    if not Config.DATABASE_URL:
        raise SystemExit("DATABASE_URL não definido no .env")
    with connect(Config.DATABASE_URL) as conn:
        novas = apply_migrations(conn)
    print("Migrations aplicadas: " + (", ".join(novas) if novas else "nenhuma (banco já atualizado)"))


if __name__ == "__main__":
    main()
