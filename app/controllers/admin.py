from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from app import db
from app.models import auditoria
from app.models import usuario as usuario_model
from app.security import admin_required

bp = Blueprint("admin", __name__, url_prefix="/admin")

SENHA_MIN = 6


def _validar_dados(form, user_id=None):
    nome = form.get("nome", "").strip()
    usuario = form.get("usuario", "").strip()
    perfil = form.get("perfil", "USUARIO")
    erros = []
    if not nome or len(nome) > 150:
        erros.append("Nome é obrigatório (máx. 150 caracteres).")
    if not usuario or len(usuario) > 60 or " " in usuario:
        erros.append("Usuário é obrigatório, sem espaços (máx. 60 caracteres).")
    elif usuario_model.usuario_existe(usuario, ignorar_id=user_id):
        erros.append("Já existe um usuário com essa identificação.")
    if perfil not in usuario_model.PERFIS:
        erros.append("Perfil inválido.")
    return {"nome": nome, "usuario": usuario, "perfil": perfil}, erros


def _validar_senha(senha, confirmacao):
    if len(senha) < SENHA_MIN:
        return f"A senha deve ter ao menos {SENHA_MIN} caracteres."
    if senha != confirmacao:
        return "A confirmação não confere com a senha."
    return None


def _usuario_ou_404(user_id):
    user = usuario_model.buscar_por_id(user_id)
    if user is None:
        abort(404)
    return user


@bp.route("/usuarios")
@admin_required
def usuarios():
    return render_template("admin/usuarios.html", usuarios=usuario_model.listar())


@bp.route("/usuarios/novo", methods=["GET", "POST"])
@admin_required
def novo_usuario():
    dados = {"nome": "", "usuario": "", "perfil": "USUARIO"}
    if request.method == "POST":
        dados, erros = _validar_dados(request.form)
        erro_senha = _validar_senha(request.form.get("senha", ""), request.form.get("confirmacao", ""))
        if erro_senha:
            erros.append(erro_senha)
        if not erros:
            novo_id = usuario_model.criar(
                dados["nome"], dados["usuario"], request.form["senha"], dados["perfil"], g.user["id"]
            )
            auditoria.registrar("criar_usuario", "usuarios", novo_id, dados)
            db.commit()
            flash(f"Usuário {dados['usuario']} cadastrado.", "sucesso")
            return redirect(url_for("admin.usuarios"))
        for e in erros:
            flash(e, "erro")
    return render_template("admin/usuario_form.html", dados=dados, novo=True)


@bp.route("/usuarios/<int:user_id>", methods=["GET", "POST"])
@admin_required
def editar_usuario(user_id):
    alvo = _usuario_ou_404(user_id)
    dados = alvo
    if request.method == "POST":
        dados, erros = _validar_dados(request.form, user_id=user_id)
        if user_id == g.user["id"] and dados["perfil"] != "ADMIN":
            erros.append("Você não pode remover seu próprio perfil de administrador.")
        if not erros:
            usuario_model.atualizar(user_id, dados["nome"], dados["usuario"], dados["perfil"], g.user["id"])
            antes = {k: alvo[k] for k in ("nome", "usuario", "perfil")}
            auditoria.registrar("editar_usuario", "usuarios", user_id, {"antes": antes, "depois": dados})
            db.commit()
            flash("Dados do usuário atualizados.", "sucesso")
            return redirect(url_for("admin.usuarios"))
        for e in erros:
            flash(e, "erro")
        dados = {**alvo, **dados}
    return render_template("admin/usuario_form.html", dados=dados, novo=False)


@bp.route("/usuarios/<int:user_id>/senha", methods=["POST"])
@admin_required
def redefinir_senha(user_id):
    alvo = _usuario_ou_404(user_id)
    erro = _validar_senha(request.form.get("senha", ""), request.form.get("confirmacao", ""))
    if erro:
        flash(erro, "erro")
        return redirect(url_for("admin.editar_usuario", user_id=user_id))
    usuario_model.redefinir_senha(user_id, request.form["senha"], g.user["id"])
    auditoria.registrar("redefinir_senha", "usuarios", user_id, {"usuario": alvo["usuario"]})
    db.commit()
    flash(f"Senha de {alvo['usuario']} redefinida.", "sucesso")
    return redirect(url_for("admin.usuarios"))


@bp.route("/usuarios/<int:user_id>/status", methods=["POST"])
@admin_required
def alternar_status(user_id):
    alvo = _usuario_ou_404(user_id)
    if user_id == g.user["id"]:
        flash("Você não pode desativar a própria conta.", "erro")
        return redirect(url_for("admin.usuarios"))
    novo = not alvo["ativo"]
    usuario_model.definir_ativo(user_id, novo, g.user["id"])
    auditoria.registrar("ativar_usuario" if novo else "desativar_usuario", "usuarios", user_id)
    db.commit()
    flash(f"Usuário {alvo['usuario']} {'ativado' if novo else 'desativado'}.", "sucesso")
    return redirect(url_for("admin.usuarios"))
