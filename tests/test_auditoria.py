import json
from datetime import date, datetime
from decimal import Decimal

from app.models.auditoria import serializar


def test_serializa_datas_e_decimais():
    dados = {"dt": datetime(2026, 11, 13, 8, 30), "d": date(2026, 11, 13), "q": Decimal("1.5"), "s": "Disponível"}
    assert json.loads(serializar(dados)) == {
        "dt": "2026-11-13T08:30:00", "d": "2026-11-13", "q": "1.5", "s": "Disponível"}
