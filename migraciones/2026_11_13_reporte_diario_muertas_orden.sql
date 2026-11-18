-- ============================================================================
-- Reporte Diario — total de muertes digitado por el usuario
--                    + entrada del galpón en un solo módulo
--
-- Reversible:
--   ALTER TABLE reporte_diario DROP COLUMN muertas;
-- ============================================================================

-- 1. Total de muertes del día (lo digita el usuario)
ALTER TABLE reporte_diario
    ADD COLUMN IF NOT EXISTS muertas integer DEFAULT 0;

COMMENT ON COLUMN reporte_diario.muertas
    IS 'Total de aves muertas del día, digitado por el usuario. Es el que descuenta el saldo';

COMMENT ON COLUMN reporte_diario.mort_total
    IS 'Suma de los 4 módulos (informativa; puede diferir de muertas)';

-- Si ya había datos, el total de módulos pasa a ser el total digitado
UPDATE reporte_diario
   SET muertas = COALESCE(mort_total, 0)
 WHERE COALESCE(muertas, 0) = 0
   AND COALESCE(mort_total, 0) > 0;

-- 2. La entrada del galpón es un solo módulo
UPDATE reporte_diario_config
   SET modulos_entrada = split_part(modulos_entrada, ',', 1)
 WHERE modulos_entrada LIKE '%,%';
