-- ============================================================================
-- Reporte Diario — proceso aplicado en el día (medicación / inyección)
-- Aditiva y reversible:
--   ALTER TABLE reporte_diario DROP COLUMN proceso;
-- ============================================================================

ALTER TABLE reporte_diario
    ADD COLUMN IF NOT EXISTS proceso varchar(30);

COMMENT ON COLUMN reporte_diario.proceso
    IS 'Proceso del día: I. MEDICACION, F. MEDICACION o INYECCION';
