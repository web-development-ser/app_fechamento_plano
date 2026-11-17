# ARCHITECTURE — MVC

```
.claude/
  regras_iniciais/        requisitos originais (não editar sem autorização)
  specs/                  SPEC.md (requisitos por módulo/camada) e este arquivo
app/
  __init__.py             create_app(): config, registro dos controllers, CSRF, erros
  config.py               lê .env
  db.py                   conexão psycopg por requisição, query/execute/commit, migrations
  security.py             login_required, admin_required, CSRF, usuário da sessão
  models/                 M — dados e regras de negócio (SQL parametrizado)
    usuario.py            usuários, hash de senha, autenticação
    registro.py           agrupamento_registro: filtros, busca, atendimento
    mapeamento.py         programas interrompidos: vagas, turnos, reserva/liberação
    importacao.py         leitura/validação do arquivo TOTVS, prévia e gravação sem duplicidade
    auditoria.py          registro de rastreabilidade
  controllers/            C — rotas Flask (Blueprints): recebem a requisição, validam formulário,
    auth.py               chamam o model, confirmam a transação e escolhem a view
    admin.py
    atendimento.py
    importacao.py
    mapeamentos.py
    consulta.py           consulta pública (sem login, somente leitura)
  views/                  V — apresentação
    templates/            Jinja2 (base.html, _flash.html, login, senha, admin/, atendimento/, importacao/, mapeamentos/, consulta/)
    static/css/app.css    tema Facebook, mobile first (tokens em :root)
    static/js/app.js      mostrar senha, confirmações, ícones Lucide
migrations/               NNN_descricao.sql aplicadas em ordem (tabela schema_migrations)
scripts/                  init_db.py, create_admin.py
tests/                    pytest (parser sem banco; integração com TEST_DATABASE_URL)
```

## Regras das camadas
- **Model** não importa Flask request/views; não faz `commit` (exceto `importacao.importar`, que fecha o próprio lote).
- **Controller** não contém SQL; é quem faz `db.commit()` / `db.rollback()` e registra auditoria.
- **View** só apresenta; nenhuma regra de negócio nos templates.
- Novo módulo = `models/<nome>.py` + `controllers/<nome>.py` + `views/templates/<nome>/` + seção em `SPEC.md`.

## Decisões
- **Sem ORM**: SQL explícito com psycopg 3 e parâmetros.
- **Rastreabilidade**: colunas `criado_por/criado_em/atualizado_por/atualizado_em` + tabela `auditoria`.
- **Duplicidade**: `UNIQUE (programa, item, prog_orig, doc_orig)` + `INSERT ... ON CONFLICT DO NOTHING RETURNING id`.
- **CSRF**: token por sessão validado em todo POST.
- **Status vazio** = `NULL`; valores permitidos garantidos por CHECK no banco.
- **Vagas**: até 7 caixas por vaga, garantido por trigger com `pg_advisory_xact_lock` por vaga (migration 003);
  Programa+Documento ativo único por índice parcial `WHERE liberado_em IS NULL`.
