import io

from tests.conftest import criar_usuario, csrf, login
from tests.test_atendimento_importacao import CAB, _importar, _linha, _xlsx


def _previa(client, conteudo, nome="rel.xlsx"):
    return client.post("/importacao/", data={
        "_csrf": csrf(client), "acao": "previa", "arquivo": (io.BytesIO(conteudo), nome)},
        content_type="multipart/form-data")


def _token(client):
    with client.session_transaction() as s:
        return s["previa"]["token"]


def _contar(app, tabela):
    from app import db
    with app.app_context():
        return db.query_one(f"SELECT count(*) n FROM {tabela}")["n"]


def test_previa_classifica_sem_gravar_e_confirma(app, admin_client, tmp_path):
    app.config["UPLOAD_DIR"] = str(tmp_path)
    _importar(admin_client, _xlsx([CAB, _linha(1, "JA")]))  # já existente
    arquivo = _xlsx([CAB, _linha(1, "JA"), _linha(1, "NOVO1"), _linha(1, "NOVO1"),
                     [1, None, "X", "", 1, 1, None, 1, None, None, None, None]])

    r = _previa(admin_client, arquivo)
    html = r.get_data(as_text=True)
    assert r.status_code == 200 and "Prévia" in html and "Nada foi gravado" in html
    assert "NOVO1" in html and "campos-chave vazios" in html
    assert "Confirmar importação (1 novos)" in html
    assert _contar(app, "agrupamento_registro") == 1 and _contar(app, "importacoes") == 1

    token = _token(admin_client)
    assert (tmp_path / f"{token}.upload").exists()
    r = admin_client.post("/importacao/", data={"_csrf": csrf(admin_client), "acao": "confirmar", "token": token})
    assert r.status_code == 200 and "Novos importados" in r.get_data(as_text=True)
    assert _contar(app, "agrupamento_registro") == 2
    assert not (tmp_path / f"{token}.upload").exists()  # temporário removido

    # token reutilizado não importa de novo
    r = admin_client.post("/importacao/", data={"_csrf": csrf(admin_client), "acao": "confirmar", "token": token})
    assert r.status_code == 400 and "expirou" in r.get_data(as_text=True)


def test_previa_csv_e_arquivo_invalido(app, admin_client, tmp_path):
    app.config["UPLOAD_DIR"] = str(tmp_path)
    csv = (";".join(CAB) + "\n1;10;SKU1;Desc;20;3;13/11/2026;5;762;Qtd;EQ1;Ana\n").encode("utf-8")
    r = _previa(admin_client, csv, "rel.csv")
    assert r.status_code == 200 and "SKU1" in r.get_data(as_text=True)
    r = _previa(admin_client, b"pdf", "rel.pdf")
    assert r.status_code == 400 and "Formato não suportado" in r.get_data(as_text=True)


def test_previa_descartar_e_token_de_outro_usuario(app, client, tmp_path):
    app.config["UPLOAD_DIR"] = str(tmp_path)
    criar_usuario(app)
    login(client)
    _previa(client, _xlsx([CAB, _linha(5, "A")]))
    token = _token(client)

    # outro usuário não consegue confirmar a prévia alheia
    criar_usuario(app, "ana", "segredo1", "USUARIO")
    outro = app.test_client()
    login(outro, "ana", "segredo1")
    r = outro.post("/importacao/", data={"_csrf": csrf(outro), "acao": "confirmar", "token": token})
    assert r.status_code == 400 and _contar(app, "agrupamento_registro") == 0

    client.post("/importacao/", data={"_csrf": csrf(client), "acao": "cancelar"})
    assert not list(tmp_path.glob("*.upload"))


def test_token_invalido_nao_acessa_arquivos(tmp_path):
    from app.models import importacao as imp
    assert imp.carregar_temporario(tmp_path, "../../etc/passwd") is None
    assert imp.carregar_temporario(tmp_path, None) is None
