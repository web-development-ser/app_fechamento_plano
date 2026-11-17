# CLAUDE.md — TEGAD / App Fechamento Plano

Aplicação web para controle de atendimento de itens de reposição (relatório TOTVS WGCP344C).

## Fonte de verdade
- Requisitos originais: `.claude/regras_iniciais/*.md` (não editar sem autorização).
- Requisitos consolidados por módulo/camada MVC + decisões assumidas: `.claude/specs/SPEC.md`.
- Arquitetura MVC e regras das camadas: `.claude/specs/ARCHITECTURE.md`.
- Não alterar regras de negócio sem autorização do usuário.

## Arquitetura (MVC)
- `app/models/` dados + regras de negócio (SQL) · `app/controllers/` rotas/Blueprints · `app/views/` templates + static.
- Controller não tem SQL; model não conhece request; view não tem regra de negócio.

## Stack
Python 3.14 · Flask · PostgreSQL (psycopg 3) · HTML/CSS/JS puro (Jinja2) · ícones Lucide · pytest.

## Comandos
```bash
python -m venv .venv && .venv/Scripts/python -m pip install -r requirements.txt
cp .env.example .env                          # preencher DATABASE_URL e SECRET_KEY
.venv/Scripts/python -m scripts.setup_db --test # cria os bancos (se faltar) + tabelas; idempotente
.venv/Scripts/python -m scripts.init_db        # só aplica migrations pendentes (banco já existente)
.venv/Scripts/python -m scripts.create_admin   # cria o primeiro administrador
.venv/Scripts/python run.py                    # http://localhost:5001
.venv/Scripts/python -m pytest                 # testes (exige TEST_DATABASE_URL)
```

## Regras técnicas (obrigatórias)
1. Configurações e credenciais somente no `.env` — nunca no código ou nos logs.
2. SQL sempre parametrizado (`%s` / `%(nome)s`), nunca concatenado.
3. Senhas apenas com hash (`werkzeug.security`), nunca exibidas.
4. Toda operação de escrita registra usuário + data/hora (`auditoria` e colunas `*_por/*_em`).
5. Duplicidade evitada no banco (UNIQUE) e na aplicação.
6. Sem operações destrutivas no banco (DROP/TRUNCATE/DELETE em massa) sem autorização explícita.
   Exceção: o banco de **teste** (`TEST_DATABASE_URL`) é recriado pelos testes.
7. Não sobrescrever arquivos existentes sem ler o conteúdo antes.

## Metodologia
Para cada funcionalidade: analisar spec → identificar arquivos → implementar pequeno incremento →
criar/atualizar testes → rodar `pytest` → corrigir → documentar (`.claude/specs/SPEC.md` "Status" / README).
Concluída = implementada + testada + documentada.

## Design
Tema Facebook claro, mobile first, sem rolagem horizontal. Tokens em `app/views/static/css/app.css` (`:root`).
Detalhes em `.claude/regras_iniciais/desing.md`.

## Deploy
`docker compose up -d --build` → porta 5001, gunicorn, banco externo via `.env`. Detalhes no README.
