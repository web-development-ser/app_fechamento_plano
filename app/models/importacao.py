"""Leitura, validação e importação do relatório TOTVS (WGCP344C) para agrupamento_registro."""
import csv
import io
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from app import db
from app.models import auditoria

EXTENSOES = (".xlsx", ".csv")


class ArquivoInvalido(Exception):
    """Arquivo ilegível ou com estrutura incorreta (nenhuma linha é importada)."""


def corrigir_mojibake(s):
    """O TOTVS exporta texto UTF-8 lido como Latin-1 ('DescriÃ§Ã£o'). Reverte quando aplicável."""
    if "Ã" not in s and "Â" not in s:
        return s
    try:
        return s.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return s


def normalizar(nome):
    """'Prog. Orig.' / 'Prog.Orig.' / 'PROG ORIG' / 'DescriÃ§Ã£o' -> 'progorig' / 'descricao'."""
    if nome is None:
        return ""
    s = unicodedata.normalize("NFKD", corrigir_mojibake(str(nome))).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", s.lower())


# coluna da tabela -> (rótulo exibido, cabeçalho normalizado no arquivo)
COLUNAS = {
    "lote": ("Lote", "lote"),
    "programa": ("Programa", "programa"),
    "item": ("Item", "item"),
    "descricao": ("Descrição", "descricao"),
    "prog_orig": ("Prog. Orig.", "progorig"),
    "doc_orig": ("Doc. Orig.", "docorig"),
    "dt_solic": ("Dt. Solic.", "dtsolic"),
    "qtd_reposicao": ("QtdReposicao", "qtdreposicao"),
    "motivo_repos": ("MotivoRepos", "motivorepos"),
    "desc_motivo_repos": ("Desc MotivoRepos", "descmotivorepos"),
    "equipto": ("Equipto", "equipto"),
    "gestor": ("Gestor", "gestor"),
}
CHAVE = ("programa", "item", "prog_orig", "doc_orig")
TAMANHOS = {
    "lote": 50, "programa": 50, "item": 60, "descricao": 255, "prog_orig": 50, "doc_orig": 50,
    "motivo_repos": 30, "desc_motivo_repos": 255, "equipto": 50, "gestor": 150,
}


@dataclass
class Resultado:
    total: int = 0
    novos: int = 0
    existentes: int = 0
    erros: list = field(default_factory=list)  # [(linha, mensagem)]
    importacao_id: int | None = None
    avisos_precisao: int = 0

    @property
    def sucesso(self):
        return not self.erros


# ---------- leitura ----------

def _ler_xlsx(conteudo):
    from openpyxl import load_workbook

    try:
        wb = load_workbook(io.BytesIO(conteudo), read_only=True, data_only=True)
    except Exception as exc:
        raise ArquivoInvalido("Não foi possível ler o arquivo .xlsx.") from exc
    try:
        ws = wb.worksheets[0]
        return [list(r) for r in ws.iter_rows(values_only=True)]
    finally:
        wb.close()


def _ler_csv(conteudo):
    for enc in ("utf-8-sig", "cp1252"):
        try:
            texto = conteudo.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ArquivoInvalido("Codificação do CSV não reconhecida.")
    linhas_texto = texto.splitlines()
    primeira = linhas_texto[0].strip() if linhas_texto else ""
    # Excel/TOTVS gravam "sep=;" na 1ª linha como dica de separador: usa e descarta
    dica = re.fullmatch(r"sep=(.)", primeira, flags=re.IGNORECASE)
    if dica:
        delim = dica.group(1)
        texto = "\n".join(linhas_texto[1:])
    else:
        delim = ";" if primeira.count(";") >= primeira.count(",") else ","
    return [row for row in csv.reader(io.StringIO(texto), delimiter=delim)]


def ler_arquivo(nome_arquivo, conteudo):
    nome = (nome_arquivo or "").lower()
    if not nome.endswith(EXTENSOES):
        raise ArquivoInvalido("Formato não suportado. Envie um arquivo .xlsx ou .csv.")
    if not conteudo:
        raise ArquivoInvalido("O arquivo está vazio.")
    linhas = _ler_xlsx(conteudo) if nome.endswith(".xlsx") else _ler_csv(conteudo)
    # ignora linhas totalmente vazias
    linhas = [l for l in linhas if any(c not in (None, "") for c in l)]
    if not linhas:
        raise ArquivoInvalido("O arquivo não contém dados.")
    return linhas


