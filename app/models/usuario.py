"""SQL da tabela usuarios. Nunca retorna senha_hash fora de buscar_para_login."""
from werkzeug.security import check_password_hash, generate_password_hash

from app import db

PERFIS = ("ADMIN", "USUARIO")
_CAMPOS = "id, nome, usuario, perfil, ativo, criado_em, atualizado_em"


def buscar_por_id(user_id):
    return db.query_one(f"SELECT {_CAMPOS} FROM usuarios WHERE id = %s", (user_id,))


def listar():
    return db.query(f"SELECT {_CAMPOS} FROM usuarios ORDER BY ativo DESC, nome")


def usuario_existe(usuario, ignorar_id=None):
    row = db.query_one(
        "SELECT 1 FROM usuarios WHERE lower(usuario) = lower(%s) AND id IS DISTINCT FROM %s",
        (usuario, ignorar_id),
    )
    return row is not None


def autenticar(usuario, senha):
    """Retorna (user, motivo_erro). Mensagem genérica para não revelar se o usuário existe."""
    row = db.query_one(
        f"SELECT {_CAMPOS}, senha_hash FROM usuarios WHERE lower(usuario) = lower(%s)", (usuario,)
    )
    if row is None or not check_password_hash(row["senha_hash"], senha):
        return None, "Usuário ou senha inválidos."
    if not row["ativo"]:
        return None, "Usuário inativo. Procure o administrador."
    row.pop("senha_hash")
    return row, None


def criar(nome, usuario, senha, perfil, criado_por=None):
    row = db.query_one(
        "INSERT INTO usuarios (nome, usuario, senha_hash, perfil, criado_por)"
        " VALUES (%s, %s, %s, %s, %s) RETURNING id",
        (nome, usuario, generate_password_hash(senha), perfil, criado_por),
    )
    return row["id"]


def atualizar(user_id, nome, usuario, perfil, por):
    return db.execute(
        "UPDATE usuarios SET nome = %s, usuario = %s, perfil = %s,"
        " atualizado_em = now(), atualizado_por = %s WHERE id = %s",
        (nome, usuario, perfil, por, user_id),
    )


def redefinir_senha(user_id, senha, por):
    return db.execute(
        "UPDATE usuarios SET senha_hash = %s, atualizado_em = now(), atualizado_por = %s WHERE id = %s",
        (generate_password_hash(senha), por, user_id),
    )


def definir_ativo(user_id, ativo, por):
    return db.execute(
        "UPDATE usuarios SET ativo = %s, atualizado_em = now(), atualizado_por = %s WHERE id = %s",
        (ativo, por, user_id),
    )
