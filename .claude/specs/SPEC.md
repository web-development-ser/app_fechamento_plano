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
- Status vazio = `NULL`. Opções: Agrupado, Disponível, Finalizado, Barberan, 3DB, **Floco, PS7, Sala de Cortes**
  (regra 08, migration 005) — CHECK no banco. Os novos status não retiram a caixa da vaga (só Disponível/Finalizado).
- Loc. TEGAD: vaga do mapeamento (M01…S20), preenchida pelo sistema — somente leitura (migration 002).
- Resp. TS7: texto livre, até 150 caracteres (ex.: "sergio") (migration 002).
- Filtros com SQL parametrizado; paginação.

### View — `app/views/templates/atendimento/lista.html`, `atendimento/editar.html`
- Lista: ID, Programa, Item, Prog. Orig., Doc., Equipto, Dt. Solic., Qtd. Reposição + botão "Atender".
- Filtros visíveis: Programa, **Programa Original** (ao lado de Programa, regra 07), **Última modificação**
  (data em que o atendimento foi salvo pela última vez, fuso de São Paulo — substitui o filtro Item/SKU, regra 08).
  Recolhíveis ("Mais filtros"): Documento, Equipamento, Data de Solicitação. Todos combinam entre si (E lógico).
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
- CSV exportado pelo Excel/TOTVS começa com a linha `sep=;`: o separador é lido dela e a linha descartada
  (antes isso causava "Colunas obrigatórias ausentes"). Origem: `regras_iniciais/06`.
- O `.xlsx` guarda números com no máximo 15 dígitos: Item com 16+ dígitos chega arredondado
  (ex.: `…256` vira `…250`). Prévia e resumo avisam quantos itens estão nessa situação; **prefira o .csv**.
  Importar o mesmo relatório em .xlsx e .csv gera itens diferentes (chaves diferentes).
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
- **Capacidade da vaga (regra 06):** cada mapeamento ativo é **1 caixa** [Assumido]; uma vaga comporta até
  **7 caixas** (programas diferentes). Vaga disponível = menos de 7 caixas ativas.
  Garantido no banco por trigger com trava por vaga (migration 003) — vale também com acessos simultâneos.
- Um Programa + Documento só tem um mapeamento ativo (índice único parcial; novo permitido após retirar).
- **Saída da caixa (regra 06):** quando o item fica com status **Disponível ou Finalizado** e **todos** os demais
  itens do mesmo Prog. Orig. + Doc. Orig. também estão Disponível/Finalizado [Assumido — no relatório real
  12 pares Prog. Orig.+Doc. têm 2 ou 3 itens]. Agrupado, Barberan e 3DB mantêm a caixa na vaga.
- Retirada: grava `liberado_em`, `liberado_por` e `registro_id`; o histórico não é apagado.
- **Estoque (regra 07):** flag "Enviar para Estoque" grava a localização especial `EST` (exibida como "Estoque").
  Quando marcada, a seleção de vagas fica bloqueada na tela e qualquer vaga enviada é ignorada no servidor.
  [Assumido] Estoque não tem limite de caixas (trigger ignora `EST`, migration 004) e segue a mesma regra de
  saída (Disponível/Finalizado). Loc. TEGAD do atendimento passa a mostrar "Estoque".

### View — `app/views/templates/mapeamentos/pagina.html` (menu "Interrompidos")
- Mobile first: Programa/Documento em 2 colunas; vagas como botões grandes por fila (5 por linha no celular, 10 no tablet/desktop).
- Só vagas com espaço são exibidas, cada uma com a ocupação (ex.: `3/7`); topo mostra vagas com espaço, total de caixas e turno.
- Lista "Caixas nas vagas" (indica se o registro já está no atendimento ou aguarda importação) e últimas caixas retiradas.
- Filtros das caixas nas vagas: **Programa** e **Documento** (busca parcial, combináveis; parâmetros `f_programa`,
  `f_documento`); o título mostra "N de total" quando filtrado (regra 08).

### Controller — `app/controllers/mapeamentos.py`
- Valida campos; vaga lotada (7 caixas) ou Programa+Documento ativo duplicado → mensagem, nada gravado.
- Auditoria `criar_mapeamento`; liberação automática via atendimento (`liberar_mapeamento`).
- **Retirada manual da caixa** (botão "Retirar caixa", com confirmação): permitida a **qualquer usuário logado**,
  as mesmas pessoas que atendem os itens (regra 09). Libera o espaço na vaga na hora; grava quem retirou
  (`liberado_por`) e auditoria `liberar_mapeamento_manual`.
