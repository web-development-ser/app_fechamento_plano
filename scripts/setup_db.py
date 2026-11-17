"""Cria o banco de dados (se não existir) e aplica todas as migrations (tabelas, índices, constraints).

Uso:
    python -m scripts.setup_db            # banco do DATABASE_URL
    python -m scripts.setup_db --test     # também o banco do TEST_DATABASE_URL

Seguro para rodar várias vezes: não apaga nada, só cria o que falta.
"""
import argparse
import os
import sys

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from app.config import normalizar_dsn
from app.db import apply_migrations, connect


def descrever(params):
    """Identifica o destino sem expor a senha."""
    return f"{params.get('user')}@{params.get('host')}:{params.get('port', 5432)}/{params.get('dbname')}"


def criar_banco_se_preciso(dsn):
    params = conninfo_to_dict(dsn)
    nome = params.get("dbname")
    if not nome:
        raise SystemExit("A URL não informa o nome do banco.")
    # conecta no banco de manutenção do mesmo servidor
    admin_dsn = make_conninfo(dsn, dbname="postgres")
    with psycopg.connect(admin_dsn, autocommit=True) as conn:
        existe = conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (nome,)).fetchone()
        if existe:
            print(f"[ok] Banco já existe: {descrever(params)}")
            return False
        conn.execute(
            sql.SQL("CREATE DATABASE {} ENCODING 'UTF8' TEMPLATE template0").format(sql.Identifier(nome))
        )
        print(f"[+] Banco criado: {descrever(params)}")
        return True


def preparar(dsn):
    criar_banco_se_preciso(dsn)
    with connect(dsn) as conn:
        novas = apply_migrations(conn)
        tabelas = [r["table_name"] for r in conn.execute(
            "SELECT table_name FROM information_schema.tables"
            " WHERE table_schema = 'public' ORDER BY table_name").fetchall()]
    print("[+] Migrations aplicadas: " + ", ".join(novas) if novas else "[ok] Nenhuma migration pendente")
    print("    Tabelas: " + ", ".join(tabelas))


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--test", action="store_true", help="também prepara o TEST_DATABASE_URL")
    args = parser.parse_args()

    alvos = [("DATABASE_URL", os.environ.get("DATABASE_URL"))]
    if args.test:
        alvos.append(("TEST_DATABASE_URL", os.environ.get("TEST_DATABASE_URL")))

    for var, url in alvos:
        if not url:
            raise SystemExit(f"{var} não definido no .env")
        print(f"== {var}")
        try:
            preparar(normalizar_dsn(url))
        except psycopg.OperationalError as exc:
            # a mensagem do libpq não contém a senha
            print(f"[erro] Não foi possível conectar: {str(exc).strip()}", file=sys.stderr)
            raise SystemExit(1)
        except psycopg.errors.InsufficientPrivilege:
            print("[erro] O usuário não tem permissão para criar bancos (CREATEDB). "
                  "Peça ao DBA para criar o banco e rode novamente.", file=sys.stderr)
            raise SystemExit(1)


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()
    main()
