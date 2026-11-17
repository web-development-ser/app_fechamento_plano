"""Fixtures. Testes de integração usam TEST_DATABASE_URL (banco descartável, nome deve terminar em _test)."""
import os
import re

import pytest
from dotenv import load_dotenv

load_dotenv()
from app.config import normalizar_dsn  # noqa: E402

TEST_DB = normalizar_dsn(os.environ.get("TEST_DATABASE_URL"))

requires_db = pytest.mark.skipif(not TEST_DB, reason="TEST_DATABASE_URL não configurado")


def _reset_schema():
    from app.db import apply_migrations, connect

    nome_banco = re.sub(r"\?.*$", "", TEST_DB).rsplit("/", 1)[-1]
    if not nome_banco.endswith("_test"):
        raise RuntimeError("Por segurança, TEST_DATABASE_URL deve apontar para um banco terminado em _test")
    with connect(TEST_DB) as conn:
        conn.execute("DROP SCHEMA public CASCADE")
        conn.execute("CREATE SCHEMA public")
        conn.commit()
        apply_migrations(conn)


@pytest.fixture
def app():
    if not TEST_DB:
        pytest.skip("TEST_DATABASE_URL não configurado")
    _reset_schema()
    from app import create_app

    return create_app({"TESTING": True, "DATABASE_URL": TEST_DB, "SECRET_KEY": "teste"})


@pytest.fixture
def client(app):
    return app.test_client()


def criar_usuario(app, usuario="admin", senha="segredo1", perfil="ADMIN", nome=None, ativo=True):
    from app import db
    from app.models import usuario as usuarios

    with app.app_context():
        uid = usuarios.criar(nome or usuario.title(), usuario, senha, perfil)
        if not ativo:
            usuarios.definir_ativo(uid, False, uid)
        db.commit()
    return uid


def csrf(client):
    client.get("/login")
    with client.session_transaction() as s:
        return s["_csrf"]


def login(client, usuario="admin", senha="segredo1"):
    token = csrf(client)
    return client.post("/login", data={"usuario": usuario, "senha": senha, "_csrf": token})


@pytest.fixture
def admin_client(app, client):
    criar_usuario(app)
    login(client)
    return client