- Atendimento salvo com Disponível/Finalizado mas com outros itens pendentes: caixa fica na vaga e a mensagem
  informa quantos itens faltam. Salvar sem status grava Loc. TEGAD e mantém a caixa.
- [Assumido] Atendimento sem mapeamento: exibe "Sem mapeamento" e pode ser salvo normalmente.
- [Assumido] Mapeamento criado para um registro que já tinha status continua reservado até liberação manual.

---

## M5 — Consulta pública de itens
Origem: `regras_iniciais/06. vagas_capacidade_e_consulta.md`

### Model — `app/models/registro.py`
- `SETORES` pelo prefixo do Equipto: **S7S – Serigrafia, S7M – Montagem, S7P – Pintura** (outros prefixos, ex.: S7B, aparecem como "—").
- Filtro `setor` (prefixo) e filtro de situação `atendidos` (status preenchido); `resumo()` = total, atendidos, pendentes.

### View — `app/views/templates/consulta/lista.html` (rota `/consulta/`, menu "Consulta")
- **Sem login** (qualquer pessoa), somente leitura; cabeçalho próprio com botão "Entrar"; link na tela de login.
- Destaque: badge **Pendente** (vermelho) ou **Atendido · <status>** (verde) e resumo com % atendido.
- Filtros: os mesmos do Atendimento (Programa, Item; Documento, Equipamento, Data em "Mais filtros")
  + **Setor** + Situação (Todos [padrão], Pendentes, Atendidos ou um status específico).
- Lista: Item, Programa, Prog. Orig., Doc., Setor, Dt. Solic., Qtd., Loc. TEGAD, **Recebido por**, **Resp. TS7**,
  Recebido em + botão **Detalhes** (regra 07; ajuste 2026-11-18: "Registrado por" removido, Resp. TS7 no lugar).
  Cartões no celular, tabela no desktop.
  - [Assumido] Recebido por = Pessoa Resp. TEGAD do atendimento.
- Detalhes (`/consulta/<id>`, `consulta/detalhe.html`, sem login): situação, Recebido por, Resp. TS7, recebido em,
  Loc. TEGAD, narrativa, todos os dados do relatório, quem importou e o histórico do programa interrompido
  (sem "Registrado por", mesmo ajuste da lista).

### Controller — `app/controllers/consulta.py`
- Somente GET; reutiliza a leitura de filtros do Atendimento (inclui Programa Original); valores inválidos são ignorados.

---

## M6 — Dashboard Troca de Turno
Origem: `regras_iniciais/07. estoque_consulta_dashboard_pwa.md`

### Model — `app/models/registro.py` (`contagem_por_status`)
- Barras na ordem fixa **Não Atendimento**, Agrupado, Disponível, Finalizado, Barberan, 3DB (zerados aparecem).
- **Não Atendimento** = registros com status vazio (NULL, em branco ou só espaços). Eles **sempre entram em
  "Itens no Total"** (ajuste 2026-11-18).
- Como o item não atendido não tem data de atendimento nem usuário, as regras de filtro são separadas:
  - Data com base **Atendimento** (padrão): atendidos no dia + todos os não atendidos solicitados até a data
    (o que ainda está em aberto para o turno).
  - Data com base **Solicitação**: atendidos e não atendidos com Dt. Solic. = data.
  - **Usuário**: filtra só os atendidos; os não atendidos continuam no total.
  - **Status**: "Não Atendimento" mostra só os vazios; "Atendidos" ou um status específico excluem os vazios.

### View — `app/views/templates/dashboard/pagina.html` (menu "Turno")
- Filtros: **Data**, Considerar data de (Solicitação | Atendimento), **Setor**, **Usuário**, **Status**.
  Mudar qualquer filtro atualiza os indicadores automaticamente (sem precisar clicar).
- Indicadores: Itens no Total (destaque), Atendidos, Não Atendimento, % atendido e barras horizontais por status
  (uma cor só, valor e % ao lado, tooltip por barra, tabela acessível).
- O gráfico mostra **sempre todos os status**, inclusive os zerados (barra cinza) e mesmo quando o total é 0
  ou quando o filtro de Status seleciona um único status (ajuste 2026-11-18).

