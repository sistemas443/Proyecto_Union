-- 2026-11-10: video en Lengua de Señas Colombiana (LSC) por indicador
-- Cada pregunta puede tener un video propio de un intérprete de señas.

ALTER TABLE indicadores_evaluacion
    ADD COLUMN IF NOT EXISTS lsc_video_url TEXT;
