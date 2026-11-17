from tests.conftest import criar_usuario, csrf, login


def _trocar(client, usuario="ana", atual="segredo1", nova="novaSenha1", confirmacao=None):
    return client.post("/senha", data={
        "_csrf": csrf(client), "usuario": usuario, "senha_atual": atual,
        "nova_senha": nova, "confirmacao": nova if confirmacao is None else confirmacao})


def test_pagina_acessivel_sem_login(client):
    html = client.get("/senha").get_data(as_text=True)
    assert "Senha atual" in html and "Nova senha" in html


def test_campos_obrigatorios(app, client):
    criar_usuario(app, "ana", "segredo1", "USUARIO")
    html = _trocar(client, usuario="", atual="", nova="").get_data(as_text=True)
    assert "Informe o usuário" in html and "Informe a senha atual" in html and "Informe a nova senha" in html


def test_credenciais_invalidas_bloqueiam(app, client):
    criar_usuario(app, "ana", "segredo1", "USUARIO")
    r = _trocar(client, atual="errada")
    assert r.status_code == 400 and "A senha não foi alterada" in r.get_data(as_text=True)
    r = _trocar(client, usuario="naoexiste")
    assert r.status_code == 400
    assert login(client, "ana", "segredo1").status_code == 302  # senha antiga intacta


def test_inativo_nao_altera(app, client):
    criar_usuario(app, "bia", "segredo1", "USUARIO", ativo=False)
    r = _trocar(client, usuario="bia")
    assert r.status_code == 400 and "inativo" in r.get_data(as_text=True)


def test_validacoes_da_nova_senha(app, client):
    criar_usuario(app, "ana", "segredo1", "USUARIO")
    assert "ao menos 6" in _trocar(client, nova="123").get_data(as_text=True)
    assert "não confere" in _trocar(client, confirmacao="outra123").get_data(as_text=True)
    assert "diferente da senha atual" in _trocar(client, nova="segredo1").get_data(as_text=True)


def test_troca_com_sucesso(app, client):
    uid = criar_usuario(app, "ana", "segredo1", "USUARIO")
    r = _trocar(client, nova="novaSenha1")
    assert r.status_code == 302 and "/login" in r.headers["Location"]

    from app import db
    with app.app_context():
        h = db.query_one("SELECT senha_hash FROM usuarios WHERE id = %s", (uid,))["senha_hash"]
        assert "novaSenha1" not in h and h.startswith(("scrypt:", "pbkdf2:"))
        assert db.query_one(
            "SELECT count(*) n FROM auditoria WHERE acao = 'alterar_propria_senha' AND usuario_id = %s", (uid,))["n"] == 1

    assert login(client, "ana", "segredo1").status_code == 401   # antiga não vale mais
    assert login(client, "ana", "novaSenha1").status_code == 302  # nova vale


def test_usuario_logado_volta_para_o_sistema(app, client):
    criar_usuario(app, "ana", "segredo1", "USUARIO")
    login(client, "ana", "segredo1")
    assert 'value="ana"' in client.get("/senha").get_data(as_text=True)  # usuário pré-preenchido
    r = _trocar(client)
    assert r.status_code == 302 and "/atendimento" in r.headers["Location"]
