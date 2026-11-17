-- 001: estrutura inicial (usuarios, agrupamento_registro, importacoes, auditoria)

CREATE TABLE IF NOT EXISTS usuarios (
    id            SERIAL PRIMARY KEY,
    nome          VARCHAR(150) NOT NULL,
    usuario       VARCHAR(60)  NOT NULL,
    senha_hash    VARCHAR(255) NOT NULL,
    perfil        VARCHAR(10)  NOT NULL DEFAULT 'USUARIO' CHECK (perfil IN ('ADMIN', 'USUARIO')),
    ativo         BOOLEAN      NOT NULL DEFAULT TRUE,
    criado_em     TIMESTAMPTZ  NOT NULL DEFAULT now(),
    criado_por    INTEGER REFERENCES usuarios(id),
    atualizado_em TIMESTAMPTZ,
    atualizado_por INTEGER REFERENCES usuarios(id)
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_usuarios_usuario ON usuarios (lower(usuario));

CREATE TABLE IF NOT EXISTS importacoes (
    id             SERIAL PRIMARY KEY,
    arquivo_nome   VARCHAR(255) NOT NULL,
    total          INTEGER NOT NULL DEFAULT 0,
    novos          INTEGER NOT NULL DEFAULT 0,
    existentes     INTEGER NOT NULL DEFAULT 0,
    erros          INTEGER NOT NULL DEFAULT 0,
    importado_por  INTEGER NOT NULL REFERENCES usuarios(id),
    importado_em   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS agrupamento_registro (
    id                 SERIAL PRIMARY KEY,
    -- dados do relatório TOTVS
    lote               VARCHAR(50),
    programa           VARCHAR(50)  NOT NULL,
    item               VARCHAR(60)  NOT NULL,
    descricao          VARCHAR(255),
    prog_orig          VARCHAR(50)  NOT NULL,
    doc_orig           VARCHAR(50)  NOT NULL,
    dt_solic           DATE,
    qtd_reposicao      NUMERIC(14, 3),
    motivo_repos       VARCHAR(30),
    desc_motivo_repos  VARCHAR(255),
    equipto            VARCHAR(50),
    gestor             VARCHAR(150),
    -- atendimento
    dt_recebimento     TIMESTAMP,
    pessoa_resp_tegad  VARCHAR(150),
    loc_tegad          CHAR(1) CHECK (loc_tegad ~ '^[A-Z]$'),
    resp_ts7           VARCHAR(3) CHECK (resp_ts7 ~ '^[A-G]([1-9]|10)$'),
    narrativa          TEXT,
    status             VARCHAR(20) CHECK (status IN ('Agrupado', 'Disponível', 'Finalizado', 'Barberan', '3DB')),
    -- rastreabilidade
    importacao_id      INTEGER REFERENCES importacoes(id),
    criado_em          TIMESTAMPTZ NOT NULL DEFAULT now(),
    criado_por         INTEGER REFERENCES usuarios(id),
    atualizado_em      TIMESTAMPTZ,
    atualizado_por     INTEGER REFERENCES usuarios(id),
    CONSTRAINT uq_agrupamento_chave UNIQUE (programa, item, prog_orig, doc_orig)
);
CREATE INDEX IF NOT EXISTS ix_agrupamento_status_nulo ON agrupamento_registro (id) WHERE status IS NULL;
CREATE INDEX IF NOT EXISTS ix_agrupamento_item ON agrupamento_registro (item);
CREATE INDEX IF NOT EXISTS ix_agrupamento_dt_solic ON agrupamento_registro (dt_solic);

CREATE TABLE IF NOT EXISTS auditoria (
    id           BIGSERIAL PRIMARY KEY,
    usuario_id   INTEGER REFERENCES usuarios(id),
    usuario_nome VARCHAR(150),
    acao         VARCHAR(60) NOT NULL,
    entidade     VARCHAR(60) NOT NULL,
    entidade_id  VARCHAR(60),
    detalhes     JSONB,
    criado_em    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_auditoria_entidade ON auditoria (entidade, entidade_id);
