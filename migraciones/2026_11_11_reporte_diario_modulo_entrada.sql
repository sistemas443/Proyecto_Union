-- ============================================================================
-- Reporte Diario — módulo donde se registra la entrada del galpón
-- Aditiva y reversible:
--   ALTER TABLE reporte_diario DROP COLUMN modulo_entrada;
-- ============================================================================

ALTER TABLE reporte_diario
    ADD COLUMN IF NOT EXISTS modulo_entrada smallint;

COMMENT ON COLUMN reporte_diario.modulo_entrada
    IS 'Módulo (1-4) donde se registra la entrada del galpón en el día. NULL = sin marcar';

ALTER TABLE reporte_diario
    DROP CONSTRAINT IF EXISTS ck_reporte_diario_modulo_entrada;

ALTER TABLE reporte_diario
    ADD CONSTRAINT ck_reporte_diario_modulo_entrada
    CHECK (modulo_entrada IS NULL OR modulo_entrada BETWEEN 1 AND 4);
