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


@bp.route("/senha", methods=["GET", "POST"])
def redefinir_senha():
    """Autoatendimento: troca a senha validando usuário + senha atual. Acessível com ou sem login."""
    usuario = g.user["usuario"] if g.get("user") else ""
    if request.method == "POST":
        usuario = request.form.get("usuario", "").strip()
        atual = request.form.get("senha_atual", "")
        nova = request.form.get("nova_senha", "")
        confirmacao = request.form.get("confirmacao", "")

        erros = []
        if not usuario:
            erros.append("Informe o usuário.")
        if not atual:
            erros.append("Informe a senha atual.")
        if not nova:
            erros.append("Informe a nova senha.")
        if not erros:
            user, erro = usuario_model.autenticar(usuario, atual)
            if user is None:
                erros.append("Usuário ou senha atual inválidos. A senha não foi alterada."
                             if "inativo" not in erro else erro)
            else:
                erro_nova = usuario_model.validar_nova_senha(nova, confirmacao)
                if erro_nova:
                    erros.append(erro_nova)
                elif nova == atual:
                    erros.append("A nova senha deve ser diferente da senha atual.")
        if erros:
            for e in erros:
                flash(e, "erro")
            return render_template("senha.html", usuario=usuario), 400

        usuario_model.redefinir_senha(user["id"], nova, user["id"])
        auditoria.registrar("alterar_propria_senha", "usuarios", user["id"], usuario=user)
        db.commit()
        flash("Senha alterada com sucesso. Use a nova senha nos próximos acessos.", "sucesso")
        if g.get("user") and g.user["id"] == user["id"]:
            return redirect(url_for("atendimento.lista"))
        return redirect(url_for("auth.login"))
    return render_template("senha.html", usuario=usuario)
