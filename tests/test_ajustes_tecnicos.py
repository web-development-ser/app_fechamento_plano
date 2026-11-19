"""Ajustes técnicos: filtro de última modificação, novos status, filtros das caixas em Interrompidos, HTTPS."""
from tests.conftest import csrf
from tests.test_atendimento_importacao import CAB, _importar, _linha, _xlsx


# ---------- Atendimento: SKU sai, Última modificação entra ----------

def test_filtro_sku_removido_e_ultima_modificacao_no_lugar(app, admin_client):
    _importar(admin_client, _xlsx([CAB, _linha(1, "SKU1"), _linha(1, "SKU2"), _linha(1, "SKU3")]))
    html = admin_client.get("/atendimento/").get_data(as_text=True)
    assert 'name="item"' not in html and "Item (SKU)</label>" not in html
    assert 'name="dt_modificacao"' in html and 'type="date"' in html

    # salva o atendimento de 1 item hoje (sem status, continua na lista padrão)
    admin_client.post("/atendimento/2", data={"_csrf": csrf(admin_client), "narrativa": "conferido"})
    from app.models.mapeamento import agora
    hoje = agora().date().isoformat()
    html = admin_client.get(f"/atendimento/?dt_modificacao={hoje}").get_data(as_text=True)
    assert "SKU2" in html and "SKU1" not in html and "SKU3" not in html
    html = admin_client.get("/atendimento/?dt_modificacao=2020-01-01").get_data(as_text=True)
    assert "Nenhum registro encontrado" in html
    assert admin_client.get("/atendimento/?dt_modificacao=invalida").status_code == 200


# ---------- novos status ----------

def test_novos_status_floco_ps7_sala_de_cortes(app, admin_client):
    _importar(admin_client, _xlsx([CAB, _linha(1, "A"), _linha(1, "B"), _linha(1, "C")]))
    html = admin_client.get("/atendimento/1").get_data(as_text=True)
    for st in ("Floco", "PS7", "Sala de Cortes"):
        assert f"<option >{st}</option>" in html or f">{st}</option>" in html
    token = csrf(admin_client)
    for rid, st in ((1, "Floco"), (2, "PS7"), (3, "Sala de Cortes")):
        assert admin_client.post(f"/atendimento/{rid}", data={"_csrf": token, "status": st}).status_code == 302
    from app import db
    with app.app_context():
        assert [r["status"] for r in db.query("SELECT status FROM agrupamento_registro ORDER BY id")] == \
            ["Floco", "PS7", "Sala de Cortes"]
    # aparecem no filtro do Atendimento e no gráfico do Turno
    assert "B" in admin_client.get("/atendimento/?status=PS7").get_data(as_text=True)
    turno = admin_client.get("/dashboard/?data=").get_data(as_text=True)
    for st in ("Floco", "PS7", "Sala de Cortes"):
        assert f'<th scope="row">{st}</th>' in turno


def test_novos_status_nao_retiram_caixa_da_vaga(app, admin_client):
    _importar(admin_client, _xlsx([CAB, _linha(1, "A", orig=321, doc=1)]))
    admin_client.post("/mapeamentos/", data={"_csrf": csrf(admin_client), "programa": "321", "documento": "1", "vaga": "M03"})
    admin_client.post("/atendimento/1", data={"_csrf": csrf(admin_client), "status": "Sala de Cortes"})
    from app import db
    with app.app_context():
        assert db.query_one("SELECT liberado_em FROM mapeamentos")["liberado_em"] is None


# ---------- Interrompidos: filtros Programa e Documento das caixas ----------

def _mapear(client, programa, documento, vaga):
    client.post("/mapeamentos/", data={"_csrf": csrf(client), "programa": programa, "documento": documento, "vaga": vaga})


def test_filtrar_caixas_por_programa_e_documento(app, admin_client):
    _mapear(admin_client, "326364", "9", "M01")
    _mapear(admin_client, "326364", "4", "M02")
    _mapear(admin_client, "299087", "9", "P01")
    html = admin_client.get("/mapeamentos/").get_data(as_text=True)
    assert 'name="f_programa"' in html and 'name="f_documento"' in html and "Caixas nas vagas (3)" in html

    html = admin_client.get("/mapeamentos/?f_programa=326364").get_data(as_text=True)
    assert "Caixas nas vagas (2 de 3)" in html and "299087" not in html.split("Caixas nas vagas")[1]
    html = admin_client.get("/mapeamentos/?f_programa=3263&f_documento=4").get_data(as_text=True)  # parcial + combinado
    assert "Caixas nas vagas (1 de 3)" in html
    html = admin_client.get("/mapeamentos/?f_documento=99").get_data(as_text=True)
    assert "Nenhuma caixa encontrada para o filtro." in html


# ---------- HTTPS para o PWA (Docker + Caddy) ----------

def test_proxy_https_reconhecido_quando_habilitado(app):
    """Com TRUST_PROXY, a aplicação atrás do Caddy enxerga a requisição como HTTPS."""
    from werkzeug.middleware.proxy_fix import ProxyFix

    from app import create_app
    app2 = create_app({"TESTING": True, "SECRET_KEY": "x", "DATABASE_URL": app.config["DATABASE_URL"],
                       "TRUST_PROXY": True})
    assert isinstance(app2.wsgi_app, ProxyFix)

    @app2.route("/_esquema")
    def _esquema():
        from flask import request
        return {"scheme": request.scheme, "seguro": request.is_secure, "ip": request.remote_addr}

    r = app2.test_client().get("/_esquema", headers={"X-Forwarded-Proto": "https", "X-Forwarded-For": "10.2.0.7"})
    assert r.get_json() == {"scheme": "https", "seguro": True, "ip": "10.2.0.7"}


def test_sem_trust_proxy_cabecalho_e_ignorado(app):
    """Sem proxy configurado, cabeçalhos X-Forwarded-* enviados pelo cliente não são confiáveis."""
    from werkzeug.middleware.proxy_fix import ProxyFix
    assert not isinstance(app.wsgi_app, ProxyFix)
