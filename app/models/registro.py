"""SQL da tabela agrupamento_registro (consulta e atendimento)."""
from app import db

STATUS_OPCOES = ("Agrupado", "Disponível", "Finalizado", "Barberan", "3DB", "Floco", "PS7", "Sala de Cortes")
RESP_TS7_MAX = 150
# setor identificado pelo prefixo do Equipto
SETORES = {"S7S": "Serigrafia", "S7M": "Montagem", "S7P": "Pintura"}


def setor_de(equipto):
    return SETORES.get((equipto or "").strip().upper()[:3])

# chave do filtro -> condição SQL (valores sempre via parâmetro)
_FILTROS = {
    "programa": "programa ILIKE %(programa)s",
    "prog_orig": "prog_orig ILIKE %(prog_orig)s",
    "item": "item ILIKE %(item)s",
    "doc": "doc_orig ILIKE %(doc)s",
    "equipto": "equipto ILIKE %(equipto)s",
    "dt_solic": "dt_solic = %(dt_solic)s",
    "dt_modificacao": "(atualizado_em AT TIME ZONE 'America/Sao_Paulo')::date = %(dt_modificacao)s",
}
_LIKE = {"programa", "prog_orig", "item", "doc", "equipto"}


# item não atendido = status vazio (NULL, em branco ou só espaços)
SQL_NAO_ATENDIDO = "nullif(trim(status), '') IS NULL"
SQL_ATENDIDO = "nullif(trim(status), '') IS NOT NULL"


def _where(filtros):
    conds, params = [], {}
    status = filtros.get("status", "")
    if status == "":  # padrão: status vazio (não atendido)
        conds.append(SQL_NAO_ATENDIDO)
    elif status == "atendidos":
        conds.append(SQL_ATENDIDO)
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
        " r.pessoa_resp_tegad AS recebido_por, r.resp_ts7,"
        " coalesce(CASE WHEN m.liberado_em IS NULL THEN m.vaga END, r.loc_tegad) AS loc_tegad"
        f" FROM (SELECT * FROM agrupamento_registro{where}) r"
        # localização do mapeamento ativo do Prog. Orig. + Doc. (PROCV)
        " LEFT JOIN LATERAL (SELECT vaga, liberado_em FROM mapeamentos mm"
        "  WHERE mm.programa = upper(trim(r.prog_orig)) AND mm.documento = upper(trim(r.doc_orig))"
        "  ORDER BY (mm.liberado_em IS NULL) DESC, mm.registrado_em DESC LIMIT 1) m ON true"
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


NAO_ATENDIMENTO = "Não Atendimento"  # barra dos itens com status vazio (NULL / em branco)
ORDEM_STATUS = (NAO_ATENDIMENTO, *STATUS_OPCOES)


def contagem_por_status(filtros):
    """Dashboard Troca de Turno: [{'status', 'n', 'pct'}] na ordem fixa + total.

    filtros: status, setor, data, base ('atendimento' | 'solicitacao'), usuario_id.
    Itens atendidos e não atendidos têm regras de data/usuário diferentes, porque o não atendido
    ainda não tem data de atendimento nem usuário:
      - base 'solicitacao': ambos pela Dt. Solic. = data;
      - base 'atendimento': atendidos pelo dia do atendimento; não atendidos = tudo em aberto
        solicitado até a data (backlog do turno);
      - usuário: filtra só os atendidos; os não atendidos continuam no total.
    """
    where, params = _where({"status": "todos", "setor": filtros.get("setor"),
                            **{k: filtros.get(k) for k in ("programa", "prog_orig", "item", "doc", "equipto")}})
    cond_atend, cond_nao = [SQL_ATENDIDO], [SQL_NAO_ATENDIDO]
    data = filtros.get("data")
    if data:
        params["data"] = data
        if filtros.get("base") == "solicitacao":
            cond_atend.append("dt_solic = %(data)s")
            cond_nao.append("dt_solic = %(data)s")
        else:
            cond_atend.append("(atualizado_em AT TIME ZONE 'America/Sao_Paulo')::date = %(data)s")
            cond_nao.append("(dt_solic IS NULL OR dt_solic <= %(data)s)")
    if filtros.get("usuario_id"):
        params["usuario_id"] = filtros["usuario_id"]
        cond_atend.append("atualizado_por = %(usuario_id)s")
    status = filtros.get("status", "todos")
    if status in STATUS_OPCOES:
        params["status"] = status
        cond_atend.append("status = %(status)s")
    grupos = []
    if status != "":           # "" = só não atendidos
        grupos.append("(" + " AND ".join(cond_atend) + ")")
    if status in ("todos", ""):  # atendidos / status específico excluem os não atendidos
        grupos.append("(" + " AND ".join(cond_nao) + ")")
    where = (where + " AND " if where else " WHERE ") + "(" + " OR ".join(grupos) + ")"
    rows = db.query(
        "SELECT coalesce(nullif(trim(status), ''), %(rotulo_vazio)s) AS status, count(*) AS n"
        f" FROM agrupamento_registro{where} GROUP BY 1",
        {**params, "rotulo_vazio": NAO_ATENDIMENTO},
    )
    por = {r["status"]: r["n"] for r in rows}
    total = sum(por.values())
    itens = [{"status": st, "n": por.get(st, 0),
              "pct": round(por.get(st, 0) * 100 / total) if total else 0} for st in ORDEM_STATUS]
    return itens, total


def buscar_detalhe(registro_id):
    """Registro + nomes de quem importou e de quem atualizou o atendimento."""
    return db.query_one(
        "SELECT r.*, ui.nome AS importado_por_nome, ua.nome AS atualizado_por_nome,"
        " i.arquivo_nome AS importacao_arquivo"
        " FROM agrupamento_registro r"
        " LEFT JOIN usuarios ui ON ui.id = r.criado_por"
        " LEFT JOIN usuarios ua ON ua.id = r.atualizado_por"
        " LEFT JOIN importacoes i ON i.id = r.importacao_id"
        " WHERE r.id = %s",
        (registro_id,),
    )


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


def relacionados(prog_orig, doc_orig, excluir_id):
    """Outros itens com o mesmo Prog. Orig. + Doc. Orig. (sem espaços, sem diferenciar maiúsculas)."""
    return db.query(
        "SELECT id, item, programa, descricao, equipto, status FROM agrupamento_registro"
        " WHERE upper(trim(prog_orig)) = upper(trim(%s)) AND upper(trim(doc_orig)) = upper(trim(%s))"
        " AND id <> %s ORDER BY id",
        (prog_orig, doc_orig, excluir_id),
    )


def atualizar_status(ids, status, usuario):
    """Aplica o mesmo status a vários itens (somente o status + rastreabilidade)."""
    if not ids:
        return 0
    return db.execute(
        "UPDATE agrupamento_registro SET status = %s, atualizado_em = now(), atualizado_por = %s"
        " WHERE id = ANY(%s)",
        (status, usuario["id"], list(ids)),
    )

