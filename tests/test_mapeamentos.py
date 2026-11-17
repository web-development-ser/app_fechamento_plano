from datetime import datetime

import pytest

from app.models import mapeamento as m
from tests.conftest import criar_usuario, csrf, login
from tests.test_atendimento_importacao import CAB, _importar, _linha, _xlsx


# ---------- regras puras (sem banco) ----------

@pytest.mark.parametrize("hora, turno", [
    ("05:24:59", None), ("05:25:00", 1), ("12:00:00", 1), ("15:14:59", 1),
    ("15:15:00", 2), ("23:59:59", 2), ("00:00:00", 2), ("00:47:59", 2),
    ("00:48:00", None), ("03:00:00", None),
])
def test_turno_por_horario(hora, turno):
    assert m.turno_de(datetime.fromisoformat(f"2026-11-17T{hora}")) == turno


def test_vagas_m_p_s_01_a_20():
    assert len(m.VAGAS) == 60
    assert m.VAGAS[0] == "M01" and m.VAGAS[19] == "M20" and m.VAGAS[-1] == "S20"
    assert "P10" in m.VAGAS and "M21" not in m.VAGAS


# ---------- integração ----------

def _mapear(client, programa="326364", documento="9", vaga="M01"):
    return client.post("/mapeamentos/", data={
        "_csrf": csrf(client), "programa": programa, "documento": documento, "vaga": vaga})


def test_cadastro_preenche_campos_automaticos_e_reserva_vaga(app, admin_client):
    r = _mapear(admin_client, " 326364 ", "9", "M01")
    assert r.status_code == 302
    from app import db
    with app.app_context():
        mp = db.query_one("SELECT * FROM mapeamentos")
        assert (mp["programa"], mp["documento"], mp["vaga"]) == ("326364", "9", "M01")
        assert mp["registrado_por"] == 1 and mp["usuario_nome"] == "Admin"
        assert mp["registrado_em"] is not None and mp["liberado_em"] is None
        assert mp["turno"] == m.turno_de(mp["registrado_em"].astimezone(m.FUSO))
        assert db.query_one("SELECT count(*) n FROM auditoria WHERE acao='criar_mapeamento'")["n"] == 1
    html = admin_client.get("/mapeamentos/").get_data(as_text=True)
    assert 'value="M01"' in html and "1/7" in html  # vaga continua disponível (1 de 7 caixas)


def test_vaga_comporta_ate_7_caixas(app, admin_client):
    for i in range(7):
        assert _mapear(admin_client, f"10{i}", "1", "P05").status_code == 302
    html = admin_client.get("/mapeamentos/").get_data(as_text=True)
    assert 'value="P05"' not in html and 'value="P06"' in html  # lotada some da seleção
    r = _mapear(admin_client, "200", "2", "P05")
    assert r.status_code == 400 and "lotada (7 caixas)" in r.get_data(as_text=True)
    from app import db
    with app.app_context():
        assert db.query_one("SELECT count(*) n FROM mapeamentos WHERE vaga='P05'")["n"] == 7


def test_validacoes_e_programa_documento_duplicado(app, admin_client):
    _mapear(admin_client, "1", "1", "P05")
    r = _mapear(admin_client, "1", "1", "P06")
    assert r.status_code == 400 and "Já existe mapeamento ativo" in r.get_data(as_text=True)
    r = _mapear(admin_client, "3", "3", "X01")
    assert r.status_code == 400 and "vaga" in r.get_data(as_text=True)
    r = _mapear(admin_client, "", "", "S01")
    assert "Programa é obrigatório" in r.get_data(as_text=True)


def test_banco_impede_oitava_caixa_mesmo_sem_validacao_da_tela(app):
    """A trigger da migration 003 garante o limite mesmo se a checagem da tela for contornada."""
    criar_usuario(app)
    from app import db
    user = {"id": 1, "nome": "Admin"}
    with app.app_context():
        for i in range(7):
            m.criar(f"1{i}", "1", "S20", user)
        db.commit()
        with pytest.raises(m.VagaIndisponivel):
            m.criar("99", "1", "S20", user)


def test_limite_de_7_com_acessos_simultaneos(app):
    """Duas conexões tentando a 7ª caixa ao mesmo tempo: só uma entra."""
    import threading

    from app.db import connect
    criar_usuario(app)
    user = {"id": 1, "nome": "Admin"}
    from app import db
    with app.app_context():
        for i in range(6):
            m.criar(f"5{i}", "1", "M20", user)
        db.commit()

    dsn = app.config["DATABASE_URL"]
    resultados, barreira = [], threading.Barrier(2)

    def tentar(prog):
        with connect(dsn) as conn:
            barreira.wait()
            try:
                conn.execute(
                    "INSERT INTO mapeamentos (programa, documento, vaga, registrado_por, usuario_nome)"
                    " VALUES (%s, '1', 'M20', 1, 'Admin')", (prog,))
                conn.commit()
                resultados.append("ok")
            except Exception as exc:  # noqa: BLE001
                resultados.append(type(exc).__name__)

    ts = [threading.Thread(target=tentar, args=(p,)) for p in ("A1", "A2")]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert sorted(resultados) == ["CheckViolation", "ok"]


