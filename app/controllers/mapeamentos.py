from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from app import db
from app.models import auditoria
from app.models import mapeamento as mapeamento_model
from app.security import admin_required, login_required

bp = Blueprint("mapeamentos", __name__, url_prefix="/mapeamentos")


def _validar(form):
    dados = {
        "programa": mapeamento_model.normalizar_chave(form.get("programa")),
        "documento": mapeamento_model.normalizar_chave(form.get("documento")),
        "vaga": (form.get("vaga") or "").strip().upper(),
    }
    erros = []
    if not dados["programa"] or len(dados["programa"]) > 50:
        erros.append("Programa é obrigatório (máx. 50 caracteres).")
    if not dados["documento"] or len(dados["documento"]) > 50:
        erros.append("Documento é obrigatório (máx. 50 caracteres).")
    if dados["vaga"] not in mapeamento_model.VAGAS:
        erros.append("Selecione uma vaga (Fila + Posição) válida.")
    elif dados["vaga"] in mapeamento_model.vagas_ocupadas():
        erros.append(f"A vaga {dados['vaga']} não está livre. Escolha outra.")
    return dados, erros


@bp.route("/", methods=["GET", "POST"])
@login_required
def pagina():
    dados = {"programa": "", "documento": "", "vaga": ""}
    status_http = 200
    if request.method == "POST":
        dados, erros = _validar(request.form)
        if not erros:
            try:
                novo_id, gravado = mapeamento_model.criar(
                    dados["programa"], dados["documento"], dados["vaga"], g.user)
                auditoria.registrar("criar_mapeamento", "mapeamentos", novo_id, gravado)
                db.commit()
            except (mapeamento_model.VagaIndisponivel, mapeamento_model.MapeamentoDuplicado) as exc:
                db.rollback()
                erros.append(str(exc))
            else:
                flash(f"Vaga {gravado['vaga']} reservada para o Programa {gravado['programa']} / "
                      f"Doc. {gravado['documento']} ({mapeamento_model.descrever_turno(gravado['turno'])}).",
                      "sucesso")
                return redirect(url_for("mapeamentos.pagina"))
        for e in erros:
            flash(e, "erro")
        status_http = 400

    momento = mapeamento_model.agora()
    livres = mapeamento_model.vagas_livres()
    return render_template(
        "mapeamentos/pagina.html",
        dados=dados,
        livres_por_fila={f: [v for v in livres if v[0] == f] for f in mapeamento_model.FILAS},
        total_livres=len(livres),
        total_vagas=len(mapeamento_model.VAGAS),
        ativos=mapeamento_model.listar_ativos(),
        liberados=mapeamento_model.listar_liberados(),
        agora=momento,
        turno_atual=mapeamento_model.descrever_turno(mapeamento_model.turno_de(momento)),
        descrever_turno=mapeamento_model.descrever_turno,
    ), status_http


@bp.route("/<int:mapeamento_id>/liberar", methods=["POST"])
@admin_required
def liberar(mapeamento_id):
    """Liberação manual (correção de reserva errada) — somente administrador."""
    if not mapeamento_model.liberar(mapeamento_id, g.user):
        abort(404)
    auditoria.registrar("liberar_mapeamento_manual", "mapeamentos", mapeamento_id)
    db.commit()
    flash("Vaga liberada manualmente.", "sucesso")
    return redirect(url_for("mapeamentos.pagina"))
