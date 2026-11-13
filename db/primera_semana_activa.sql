-- Tabla activa de Primera Semana por lote.
-- dia1 = primera_semana (oficial), dia2 = primera_semana_dia2 (visual).
ALTER TABLE cabecera_lotes
    ADD COLUMN IF NOT EXISTS tabla_primera_activa varchar(10) DEFAULT 'dia1';

UPDATE cabecera_lotes
SET tabla_primera_activa = 'dia1'
WHERE tabla_primera_activa IS NULL;

-- Vista de lectura que devuelve la tabla activa de cada lote.
-- Los módulos que dependen de Primera Semana deben consultar esta vista.
CREATE OR REPLACE VIEW primera_semana_activa AS
SELECT
    p.id, p.lote, p.fecha, p.semana, p.mortalidad, p.sel,
    p.porc_mort_sem, p.porc_mort_acum, p.saldo_aves, p.peso_tabla,
    p.peso_real, p.unif_10_menos, p.porc_uniformidad, p.unif_10_mas,
    p.coef_variacion, p.observaciones, p.consumo_gr_a_tab, p.consumo_kg,
    p.consumo_gr_a_d, p.cons_k_acum, p.cons_gr_ave_tab_acum,
    p.cons_gr_ave_ac, p.id_lote
FROM primera_semana p
JOIN cabecera_lotes c ON c.lote = p.lote
WHERE COALESCE(c.tabla_primera_activa, 'dia1') = 'dia1'
UNION ALL
SELECT
    d.id, d.lote, d.fecha, d.semana, d.mortalidad, d.sel,
    d.porc_mort_sem, d.porc_mort_acum, d.saldo_aves, d.peso_tabla,
    d.peso_real, d.unif_10_menos, d.porc_uniformidad, d.unif_10_mas,
    d.coef_variacion, d.observaciones, d.consumo_gr_a_tab, d.consumo_kg,
    d.consumo_gr_a_d, d.cons_k_acum, d.cons_gr_ave_tab_acum,
    d.cons_gr_ave_ac, d.id_lote
FROM primera_semana_dia2 d
JOIN cabecera_lotes c ON c.lote = d.lote
WHERE c.tabla_primera_activa = 'dia2';
