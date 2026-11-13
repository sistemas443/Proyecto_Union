-- 2026-11-10: catálogo de áreas + roles de líder y coordinador
-- Nota: la tabla `areas` ya existía (con otra estructura y listado), por eso
-- el catálogo de este módulo vive en `areas_catalogo`.

CREATE TABLE IF NOT EXISTS areas_catalogo (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(100) UNIQUE NOT NULL,
    activa BOOLEAN NOT NULL DEFAULT TRUE,
    creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    actualizado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO areas_catalogo (nombre)
SELECT DISTINCT TRIM(c.area)
FROM colaboradores c
WHERE c.eliminado_en IS NULL
  AND c.area IS NOT NULL
  AND TRIM(c.area) <> ''
  AND NOT EXISTS (SELECT 1 FROM areas_catalogo a WHERE a.nombre = TRIM(c.area));

ALTER TABLE usuarios
    ADD COLUMN IF NOT EXISTS area VARCHAR(100);

INSERT INTO roles (nombre, descripcion)
SELECT 'Líder de proceso', 'Líder de un área: ve y evalúa solo a su equipo'
WHERE NOT EXISTS (SELECT 1 FROM roles WHERE nombre = 'Líder de proceso');

INSERT INTO roles (nombre, descripcion)
SELECT 'Coordinador administrativo', 'Coordina a los líderes de proceso: ve y evalúa a los líderes'
WHERE NOT EXISTS (SELECT 1 FROM roles WHERE nombre = 'Coordinador administrativo');
