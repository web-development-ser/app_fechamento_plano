from flask import Flask, render_template

from app import db
from app.config import Config
from app.security import csrf_token, load_current_user, verify_csrf


def create_app(overrides=None):
    app = Flask(__name__, template_folder="views/templates", static_folder="views/static")
    app.config.from_object(Config)
    if overrides:
        app.config.update(overrides)
    if not app.config.get("SECRET_KEY"):
        raise RuntimeError("SECRET_KEY não definido no .env")
    if not app.config.get("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL não definido no .env")

    db.init_app(app)
    app.before_request(verify_csrf)
    app.before_request(load_current_user)
    app.jinja_env.globals["csrf_token"] = csrf_token

    from app.controllers import admin, atendimento, auth, importacao

    app.register_blueprint(auth.bp)
    app.register_blueprint(admin.bp)
    app.register_blueprint(atendimento.bp)
    app.register_blueprint(importacao.bp)

    @app.errorhandler(400)
    @app.errorhandler(403)
    @app.errorhandler(404)
    @app.errorhandler(413)
    def erro_http(e):
        mensagens = {
            403: "Acesso restrito a administradores.",
            404: "Página ou registro não encontrado.",
            413: "Arquivo maior que o limite permitido.",
        }
        msg = mensagens.get(e.code) or e.description
        return render_template("erro.html", codigo=e.code, mensagem=msg), e.code

    @app.errorhandler(500)
    def erro_interno(_e):
        app.logger.exception("Erro interno")
        return render_template("erro.html", codigo=500, mensagem="Erro interno. Tente novamente."), 500

    return app
