"""Mapeamentos de Programas Interrompidos: reserva e liberação de vagas (M01..M20, P01..P20, S01..S20)."""
from datetime import datetime, time
from zoneinfo import ZoneInfo

import psycopg

from app import db

FUSO = ZoneInfo("America/Sao_Paulo")
FILAS = ("M", "P", "S")
VAGAS = tuple(f"{fila}{n:02d}" for fila in FILAS for n in range(1, 21))
ESTOQUE = "EST"  # localização especial, sem limite de caixas (migration 004)
CAPACIDADE_VAGA = 7  # caixas (mapeamentos ativos) por vaga — também garantido no banco (migration 003)
STATUS_LIBERAM = ("Disponível", "Finalizado")  # status do item que tiram a caixa da vaga

INICIO_T1 = time(5, 25)   # 1º turno: 05:25:00 – 15:14:59
INICIO_T2 = time(15, 15)  # 2º turno: 15:15:00 – 00:47:59 (atravessa a meia-noite)
FIM_T2 = time(0, 48)      # a partir de 00:48:00 até 05:24:59 = fora de turno


class VagaIndisponivel(Exception):
    pass


class MapeamentoDuplicado(Exception):
    pass


def normalizar_chave(valor):
    """Programa/Documento comparados sem espaços e sem diferenciar maiúsculas."""
    return (valor or "").strip().upper()


def turno_de(momento):
    """1, 2 ou None (fora de turno). Transição 15:15 pertence ao 2º turno; 00:47 ainda é 2º turno."""
    t = momento.time()
    if INICIO_T1 <= t < INICIO_T2:
        return 1
    if t >= INICIO_T2 or t < FIM_T2:
        return 2
    return None


def descrever_turno(turno):
    return {1: "1º turno", 2: "2º turno"}.get(turno, "Fora de turno")


def agora():
    return datetime.now(FUSO)


def ocupacao():
    """{vaga: nº de caixas ativas}."""
    rows = db.query(
        "SELECT vaga, count(*) AS n FROM mapeamentos WHERE liberado_em IS NULL GROUP BY vaga")
    return {r["vaga"]: r["n"] for r in rows}


def vagas_livres(ocup=None):
    """Vagas com menos de 7 caixas."""
    ocup = ocupacao() if ocup is None else ocup
    return [v for v in VAGAS if ocup.get(v, 0) < CAPACIDADE_VAGA]


def vaga_lotada(vaga):
    if vaga == ESTOQUE:
        return False
    return ocupacao().get(vaga, 0) >= CAPACIDADE_VAGA


def descrever_local(codigo):
    """Nome exibido da localização: 'EST' -> 'Estoque'; vagas ficam como estão."""
    if not codigo:
        return codigo
    codigo = str(codigo).strip()
    return "Estoque" if codigo == ESTOQUE else codigo


def status_libera(status):
    return status in STATUS_LIBERAM


def criar(programa, documento, vaga, usuario, momento=None):
    """Adiciona uma caixa à vaga. Capacidade e duplicidade garantidas no banco (trigger + índice único)."""
    momento = momento or agora()
    params = {
        "programa": normalizar_chave(programa),
        "documento": normalizar_chave(documento),
        "vaga": vaga,
        "turno": turno_de(momento),
        "em": momento,
        "por": usuario["id"],
        "nome": usuario["nome"],
    }
    conn = db.get_conn()
    try:
        with conn.transaction():
            row = db.query_one(
                "INSERT INTO mapeamentos (programa, documento, vaga, turno, registrado_em,"
                " registrado_por, usuario_nome) VALUES (%(programa)s, %(documento)s, %(vaga)s,"
                " %(turno)s, %(em)s, %(por)s, %(nome)s) RETURNING id",
                params,
            )
    except psycopg.errors.CheckViolation as exc:
        if exc.diag.message_primary == "VAGA_LOTADA":
            raise VagaIndisponivel(
                f"A vaga {vaga} está lotada ({CAPACIDADE_VAGA} caixas). Escolha outra.") from None
        raise
    except psycopg.errors.UniqueViolation:
        raise MapeamentoDuplicado(
            f"Já existe mapeamento ativo para o Programa {params['programa']} / "
            f"Documento {params['documento']}."
        ) from None
    return row["id"], params


def listar_ativos():
    return db.query(
        "SELECT m.*, EXISTS (SELECT 1 FROM agrupamento_registro r"
        "  WHERE upper(trim(r.prog_orig)) = m.programa AND upper(trim(r.doc_orig)) = m.documento"
        " ) AS tem_registro"
        " FROM mapeamentos m WHERE m.liberado_em IS NULL ORDER BY m.vaga"
    )


def listar_liberados(limite=20):
    return db.query(
        "SELECT * FROM mapeamentos WHERE liberado_em IS NOT NULL ORDER BY liberado_em DESC LIMIT %s",
        (limite,),
    )


def buscar_ativo(programa, documento):
    """PROCV: Prog. Orig. -> Programa, Doc. Orig. -> Documento."""
    return db.query_one(
        "SELECT * FROM mapeamentos WHERE programa = %s AND documento = %s AND liberado_em IS NULL",
        (normalizar_chave(programa), normalizar_chave(documento)),
    )


def buscar_ultimo(programa, documento):
    """Mapeamento ativo ou, se não houver, o último liberado (para exibir histórico)."""
    return db.query_one(
        "SELECT * FROM mapeamentos WHERE programa = %s AND documento = %s"
        " ORDER BY (liberado_em IS NULL) DESC, registrado_em DESC LIMIT 1",
        (normalizar_chave(programa), normalizar_chave(documento)),
    )


def liberar(mapeamento_id, usuario, registro_id=None):
    return db.execute(
        "UPDATE mapeamentos SET liberado_em = now(), liberado_por = %s, registro_id = %s"
        " WHERE id = %s AND liberado_em IS NULL",
        (usuario["id"], registro_id, mapeamento_id),
    )
