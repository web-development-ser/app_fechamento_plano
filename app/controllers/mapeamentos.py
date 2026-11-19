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
        "estoque": form.get("estoque") == "1",
    }
    # flag Estoque: direciona automaticamente e ignora qualquer vaga enviada
    if dados["estoque"]:
        dados["vaga"] = mapeamento_model.ESTOQUE
    erros = []
    if not dados["programa"] or len(dados["programa"]) > 50:
        erros.append("Programa é obrigatório (máx. 50 caracteres).")
    if not dados["documento"] or len(dados["documento"]) > 50:
        erros.append("Documento é obrigatório (máx. 50 caracteres).")
    if not dados["estoque"] and dados["vaga"] not in mapeamento_model.VAGAS:
        erros.append("Selecione uma vaga (Fila + Posição) válida ou marque Estoque.")
    elif mapeamento_model.vaga_lotada(dados["vaga"]):
        erros.append(f"A vaga {dados['vaga']} está lotada ({mapeamento_model.CAPACIDADE_VAGA} caixas). "
                     "Escolha outra.")
    return dados, erros


@bp.route("/", methods=["GET", "POST"])
@login_required
def pagina():
    dados = {"programa": "", "documento": "", "vaga": "", "estoque": False}
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
                destino = ("enviada para o Estoque" if gravado["vaga"] == mapeamento_model.ESTOQUE
                           else f"adicionada à vaga {gravado['vaga']}")
                flash(f"Caixa {destino}: Programa {gravado['programa']} / "
                      f"Doc. {gravado['documento']} ({mapeamento_model.descrever_turno(gravado['turno'])}).",
                      "sucesso")
                return redirect(url_for("mapeamentos.pagina"))
        for e in erros:
            flash(e, "erro")
        status_http = 400

    momento = mapeamento_model.agora()
    filtro = {k: request.args.get(f"f_{k}", "").strip()[:50] for k in ("programa", "documento")}
    ocup = mapeamento_model.ocupacao()
    livres = mapeamento_model.vagas_livres(ocup)
    return render_template(
        "mapeamentos/pagina.html",
        dados=dados,
        livres_por_fila={f: [v for v in livres if v[0] == f] for f in mapeamento_model.FILAS},
        total_livres=len(livres),
        total_vagas=len(mapeamento_model.VAGAS),
        ocupacao=ocup,
        capacidade=mapeamento_model.CAPACIDADE_VAGA,
        total_caixas=sum(n for v, n in ocup.items() if v != mapeamento_model.ESTOQUE),
        no_estoque=ocup.get(mapeamento_model.ESTOQUE, 0),
        ativos=mapeamento_model.listar_ativos(filtro["programa"], filtro["documento"]),
        filtro=filtro,
        filtro_ativo=bool(filtro["programa"] or filtro["documento"]),
        total_ativos=sum(ocup.values()),
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
    flash("Caixa retirada da vaga manualmente.", "sucesso")
    return redirect(url_for("mapeamentos.pagina"))
