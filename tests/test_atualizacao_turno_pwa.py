"""Testes da atualização: Estoque, Consulta (nomes/detalhes), filtro Prog. Orig., Dashboard e PWA."""
import json
import re

from tests.conftest import criar_usuario, csrf, login
from tests.test_atendimento_importacao import CAB, _importar, _linha, _xlsx


def _mapear(client, programa, documento, vaga="", estoque=False):
    dados = {"_csrf": csrf(client), "programa": programa, "documento": documento, "vaga": vaga}
    if estoque:
        dados["estoque"] = "1"
    return client.post("/mapeamentos/", data=dados)


# ---------- 1. Interrompidos: flag Estoque ----------

def test_flag_estoque_direciona_e_ignora_vaga(app, admin_client):
    r = _mapear(admin_client, "500", "1", vaga="M01", estoque=True)  # vaga enviada é ignorada
    assert r.status_code == 302
    from app import db
    with app.app_context():
        assert db.query_one("SELECT vaga FROM mapeamentos")["vaga"] == "EST"
    html = admin_client.get("/mapeamentos/").get_data(as_text=True)
    assert "Estoque" in html and "1 no Estoque" in html and "0 caixas nas vagas" in html
    assert 'data-bloqueia="#vagas-box"' in html  # checkbox bloqueia a seleção de vagas


def test_estoque_sem_limite_de_caixas(app, admin_client):
    for i in range(9):
        assert _mapear(admin_client, f"6{i}", "1", estoque=True).status_code == 302
    from app import db
    with app.app_context():
        assert db.query_one("SELECT count(*) n FROM mapeamentos WHERE vaga='EST'")["n"] == 9


def test_sem_vaga_e_sem_estoque_e_erro(app, admin_client):
    r = _mapear(admin_client, "700", "1")
    assert r.status_code == 400 and "ou marque Estoque" in r.get_data(as_text=True)


def test_estoque_no_atendimento_e_retirada(app, admin_client):
    _importar(admin_client, _xlsx([CAB, _linha(1, "SKU1", orig=800, doc=2)]))
    _mapear(admin_client, "800", "2", estoque=True)
    html = admin_client.get("/atendimento/1").get_data(as_text=True)
    assert 'id="loc_tegad" value="Estoque" readonly' in html
    r = admin_client.post("/atendimento/1", data={"_csrf": csrf(admin_client), "status": "Finalizado"},
                          follow_redirects=True)
    assert "Caixa retirada do Estoque" in r.get_data(as_text=True)


# ---------- 2. Consulta: Recebido por + Resp. TS7 + detalhes ----------

def test_consulta_mostra_recebido_por_resp_ts7_e_detalhes(app, client):
    criar_usuario(app, "maria", "segredo1", "ADMIN", nome="Maria Lima")
    criar_usuario(app, "joao", "segredo1", "USUARIO", nome="Joao Souza")
    login(client, "maria", "segredo1")
    _importar(client, _xlsx([CAB, _linha(1, "SKU1", orig=900, doc=3)]))
    _mapear(client, "900", "3", vaga="P01")
    client.post("/logout", data={"_csrf": csrf(client)})
    login(client, "joao", "segredo1")
    client.post("/atendimento/1", data={"_csrf": csrf(client), "status": "Agrupado", "narrativa": "ok",
                                         "resp_ts7": "sergio"})
    client.post("/logout", data={"_csrf": csrf(client)})

    anon = app.test_client()
    html = anon.get("/consulta/").get_data(as_text=True)
    assert "<th>Recebido por</th><th>Resp. TS7</th>" in html
    assert "Joao Souza" in html and "sergio" in html
    assert "Registrado por" not in html and "Maria Lima" not in html
    assert "/consulta/1" in html  # botão de detalhes
    det = anon.get("/consulta/1").get_data(as_text=True)
    assert "Registrado por" not in det
    assert "Recebido por" in det and "Joao Souza" in det and "sergio" in det and "P01" in det
    assert "Importado por" in det and 'name="_csrf"' not in det
    assert anon.get("/consulta/999").status_code == 404


# ---------- 3. Atendimento: filtro Programa Original junto com Programa ----------

