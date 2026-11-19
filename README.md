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
O banco PostgreSQL é externo (não sobe no compose). Sobem dois containers: `app` (Flask/gunicorn, interno) e
`proxy` (Caddy, HTTPS na porta 5001 — necessário para o PWA). No servidor:
```bash
cp .env.example .env        # preencher SECRET_KEY, DATABASE_URL e TEGAD_ENDERECOS
docker compose up -d --build
docker compose exec app python -m scripts.create_admin   # só na primeira vez
docker compose logs -f app proxy
```
- `.env`: `TEGAD_ENDERECOS=https://<ip-do-servidor>:5001` (vários endereços separados por vírgula, ex.: IP e nome).
- Acesso: `https://<ip-do-servidor>:5001`. Quem entrar por `http://` é redirecionado.
  Outra porta externa: `APP_PORT=8443 docker compose up -d` (ajuste também o `TEGAD_ENDERECOS`).

### Confiar no certificado (uma vez por aparelho) — obrigatório para instalar o app
O certificado é emitido por uma CA interna criada pelo Caddy. Baixe `https://<ip-do-servidor>:5001/tegad-ca.crt`
(o navegador vai avisar sobre o certificado nesse primeiro acesso; prossiga) e instale:
- **Android:** Configurações → Segurança → Criptografia e credenciais → Instalar certificado → *Certificado CA*.
- **iPhone/iPad:** abra o arquivo → Ajustes → Perfil baixado → Instalar; depois Ajustes → Geral → Sobre →
  Ajustes de Confiança de Certificados → ativar a CA "Caddy Local Authority".
- **Windows:** dois cliques no arquivo → Instalar certificado → Máquina local → *Autoridades de Certificação Raiz Confiáveis*.
- **macOS:** Acesso às Chaves → importar em *Sistema* → abrir o certificado → Confiar: *Sempre confiar*.

Depois disso, ao abrir `https://<ip-do-servidor>:5001` o navegador oferece **Instalar app** (Chrome/Edge: ícone na
barra de endereço ou menu ⋮ → Instalar; iPhone: Compartilhar → Adicionar à Tela de Início).
Não apague o volume `caddy_data`: ele guarda a CA; se for recriado, os aparelhos precisam instalar o novo certificado.

Teste rápido sem certificado (só para homologação, Chrome/Edge): `chrome://flags/#unsafely-treat-insecure-origin-as-secure`
→ adicionar `http://<ip>:5001` → reiniciar o navegador.
- Na inicialização o container aplica migrations pendentes (`RUN_MIGRATIONS=1`). Ele **não cria o banco**:
  se o banco ainda não existir, rode antes `python -m scripts.setup_db` (local ou `docker compose run --rm app python -m scripts.setup_db`).
- Healthcheck: `GET /health` → 200 (app + banco ok) ou 503.
- Servidor: gunicorn (2 workers × 4 threads, timeout 120 s); ajustável por `GUNICORN_WORKERS`, `GUNICORN_THREADS`, `GUNICORN_TIMEOUT`.
- Atualizar versão: `git pull && docker compose up -d --build`.
