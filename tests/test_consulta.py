from app.models.registro import setor_de
from tests.conftest import csrf
from tests.test_atendimento_importacao import CAB, _importar, _linha, _xlsx


def test_setor_pelo_prefixo_do_equipto():
    assert setor_de("S7S02") == "Serigrafia"
    assert setor_de("s7m10") == "Montagem"
    assert setor_de("S7P59") == "Pintura"
    assert setor_de("S7B01") is None and setor_de(None) is None


def _dados(app, admin_client):
    _importar(admin_client, _xlsx([CAB, _linha(1, "SERI1", equip="S7S02"), _linha(1, "MONT1", equip="S7M04"),
                                   _linha(1, "PINT1", equip="S7P59")]))
    admin_client.post("/atendimento/1", data={"_csrf": csrf(admin_client), "status": "Finalizado"})
    admin_client.post("/logout", data={"_csrf": csrf(admin_client)})


def test_consulta_publica_sem_login_mostra_situacao(app, admin_client):
    _dados(app, admin_client)
    anonimo = app.test_client()
    r = anonimo.get("/consulta/")
    html = r.get_data(as_text=True)
    assert r.status_code == 200
    assert "SERI1" in html and "MONT1" in html and "PINT1" in html  # padrão: todos
    assert "Atendido · Finalizado" in html and "Pendente" in html
    assert "Serigrafia" in html and "Entrar" in html
    assert 'name="_csrf"' not in html  # sem formulários de escrita
    # resumo
    assert "<b style=\"color:var(--ok)\">1</b>" in html and "<b style=\"color:var(--err)\">2</b>" in html


def test_filtros_setor_e_situacao(app, admin_client):
    _dados(app, admin_client)
    c = app.test_client()
    html = c.get("/consulta/?setor=S7M").get_data(as_text=True)
    assert "MONT1" in html and "SERI1" not in html and "PINT1" not in html
    html = c.get("/consulta/?status=atendidos").get_data(as_text=True)
    assert "SERI1" in html and "MONT1" not in html
    html = c.get("/consulta/?status=").get_data(as_text=True)  # pendentes
    assert "SERI1" not in html and "MONT1" in html and "PINT1" in html
    html = c.get("/consulta/?setor=XXX&status=invalido").get_data(as_text=True)  # valores inválidos ignorados
    assert "SERI1" in html and "MONT1" in html


def test_consulta_nao_permite_editar(app, admin_client):
    _dados(app, admin_client)
    c = app.test_client()
    assert c.get("/atendimento/1").status_code == 302  # edição exige login
    assert c.post("/consulta/", data={}).status_code in (400, 405)
