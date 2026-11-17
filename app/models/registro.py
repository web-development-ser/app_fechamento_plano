"""SQL da tabela agrupamento_registro (consulta e atendimento)."""
from app import db

STATUS_OPCOES = ("Agrupado", "Disponível", "Finalizado", "Barberan", "3DB")
RESP_TS7_MAX = 150
# setor identificado pelo prefixo do Equipto
SETORES = {"S7S": "Serigrafia", "S7M": "Montagem", "S7P": "Pintura"}


def setor_de(equipto):
    return SETORES.get((equipto or "").strip().upper()[:3])

# chave do filtro -> condição SQL (valores sempre via parâmetro)
_FILTROS = {
    "programa": "programa ILIKE %(programa)s",
    "item": "item ILIKE %(item)s",
    "doc": "doc_orig ILIKE %(doc)s",
    "equipto": "equipto ILIKE %(equipto)s",
    "dt_solic": "dt_solic = %(dt_solic)s",
}
_LIKE = {"programa", "item", "doc", "equipto"}


def _where(filtros):
    conds, params = [], {}
    status = filtros.get("status", "")
    if status == "":  # padrão: status vazio (pendente)
        conds.append("status IS NULL")
    elif status == "atendidos":
        conds.append("status IS NOT NULL")
    elif status in STATUS_OPCOES:
        conds.append("status = %(status)s")
        params["status"] = status
    # "todos" -> sem condição de status
    setor = filtros.get("setor")
    if setor in SETORES:
        conds.append("equipto ILIKE %(setor)s")
        params["setor"] = f"{setor}%"
    for chave, cond in _FILTROS.items():
        valor = filtros.get(chave)
        if valor:
            conds.append(cond)
            params[chave] = f"%{valor}%" if chave in _LIKE else valor
    return (" WHERE " + " AND ".join(conds)) if conds else "", params


def listar(filtros, limite, offset):
    where, params = _where(filtros)
    params.update(limite=limite, offset=offset)
    total = db.query_one(f"SELECT count(*) AS n FROM agrupamento_registro{where}", params)["n"]
    # vaga do mapeamento ativo (PROCV: Prog. Orig. -> Programa, Doc. Orig. -> Documento)
    rows = db.query(
        "SELECT r.id, r.programa, r.item, r.prog_orig, r.doc_orig, r.equipto, r.dt_solic,"
        " r.qtd_reposicao, r.status, r.descricao, r.dt_recebimento,"
        " coalesce(m.vaga, r.loc_tegad) AS loc_tegad"
        f" FROM (SELECT * FROM agrupamento_registro{where}) r"
        " LEFT JOIN mapeamentos m ON m.liberado_em IS NULL"
        "  AND m.programa = upper(trim(r.prog_orig)) AND m.documento = upper(trim(r.doc_orig))"
        " ORDER BY r.dt_solic NULLS LAST, r.id"
        " LIMIT %(limite)s OFFSET %(offset)s",
        params,
    )
    return rows, total


def resumo(filtros):
    """Totais de atendidos x pendentes para os filtros informados (ignora o filtro de status)."""
    where, params = _where({**filtros, "status": "todos"})
    return db.query_one(
        "SELECT count(*) AS total, count(status) AS atendidos, count(*) - count(status) AS pendentes"
        f" FROM agrupamento_registro{where}", params)


def buscar(registro_id):
    return db.query_one("SELECT * FROM agrupamento_registro WHERE id = %s", (registro_id,))


def salvar_atendimento(registro_id, dados, usuario):
    return db.execute(
        "UPDATE agrupamento_registro SET dt_recebimento = %(dt_recebimento)s,"
        " pessoa_resp_tegad = %(pessoa)s, loc_tegad = %(loc_tegad)s, resp_ts7 = %(resp_ts7)s,"
        " narrativa = %(narrativa)s, status = %(status)s,"
        " atualizado_em = now(), atualizado_por = %(por)s WHERE id = %(id)s",
        {**dados, "pessoa": usuario["nome"], "por": usuario["id"], "id": registro_id},
    )


def contar_pendentes(prog_orig, doc_orig, status_concluidos, ignorar_id=None):
    """Itens do mesmo Prog. Orig. + Doc. Orig. que ainda não estão em um dos status concluídos."""
    return db.query_one(
        "SELECT count(*) AS n FROM agrupamento_registro"
        " WHERE upper(trim(prog_orig)) = upper(trim(%s)) AND upper(trim(doc_orig)) = upper(trim(%s))"
        " AND id IS DISTINCT FROM %s AND (status IS NULL OR NOT (status = ANY(%s)))",
        (prog_orig, doc_orig, ignorar_id, list(status_concluidos)),
    )["n"]
