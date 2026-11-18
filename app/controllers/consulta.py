"""Consulta pública de itens (somente leitura, sem login): mostra se cada item foi atendido."""
import math

from flask import Blueprint, current_app, render_template, request, url_for

from app.controllers.atendimento import ler_filtros
from app.models import registro as registro_model

bp = Blueprint("consulta", __name__, url_prefix="/consulta")


@bp.route("/")
def lista():
    filtros = ler_filtros(request.args, status_padrao="todos")
    pagina = max(request.args.get("pagina", 1, type=int) or 1, 1)
    tamanho = current_app.config["PAGE_SIZE"]
    registros, total = registro_model.listar(filtros, tamanho, (pagina - 1) * tamanho)
    return render_template(
        "consulta/lista.html",
        publico=True,
        registros=registros,
        total=total,
        resumo=registro_model.resumo(filtros),
        pagina=pagina,
        paginas=max(math.ceil(total / tamanho), 1),
        filtros=filtros,
        filtros_ocultos_ativos=any(filtros[k] for k in ("doc", "equipto", "dt_solic")),
        status_opcoes=registro_model.STATUS_OPCOES,
        setores=registro_model.SETORES,
        setor_de=registro_model.setor_de,
        args_base={k: v for k, v in request.args.items() if k != "pagina"},
    )


@bp.route("/<int:registro_id>")
def detalhe(registro_id):
    """Detalhes do item (somente leitura, sem login)."""
    from flask import abort

    from app.models import mapeamento as mapeamento_model

    r = registro_model.buscar_detalhe(registro_id)
    if r is None:
        abort(404)
    voltar = request.args.get("voltar") or url_for("consulta.lista")
    if not voltar.startswith("/") or voltar.startswith("//"):
        voltar = url_for("consulta.lista")
    mapeamento = mapeamento_model.buscar_ultimo(r["prog_orig"], r["doc_orig"])
    return render_template(
        "consulta/detalhe.html",
        publico=True,
        r=r,
        mapeamento=mapeamento,
        setor=registro_model.setor_de(r["equipto"]),
        descrever_turno=mapeamento_model.descrever_turno,
        fuso=mapeamento_model.FUSO,
        voltar=voltar,
    )
