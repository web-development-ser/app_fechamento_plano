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
- [Assumido] Senha mínima de 6 caracteres (regra única em `usuario.validar_nova_senha`).

### Redefinir senha (autoatendimento) — origem: `regras_iniciais/05. redefinir_senha.md`
- Tela `/senha` (`views/templates/senha.html`, controller `auth.redefinir_senha`), acessível pelo login e pelo cabeçalho.
- Campos: Usuário, Senha atual, Nova senha (+ Confirmar nova senha [Assumido], para evitar erro de digitação).
- Valida usuário + senha atual; credencial inválida ou usuário inativo → bloqueia com mensagem; nada é alterado.
- Sucesso: grava novo hash imediatamente, registra `alterar_propria_senha` na auditoria.
- [Assumido] Nova senha deve ser diferente da atual. Quem não lembra a senha atual continua usando a redefinição pelo admin.
- [Assumido] Admin não pode desativar a si mesmo nem remover o próprio perfil ADMIN.

---

## M2 — Atendimento ao item
Origem: `regras_iniciais/2. interface_edição_view.md`

### Model — `app/models/registro.py`
- Tabela `agrupamento_registro` (dados TOTVS + campos de atendimento + rastreabilidade).
- Status vazio = `NULL`. Opções: Agrupado, Disponível, Finalizado, Barberan, 3DB (CHECK no banco).
- Loc. TEGAD: vaga do mapeamento (M01…S20), preenchida pelo sistema — somente leitura (migration 002).
- Resp. TS7: texto livre, até 150 caracteres (ex.: "sergio") (migration 002).
- Filtros com SQL parametrizado; paginação.

### View — `app/views/templates/atendimento/lista.html`, `atendimento/editar.html`
- Lista: ID, Programa, Item, Prog. Orig., Doc., Equipto, Dt. Solic., Qtd. Reposição + botão "Atender".
- Filtros visíveis: Programa, Item. Recolhíveis ("Mais filtros"): Documento, Equipamento, Data de Solicitação.
- Mensagem vazia: "Nenhum registro encontrado para os filtros selecionados."
- Tela de atendimento: Informações gerais (somente leitura) + formulário (Data/Hora de recebimento,
  Pessoa Resp. TEGAD = usuário atual, Loc. TEGAD somente leitura, Resp. TS7 texto livre, Narrativa, Status).
- Painel "Mapeamento de programa interrompido": vaga, programa/documento, data, turno, usuário e situação.
- Lista mostra a coluna Loc. TEGAD (vaga do mapeamento ativo).
- Mobile: cartões e campos em coluna; desktop: tabela e formulário em 3 colunas.

### Controller — `app/controllers/atendimento.py`
- Carrega por padrão status vazio; valida todos os campos antes de gravar.
- Loc. TEGAD nunca vem do formulário: vaga do mapeamento ativo ou, sem mapeamento, o valor já gravado.
- Ao salvar com Status preenchido e mapeamento ativo, libera a vaga na mesma transação (ver M4).
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
- Botões **Visualizar Prévia** (padrão) e **Importar direto**.
- Prévia: totais (analisadas, serão importadas, já existentes, erros) + tabela (desktop) / cartões (mobile)
  com a situação de cada linha (Novo / Já existe / Erro); até 300 linhas exibidas, totais do arquivo inteiro.
  Botões **Confirmar importação** e **Descartar**. Nada é gravado antes da confirmação.
- Upload, lista de colunas obrigatórias, resumo (analisados, novos, existentes, erros com nº da linha),
  status geral (sucesso / inconsistências) e últimas importações.

### Controller — `app/controllers/importacao.py`
- Valida presença do arquivo; arquivo inválido → mensagem e nada é importado.
- [Assumido] Limite de 10 MB (`MAX_UPLOAD_MB`).
- Prévia guarda o arquivo em `UPLOAD_DIR` (padrão `instance/uploads`) com token aleatório ligado ao usuário
  na sessão; confirmação importa esse arquivo e o apaga. Prévias abandonadas expiram em 2 h.

---

## M4 — Mapeamentos de Programas Interrompidos
Origem: `regras_iniciais/04. mapeamentos_e_ajustes.md`

### Model — `app/models/mapeamento.py` (tabela `mapeamentos`, migration 002)
- Campos do usuário: Programa, Documento, Vaga (Fila + Posição: M01–M20, P01–P20, S01–S20).
- Campos do sistema: data/hora de registro (America/Sao_Paulo), turno, usuário (id + nome).
- Turnos (seção 7 — transições definidas):
  - 1º turno: 05:25:00 até 15:14:59.
  - 2º turno: 15:15:00 até 00:47:59 (atravessa a meia-noite). **15:15 pertence ao 2º turno.**
  - 00:48:00 até 05:24:59: **Fora de turno** (turno vazio). [Assumido]
- Vínculo (PROCV): `mapeamentos.programa = Prog. Orig.` e `mapeamentos.documento = Doc. Orig.`,
  comparados sem espaços e sem diferenciar maiúsculas. [Assumido: sem remover zeros à esquerda]
- Duplicidade (índices únicos parciais, garantem também concorrência):
  - uma vaga só tem um mapeamento ativo;
  - um Programa + Documento só tem um mapeamento ativo (novo mapeamento permitido após liberar).
- Liberação: grava `liberado_em`, `liberado_por` e `registro_id`; o histórico não é apagado.

### View — `app/views/templates/mapeamentos/pagina.html` (menu "Interrompidos")
- Mobile first: Programa/Documento em 2 colunas; vagas como botões grandes por fila (5 por linha no celular, 10 no tablet/desktop).
- Só vagas livres são exibidas; contador de livres e turno atual no topo.
- Lista de vagas reservadas (indica se o registro já está no atendimento ou aguarda importação) e últimas liberações.

### Controller — `app/controllers/mapeamentos.py`
- Valida campos; vaga ocupada ou Programa+Documento ativo duplicado → mensagem, nada gravado.
- Auditoria `criar_mapeamento`; liberação automática via atendimento (`liberar_mapeamento`).
- [Assumido] Liberação manual (corrigir reserva errada): somente ADMIN, auditada (`liberar_mapeamento_manual`).
- [Assumido] A vaga é liberada quando o atendimento é salvo **com Status preenchido** (qualquer status);
  salvar sem status grava Loc. TEGAD mas mantém a vaga reservada.
- [Assumido] Atendimento sem mapeamento: exibe "Sem mapeamento" e pode ser salvo normalmente.
- [Assumido] Mapeamento criado para um registro que já tinha status continua reservado até liberação manual.

---

## Status de implementação
| Módulo | Status |
|---|---|
| Base (config, DB, migrations, setup_db, layout) | Concluído — testado (config, auditoria) |
| M1 Autenticação/Admin | Concluído — 8 testes de integração passando |
| M2 Atendimento | Concluído — testes de integração passando |
| M3 Importação | Concluído — parser (10, inclui planilha real) + integração passando |

| M4 Mapeamentos + integração atendimento | Concluído — testes de turno, vagas, reserva, concorrência, PROCV e liberação |
| M3 Prévia de importação | Concluído — testes de prévia, confirmação, descarte, token |
| M1 Redefinir senha (autoatendimento) | Concluído — 7 testes |

Total: 55 testes passando no PostgreSQL (2026-11-17). Pendente: validar os itens [Assumido] com a equipe de Fechamento.
