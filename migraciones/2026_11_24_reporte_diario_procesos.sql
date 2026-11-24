-- ============================================================================
-- Reporte Diario: varios procesos por dia y modulos donde se aplico
--
-- Un dia puede tener hasta 3 procesos distintos (I. MEDICACION, F. MEDICACION,
-- INYECCION). Cada proceso guarda los modulos (1-4) donde se aplico.
-- Un mismo proceso no se repite en el mismo dia.
--
-- Reversible:
--   DROP TABLE reporte_diario_procesos;
-- ============================================================================

CREATE TABLE IF NOT EXISTS reporte_diario_procesos (
    id          serial PRIMARY KEY,
    id_reporte  integer NOT NULL
                REFERENCES reporte_diario(id) ON DELETE CASCADE,
    proceso     varchar(20) NOT NULL,
    modulos     smallint[] NOT NULL DEFAULT '{}',
    orden       smallint NOT NULL DEFAULT 0,
    creado_en   timestamptz NOT NULL DEFAULT now(),

    UNIQUE (id_reporte, proceso),
    CHECK (proceso IN ('I. MEDICACION', 'F. MEDICACION', 'INYECCION')),
    CHECK (modulos <@ ARRAY[1, 2, 3, 4]::smallint[])
);

CREATE INDEX IF NOT EXISTS idx_reporte_diario_procesos_reporte
    ON reporte_diario_procesos (id_reporte);

COMMENT ON TABLE reporte_diario_procesos IS
    'Procesos aplicados por dia y modulos donde se aplicaron';
COMMENT ON COLUMN reporte_diario_procesos.modulos IS
    'Modulos 1-4 donde se aplico el proceso';

-- Traslada el proceso unico que ya existia. Queda sin modulos (sin resaltado).
INSERT INTO reporte_diario_procesos (id_reporte, proceso, modulos, orden)
SELECT id, proceso, '{}', 0
FROM reporte_diario
WHERE proceso IS NOT NULL AND TRIM(proceso) <> ''
ON CONFLICT (id_reporte, proceso) DO NOTHING;
