"""Cria um usuário administrador (interativo). Uso: python -m scripts.create_admin"""
import getpass

from app import create_app, db
from app.models import usuario as usuarios


def main():
    app = create_app()
    with app.app_context():
        nome = input("Nome completo: ").strip()
        usuario = input("Usuário (login): ").strip()
        senha = getpass.getpass("Senha (mín. 6): ")
        if not nome or not usuario or len(senha) < 6:
            raise SystemExit("Dados inválidos.")
        if senha != getpass.getpass("Confirme a senha: "):
            raise SystemExit("As senhas não conferem.")
        if usuarios.usuario_existe(usuario):
            raise SystemExit("Já existe um usuário com essa identificação.")
        novo_id = usuarios.criar(nome, usuario, senha, "ADMIN")
        db.execute(
            "INSERT INTO auditoria (acao, entidade, entidade_id, usuario_nome)"
            " VALUES ('criar_admin_cli', 'usuarios', %s, 'script create_admin')",
            (str(novo_id),),
        )
        db.commit()
        print(f"Administrador '{usuario}' criado (id {novo_id}).")


if __name__ == "__main__":
    main()
