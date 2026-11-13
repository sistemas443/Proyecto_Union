-- ============================================================================
-- Reporte Diario — captura operativa por lote y día
-- Fase 1: estructura base (solo lectura en la interfaz)
--
-- No modifica ninguna tabla existente. Es aditiva y reversible:
--   DROP TABLE reporte_diario;
-- ============================================================================

CREATE TABLE IF NOT EXISTS reporte_diario (
    id                serial PRIMARY KEY,
    id_lote           integer      NOT NULL,
    lote              varchar(50)  NOT NULL,
    fecha             date         NOT NULL,

    -- Producción y alimentación
    produccion        integer      DEFAULT 0,
    alimento          numeric(12,2) DEFAULT 0,

    -- Mortalidad por módulo (galpones de batería: 4 fijos)
    mort_m1           integer      DEFAULT 0,
    mort_m2           integer      DEFAULT 0,
    mort_m3           integer      DEFAULT 0,
    mort_m4           integer      DEFAULT 0,
    mort_total        integer      GENERATED ALWAYS AS (
                          COALESCE(mort_m1,0) + COALESCE(mort_m2,0) +
                          COALESCE(mort_m3,0) + COALESCE(mort_m4,0)
                      ) STORED,

    -- Casos especiales (venta, necropsia, otros)
    otras             integer      DEFAULT 0,
    otras_motivo      varchar(40),
    afecta_saldo      boolean      DEFAULT true,

    -- Consumos del día
    saldo_aves        integer,
    agua              numeric(12,2) DEFAULT 0,
    silo              numeric(12,2) DEFAULT 0,

    -- Manejo
    entrada_tipo      varchar(20),
    entrada_producto  varchar(120),
    desinfeccion      varchar(60),
    gallinaza         varchar(60),
    cierra_silo       varchar(60),
    observaciones     text,

    -- Trazabilidad
    registrado_por    varchar(120),
    creado_en         timestamptz  DEFAULT now(),
    actualizado_en    timestamptz  DEFAULT now(),

    CONSTRAINT uq_reporte_diario_lote_fecha UNIQUE (id_lote, fecha)
);

CREATE INDEX IF NOT EXISTS idx_reporte_diario_fecha ON reporte_diario (fecha);
CREATE INDEX IF NOT EXISTS idx_reporte_diario_lote  ON reporte_diario (lote);

COMMENT ON TABLE  reporte_diario IS 'Captura diaria de granja (producción, mortalidad por módulo, consumos y manejo)';
COMMENT ON COLUMN reporte_diario.mort_total  IS 'Suma automática de los 4 módulos';
COMMENT ON COLUMN reporte_diario.afecta_saldo IS 'Si es false, "otras" no descuenta aves del saldo (p. ej. necropsia)';
