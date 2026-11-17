# TEGAD — App Fechamento Plano

Controle de atendimento de itens de reposição importados do TOTVS (relatório WGCP344C).

Módulos: **Login/Usuários** (admin) · **Atendimento ao item** · **Geração e importação**.
Arquitetura MVC (`app/models`, `app/controllers`, `app/views`). Requisitos em `.claude/specs/SPEC.md`; arquitetura em `.claude/specs/ARCHITECTURE.md`; regras para o Claude Code em `CLAUDE.md`.

## Pré-requisitos
- Python 3.12+ (testado em 3.14)
- PostgreSQL 14+. O `setup_db` cria os bancos `app_fechameto_plano` e `app_fechameto_plano_test`
  (este é recriado a cada teste) se o usuário tiver permissão CREATEDB.

## Instalação
```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
cp .env.example .env            # editar SECRET_KEY, DATABASE_URL, TEST_DATABASE_URL
.venv/Scripts/python -m scripts.setup_db --test   # cria bancos (se faltar) e todas as tabelas
.venv/Scripts/python -m scripts.create_admin
.venv/Scripts/python run.py     # http://localhost:5001
```

## Testes
```bash
.venv/Scripts/python -m pytest -q
```
Sem `TEST_DATABASE_URL`, apenas os testes do parser de importação rodam; os de integração são pulados.

## Observações da importação
- Cabeçalhos são comparados de forma normalizada (`Prog.Orig.` ≡ `Prog. Orig.`).
- O TOTVS exporta acentos com mojibake (`DescriÃ§Ã£o`); o importador corrige automaticamente.
- Item (SKU) é sempre gravado como texto.

## Deploy no servidor (Docker)
O banco PostgreSQL é externo (não sobe no compose). No servidor:
```bash
cp .env.example .env        # preencher SECRET_KEY e DATABASE_URL (TEST_DATABASE_URL não é necessário)
docker compose up -d --build
docker compose exec app python -m scripts.create_admin   # só na primeira vez
docker compose logs -f app
```
- Acesso: `http://<ip-do-servidor>:5001` (outra porta: `APP_PORT=8080 docker compose up -d`).
- Na inicialização o container aplica migrations pendentes (`RUN_MIGRATIONS=1`). Ele **não cria o banco**:
  se o banco ainda não existir, rode antes `python -m scripts.setup_db` (local ou `docker compose run --rm app python -m scripts.setup_db`).
- Healthcheck: `GET /health` → 200 (app + banco ok) ou 503.
- Servidor: gunicorn (2 workers × 4 threads, timeout 120 s); ajustável por `GUNICORN_WORKERS`, `GUNICORN_THREADS`, `GUNICORN_TIMEOUT`.
- Atualizar versão: `git pull && docker compose up -d --build`.
