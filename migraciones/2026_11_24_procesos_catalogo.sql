-- ============================================================================
-- Catalogo de procesos del Reporte Diario
--
-- Permite crear procesos nuevos sin tocar el codigo. Cada proceso tiene su
-- color, que se usa para resaltar los modulos donde se aplico.
--
-- Reversible:
--   DROP TABLE procesos;
--   (volver a crear el CHECK de los tres procesos originales)
-- ============================================================================

CREATE TABLE IF NOT EXISTS procesos (
    id          serial PRIMARY KEY,
    nombre      varchar(40) NOT NULL UNIQUE,
    color       varchar(7) NOT NULL DEFAULT '#35c6ea',
    activo      boolean NOT NULL DEFAULT true,
    creado_en   timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE procesos IS 'Catalogo de procesos aplicados en el galpon';
COMMENT ON COLUMN procesos.color IS 'Color hexadecimal para el resaltado';

INSERT INTO procesos (nombre, color)
VALUES
    ('I. MEDICACION', '#35c6ea'),
    ('F. MEDICACION', '#ffe600'),
    ('INYECCION', '#e8b8b8')
ON CONFLICT (nombre) DO NOTHING;

-- Los procesos ahora salen del catalogo, no de una lista fija.
ALTER TABLE reporte_diario_procesos
    DROP CONSTRAINT IF EXISTS reporte_diario_procesos_proceso_check;

-- Margen para nombres nuevos (el catalogo limita a 40).
ALTER TABLE reporte_diario_procesos
    ALTER COLUMN proceso TYPE varchar(60);
