from flask import Blueprint, current_app, flash, g, render_template, request, session

from app import db
from app.models import importacao as importacao_model
from app.security import login_required

bp = Blueprint("importacao", __name__, url_prefix="/importacao")

LIMITE_LINHAS_PREVIA = 300


def _pasta():
    return current_app.config["UPLOAD_DIR"]


def _executar_importacao(nome, conteudo):
    try:
        return importacao_model.importar(nome, conteudo, g.user), 200
    except importacao_model.ArquivoInvalido as exc:
        db.rollback()
        flash(str(exc), "erro")
        return None, 400
    except Exception:
        db.rollback()
        current_app.logger.exception("Falha na importação de %s", nome)
        flash("Erro inesperado ao processar o arquivo. Nenhum registro foi importado.", "erro")
        return None, 500


@bp.route("/", methods=["GET", "POST"])
@login_required
def pagina():
    resultado = previa = None
    arquivo_nome = None
    status_http = 200
    acao = request.form.get("acao", "importar")

    if request.method == "POST" and acao == "confirmar":
        # importa o arquivo guardado na prévia
        dados = session.get("previa") or {}
        token = request.form.get("token")
        conteudo = None
        if token and dados.get("token") == token and dados.get("user_id") == g.user["id"]:
            conteudo = importacao_model.carregar_temporario(_pasta(), token)
        if conteudo is None:
            flash("A prévia expirou ou não foi encontrada. Envie o arquivo novamente.", "erro")
            status_http = 400
        else:
            arquivo_nome = dados["nome"]
            resultado, status_http = _executar_importacao(arquivo_nome, conteudo)
            importacao_model.remover_temporario(_pasta(), token)
            session.pop("previa", None)

    elif request.method == "POST" and acao == "cancelar":
        dados = session.pop("previa", None) or {}
        importacao_model.remover_temporario(_pasta(), dados.get("token"))
        flash("Prévia descartada.", "aviso")

    elif request.method == "POST":
        arquivo = request.files.get("arquivo")
        if arquivo is None or not arquivo.filename:
            flash("Selecione um arquivo .xlsx ou .csv.", "erro")
            status_http = 400
        else:
            arquivo_nome = arquivo.filename
            conteudo = arquivo.read()
            if acao == "previa":
                try:
                    previa = importacao_model.analisar(arquivo_nome, conteudo)
                except importacao_model.ArquivoInvalido as exc:
                    flash(str(exc), "erro")
                    status_http = 400
                else:
                    antiga = session.get("previa") or {}
                    importacao_model.remover_temporario(_pasta(), antiga.get("token"))
                    token = importacao_model.guardar_temporario(_pasta(), conteudo)
                    session["previa"] = {"token": token, "nome": arquivo_nome, "user_id": g.user["id"]}
                    previa.token = token
            else:
                resultado, status_http = _executar_importacao(arquivo_nome, conteudo)

    return render_template(
        "importacao/pagina.html",
        resultado=resultado,
        previa=previa,
        limite_previa=LIMITE_LINHAS_PREVIA,
        arquivo_nome=arquivo_nome,
        historico=importacao_model.ultimas_importacoes(),
    ), status_http
