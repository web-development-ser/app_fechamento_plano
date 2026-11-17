"""Testes unitários do parser (sem banco)."""
import io
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from openpyxl import Workbook

from app.models import importacao as svc

AMOSTRA = Path(__file__).resolve().parent.parent / ".claude/regras_iniciais/pasta_excel/WGCP344C_SOLICITACOES.xlsx"


def _xlsx(linhas):
    wb = Workbook()
    ws = wb.active
    for l in linhas:
        ws.append(l)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


CAB = ["Lote", "Programa", "Item", "Descrição", "Prog.Orig.", "Doc.Orig.", "Dt.Solic",
       "QtdReposicao", "MotivoRepos", "Desc MotivoRepos", "Equipto", "Gestor"]


def test_normalizar_cabecalhos_equivalentes():
    assert svc.normalizar("Prog. Orig.") == svc.normalizar("Prog.Orig.") == "progorig"
    assert svc.normalizar("Descrição") == "descricao"
    assert svc.normalizar("Dt. Solic.") == svc.normalizar("Dt.Solic") == "dtsolic"
    assert svc.normalizar("DescriÃ§Ã£o") == "descricao"  # mojibake exportado pelo TOTVS
    assert svc.texto("SituaÃ§Ã£o") == "Situação"


def test_formato_nao_suportado():
    with pytest.raises(svc.ArquivoInvalido, match="Formato"):
        svc.ler_arquivo("relatorio.pdf", b"x")


def test_arquivo_vazio():
    with pytest.raises(svc.ArquivoInvalido, match="vazio"):
        svc.ler_arquivo("r.csv", b"")


def test_colunas_ausentes_informadas():
    with pytest.raises(svc.ArquivoInvalido) as exc:
        svc.mapear_cabecalho(["Lote", "Programa", "Item"])
    assert "Prog. Orig." in str(exc.value) and "Gestor" in str(exc.value)


def test_item_numerico_grande_vira_texto_sem_notacao():
    assert svc.texto(2729104140920250) == "2729104140920250"
    assert svc.texto(2729104140920250.0) == "2729104140920250"
    assert svc.texto("2361286CH4820280") == "2361286CH4820280"
    assert svc.texto("  ") is None


def test_conversao_data_e_quantidade():
    assert svc.data(datetime(2026, 11, 13)) == date(2026, 11, 13)
    assert svc.data("13/11/2026") == date(2026, 11, 13)
    assert svc.quantidade("1.234,5") == Decimal("1234.5")
    assert svc.quantidade(90) == Decimal("90")
    with pytest.raises(ValueError):
        svc.data("ontem")
    with pytest.raises(ValueError):
        svc.quantidade("abc")


def test_linha_sem_chave_gera_erro():
    mapa = svc.mapear_cabecalho(CAB)
    with pytest.raises(ValueError, match="campos-chave"):
        svc.converter_linha([1, None, "SKU", "d", 3, 4, None, 1, None, None, None, None], mapa)


def test_xlsx_com_colunas_extras_e_duplicadas():
    cab = ["Lote", "Ordem"] + CAB[1:] + ["Ordem"]
    linha = [701311, 999, 354271, 2729104140920250, "FORQ", 326364, 9, datetime(2026, 11, 13),
             90, 333, "Quantidade Full", "S7S02", None, 111]
    linhas = svc.ler_arquivo("r.xlsx", _xlsx([cab, linha]))
    mapa = svc.mapear_cabecalho(linhas[0])
    reg = svc.converter_linha(linhas[1], mapa)
    assert reg["programa"] == "354271"
    assert reg["item"] == "2729104140920250"
    assert reg["prog_orig"] == "326364" and reg["doc_orig"] == "9"
    assert reg["dt_solic"] == date(2026, 11, 13)
    assert reg["qtd_reposicao"] == Decimal("90")
    assert reg["gestor"] is None


def test_csv_ponto_e_virgula_cp1252():
    conteudo = (";".join(CAB) + "\n" + "1;10;SKU1;Descrição;20;3;13/11/2026;5;762;Qtd;EQ1;Ana\n").encode("cp1252")
    linhas = svc.ler_arquivo("r.csv", conteudo)
    reg = svc.converter_linha(linhas[1], svc.mapear_cabecalho(linhas[0]))
    assert reg["descricao"] == "Descrição" and reg["dt_solic"] == date(2026, 11, 13)


@pytest.mark.skipif(not AMOSTRA.exists(), reason="planilha de amostra ausente")
def test_planilha_real_do_totvs_e_valida():
    linhas = svc.ler_arquivo(AMOSTRA.name, AMOSTRA.read_bytes())
    mapa = svc.mapear_cabecalho(linhas[0])
    regs = [svc.converter_linha(l, mapa) for l in linhas[1:]]
    assert len(regs) == len(linhas) - 1 > 0
    assert all(r["programa"] and r["item"] for r in regs)
