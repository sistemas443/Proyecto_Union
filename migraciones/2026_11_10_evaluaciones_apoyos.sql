-- 2026-11-10: apoyos visuales por indicador (pictograma + lenguaje claro)
-- Cada pregunta puede tener una versión corta y un icono que la represente.

ALTER TABLE indicadores_evaluacion
    ADD COLUMN IF NOT EXISTS descripcion_clara TEXT,
    ADD COLUMN IF NOT EXISTS pictograma VARCHAR(80);
