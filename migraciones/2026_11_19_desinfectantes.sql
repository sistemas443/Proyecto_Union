-- ============================================================================
-- Catalogo de desinfectantes para el Reporte Diario
--
-- Reversible:
--   DROP TABLE desinfectantes;
-- ============================================================================

CREATE TABLE IF NOT EXISTS desinfectantes (
    id         serial PRIMARY KEY,
    nombre     varchar(120) NOT NULL UNIQUE,
    activo     boolean NOT NULL DEFAULT true,
    creado_en  timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE desinfectantes IS 'Productos usados en la desinfeccion del galpon';

-- Cargar los productos que ya se hayan escrito a mano en el reporte
INSERT INTO desinfectantes (nombre)
SELECT DISTINCT TRIM(desinfeccion_producto)
FROM reporte_diario
WHERE desinfeccion_producto IS NOT NULL
  AND TRIM(desinfeccion_producto) <> ''
ON CONFLICT (nombre) DO NOTHING;
