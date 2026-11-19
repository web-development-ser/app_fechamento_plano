import hashlib
import os
from pathlib import Path

from flask import Flask, render_template

from app import db
from app.config import Config
from app.security import csrf_token, load_current_user, verify_csrf


def calcular_versao(app):
    """Hash do conteúdo de static/ + templates/: muda a cada deploy com alteração de tela/JS,
    o que força a atualização automática do PWA (service worker novo) e dos arquivos em cache."""
    h = hashlib.sha256()
    raiz = Path(app.root_path) / "views"
    for pasta in ("static", "templates"):
        for arq in sorted((raiz / pasta).rglob("*")):
            if arq.is_file():
                h.update(str(arq.relative_to(raiz)).encode())
                h.update(arq.read_bytes())
    return h.hexdigest()[:12]


def create_app(overrides=None):
    app = Flask(__name__, template_folder="views/templates", static_folder="views/static")
    app.config.from_object(Config)
    if overrides:
        app.config.update(overrides)
    if not app.config.get("SECRET_KEY"):
        raise RuntimeError("SECRET_KEY não definido no .env")
    if not app.config.get("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL não definido no .env")
    # arquivos temporários da pré-visualização de importação
    app.config.setdefault("UPLOAD_DIR", os.environ.get("UPLOAD_DIR") or os.path.join(app.instance_path, "uploads"))

    app.config.setdefault("APP_VERSION", os.environ.get("APP_VERSION") or calcular_versao(app))

    if app.config.get("TRUST_PROXY"):
        from werkzeug.middleware.proxy_fix import ProxyFix

        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)

    db.init_app(app)
    app.before_request(verify_csrf)
    app.before_request(load_current_user)
    app.jinja_env.globals["csrf_token"] = csrf_token
    from app.models.mapeamento import descrever_local

    app.jinja_env.filters["local"] = descrever_local  # 'EST' -> 'Estoque'
    from app.controllers.pwa import asset

    app.jinja_env.globals["asset"] = asset

    from app.controllers import admin, atendimento, auth, consulta, dashboard, importacao, mapeamentos, pwa

    app.register_blueprint(auth.bp)
    app.register_blueprint(admin.bp)
    app.register_blueprint(atendimento.bp)
    app.register_blueprint(importacao.bp)
    app.register_blueprint(mapeamentos.bp)
    app.register_blueprint(consulta.bp)
    app.register_blueprint(dashboard.bp)
    app.register_blueprint(pwa.bp)

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
