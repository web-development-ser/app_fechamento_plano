"""Acesso ao PostgreSQL: uma conexão por requisição, sempre com SQL parametrizado."""
from pathlib import Path

import psycopg
from flask import current_app, g
from psycopg.rows import dict_row

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


def connect(dsn):
    return psycopg.connect(dsn, row_factory=dict_row)


def get_conn():
    if "db" not in g:
        g.db = connect(current_app.config["DATABASE_URL"])
    return g.db


def close_conn(_exc=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.rollback()  # descarta o que não foi explicitamente confirmado
        conn.close()


def query(sql, params=None):
    with get_conn().cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def query_one(sql, params=None):
    with get_conn().cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone()


def execute(sql, params=None):
    with get_conn().cursor() as cur:
        cur.execute(sql, params)
        return cur.rowcount


def ping():
    """True se o banco responde. Usado pelo healthcheck."""
    try:
        query_one("SELECT 1 AS ok")
        return True
    except Exception:  # noqa: BLE001
        return False


def commit():
    get_conn().commit()


def rollback():
    get_conn().rollback()


def apply_migrations(conn):
    """Aplica migrations/*.sql ainda não registradas. Idempotente."""
    with conn.cursor() as cur:
        cur.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            " nome VARCHAR(255) PRIMARY KEY, aplicado_em TIMESTAMPTZ NOT NULL DEFAULT now())"
        )
        cur.execute("SELECT nome FROM schema_migrations")
        aplicadas = {r["nome"] for r in cur.fetchall()}
        novas = []
        for arquivo in sorted(MIGRATIONS_DIR.glob("*.sql")):
            if arquivo.name in aplicadas:
                continue
            cur.execute(arquivo.read_text(encoding="utf-8"))
            cur.execute("INSERT INTO schema_migrations (nome) VALUES (%s)", (arquivo.name,))
            novas.append(arquivo.name)
    conn.commit()
    return novas


def init_app(app):
    app.teardown_appcontext(close_conn)
