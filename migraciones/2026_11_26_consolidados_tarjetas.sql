-- ============================================================================
-- Tarjetas de Consolidados: icono y titulo personalizados
--
-- Solo el rol Superadmin puede modificarlas. Si no hay fila para una tarjeta,
-- se usa el icono emoji y el titulo definidos en el codigo.
--
-- Reversible:
--   DROP TABLE consolidados_tarjetas;
-- ============================================================================

CREATE TABLE IF NOT EXISTS consolidados_tarjetas (
    clave           varchar(60) PRIMARY KEY,
    titulo          varchar(120),
    icono_data      bytea,
    icono_mime      varchar(60),
    icono_nombre    varchar(160),
    actualizado_en  timestamptz NOT NULL DEFAULT now(),
    actualizado_por integer
);

COMMENT ON TABLE consolidados_tarjetas IS
    'Icono y titulo personalizados de las tarjetas del indice de Consolidados';
COMMENT ON COLUMN consolidados_tarjetas.clave IS
    'Sufijo del endpoint de la tarjeta, por ejemplo primer_huevo';
