-- ============================================================
-- Eventualidades por lote (anotaciones sobre los gráficos)
-- Fecha: 2026-11-07
-- ============================================================

CREATE TABLE IF NOT EXISTS tipos_eventualidad (
    id         SERIAL PRIMARY KEY,
    nombre     TEXT UNIQUE NOT NULL,
    color      TEXT DEFAULT '#dc3545',
    activo     BOOLEAN DEFAULT TRUE,
    creado_en  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS eventualidades_lote (
    id                 SERIAL PRIMARY KEY,
    id_lote            INTEGER NOT NULL REFERENCES cabecera_lotes(id) ON DELETE CASCADE,
    lote               TEXT NOT NULL,
    ambito             TEXT NOT NULL,
    semana             INTEGER NOT NULL,
    fecha              DATE,
    tipo_id            INTEGER REFERENCES tipos_eventualidad(id),
    titulo             TEXT NOT NULL,
    detalle            TEXT,
    impacto            TEXT,
    creado_por         INTEGER,
    creado_por_nombre  TEXT,
    creado_en          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    actualizado_en     TIMESTAMP,
    eliminado_en       TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_eventualidades_lote
    ON eventualidades_lote (id_lote, ambito, semana)
    WHERE eliminado_en IS NULL;

CREATE INDEX IF NOT EXISTS idx_eventualidades_tipo
    ON eventualidades_lote (tipo_id);

INSERT INTO tipos_eventualidad (nombre, color) VALUES
    ('Taponamiento',    '#dc3545'),
    ('Falla eléctrica', '#fd7e14'),
    ('Corte de agua',   '#0dcaf0'),
    ('Alimento',        '#6f42c1'),
    ('Sanidad',         '#198754'),
    ('Vacunación',      '#20c997'),
    ('Clima',           '#0d6efd'),
    ('Manejo',          '#6c757d'),
    ('Otro',            '#adb5bd')
ON CONFLICT (nombre) DO NOTHING;