def mapear_cabecalho(cabecalho):
    """Retorna {coluna_tabela: índice}. Usa a primeira ocorrência de cada cabeçalho."""
    indices = {}
    for i, h in enumerate(cabecalho):
        indices.setdefault(normalizar(h), i)
    faltando = [rot for col, (rot, norm) in COLUNAS.items() if norm not in indices]
    if faltando:
        raise ArquivoInvalido("Colunas obrigatórias ausentes: " + ", ".join(faltando) + ".")
    return {col: indices[norm] for col, (_rot, norm) in COLUNAS.items()}


# ---------- conversão de valores ----------

def texto(valor):
    if valor is None:
        return None
    if isinstance(valor, bool):
        return str(valor)
    if isinstance(valor, int):
        return str(valor)
    if isinstance(valor, float):
        return str(int(valor)) if valor.is_integer() else format(Decimal(str(valor)), "f")
    if isinstance(valor, (datetime, date)):
        return valor.strftime("%Y-%m-%d")
    s = corrigir_mojibake(str(valor).strip())
    return s or None


def data(valor):
    if valor in (None, ""):
        return None
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    s = str(valor).strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d/%m/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%d/%m/%y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"data inválida '{s}'")


def quantidade(valor):
    if valor in (None, ""):
        return None
    if isinstance(valor, (int, float, Decimal)) and not isinstance(valor, bool):
        return Decimal(str(valor))
    s = str(valor).strip()
    if "," in s:  # formato pt-BR: 1.234,5
        s = s.replace(".", "").replace(",", ".")
    try:
        return Decimal(s)
    except InvalidOperation:
        raise ValueError(f"quantidade inválida '{valor}'") from None


LIMITE_PRECISAO_EXCEL = 10 ** 15  # Excel guarda no máximo 15 dígitos significativos


def item_pode_ter_perdido_precisao(linha, mapa):
    """Item numérico com 16+ dígitos vindo do .xlsx: o Excel já arredondou o último dígito."""
    i = mapa["item"]
    valor = linha[i] if i < len(linha) else None
    return (isinstance(valor, (int, float)) and not isinstance(valor, bool)
            and abs(valor) >= LIMITE_PRECISAO_EXCEL)


def converter_linha(linha, mapa):
    def cel(col):
        i = mapa[col]
        return linha[i] if i < len(linha) else None

    reg = {}
    for col in COLUNAS:
        if col == "dt_solic":
            reg[col] = data(cel(col))
        elif col == "qtd_reposicao":
            reg[col] = quantidade(cel(col))
        else:
            v = texto(cel(col))
            if v and len(v) > TAMANHOS[col]:
                raise ValueError(f"{COLUNAS[col][0]} excede {TAMANHOS[col]} caracteres")
            reg[col] = v
    faltando = [COLUNAS[c][0] for c in CHAVE if not reg[c]]
    if faltando:
        raise ValueError("campos-chave vazios: " + ", ".join(faltando))
    return reg


# ---------- importação ----------

_INSERT = (
    "INSERT INTO agrupamento_registro ("
    + ", ".join(COLUNAS)
    + ", importacao_id, criado_por) VALUES ("
    + ", ".join(f"%({c})s" for c in COLUNAS)
    + ", %(importacao_id)s, %(criado_por)s)"
    " ON CONFLICT ON CONSTRAINT uq_agrupamento_chave DO NOTHING RETURNING id"
)


def importar(nome_arquivo, conteudo, usuario):
    """Lê, valida e importa. Levanta ArquivoInvalido se a estrutura for inválida."""
    linhas = ler_arquivo(nome_arquivo, conteudo)
    mapa = mapear_cabecalho(linhas[0])
    res = Resultado()

    imp = db.query_one(
        "INSERT INTO importacoes (arquivo_nome, importado_por) VALUES (%s, %s) RETURNING id",
        (nome_arquivo[:255], usuario["id"]),
    )
    res.importacao_id = imp["id"]

    conn = db.get_conn()
    for n, linha in enumerate(linhas[1:], start=2):  # n = linha no arquivo
        res.total += 1
        if item_pode_ter_perdido_precisao(linha, mapa):
            res.avisos_precisao += 1
        try:
            reg = converter_linha(linha, mapa)
        except ValueError as exc:
            res.erros.append((n, str(exc)))
            continue
        reg.update(importacao_id=res.importacao_id, criado_por=usuario["id"])
        try:
            with conn.transaction():  # savepoint: erro numa linha não derruba as demais
                novo = db.query_one(_INSERT, reg)
        except Exception as exc:  # noqa: BLE001 - registra e segue
            res.erros.append((n, f"erro ao gravar: {type(exc).__name__}"))
            continue
        if novo:
            res.novos += 1
        else:
            res.existentes += 1

    db.execute(
        "UPDATE importacoes SET total = %s, novos = %s, existentes = %s, erros = %s WHERE id = %s",
        (res.total, res.novos, res.existentes, len(res.erros), res.importacao_id),
    )
    auditoria.registrar(
        "importar_arquivo", "importacoes", res.importacao_id,
        {"arquivo": nome_arquivo, "total": res.total, "novos": res.novos,
         "existentes": res.existentes, "erros": len(res.erros)},
        usuario=usuario,
    )
    db.commit()
    return res


