from app.config import normalizar_dsn


def test_normaliza_url_sqlalchemy_para_libpq():
    assert normalizar_dsn("postgresql+psycopg://u:p@h:5432/db") == "postgresql://u:p@h:5432/db"
    assert normalizar_dsn("postgresql+psycopg2://u:p@h/db") == "postgresql://u:p@h/db"
    assert normalizar_dsn("postgres://u:p@h/db") == "postgresql://u:p@h/db"
    assert normalizar_dsn("postgresql://u:p@h/db") == "postgresql://u:p@h/db"
    assert normalizar_dsn(None) is None
