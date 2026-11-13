-- 2026-11-10: ciclos de evaluación de desempeño
-- Vincula cada evaluación con el ciclo que la originó (3M / 6M / ANUAL n).
-- Columnas nullable: no afectan las evaluaciones existentes.

ALTER TABLE evaluaciones_desempeno
    ADD COLUMN IF NOT EXISTS ciclo_tipo   VARCHAR(10),
    ADD COLUMN IF NOT EXISTS ciclo_numero INTEGER;

CREATE INDEX IF NOT EXISTS idx_eval_ciclo
    ON evaluaciones_desempeno (colaborador_id, ciclo_tipo, ciclo_numero);