# ---------- pré-visualização (não grava nada) ----------

@dataclass
class Previa:
    total: int = 0
    novos: int = 0
    existentes: int = 0
    erros: int = 0
    linhas: list = field(default_factory=list)  # [{"n", "reg", "situacao", "msg"}]
    avisos_precisao: int = 0
    token: str | None = None  # arquivo guardado para confirmação

    @property
    def importaveis(self):
        return self.novos > 0


def _chaves_existentes(chaves):
    if not chaves:
        return set()
    colunas = list(zip(*chaves))
    rows = db.query(
        "SELECT programa, item, prog_orig, doc_orig FROM agrupamento_registro"
        " WHERE (programa, item, prog_orig, doc_orig) IN"
        " (SELECT * FROM unnest(%s::text[], %s::text[], %s::text[], %s::text[]))",
        [list(c) for c in colunas],
    )
    return {(r["programa"], r["item"], r["prog_orig"], r["doc_orig"]) for r in rows}


def analisar(nome_arquivo, conteudo):
    """Classifica cada linha (Novo / Já existe / Erro) sem gravar. Mesmas regras de importar()."""
    linhas = ler_arquivo(nome_arquivo, conteudo)
    mapa = mapear_cabecalho(linhas[0])
    previa = Previa()
    convertidas = []
    for n, linha in enumerate(linhas[1:], start=2):
        previa.total += 1
        if item_pode_ter_perdido_precisao(linha, mapa):
            previa.avisos_precisao += 1
        try:
            convertidas.append((n, converter_linha(linha, mapa), None))
        except ValueError as exc:
            convertidas.append((n, None, str(exc)))

    existentes = _chaves_existentes([tuple(r[c] for c in CHAVE) for _n, r, _e in convertidas if r])
    vistas = set()
    for n, reg, erro in convertidas:
        if erro:
            previa.erros += 1
            previa.linhas.append({"n": n, "reg": None, "situacao": "Erro", "msg": erro})
            continue
        chave = tuple(reg[c] for c in CHAVE)
        if chave in existentes or chave in vistas:
            previa.existentes += 1
            situacao = "Já existe"
        else:
            previa.novos += 1
            situacao = "Novo"
        vistas.add(chave)
        previa.linhas.append({"n": n, "reg": reg, "situacao": situacao, "msg": None})
    return previa


# ---------- arquivo temporário entre a prévia e a confirmação ----------

_TOKEN_RE = re.compile(r"^[a-f0-9]{32}$")
VALIDADE_PREVIA_S = 2 * 60 * 60


def guardar_temporario(pasta, conteudo):
    import secrets
    import time
    from pathlib import Path

    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    limite = time.time() - VALIDADE_PREVIA_S
    for antigo in pasta.glob("*.upload"):  # limpeza de prévias abandonadas
        try:
            if antigo.stat().st_mtime < limite:
                antigo.unlink()
        except OSError:
            pass
    token = secrets.token_hex(16)
    (pasta / f"{token}.upload").write_bytes(conteudo)
    return token


def carregar_temporario(pasta, token):
    from pathlib import Path

    if not token or not _TOKEN_RE.match(token):
        return None
    caminho = Path(pasta) / f"{token}.upload"
    return caminho.read_bytes() if caminho.exists() else None


def remover_temporario(pasta, token):
    from pathlib import Path

    if token and _TOKEN_RE.match(token):
        (Path(pasta) / f"{token}.upload").unlink(missing_ok=True)


def ultimas_importacoes(limite=10):
    return db.query(
        "SELECT i.*, u.nome AS usuario_nome FROM importacoes i"
        " JOIN usuarios u ON u.id = i.importado_por ORDER BY i.id DESC LIMIT %s",
        (limite,),
    )