def test_filtros_programa_e_programa_original_combinados(app, admin_client):
    _importar(admin_client, _xlsx([CAB, _linha(111, "A1", orig=555), _linha(111, "A2", orig=666),
                                   _linha(222, "A3", orig=555)]))
    html = admin_client.get("/atendimento/").get_data(as_text=True)
    assert 'name="prog_orig"' in html
    assert html.index('name="programa"') < html.index('name="prog_orig"') < html.index('name="item"')
    html = admin_client.get("/atendimento/?programa=111&prog_orig=555").get_data(as_text=True)
    assert "A1" in html and "A2" not in html and "A3" not in html
    html = admin_client.get("/atendimento/?prog_orig=555").get_data(as_text=True)
    assert "A1" in html and "A3" in html and "A2" not in html


# ---------- 4. Dashboard Troca de Turno ----------

def test_dashboard_exige_login(client):
    r = client.get("/dashboard/")
    assert r.status_code == 302 and "/login" in r.headers["Location"]


def _total(html):
    return int(re.search(r'<div class="stat hero"><b>(\d+)</b>', html).group(1))


def _qtd(html, status):
    m = re.search(r'<th scope="row">' + re.escape(status) + r"</th>.*?<strong>(\d+)</strong>", html, re.S)
    return int(m.group(1)) if m else None


def test_dashboard_contagens_e_filtros(app, client):
    criar_usuario(app, "maria", "segredo1", "ADMIN", nome="Maria")
    uid_joao = criar_usuario(app, "joao", "segredo1", "USUARIO", nome="Joao")
    login(client, "maria", "segredo1")
    _importar(client, _xlsx([CAB, _linha(1, "S1", equip="S7S01"), _linha(1, "S2", equip="S7S02"),
                             _linha(1, "M1", equip="S7M01"), _linha(1, "P1", equip="S7P01")]))
    client.post("/atendimento/1", data={"_csrf": csrf(client), "status": "Finalizado"})
    client.post("/logout", data={"_csrf": csrf(client)})
    login(client, "joao", "segredo1")
    client.post("/atendimento/3", data={"_csrf": csrf(client), "status": "Agrupado"})

    html = client.get("/dashboard/?data=2026-11-13&base=solicitacao").get_data(as_text=True)
    assert _total(html) == 4
    assert _qtd(html, "Não Atendimento") == 2 and _qtd(html, "Finalizado") == 1 and _qtd(html, "Agrupado") == 1
    assert _qtd(html, "3DB") == 0  # todos os status aparecem, mesmo zerados

    assert _total(client.get("/dashboard/?data=&setor=S7S").get_data(as_text=True)) == 2
    # usuário filtra os atendidos (1 do Joao); os 2 não atendidos continuam no total
    html_joao = client.get(f"/dashboard/?data=&usuario={uid_joao}").get_data(as_text=True)
    assert _qtd(html_joao, "Agrupado") == 1 and _qtd(html_joao, "Finalizado") == 0
    assert _qtd(html_joao, "Não Atendimento") == 2 and _total(html_joao) == 3
    assert _total(client.get("/dashboard/?data=&status=").get_data(as_text=True)) == 2  # pendentes
    assert _total(client.get("/dashboard/?data=&status=atendidos").get_data(as_text=True)) == 2
    vazio = client.get("/dashboard/?data=2020-01-01").get_data(as_text=True)
    assert _total(vazio) == 0
    # gráfico continua com todos os status, mesmo zerados
    for st in ("Não Atendimento", "Agrupado", "Disponível", "Finalizado", "Barberan", "3DB"):
        assert _qtd(vazio, st) == 0
    # filtrando um status, os demais aparecem zerados no gráfico
    so_agrupado = client.get("/dashboard/?data=&status=Agrupado").get_data(as_text=True)
    assert _qtd(so_agrupado, "Agrupado") == 1 and _qtd(so_agrupado, "Não Atendimento") == 0
    # data do atendimento = hoje (padrão): 2 atendidos hoje + 2 não atendidos em aberto = 4
    from app.models.mapeamento import agora
    hoje = agora().date().isoformat()
    turno = client.get(f"/dashboard/?data={hoje}&base=atendimento").get_data(as_text=True)
    assert _qtd(turno, "Não Atendimento") == 2 and _total(turno) == 4
    assert _total(client.get("/dashboard/").get_data(as_text=True)) == 4  # padrão = hoje + data do atendimento
    # data anterior à solicitação: nada atendido e nada em aberto ainda
    assert _total(client.get("/dashboard/?data=2026-11-12&base=atendimento").get_data(as_text=True)) == 0
    # valores inválidos são ignorados
    assert client.get("/dashboard/?data=xx&setor=ZZZ&status=nada&usuario=abc").status_code == 200


