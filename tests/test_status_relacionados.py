"""Spec 10: aplicar o status somente ao item atual ou a todos os relacionados (mesmo Prog. Orig. + Doc.)."""
from tests.conftest import csrf
from tests.test_atendimento_importacao import CAB, _importar, _linha, _xlsx


def _dados(client):
    # ids 1, 2, 3: mesmo Prog. Orig. 310715 + Doc. 4 | id 4: mesmo Prog. Orig., outro Doc. | id 5: outro programa
    _importar(client, _xlsx([CAB,
                             _linha(1, "REL1", orig=310715, doc=4),
                             _linha(1, "REL2", orig=310715, doc=4),
                             _linha(2, "REL3", orig=310715, doc=4),
                             _linha(1, "OUTRODOC", orig=310715, doc=5),
                             _linha(1, "OUTROPROG", orig=999999, doc=4)]))


def _status(app):
    from app import db
    with app.app_context():
        return {r["item"]: r["status"] for r in db.query("SELECT item, status FROM agrupamento_registro")}


def test_modal_aparece_com_itens_relacionados(app, admin_client):
    _dados(admin_client)
    html = admin_client.get("/atendimento/1").get_data(as_text=True)
    assert 'data-relacionados="2"' in html and 'id="modal-relacionados"' in html
    assert "A alteração de status deve ser aplicada somente a este item ou a todos os itens relacionados?" in html
    assert "Ver esses itens" in html and "Somente este item" in html and "Todos os itens (3)" in html
    lista = html.split("data-lista")[1].split("modal-acoes")[0]
    assert "REL2" in lista and "REL3" in lista          # relacionados aparecem em "Ver esses itens"
    assert "REL1" not in lista                          # o próprio item não entra na lista
    assert "OUTRODOC" not in lista and "OUTROPROG" not in lista  # sem correspondência ficam de fora


def test_sem_relacionados_salva_sem_modal(app, admin_client):
    _dados(admin_client)
    html = admin_client.get("/atendimento/5").get_data(as_text=True)  # OUTROPROG: único na combinação
    assert "data-relacionados" not in html and "modal-relacionados" not in html
    r = admin_client.post("/atendimento/5", data={"_csrf": csrf(admin_client), "status": "Floco"})
    assert r.status_code == 302 and _status(app)["OUTROPROG"] == "Floco"


def test_somente_este_item(app, admin_client):
    _dados(admin_client)
    admin_client.post("/atendimento/1", data={"_csrf": csrf(admin_client), "status": "Agrupado", "aplicar": "este"})
    st = _status(app)
    assert st["REL1"] == "Agrupado" and st["REL2"] is None and st["REL3"] is None


def test_sem_escolha_salva_somente_este_item(app, admin_client):
    """Sem JavaScript (campo 'aplicar' vazio) ou valor inválido: comportamento seguro = só este item."""
    _dados(admin_client)
    admin_client.post("/atendimento/1", data={"_csrf": csrf(admin_client), "status": "PS7"})
    admin_client.post("/atendimento/2", data={"_csrf": csrf(admin_client), "status": "PS7", "aplicar": "xyz"})
    st = _status(app)
    assert st["REL1"] == "PS7" and st["REL2"] == "PS7" and st["REL3"] is None


def test_todos_os_itens(app, admin_client):
    _dados(admin_client)
    admin_client.post("/atendimento/2", data={"_csrf": csrf(admin_client), "status": "Agrupado", "aplicar": "este"})
    r = admin_client.post("/atendimento/1", data={"_csrf": csrf(admin_client), "status": "Sala de Cortes",
                                                  "narrativa": "lote", "aplicar": "todos"}, follow_redirects=True)
    import html as html_lib
    texto = html_lib.unescape(r.get_data(as_text=True))  # aspas chegam escapadas (&#34;) no HTML
    assert 'Status "Sala de Cortes" aplicado também a 2 item(ns) relacionado(s).' in texto
    st = _status(app)
    assert st["REL1"] == st["REL2"] == st["REL3"] == "Sala de Cortes"
    assert st["OUTRODOC"] is None and st["OUTROPROG"] is None  # sem correspondência: intactos

    from app import db
    with app.app_context():
        # só o status é copiado; os demais campos do atendimento ficam no item atual
        rel = {r["item"]: r for r in db.query("SELECT * FROM agrupamento_registro")}
        assert rel["REL1"]["narrativa"] == "lote" and rel["REL3"]["narrativa"] is None
        assert rel["REL3"]["atualizado_por"] == 1 and rel["REL3"]["atualizado_em"] is not None
        aud = db.query("SELECT entidade_id, detalhes FROM auditoria WHERE acao = 'aplicar_status_relacionado'"
                       " ORDER BY entidade_id")
        assert [a["entidade_id"] for a in aud] == ["2", "3"]
        assert aud[0]["detalhes"]["antes"]["status"] == "Agrupado"
        assert aud[0]["detalhes"]["depois"]["status"] == "Sala de Cortes"
        assert aud[0]["detalhes"]["origem_registro_id"] == 1


def test_todos_com_finalizado_retira_a_caixa_da_vaga(app, admin_client):
    _dados(admin_client)
    admin_client.post("/mapeamentos/", data={"_csrf": csrf(admin_client), "programa": "310715",
                                             "documento": "4", "vaga": "S05"})
    r = admin_client.post("/atendimento/1", data={"_csrf": csrf(admin_client), "status": "Finalizado",
                                                  "aplicar": "todos"}, follow_redirects=True)
    assert "Caixa retirada da vaga S05" in r.get_data(as_text=True)  # nenhum item do programa ficou pendente
    from app import db
    with app.app_context():
        assert db.query_one("SELECT liberado_em FROM mapeamentos")["liberado_em"] is not None


def test_somente_este_com_finalizado_mantem_a_caixa(app, admin_client):
    _dados(admin_client)
    admin_client.post("/mapeamentos/", data={"_csrf": csrf(admin_client), "programa": "310715",
                                             "documento": "4", "vaga": "S06"})
    r = admin_client.post("/atendimento/1", data={"_csrf": csrf(admin_client), "status": "Finalizado",
                                                  "aplicar": "este"}, follow_redirects=True)
    assert "2 item(ns) do mesmo programa/documento ainda pendente(s)" in r.get_data(as_text=True)


def test_correspondencia_ignora_espacos_e_maiusculas(app, admin_client):
    _importar(admin_client, _xlsx([CAB, _linha(1, "X1", orig="ab12", doc="7"), _linha(1, "X2", orig=" AB12 ", doc="7")]))
    admin_client.post("/atendimento/1", data={"_csrf": csrf(admin_client), "status": "3DB", "aplicar": "todos"})
    st = _status(app)
    assert st["X1"] == "3DB" and st["X2"] == "3DB"
