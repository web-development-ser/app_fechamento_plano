"""Dashboard Troca de Turno: indicadores por status conforme filtros (somente usuários autenticados)."""
from datetime import date

from flask import Blueprint, render_template, request

from app.models import mapeamento as mapeamento_model
from app.models import registro as registro_model
from app.models import usuario as usuario_model
from app.security import login_required

bp = Blueprint("dashboard", __name__, url_prefix="/dashboard")

BASES_DATA = {"atendimento": "Data do atendimento", "solicitacao": "Data de solicitação"}


def ler_filtros(args):
    base = args.get("base", "atendimento")
    base = base if base in BASES_DATA else "atendimento"
    # data: padrão = hoje; "todas" (campo vazio enviado) = sem filtro de data
    bruto = args.get("data", None)
    if bruto is None:
        data = mapeamento_model.agora().date()
    else:
        try:
            data = date.fromisoformat(bruto) if bruto else None
        except ValueError:
            data = None
    status = args.get("status", "todos")
    if status not in ("todos", "", "atendidos", *registro_model.STATUS_OPCOES):
        status = "todos"
    setor = args.get("setor", "")
    setor = setor if setor in registro_model.SETORES else ""
    usuario = args.get("usuario", type=int)
    return {"base": base, "data": data, "status": status, "setor": setor, "usuario": usuario}


@bp.route("/")
@login_required
def pagina():
    f = ler_filtros(request.args)
    itens, total = registro_model.contagem_por_status({
        "status": f["status"], "setor": f["setor"], "usuario_id": f["usuario"],
        "data": f["data"], "base": f["base"],
    })
    maximo = max((i["n"] for i in itens), default=0)
    momento = mapeamento_model.agora()
    return render_template(
        "dashboard/pagina.html",
        filtros=f,
        itens=itens,
        total=total,
        maximo=maximo,
        atendidos=sum(i["n"] for i in itens if i["status"] != registro_model.NAO_ATENDIMENTO),
        nao_atendidos=next(i["n"] for i in itens if i["status"] == registro_model.NAO_ATENDIMENTO),
        bases=BASES_DATA,
        setores=registro_model.SETORES,
        status_opcoes=registro_model.STATUS_OPCOES,
        usuarios=usuario_model.listar(),
        agora=momento,
        turno_atual=mapeamento_model.descrever_turno(mapeamento_model.turno_de(momento)),
    )
