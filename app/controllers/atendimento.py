import math
from datetime import date, datetime

from flask import Blueprint, abort, current_app, flash, g, redirect, render_template, request, url_for

from app import db
from app.models import auditoria
from app.models import registro as registro_model
from app.security import login_required

bp = Blueprint("atendimento", __name__, url_prefix="/atendimento")

FILTROS_TEXTO = ("programa", "item", "doc", "equipto")
CAMPOS_ATENDIMENTO = ("dt_recebimento", "loc_tegad", "resp_ts7", "narrativa", "status")


def ler_filtros(args):
    filtros = {k: args.get(k, "").strip()[:60] for k in FILTROS_TEXTO}
    filtros["status"] = args.get("status", "")
    if filtros["status"] not in ("", "todos", *registro_model.STATUS_OPCOES):
        filtros["status"] = ""
    dt = args.get("dt_solic", "").strip()
    try:
        filtros["dt_solic"] = date.fromisoformat(dt) if dt else None
    except ValueError:
        filtros["dt_solic"] = None
    return filtros


def validar_atendimento(form):
    """Retorna (dados, erros). Campos vazios viram NULL."""
    erros = []
    dados = {k: (form.get(k) or "").strip() or None for k in CAMPOS_ATENDIMENTO}
    if dados["dt_recebimento"]:
        try:
            dados["dt_recebimento"] = datetime.fromisoformat(dados["dt_recebimento"])
        except ValueError:
            erros.append("Data e hora de recebimento inválida.")
    if dados["loc_tegad"] and dados["loc_tegad"] not in registro_model.LOC_TEGAD_OPCOES:
        erros.append("Loc. TEGAD inválido (use A a Z).")
    if dados["resp_ts7"]:
        dados["resp_ts7"] = dados["resp_ts7"].upper()
        if dados["resp_ts7"] not in registro_model.RESP_TS7_OPCOES:
            erros.append("Resp. TS7 inválido (use A1 a G10).")
    if dados["status"] and dados["status"] not in registro_model.STATUS_OPCOES:
        erros.append("Status inválido.")
    if dados["narrativa"] and len(dados["narrativa"]) > 2000:
        erros.append("Narrativa deve ter no máximo 2000 caracteres.")
    return dados, erros


@bp.route("/")
@login_required
def lista():
    filtros = ler_filtros(request.args)
    pagina = max(request.args.get("pagina", 1, type=int) or 1, 1)
    tamanho = current_app.config["PAGE_SIZE"]
    registros, total = registro_model.listar(filtros, tamanho, (pagina - 1) * tamanho)
    paginas = max(math.ceil(total / tamanho), 1)
    filtros_ocultos_ativos = any(filtros[k] for k in ("doc", "equipto", "dt_solic"))
    args_base = {k: v for k, v in request.args.items() if k != "pagina"}
    return render_template(
        "atendimento/lista.html",
        registros=registros,
        total=total,
        pagina=pagina,
        paginas=paginas,
        filtros=filtros,
        filtros_ocultos_ativos=filtros_ocultos_ativos,
        status_opcoes=registro_model.STATUS_OPCOES,
        args_base=args_base,
    )


@bp.route("/<int:registro_id>", methods=["GET", "POST"])
@login_required
def editar(registro_id):
    registro = registro_model.buscar(registro_id)
    if registro is None:
        abort(404)
    voltar = request.args.get("voltar") or url_for("atendimento.lista")
    if not voltar.startswith("/") or voltar.startswith("//"):
        voltar = url_for("atendimento.lista")

    if request.method == "POST":
        dados, erros = validar_atendimento(request.form)
        if erros:
            for e in erros:
                flash(e, "erro")
            registro = {**registro, **dados}
        else:
            try:
                registro_model.salvar_atendimento(registro_id, dados, g.user)
                antes = {k: registro[k] for k in CAMPOS_ATENDIMENTO}
                auditoria.registrar(
                    "atender_item", "agrupamento_registro", registro_id,
                    {"antes": antes, "depois": dados},
                )
                db.commit()
            except Exception:
                db.rollback()
                current_app.logger.exception("Falha ao salvar atendimento %s", registro_id)
                flash("Não foi possível salvar o atendimento. Tente novamente.", "erro")
            else:
                flash("Atendimento salvo com sucesso.", "sucesso")
                return redirect(url_for("atendimento.editar", registro_id=registro_id, voltar=voltar))

    return render_template(
        "atendimento/editar.html",
        r=registro,
        voltar=voltar,
        status_opcoes=registro_model.STATUS_OPCOES,
        loc_opcoes=registro_model.LOC_TEGAD_OPCOES,
        ts7_opcoes=registro_model.RESP_TS7_OPCOES,
    )
