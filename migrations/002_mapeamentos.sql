-- 002: Mapeamentos de Programas Interrompidos + ajustes de Loc. TEGAD / Resp. TS7
-- Não remove dados: apenas troca tipos/constraints e cria a nova tabela.

-- Resp. TS7 passa a ser texto livre (nome do responsável)
ALTER TABLE agrupamento_registro DROP CONSTRAINT IF EXISTS agrupamento_registro_resp_ts7_check;
ALTER TABLE agrupamento_registro ALTER COLUMN resp_ts7 TYPE VARCHAR(150);

-- Loc. TEGAD passa a receber a vaga do mapeamento (M01..S20), preenchida pelo sistema
ALTER TABLE agrupamento_registro DROP CONSTRAINT IF EXISTS agrupamento_registro_loc_tegad_check;
ALTER TABLE agrupamento_registro ALTER COLUMN loc_tegad TYPE VARCHAR(3) USING trim(loc_tegad);

CREATE TABLE IF NOT EXISTS mapeamentos (
    id              SERIAL PRIMARY KEY,
    programa        VARCHAR(50) NOT NULL,
    documento       VARCHAR(50) NOT NULL,
    vaga            VARCHAR(3)  NOT NULL CHECK (vaga ~ '^[MPS](0[1-9]|1[0-9]|20)$'),
    turno           SMALLINT CHECK (turno IN (1, 2)),          -- NULL = fora de turno
    registrado_em   TIMESTAMPTZ NOT NULL DEFAULT now(),
    registrado_por  INTEGER NOT NULL REFERENCES usuarios(id),
    usuario_nome    VARCHAR(150) NOT NULL,
    -- liberação (atendimento)
    liberado_em     TIMESTAMPTZ,
    liberado_por    INTEGER REFERENCES usuarios(id),
    registro_id     INTEGER REFERENCES agrupamento_registro(id)
);

-- uma vaga só pode ter um mapeamento ativo
CREATE UNIQUE INDEX IF NOT EXISTS ux_mapeamentos_vaga_ativa
    ON mapeamentos (vaga) WHERE liberado_em IS NULL;
-- um Programa + Documento só pode ter um mapeamento ativo
CREATE UNIQUE INDEX IF NOT EXISTS ux_mapeamentos_prog_doc_ativo
    ON mapeamentos (programa, documento) WHERE liberado_em IS NULL;
CREATE INDEX IF NOT EXISTS ix_mapeamentos_registrado_em ON mapeamentos (registrado_em DESC);
