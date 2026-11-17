-- 003: uma vaga (Fila + Posição) comporta até 7 caixas (mapeamentos ativos).
-- Não remove dados: troca o índice único por um índice comum e cria a trava de capacidade.

DROP INDEX IF EXISTS ux_mapeamentos_vaga_ativa;
CREATE INDEX IF NOT EXISTS ix_mapeamentos_vaga_ativa ON mapeamentos (vaga) WHERE liberado_em IS NULL;

CREATE OR REPLACE FUNCTION fn_mapeamentos_capacidade() RETURNS trigger AS $$
DECLARE
    ocupadas integer;
BEGIN
    -- serializa reservas da mesma vaga até o fim da transação (evita passar de 7 em acessos simultâneos)
    PERFORM pg_advisory_xact_lock(hashtext('mapeamentos_vaga:' || NEW.vaga));
    SELECT count(*) INTO ocupadas FROM mapeamentos WHERE vaga = NEW.vaga AND liberado_em IS NULL;
    IF ocupadas >= 7 THEN
        RAISE EXCEPTION 'VAGA_LOTADA' USING ERRCODE = 'check_violation', DETAIL = NEW.vaga;
    END IF;
    RETURN NEW;
END
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_mapeamentos_capacidade ON mapeamentos;
CREATE TRIGGER trg_mapeamentos_capacidade
    BEFORE INSERT ON mapeamentos
    FOR EACH ROW EXECUTE FUNCTION fn_mapeamentos_capacidade();
