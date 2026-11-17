"""Sessão, controle de acesso e proteção CSRF."""
import secrets
from functools import wraps

from flask import abort, flash, g, redirect, request, session, url_for

from app.models import usuario as usuario_model


def load_current_user():
    """Carrega o usuário da sessão a cada requisição; derruba sessão de usuário inativo/removido."""
    g.user = None
    user_id = session.get("user_id")
    if user_id is None or request.endpoint == "static":
        return
    user = usuario_model.buscar_por_id(user_id)
    if user is None or not user["ativo"]:
        session.clear()
        flash("Sessão encerrada: usuário inativo ou inexistente.", "erro")
        return
    g.user = user


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if g.get("user") is None:
            return redirect(url_for("auth.login", next=request.path))
        return view(*args, **kwargs)

    return wrapper


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapper(*args, **kwargs):
        if g.user["perfil"] != "ADMIN":
            abort(403)
        return view(*args, **kwargs)

    return wrapper


def csrf_token():
    token = session.get("_csrf")
    if token is None:
        token = secrets.token_urlsafe(32)
        session["_csrf"] = token
    return token


def verify_csrf():
    if request.method != "POST":
        return
    sent = request.form.get("_csrf") or request.headers.get("X-CSRF-Token")
    expected = session.get("_csrf")
    if not sent or not expected or not secrets.compare_digest(sent, expected):
        abort(400, description="Token de segurança inválido. Recarregue a página e tente novamente.")
