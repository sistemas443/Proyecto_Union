-- ============================================================================
-- Reporte Diario — producto usado en la desinfección
-- Aditiva y reversible:
--   ALTER TABLE reporte_diario DROP COLUMN desinfeccion_producto;
-- ============================================================================

ALTER TABLE reporte_diario
    ADD COLUMN IF NOT EXISTS desinfeccion_producto varchar(120);

COMMENT ON COLUMN reporte_diario.desinfeccion_producto
    IS 'Producto con el que se desinfectó (solo aplica cuando desinfeccion = Si)';
