from flask import Blueprint, current_app, flash, g, render_template, request

from app import db
from app.security import login_required
from app.models import importacao as importacao_model

bp = Blueprint("importacao", __name__, url_prefix="/importacao")


@bp.route("/", methods=["GET", "POST"])
@login_required
def pagina():
    resultado = None
    arquivo_nome = None
    status_http = 200
    if request.method == "POST":
        arquivo = request.files.get("arquivo")
        if arquivo is None or not arquivo.filename:
            flash("Selecione um arquivo para importar.", "erro")
            status_http = 400
        else:
            arquivo_nome = arquivo.filename
            try:
                resultado = importacao_model.importar(arquivo.filename, arquivo.read(), g.user)
            except importacao_model.ArquivoInvalido as exc:
                db.rollback()
                flash(str(exc), "erro")
                status_http = 400
            except Exception:
                db.rollback()
                current_app.logger.exception("Falha na importação de %s", arquivo.filename)
                flash("Erro inesperado ao processar o arquivo. Nenhum registro foi importado.", "erro")
                status_http = 500
    return render_template(
        "importacao/pagina.html",
        resultado=resultado,
        arquivo_nome=arquivo_nome,
        historico=importacao_model.ultimas_importacoes(),
    ), status_http
