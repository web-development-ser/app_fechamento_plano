from tests.conftest import criar_usuario, csrf, login


def test_rota_protegida_redireciona_para_login(client):
    r = client.get("/atendimento/")
    assert r.status_code == 302 and "/login" in r.headers["Location"]


def test_login_valido_e_invalido(app, client):
    criar_usuario(app, "ana", "segredo1", "USUARIO")
    assert login(client, "ana", "errada").status_code == 401
    r = login(client, "ANA", "segredo1")  # login sem diferenciar maiúsculas
    assert r.status_code == 302
    assert client.get("/atendimento/").status_code == 200


def test_usuario_inativo_nao_entra(app, client):
    criar_usuario(app, "bia", "segredo1", "USUARIO", ativo=False)
    r = login(client, "bia", "segredo1")
    assert r.status_code == 401
    assert "inativo" in r.get_data(as_text=True)


def test_post_sem_csrf_rejeitado(client):
    assert client.post("/login", data={"usuario": "x", "senha": "y"}).status_code == 400


def test_usuario_comum_nao_acessa_admin(app, client):
    criar_usuario(app, "ana", "segredo1", "USUARIO")
    login(client, "ana", "segredo1")
    assert client.get("/admin/usuarios").status_code == 403


def test_admin_cria_edita_redefine_e_desativa(app, admin_client):
    token = csrf(admin_client)
    r = admin_client.post("/admin/usuarios/novo", data={
        "_csrf": token, "nome": "Carlos Souza", "usuario": "carlos", "perfil": "USUARIO",
        "senha": "abc123", "confirmacao": "abc123"})
    assert r.status_code == 302

    from app import db
    with app.app_context():
        u = db.query_one("SELECT * FROM usuarios WHERE usuario = 'carlos'")
        assert u["senha_hash"] != "abc123" and u["criado_por"] is not None
        uid = u["id"]

    # duplicidade
    r = admin_client.post("/admin/usuarios/novo", data={
        "_csrf": token, "nome": "Outro", "usuario": "CARLOS", "perfil": "USUARIO",
        "senha": "abc123", "confirmacao": "abc123"})
    assert "Já existe" in r.get_data(as_text=True)

    admin_client.post(f"/admin/usuarios/{uid}", data={
        "_csrf": token, "nome": "Carlos S.", "usuario": "carlos.s", "perfil": "USUARIO"})
    admin_client.post(f"/admin/usuarios/{uid}/senha", data={
        "_csrf": token, "senha": "nova123", "confirmacao": "nova123"})
    admin_client.post(f"/admin/usuarios/{uid}/status", data={"_csrf": token})

    with app.app_context():
        u = db.query_one("SELECT * FROM usuarios WHERE id = %s", (uid,))
        assert u["nome"] == "Carlos S." and u["usuario"] == "carlos.s" and u["ativo"] is False
        acoes = [r["acao"] for r in db.query(
            "SELECT acao FROM auditoria WHERE entidade_id = %s ORDER BY id", (str(uid),))]
        assert acoes == ["criar_usuario", "editar_usuario", "redefinir_senha", "desativar_usuario"]

    # senha nunca aparece na interface
    assert "senha_hash" not in admin_client.get(f"/admin/usuarios/{uid}").get_data(as_text=True)


def test_admin_nao_desativa_a_si_mesmo(app, admin_client):
    token = csrf(admin_client)
    admin_client.post("/admin/usuarios/1/status", data={"_csrf": token})
    from app import db
    with app.app_context():
        assert db.query_one("SELECT ativo FROM usuarios WHERE id = 1")["ativo"] is True


def test_sessao_derrubada_ao_desativar(app, client):
    uid = criar_usuario(app, "ana", "segredo1", "USUARIO")
    login(client, "ana", "segredo1")
    from app import db
    from app.models import usuario as usuarios
    with app.app_context():
        usuarios.definir_ativo(uid, False, uid)
        db.commit()
    assert client.get("/atendimento/").status_code == 302
