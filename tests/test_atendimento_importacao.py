import io
from datetime import datetime

from openpyxl import Workbook

from tests.conftest import csrf

CAB = ["Lote", "Programa", "Item", "Descrição", "Prog.Orig.", "Doc.Orig.", "Dt.Solic",
       "QtdReposicao", "MotivoRepos", "Desc MotivoRepos", "Equipto", "Gestor"]


def _linha(prog, item, orig=100, doc=1, equip="EQ1"):
    return [1, prog, item, "Desc", orig, doc, datetime(2026, 11, 13), 10, 762, "Qtd", equip, "Gestor"]


def _xlsx(linhas):
    wb = Workbook()
    for l in linhas:
        wb.active.append(l)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _importar(client, conteudo, nome="rel.xlsx"):
    return client.post("/importacao/", data={
        "_csrf": csrf(client), "arquivo": (io.BytesIO(conteudo), nome)},
        content_type="multipart/form-data")


def test_importacao_novos_existentes_e_erros(app, admin_client):
    arquivo = _xlsx([CAB, _linha(1, "A"), _linha(1, "B"), _linha(1, "A"),  # duplicado no arquivo
                     [1, None, "C", "", 1, 1, None, 1, None, None, None, None]])  # sem programa
    r = _importar(admin_client, arquivo)
    html = r.get_data(as_text=True)
    assert r.status_code == 200 and "inconsistências" in html

    from app import db
    with app.app_context():
        imp = db.query_one("SELECT * FROM importacoes ORDER BY id DESC LIMIT 1")
        assert (imp["total"], imp["novos"], imp["existentes"], imp["erros"]) == (4, 2, 1, 1)

    # reimportação não duplica
    _importar(admin_client, _xlsx([CAB, _linha(1, "A"), _linha(1, "B"), _linha(2, "A")]))
    with app.app_context():
        imp = db.query_one("SELECT * FROM importacoes ORDER BY id DESC LIMIT 1")
        assert (imp["novos"], imp["existentes"], imp["erros"]) == (1, 2, 0)
        assert db.query_one("SELECT count(*) n FROM agrupamento_registro")["n"] == 3


def test_importacao_arquivo_invalido(app, admin_client):
    r = _importar(admin_client, _xlsx([["Lote", "Programa"], [1, 2]]))
    assert r.status_code == 400 and "Colunas obrigatórias ausentes" in r.get_data(as_text=True)
    r = _importar(admin_client, b"abc", nome="x.txt")
    assert r.status_code == 400


def test_lista_padrao_status_vazio_e_filtros(app, admin_client):
    _importar(admin_client, _xlsx([CAB, _linha(10, "SKU1"), _linha(20, "SKU2", equip="ZZ9")]))
    from app import db
    with app.app_context():
        db.execute("UPDATE agrupamento_registro SET status = 'Finalizado' WHERE item = 'SKU2'")
        db.commit()
    html = admin_client.get("/atendimento/").get_data(as_text=True)
    assert "SKU1" in html and "SKU2" not in html
    html = admin_client.get("/atendimento/?status=todos&equipto=zz9").get_data(as_text=True)
    assert "SKU2" in html and "SKU1" not in html
    html = admin_client.get("/atendimento/?item=nao-existe").get_data(as_text=True)
    assert "Nenhum registro encontrado para os filtros selecionados." in html


def test_salvar_atendimento(app, admin_client):
    _importar(admin_client, _xlsx([CAB, _linha(10, "SKU1")]))
    token = csrf(admin_client)
    base = {"_csrf": token, "dt_recebimento": "2026-11-13T08:30", "loc_tegad": "Z99",
            "resp_ts7": "sergio", "narrativa": "ok", "status": "Agrupado"}

    r = admin_client.post("/atendimento/1", data={**base, "resp_ts7": "x" * 151})
    assert "Resp. TS7 deve ter no máximo" in r.get_data(as_text=True)

    r = admin_client.post("/atendimento/1", data=base)
    assert r.status_code == 302
    from app import db
    with app.app_context():
        reg = db.query_one("SELECT * FROM agrupamento_registro WHERE id = 1")
        assert reg["status"] == "Agrupado" and reg["resp_ts7"] == "sergio"  # texto livre
        assert reg["loc_tegad"] is None  # somente leitura: valor do formulário ignorado
        assert reg["pessoa_resp_tegad"] == "Admin" and reg["atualizado_por"] == 1
        assert db.query_one("SELECT count(*) n FROM auditoria WHERE acao = 'atender_item'")["n"] == 1
    # deixa de aparecer na lista padrão (status vazio)
    assert "SKU1" not in admin_client.get("/atendimento/").get_data(as_text=True)


def test_registro_inexistente_404(admin_client):
    assert admin_client.get("/atendimento/999").status_code == 404
