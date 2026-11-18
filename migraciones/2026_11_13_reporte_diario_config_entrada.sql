-- ============================================================================
-- Reporte Diario — módulos del lote que tienen la entrada (puerta) del galpón
--
-- Reversible:
--   DROP TABLE reporte_diario_config;
--   ALTER TABLE reporte_diario ADD COLUMN modulo_entrada smallint;
-- ============================================================================

CREATE TABLE IF NOT EXISTS reporte_diario_config (
    id_lote           integer PRIMARY KEY,
    modulos_entrada   varchar(20) NOT NULL DEFAULT '',
    actualizado_en    timestamptz DEFAULT now()
);

COMMENT ON TABLE  reporte_diario_config IS 'Configuración del reporte diario por lote';
COMMENT ON COLUMN reporte_diario_config.modulos_entrada
    IS 'Módulo (1-4) junto al que está la puerta/entrada del galpón';

-- La marca por día se reemplaza por esta configuración fija del lote.
ALTER TABLE reporte_diario DROP COLUMN IF EXISTS modulo_entrada;