def test_atendimento_localiza_mapeamento_e_libera_vaga(app, admin_client):
    _importar(admin_client, _xlsx([CAB, _linha(354271, "SKU1", orig=326364, doc=9)]))
    _mapear(admin_client, "326364", "9", "M07")

    # lista e tela de atendimento mostram a vaga (PROCV Prog. Orig./Doc.)
    assert "M07" in admin_client.get("/atendimento/").get_data(as_text=True)
    html = admin_client.get("/atendimento/1").get_data(as_text=True)
    assert 'id="loc_tegad" value="M07" readonly' in html
    assert "Reservada" in html

    token = csrf(admin_client)
    # salvar sem status não libera a vaga, mas grava Loc. TEGAD
    admin_client.post("/atendimento/1", data={"_csrf": token, "resp_ts7": "sergio"})
    from app import db
    with app.app_context():
        assert db.query_one("SELECT loc_tegad FROM agrupamento_registro WHERE id=1")["loc_tegad"] == "M07"
        assert db.query_one("SELECT liberado_em FROM mapeamentos")["liberado_em"] is None

    # salvar com status libera a vaga
    r = admin_client.post("/atendimento/1", data={"_csrf": token, "status": "Disponível", "loc_tegad": "S01"},
                          follow_redirects=True)
    assert "Caixa retirada da vaga M07" in r.get_data(as_text=True)
    with app.app_context():
        mp = db.query_one("SELECT * FROM mapeamentos")
        assert mp["liberado_em"] is not None and mp["registro_id"] == 1 and mp["liberado_por"] == 1
        reg = db.query_one("SELECT loc_tegad FROM agrupamento_registro WHERE id=1")
        assert reg["loc_tegad"] == "M07"  # mantém histórico, ignora valor enviado
    assert 'value="M07"' in admin_client.get("/mapeamentos/").get_data(as_text=True)  # vaga livre de novo
    # mesma combinação pode ser mapeada novamente após a liberação
    assert _mapear(admin_client, "326364", "9", "M08").status_code == 302


def test_atendimento_sem_mapeamento(app, admin_client):
    _importar(admin_client, _xlsx([CAB, _linha(1, "SKU9", orig=555, doc=1)]))
    html = admin_client.get("/atendimento/1").get_data(as_text=True)
    assert "Nenhum mapeamento encontrado" in html and "Sem mapeamento" in html
    r = admin_client.post("/atendimento/1", data={"_csrf": csrf(admin_client), "status": "Finalizado"})
    assert r.status_code == 302


def test_liberacao_manual_somente_admin(app, client):
    criar_usuario(app)
    criar_usuario(app, "ana", "segredo1", "USUARIO")
    login(client, "ana", "segredo1")
    assert _mapear(client, "1", "1", "M01").status_code == 302  # usuário comum cadastra
    assert client.post("/mapeamentos/1/liberar", data={"_csrf": csrf(client)}).status_code == 403


def test_status_que_nao_liberam_mantem_a_caixa(app, admin_client):
    _importar(admin_client, _xlsx([CAB, _linha(1, "SKU1", orig=777, doc=1)]))
    _mapear(admin_client, "777", "1", "S03")
    token = csrf(admin_client)
    for status in ("Agrupado", "Barberan", "3DB"):
        admin_client.post("/atendimento/1", data={"_csrf": token, "status": status})
    from app import db
    with app.app_context():
        assert db.query_one("SELECT liberado_em FROM mapeamentos")["liberado_em"] is None
    r = admin_client.post("/atendimento/1", data={"_csrf": token, "status": "Finalizado"}, follow_redirects=True)
    assert "Caixa retirada da vaga S03" in r.get_data(as_text=True)


def test_caixa_so_sai_quando_todos_os_itens_do_programa_concluidos(app, admin_client):
    # dois itens com o mesmo Prog. Orig. + Doc. (caso real do relatório TOTVS)
    _importar(admin_client, _xlsx([CAB, _linha(1, "SKU1", orig=310715, doc=4), _linha(1, "SKU2", orig=310715, doc=4)]))
    _mapear(admin_client, "310715", "4", "M02")
    token = csrf(admin_client)
    r = admin_client.post("/atendimento/1", data={"_csrf": token, "status": "Disponível"}, follow_redirects=True)
    assert "1 item(ns) do mesmo programa/documento ainda pendente(s)" in r.get_data(as_text=True)
    from app import db
    with app.app_context():
        assert db.query_one("SELECT liberado_em FROM mapeamentos")["liberado_em"] is None
    r = admin_client.post("/atendimento/2", data={"_csrf": token, "status": "Finalizado"}, follow_redirects=True)
    assert "Caixa retirada da vaga M02" in r.get_data(as_text=True)
    with app.app_context():
        mp = db.query_one("SELECT * FROM mapeamentos")
        assert mp["liberado_em"] is not None and mp["registro_id"] == 2
