import math
from datetime import date, datetime

from flask import Blueprint, abort, current_app, flash, g, redirect, render_template, request, url_for

from app import db
from app.models import auditoria
from app.models import mapeamento as mapeamento_model
from app.models import registro as registro_model
from app.security import login_required

bp = Blueprint("atendimento", __name__, url_prefix="/atendimento")

FILTROS_TEXTO = ("programa", "prog_orig", "item", "doc", "equipto")
# campos editáveis pelo usuário (Loc. TEGAD vem do mapeamento, nunca do formulário)
CAMPOS_FORM = ("dt_recebimento", "resp_ts7", "narrativa", "status")
CAMPOS_ATENDIMENTO = CAMPOS_FORM + ("loc_tegad",)


def ler_filtros(args, status_padrao=""):
    filtros = {k: args.get(k, "").strip()[:60] for k in FILTROS_TEXTO}
    filtros["status"] = args.get("status", status_padrao)
    if filtros["status"] not in ("", "todos", "atendidos", *registro_model.STATUS_OPCOES):
        filtros["status"] = status_padrao
    filtros["setor"] = args.get("setor", "") if args.get("setor", "") in registro_model.SETORES else ""
    dt = args.get("dt_solic", "").strip()
    try:
        filtros["dt_solic"] = date.fromisoformat(dt) if dt else None
    except ValueError:
        filtros["dt_solic"] = None
    return filtros


def validar_atendimento(form):
    """Retorna (dados, erros). Campos vazios viram NULL. Loc. TEGAD é ignorado (somente leitura)."""
    erros = []
    dados = {k: (form.get(k) or "").strip() or None for k in CAMPOS_FORM}
    if dados["dt_recebimento"]:
        try:
            dados["dt_recebimento"] = datetime.fromisoformat(dados["dt_recebimento"])
        except ValueError:
            erros.append("Data e hora de recebimento inválida.")
    if dados["resp_ts7"] and len(dados["resp_ts7"]) > registro_model.RESP_TS7_MAX:
        erros.append(f"Resp. TS7 deve ter no máximo {registro_model.RESP_TS7_MAX} caracteres.")
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

    # PROCV: Prog. Orig. -> Programa, Doc. Orig. -> Documento
    mapeamento = mapeamento_model.buscar_ativo(registro["prog_orig"], registro["doc_orig"])

    if request.method == "POST":
        dados, erros = validar_atendimento(request.form)
        # Loc. TEGAD: vaga do mapeamento ativo; sem mapeamento, mantém o valor já gravado
        dados["loc_tegad"] = mapeamento["vaga"] if mapeamento else registro["loc_tegad"]
        if erros:
            for e in erros:
                flash(e, "erro")
            registro = {**registro, **dados}
        else:
            # a caixa sai da vaga quando este item fica Disponível/Finalizado e nenhum outro item
            # do mesmo Prog. Orig. + Doc. Orig. continua pendente
            liberar = False
            pendentes = 0
            if mapeamento is not None and mapeamento_model.status_libera(dados["status"]):
                pendentes = registro_model.contar_pendentes(
                    registro["prog_orig"], registro["doc_orig"],
                    mapeamento_model.STATUS_LIBERAM, ignorar_id=registro_id)
                liberar = pendentes == 0
            try:
                registro_model.salvar_atendimento(registro_id, dados, g.user)
                antes = {k: registro[k] for k in CAMPOS_ATENDIMENTO}
                auditoria.registrar(
                    "atender_item", "agrupamento_registro", registro_id,
                    {"antes": antes, "depois": dados},
                )
                if liberar:
                    mapeamento_model.liberar(mapeamento["id"], g.user, registro_id)
                    auditoria.registrar(
                        "liberar_mapeamento", "mapeamentos", mapeamento["id"],
                        {"vaga": mapeamento["vaga"], "registro_id": registro_id},
                    )
                db.commit()
            except Exception:
                db.rollback()
                current_app.logger.exception("Falha ao salvar atendimento %s", registro_id)
                flash("Não foi possível salvar o atendimento. Tente novamente.", "erro")
            else:
                msg = "Atendimento salvo com sucesso."
                if mapeamento is not None:
                    est = mapeamento["vaga"] == mapeamento_model.ESTOQUE
                    de_local = "do Estoque" if est else f"da vaga {mapeamento['vaga']}"
                    no_local = "no Estoque" if est else f"na vaga {mapeamento['vaga']}"
                if liberar:
                    msg += f" Caixa retirada {de_local}."
                elif pendentes:
                    msg += (f" A caixa continua {no_local}: {pendentes} item(ns) do mesmo"
                            " programa/documento ainda pendente(s).")
                flash(msg, "sucesso")
                return redirect(url_for("atendimento.editar", registro_id=registro_id, voltar=voltar))

    if mapeamento is None:
        historico = mapeamento_model.buscar_ultimo(registro["prog_orig"], registro["doc_orig"])
    else:
        historico = mapeamento
    return render_template(
        "atendimento/editar.html",
        r=registro,
        voltar=voltar,
        mapeamento=historico,
        loc_tegad=mapeamento["vaga"] if mapeamento else registro["loc_tegad"],
        status_opcoes=registro_model.STATUS_OPCOES,
        descrever_turno=mapeamento_model.descrever_turno,
        fuso=mapeamento_model.FUSO,
    )
