-- Tabla del "Día 2" de Primera Semana.
-- Es independiente de primera_semana: no participa en cálculos oficiales,
-- reportes ni consolidados. Solo guarda la segunda tabla visual del lote.
CREATE TABLE IF NOT EXISTS primera_semana_dia2 (
    id serial PRIMARY KEY,
    lote varchar NOT NULL,
    id_lote integer REFERENCES cabecera_lotes(id) ON DELETE CASCADE,
    fecha date,
    semana varchar,
    mortalidad integer,
    sel integer,
    porc_mort_sem numeric,
    porc_mort_acum numeric,
    saldo_aves integer,
    peso_tabla numeric,
    peso_real numeric,
    unif_10_menos numeric,
    porc_uniformidad numeric,
    unif_10_mas numeric,
    coef_variacion numeric,
    observaciones text,
    consumo_gr_a_tab numeric,
    consumo_kg numeric,
    consumo_gr_a_d numeric,
    cons_k_acum numeric,
    cons_gr_ave_tab_acum numeric,
    cons_gr_ave_ac numeric,
    fecha_registro timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);

-- Un solo juego de 8 filas por lote.
CREATE UNIQUE INDEX IF NOT EXISTS primera_semana_dia2_lote_semana_key
    ON primera_semana_dia2 (lote, semana);

CREATE INDEX IF NOT EXISTS primera_semana_dia2_lote_idx
    ON primera_semana_dia2 (lote);
