-- ============================================================================
-- Reporte Diario: Gallinaza pasa a valores Si / No
--
-- Reversible:
--   UPDATE reporte_diario SET gallinaza = 'Hoy'       WHERE gallinaza = 'Si';
--   UPDATE reporte_diario SET gallinaza = 'No aplica' WHERE gallinaza = 'No';
-- ============================================================================

UPDATE reporte_diario SET gallinaza = 'Sí' WHERE gallinaza = 'Hoy';
UPDATE reporte_diario SET gallinaza = 'No' WHERE gallinaza = 'No aplica';
