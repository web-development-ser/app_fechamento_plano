"""Registro de auditoria: quem fez o quê, quando. Não faz commit (participa da transação atual)."""
import json
from datetime import date, datetime, time
from decimal import Decimal

from flask import g
from psycopg.types.json import Jsonb

from app import db


def _json_default(valor):
    """Converte tipos que o json padrão não serializa (datas, horas, decimais)."""
    if isinstance(valor, (datetime, date, time)):
        return valor.isoformat()
    if isinstance(valor, Decimal):
        return str(valor)
    raise TypeError(f"Tipo não serializável na auditoria: {type(valor).__name__}")


def serializar(detalhes):
    return json.dumps(detalhes, default=_json_default, ensure_ascii=False)


def registrar(acao, entidade, entidade_id=None, detalhes=None, usuario=None):
    usuario = usuario or g.get("user")
    db.execute(
        "INSERT INTO auditoria (usuario_id, usuario_nome, acao, entidade, entidade_id, detalhes)"
        " VALUES (%s, %s, %s, %s, %s, %s)",
        (
            usuario["id"] if usuario else None,
            usuario["nome"] if usuario else None,
            acao,
            entidade,
            str(entidade_id) if entidade_id is not None else None,
            Jsonb(detalhes, dumps=serializar) if detalhes is not None else None,
        ),
    )
