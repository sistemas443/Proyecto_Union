-- ============================================================================
-- Miniaturas de los iconos de las tarjetas de Consolidados
--
-- Se generan al subir la imagen y se incrustan en el HTML del indice para que
-- las tarjetas no tengan que pedir cada icono por separado.
--
-- Reversible:
--   ALTER TABLE consolidados_tarjetas DROP COLUMN icono_thumb;
--   ALTER TABLE consolidados_tarjetas DROP COLUMN icono_thumb_mime;
-- ============================================================================

ALTER TABLE consolidados_tarjetas
    ADD COLUMN IF NOT EXISTS icono_thumb bytea;

ALTER TABLE consolidados_tarjetas
    ADD COLUMN IF NOT EXISTS icono_thumb_mime varchar(60);
