# SPEC — TEGAD / App Fechamento Plano

Consolidação de `.claude/regras_iniciais/`, organizada por módulo e por camada MVC.
Itens **[Assumido]** são decisões provisórias (pontos pendentes da spec original) a validar com a
equipe de Fechamento.

---

## M1 — Autenticação e gerenciamento de usuários
Origem: `regras_iniciais/1. login_administração.md`

### Model — `app/models/usuario.py`, `app/models/auditoria.py`
- Tabela `usuarios`: id, nome, usuario (único, sem diferenciar maiúsculas), senha_hash, perfil (`ADMIN`/`USUARIO`), ativo, criado/atualizado por/em.
- Senha armazenada apenas como hash (werkzeug); nunca retornada fora de `autenticar`.
- `autenticar` rejeita senha errada (mensagem genérica) e usuário inativo.
- Tabela `auditoria`: usuário, nome, ação, entidade, id, detalhes (JSONB), data/hora — toda operação de escrita registra.

### View — `app/views/templates/login.html`, `admin/usuarios.html`, `admin/usuario_form.html`
- Login: Usuário, Senha (botão mostrar/ocultar), aviso "procure o administrador".
- Lista de usuários (cartões no mobile, tabela no desktop) com perfil e status.
- Formulário de cadastro/edição e bloco separado de redefinição de senha (senha atual nunca exibida).

### Controller — `app/controllers/auth.py`, `app/controllers/admin.py`
- `/login`, `/logout`; redireciona só para caminhos internos.
- `/admin/usuarios…` exclusivo de ADMIN (403 para usuário comum).
- Sessão de usuário desativado é encerrada na próxima requisição.
- [Assumido] Senha mínima de 6 caracteres.
- [Assumido] Admin não pode desativar a si mesmo nem remover o próprio perfil ADMIN.

---

## M2 — Atendimento ao item
Origem: `regras_iniciais/2. interface_edição_view.md`

### Model — `app/models/registro.py`
- Tabela `agrupamento_registro` (dados TOTVS + campos de atendimento + rastreabilidade).
- Status vazio = `NULL`. Opções: Agrupado, Disponível, Finalizado, Barberan, 3DB (CHECK no banco).
- Loc. TEGAD: A–Z. Resp. TS7: A1–A10 … G1–G10 (CHECK no banco).
- Filtros com SQL parametrizado; paginação.

### View — `app/views/templates/atendimento/lista.html`, `atendimento/editar.html`
- Lista: ID, Programa, Item, Prog. Orig., Doc., Equipto, Dt. Solic., Qtd. Reposição + botão "Atender".
- Filtros visíveis: Programa, Item. Recolhíveis ("Mais filtros"): Documento, Equipamento, Data de Solicitação.
- Mensagem vazia: "Nenhum registro encontrado para os filtros selecionados."
- Tela de atendimento: Informações gerais (somente leitura) + formulário (Data/Hora de recebimento,
  Pessoa Resp. TEGAD = usuário atual, Loc. TEGAD, Resp. TS7 com pesquisa, Narrativa, Status).
- Mobile: cartões e campos em coluna; desktop: tabela e formulário em 3 colunas.

### Controller — `app/controllers/atendimento.py`
- Carrega por padrão status vazio; valida todos os campos antes de gravar.
- [Assumido] Filtro adicional de Status (padrão "Vazio", opção "Todos").
- [Assumido] Todos os perfis podem editar o atendimento.
- [Assumido] Salvamento manual (botão "Salvar") com mensagem de sucesso/erro; recarrega dados atualizados.
- [Assumido] Campos de atendimento opcionais; paginação de 50 registros.

---

## M3 — Geração e importação (TOTVS)
Origem: `regras_iniciais/03. importação.md`

### Model — `app/models/importacao.py`
- Lê `.xlsx` (1ª planilha) e `.csv` (`;` ou `,`, UTF-8 ou CP1252).
- Cabeçalhos normalizados (sem acento/espaço/ponto/caixa): `Prog.Orig.` ≡ `Prog. Orig.`.
- Corrige mojibake exportado pelo TOTVS (`DescriÃ§Ã£o` → `Descrição`).
- Colunas obrigatórias: Lote, Programa, Item, Descrição, Prog. Orig., Doc. Orig., Dt. Solic.,
  QtdReposicao, MotivoRepos, Desc MotivoRepos, Equipto, Gestor. Demais colunas ignoradas.
- Chave: Programa + Item + Prog. Orig. + Doc. Orig. (`UNIQUE` + `ON CONFLICT DO NOTHING`).
- Linha inválida (chave vazia, data/quantidade inválida) vira erro sem interromper as demais (savepoint).
- Item (SKU) sempre texto, sem notação científica.
- Tabela `importacoes` guarda o histórico (arquivo, totais, usuário, data/hora).

### View — `app/views/templates/importacao/pagina.html`
- Upload, lista de colunas obrigatórias, resumo (analisados, novos, existentes, erros com nº da linha),
  status geral (sucesso / inconsistências) e últimas importações.

### Controller — `app/controllers/importacao.py`
- Valida presença do arquivo; arquivo inválido → mensagem e nada é importado.
- [Assumido] Limite de 10 MB (`MAX_UPLOAD_MB`).

---

## Status de implementação
| Módulo | Status |
|---|---|
| Base (config, DB, migrations, setup_db, layout) | Concluído — testado (config, auditoria) |
| M1 Autenticação/Admin | Concluído — 8 testes de integração passando |
| M2 Atendimento | Concluído — testes de integração passando |
| M3 Importação | Concluído — parser (10, inclui planilha real) + integração passando |

Total: 25 testes passando no PostgreSQL (2026-11-13). Pendente: validar os itens [Assumido] com a equipe de Fechamento.
