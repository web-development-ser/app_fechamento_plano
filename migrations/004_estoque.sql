-- 004: localização especial "Estoque" (código EST) para Programas Interrompidos.
-- Estoque não tem limite de caixas. Não remove dados.

ALTER TABLE mapeamentos DROP CONSTRAINT IF EXISTS mapeamentos_vaga_check;
ALTER TABLE mapeamentos ADD CONSTRAINT mapeamentos_vaga_check
    CHECK (vaga ~ '^([MPS](0[1-9]|1[0-9]|20)|EST)$');

CREATE OR REPLACE FUNCTION fn_mapeamentos_capacidade() RETURNS trigger AS $$
DECLARE
    ocupadas integer;
BEGIN
    IF NEW.vaga = 'EST' THEN
        RETURN NEW;  -- Estoque: sem limite de caixas
    END IF;
    PERFORM pg_advisory_xact_lock(hashtext('mapeamentos_vaga:' || NEW.vaga));
    SELECT count(*) INTO ocupadas FROM mapeamentos WHERE vaga = NEW.vaga AND liberado_em IS NULL;
    IF ocupadas >= 7 THEN
        RAISE EXCEPTION 'VAGA_LOTADA' USING ERRCODE = 'check_violation', DETAIL = NEW.vaga;
    END IF;
    RETURN NEW;
END
$$ LANGUAGE plpgsql;

-- consulta do último mapeamento (ativo ou retirado) por Programa + Documento
CREATE INDEX IF NOT EXISTS ix_mapeamentos_prog_doc ON mapeamentos (programa, documento, registrado_em DESC);
-- dashboard / filtros por data de atendimento e usuário
CREATE INDEX IF NOT EXISTS ix_agrupamento_atualizado ON agrupamento_registro (atualizado_em);
