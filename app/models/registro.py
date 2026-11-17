"""SQL da tabela agrupamento_registro (consulta e atendimento)."""
from app import db

STATUS_OPCOES = ("Agrupado", "Disponível", "Finalizado", "Barberan", "3DB")
RESP_TS7_MAX = 150

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
    if status == "":  # padrão: status vazio
        conds.append("status IS NULL")
    elif status in STATUS_OPCOES:
        conds.append("status = %(status)s")
        params["status"] = status
    # "todos" -> sem condição de status
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
        " r.qtd_reposicao, r.status, coalesce(m.vaga, r.loc_tegad) AS loc_tegad"
        f" FROM (SELECT * FROM agrupamento_registro{where}) r"
        " LEFT JOIN mapeamentos m ON m.liberado_em IS NULL"
        "  AND m.programa = upper(trim(r.prog_orig)) AND m.documento = upper(trim(r.doc_orig))"
        " ORDER BY r.dt_solic NULLS LAST, r.id"
        " LIMIT %(limite)s OFFSET %(offset)s",
        params,
    )
    return rows, total


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
