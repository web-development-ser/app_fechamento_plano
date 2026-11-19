-- 005: novos status de atendimento: Floco, PS7, Sala de Cortes. Não remove dados.
ALTER TABLE agrupamento_registro DROP CONSTRAINT IF EXISTS agrupamento_registro_status_check;
ALTER TABLE agrupamento_registro ADD CONSTRAINT agrupamento_registro_status_check
    CHECK (status IN ('Agrupado', 'Disponível', 'Finalizado', 'Barberan', '3DB', 'Floco', 'PS7', 'Sala de Cortes'));

-- filtro "última modificação" do Atendimento
CREATE INDEX IF NOT EXISTS ix_agrupamento_atualizado ON agrupamento_registro (atualizado_em);
-- filtros Programa / Documento das caixas em Interrompidos
CREATE INDEX IF NOT EXISTS ix_mapeamentos_ativos ON mapeamentos (programa, documento) WHERE liberado_em IS NULL;
