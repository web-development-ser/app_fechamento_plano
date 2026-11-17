from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for

from app import db
from app.models import auditoria
from app.models import usuario as usuario_model

bp = Blueprint("auth", __name__)


def _destino_seguro(nxt):
    # só aceita caminhos internos (evita open redirect)
    if nxt and nxt.startswith("/") and not nxt.startswith("//"):
        return nxt
    return url_for("atendimento.lista")


@bp.route("/")
def index():
    if g.get("user"):
        return redirect(url_for("atendimento.lista"))
    return redirect(url_for("auth.login"))


@bp.route("/health")
def health():
    """Healthcheck do container: 200 se app e banco respondem, 503 caso contrário."""
    if db.ping():
        return {"status": "ok"}, 200
    return {"status": "erro", "banco": "indisponível"}, 503


@bp.route("/login", methods=["GET", "POST"])
def login():
    if g.get("user"):
        return redirect(url_for("atendimento.lista"))
    if request.method == "POST":
        usuario = request.form.get("usuario", "").strip()
        senha = request.form.get("senha", "")
        if not usuario or not senha:
            flash("Informe usuário e senha.", "erro")
            return render_template("login.html", usuario=usuario), 400
        user, erro = usuario_model.autenticar(usuario, senha)
        if user is None:
            flash(erro, "erro")
            return render_template("login.html", usuario=usuario), 401
        csrf = session.get("_csrf")
        session.clear()
        session["user_id"] = user["id"]
        if csrf:
            session["_csrf"] = csrf
        auditoria.registrar("login", "usuarios", user["id"], usuario=user)
        db.commit()
        return redirect(_destino_seguro(request.args.get("next")))
    return render_template("login.html", usuario="")


@bp.route("/logout", methods=["POST"])
def logout():
    if g.get("user"):
        auditoria.registrar("logout", "usuarios", g.user["id"])
        db.commit()
    session.clear()
    flash("Sessão encerrada.", "sucesso")
    return redirect(url_for("auth.login"))
