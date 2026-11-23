-- Columna derivada Agua/Consumo del modulo Diario.
-- Se calcula como agua por ave (prom_ave_dia_cc, cc) / consumo por ave
-- (consumo_gr_a_d, g/ave/dia) = cc de agua por gramo de alimento.
--
-- La columna la recalcula la aplicacion en cada guardado; este script solo
-- crea la columna y rellena los registros existentes.

ALTER TABLE data_diario
    ADD COLUMN IF NOT EXISTS agua_consumo NUMERIC(10, 2);

UPDATE data_diario
SET agua_consumo = ROUND(prom_ave_dia_cc / NULLIF(consumo_gr_a_d, 0), 1)
WHERE prom_ave_dia_cc IS NOT NULL
  AND consumo_gr_a_d IS NOT NULL
  AND consumo_gr_a_d <> 0;