### Controller — `app/controllers/dashboard.py`
- Somente usuários autenticados (`login_required`).
- [Assumido] Data padrão = hoje; "Todas as datas" remove o filtro. Base padrão = **data do atendimento**
  (visão do turno: o que foi atendido hoje + o que está em aberto).
- [Assumido] Usuário = quem salvou o atendimento por último; com base "Atendimento", data = dia do último salvamento.

---

## M7 — PWA (Progressive Web App)
Origem: `regras_iniciais/07. estoque_consulta_dashboard_pwa.md`

### Controller — `app/controllers/pwa.py`
- `/manifest.webmanifest`: nome, `display: standalone`, `start_url`, cores do tema, ícones 192/512/maskable/SVG
  e atalhos (Atendimento, Interrompidos, Troca de turno, Consulta).
- `/sw.js` (escopo `/`, sem cache HTTP) e `/offline`.

### Service worker — `app/views/templates/pwa/sw.js`
- Instalação guarda CSS, JS, ícones, biblioteca de ícones (local) e a página offline.
- Arquivos estáticos: cache primeiro (URLs versionadas `?v=`). Páginas: rede primeiro.
- Sem conexão: Consulta já visitada abre da memória; demais páginas mostram "Sem conexão".
  [Assumido] Páginas autenticadas não são guardadas no aparelho (privacidade); o cache de páginas é apagado ao sair.
- Formulários (POST) nunca passam pelo cache.

### Atualização automática
- `APP_VERSION` = hash de `views/static` + `views/templates` calculado ao iniciar; muda a cada deploy com alteração.
- Versão nova gera service worker novo → instala, assume (`skipWaiting`/`clients.claim`), limpa caches antigos
  e recarrega a página. Se houver formulário sendo preenchido, mostra "Nova versão disponível" em vez de recarregar.
- O app verifica atualização ao voltar para a tela e a cada 30 min.

### Ícone e tela de abertura
- Ícones gerados por `scripts/gerar_icones.py` (T branco sobre #1877F2). Tela de abertura: Android/desktop pelo
  manifesto (fundo azul + ícone + nome) e tela própria em CSS no app instalado (inclui iOS), 1x por sessão.
- Biblioteca Lucide servida localmente (`static/js/vendor`), sem depender da internet externa.

### Requisito de infraestrutura — HTTPS
- Service worker e instalação só funcionam em contexto seguro (HTTPS ou `localhost`). Em `http://<ip>:5001`
  o sistema funciona normalmente, mas não instala nem usa cache offline (o JS só registra o SW em contexto seguro).
- 2026-11-19: o proxy Caddy com CA interna (regra 08) foi **revertido** a pedido do usuário. Sem `TEGAD_ENDERECOS`
  configurado, o certificado saiu só para `localhost` e o acesso pelo IP parou. O docker-compose voltou a publicar
  a aplicação direto em HTTP na porta 5001.
- Para ativar o PWA depois: proxy HTTPS com certificado confiável pelos aparelhos (definir com a TI) +
  `TRUST_PROXY=1` e `SESSION_COOKIE_SECURE=1` no `.env` (suporte já existe na aplicação, desligado por padrão).

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
| Regra 06: vagas com 7 caixas + saída por Disponível/Finalizado | Concluído — inclui teste de concorrência |
| Regra 06: CSV com `sep=;` + aviso de precisão do .xlsx | Concluído — testado com o CSV real (66 linhas) |
| M5 Consulta pública | Concluído — 4 testes |
| Regra 07: Estoque, Consulta (recebido por/Resp. TS7/detalhes), filtro Programa Original | Concluído — 6 testes |
| M6 Dashboard Troca de Turno | Concluído — 2 testes (acesso, contagens e todos os filtros) |
| M7 PWA | Concluído — 5 testes (manifesto, SW/precache, assets versionados, versão, offline); instalação real depende de HTTPS |
| Regra 08: filtro Última modificação, status Floco/PS7/Sala de Cortes, filtros das caixas | Concluído — 4 testes |
| Regra 08: HTTPS para o PWA | **Revertido** em 2026-11-19 (proxy Caddy removido do compose); suporte a proxy (ProxyFix, desligado por padrão) mantido e testado |

Total: 86 testes passando no PostgreSQL (2026-11-19). Pendente: validar os itens [Assumido] com a equipe de Fechamento.
