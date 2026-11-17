"""Consulta pública de itens (somente leitura, sem login): mostra se cada item foi atendido."""
import math

from flask import Blueprint, current_app, render_template, request

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