# ---------- 5. PWA ----------

def test_manifest_instalavel(client):
    r = client.get("/manifest.webmanifest")
    assert r.status_code == 200 and r.mimetype == "application/manifest+json"
    m = json.loads(r.get_data(as_text=True))
    assert m["display"] == "standalone" and m["start_url"].startswith("/") and m["short_name"] == "TEGAD"
    assert m["background_color"] and m["theme_color"]
    tamanhos = {(i["sizes"], i["purpose"]) for i in m["icons"]}
    assert ("192x192", "any") in tamanhos and ("512x512", "any") in tamanhos and ("512x512", "maskable") in tamanhos
    for icone in m["icons"]:
        assert client.get(icone["src"]).status_code == 200


def test_service_worker_e_precache(app, client):
    r = client.get("/sw.js")
    corpo = r.get_data(as_text=True)
    assert r.status_code == 200 and r.mimetype == "application/javascript"
    assert "no-cache" in r.headers["Cache-Control"] and r.headers["Service-Worker-Allowed"] == "/"
    assert app.config["APP_VERSION"] in corpo and "skipWaiting" in corpo and "clients.claim" in corpo
    precache = json.loads(corpo.split("const PRECACHE = ")[1].split(";\n")[0])
    assert "/offline" in precache and any("lucide.min.js" in u for u in precache)
    for url in precache:  # tudo o que o SW guarda precisa existir
        assert client.get(url).status_code == 200, url


def test_paginas_tem_manifest_icones_e_assets_versionados(app, client):
    html = client.get("/login").get_data(as_text=True)
    v = app.config["APP_VERSION"]
    assert 'rel="manifest"' in html and 'rel="apple-touch-icon"' in html and 'name="theme-color"' in html
    assert f"css/app.css?v={v}" in html and f"js/app.js?v={v}" in html
    assert "unpkg.com" not in html  # ícones servidos localmente (funciona sem internet externa)
    assert 'id="splash"' in html


def test_versao_muda_quando_arquivo_estatico_muda(tmp_path):
    from app import calcular_versao

    class Falso:
        root_path = str(tmp_path)

    (tmp_path / "views" / "static").mkdir(parents=True)
    (tmp_path / "views" / "templates").mkdir(parents=True)
    arq = tmp_path / "views" / "static" / "a.css"
    arq.write_text("a{}")
    v1 = calcular_versao(Falso)
    assert calcular_versao(Falso) == v1  # determinística
    arq.write_text("a{color:red}")
    assert calcular_versao(Falso) != v1


def test_pagina_offline(client):
    r = client.get("/offline")
    assert r.status_code == 200 and "Sem conexão" in r.get_data(as_text=True)


def test_status_em_branco_conta_como_nao_atendimento(app, admin_client):
    """Status '' ou só espaços (vindo de fora da aplicação) também é Não Atendimento."""
    _importar(admin_client, _xlsx([CAB, _linha(1, "B1"), _linha(1, "B2"), _linha(1, "B3")]))
    from app import db
    with app.app_context():
        # o CHECK do banco só aceita os 5 status ou NULL; simulamos o caso removendo-o temporariamente
        db.execute("ALTER TABLE agrupamento_registro DROP CONSTRAINT agrupamento_registro_status_check")
        db.execute("UPDATE agrupamento_registro SET status = '' WHERE item = 'B1'")
        db.execute("UPDATE agrupamento_registro SET status = '   ' WHERE item = 'B2'")
        db.commit()
    html = admin_client.get("/dashboard/?data=").get_data(as_text=True)
    assert _qtd(html, "Não Atendimento") == 3 and _total(html) == 3
